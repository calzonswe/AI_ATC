from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from runtime.aircraft import ActiveAircraft, TrajectoryPoint
from pubsub import EventBus, EventType


@dataclass
class ConflictInfo:
    aircraft_a: str
    aircraft_b: str
    lateral_distance_nm: float
    vertical_distance_ft: float
    time_to_conflict_s: float
    severity: str  # "warning", "critical"


class ConflictManager:
    def __init__(
        self,
        event_bus: Optional[EventBus] = None,
        lateral_separation_nm: float = 5.0,
        vertical_separation_ft: float = 1000.0,
        terminal_lateral_separation_nm: float = 3.0,
    ) -> None:
        self._event_bus = event_bus
        self._lateral_sep = lateral_separation_nm
        self._vertical_sep = vertical_separation_ft
        self._terminal_lateral_sep = terminal_lateral_separation_nm
        self._active_conflicts: Dict[str, ConflictInfo] = {}

    def check_pair(
        self, a: ActiveAircraft, b: ActiveAircraft
    ) -> Optional[ConflictInfo]:
        lat_dist = self._haversine_nm(
            a.position.lat, a.position.lon,
            b.position.lat, b.position.lon,
        )
        vert_dist = abs(a.position.alt_msl_ft - b.position.alt_msl_ft)
        threshold = (
            self._terminal_lateral_sep
            if (a.motion.on_ground or b.motion.on_ground)
            else self._lateral_sep
        )

        if lat_dist < threshold and vert_dist < self._vertical_sep:
            conflict_key = self._conflict_key(a.callsign, b.callsign)
            ttc = self._estimate_time_to_conflict(a, b, lat_dist)
            severity = "critical" if lat_dist < threshold * 0.5 else "warning"
            return ConflictInfo(
                aircraft_a=a.callsign,
                aircraft_b=b.callsign,
                lateral_distance_nm=lat_dist,
                vertical_distance_ft=vert_dist,
                time_to_conflict_s=ttc,
                severity=severity,
            )
        return None

    def check_all(
        self, aircraft_list: list[ActiveAircraft]
    ) -> list[ConflictInfo]:
        active_keys: set[str] = set()
        conflicts: list[ConflictInfo] = []

        for i in range(len(aircraft_list)):
            for j in range(i + 1, len(aircraft_list)):
                a = aircraft_list[i]
                b = aircraft_list[j]
                conflict = self.check_pair(a, b)
                if conflict is not None:
                    key = self._conflict_key(a.callsign, b.callsign)
                    active_keys.add(key)
                    if key not in self._active_conflicts:
                        self._active_conflicts[key] = conflict
                        if self._event_bus:
                            self._event_bus.publish(
                                EventType.CONFLICT_DETECTED,
                                {
                                    "aircraft_a": a.callsign,
                                    "aircraft_b": b.callsign,
                                    "lateral_nm": round(conflict.lateral_distance_nm, 2),
                                    "vertical_ft": round(conflict.vertical_distance_ft, 1),
                                    "severity": conflict.severity,
                                },
                                source="ConflictManager",
                            )
                    conflicts.append(conflict)

        resolved = [
            k for k in self._active_conflicts if k not in active_keys
        ]
        for key in resolved:
            info = self._active_conflicts.pop(key)
            if self._event_bus:
                self._event_bus.publish(
                    EventType.CONFLICT_RESOLVED,
                    {
                        "aircraft_a": info.aircraft_a,
                        "aircraft_b": info.aircraft_b,
                    },
                    source="ConflictManager",
                )

        return conflicts

    def check_trajectory_conflict(
        self,
        a_callsign: str,
        b_callsign: str,
        a_traj: list[TrajectoryPoint],
        b_traj: list[TrajectoryPoint],
    ) -> Optional[ConflictInfo]:
        min_points = min(len(a_traj), len(b_traj))
        for i in range(min_points):
            pa = a_traj[i]
            pb = b_traj[i]
            lat_dist = self._haversine_nm(pa.lat, pa.lon, pb.lat, pb.lon)
            vert_dist = abs(pa.alt_msl_ft - pb.alt_msl_ft)
            if lat_dist < self._lateral_sep and vert_dist < self._vertical_sep:
                ttc = pa.timestamp_s - min(a_traj[0].timestamp_s, b_traj[0].timestamp_s)
                return ConflictInfo(
                    aircraft_a=a_callsign,
                    aircraft_b=b_callsign,
                    lateral_distance_nm=lat_dist,
                    vertical_distance_ft=vert_dist,
                    time_to_conflict_s=max(0.0, ttc),
                    severity="warning",
                )
        return None

    @staticmethod
    def _haversine_nm(
        lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
        R = 3440.065
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(math.radians(lat1))
            * math.cos(math.radians(lat2))
            * math.sin(dlon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    @staticmethod
    def _estimate_time_to_conflict(
        a: ActiveAircraft, b: ActiveAircraft, current_dist_nm: float
    ) -> float:
        rel_speed = abs(a.motion.groundspeed_kn - b.motion.groundspeed_kn)
        if rel_speed < 1.0:
            return 999.0
        closure_rate = rel_speed * 1.6878  # convert kn to ft/s
        dist_ft = current_dist_nm * 6076.12
        return dist_ft / closure_rate

    @staticmethod
    def _conflict_key(a: str, b: str) -> str:
        return f"{min(a, b)}:{max(a, b)}"
