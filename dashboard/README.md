# Live dashboard

Deploy `app.py` to Streamlit Community Cloud and add the Adafruit IO secrets listed in [`../docs/integration.md`](../docs/integration.md). The dashboard reads recent records from the `tank-telemetry` feed every 2 seconds.

The single-page dashboard shows the latest tank level, litres, generator and pump state, runtime estimate, feed freshness, and plain-language interpretation on the left, with the fuel-level graph on the right. On mobile, the values and graph stack vertically. The page does not embed Wokwi; open the simulation separately when changing the sensor slider or switch.

The separate cloud-enabled Wokwi project in [`../firmware/wokwi-cloud-fast/`](../firmware/wokwi-cloud-fast/) publishes JSON snapshots over a persistent TLS MQTT connection about every 2.2 seconds. That is approximately 27 updates per minute, allowing some headroom under Adafruit IO's current free-account limit of 30 data points per minute. The dashboard flags data older than 8 seconds as stale. Cloud and browser latency can vary.

The dashboard uses the specified rule of more than 5 percentage points of fuel loss within 60 seconds while the generator is OFF. The offline simulator's ML model is separate and is not a validated real-world classifier.

## Offline simulator and ML demonstration

The offline demo needs no Adafruit IO connection:

```text
streamlit run dashboard/simulator_app.py
```

It includes manual controls, scenario playback, charts, and an ML demonstration trained on synthetic data. The model is not validated as a real-world theft classifier.
