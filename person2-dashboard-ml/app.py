from datetime import datetime, timezone
from pathlib import Path
import time

import requests
import streamlit as st
import streamlit.components.v1 as components
from streamlit_autorefresh import st_autorefresh

from monitor_logic import detect_rapid_drop


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


def render_tank(level: float) -> None:
    template_path = Path(__file__).parent.parent / "person3-3d-tank" / "tank_viewer.html"
    template = template_path.read_text(encoding="utf-8")
    safe_level = max(0.0, min(100.0, level))
    html = template.replace("__LEVEL_PERCENT__", f"{safe_level:.1f}")
    components.html(html, height=390, scrolling=False)


st.set_page_config(page_title="Diesel Tank Monitor", page_icon="⛽", layout="wide")
st.title("Diesel Tank Level & Theft Monitor")
st.caption("Live Adafruit IO readings · 500 L tank · updates every 20 seconds")
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
except (requests.RequestException, ValueError) as exc:
    st.error(f"Could not read Adafruit IO feeds: {exc}")
    st.stop()

values = {feed: data[0] for feed, data in readings.items()}
latest_timestamp = max(data[1] for data in readings.values())
age_seconds = max(0, int((datetime.now(timezone.utc) - latest_timestamp).total_seconds()))
st.caption(f"Latest feed update: {age_seconds} seconds ago")

level = max(0.0, min(100.0, values["level"]))
litres = max(0.0, min(500.0, values["litres"]))
generator_on = values["generator"] >= 0.5
pump_on = values["pump"] >= 0.5
firmware_alarm = values["theft"] >= 0.5

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

first, second, third, fourth = st.columns(4)
first.metric("Tank level", f"{level:.1f}%")
second.metric("Fuel volume", f"{litres:.1f} L")
third.metric("Generator", "ON" if generator_on else "OFF")
fourth.metric("Pump", "ON" if pump_on else "OFF")

if alarm:
    st.error("THEFT? Rapid unexplained level drop detected.")
else:
    st.success("No theft alarm reported.")

left, right = st.columns([1, 1])
with left:
    st.subheader("Tank view")
    render_tank(level)
with right:
    st.subheader("Operating state")
    st.write(f"**Sensor distance:** {values['distance']:.1f} cm")
    hours_left = values["hours-left"]
    st.write(
        "**Estimated hours left:** "
        + (f"{hours_left:.1f} h" if hours_left >= 0 else "Not available yet")
    )
    st.write(
        "**Alarm source:** "
        + (
            "Firmware and/or dashboard trend rule"
            if alarm
            else "None"
        )
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
