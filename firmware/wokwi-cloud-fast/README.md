# Wokwi fast-cloud diesel tank monitor

This is the cloud-enabled Wokwi firmware for the diesel tank monitor. It publishes to Adafruit IO for the Streamlit dashboard in `dashboard/`.

## What it does

- Keeps the ultrasonic distance slider and Serial Monitor distance entry (`0` to `105` cm); enter `AUTO` to return to the slider and `CLEAR` to reset the theft alarm.
- Adds a `DEMO` Serial Monitor command that runs the demonstration cases automatically, holding each case for 10 seconds so the dashboard has time to receive and display multiple updates. The generator-ON runtime portion takes about 70 seconds; an estimate is expected only after at least 60 seconds of measurable generator-ON fuel decline.
- Preserves the 100 L model, pump hysteresis, generator switch, LEDs, LCD, theft alarm, and runtime estimate.
- Publishes one JSON telemetry snapshot to the Adafruit IO `tank-telemetry` feed over a persistent TLS MQTT connection about every 2.2 seconds.
- Prints readings and cloud connection/publish status in the Serial Monitor.

An interval of about 2.2 seconds allows approximately 27 updates per minute, below Adafruit IO's free-account limit of 30 data points per minute. Updates are much faster than opening a new HTTPS/TLS connection for each reading, but Wi-Fi, Wokwi, Adafruit IO, and dashboard hosting can still add network latency.

## Wokwi setup

1. Make a separate ESP32 project and import `sketch.ino`, `diagram.json`, and `libraries.txt` from this folder.
2. Add a private `secrets.h` file to that Wokwi project. Use `secrets.h.example` as the template, then enter your Adafruit IO username and key and the trusted root CA certificate for `io.adafruit.com`.
3. Keep the credentials private. Do not commit `secrets.h` or paste real keys into a public Wokwi project.
4. Start the simulation and open the Serial Monitor. The sketch connects to Wokwi's open `Wokwi-GUEST` network on channel 6, then waits for Wi-Fi before initializing the LCD, reading inputs, or showing the operating commands. After `Wokwi Wi-Fi connected. Starting the tank monitor.`, wait for MQTT to connect and check for `Cloud update sent`.

The feed key defaults to `tank-telemetry`. The dashboard reads `AIO_USERNAME`, `AIO_KEY`, and `AIO_FEED_KEY` from Streamlit secrets and refreshes the current values and graph every 2 seconds.

## Telemetry message

The feed contains one JSON object per update with the current timestamp, sensor distance, level percentage, litres, generator state, pump state, theft alarm, runtime estimate, and `manual_request_id` (zero; no dashboard acknowledgment is required).

## Demo input

- Enter `DEMO` in the Serial Monitor to run the scripted sequence: normal reading, pump ON, hysteresis hold, pump OFF, theft baseline/drop/reset, and generator-ON runtime trend. The script runs for about 140 seconds and publishes to the same feed used by the dashboard.
- Each case lasts at least 10 seconds; the dashboard refreshes every 2 seconds. Watch the Serial Monitor for the case name and `Cloud update sent`, and watch the dashboard's LIVE values and graph. The device does not receive an acknowledgment that the dashboard has rendered a case.
- During the scripted demo, the sketch controls the simulated generator state and manual distance. Enter a number to cancel the sequence and continue with manual distance input, or enter `AUTO`/`STOP` to cancel and resume the sensor slider. `CLEAR` cancels the demo and clears the alarm.
- You can still use the original interactive workflow at any time: enter a distance, use `AUTO` for the HC-SR04 slider, or use `CLEAR` to reset the alarm. Do not start a second Wokwi publisher on the same Adafruit account/feed during this demonstration.
- The firmware does not receive a dashboard-render acknowledgment; it holds each case for 10 seconds while the dashboard polls every 2 seconds. Confirm `Cloud update sent` in Serial Monitor and **LIVE** on the dashboard.
- Adjust the HC-SR04 slider, or enter a distance such as `85` in Serial Monitor.
- Enter `AUTO` to resume using the ultrasonic slider.
- Set the generator switch ON for a gradual decrease to collect runtime history.
- Set it OFF and lower the level by more than five percentage points within a minute to trigger the theft alarm.
- The pump turns ON at or below 20% and turns OFF only above 90%.

The relay and buzzer are simulated indicators; this project must not control real fuel equipment.
