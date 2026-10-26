import unittest

from wokwi_embed import WOKWI_EMBED_URL, build_wokwi_embed_html


class WokwiEmbedTests(unittest.TestCase):
    def test_embed_is_resizable_and_has_fullscreen_control(self):
        html = build_wokwi_embed_html()
        self.assertIn('resize: both', html)
        self.assertIn('width: 100%', html)
        self.assertIn('id="fullscreen-simulation"', html)
        self.assertIn("requestFullscreen()", html)
        self.assertIn(f'src="{WOKWI_EMBED_URL}"', html)


if __name__ == "__main__":
    unittest.main()
