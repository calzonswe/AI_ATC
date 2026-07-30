from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


PHONETIC_CODES = [
    "Alpha", "Bravo", "Charlie", "Delta", "Echo",
    "Foxtrot", "Golf", "Hotel", "India", "Juliett",
    "Kilo", "Lima", "Mike", "November", "Oscar",
    "Papa", "Quebec", "Romeo", "Sierra", "Tango",
    "Uniform", "Victor", "Whiskey", "X-ray", "Yankee", "Zulu",
]


@dataclass
class MetarData:
    airport_icao: str
    time_zulu: str = ""
    wind_dir: int = 0
    wind_speed_kt: int = 0
    wind_gust_kt: Optional[int] = None
    wind_variable_from: Optional[int] = None
    wind_variable_to: Optional[int] = None
    visibility_m: int = 9999
    cavok: bool = False
    weather: List[str] = field(default_factory=list)
    clouds: List[dict] = field(default_factory=list)
    temp_c: Optional[int] = None
    dewpoint_c: Optional[int] = None
    qnh_hpa: Optional[int] = None
    trend: str = ""
    raw: str = ""


@dataclass
class AtisData:
    airport_icao: str
    identifier: str
    metar: MetarData
    runways_in_use: List[str] = field(default_factory=list)
    approach_in_use: str = ""
    notices: List[str] = field(default_factory=list)
