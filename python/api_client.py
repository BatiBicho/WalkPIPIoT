"""
Cliente para enviar datos a la API de Django desde el sensor reader.
"""
import requests
import time
import json
from datetime import datetime
from typing import Dict, Any, Optional

# Configuración de la API
API_BASE_URL = "http://127.0.0.1:8000"  # Cambia esto si tu Django está en otro puerto
ENDPOINT_CAMINATA = f"{API_BASE_URL}/metrics/caminata/"
ENDPOINT_CORAZON = f"{API_BASE_URL}/metrics/corazon/"

# Configuración de reintentos
MAX_RETRIES = 3
RETRY_DELAY = 2  # segundos
TIMEOUT = 5  # segundos

# Cache para evitar envíos duplicados muy seguidos
_last_sent_data = {
    'caminata': None,
    'corazon': None,
    'timestamp': 0
}

def _should_send_data(data_type: str, new_data: Dict[str, Any]) -> bool:
    """
    Verifica si se debe enviar los datos (evita duplicados).
    """
    current_time = time.time()
    last_data = _last_sent_data[data_type]
    
    # Si no hay datos previos, enviar
    if last_data is None:
        return True
    
    # Si han pasado más de 1.5 segundos desde el último envío
    if current_time - _last_sent_data['timestamp'] < 1.5:
        return False
    
    # Comparar datos (para evitar envíos duplicados)
    if json.dumps(new_data, sort_keys=True) == json.dumps(last_data, sort_keys=True):
        return False
    
    return True

def _send_request(endpoint: str, data: Dict[str, Any]) -> bool:
    """
    Envía una solicitud POST a la API con reintentos.
    """
    headers = {
        'Content-Type': 'application/json',
        'User-Agent': 'SensorReader/1.0'
    }
    
    for attempt in range(MAX_RETRIES):
        try:
            print(f"📤 Enviando a {endpoint} (intento {attempt + 1}/{MAX_RETRIES})...")
            
            response = requests.post(
                endpoint,
                json=data,
                headers=headers,
                timeout=TIMEOUT
            )
            
            if response.status_code in [200, 201]:
                print(f"✅ Datos enviados exitosamente (Status: {response.status_code})")
                return True
            else:
                print(f"⚠️ Error en respuesta (Status: {response.status_code}): {response.text}")
                
                # Si es error del servidor, reintentar
                if response.status_code >= 500:
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(RETRY_DELAY)
                        continue
                
                return False
                
        except requests.exceptions.ConnectionError:
            print(f"❌ No se pudo conectar al servidor {API_BASE_URL}")
            if attempt < MAX_RETRIES - 1:
                print(f"⏳ Reintentando en {RETRY_DELAY} segundos...")
                time.sleep(RETRY_DELAY)
                continue
            return False
            
        except requests.exceptions.Timeout:
            print(f"⏱️ Timeout al conectar con el servidor")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
                continue
            return False
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Error de red: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
                continue
            return False
            
        except Exception as e:
            print(f"❌ Error inesperado: {e}")
            return False
    
    return False

def _prepare_caminata_data(sensor_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Prepara los datos de caminata para enviar a la API.
    """
    gps_speed = sensor_data.get('gps_speed', 0)
    pasos = sensor_data.get('pasos_totales', 0)
    
    # Calcular distancia basada en velocidad (si hay GPS)
    if gps_speed > 0:
        # Asumimos intervalo de 2 segundos entre envíos
        km_recorridos = round((gps_speed * 2) / 3600, 4)
    else:
        # Estimación basada en pasos (aproximadamente 0.0008 km por paso)
        km_recorridos = round(pasos * 0.0008, 4)
    
    # Calcular calorías (aproximadamente 0.04 calorías por paso)
    calorias_quemadas = round(pasos * 0.04, 2)
    
    return {
        "km_recorridos": str(km_recorridos),
        "pasos": pasos,
        "tiempo_actividad": "00:00:02",  # Intervalo de envío
        "velocidad_promedio": str(round(gps_speed, 2)),
        "calorias_quemadas": str(calorias_quemadas),
        "sesion": 1  # Por defecto, puedes cambiarlo si tienes múltiples sesiones
    }

def _prepare_corazon_data(sensor_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Prepara los datos de corazón para enviar a la API.
    """
    now = datetime.now()
    
    return {
        "ritmo_cardiaco": sensor_data.get('ritmo_cardiaco', 0),
        "presion": "120/80",  # Valor por defecto (puedes ajustar si tienes sensor de presión)
        "oxigenacion": str(round(sensor_data.get('spo2', 0), 2)),
        "fecha": now.strftime('%Y-%m-%d'),
        "hora": now.strftime('%H:%M:%S'),
        "sesion": 1  # Por defecto, puedes cambiarlo si tienes múltiples sesiones
    }

def send_caminata(sensor_data: Dict[str, Any]) -> bool:
    """
    Envía datos de caminata a la API.
    
    Args:
        sensor_data: Diccionario con los datos del sensor
        
    Returns:
        bool: True si se envió exitosamente, False en caso contrario
    """
    try:
        # Preparar datos
        caminata_data = _prepare_caminata_data(sensor_data)
        
        # Verificar si se debe enviar (evitar duplicados)
        if not _should_send_data('caminata', caminata_data):
            print("⏭️  Datos de caminata similares, omitiendo envío...")
            return True
        
        # Enviar datos
        success = _send_request(ENDPOINT_CAMINATA, caminata_data)
        
        if success:
            # Actualizar cache
            _last_sent_data['caminata'] = caminata_data
            _last_sent_data['timestamp'] = time.time()
        
        return success
        
    except Exception as e:
        print(f"❌ Error preparando datos de caminata: {e}")
        return False

def send_corazon(sensor_data: Dict[str, Any]) -> bool:
    """
    Envía datos de corazón a la API.
    
    Args:
        sensor_data: Diccionario con los datos del sensor
        
    Returns:
        bool: True si se envió exitosamente, False en caso contrario
    """
    try:
        # Preparar datos
        corazon_data = _prepare_corazon_data(sensor_data)
        
        # Verificar si se debe enviar (evitar duplicados)
        if not _should_send_data('corazon', corazon_data):
            print("⏭️  Datos de corazón similares, omitiendo envío...")
            return True
        
        # Enviar datos
        success = _send_request(ENDPOINT_CORAZON, corazon_data)
        
        if success:
            # Actualizar cache
            _last_sent_data['corazon'] = corazon_data
            _last_sent_data['timestamp'] = time.time()
        
        return success
        
    except Exception as e:
        print(f"❌ Error preparando datos de corazón: {e}")
        return False

def test_connection() -> bool:
    """
    Prueba la conexión con la API.
    
    Returns:
        bool: True si la conexión es exitosa, False en caso contrario
    """
    try:
        print("🔍 Probando conexión con la API...")
        
        # Intentar conectar al endpoint de caminata
        response = requests.get(f"{API_BASE_URL}/metrics/caminata/", timeout=3)
        
        if response.status_code == 200:
            print(f"✅ Conexión exitosa con la API en {API_BASE_URL}")
            return True
        else:
            print(f"⚠️ API respondió con código: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"❌ No se pudo conectar a {API_BASE_URL}")
        print("   Asegúrate de que Django esté ejecutándose:")
        print("   $ python manage.py runserver")
        return False
        
    except Exception as e:
        print(f"❌ Error probando conexión: {e}")
        return False

def clear_cache():
    """
    Limpia la cache de datos enviados.
    Útil para forzar un nuevo envío.
    """
    global _last_sent_data
    _last_sent_data = {
        'caminata': None,
        'corazon': None,
        'timestamp': 0
    }
    print("🗑️  Cache limpiada")

# Función principal para pruebas
if __name__ == "__main__":
    print("🧪 Probando api_client.py")
    
    # Probar conexión
    if not test_connection():
        print("❌ No se pudo establecer conexión. Verifica que Django esté ejecutándose.")
        exit(1)
    
    # Datos de prueba
    test_sensor_data = {
        'gps_speed': 5.5,
        'pasos_totales': 100,
        'ritmo_cardiaco': 75,
        'spo2': 98.5,
        'finger_detected': True
    }
    
    print("\n📤 Enviando datos de prueba...")
    
    # Enviar datos de caminata
    print("\n--- Enviando datos de caminata ---")
    success_caminata = send_caminata(test_sensor_data)
    
    # Enviar datos de corazón
    print("\n--- Enviando datos de corazón ---")
    success_corazon = send_corazon(test_sensor_data)
    
    # Resultados
    print("\n" + "="*50)
    print("RESULTADOS DE PRUEBA:")
    print(f"Caminata: {'✅ Éxito' if success_caminata else '❌ Fallo'}")
    print(f"Corazón:  {'✅ Éxito' if success_corazon else '❌ Fallo'}")
    
    if success_caminata and success_corazon:
        print("\n🎉 ¡Todas las pruebas pasaron!")
        print("El sensor reader puede enviar datos a Django.")
    else:
        print("\n⚠️  Algunas pruebas fallaron.")
        print("Verifica que los endpoints estén correctamente configurados en Django.")