# Diesel Tank Level and Theft Monitor

An IoT prototype that monitors a diesel tank's level, estimates the remaining fuel, controls a simulated refill pump and flags suspicious fuel loss.

The ESP32 firmware runs in the [Wokwi](https://wokwi.com) simulator, publishes telemetry to Adafruit IO over MQTT (TLS), and a Streamlit dashboard reads it back for remote monitoring.

**Everything here is simulated.** The ultrasonic sensor, ESP32, relay and buzzer are Wokwi parts; the cloud link and dashboard demonstrate the data flow. See [Limitations](#limitations-and-safety).

## How it works

```
HC-SR04 (Wokwi) -> ESP32-S2 firmware -> Adafruit IO feed -> Streamlit dashboard
                        |
          LCD, 3 level LEDs, relay (pump), buzzer
```

1. **Sensor and logic:** the ESP32 converts the HC-SR04 distance into a level percentage and litres.
2. **Local control:** pump hysteresis and theft detection run in the firmware; the dashboard is monitor-only and does not control the pump.
3. **Cloud telemetry:** the firmware publishes one JSON snapshot about every 2.2 s to the `tank-telemetry` feed.
4. **Dashboard:** the Streamlit app polls the Adafruit IO HTTPS API every 2 s and shows the latest values, a 5-minute graph, a runtime estimate and a historical explorer.

## Tank model and rules

| Parameter | Value |
| --- | --- |
| Model capacity | 100 L |
| Full / empty distance | 5 cm / 105 cm |
| Level | `(105 - distance) / (105 - 5) x 100`, clamped to 0-100 % |
| Pump ON | level at or below 20 % |
| Pump OFF | level above 90 % (it stays ON in between) |
| Suspected theft | generator OFF and level drop of more than 5 percentage points within 60 s |
| Stale data | dashboard shows **STALE** when the last reading is 8 s old or more |

The theft flag is a rule-based warning, not proof of theft. The runtime estimate needs at least 60 s of measurable generator-ON fuel decline and comes from simulated readings only.

## Repository layout

| Path | Contents |
| --- | --- |
| [`firmware/wokwi-cloud-fast/`](firmware/wokwi-cloud-fast/) | ESP32 sketch, Wokwi circuit, library list, credentials template and setup notes |
| [`dashboard/`](dashboard/) | Streamlit app, Adafruit IO client, detection logic and secrets template |
| [`requirements.txt`](requirements.txt) | Python dependencies for the dashboard |
| [`poster-items/`](poster-items/) | Poster text, demo flowchart and image assets |

## Setup

**Requirements:** a Wokwi account, an Adafruit IO account with a feed (default key `tank-telemetry`), and Python 3 for running the dashboard locally (or a Streamlit Community Cloud app).

### 1. Firmware (Wokwi)

Follow [`firmware/wokwi-cloud-fast/README.md`](firmware/wokwi-cloud-fast/README.md): create a Wokwi ESP32 project, import `sketch.ino`, `diagram.json` and `libraries.txt`, then add a private `secrets.h` based on `secrets.h.example`.

### 2. Dashboard

The app reads `AIO_USERNAME` and `AIO_KEY` from Streamlit secrets, plus optional `AIO_FEED_KEY` (default `tank-telemetry`) and `AIO_ACK_FEED_KEY` (default `tank-manual-ack`; the cloud firmware does not use it). Copy [`dashboard/secrets.toml.example`](dashboard/secrets.toml.example) to `.streamlit/secrets.toml` in the repository root and fill it in, or paste the same keys into the Streamlit Community Cloud app's Secrets settings.

```
python -m venv .venv
# activate the environment, then:
python -m pip install -r requirements.txt
python -m streamlit run dashboard/app.py
```

## Running the demonstration

1. Start the Wokwi simulation and open the Serial Monitor. Wait for `Wokwi Wi-Fi connected`, then for MQTT to connect and `Cloud update sent`.
2. Open the dashboard and wait for **LIVE**.
3. Type `DEMO`. It runs 14 scripted cases of 10 s each (about 140 s): normal level, pump ON at 20 %, hysteresis hold, pump OFF above 90 %, theft baseline, theft drop, alarm clear, and a generator-ON runtime trend.

Other Serial Monitor commands: a distance from `0` to `105` (manual reading), `AUTO` (back to the HC-SR04 slider), `CLEAR` (clear the theft alarm), `STOP` (cancel the demo). Do not run a second Wokwi publisher on the same Adafruit feed.

Expected checks: 55 cm gives about 50 % / 50 L; 85 cm turns the pump ON; 75 cm keeps it ON; 14 cm (91 %) turns it OFF. Allow a few seconds for network and dashboard polling.

## Limitations and safety

This is a simulation-based prototype. It has not established the accuracy, reliability or safety of real diesel-tank measurement or pump operation, and it is not a real-time safety system. Network and hosting delays affect the dashboard, and the theft rule can raise false alarms. Do not connect it to real fuel equipment without engineering validation, electrical protection and rated switching hardware.

## Security

Never commit `secrets.h`, `.streamlit/secrets.toml` or `.env`; they are listed in `.gitignore`. Do not put real keys in a public Wokwi project, screenshots or README examples. If a working key was ever committed, rotate it in Adafruit IO.

## Project links

- Wokwi simulation: https://wokwi.com/projects/478875514435866625
- Live dashboard: https://diesel-tank-level-and-theft-monitor-gdeuatg2cdraw4zq545ekd.streamlit.app/ (the app currently redirects to a sign-in page, so reviewers may need access; set it to public in Streamlit sharing settings if intended)
