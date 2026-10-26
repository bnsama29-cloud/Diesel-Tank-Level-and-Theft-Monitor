import unittest
from pathlib import Path
from unittest.mock import patch

from resizable_dashboard import render_resizable_dashboard


FRONTEND_DIR = Path(__file__).parent / "static" / "resizable_dashboard"


class ResizableDashboardTests(unittest.TestCase):
    def test_frontend_has_initial_three_panel_layout_and_drag_splitters(self):
        html = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")
        script = (FRONTEND_DIR / "index.js").read_text(encoding="utf-8")

        self.assertIn("--left-size: 25%", html)
        self.assertIn('id="interpretation-panel"', html)
        self.assertIn('id="graph-panel"', html)
        self.assertIn('id="simulation-panel"', html)
        self.assertIn("pointerdown", script)
        self.assertIn("pointermove", script)
        self.assertIn("Plotly.react", script)
        self.assertIn("streamlit:render", script)
        self.assertIn("window.screen.availHeight", script)

    @patch("resizable_dashboard._dashboard_component")
    def test_component_receives_latest_values_and_graph_with_stable_key(self, component):
        latest = {
            "litres": 250.0,
            "level_percent": 50.0,
            "generator_on": True,
            "pump_on": False,
            "hours_left": 12.5,
            "distance_cm": 55.0,
        }

        render_resizable_dashboard(
            latest=latest,
            status="Generator running",
            explanation="Fuel use is being monitored.",
            freshness="LIVE",
            age_seconds=1,
            figure_json='{"data":[],"layout":{}}',
        )

        kwargs = component.call_args.kwargs
        self.assertEqual(kwargs["latest"], latest)
        self.assertEqual(kwargs["chart"], {"data": [], "layout": {}})
        self.assertEqual(kwargs["key"], "diesel-resizable-dashboard")


if __name__ == "__main__":
    unittest.main()
