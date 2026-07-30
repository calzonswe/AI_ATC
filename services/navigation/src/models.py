from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple


@dataclass
class LatLon:
    lat: float
    lon: float


@dataclass
class GeoVector:
    heading_deg: float
    distance_nm: float


class NodeType(Enum):
    INTERSECTION = "intersection"
    GATE = "gate"
    RUNWAY_THRESHOLD = "runway_threshold"
    PARKING = "parking"
    DEICE = "deice"
    HOLD_SHORT = "hold_short"


@dataclass
class TaxiNode:
    node_id: str
    position: LatLon
    node_type: NodeType = NodeType.INTERSECTION
    name: str = ""


@dataclass
class TaxiEdge:
    edge_id: str
    from_node: str
    to_node: str
    distance_m: float
    taxiway_name: str = ""
    closed: bool = False
    width_ft: float = 75.0


@dataclass
class TaxiGraph:
    nodes: Dict[str, TaxiNode] = field(default_factory=dict)
    edges: Dict[str, TaxiEdge] = field(default_factory=dict)
    adjacency: Dict[str, Dict[str, str]] = field(default_factory=dict)

    def add_node(self, node: TaxiNode) -> None:
        self.nodes[node.node_id] = node
        if node.node_id not in self.adjacency:
            self.adjacency[node.node_id] = {}

    def add_edge(self, edge: TaxiEdge) -> None:
        self.edges[edge.edge_id] = edge
        self.adjacency.setdefault(edge.from_node, {})[edge.to_node] = edge.edge_id
        self.adjacency.setdefault(edge.to_node, {})[edge.from_node] = edge.edge_id


@dataclass
class TaxiRoute:
    nodes: List[TaxiNode] = field(default_factory=list)
    edges: List[TaxiEdge] = field(default_factory=list)
    total_distance_m: float = 0.0
    total_duration_s: float = 0.0

    @property
    def instructions(self) -> List[str]:
        if not self.edges:
            return []
        result = []
        for i, edge in enumerate(self.edges):
            from_node = self.nodes[i] if i < len(self.nodes) else None
            to_node = self.nodes[i + 1] if i + 1 < len(self.nodes) else None
            if from_node and to_node:
                result.append(
                    f"Taxi via {edge.taxiway_name} from {from_node.name or from_node.node_id} "
                    f"to {to_node.name or to_node.node_id} ({edge.distance_m:.0f}m)"
                )
            else:
                result.append(f"Taxi via {edge.taxiway_name} ({edge.distance_m:.0f}m)")
        return result


class ProcedureType(Enum):
    SID = "SID"
    STAR = "STAR"
    IAP = "IAP"


@dataclass
class ProcedureWaypoint:
    ident: str
    lat: float
    lon: float
    altitude_ft: Optional[float] = None
    speed_kn: Optional[float] = None
    is_flyover: bool = False
    leg_type: str = ""


@dataclass
class Procedure:
    type: ProcedureType
    name: str
    airport_icao: str = ""
    runways: List[str] = field(default_factory=list)
    waypoints: List[ProcedureWaypoint] = field(default_factory=list)
    altitude_restrictions: List[Dict] = field(default_factory=list)
    speed_restrictions: List[Dict] = field(default_factory=list)

    @property
    def total_distance_nm(self) -> float:
        from geo import geodetic_distance
        if len(self.waypoints) < 2:
            return 0.0
        total = 0.0
        for i in range(len(self.waypoints) - 1):
            a = self.waypoints[i]
            b = self.waypoints[i + 1]
            total += geodetic_distance(a.lat, a.lon, b.lat, b.lon)
        return total

    @property
    def leg_distances_nm(self) -> List[float]:
        from geo import geodetic_distance
        if len(self.waypoints) < 2:
            return []
        return [
            geodetic_distance(
                self.waypoints[i].lat, self.waypoints[i].lon,
                self.waypoints[i + 1].lat, self.waypoints[i + 1].lon,
            )
            for i in range(len(self.waypoints) - 1)
        ]


@dataclass
class ILSIntercept:
    intercept_angle_deg: float
    intercept_distance_nm: float
    intercept_altitude_ft: float
    is_feasible: bool = True
    recommended_heading: float = 0.0
    distance_to_threshold_nm: float = 0.0
    reason: str = ""


class HoldEntryType(Enum):
    DIRECT = "direct"
    TEARDROP = "teardrop"
    PARALLEL = "parallel"


class TurnDirection(Enum):
    LEFT = "left"
    RIGHT = "right"


@dataclass
class HoldingPattern:
    fix_lat: float
    fix_lon: float
    inbound_heading: float
    turn_direction: TurnDirection = TurnDirection.RIGHT
    leg_length_nm: float = 10.0
    leg_duration_s: float = 60.0
    speed_kn: float = 200.0
    outbound_heading: float = 0.0
    entry_type: HoldEntryType = HoldEntryType.DIRECT


@dataclass
class HoldEntrySolution:
    entry_type: HoldEntryType
    inbound_heading: float
    outbound_heading: float
    outbound_leg_duration_s: float
    outbound_distance_nm: float
    turn_direction: TurnDirection
    entry_heading: float = 0.0
    sector_angle_deg: float = 0.0
    instructions: List[str] = field(default_factory=list)


@dataclass
class VectorInstruction:
    heading_deg: float
    reason: str = ""
    distance_nm: float = 0.0
    altitude_ft: Optional[int] = None
    speed_kn: Optional[int] = None
    turn_direction: Optional[str] = None


@dataclass
class FinalApproachVector:
    heading_to_intercept: float
    intercept_angle_deg: float
    distance_to_runway_nm: float
    intercept_distance_nm: float
    altitude_ft: int
    instructions: List[VectorInstruction] = field(default_factory=list)


@dataclass
class RunwayOccupancy:
    runway_id: str
    aircraft_callsign: str
    landing_speed_kn: float
    exit_speed_kn: float
    distance_to_exit_m: float
    estimated_occupancy_s: float
    time_to_vacate_s: float
    clearance_time_s: float
    minimum_separation_s: float


@dataclass
class ConflictPrediction:
    aircraft_a: str
    aircraft_b: str
    time_to_conflict_s: float
    closest_distance_nm: float
    position_a_lat: float
    position_a_lon: float
    position_b_lat: float
    position_b_lon: float
    severity: str = "warning"
    type: str = "lateral"
