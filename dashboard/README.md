# Web dashboards

## Live Adafruit IO dashboard

Deploy `dashboard/app.py` on Streamlit Community Cloud and configure `AIO_USERNAME` and `AIO_KEY` in the app's private **Settings → Secrets**. This is the project's main dashboard: it reads current Adafruit feeds, plots level history, shows pump/generator/alarm status, and embeds the tank visualization from `assets/tank_viewer.html`.

## Offline simulator and ML demonstration

`dashboard/simulator_app.py` is an offline demo with manual control, scenario playback, charts, and an ML anomaly detector. It does not read Adafruit IO. Run it from the repository root with:

```text
streamlit run dashboard/simulator_app.py
```

The bundled model is trained on synthetic demonstration data and should not be presented as a validated real-world theft classifier.
