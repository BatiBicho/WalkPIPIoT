# test_connection.py
import serial
import time

def test_serial():
    ports = ['COM3', 'COM4', 'COM5', 'COM6']  # Puertos comunes en Windows
    # ports = ['/dev/ttyUSB0', '/dev/ttyUSB1', '/dev/ttyACM0']  # Para Linux
    
    for port in ports:
        try:
            print(f"Probando {port}...")
            ser = serial.Serial(port, 115200, timeout=2)
            time.sleep(2)
            
            print(f"✅ Conectado a {port}")
            print("Leyendo datos... (5 segundos)")
            
            start_time = time.time()
            while time.time() - start_time < 5:
                if ser.in_waiting > 0:
                    line = ser.readline().decode('utf-8').strip()
                    print(f"   {line}")
                time.sleep(0.1)
                
            ser.close()
            break
            
        except serial.SerialException:
            print(f"❌ No se pudo conectar a {port}")
        except Exception as e:
            print(f"⚠️  Error en {port}: {e}")

if __name__ == "__main__":
    test_serial()