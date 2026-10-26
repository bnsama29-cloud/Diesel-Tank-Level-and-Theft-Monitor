import tempfile
import unittest
from pathlib import Path

from tank_view import build_tank_html


class TankViewTests(unittest.TestCase):
    def test_injects_clamped_live_values_into_viewer(self):
        with tempfile.TemporaryDirectory() as folder:
            template_path = Path(folder) / "tank.html"
            template_path.write_text(
                '<div>__LEVEL_PERCENT__</div><div>__LITRES__ / __TANK_CAPACITY_LITRES__ L</div>',
                encoding="utf-8",
            )
            html = build_tank_html(template_path, 42.5, 50)
        self.assertEqual(html, "<div>42.5</div><div>50.0 / 100 L</div>")

    def test_clamps_values_to_physical_tank_range(self):
        with tempfile.TemporaryDirectory() as folder:
            template_path = Path(folder) / "tank.html"
            template_path.write_text("__LEVEL_PERCENT__|__LITRES__", encoding="utf-8")
            html = build_tank_html(template_path, 120, -10)
        self.assertEqual(html, "100.0|0.0")

    def test_embeds_team_gltf_model_for_component_rendering(self):
        with tempfile.TemporaryDirectory() as folder:
            template_path = Path(folder) / "tank.html"
            model_path = Path(folder) / "tank.gltf"
            template_path.write_text("__TANK_MODEL_BASE64__", encoding="utf-8")
            model_path.write_bytes(b'{"asset":{"version":"2.0"}}')
            html = build_tank_html(template_path, 50, 50, model_path)
        self.assertEqual(
            html,
            "eyJhc3NldCI6eyJ2ZXJzaW9uIjoiMi4wIn19",
        )


if __name__ == "__main__":
    unittest.main()
