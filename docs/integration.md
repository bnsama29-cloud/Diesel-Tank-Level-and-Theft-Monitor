# Shared integration contract

Adafruit IO is the background data relay between Wokwi and the hosted website. The desktop dashboard embeds the public Wokwi project; start the simulator inside that page. The simulation publishes telemetry; the website reads it and can send virtual sensor/switch inputs back to the ESP32. A mobile URL provides the same live readings, graph, and 3D tank in read-only mode, without embedding Wokwi or showing controls. Viewers do not need to open the Adafruit IO dashboard.

## Feeds

Create these eight Adafruit IO feeds with the exact lowercase keys:

| Feed key | Type / example | Meaning |
| --- | --- | --- |
| `distance` | number, `55.0` | Sensor-to-fuel distance in cm |
| `level` | number, `50.0` | Tank full percentage, 0–100 |
| `litres` | number, `250.0` | Estimated fuel volume, 0–500 |
| `generator` | integer, `0` or `1` | Generator OFF / ON |
| `pump` | integer, `0` or `1` | Pump relay OFF / ON |
| `theft` | integer, `0` or `1` | Latched firmware theft alarm |
| `hours-left` | number, `-1` or hours | `-1` means unavailable |
| `command` | integer, `0` or encoded input | `0` returns control to Wokwi; nonzero values are dashboard virtual inputs |

The firmware posts each telemetry feed once per 20-second cycle (up to 21 data points/minute) and checks the `command` feed every 10 seconds. Create the `command` feed before enabling dashboard controls.

## Bidirectional simulation controls

The desktop page (the app URL without a query string) embeds the Wokwi simulation and has a virtual distance slider and generator toggle. **Apply dashboard inputs** writes `10000 + round(distance_cm * 10) + (2000 if generator_on else 0)` to `command`; `0` releases the override. The Wokwi firmware polls it every 10 seconds, uses the virtual inputs in the tank/pump/theft logic, and publishes the resulting telemetry. The desktop dashboard and mobile read-only page then show the updated readings, history graph, and 3D tank.

If the physical HC-SR04 distance slider or generator switch is changed in Wokwi while remote inputs are active, the firmware returns control to Wokwi and clears the command. The remote inputs affect firmware behavior and reported readings; they do not move Wokwi's component graphics. **Return control to Wokwi** in the desktop page releases the virtual inputs manually.

Use `?view=mobile` on the deployed website URL for the mobile read-only page. The default URL is the desktop control room with the embedded Wokwi simulation.

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
- Set a separate private `CONTROL_PASSWORD` secret to protect dashboard-to-Wokwi commands. Never share it in the repository or mobile bookmark.
- Never put the key in this repository, screenshots, source files, or a public Wokwi project. Revoke the previously pasted key.
- Firmware TLS certificate verification must remain enabled. Configure the current CA certificate for `io.adafruit.com` in the private `secrets.h`.

## Integration checklist

1. Create the seven telemetry feeds and the `command` feed.
2. Compare Wokwi Serial Monitor HTTP status and Adafruit IO latest telemetry values.
3. Deploy `dashboard/app.py` to Streamlit Community Cloud and configure its app secrets.
4. Open the default website on the desktop; apply a distance/generator change and verify Wokwi Serial Monitor and dashboard telemetry update.
5. Move Wokwi's sensor slider or generator switch; verify it takes control back and both dashboard views update.
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

The website provides a live Plotly graph, system status, and an interactive WebGL tank that follows the reported level. Its mobile URL is read-only; use the default desktop URL for simulation controls.

The live visualization uses the Onshape-exported `diesel-tank.gltf` at the repository root. The dashboard embeds the model data into the viewer component, so it does not need a separate asset host.
