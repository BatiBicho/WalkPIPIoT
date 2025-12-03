# debug_serial.py
import serial
import time
import json

def debug_serial(port='COM3', baudrate=115200):
    try:
        ser = serial.Serial(port, baudrate, timeout=1)
        print(f"✅ Conectado a {port}")
        time.sleep(2)  # Esperar inicialización
        
        print("🔍 Esperando datos... (Presiona Ctrl+C para detener)")
        print("-" * 50)
        
        timeout = time.time() + 10  # 10 segundos de timeout
        data_received = False
        
        while time.time() < timeout:
            # Verificar cuántos bytes hay disponibles
            bytes_waiting = ser.in_waiting
            if bytes_waiting > 0:
                print(f"📨 Bytes disponibles: {bytes_waiting}")
                
                # Leer toda la data disponible
                raw_data = ser.read(bytes_waiting)
                print(f"📦 Datos crudos (hex): {raw_data.hex()}")
                
                try:
                    # Intentar decodificar como texto
                    text_data = raw_data.decode('utf-8')
                    print(f"📝 Datos como texto: '{text_data}'")
                    
                    # Probar diferentes separadores de línea
                    lines = text_data.split('\n')
                    for i, line in enumerate(lines):
                        line = line.strip()
                        if line:
                            print(f"   Línea {i+1}: '{line}'")
                            # Intentar parsear como JSON
                            if line.startswith('{') and line.endswith('}'):
                                try:
                                    parsed = json.loads(line)
                                    print(f"   ✅ JSON válido: {parsed}")
                                except json.JSONDecodeError as e:
                                    print(f"   ❌ JSON inválido: {e}")
                    
                    data_received = True
                    
                except UnicodeDecodeError:
                    print("❌ No se pudo decodificar como UTF-8")
                    
            else:
                print("⏳ No hay datos disponibles...", end='\r')
                time.sleep(0.5)
        
        if not data_received:
            print("\n❌ No se recibieron datos en 10 segundos")
            print("\n🔧 Soluciones posibles:")
            print("   1. Verifica que el Arduino esté programado correctamente")
            print("   2. Revisa que uses el mismo baudrate (115200)")
            print("   3. Verifica los cables de conexión")
            print("   4. Prueba reiniciar el Arduino")
        
        ser.close()
        
    except serial.SerialException as e:
        print(f"❌ Error de conexión: {e}")

if __name__ == "__main__":
    debug_serial('COM3')  # Cambia por tu puerto