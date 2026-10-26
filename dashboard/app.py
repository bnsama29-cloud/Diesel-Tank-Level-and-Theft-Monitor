from datetime import datetime, timedelta, timezone
from typing import Any

import plotly.graph_objects as go
import requests
import streamlit as st
import streamlit.components.v1 as components

from adafruit_client import fetch_telemetry_history
from monitor_logic import detect_rapid_drop
from wokwi_embed import build_wokwi_embed_html


POLL_INTERVAL_SECONDS = 3
THEFT_WINDOW_SECONDS = 60
THEFT_DROP_PERCENT = 5.0
STALE_AFTER_SECONDS = 10
HISTORY_LIMIT = 120


def derive_theft_alarm(history: list[dict[str, Any]]) -> bool:
    latest = history[-1]
    cutoff = latest["timestamp"].timestamp() - THEFT_WINDOW_SECONDS
    recent_samples = [
        (reading["timestamp"].timestamp(), reading["level_percent"])
        for reading in history
        if reading["timestamp"].timestamp() >= cutoff and not reading["generator_on"]
    ]
    return (
        not latest["generator_on"]
        and detect_rapid_drop(
            recent_samples,
            latest["timestamp"].timestamp(),
            window_seconds=THEFT_WINDOW_SECONDS,
            drop_threshold_percent=THEFT_DROP_PERCENT,
        )
    )


def theft_marker_readings(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    markers = []
    previous_dashboard_alarm = False
    for index, reading in enumerate(history):
        previous_firmware_alarm = index > 0 and history[index - 1]["theft_alarm"]
        dashboard_alarm = False
        if not reading["generator_on"]:
            current_time = reading["timestamp"].timestamp()
            window = [
                earlier
                for earlier in history[:index]
                if current_time - earlier["timestamp"].timestamp()
                <= THEFT_WINDOW_SECONDS
                and not earlier["generator_on"]
            ]
            dashboard_alarm = bool(
                window
                and window[0]["level_percent"] - reading["level_percent"]
                > THEFT_DROP_PERCENT
            )
        firmware_alarm_edge = (
            reading["theft_alarm"] and not previous_firmware_alarm
        )
        if firmware_alarm_edge or (
            dashboard_alarm and not previous_dashboard_alarm
        ):
            markers.append(reading)
        previous_dashboard_alarm = dashboard_alarm
    return markers


def interpretation(
    latest: dict[str, Any],
    history: list[dict[str, Any]],
    alarm: bool,
) -> tuple[str, str]:
    if alarm or latest["theft_alarm"]:
        return (
            "Suspected theft",
            "The generator is OFF and the fuel level dropped by more than 5 percentage "
            "points within 60 seconds. Check the tank and sensor.",
        )
    if latest["level_percent"] <= 20:
        pump_message = (
            "The refill pump is ON."
            if latest["pump_on"]
            else "Check the pump relay."
        )
        label = (
            "Low fuel — refill active"
            if latest["pump_on"]
            else "Low fuel — check pump"
        )
        return label, f"Fuel is at or below 20%. {pump_message}"
    if latest["generator_on"]:
        if (
            len(history) > 1
            and history[-1]["level_percent"] < history[0]["level_percent"]
        ):
            return (
                "Generator running — fuel decreasing",
                "Fuel is trending down while the generator is ON. The runtime estimate "
                "uses the observed level trend; it appears after enough history is collected.",
            )
        return (
            "Generator running",
            "No rapid unexplained loss is detected. The dashboard is collecting "
            "consumption history for a runtime estimate.",
        )
    return (
        "Normal",
        "No rapid unexplained fuel drop is detected. Pump control follows the 20% ON "
        "and above-90% OFF hysteresis thresholds.",
    )


def build_level_chart(history: list[dict[str, Any]]) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=[reading["timestamp"] for reading in history],
            y=[reading["level_percent"] for reading in history],
            name="Fuel level",
            mode="lines",
            line={"color": "#42d3c8", "width": 3},
            fill="tozeroy",
            fillcolor="rgba(66,211,200,.12)",
            hovertemplate="%{x|%H:%M:%S}<br>%{y:.1f}%<extra>Fuel level</extra>",
        )
    )

    pump_events = []
    theft_events = theft_marker_readings(history)
    for index, reading in enumerate(history):
        previous = history[index - 1] if index else None
        if reading["pump_on"] and (previous is None or not previous["pump_on"]):
            pump_events.append(reading)

    for events, label, color, symbol in (
        (pump_events, "Refill pump ON", "#ffd166", "triangle-up"),
        (theft_events, "Theft alert", "#ff7777", "x"),
    ):
        if events:
            fig.add_trace(
                go.Scatter(
                    x=[event["timestamp"] for event in events],
                    y=[event["level_percent"] for event in events],
                    name=label,
                    mode="markers",
                    marker={"color": color, "size": 11, "symbol": symbol},
                    hovertemplate="%{x|%H:%M:%S}<br>%{y:.1f}%<extra>"
                    + label
                    + "</extra>",
                )
            )

    fig.add_hline(
        y=20,
        line_dash="dash",
        line_color="#ff7777",
        annotation_text="Pump ON · 20%",
        annotation_position="bottom right",
    )
    fig.add_hline(
        y=90,
        line_dash="dash",
        line_color="#68d391",
        annotation_text="Pump OFF · >90%",
        annotation_position="top right",
    )
    fig.update_layout(
        height=360,
        margin={"l": 10, "r": 15, "t": 24, "b": 10},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#d9e6f2"},
        hovermode="x unified",
        xaxis={"showgrid": False, "title": None},
        yaxis={
            "range": [0, 100],
            "ticksuffix": "%",
            "gridcolor": "rgba(180,205,225,.12)",
            "title": None,
        },
        legend={"orientation": "h", "y": 1.12, "x": 0},
    )
    return fig


@st.fragment(run_every=POLL_INTERVAL_SECONDS)
def render_live_dashboard(username: str, key: str, feed: str) -> None:
    try:
        history = fetch_telemetry_history(username, key, feed, HISTORY_LIMIT)
        st.session_state.telemetry_history = history
        st.session_state.telemetry_fetch_error = None
    except (requests.RequestException, ValueError) as exc:
        st.session_state.telemetry_fetch_error = str(exc)
        history = st.session_state.get("telemetry_history", [])

    fetch_error = st.session_state.get("telemetry_fetch_error")
    if not history:
        st.error(
            "Waiting for telemetry from Adafruit IO. Start Wokwi and confirm the "
            "feed key and Adafruit credentials."
        )
        if fetch_error:
            st.warning(f"Could not read the telemetry feed: {fetch_error}")
        return

    latest = history[-1]
    now = datetime.now(timezone.utc)
    age_seconds = max(0, int((now - latest["received_at"]).total_seconds()))
    connected = not fetch_error and age_seconds < STALE_AFTER_SECONDS
    if fetch_error:
        st.warning(
            f"Feed request failed; showing the last received reading. {fetch_error}"
        )

    alarm = derive_theft_alarm(history)
    status, explanation = interpretation(latest, history, alarm)
    st.subheader("System interpretation")
    if not connected:
        st.warning(
            f"⚪ DATA STALE · Last known state: {status}. {explanation} "
            "Displayed readings are not current."
        )
    elif alarm or latest["theft_alarm"]:
        st.error(f"🚨 {status} · {explanation}")
    elif latest["level_percent"] <= 20:
        st.warning(f"🟡 {status} · {explanation}")
    else:
        st.success(f"🟢 {status} · {explanation}")

    freshness = "LIVE" if connected else "STALE"
    st.caption(
        f"{freshness} · Last received {age_seconds}s ago · "
        f"refreshes every {POLL_INTERVAL_SECONDS}s · "
        f"{latest['received_at'].astimezone().strftime('%H:%M:%S')}"
    )
    fuel_metrics = st.columns(2, gap="small")
    state_metrics = st.columns(2, gap="small")
    fuel_metrics[0].metric("Fuel remaining", f"{latest['litres']:.1f} L")
    fuel_metrics[1].metric("Tank level", f"{latest['level_percent']:.1f}%")
    state_metrics[0].metric("Generator", "ON" if latest["generator_on"] else "OFF")
    state_metrics[1].metric("Refill pump", "ON" if latest["pump_on"] else "OFF")

    runtime = (
        f"{latest['hours_left']:.1f} h"
        if latest["hours_left"] is not None
        else "—"
    )
    runtime_note = (
        "Calculated from the observed generator-on consumption trend."
        if latest["hours_left"] is not None
        else "Awaiting enough generator-on consumption history."
    )
    runtime_column, details_column = st.columns([1, 2], gap="small")
    with runtime_column:
        st.metric("Estimated runtime", runtime)
    with details_column:
        st.caption(
            f"Sensor distance: {latest['distance_cm']:.1f} cm · {runtime_note}"
        )

    st.subheader("Fuel level history")
    chart_range = st.selectbox(
        "Chart window",
        ["Last 5 minutes", "Last 10 minutes", "All loaded readings"],
        index=0,
        key="history-range",
    )
    seconds = {"Last 5 minutes": 300, "Last 10 minutes": 600}.get(chart_range)
    cutoff = now - timedelta(seconds=seconds) if seconds is not None else None
    visible_history = [
        reading
        for reading in history
        if cutoff is None or reading["timestamp"] >= cutoff
    ]
    if len(visible_history) > 1:
        st.plotly_chart(
            build_level_chart(visible_history),
            use_container_width=True,
            config={"displayModeBar": False},
        )
    else:
        st.info(
            "The graph appears after at least two readings in the selected time window."
        )
    st.caption(
        "Markers show firmware-reported theft alerts and refill pump starts. "
        "A suspected-theft interpretation also uses the dashboard's 5%-within-60-seconds rule."
    )


def render_wokwi() -> None:
    components.html(
        build_wokwi_embed_html(),
        height=650,
        scrolling=False,
    )


st.set_page_config(
    page_title="Diesel Tank Monitor",
    page_icon="⛽",
    layout="wide",
    initial_sidebar_state="collapsed",
)
st.markdown(
    """
    <style>
      .stApp { background: radial-gradient(ellipse at 15% 0%, #17324a 0, #0b1220 42%); }
      .block-container { max-width: 1600px; padding-top: 1.4rem; }
      h1, h2, h3 { letter-spacing: -0.025em; }
      div[data-testid="stMetric"] {
        background: linear-gradient(145deg, rgba(25,46,67,.96), rgba(15,27,42,.96));
        border: 1px solid rgba(125,175,210,.18);
        border-radius: 14px;
        padding: 10px 12px;
        box-shadow: 0 12px 30px rgba(0,0,0,.16);
      }
      div[data-testid="stMetricLabel"] { color: #9eb5c9; font-size: .8rem; }
      div[data-testid="stMetricValue"] { color: #f2f8fc; font-size: 1.4rem; }
      [data-testid="stAlert"] { border-radius: 14px; }
      @media (max-width: 700px) {
        .block-container { padding: 1rem .8rem 2rem; }
        h1 { font-size: 1.65rem !important; }
        div[data-testid="stMetric"] { padding: 8px; }
        div[data-testid="stMetricValue"] { font-size: 1.1rem; }
      }
    </style>
    """,
    unsafe_allow_html=True,
)
st.title("⛽ Diesel Tank Monitor")
mobile_view = st.query_params.get("view", "desktop") == "mobile"
st.caption(
    f"{'Read-only live monitor' if mobile_view else 'Wokwi simulation · Live monitor'}"
    " · 500 L tank · Theft rule: >5 percentage points in 60 seconds while generator OFF"
)

try:
    aio_username = st.secrets["AIO_USERNAME"]
    aio_key = st.secrets["AIO_KEY"]
    aio_feed = st.secrets.get("AIO_FEED_KEY", "tank-telemetry")
except (KeyError, FileNotFoundError):
    st.error(
        "Adafruit IO is not configured. Add AIO_USERNAME, AIO_KEY, and "
        "AIO_FEED_KEY in Streamlit Community Cloud → App settings → Secrets."
    )
    st.stop()

if mobile_view:
    st.link_button(
        "Open Wokwi simulation", "https://wokwi.com/projects/478875514435866625"
    )
    render_live_dashboard(aio_username, aio_key, aio_feed)
else:
    dashboard_column, simulation_column = st.columns([2.0, 1.0], gap="large")
    with dashboard_column:
        render_live_dashboard(aio_username, aio_key, aio_feed)
    with simulation_column:
        st.subheader("Wokwi simulation")
        st.caption(
            "Change the distance slider and generator switch. "
            "On phones, use the read-only dashboard and open Wokwi separately."
        )
        render_wokwi()
