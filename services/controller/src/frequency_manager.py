from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from shapely.geometry import Point

EARTH_RADIUS_NM = 3440.065

DEFAULT_RANGES: Dict[str, float] = {
    "GROUND": 5.0,
    "TOWER": 30.0,
    "DEPARTURE": 50.0,
    "APPROACH": 50.0,
    "CENTER": 200.0,
    "ATIS": 100.0,
}


def _haversine_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_NM * c


@dataclass
class ControllerFacility:
    facility_type: str
    controller_callsign: str
    frequency_mhz: float
    airport_icao: Optional[str] = None
    sector_id: Optional[str] = None
    latitude: float = 0.0
    longitude: float = 0.0
    range_nm: float = 0.0


class FrequencyManager:
    def __init__(self) -> None:
        self._facilities: Dict[str, List[ControllerFacility]] = {}
        self._ownership: Dict[str, str] = {}

    def add_facility(self, facility: ControllerFacility) -> None:
        key = f"{facility.frequency_mhz:.3f}"
        if key not in self._facilities:
            self._facilities[key] = []
        self._facilities[key].append(facility)

    def remove_facility(self, frequency_mhz: float, controller_callsign: str) -> None:
        key = f"{frequency_mhz:.3f}"
        if key in self._facilities:
            self._facilities[key] = [
                f for f in self._facilities[key]
                if f.controller_callsign != controller_callsign
            ]

    def clear_facilities(self) -> None:
        self._facilities.clear()

    def resolve_frequency(
        self, frequency_mhz: float, position: Point
    ) -> Optional[ControllerFacility]:
        key = f"{frequency_mhz:.3f}"
        candidates = self._facilities.get(key, [])
        if not candidates:
            return None

        best: Optional[ControllerFacility] = None
        best_dist = float("inf")

        for fac in candidates:
            if fac.latitude == 0.0 and fac.longitude == 0.0:
                continue
            dist = _haversine_nm(position.y, position.x, fac.latitude, fac.longitude)
            if dist <= fac.range_nm and dist < best_dist:
                best_dist = dist
                best = fac

        return best

    def find_facilities(
        self,
        facility_type: Optional[str] = None,
        airport_icao: Optional[str] = None,
    ) -> List[ControllerFacility]:
        results: List[ControllerFacility] = []
        for facilities in self._facilities.values():
            for fac in facilities:
                if facility_type and fac.facility_type != facility_type:
                    continue
                if airport_icao and fac.airport_icao != airport_icao:
                    continue
                results.append(fac)
        return results

    def get_owner(self, callsign: str) -> Optional[str]:
        return self._ownership.get(callsign)

    def set_owner(self, callsign: str, controller_callsign: str) -> None:
        self._ownership[callsign] = controller_callsign

    def release_owner(self, callsign: str) -> Optional[str]:
        return self._ownership.pop(callsign, None)

    def load_airport_frequencies(
        self,
        icao: str,
        latitude: float,
        longitude: float,
        frequencies: List[Dict[str, Any]],
    ) -> None:
        for freq in frequencies:
            ftype = freq.get("type", "").upper()
            freq_mhz = freq.get("frequency_mhz", 0.0)
            if not ftype or freq_mhz <= 0:
                continue
            callsign = freq.get("callsign") or f"{icao}_{ftype}"
            facility_range = freq.get("range_nm", DEFAULT_RANGES.get(ftype, 10.0))

            self.add_facility(ControllerFacility(
                facility_type=ftype,
                controller_callsign=callsign,
                frequency_mhz=freq_mhz,
                airport_icao=icao,
                latitude=latitude,
                longitude=longitude,
                range_nm=facility_range,
            ))

    def load_controller_frequencies(
        self, controllers: List[Dict[str, Any]]
    ) -> None:
        for ctrl in controllers:
            freq_mhz = ctrl.get("frequency_mhz", 0.0)
            ctype = ctrl.get("type", "CENTER").upper()
            callsign = ctrl.get("callsign", "")
            if freq_mhz <= 0 or not callsign or not ctype:
                continue
            self.add_facility(ControllerFacility(
                facility_type=ctype,
                controller_callsign=callsign,
                frequency_mhz=freq_mhz,
                airport_icao=ctrl.get("airport_icao"),
                sector_id=ctrl.get("sector_id"),
                latitude=ctrl.get("latitude", 0.0),
                longitude=ctrl.get("longitude", 0.0),
                range_nm=ctrl.get("range_nm", DEFAULT_RANGES.get(ctype, 100.0)),
            ))
