# Demonstration flowchart

Use this as the simple presenter/evaluator sequence. It assumes the cloud-enabled Wokwi version and dashboard are configured first. You can perform the steps manually, or type `DEMO` in Wokwi Serial Monitor to run them automatically. The scripted sequence holds each case for 10 seconds and publishes multiple readings for the dashboard; it cannot confirm that a browser has finished rendering a case.

![Diesel tank monitor demonstration flowchart](assets/demo-flowchart.svg)

## Editable Mermaid version

```mermaid
flowchart TD
    A["Before demo: Adafruit feed tank-telemetry and matching private credentials configured"] --> B["Start cloud Wokwi; open Serial Monitor"]
    B --> C["Wait for Wi-Fi/MQTT connected and Cloud update sent"]
    C --> D["Open Streamlit dashboard"]
    D --> E{"Dashboard shows LIVE?"}
    E -- No --> F["Check Wokwi publish log, feed key, credentials, and network"] --> C
    E -- Yes --> G["Type DEMO to run the sequence, or perform the cases manually"]
    G --> G1["Each scripted case lasts 10 seconds; watch case name and Cloud update sent"]
    G1 --> H["Normal: 55 cm, generator ON; about 50% / 50 L"]
    H --> I["Graph appears after at least two readings"]
    I --> J["Pump ON: 85 cm, generator OFF; about 20%"]
    J --> K["Pump turns ON"]
    K --> L["Hysteresis: 75 cm; pump stays ON at about 30%"]
    L --> M["Pump OFF: 14 cm; about 91%, pump turns OFF"]
    M --> O["Theft baseline: 55 cm, generator OFF"]
    O --> O1["Theft drop: 65 cm after baseline"]
    O1 --> Q["Show THEFT? on Serial Monitor and dashboard"]
    Q --> R["Enter CLEAR"]
    R --> S["Generator ON; gradual scripted level decline"]
    S --> T{"Runtime estimate available?"}
    T -- No --> U["Keep generator ON and collect a gradual measurable fuel decline"] --> T
    T -- Yes --> V["Show estimated runtime on dashboard"]
    V --> W["Enter AUTO; move HC-SR04 slider"]
    W --> X["Show the fuel-level graph following new readings"]
    X --> Y["End: explain 100 L model, thresholds, cloud delay, and simulation limits"]
```

### Presenter reminders

- Calibration: 5 cm = full; 105 cm = empty. Distance input remains manual until `AUTO`.
- To run the scripted cloud demo, type `DEMO` in Serial Monitor. It takes about 140 seconds, with a 10-second display window per case.
- Enter a distance to interrupt the script and resume manual input; enter `AUTO` or `STOP` to cancel and resume the ultrasonic slider.
- Dashboard values are arranged beside the graph on desktop and stacked on mobile.
- Click `↻` to request a dashboard refresh; it also refreshes automatically.
- Runtime needs at least 60 seconds of generator-ON history with a measurable fuel decline. It will show `—` until the firmware has enough data; the scripted runtime segment is about 70 seconds.
- The sketch holds a case for 10 seconds but does not know whether the browser has rendered it. Confirm the cloud update log and **LIVE** freshness on the dashboard.
- If freshness reads **STALE**, resolve telemetry connectivity before presenting cloud results.
- This is a simulation. The theft alarm means suspected rapid loss, not confirmed theft; the relay and buzzer must not control real fuel equipment.
