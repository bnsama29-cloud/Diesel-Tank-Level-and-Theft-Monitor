from datetime import datetime, timezone
from pathlib import Path
import time

import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

from monitor_logic import detect_rapid_drop
from mqtt_telemetry import MQTTTelemetryStore
from tank_view import build_tank_html
from telemetry import display_level, display_litres
from wokwi_embed import build_wokwi_embed_html


FEEDS = {
    "distance": "Distance (cm)",
    "level": "Level (%)",
    "litres": "Fuel (L)",
    "generator": "Generator",
    "pump": "Pump",
    "theft": "Firmware alarm",
    "hours-left": "Hours left",
}
POLL_INTERVAL_SECONDS = 2
THEFT_WINDOW_SECONDS = 60
THEFT_DROP_PERCENT = 5.0
TANK_CAPACITY_LITRES = 500.0
STALE_AFTER_SECONDS = 8


def append_event(message: str) -> None:
    events = st.session_state.get("dashboard_events", [])
    events.append(
        {
            "Time": datetime.now().astimezone().strftime("%H:%M:%S"),
            "Event": message,
        }
    )
    st.session_state.dashboard_events = events[-50:]


def render_tank(level: float, litres: float) -> None:
    dashboard_path = Path(__file__).parent
    template_path = dashboard_path / "assets" / "tank_viewer.html"
    model_path = dashboard_path.parent / "diesel-tank.gltf"
    html = build_tank_html(template_path, level, litres, model_path)
    components.html(html, height=390, scrolling=False)


@st.cache_resource
def connect_mqtt(
    host: str,
    port: int,
    username: str,
    password: str,
    topic: str,
) -> MQTTTelemetryStore:
    store = MQTTTelemetryStore(host, port, username, password, topic)
    store.start()
    return store


@st.fragment(run_every=POLL_INTERVAL_SECONDS)
def render_live_panel(store: MQTTTelemetryStore) -> None:
    latest = store.get_latest()
    level_history = [
        {
            "timestamp": reading["timestamp"],
            "level": reading["level_percent"],
        }
        for reading in store.get_history()
    ]
    if latest is None:
        status_column, records_column = st.columns([0.95, 1.05], gap="medium")
        error_message = store.last_error
        if st.session_state.get("last_telemetry_error") != error_message:
            if error_message:
                append_event(f"MQTT telemetry error: {error_message}")
            st.session_state.last_telemetry_error = error_message
        with status_column:
            st.error(
                "Waiting for MQTT telemetry. Check that Wokwi is running and "
                "that broker settings and topic match."
            )
            st.caption(
                "The dashboard will update as soon as a retained or new message arrives."
            )
        with records_column:
            if error_message:
                st.warning(error_message)
            st.subheader("Recent activity")
            render_event_log()
        return

    if st.session_state.pop("last_telemetry_error", None):
        append_event("MQTT telemetry connection restored.")

    source_timestamp = latest["timestamp"]
    readings = {
        "distance": (latest["distance_cm"], source_timestamp),
        "level": (latest["level_percent"], source_timestamp),
        "litres": (latest["litres"], source_timestamp),
        "generator": (float(latest["generator_on"]), source_timestamp),
        "pump": (float(latest["pump_on"]), source_timestamp),
        "theft": (float(latest["theft_alarm"]), source_timestamp),
        "hours-left": (
            -1.0 if latest["hours_left"] is None else latest["hours_left"],
            source_timestamp,
        ),
    }
    values = {feed: data[0] for feed, data in readings.items()}
    age_seconds = max(
        0, int((datetime.now(timezone.utc) - source_timestamp).total_seconds())
    )
    connected = store.is_connected and age_seconds < STALE_AFTER_SECONDS

    distance = values["distance"]
    raw_level = values["level"]
    level, invalid_level = display_level(raw_level, distance)
    raw_litres = values["litres"]
    litres, invalid_litres = display_litres(raw_litres, level)
    safe_level = 0.0 if level is None else level
    safe_litres = 0.0 if litres is None else litres

    generator_on = latest["generator_on"]
    pump_on = latest["pump_on"]
    firmware_alarm = latest["theft_alarm"]
    level_status = (
        "INVALID"
        if level is None
        else "LOW"
        if level < 20
        else "FULL"
        if level > 90
        else "MEDIUM"
    )

    sample_time = source_timestamp.timestamp()
    previous_sample_time = st.session_state.get("last_logged_sample_time")
    if previous_sample_time != sample_time:
        if previous_sample_time is None:
            append_event("Connected to telemetry feed.")
        else:
            append_event(
                f"Telemetry: {safe_level:.1f}% · {safe_litres:.1f} L · "
                f"Generator {'ON' if generator_on else 'OFF'} · "
                f"Pump {'ON' if pump_on else 'OFF'}"
            )
        if invalid_level:
            append_event(
                f"Invalid level feed value {raw_level:g}; "
                + (
                    f"using distance-derived {safe_level:.1f}%."
                    if level is not None
                    else "sensor distance is invalid too."
                )
            )
        if invalid_litres:
            append_event(
                f"Invalid litres feed value {raw_litres:g}; using "
                + (
                    f"{safe_litres:.1f} L derived from level."
                    if litres is not None
                    else "no valid level is available."
                )
            )
        st.session_state.last_logged_sample_time = sample_time

    previous_stale = st.session_state.get("telemetry_was_stale")
    if previous_stale is None or previous_stale != (not connected):
        append_event(
            "Telemetry connection is stale."
            if not connected
            else "Telemetry connection is live."
        )
        st.session_state.telemetry_was_stale = not connected

    if firmware_alarm and not st.session_state.get("previous_firmware_alarm", False):
        append_event("THEFT alarm reported by firmware.")
    st.session_state.previous_firmware_alarm = firmware_alarm

    if not invalid_level and level is not None:
        sample_history = st.session_state.get("recent_level_samples", [])
        if not sample_history or sample_history[-1][0] != sample_time:
            sample_history.append((sample_time, level))
        sample_history = [
            sample
            for sample in sample_history
            if 0 <= time.time() - sample[0] <= THEFT_WINDOW_SECONDS
        ]
        st.session_state.recent_level_samples = sample_history
    else:
        sample_history = st.session_state.get("recent_level_samples", [])

    dashboard_alarm = (
        not generator_on
        and detect_rapid_drop(
            sample_history,
            time.time(),
            window_seconds=THEFT_WINDOW_SECONDS,
            drop_threshold_percent=THEFT_DROP_PERCENT,
        )
    )
    alarm = firmware_alarm or dashboard_alarm
    previous_alarm = st.session_state.get("previous_combined_alarm", False)
    if alarm and not previous_alarm:
        append_event("THEFT alert: rapid unexplained level drop detected.")
    st.session_state.previous_combined_alarm = alarm

    status_column, records_column = st.columns([0.95, 1.05], gap="medium")
    with status_column:
        st.subheader("Live status")
        st.caption(
            f"{'🟢 LIVE' if connected else '⚪ STALE'} · "
            f"Updated {age_seconds}s ago · dashboard refreshes every 2s"
        )
        level_label = f"{level:.1f}%" if level is not None else "INVALID"
        litres_label = f"{litres:.1f} L" if litres is not None else "INVALID"
        top_metrics = st.columns(2, gap="small")
        bottom_metrics = st.columns(2, gap="small")
        top_metrics[0].metric("Tank level", level_label, level_status)
        top_metrics[1].metric(
            "Fuel volume", litres_label, f"of {TANK_CAPACITY_LITRES:.0f} L"
        )
        bottom_metrics[0].metric(
            "Generator", "RUNNING" if generator_on else "STOPPED"
        )
        bottom_metrics[1].metric("Refill pump", "ON" if pump_on else "OFF")

        if invalid_level:
            st.warning(
                f"MQTT level={raw_level:g} is outside the valid 0–100% range. "
                + (
                    f"Showing {safe_level:.1f}% calculated from sensor distance."
                    if level is not None
                    else "Distance is invalid, so the level is not displayed."
                )
            )
        if invalid_litres:
            st.warning(
                f"MQTT litres={raw_litres:g} is outside the valid 0–500 L range. "
                + (
                    f"Showing {safe_litres:.1f} L calculated from level."
                    if litres is not None
                    else "Fuel volume is not displayed."
                )
            )
        if alarm:
            st.error("🚨 THEFT ALERT · Rapid unexplained tank-level drop detected.")
        else:
            st.success("✅ No theft alarm reported.")

        st.subheader("3D diesel chamber")
        if level is None:
            st.info("3D fuel level is unavailable until a valid sensor reading arrives.")
        else:
            render_tank(safe_level, safe_litres)

        st.subheader("Operating state")
        st.write(f"**Sensor distance:** {distance:.1f} cm")
        st.write(f"**Generator:** {'🟢 ON' if generator_on else '⚪ OFF'}")
        st.write(f"**Pump relay:** {'🟢 ON' if pump_on else '⚪ OFF'}")
        st.write(f"**Alarm:** {'🔴 THEFT?' if alarm else '🟢 Clear'}")

        hours_left = latest["hours_left"]
        st.subheader("Consumption estimate")
        st.write(
            "**Estimated hours left:** "
            + (
                f"{hours_left:.1f} h"
                if hours_left is not None and hours_left >= 0
                else "Not available yet"
            )
        )
        st.caption(
            "The firmware estimates consumption only after it has a usable trend."
        )

    with records_column:
        st.subheader("Latest MQTT telemetry")
        st.dataframe(
            [
                {
                    "Feed": FEEDS[feed],
                    "Value": (
                        "Not available"
                        if feed == "hours-left" and hours_left is None
                        else f"{readings[feed][0]:.2f}"
                    ),
                    "Updated": readings[feed][1]
                    .astimezone()
                    .strftime("%H:%M:%S"),
                }
                for feed in FEEDS
            ],
            hide_index=True,
            use_container_width=True,
            height=270,
        )

        st.subheader("Recent activity")
        render_event_log()

        st.subheader("Fuel level history")
        valid_history = [
            reading
            for reading in level_history
            if 0.0 <= reading["level"] <= 100.0
        ]
        if len(valid_history) > 1:
            chart_range = st.selectbox(
                "Time range",
                ["Last 30 minutes", "Last 2 hours", "All loaded readings"],
                index=0,
                key="history-range",
            )
            range_seconds = {
                "Last 30 minutes": 30 * 60,
                "Last 2 hours": 2 * 60 * 60,
            }.get(chart_range)
            if range_seconds is None:
                visible_history = valid_history
            else:
                cutoff = datetime.now(timezone.utc).timestamp() - range_seconds
                visible_history = [
                    reading
                    for reading in valid_history
                    if reading["timestamp"].timestamp() >= cutoff
                ]
            if len(visible_history) > 1:
                fig = build_level_chart(visible_history)
                st.plotly_chart(
                    fig, use_container_width=True, config={"displayModeBar": False}
                )
                st.caption(
                    f"Showing {len(visible_history)} valid readings held in memory."
                )
            else:
                st.info("Not enough readings in this time range to draw the graph.")
        else:
            st.info("The graph appears after two valid level readings.")

def render_event_log() -> None:
    events = st.session_state.get("dashboard_events", [])
    if not events:
        st.info("No events logged yet; new telemetry and state changes will appear here.")
        return
    st.dataframe(
        list(reversed(events[-8:])),
        hide_index=True,
        use_container_width=True,
        height=220,
    )


def build_level_chart(visible_history: list[dict]) -> go.Figure:
    history_times = [reading["timestamp"] for reading in visible_history]
    history_levels = [reading["level"] for reading in visible_history]
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=history_times,
            y=history_levels,
            name="Level",
            mode="lines",
            line={"color": "#42d3c8", "width": 3, "shape": "spline"},
            fill="tozeroy",
            fillcolor="rgba(66,211,200,.12)",
            hovertemplate="%{x|%b %d, %H:%M:%S}<br>%{y:.1f}%<extra>Tank level</extra>",
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
        annotation_text="Pump OFF · 90%",
        annotation_position="top right",
    )
    fig.update_layout(
        height=350,
        margin={"l": 10, "r": 15, "t": 20, "b": 10},
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
        showlegend=False,
    )
    return fig


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
      .block-container { max-width: 1880px; padding-top: 1.4rem; }
      h1, h2, h3 { letter-spacing: -0.025em; }
      div[data-testid="stMetric"] {
        background: linear-gradient(145deg, rgba(25,46,67,.96), rgba(15,27,42,.96));
        border: 1px solid rgba(125,175,210,.18);
        border-radius: 14px;
        padding: 9px 10px;
        box-shadow: 0 12px 30px rgba(0,0,0,.16);
      }
      div[data-testid="stMetricLabel"] { color: #9eb5c9; font-size: .78rem; }
      div[data-testid="stMetricValue"] { color: #f2f8fc; font-size: 1.35rem; }
      div[data-testid="stMetricDelta"] { font-size: .72rem !important; line-height: 1rem; }
      div[data-testid="stMetricDelta"] svg { width: .72rem; height: .72rem; }
      .hero-note { color: #91a8bc; margin-top: -.5rem; }
      [data-testid="stAlert"] { border-radius: 14px; }
      @media (max-width: 700px) {
        .block-container { padding: 1rem .8rem 2rem; }
        h1 { font-size: 1.65rem !important; }
        h2 { font-size: 1.25rem !important; }
        div[data-testid="stMetric"] { padding: 8px; }
        div[data-testid="stMetricLabel"] { font-size: .7rem; }
        div[data-testid="stMetricValue"] { font-size: 1.1rem; }
        div[data-testid="stMetricDelta"] { font-size: .65rem !important; }
        div[data-testid="stMetricDelta"] svg { width: .65rem; height: .65rem; }
      }
    </style>
    """,
    unsafe_allow_html=True,
)
st.title("⛽ Diesel Tank Monitor")
mobile_view = st.query_params.get("view", "desktop") == "mobile"
st.markdown(
    '<div class="hero-note">'
    + ("Read-only live monitor" if mobile_view else "Wokwi simulation · Live monitor")
    + " · 500 L diesel chamber</div>",
    unsafe_allow_html=True,
)

try:
    mqtt_host = st.secrets["MQTT_HOST"]
    mqtt_port = int(st.secrets.get("MQTT_PORT", 8883))
    mqtt_username = st.secrets["MQTT_USERNAME"]
    mqtt_password = st.secrets["MQTT_PASSWORD"]
    mqtt_topic = st.secrets.get("MQTT_TOPIC", "diesel-tank/telemetry")
except (KeyError, FileNotFoundError, ValueError):
    st.error(
        "MQTT broker settings are not configured. Add MQTT_HOST, MQTT_USERNAME, "
        "and MQTT_PASSWORD in Streamlit Community Cloud → App settings → Secrets."
    )
    st.stop()

try:
    telemetry_store = connect_mqtt(
        mqtt_host,
        mqtt_port,
        mqtt_username,
        mqtt_password,
        mqtt_topic,
    )
except (OSError, ValueError) as exc:
    st.error(f"Could not initialize the MQTT telemetry client: {exc}")
    st.stop()

if mobile_view:
    render_live_panel(telemetry_store)
else:
    dashboard_column, simulation_column = st.columns([2.0, 1.0], gap="large")
    with dashboard_column:
        render_live_panel(telemetry_store)
    with simulation_column:
        st.subheader("Wokwi simulation")
        st.caption(
            "Operate the sensor slider and generator switch in Wokwi. "
            "Drag the lower-right corner to resize or use Enlarge for fullscreen."
        )
        render_wokwi()
