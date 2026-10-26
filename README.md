# ⛽ Diesel Tank Level & Theft Monitor — Python Dashboard

A real-time monitoring dashboard for diesel tank level tracking, pump hysteresis control, and **ML-based theft detection**. Built with Streamlit, scikit-learn, and Plotly.

## 🏗️ Architecture

```
ESP32 / Wokwi ──WebSocket/MQTT──▶ bridge.py ──▶ tank_model.py ──▶ ml_detector.py
                                                                        │
                                                                        ▼
                simulator.py (offline testing) ──────────────▶     app.py (Dashboard)
```

## 📦 Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Train the ML model (generates synthetic data + trains Isolation Forest + Gradient Boosting)
python train_model.py

# 3. Launch the dashboard
streamlit run app.py
```

## 🎬 Demo Test Cases

| # | Scenario | What to Expect |
|---|----------|----------------|
| 1 | **Hysteresis Demo** | Level sweeps Full→Empty→Full. Pump turns ON at 20%, OFF at 90% (hysteresis). |
| 2 | **Theft Demo** | Generator OFF, level drops 20% in 20s. ML detects theft, flashing red alert + buzzer. |
| 3 | **Consumption Demo** | Generator ON, steady 0.5%/s drain. Dashboard shows **hours remaining** countdown. |

Click the scenario buttons on the dashboard to run each demo.

## 🧠 ML Theft Detection

Instead of a rigid "5% drop in 1 minute" rule, we use an **ensemble ML model**:

- **Isolation Forest** — unsupervised anomaly detection (catches novel theft patterns)
- **Gradient Boosting Classifier** — supervised classifier (high accuracy on known patterns)

### Features Used
| Feature | Description |
|---------|-------------|
| `rate_of_change` | Level change per second (30s window) |
| `rate_of_change_10s` | Level change per second (10s window) |
| `rolling_std` | Standard deviation of level readings |
| `drop_magnitude` | Max drop from peak in window |
| `generator_state` | Generator ON (1) or OFF (0) |
| `level_current` | Current level percentage |
| `acceleration` | Rate-of-change of rate-of-change |
| `drop_sharpness` | Ratio of short-term to long-term drop rate |

### Why ML > Fixed Rules?
- Adapts to different theft speeds and patterns
- Reduces false alarms from sensor noise
- Provides **confidence scores** instead of binary alerts
- Can distinguish consumption (gen ON) from theft (gen OFF) contextually

## 🔌 Connecting to Wokwi

1. Your friend's ESP32 should broadcast JSON via WebSocket:
   ```json
   { "distance_cm": 45.2, "generator_on": false, "pump_on": true }
   ```
2. In the dashboard sidebar, select **WebSocket (Wokwi)**
3. Enter the WebSocket URL (default: `ws://localhost:4000`)
4. Click **🔌 Connect WebSocket**

MQTT is also supported with topic `diesel/sensor`.

## 📁 Project Structure

```
├── app.py              # Streamlit dashboard (main entry point)
├── bridge.py           # WebSocket/MQTT data ingestion
├── tank_model.py       # Tank physics & calculations
├── ml_detector.py      # ML anomaly detection (IF + GB ensemble)
├── simulator.py        # Test scenario generator
├── train_model.py      # Synthetic data generation & model training
├── models/
│   └── theft_detector.joblib  # Trained ML model
├── requirements.txt
└── README.md
```

## 🔧 Tank Configuration

Default: **100 cm deep, 500 L cylindrical tank**

Adjustable in the dashboard sidebar:
- Tank depth (cm)
- Tank capacity (L)
- Pump ON threshold (20%)
- Pump OFF threshold (90%)

## License

Academic project — Skill Lab EL
