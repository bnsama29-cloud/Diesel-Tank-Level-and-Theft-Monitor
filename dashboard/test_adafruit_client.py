import json
import unittest
from unittest.mock import patch

from adafruit_client import (
    fetch_telemetry_history,
    parse_telemetry_history,
    parse_telemetry_record,
)


def telemetry_record(**overrides):
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
    return {
        "value": json.dumps(data),
        "created_at": "2026-10-26T11:00:00Z",
    }


class AdafruitClientTests(unittest.TestCase):
    def test_parse_record_validates_json_and_converts_unavailable_runtime(self):
        reading = parse_telemetry_record(telemetry_record())

        self.assertEqual(reading["level_percent"], 50.0)
        self.assertIsNone(reading["hours_left"])
        self.assertFalse(reading["generator_on"])
        self.assertIsNotNone(reading["timestamp"].tzinfo)
        self.assertIsNotNone(reading["received_at"].tzinfo)

    def test_parse_record_rejects_malformed_and_out_of_range_payloads(self):
        with self.assertRaisesRegex(ValueError, "valid JSON"):
            parse_telemetry_record(
                {"value": "not-json", "created_at": "2026-10-26T11:00:00Z"}
            )
        with self.assertRaisesRegex(ValueError, "out of range"):
            parse_telemetry_record(telemetry_record(level_percent=1000))

    def test_parse_record_requires_boolean_switch_states(self):
        with self.assertRaisesRegex(ValueError, "must be boolean"):
            parse_telemetry_record(telemetry_record(generator_on=1))

    def test_history_is_sorted_oldest_first(self):
        older = telemetry_record(timestamp=1793009000)
        newer = telemetry_record(timestamp=1793010000)

        readings = parse_telemetry_history([newer, older])

        self.assertLess(readings[0]["timestamp"], readings[1]["timestamp"])

    @patch("adafruit_client.requests.get")
    def test_fetches_a_single_feed_with_api_key_header(self, get):
        response = get.return_value
        response.json.return_value = [telemetry_record()]

        readings = fetch_telemetry_history("tank-user", "private-key", "tank-telemetry")

        get.assert_called_once()
        args, kwargs = get.call_args
        self.assertEqual(
            args[0],
            "https://io.adafruit.com/api/v2/tank-user/feeds/tank-telemetry/data",
        )
        self.assertEqual(kwargs["headers"], {"X-AIO-Key": "private-key"})
        self.assertEqual(kwargs["params"], {"limit": 120})
        self.assertEqual(len(readings), 1)


if __name__ == "__main__":
    unittest.main()
