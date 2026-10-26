import unittest

from monitor_logic import detect_rapid_drop, level_from_distance, pump_should_run


class TankLogicTests(unittest.TestCase):
    def test_distance_conversion_and_clamping(self):
        self.assertEqual(level_from_distance(5), (100.0, 500.0))
        self.assertEqual(level_from_distance(55), (50.0, 250.0))
        self.assertEqual(level_from_distance(105), (0.0, 0.0))
        self.assertEqual(level_from_distance(0), (100.0, 500.0))
        self.assertEqual(level_from_distance(120), (0.0, 0.0))

    def test_pump_hysteresis_boundaries(self):
        self.assertTrue(pump_should_run(20.0, False))
        self.assertTrue(pump_should_run(50.0, True))
        self.assertFalse(pump_should_run(50.0, False))
        self.assertTrue(pump_should_run(90.0, True))
        self.assertFalse(pump_should_run(90.01, True))

    def test_theft_drop_requires_more_than_five_points_within_window(self):
        self.assertTrue(detect_rapid_drop([(10, 30), (60, 24.9)], 60))
        self.assertFalse(detect_rapid_drop([(10, 30), (60, 25)], 60))
        self.assertFalse(detect_rapid_drop([(0, 30), (61, 20)], 61))
        self.assertFalse(detect_rapid_drop([(20, 30)], 20))


if __name__ == "__main__":
    unittest.main()
