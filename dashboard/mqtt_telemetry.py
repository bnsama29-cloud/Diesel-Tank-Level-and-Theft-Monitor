from __future__ import annotations

import json
import math
import threading
from collections import deque
from datetime import datetime, timezone
from typing import Any

import paho.mqtt.client as mqtt


HISTORY_LIMIT = 3600


def parse_telemetry_payload(payload: bytes | str) -> dict[str, Any]:
    try:
        data = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
        raise ValueError("MQTT message is not valid JSON.") from exc

    if not isinstance(data, dict):
        raise ValueError("MQTT telemetry must be a JSON object.")

    timestamp = data.get("timestamp")
    if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)):
        raise ValueError("MQTT telemetry field 'timestamp' must be a Unix timestamp.")
    if not math.isfinite(timestamp) or timestamp < 1_700_000_000:
        raise ValueError("MQTT telemetry field 'timestamp' is invalid.")
    try:
        data["timestamp"] = datetime.fromtimestamp(timestamp, timezone.utc)
    except (OverflowError, OSError, ValueError) as exc:
        raise ValueError("MQTT telemetry field 'timestamp' is invalid.") from exc

    numeric_fields = {
        "distance_cm": (2.0, 400.0),
        "level_percent": (0.0, 100.0),
        "litres": (0.0, 500.0),
        "hours_left": (-1.0, math.inf),
    }
    for field, (minimum, maximum) in numeric_fields.items():
        value = data.get(field)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"MQTT telemetry field '{field}' must be numeric.")
        if not math.isfinite(value) or not minimum <= value <= maximum:
            raise ValueError(f"MQTT telemetry field '{field}' is out of range.")
        data[field] = float(value)

    for field in ("generator_on", "pump_on", "theft_alarm"):
        if not isinstance(data.get(field), bool):
            raise ValueError(f"MQTT telemetry field '{field}' must be boolean.")

    if data["hours_left"] < 0:
        data["hours_left"] = None

    return data


class MQTTTelemetryStore:
    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        topic: str,
    ) -> None:
        if not host or not username or not password or not topic:
            raise ValueError("MQTT host, username, password, and topic are required.")
        if not 1 <= port <= 65535:
            raise ValueError("MQTT port must be between 1 and 65535.")

        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._topic = topic
        self._lock = threading.Lock()
        self._history: deque[dict[str, Any]] = deque(maxlen=HISTORY_LIMIT)
        self._latest: dict[str, Any] | None = None
        self._client: mqtt.Client | None = None
        self._connected = False
        self._last_error: str | None = None

    def start(self) -> None:
        if self._client is not None:
            return

        callback_api = getattr(mqtt, "CallbackAPIVersion", None)
        client = (
            mqtt.Client(callback_api.VERSION2)
            if callback_api is not None
            else mqtt.Client()
        )
        client.username_pw_set(self._username, self._password)
        client.tls_set()
        client.reconnect_delay_set(min_delay=1, max_delay=15)
        client.on_connect = self._on_connect
        client.on_disconnect = self._on_disconnect
        client.on_message = self._on_message
        self._client = client
        client.connect_async(self._host, self._port, keepalive=30)
        client.loop_start()

    def get_latest(self) -> dict[str, Any] | None:
        with self._lock:
            return self._latest.copy() if self._latest is not None else None

    def get_history(self) -> list[dict[str, Any]]:
        with self._lock:
            return [reading.copy() for reading in self._history]

    @property
    def is_connected(self) -> bool:
        with self._lock:
            return self._connected

    @property
    def last_error(self) -> str | None:
        with self._lock:
            return self._last_error

    def _on_connect(self, client, _userdata, _flags, reason_code, *_properties) -> None:
        if int(reason_code) != 0:
            with self._lock:
                self._connected = False
                self._last_error = f"MQTT broker rejected the connection (code {reason_code})."
            return

        result, _message_id = client.subscribe(self._topic, qos=0)
        with self._lock:
            self._connected = result == mqtt.MQTT_ERR_SUCCESS
            self._last_error = (
                None
                if self._connected
                else f"Could not subscribe to MQTT topic '{self._topic}' (code {result})."
            )

    def _on_disconnect(self, _client, _userdata, *args) -> None:
        with self._lock:
            self._connected = False
            if args and int(args[-2] if len(args) > 2 else args[0]) != 0:
                self._last_error = "MQTT connection lost; reconnecting."

    def _on_message(self, _client, _userdata, message) -> None:
        try:
            reading = parse_telemetry_payload(message.payload)
        except ValueError as exc:
            with self._lock:
                self._last_error = str(exc)
            return

        reading["received_at"] = datetime.now(timezone.utc)
        with self._lock:
            self._latest = reading
            self._history.append(reading)
            self._last_error = None
