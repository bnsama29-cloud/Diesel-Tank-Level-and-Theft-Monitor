# Web dashboards

## Live Adafruit IO monitor

Deploy `app.py` to Streamlit Community Cloud and add the Adafruit IO secrets listed in [`../docs/integration.md`](../docs/integration.md). The ESP32 publishes one JSON telemetry value to the `tank-telemetry` feed every 3 seconds; the dashboard reads recent feed data at the same interval.

The responsive dashboard prioritizes current fuel, generator and pump state, calculated runtime, feed freshness, rule-based interpretation, and a fuel-level graph. Refill and firmware theft events are marked on the graph when present. The 3D tank viewer is deferred and is not a dependency of the live monitor.

On desktop the page embeds Wokwi beside the monitor. Add `?view=mobile` for the read-only monitor and a link to open Wokwi separately. The Wokwi project is separate from Git; copy the updated sketch, corrected diagram, and private Adafruit settings into Wokwi.

The dashboard uses the explicit rule “more than 5 percentage points in 60 seconds while generator OFF” for suspected theft. The offline simulator's ML model is separate and is not a validated real-world classifier.

## Offline simulator and ML demonstration

`simulator_app.py` is an offline demo with manual controls, scenario playback, charts, and an ML anomaly detector. It needs no Adafruit IO connection:

```text
streamlit run dashboard/simulator_app.py
```

The bundled model is trained on synthetic demonstration data and is not validated as a real-world theft classifier.
