from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from managers.aircraft import AircraftManager
from managers.airport import AirportManager
from managers.conflict import ConflictManager
from managers.sector import SectorManager
from managers.weather import WeatherManager
from pubsub import EventBus, EventType
from runtime.aircraft import ActiveAircraft, AircraftState
from runtime.airport import AirportState
from settings import WorldSettings, settings as default_settings

logger = logging.getLogger(__name__)


class WorldEngine:
    def __init__(
        self,
        settings: Optional[WorldSettings] = None,
        event_bus: Optional[EventBus] = None,
    ) -> None:
        self.settings = settings or default_settings
        self.event_bus = event_bus or EventBus()
        self.start_time: float = 0.0

        self.aircraft_manager = AircraftManager(event_bus=self.event_bus)
        self.airport_manager = AirportManager(event_bus=self.event_bus)
        self.weather_manager = WeatherManager(event_bus=self.event_bus)
        self.sector_manager = SectorManager(event_bus=self.event_bus)
        self.conflict_manager = ConflictManager(
            event_bus=self.event_bus,
            lateral_separation_nm=self.settings.lateral_separation_nm,
            vertical_separation_ft=self.settings.vertical_separation_ft,
            terminal_lateral_separation_nm=self.settings.terminal_lateral_separation_nm,
        )

        self._initialized = False
        self._tick_count = 0

    def initialize(self) -> None:
        self.start_time = time.time()
        self._initialized = True
        logger.info("WorldEngine initialized")

    def process_telemetry(self, frame: dict) -> Optional[ActiveAircraft]:
        if not self._initialized:
            self.initialize()

        ac = self.aircraft_manager.add_or_update(frame)
        pos = frame.get("position", {})
        lat = pos.get("lat", ac.position.lat)
        lon = pos.get("lon", ac.position.lon)
        alt = pos.get("alt_msl", ac.position.alt_msl_ft)

        sector_id = self.sector_manager.update_aircraft_position(
            ac.callsign, lat, lon, alt
        )
        if sector_id >= 0:
            ac.current_sector_id = sector_id

        if self.settings.conflict_detection_enabled:
            all_ac = self.aircraft_manager.get_all()
            conflicts = self.conflict_manager.check_all(all_ac)
            if conflicts:
                logger.debug("Detected %d conflict(s)", len(conflicts))

        return ac

    def process_batch_telemetry(self, frames: list[dict]) -> list[ActiveAircraft]:
        results: list[ActiveAircraft] = []
        for frame in frames:
            ac = self.process_telemetry(frame)
            if ac:
                results.append(ac)
        return results

    def tick(self) -> None:
        self._tick_count += 1
        all_ac = self.aircraft_manager.get_all()

        for ac in all_ac:
            if not ac.trajectory:
                continue
            latest = ac.trajectory[-1]
            sector_id = self.sector_manager.update_aircraft_position(
                ac.callsign, latest.lat, latest.lon, latest.alt_msl_ft
            )
            if sector_id >= 0:
                ac.current_sector_id = sector_id

        if self.settings.conflict_detection_enabled:
            conflicts = self.conflict_manager.check_all(all_ac)

    def set_flight_plan(self, callsign: str, fp_data: dict) -> None:
        from runtime.aircraft import FlightPlan, FlightRules

        ac = self.aircraft_manager.get(callsign)
        if ac is None:
            return

        fr = fp_data.get("flight_rules", "IFR")
        ac.flight_plan = FlightPlan(
            departure=fp_data.get("departure", ""),
            arrival=fp_data.get("arrival", ""),
            alternate=fp_data.get("alternate"),
            route=fp_data.get("route", []),
            cruise_alt_ft=fp_data.get("cruise_alt_ft", 35000),
            cruise_speed_kn=fp_data.get("cruise_speed_kn", 450.0),
            flight_rules=FlightRules.IFR if fr == "IFR" else FlightRules.VFR,
            aircraft_type=fp_data.get("aircraft_type", "B738"),
        )

    def set_aircraft_state(self, callsign: str, state: str) -> None:
        try:
            new_state = AircraftState(state)
        except ValueError:
            logger.warning("Unknown aircraft state: %s", state)
            return
        ac = self.aircraft_manager.get(callsign)
        if ac:
            prev = ac.state
            ac.state = new_state
            ac.previous_state = prev
            self.event_bus.publish(
                EventType.AIRCRAFT_STATE_CHANGED,
                {
                    "callsign": callsign,
                    "from": prev.value,
                    "to": new_state.value,
                },
                source="WorldEngine",
            )

    def set_metar_from_dict(self, data: dict) -> None:
        self.weather_manager.set_metar_from_dict(data)

    def determine_airport_runways(self, icao: str) -> None:
        wind = self.weather_manager.get_wind(icao)
        if wind is None:
            return
        self.airport_manager.determine_active_runways(icao, wind)

    def get_state_summary(self) -> dict:
        return {
            "uptime_s": time.time() - self.start_time if self.start_time else 0.0,
            "tick_count": self._tick_count,
            "aircraft_count": self.aircraft_manager.count,
            "airport_count": len(self.airport_manager.get_all()),
            "weather_count": self.weather_manager.airport_count,
            "sector_count": len(self.sector_manager.get_all_sectors()),
            "initialized": self._initialized,
        }

    def get_aircraft_state(self, callsign: str) -> Optional[dict]:
        ac = self.aircraft_manager.get(callsign)
        if ac is None:
            return None
        return {
            "callsign": ac.callsign,
            "state": ac.state.value,
            "sector_id": ac.current_sector_id,
            "position": {
                "lat": ac.position.lat,
                "lon": ac.position.lon,
                "alt_msl": ac.position.alt_msl_ft,
            },
            "motion": {
                "groundspeed": ac.motion.groundspeed_kn,
                "vertical_speed": ac.motion.vertical_speed_fpm,
                "on_ground": ac.motion.on_ground,
            },
            "flight_plan": {
                "departure": ac.flight_plan.departure if ac.flight_plan else "",
                "arrival": ac.flight_plan.arrival if ac.flight_plan else "",
            }
            if ac.flight_plan
            else None,
        }

    def load_airport_from_db_model(
        self,
        icao: str,
        elevation_ft: int = 0,
        magnetic_var: float = 0.0,
        runways: Optional[List[Dict[str, Any]]] = None,
    ) -> AirportState:
        return self.airport_manager.load_airport(
            icao=icao,
            elevation_ft=elevation_ft,
            magnetic_var=magnetic_var,
            runways=runways,
        )

    def load_sector_from_db_model(
        self,
        sector_id: int,
        floor_ft: int,
        ceiling_ft: int,
        polygon_coords: List[List[float]],
        identifier: str = "",
    ) -> None:
        from shapely.geometry import Polygon
        from runtime.sector import AirspaceVolume

        volume = AirspaceVolume(
            sector_id=sector_id,
            floor_ft=floor_ft,
            ceiling_ft=ceiling_ft,
            polygon=Polygon(polygon_coords),
            identifier=identifier,
        )
        self.sector_manager.add_sector(volume)
