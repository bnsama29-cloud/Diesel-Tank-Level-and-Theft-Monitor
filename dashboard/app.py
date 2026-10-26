from datetime import datetime, timezone
import hmac
from pathlib import Path
import time

import plotly.graph_objects as go
import requests
import streamlit as st
import streamlit.components.v1 as components

from adafruit_client import (
    decode_remote_command,
    encode_remote_command,
    fetch_latest_command,
    fetch_latest_feed,
    fetch_level_history,
    publish_command,
)
from monitor_logic import detect_rapid_drop
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
POLL_INTERVAL_SECONDS = 20
THEFT_WINDOW_SECONDS = 60
THEFT_DROP_PERCENT = 5.0
TANK_CAPACITY_LITRES = 500.0
HISTORY_LIMIT = 500


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


def unlock_control_session() -> None:
    supplied = st.session_state.get("control-password", "")
    expected = st.secrets.get("CONTROL_PASSWORD", "")
    st.session_state.controls_unlocked = bool(
        expected and hmac.compare_digest(supplied, expected)
    )
    st.session_state.control_password_invalid = not st.session_state.controls_unlocked
    st.session_state["control-password"] = ""


def load_telemetry(username: str, aio_key: str):
    readings = {
        feed: fetch_latest_feed(username, aio_key, feed)
        for feed in FEEDS
    }
    history = fetch_level_history(username, aio_key, limit=HISTORY_LIMIT)
    return readings, history


@st.fragment(run_every=POLL_INTERVAL_SECONDS)
def render_live_panel(username: str, aio_key: str) -> None:
    try:
        readings, level_history = load_telemetry(username, aio_key)
    except (requests.RequestException, ValueError) as exc:
        error_message = str(exc)
        if st.session_state.get("last_telemetry_error") != error_message:
            append_event(f"Telemetry read failed: {error_message}")
            st.session_state.last_telemetry_error = error_message
        st.error(f"Could not load live telemetry. Check the Wokwi connection and feeds. Details: {exc}")
        st.caption("The Wokwi simulation remains running; this live panel will retry automatically.")
        render_event_log()
        return

    if st.session_state.pop("last_telemetry_error", None):
        append_event("Telemetry connection restored.")

    values = {feed: data[0] for feed, data in readings.items()}
    latest_timestamp = max(data[1] for data in readings.values())
    age_seconds = max(
        0, int((datetime.now(timezone.utc) - latest_timestamp).total_seconds())
    )
    connected = age_seconds < 90
    st.caption(
        f"{'🟢 LIVE' if connected else '⚪ STALE'} · "
        f"Latest telemetry {age_seconds} seconds ago · Auto-refreshes every 20 seconds"
    )

    distance = values["distance"]
    raw_level = values["level"]
    level, invalid_level = display_level(raw_level, distance)
    raw_litres = values["litres"]
    litres, invalid_litres = display_litres(raw_litres, level)
    safe_level = 0.0 if level is None else level
    safe_litres = 0.0 if litres is None else litres

    generator_on = values["generator"] >= 0.5
    pump_on = values["pump"] >= 0.5
    firmware_alarm = values["theft"] >= 0.5
    level_status = (
        "INVALID"
        if level is None
        else "LOW"
        if level < 20
        else "FULL"
        if level > 90
        else "MEDIUM"
    )

    sample_time = readings["level"][1].timestamp()
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

    st.subheader("Live status")
    level_label = f"{level:.1f}%" if level is not None else "INVALID"
    litres_label = f"{litres:.1f} L" if litres is not None else "INVALID"
    first, second, third, fourth = st.columns(4)
    first.metric("Tank level", level_label, level_status)
    second.metric("Fuel volume", litres_label, f"of {TANK_CAPACITY_LITRES:.0f} L")
    third.metric("Generator", "RUNNING" if generator_on else "STOPPED")
    fourth.metric("Refill pump", "ON" if pump_on else "OFF")

    if invalid_level:
        st.warning(
            f"Adafruit returned level={raw_level:g}, outside the valid 0–100% range. "
            + (
                f"Showing {safe_level:.1f}% calculated from sensor distance."
                if level is not None
                else "Distance is invalid, so the level is not displayed."
            )
        )
    if invalid_litres:
        st.warning(
            f"Adafruit returned litres={raw_litres:g}, outside the valid 0–500 L range. "
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

    st.subheader("Recent activity log")
    render_event_log()

    left, right = st.columns([1, 1.2], gap="large")
    with left:
        st.subheader("3D diesel chamber")
        if level is None:
            st.info("3D fuel level is unavailable until a valid sensor reading arrives.")
        else:
            render_tank(safe_level, safe_litres)
    with right:
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
                    f"Showing {len(visible_history)} valid readings; "
                    f"{len(level_history) - len(valid_history)} invalid readings excluded."
                )
            else:
                st.info("Not enough readings in this time range to draw the graph.")
        else:
            st.info("The graph appears after two valid level readings.")

    left, right = st.columns(2)
    with left:
        st.subheader("Operating state")
        st.write(f"**Sensor distance:** {distance:.1f} cm")
        st.write(f"**Generator:** {'🟢 ON' if generator_on else '⚪ OFF'}")
        st.write(f"**Pump relay:** {'🟢 ON' if pump_on else '⚪ OFF'}")
        st.write(f"**Alarm:** {'🔴 THEFT?' if alarm else '🟢 Clear'}")
    with right:
        hours_left = values["hours-left"]
        st.subheader("Consumption estimate")
        st.write(
            "**Estimated hours left:** "
            + (f"{hours_left:.1f} h" if hours_left >= 0 else "Not available yet")
        )
        st.caption(
            "The firmware estimates consumption only after it has a usable trend."
        )

    with st.expander("Latest telemetry feed records"):
        st.dataframe(
            [
                {
                    "Feed": FEEDS[feed],
                    "Value": f"{readings[feed][0]:.2f}",
                    "Updated": readings[feed][1]
                    .astimezone()
                    .strftime("%Y-%m-%d %H:%M:%S %Z"),
                }
                for feed in FEEDS
            ],
            hide_index=True,
            use_container_width=True,
        )


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


@st.fragment
def render_controls(username: str, aio_key: str) -> None:
    st.subheader("Simulation controls")
    st.caption(
        "Dashboard inputs control ESP32 logic. The Wokwi graphics do not move remotely."
    )
    control_password = st.secrets.get("CONTROL_PASSWORD", "")
    if not control_password:
        st.error("Set the private CONTROL_PASSWORD app secret to unlock controls.")
        return
    if not st.session_state.get("controls_unlocked", False):
        st.text_input("Control password", type="password", key="control-password")
        st.button("Unlock controls", on_click=unlock_control_session)
        if st.session_state.get("control_password_invalid", False):
            st.error("Incorrect control password.")
        return

    try:
        command_reading = fetch_latest_command(username, aio_key)
    except (requests.RequestException, ValueError) as exc:
        st.error(f"Could not read command feed: {exc}")
        return

    remote_command = (
        decode_remote_command(command_reading[0])
        if command_reading is not None
        else None
    )
    st.info(
        "Input source: "
        + ("Dashboard virtual inputs" if remote_command else "Wokwi controls")
    )
    if "control_distance" not in st.session_state:
        st.session_state.control_distance = (
            remote_command[0] if remote_command else 55.0
        )
    if "control_generator" not in st.session_state:
        st.session_state.control_generator = (
            remote_command[1] if remote_command else False
        )
    with st.form("simulation-controls"):
        st.slider(
            "Virtual sensor distance",
            min_value=5.0,
            max_value=105.0,
            step=0.5,
            key="control_distance",
            help="5 cm is full; 105 cm is empty.",
        )
        st.toggle("Generator running", key="control_generator")
        apply_inputs = st.form_submit_button("Apply dashboard inputs")
    release_inputs = st.button("Return control to Wokwi")
    if apply_inputs:
        try:
            code = encode_remote_command(
                st.session_state.control_distance,
                st.session_state.control_generator,
            )
            publish_command(username, aio_key, code)
            append_event(
                f"Dashboard command sent: {st.session_state.control_distance:.1f} cm, "
                f"generator {'ON' if st.session_state.control_generator else 'OFF'}."
            )
            st.success("Command sent; Wokwi checks for it within 10 seconds.")
        except (requests.RequestException, ValueError) as exc:
            append_event(f"Dashboard command failed: {exc}")
            st.error(f"Could not send simulation controls: {exc}")
    if release_inputs:
        try:
            publish_command(username, aio_key, 0)
            append_event("Dashboard released virtual inputs to Wokwi.")
            st.success("Control released. Wokwi inputs are active again.")
        except requests.RequestException as exc:
            append_event(f"Control release failed: {exc}")
            st.error(f"Could not release dashboard controls: {exc}")


def render_wokwi() -> None:
    components.html(
        build_wokwi_embed_html(),
        height=580,
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
      .block-container { max-width: 1680px; padding-top: 1.4rem; }
      h1, h2, h3 { letter-spacing: -0.025em; }
      div[data-testid="stMetric"] {
        background: linear-gradient(145deg, rgba(25,46,67,.96), rgba(15,27,42,.96));
        border: 1px solid rgba(125,175,210,.18);
        border-radius: 16px;
        padding: 14px 16px;
        box-shadow: 0 12px 30px rgba(0,0,0,.16);
      }
      div[data-testid="stMetricLabel"] { color: #9eb5c9; }
      div[data-testid="stMetricValue"] { color: #f2f8fc; }
      .hero-note { color: #91a8bc; margin-top: -.5rem; }
      [data-testid="stAlert"] { border-radius: 14px; }
      @media (max-width: 700px) {
        .block-container { padding: 1rem .8rem 2rem; }
        h1 { font-size: 1.65rem !important; }
        h2 { font-size: 1.25rem !important; }
        div[data-testid="stMetric"] { padding: 12px; }
        div[data-testid="stMetricValue"] { font-size: 1.2rem; }
      }
    </style>
    """,
    unsafe_allow_html=True,
)
st.title("⛽ Diesel Tank Monitor")
mobile_view = st.query_params.get("view", "desktop") == "mobile"
st.markdown(
    '<div class="hero-note">'
    + ("Read-only live monitor" if mobile_view else "Live control room")
    + " · 500 L diesel chamber</div>",
    unsafe_allow_html=True,
)

try:
    username = st.secrets["AIO_USERNAME"]
    aio_key = st.secrets["AIO_KEY"]
except (KeyError, FileNotFoundError):
    st.error(
        "Adafruit IO credentials are not configured. Add AIO_USERNAME and AIO_KEY "
        "in Streamlit Community Cloud → App settings → Secrets."
    )
    st.stop()

if mobile_view:
    render_live_panel(username, aio_key)
else:
    st.caption("Desktop controls, activity log, live 3D chamber, and Wokwi simulation.")
    live_column, simulation_column = st.columns([1.2, 0.8], gap="large")
    with live_column:
        render_live_panel(username, aio_key)
    with simulation_column:
        render_controls(username, aio_key)
        st.subheader("Wokwi simulation")
        st.caption(
            "The simulation stays mounted while live data refreshes. Drag its lower-right "
            "corner to resize or use Enlarge for full-screen controls."
        )
        render_wokwi()
