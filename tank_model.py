"""
Tank Model — Physics & Calculations for Diesel Tank Monitor
============================================================

Provides the core calculation engine for a diesel tank monitoring system.
Converts ultrasonic distance readings into fill-level percentages, volumes,
pump control signals (with hysteresis), fuel-consumption estimates, and
legacy theft-detection alerts.

Typical usage::

    from tank_model import TankConfig, TankModel

    model = TankModel(TankConfig(depth_cm=120, capacity_litres=600))
    state = model.process_reading(distance_cm=30.0, generator_on=True)
    print(state)
"""

from __future__ import annotations

import dataclasses
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Deque, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class TankConfig:
    """Immutable configuration for a cylindrical diesel tank.

    Attributes:
        depth_cm:         Total internal depth of the tank in centimetres.
        capacity_litres:  Maximum volume the tank can hold in litres.
        low_pct:          Fill-level percentage at which the pump turns ON.
        high_pct:         Fill-level percentage at which the pump turns OFF.
        theft_drop_pct:   Legacy threshold — minimum drop (%) within the
                          theft window to trigger an alert.
        theft_window_sec: Legacy threshold — time window (seconds) in which
                          the drop is measured.
    """

    depth_cm: float = 100.0
    capacity_litres: float = 500.0
    low_pct: float = 20.0          # pump ON threshold
    high_pct: float = 90.0         # pump OFF threshold
    theft_drop_pct: float = 5.0    # legacy theft-detection drop (for reference)
    theft_window_sec: float = 60.0 # legacy theft-detection window


# ---------------------------------------------------------------------------
# State snapshot returned by TankModel.process_reading()
# ---------------------------------------------------------------------------

@dataclass
class TankState:
    """Snapshot of the current state of the tank system.

    Attributes:
        level_pct:        Current fill level as a percentage (0–100).
        volume_litres:    Current volume of diesel in litres.
        pump_on:          Whether the refill pump is currently running.
        generator_on:     Whether the generator is currently consuming fuel.
        theft_alert:      ``True`` if a legacy theft rule has triggered.
        theft_confidence: Confidence score for the theft alert (0.0–1.0).
        hours_remaining:  Estimated hours of fuel remaining (``None`` if not
                          applicable or insufficient data).
        status:           Human-readable label — ``"LOW"``, ``"MEDIUM"``, or
                          ``"FULL"``.
        timestamp:        Timestamp of the reading.
    """

    level_pct: float
    volume_litres: float
    pump_on: bool
    generator_on: bool
    theft_alert: bool
    theft_confidence: float
    hours_remaining: Optional[float]
    status: str          # "LOW", "MEDIUM", "FULL"
    timestamp: datetime


# ---------------------------------------------------------------------------
# Core calculation engine
# ---------------------------------------------------------------------------

class TankModel:
    """Core calculation engine for the diesel tank monitor.

    Converts raw ultrasonic distance readings into actionable state —
    fill-level, volume, pump hysteresis control, consumption estimates,
    and legacy theft detection.

    Parameters:
        config: A :class:`TankConfig` instance.  Falls back to defaults when
                omitted.
    """

    def __init__(self, config: TankConfig = None) -> None:
        self.config: TankConfig = config or TankConfig()

        # Internal hysteresis state for the refill pump
        self._pump_on: bool = False

        # Rolling window of (timestamp, level_pct) readings.
        # Default 600 entries ≈ 10 minutes at 1 reading/second.
        self._level_history: Deque[Tuple[datetime, float]] = deque(maxlen=600)

    # ------------------------------------------------------------------ #
    # Conversion helpers
    # ------------------------------------------------------------------ #

    def distance_to_level_pct(self, distance_cm: float) -> float:
        """Convert an ultrasonic distance reading to a fill-level percentage.

        The sensor measures the gap between the top of the tank and the
        liquid surface.  ``distance_cm = 0`` → tank is **full**;
        ``distance_cm = depth_cm`` → tank is **empty**.

        The result is clamped to the 0–100 % range.

        Args:
            distance_cm: Distance from the sensor to the liquid surface (cm).

        Returns:
            Fill level as a percentage (0.0–100.0).
        """
        level = ((self.config.depth_cm - distance_cm) / self.config.depth_cm) * 100.0
        return max(0.0, min(100.0, level))

    def level_to_litres(self, level_pct: float) -> float:
        """Convert a fill-level percentage to a volume in litres.

        Assumes a linear (cylindrical) relationship between level and volume.

        Args:
            level_pct: Fill level as a percentage (0.0–100.0).

        Returns:
            Volume in litres.
        """
        return (level_pct / 100.0) * self.config.capacity_litres

    # ------------------------------------------------------------------ #
    # Status classification
    # ------------------------------------------------------------------ #

    def get_status_label(self, level_pct: float) -> str:
        """Return a human-readable status label based on fill-level thresholds.

        Args:
            level_pct: Fill level as a percentage (0.0–100.0).

        Returns:
            ``"LOW"`` if *level_pct* ≤ *low_pct*,
            ``"FULL"`` if *level_pct* ≥ *high_pct*,
            ``"MEDIUM"`` otherwise.
        """
        if level_pct <= self.config.low_pct:
            return "LOW"
        elif level_pct >= self.config.high_pct:
            return "FULL"
        else:
            return "MEDIUM"

    # ------------------------------------------------------------------ #
    # Pump hysteresis control
    # ------------------------------------------------------------------ #

    def update_pump_hysteresis(self, level_pct: float) -> bool:
        """Apply hysteresis logic to determine whether the refill pump runs.

        The pump turns **ON** when the level drops to or below *low_pct*
        and turns **OFF** only when the level rises to or above *high_pct*.
        Between the two thresholds the pump maintains its previous state,
        preventing rapid on/off cycling.

        Args:
            level_pct: Current fill level as a percentage (0.0–100.0).

        Returns:
            ``True`` if the pump should be ON, ``False`` otherwise.
        """
        if level_pct <= self.config.low_pct:
            self._pump_on = True
        elif level_pct >= self.config.high_pct:
            self._pump_on = False
        # Between thresholds: maintain current state (hysteresis)
        return self._pump_on

    # ------------------------------------------------------------------ #
    # Level history / trend analysis
    # ------------------------------------------------------------------ #

    def record_level(self, level_pct: float, timestamp: datetime = None) -> None:
        """Append a level reading to the internal rolling history.

        Args:
            level_pct: Fill level as a percentage (0.0–100.0).
            timestamp: Time of the reading.  Defaults to *now* if omitted.
        """
        if timestamp is None:
            timestamp = datetime.now()
        self._level_history.append((timestamp, level_pct))

    def estimate_hours_remaining(self, generator_on: bool) -> Optional[float]:
        """Estimate the number of hours until the tank is empty.

        Uses ordinary-least-squares linear regression on the readings from
        the last 120 seconds.  Only meaningful when the generator is running
        (fuel is being consumed) and the level is actively declining.

        Args:
            generator_on: Whether the generator is currently consuming fuel.

        Returns:
            Estimated hours remaining (clamped to 0–999), or ``None`` when
            the generator is off, data is insufficient, or the level is not
            falling.
        """
        if not generator_on or len(self._level_history) < 10:
            return None

        # Gather readings from the last 120 seconds
        now: datetime = self._level_history[-1][0]
        recent: List[Tuple[datetime, float]] = [
            (t, lvl)
            for t, lvl in self._level_history
            if (now - t).total_seconds() <= 120
        ]

        if len(recent) < 5:
            return None

        # Simple linear regression: level (%) vs elapsed time (seconds)
        t0 = recent[0][0]
        times: List[float] = [(t - t0).total_seconds() for t, _ in recent]
        levels: List[float] = [lvl for _, lvl in recent]

        n = len(times)
        sum_x = sum(times)
        sum_y = sum(levels)
        sum_xy = sum(x * y for x, y in zip(times, levels))
        sum_xx = sum(x * x for x in times)

        denom = n * sum_xx - sum_x * sum_x
        if abs(denom) < 1e-10:
            return None

        slope = (n * sum_xy - sum_x * sum_y) / denom  # %/second

        # If the level is not dropping (or dropping too slowly), bail out
        if slope >= -0.001:
            return None

        current_level = levels[-1]
        seconds_remaining = -current_level / slope  # time until 0 %
        hours = seconds_remaining / 3600.0
        return max(0.0, min(999.0, hours))  # clamp to a sane range

    # ------------------------------------------------------------------ #
    # Legacy theft detection (rule-based fallback)
    # ------------------------------------------------------------------ #

    def check_legacy_theft(self, generator_on: bool) -> bool:
        """Run the legacy rule-based theft check.

        Triggers when the generator is **off** and the level has dropped by
        more than *theft_drop_pct* within the last *theft_window_sec*
        seconds.  This is a simple fallback; a trained ML model is the
        preferred detection method.

        Args:
            generator_on: Whether the generator is currently consuming fuel.

        Returns:
            ``True`` if a theft-like drop was detected.
        """
        if generator_on or len(self._level_history) < 2:
            return False

        now_time, now_level = self._level_history[-1]
        for t, lvl in self._level_history:
            if (now_time - t).total_seconds() >= self.config.theft_window_sec:
                drop = lvl - now_level
                if drop >= self.config.theft_drop_pct:
                    return True
                break
        return False

    # ------------------------------------------------------------------ #
    # Full processing pipeline
    # ------------------------------------------------------------------ #

    def process_reading(
        self,
        distance_cm: float,
        generator_on: bool,
        timestamp: datetime = None,
    ) -> TankState:
        """Run the full processing pipeline for a single sensor reading.

        Steps:
            1. Convert distance → fill-level percentage.
            2. Convert level → volume in litres.
            3. Update pump hysteresis state.
            4. Classify status label.
            5. Record the level for trend analysis.
            6. Estimate hours remaining (if generator is on).
            7. Run legacy theft detection (if generator is off).

        Args:
            distance_cm:  Ultrasonic distance from sensor to liquid surface.
            generator_on: Whether the generator is currently running.
            timestamp:    Optional explicit timestamp; defaults to *now*.

        Returns:
            A :class:`TankState` snapshot capturing all computed values.
        """
        level_pct = self.distance_to_level_pct(distance_cm)
        volume = self.level_to_litres(level_pct)
        pump_on = self.update_pump_hysteresis(level_pct)
        status = self.get_status_label(level_pct)
        self.record_level(level_pct, timestamp)
        hours_left = self.estimate_hours_remaining(generator_on)
        theft = self.check_legacy_theft(generator_on)

        return TankState(
            level_pct=round(level_pct, 1),
            volume_litres=round(volume, 1),
            pump_on=pump_on,
            generator_on=generator_on,
            theft_alert=theft,
            theft_confidence=1.0 if theft else 0.0,
            hours_remaining=round(hours_left, 1) if hours_left is not None else None,
            status=status,
            timestamp=timestamp or datetime.now(),
        )

    # ------------------------------------------------------------------ #
    # Accessors / utilities
    # ------------------------------------------------------------------ #

    def get_level_history(self) -> List[Tuple[datetime, float]]:
        """Return the level history as a plain list of *(timestamp, level_pct)* tuples."""
        return list(self._level_history)

    def reset(self) -> None:
        """Reset all mutable internal state (pump flag and level history)."""
        self._pump_on = False
        self._level_history.clear()
