import tempfile
import unittest
from pathlib import Path

from tank_view import build_tank_html


class TankViewTests(unittest.TestCase):
    def test_injects_clamped_live_values_into_viewer(self):
        with tempfile.TemporaryDirectory() as folder:
            template_path = Path(folder) / "tank.html"
            template_path.write_text(
                '<div>__LEVEL_PERCENT__</div><div>__LITRES__</div>',
                encoding="utf-8",
            )
            html = build_tank_html(template_path, 42.5, 212.5)
        self.assertEqual(html, "<div>42.5</div><div>212.5</div>")

    def test_clamps_values_to_physical_tank_range(self):
        with tempfile.TemporaryDirectory() as folder:
            template_path = Path(folder) / "tank.html"
            template_path.write_text("__LEVEL_PERCENT__|__LITRES__", encoding="utf-8")
            html = build_tank_html(template_path, 120, -10)
        self.assertEqual(html, "100.0|0.0")


if __name__ == "__main__":
    unittest.main()
