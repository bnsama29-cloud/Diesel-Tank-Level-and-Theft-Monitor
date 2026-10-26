# Web dashboards

## Live MQTT monitor

Deploy `app.py` to Streamlit Community Cloud and add the MQTT secrets listed in [`../docs/integration.md`](../docs/integration.md). The ESP32 publishes a retained telemetry snapshot to the cloud broker every 2 seconds; this app subscribes to that topic and redraws the live section every 2 seconds. No Adafruit IO account or feed setup is required.

The desktop page embeds Wokwi and displays tank status, live activity, level history, and the interactive WebGL tank. Add `?view=mobile` for the same read-only monitor without the simulator. Recent chart samples are held in memory and are lost if the app restarts.

The public Wokwi project is separate from Git. Copy the updated sketch, corrected diagram, and private broker settings into Wokwi; pushes do not update the hosted simulation.

The 3D view embeds the team's Onshape `diesel-tank.gltf` export. Three.js renders a rotatable chamber whose liquid surface follows the latest telemetry.

## Offline simulator and ML demonstration

`simulator_app.py` is an offline demo with manual controls, scenario playback, charts, and an ML anomaly detector. It needs no MQTT connection:

```text
streamlit run dashboard/simulator_app.py
```

The bundled model is trained on synthetic demonstration data and is not validated as a real-world theft classifier.
