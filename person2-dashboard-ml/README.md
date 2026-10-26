# Person 2 — Dashboard and anomaly analysis

The Streamlit app reads the latest values from the seven Adafruit IO feeds, plots level history with the 20%/90% pump thresholds, shows current operating status, and embeds the procedural 3D tank viewer. It also applies the required transparent rapid-drop rule to readings observed by the dashboard.

## Run/deploy in the browser

1. In Streamlit Community Cloud, deploy this repository and select `person2-dashboard-ml/app.py` as the app file.
2. In the app's **Settings → Secrets**, add:

   ```toml
   AIO_USERNAME = "your_adafruit_username"
   AIO_KEY = "your_new_private_adafruit_io_key"
   ```

3. Confirm that the seven feed keys match [`../integration/README.md`](../integration/README.md).

The history graph uses up to the most recent 500 values from the Adafruit `level` feed and refreshes every 20 seconds. Keep the Wokwi simulation running while viewing it so new samples arrive.
The repository-root `requirements.txt` includes the packages required by both the full demo dashboard and this Adafruit-connected dashboard.

Do not add a `.streamlit/secrets.toml` file or a real key to GitHub. Local launch is optional and requires Python, so it is not part of the no-install workflow.

## ML handoff

The current detection is a 5-percentage-point / 60-second rule, matching the hardware requirement. It is not machine learning. Person 2 can later add a trained classifier once the team has labeled readings for normal generator consumption, refill events, sensor noise, and theft-like drops. Compare any model against the threshold baseline and preserve the explicit safety alarm behavior.

## How the shared system connects

The ESP32 publishes values to Adafruit IO over HTTPS. This dashboard reads the latest value from each agreed feed and embeds the level-controlled tank from `person3-3d-tank/tank_viewer.html`. All three parts use the field definitions and secret-handling instructions in [`../integration/README.md`](../integration/README.md).
