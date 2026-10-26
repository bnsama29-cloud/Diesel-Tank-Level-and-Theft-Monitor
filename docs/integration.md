# Live Adafruit IO integration

## Architecture

```text
Wokwi ESP32 -- HTTPS, one JSON telemetry value every 3 seconds --> Adafruit IO feed
                                                                    |
                                                   HTTPS history read every 3 seconds
                                                                    v
                                                Streamlit desktop + mobile dashboard
                                                         |
                                         manual-reading acknowledgment POST
                                                         v
                                              Adafruit IO acknowledgment feed
                                                         |
                                              acknowledgment check by ESP32
```

The simulated tank capacity is **100 L**, with 5 cm calibrated as full and 105 cm as empty. The circuit remains the simulation control surface; dashboard controls are not used. The desktop page starts with interpretation and graph panels stacked in the left 25% and Wokwi in the right 75%. Drag the vertical splitter to change the left/right widths and the horizontal splitter to resize the interpretation and graph. These panel sizes remain unchanged during telemetry refreshes. Add `?view=mobile` for a read-only dashboard with a link to open Wokwi separately. The live dashboard does not load the 3D tank.

For level demonstrations, use the ultrasonic sensor slider as usual, or enter a distance from `0` to `105` in the Wokwi Serial Monitor and send the line. A numeric command temporarily selects manual-distance mode and sends one reading. The firmware then waits for the dashboard to write that reading's ID to `tank-manual-ack` before it prompts for another number. Enter `AUTO` at any time to cancel manual mode and return to periodic ultrasonic readings. In manual mode, the sensor input is bypassed, but generator-switch input, tank calculations, pump control, theft detection, LCD/LED/buzzer outputs, and cloud publishing continue to work.

The ESP32 writes one feed point every 3 seconds (20 writes per minute), instead of writing seven separate feed points. The dashboard requests recent feed history every 3 seconds and marks readings stale after 10 seconds. Actual latency depends on Wokwi, Adafruit IO, Streamlit, network, and browser scheduling. The graph shows the recent points returned by Adafruit IO; it is not a permanent database.

## Create the Adafruit IO feed

1. Sign in to [Adafruit IO](https://io.adafruit.com/).
2. Create feeds with the keys `tank-telemetry` and `tank-manual-ack`. The dashboard writes a reading ID to the acknowledgment feed after it receives a manual-distance reading; Wokwi checks that feed before asking for another number.
3. Copy your Adafruit IO username and active **AIO Key** from the account's key page.
4. Keep the key private. If a real AIO key was ever committed or posted publicly, revoke it and create a replacement before continuing.

The account's current rate limits and plan terms can change; verify them in Adafruit IO. At one write every 3 seconds, this firmware sends 20 data points per minute to this feed.

## Configure Streamlit Community Cloud

Deploy `dashboard/app.py` to Streamlit Community Cloud. Under **App settings → Secrets**, add:

```toml
AIO_USERNAME = "your_adafruit_io_username"
AIO_KEY = "your_private_adafruit_io_key"
AIO_FEED_KEY = "tank-telemetry"
AIO_ACK_FEED_KEY = "tank-manual-ack"
```

Save the secrets and reboot the app if it does not restart automatically. Do not commit these values to GitHub.

## Configure Wokwi

1. Make the Wokwi project private before entering a real AIO key. Do not put live keys in a public sketch.
2. Copy `firmware/wokwi/sketch.ino` and the corrected `firmware/wokwi/diagram.json` into the hosted Wokwi project. Git pushes do not update Wokwi.
3. Add a private `secrets.h` based on `firmware/wokwi/secrets.h.example`. Set `AIO_USERNAME` and `AIO_KEY` to the same values used in Streamlit. The firmware writes to the fixed `tank-telemetry` feed; if you choose another feed key, change that path in `sketch.ino` and set the matching `AIO_FEED_KEY` in Streamlit.
4. Put the trusted root CA for `io.adafruit.com` in `AIO_ROOT_CA`. Keep TLS verification enabled; do not replace it with an insecure TLS bypass.
5. Ensure the `LiquidCrystal I2C` library in `firmware/wokwi/libraries.txt` is installed.
6. Start the simulation. In the Serial Monitor, expect `Wokwi Wi-Fi connected.` and successful Adafruit IO HTTP status lines. To test manual distance, enter a number from `0` to `105` and send it; enter `AUTO` to switch back to the ultrasonic slider.

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
  "hours_left": -1.0,
  "manual_request_id": 0
}
```

`hours_left: -1` means no usable consumption estimate is available yet. The dashboard renders it as “—”. The single feed snapshot keeps all values synchronized to one sample.
`manual_request_id: 0` identifies an ordinary sensor reading. A positive ID marks a one-time serial-entered reading; after the dashboard receives it, the dashboard writes that ID to the separate acknowledgment feed.

## Run and verify

1. Add matching AIO username, key, and feed key to Streamlit and the private Wokwi `secrets.h`.
2. Start Wokwi. Confirm Wi-Fi connects and the Serial Monitor prints `Adafruit IO value: {...}` followed by `Adafruit IO telemetry: HTTP 200` for successful posts.
3. Open the desktop dashboard. It should show **LIVE**, last-received age, fuel in litres and percent, generator, pump, runtime estimate, and a plain-language interpretation.
4. Move the distance slider, or type a distance such as `55` into the Serial Monitor and send it. Confirm the LCD and LEDs update locally, then the dashboard values and graph follow within a few seconds. The dashboard acknowledgment allows Wokwi to prompt for the next number. Type `AUTO` to return to periodic HC-SR04 slider readings.
5. Test the pump hysteresis: it should turn ON at or below 20% and turn OFF only above 90%.
6. Turn the generator OFF and drop the level by more than 5 percentage points within one minute. Confirm the firmware alarm and dashboard suspected-theft interpretation.
7. Turn the generator ON and lower the level gradually. Leave the simulation running long enough for the firmware to form a consumption trend; then check the calculated runtime estimate.
8. Open the dashboard with `?view=mobile`. It should be read-only and link to Wokwi. Stop the simulator; after about 10 seconds without a new feed record, the dashboard should label data stale.

## Troubleshooting and limits

- **No HTTP 200:** confirm Wi-Fi, username, AIO key, feed key, and TLS root CA. Read the HTTP status logged by Wokwi and verify that the AIO key has write access.
- **Manual input is waiting for acknowledgment:** confirm the `tank-manual-ack` feed exists and the dashboard is running with matching AIO credentials. If you use a different acknowledgment feed, set the same `AIO_ACK_FEED_KEY` in Streamlit secrets and Wokwi's private `secrets.h`.
- **Slow Serial Monitor updates:** the local sensor and control loop runs continuously, but the HTTPS publish is synchronous and can block while connecting to Adafruit IO. The 3-second publish interval is a target minimum, not a guarantee; network/TLS time and the 5-second request timeout can stretch the time between completed uploads. The JSON line is printed immediately before each upload attempt.
- **Feed updates but dashboard waits:** confirm Streamlit secrets exactly match the account and feed key, and that the feed's `value` contains the JSON object above.
- **Dashboard shows stale data:** check the feed's latest record timestamp and whether Wokwi continues publishing. The page retains previous values after a request failure but explicitly flags them as stale and reports the error.
- **Generator switch warning:** re-import the corrected `diagram.json`; its switch common is on GPIO 12 and outer pins connect to 3V3/GND.
- **No runtime estimate:** the firmware requires enough valid generator-ON consumption history to estimate a rate.
- **ML is not used in this live dashboard:** theft detection follows the specified deterministic >5%-within-60-seconds rule. The separate offline synthetic model is not a validated real-world theft classifier.
