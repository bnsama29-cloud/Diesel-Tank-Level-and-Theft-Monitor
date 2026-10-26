# Shared integration contract

Use the existing Adafruit IO account as the bridge between Wokwi and the dashboard. The ESP32 sends HTTPS updates; the dashboard reads the latest value from each feed. A local WebSocket/MQTT gateway is not needed for this browser-only setup.

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
3. Configure Streamlit secrets and deploy `person2-dashboard-ml/`.
4. Check that the dashboard displays all feed values and the tank fill follows `level`.
5. Test theft with generator OFF and a drop greater than 5 percentage points within 60 seconds; compare LCD, buzzer, `theft` feed, and dashboard.
6. Test generator ON with gradual decline; verify the hours-left value is available only when a usable trend exists.

The current dashboard uses an explainable threshold rule, not a trained ML classifier. Person 2 should only add a learned model after collecting representative normal-use and theft-labeled observations.
