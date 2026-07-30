from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class WindData:
    direction: float
    speed_kn: float
    gust_kn: float = 0.0
    variation_from: Optional[float] = None
    variation_to: Optional[float] = None


@dataclass
class CloudLayer:
    coverage: str
    altitude_ft: int


@dataclass
class MetarData:
    icao: str
    time: float
    wind: WindData
    visibility_m: float
    qnh_hpa: float
    temperature_c: float
    dewpoint_c: float
    clouds: List[CloudLayer] = field(default_factory=list)
