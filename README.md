# Diesel Tank Level and Theft Monitor

Browser-first starter for the Wokwi ESP32, Adafruit IO, Python dashboard, and tank visualization. The project is divided so each teammate can work in a separate folder and use the shared data contract in [`integration/README.md`](integration/README.md).

## Project folders

| Folder | Owner | Contents |
| --- | --- | --- |
| [`person1-esp32/`](person1-esp32/) | Person 1 | Wokwi circuit, ESP32 firmware, pin map, cloud setup |
| [`person2-dashboard-ml/`](person2-dashboard-ml/) | Person 2 | Streamlit dashboard, cloud feed reader, theft trend rule |
| [`person3-3d-tank/`](person3-3d-tank/) | Person 3 | Browser tank viewer, ready for the Onshape model |
| [`integration/`](integration/) | Everyone | Shared Adafruit IO feed names and integration checklist |
| [`report-evidence/`](report-evidence/) | Everyone | Screenshot and test-results checklist |

## Free browser workflow

1. Open the Wokwi project and save the firmware and circuit files from `person1-esp32/`.
2. Create or use the seven Adafruit IO feeds listed in the integration guide.
3. Put the new Adafruit IO key in Wokwi's private `secrets.h` and Streamlit's app secrets. Never commit either secrets file.
4. Person 2 deploys `person2-dashboard-ml/` from this GitHub repository to Streamlit Community Cloud.
5. Person 3 replaces the starter tank drawing with the exported Onshape GLB/GLTF asset when ready.

No local software is required for the intended workflow: edit the repository with GitHub's web editor, run the circuit in Wokwi, edit the model in Onshape, and host the dashboard with Streamlit Community Cloud. Python tests are optional and can be run in a browser-based development environment.

## Safety and current status

- The Adafruit key and Wi-Fi password pasted into the original project chat are considered exposed. Revoke/regenerate the Adafruit IO key and change the Wi-Fi password before using those accounts again.
- This repository intentionally contains no usable credentials. `person1-esp32/secrets.h.example` is a template; create the ignored `secrets.h` privately in Wokwi.
- Pump output in Wokwi is a simulated relay signal. Do not connect a real pump or mains voltage without a properly rated, isolated driver and qualified supervision.
- The core level conversion and pump hysteresis are implemented. Cloud publishing and dashboard polling require the team's newly generated private Adafruit IO key and should be validated in Wokwi before marking integration tests as passed.
- The dashboard currently uses the required explainable rapid-drop threshold. It is not a trained ML model; collect labeled samples before claiming machine-learning classification.

## First team milestone

Have Person 1 verify the local Wokwi tests, then publish to all seven Adafruit feeds. Have Person 2 confirm the same latest readings on the dashboard, and Person 3 confirm that the tank fill follows `level`. Record actual results and screenshots in [`report-evidence/README.md`](report-evidence/README.md).
