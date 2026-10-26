from datetime import datetime, timezone
from urllib.parse import quote

import requests


def fetch_latest_feed(
    username: str,
    key: str,
    feed: str,
) -> tuple[float, datetime]:
    url = (
        f"https://io.adafruit.com/api/v2/{quote(username, safe='')}"
        f"/feeds/{quote(feed, safe='')}/data/last"
    )
    response = requests.get(url, headers={"X-AIO-Key": key}, timeout=10)
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


def fetch_level_history(username: str, key: str, limit: int = 500):
    from adafruit_history import parse_level_history

    url = (
        f"https://io.adafruit.com/api/v2/{quote(username, safe='')}"
        "/feeds/level/data"
    )
    response = requests.get(
        url,
        headers={"X-AIO-Key": key},
        params={"limit": limit},
        timeout=10,
    )
    response.raise_for_status()
    return parse_level_history(response.json())
