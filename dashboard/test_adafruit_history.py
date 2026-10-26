import unittest
from datetime import datetime, timezone

from adafruit_history import parse_level_history


class AdafruitHistoryTests(unittest.TestCase):
    def test_parses_and_sorts_feed_history(self):
        rows = parse_level_history(
            [
                {"value": "55.5", "created_at": "2026-10-26T10:02:00Z"},
                {"value": "42", "created_at": "2026-10-26T10:01:00Z"},
            ]
        )
        self.assertEqual([row["level"] for row in rows], [42.0, 55.5])
        self.assertEqual(
            rows[0]["timestamp"],
            datetime(2026, 10, 26, 10, 1, tzinfo=timezone.utc),
        )

    def test_preserves_out_of_range_level_for_validation(self):
        rows = parse_level_history(
            [{"value": "120", "created_at": "2026-10-26T10:00:00Z"}]
        )
        self.assertEqual(rows[0]["level"], 120.0)

    def test_rejects_malformed_history(self):
        with self.assertRaises(ValueError):
            parse_level_history({"value": "55"})
        with self.assertRaises(ValueError):
            parse_level_history([{"value": "bad", "created_at": "invalid"}])


if __name__ == "__main__":
    unittest.main()
