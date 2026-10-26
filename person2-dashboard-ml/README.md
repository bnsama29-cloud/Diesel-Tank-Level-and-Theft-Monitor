# Person 2 — Dashboard and anomaly analysis

The Streamlit app reads the latest values from the seven Adafruit IO feeds, shows the current level/pump/generator/alarm state, and embeds the tank viewer. It also applies the required transparent rapid-drop rule to readings observed by the dashboard.

## Run/deploy in the browser

1. Deploy this folder from GitHub using Streamlit Community Cloud.
2. In the app's **Settings → Secrets**, add:

   ```toml
   AIO_USERNAME = "your_adafruit_username"
   AIO_KEY = "your_new_private_adafruit_io_key"
   ```

3. Confirm that the seven feed keys match [`../integration/README.md`](../integration/README.md).

Do not add a `.streamlit/secrets.toml` file or a real key to GitHub. Local launch is optional and requires Python, so it is not part of the no-install workflow.

## ML handoff

The current detection is a 5-percentage-point / 60-second rule, matching the hardware requirement. It is not machine learning. Person 2 can later add a trained classifier once the team has labeled readings for normal generator consumption, refill events, sensor noise, and theft-like drops. Compare any model against the threshold baseline and preserve the explicit safety alarm behavior.
