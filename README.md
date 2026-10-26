# Diesel Tank Level and Theft Monitor

An ESP32-S2 Wokwi simulation that measures diesel level with an ultrasonic sensor, controls a refill relay with hysteresis, detects rapid unexplained drops, and publishes readings to a mobile-friendly browser dashboard with live graphs and an interactive 3D diesel chamber.

## What it does

- Converts the sensor distance to tank level and volume for a 500 L tank. The calibrated sensor span is 5 cm (full) to 105 cm (empty).
- Shows level and volume on an I2C LCD and indicates LOW / MEDIUM / FULL with LEDs.
- Turns the refill pump ON at or below 20%; once on, it stays on until the level rises above 90%.
- Reads the generator slide switch and detects a >5 percentage-point drop within 60 seconds while the generator is OFF.
- Publishes seven telemetry values over HTTPS from Wokwi through Adafruit IO as the cloud relay.
- Displays live readings, recent feed records, history, status, and an interactive WebGL 3D chamber in a Streamlit website. Simulation inputs are controlled only in Wokwi; the mobile URL is read-only.
- Renders the team's Onshape-exported `diesel-tank.gltf` model in the live 3D view, with the fuel surface driven by the reported tank level.
- Keeps the Wokwi simulation mounted in a right-side panel that can be resized or expanded to fullscreen; tank status and 3D view appear on the left, with live feed records and graph in the middle.

## Repository layout

```text
firmware/
  wokwi/                 Wokwi sketch, circuit, libraries, and private-secrets template
dashboard/
  app.py                 Desktop control room and mobile read-only website
  simulator_app.py       Offline scenario and ML demonstration dashboard
  assets/                Tank visualization embedded by the live dashboard
  models/                Trained demo model artifact
diesel-tank.gltf         Onshape-exported 3D chamber used by the live dashboard
  ...                    Dashboard logic, simulators, tests, and model training
docs/
  integration.md         Adafruit feed contract and cloud setup
  test-evidence.md       Wokwi and dashboard verification checklist
requirements.txt         Dependencies for both dashboard entry points
```

## See the live dashboard

Deploy this repository on [Streamlit Community Cloud](https://share.streamlit.io/) and set the app file to `dashboard/app.py`. The default app URL is the desktop monitor with the embedded Wokwi simulation; append `?view=mobile` for a read-only mobile view. Add the following under the app's **Settings → Secrets**:

```toml
AIO_USERNAME = "your_adafruit_username"
AIO_KEY = "your_private_adafruit_io_key"
```

Create the seven telemetry feeds documented in [`docs/integration.md`](docs/integration.md). The desktop dashboard embeds the [Wokwi project](https://wokwi.com/projects/478875514435866625); start the simulation there and use its sensor slider and generator switch. The firmware publishes telemetry to Adafruit IO; both desktop and mobile views refresh readings every 20 seconds, and the mobile view is read-only.

## Run the simulation dashboard

The separate simulator is useful for demonstrating scenarios without cloud credentials. In a Python environment with the repository requirements installed:

```text
streamlit run dashboard/simulator_app.py
```

It includes manual readings and hysteresis, theft, and generator-consumption scenarios. The included ML model is trained on synthetic demonstration data; it has not been validated as a production theft classifier.

## Wokwi simulation

The desktop website embeds the public Wokwi simulation directly, so you can start and interact with the circuit there. The firmware uses `Wokwi-GUEST` with a blank Wi-Fi password; it does not use home Wi-Fi. Keep Adafruit credentials in private Wokwi secrets and Streamlit secrets; never place real credentials in the public sketch. Adafruit IO remains the background telemetry bridge; you do not need to open its UI while demonstrating.

The Wokwi project is hosted separately from this Git repository. If its sketch still polls the old `command` feed, copy the updated `firmware/wokwi/sketch.ino` into the Wokwi editor and save the project; the dashboard now only reads telemetry.

## Validation

Run the focused dashboard/data tests from the repository root:

```text
python -m unittest discover -s dashboard -p "test_*.py" -v
```

Check the Wokwi, background cloud relay, and dashboard scenarios in [`docs/test-evidence.md`](docs/test-evidence.md). The documented expectations should only be marked PASS after checking the actual simulation.
