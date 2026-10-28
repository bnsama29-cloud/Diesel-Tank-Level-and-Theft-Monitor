# Wokwi fast-cloud diesel tank monitor

This is a separate cloud-enabled copy of the local Wokwi demo. The original offline project in `firmware/wokwi-local-only/` remains unchanged.

## What it does

- Keeps the ultrasonic distance slider and Serial Monitor distance entry (`0` to `105` cm); enter `AUTO` to return to the slider and `CLEAR` to reset the theft alarm.
- Preserves the 100 L model, pump hysteresis, generator switch, LEDs, LCD, theft alarm, and runtime estimate.
- Publishes one JSON telemetry snapshot to the Adafruit IO `tank-telemetry` feed over a persistent TLS MQTT connection about every 2.2 seconds.
- Prints readings and cloud connection/publish status in the Serial Monitor.

An interval of about 2.2 seconds allows approximately 27 updates per minute, below Adafruit IO's free-account limit of 30 data points per minute. Updates are much faster than opening a new HTTPS/TLS connection for each reading, but Wi-Fi, Wokwi, Adafruit IO, and dashboard hosting can still add network latency.

## Wokwi setup

1. Make a separate ESP32 project and import `sketch.ino`, `diagram.json`, and `libraries.txt` from this folder.
2. Add a private `secrets.h` file to that Wokwi project. Use `secrets.h.example` as the template, then enter your Adafruit IO username and key and the trusted root CA certificate for `io.adafruit.com`.
3. Keep the credentials private. Do not commit `secrets.h` or paste real keys into a public Wokwi project.
4. Start the simulation and open the Serial Monitor. Confirm Wi-Fi and MQTT connect, then check for `Cloud update sent`.

The feed key defaults to `tank-telemetry`. The dashboard reads `AIO_USERNAME`, `AIO_KEY`, and `AIO_FEED_KEY` from Streamlit secrets and refreshes the current values and graph every 2 seconds.

## Telemetry message

The feed contains one JSON object per update with the current timestamp, sensor distance, level percentage, litres, generator state, pump state, theft alarm, runtime estimate, and `manual_request_id` (zero; no dashboard acknowledgment is required).

## Demo input

- Adjust the HC-SR04 slider, or enter a distance such as `85` in Serial Monitor.
- Enter `AUTO` to resume using the ultrasonic slider.
- Set the generator switch ON for a gradual decrease to collect runtime history.
- Set it OFF and lower the level by more than five percentage points within a minute to trigger the theft alarm.
- The pump turns ON at or below 20% and turns OFF only above 90%.

The relay and buzzer are simulated indicators; this project must not control real fuel equipment.
