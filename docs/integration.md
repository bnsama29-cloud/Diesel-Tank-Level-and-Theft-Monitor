# Fast Adafruit IO integration

## Architecture

```text
Wokwi ESP32 -- persistent TLS MQTT, one JSON point about every 2.2 seconds --> Adafruit IO
                                                                                |
                                                        HTTPS history read every 2 seconds
                                                                                v
                                                     Responsive Streamlit dashboard
                                                     latest values | level graph
```

The tank model is 100 L: 5 cm is full and 105 cm is empty. The page shows the current values to the left of the graph on desktop and stacks them on mobile. Wokwi is opened separately; the dashboard does not embed it. The offline project in `firmware/wokwi-local-only/` remains cloud-free, while this quick-cloud route is in `firmware/wokwi-cloud-fast/`.

The cloud sketch reuses the local project's controls and behavior: move the HC-SR04 slider or enter `0`–`105` in the Serial Monitor. A typed number remains active for repeated readings until you enter `AUTO`; no dashboard acknowledgment is required. `CLEAR` resets the theft alarm.

The cloud sketch keeps one TLS MQTT connection open instead of opening a new HTTPS/TLS connection for every upload. It publishes at a 2.2-second minimum interval (about 27 data points per minute), leaving headroom under Adafruit IO's current free-account limit of 30 points per minute. The dashboard reads feed history every 2 seconds and flags data older than 8 seconds as stale. These are target intervals; network, broker, hosting, and browser latency can vary. Check current Adafruit IO plan limits before using other devices or feeds.

## Create the Adafruit IO feed

1. Sign in to [Adafruit IO](https://io.adafruit.com/).
2. Create one feed with the key `tank-telemetry`.
3. Copy your Adafruit IO username and active AIO key from the account's key page.
4. Keep the key private. If a real AIO key was committed or posted publicly, revoke it and create a replacement.

## Configure Streamlit Community Cloud

Deploy `dashboard/app.py` to Streamlit Community Cloud. Under **App settings → Secrets**, add:

```toml
AIO_USERNAME = "your_adafruit_io_username"
AIO_KEY = "your_private_adafruit_io_key"
AIO_FEED_KEY = "tank-telemetry"
```

Save the secrets and reboot the app if it does not restart automatically. Never commit these values to GitHub.

## Configure Wokwi

1. Create a separate Wokwi ESP32-S2 project. Copy `sketch.ino`, `diagram.json`, and `libraries.txt` from `firmware/wokwi-cloud-fast/`. Git pushes do not update a hosted Wokwi project.
2. Add a private `secrets.h` based on `firmware/wokwi-cloud-fast/secrets.h.example`. Set `AIO_USERNAME` and `AIO_KEY` to the same values used in Streamlit; use `tank-telemetry` for `AIO_FEED_KEY`.
3. Put the trusted root CA certificate for `io.adafruit.com` in `AIO_ROOT_CA`. TLS certificate verification must remain enabled.
4. Ensure the `LiquidCrystal I2C` and `PubSubClient` libraries are installed.
5. Start the simulation. The Serial Monitor should report Wi-Fi and MQTT connection status and then print `Cloud update sent: {...}` after successful publications.

Do not put real credentials in a public Wokwi project or commit `secrets.h`. If Wokwi cannot keep that file private, use only a test key that can be revoked.

## Telemetry format

Each Adafruit IO feed value is a JSON object:

```json
{
  "timestamp": 1793010000,
  "distance_cm": 55.0,
  "level_percent": 50.0,
  "litres": 50.0,
  "generator_on": false,
  "pump_on": false,
  "theft_alarm": false,
  "hours_left": -1.0,
  "manual_request_id": 0
}
```

`hours_left: -1` means no usable consumption estimate is available yet; the dashboard renders it as “—”. `manual_request_id` stays zero because this project does not wait for dashboard acknowledgments.

## Run and verify

1. Add matching Adafruit IO username, key, and feed key to Streamlit secrets and private Wokwi `secrets.h`.
2. Start Wokwi. Confirm Wi-Fi and MQTT connect, and that the Serial Monitor prints `Cloud update sent`.
3. Open the dashboard. It should show **LIVE**, fuel in litres and percent, generator and pump state, runtime, and the level graph.
4. Move the distance slider, or enter a distance such as `55` in the Serial Monitor. Confirm the LCD/LEDs update and the values/graph follow shortly. Enter `AUTO` to return to the slider.
5. Test pump hysteresis: it turns ON at or below 20% and turns OFF only above 90%.
6. Turn the generator OFF and lower the level by more than five percentage points within one minute. Confirm the firmware alarm and dashboard suspected-theft interpretation.
7. Turn the generator ON and lower the level gradually. Leave the simulation running long enough for the firmware to form a consumption trend, then check the runtime estimate.
8. Stop Wokwi. After about 8 seconds without new feed records, the dashboard should flag the values as stale.

## Troubleshooting and limits

- **MQTT connection does not succeed:** confirm Wi-Fi is connected, the username/key are correct, the `tank-telemetry` feed exists, the root CA is current and complete, and the device clock has synchronized. Keep TLS verification enabled.
- **Feed updates but dashboard waits:** confirm Streamlit secrets match the same account and feed key, and that the feed's `value` contains the JSON object above.
- **Dashboard shows stale data:** check the feed's latest record and whether Wokwi continues to publish. The page retains prior values after a request failure, flags them as stale, and reports the error.
- **Update rate is limited:** the sketch publishes one feed point per update, every 2.2 seconds. Adafruit IO limits are shared across devices using the account; do not lower the interval without checking current terms.
- **Generator switch warning:** use the provided `diagram.json`; its switch common is on GPIO 12 and outer pins connect to 3V3/GND.
- **No runtime estimate:** the firmware needs enough valid generator-ON fuel-consumption history to estimate a rate.
- **ML is not used in this live dashboard:** theft detection follows the deterministic >5%-within-60-seconds rule. The separate offline synthetic model is not a validated real-world classifier.

The original HTTPS/acknowledgment sketch remains in `firmware/wokwi/`; the offline version remains in `firmware/wokwi-local-only/`.
