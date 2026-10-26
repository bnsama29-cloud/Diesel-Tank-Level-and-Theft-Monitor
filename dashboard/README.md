# Web dashboards

## Live mobile monitoring website

Deploy `dashboard/app.py` on Streamlit Community Cloud and configure `AIO_USERNAME`, `AIO_KEY`, and a private `CONTROL_PASSWORD` in the app's **Settings → Secrets**. The default app URL is the password-protected desktop control room: it embeds the Wokwi circuit, reads current telemetry, plots level history, shows pump/generator/alarm status, embeds an interactive WebGL 3D chamber, and sends virtual sensor/generator inputs to Wokwi through the `command` feed. Start the embedded simulation in the dashboard. Add `?view=mobile` to the URL for a read-only mobile view with the same metrics, graph, and 3D chamber; it does not embed Wokwi or expose controls.

Adafruit IO remains the hidden network bridge between Wokwi and the hosted website. Wokwi polls the `command` feed every 10 seconds while the website refreshes metrics every 20 seconds. Create the command feed along with the telemetry feeds. Dashboard remote inputs change the firmware's simulated sensor/switch readings but cannot move the Wokwi component graphics; use the embedded Wokwi controls for changes that should visibly move the circuit controls. A physical Wokwi sensor or switch change takes control back.

The 3D view embeds the team's `diesel-tank.gltf` Onshape export directly into the dashboard component. Three.js and its glTF loader render it as a rotatable 3D scene, with liquid height driven by live level/litre readings. The mobile viewer supports touch-drag rotation.

On desktop, the live status, recent telemetry/event log, 3D model, and graph appear in the left panel, with controls and a smaller Wokwi simulation at the right. Drag the simulation panel's lower-right corner to resize its width and height, or use **Enlarge** for fullscreen. The live data uses a Streamlit fragment to refresh every 20 seconds without reloading the Wokwi iframe. Unexpected level values outside 0–100% are flagged in the log and recovered from sensor distance when possible instead of displaying values such as 1000%.

## Offline simulator and ML demonstration

`dashboard/simulator_app.py` is an offline demo with manual control, scenario playback, charts, and an ML anomaly detector. It does not read Adafruit IO. Run it from the repository root with:

```text
streamlit run dashboard/simulator_app.py
```

The bundled model is trained on synthetic demonstration data and should not be presented as a validated real-world theft classifier.
