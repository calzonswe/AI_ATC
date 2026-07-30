from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional


class RunwaySurfaceCondition(Enum):
    DRY = "dry"
    WET = "wet"
    ICE = "ice"
    SNOW = "snow"


class OperationalMode(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    CLOSED = "closed"


@dataclass
class RunwayState:
    identifier: str
    heading: float
    length_ft: int
    surface: str = "concrete"
    active_for_departure: bool = False
    active_for_arrival: bool = False
    ils_frequency: Optional[float] = None
    surface_condition: RunwaySurfaceCondition = RunwaySurfaceCondition.DRY
    operational_mode: OperationalMode = OperationalMode.ACTIVE


@dataclass
class AirportState:
    icao: str
    elevation_ft: int = 0
    magnetic_var: float = 0.0
    runways: Dict[str, RunwayState] = field(default_factory=dict)
    active_runway_dep: Optional[str] = None
    active_runway_arr: Optional[str] = None
    flow_direction: str = "unknown"
    operational_mode: OperationalMode = OperationalMode.ACTIVE
