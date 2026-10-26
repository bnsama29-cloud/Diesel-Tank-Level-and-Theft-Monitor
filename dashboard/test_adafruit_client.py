import unittest
from unittest.mock import Mock, patch

from adafruit_client import (
    decode_remote_command,
    encode_remote_command,
    publish_command,
)


class RemoteCommandTests(unittest.TestCase):
    def test_round_trips_distance_and_generator_inputs(self):
        for distance, generator_on in ((5.0, False), (24.2, True), (105.0, False)):
            with self.subTest(distance=distance, generator_on=generator_on):
                command = encode_remote_command(distance, generator_on)
                self.assertEqual(
                    decode_remote_command(command),
                    (round(distance * 10) / 10, generator_on),
                )

    def test_release_command_is_not_a_remote_override(self):
        self.assertIsNone(decode_remote_command(0))
        self.assertIsNone(decode_remote_command(1))

    def test_rejects_distance_outside_calibrated_range(self):
        with self.assertRaises(ValueError):
            encode_remote_command(106, False)
        with self.assertRaises(ValueError):
            encode_remote_command(4.9, False)

    @patch("adafruit_client.requests.post")
    def test_publishes_encoded_value_to_command_feed(self, post):
        post.return_value = Mock()
        publish_command("tank-user", "private-key", 12242)
        post.assert_called_once_with(
            "https://io.adafruit.com/api/v2/tank-user/feeds/command/data",
            headers={"X-AIO-Key": "private-key"},
            json={"value": "12242"},
            timeout=10,
        )


if __name__ == "__main__":
    unittest.main()
