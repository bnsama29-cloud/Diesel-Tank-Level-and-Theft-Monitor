# Shared integration contract

Adafruit IO is the background data relay between Wokwi and the hosted dashboard. The user-facing demo is Wokwi plus the Streamlit website; viewers do not need to open the Adafruit IO dashboard. Wokwi sends HTTPS updates, and the website reads feed history and current values. A local WebSocket/MQTT gateway is not needed for this browser-only setup.

## Feeds

Create these seven Adafruit IO feeds with the exact lowercase keys:

| Feed key | Type / example | Meaning |
| --- | --- | --- |
| `distance` | number, `55.0` | Sensor-to-fuel distance in cm |
| `level` | number, `50.0` | Tank full percentage, 0–100 |
| `litres` | number, `250.0` | Estimated fuel volume, 0–500 |
| `generator` | integer, `0` or `1` | Generator OFF / ON |
| `pump` | integer, `0` or `1` | Pump relay OFF / ON |
| `theft` | integer, `0` or `1` | Latched firmware theft alarm |
| `hours-left` | number, `-1` or hours | `-1` means unavailable |

The firmware posts each feed once per 20-second cycle (up to 21 data points/minute). Keep that interval unless the account's current Adafruit IO rate limit has been checked.

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

1. Verify each feed appears in Adafruit IO and receives updated values.
2. Compare Wokwi Serial Monitor HTTP status and Adafruit IO latest feed values.
3. Deploy `dashboard/app.py` to Streamlit Community Cloud and configure its app secrets.
4. Check that the dashboard displays all feed values and the tank fill follows `level`.
5. Test theft with generator OFF and a drop greater than 5 percentage points within 60 seconds; compare LCD, buzzer, `theft` feed, and dashboard.
6. Test generator ON with gradual decline; verify the hours-left value is available only when a usable trend exists.

The live dashboard displays the firmware alarm and uses an explainable rapid-drop threshold. The separate offline simulator dashboard includes an ML demonstration model trained on synthetic data; it is not validated against real theft observations.

## View graphs in Adafruit IO

Adafruit IO can show graphs without deploying the Python dashboard:

1. Open **Dashboards** and create a dashboard, or open the existing one.
2. Add a **Line Chart** block and select the `level` feed. Choose a time range and title it “Tank level (%)”.
3. Add another **Line Chart** block for `litres` if you want the volume history too.
4. Add **Gauge** blocks for `level` (0–100) and `litres` (0–500), plus **Indicator** blocks for `pump`, `generator`, and `theft`.
5. Save the dashboard and keep the Wokwi simulation running to produce graph data.

For the custom mobile monitoring website, deploy `dashboard/app.py` to Streamlit Community Cloud and add the Adafruit username/key under that app's private **Settings → Secrets**. This dashboard adds a level-history Plotly graph, system status, and an interactive WebGL tank that follows the reported level.
