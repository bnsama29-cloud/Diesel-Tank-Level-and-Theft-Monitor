# Diesel Tank Level and Theft Monitor

An ESP32-S2 Wokwi simulation that measures diesel level with an ultrasonic sensor, controls a refill relay with hysteresis, detects rapid unexplained drops, and publishes live readings to a mobile-friendly dashboard with a graph and plain-language interpretations.

## What it does

- Converts sensor distance to level and volume for a 100 L tank (5 cm full, 105 cm empty).
- Lets you use the HC-SR04 slider or enter a simulated distance from 0–105 cm in the Serial Monitor; enter `AUTO` to return to the sensor.
- Shows level and volume on an I2C LCD and indicates LOW / MEDIUM / FULL with LEDs.
- Turns the refill pump ON at or below 20%; once on, it stays on until the level rises above 90%.
- Detects a >5 percentage-point drop within 60 seconds while the generator is OFF.
- Publishes one JSON telemetry record to Adafruit IO over a persistent TLS MQTT connection about every 2.2 seconds.
- Shows the latest fuel, generator, pump, runtime estimate, data freshness, and a live history graph in a responsive Streamlit dashboard.
- Displays latest values to the left of the graph on desktop; the panels stack on mobile. Open Wokwi separately.

## Repository layout

```text
firmware/wokwi/            ESP32 sketch, Wokwi circuit, libraries, secrets template
firmware/wokwi-local-only/ Standalone Wokwi demo with no Wi-Fi or cloud
firmware/wokwi-cloud-fast/ Separate Wokwi variant with faster MQTT cloud updates
dashboard/app.py           Responsive live dashboard
dashboard/simulator_app.py Offline scenario and synthetic ML demonstration
dashboard/assets/          3D tank viewer
dashboard/models/          Synthetic demonstration model
diesel-tank.gltf            Deferred Onshape-exported tank mesh
docs/integration.md         Adafruit IO setup and end-to-end test steps
docs/test-evidence.md       Evidence checklist and captured report images
requirements.txt            Python dependencies
```

## Live dashboard setup

1. Create an Adafruit IO feed with key `tank-telemetry`; see [`docs/integration.md`](docs/integration.md).
2. Deploy this repository to Streamlit Community Cloud with `dashboard/app.py` as the app file.
3. Add `AIO_USERNAME`, `AIO_KEY`, and `AIO_FEED_KEY` as Streamlit app secrets.
4. Configure the same Adafruit IO username, key, feed key, and trusted root CA certificate in a private Wokwi `secrets.h`.
5. Copy `firmware/wokwi-cloud-fast/sketch.ino`, `diagram.json`, and `libraries.txt` into a separate hosted Wokwi project, add private credentials, then start the simulation.

The cloud-enabled firmware publishes one sensor snapshot about every 2.2 seconds, remaining below the current 30-data-points-per-minute Adafruit IO free-tier limit. The dashboard polls every 2 seconds and marks data older than 8 seconds as stale. A Serial Monitor distance entry stays active until `AUTO` returns control to the ultrasonic slider. The 100 L tank calibration is 5 cm full, 105 cm empty, and 55 cm about 50 L. Network and hosting latency still apply.

Full setup and troubleshooting instructions are in [`docs/integration.md`](docs/integration.md). Never commit Adafruit IO keys or expose them in a public Wokwi project.

For a Wokwi-only demonstration with no Adafruit IO or dashboard, use the separate [`firmware/wokwi-local-only/`](firmware/wokwi-local-only/) project. Its Serial Monitor accepts `0`–`105`, `AUTO`, and `CLEAR` commands while retaining the HC-SR04 slider.

## Offline simulator

The offline demo runs without broker credentials:

```text
streamlit run dashboard/simulator_app.py
```

It includes manual controls, scenario playback, charts, and an ML demonstration trained on synthetic data. The model is not validated as a real-world theft classifier.

## Validation

Run tests from the repository root:

```text
python -m unittest discover -s dashboard -p "test_*.py" -v
python dashboard/test_integration.py
```

Live hardware/cloud cases should be marked passed only after checking the actual Wokwi circuit and deployed dashboard; see [`docs/test-evidence.md`](docs/test-evidence.md).
