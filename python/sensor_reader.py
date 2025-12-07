# sensor_reader.py - VERSIÓN CORREGIDA
import serial
import time
import json
import csv
from datetime import datetime
import os
import sys
import requests
import threading
from collections import deque


class CompleteSensorSystem:
    def __init__(self, port='COM3', baudrate=115200):
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self.csv_file = None
        self.csv_writer = None

        # Buffer de datos para procesamiento en tiempo real
        self.data_buffer = deque(maxlen=10)  # Últimos 10 datos
        self.last_valid_data = None
        self.data_count = 0

        # Estadísticas
        self.total_pasos = 0
        self.max_spo2 = 0
        self.min_spo2 = 100

        # Configuración de API
        self.api_base_url = "http://127.0.0.1:8000"
        self.endpoint_caminata = f"{self.api_base_url}/metrics/caminata/"
        self.endpoint_corazon = f"{self.api_base_url}/metrics/corazon/"

        # Control de tiempo para envíos
        self.last_caminata_send = 0
        self.last_corazon_send = 0
        # REDUCIDO: Enviar cada 3 segundos (más rápido para gráficas)
        self.send_interval = 3
        self.session_start_time = None
        self.pasos_anteriores = 0

        # Estado del sistema
        self.running = True
        self.finger_last_state = False
        self.finger_state_changed_time = 0

        # Hilos separados para lectura y procesamiento
        self.read_thread = None
        self.process_thread = None

        # Mejora: Tiempo de espera reducido para detección rápida
        self.no_finger_timeout = 1.0  # 1 segundo sin dedo = reset
        self.last_finger_time = 0

    def connect(self):
        """Conectar al puerto serial CON CONFIGURACIÓN OPTIMIZADA"""
        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=0.1,  # Timeout MUY corto para lectura rápida
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                xonxoff=False,
                rtscts=False,
                dsrdtr=False
            )

            # Limpiar buffers
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()

            # Configuración para lectura no bloqueante
            self.ser.set_buffer_size(rx_size=128)  # Buffer pequeño

            time.sleep(1)  # Espera mínima para estabilización
            print(f"✅ Conectado a {self.port}")
            print(
                f"⚡ Configuración: timeout={self.ser.timeout}s, baudrate={self.baudrate}")
            return True
        except serial.SerialException as e:
            print(f"❌ Error conectando: {e}")
            print("🔍 Puertos disponibles:")
            self.list_serial_ports()
            return False

    def list_serial_ports(self):
        """Listar puertos seriales disponibles"""
        try:
            import serial.tools.list_ports
            ports = serial.tools.list_ports.comports()
            if ports:
                for port in ports:
                    print(f"   - {port.device}: {port.description}")
            else:
                print("   - No se encontraron puertos seriales")
        except:
            print("   - No se pudieron listar los puertos")

    def setup_csv(self, filename='../datos/sensores_completos.csv'):
        """Configurar archivo CSV optimizado"""
        try:
            # Crear directorio si no existe
            os.makedirs(os.path.dirname(filename), exist_ok=True)

            self.csv_file = open(filename, 'w', newline='', encoding='utf-8')
            self.csv_writer = csv.writer(self.csv_file)

            # ENCABEZADOS SIMPLIFICADOS PARA RENDIMIENTO
            self.csv_writer.writerow([
                'timestamp', 'spo2', 'ritmo_cardiaco', 'ir_value', 'red_value',
                'finger_detected', 'acel_total', 'pasos_totales',
                'max30102_ok', 'mpu6050_ok'
            ])
            print(f"💾 Guardando datos en: {filename}")
            return True
        except Exception as e:
            print(f"❌ Error con CSV: {e}")
            return False

    def read_from_serial(self):
        """Hilo dedicado a lectura continua del puerto serial"""
        print("📡 Iniciando hilo de lectura serial...")

        buffer = ""
        while self.running:
            try:
                if self.ser and self.ser.in_waiting > 0:
                    # Leer todo lo disponible
                    raw_data = self.ser.read(self.ser.in_waiting).decode(
                        'utf-8', errors='ignore')
                    buffer += raw_data

                    # Procesar líneas completas
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        line = line.strip()

                        if line and line.startswith('{') and line.endswith('}'):
                            # Agregar al buffer para procesamiento inmediato
                            self.data_buffer.append({
                                'raw': line,
                                'timestamp': time.time()
                            })

                # Pequeña pausa para no saturar CPU
                time.sleep(0.01)

            except Exception as e:
                print(f"⚠️ Error en lectura serial: {e}")
                time.sleep(0.1)

    def process_data(self):
        """Hilo dedicado a procesamiento de datos"""
        print("⚡ Iniciando hilo de procesamiento...")

        while self.running:
            try:
                # Procesar todos los datos en el buffer
                while self.data_buffer:
                    data_item = self.data_buffer.popleft()
                    line = data_item['raw']

                    # Parsear JSON rápidamente
                    try:
                        sensor_data = json.loads(line)
                    except json.JSONDecodeError:
                        continue  # Ignorar datos corruptos

                    # PROCESAMIENTO EN TIEMPO REAL
                    current_time = time.time()

                    # 1. NO forzar valores a 0 - dejar que ESP32 controle
                    # Esto permite ver transiciones naturales en gráficas

                    # 2. Actualizar estadísticas
                    spo2 = sensor_data.get('spo2', 0)
                    if spo2 > 0:
                        self.max_spo2 = max(self.max_spo2, spo2)
                        self.min_spo2 = min(self.min_spo2, spo2)

                    self.total_pasos = sensor_data.get('pasos_totales', 0)

                    # 3. Guardar último dato válido
                    self.last_valid_data = sensor_data
                    self.data_count += 1

                    # 4. Mostrar dashboard
                    self.display_dashboard_realtime(sensor_data)

                    # 5. Guardar en CSV
                    self.save_to_csv_fast(sensor_data)

                    # 6. Enviar a API SIEMPRE (controlado por tiempo)
                    self.send_to_api_if_ready(sensor_data, current_time)

                # Pequeña pausa si no hay datos
                time.sleep(0.01)

            except Exception as e:
                print(f"⚠️ Error en procesamiento: {e}")
                time.sleep(0.1)

    def display_dashboard_realtime(self, data):
        """Dashboard optimizado para tiempo real"""
        if not data:
            return

        spo2 = data.get('spo2', 0)
        ritmo = data.get('ritmo_cardiaco', 0)
        finger_detected = data.get('finger_detected', False)
        pasos = data.get('pasos_totales', 0)
        acel_total = data.get('acel_total', 0)
        is_moving = data.get('is_moving', False)
        ir_value = data.get('ir_value', 0)

        # Limpiar consola
        print("\033[H\033[J")

        print("="*60)
        print("🎯 SISTEMA DE SENSORES - TIEMPO REAL")
        print("="*60)

        # Estado sensores
        sensor_status = "✅ AMBOS OK"
        if ir_value == 0 and not finger_detected:
            sensor_status = "👆 PON DEDO EN MAX30105"

        print(f"🔧 Estado: {sensor_status}")
        print("-"*60)

        # Datos MAX30105
        if finger_detected:
            print(f"📟 MAX30105 - Dedo: 👆 DETECTADO")
            print(f"   SpO2: {spo2:5.1f}% | Ritmo: {ritmo:3d} bpm")
            print(f"   IR: {ir_value:,} | Rojo: {data.get('red_value', 0):,}")
        else:
            print(f"📟 MAX30105 - Dedo: 👈 NO DETECTADO")
            print(f"   SpO2: {spo2:5.1f}% | Ritmo: {ritmo:3d} bpm")
            print(f"   IR: {ir_value:,}")

        print("-"*60)

        # Datos MPU6050
        moving_icon = "🚀 MOVIÉNDOSE" if is_moving else "💤 QUIETO"
        print(f"📊 MPU6050 - {moving_icon}")
        print(f"   Aceleración: {acel_total:5.2f} m/s²")
        print(f"   Pasos totales: {pasos}")
        print(f"   Temperatura: {data.get('temperatura', 0):4.1f}°C")

        print("-"*60)
        print(f"📈 Datos procesados: {self.data_count}")
        print("="*60)
        print("\nPresiona Ctrl+C para salir")

    def save_to_csv_fast(self, data):
        """Guardar en CSV optimizado"""
        if self.csv_writer and data:
            try:
                timestamp = datetime.now().isoformat()
                sensor_status = data.get('sensor_status', {})

                # Solo guardar campos esenciales para velocidad
                self.csv_writer.writerow([
                    timestamp,
                    data.get('spo2', 0),
                    data.get('ritmo_cardiaco', 0),
                    data.get('ir_value', 0),
                    data.get('red_value', 0),
                    1 if data.get('finger_detected') else 0,
                    data.get('acel_total', 0),
                    data.get('pasos_totales', 0),
                    1 if sensor_status.get('max30102', False) else 0,
                    1 if sensor_status.get('mpu6050', False) else 0
                ])

                # Flush cada 10 registros
                if self.data_count % 10 == 0:
                    self.csv_file.flush()

            except Exception as e:
                print(f"⚠️ Error guardando CSV: {e}")

    def send_to_api_if_ready(self, sensor_data, current_time):
        """Enviar a API si es tiempo (no bloqueante)"""
        try:
            # Enviar datos de caminata
            if current_time - self.last_caminata_send >= self.send_interval:
                self.send_caminata_background(sensor_data, current_time)

            # Enviar datos de corazón
            if current_time - self.last_corazon_send >= self.send_interval:
                self.send_corazon_background(sensor_data, current_time)

        except Exception as e:
            print(f"⚠️ Error preparando envío API: {e}")

    def send_caminata_background(self, sensor_data, current_time):
        """Enviar datos de caminata en segundo plano"""
        def send_thread():
            try:
                pasos = sensor_data.get('pasos_totales', 0)
                pasos_nuevos = pasos - self.pasos_anteriores

                # Enviar SIEMPRE, incluso si pasos_nuevos es 0
                # Esto mantiene la conexión activa

                km_recorridos = round((max(pasos_nuevos, 0) * 0.08), 4)
                calorias = round((max(pasos_nuevos, 0) * 0.04), 2)

                data = {
                    "km_recorridos": str(km_recorridos),
                    "pasos": max(pasos_nuevos, 0),
                    "tiempo_actividad": str(int(time.time() - self.session_start_time)),
                    "velocidad_promedio": "0",
                    "calorias_quemadas": str(calorias),
                    "sesion": 1
                }

                response = requests.post(
                    self.endpoint_caminata,
                    json=data,
                    headers={'Content-Type': 'application/json'},
                    timeout=2
                )

                if response.status_code in [200, 201]:
                    if pasos_nuevos > 0:
                        print(f"✅ API Caminata: {pasos_nuevos} pasos enviados")
                    # No mostrar mensaje si es 0 para no saturar consola
                else:
                    print(f"⚠️ API Caminata error: {response.status_code}")

                self.pasos_anteriores = pasos
                self.last_caminata_send = current_time

            except requests.exceptions.ConnectionError:
                print("⚠️ No hay conexión al servidor")
            except Exception as e:
                print(f"⚠️ Error API Caminata: {e}")

        # Ejecutar en hilo separado
        thread = threading.Thread(target=send_thread, daemon=True)
        thread.start()

    def send_corazon_background(self, sensor_data, current_time):
        """Enviar datos de corazón en segundo plano - CORREGIDO"""
        def send_thread():
            try:
                spo2 = sensor_data.get('spo2', 0)
                ritmo = sensor_data.get('ritmo_cardiaco', 0)
                finger_detected = sensor_data.get('finger_detected', False)

                # ENVIAR SIEMPRE, incluso si son 0
                # Esto hará que las gráficas muestren la bajada a 0

                now = datetime.now()
                data = {
                    "ritmo_cardiaco": int(ritmo),
                    "presion": "90",  # Valor fijo para demo
                    "oxigenacion": str(round(spo2, 2)),
                    "fecha": now.strftime('%Y-%m-%d'),
                    "hora": now.strftime('%H%M%S'),
                    "sesion": 1
                }

                response = requests.post(
                    self.endpoint_corazon,
                    json=data,
                    headers={'Content-Type': 'application/json'},
                    timeout=2
                )

                if response.status_code in [200, 201]:
                    if ritmo > 0 or spo2 > 0:
                        print(f"✅ API Corazón: {ritmo} bpm, {spo2:.1f}% SpO2")
                    else:
                        # Solo mostrar cada 5 envíos cuando es 0 para no saturar
                        if int(current_time) % 15 < 3:  # Cada ~15 segundos
                            print(f"📉 API: Sin dedo (0 bpm, 0% SpO2)")
                else:
                    print(f"⚠️ API Corazón error: {response.status_code}")

                self.last_corazon_send = current_time

            except requests.exceptions.ConnectionError:
                print("⚠️ No hay conexión al servidor")
            except Exception as e:
                print(f"⚠️ Error API Corazón: {e}")

        # CORRECCIÓN: Esta línea debe estar DENTRO de la función, no fuera
        thread = threading.Thread(target=send_thread, daemon=True)
        thread.start()

    def run(self):
        """Ejecutar sistema optimizado"""
        if not self.connect():
            return

        if not self.setup_csv():
            return

        # Inicializar tiempo de sesión
        self.session_start_time = time.time()
        self.last_finger_time = time.time()

        try:
            print("\n" + "="*60)
            print("🎯 SISTEMA PARA GRÁFICAS EN TIEMPO REAL")
            print("="*60)
            print("📟 MAX30105: Pulso y Oxigenación")
            print("📊 MPU6050:  Pasos y Movimiento")
            print("\n⚡ CONFIGURACIÓN:")
            print("   • Envío API cada 3 segundos")
            print("   • Dashboard actualizado en tiempo real")
            print("   • Valores 0 también se envían")
            print("\n👆 INSTRUCCIONES:")
            print("   - Pon/quita dedo para ver transiciones en gráficas")
            print("   - Agita sensor para contar pasos")
            print("   - Ctrl+C para salir")
            print("\n⏱️  Iniciando monitoreo...")
            print("="*60)

            # Iniciar hilos
            self.running = True
            self.read_thread = threading.Thread(
                target=self.read_from_serial, daemon=True)
            self.process_thread = threading.Thread(
                target=self.process_data, daemon=True)

            self.read_thread.start()
            self.process_thread.start()

            # Mantener hilo principal activo
            while self.running:
                # Mostrar estadísticas cada 30 segundos
                time.sleep(30)
                self.show_statistics_brief()

        except KeyboardInterrupt:
            print("\n🛑 Sistema detenido por el usuario")
            self.stop()

        except Exception as e:
            print(f"\n💥 Error inesperado: {e}")
            self.stop()

        finally:
            self.cleanup()

    def show_statistics_brief(self):
        """Mostrar estadísticas breves"""
        print("\n" + "="*60)
        print("📊 ESTADÍSTICAS ACTUALES")
        print("="*60)
        print(f"Datos procesados: {self.data_count}")
        print(f"Pasos totales: {self.total_pasos}")
        if self.max_spo2 > 0:
            print(f"SpO2: {self.min_spo2:.1f}% - {self.max_spo2:.1f}%")
        print("="*60)

    def stop(self):
        """Detener el sistema"""
        self.running = False
        time.sleep(0.5)  # Dar tiempo a los hilos para terminar

    def cleanup(self):
        """Limpiar recursos"""
        print("\n🧹 Limpiando recursos...")

        if self.ser and self.ser.is_open:
            self.ser.close()
            print("✅ Puerto serial cerrado")

        if self.csv_file:
            self.csv_file.close()
            print("✅ Archivo CSV guardado")

        print(f"\n📈 RESUMEN FINAL:")
        print(f"   • Datos procesados: {self.data_count}")
        print(f"   • Pasos contados: {self.total_pasos}")
        if self.max_spo2 > 0:
            print(
                f"   • SpO2 rango: {self.min_spo2:.1f}% - {self.max_spo2:.1f}%")

        print("\n👋 Sistema finalizado")


def find_arduino_port():
    """Encontrar puerto automáticamente"""
    try:
        import serial.tools.list_ports
        ports = list(serial.tools.list_ports.comports())
        for port in ports:
            desc_lower = port.description.lower()
            if any(keyword in desc_lower for keyword in
                   ['arduino', 'ch340', 'cp210', 'ftdi', 'usb', 'serial', 'esp32']):
                print(f"🔍 Detectado: {port.device} - {port.description}")
                return port.device
    except:
        pass

    # Puertos por defecto según sistema operativo
    import platform
    system = platform.system()

    if system == 'Windows':
        return 'COM3'
    elif system == 'Linux':
        return '/dev/ttyUSB0'
    elif system == 'Darwin':  # macOS
        return '/dev/tty.usbserial'

    return 'COM3'


if __name__ == "__main__":
    # Configuración optimizada
    port = find_arduino_port()
    baudrate = 115200

    print(f"\n🔌 Configuración:")
    print(f"   Puerto: {port}")
    print(f"   Baudrate: {baudrate}")
    print(f"   Envío API: cada 3 segundos")
    print(f"   Dashboard: tiempo real")

    # Crear y ejecutar sistema
    system = CompleteSensorSystem(port=port, baudrate=baudrate)

    try:
        system.run()
    except Exception as e:
        print(f"\n💥 Error crítico: {e}")
        system.cleanup()
