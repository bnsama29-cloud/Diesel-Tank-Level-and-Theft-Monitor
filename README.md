# Diesel Tank Monitor

This repository contains two Wokwi project variants:

1. **Wokwi only, no dashboard or cloud:** import the files in [`firmware/wokwi-local-only/`](firmware/wokwi-local-only/) into Wokwi. Use its HC-SR04 slider or enter a distance from `0` to `105` in the Serial Monitor. Enter `AUTO` to use the sensor slider again and `CLEAR` to reset the theft alarm.
2. **Wokwi with cloud dashboard:** import [`firmware/wokwi-cloud-fast/`](firmware/wokwi-cloud-fast/) into a separate Wokwi project, then deploy [`dashboard/app.py`](dashboard/app.py) to Streamlit Community Cloud. Configure Adafruit IO and private credentials using the instructions in that Wokwi folder's README.

Both variants use a 100 L tank model, calibrated from 5 cm (full) to 105 cm (empty), with pump hysteresis: ON at or below 20%, OFF only above 90%. The theft alarm triggers when the generator is OFF and the level falls by more than five percentage points within 60 seconds. In the cloud Wokwi project, type `DEMO` in the Serial Monitor to run the scripted presentation; each case is held for 10 seconds for dashboard updates. Numeric input, `AUTO`, and `STOP` remain available to cancel the sequence and return to interactive use.

The cloud dashboard shows latest values beside a five-minute level graph on desktop and stacks them on mobile. The cloud firmware waits for Wokwi Wi-Fi before initializing the tank monitor, then publishes one TLS MQTT snapshot about every 2.2 seconds. Type `DEMO` in Serial Monitor to run the scripted presentation; each case is held for 10 seconds for dashboard updates. Numeric input, `AUTO`, and `STOP` remain available to cancel the sequence. Internet, broker, and hosting latency can vary; this is not a real-time safety system and must not control real fuel equipment.

Install the Python dependencies for the dashboard with `pip install -r requirements.txt`. Keep real Adafruit IO credentials and `secrets.h` private; never commit them or put them in a public Wokwi project.
