"""
Diesel Tank Level & Theft Monitor — Streamlit Dashboard
========================================================

Central control panel for the diesel tank monitoring system.
Captures Wokwi data stream or runs built-in simulations, displays
live gauges, manages pump hysteresis, and runs ML-based theft detection.

Run with:
    streamlit run app.py
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
import time
import os
import sys
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Project imports
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(__file__))

from tank_model import TankConfig, TankModel, TankState
from simulator import TankSimulator, Scenario, SimReading
from ml_detector import TheftDetector
from bridge import DataBridge

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Diesel Tank Monitor",
    page_icon="⛽",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS for LED indicators and alerts
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    /* Status LED styles */
    .led {
        display: inline-block;
        width: 22px; height: 22px;
        border-radius: 50%;
        margin: 0 6px;
        box-shadow: inset 0 -2px 4px rgba(0,0,0,0.3);
        vertical-align: middle;
    }
    .led-red    { background: #ff4444; box-shadow: 0 0 12px #ff4444, inset 0 -2px 4px rgba(0,0,0,0.3); }
    .led-yellow { background: #ffbb33; box-shadow: 0 0 12px #ffbb33, inset 0 -2px 4px rgba(0,0,0,0.3); }
    .led-green  { background: #00C851; box-shadow: 0 0 12px #00C851, inset 0 -2px 4px rgba(0,0,0,0.3); }
    .led-off    { background: #444; }

    /* Theft alert banner */
    .theft-alert {
        background: linear-gradient(135deg, #ff0000, #cc0000);
        color: white;
        padding: 20px;
        border-radius: 12px;
        text-align: center;
        font-size: 1.4em;
        font-weight: bold;
        animation: pulse 1s infinite;
        margin: 10px 0;
    }
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.7; }
    }

    /* Metric card styling */
    .metric-card {
        background: #1e1e2e;
        border-radius: 12px;
        padding: 18px;
        text-align: center;
        border: 1px solid #333;
    }
    .metric-value {
        font-size: 2.2em;
        font-weight: bold;
        color: #4fc3f7;
    }
    .metric-label {
        font-size: 0.9em;
        color: #aaa;
        margin-top: 4px;
    }

    /* Pump/Generator badge */
    .badge-on  { background: #00C851; color: white; padding: 4px 14px;
                  border-radius: 20px; font-weight: bold; font-size: 0.95em; }
    .badge-off { background: #555; color: #aaa; padding: 4px 14px;
                  border-radius: 20px; font-weight: bold; font-size: 0.95em; }

    /* Hide default Streamlit footer */
    footer { visibility: hidden; }
    .stDeployButton { display: none; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------
def init_session_state():
    """Initialise all session-state keys on first run."""
    defaults = {
        "tank_config": TankConfig(),
        "tank_model": TankModel(),
        "bridge": DataBridge(),
        "detector": TheftDetector(),
        "sim": TankSimulator(),
        "history_df": pd.DataFrame(columns=[
            "timestamp", "level_pct", "volume_litres", "pump_on",
            "generator_on", "status", "theft_alert", "theft_confidence",
            "hours_remaining", "distance_cm"
        ]),
        "current_state": None,
        "running_scenario": None,
        "scenario_readings": [],
        "scenario_index": 0,
        "theft_events": [],
        "data_source": "simulator",
        "auto_run": False,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

init_session_state()

# Convenience aliases
tank: TankModel = st.session_state.tank_model
detector: TheftDetector = st.session_state.detector
bridge: DataBridge = st.session_state.bridge
sim: TankSimulator = st.session_state.sim

# ---------------------------------------------------------------------------
# Sidebar — Configuration & Data Source
# ---------------------------------------------------------------------------
with st.sidebar:
    st.image("https://img.icons8.com/color/96/gas-station.png", width=64)
    st.title("⛽ Tank Config")

    st.subheader("Tank Dimensions")
    depth = st.number_input("Depth (cm)", 10, 500, 100, key="cfg_depth")
    capacity = st.number_input("Capacity (L)", 10, 10000, 500, key="cfg_cap")
    if depth != tank.config.depth_cm or capacity != tank.config.capacity_litres:
        new_cfg = TankConfig(depth_cm=depth, capacity_litres=capacity)
        st.session_state.tank_config = new_cfg
        st.session_state.tank_model = TankModel(new_cfg)
        tank = st.session_state.tank_model

    st.divider()
    st.subheader("Data Source")
    source = st.radio(
        "Source", ["Simulator", "WebSocket (Wokwi)", "MQTT"],
        index=0, key="src_radio"
    )
    st.session_state.data_source = source.lower().split()[0]

    if "websocket" in source.lower():
        ws_url = st.text_input("WebSocket URL", "ws://localhost:4000")
        if st.button("🔌 Connect WebSocket"):
            bridge.stop()
            bridge._ws_url = ws_url
            bridge.start_websocket()
            st.success("Connecting…")
    elif "mqtt" in source.lower():
        mqtt_host = st.text_input("MQTT Host", "localhost")
        mqtt_topic = st.text_input("MQTT Topic", "diesel/sensor")
        if st.button("🔌 Connect MQTT"):
            bridge.stop()
            bridge._mqtt_host = mqtt_host
            bridge._mqtt_topic = mqtt_topic
            bridge.start_mqtt()
            st.success("Connecting…")

    st.divider()
    st.subheader("ML Model")
    if detector.is_trained:
        st.success("✅ Model loaded")
    else:
        st.warning("⚠️ No trained model")
        st.caption("Run `python train_model.py` to train.")

    st.divider()
    if st.button("🔄 Reset System"):
        tank.reset()
        bridge.clear()
        st.session_state.history_df = pd.DataFrame(columns=st.session_state.history_df.columns)
        st.session_state.theft_events = []
        st.session_state.running_scenario = None
        st.session_state.scenario_readings = []
        st.session_state.scenario_index = 0
        st.session_state.current_state = None
        st.rerun()

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------
def make_gauge(value: float, title: str, max_val: float = 100,
               suffix: str = "%", color_thresholds=None) -> go.Figure:
    """Create a half-circle gauge chart."""
    if color_thresholds is None:
        color_thresholds = {
            "axis": {"range": [0, max_val]},
            "bar": {"color": "#4fc3f7"},
            "steps": [
                {"range": [0, max_val * 0.2], "color": "#ff4444"},
                {"range": [max_val * 0.2, max_val * 0.9], "color": "#ffbb33"},
                {"range": [max_val * 0.9, max_val], "color": "#00C851"},
            ],
            "threshold": {
                "line": {"color": "white", "width": 3},
                "thickness": 0.8,
                "value": value,
            },
        }
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        number={"suffix": suffix, "font": {"size": 36}},
        title={"text": title, "font": {"size": 16}},
        gauge=color_thresholds,
    ))
    fig.update_layout(
        height=220, margin=dict(l=20, r=20, t=40, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        font={"color": "white"},
    )
    return fig


def render_leds(status: str):
    """Render LOW / MEDIUM / FULL LED indicators."""
    low_cls = "led led-red" if status == "LOW" else "led led-off"
    med_cls = "led led-yellow" if status == "MEDIUM" else "led led-off"
    full_cls = "led led-green" if status == "FULL" else "led led-off"
    html = f"""
    <div style="text-align:center; margin:8px 0;">
        <span class="{low_cls}"></span> LOW &nbsp;&nbsp;
        <span class="{med_cls}"></span> MEDIUM &nbsp;&nbsp;
        <span class="{full_cls}"></span> FULL
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_badge(label: str, is_on: bool):
    """Render an ON/OFF badge."""
    cls = "badge-on" if is_on else "badge-off"
    text = "ON" if is_on else "OFF"
    st.markdown(
        f'<span class="{cls}">{label}: {text}</span>',
        unsafe_allow_html=True,
    )


def append_to_history(state: TankState, distance_cm: float):
    """Append a TankState to the session history DataFrame."""
    new_row = pd.DataFrame([{
        "timestamp": state.timestamp,
        "level_pct": state.level_pct,
        "volume_litres": state.volume_litres,
        "pump_on": state.pump_on,
        "generator_on": state.generator_on,
        "status": state.status,
        "theft_alert": state.theft_alert,
        "theft_confidence": state.theft_confidence,
        "hours_remaining": state.hours_remaining,
        "distance_cm": distance_cm,
    }])
    st.session_state.history_df = pd.concat(
        [st.session_state.history_df, new_row], ignore_index=True
    )


def process_reading(distance_cm: float, generator_on: bool,
                    timestamp: datetime = None) -> TankState:
    """Full processing pipeline: tank model + ML detector."""
    ts = timestamp or datetime.now()
    state = tank.process_reading(distance_cm, generator_on, ts)

    # ML theft detection (overrides legacy rule)
    history = tank.get_level_history()
    if len(history) >= 5:
        ml_result = detector.predict(history, generator_on, ts)
        state.theft_alert = ml_result.is_theft
        state.theft_confidence = ml_result.confidence
        if ml_result.is_theft:
            st.session_state.theft_events.append({
                "timestamp": ts,
                "confidence": ml_result.confidence,
                "explanation": ml_result.explanation,
                "level_pct": state.level_pct,
            })

    st.session_state.current_state = state
    append_to_history(state, distance_cm)
    return state

# ---------------------------------------------------------------------------
# Main dashboard header
# ---------------------------------------------------------------------------
st.markdown("# ⛽ Diesel Tank Level & Theft Monitor")
st.caption("Real-time monitoring • ML anomaly detection • Pump hysteresis control")

# ---------------------------------------------------------------------------
# Scenario control panel
# ---------------------------------------------------------------------------
st.markdown("### 🎬 Demo Scenarios")
scenario_cols = st.columns(4)

with scenario_cols[0]:
    if st.button("▶️ 1. Hysteresis Demo", use_container_width=True,
                 help="Full→Empty→Full: pump switches at 20%/90%"):
        tank.reset()
        bridge.clear()
        st.session_state.history_df = pd.DataFrame(
            columns=st.session_state.history_df.columns)
        st.session_state.theft_events = []
        readings = sim.generate_scenario(Scenario.HYSTERESIS, speed_multiplier=2.0)
        st.session_state.scenario_readings = readings
        st.session_state.scenario_index = 0
        st.session_state.running_scenario = "hysteresis"
        st.session_state.auto_run = True
        st.rerun()

with scenario_cols[1]:
    if st.button("▶️ 2. Theft Demo", use_container_width=True,
                 help="Generator OFF, sudden level drop → THEFT alarm"):
        tank.reset()
        bridge.clear()
        st.session_state.history_df = pd.DataFrame(
            columns=st.session_state.history_df.columns)
        st.session_state.theft_events = []
        readings = sim.generate_scenario(Scenario.THEFT, speed_multiplier=2.0)
        st.session_state.scenario_readings = readings
        st.session_state.scenario_index = 0
        st.session_state.running_scenario = "theft"
        st.session_state.auto_run = True
        st.rerun()

with scenario_cols[2]:
    if st.button("▶️ 3. Consumption Demo", use_container_width=True,
                 help="Generator ON, steady drain → hours-left countdown"):
        tank.reset()
        bridge.clear()
        st.session_state.history_df = pd.DataFrame(
            columns=st.session_state.history_df.columns)
        st.session_state.theft_events = []
        readings = sim.generate_scenario(Scenario.CONSUMPTION, speed_multiplier=2.0)
        st.session_state.scenario_readings = readings
        st.session_state.scenario_index = 0
        st.session_state.running_scenario = "consumption"
        st.session_state.auto_run = True
        st.rerun()

with scenario_cols[3]:
    if st.button("⏹️ Stop", use_container_width=True):
        st.session_state.auto_run = False
        st.session_state.running_scenario = None

# ---------------------------------------------------------------------------
# Manual control (when not running a scenario)
# ---------------------------------------------------------------------------
if not st.session_state.auto_run:
    st.markdown("### 🎛️ Manual Control")
    manual_cols = st.columns([3, 1, 1])
    with manual_cols[0]:
        distance = st.slider(
            "Ultrasonic Distance (cm) — 0 = Full, 100 = Empty",
            0.0, float(tank.config.depth_cm), 50.0, 0.5,
            key="manual_dist"
        )
    with manual_cols[1]:
        gen_on = st.toggle("Generator ON", value=False, key="manual_gen")
    with manual_cols[2]:
        if st.button("📡 Send Reading", use_container_width=True):
            process_reading(distance, gen_on)
            st.rerun()

# ---------------------------------------------------------------------------
# Auto-advance scenario simulation
# ---------------------------------------------------------------------------
if st.session_state.auto_run and st.session_state.scenario_readings:
    idx = st.session_state.scenario_index
    readings = st.session_state.scenario_readings

    if idx < len(readings):
        # Process a batch of readings per refresh (for speed)
        batch_size = 3
        end_idx = min(idx + batch_size, len(readings))
        for i in range(idx, end_idx):
            r = readings[i]
            process_reading(r.distance_cm, r.generator_on, r.timestamp)
        st.session_state.scenario_index = end_idx

        progress = end_idx / len(readings)
        st.progress(progress, text=f"Scenario: {st.session_state.running_scenario} "
                                   f"— {end_idx}/{len(readings)} readings")
    else:
        st.session_state.auto_run = False
        st.success("✅ Scenario complete!")

# ---------------------------------------------------------------------------
# Dashboard display (always rendered with latest state)
# ---------------------------------------------------------------------------
state: TankState = st.session_state.current_state

if state is not None:
    # ── Theft alert banner ──────────────────────────────────────────────
    if state.theft_alert:
        st.markdown(
            '<div class="theft-alert">🚨 THEFT DETECTED — '
            f'Confidence: {state.theft_confidence:.0%} — '
            'BUZZER ACTIVE 🔊</div>',
            unsafe_allow_html=True,
        )
        # Show last theft event details
        if st.session_state.theft_events:
            last_event = st.session_state.theft_events[-1]
            st.error(f"🔍 {last_event['explanation']}")

    # ── Gauge row ───────────────────────────────────────────────────────
    g1, g2 = st.columns(2)
    with g1:
        st.plotly_chart(
            make_gauge(state.level_pct, "Tank Level", 100, "%"),
            use_container_width=True, key="gauge_level"
        )
    with g2:
        st.plotly_chart(
            make_gauge(state.volume_litres, "Volume",
                       tank.config.capacity_litres, " L"),
            use_container_width=True, key="gauge_volume"
        )

    # ── LED status + badges ─────────────────────────────────────────────
    led_col, badge_col1, badge_col2, hrs_col = st.columns([2, 1, 1, 1])
    with led_col:
        render_leds(state.status)
    with badge_col1:
        render_badge("🔧 PUMP", state.pump_on)
    with badge_col2:
        render_badge("⚡ GEN", state.generator_on)
    with hrs_col:
        if state.hours_remaining is not None:
            st.markdown(
                f'<div style="text-align:center;font-size:1.3em;">'
                f'⏱️ <b>{state.hours_remaining:.1f} hrs</b> remaining</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div style="text-align:center;color:#888;">⏱️ N/A</div>',
                unsafe_allow_html=True,
            )

    # ── Metrics row ─────────────────────────────────────────────────────
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Level", f"{state.level_pct:.1f} %")
    m2.metric("Volume", f"{state.volume_litres:.1f} L")
    m3.metric("Status", state.status)
    m4.metric("Readings", len(st.session_state.history_df))

    st.divider()

    # ── Real-time level chart ───────────────────────────────────────────
    st.markdown("### 📈 Level Over Time")
    df = st.session_state.history_df
    if len(df) > 1:
        fig = go.Figure()

        # Level line
        fig.add_trace(go.Scatter(
            x=df["timestamp"], y=df["level_pct"],
            mode="lines", name="Level %",
            line=dict(color="#4fc3f7", width=2),
            fill="tozeroy", fillcolor="rgba(79,195,247,0.15)",
        ))

        # Pump ON regions
        pump_on_df = df[df["pump_on"] == True]
        if len(pump_on_df) > 0:
            fig.add_trace(go.Scatter(
                x=pump_on_df["timestamp"], y=pump_on_df["level_pct"],
                mode="markers", name="Pump ON",
                marker=dict(color="#00C851", size=6, symbol="triangle-up"),
            ))

        # Theft events
        theft_df = df[df["theft_alert"] == True]
        if len(theft_df) > 0:
            fig.add_trace(go.Scatter(
                x=theft_df["timestamp"], y=theft_df["level_pct"],
                mode="markers", name="🚨 Theft Alert",
                marker=dict(color="#ff4444", size=12, symbol="x"),
            ))

        # Threshold lines
        fig.add_hline(y=20, line_dash="dash", line_color="#ff4444",
                      annotation_text="20% — Pump ON", annotation_position="top left")
        fig.add_hline(y=90, line_dash="dash", line_color="#00C851",
                      annotation_text="90% — Pump OFF", annotation_position="top left")

        fig.update_layout(
            height=350,
            margin=dict(l=10, r=10, t=10, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.1)"),
            yaxis=dict(range=[0, 105], showgrid=True,
                       gridcolor="rgba(255,255,255,0.1)"),
            legend=dict(orientation="h", y=-0.15),
            font=dict(color="white"),
        )
        st.plotly_chart(fig, use_container_width=True, key="chart_level")

    # ── Pump hysteresis chart ───────────────────────────────────────────
    if len(df) > 1:
        chart_col1, chart_col2 = st.columns(2)

        with chart_col1:
            st.markdown("### 🔧 Pump Hysteresis")
            fig_pump = go.Figure()
            fig_pump.add_trace(go.Scatter(
                x=df["timestamp"], y=df["level_pct"],
                mode="lines", name="Level %",
                line=dict(color="#4fc3f7", width=1.5),
            ))
            # Colour background by pump state
            fig_pump.add_trace(go.Scatter(
                x=df["timestamp"],
                y=df["pump_on"].astype(int) * 100,
                mode="lines", name="Pump ON",
                line=dict(color="#00C851", width=2, dash="dot"),
                yaxis="y2",
            ))
            fig_pump.update_layout(
                height=260,
                margin=dict(l=10, r=40, t=10, b=10),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                yaxis=dict(title="Level %", range=[0, 105],
                           showgrid=True, gridcolor="rgba(255,255,255,0.1)"),
                yaxis2=dict(title="Pump", overlaying="y", side="right",
                            range=[0, 1.2], showgrid=False),
                legend=dict(orientation="h", y=-0.2),
                font=dict(color="white"),
            )
            st.plotly_chart(fig_pump, use_container_width=True, key="chart_pump")

        with chart_col2:
            st.markdown("### 🔍 ML Anomaly Score")
            if "theft_confidence" in df.columns:
                fig_ml = go.Figure()
                fig_ml.add_trace(go.Scatter(
                    x=df["timestamp"], y=df["theft_confidence"],
                    mode="lines+markers", name="Theft Confidence",
                    line=dict(color="#ff4444", width=2),
                    marker=dict(size=3),
                ))
                fig_ml.add_hline(y=0.5, line_dash="dash", line_color="#ffbb33",
                                 annotation_text="Alert Threshold")
                fig_ml.update_layout(
                    height=260,
                    margin=dict(l=10, r=10, t=10, b=10),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    yaxis=dict(range=[0, 1.05], showgrid=True,
                               gridcolor="rgba(255,255,255,0.1)"),
                    legend=dict(orientation="h", y=-0.2),
                    font=dict(color="white"),
                )
                st.plotly_chart(fig_ml, use_container_width=True, key="chart_ml")

    # ── ML Feature Importance ───────────────────────────────────────────
    if detector.is_trained:
        with st.expander("🧠 ML Model — Feature Importance"):
            importance = detector.get_feature_importance()
            if importance:
                imp_df = pd.DataFrame(
                    list(importance.items()),
                    columns=["Feature", "Importance"]
                ).sort_values("Importance", ascending=True)
                fig_imp = px.bar(
                    imp_df, x="Importance", y="Feature",
                    orientation="h", color="Importance",
                    color_continuous_scale="RdYlGn_r",
                )
                fig_imp.update_layout(
                    height=300,
                    margin=dict(l=10, r=10, t=10, b=10),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="white"),
                )
                st.plotly_chart(fig_imp, use_container_width=True, key="chart_imp")

    # ── Theft event log ─────────────────────────────────────────────────
    if st.session_state.theft_events:
        with st.expander(f"🚨 Theft Event Log ({len(st.session_state.theft_events)} events)"):
            for i, evt in enumerate(reversed(st.session_state.theft_events[-20:])):
                st.markdown(
                    f"**#{len(st.session_state.theft_events) - i}** "
                    f"@ {evt['timestamp'].strftime('%H:%M:%S')} — "
                    f"Level: {evt['level_pct']:.1f}% — "
                    f"Confidence: {evt['confidence']:.0%}"
                )
                st.caption(evt["explanation"])

    # ── Raw data table ──────────────────────────────────────────────────
    with st.expander("📋 Raw Data Log"):
        st.dataframe(
            df.tail(50).iloc[::-1],
            use_container_width=True,
            hide_index=True,
        )

else:
    # No data yet
    st.info(
        "👆 Select a **Demo Scenario** above or use **Manual Control** "
        "to start sending sensor readings."
    )
    st.markdown("""
    #### Quick Start
    1. Click **▶️ 1. Hysteresis Demo** to see the pump switch ON at 20% and OFF at 90%
    2. Click **▶️ 2. Theft Demo** to trigger the ML-based theft alarm
    3. Click **▶️ 3. Consumption Demo** to see the hours-remaining countdown

    #### Connecting to Wokwi
    - Set **Data Source** in the sidebar to *WebSocket (Wokwi)*
    - Enter the WebSocket URL from your friend's Wokwi bridge
    - Click **🔌 Connect WebSocket**
    """)

# ---------------------------------------------------------------------------
# Auto-refresh for running scenarios
# ---------------------------------------------------------------------------
if st.session_state.auto_run and st.session_state.scenario_index < len(
        st.session_state.scenario_readings):
    time.sleep(0.1)  # small delay for visual pacing
    st.rerun()
