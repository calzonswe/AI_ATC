from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from .base import BaseController
from .models import (
    ControllerState,
    PatternConflict,
    TowerState,
    TrafficAdvisory,
    TrafficAdvisoryType,
    VfrCircuitProgress,
)


@dataclass
class RunwayStatus:
    runway_id: str
    is_occupied: bool = False
    last_departure_time_s: float = 0.0
    last_arrival_time_s: float = 0.0
    current_departure_callsign: Optional[str] = None
    current_arrival_callsign: Optional[str] = None


class TowerController(BaseController):
    runways: Dict[str, RunwayStatus]
    _aircraft_states: Dict[str, TowerState]
    _approaching_aircraft: Set[str]
    _aircraft_runways: Dict[str, str]

    def __init__(
        self,
        callsign: str,
        frequency: float,
        sector_id: str,
        airport_icao: str,
        runways: Optional[List[str]] = None,
    ):
        super().__init__(callsign, frequency, sector_id, airport_icao=airport_icao)
        self.runways = {
            rwy: RunwayStatus(runway_id=rwy)
            for rwy in (runways or ["01L/19R"])
        }
        self._aircraft_states: Dict[str, TowerState] = {}
        self._approaching_aircraft: Set[str] = set()
        self._aircraft_runways: Dict[str, str] = {}
        self._wind_info: str = ""
        self._vfr_circuits: Dict[str, VfrCircuitProgress] = {}
        self._departure_separation_s: float = 60.0
        self._arrival_separation_s: float = 60.0
        self._departure_arrival_separation_s: float = 120.0
        self._arrival_departure_separation_s: float = 60.0
        self._extended_downwind: Set[str] = set()
        self._sequence_numbers: Dict[str, int] = {}
        self._next_sequence_number: int = 1
        self._pattern_separation_s: float = 30.0

    def get_aircraft_tower_state(self, callsign: str) -> Optional[TowerState]:
        return self._aircraft_states.get(callsign)

    # ── Wind ──

    def update_wind(self, wind_info: str) -> None:
        self._wind_info = wind_info

    # ── Separation Queries ──

    def can_clear_takeoff(self, runway: str) -> bool:
        status = self.runways.get(runway)
        if not status:
            return False
        if status.is_occupied:
            return False
        now = time.time()
        if now - status.last_departure_time_s < self._departure_separation_s:
            return False
        if now - status.last_arrival_time_s < self._departure_arrival_separation_s:
            return False
        return True

    def can_clear_landing(self, runway: str) -> bool:
        status = self.runways.get(runway)
        if not status:
            return False
        if status.is_occupied:
            return False
        if status.current_departure_callsign is not None:
            return False
        return True

    # ── Accept from Ground ──

    def accept_from_ground(self, callsign: str, runway: str) -> None:
        self.accept_aircraft(callsign)
        self._aircraft_states[callsign] = TowerState.IDLE
        self._aircraft_runways[callsign] = runway
        self.log_status_change(
            callsign, None, TowerState.IDLE.value,
            command_type="contact_tower",
        )
        self._issue_command(
            "contact_tower",
            callsign,
            frequency=self.frequency,
            instruction=f"Contact Tower on {self.frequency}",
        )

    # ── Line Up ──

    def line_up(self, callsign: str, runway: str) -> None:
        if not self.is_controlling(callsign):
            self.accept_aircraft(callsign)
        prev = self._aircraft_states.get(callsign)
        self._aircraft_states[callsign] = TowerState.LINE_UP
        self._aircraft_runways[callsign] = runway
        self.set_clearance_state(callsign, "line_up", runway=runway)
        self.log_status_change(
            callsign, prev.value if prev else None,
            TowerState.LINE_UP.value,
            command_type="line_up",
        )
        self._issue_command(
            "line_up",
            callsign,
            runway=runway,
            instruction=f"Line up and wait runway {runway}",
        )

    # ── Takeoff ──

    def clear_takeoff(self, callsign: str, runway: str, wind_info: str = "") -> None:
        if not self.is_controlling(callsign):
            self.accept_aircraft(callsign)
        prev = self._aircraft_states.get(callsign)
        self._aircraft_states[callsign] = TowerState.TAKEOFF_CLEARED
        self._aircraft_runways[callsign] = runway
        wind = wind_info or self._wind_info
        self.set_clearance_state(
            callsign, "takeoff", runway=runway, wind=wind,
        )
        self.log_status_change(
            callsign, prev.value if prev else None,
            TowerState.TAKEOFF_CLEARED.value,
            command_type="takeoff",
        )
        if runway in self.runways:
            self.runways[runway].is_occupied = True
            self.runways[runway].current_departure_callsign = callsign
        wind_str = f", wind {wind}" if wind else ""
        self._issue_command(
            "takeoff",
            callsign,
            runway=runway,
            instruction=f"Cleared for takeoff runway {runway}{wind_str}",
        )

    def departure_airborne(self, callsign: str, runway: str, time_s: float) -> None:
        if callsign in self._aircraft_states:
            del self._aircraft_states[callsign]
        self._aircraft_runways.pop(callsign, None)
        self.revoke_clearance(callsign)
        self.release_aircraft(callsign)
        if runway in self.runways:
            self.runways[runway].is_occupied = False
            self.runways[runway].last_departure_time_s = time_s
            self.runways[runway].current_departure_callsign = None
        self._propose_handoff(
            callsign,
            to_controller=f"{self.airport_icao}_DEP",
            frequency=0.0,
        )

    # ── Landing ──

    def clear_landing(self, callsign: str, runway: str) -> None:
        if not self.can_clear_landing(runway):
            self.go_around(
                callsign, runway,
                reason=f"runway {runway} not available",
            )
            return
        self.accept_aircraft(callsign)
        prev = self._aircraft_states.get(callsign)
        self._aircraft_states[callsign] = TowerState.LANDING_CLEARED
        self._aircraft_runways[callsign] = runway
        self._approaching_aircraft.add(callsign)
        self.set_clearance_state(callsign, "landing", runway=runway)
        self.log_status_change(
            callsign, prev.value if prev else None,
            TowerState.LANDING_CLEARED.value,
            command_type="landing",
        )
        if runway in self.runways:
            self.runways[runway].is_occupied = True
            self.runways[runway].current_arrival_callsign = callsign
        self._issue_command(
            "landing",
            callsign,
            runway=runway,
            instruction=f"Cleared to land runway {runway}",
        )

    def arrival_landed(self, callsign: str, runway: str, time_s: float) -> None:
        self._approaching_aircraft.discard(callsign)
        if callsign in self._aircraft_states:
            del self._aircraft_states[callsign]
        self._aircraft_runways.pop(callsign, None)
        self.revoke_clearance(callsign)
        self.release_aircraft(callsign)
        if runway in self.runways:
            self.runways[runway].is_occupied = False
            self.runways[runway].last_arrival_time_s = time_s
            self.runways[runway].current_arrival_callsign = None
        self._propose_handoff(
            callsign,
            to_controller=f"{self.airport_icao}_GND",
            frequency=0.0,
        )

    # ── Go Around ──

    def go_around(self, callsign: str, runway: str, reason: str = "") -> None:
        if not self.is_controlling(callsign):
            self.accept_aircraft(callsign)
        prev = self._aircraft_states.get(callsign)
        self._aircraft_states[callsign] = TowerState.GO_AROUND
        self._aircraft_runways[callsign] = runway
        self._approaching_aircraft.discard(callsign)
        self.log_status_change(
            callsign, prev.value if prev else None,
            TowerState.GO_AROUND.value,
            command_type="go_around",
        )
        self.revoke_clearance(callsign)
        if runway in self.runways:
            occupant = self.runways[runway].current_arrival_callsign
            if occupant == callsign:
                self.runways[runway].is_occupied = False
                self.runways[runway].current_arrival_callsign = None
        msg = f"Go around{', ' + reason if reason else ''}"
        self._issue_command(
            "go_around",
            callsign,
            runway=runway,
            reason=reason,
            instruction=msg,
        )

    # ── Traffic Advisories ──

    def issue_traffic_advisory(
        self,
        callsign: str,
        traffic_callsign: str,
        position: str = "",
    ) -> TrafficAdvisory:
        advisory = TrafficAdvisory(
            advisory_type=TrafficAdvisoryType.TRAFFIC_IN_VICINITY,
            target_callsign=callsign,
            traffic_callsign=traffic_callsign,
            position=position,
            issued_by=self.callsign,
        )
        pos = f" {position}" if position else ""
        self._issue_command(
            "traffic_advisory",
            callsign,
            traffic=traffic_callsign,
            position=position,
            instruction=(
                f"{callsign}, traffic{pos}"
                f" is a {traffic_callsign}"
            ),
        )
        return advisory

    def issue_circuit_instruction(
        self,
        callsign: str,
        runway: str,
        circuit_direction: str = "left",
    ) -> None:
        self.accept_aircraft(callsign)
        dir_label = "left-hand" if circuit_direction == "left" else "right-hand"
        self._issue_command(
            "circuit",
            callsign,
            runway=runway,
            circuit_direction=circuit_direction,
            instruction=(
                f"{callsign}, {dir_label} circuit,"
                f" runway {runway}"
            ),
        )

    def report_traffic(
        self,
        callsign: str,
        traffic_callsign: str,
        clock_position: str,
        distance: str,
        altitude: str = "",
    ) -> None:
        alt = f", {altitude}" if altitude else ""
        self._issue_command(
            "traffic_info",
            callsign,
            traffic=traffic_callsign,
            clock=clock_position,
            distance=distance,
            instruction=(
                f"{callsign}, traffic {clock_position}"
                f" o'clock, {distance}{alt}"
            ),
        )

    # ── Departure Handoff ──

    def release_to_departure(self, callsign: str) -> None:
        self._aircraft_states.pop(callsign, None)
        self._aircraft_runways.pop(callsign, None)
        self.revoke_clearance(callsign)
        self.release_aircraft(callsign)

    # ── VFR Pattern Operations ──

    def init_vfr_circuit(
        self, callsign: str, runway: str,
        pattern_direction: str = "left",
    ) -> VfrCircuitProgress:
        self.accept_aircraft(callsign)
        progress = VfrCircuitProgress(
            callsign=callsign,
            runway=runway,
            pattern_direction=pattern_direction,
            joined_at_s=time.time(),
        )
        self._vfr_circuits[callsign] = progress
        return progress

    def report_downwind(self, callsign: str, runway: str) -> None:
        if not self.is_controlling(callsign):
            self.accept_aircraft(callsign)
        prev = self._aircraft_states.get(callsign)
        self._aircraft_states[callsign] = TowerState.DOWNWIND
        self._aircraft_runways[callsign] = runway
        if callsign in self._vfr_circuits:
            self._vfr_circuits[callsign].current_leg = "downwind"
        self.log_status_change(
            callsign, prev.value if prev else None,
            TowerState.DOWNWIND.value,
            command_type="downwind",
        )
        self._issue_command(
            "downwind",
            callsign,
            runway=runway,
            instruction=f"{callsign}, runway {runway}, report base",
        )

    def report_base(self, callsign: str, runway: str) -> None:
        if not self.is_controlling(callsign):
            return
        prev = self._aircraft_states.get(callsign)
        self._aircraft_states[callsign] = TowerState.BASE
        self._aircraft_runways[callsign] = runway
        if callsign in self._vfr_circuits:
            self._vfr_circuits[callsign].current_leg = "base"
        self.log_status_change(
            callsign, prev.value if prev else None,
            TowerState.BASE.value,
            command_type="base",
        )
        self._issue_command(
            "base",
            callsign,
            runway=runway,
            instruction=f"{callsign}, runway {runway}, report final",
        )

    def report_final(self, callsign: str, runway: str) -> None:
        if not self.is_controlling(callsign):
            return
        prev = self._aircraft_states.get(callsign)
        self._aircraft_states[callsign] = TowerState.FINAL_APPROACH
        self._aircraft_runways[callsign] = runway
        if callsign in self._vfr_circuits:
            self._vfr_circuits[callsign].current_leg = "final"
        self.log_status_change(
            callsign, prev.value if prev else None,
            TowerState.FINAL_APPROACH.value,
            command_type="final",
        )
        self._issue_command(
            "final",
            callsign,
            runway=runway,
            instruction=f"{callsign}, runway {runway}, cleared to land",
        )

    def clear_touch_and_go(self, callsign: str, runway: str) -> None:
        if not self.is_controlling(callsign):
            self.accept_aircraft(callsign)
        prev = self._aircraft_states.get(callsign)
        self._aircraft_states[callsign] = TowerState.TOUCH_AND_GO
        self._aircraft_runways[callsign] = runway
        self.set_clearance_state(callsign, "touch_and_go", runway=runway)
        self.log_status_change(
            callsign, prev.value if prev else None,
            TowerState.TOUCH_AND_GO.value,
            command_type="touch_and_go",
        )
        if runway in self.runways:
            self.runways[runway].is_occupied = True
        self._issue_command(
            "touch_and_go",
            callsign,
            runway=runway,
            instruction=f"{callsign}, cleared touch-and-go, runway {runway}",
        )

    def clear_option(self, callsign: str, runway: str) -> None:
        if not self.is_controlling(callsign):
            self.accept_aircraft(callsign)
        prev = self._aircraft_states.get(callsign)
        self._aircraft_states[callsign] = TowerState.OPTION
        self._aircraft_runways[callsign] = runway
        self.set_clearance_state(callsign, "option", runway=runway)
        self.log_status_change(
            callsign, prev.value if prev else None,
            TowerState.OPTION.value,
            command_type="option",
        )
        if runway in self.runways:
            self.runways[runway].is_occupied = True
        self._issue_command(
            "option",
            callsign,
            runway=runway,
            instruction=f"{callsign}, cleared option, runway {runway}",
        )

    def clear_low_approach(self, callsign: str, runway: str) -> None:
        if not self.is_controlling(callsign):
            self.accept_aircraft(callsign)
        prev = self._aircraft_states.get(callsign)
        self._aircraft_states[callsign] = TowerState.LOW_APPROACH
        self._aircraft_runways[callsign] = runway
        self.set_clearance_state(callsign, "low_approach", runway=runway)
        self.log_status_change(
            callsign, prev.value if prev else None,
            TowerState.LOW_APPROACH.value,
            command_type="low_approach",
        )
        self._issue_command(
            "low_approach",
            callsign,
            runway=runway,
            instruction=f"{callsign}, cleared low approach, runway {runway}",
        )

    def clear_stop_and_go(self, callsign: str, runway: str) -> None:
        if not self.is_controlling(callsign):
            self.accept_aircraft(callsign)
        prev = self._aircraft_states.get(callsign)
        self._aircraft_states[callsign] = TowerState.STOP_AND_GO
        self._aircraft_runways[callsign] = runway
        self.set_clearance_state(callsign, "stop_and_go", runway=runway)
        self.log_status_change(
            callsign, prev.value if prev else None,
            TowerState.STOP_AND_GO.value,
            command_type="stop_and_go",
        )
        if runway in self.runways:
            self.runways[runway].is_occupied = True
        self._issue_command(
            "stop_and_go",
            callsign,
            runway=runway,
            instruction=f"{callsign}, cleared stop-and-go, runway {runway}",
        )

    def clear_full_stop(self, callsign: str, runway: str) -> None:
        if not self.can_clear_landing(runway):
            self.go_around(
                callsign, runway,
                reason=f"runway {runway} not available",
            )
            return
        self.accept_aircraft(callsign)
        prev = self._aircraft_states.get(callsign)
        self._aircraft_states[callsign] = TowerState.FULL_STOP
        self._aircraft_runways[callsign] = runway
        self._approaching_aircraft.add(callsign)
        self.set_clearance_state(callsign, "full_stop", runway=runway)
        self.log_status_change(
            callsign, prev.value if prev else None,
            TowerState.FULL_STOP.value,
            command_type="full_stop",
        )
        if runway in self.runways:
            self.runways[runway].is_occupied = True
            self.runways[runway].current_arrival_callsign = callsign
        self._issue_command(
            "full_stop",
            callsign,
            runway=runway,
            instruction=f"{callsign}, cleared full stop, runway {runway}",
        )

    def issue_overhead_join(
        self, callsign: str, runway: str,
        pattern_direction: str = "left",
        break_alt_ft: int = 1000,
    ) -> None:
        if not self.is_controlling(callsign):
            self.accept_aircraft(callsign)
        prev = self._aircraft_states.get(callsign)
        self._aircraft_states[callsign] = TowerState.OVERHEAD_JOIN
        self._aircraft_runways[callsign] = runway
        dir_label = "left-hand" if pattern_direction == "left" else "right-hand"
        progress = self._vfr_circuits.get(callsign)
        if not progress:
            progress = self.init_vfr_circuit(callsign, runway, pattern_direction)
        progress.current_leg = "overhead"
        self.log_status_change(
            callsign, prev.value if prev else None,
            TowerState.OVERHEAD_JOIN.value,
            command_type="overhead_join",
        )
        self._issue_command(
            "overhead_join",
            callsign,
            runway=runway,
            pattern_direction=pattern_direction,
            instruction=(
                f"{callsign}, overhead join approved,"
                f" runway {runway}, break {dir_label}"
                f" at {break_alt_ft} feet"
            ),
        )

    def issue_pattern_entry(
        self, callsign: str, runway: str,
        entry_point: str = "downwind",
        pattern_direction: str = "left",
    ) -> None:
        self.accept_aircraft(callsign)
        dir_label = "left-hand" if pattern_direction == "left" else "right-hand"
        self.init_vfr_circuit(callsign, runway, pattern_direction)
        self._issue_command(
            "pattern_entry",
            callsign,
            runway=runway,
            entry_point=entry_point,
            instruction=(
                f"{callsign}, enter {dir_label} pattern,"
                f" runway {runway}, report {entry_point}"
            ),
        )

    def issue_pattern_exit(self, callsign: str, runway: str) -> None:
        if not self.is_controlling(callsign):
            return
        progress = self._vfr_circuits.get(callsign)
        dir_label = "left-hand" if (progress and progress.pattern_direction == "left") else "right-hand"
        self._vfr_circuits.pop(callsign, None)
        self._issue_command(
            "pattern_exit",
            callsign,
            runway=runway,
            instruction=(
                f"{callsign}, exit {dir_label} pattern,"
                f" runway {runway}"
            ),
        )

    def circuit_touch_and_go_complete(self, callsign: str, runway: str) -> None:
        progress = self._vfr_circuits.get(callsign)
        if progress:
            progress.circuit_count += 1
            progress.touch_and_go_count += 1
            progress.current_leg = "downwind"
        self._aircraft_states[callsign] = TowerState.DOWNWIND
        if runway in self.runways:
            self.runways[runway].is_occupied = False
        self.revoke_clearance(callsign)
        self._issue_command(
            "circuit_continue",
            callsign,
            runway=runway,
            instruction=f"{callsign}, continue the pattern, report downwind",
        )

    def circuit_full_stop_complete(self, callsign: str, runway: str) -> None:
        self._vfr_circuits.pop(callsign, None)
        self._approaching_aircraft.discard(callsign)
        if callsign in self._aircraft_states:
            del self._aircraft_states[callsign]
        self._aircraft_runways.pop(callsign, None)
        self.revoke_clearance(callsign)
        self.release_aircraft(callsign)
        if runway in self.runways:
            self.runways[runway].is_occupied = False
            self.runways[runway].last_arrival_time_s = time.time()
            self.runways[runway].current_arrival_callsign = None
        self._propose_handoff(
            callsign,
            to_controller=f"{self.airport_icao}_GND",
            frequency=0.0,
        )

    # ── Multi-Aircraft Pattern Management ──

    def get_pattern_aircraft_on_leg(self, runway: str, leg: str) -> List[str]:
        result: List[str] = []
        for callsign, progress in self._vfr_circuits.items():
            if progress.runway == runway and progress.current_leg == leg:
                result.append(callsign)
        return result

    def get_all_pattern_aircraft(self, runway: str) -> Dict[str, VfrCircuitProgress]:
        return {
            cs: p for cs, p in self._vfr_circuits.items()
            if p.runway == runway
        }

    def issue_extend_downwind(self, callsign: str, runway: str) -> None:
        if not self.is_controlling(callsign):
            return
        if self._aircraft_states.get(callsign) != TowerState.DOWNWIND:
            return
        self._extended_downwind.add(callsign)
        self._issue_command(
            "extend_downwind",
            callsign,
            runway=runway,
            instruction=f"{callsign}, extend downwind, runway {runway}",
        )

    def cancel_extend_downwind(self, callsign: str, runway: str) -> None:
        self._extended_downwind.discard(callsign)
        self._issue_command(
            "cancel_extend_downwind",
            callsign,
            runway=runway,
            instruction=f"{callsign}, turn base now, runway {runway}",
        )

    def sequence_aircraft(self, callsign: str, runway: str) -> int:
        seq = self._next_sequence_number
        self._next_sequence_number += 1
        self._sequence_numbers[callsign] = seq
        if seq == 1:
            self._issue_command(
                "sequence",
                callsign,
                runway=runway,
                sequence=seq,
                instruction=f"{callsign}, number {seq}",
            )
        else:
            follow = ""
            for cs in sorted(self._sequence_numbers, key=lambda c: self._sequence_numbers[c]):
                if self._sequence_numbers.get(cs) == seq - 1:
                    follow = cs
                    break
            if follow:
                self._issue_command(
                    "sequence",
                    callsign,
                    runway=runway,
                    sequence=seq,
                    follow=follow,
                    instruction=f"{callsign}, number {seq}, follow {follow}",
                )
            else:
                self._issue_command(
                    "sequence",
                    callsign,
                    runway=runway,
                    sequence=seq,
                    instruction=f"{callsign}, number {seq}",
                )
        return seq

    def detect_pattern_conflicts(self, runway: str) -> List[PatternConflict]:
        conflicts: List[PatternConflict] = []
        pattern = self.get_all_pattern_aircraft(runway)
        callsigns = list(pattern.keys())
        if not callsigns:
            return conflicts
        for leg in ("downwind", "base", "final"):
            on_leg = [cs for cs in callsigns if pattern[cs].current_leg == leg]
            if len(on_leg) > 1:
                for i in range(len(on_leg) - 1):
                    severity = "critical" if leg == "final" else "warning"
                    conflicts.append(PatternConflict(
                        runway=runway,
                        leg=leg,
                        aircraft_a=on_leg[i],
                        aircraft_b=on_leg[i + 1],
                        conflict_type="same_leg",
                        severity=severity,
                        recommendation=(
                            f"Go around {on_leg[i + 1]}, traffic ahead on {leg}"
                            if severity == "critical"
                            else f"Check spacing between {on_leg[i]} and "
                                 f"{on_leg[i + 1]} on {leg}"
                        ),
                    ))
        for cs in list(self._approaching_aircraft):
            if self._aircraft_runways.get(cs) != runway:
                continue
            for pc in callsigns:
                if pc == cs:
                    continue
                if pattern[pc].current_leg == "final":
                    conflicts.append(PatternConflict(
                        runway=runway,
                        leg="final",
                        aircraft_a=cs,
                        aircraft_b=pc,
                        conflict_type="merge",
                        severity="critical",
                        recommendation=(
                            f"Go around {pc}, traffic on final ahead"
                        ),
                    ))
        return conflicts

    # ── Process: Automated Conflict Detection ──

    def process(self, dt: float, context: Dict[str, Any]) -> None:
        for callsign in list(self._approaching_aircraft):
            state = self._aircraft_states.get(callsign)
            if state not in (TowerState.LANDING_CLEARED, TowerState.FULL_STOP):
                self._approaching_aircraft.discard(callsign)
                continue
            runway = self._aircraft_runways.get(callsign, "")
            status = self.runways.get(runway)
            if status is None:
                continue
            if not status.is_occupied:
                continue
            occupant = (
                status.current_departure_callsign
                or status.current_arrival_callsign
            )
            if occupant and occupant != callsign:
                self.go_around(
                    callsign,
                    runway,
                    reason=f"runway occupied by {occupant}",
                )
        processed_runways: Set[str] = set()
        for callsign in list(self._vfr_circuits.keys()):
            progress = self._vfr_circuits[callsign]
            if progress.runway in processed_runways:
                continue
            processed_runways.add(progress.runway)
            conflicts = self.detect_pattern_conflicts(progress.runway)
            for conflict in conflicts:
                if conflict.conflict_type == "merge" and conflict.severity == "critical":
                    target = conflict.aircraft_a
                    if target in self._aircraft_states:
                        self.go_around(
                            target,
                            conflict.runway,
                            reason=conflict.recommendation,
                        )
                        break
