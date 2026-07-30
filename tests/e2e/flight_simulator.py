from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List


class FlightPhase(str, Enum):
    PARKED = "parked"
    STARTUP = "startup"
    PUSHBACK = "pushback"
    TAXI = "taxi"
    TAKEOFF = "takeoff"
    DEPARTURE_CLIMB = "departure_climb"
    ENROUTE_CRUISE = "enroute_cruise"
    APPROACH_DESCENT = "approach_descent"
    FINAL_ILS = "final_ils"
    LANDING = "landing"
    TAXI_TO_GATE = "taxi_to_gate"
    SHUTDOWN = "shutdown"


@dataclass
class Waypoint:
    lat: float
    lon: float
    alt_ft: float
    speed_kn: float


ESSA = Waypoint(lat=59.6494, lon=17.9231, alt_ft=137.0, speed_kn=0.0)
ESSB = Waypoint(lat=59.3544, lon=17.9417, alt_ft=46.0, speed_kn=0.0)

FLIGHT_PLAN = {
    FlightPhase.PARKED: Waypoint(59.6510, 17.9200, 137.0, 0.0),
    FlightPhase.STARTUP: Waypoint(59.6510, 17.9200, 137.0, 0.0),
    FlightPhase.PUSHBACK: Waypoint(59.6512, 17.9195, 137.0, 5.0),
    FlightPhase.TAXI: Waypoint(59.6494, 17.9210, 137.0, 20.0),
    FlightPhase.TAKEOFF: Waypoint(59.6500, 17.9250, 137.0, 160.0),
    FlightPhase.DEPARTURE_CLIMB: Waypoint(59.6300, 17.9400, 3000.0, 220.0),
    FlightPhase.ENROUTE_CRUISE: Waypoint(59.5000, 17.9500, 5000.0, 280.0),
    FlightPhase.APPROACH_DESCENT: Waypoint(59.4100, 17.9300, 2000.0, 200.0),
    FlightPhase.FINAL_ILS: Waypoint(59.3700, 17.9350, 500.0, 140.0),
    FlightPhase.LANDING: Waypoint(59.3544, 17.9417, 46.0, 120.0),
    FlightPhase.TAXI_TO_GATE: Waypoint(59.3550, 17.9440, 46.0, 15.0),
    FlightPhase.SHUTDOWN: Waypoint(59.3555, 17.9450, 46.0, 0.0),
}


class FlightTelemetryGenerator:
    def __init__(
        self,
        callsign: str = "SAS123",
        frames_per_phase: int = 3,
        inter_frame_delay_s: float = 0.01,
    ):
        self.callsign = callsign
        self.frames_per_phase = frames_per_phase
        self.inter_frame_delay_s = inter_frame_delay_s
        self._phase_index = 0
        self._phases = list(FlightPhase)
        self._sim_time = 0.0
        self._on_ground = True

    @property
    def current_phase(self) -> FlightPhase:
        return self._phases[self._phase_index]

    @property
    def is_complete(self) -> bool:
        return self._phase_index >= len(self._phases)

    @property
    def phase_progress(self) -> str:
        return f"{self._phase_index + 1}/{len(self._phases)}"

    def advance_phase(self) -> None:
        if self._phase_index < len(self._phases):
            self._phase_index += 1

    def generate_telemetry(self) -> List[Dict[str, Any]]:
        if self.is_complete:
            return []

        phase = self.current_phase
        wp = FLIGHT_PLAN[phase]
        frames = []

        if phase == FlightPhase.PARKED:
            self._on_ground = True
            frames.append(self._make_frame(wp, parked=True))
            self.advance_phase()
        elif phase == FlightPhase.STARTUP:
            self._on_ground = True
            frames.append(self._make_frame(wp))
            self.advance_phase()
        elif phase == FlightPhase.PUSHBACK:
            self._on_ground = True
            for i in range(self.frames_per_phase):
                t = (i + 1) / self.frames_per_phase
                frames.append(self._make_frame(
                    Waypoint(
                        lat=wp.lat + t * 0.0002,
                        lon=wp.lon - t * 0.0003,
                        alt_ft=wp.alt_ft,
                        speed_kn=wp.speed_kn + t * 3.0,
                    ),
                    on_ground=True,
                ))
            self.advance_phase()
        elif phase == FlightPhase.TAXI:
            self._on_ground = True
            for i in range(self.frames_per_phase):
                t = (i + 1) / self.frames_per_phase
                frames.append(self._make_frame(
                    Waypoint(
                        lat=wp.lat - t * 0.0015,
                        lon=wp.lon + t * 0.0010,
                        alt_ft=wp.alt_ft,
                        speed_kn=wp.speed_kn + t * 15.0,
                    ),
                    on_ground=True,
                ))
            self.advance_phase()
        elif phase == FlightPhase.TAKEOFF:
            self._on_ground = False
            for i in range(self.frames_per_phase):
                t = (i + 1) / self.frames_per_phase
                frames.append(self._make_frame(
                    Waypoint(
                        lat=wp.lat + t * 0.0020,
                        lon=wp.lon + t * 0.0030,
                        alt_ft=wp.alt_ft + t * 500.0,
                        speed_kn=wp.speed_kn + t * 80.0,
                    ),
                    on_ground=i < self.frames_per_phase - 1,
                ))
            self.advance_phase()
        elif phase == FlightPhase.DEPARTURE_CLIMB:
            self._on_ground = False
            for i in range(self.frames_per_phase):
                t = (i + 1) / self.frames_per_phase
                frames.append(self._make_frame(
                    Waypoint(
                        lat=wp.lat - t * 0.0200,
                        lon=wp.lon + t * 0.0050,
                        alt_ft=wp.alt_ft + t * 2000.0,
                        speed_kn=wp.speed_kn + t * 60.0,
                    ),
                    on_ground=False,
                ))
            self.advance_phase()
        elif phase == FlightPhase.ENROUTE_CRUISE:
            self._on_ground = False
            for i in range(self.frames_per_phase):
                t = (i + 1) / self.frames_per_phase
                frames.append(self._make_frame(
                    Waypoint(
                        lat=wp.lat - t * 0.1300,
                        lon=wp.lon + t * 0.0050,
                        alt_ft=wp.alt_ft,
                        speed_kn=wp.speed_kn + t * 10.0,
                    ),
                    on_ground=False,
                ))
            self.advance_phase()
        elif phase == FlightPhase.APPROACH_DESCENT:
            self._on_ground = False
            for i in range(self.frames_per_phase):
                t = (i + 1) / self.frames_per_phase
                frames.append(self._make_frame(
                    Waypoint(
                        lat=wp.lat - t * 0.0400,
                        lon=wp.lon + t * 0.0030,
                        alt_ft=wp.alt_ft - t * 1500.0,
                        speed_kn=wp.speed_kn - t * 60.0,
                    ),
                    on_ground=False,
                ))
            self.advance_phase()
        elif phase == FlightPhase.FINAL_ILS:
            self._on_ground = False
            for i in range(self.frames_per_phase):
                t = (i + 1) / self.frames_per_phase
                frames.append(self._make_frame(
                    Waypoint(
                        lat=wp.lat - t * 0.0150,
                        lon=wp.lon + t * 0.0040,
                        alt_ft=wp.alt_ft - t * 400.0,
                        speed_kn=wp.speed_kn - t * 20.0,
                    ),
                    on_ground=False,
                ))
            self.advance_phase()
        elif phase == FlightPhase.LANDING:
            self._on_ground = True
            for i in range(self.frames_per_phase):
                t = (i + 1) / self.frames_per_phase
                frames.append(self._make_frame(
                    Waypoint(
                        lat=wp.lat + t * 0.0005,
                        lon=wp.lon + t * 0.0010,
                        alt_ft=wp.alt_ft,
                        speed_kn=wp.speed_kn - t * 100.0,
                    ),
                    on_ground=True,
                ))
            self.advance_phase()
        elif phase == FlightPhase.TAXI_TO_GATE:
            self._on_ground = True
            for i in range(self.frames_per_phase):
                t = (i + 1) / self.frames_per_phase
                frames.append(self._make_frame(
                    Waypoint(
                        lat=wp.lat + t * 0.0003,
                        lon=wp.lon + t * 0.0010,
                        alt_ft=wp.alt_ft,
                        speed_kn=wp.speed_kn - t * 10.0,
                    ),
                    on_ground=True,
                ))
            self.advance_phase()
        elif phase == FlightPhase.SHUTDOWN:
            self._on_ground = True
            frames.append(self._make_frame(wp, parked=True))
            self.advance_phase()

        self._sim_time += 1.0
        return frames

    def _make_frame(
        self,
        wp: Waypoint,
        on_ground: bool | None = None,
        parked: bool = False,
    ) -> Dict[str, Any]:
        og = on_ground if on_ground is not None else self._on_ground
        ias = wp.speed_kn if not parked else 0.0
        gs = ias * (0.95 if og else 1.02)
        vs = 0.0 if og else 800.0
        heading = self._bearing(ESSA.lat, ESSA.lon, wp.lat, wp.lon)
        alt_agl = 0.0 if og else wp.alt_ft

        return {
            "event": "telemetry_update",
            "callsign": self.callsign,
            "position": {
                "lat": round(wp.lat, 6),
                "lon": round(wp.lon, 6),
                "alt_msl": round(wp.alt_ft, 1),
                "alt_agl": round(alt_agl, 1),
                "heading": round(heading, 1),
                "pitch": 0.0,
                "bank": 0.0,
            },
            "motion": {
                "ias": round(ias, 1),
                "groundspeed": round(gs, 1),
                "vertical_speed": round(vs, 1),
                "on_ground": og,
            },
            "radios": {
                "com1": 118.300,
                "com2": 121.800,
                "squawk": "2000",
                "squawk_mode": "alt",
            },
            "sim_time": round(self._sim_time, 1),
            "ts": int(time.time() * 1000),
        }

    @staticmethod
    def _bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        import math
        dlon = math.radians(lon2 - lon1)
        y = math.sin(dlon) * math.cos(math.radians(lat2))
        x = (math.cos(math.radians(lat1)) * math.sin(math.radians(lat2))
             - math.sin(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.cos(dlon))
        return (math.degrees(math.atan2(y, x)) + 360) % 360


class PilotVoiceSimulator:
    """Generates simulated pilot radio calls for each flight phase."""

    PHASE_CALLS = {
        FlightPhase.STARTUP: [
            {"type": "radio_transmit", "frequency": 121.800,
             "text": "ESSA Ground, SAS123, request startup at gate B4, info A."},
        ],
        FlightPhase.PUSHBACK: [
            {"type": "radio_transmit", "frequency": 121.800,
             "text": "ESSA Ground, SAS123, request pushback, facing south."},
        ],
        FlightPhase.TAXI: [
            {"type": "radio_transmit", "frequency": 121.800,
             "text": "ESSA Ground, SAS123, request taxi, IFR to ESSB."},
        ],
        FlightPhase.TAKEOFF: [
            {"type": "radio_transmit", "frequency": 118.500,
             "text": "ESSA Tower, SAS123, holding short runway 01L, ready for departure."},
        ],
        FlightPhase.DEPARTURE_CLIMB: [
            {"type": "radio_transmit", "frequency": 119.200,
             "text": "ESSA Departure, SAS123, passing 2000 feet, climbing to 5000."},
        ],
        FlightPhase.APPROACH_DESCENT: [
            {"type": "radio_transmit", "frequency": 124.300,
             "text": "ESSA Approach, SAS123, descending to 2000 feet, inbound for ESSB."},
        ],
        FlightPhase.FINAL_ILS: [
            {"type": "radio_transmit", "frequency": 124.300,
             "text": "ESSA Approach, SAS123, established ILS runway 12, ESSB."},
        ],
        FlightPhase.LANDING: [
            {"type": "radio_transmit", "frequency": 118.500,
             "text": "ESSB Tower, SAS123, runway 12, landing ESSB."},
        ],
        FlightPhase.TAXI_TO_GATE: [
            {"type": "radio_transmit", "frequency": 121.800,
             "text": "ESSB Ground, SAS123, clear of runway 12, request taxi to gate."},
        ],
    }

    def get_calls_for_phase(self, phase: FlightPhase) -> list:
        return self.PHASE_CALLS.get(phase, [])
