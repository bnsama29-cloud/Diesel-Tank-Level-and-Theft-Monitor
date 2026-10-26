# Diesel Tank Level and Theft Monitor

An ESP32-S2 Wokwi simulation that measures diesel level with an ultrasonic sensor, controls a refill relay with hysteresis, detects rapid unexplained drops, and publishes live readings to a mobile-friendly dashboard with a graph and plain-language interpretations.

## What it does

- Converts sensor distance to level and volume for a 500 L tank (5 cm full, 105 cm empty).
- Shows level and volume on an I2C LCD and indicates LOW / MEDIUM / FULL with LEDs.
- Turns the refill pump ON at or below 20%; once on, it stays on until the level rises above 90%.
- Detects a >5 percentage-point drop within 60 seconds while the generator is OFF.
- Publishes one JSON telemetry record to an Adafruit IO feed over HTTPS every 3 seconds.
- Shows fuel, generator, pump, runtime estimate, data freshness, and a live history graph in a Streamlit desktop/mobile website.
- Embeds the Wokwi simulator on desktop; the `?view=mobile` view is read-only.

## Repository layout

```text
firmware/wokwi/            ESP32 sketch, Wokwi circuit, libraries, secrets template
dashboard/app.py           Live desktop and read-only mobile dashboard
dashboard/simulator_app.py Offline scenario and synthetic ML demonstration
dashboard/assets/          3D tank viewer
dashboard/models/          Synthetic demonstration model
diesel-tank.gltf            Deferred Onshape-exported tank mesh
docs/integration.md         Adafruit IO setup and end-to-end test steps
docs/test-evidence.md       Evidence checklist and captured report images
requirements.txt            Python dependencies
```

## Live dashboard setup

1. Create an Adafruit IO account and a feed with key `tank-telemetry`; see [`docs/integration.md`](docs/integration.md).
2. Deploy this repository to Streamlit Community Cloud with `dashboard/app.py` as the app file.
3. Add `AIO_USERNAME`, `AIO_KEY`, and `AIO_FEED_KEY` as Streamlit app secrets.
4. Configure the same Adafruit IO username, key, feed key, and trusted root CA certificate in a private Wokwi `secrets.h`.
5. Copy the current `firmware/wokwi/sketch.ino` and corrected `firmware/wokwi/diagram.json` into the hosted Wokwi project, then start the simulation.

The firmware writes one complete telemetry record every 3 seconds, and the dashboard reads the feed every 3 seconds. Expect a few seconds of end-to-end delay depending on network and hosting conditions. The dashboard chart uses recent feed history and does not depend on a 3D model.

Full setup and troubleshooting instructions are in [`docs/integration.md`](docs/integration.md). Never commit Adafruit IO keys or expose them in a public Wokwi project.

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
