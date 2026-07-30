from __future__ import annotations

import math
from typing import Dict, List, Optional

from runtime.aircraft import (
    ActiveAircraft,
    AircraftState,
    MotionData,
    PositionData,
    TrajectoryPoint,
)
from pubsub import EventBus, EventType


class AircraftManager:
    def __init__(self, event_bus: Optional[EventBus] = None) -> None:
        self._aircraft: Dict[str, ActiveAircraft] = {}
        self._event_bus = event_bus

    @property
    def count(self) -> int:
        return len(self._aircraft)

    def add_or_update(self, frame: dict) -> ActiveAircraft:
        callsign: str = frame.get("callsign", "")
        if not callsign:
            raise ValueError("Telemetry frame missing callsign")

        position_dict = frame.get("position", {})
        motion_dict = frame.get("motion", {})
        ts: float = frame.get("ts", 0.0) / 1000.0

        if callsign in self._aircraft:
            ac = self._aircraft[callsign]
            prev_state = ac.state
            ac.position = self._dict_to_position(position_dict)
            ac.motion = self._dict_to_motion(motion_dict)
            ac.last_update_s = ts

            self._detect_state_transition(ac, prev_state)
        else:
            ac = ActiveAircraft(
                callsign=callsign,
                position=self._dict_to_position(position_dict),
                motion=self._dict_to_motion(motion_dict),
                state=AircraftState.CRUISE,
                squawk_code=frame.get("radios", {}).get("squawk", "1200"),
                last_update_s=ts,
            )
            self._aircraft[callsign] = ac

        self._append_trajectory_point(ac)

        if self._event_bus:
            self._event_bus.publish(
                EventType.AIRCRAFT_POSITION_UPDATED,
                {"callsign": callsign, "position": position_dict},
                source="AircraftManager",
            )

        return ac

    def remove(self, callsign: str) -> None:
        self._aircraft.pop(callsign, None)

    def get(self, callsign: str) -> Optional[ActiveAircraft]:
        return self._aircraft.get(callsign)

    def get_all(self) -> list[ActiveAircraft]:
        return list(self._aircraft.values())

    def get_by_state(self, state: AircraftState) -> list[ActiveAircraft]:
        return [ac for ac in self._aircraft.values() if ac.state == state]

    def get_nearby(
        self, lat: float, lon: float, radius_nm: float
    ) -> list[ActiveAircraft]:
        result: list[ActiveAircraft] = []
        for ac in self._aircraft.values():
            dist = self._haversine_nm(lat, lon, ac.position.lat, ac.position.lon)
            if dist <= radius_nm:
                result.append(ac)
        return result

    def predict_trajectory(
        self, callsign: str, lookahead_s: float
    ) -> list[TrajectoryPoint]:
        ac = self.get(callsign)
        if ac is None:
            return []

        points: list[TrajectoryPoint] = []
        heading_rad = math.radians(ac.position.heading_true)
        speed_nm_per_s = ac.motion.groundspeed_kn / 3600.0
        vs_fpm = ac.motion.vertical_speed_fpm
        lat = ac.position.lat
        lon = ac.position.lon
        alt = ac.position.alt_msl_ft
        t0 = ac.last_update_s

        steps = max(1, int(lookahead_s / 5.0))
        for i in range(1, steps + 1):
            dt = i * lookahead_s / steps
            dist_nm = speed_nm_per_s * dt
            dlat = dist_nm * math.cos(heading_rad) / 60.0
            dlon = dist_nm * math.sin(heading_rad) / (60.0 * math.cos(math.radians(lat)))
            new_lat = lat + dlat
            new_lon = lon + dlon
            new_alt = alt + vs_fpm * dt / 60.0
            points.append(
                TrajectoryPoint(
                    lat=new_lat,
                    lon=new_lon,
                    alt_msl_ft=new_alt,
                    timestamp_s=t0 + dt,
                )
            )

        return points

    def _dict_to_position(self, d: dict) -> PositionData:
        return PositionData(
            lat=d.get("lat", 0.0),
            lon=d.get("lon", 0.0),
            alt_msl_ft=d.get("alt_msl", 0.0),
            alt_agl_ft=d.get("alt_agl", 0.0),
            heading_true=d.get("heading", 0.0),
            heading_mag=d.get("heading", 0.0),
            pitch_deg=d.get("pitch", 0.0),
            bank_deg=d.get("bank", 0.0),
        )

    def _dict_to_motion(self, d: dict) -> MotionData:
        return MotionData(
            ias_kn=d.get("ias", 0.0),
            groundspeed_kn=d.get("groundspeed", 0.0),
            vertical_speed_fpm=d.get("vertical_speed", 0.0),
            on_ground=d.get("on_ground", True),
        )

    def _detect_state_transition(
        self, ac: ActiveAircraft, prev_state: AircraftState
    ) -> None:
        if ac.state != prev_state:
            ac.previous_state = prev_state
            if self._event_bus:
                self._event_bus.publish(
                    EventType.AIRCRAFT_STATE_CHANGED,
                    {
                        "callsign": ac.callsign,
                        "from": prev_state.value,
                        "to": ac.state.value,
                    },
                    source="AircraftManager",
                )

    def _append_trajectory_point(self, ac: ActiveAircraft) -> None:
        ac.trajectory.append(
            TrajectoryPoint(
                lat=ac.position.lat,
                lon=ac.position.lon,
                alt_msl_ft=ac.position.alt_msl_ft,
                timestamp_s=ac.last_update_s,
            )
        )
        if len(ac.trajectory) > 1000:
            ac.trajectory = ac.trajectory[-500:]

    @staticmethod
    def _haversine_nm(
        lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
        R = 3440.065  # Earth radius in NM
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
