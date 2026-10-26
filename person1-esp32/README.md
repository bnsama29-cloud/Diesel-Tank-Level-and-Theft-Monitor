# Person 1 — Wokwi and ESP32

## Files

- `sketch.ino`: level calculation, LCD/LEDs, pump hysteresis, generator switch, rapid-drop alarm, and Adafruit IO HTTPS publishing.
- `diagram.json`: the supplied ESP32-S2 / HC-SR04 / LCD / LEDs / relay / buzzer / switch circuit.
- `secrets.h.example`: safe template. Make a private `secrets.h` in the Wokwi project; do not add real keys to GitHub.

## Configure cloud access

1. Revoke the Adafruit IO key that was pasted into the project chat and generate a new key.
2. In Wokwi, set Wi-Fi to `Wokwi-GUEST` with an empty password.
3. Create `secrets.h` privately using the shape in `secrets.h.example`, and fill in the regenerated Adafruit username/key. Do not share a public Wokwi project containing that file.
4. Configure `AIO_ROOT_CA` with the current CA certificate chain required by `io.adafruit.com`; do not use TLS with certificate validation disabled.
5. Create the seven feeds from `integration/README.md`, then run the simulation and check the Serial Monitor for successful publish responses.

The Wokwi simulator's Wi-Fi is not your home Wi-Fi. The original pasted sketch included a home Wi-Fi password; this version uses the Wokwi network setting instead.

## Pin map

| Device | ESP32-S2 GPIO |
| --- | ---: |
| HC-SR04 TRIG / ECHO | 5 / 6 |
| LOW / MEDIUM / FULL LEDs | 7 / 8 / 9 |
| Relay input / buzzer | 10 / 11 |
| Generator slide switch center | 12 |
| I2C LCD SDA / SCL | 21 / 20 |

Tank calibration: 5 cm is full, 105 cm is empty, capacity is 500 L. The HC-SR04 echo is wired as in the supplied Wokwi circuit; never use this direct wiring on a physical 3.3 V ESP32 without checking the sensor's output voltage and using level shifting as needed.

## Behavior

- Litres and percentage are linear across the configured 100 cm sensing span.
- Pump turns ON at or below 20% and stays ON until the level is above 90%.
- Theft alarm latches if the generator is OFF and the measured level drops by more than 5 percentage points over at least 60 seconds.
- Cloud publishing is rate-limited to one update cycle every 20 seconds. Seven separate feed updates produce up to 21 data points/minute.
- Hours-left is a rough estimate based on the recent level trend; it is unavailable until the history window is filled and consumption is detected.
- LEDs are active-high, with their cathodes connected directly to ESP32 ground. LOW is on at or below 20%, MEDIUM above 20% through 90%, and FULL only above 90%.
- The Serial Monitor logs the detected I2C address and local sensor/LED/pump state once per second for simulation debugging.

Verify the tests in the root report-evidence checklist against the actual simulation before reporting PASS.
