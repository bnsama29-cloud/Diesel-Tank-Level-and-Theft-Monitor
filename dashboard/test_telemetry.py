import unittest

from telemetry import display_level, display_litres, level_from_sensor_distance


class TelemetryDisplayTests(unittest.TestCase):
    def test_valid_level_is_preserved(self):
        self.assertEqual(display_level(67.5, 24.0), (67.5, False))

    def test_invalid_level_is_recovered_from_distance(self):
        self.assertEqual(display_level(1000, 55), (50.0, True))
        self.assertEqual(display_level(1000, 5), (100.0, True))

    def test_unrecoverable_invalid_level_is_not_shown_as_percent(self):
        self.assertEqual(display_level(1000, -1), (None, True))

    def test_sensor_distance_is_calibrated_and_clamped(self):
        self.assertEqual(level_from_sensor_distance(5), 100.0)
        self.assertEqual(level_from_sensor_distance(105), 0.0)
        self.assertIsNone(level_from_sensor_distance(401))

    def test_invalid_litres_are_recovered_from_display_level(self):
        self.assertEqual(display_litres(10000, 60), (300.0, True))
        self.assertEqual(display_litres(250, 60), (250.0, False))
        self.assertEqual(display_litres(-1, None), (None, True))


if __name__ == "__main__":
    unittest.main()
