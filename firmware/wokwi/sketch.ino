#include "secrets.h"
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

// =====================================================
// 1. ESP32-S2-MINI-1 PIN CONFIGURATION
// =====================================================
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

// =====================================================
// 2. TANK CONFIGURATION
// HC-SR04 distance: 5 cm = full, 105 cm = empty
// =====================================================
const float TANK_CAPACITY_L = 500.0f;
const float FULL_DISTANCE_CM = 5.0f;
const float EMPTY_DISTANCE_CM = 105.0f;
const float PUMP_ON_LEVEL = 20.0f;
const float PUMP_OFF_LEVEL = 90.0f;
const float THEFT_DROP_PERCENT = 5.0f;
const bool RELAY_ACTIVE_LOW = false;

bool generatorOn = false;
bool localTheftAlarm = false;
const unsigned long SAMPLE_INTERVAL_MS = 1000UL;
const unsigned long THEFT_WINDOW_MS = 60000UL;
const int HISTORY_SIZE = 61;

float levelHistory[HISTORY_SIZE] = {0};
unsigned long timeHistory[HISTORY_SIZE] = {0};
int historyWriteIndex = 0;
int historyCount = 0;
unsigned long lastSampleTime = 0;
unsigned long lastLcdTime = 0;
unsigned long lastCloudPublish = 0;
float physicalDistanceCm = -1.0f;
bool physicalSensorOK = false;
bool physicalGeneratorOn = false;

// =====================================================
// 5. TIMING AND CLOUD SETTINGS
// =====================================================
const unsigned long LCD_INTERVAL_MS = 500UL;
const unsigned long CLOUD_PUBLISH_MS = 2000UL;
const bool ENABLE_CLOUD = true;
const char* WIFI_SSID = "Wokwi-GUEST";
const char* WIFI_PASSWORD = "";

LiquidCrystal_I2C lcd(0x27, 16, 2);
WiFiClientSecure mqttNetworkClient;
PubSubClient mqttClient(mqttNetworkClient);
float distanceCm = -1.0f;
float levelPct = 0.0f;
float litres = 0.0f;
bool sensorOK = false;
bool pumpOn = false;
unsigned long lastMqttReconnect = 0;

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

void updatePhysicalInputs() {
  const float measuredDistance = readDistanceCm();
  physicalSensorOK = measuredDistance >= 2.0f && measuredDistance <= 400.0f;
  if (physicalSensorOK) physicalDistanceCm = measuredDistance;
  physicalGeneratorOn = digitalRead(GENERATOR_SWITCH_PIN) == HIGH;
}

void updateTankLevel() {
  sensorOK = physicalSensorOK;
  generatorOn = physicalGeneratorOn;
  if (!sensorOK) return;

  distanceCm = physicalDistanceCm;
  float fraction = (EMPTY_DISTANCE_CM - distanceCm) /
                   (EMPTY_DISTANCE_CM - FULL_DISTANCE_CM);
  fraction = constrain(fraction, 0.0f, 1.0f);
  levelPct = fraction * 100.0f;
  litres = fraction * TANK_CAPACITY_L;
  sensorOK = true;
}

void updatePump() {
  if (!sensorOK) {
    pumpOn = false; // fail-safe: stop pump if sensor data is invalid
  } else {
    if (levelPct <= PUMP_ON_LEVEL) pumpOn = true;
    else if (levelPct > PUMP_OFF_LEVEL) pumpOn = false;
    // Between 20% and 90%, retain previous pump state.
  }
  digitalWrite(RELAY_PIN, relayLevel(pumpOn));
}

void updateLEDs() {
  const bool low = sensorOK && levelPct < 20.0f;
  const bool full = sensorOK && levelPct > 90.0f;
  const bool medium = sensorOK && !low && !full;
  digitalWrite(LED_LOW, low ? HIGH : LOW);
  digitalWrite(LED_MEDIUM, medium ? HIGH : LOW);
  digitalWrite(LED_FULL, full ? HIGH : LOW);
}

int oldestSampleAtLeast(unsigned long minimumAge, unsigned long now,
                        unsigned long* sampleAge) {
  int found = -1;
  unsigned long greatestAge = 0;
  for (int i = 0; i < historyCount; i++) {
    const unsigned long age = now - timeHistory[i];
    if (age >= minimumAge) {
      if (age > greatestAge) {
        greatestAge = age;
        found = i;
      }
    }
  }
  if (sampleAge) *sampleAge = greatestAge;
  return found;
}

void recordLevel() {
  const unsigned long now = millis();
  if (now - lastSampleTime < SAMPLE_INTERVAL_MS || !sensorOK) return;
  lastSampleTime = now;
  levelHistory[historyWriteIndex] = levelPct;
  timeHistory[historyWriteIndex] = now;
  historyWriteIndex = (historyWriteIndex + 1) % HISTORY_SIZE;
  if (historyCount < HISTORY_SIZE) historyCount++;
}

bool detectRapidDrop() {
  if (generatorOn || !sensorOK) return false;
  unsigned long age = 0;
  const int baselineIndex = oldestSampleAtLeast(THEFT_WINDOW_MS, millis(), &age);
  return baselineIndex >= 0 &&
         levelHistory[baselineIndex] - levelPct > THEFT_DROP_PERCENT;
}

float estimateHoursLeft() {
  if (!generatorOn || !sensorOK) return -1.0f;
  unsigned long age = 0;
  const int baselineIndex = oldestSampleAtLeast(THEFT_WINDOW_MS, millis(), &age);
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

void updateBuzzer() {
  digitalWrite(BUZZER_PIN, localTheftAlarm ? HIGH : LOW);
}

void connectWiFi() {
  if (!ENABLE_CLOUD) return;
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Connecting to Wokwi Wi-Fi");
  const unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 15000UL) {
    delay(300);
    Serial.print('.');
  }
  Serial.println();
  Serial.println(WiFi.status() == WL_CONNECTED
                     ? "Wokwi Wi-Fi connected."
                     : "Wi-Fi unavailable; local monitoring continues.");
}

void maintainMqttConnection() {
  if (!ENABLE_CLOUD || WiFi.status() != WL_CONNECTED || mqttClient.connected()) return;

  const unsigned long now = millis();
  if (now - lastMqttReconnect < 5000UL) return;
  lastMqttReconnect = now;

  time_t currentTime;
  time(&currentTime);
  if (currentTime < 1700000000) {
    Serial.println("Waiting for network time before MQTT TLS.");
    return;
  }

  char clientId[32];
  snprintf(clientId, sizeof(clientId), "diesel-%08llx",
           (unsigned long long)ESP.getEfuseMac());
  if (mqttClient.connect(clientId, MQTT_USERNAME, MQTT_PASSWORD)) {
    Serial.println("MQTT broker connected.");
  } else {
    Serial.printf("MQTT connection failed, state=%d\n", mqttClient.state());
  }
}

void publishTelemetry() {
  if (!ENABLE_CLOUD || !mqttClient.connected() || !sensorOK) return;
  const unsigned long now = millis();
  if (now - lastCloudPublish < CLOUD_PUBLISH_MS) return;
  lastCloudPublish = now;

  char payload[256];
  const float hoursLeft = estimateHoursLeft();
  time_t currentTime;
  time(&currentTime);
  snprintf(payload, sizeof(payload),
           "{\"timestamp\":%lu,\"distance_cm\":%.2f,"
           "\"level_percent\":%.2f,\"litres\":%.2f,"
           "\"generator_on\":%s,\"pump_on\":%s,\"theft_alarm\":%s,"
           "\"hours_left\":%.2f}",
           (unsigned long)currentTime, distanceCm, levelPct, litres,
           generatorOn ? "true" : "false",
           pumpOn ? "true" : "false",
           localTheftAlarm ? "true" : "false",
           hoursLeft);
  const bool published = mqttClient.publish(MQTT_TOPIC, payload, true);
  Serial.println(published ? "MQTT telemetry published."
                           : "MQTT telemetry publish failed.");
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
  pinMode(GENERATOR_SWITCH_PIN, INPUT); // switch wired to 3V3 or GND
  digitalWrite(TRIG_PIN, LOW);
  digitalWrite(BUZZER_PIN, LOW);
  digitalWrite(RELAY_PIN, relayLevel(false));

  Wire.begin(LCD_SDA, LCD_SCL);
  lcd.init();
  lcd.backlight();
  lcd.setCursor(0, 0); lcd.print("Tank Monitor");
  lcd.setCursor(0, 1); lcd.print("Starting...");
  mqttNetworkClient.setCACert(MQTT_ROOT_CA);
  mqttClient.setServer(MQTT_HOST, MQTT_PORT);
  mqttClient.setKeepAlive(30);
  mqttClient.setBufferSize(512);
  mqttClient.setSocketTimeout(2);
  connectWiFi();
  if (WiFi.status() == WL_CONNECTED) {
    configTime(0, 0, "pool.ntp.org", "time.google.com");
  }
  lcd.clear();
  Serial.println("Diesel tank monitor started.");
}

void loop() {
  updatePhysicalInputs();
  updateTankLevel();
  updatePump();
  updateLEDs();
  recordLevel();

  if (detectRapidDrop()) {
    if (!localTheftAlarm) {
      Serial.println("THEFT ALERT: rapid level drop while generator OFF.");
    }
    localTheftAlarm = true;
  }

  updateLCD();
  updateBuzzer();
  maintainMqttConnection();
  mqttClient.loop();
  publishTelemetry();
  delay(50);
}
