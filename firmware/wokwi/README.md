# Original HTTPS Wokwi firmware and circuit

This is the original HTTPS-based version and is retained for compatibility. For the faster MQTT route used by the current responsive dashboard, use the separate [`../wokwi-cloud-fast/`](../wokwi-cloud-fast/) project instead.

This folder contains the runnable Wokwi project:

- `sketch.ino` — tank calculation, LCD, LEDs, relay hysteresis, generator switch, theft alarm, and secure Adafruit IO publishing.
- `diagram.json` — ESP32-S2, HC-SR04, I2C LCD, LEDs, relay, buzzer, and corrected generator-switch wiring.
- `libraries.txt` — Wokwi Arduino library dependencies.
- `secrets.h.example` — Adafruit IO credentials and trusted-CA template; put real credentials only in a private Wokwi `secrets.h`.

The simulation connects to `Wokwi-GUEST` with a blank Wi-Fi password. Tank calibration is 5 cm full and 105 cm empty for a 100 L capacity. In sensor mode, it writes to the `tank-telemetry` feed every 3 seconds. You can instead enter a distance from 0 to 105 cm in the Serial Monitor; that reading is sent once, and the firmware waits for the dashboard's matching acknowledgment in `tank-manual-ack` before requesting another value. Enter `AUTO` to return to the HC-SR04 slider. Configure both Adafruit IO feeds as documented in [`../../docs/integration.md`](../../docs/integration.md).

Keep the Adafruit IO key and private secrets out of GitHub and public Wokwi projects. TLS certificate verification must remain enabled.
