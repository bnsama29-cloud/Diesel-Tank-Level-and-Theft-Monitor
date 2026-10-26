import json
import unittest
from types import SimpleNamespace

from mqtt_telemetry import MQTTTelemetryStore, parse_telemetry_payload


def telemetry_payload(**overrides):
    data = {
        "timestamp": 1793010000,
        "distance_cm": 55,
        "level_percent": 50,
        "litres": 250,
        "generator_on": False,
        "pump_on": False,
        "theft_alarm": False,
        "hours_left": -1,
    }
    data.update(overrides)
    return json.dumps(data)


class MqttTelemetryTests(unittest.TestCase):
    def test_parse_payload_converts_unavailable_hours_to_none(self):
        reading = parse_telemetry_payload(telemetry_payload())
        self.assertEqual(reading["level_percent"], 50.0)
        self.assertIsNone(reading["hours_left"])
        self.assertFalse(reading["generator_on"])
        self.assertIsNotNone(reading["timestamp"].tzinfo)

    def test_parse_payload_rejects_invalid_json_and_out_of_range_level(self):
        with self.assertRaisesRegex(ValueError, "valid JSON"):
            parse_telemetry_payload(b"not-json")
        with self.assertRaisesRegex(ValueError, "out of range"):
            parse_telemetry_payload(telemetry_payload(level_percent=1000))

    def test_parse_payload_requires_boolean_switch_states(self):
        with self.assertRaisesRegex(ValueError, "must be boolean"):
            parse_telemetry_payload(telemetry_payload(generator_on=1))

    def test_store_keeps_latest_reading_and_history(self):
        store = MQTTTelemetryStore(
            "broker.example", 8883, "username", "password", "diesel-tank/telemetry"
        )
        store._on_message(
            None,
            None,
            SimpleNamespace(payload=telemetry_payload(level_percent=42)),
        )

        self.assertEqual(store.get_latest()["level_percent"], 42.0)
        history = store.get_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["level_percent"], 42.0)
        self.assertIsNotNone(history[0]["received_at"].tzinfo)
        self.assertIsNone(store.last_error)

    def test_store_reports_malformed_messages(self):
        store = MQTTTelemetryStore(
            "broker.example", 8883, "username", "password", "diesel-tank/telemetry"
        )
        store._on_message(None, None, SimpleNamespace(payload=b"bad"))

        self.assertIsNone(store.get_latest())
        self.assertIn("valid JSON", store.last_error)


if __name__ == "__main__":
    unittest.main()
