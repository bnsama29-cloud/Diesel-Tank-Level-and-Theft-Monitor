# Demonstration evidence checklist

Save Wokwi, Adafruit IO, and dashboard screenshots under `docs/evidence/`. Do not include AIO keys or personal Wi-Fi details in screenshots.

| Test | Setup | Expected result | Actual |
| --- | --- | --- | --- |
| Full tank | Distance 5 cm | 100%, 500 L, pump OFF, FULL LED | LCD showed 100%, 500 L: [Wokwi screenshot](./evidence/01-full-tank-wokwi.png). |
| Low tank | Distance 95 cm | 10%, 50 L, pump ON, LOW LED | LCD showed 9%, 46 L: [Wokwi screenshot](./evidence/02-distance-95cm-observed.png). |
| Hysteresis hold | Start low, raise to 50% | Pump stays ON | Pending |
| Hysteresis stop | Raise above 90% | Pump turns OFF | Pending |
| Medium level | Distance 55 cm | 50%, 250 L, MEDIUM LED | LCD showed 50%, 248 L: [Wokwi screenshot](./evidence/03-distance-55cm-observed.png). |
| Generator ON | Switch ON, stable/gradual level | Generator ON, no theft alarm | Pending: the corrected local wiring below still needs to be reloaded into the hosted Wokwi project and verified. |
| Theft alarm | Generator OFF, >5 point drop in 60 seconds | `THEFT?`, buzzer, `theft_alarm: true` in the JSON feed | Pending |
| Empty tank | Distance at/above 105 cm | 0%, 0 L, pump ON | Pending |
| Cloud integration | Wokwi posts one JSON point to the `tank-telemetry` Adafruit IO feed every 3 seconds | Dashboard receives the new feed record and marks it live | Pending: the current single-feed route still needs live verification. |
| Dashboard readings + graph | Open deployed dashboard and vary the Wokwi distance slider | Values and graph follow the latest JSON feed; stale status appears when publishing stops | Pending |

Suggested filenames for the remaining live captures: `04-pump-hysteresis-wokwi.png`, `05-generator-on-wokwi.png`, `06-theft-alarm-wokwi.png`, `07-empty-tank-wokwi.png`, `08-adafruit-json-feed.png`, and `09-dashboard-live-graph.png`.

## Generator switch wiring note

The public Wokwi project is separate from the files in this repository. Toggling its generator switch produced Wokwi `Short circuit!` warnings between ESP32 GND and 3V3, so the generator-ON case is not verified. In the local [Wokwi diagram](../firmware/wokwi/diagram.json), the switch common pin (`sw1:2`) now connects to GPIO 12, with the two outer switch pins connected to 3V3 and GND. This lets the input read HIGH or LOW without directly bridging the supply rails. Reload the corrected diagram into the hosted project before testing the generator-ON case.

## Illustrative dashboard graphs

The following report-ready charts are generated example data, not screenshots of a live Wokwi run, cloud broker, or dashboard session. Use them to explain the expected behavior only; replace them with captured live evidence when the corresponding test is run.

| Example | Chart |
| --- | --- |
| Pump turns on at or below 20% and stays on until above 90% | [Pump hysteresis example](./evidence/example-pump-hysteresis.png) |
| Generator OFF with a rapid level drop that crosses the theft threshold | [Theft drop example](./evidence/example-theft-drop.png) |
| Generator ON with a gradual decline and illustrative remaining-hours estimate | [Generator consumption example](./evidence/example-generator-consumption.png) |
