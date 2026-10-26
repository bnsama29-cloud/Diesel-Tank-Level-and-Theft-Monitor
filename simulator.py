"""
Simulator — Test Scenario Generator for Diesel Tank Monitor
============================================================

Generates realistic sensor data streams for the three required demo test cases.
Each scenario returns timestamped (datetime, distance_cm, generator_on) tuples
at ~1 Hz, with configurable speed multipliers for fast-forwarding demos.

Scenarios
---------
1. **Hysteresis** — Full→Empty→Full cycle; pump toggles ON at 20%, OFF at 90%.
2. **Theft**      — Generator OFF, sudden unexplained drop in level.
3. **Consumption**— Generator ON, slow steady drain with hours-remaining info.

Usage
-----
    from simulator import TankSimulator, Scenario

    sim = TankSimulator(tank_depth_cm=100.0)
    readings = sim.generate_scenario(Scenario.HYSTERESIS, speed_multiplier=2.0)
    for r in readings:
        print(r)
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Generator, List


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class Scenario(Enum):
    """Predefined demo scenarios for the diesel tank monitor."""

    HYSTERESIS = "hysteresis"       # Full→Empty→Full, pump toggles
    THEFT = "theft"                 # Generator OFF, sudden drop
    CONSUMPTION = "consumption"     # Generator ON, slow steady drain


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class SimReading:
    """A single simulated sensor reading from the ultrasonic distance sensor.

    Attributes
    ----------
    timestamp : datetime
        The wall-clock time of the reading.
    distance_cm : float
        Ultrasonic sensor distance in cm (0 = tank full, ``tank_depth`` = tank empty).
    generator_on : bool
        Whether the diesel generator is currently running.
    scenario_name : str
        Human-readable label of the active scenario.
    description : str
        Optional annotation describing what is happening at this instant.
    """

    timestamp: datetime
    distance_cm: float
    generator_on: bool
    scenario_name: str
    description: str = ""


# ---------------------------------------------------------------------------
# Core simulator
# ---------------------------------------------------------------------------

class TankSimulator:
    """Generates realistic sensor data streams for demo test cases.

    Parameters
    ----------
    tank_depth_cm : float
        Physical depth of the tank in centimetres.  The ultrasonic sensor is
        mounted at the top, so ``distance_cm == 0`` means the tank is
        completely full and ``distance_cm == tank_depth_cm`` means it is empty.
    """

    def __init__(self, tank_depth_cm: float = 100.0) -> None:
        self.tank_depth_cm: float = tank_depth_cm
        self._running: bool = False

    # -- helpers ------------------------------------------------------------

    def level_to_distance(self, level_pct: float) -> float:
        """Convert a fuel-level percentage to an ultrasonic distance reading.

        The sensor reads from the top of the tank, so a *higher* level
        percentage corresponds to a *shorter* distance.

        Parameters
        ----------
        level_pct : float
            Current fuel level as a percentage (0–100).

        Returns
        -------
        float
            Distance in cm that the ultrasonic sensor would report.
        """
        return self.tank_depth_cm * (1.0 - level_pct / 100.0)

    # -- public interface ---------------------------------------------------

    def generate_scenario(
        self,
        scenario: Scenario,
        speed_multiplier: float = 1.0,
    ) -> List[SimReading]:
        """Generate a complete scenario data set.

        Parameters
        ----------
        scenario : Scenario
            Which demo scenario to generate.
        speed_multiplier : float
            Values > 1 compress the time axis so the scenario runs faster,
            which is handy for live demos.

        Returns
        -------
        list[SimReading]
            Chronologically ordered list of simulated sensor readings.
        """
        if scenario == Scenario.HYSTERESIS:
            return self._gen_hysteresis(speed_multiplier)
        elif scenario == Scenario.THEFT:
            return self._gen_theft(speed_multiplier)
        elif scenario == Scenario.CONSUMPTION:
            return self._gen_consumption(speed_multiplier)
        else:
            raise ValueError(f"Unknown scenario: {scenario!r}")

    def stream_scenario(
        self,
        scenario: Scenario,
        speed_multiplier: float = 1.0,
    ) -> Generator[SimReading, None, None]:
        """Yield readings one at a time with real-time delays.

        This generator is useful for live-streaming a simulation to a
        dashboard or serial interface.  Call :meth:`stop` from another
        thread to abort early.

        Parameters
        ----------
        scenario : Scenario
            Which demo scenario to stream.
        speed_multiplier : float
            Time-compression factor (>1 = faster).

        Yields
        ------
        SimReading
            One reading per simulated time-step.
        """
        readings = self.generate_scenario(scenario, speed_multiplier)
        self._running = True
        prev_time: datetime | None = None

        for reading in readings:
            if not self._running:
                break
            # Respect inter-reading timing for realistic playback
            if prev_time is not None:
                delay = (reading.timestamp - prev_time).total_seconds()
                time.sleep(max(0.0, delay))
            prev_time = reading.timestamp
            yield reading

        self._running = False

    def stop(self) -> None:
        """Stop a running :meth:`stream_scenario` generator."""
        self._running = False

    # -- private scenario generators ----------------------------------------

    def _gen_hysteresis(self, speed: float) -> List[SimReading]:
        """Scenario 1 — Hysteresis / pump-toggle demo.

        Starts at 95 % (full), drains to 15 % (below the 20 % LOW
        threshold), then refills back to 95 % (above the 90 % HIGH
        threshold).  The pump turns ON at 20 % and OFF at 90 %.

        Total ≈ 180 simulated seconds at ``speed == 1``.
        """
        readings: List[SimReading] = []
        base_time = datetime.now()
        dt: float = 1.0 / speed  # seconds between readings
        level: float = 95.0      # start full
        t: float = 0.0

        # Phase 1: Drain from 95 % → 15 % (dropping ~1 %/step)
        while level > 15.0:
            noise = random.gauss(0, 0.2)
            dist = self.level_to_distance(level + noise)

            desc = "Draining"
            if level <= 20.0:
                desc = "⚡ PUMP ON — level below 20%"

            readings.append(SimReading(
                timestamp=base_time + timedelta(seconds=t),
                distance_cm=max(0.0, min(self.tank_depth_cm, dist)),
                generator_on=False,
                scenario_name="Hysteresis Demo",
                description=desc,
            ))

            level -= 1.0 * speed
            t += dt

        # Phase 2: Refill from 15 % → 95 % (pump is ON, filling ~1 %/step)
        while level < 95.0:
            noise = random.gauss(0, 0.2)
            dist = self.level_to_distance(level + noise)

            desc = "Refilling (pump ON)"
            if level >= 90.0:
                desc = "⚡ PUMP OFF — level above 90%"

            readings.append(SimReading(
                timestamp=base_time + timedelta(seconds=t),
                distance_cm=max(0.0, min(self.tank_depth_cm, dist)),
                generator_on=False,
                scenario_name="Hysteresis Demo",
                description=desc,
            ))

            level += 1.0 * speed
            t += dt

        return readings

    def _gen_theft(self, speed: float) -> List[SimReading]:
        """Scenario 2 — Fuel-theft detection demo.

        Generator is OFF.  Level is stable at 70 % for 30 s, then drops
        sharply by 20 % over 20 s (simulating siphoning), then stabilises
        at ~50 %.

        Total ≈ 90 simulated seconds at ``speed == 1``.
        """
        readings: List[SimReading] = []
        base_time = datetime.now()
        dt: float = 1.0 / speed
        t: float = 0.0

        # Phase 1: Stable at 70 % for 30 seconds
        for _ in range(30):
            noise = random.gauss(0, 0.15)
            level = 70.0 + noise
            readings.append(SimReading(
                timestamp=base_time + timedelta(seconds=t),
                distance_cm=self.level_to_distance(level),
                generator_on=False,
                scenario_name="Theft Demo",
                description="Stable — generator OFF",
            ))
            t += dt

        # Phase 2: Sudden theft — drop 20 % over 20 seconds
        for i in range(20):
            drop = (i + 1) * (20.0 / 20)  # linear 1 % per step
            level = 70.0 - drop + random.gauss(0, 0.3)
            readings.append(SimReading(
                timestamp=base_time + timedelta(seconds=t),
                distance_cm=self.level_to_distance(level),
                generator_on=False,
                scenario_name="Theft Demo",
                description="🚨 THEFT IN PROGRESS — rapid level drop!",
            ))
            t += dt

        # Phase 3: Stable at ~50 % for 40 seconds (theft complete)
        for _ in range(40):
            noise = random.gauss(0, 0.15)
            level = 50.0 + noise
            readings.append(SimReading(
                timestamp=base_time + timedelta(seconds=t),
                distance_cm=self.level_to_distance(level),
                generator_on=False,
                scenario_name="Theft Demo",
                description="Post-theft — level stabilized",
            ))
            t += dt

        return readings

    def _gen_consumption(self, speed: float) -> List[SimReading]:
        """Scenario 3 — Normal consumption / hours-remaining demo.

        Generator is ON, level drains slowly from 80 % at 0.5 %/step over
        ~120 simulated seconds.  The dashboard should compute and display
        estimated hours remaining.

        Total ≈ 120 simulated seconds at ``speed == 1``.
        """
        readings: List[SimReading] = []
        base_time = datetime.now()
        dt: float = 1.0 / speed
        level: float = 80.0
        t: float = 0.0

        for _ in range(120):
            noise = random.gauss(0, 0.1)
            dist = self.level_to_distance(level + noise)

            # Rough estimate of simulated hours remaining at current drain rate
            hours_remaining = (level / 0.5) / 3600 * dt  # informational only

            readings.append(SimReading(
                timestamp=base_time + timedelta(seconds=t),
                distance_cm=max(0.0, min(self.tank_depth_cm, dist)),
                generator_on=True,
                scenario_name="Consumption Demo",
                description="Generator running — steady consumption",
            ))

            level -= 0.5 * speed  # ~0.5 %/s simulated drain
            level = max(0.0, level)
            t += dt

        return readings


# ---------------------------------------------------------------------------
# CLI demo entry-point
# ---------------------------------------------------------------------------

def _print_banner(title: str) -> None:
    """Print a formatted section banner to the console."""
    width = 72
    print()
    print("=" * width)
    print(f"  {title}")
    print("=" * width)


def main() -> None:
    """Run all three demo scenarios and print sample output."""
    import sys
    import io

    # Ensure stdout can handle Unicode emoji on Windows consoles
    if sys.stdout.encoding and sys.stdout.encoding.lower().startswith("cp"):
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer, encoding="utf-8", errors="replace"
        )

    sim = TankSimulator(tank_depth_cm=100.0)

    for scenario in Scenario:
        readings = sim.generate_scenario(scenario, speed_multiplier=2.0)
        _print_banner(f"Scenario: {scenario.value.upper()}  ({len(readings)} readings)")

        # Print every 10th reading to keep console output manageable
        for idx, r in enumerate(readings):
            if idx % 10 == 0 or idx == len(readings) - 1:
                level_pct = 100.0 - (r.distance_cm / sim.tank_depth_cm * 100.0)
                gen_status = "ON " if r.generator_on else "OFF"
                print(
                    f"  [{r.timestamp.strftime('%H:%M:%S')}]  "
                    f"dist={r.distance_cm:6.1f} cm  "
                    f"level={level_pct:5.1f}%  "
                    f"gen={gen_status}  "
                    f"| {r.description}"
                )

    print()
    print("All scenarios generated successfully.")


if __name__ == "__main__":
    main()
