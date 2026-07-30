from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from geo import (
        geodetic_distance,
        initial_bearing,
        normalize_heading,
    )
from models import (
    LatLon,
    Procedure,
    ProcedureType,
    ProcedureWaypoint,
)


class ProceduralRouteEngine:
    def __init__(self) -> None:
        self._procedures: Dict[str, Dict[str, Procedure]] = {}

    def load_procedure(self, procedure: Procedure) -> None:
        key = f"{procedure.airport_icao}:{procedure.type.value}:{procedure.name}"
        self._procedures[key] = procedure

    def get_procedure(
        self, airport_icao: str, proc_type: ProcedureType, name: str
    ) -> Optional[Procedure]:
        key = f"{airport_icao}:{proc_type.value}:{name}"
        return self._procedures.get(key)

    def get_procedures_for_airport(
        self, airport_icao: str, proc_type: Optional[ProcedureType] = None
    ) -> List[Procedure]:
        results = []
        for key, proc in self._procedures.items():
            if key.startswith(airport_icao + ":"):
                if proc_type is None or proc.type == proc_type:
                    results.append(proc)
        return results

    def build_procedure_from_waypoints(
        self,
        proc_type: ProcedureType,
        name: str,
        airport_icao: str,
        waypoint_data: List[Dict],
        runways: Optional[List[str]] = None,
    ) -> Procedure:
        wpts = []
        for wd in waypoint_data:
            wpts.append(ProcedureWaypoint(
                ident=wd["ident"],
                lat=wd["lat"],
                lon=wd["lon"],
                altitude_ft=wd.get("altitude_ft"),
                speed_kn=wd.get("speed_kn"),
                is_flyover=wd.get("is_flyover", False),
                leg_type=wd.get("leg_type", ""),
            ))
        proc = Procedure(
            type=proc_type,
            name=name,
            airport_icao=airport_icao,
            runways=runways or [],
            waypoints=wpts,
        )
        self.load_procedure(proc)
        return proc

    def compute_leg_headings(
        self, procedure: Procedure
    ) -> List[Tuple[float, float]]:
        headings = []
        wpts = procedure.waypoints
        for i in range(len(wpts) - 1):
            hdg = initial_bearing(wpts[i].lat, wpts[i].lon, wpts[i + 1].lat, wpts[i + 1].lon)
            dist = geodetic_distance(wpts[i].lat, wpts[i].lon, wpts[i + 1].lat, wpts[i + 1].lon)
            headings.append((hdg, dist))
        return headings

    def find_transition(
        self, procedure: Procedure, from_waypoint: str, to_waypoint: str
    ) -> Optional[List[ProcedureWaypoint]]:
        wpts = procedure.waypoints
        start_idx = -1
        end_idx = -1
        for i, wp in enumerate(wpts):
            if wp.ident.upper() == from_waypoint.upper():
                start_idx = i
            if wp.ident.upper() == to_waypoint.upper():
                end_idx = i
        if start_idx == -1 or end_idx == -1 or start_idx > end_idx:
            return None
        return wpts[start_idx : end_idx + 1]

    def validate_constraints(
        self,
        procedure: Procedure,
        altitude_ft: float,
        speed_kn: float,
    ) -> List[str]:
        warnings = []
        for i, wp in enumerate(procedure.waypoints):
            if wp.altitude_ft is not None:
                margin = abs(altitude_ft - wp.altitude_ft)
                if margin > 500:
                    warnings.append(
                        f"Waypoint {wp.ident}: altitude {altitude_ft:.0f}ft "
                        f"outside constraint {wp.altitude_ft:.0f}ft (+/-500ft)"
                    )
            if wp.speed_kn is not None and speed_kn > wp.speed_kn + 10:
                warnings.append(
                    f"Waypoint {wp.ident}: speed {speed_kn:.0f}kn "
                    f"exceeds constraint {wp.speed_kn:.0f}kn"
                )
        return warnings

    def compute_route_geometry(self, procedure: Procedure) -> Dict:
        wpts = procedure.waypoints
        return {
            "name": procedure.name,
            "type": procedure.type.value,
            "airport": procedure.airport_icao,
            "runways": procedure.runways,
            "waypoint_count": len(wpts),
            "total_distance_nm": procedure.total_distance_nm,
            "legs": [
                {
                    "from": wpts[i].ident,
                    "to": wpts[i + 1].ident,
                    "heading_deg": round(
                        initial_bearing(wpts[i].lat, wpts[i].lon, wpts[i + 1].lat, wpts[i + 1].lon), 1
                    ),
                    "distance_nm": round(
                        geodetic_distance(wpts[i].lat, wpts[i].lon, wpts[i + 1].lat, wpts[i + 1].lon), 2
                    ),
                    "altitude_ft": wpts[i + 1].altitude_ft,
                    "speed_kn": wpts[i + 1].speed_kn,
                }
                for i in range(len(wpts) - 1)
            ],
        }
