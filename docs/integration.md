# Live MQTT integration

## Architecture

```text
Wokwi ESP32 -- MQTT over TLS (one retained JSON message every 2 seconds) --> HiveMQ Cloud
                                                                               |
                                                              MQTT subscription over TLS
                                                                               v
                                                        Streamlit desktop + mobile dashboard
```

Adafruit IO is no longer part of the live path. The dashboard subscribes to the same cloud MQTT topic as the ESP32 publishes to. The Wokwi circuit remains the only simulation control surface; `?view=mobile` is read-only.

The firmware publishes every 2 seconds and the Streamlit fragment redraws every 2 seconds. Typical display latency should be a few seconds, depending on Wokwi, broker, network, and browser scheduling. The dashboard marks telemetry stale after 8 seconds. MQTT messages are retained so a dashboard that connects after the simulator can receive its latest state. The dashboard keeps up to 3,600 readings in process memory; this chart history resets if the Streamlit app restarts and is not a permanent database.

## Create a free broker

This configuration targets a HiveMQ Cloud serverless cluster:

1. Create a free HiveMQ Cloud account and a serverless cluster.
2. Copy the cluster hostname (hostname only, without `mqtts://`), TLS MQTT port `8883`, and create a username/password in the cluster's access management.
3. Permit that username to publish and subscribe to `diesel-tank/telemetry` (or configure another single topic consistently on both ends).
4. Obtain the broker's trusted root CA PEM from its TLS/certificate documentation. Do not disable certificate verification.

The free broker tier is subject to the provider's current usage and connection limits; check its current plan before a long demonstration.

## Configure the dashboard

Deploy `dashboard/app.py` to Streamlit Community Cloud. Under **App settings → Secrets**, add:

```toml
MQTT_HOST = "your-cluster-hostname"
MQTT_PORT = 8883
MQTT_USERNAME = "your_mqtt_username"
MQTT_PASSWORD = "your_private_mqtt_password"
MQTT_TOPIC = "diesel-tank/telemetry"
```

The Streamlit MQTT client uses TLS and the Python runtime's trusted CA store to verify the broker certificate. Do not commit broker credentials.

## Configure Wokwi

1. Copy `firmware/wokwi/secrets.h.example` into a private `secrets.h` file in the Wokwi project.
2. Set `MQTT_HOST`, `MQTT_PORT`, `MQTT_USERNAME`, `MQTT_PASSWORD`, and `MQTT_TOPIC` to the same broker settings as the dashboard. Paste the broker's trusted root CA PEM into `MQTT_ROOT_CA`.
3. Add the `PubSubClient` library listed in `firmware/wokwi/libraries.txt` if Wokwi does not add it automatically.
4. Copy `firmware/wokwi/sketch.ino` into the hosted Wokwi sketch and save. Git pushes do not update the hosted Wokwi project.
5. Reload `firmware/wokwi/diagram.json` too. Its generator switch common pin is wired to GPIO 12; the earlier hosted diagram connected the switch in a way that caused a short-circuit warning.
6. Start the simulation. In the Serial Monitor, expect `Wokwi Wi-Fi connected.`, `MQTT broker connected.`, then `MQTT telemetry published.` at about 2-second intervals.

Keep `secrets.h` private and never paste the broker username/password or CA-containing secrets file into a public sketch or GitHub.

## Telemetry message

The ESP32 publishes one JSON object per sample to `diesel-tank/telemetry`:

```json
{
  "timestamp": 1793010000,
  "distance_cm": 55.0,
  "level_percent": 50.0,
  "litres": 250.0,
  "generator_on": false,
  "pump_on": false,
  "theft_alarm": false,
  "hours_left": -1.0
}
```

`hours_left: -1` means no usable consumption estimate is available yet. The dashboard shows that as “Not available yet”.

## Run and verify

1. Add identical broker host, port, credentials, and topic to Wokwi and Streamlit secrets.
2. Start the hosted Wokwi simulation and confirm the MQTT connection and publish messages in its Serial Monitor.
3. Open the desktop dashboard, start the embedded simulation, and move the distance slider. The LCD should update locally; the dashboard metrics, graph, and 3D fuel view should follow within a few seconds.
4. Toggle the corrected generator switch and verify the dashboard state follows.
5. Open the same site with `?view=mobile`; it should show live data, graph, and 3D tank but no simulation controls.
6. Stop the Wokwi simulation. After 8 seconds without a message, the dashboard should label the reading stale.
7. Check theft and generator-consumption behavior separately; do not mark those live cases passed until their LCD/indicator and dashboard behavior are captured.

## Limits and troubleshooting

- **No MQTT messages:** verify Wokwi Wi-Fi, hostname, TLS port, credentials, certificate PEM, topic spelling, and broker ACL. Compare Serial Monitor messages with the dashboard broker configuration.
- **Dashboard says it is waiting:** confirm Streamlit Community Cloud can reach the broker on outbound TLS port `8883`, then check the browser's page refresh and the broker connection limit.
- **Metrics update but graph resets after redeploy:** chart history is intentionally process-local and not persisted. Add a database only if retained long-term history is required.
- **Generator switch short warning:** re-import the corrected `diagram.json`; do not continue toggling the old public diagram.
- **No real ML classifier:** the separate offline simulator's model is trained on synthetic examples and is not validated for real theft detection.
