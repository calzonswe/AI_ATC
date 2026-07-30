from __future__ import annotations

import math
from typing import Dict, List, Optional

from models import RunwayOccupancy


class RunwayOccupancyTracker:
    APPROACH_SPEED_KN = 140.0
    TOUCHDOWN_DISTANCE_M = 300.0
    EXIT_SPEED_KN = 30.0
    VACATE_TURN_TIME_S = 8.0
    RUNWAY_CLEARANCE_BUFFER_S = 15.0
    DEPARTURE_SEPARATION_S = 60.0

    AIRCRAFT_PERFORMANCE: Dict[str, Dict] = {
        "A320": {"landing_speed_kn": 135, "exit_speed_kn": 25, "turnoff_time_s": 6},
        "B738": {"landing_speed_kn": 140, "exit_speed_kn": 28, "turnoff_time_s": 7},
        "B737": {"landing_speed_kn": 135, "exit_speed_kn": 25, "turnoff_time_s": 6},
        "A380": {"landing_speed_kn": 150, "exit_speed_kn": 15, "turnoff_time_s": 12},
        "B744": {"landing_speed_kn": 155, "exit_speed_kn": 18, "turnoff_time_s": 10},
        "B772": {"landing_speed_kn": 145, "exit_speed_kn": 22, "turnoff_time_s": 8},
        "C172": {"landing_speed_kn": 60, "exit_speed_kn": 15, "turnoff_time_s": 4},
        "default": {"landing_speed_kn": 140, "exit_speed_kn": 25, "turnoff_time_s": 8},
    }

    def calculate_occupancy(
        self,
        runway_id: str,
        aircraft_callsign: str,
        aircraft_type: str = "default",
        runway_length_m: float = 3000.0,
        exit_taxiway_distance_m: float = 2000.0,
        landing_speed_kn: Optional[float] = None,
        exit_speed_kn: Optional[float] = None,
    ) -> RunwayOccupancy:
        perf = self.AIRCRAFT_PERFORMANCE.get(aircraft_type, self.AIRCRAFT_PERFORMANCE["default"])
        land_kn = landing_speed_kn or perf["landing_speed_kn"]
        exit_kn = exit_speed_kn or perf["exit_speed_kn"]

        air_distance_m = runway_length_m * 0.5
        rollout_distance_m = exit_taxiway_distance_m - 300.0
        avg_rollout_speed_ms = ((land_kn + exit_kn) / 2.0) * 0.514444

        rollout_time_s = rollout_distance_m / avg_rollout_speed_ms if avg_rollout_speed_ms > 0 else 0
        turnoff_time_s = perf["turnoff_time_s"]
        estimated_occupancy_s = rollout_time_s + turnoff_time_s

        vacate_distance_m = exit_taxiway_distance_m
        vacate_speed_ms = exit_kn * 0.514444
        time_to_vacate_s = vacate_distance_m / vacate_speed_ms if vacate_speed_ms > 0 else 0

        clearance_time_s = time_to_vacate_s + self.RUNWAY_CLEARANCE_BUFFER_S

        min_sep_s = self._minimum_departure_separation(
            estimated_occupancy_s, aircraft_type
        )

        return RunwayOccupancy(
            runway_id=runway_id,
            aircraft_callsign=aircraft_callsign,
            landing_speed_kn=land_kn,
            exit_speed_kn=exit_kn,
            distance_to_exit_m=vacate_distance_m,
            estimated_occupancy_s=round(estimated_occupancy_s, 1),
            time_to_vacate_s=round(time_to_vacate_s, 1),
            clearance_time_s=round(clearance_time_s, 1),
            minimum_separation_s=round(min_sep_s, 1),
        )

    def calculate_wake_turbulence_separation(
        self,
        lead_type: str,
        trail_type: str,
    ) -> int:
        categories = {
            "H": "heavy",
            "M": "medium",
            "L": "light",
        }
        lead_cat = "M"
        trail_cat = "M"

        if "380" in lead_type or "744" in lead_type or "772" in lead_type:
            lead_cat = "H"
        if "320" in lead_type or "738" in lead_type or "737" in lead_type:
            lead_cat = "M"
        if "172" in lead_type:
            lead_cat = "L"
        if "380" in trail_type or "744" in trail_type or "772" in trail_type:
            trail_cat = "H"
        if "320" in trail_type or "738" in trail_type or "737" in trail_type:
            trail_cat = "M"
        if "172" in trail_type:
            trail_cat = "L"

        matrix = {
            ("H", "H"): 4,
            ("H", "M"): 5,
            ("H", "L"): 6,
            ("M", "H"): 3,
            ("M", "M"): 3,
            ("M", "L"): 4,
            ("L", "H"): 0,
            ("L", "M"): 0,
            ("L", "L"): 3,
        }
        return matrix.get((lead_cat, trail_cat), 3)

    def can_accept_arrival(
        self,
        runway_id: str,
        current_occupancy: Optional[RunwayOccupancy],
        time_since_last_landing_s: float,
        min_separation_s: float = 90.0,
    ) -> bool:
        if current_occupancy is not None and not self._is_runway_clear(
            current_occupancy, time_since_last_landing_s
        ):
            return False
        return time_since_last_landing_s >= min_separation_s

    def can_release_departure(
        self,
        runway_id: str,
        last_arrival: Optional[RunwayOccupancy],
        time_since_last_arrival_s: float,
        time_since_last_departure_s: float,
        departure_separation_s: Optional[float] = None,
    ) -> bool:
        sep = departure_separation_s or self.DEPARTURE_SEPARATION_S
        if last_arrival is not None:
            if time_since_last_arrival_s < last_arrival.clearance_time_s:
                return False
        if time_since_last_departure_s < sep:
            return False
        return True

    def _is_runway_clear(
        self, occupancy: RunwayOccupancy, elapsed_s: float
    ) -> bool:
        return elapsed_s >= occupancy.clearance_time_s

    def _minimum_departure_separation(
        self, occupancy_s: float, aircraft_type: str
    ) -> float:
        return max(occupancy_s + self.DEPARTURE_SEPARATION_S, 90.0)
