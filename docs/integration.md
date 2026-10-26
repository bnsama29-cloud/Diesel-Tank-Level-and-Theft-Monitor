# Live Adafruit IO integration

## Architecture

```text
Wokwi ESP32 -- HTTPS, one JSON telemetry value every 3 seconds --> Adafruit IO feed
                                                                    |
                                                   HTTPS history read every 3 seconds
                                                                    v
                                                Streamlit desktop + mobile dashboard
```

The simulated tank capacity is **100 L**, with 5 cm calibrated as full and 105 cm as empty. The circuit remains the simulation control surface; dashboard controls are not used. The desktop page starts with interpretation and graph panels stacked in the left 25% and Wokwi in the right 75%. Drag the vertical splitter to change the left/right widths and the horizontal splitter to resize the interpretation and graph. These panel sizes remain unchanged during telemetry refreshes. Add `?view=mobile` for a read-only dashboard with a link to open Wokwi separately. The live dashboard does not load the 3D tank.

The ESP32 writes one feed point every 3 seconds (20 writes per minute), instead of writing seven separate feed points. The dashboard requests recent feed history every 3 seconds and marks readings stale after 10 seconds. Actual latency depends on Wokwi, Adafruit IO, Streamlit, network, and browser scheduling. The graph shows the recent points returned by Adafruit IO; it is not a permanent database.

## Create the Adafruit IO feed

1. Sign in to [Adafruit IO](https://io.adafruit.com/).
2. Create a feed with the key `tank-telemetry`. The feed key must match the value used in Wokwi and Streamlit.
3. Copy your Adafruit IO username and active **AIO Key** from the account's key page.
4. Keep the key private. If a real AIO key was ever committed or posted publicly, revoke it and create a replacement before continuing.

The account's current rate limits and plan terms can change; verify them in Adafruit IO. At one write every 3 seconds, this firmware sends 20 data points per minute to this feed.

## Configure Streamlit Community Cloud

Deploy `dashboard/app.py` to Streamlit Community Cloud. Under **App settings → Secrets**, add:

```toml
AIO_USERNAME = "your_adafruit_io_username"
AIO_KEY = "your_private_adafruit_io_key"
AIO_FEED_KEY = "tank-telemetry"
```

Save the secrets and reboot the app if it does not restart automatically. Do not commit these values to GitHub.

## Configure Wokwi

1. Make the Wokwi project private before entering a real AIO key. Do not put live keys in a public sketch.
2. Copy `firmware/wokwi/sketch.ino` and the corrected `firmware/wokwi/diagram.json` into the hosted Wokwi project. Git pushes do not update Wokwi.
3. Add a private `secrets.h` based on `firmware/wokwi/secrets.h.example`. Set `AIO_USERNAME` and `AIO_KEY` to the same values used in Streamlit. The firmware writes to the fixed `tank-telemetry` feed; if you choose another feed key, change that path in `sketch.ino` and set the matching `AIO_FEED_KEY` in Streamlit.
4. Put the trusted root CA for `io.adafruit.com` in `AIO_ROOT_CA`. Keep TLS verification enabled; do not replace it with an insecure TLS bypass.
5. Ensure the `LiquidCrystal I2C` library in `firmware/wokwi/libraries.txt` is installed.
6. Start the simulation. In the Serial Monitor, expect `Wokwi Wi-Fi connected.` and `Adafruit IO telemetry: HTTP 200` every 3 seconds.

Keep the private `secrets.h` and AIO key out of GitHub. If Wokwi does not keep that file private in your project, do not use a real credential in a public project.

## Telemetry format

The ESP32 posts one Adafruit IO data point with a string value containing this JSON object:

```json
{
  "timestamp": 1793010000,
  "distance_cm": 55.0,
  "level_percent": 50.0,
  "litres": 50.0,
  "generator_on": false,
  "pump_on": false,
  "theft_alarm": false,
  "hours_left": -1.0
}
```

`hours_left: -1` means no usable consumption estimate is available yet. The dashboard renders it as “—”. The single feed snapshot keeps all values synchronized to one sample.

## Run and verify

1. Add matching AIO username, key, and feed key to Streamlit and the private Wokwi `secrets.h`.
2. Start Wokwi. Confirm Wi-Fi connects and the Serial Monitor logs `Adafruit IO telemetry: HTTP 200` around every 3 seconds.
3. Open the desktop dashboard. It should show **LIVE**, last-received age, fuel in litres and percent, generator, pump, runtime estimate, and a plain-language interpretation.
4. Move the distance slider. Confirm the LCD and LEDs update locally, then the dashboard values and graph follow within a few seconds.
5. Test the pump hysteresis: it should turn ON at or below 20% and turn OFF only above 90%.
6. Turn the generator OFF and drop the level by more than 5 percentage points within one minute. Confirm the firmware alarm and dashboard suspected-theft interpretation.
7. Turn the generator ON and lower the level gradually. Leave the simulation running long enough for the firmware to form a consumption trend; then check the calculated runtime estimate.
8. Open the dashboard with `?view=mobile`. It should be read-only and link to Wokwi. Stop the simulator; after about 10 seconds without a new feed record, the dashboard should label data stale.

## Troubleshooting and limits

- **No HTTP 200:** confirm Wi-Fi, username, AIO key, feed key, and TLS root CA. Read the HTTP status logged by Wokwi and verify that the AIO key has write access.
- **Feed updates but dashboard waits:** confirm Streamlit secrets exactly match the account and feed key, and that the feed's `value` contains the JSON object above.
- **Dashboard shows stale data:** check the feed's latest record timestamp and whether Wokwi continues publishing. The page retains previous values after a request failure but explicitly flags them as stale and reports the error.
- **Generator switch warning:** re-import the corrected `diagram.json`; its switch common is on GPIO 12 and outer pins connect to 3V3/GND.
- **No runtime estimate:** the firmware requires enough valid generator-ON consumption history to estimate a rate.
- **ML is not used in this live dashboard:** theft detection follows the specified deterministic >5%-within-60-seconds rule. The separate offline synthetic model is not a validated real-world theft classifier.
