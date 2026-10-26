# Shared integration contract

Adafruit IO is the background telemetry relay between Wokwi and the hosted website. The desktop dashboard embeds the public Wokwi project; start and operate the simulation there. Wokwi publishes telemetry and the website reads it. A mobile URL provides the same live readings, graph, and 3D tank in read-only mode, without embedding Wokwi. Viewers do not need to open the Adafruit IO dashboard.

The desktop layout keeps live status and the 3D model on the left, live feed records and the graph in the middle, and the Wokwi simulator on the right. Drag the simulation's lower-right corner to resize it, or use browser fullscreen. Telemetry refreshes in a Streamlit fragment every 20 seconds so it does not restart the embedded simulation.

## Feeds

Create these seven Adafruit IO telemetry feeds with the exact lowercase keys:

| Feed key | Type / example | Meaning |
| --- | --- | --- |
| `distance` | number, `55.0` | Sensor-to-fuel distance in cm |
| `level` | number, `50.0` | Tank full percentage, 0–100 |
| `litres` | number, `250.0` | Estimated fuel volume, 0–500 |
| `generator` | integer, `0` or `1` | Generator OFF / ON |
| `pump` | integer, `0` or `1` | Pump relay OFF / ON |
| `theft` | integer, `0` or `1` | Latched firmware theft alarm |
| `hours-left` | number, `-1` or hours | `-1` means unavailable |
The firmware posts each telemetry feed once per 20-second cycle (up to 21 data points/minute). There is no dashboard command feed: sensor and generator inputs are controlled in Wokwi.

The public Wokwi project is hosted separately from this Git repository. If its sketch still contains the old command polling code, replace it with `firmware/wokwi/sketch.ino` in the Wokwi editor and save the project; a Git push does not change the hosted simulation.

Use `?view=mobile` on the deployed website URL for the mobile read-only page. The default URL is the desktop monitor with the embedded Wokwi simulation.

## Data shape

The current firmware writes one value to each feed using Adafruit IO's data endpoint, e.g.:

```json
{"value":"50.00"}
```

The dashboard combines the latest feed values into a common record:

```json
{
  "distance_cm": 55.0,
  "level_percent": 50.0,
  "litres": 250.0,
  "generator_on": false,
  "pump_on": false,
  "theft_alarm": false,
  "hours_left": null
}
```

## Access and secrets

- ESP32 writes require `AIO_USERNAME` and a newly generated `AIO_KEY` in a private Wokwi `secrets.h`.
- Dashboard reads require the same username/key in Streamlit Community Cloud's app secrets as `AIO_USERNAME` and `AIO_KEY`.
- Never put the key in this repository, screenshots, source files, or a public Wokwi project. Revoke the previously pasted key.
- Firmware TLS certificate verification must remain enabled. Configure the current CA certificate for `io.adafruit.com` in the private `secrets.h`.

## Integration checklist

1. Create the seven telemetry feeds.
2. Compare Wokwi Serial Monitor HTTP status and Adafruit IO latest telemetry values.
3. Deploy `dashboard/app.py` to Streamlit Community Cloud and configure its app secrets.
4. Open the default website on the desktop; start Wokwi and move its sensor slider or generator switch. Verify Serial Monitor and dashboard telemetry update.
5. Confirm both dashboard views display the new readings, history, and 3D tank.
6. Open the same website with `?view=mobile`; verify readings, graph, and tank are visible but no control widgets appear.
7. Test theft with generator OFF and a drop greater than 5 percentage points within 60 seconds; compare LCD, buzzer, `theft` feed, and dashboard.
8. Test generator ON with gradual decline; verify the hours-left value is available only when a usable trend exists.

The live dashboard displays the firmware alarm and uses an explainable rapid-drop threshold. The separate offline simulator dashboard includes an ML demonstration model trained on synthetic data; it is not validated against real theft observations.

## View graphs in Adafruit IO

Adafruit IO can show graphs without deploying the Python dashboard:

1. Open **Dashboards** and create a dashboard, or open the existing one.
2. Add a **Line Chart** block and select the `level` feed. Choose a time range and title it “Tank level (%)”.
3. Add another **Line Chart** block for `litres` if you want the volume history too.
4. Add **Gauge** blocks for `level` (0–100) and `litres` (0–500), plus **Indicator** blocks for `pump`, `generator`, and `theft`.
5. Save the dashboard and keep the Wokwi simulation running to produce graph data.

The website provides a live Plotly graph, system status, and an interactive WebGL tank that follows the reported level. Its mobile URL is read-only; operate the simulation in the embedded Wokwi window on desktop.

The live visualization uses the Onshape-exported `diesel-tank.gltf` at the repository root. The dashboard embeds the model data into the viewer component, so it does not need a separate asset host.

Out-of-range level feed values are retained in history for diagnosis, excluded from the graph, and flagged in the event log. The live level is recalculated from sensor distance if the level feed is invalid; if both are invalid, the dashboard displays `INVALID` rather than a misleading percentage.
