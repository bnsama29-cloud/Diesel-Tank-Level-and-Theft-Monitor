from datetime import datetime, timezone
from typing import Any


def parse_level_history(payload: Any) -> list[dict[str, float | datetime]]:
    if not isinstance(payload, list):
        raise ValueError("Adafruit IO level history must be a JSON list.")

    readings: list[dict[str, float | datetime]] = []
    for item in payload:
        if not isinstance(item, dict):
            raise ValueError("Adafruit IO returned a malformed level history item.")
        try:
            level = float(item["value"])
            timestamp = datetime.fromisoformat(
                item["created_at"].replace("Z", "+00:00")
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                "Adafruit IO returned a level reading without a valid value/timestamp."
            ) from exc
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        readings.append({"timestamp": timestamp, "level": level})

    readings.sort(key=lambda reading: reading["timestamp"])
    return readings
