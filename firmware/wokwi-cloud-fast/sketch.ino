#include <ctype.h>
#include <limits.h>
#include <math.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <time.h>
#include "secrets.h"

const int TRIG_PIN = 5;
const int ECHO_PIN = 6;
const int LED_LOW = 7;
const int LED_MEDIUM = 8;
const int LED_FULL = 9;
const int RELAY_PIN = 10;
const int BUZZER_PIN = 11;
const int GENERATOR_SWITCH_PIN = 12;
const int LCD_SDA = 21;
const int LCD_SCL = 20;
const char* WIFI_SSID = "Wokwi-GUEST";
const char* WIFI_PASSWORD = "";
const char* AIO_HOST = "io.adafruit.com";
const uint16_t AIO_PORT = 8883;
const char* AIO_TOPIC = AIO_USERNAME "/feeds/" AIO_FEED_KEY;

const float TANK_CAPACITY_L = 100.0f;
const float FULL_DISTANCE_CM = 5.0f;
const float EMPTY_DISTANCE_CM = 105.0f;
const float PUMP_ON_LEVEL = 20.0f;
const float PUMP_OFF_LEVEL = 90.0f;
const float THEFT_DROP_PERCENT = 5.0f;
const bool RELAY_ACTIVE_LOW = false;

const unsigned long SAMPLE_INTERVAL_MS = 1000UL;
const unsigned long SERIAL_REPORT_INTERVAL_MS = 1000UL;
const unsigned long LCD_INTERVAL_MS = 500UL;
const unsigned long TELEMETRY_INTERVAL_MS = 2200UL;
const unsigned long WIFI_RETRY_INTERVAL_MS = 10000UL;
const unsigned long MQTT_RETRY_INTERVAL_MS = 8000UL;
const unsigned long THEFT_WINDOW_MS = 60000UL;
const int HISTORY_SIZE = 61;

LiquidCrystal_I2C lcd(0x27, 16, 2);
WiFiClientSecure secureClient;
PubSubClient mqttClient(secureClient);

float levelHistory[HISTORY_SIZE] = {0};
unsigned long timeHistory[HISTORY_SIZE] = {0};
bool generatorHistory[HISTORY_SIZE] = {false};
int historyWriteIndex = 0;
int historyCount = 0;

float distanceCm = -1.0f;
float levelPct = 0.0f;
float litres = 0.0f;
float manualDistanceCm = 0.0f;
bool sensorOK = false;
bool generatorOn = false;
bool pumpOn = false;
bool localTheftAlarm = false;
bool manualDistanceMode = false;
bool mqttConnectionAttempted = false;

unsigned long lastSampleTime = 0;
unsigned long lastSerialReportTime = 0;
unsigned long lastLcdTime = 0;
unsigned long lastTelemetryTime = 0;
unsigned long lastWiFiAttemptTime = 0;
unsigned long lastMqttAttemptTime = 0;
char serialInput[32];
size_t serialInputLength = 0;
bool serialInputOverflow = false;

int relayLevel(bool on) {
  if (RELAY_ACTIVE_LOW) return on ? LOW : HIGH;
  return on ? HIGH : LOW;
}

float readDistanceCm() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(3);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);

  const unsigned long duration = pulseIn(ECHO_PIN, HIGH, 30000UL);
  if (duration == 0) return -1.0f;
  return duration * 0.0343f / 2.0f;
}

void processSerialCommand(char* command) {
  while (isspace((unsigned char)*command)) command++;
  char* end = command + strlen(command);
  while (end > command && isspace((unsigned char)end[-1])) *--end = '\0';
  if (*command == '\0') return;

  for (char* cursor = command; *cursor; cursor++) {
    *cursor = (char)toupper((unsigned char)*cursor);
  }

  if (strcmp(command, "AUTO") == 0) {
    manualDistanceMode = false;
    Serial.println("Input mode: HC-SR04 sensor slider.");
    return;
  }
  if (strcmp(command, "CLEAR") == 0) {
    localTheftAlarm = false;
    Serial.println("Theft alarm cleared.");
    return;
  }

  char* parsedEnd = nullptr;
  const float requestedDistance = strtof(command, &parsedEnd);
  while (parsedEnd && isspace((unsigned char)*parsedEnd)) parsedEnd++;
  if (parsedEnd == command || !parsedEnd || *parsedEnd != '\0' ||
      !isfinite(requestedDistance) || requestedDistance < 0.0f ||
      requestedDistance > EMPTY_DISTANCE_CM) {
    Serial.println("Invalid command. Enter 0-105 cm, AUTO, or CLEAR.");
    return;
  }

  manualDistanceCm = requestedDistance;
  manualDistanceMode = true;
  Serial.printf("Input mode: MANUAL - distance set to %.1f cm.\n",
                manualDistanceCm);
}

void readSerialCommands() {
  while (Serial.available() > 0) {
    const char value = (char)Serial.read();
    if (value == '\r') continue;
    if (value == '\n') {
      if (serialInputOverflow) {
        Serial.println("Input too long. Enter 0-105, AUTO, or CLEAR.");
      } else {
        serialInput[serialInputLength] = '\0';
        processSerialCommand(serialInput);
      }
      serialInputLength = 0;
      serialInputOverflow = false;
    } else if (!serialInputOverflow) {
      if (serialInputLength < sizeof(serialInput) - 1) {
        serialInput[serialInputLength++] = value;
      } else {
        serialInputOverflow = true;
      }
    }
  }
}

void updateInputsAndLevel() {
  generatorOn = digitalRead(GENERATOR_SWITCH_PIN) == HIGH;
  if (manualDistanceMode) {
    distanceCm = manualDistanceCm;
    sensorOK = true;
  } else {
    distanceCm = readDistanceCm();
    sensorOK = distanceCm >= 2.0f && distanceCm <= 400.0f;
  }
  if (!sensorOK) return;

  float fraction = (EMPTY_DISTANCE_CM - distanceCm) /
                   (EMPTY_DISTANCE_CM - FULL_DISTANCE_CM);
  fraction = constrain(fraction, 0.0f, 1.0f);
  levelPct = fraction * 100.0f;
  litres = fraction * TANK_CAPACITY_L;
}

void updatePumpAndIndicators() {
  if (!sensorOK) {
    pumpOn = false;
  } else {
    if (levelPct <= PUMP_ON_LEVEL) pumpOn = true;
    else if (levelPct > PUMP_OFF_LEVEL) pumpOn = false;
  }

  const bool low = sensorOK && levelPct < 20.0f;
  const bool full = sensorOK && levelPct > 90.0f;
  const bool medium = sensorOK && !low && !full;
  digitalWrite(RELAY_PIN, relayLevel(pumpOn));
  digitalWrite(LED_LOW, low ? HIGH : LOW);
  digitalWrite(LED_MEDIUM, medium ? HIGH : LOW);
  digitalWrite(LED_FULL, full ? HIGH : LOW);
  digitalWrite(BUZZER_PIN, localTheftAlarm ? HIGH : LOW);
}

void recordLevel() {
  const unsigned long now = millis();
  if (!sensorOK || now - lastSampleTime < SAMPLE_INTERVAL_MS) return;
  lastSampleTime = now;
  levelHistory[historyWriteIndex] = levelPct;
  timeHistory[historyWriteIndex] = now;
  generatorHistory[historyWriteIndex] = generatorOn;
  historyWriteIndex = (historyWriteIndex + 1) % HISTORY_SIZE;
  if (historyCount < HISTORY_SIZE) historyCount++;
}

int findOldestMatchingSample(unsigned long now, bool requiredGeneratorState,
                             unsigned long minimumAge,
                             unsigned long maximumAge,
                             unsigned long* foundAge) {
  int found = -1;
  unsigned long greatestAge = 0;
  const int oldestIndex =
      (historyWriteIndex - historyCount + HISTORY_SIZE) % HISTORY_SIZE;
  for (int offset = 0; offset < historyCount; offset++) {
    const int index = (oldestIndex + offset) % HISTORY_SIZE;
    if (generatorHistory[index] != requiredGeneratorState) continue;
    const unsigned long age = now - timeHistory[index];
    if (age < minimumAge || age > maximumAge) continue;
    if (age >= greatestAge) {
      greatestAge = age;
      found = index;
    }
  }
  if (foundAge) *foundAge = greatestAge;
  return found;
}

bool detectRapidDrop() {
  if (generatorOn || !sensorOK) return false;
  unsigned long age = 0;
  const int baselineIndex = findOldestMatchingSample(
      millis(), false, 0, THEFT_WINDOW_MS, &age);
  return baselineIndex >= 0 &&
         levelHistory[baselineIndex] - levelPct > THEFT_DROP_PERCENT;
}

float estimateHoursLeft() {
  if (!generatorOn || !sensorOK) return -1.0f;
  unsigned long age = 0;
  const int baselineIndex = findOldestMatchingSample(
      millis(), true, THEFT_WINDOW_MS, ULONG_MAX, &age);
  if (baselineIndex < 0 || age == 0) return -1.0f;

  const float dropPct = levelHistory[baselineIndex] - levelPct;
  if (dropPct <= 0.1f) return -1.0f;
  const float percentPerHour = dropPct / (age / 3600000.0f);
  if (percentPerHour <= 0.0f) return -1.0f;
  return levelPct / percentPerHour;
}

void updateLCD() {
  const unsigned long now = millis();
  if (now - lastLcdTime < LCD_INTERVAL_MS) return;
  lastLcdTime = now;

  if (!sensorOK) {
    lcd.setCursor(0, 0); lcd.print("Sensor error    ");
    lcd.setCursor(0, 1); lcd.print("Check HC-SR04   ");
  } else if (localTheftAlarm) {
    lcd.setCursor(0, 0); lcd.print("THEFT?          ");
    char line[17];
    snprintf(line, sizeof(line), "%.0f%% %.0f L", levelPct, litres);
    lcd.setCursor(0, 1); lcd.print(line); lcd.print("       ");
  } else {
    char line1[17];
    char line2[17];
    snprintf(line1, sizeof(line1), "LEVEL: %3.0f%%", levelPct);
    snprintf(line2, sizeof(line2), "FUEL: %4.0f L", litres);
    lcd.setCursor(0, 0); lcd.print(line1); lcd.print("   ");
    lcd.setCursor(0, 1); lcd.print(line2); lcd.print("   ");
  }
}

void printStatus() {
  const unsigned long now = millis();
  if (now - lastSerialReportTime < SERIAL_REPORT_INTERVAL_MS) return;
  lastSerialReportTime = now;

  Serial.println();
  Serial.println("===== DIESEL TANK MONITOR =====");
  Serial.printf("Input mode: %s\n", manualDistanceMode ? "MANUAL" : "HC-SR04");
  if (!sensorOK) {
    Serial.println("Sensor: no valid echo; check the ultrasonic sensor.");
    Serial.printf("Generator: %s\n", generatorOn ? "ON" : "OFF");
    Serial.println("===============================");
    return;
  }

  Serial.printf("Distance: %.1f cm\n", distanceCm);
  Serial.printf("Fuel level: %.1f %%\n", levelPct);
  Serial.printf("Fuel remaining: %.1f L / %.0f L\n",
                litres, TANK_CAPACITY_L);
  Serial.printf("Generator: %s\n", generatorOn ? "ON" : "OFF");
  Serial.printf("Refill pump / relay: %s\n", pumpOn ? "ON" : "OFF");
  Serial.printf("Level indicator: %s\n",
                levelPct < 20.0f ? "LOW LED"
                : levelPct > 90.0f ? "FULL LED"
                                   : "MEDIUM LED");
  Serial.printf("Theft alarm: %s\n", localTheftAlarm ? "THEFT?" : "OFF");
  Serial.printf("Buzzer: %s\n", localTheftAlarm ? "ON" : "OFF");
  const float hoursLeft = estimateHoursLeft();
  if (hoursLeft >= 0.0f) {
    Serial.printf("Estimated runtime: %.2f hours\n", hoursLeft);
  } else {
    Serial.println("Estimated runtime: collecting generator fuel-use history");
  }
  Serial.println("Pump thresholds: ON at <=20%; OFF only above 90%.");
  Serial.println("Theft rule: generator OFF and drop >5 percentage points in 60 sec.");
  Serial.println("===============================");
}

void serviceCloudConnection() {
  const unsigned long now = millis();
  if (WiFi.status() != WL_CONNECTED) {
    if (now - lastWiFiAttemptTime >= WIFI_RETRY_INTERVAL_MS) {
      lastWiFiAttemptTime = now;
      Serial.println("Connecting to Wokwi Wi-Fi...");
      WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    }
    return;
  }

  if (!mqttClient.connected()) {
    if (mqttConnectionAttempted &&
        now - lastMqttAttemptTime < MQTT_RETRY_INTERVAL_MS) return;
    lastMqttAttemptTime = now;
    mqttConnectionAttempted = true;
    if (time(nullptr) < 1700000000) {
      Serial.println("Waiting for network time before TLS connection.");
      return;
    }
    Serial.print("Connecting to Adafruit IO MQTT...");
    if (mqttClient.connect("diesel-tank-monitor", AIO_USERNAME, AIO_KEY)) {
      Serial.println(" connected.");
    } else {
      Serial.printf(" failed (state %d); retrying shortly.\n",
                    mqttClient.state());
    }
    return;
  }

  mqttClient.loop();
}

void publishTelemetry() {
  const unsigned long now = millis();
  if (now - lastTelemetryTime < TELEMETRY_INTERVAL_MS) return;
  lastTelemetryTime = now;
  if (!sensorOK || !mqttClient.connected()) return;

  const float hoursLeft = estimateHoursLeft();
  char telemetry[256];
  snprintf(
      telemetry, sizeof(telemetry),
      "{\"timestamp\":%lu,\"distance_cm\":%.2f,\"level_percent\":%.2f,"
      "\"litres\":%.2f,\"generator_on\":%s,\"pump_on\":%s,"
      "\"theft_alarm\":%s,\"hours_left\":%.2f,\"manual_request_id\":0}",
      (unsigned long)time(nullptr), distanceCm, levelPct, litres,
      generatorOn ? "true" : "false", pumpOn ? "true" : "false",
      localTheftAlarm ? "true" : "false", hoursLeft);

  if (mqttClient.publish(AIO_TOPIC, telemetry)) {
    Serial.printf("Cloud update sent: %s\n", telemetry);
  } else {
    Serial.println("Cloud update failed; MQTT will reconnect if needed.");
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  pinMode(LED_LOW, OUTPUT);
  pinMode(LED_MEDIUM, OUTPUT);
  pinMode(LED_FULL, OUTPUT);
  pinMode(RELAY_PIN, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(GENERATOR_SWITCH_PIN, INPUT);
  digitalWrite(TRIG_PIN, LOW);
  digitalWrite(BUZZER_PIN, LOW);
  digitalWrite(RELAY_PIN, relayLevel(false));

  Wire.begin(LCD_SDA, LCD_SCL);
  lcd.init();
  lcd.backlight();
  lcd.setCursor(0, 0); lcd.print("Tank Monitor");
  lcd.setCursor(0, 1); lcd.print("Wokwi cloud MQTT");

  Serial.println();
  Serial.println("Diesel tank monitor - Wokwi cloud MQTT mode.");
  Serial.println("Use HC-SR04 distance slider, or enter 0-105 cm in Serial Monitor.");
  Serial.println("Enter AUTO to return to the sensor; CLEAR resets the theft alarm.");

  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  secureClient.setCACert(AIO_ROOT_CA);
  mqttClient.setServer(AIO_HOST, AIO_PORT);
  if (!mqttClient.setBufferSize(512)) {
    Serial.println("Could not allocate the MQTT message buffer.");
  }
  mqttClient.setKeepAlive(30);
  mqttClient.setSocketTimeout(2);
  lastWiFiAttemptTime = millis();
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  configTime(0, 0, "pool.ntp.org", "time.nist.gov");
  Serial.println("Connecting to Wokwi Wi-Fi and Adafruit IO MQTT.");
}

void loop() {
  readSerialCommands();
  updateInputsAndLevel();
  updatePumpAndIndicators();

  if (detectRapidDrop() && !localTheftAlarm) {
    localTheftAlarm = true;
    digitalWrite(BUZZER_PIN, HIGH);
    Serial.println("!!! THEFT ALERT: rapid level drop while generator is OFF. !!!");
  }

  recordLevel();
  updateLCD();
  printStatus();
  serviceCloudConnection();
  publishTelemetry();
  delay(25);
}
