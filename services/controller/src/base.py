from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from .models import (
    AircraftHandoff,
    ClearanceState,
    ControllerCommand,
    ControllerState,
    FlightStatusRecord,
)


class BaseController(ABC):
    callsign: str
    frequency: float
    sector_id: str
    airport_icao: Optional[str]

    def __init__(
        self,
        callsign: str,
        frequency: float,
        sector_id: str,
        airport_icao: Optional[str] = None,
    ):
        self.callsign = callsign
        self.frequency = frequency
        self.sector_id = sector_id
        self.airport_icao = airport_icao
        self._controlled_aircraft: List[str] = []
        self._state = ControllerState.IDLE
        self._pending_commands: List[ControllerCommand] = []
        self._pending_handoffs: List[AircraftHandoff] = []
        self._flight_history: Dict[str, List[FlightStatusRecord]] = {}
        self._pending_clearances: Dict[str, ClearanceState] = {}

    @property
    def state(self) -> ControllerState:
        return self._state

    @state.setter
    def state(self, value: ControllerState) -> None:
        self._state = value

    @property
    def controlled_aircraft(self) -> List[str]:
        return list(self._controlled_aircraft)

    @property
    def aircraft_count(self) -> int:
        return len(self._controlled_aircraft)

    def is_controlling(self, callsign: str) -> bool:
        return callsign in self._controlled_aircraft

    def accept_aircraft(self, callsign: str) -> None:
        if callsign not in self._controlled_aircraft:
            self._controlled_aircraft.append(callsign)

    def release_aircraft(self, callsign: str) -> bool:
        if callsign in self._controlled_aircraft:
            self._controlled_aircraft.remove(callsign)
            return True
        return False

    def get_pending_commands(self) -> List[ControllerCommand]:
        cmds = list(self._pending_commands)
        self._pending_commands.clear()
        return cmds

    def get_pending_handoffs(self) -> List[AircraftHandoff]:
        hofs = list(self._pending_handoffs)
        self._pending_handoffs.clear()
        return hofs

    def _issue_command(
        self, cmd_type: str, target: str, **data: Any
    ) -> ControllerCommand:
        cmd = ControllerCommand(
            command_type=cmd_type,
            target_callsign=target,
            source=self.callsign,
            data=data,
        )
        self._pending_commands.append(cmd)
        return cmd

    def _propose_handoff(
        self, callsign: str, to_controller: str, frequency: float
    ) -> AircraftHandoff:
        handoff = AircraftHandoff(
            callsign=callsign,
            from_controller=self.callsign,
            to_controller=to_controller,
            frequency=frequency,
        )
        self._pending_handoffs.append(handoff)
        return handoff

    def log_status_change(
        self,
        callsign: str,
        previous_state: Optional[str],
        new_state: str,
        command_type: Optional[str] = None,
        timestamp_s: Optional[float] = None,
    ) -> FlightStatusRecord:
        record = FlightStatusRecord(
            timestamp_s=timestamp_s or time.time(),
            callsign=callsign,
            controller_callsign=self.callsign,
            previous_state=previous_state,
            new_state=new_state,
            command_type=command_type,
        )
        if callsign not in self._flight_history:
            self._flight_history[callsign] = []
        self._flight_history[callsign].append(record)
        return record

    def get_aircraft_history(
        self, callsign: str
    ) -> List[FlightStatusRecord]:
        return list(self._flight_history.get(callsign, []))

    def get_all_history(self) -> Dict[str, List[FlightStatusRecord]]:
        return dict(self._flight_history)

    def clear_history(self, callsign: Optional[str] = None) -> None:
        if callsign:
            self._flight_history.pop(callsign, None)
        else:
            self._flight_history.clear()

    def set_clearance_state(
        self,
        callsign: str,
        clearance_type: str,
        **details: Any,
    ) -> ClearanceState:
        clearance = ClearanceState(
            clearance_type=clearance_type,
            issued_by=self.callsign,
            is_active=True,
            acknowledged=False,
            issued_at_s=time.time(),
            details=details,
        )
        self._pending_clearances[callsign] = clearance
        return clearance

    def get_clearance_state(self, callsign: str) -> Optional[ClearanceState]:
        return self._pending_clearances.get(callsign)

    def acknowledge_clearance(self, callsign: str) -> bool:
        clearance = self._pending_clearances.get(callsign)
        if clearance and clearance.is_active:
            clearance.acknowledged = True
            return True
        return False

    def revoke_clearance(self, callsign: str) -> bool:
        clearance = self._pending_clearances.get(callsign)
        if clearance and clearance.is_active:
            clearance.is_active = False
            return True
        return False

    def report_holding_short(self, callsign: str, runway: str) -> None:
        self.log_status_change(callsign, None, "holding_short", "holding_short")

    def departure_airborne(self, callsign: str, runway: str, timestamp_s: float) -> None:
        self.log_status_change(callsign, None, "airborne", "departure",
                               timestamp_s=timestamp_s)

    def arrival_landed(self, callsign: str, runway: str, timestamp_s: float) -> None:
        self.log_status_change(callsign, None, "landed", "arrival",
                               timestamp_s=timestamp_s)

    def handoff_to_center(self, callsign: str, center_callsign: str, frequency: float) -> None:
        self._propose_handoff(callsign, center_callsign, frequency)

    def handoff_to_approach(self, callsign: str, approach_callsign: str, frequency: float) -> None:
        self._propose_handoff(callsign, approach_callsign, frequency)

    def handoff_to_tower(self, callsign: str, tower_callsign: str, frequency: float) -> None:
        self._propose_handoff(callsign, tower_callsign, frequency)

    @abstractmethod
    def process(self, dt: float, context: Dict[str, Any]) -> None:
        ...
