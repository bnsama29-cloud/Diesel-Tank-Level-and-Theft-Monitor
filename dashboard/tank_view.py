import base64
from pathlib import Path


TANK_CAPACITY_LITRES = 500.0


def build_tank_html(
    template_path: Path,
    level_percent: float,
    litres: float,
    model_path: Path | None = None,
) -> str:
    template = template_path.read_text(encoding="utf-8")
    safe_level = max(0.0, min(100.0, level_percent))
    safe_litres = max(0.0, min(TANK_CAPACITY_LITRES, litres))
    model_data = (
        base64.b64encode(model_path.read_bytes()).decode("ascii")
        if model_path is not None
        else ""
    )
    return (
        template.replace("__LEVEL_PERCENT__", f"{safe_level:.1f}")
        .replace("__LITRES__", f"{safe_litres:.1f}")
        .replace("__TANK_MODEL_BASE64__", model_data)
    )
