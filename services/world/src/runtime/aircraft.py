from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class FlightRules(Enum):
    VFR = "VFR"
    IFR = "IFR"


class AircraftState(Enum):
    PARKED = "parked"
    PUSHBACK = "pushback"
    TAXI = "taxi"
    QUEUED = "queued"
    LINE_UP = "line_up"
    TAKEOFF = "takeoff"
    CLIMB = "climb"
    CRUISE = "cruise"
    DESCENT = "descent"
    APPROACH = "approach"
    LANDING = "landing"
    ROLLOUT = "rollout"
    GO_AROUND = "go_around"


@dataclass
class PositionData:
    lat: float = 0.0
    lon: float = 0.0
    alt_msl_ft: float = 0.0
    alt_agl_ft: float = 0.0
    heading_true: float = 0.0
    heading_mag: float = 0.0
    pitch_deg: float = 0.0
    bank_deg: float = 0.0


@dataclass
class MotionData:
    ias_kn: float = 0.0
    groundspeed_kn: float = 0.0
    vertical_speed_fpm: float = 0.0
    mach: float = 0.0
    on_ground: bool = True


@dataclass
class TrajectoryPoint:
    lat: float
    lon: float
    alt_msl_ft: float
    timestamp_s: float


@dataclass
class FlightPlan:
    departure: str = ""
    arrival: str = ""
    alternate: Optional[str] = None
    route: List[str] = field(default_factory=list)
    cruise_alt_ft: int = 35000
    cruise_speed_kn: float = 450.0
    flight_rules: FlightRules = FlightRules.IFR
    aircraft_type: str = "B738"


@dataclass
class ActiveAircraft:
    callsign: str
    position: PositionData = field(default_factory=PositionData)
    motion: MotionData = field(default_factory=MotionData)
    state: AircraftState = AircraftState.PARKED
    previous_state: Optional[AircraftState] = None
    flight_plan: Optional[FlightPlan] = None
    trajectory: List[TrajectoryPoint] = field(default_factory=list)
    current_sector_id: Optional[int] = None
    current_airport_icao: Optional[str] = None
    squawk_code: str = "1200"
    last_update_s: float = 0.0
