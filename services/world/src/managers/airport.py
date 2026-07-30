from __future__ import annotations

import math
from typing import Dict, List, Optional

from runtime.airport import (
    AirportState,
    OperationalMode,
    RunwayState,
    RunwaySurfaceCondition,
)
from runtime.weather import WindData
from pubsub import EventBus, EventType


class AirportManager:
    def __init__(self, event_bus: Optional[EventBus] = None) -> None:
        self._airports: Dict[str, AirportState] = {}
        self._event_bus = event_bus

    def load_airport(
        self,
        icao: str,
        elevation_ft: int = 0,
        magnetic_var: float = 0.0,
        runways: Optional[List[dict]] = None,
    ) -> AirportState:
        runway_states: Dict[str, RunwayState] = {}
        if runways:
            for r in runways:
                rwy = RunwayState(
                    identifier=r["identifier"],
                    heading=r.get("heading", 0.0),
                    length_ft=r.get("length_ft", 0),
                    surface=r.get("surface", "concrete"),
                    ils_frequency=r.get("ils_frequency"),
                )
                runway_states[rwy.identifier] = rwy

        state = AirportState(
            icao=icao,
            elevation_ft=elevation_ft,
            magnetic_var=magnetic_var,
            runways=runway_states,
        )
        self._airports[icao] = state
        return state

    def get(self, icao: str) -> Optional[AirportState]:
        return self._airports.get(icao.upper())

    def get_all(self) -> list[AirportState]:
        return list(self._airports.values())

    def update_runway_state(
        self,
        icao: str,
        runway_id: str,
        active_for_departure: Optional[bool] = None,
        active_for_arrival: Optional[bool] = None,
        surface_condition: Optional[RunwaySurfaceCondition] = None,
        operational_mode: Optional[OperationalMode] = None,
    ) -> None:
        apt = self.get(icao)
        if apt is None:
            return
        rwy = apt.runways.get(runway_id)
        if rwy is None:
            return
        if active_for_departure is not None:
            rwy.active_for_departure = active_for_departure
        if active_for_arrival is not None:
            rwy.active_for_arrival = active_for_arrival
        if surface_condition is not None:
            rwy.surface_condition = surface_condition
        if operational_mode is not None:
            rwy.operational_mode = operational_mode
        if self._event_bus:
            self._event_bus.publish(
                EventType.RUNWAY_STATE_CHANGED,
                {
                    "airport": icao,
                    "runway": runway_id,
                    "departure": rwy.active_for_departure,
                    "arrival": rwy.active_for_arrival,
                },
                source="AirportManager",
            )

    def determine_active_runways(
        self, icao: str, wind: WindData
    ) -> tuple[Optional[str], Optional[str]]:
        apt = self.get(icao)
        if apt is None or not apt.runways:
            return None, None

        best_dep = None
        best_arr = None
        min_crosswind_dep = float("inf")
        max_headwind_arr = float("-inf")

        for rwy_id, rwy in apt.runways.items():
            if rwy.operational_mode != OperationalMode.ACTIVE:
                continue
            crosswind, headwind = self._calculate_wind_components(
                wind, rwy.heading
            )
            if crosswind < min_crosswind_dep and headwind >= 0:
                min_crosswind_dep = crosswind
                best_dep = rwy_id
            if headwind > max_headwind_arr:
                max_headwind_arr = headwind
                best_arr = rwy_id

        if best_dep:
            apt.runways[best_dep].active_for_departure = True
        if best_arr:
            apt.runways[best_arr].active_for_arrival = True
        apt.active_runway_dep = best_dep
        apt.active_runway_arr = best_arr

        if best_dep and best_arr:
            apt.flow_direction = (
                "same" if best_dep == best_arr else "opposite"
            )

        if self._event_bus:
            self._event_bus.publish(
                EventType.RUNWAY_STATE_CHANGED,
                {
                    "airport": icao,
                    "departure_runway": best_dep,
                    "arrival_runway": best_arr,
                    "flow": apt.flow_direction,
                    "wind_direction": wind.direction,
                    "wind_speed": wind.speed_kn,
                },
                source="AirportManager",
            )

        return best_dep, best_arr

    def set_operational_mode(
        self, icao: str, mode: OperationalMode
    ) -> None:
        apt = self.get(icao)
        if apt is None:
            return
        apt.operational_mode = mode

    def get_active_runway_for_departure(self, icao: str) -> Optional[RunwayState]:
        apt = self.get(icao)
        if apt is None or apt.active_runway_dep is None:
            return None
        return apt.runways.get(apt.active_runway_dep)

    def get_active_runway_for_arrival(self, icao: str) -> Optional[RunwayState]:
        apt = self.get(icao)
        if apt is None or apt.active_runway_arr is None:
            return None
        return apt.runways.get(apt.active_runway_arr)

    @staticmethod
    def _calculate_wind_components(
        wind: WindData, runway_heading: float
    ) -> tuple[float, float]:
        angle_diff = math.radians(wind.direction - runway_heading)
        crosswind = wind.speed_kn * math.sin(angle_diff)
        headwind = wind.speed_kn * math.cos(angle_diff)
        return abs(crosswind), headwind

    @staticmethod
    def calculate_crosswind(
        wind_direction: float, wind_speed_kn: float, runway_heading: float
    ) -> float:
        angle_diff = math.radians(wind_direction - runway_heading)
        return abs(wind_speed_kn * math.sin(angle_diff))

    @staticmethod
    def calculate_headwind(
        wind_direction: float, wind_speed_kn: float, runway_heading: float
    ) -> float:
        angle_diff = math.radians(wind_direction - runway_heading)
        return wind_speed_kn * math.cos(angle_diff)
