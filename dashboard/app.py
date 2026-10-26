from datetime import datetime, timezone
from pathlib import Path
import time

import plotly.graph_objects as go
import requests
import streamlit as st
import streamlit.components.v1 as components
from streamlit_autorefresh import st_autorefresh

from adafruit_history import parse_level_history
from monitor_logic import detect_rapid_drop
from tank_view import build_tank_html


FEEDS = {
    "distance": "Distance (cm)",
    "level": "Level (%)",
    "litres": "Fuel (L)",
    "generator": "Generator",
    "pump": "Pump",
    "theft": "Firmware alarm",
    "hours-left": "Hours left",
}
POLL_INTERVAL_MS = 20_000
THEFT_WINDOW_SECONDS = 60
THEFT_DROP_PERCENT = 5.0
TANK_CAPACITY_LITRES = 500.0
HISTORY_LIMIT = 500


def fetch_level_history(username: str, key: str) -> list[dict[str, float | datetime]]:
    url = f"https://io.adafruit.com/api/v2/{username}/feeds/level/data"
    response = requests.get(
        url,
        headers={"X-AIO-Key": key},
        params={"limit": HISTORY_LIMIT},
        timeout=10,
    )
    response.raise_for_status()
    return parse_level_history(response.json())


def fetch_latest_feed(username: str, key: str, feed: str) -> tuple[float, datetime]:
    url = f"https://io.adafruit.com/api/v2/{username}/feeds/{feed}/data/last"
    response = requests.get(
        url,
        headers={"X-AIO-Key": key},
        timeout=10,
    )
    response.raise_for_status()
    payload = response.json()
    try:
        value = float(payload["value"])
        timestamp = datetime.fromisoformat(
            payload["created_at"].replace("Z", "+00:00")
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"Feed '{feed}' returned an invalid latest-data record.") from exc
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return value, timestamp


def render_tank(level: float, litres: float) -> None:
    template_path = Path(__file__).parent / "assets" / "tank_viewer.html"
    html = build_tank_html(template_path, level, litres)
    components.html(html, height=390, scrolling=False)


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
      .block-container { max-width: 1440px; padding-top: 2rem; }
      h1, h2, h3 { letter-spacing: -0.025em; }
      div[data-testid="stMetric"] {
        background: linear-gradient(145deg, rgba(25,46,67,.96), rgba(15,27,42,.96));
        border: 1px solid rgba(125,175,210,.18);
        border-radius: 16px;
        padding: 18px 20px;
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
        div[data-testid="stMetricValue"] { font-size: 1.35rem; }
      }
    </style>
    """,
    unsafe_allow_html=True,
)
st.title("⛽ Diesel Tank Monitor")
st.markdown(
    '<div class="hero-note">Live simulation monitor · 500 L diesel chamber</div>',
    unsafe_allow_html=True,
)
st_autorefresh(interval=POLL_INTERVAL_MS, key="feed-refresh")

try:
    username = st.secrets["AIO_USERNAME"]
    aio_key = st.secrets["AIO_KEY"]
except (KeyError, FileNotFoundError):
    st.error(
        "Adafruit IO credentials are not configured. Add AIO_USERNAME and AIO_KEY "
        "in Streamlit Community Cloud → App settings → Secrets."
    )
    st.stop()

try:
    readings = {
        feed: fetch_latest_feed(username, aio_key, feed)
        for feed in FEEDS
    }
    level_history = fetch_level_history(username, aio_key)
except (requests.RequestException, ValueError) as exc:
    st.error(f"Could not load Adafruit IO data. Check the feed names and app secrets. Details: {exc}")
    st.stop()

values = {feed: data[0] for feed, data in readings.items()}
latest_timestamp = max(data[1] for data in readings.values())
age_seconds = max(0, int((datetime.now(timezone.utc) - latest_timestamp).total_seconds()))
connection_label = "LIVE" if age_seconds < 90 else "STALE"
st.caption(f"● {connection_label} · Latest feed update {age_seconds} seconds ago")

level = max(0.0, min(100.0, values["level"]))
litres = max(0.0, min(TANK_CAPACITY_LITRES, values["litres"]))
generator_on = values["generator"] >= 0.5
pump_on = values["pump"] >= 0.5
firmware_alarm = values["theft"] >= 0.5
level_status = "LOW" if level < 20 else "FULL" if level > 90 else "MEDIUM"

if "level_history" not in st.session_state:
    st.session_state.level_history = []
sample_time = readings["level"][1].timestamp()
history = st.session_state.level_history
if not history or history[-1][0] != sample_time:
    history.append((sample_time, level))
st.session_state.level_history = [
    sample for sample in history
    if 0 <= time.time() - sample[0] <= THEFT_WINDOW_SECONDS
]

dashboard_alarm = (
    not generator_on
    and detect_rapid_drop(
        st.session_state.level_history,
        time.time(),
        window_seconds=THEFT_WINDOW_SECONDS,
        drop_threshold_percent=THEFT_DROP_PERCENT,
    )
)
alarm = firmware_alarm or dashboard_alarm

st.subheader("Live status")
first, second, third, fourth = st.columns(4)
first.metric("Tank level", f"{level:.1f}%", level_status)
second.metric("Fuel volume", f"{litres:.1f} L", f"of {TANK_CAPACITY_LITRES:.0f} L")
third.metric("Generator", "RUNNING" if generator_on else "STOPPED")
fourth.metric("Refill pump", "ON" if pump_on else "OFF")

if alarm:
    st.error("🚨 THEFT ALERT · Rapid unexplained tank-level drop detected.")
else:
    st.success("✅ No theft alarm reported.")

left, right = st.columns([1, 1.35], gap="large")
with left:
    st.subheader("Interactive 3D diesel chamber")
    render_tank(level, litres)
with right:
    st.subheader("Fuel level history")
    if len(level_history) > 1:
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
            visible_history = level_history
        else:
            cutoff = datetime.now(timezone.utc).timestamp() - range_seconds
            visible_history = [
                reading for reading in level_history
                if reading["timestamp"].timestamp() >= cutoff
            ]
        if len(visible_history) > 1:
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
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
            st.caption(
                f"Showing {len(visible_history)} of {len(level_history)} stored tank readings."
            )
        else:
            st.info("Not enough readings yet for this time range. Leave the simulator running to collect more.")
    else:
        st.info("The graph appears after Adafruit IO has at least two level readings.")

st.divider()
left, right = st.columns(2)
with left:
    st.subheader("Operating state")
    st.write(f"**Sensor distance:** {values['distance']:.1f} cm")
    st.write(f"**Generator:** {'🟢 ON' if generator_on else '⚪ OFF'}")
    st.write(f"**Pump relay:** {'🟢 ON' if pump_on else '⚪ OFF'}")
    st.write(f"**Alarm:** {'🔴 THEFT?' if alarm else '🟢 Clear'}")
with right:
    st.subheader("Consumption estimate")
    hours_left = values["hours-left"]
    st.write(
        "**Estimated hours left:** "
        + (f"{hours_left:.1f} h" if hours_left >= 0 else "Not available yet")
    )
    st.caption(
        "Dashboard rule uses a >5 percentage-point drop within 60 seconds. "
        "A trained ML model is not included yet."
    )

st.subheader("Latest feed values")
st.dataframe(
    [
        {
            "Feed": FEEDS[feed],
            "Value": f"{values[feed]:.2f}",
            "Updated": readings[feed][1].astimezone().strftime("%Y-%m-%d %H:%M:%S %Z"),
        }
        for feed in FEEDS
    ],
    hide_index=True,
    use_container_width=True,
)
