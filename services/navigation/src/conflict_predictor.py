from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from .geo import (
    destination_point,
    geodetic_distance,
    initial_bearing,
    normalize_heading,
)
from models import ConflictPrediction, LatLon


class ConflictPredictor:
    TIME_STEP_S = 10.0
    MAX_LOOKAHEAD_S = 300.0
    DEFAULT_LATERAL_NM = 5.0
    DEFAULT_VERTICAL_FT = 1000.0

    def predict(
        self,
        aircraft_list: List[Dict],
        lateral_separation_nm: float = DEFAULT_LATERAL_NM,
        vertical_separation_ft: float = DEFAULT_VERTICAL_FT,
        lookahead_s: float = MAX_LOOKAHEAD_S,
    ) -> List[ConflictPrediction]:
        conflicts: List[ConflictPrediction] = []
        steps = max(1, int(lookahead_s / self.TIME_STEP_S))

        for i in range(len(aircraft_list)):
            for j in range(i + 1, len(aircraft_list)):
                a = aircraft_list[i]
                b = aircraft_list[j]

                result = self._predict_pair(
                    a, b, lateral_separation_nm, vertical_separation_ft, steps
                )
                if result is not None:
                    conflicts.append(result)

        return conflicts

    def predict_pair(
        self,
        ac_a: Dict,
        ac_b: Dict,
        lateral_separation_nm: float = DEFAULT_LATERAL_NM,
        vertical_separation_ft: float = DEFAULT_VERTICAL_FT,
    ) -> Optional[ConflictPrediction]:
        steps = max(1, int(self.MAX_LOOKAHEAD_S / self.TIME_STEP_S))
        return self._predict_pair(ac_a, ac_b, lateral_separation_nm, vertical_separation_ft, steps)

    def project_position(
        self,
        lat: float,
        lon: float,
        alt_ft: float,
        heading_deg: float,
        speed_kn: float,
        vertical_speed_fpm: float,
        time_s: float,
    ) -> Tuple[float, float, float]:
        dist_nm = (speed_kn * time_s) / 3600.0
        new_lat, new_lon = destination_point(lat, lon, heading_deg, dist_nm)
        new_alt = alt_ft + (vertical_speed_fpm * time_s) / 60.0
        return new_lat, new_lon, new_alt

    def project_trajectory(
        self,
        ac: Dict,
        steps: int,
    ) -> List[Tuple[float, float, float]]:
        trajectory = []
        for step in range(1, steps + 1):
            t = step * self.TIME_STEP_S
            lat, lon, alt = self.project_position(
                lat=ac.get("lat", 0.0),
                lon=ac.get("lon", 0.0),
                alt_ft=ac.get("alt_msl", 0.0),
                heading_deg=ac.get("heading", 0.0),
                speed_kn=ac.get("groundspeed", 0.0),
                vertical_speed_fpm=ac.get("vertical_speed", 0.0),
                time_s=t,
            )
            trajectory.append((lat, lon, alt))
        return trajectory

    def _predict_pair(
        self,
        a: Dict,
        b: Dict,
        lateral_nm: float,
        vertical_ft: float,
        steps: int,
    ) -> Optional[ConflictPrediction]:
        min_dist_nm = float("inf")
        min_time_s = 0.0
        min_pos_a = (0.0, 0.0, 0.0)
        min_pos_b = (0.0, 0.0, 0.0)

        a_traj = self.project_trajectory(a, steps)
        b_traj = self.project_trajectory(b, steps)

        for step in range(steps):
            pa = a_traj[step]
            pb = b_traj[step]

            lat_dist = geodetic_distance(pa[0], pa[1], pb[0], pb[1])
            alt_dist = abs(pa[2] - pb[2])

            if lat_dist < min_dist_nm:
                min_dist_nm = lat_dist
                min_time_s = (step + 1) * self.TIME_STEP_S
                min_pos_a = pa
                min_pos_b = pb

            if lat_dist < lateral_nm and alt_dist < vertical_ft:
                severity = "critical" if lat_dist < lateral_nm * 0.5 else "warning"
                conflict_type = "lateral_vertical" if alt_dist < vertical_ft * 0.5 else "lateral"
                ttc = (step + 1) * self.TIME_STEP_S

                return ConflictPrediction(
                    aircraft_a=a.get("callsign", "UNKNOWN"),
                    aircraft_b=b.get("callsign", "UNKNOWN"),
                    time_to_conflict_s=round(ttc, 1),
                    closest_distance_nm=round(min_dist_nm, 2),
                    position_a_lat=pa[0],
                    position_a_lon=pa[1],
                    position_b_lat=pb[0],
                    position_b_lon=pb[1],
                    severity=severity,
                    type=conflict_type,
                )

        return None

    def minimum_separation(
        self, ac_a: Dict, ac_b: Dict
    ) -> Tuple[float, float, float]:
        steps = max(1, int(self.MAX_LOOKAHEAD_S / self.TIME_STEP_S))
        min_dist = float("inf")
        min_lat = 0.0
        min_alt = 0.0

        a_traj = self.project_trajectory(ac_a, steps)
        b_traj = self.project_trajectory(ac_b, steps)

        for step in range(steps):
            pa = a_traj[step]
            pb = b_traj[step]
            lat_dist = geodetic_distance(pa[0], pa[1], pb[0], pb[1])
            alt_dist = abs(pa[2] - pb[2])
            total = math.sqrt(lat_dist ** 2 + (alt_dist / 6076.12) ** 2)
            if total < min_dist:
                min_dist = total
                min_lat = lat_dist
                min_alt = alt_dist

        return min_dist, min_lat, min_alt
