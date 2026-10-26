# Diesel Tank Level and Theft Monitor

An ESP32-S2 Wokwi simulation that measures diesel level with an ultrasonic sensor, controls a refill relay with hysteresis, detects rapid unexplained drops, and publishes live readings to a mobile-friendly dashboard with graphs and an interactive 3D tank.

## What it does

- Converts sensor distance to level and volume for a 500 L tank (5 cm full, 105 cm empty).
- Shows level and volume on an I2C LCD and indicates LOW / MEDIUM / FULL with LEDs.
- Turns the refill pump ON at or below 20%; once on, it stays on until the level rises above 90%.
- Detects a >5 percentage-point drop within 60 seconds while the generator is OFF.
- Publishes one retained JSON telemetry message over secure MQTT every 2 seconds.
- Shows status, recent level history, and the team's Onshape-exported interactive 3D chamber in a Streamlit desktop/mobile website.
- Embeds the Wokwi simulator on desktop; the `?view=mobile` view is read-only.

## Repository layout

```text
firmware/wokwi/            ESP32 sketch, Wokwi circuit, libraries, secrets template
dashboard/app.py           Live desktop and read-only mobile dashboard
dashboard/simulator_app.py Offline scenario and synthetic ML demonstration
dashboard/assets/          3D tank viewer
dashboard/models/          Synthetic demonstration model
diesel-tank.gltf            Onshape-exported tank mesh
docs/integration.md         MQTT broker setup and end-to-end test steps
docs/test-evidence.md       Evidence checklist and captured report images
requirements.txt            Python dependencies
```

## Live dashboard setup

1. Create an EMQX Serverless deployment, keep its spend limit at zero to avoid usage-based charges, and create MQTT credentials for `diesel-tank/telemetry`; see [`docs/integration.md`](docs/integration.md).
2. Deploy this repository to Streamlit Community Cloud with `dashboard/app.py` as the app file.
3. Add the broker host, port, username, password, and topic as Streamlit app secrets.
4. Configure the same broker values and trusted root CA certificate in a private Wokwi `secrets.h`.
5. Copy the current `firmware/wokwi/sketch.ino` and corrected `firmware/wokwi/diagram.json` into the hosted Wokwi project, then start the simulation.

The firmware publishes every 2 seconds and the dashboard refreshes every 2 seconds. Expect a few seconds of end-to-end delay depending on network and hosting conditions. Adafruit IO is not used. The dashboard retains recent graph samples in app memory; that history resets when the hosted app restarts.

Full setup and troubleshooting instructions are in [`docs/integration.md`](docs/integration.md). Never commit broker secrets or expose them in public Wokwi files.

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
