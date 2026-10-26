# Web dashboards

## Live mobile monitoring website

Deploy `dashboard/app.py` on Streamlit Community Cloud and configure `AIO_USERNAME` and `AIO_KEY` in the app's private **Settings → Secrets**. This is the project's main monitoring website: it reads current telemetry, plots level history, shows pump/generator/alarm status, and embeds an interactive WebGL 3D chamber that can be rotated on mobile.

Adafruit IO remains the hidden network bridge between Wokwi and the hosted dashboard. You only need to view the Wokwi simulation and the Streamlit website; you do not need to open Adafruit's dashboard. Wokwi's public gateway supports outbound cloud publishing, not inbound connections from the hosted website.

The 3D view loads the Three.js ES module from jsDelivr when the page opens. The browser renders the diesel chamber as a rotatable 3D scene and sets the liquid volume from the live level/litre readings. The mobile viewer supports touch-drag rotation.

## Offline simulator and ML demonstration

`dashboard/simulator_app.py` is an offline demo with manual control, scenario playback, charts, and an ML anomaly detector. It does not read Adafruit IO. Run it from the repository root with:

```text
streamlit run dashboard/simulator_app.py
```

The bundled model is trained on synthetic demonstration data and should not be presented as a validated real-world theft classifier.
