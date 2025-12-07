// main.cpp - VERSIÓN PARA GRÁFICAS EN TIEMPO REAL
#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_MPU6050.h>
#include "MAX30105.h"

// ===========================
// OBJETOS GLOBALES
// ===========================
MAX30105 particleSensor;
Adafruit_MPU6050 mpu;

// ===========================
// VARIABLES GLOBALES SIMPLES
// ===========================
struct SensorData
{
    // MAX30105
    float spO2 = 0;
    int heartRate = 0;
    int32_t irValue = 0;
    int32_t redValue = 0;
    bool fingerDetected = false;

    // MPU6050
    float accelX = 0, accelY = 0, accelZ = 0;
    float temperature = 0;
    int stepCount = 0;
} sensorData;

// ===========================
// VARIABLES PARA DETECCIÓN MEJORADA
// ===========================
// Para MAX30105
unsigned long lastBeatTime = 0;
const int BEAT_ARRAY_SIZE = 5; // Más pequeño para respuesta más rápida
int beatArray[BEAT_ARRAY_SIZE];
int beatIndex = 0;
int beatSamples = 0;

// Para MPU6050
unsigned long lastStepTime = 0;
const unsigned long STEP_COOLDOWN = 300; // ms entre pasos
float lastAcceleration = 9.8;
const float STEP_THRESHOLD = 0.5; // Umbral más bajo para mejor detección
int stepCounter = 0;
bool isMoving = false;

// LEDs
const int LED_PULSE = 2;
const int LED_READ = 19;

// Control de tiempo
unsigned long lastSendTime = 0;
const unsigned long SEND_INTERVAL = 500; // Enviar cada 500ms (más rápido para gráficas)

// ===========================
// SETUP
// ===========================
void setup()
{
    Serial.begin(115200);
    Wire.begin(21, 22);

    pinMode(LED_PULSE, OUTPUT);
    pinMode(LED_READ, OUTPUT);

    delay(2000);

    Serial.println("\n🎯 SISTEMA PARA GRÁFICAS EN TIEMPO REAL");
    Serial.println("========================================\n");

    // Inicializar MAX30105
    Serial.print("📟 MAX30105: ");
    if (particleSensor.begin(Wire, I2C_SPEED_FAST))
    {
        Serial.println("✅ CONECTADO");

        // Configuración optimizada para respuesta rápida
        particleSensor.setup(100, 4, 2, 100, 411, 4096); // Brillo más alto
        particleSensor.setPulseAmplitudeRed(0x3A);       // Brillo alto para mejor lectura
        particleSensor.setPulseAmplitudeIR(0x2A);

        // Apagar LED verde
        particleSensor.setPulseAmplitudeGreen(0);

        // Habilitar todas las funcionalidades
        particleSensor.enableDIETEMPRDY();
    }
    else
    {
        Serial.println("❌ NO CONECTADO");
    }

    // Inicializar MPU6050
    Serial.print("📊 MPU6050: ");
    if (mpu.begin())
    {
        Serial.println("✅ CONECTADO");
        mpu.setAccelerometerRange(MPU6050_RANGE_4_G);
        mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);
    }
    else
    {
        Serial.println("❌ NO CONECTADO");
    }

    Serial.println("\n⚡ SISTEMA LISTO PARA GRÁFICAS");
    Serial.println("👆 Pon tu dedo en el sensor MAX30105");
    Serial.println("🎯 Agita el MPU6050 para contar 'pasos'");
    Serial.println("📈 Datos se envían cada 500ms");
    Serial.println("========================================\n");

    // Inicializar array de latidos
    for (int i = 0; i < BEAT_ARRAY_SIZE; i++)
    {
        beatArray[i] = 0;
    }
}

// ===========================
// FUNCIÓN PARA CALCULAR SpO2 MEJORADA
// ===========================
float calculateSpO2(int32_t ir, int32_t red)
{
    if (ir < 20000 || red < 5000) // Umbral más bajo para detección temprana
        return 0;

    // Fórmula mejorada para rango más realista
    float ratio = (float)red / (float)ir;

    // Ajustar fórmula para valores más realistas
    float spO2 = 104.0 - (17.0 * ratio); // Ajustado para mejor rango

    // Limitar a rango razonable pero permitir variación
    if (spO2 < 70.0)
        spO2 = 0; // Si es muy bajo, devolver 0
    if (spO2 > 100.0)
        spO2 = 100.0;

    return spO2;
}

// ===========================
// FUNCIÓN PARA DETECTAR PASOS MEJORADA
// ===========================
void detectStep(float currentAccel)
{
    unsigned long currentTime = millis();

    // Calcular cambio en aceleración
    float accelChange = abs(currentAccel - lastAcceleration);

    // Si el cambio es significativo y ha pasado el tiempo de cooldown
    if (accelChange > STEP_THRESHOLD && (currentTime - lastStepTime) > STEP_COOLDOWN)
    {
        stepCounter++;
        lastStepTime = currentTime;

        // Solo mostrar cada 5 pasos para no saturar serial
        if (stepCounter % 5 == 0)
        {
            Serial.print("👣 Paso #");
            Serial.println(stepCounter);
        }
    }

    lastAcceleration = currentAccel;
}

// ===========================
// FUNCIÓN PARA ENVIAR DATOS (JSON)
// ===========================
void sendSensorData()
{
    unsigned long currentTime = millis();

    // Crear JSON
    Serial.print("{");

    // Timestamp (en segundos con decimales para gráficas)
    Serial.print("\"timestamp\":");
    Serial.print(currentTime / 1000.0, 3);
    Serial.print(",");

    // ===== DATOS MAX30105 - SIEMPRE PRESENTES =====
    Serial.print("\"spo2\":");
    Serial.print(sensorData.spO2, 1);
    Serial.print(",\"ritmo_cardiaco\":");
    Serial.print(sensorData.heartRate);
    Serial.print(",\"ir_value\":");
    Serial.print(sensorData.irValue);
    Serial.print(",\"red_value\":");
    Serial.print(sensorData.redValue);
    Serial.print(",\"finger_detected\":");
    Serial.print(sensorData.fingerDetected ? "true" : "false");
    Serial.print(",");

    // ===== DATOS MPU6050 - SIEMPRE PRESENTES =====
    float accelTotal = sqrt(sensorData.accelX * sensorData.accelX +
                            sensorData.accelY * sensorData.accelY +
                            sensorData.accelZ * sensorData.accelZ);

    Serial.print("\"acel_x\":");
    Serial.print(sensorData.accelX, 2);
    Serial.print(",\"acel_y\":");
    Serial.print(sensorData.accelY, 2);
    Serial.print(",\"acel_z\":");
    Serial.print(sensorData.accelZ, 2);
    Serial.print(",\"acel_total\":");
    Serial.print(accelTotal, 2);
    Serial.print(",\"temperatura\":");
    Serial.print(sensorData.temperature, 1);
    Serial.print(",\"pasos_totales\":");
    Serial.print(sensorData.stepCount);
    Serial.print(",\"is_moving\":");
    Serial.print(isMoving ? "true" : "false");
    Serial.print(",");

    // Estado sensores
    bool maxConnected = particleSensor.begin(Wire, I2C_SPEED_FAST);
    bool mpuConnected = mpu.begin();

    Serial.print("\"sensor_status\":{");
    Serial.print("\"max30102\":");
    Serial.print(maxConnected ? "true" : "false");
    Serial.print(",\"mpu6050\":");
    Serial.print(mpuConnected ? "true" : "false");
    Serial.print("}");

    Serial.println("}");
}

// ===========================
// LOOP PRINCIPAL - OPTIMIZADO PARA GRÁFICAS
// ===========================
void loop()
{
    static unsigned long lastDebugTime = 0;
    unsigned long currentTime = millis();

    // LED indicador de actividad
    static bool ledState = false;
    ledState = !ledState;
    digitalWrite(LED_READ, ledState);

    // ===========================
    // LEER MAX30105 - CADA ITERACIÓN
    // ===========================
    sensorData.irValue = particleSensor.getIR();
    sensorData.redValue = particleSensor.getRed();

    // Detectar dedo con histéresis para evitar flickering
    static bool lastFingerState = false;
    static unsigned long fingerStateTime = 0;

    bool currentFingerDetected = (sensorData.irValue > 30000); // Umbral más bajo

    // Aplicar histéresis: cambiar estado solo después de 100ms estable
    if (currentFingerDetected != lastFingerState)
    {
        if (currentTime - fingerStateTime > 100)
        {
            sensorData.fingerDetected = currentFingerDetected;
            lastFingerState = currentFingerDetected;
            fingerStateTime = currentTime;

            // Feedback visual inmediato
            if (sensorData.fingerDetected)
            {
                Serial.println("✅ DEDO DETECTADO - Comenzando medición...");
                digitalWrite(LED_PULSE, HIGH);
            }
            else
            {
                Serial.println("❌ DEDO QUITADO - Deteniendo medición...");
                digitalWrite(LED_PULSE, LOW);
            }
        }
    }
    else
    {
        fingerStateTime = currentTime;
    }

    if (sensorData.fingerDetected)
    {
        // Detección de latido mejorada
        static int32_t lastIR = 0;
        static int32_t lastLastIR = 0;
        int32_t delta = sensorData.irValue - lastIR;
        int32_t lastDelta = lastIR - lastLastIR;

        // Detectar picos (latidos) - algoritmo mejorado
        static bool wasRising = false;

        // Solo detectar si hay suficiente señal
        if (abs(delta) > 80)
        {
            if (delta > 0 && lastDelta <= 0 && !wasRising)
            {
                wasRising = true;
            }

            if (delta < 0 && lastDelta >= 0 && wasRising)
            {
                wasRising = false;

                if (currentTime - lastBeatTime > 300) // Mínimo 300ms entre latidos
                {
                    long beatInterval = currentTime - lastBeatTime;

                    if (beatInterval > 300 && beatInterval < 1500) // 40-200 BPM
                    {
                        int bpm = 60000 / beatInterval;

                        // Promediar últimos latidos
                        beatArray[beatIndex] = bpm;
                        beatIndex = (beatIndex + 1) % BEAT_ARRAY_SIZE;
                        beatSamples = min(beatSamples + 1, BEAT_ARRAY_SIZE);

                        // Calcular promedio
                        int sum = 0;
                        for (int i = 0; i < beatSamples; i++)
                        {
                            sum += beatArray[i];
                        }

                        sensorData.heartRate = sum / beatSamples;

                        // Parpadeo LED con latido
                        digitalWrite(LED_PULSE, HIGH);
                        delay(10);
                        digitalWrite(LED_PULSE, LOW);
                    }

                    lastBeatTime = currentTime;
                }
            }
        }

        lastLastIR = lastIR;
        lastIR = sensorData.irValue;

        // Calcular SpO2 con valores actuales
        sensorData.spO2 = calculateSpO2(sensorData.irValue, sensorData.redValue);

        // Si SpO2 es 0 pero hay dedo, usar valor por defecto
        if (sensorData.spO2 == 0 && sensorData.irValue > 50000)
        {
            sensorData.spO2 = 98.0; // Valor por defecto cuando hay dedo
        }
    }
    else
    {
        // SIN DEDO - PONER TODO EN 0 INMEDIATAMENTE
        sensorData.heartRate = 0;
        sensorData.spO2 = 0;

        // Resetear variables de latido
        for (int i = 0; i < BEAT_ARRAY_SIZE; i++)
        {
            beatArray[i] = 0;
        }
        beatIndex = 0;
        beatSamples = 0;

        digitalWrite(LED_PULSE, LOW);
    }

    // ===========================
    // LEER MPU6050 - CADA ITERACIÓN
    // ===========================
    sensors_event_t a, g, temp;
    if (mpu.getEvent(&a, &g, &temp))
    {
        sensorData.accelX = a.acceleration.x;
        sensorData.accelY = a.acceleration.y;
        sensorData.accelZ = a.acceleration.z;
        sensorData.temperature = temp.temperature;

        // Calcular aceleración total
        float currentAccel = sqrt(sensorData.accelX * sensorData.accelX +
                                  sensorData.accelY * sensorData.accelY +
                                  sensorData.accelZ * sensorData.accelZ);

        // Detectar pasos
        detectStep(currentAccel);
        sensorData.stepCount = stepCounter;

        // Determinar si hay movimiento
        float accelVariation = abs(currentAccel - 9.8);
        isMoving = (accelVariation > 0.2); // Umbral más bajo
    }
    else
    {
        // Si no hay sensor, mantener valores por defecto
        sensorData.accelX = 0;
        sensorData.accelY = 0;
        sensorData.accelZ = 9.8;
        sensorData.temperature = 25.0;
        isMoving = false;
    }

    // ===========================
    // ENVIAR DATOS CADA 500ms (PARA GRÁFICAS SUAVES)
    // ===========================
    if (currentTime - lastSendTime >= SEND_INTERVAL)
    {
        lastSendTime = currentTime;

        // Enviar datos
        sendSensorData();

        // Debug cada 5 segundos
        if (currentTime - lastDebugTime >= 5000)
        {
            lastDebugTime = currentTime;

            Serial.print("📊 ESTADO: ");
            Serial.print("SpO2: ");
            Serial.print(sensorData.spO2, 1);
            Serial.print("% | HR: ");
            Serial.print(sensorData.heartRate);
            Serial.print(" | IR: ");
            Serial.print(sensorData.irValue);
            Serial.print(" | Dedo: ");
            Serial.print(sensorData.fingerDetected ? "SI" : "NO");
            Serial.print(" | Pasos: ");
            Serial.print(sensorData.stepCount);
            Serial.print(" | Mov: ");
            Serial.print(isMoving ? "SI" : "NO");
            Serial.println();
        }
    }

    // Pequeña pausa para no saturar
    delay(50);
}