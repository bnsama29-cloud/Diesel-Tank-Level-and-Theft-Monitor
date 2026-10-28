from pathlib import Path
import json
from typing import Any

import streamlit.components.v1 as components


_COMPONENT_DIR = Path(__file__).parent / "static" / "resizable_dashboard"
_dashboard_component = components.declare_component(
    "diesel_resizable_dashboard",
    path=str(_COMPONENT_DIR),
)


def render_resizable_dashboard(
    *,
    latest: dict[str, Any] | None,
    status: str,
    explanation: str,
    freshness: str,
    age_seconds: int | None,
    figure_json: str | None,
    fetch_error: str | None = None,
) -> None:
    latest_payload = None
    if latest is not None:
        latest_payload = {
            "litres": latest["litres"],
            "level_percent": latest["level_percent"],
            "generator_on": latest["generator_on"],
            "pump_on": latest["pump_on"],
            "theft_alarm": latest["theft_alarm"],
            "hours_left": latest["hours_left"],
            "distance_cm": latest["distance_cm"],
        }

    _dashboard_component(
        latest=latest_payload,
        status=status,
        explanation=explanation,
        freshness=freshness,
        age_seconds=age_seconds,
        chart=json.loads(figure_json) if figure_json else None,
        fetch_error=fetch_error,
        key="diesel-resizable-dashboard",
    )
