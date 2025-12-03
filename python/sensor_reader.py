# sensor_reader.py
import serial
import time
import json
import csv
from datetime import datetime
import os
import sys
import requests

class CompleteSensorSystem:
    def __init__(self, port='COM3', baudrate=115200):
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self.csv_file = None
        self.csv_writer = None
        
        # Estadísticas
        self.data_count = 0
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
        self.send_interval = 5  # Enviar cada 5 segundos
        self.session_start_time = None
        self.pasos_anteriores = 0
        
    def connect(self):
        """Conectar al puerto serial"""
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
            time.sleep(2)
            print(f"✅ Conectado a {self.port}")
            self.ser.reset_input_buffer()
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
        """Configurar archivo CSV para los dos sensores"""
        try:
            # Crear directorio si no existe
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            
            self.csv_file = open(filename, 'w', newline='', encoding='utf-8')
            self.csv_writer = csv.writer(self.csv_file)
            
            # ENCABEZADOS PARA LOS 2 SENSORES
            self.csv_writer.writerow([
                'timestamp', 
                
                # 📟 DATOS MAX30102 (SpO2 y Oxigenación)
                'spo2', 'ritmo_cardiaco', 'ir_value', 'red_value', 
                'finger_detected', 'spo2_buffer_ready',
                
                # 📊 DATOS MPU6050 (Acelerómetro y Pasos)
                'acel_x', 'acel_y', 'acel_z', 'acel_total',
                'gyro_x', 'gyro_y', 'gyro_z', 'temperatura_mpu',
                'pasos_totales', 'umbral_pasos', 'calibrado_pasos',
                
                # 🔧 ESTADO DE SENSORES
                'max30102_ok', 'mpu6050_ok'
            ])
            print(f"💾 Guardando datos en: {filename}")
            return True
        except Exception as e:
            print(f"❌ Error con CSV: {e}")
            return False
    
    def read_sensor_data(self):
        """Leer datos del serial"""
        if self.ser and self.ser.in_waiting > 0:
            try:
                line = self.ser.readline().decode('utf-8').strip()
                if line and line.startswith('{') and line.endswith('}'):
                    return line
            except UnicodeDecodeError:
                return None
            except Exception as e:
                print(f"⚠️ Error leyendo serial: {e}")
                return None
        return None
    
    def parse_json_data(self, data_line):
        """Convertir datos JSON a diccionario"""
        try:
            return json.loads(data_line)
        except json.JSONDecodeError as e:
            print(f"❌ Error JSON: {e}")
            print(f"   Datos: {data_line}")
            return None
    
    def get_spo2_status(self, spo2):
        """Obtener estado y color según nivel de SpO2"""
        if spo2 >= 95: 
            return "🟢 EXCELENTE", "green"
        elif spo2 >= 90: 
            return "🟡 NORMAL", "yellow"
        elif spo2 >= 85: 
            return "🟠 BAJO", "orange"
        else: 
            return "🔴 CRÍTICO", "red"
    
    def display_dashboard(self, data):
        """Mostrar dashboard completo en consola (2 sensores)"""
        if not data:
            return
            
        # 📟 DATOS SpO2
        spo2 = data.get('spo2', 0)
        ritmo = data.get('ritmo_cardiaco', 0)
        finger_detected = data.get('finger_detected', False)
        buffer_ready = data.get('spo2_buffer_ready', False)
        
        spo2_status, spo2_color = self.get_spo2_status(spo2)
        finger_icon = "👆" if finger_detected else "👈"
        buffer_icon = "✅" if buffer_ready else "⏳"
        
        # 📊 DATOS PASOS Y ACELERACIÓN
        pasos = data.get('pasos_totales', 0)
        acel_total = data.get('acel_total', 0)
        calibrado = data.get('calibrado', False)
        temperatura = data.get('temperatura', 0)
        
        calibrado_icon = "✓" if calibrado else "✗"
        
        # 📊 ESTADO SENSORES
        sensor_status = data.get('sensor_status', {})
        max30102_ok = sensor_status.get('max30102', False)
        mpu6050_ok = sensor_status.get('mpu6050', False)
        
        sensor_max = "✅" if max30102_ok else "❌"
        sensor_mpu = "✅" if mpu6050_ok else "❌"
        
        # ACTUALIZAR ESTADÍSTICAS
        self.total_pasos = pasos
        if spo2 > 0:
            self.max_spo2 = max(self.max_spo2, spo2)
            self.min_spo2 = min(self.min_spo2, spo2)
        
        # 🎯 DASHBOARD VISUAL
        print("\n" + "="*90)
        print("🎯 SISTEMA DE 2 SENSORES - MONITOREO EN TIEMPO REAL")
        print("="*90)
        
        # LÍNEA 1: SpO2 y Ritmo Cardiaco
        spo2_bars = int((spo2 - 70) / 3)  # Escala 70-100%
        spo2_bars = max(0, min(10, spo2_bars))
        
        print(f"📟 OXIGENACIÓN: {spo2:5.1f}% [{('█' * spo2_bars).ljust(10)}] {spo2_status}")
        print(f"❤️  RITMO: {ritmo:3d} bpm | Dedo: {finger_icon} | Buffer: {buffer_icon}")
        
        # LÍNEA 2: Pasos y Aceleración
        acel_bars = int((acel_total - 5) / 1.5)  # Escala 5-20 m/s²
        acel_bars = max(0, min(10, acel_bars))
        
        print(f"📊 PASOS: {pasos:4d} {calibrado_icon} | Acel: {acel_total:5.1f} m/s² [{('█' * acel_bars).ljust(10)}]")
        print(f"🌡️  TEMP: {temperatura:4.1f}°C | Sensores: MAX{sensor_max} MPU{sensor_mpu}")
        
        print("="*90)
    
    def save_to_csv(self, data):
        """Guardar datos en CSV (2 sensores)"""
        if self.csv_writer and data:
            try:
                timestamp = datetime.now().isoformat()
                sensor_status = data.get('sensor_status', {})
                
                self.csv_writer.writerow([
                    timestamp,
                    
                    # Datos MAX30102
                    data.get('spo2', 0),
                    data.get('ritmo_cardiaco', 0),
                    data.get('ir_value', 0),
                    data.get('red_value', 0),
                    1 if data.get('finger_detected') else 0,
                    1 if data.get('spo2_buffer_ready') else 0,
                    
                    # Datos MPU6050
                    data.get('acel_x', 0),
                    data.get('acel_y', 0),
                    data.get('acel_z', 0),
                    data.get('acel_total', 0),
                    data.get('gyro_x', 0),
                    data.get('gyro_y', 0),
                    data.get('gyro_z', 0),
                    data.get('temperatura', 0),
                    data.get('pasos_totales', 0),
                    data.get('umbral_pasos', 0),
                    1 if data.get('calibrado') else 0,
                    
                    # Estado sensores
                    1 if sensor_status.get('max30102') else 0,
                    1 if sensor_status.get('mpu6050') else 0
                ])
                self.csv_file.flush()
                return True
                
            except Exception as e:
                print(f"❌ Error guardando en CSV: {e}")
                return False
        return False
    
    def show_statistics(self):
        """Mostrar estadísticas finales"""
        print("\n" + "="*90)
        print("📈 ESTADÍSTICAS FINALES")
        print("="*90)
        print(f"📊 Total de datos registrados: {self.data_count}")
        print(f"🚶 Total de pasos contados: {self.total_pasos}")
        print(f"🩸 SpO2 - Máximo: {self.max_spo2:.1f}% | Mínimo: {self.min_spo2:.1f}%")
        
        if self.max_spo2 > 0:
            spo2_promedio = (self.max_spo2 + self.min_spo2) / 2
            print(f"📋 SpO2 promedio estimado: {spo2_promedio:.1f}%")
        
        print("="*90)
    
    def send_caminata(self, sensor_data):
        """Enviar datos de caminata al backend"""
        try:
            current_time = time.time()
            
            # Verificar si es tiempo de enviar
            if current_time - self.last_caminata_send < self.send_interval:
                return
            
            pasos = sensor_data.get('pasos_totales', 0)
            pasos_nuevos = pasos - self.pasos_anteriores
            
            # Calcular distancia basada en pasos (aproximadamente 0.0008 km por paso)
            km_recorridos = round((pasos_nuevos * 0.0008), 4)
            
            # Calcular calorías (aproximadamente 0.04 calorías por paso)
            calorias = round(pasos_nuevos * 0.04, 2)
            
            # Obtener tiempo de sesión
            tiempo_sesion = int(current_time - self.session_start_time) if self.session_start_time else 0
            
            data = {
                "km_recorridos": str(km_recorridos),
                "pasos": pasos_nuevos,
                "tiempo_actividad": str(tiempo_sesion),
                "velocidad_promedio": "0",
                "calorias_quemadas": str(calorias),
                "sesion": 1
            }
            
            headers = {'Content-Type': 'application/json'}
            
            response = requests.post(
                self.endpoint_caminata,
                json=data,
                headers=headers,
                timeout=5
            )
            
            if response.status_code in [200, 201]:
                print(f"✅ Datos de caminata enviados: {pasos_nuevos} pasos, {km_recorridos} km")
                self.pasos_anteriores = pasos
                self.last_caminata_send = current_time
            else:
                print(f"⚠️ Error enviando caminata (Status: {response.status_code})")
                
        except requests.exceptions.ConnectionError:
            print(f"⚠️ No se pudo conectar al servidor {self.api_base_url}")
        except Exception as e:
            print(f"⚠️ Error enviando datos de caminata: {e}")
    
    def send_corazon(self, sensor_data):
        """Enviar datos de corazón al backend"""
        try:
            current_time = time.time()
            
            # Verificar si es tiempo de enviar
            if current_time - self.last_corazon_send < self.send_interval:
                return
            
            spo2 = sensor_data.get('spo2', 0)
            ritmo = sensor_data.get('ritmo_cardiaco', 0)
            
            now = datetime.now()
            
            data = {
                "ritmo_cardiaco": int(ritmo),
                "presion": "90",
                "oxigenacion": str(round(spo2, 2)),
                "fecha": now.strftime('%Y-%m-%d'),
                "hora": now.strftime('%H%M%S'),
                "sesion": 1
            }
            
            headers = {'Content-Type': 'application/json'}
            
            response = requests.post(
                self.endpoint_corazon,
                json=data,
                headers=headers,
                timeout=5
            )
            
            if response.status_code in [200, 201]:
                print(f"✅ Datos de corazón enviados: {ritmo} bpm, SpO2: {spo2:.1f}%")
                self.last_corazon_send = current_time
            else:
                print(f"⚠️ Error enviando corazón (Status: {response.status_code})")
                
        except requests.exceptions.ConnectionError:
            print(f"⚠️ No se pudo conectar al servidor {self.api_base_url}")
        except Exception as e:
            print(f"⚠️ Error enviando datos de corazón: {e}")
    
    def run(self):
        """Ejecutar sistema de 2 sensores"""
        if not self.connect():
            return
        
        if not self.setup_csv():
            return
        
        # Inicializar tiempo de sesión
        self.session_start_time = time.time()
        
        try:
            print("\n🎯 SISTEMA DE 2 SENSORES INICIADO")
            print("📡 Monitoreando sensores:")
            print("   1. 📟 MAX30102 - Oxigenación (SpO2) y Ritmo Cardiaco")
            print("   2. 📊 MPU6050  - Aceleración, Pasos y Temperatura")
            print("\n👆 INSTRUCCIONES SpO2:")
            print("   - Coloca la YEMA del dedo en el sensor MAX30102")
            print("   - Presiona FIRMEMENTE y mantén 15-30 segundos")
            print("   - Los valores se estabilizarán gradualmente")
            print("\n🚶 INSTRUCCIONES Pasos:")
            print("   - Camina normalmente con el dispositivo")
            print("   - Los pasos se contarán automáticamente")
            print("\n⏱️  Iniciando monitoreo... (Ctrl+C para detener)")
            
            last_dashboard_time = 0
            dashboard_interval = 2  # Segundos entre actualizaciones
            
            while True:
                data_line = self.read_sensor_data()
                
                if data_line:
                    sensor_data = self.parse_json_data(data_line)
                    
                    if sensor_data:
                        # Mostrar dashboard cada X segundos
                        current_time = time.time()
                        if current_time - last_dashboard_time >= dashboard_interval:
                            self.display_dashboard(sensor_data)
                            last_dashboard_time = current_time
                        
                        # Guardar en CSV
                        if self.save_to_csv(sensor_data):
                            self.data_count += 1
                        
                        # Enviar datos al backend
                        self.send_caminata(sensor_data)
                        self.send_corazon(sensor_data)
                
                # Mostrar progreso cada 50 datos
                if self.data_count > 0 and self.data_count % 50 == 0:
                    print(f"\n📈 Progreso: {self.data_count} datos registrados...")
                
                time.sleep(0.1)  # Pequeña pausa
                
        except KeyboardInterrupt:
            print(f"\n🛑 Sistema detenido por el usuario")
            self.show_statistics()
            
        except Exception as e:
            print(f"\n💥 Error inesperado: {e}")
            
        finally:
            # Cerrar conexiones
            if self.ser:
                self.ser.close()
            if self.csv_file:
                self.csv_file.close()
            print("👋 Recursos liberados - Sistema finalizado")

def find_arduino_port():
    """Intentar encontrar el puerto del Arduino automáticamente"""
    try:
        import serial.tools.list_ports
        ports = list(serial.tools.list_ports.comports())
        for port in ports:
            if any(keyword in port.description.lower() for keyword in 
                  ['arduino', 'usb', 'serial', 'ch340', 'cp210', 'esp32']):
                return port.device
    except:
        pass
    return None

if __name__ == "__main__":
    # Detectar puerto automáticamente
    port = find_arduino_port()
    if not port:
        port = 'COM3'  # Puerto por defecto para Windows
        # port = '/dev/ttyUSB0'  # Para Linux
        # port = '/dev/tty.usbserial'  # Para Mac
    
    print(f"🔍 Buscando Arduino en: {port}")
    
    # Crear y ejecutar sistema
    system = CompleteSensorSystem(port=port)
    system.run()