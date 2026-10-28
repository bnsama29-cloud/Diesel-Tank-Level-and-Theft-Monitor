# Demonstration flowchart

Use this as the simple presenter/evaluator sequence. It assumes the cloud-enabled Wokwi version and the dashboard are configured first.

![Diesel tank monitor demonstration flowchart](assets/demo-flowchart.svg)

## Editable Mermaid version

```mermaid
flowchart TD
    A["Before demo: Adafruit feed tank-telemetry and matching private credentials configured"] --> B["Start cloud Wokwi; open Serial Monitor"]
    B --> C["Wait for Wi-Fi/MQTT connected and Cloud update sent"]
    C --> D["Open Streamlit dashboard"]
    D --> E{"Dashboard shows LIVE?"}
    E -- No --> F["Check Wokwi publish log, feed key, credentials, and network"] --> C
    E -- Yes --> G["Set generator ON; enter 55 cm"]
    G --> H["Show about 50% / 50 L; confirm dashboard values"]
    H --> I["Graph appears after at least two readings"]
    I --> J["Set generator OFF; enter 85 cm"]
    J --> K["At 20%: pump turns ON"]
    K --> L["Enter 75 cm"]
    L --> M["At 30%: pump remains ON (hysteresis)"]
    M --> N["Enter 14 cm"]
    N --> O["At about 91%: pump turns OFF"]
    O --> P["Keep generator OFF; enter 55 cm, wait a few seconds, then 65 cm"]
    P --> Q["Show THEFT? on Serial Monitor and suspected-theft dashboard status"]
    Q --> R["Enter CLEAR"]
    R --> S["Set generator ON; enter 45 cm, wait, then gradually increase distance"]
    S --> T{"Runtime estimate available?"}
    T -- No --> U["Keep generator ON and collect a gradual measurable fuel decline"] --> T
    T -- Yes --> V["Show estimated runtime on dashboard"]
    V --> W["Enter AUTO; move HC-SR04 slider"]
    W --> X["Show the fuel-level graph following new readings"]
    X --> Y["End: explain 100 L model, thresholds, cloud delay, and simulation limits"]
```

### Presenter reminders

- Calibration: 5 cm = full; 105 cm = empty. Distance input remains manual until `AUTO`.
- Dashboard values are arranged beside the graph on desktop and stacked on mobile.
- Click `↻` to request a dashboard refresh; it also refreshes automatically.
- Runtime needs generator-ON history with a measurable fuel decline. It will show `—` until the firmware has enough data.
- If freshness reads **STALE**, resolve telemetry connectivity before presenting cloud results.
- This is a simulation. The theft alarm means suspected rapid loss, not confirmed theft; the relay and buzzer must not control real fuel equipment.
