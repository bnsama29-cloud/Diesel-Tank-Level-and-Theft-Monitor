# Wokwi firmware and circuit

This folder contains the runnable Wokwi project:

- `sketch.ino` — tank calculation, LCD, LEDs, relay hysteresis, generator switch, theft alarm, and Adafruit IO publishing.
- `diagram.json` — ESP32-S2, HC-SR04, I2C LCD, LEDs, relay, buzzer, and switch wiring.
- `libraries.txt` — Wokwi Arduino library dependency.
- `secrets.h.example` — certificate and credential template; put actual credentials only in a private Wokwi `secrets.h`.

The simulation connects to `Wokwi-GUEST` with a blank password. The tank calibration is 5 cm full and 105 cm empty for a 500 L capacity. Adafruit IO feed names and dashboard deployment are documented in [`../../docs/integration.md`](../../docs/integration.md).

Do not put Adafruit keys in GitHub or a public Wokwi project. The firmware verifies HTTPS using the CA certificate in the secrets template.
