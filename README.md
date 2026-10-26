# Diesel Tank Level and Theft Monitor

An ESP32-S2 Wokwi simulation that measures diesel level with an ultrasonic sensor, controls a refill relay with hysteresis, detects rapid unexplained drops, and publishes readings to a mobile-friendly browser dashboard with live graphs and an interactive 3D diesel chamber.

## What it does

- Converts the sensor distance to tank level and volume for a 500 L tank. The calibrated sensor span is 5 cm (full) to 105 cm (empty).
- Shows level and volume on an I2C LCD and indicates LOW / MEDIUM / FULL with LEDs.
- Turns the refill pump ON at or below 20%; once on, it stays on until the level rises above 90%.
- Reads the generator slide switch and detects a >5 percentage-point drop within 60 seconds while the generator is OFF.
- Publishes seven telemetry values over HTTPS from Wokwi through Adafruit IO as the cloud relay.
- Displays live readings, history, status, and an interactive WebGL 3D chamber in a Streamlit website. The desktop view controls virtual sensor/generator inputs; a mobile URL is read-only.

## Repository layout

```text
firmware/
  wokwi/                 Wokwi sketch, circuit, libraries, and private-secrets template
dashboard/
  app.py                 Mobile monitoring website (Streamlit Cloud entry point)
  simulator_app.py       Offline scenario and ML demonstration dashboard
  assets/                Tank visualization embedded by the live dashboard
  models/                Trained demo model artifact
  ...                    Dashboard logic, simulators, tests, and model training
docs/
  integration.md         Adafruit feed contract and cloud setup
  test-evidence.md       Wokwi and dashboard verification checklist
requirements.txt         Dependencies for both dashboard entry points
```

## See the live dashboard

Deploy this repository on [Streamlit Community Cloud](https://share.streamlit.io/) and set the app file to `dashboard/app.py`. The default app URL is the desktop control room; append `?view=mobile` for a read-only mobile view. Add the following under the app's **Settings → Secrets**:

```toml
AIO_USERNAME = "your_adafruit_username"
AIO_KEY = "your_private_adafruit_io_key"
CONTROL_PASSWORD = "choose_a_private_dashboard_control_password"
```

Create all eight feeds documented in [`docs/integration.md`](docs/integration.md), including `command`. Keep the Wokwi simulation running and upload the current [`sketch.ino`](firmware/wokwi/sketch.ino) to that Wokwi project. The simulation publishes to Adafruit IO in the background and checks for desktop controls every 10 seconds. Both views refresh telemetry every 20 seconds; each shows the live graph and 3D tank, and mobile exposes no controls. Set a private `CONTROL_PASSWORD` secret to protect the desktop command interface.

## Run the simulation dashboard

The separate simulator is useful for demonstrating scenarios without cloud credentials. In a Python environment with the repository requirements installed:

```text
streamlit run dashboard/simulator_app.py
```

It includes manual readings and hysteresis, theft, and generator-consumption scenarios. The included ML model is trained on synthetic demonstration data; it has not been validated as a production theft classifier.

## Wokwi simulation

Use the files in [`firmware/wokwi/`](firmware/wokwi/) in your Wokwi project. The firmware uses `Wokwi-GUEST` with a blank Wi-Fi password; it does not use home Wi-Fi. Create a private `secrets.h` in Wokwi based on [`secrets.h.example`](firmware/wokwi/secrets.h.example), entering Adafruit credentials there. Never commit real credentials or make a public Wokwi project containing them. Adafruit IO is the background bridge because the hosted dashboard cannot directly receive a connection from Wokwi's public gateway; you don't need to open Adafruit's UI while demonstrating the project.

## Validation

Run the focused dashboard/data tests from the repository root:

```text
python -m unittest discover -s dashboard -p "test_*.py" -v
```

Check the Wokwi, background cloud relay, and dashboard scenarios in [`docs/test-evidence.md`](docs/test-evidence.md). The documented expectations should only be marked PASS after checking the actual simulation.
