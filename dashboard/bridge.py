"""
Wokwi Data Bridge — WebSocket/MQTT Data Ingestion for Diesel Tank Monitor
==========================================================================

Provides a thread-safe :class:`DataBridge` that connects to an ESP32's
WebSocket stream (via Wokwi) or an MQTT broker to receive real-time sensor
data.  When no external connection is available the bridge can also accept
manually-pushed simulated readings, making it a drop-in data source for
the dashboard regardless of the back-end.

Key features
------------
* **Thread-safe ring buffer** backed by :class:`collections.deque` — safe
  to read from the GUI thread while the listener thread writes.
* **WebSocket listener** (requires the ``websockets`` package) that
  connects to the Wokwi virtual-serial gateway.
* **MQTT listener** (requires ``paho-mqtt``) for broker-based setups.
* **Callback system** — register any number of ``on_reading`` callbacks
  that fire every time a new :class:`SensorReading` arrives.
* **Simulated push** — the internal simulator can call
  :meth:`DataBridge.push_simulated` to inject synthetic readings without
  any network dependency.

Typical usage
-------------
>>> bridge = DataBridge()
>>> bridge.push_simulated(distance_cm=12.5, generator_on=True)
>>> latest = bridge.get_latest()
>>> print(latest.distance_cm)
12.5
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, List, Optional


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class SensorReading:
    """A single snapshot of the diesel-tank sensor state.

    Attributes
    ----------
    timestamp : datetime
        Wall-clock time when the reading was captured / received.
    distance_cm : float
        Ultrasonic sensor distance in centimetres (lower → more fuel).
    generator_on : bool
        Whether the generator is currently running.
    pump_on : bool
        Whether the fuel pump relay is currently energised (from ESP32).
    source : str
        Origin of the reading — one of ``"wokwi"``, ``"mqtt"``, or
        ``"simulator"``.
    """

    timestamp: datetime
    distance_cm: float
    generator_on: bool
    pump_on: bool
    source: str  # "wokwi", "mqtt", "simulator"


# ---------------------------------------------------------------------------
# Data bridge
# ---------------------------------------------------------------------------

class DataBridge:
    """Thread-safe data bridge that manages connections and buffers readings.

    The bridge maintains an internal ring buffer of :class:`SensorReading`
    objects and exposes both *push* (write) and *pull* (read) interfaces so
    that producer threads (WebSocket / MQTT listeners, simulator) and
    consumer threads (dashboard GUI) can operate concurrently without
    explicit synchronisation on the caller's side.

    Parameters
    ----------
    buffer_size : int
        Maximum number of readings to keep in the ring buffer.  Older
        readings are silently discarded when the buffer is full.
    ws_url : str
        WebSocket URL of the Wokwi serial gateway.
    mqtt_host : str
        Hostname or IP address of the MQTT broker.
    mqtt_port : int
        TCP port of the MQTT broker.
    mqtt_topic : str
        MQTT topic to subscribe to for sensor payloads.
    """

    def __init__(
        self,
        buffer_size: int = 600,
        ws_url: str = "ws://localhost:4000",
        mqtt_host: str = "localhost",
        mqtt_port: int = 1883,
        mqtt_topic: str = "diesel/sensor",
    ) -> None:
        # Ring buffer & synchronisation
        self._buffer: deque[SensorReading] = deque(maxlen=buffer_size)
        self._lock: threading.Lock = threading.Lock()

        # WebSocket configuration
        self._ws_url: str = ws_url

        # MQTT configuration
        self._mqtt_host: str = mqtt_host
        self._mqtt_port: int = mqtt_port
        self._mqtt_topic: str = mqtt_topic

        # Runtime state
        self._running: bool = False
        self._thread: Optional[threading.Thread] = None
        self._source: str = "disconnected"
        self._callbacks: List[Callable[[SensorReading], None]] = []
        self._last_error: Optional[str] = None

    # ------------------------------------------------------------------
    # Buffer operations (thread-safe)
    # ------------------------------------------------------------------

    def add_reading(self, reading: SensorReading) -> None:
        """Thread-safe: append *reading* to the ring buffer and notify
        all registered callbacks.

        Parameters
        ----------
        reading : SensorReading
            The new sensor reading to store.
        """
        with self._lock:
            self._buffer.append(reading)

        # Fire callbacks outside the lock to avoid potential deadlocks
        # if a callback tries to read from the buffer.
        for cb in self._callbacks:
            try:
                cb(reading)
            except Exception:
                # Never let a misbehaving callback crash the producer.
                pass

    def get_readings(self, n: Optional[int] = None) -> List[SensorReading]:
        """Thread-safe: return the last *n* readings (or all if *n* is
        ``None``).

        Parameters
        ----------
        n : int or None
            Number of most-recent readings to return.  ``None`` returns
            the entire buffer contents.

        Returns
        -------
        list[SensorReading]
            A **copy** of the requested readings (safe to mutate).
        """
        with self._lock:
            if n is None:
                return list(self._buffer)
            return list(self._buffer)[-n:]

    def get_latest(self) -> Optional[SensorReading]:
        """Thread-safe: return the most recent reading, or ``None`` if
        the buffer is empty.
        """
        with self._lock:
            return self._buffer[-1] if self._buffer else None

    def clear(self) -> None:
        """Thread-safe: discard all buffered readings."""
        with self._lock:
            self._buffer.clear()

    # ------------------------------------------------------------------
    # Callback registration
    # ------------------------------------------------------------------

    def on_reading(self, callback: Callable[[SensorReading], None]) -> None:
        """Register a *callback* that is invoked every time a new reading
        is added.

        Parameters
        ----------
        callback : callable
            A function accepting a single :class:`SensorReading` argument.
        """
        self._callbacks.append(callback)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def source(self) -> str:
        """Current data source identifier (``"wokwi"``, ``"mqtt"``,
        ``"simulator"``, or ``"disconnected"``)."""
        return self._source

    @property
    def is_connected(self) -> bool:
        """``True`` while a background listener thread is running."""
        return self._running

    @property
    def buffer_size(self) -> int:
        """Number of readings currently stored in the buffer."""
        with self._lock:
            return len(self._buffer)

    @property
    def last_error(self) -> Optional[str]:
        """Human-readable description of the last connection error, or
        ``None`` if no error has occurred."""
        return self._last_error

    # ------------------------------------------------------------------
    # WebSocket listener
    # ------------------------------------------------------------------

    def start_websocket(self) -> None:
        """Start a WebSocket listener in a background daemon thread.

        The listener connects to :attr:`_ws_url` and continuously
        deserialises incoming JSON frames into :class:`SensorReading`
        objects that are pushed into the ring buffer.

        Requires the ``websockets`` package.
        """
        self._source = "wokwi"
        self._running = True
        self._thread = threading.Thread(
            target=self._ws_loop, daemon=True, name="DataBridge-WS"
        )
        self._thread.start()

    def _ws_loop(self) -> None:
        """Internal: WebSocket receive loop (runs in its own thread)."""
        try:
            import websockets  # noqa: F811 — late import to keep dependency optional

            async def listen() -> None:
                try:
                    async with websockets.connect(self._ws_url) as ws:
                        self._last_error = None
                        while self._running:
                            try:
                                msg = await asyncio.wait_for(
                                    ws.recv(), timeout=5.0
                                )
                                data = json.loads(msg)
                                reading = SensorReading(
                                    timestamp=datetime.now(),
                                    distance_cm=float(
                                        data.get("distance_cm", 0)
                                    ),
                                    generator_on=bool(
                                        data.get("generator_on", False)
                                    ),
                                    pump_on=bool(data.get("pump_on", False)),
                                    source="wokwi",
                                )
                                self.add_reading(reading)
                            except asyncio.TimeoutError:
                                # No message within the timeout — just retry.
                                continue
                except Exception as exc:
                    self._last_error = f"WebSocket error: {exc}"
                    self._running = False

            asyncio.run(listen())

        except ImportError:
            self._last_error = "websockets package not installed"
            self._running = False
        except Exception as exc:
            self._last_error = str(exc)
            self._running = False

    # ------------------------------------------------------------------
    # MQTT listener
    # ------------------------------------------------------------------

    def start_mqtt(self) -> None:
        """Start an MQTT listener in a background daemon thread.

        The listener subscribes to :attr:`_mqtt_topic` on the broker at
        :attr:`_mqtt_host`::attr:`_mqtt_port` and deserialises incoming
        JSON payloads into :class:`SensorReading` objects.

        Requires the ``paho-mqtt`` package.
        """
        self._source = "mqtt"
        self._running = True
        self._thread = threading.Thread(
            target=self._mqtt_loop, daemon=True, name="DataBridge-MQTT"
        )
        self._thread.start()

    def _mqtt_loop(self) -> None:
        """Internal: MQTT subscribe-and-loop (runs in its own thread)."""
        try:
            import paho.mqtt.client as mqtt_client  # late import

            def on_message(
                client: mqtt_client.Client,
                userdata: object,
                msg: mqtt_client.MQTTMessage,
            ) -> None:
                """Handle an incoming MQTT message."""
                try:
                    data = json.loads(msg.payload.decode())
                    reading = SensorReading(
                        timestamp=datetime.now(),
                        distance_cm=float(data.get("distance_cm", 0)),
                        generator_on=bool(data.get("generator_on", False)),
                        pump_on=bool(data.get("pump_on", False)),
                        source="mqtt",
                    )
                    self.add_reading(reading)
                except Exception:
                    # Malformed payload — silently skip.
                    pass

            client = mqtt_client.Client()
            client.on_message = on_message
            try:
                client.connect(self._mqtt_host, self._mqtt_port)
                client.subscribe(self._mqtt_topic)
                self._last_error = None
                while self._running:
                    client.loop(timeout=1.0)
            except Exception as exc:
                self._last_error = f"MQTT error: {exc}"
                self._running = False

        except ImportError:
            self._last_error = "paho-mqtt package not installed"
            self._running = False

    # ------------------------------------------------------------------
    # Simulated / manual push
    # ------------------------------------------------------------------

    def push_simulated(
        self,
        distance_cm: float,
        generator_on: bool,
        pump_on: bool = False,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Manually push a simulated reading into the buffer.

        This is the primary integration point for the internal simulator:
        it allows synthetic data to flow through the same pipeline as
        real hardware data.

        Parameters
        ----------
        distance_cm : float
            Simulated ultrasonic distance in centimetres.
        generator_on : bool
            Simulated generator state.
        pump_on : bool
            Simulated pump-relay state.
        timestamp : datetime or None
            Override timestamp; defaults to :func:`datetime.now`.
        """
        reading = SensorReading(
            timestamp=timestamp or datetime.now(),
            distance_cm=distance_cm,
            generator_on=generator_on,
            pump_on=pump_on,
            source="simulator",
        )
        self._source = "simulator"
        self.add_reading(reading)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def stop(self) -> None:
        """Signal the background listener to stop and wait for it to
        join (up to 3 seconds)."""
        self._running = False
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=3.0)


# ======================================================================
# Demo / self-test
# ======================================================================

if __name__ == "__main__":
    print("=== DataBridge Demo ===\n")

    # Create a bridge with a small buffer for demonstration purposes.
    bridge = DataBridge(buffer_size=10)

    # Register a callback that prints every new reading.
    bridge.on_reading(
        lambda r: print(f"  [callback] {r.source}: {r.distance_cm:.1f} cm")
    )

    # Push a handful of simulated readings.
    distances = [25.0, 24.3, 23.7, 22.1, 21.5, 20.8, 19.2, 18.6, 17.0, 16.4]
    for i, dist in enumerate(distances):
        gen_on = i >= 3  # generator kicks in after a few readings
        bridge.push_simulated(distance_cm=dist, generator_on=gen_on)
        time.sleep(0.05)  # tiny delay to vary timestamps

    # Query the buffer.
    print(f"\nSource       : {bridge.source}")
    print(f"Buffer count : {bridge.buffer_size}")
    print(f"Connected    : {bridge.is_connected}")
    print(f"Last error   : {bridge.last_error}")

    latest = bridge.get_latest()
    if latest is not None:
        print(
            f"\nLatest reading: {latest.distance_cm:.1f} cm "
            f"@ {latest.timestamp:%H:%M:%S}  "
            f"(gen={'ON' if latest.generator_on else 'OFF'})"
        )

    last_five = bridge.get_readings(n=5)
    print(f"\nLast 5 readings:")
    for r in last_five:
        print(
            f"  {r.timestamp:%H:%M:%S.%f}  dist={r.distance_cm:5.1f} cm  "
            f"gen={'ON' if r.generator_on else 'OFF'}  "
            f"pump={'ON' if r.pump_on else 'OFF'}"
        )

    # Clean up.
    bridge.stop()
    print("\nDone.")
