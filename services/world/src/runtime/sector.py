from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from shapely.geometry import MultiPolygon, Polygon


@dataclass
class AirspaceVolume:
    sector_id: int
    floor_ft: int
    ceiling_ft: int
    polygon: Polygon
    identifier: str = ""


@dataclass
class SectorAssignment:
    sector_id: int
    controller_callsign: Optional[str] = None
    aircraft_callsigns: List[str] = field(default_factory=list)
    frequency_mhz: float = 0.0
