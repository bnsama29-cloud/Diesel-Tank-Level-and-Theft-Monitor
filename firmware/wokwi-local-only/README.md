# Wokwi local-only diesel tank monitor

This is the standalone Wokwi-only version of the project. It does not use Wi-Fi, Adafruit IO, Streamlit, credentials, or dashboard acknowledgments. For the cloud-enabled version with a live dashboard, use `firmware/wokwi-cloud-fast/` and `dashboard/app.py`.

## Open in Wokwi

Create a separate Wokwi ESP32 project and import the files in this folder:

- `sketch.ino`
- `diagram.json`
- `libraries.txt`

The LCD dependency is `LiquidCrystal I2C`. Start the simulation and open its Serial Monitor.

## Controls

- Click the HC-SR04 and use its distance slider for continuous sensor readings.
- In the Serial Monitor, enter a distance from `0` to `105` and send the line to use a manually simulated distance.
- Enter `AUTO` to return to the HC-SR04 slider.
- Enter `CLEAR` to clear the latched theft alarm before another test.
- Use the slide switch to set generator OFF or ON.

The Serial Monitor reports distance, fuel percentage and litres, generator state, pump/relay state, active level LED, theft alarm, buzzer, runtime estimate, and control thresholds once per second. It prints a theft alert immediately when the configured theft rule is met.

## Tank model and behavior

- Capacity: 100 L.
- Calibration: 5 cm is full; 105 cm or farther is empty.
- Pump turns ON at or below 20% and turns OFF only above 90%.
- Suspected theft is raised when the generator is OFF and the level drops by more than 5 percentage points within 60 seconds.
- Runtime estimate uses observed fuel decline while the generator is ON and appears after enough history is available.

The relay, generator, and pump are simulated indicators; the circuit does not run real equipment.
