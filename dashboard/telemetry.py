import math


TANK_CAPACITY_LITRES = 500.0
FULL_DISTANCE_CM = 5.0
EMPTY_DISTANCE_CM = 105.0


def valid_level(value: float) -> bool:
    return math.isfinite(value) and 0.0 <= value <= 100.0


def level_from_sensor_distance(distance_cm: float) -> float | None:
    if not math.isfinite(distance_cm) or not 2.0 <= distance_cm <= 400.0:
        return None
    fraction = (EMPTY_DISTANCE_CM - distance_cm) / (
        EMPTY_DISTANCE_CM - FULL_DISTANCE_CM
    )
    return max(0.0, min(1.0, fraction)) * 100.0


def display_level(raw_level: float, distance_cm: float) -> tuple[float | None, bool]:
    if valid_level(raw_level):
        return raw_level, False
    return level_from_sensor_distance(distance_cm), True


def display_litres(raw_litres: float, level_percent: float | None) -> tuple[float | None, bool]:
    if math.isfinite(raw_litres) and 0.0 <= raw_litres <= TANK_CAPACITY_LITRES:
        return raw_litres, False
    if level_percent is None:
        return None, True
    return level_percent / 100.0 * TANK_CAPACITY_LITRES, True
