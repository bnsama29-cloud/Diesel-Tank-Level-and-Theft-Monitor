# Web dashboards

## Live mobile monitoring website

Deploy `dashboard/app.py` on Streamlit Community Cloud and configure `AIO_USERNAME` and `AIO_KEY` in the app's **Settings → Secrets**. The desktop page embeds the Wokwi circuit, reads telemetry, plots level history, shows pump/generator/alarm status, and displays the interactive WebGL 3D chamber. Start and operate the simulation in Wokwi; the dashboard is read-only. Add `?view=mobile` for the read-only mobile view, which shows the same metrics, graph, and 3D chamber without embedding Wokwi.

Adafruit IO is the hidden telemetry bridge between Wokwi and the hosted website. The firmware publishes seven telemetry feeds every 20 seconds and the dashboard refreshes every 20 seconds. Change the sensor distance and generator state using the controls in the embedded Wokwi simulation; the resulting readings then appear in the desktop and mobile dashboards.

The public Wokwi project is separate from this repository. When updating firmware, copy `firmware/wokwi/sketch.ino` into the Wokwi editor and save it; Git pushes do not automatically update the hosted simulation.

The 3D view embeds the team's `diesel-tank.gltf` Onshape export directly into the dashboard component. Three.js and its glTF loader render it as a rotatable 3D scene, with liquid height driven by live level/litre readings. The mobile viewer supports touch-drag rotation.

On desktop, the tank metrics, 3D model, and operating status appear on the left; live feed records and the level graph are in the middle; and Wokwi is on the right. Drag the simulation panel's lower-right corner to resize it or use **Enlarge** for fullscreen. The live data uses a Streamlit fragment to refresh every 20 seconds without reloading the Wokwi iframe. Unexpected level values outside 0–100% are flagged and recovered from sensor distance when possible instead of displaying values such as 1000%.

## Offline simulator and ML demonstration

`dashboard/simulator_app.py` is an offline demo with manual control, scenario playback, charts, and an ML anomaly detector. It does not read Adafruit IO. Run it from the repository root with:

```text
streamlit run dashboard/simulator_app.py
```

The bundled model is trained on synthetic demonstration data and should not be presented as a validated real-world theft classifier.
