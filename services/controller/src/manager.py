from __future__ import annotations

from typing import Any, Dict, List, Optional

from .approach import ApproachController
from .atis import AtisController
from .base import BaseController
from .center import CenterController
from .departure import DepartureController
from .ground import GroundController
from .models import (
    AircraftHandoff,
    ClearanceState,
    ControllerCommand,
    ControllerPosition,
    FlightStatusRecord,
)
from .tower import TowerController


class ControllerManager:
    def __init__(self) -> None:
        self._controllers: Dict[str, BaseController] = {}
        self._position_map: Dict[ControllerPosition, str] = {}
        self._airport_map: Dict[str, Dict[ControllerPosition, str]] = {}

    def add_controller(self, controller: BaseController) -> None:
        self._controllers[controller.callsign] = controller
        self._find_position(controller)

    _POSITION_SUFFIXES: Dict[ControllerPosition, str] = {
        ControllerPosition.GROUND: "_GND",
        ControllerPosition.TOWER: "_TWR",
        ControllerPosition.DEPARTURE: "_DEP",
        ControllerPosition.APPROACH: "_APP",
        ControllerPosition.CENTER: "_CTR",
        ControllerPosition.ATIS: "_ATIS",
    }

    def _find_position(self, controller: BaseController) -> None:
        upper_cs = controller.callsign.upper()
        for pos, suffix in self._POSITION_SUFFIXES.items():
            if suffix in upper_cs:
                self._position_map[pos] = controller.callsign
                break
        icao = controller.airport_icao
        if icao:
            if icao not in self._airport_map:
                self._airport_map[icao] = {}
            for pos, suffix in self._POSITION_SUFFIXES.items():
                if suffix in upper_cs:
                    self._airport_map[icao][pos] = controller.callsign

    def get_controller(self, callsign: str) -> Optional[BaseController]:
        return self._controllers.get(callsign)

    def get_by_position(
        self, position: ControllerPosition, airport_icao: Optional[str] = None
    ) -> Optional[BaseController]:
        if airport_icao:
            if airport_icao in self._airport_map:
                cs = self._airport_map[airport_icao].get(position)
                if cs:
                    return self._controllers.get(cs)
            return None
        cs = self._position_map.get(position)
        return self._controllers.get(cs) if cs else None

    def get_controllers_for_airport(
        self, icao: str
    ) -> List[BaseController]:
        result: List[BaseController] = []
        for ctrl in self._controllers.values():
            if ctrl.airport_icao == icao:
                result.append(ctrl)
        return result

    @property
    def all_controllers(self) -> List[BaseController]:
        return list(self._controllers.values())

    @property
    def controller_count(self) -> int:
        return len(self._controllers)

    def process_all(self, dt: float, context: Dict[str, Any]) -> None:
        for ctrl in self._controllers.values():
            ctrl.process(dt, context)

    def collect_commands(self) -> List[ControllerCommand]:
        commands: List[ControllerCommand] = []
        for ctrl in self._controllers.values():
            commands.extend(ctrl.get_pending_commands())
        return commands

    def collect_handoffs(self) -> List[AircraftHandoff]:
        handoffs: List[AircraftHandoff] = []
        for ctrl in self._controllers.values():
            handoffs.extend(ctrl.get_pending_handoffs())
        return handoffs

    def route_handoff(self, handoff: AircraftHandoff) -> bool:
        target = self._controllers.get(handoff.to_controller)
        if not target:
            return False
        source = self._controllers.get(handoff.from_controller)
        if source:
            source.release_aircraft(handoff.callsign)
        target.accept_aircraft(handoff.callsign)
        handoff.accepted = True
        return True

    def create_from_db_config(
        self,
        airports: List[Dict[str, Any]],
        controllers: List[Dict[str, Any]],
    ) -> None:
        for ap in airports:
            icao = ap.get("icao_code", "")
            lat = ap.get("latitude", 0.0)
            lon = ap.get("longitude", 0.0)
            runways_raw = ap.get("runways", [])
            runway_ids = [
                r.get("identifier", "") for r in runways_raw if r.get("identifier")
            ]
            freqs_raw = ap.get("frequencies", [])

            freq_map: Dict[str, float] = {}
            for f in freqs_raw:
                ftype = f.get("type", "").lower()
                fmhz = f.get("frequency_mhz", 0.0)
                if ftype and fmhz > 0:
                    freq_map[ftype] = fmhz

            positions = [
                (ControllerPosition.GROUND, f"{icao}_GND", freq_map.get("ground", 121.8), True),
                (ControllerPosition.TOWER, f"{icao}_TWR", freq_map.get("tower", 118.5), True),
                (ControllerPosition.DEPARTURE, f"{icao}_DEP", freq_map.get("departure", 125.2), True),
                (ControllerPosition.APPROACH, f"{icao}_APP", freq_map.get("approach", 124.0), True),
                (ControllerPosition.ATIS, f"{icao}_ATIS", freq_map.get("atis", 128.425), True),
            ]
            for pos, cs, freq, _ in positions:
                if cs not in self._controllers:
                    ctrl = self._create_controller(pos, cs, freq, icao, runway_ids)
                    if ctrl:
                        self.add_controller(ctrl)

        for ctrl in controllers:
            cs = ctrl.get("callsign", "")
            if cs and cs not in self._controllers:
                freq = ctrl.get("frequency_mhz", 135.5)
                ctype = ctrl.get("type", "CENTER").upper()
                pos = self._type_to_position(ctype)
                ctrl_obj = self._create_controller(
                    pos, cs, freq,
                    airport_icao=ctrl.get("airport_icao"),
                    facility_name=ctrl.get("name", "Center"),
                )
                if ctrl_obj:
                    self.add_controller(ctrl_obj)

    def _create_controller(
        self,
        position: ControllerPosition,
        callsign: str,
        frequency: float,
        airport_icao: Optional[str] = None,
        runways: Optional[List[str]] = None,
        facility_name: str = "Center",
    ) -> Optional[BaseController]:
        if position == ControllerPosition.GROUND:
            if not airport_icao:
                return None
            return GroundController(callsign, frequency, f"{airport_icao}_GND", airport_icao)
        if position == ControllerPosition.TOWER:
            if not airport_icao:
                return None
            return TowerController(callsign, frequency, f"{airport_icao}_TWR", airport_icao, runways)
        if position == ControllerPosition.DEPARTURE:
            if not airport_icao:
                return None
            return DepartureController(callsign, frequency, f"{airport_icao}_DEP", airport_icao)
        if position == ControllerPosition.APPROACH:
            if not airport_icao:
                return None
            return ApproachController(callsign, frequency, f"{airport_icao}_APP", airport_icao)
        if position == ControllerPosition.ATIS:
            if not airport_icao:
                return None
            return AtisController(callsign, frequency, f"{airport_icao}_ATIS", airport_icao)
        if position == ControllerPosition.CENTER:
            return CenterController(callsign, frequency, f"{callsign}_CTR", facility_name)
        return None

    @staticmethod
    def _type_to_position(ctype: str) -> ControllerPosition:
        mapping = {
            "GROUND": ControllerPosition.GROUND,
            "TOWER": ControllerPosition.TOWER,
            "DEPARTURE": ControllerPosition.DEPARTURE,
            "APPROACH": ControllerPosition.APPROACH,
            "CENTER": ControllerPosition.CENTER,
            "ATIS": ControllerPosition.ATIS,
        }
        return mapping.get(ctype, ControllerPosition.CENTER)

    def get_all_history(self) -> Dict[str, List[FlightStatusRecord]]:
        combined: Dict[str, List[FlightStatusRecord]] = {}
        for ctrl in self._controllers.values():
            for cs, records in ctrl.get_all_history().items():
                if cs not in combined:
                    combined[cs] = []
                combined[cs].extend(records)
        return combined

    def get_aircraft_history(self, callsign: str) -> List[FlightStatusRecord]:
        records: List[FlightStatusRecord] = []
        for ctrl in self._controllers.values():
            records.extend(ctrl.get_aircraft_history(callsign))
        records.sort(key=lambda r: r.timestamp_s)
        return records

    def get_clearance_state(self, callsign: str) -> Optional[ClearanceState]:
        for ctrl in self._controllers.values():
            clearance = ctrl.get_clearance_state(callsign)
            if clearance:
                return clearance
        return None
