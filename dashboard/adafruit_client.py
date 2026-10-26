from datetime import datetime, timezone
from urllib.parse import quote

import requests


REMOTE_COMMAND_BASE = 10_000
REMOTE_GENERATOR_OFFSET = 2_000


def encode_remote_command(distance_cm: float, generator_on: bool) -> int:
    if not 5.0 <= distance_cm <= 105.0:
        raise ValueError("Distance command must be between 5 and 105 cm.")
    distance_tenths = round(distance_cm * 10)
    return (
        REMOTE_COMMAND_BASE
        + (REMOTE_GENERATOR_OFFSET if generator_on else 0)
        + distance_tenths
    )


def decode_remote_command(value: float) -> tuple[float, bool] | None:
    code = round(value)
    offset = code - REMOTE_COMMAND_BASE
    if offset < 50 or offset > REMOTE_GENERATOR_OFFSET + 1050:
        return None
    generator_on = offset >= REMOTE_GENERATOR_OFFSET
    if generator_on:
        offset -= REMOTE_GENERATOR_OFFSET
    return offset / 10, generator_on


def fetch_latest_feed(username: str, key: str, feed: str) -> tuple[float, datetime]:
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


def fetch_latest_command(username: str, key: str) -> tuple[float, datetime] | None:
    try:
        return fetch_latest_feed(username, key, "command")
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            return None
        raise


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


def publish_command(username: str, key: str, command: int) -> None:
    url = (
        f"https://io.adafruit.com/api/v2/{quote(username, safe='')}"
        "/feeds/command/data"
    )
    response = requests.post(
        url,
        headers={"X-AIO-Key": key},
        json={"value": str(command)},
        timeout=10,
    )
    response.raise_for_status()
