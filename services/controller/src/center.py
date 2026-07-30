from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from .base import BaseController
from .models import (
    AirwayAssignment,
    AltitudeChangeRequest,
    CenterState,
    ControllerState,
)


class CenterController(BaseController):
    facility_name: str
    _aircraft_states: Dict[str, CenterState]
    _airway_assignments: Dict[str, AirwayAssignment]
    _pending_altitude_requests: Dict[str, AltitudeChangeRequest]
    _last_sector_release_time: Dict[str, float]
    _tod_distance_nm: float

    def __init__(
        self,
        callsign: str,
        frequency: float,
        sector_id: str,
        facility_name: str = "Center",
        tod_distance_nm: float = 50.0,
    ):
        super().__init__(callsign, frequency, sector_id)
        self.facility_name = facility_name
        self._aircraft_states: Dict[str, CenterState] = {}
        self._airway_assignments: Dict[str, AirwayAssignment] = {}
        self._pending_altitude_requests: Dict[str, AltitudeChangeRequest] = {}
        self._last_sector_release_time: Dict[str, float] = {}
        self._tod_distance_nm = tod_distance_nm
        self._state = ControllerState.ACTIVE

    # ──────────────────────────────────────────
    # Queries
    # ──────────────────────────────────────────

    def get_aircraft_center_state(self, callsign: str) -> Optional[CenterState]:
        return self._aircraft_states.get(callsign)

    def get_airway_assignment(self, callsign: str) -> Optional[AirwayAssignment]:
        return self._airway_assignments.get(callsign)

    def get_pending_altitude_request(
        self, callsign: str,
    ) -> Optional[AltitudeChangeRequest]:
        return self._pending_altitude_requests.get(callsign)

    # ──────────────────────────────────────────
    # Accept from Departure
    # ──────────────────────────────────────────

    def accept_from_departure(self, callsign: str, alt_ft: float) -> None:
        self.accept_aircraft(callsign)
        self._aircraft_states[callsign] = CenterState.ENROUTE
        self.log_status_change(
            callsign, None, CenterState.ENROUTE.value,
            command_type="contact_center",
        )
        self._issue_command(
            "contact_center",
            callsign,
            frequency=self.frequency,
            altitude_ft=alt_ft,
            instruction=f"Contact Center on {self.frequency}",
        )

    # ──────────────────────────────────────────
    # Altitude Management (backward-compatible)
    # ──────────────────────────────────────────

    def maintain_altitude(self, callsign: str, alt_ft: int) -> None:
        if not self.is_controlling(callsign):
            self.accept_aircraft(callsign)
        prev = self._aircraft_states.get(callsign)
        self._aircraft_states[callsign] = CenterState.ENROUTE
        self.log_status_change(
            callsign, prev.value if prev else None,
            CenterState.ENROUTE.value, command_type="maintain",
        )
        self._issue_command(
            "maintain",
            callsign,
            altitude_ft=alt_ft,
            instruction=f"Maintain {alt_ft}ft",
        )

    def assign_climb(
        self, callsign: str, target_alt_ft: int,
        altimeter_qnh: Optional[float] = None,
    ) -> None:
        self.accept_aircraft(callsign)
        prev = self._aircraft_states.get(callsign)
        self._aircraft_states[callsign] = CenterState.ENROUTE
        self.set_clearance_state(callsign, "climb", target_alt=target_alt_ft)
        self.log_status_change(
            callsign, prev.value if prev else None,
            CenterState.ENROUTE.value, command_type="climb",
        )
        qnh = f", QNH {altimeter_qnh}" if altimeter_qnh else ""
        self._issue_command(
            "climb",
            callsign,
            target_altitude_ft=target_alt_ft,
            instruction=f"Climb to {target_alt_ft}ft{qnh}",
        )

    def assign_descent(
        self, callsign: str, target_alt_ft: int,
        star_name: Optional[str] = None,
    ) -> None:
        self.accept_aircraft(callsign)
        prev = self._aircraft_states.get(callsign)
        self._aircraft_states[callsign] = CenterState.DESCENT_CLEARED
        self.set_clearance_state(
            callsign, "descend", target_alt=target_alt_ft, star=star_name or "",
        )
        self.log_status_change(
            callsign, prev.value if prev else None,
            CenterState.DESCENT_CLEARED.value, command_type="descend",
        )
        star = f" via {star_name}" if star_name else ""
        self._issue_command(
            "descend",
            callsign,
            target_altitude_ft=target_alt_ft,
            star=star_name or "",
            instruction=f"Descend to {target_alt_ft}ft{star}",
        )

    # ──────────────────────────────────────────
    # Airway Tracking
    # ──────────────────────────────────────────

    def assign_airway(
        self,
        callsign: str,
        airway_name: str,
        entry_fix: str,
        exit_fix: str,
        fixes: Optional[List[str]] = None,
        flight_level: int = 0,
        distance_to_exit_nm: float = 0.0,
    ) -> None:
        if not self.is_controlling(callsign):
            self.accept_aircraft(callsign)
        prev = self._aircraft_states.get(callsign)
        self._aircraft_states[callsign] = CenterState.CRUISE
        airway = AirwayAssignment(
            airway_name=airway_name,
            entry_fix=entry_fix,
            exit_fix=exit_fix,
            fixes=fixes or [entry_fix, exit_fix],
            assigned_flight_level=flight_level,
            distance_to_exit_nm=distance_to_exit_nm,
        )
        self._airway_assignments[callsign] = airway
        self.log_status_change(
            callsign, prev.value if prev else None,
            CenterState.CRUISE.value, command_type="assign_airway",
        )
        self.set_clearance_state(
            callsign, "airway",
            airway=airway_name, entry_fix=entry_fix, exit_fix=exit_fix,
            flight_level=flight_level,
        )
        fl = f"FL{flight_level}" if flight_level else "cruise"
        self._issue_command(
            "assign_airway",
            callsign,
            airway=airway_name,
            entry_fix=entry_fix,
            exit_fix=exit_fix,
            flight_level=flight_level,
            instruction=(
                f"Cleared via {airway_name} airway, "
                f"{entry_fix} to {exit_fix}, {fl}"
            ),
        )

    def advance_along_airway(self, callsign: str, fix: str) -> None:
        airway = self._airway_assignments.get(callsign)
        if not airway:
            return
        if fix in airway.fixes:
            airway.current_fix_index = airway.fixes.index(fix)
        self.log_status_change(
            callsign,
            self._aircraft_states.get(callsign, CenterState.CRUISE).value,
            self._aircraft_states.get(callsign, CenterState.CRUISE).value,
            command_type="position_report",
        )
        self._issue_command(
            "position_report",
            callsign,
            fix=fix,
            instruction=f"Position {fix}",
        )

    def get_next_airway_fix(self, callsign: str) -> Optional[str]:
        airway = self._airway_assignments.get(callsign)
        if not airway:
            return None
        next_idx = airway.current_fix_index + 1
        if next_idx < len(airway.fixes):
            return airway.fixes[next_idx]
        return None

    def update_sector_distance(self, callsign: str, distance_nm: float) -> None:
        airway = self._airway_assignments.get(callsign)
        if airway:
            airway.distance_to_exit_nm = distance_nm

    # ──────────────────────────────────────────
    # Cruise Altitude Change Requests
    # ──────────────────────────────────────────

    def request_altitude_change(
        self, callsign: str, requested_alt_ft: int,
        current_alt_ft: int, reason: str = "",
    ) -> None:
        if not self.is_controlling(callsign):
            return
        req = AltitudeChangeRequest(
            callsign=callsign,
            requested_alt_ft=requested_alt_ft,
            current_alt_ft=current_alt_ft,
            reason=reason,
        )
        self._pending_altitude_requests[callsign] = req
        self.log_status_change(
            callsign,
            self._aircraft_states.get(callsign, CenterState.CRUISE).value,
            self._aircraft_states.get(callsign, CenterState.CRUISE).value,
            command_type="altitude_request",
        )
        self._issue_command(
            "altitude_request",
            callsign,
            requested_altitude_ft=requested_alt_ft,
            current_altitude_ft=current_alt_ft,
            reason=reason,
            instruction=(
                f"Request altitude {requested_alt_ft}ft, "
                f"currently {current_alt_ft}ft"
            ),
        )

    def approve_altitude_change(self, callsign: str) -> None:
        req = self._pending_altitude_requests.get(callsign)
        if not req:
            return
        req.approved = True
        req.responded_at_s = time.time()
        prev = self._aircraft_states.get(callsign)
        self._aircraft_states[callsign] = (
            CenterState.CLIMB_CLEARED
            if req.requested_alt_ft > req.current_alt_ft
            else CenterState.CRUISE
        )
        self.set_clearance_state(
            callsign, "altitude_change", target_alt=req.requested_alt_ft,
        )
        self.log_status_change(
            callsign, prev.value if prev else None,
            self._aircraft_states[callsign].value,
            command_type="approve_altitude",
        )
        self._issue_command(
            "approve_altitude",
            callsign,
            target_altitude_ft=req.requested_alt_ft,
            instruction=f"Approved altitude {req.requested_alt_ft}ft",
        )

    def deny_altitude_change(self, callsign: str, reason: str = "") -> None:
        req = self._pending_altitude_requests.get(callsign)
        if not req:
            return
        req.approved = False
        req.responded_at_s = time.time()
        self.log_status_change(
            callsign,
            self._aircraft_states.get(callsign, CenterState.CRUISE).value,
            self._aircraft_states.get(callsign, CenterState.CRUISE).value,
            command_type="deny_altitude",
        )
        msg = f"Unable altitude {req.requested_alt_ft}ft"
        if reason:
            msg += f", {reason}"
        self._issue_command(
            "deny_altitude",
            callsign,
            requested_altitude_ft=req.requested_alt_ft,
            reason=reason,
            instruction=msg,
        )

    # ──────────────────────────────────────────
    # Top of Descent Planning
    # ──────────────────────────────────────────

    def clear_top_of_descent(
        self, callsign: str, target_alt_ft: int,
        descent_point: str, star_name: Optional[str] = None,
    ) -> None:
        if not self.is_controlling(callsign):
            self.accept_aircraft(callsign)
        prev = self._aircraft_states.get(callsign)
        self._aircraft_states[callsign] = CenterState.DESCENT_CLEARED
        self.set_clearance_state(
            callsign, "top_of_descent",
            target_alt=target_alt_ft, descent_point=descent_point,
            star=star_name or "",
        )
        self.log_status_change(
            callsign, prev.value if prev else None,
            CenterState.DESCENT_CLEARED.value,
            command_type="top_of_descent",
        )
        star = f" via {star_name}" if star_name else ""
        self._issue_command(
            "top_of_descent",
            callsign,
            target_altitude_ft=target_alt_ft,
            descent_point=descent_point,
            star=star_name or "",
            instruction=(
                f"Top of descent at {descent_point}, "
                f"descend to {target_alt_ft}ft{star}"
            ),
        )

    def estimate_top_of_descent(
        self, callsign: str, target_alt_ft: int,
        current_alt_ft: int, distance_to_descent_nm: float,
    ) -> Optional[int]:
        airway = self._airway_assignments.get(callsign)
        if not airway:
            return None
        alt_diff = current_alt_ft - target_alt_ft
        if alt_diff <= 0:
            return int(distance_to_descent_nm)
        rate_per_nm = 300.0
        required_nm = alt_diff / rate_per_nm
        if required_nm >= distance_to_descent_nm:
            return 0
        return int(distance_to_descent_nm - required_nm)

    # ──────────────────────────────────────────
    # Handoff to Approach (backward-compatible)
    # ──────────────────────────────────────────

    def handoff_to_approach(
        self, callsign: str, approach_controller: str, approach_freq: float
    ) -> None:
        prev = self._aircraft_states.get(callsign)
        self._aircraft_states[callsign] = CenterState.HANDOFF
        self.log_status_change(
            callsign, prev.value if prev else None,
            CenterState.HANDOFF.value, command_type="contact_approach",
        )
        self._issue_command(
            "contact_approach",
            callsign,
            controller=approach_controller,
            frequency=approach_freq,
            instruction=f"Contact Approach on {approach_freq}",
        )
        self._propose_handoff(
            callsign,
            to_controller=approach_controller,
            frequency=approach_freq,
        )

    def release_to_approach(self, callsign: str) -> None:
        self._aircraft_states.pop(callsign, None)
        self._airway_assignments.pop(callsign, None)
        self._pending_altitude_requests.pop(callsign, None)
        self.revoke_clearance(callsign)
        self.release_aircraft(callsign)

    # ──────────────────────────────────────────
    # Adjacent Center Handoff (backward-compatible)
    # ──────────────────────────────────────────

    def accept_from_adjacent_center(self, callsign: str, alt_ft: float) -> None:
        self.accept_aircraft(callsign)
        self._aircraft_states[callsign] = CenterState.ENROUTE
        self.log_status_change(
            callsign, None, CenterState.ENROUTE.value,
            command_type="contact_center",
        )
        self._issue_command(
            "contact_center",
            callsign,
            frequency=self.frequency,
            altitude_ft=alt_ft,
            instruction=f"Contact {self.callsign} on {self.frequency}",
        )

    # ──────────────────────────────────────────
    # Sector-to-Sector Boundary Handoffs
    # ──────────────────────────────────────────

    def can_handoff_to_adjacent_center(
        self, callsign: str,
        exit_fix: Optional[str] = None,
        current_time: Optional[float] = None,
    ) -> bool:
        airway = self._airway_assignments.get(callsign)
        fix = exit_fix or (airway.exit_fix if airway else None)
        if not fix:
            return True
        if fix not in self._last_sector_release_time:
            return True
        now = current_time if current_time is not None else time.time()
        last = self._last_sector_release_time[fix]
        return (now - last) >= 120.0

    def handoff_to_adjacent_center(
        self, callsign: str,
        adjacent_center: str, adjacent_freq: float,
    ) -> None:
        if not self.is_controlling(callsign):
            return
        prev = self._aircraft_states.get(callsign)
        self._aircraft_states[callsign] = CenterState.HANDOFF
        self.log_status_change(
            callsign, prev.value if prev else None,
            CenterState.HANDOFF.value, command_type="contact_center",
        )
        self._issue_command(
            "contact_center",
            callsign,
            controller=adjacent_center,
            frequency=adjacent_freq,
            instruction=f"Contact {adjacent_center} on {adjacent_freq}",
        )
        self._propose_handoff(
            callsign,
            to_controller=adjacent_center,
            frequency=adjacent_freq,
        )

    def release_to_adjacent_center(
        self, callsign: str,
        exit_fix: Optional[str] = None,
        current_time: Optional[float] = None,
    ) -> None:
        if not self.is_controlling(callsign):
            return
        airway = self._airway_assignments.get(callsign)
        fix = exit_fix or (airway.exit_fix if airway else None)
        if fix:
            self._last_sector_release_time[fix] = (
                current_time if current_time is not None else time.time()
            )
        self._aircraft_states.pop(callsign, None)
        self._airway_assignments.pop(callsign, None)
        self._pending_altitude_requests.pop(callsign, None)
        self.revoke_clearance(callsign)
        self.release_aircraft(callsign)

    # ──────────────────────────────────────────
    # Process — Automated TOD & Conflict Detection
    # ──────────────────────────────────────────

    def process(self, dt: float, context: Dict[str, Any]) -> None:
        now = time.time()
        for cs, state in list(self._aircraft_states.items()):
            if state == CenterState.DESCENT_CLEARED:
                continue
            if state == CenterState.HANDOFF:
                continue
            airway = self._airway_assignments.get(cs)
            if not airway:
                continue
            if airway.distance_to_exit_nm <= self._tod_distance_nm:
                self._issue_command(
                    "top_of_descent_advisory",
                    cs,
                    airway=airway.airway_name,
                    exit_fix=airway.exit_fix,
                    distance_nm=airway.distance_to_exit_nm,
                    instruction=(
                        f"Approaching sector boundary, "
                        f"expect descent at {airway.exit_fix}"
                    ),
                )
