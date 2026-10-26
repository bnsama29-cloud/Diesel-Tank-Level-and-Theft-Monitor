#include "secrets.h"
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

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

const float TANK_CAPACITY_L = 500.0f;
const float FULL_DISTANCE_CM = 5.0f;
const float EMPTY_DISTANCE_CM = 105.0f;
const float PUMP_ON_LEVEL = 20.0f;
const float PUMP_OFF_LEVEL = 90.0f;
const float THEFT_DROP_PERCENT = 5.0f;
const bool RELAY_ACTIVE_LOW = false;

const unsigned long SAMPLE_INTERVAL_MS = 1000UL;
const unsigned long THEFT_WINDOW_MS = 60000UL;
const unsigned long LCD_INTERVAL_MS = 500UL;
const unsigned long CLOUD_PUBLISH_MS = 20000UL;
const int HISTORY_SIZE = 61;

LiquidCrystal_I2C lcd(0x27, 16, 2);
float levelHistory[HISTORY_SIZE] = {};
unsigned long timeHistory[HISTORY_SIZE] = {};
int historyWriteIndex = 0;
int historyCount = 0;
unsigned long lastSampleTime = 0;
unsigned long lastLcdTime = 0;
unsigned long lastCloudPublish = 0;

float distanceCm = 0.0f;
float levelPct = 0.0f;
float litres = 0.0f;
bool sensorOK = false;
bool pumpOn = false;
bool generatorOn = false;
bool theftAlarm = false;

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

void updateTankLevel() {
  const float measuredDistance = readDistanceCm();
  if (measuredDistance < 2.0f || measuredDistance > 400.0f) {
    sensorOK = false;
    return;
  }

  distanceCm = measuredDistance;
  float fraction = (EMPTY_DISTANCE_CM - distanceCm) /
                   (EMPTY_DISTANCE_CM - FULL_DISTANCE_CM);
  fraction = constrain(fraction, 0.0f, 1.0f);
  levelPct = fraction * 100.0f;
  litres = fraction * TANK_CAPACITY_L;
  sensorOK = true;
}

void updatePump() {
  if (!sensorOK) {
    pumpOn = false;
  } else if (levelPct <= PUMP_ON_LEVEL) {
    pumpOn = true;
  } else if (levelPct > PUMP_OFF_LEVEL) {
    pumpOn = false;
  }
  digitalWrite(RELAY_PIN, relayLevel(pumpOn));
}

void updateIndicators() {
  const bool low = sensorOK && levelPct < 20.0f;
  const bool full = sensorOK && levelPct > 90.0f;
  const bool medium = sensorOK && !low && !full;
  digitalWrite(LED_LOW, low ? HIGH : LOW);
  digitalWrite(LED_MEDIUM, medium ? HIGH : LOW);
  digitalWrite(LED_FULL, full ? HIGH : LOW);
}

int oldestSampleAtLeast(unsigned long minimumAge, unsigned long now,
                        unsigned long* sampleAge) {
  for (int offset = 0; offset < historyCount; offset++) {
    const int index = (historyWriteIndex + HISTORY_SIZE - historyCount + offset)
                      % HISTORY_SIZE;
    const unsigned long age = now - timeHistory[index];
    if (age >= minimumAge) {
      if (sampleAge) *sampleAge = age;
      return index;
    }
  }
  return -1;
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

bool rapidDropDetected() {
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

void updateDisplay() {
  const unsigned long now = millis();
  if (now - lastLcdTime < LCD_INTERVAL_MS) return;
  lastLcdTime = now;

  if (!sensorOK) {
    lcd.setCursor(0, 0); lcd.print("Sensor error    ");
    lcd.setCursor(0, 1); lcd.print("Check HC-SR04   ");
  } else if (theftAlarm) {
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

void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin("Wokwi-GUEST", "");
  Serial.print("Connecting to Wokwi-GUEST");
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

bool publishFeedValue(const char* feedKey, const String& value) {
  WiFiClientSecure client;
  client.setCACert(AIO_ROOT_CA);
  HTTPClient https;
  const String url = String("https://io.adafruit.com/api/v2/") +
                     AIO_USERNAME + "/feeds/" + feedKey + "/data";
  https.setTimeout(5000);
  if (!https.begin(client, url)) {
    Serial.printf("HTTPS setup failed for feed %s\n", feedKey);
    return false;
  }

  https.addHeader("X-AIO-Key", AIO_KEY);
  https.addHeader("Content-Type", "application/json");
  const String payload = "{\"value\":\"" + value + "\"}";
  const int status = https.POST(payload);
  Serial.printf("Adafruit feed %s: HTTP %d\n", feedKey, status);
  if (status < 200 || status >= 300) Serial.println(https.getString());
  https.end();
  return status >= 200 && status < 300;
}

void publishTelemetry() {
  if (WiFi.status() != WL_CONNECTED || !sensorOK) return;
  const unsigned long now = millis();
  if (now - lastCloudPublish < CLOUD_PUBLISH_MS) return;
  lastCloudPublish = now;

  bool allOK = true;
  allOK &= publishFeedValue("distance", String(distanceCm, 2));
  allOK &= publishFeedValue("level", String(levelPct, 2));
  allOK &= publishFeedValue("litres", String(litres, 2));
  allOK &= publishFeedValue("generator", String(generatorOn ? 1 : 0));
  allOK &= publishFeedValue("pump", String(pumpOn ? 1 : 0));
  allOK &= publishFeedValue("theft", String(theftAlarm ? 1 : 0));
  allOK &= publishFeedValue("hours-left", String(estimateHoursLeft(), 2));
  Serial.println(allOK ? "Adafruit IO publish cycle succeeded."
                       : "Adafruit IO publish cycle had errors.");
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
  lcd.setCursor(0, 1); lcd.print("Starting...");
  connectWiFi();
  lcd.clear();
  Serial.println("Diesel tank monitor started.");
}

void loop() {
  updateTankLevel();
  generatorOn = digitalRead(GENERATOR_SWITCH_PIN) == HIGH;
  updatePump();
  updateIndicators();
  recordLevel();

  if (!theftAlarm && rapidDropDetected()) {
    theftAlarm = true;
    Serial.println("THEFT ALERT: rapid drop while generator is OFF.");
  }

  digitalWrite(BUZZER_PIN, theftAlarm ? HIGH : LOW);
  updateDisplay();
  publishTelemetry();
  delay(50);
}
