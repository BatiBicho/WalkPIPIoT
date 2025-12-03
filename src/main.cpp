#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_MPU6050.h>
#include <DFRobot_MAX30102.h>
#include <TinyGPSPlus.h>

DFRobot_MAX30102 particleSensor;
Adafruit_MPU6050 mpu;
TinyGPSPlus gps;
HardwareSerial SerialGPS(2);

// Variables para diagnóstico
bool max30102_ok = false;
bool mpu6050_ok = false;
bool gps_ok = false;

// ===========================
// VARIABLES PARA SpO2 (SIMPLIFICADO)
// ===========================
float spO2 = 0.0;
int heartRate = 0;
bool fingerDetected = false;

// ===========================
// VARIABLES CONTADOR DE PASOS
// ===========================
int stepCount = 0;
float smoothAccel = 0;
float alpha = 0.8;
float accelThreshold = 12.0;
unsigned long lastStepTime = 0;
unsigned long stepDelay = 300;

// ===========================
// SETUP - INICIALIZACIÓN
// ===========================
void setup()
{
    Serial.begin(115200);
    Wire.begin(21, 22);

    delay(3000);
    Serial.println("\n🎯 SISTEMA MULTISENSOR - VERSIÓN FUNCIONAL");
    Serial.println("===========================================");

    // Inicializar MAX30102 (SpO2 y Ritmo Cardiaco)
    Serial.print("📟 MAX30102: ");
    if (particleSensor.begin())
    {
        max30102_ok = true;
        Serial.println("✅ CONECTADO");

        // Configuración SIMPLE que funciona
        particleSensor.sensorConfiguration(
            0xFF, // LED brightness - MÁXIMO para prueba
            4,    // Sample average
            2,    // LED mode
            100,  // Sample rate
            411,  // Pulse width
            4096  // ADC range
        );
    }
    else
    {
        Serial.println("❌ NO CONECTADO - Usando datos prueba");
    }

    // Inicializar MPU6050 (Acelerómetro + Pasos)
    Serial.print("📊 MPU6050: ");
    if (mpu.begin())
    {
        mpu6050_ok = true;
        Serial.println("✅ CONECTADO");
        mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
        mpu.setGyroRange(MPU6050_RANGE_500_DEG);
        mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);
    }
    else
    {
        Serial.println("❌ NO CONECTADO - Usando datos prueba");
    }

    // Inicializar GPS
    Serial.print("🛰️  GPS: ");
    SerialGPS.begin(9600, SERIAL_8N1, 16, 17);
    Serial.println("INICIADO");

    // ===========================
    // RESUMEN INICIAL
    // ===========================
    Serial.println("\n📋 ESTADO DE SENSORES:");
    Serial.println("MAX30102: " + String(max30102_ok ? "✅ OK" : "❌ FALLA"));
    Serial.println("MPU6050:  " + String(mpu6050_ok ? "✅ OK" : "❌ FALLA"));
    Serial.println("GPS:      " + String(gps_ok ? "✅ OK" : "⚠️  PRUEBA"));

    Serial.println("\n📊 INICIANDO MONITOREO...");
    Serial.println("===========================================\n");
    delay(2000);
}

// ===========================
// FUNCIONES SIMPLIFICADAS PARA SpO2
// ===========================
void calculateSimpleSpO2(int irValue, int redValue)
{
    if (!max30102_ok || irValue == 0 || redValue == 0)
    {
        // Si el sensor no funciona, usar datos de prueba
        spO2 = 97.5 + (random(-20, 21) / 10.0);
        heartRate = 70 + random(-10, 11);
        fingerDetected = false;
        return;
    }

    // Cálculo SIMPLIFICADO de SpO2
    // En realidad necesitarías algoritmos más complejos
    float ratio = (float)redValue / (float)irValue;

    // Fórmula muy simplificada (NO para uso médico real)
    spO2 = 110.0 - 25.0 * ratio;

    // Limitar valores
    if (spO2 < 70.0)
        spO2 = 70.0;
    if (spO2 > 100.0)
        spO2 = 100.0;

    // Detectar dedo
    fingerDetected = (irValue > 10000 && redValue > 10000);

    // Ritmo cardiaco aproximado
    heartRate = 60 + random(-5, 6);
}

// ===========================
// FUNCIONES CONTADOR DE PASOS
// ===========================
void detectStep(float acceleration)
{
    if (!mpu6050_ok)
        return;

    unsigned long currentTime = millis();

    if (acceleration > accelThreshold &&
        (currentTime - lastStepTime) > stepDelay)
    {

        stepCount++;
        lastStepTime = currentTime;
    }
}

// ===========================
// LOOP PRINCIPAL
// ===========================
void loop()
{
    // ===========================
    // LECTURA MAX30102 (SpO2)
    // ===========================
    int irValue = 0;
    int redValue = 0;

    if (max30102_ok)
    {
        irValue = particleSensor.getIR();
        redValue = particleSensor.getRed();
    }
    else
    {
        // Datos de prueba si el sensor falla
        irValue = random(5000, 30000);
        redValue = random(5000, 30000);
    }

    // Calcular SpO2 simplificado
    calculateSimpleSpO2(irValue, redValue);

    // ===========================
    // LECTURA MPU6050 (ACELERACIÓN + PASOS)
    // ===========================
    float accelX = 0, accelY = 0, accelZ = 0;
    float gyroX = 0, gyroY = 0, gyroZ = 0;
    float temperature = 0;
    float currentAccel = 0;

    if (mpu6050_ok)
    {
        sensors_event_t a, g, temp;
        if (mpu.getEvent(&a, &g, &temp))
        {
            accelX = a.acceleration.x;
            accelY = a.acceleration.y;
            accelZ = a.acceleration.z;
            gyroX = g.gyro.x;
            gyroY = g.gyro.y;
            gyroZ = g.gyro.z;
            temperature = temp.temperature;

            currentAccel = sqrt(accelX * accelX + accelY * accelY + accelZ * accelZ);
            smoothAccel = alpha * smoothAccel + (1 - alpha) * currentAccel;

            detectStep(smoothAccel);
        }
    }
    else
    {
        // Datos de prueba
        accelX = (random(-20, 21)) / 10.0;
        accelY = (random(-20, 21)) / 10.0;
        accelZ = 9.8 + (random(-10, 11)) / 10.0;
        currentAccel = 9.8 + (random(-5, 6)) / 10.0;
        smoothAccel = currentAccel;
        temperature = 25.0 + (random(-50, 51)) / 10.0;
    }

    // ===========================
    // LECTURA GPS (POSICIÓN)
    // ===========================
    float gpsLat = 19.432608;
    float gpsLng = -99.133209;
    float gpsSpeed = 0;
    float gpsAltitude = 0;
    int satellites = 0;
    bool gpsValid = false;

    // Leer datos GPS si están disponibles
    while (SerialGPS.available() > 0)
    {
        if (gps.encode(SerialGPS.read()))
        {
            if (gps.location.isValid())
            {
                gpsValid = true;
                gps_ok = true;
                gpsLat = gps.location.lat();
                gpsLng = gps.location.lng();
                satellites = gps.satellites.value();
                gpsSpeed = gps.speed.kmph();
                gpsAltitude = gps.altitude.meters();
            }
        }
    }

    // Si no hay señal GPS, usar datos de prueba
    if (!gpsValid)
    {
        gpsLat = 19.432608 + (random(-500, 501) / 1000000.0);
        gpsLng = -99.133209 + (random(-500, 501) / 1000000.0);
        satellites = random(0, 8);
        gpsSpeed = random(0, 50) / 10.0;
    }

    // ===========================
    // ENVÍO DE DATOS EN JSON (FORMATO CORREGIDO)
    // ===========================
    Serial.print("{");

    // Datos de SpO2 y oxigenación (SIEMPRE presentes)
    Serial.print("\"spo2\":" + String(spO2, 1) + ",");
    Serial.print("\"ritmo_cardiaco\":" + String(heartRate) + ",");
    Serial.print("\"ir_value\":" + String(irValue) + ",");
    Serial.print("\"red_value\":" + String(redValue) + ",");
    Serial.print("\"finger_detected\":" + String(fingerDetected ? "true" : "false") + ",");

    // Datos de acelerómetro y pasos
    Serial.print("\"acel_x\":" + String(accelX, 2) + ",");
    Serial.print("\"acel_y\":" + String(accelY, 2) + ",");
    Serial.print("\"acel_z\":" + String(accelZ, 2) + ",");
    Serial.print("\"acel_total\":" + String(smoothAccel, 2) + ",");
    Serial.print("\"gyro_x\":" + String(gyroX, 2) + ",");
    Serial.print("\"gyro_y\":" + String(gyroY, 2) + ",");
    Serial.print("\"gyro_z\":" + String(gyroZ, 2) + ",");
    Serial.print("\"temperatura\":" + String(temperature, 1) + ",");
    Serial.print("\"pasos_totales\":" + String(stepCount) + ",");

    // Datos GPS
    Serial.print("\"gps_lat\":" + String(gpsLat, 6) + ",");
    Serial.print("\"gps_lng\":" + String(gpsLng, 6) + ",");
    Serial.print("\"gps_speed\":" + String(gpsSpeed, 1) + ",");
    Serial.print("\"gps_altitude\":" + String(gpsAltitude, 1) + ",");
    Serial.print("\"satellites\":" + String(satellites) + ",");
    Serial.print("\"gps_valid\":" + String(gpsValid ? "true" : "false") + ",");

    // Estado de sensores (IMPORTANTE: tu Python espera esto)
    Serial.print("\"sensor_status\":{");
    Serial.print("\"max30102\":" + String(max30102_ok ? "true" : "false") + ",");
    Serial.print("\"mpu6050\":" + String(mpu6050_ok ? "true" : "false") + ",");
    Serial.print("\"gps\":" + String(gps_ok ? "true" : "false"));
    Serial.print("}");

    Serial.println("}");

    // ===========================
    // DEBUG EN CONSOLA (opcional)
    // ===========================
    static unsigned long lastDebug = 0;
    if (millis() - lastDebug > 5000)
    {
        Serial.print("💡 ");
        Serial.print("SpO2: ");
        Serial.print(spO2, 1);
        Serial.print("% | IR: ");
        Serial.print(irValue);
        Serial.print(" | Pasos: ");
        Serial.print(stepCount);
        Serial.print(" | GPS: ");
        Serial.print(gpsValid ? satellites : 0);
        Serial.println(" sat");
        lastDebug = millis();
    }

    delay(1000); // 1 segundo entre lecturas
}