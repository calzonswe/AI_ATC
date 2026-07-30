import math
import random
import time
from datetime import datetime, timezone

from .models import (
    TelemetryFrame,
    PositionData,
    MotionData,
    RadioData,
    SimConnectState,
)
from .client import SimConnectClientBase

_DEFAULT_CALLSIGN = "SAS123"


class MockSimConnectClient(SimConnectClientBase):
    """SimConnect client that generates synthetic telemetry.

    Useful for development and testing on machines without MSFS.
    Simulates a simple flight path: takeoff, climb, cruise, approach.
    """

    def __init__(self, callsign: str = _DEFAULT_CALLSIGN):
        self._state = SimConnectState.DISCONNECTED
        self._callsign = callsign
        self._start_time = 0.0
        self._lat = 59.6494
        self._lon = 17.9231
        self._alt_msl = 0.0
        self._heading = 180.0
        self._ias = 0.0
        self._groundspeed = 0.0
        self._vertical_speed = 0.0
        self._on_ground = True
        self._pitch = 0.0
        self._bank = 0.0
        self._frame_count = 0

    async def connect(self) -> None:
        self._state = SimConnectState.CONNECTING
        await _async_sleep(0.1)
        self._state = SimConnectState.CONNECTED
        self._start_time = time.time()

    async def disconnect(self) -> None:
        self._state = SimConnectState.DISCONNECTED

    async def read_frame(self) -> TelemetryFrame:
        if self._state != SimConnectState.CONNECTED:
            return None

        elapsed = time.time() - self._start_time
        self._frame_count += 1

        self._simulate_flight_profile(elapsed)

        return TelemetryFrame(
            callsign=self._callsign,
            position=PositionData(
                lat=self._lat,
                lon=self._lon,
                alt_msl_ft=self._alt_msl,
                alt_agl_ft=self._alt_msl if not self._on_ground else 0.0,
                heading_true=self._heading,
                heading_mag=self._heading - 5.5,
                pitch_deg=self._pitch,
                bank_deg=self._bank,
            ),
            motion=MotionData(
                ias_kn=self._ias,
                groundspeed_kn=self._groundspeed,
                vertical_speed_fpm=self._vertical_speed,
                on_ground=self._on_ground,
            ),
            radios=RadioData(
                com1_freq_mhz=118.300,
                com2_freq_mhz=121.800,
                transponder_code="2000",
                transponder_mode="alt",
            ),
            sim_time_s=elapsed,
            recorded_at=time.time(),
        )

    @property
    def state(self) -> SimConnectState:
        return self._state

    @property
    def callsign(self) -> str:
        return self._callsign

    def _simulate_flight_profile(self, elapsed_s: float):
        """Advance the simulated aircraft state through a simple profile."""
        phase_1 = 15.0   # taxi
        phase_2 = 30.0   # takeoff roll
        phase_3 = 120.0  # climb
        phase_4 = 300.0  # cruise

        if elapsed_s < phase_1:
            self._on_ground = True
            self._ias = 15 + (elapsed_s / phase_1) * 10
            self._groundspeed = self._ias * 0.9
            self._alt_msl = 137.0
            self._vertical_speed = 0
            self._pitch = 0.0
            self._lon += 0.00002

        elif elapsed_s < phase_2:
            self._on_ground = True
            t = (elapsed_s - phase_1) / (phase_2 - phase_1)
            self._ias = 25 + t * 130
            self._groundspeed = self._ias * 0.95
            self._alt_msl = 137.0
            self._vertical_speed = 0
            self._pitch = math.radians(2)
            self._lon += 0.00005

        elif elapsed_s < phase_3:
            self._on_ground = False
            t = (elapsed_s - phase_2) / (phase_3 - phase_2)
            self._ias = 155 + t * 85
            self._groundspeed = self._ias * 1.02
            self._alt_msl = 137 + t * 3000
            self._vertical_speed = 1800
            self._pitch = math.radians(8)
            self._heading += 0.02
            self._lon += 0.0005
            self._lat += 0.0003

        else:
            self._on_ground = False
            t = min((elapsed_s - phase_3) / (phase_4 - phase_3), 1.0)
            self._ias = 240 + t * 60
            self._groundspeed = self._ias * 1.03
            self._alt_msl = 3137 + t * 20000
            self._vertical_speed = 200
            self._pitch = math.radians(3)
            self._heading += 0.01
            self._lon += 0.0008
            self._lat += 0.0005

        self._bank = math.sin(elapsed_s * 0.1) * 5


async def _async_sleep(seconds: float):
    import asyncio
    await asyncio.sleep(seconds)
