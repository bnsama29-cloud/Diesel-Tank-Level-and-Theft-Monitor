from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from urllib.parse import quote
from typing import Any

import requests


TANK_CAPACITY_LITRES = 100.0
HISTORY_LIMIT = 120


def parse_telemetry_record(record: Any) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise ValueError("Adafruit IO returned a malformed telemetry record.")

    value = record.get("value")
    try:
        payload = json.loads(value) if isinstance(value, str) else value
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError("Adafruit IO telemetry value is not valid JSON.") from exc
    if not isinstance(payload, dict):
        raise ValueError("Adafruit IO telemetry value must be a JSON object.")

    timestamp = payload.get("timestamp")
    if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)):
        raise ValueError("Telemetry field 'timestamp' must be a Unix timestamp.")
    if not math.isfinite(timestamp) or timestamp < 1_700_000_000:
        raise ValueError("Telemetry field 'timestamp' is invalid.")
    try:
        payload["timestamp"] = datetime.fromtimestamp(timestamp, timezone.utc)
    except (OverflowError, OSError, ValueError) as exc:
        raise ValueError("Telemetry field 'timestamp' is invalid.") from exc

    fields = {
        "distance_cm": (2.0, 400.0),
        "level_percent": (0.0, 100.0),
        "hours_left": (-1.0, math.inf),
    }
    for field, (minimum, maximum) in fields.items():
        field_value = payload.get(field)
        if isinstance(field_value, bool) or not isinstance(field_value, (int, float)):
            raise ValueError(f"Telemetry field '{field}' must be numeric.")
        if not math.isfinite(field_value) or not minimum <= field_value <= maximum:
            raise ValueError(f"Telemetry field '{field}' is out of range.")
        payload[field] = float(field_value)

    raw_litres = payload.get("litres")
    if (
        isinstance(raw_litres, bool)
        or not isinstance(raw_litres, (int, float))
        or not math.isfinite(raw_litres)
        or raw_litres < 0
    ):
        raise ValueError("Telemetry field 'litres' is out of range.")
    expected_litres = payload["level_percent"] / 100.0 * TANK_CAPACITY_LITRES
    payload["litres_recovered"] = not math.isclose(
        raw_litres, expected_litres, rel_tol=0.0, abs_tol=0.1
    )
    payload["litres"] = expected_litres

    manual_request_id = payload.get("manual_request_id", 0)
    if (
        isinstance(manual_request_id, bool)
        or not isinstance(manual_request_id, int)
        or not 0 <= manual_request_id <= 4_294_967_295
    ):
        raise ValueError("Telemetry field 'manual_request_id' is out of range.")

    for field in ("generator_on", "pump_on", "theft_alarm"):
        if not isinstance(payload.get(field), bool):
            raise ValueError(f"Telemetry field '{field}' must be boolean.")

    if payload["hours_left"] < 0:
        payload["hours_left"] = None

    created_at = record.get("created_at")
    try:
        received_at = datetime.fromisoformat(
            created_at.replace("Z", "+00:00")
        )
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("Adafruit IO record has an invalid created_at timestamp.") from exc
    if received_at.tzinfo is None:
        received_at = received_at.replace(tzinfo=timezone.utc)
    payload["received_at"] = received_at.astimezone(timezone.utc)
    return payload


def post_manual_acknowledgment(
    username: str,
    key: str,
    feed: str,
    request_id: int,
) -> None:
    if not username or not key or not feed:
        raise ValueError(
            "Adafruit IO username, key, and acknowledgment feed are required."
        )
    if (
        isinstance(request_id, bool)
        or not isinstance(request_id, int)
        or not 1 <= request_id <= 4_294_967_295
    ):
        raise ValueError("Manual reading acknowledgment ID is invalid.")

    url = (
        f"https://io.adafruit.com/api/v2/{quote(username, safe='')}"
        f"/feeds/{quote(feed, safe='')}/data"
    )
    response = requests.post(
        url,
        headers={"X-AIO-Key": key},
        json={"value": str(request_id)},
        timeout=8,
    )
    response.raise_for_status()


def parse_telemetry_history(records: Any) -> list[dict[str, Any]]:
    if not isinstance(records, list):
        raise ValueError("Adafruit IO telemetry history must be a JSON list.")
    readings = [parse_telemetry_record(record) for record in records]
    return sorted(
        readings,
        key=lambda reading: (reading["received_at"], reading["timestamp"]),
    )


def fetch_telemetry_history(
    username: str,
    key: str,
    feed: str,
    limit: int = HISTORY_LIMIT,
) -> list[dict[str, Any]]:
    if not username or not key or not feed:
        raise ValueError("Adafruit IO username, key, and feed are required.")
    if not 1 <= limit <= 1000:
        raise ValueError("Telemetry history limit must be between 1 and 1000.")

    url = (
        f"https://io.adafruit.com/api/v2/{quote(username, safe='')}"
        f"/feeds/{quote(feed, safe='')}/data"
    )
    response = requests.get(
        url,
        headers={"X-AIO-Key": key},
        params={"limit": limit},
        timeout=8,
    )
    response.raise_for_status()
    return parse_telemetry_history(response.json())
