from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ControllerPosition(Enum):
    GROUND = "ground"
    TOWER = "tower"
    DEPARTURE = "departure"
    APPROACH = "approach"
    CENTER = "center"
    ATIS = "atis"
    DELIVERY = "delivery"


class ControllerState(Enum):
    IDLE = "idle"
    ACTIVE = "active"
    HANDOFF = "handoff"


class GroundState(Enum):
    IDLE = "idle"
    STARTUP = "startup"
    PUSHBACK_IN_PROGRESS = "pushback_in_progress"
    TAXI_CLEARED = "taxi_cleared"
    HOLDING_SHORT = "holding_short"
    CROSSING_RUNWAY = "crossing_runway"
    ARRIVAL_GROUND = "arrival_ground"


class TaxiRefusalReason(Enum):
    RUNWAY_OCCUPIED = "runway_occupied"
    TAXIWAY_OCCUPIED = "taxiway_occupied"
    INVALID_START_POINT = "invalid_start_point"
    INVALID_CLEARANCE_REQUEST = "invalid_clearance_request"
    NO_ROUTE_AVAILABLE = "no_route_available"
    AIRCRAFT_NOT_UNDER_CONTROL = "aircraft_not_under_control"
    INVALID_STATE_FOR_TAXI = "invalid_state_for_taxi"


@dataclass
class TaxiProgress:
    callsign: str
    cleared_nodes: list[str]
    visited_nodes: list[str] = field(default_factory=list)
    current_node_id: str | None = None
    started_at_s: float = 0.0
    last_progress_s: float = 0.0
    route_completed: bool = False


class TowerState(Enum):
    IDLE = "idle"
    LINE_UP = "line_up"
    TAKEOFF_CLEARED = "takeoff_cleared"
    LANDING_CLEARED = "landing_cleared"
    GO_AROUND = "go_around"
    DOWNWIND = "downwind"
    BASE = "base"
    FINAL_APPROACH = "final_approach"
    TOUCH_AND_GO = "touch_and_go"
    OPTION = "option"
    LOW_APPROACH = "low_approach"
    STOP_AND_GO = "stop_and_go"
    FULL_STOP = "full_stop"
    OVERHEAD_JOIN = "overhead_join"


class DepartureState(Enum):
    IDLE = "idle"
    INITIAL_CLIMB = "initial_climb"
    RADAR_CONTACT = "radar_contact"
    ENROUTE = "enroute"
    HANDOFF = "handoff"
    HEADING_ASSIGNED = "heading_assigned"
    CLIMB_CLEARED = "climb_cleared"


class ApproachState(Enum):
    IDLE = "idle"
    VECTORING = "vectoring"
    HOLDING = "holding"
    ILS_CLEARED = "ils_cleared"
    FINAL = "final"
    GO_AROUND = "go_around"
    DESCENT_CLEARED = "descent_cleared"
    RNAV_CLEARED = "rnav_cleared"
    VISUAL_CLEARED = "visual_cleared"
    APPROACH_SEQUENCE = "approach_sequence"


class CenterState(Enum):
    IDLE = "idle"
    ENROUTE = "enroute"
    CRUISE = "cruise"
    CLIMB_CLEARED = "climb_cleared"
    DESCENT_CLEARED = "descent_cleared"
    HANDOFF = "handoff"


class AtisState(Enum):
    IDLE = "idle"
    BROADCASTING = "broadcasting"


@dataclass
class ControllerCommand:
    command_type: str
    target_callsign: str
    source: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class AircraftHandoff:
    callsign: str
    from_controller: str
    to_controller: str
    frequency: float
    accepted: bool = False


@dataclass
class FlightStatusRecord:
    timestamp_s: float
    callsign: str
    controller_callsign: str
    previous_state: Optional[str]
    new_state: str
    command_type: Optional[str] = None


@dataclass
class ClearanceState:
    clearance_type: str
    issued_by: str
    is_active: bool = True
    acknowledged: bool = False
    issued_at_s: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)


class TrafficAdvisoryType(Enum):
    TRAFFIC_IN_VICINITY = "traffic_in_vicinity"
    CIRCUIT_JOIN = "circuit_join"
    CIRCUIT_DOWNWIND = "circuit_downwind"
    CIRCUIT_BASE = "circuit_base"
    CIRCUIT_FINAL = "circuit_final"
    PATTERN_ENTER = "pattern_enter"
    PATTERN_EXIT = "pattern_exit"
    LANDING_SEQUENCE = "landing_sequence"


@dataclass
class TrafficAdvisory:
    advisory_type: TrafficAdvisoryType
    target_callsign: str
    traffic_callsign: str
    position: str = ""
    instruction: str = ""
    issued_by: str = ""


@dataclass
class AtisBroadcast:
    airport_icao: str
    identifier: str
    frequency_mhz: float
    timestamp_s: float = 0.0
    metar: str = ""
    runways_in_use: List[str] = field(default_factory=list)
    approach_in_use: str = ""
    notices: List[str] = field(default_factory=list)


@dataclass
class SIDAssignment:
    sid_name: str
    initial_alt_ft: int
    departure_fix: str = ""
    current_alt_ft: int = 0
    is_vectored: bool = False
    vector_heading: Optional[float] = None
    speed_restriction: Optional[int] = None
    handoff_alt_ft: Optional[int] = None


@dataclass
class STARAssignment:
    star_name: str
    initial_alt_ft: int
    approach_runway: str = ""
    current_alt_ft: int = 0
    speed_restriction: Optional[int] = None
    intercept_distance_nm: float = 10.0
    vector_heading: Optional[float] = None


@dataclass
class AirwayAssignment:
    airway_name: str
    entry_fix: str
    exit_fix: str
    fixes: List[str] = field(default_factory=list)
    current_fix_index: int = 0
    assigned_flight_level: int = 0
    distance_to_exit_nm: float = 0.0


@dataclass
class AltitudeChangeRequest:
    callsign: str
    requested_alt_ft: int
    current_alt_ft: int
    reason: str = ""
    approved: Optional[bool] = None
    responded_at_s: Optional[float] = None


@dataclass
class VfrCircuitProgress:
    callsign: str
    runway: str
    pattern_direction: str = "left"
    current_leg: str = ""
    circuit_count: int = 0
    touch_and_go_count: int = 0
    joined_at_s: float = 0.0


@dataclass
class PatternConflict:
    runway: str
    leg: str
    aircraft_a: str
    aircraft_b: str
    conflict_type: str = "same_leg"
    severity: str = "warning"
    recommendation: str = ""


class DeliveryState(Enum):
    IDLE = "idle"
    CLEARANCE_ISSUED = "clearance_issued"
    READBACK_PENDING = "readback_pending"
    READBACK_VERIFIED = "readback_verified"
    RELEASED = "released"


@dataclass
class CraftClearance:
    callsign: str
    destination: str
    sid_name: str
    initial_altitude_ft: int
    departure_frequency_mhz: float
    squawk: str
    route: str = ""
    remarks: str = ""


@dataclass
class HoldingInstruction:
    callsign: str
    fix: str
    altitude_ft: int
    leg_direction: str = "left"
    inbound_heading: Optional[float] = None
    outbound_heading: Optional[float] = None
    leg_length: str = "1 minute"
    expected_approach_time: Optional[str] = None


@dataclass
class MissedApproachProcedure:
    callsign: str
    missed_approach_point: str = ""
    climb_to_altitude_ft: int = 3000
    heading: Optional[float] = None
    contact_frequency_mhz: Optional[float] = None
    instructions: str = ""


@dataclass
class FlightContext:
    callsign: str
    aircraft_type: str = ""
    origin: str = ""
    destination: str = ""
    current_alt_ft: float = 0.0
    assigned_runway: str = ""
    sid_name: str = ""
    star_name: str = ""
    approach_type: str = ""
    gate: str = ""
    current_controller: str = ""
    previous_controller: str = ""
    history: List[Dict[str, Any]] = field(default_factory=list)
