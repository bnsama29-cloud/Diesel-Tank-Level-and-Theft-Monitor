# Wokwi firmware and circuit

This folder contains the runnable Wokwi project:

- `sketch.ino` — tank calculation, LCD, LEDs, relay hysteresis, generator switch, theft alarm, and secure MQTT publishing.
- `diagram.json` — ESP32-S2, HC-SR04, I2C LCD, LEDs, relay, buzzer, and corrected generator-switch wiring.
- `libraries.txt` — Wokwi Arduino library dependencies.
- `secrets.h.example` — MQTT broker and trusted-CA template; put real credentials only in a private Wokwi `secrets.h`.

The simulation connects to `Wokwi-GUEST` with a blank Wi-Fi password. Tank calibration is 5 cm full and 105 cm empty for a 500 L capacity. Configure the MQTT broker as documented in [`../../docs/integration.md`](../../docs/integration.md).

Keep the broker username, password, and private secrets out of GitHub and any public sketch. TLS certificate verification must remain enabled.
