from __future__ import annotations

import math
from typing import Dict, List, Optional

from shapely.geometry import Point

from runtime.sector import AirspaceVolume, SectorAssignment
from pubsub import EventBus, EventType


class SectorManager:
    def __init__(self, event_bus: Optional[EventBus] = None) -> None:
        self._sectors: Dict[int, AirspaceVolume] = {}
        self._assignments: Dict[str, SectorAssignment] = {}
        self._aircraft_sector: Dict[str, int] = {}
        self._event_bus = event_bus

    def add_sector(self, volume: AirspaceVolume) -> None:
        self._sectors[volume.sector_id] = volume
        self._assignments[volume.sector_id] = SectorAssignment(
            sector_id=volume.sector_id,
        )

    def remove_sector(self, sector_id: int) -> None:
        self._sectors.pop(sector_id, None)
        self._assignments.pop(sector_id, None)
        removed = [
            cs for cs, sid in self._aircraft_sector.items() if sid == sector_id
        ]
        for cs in removed:
            del self._aircraft_sector[cs]

    def find_sector_for_position(
        self, lat: float, lon: float, alt_ft: float
    ) -> Optional[int]:
        point = Point(lon, lat)
        for sid, vol in self._sectors.items():
            if vol.floor_ft <= alt_ft <= vol.ceiling_ft:
                if vol.polygon.contains(point):
                    return sid
        return None

    def assign_aircraft_to_sector(
        self, callsign: str, sector_id: int
    ) -> None:
        old_sector_id = self._aircraft_sector.get(callsign)
        if old_sector_id == sector_id:
            return
        if old_sector_id is not None:
            old_assignment = self._assignments.get(old_sector_id)
            if old_assignment and callsign in old_assignment.aircraft_callsigns:
                old_assignment.aircraft_callsigns.remove(callsign)
            if self._event_bus:
                self._event_bus.publish(
                    EventType.AIRCRAFT_LEFT_SECTOR,
                    {
                        "callsign": callsign,
                        "sector_id": old_sector_id,
                    },
                    source="SectorManager",
                )
        assignment = self._assignments.get(sector_id)
        if assignment and callsign not in assignment.aircraft_callsigns:
            assignment.aircraft_callsigns.append(callsign)
        self._aircraft_sector[callsign] = sector_id
        if self._event_bus:
            self._event_bus.publish(
                EventType.AIRCRAFT_ENTERED_SECTOR,
                {
                    "callsign": callsign,
                    "sector_id": sector_id,
                },
                source="SectorManager",
            )

    def get_aircraft_in_sector(self, sector_id: int) -> list[str]:
        assignment = self._assignments.get(sector_id)
        return list(assignment.aircraft_callsigns) if assignment else []

    def get_sector_of_aircraft(self, callsign: str) -> Optional[int]:
        return self._aircraft_sector.get(callsign)

    def get_all_sectors(self) -> list[AirspaceVolume]:
        return list(self._sectors.values())

    def get_sector_volume(self, sector_id: int) -> Optional[AirspaceVolume]:
        return self._sectors.get(sector_id)

    def update_aircraft_position(
        self, callsign: str, lat: float, lon: float, alt_ft: float
    ) -> int:
        new_sector = self.find_sector_for_position(lat, lon, alt_ft)
        if new_sector is None:
            old = self._aircraft_sector.pop(callsign, None)
            if old is not None:
                old_assignment = self._assignments.get(old)
                if old_assignment and callsign in old_assignment.aircraft_callsigns:
                    old_assignment.aircraft_callsigns.remove(callsign)
                if self._event_bus:
                    self._event_bus.publish(
                        EventType.AIRCRAFT_LEFT_SECTOR,
                        {
                            "callsign": callsign,
                            "sector_id": old,
                        },
                        source="SectorManager",
                    )
            return -1
        self.assign_aircraft_to_sector(callsign, new_sector)
        return new_sector

    def set_controller(self, sector_id: int, callsign: str) -> None:
        assignment = self._assignments.get(sector_id)
        if assignment:
            assignment.controller_callsign = callsign

    def set_frequency(self, sector_id: int, freq_mhz: float) -> None:
        assignment = self._assignments.get(sector_id)
        if assignment:
            assignment.frequency_mhz = freq_mhz

    def get_all_assignments(self) -> list[SectorAssignment]:
        return list(self._assignments.values())
