from collections.abc import Sequence


def level_from_distance(
    distance_cm: float,
    capacity_litres: float = 500.0,
    full_distance_cm: float = 5.0,
    empty_distance_cm: float = 105.0,
) -> tuple[float, float]:
    if empty_distance_cm <= full_distance_cm:
        raise ValueError("Empty distance must be greater than full distance.")
    fraction = (empty_distance_cm - distance_cm) / (
        empty_distance_cm - full_distance_cm
    )
    fraction = max(0.0, min(1.0, fraction))
    return fraction * 100.0, fraction * capacity_litres


def pump_should_run(level_percent: float, currently_running: bool) -> bool:
    if level_percent <= 20.0:
        return True
    if level_percent > 90.0:
        return False
    return currently_running


def detect_rapid_drop(
    readings: Sequence[tuple[float, float]],
    now_seconds: float,
    window_seconds: float = 60.0,
    drop_threshold_percent: float = 5.0,
) -> bool:
    recent = [
        sample
        for sample in readings
        if 0 <= now_seconds - sample[0] <= window_seconds
    ]
    if len(recent) < 2:
        return False
    baseline = min(recent, key=lambda sample: sample[0])
    latest = max(recent, key=lambda sample: sample[0])
    return baseline[1] - latest[1] > drop_threshold_percent
