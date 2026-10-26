# Demonstration evidence checklist

Save Wokwi, Adafruit IO, dashboard, and tank-viewer screenshots in this folder after capturing them. Do not include account keys, private feed URLs, or personal Wi-Fi details in screenshots.

| Test | Setup | Expected result | Actual |
| --- | --- | --- | --- |
| Full tank | Distance 5 cm | 100%, 500 L, pump OFF, FULL LED | Pending |
| Low tank | Distance 95 cm | 10%, 50 L, pump ON, LOW LED | Pending |
| Hysteresis hold | Start low, raise to 50% | Pump stays ON | Pending |
| Hysteresis stop | Raise above 90% | Pump turns OFF | Pending |
| Medium level | Distance 55 cm | 50%, 250 L, MEDIUM LED | Pending |
| Generator ON | Switch ON, stable/gradual level | Generator ON, no theft alarm | Pending |
| Theft alarm | Generator OFF, >5 point drop in 60 seconds | `THEFT?`, buzzer, alarm feed ON | Pending |
| Empty tank | Distance at/above 105 cm | 0%, 0 L, pump ON | Pending |
| Cloud integration | Run Wokwi with valid private key | Seven Adafruit feeds update | Pending |
| Dashboard + tank | Open deployed dashboard | Readings and tank fill follow feeds | Pending |

Suggested filenames: `01_full_tank.png`, `02_low_level_pump_on.png`, `03_pump_hysteresis.png`, `04_medium_level.png`, `05_generator_on.png`, `06_theft_alarm.png`, `07_empty_tank.png`, `08_adafruit_feeds.png`, `09_dashboard_tank.png`.
