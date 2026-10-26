from pathlib import Path


TANK_CAPACITY_LITRES = 500.0


def build_tank_html(template_path: Path, level_percent: float, litres: float) -> str:
    template = template_path.read_text(encoding="utf-8")
    safe_level = max(0.0, min(100.0, level_percent))
    safe_litres = max(0.0, min(TANK_CAPACITY_LITRES, litres))
    return (
        template.replace("__LEVEL_PERCENT__", f"{safe_level:.1f}")
        .replace("__LITRES__", f"{safe_litres:.1f}")
    )
