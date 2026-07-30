from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from .base import BaseController
from .models import ControllerState, DepartureState, SIDAssignment


class DepartureController(BaseController):
    _aircraft_states: Dict[str, DepartureState]
    _sid_assignments: Dict[str, SIDAssignment]
    _heading_assignments: Dict[str, float]
    _speed_restrictions: Dict[str, int]
    _last_fix_departure: Dict[str, float]

    def __init__(
        self,
        callsign: str,
        frequency: float,
        sector_id: str,
        airport_icao: str,
        departure_separation_s: int = 120,
    ):
        super().__init__(callsign, frequency, sector_id, airport_icao=airport_icao)
        self._aircraft_states: Dict[str, DepartureState] = {}
        self._state = ControllerState.ACTIVE
        self._sid_assignments: Dict[str, SIDAssignment] = {}
        self._heading_assignments: Dict[str, float] = {}
        self._speed_restrictions: Dict[str, int] = {}
        self._last_fix_departure: Dict[str, float] = {}
        self._departure_separation_s = departure_separation_s

    def get_aircraft_departure_state(self, callsign: str) -> Optional[DepartureState]:
        return self._aircraft_states.get(callsign)

    def get_sid_assignment(self, callsign: str) -> Optional[SIDAssignment]:
        return self._sid_assignments.get(callsign)

    def accept_from_tower(
        self,
        callsign: str,
        sid_info: Optional[dict] = None,
    ) -> None:
        self.accept_aircraft(callsign)
        self._aircraft_states[callsign] = DepartureState.INITIAL_CLIMB
        self.log_status_change(
            callsign, None, DepartureState.INITIAL_CLIMB.value,
            command_type="contact_departure",
        )
        if sid_info:
            sid = SIDAssignment(
                sid_name=sid_info.get("sid_name", ""),
                initial_alt_ft=sid_info.get("initial_alt_ft", 3000),
                departure_fix=sid_info.get("departure_fix", ""),
                current_alt_ft=sid_info.get("initial_alt_ft", 3000),
                handoff_alt_ft=sid_info.get("handoff_alt_ft"),
            )
            self._sid_assignments[callsign] = sid
            self.set_clearance_state(
                callsign, "sid", sid_name=sid.sid_name,
                initial_alt=sid.initial_alt_ft,
            )
        self._issue_command(
            "contact_departure",
            callsign,
            frequency=self.frequency,
            instruction=f"Contact Departure on {self.frequency}",
        )

    def assign_sid(
        self,
        callsign: str,
        sid_name: str,
        initial_alt_ft: int,
        departure_fix: str = "",
        handoff_alt_ft: Optional[int] = None,
    ) -> None:
        if not self.is_controlling(callsign):
            self.accept_aircraft(callsign)
        prev = self._aircraft_states.get(callsign)
        self._aircraft_states[callsign] = DepartureState.ENROUTE
        sid = SIDAssignment(
            sid_name=sid_name,
            initial_alt_ft=initial_alt_ft,
            departure_fix=departure_fix,
            current_alt_ft=initial_alt_ft,
            handoff_alt_ft=handoff_alt_ft,
        )
        self._sid_assignments[callsign] = sid
        self.set_clearance_state(
            callsign, "climb_via_sid",
            sid=sid_name, alt=initial_alt_ft,
        )
        self.log_status_change(
            callsign, prev.value if prev else None,
            DepartureState.ENROUTE.value, command_type="climb_via_sid",
        )
        fix = f" via {departure_fix}" if departure_fix else ""
        ha = f", expect {handoff_alt_ft}ft" if handoff_alt_ft else ""
        self._issue_command(
            "climb_via_sid",
            callsign,
            sid=sid_name,
            initial_altitude_ft=initial_alt_ft,
            departure_fix=departure_fix,
            instruction=f"Climb via {sid_name} SID{fix}, initial climb {initial_alt_ft}ft{ha}",
        )

    def assign_heading(
        self,
        callsign: str,
        heading: float,
        reason: str = "",
    ) -> None:
        if not self.is_controlling(callsign):
            return
        prev = self._aircraft_states.get(callsign)
        self._aircraft_states[callsign] = DepartureState.HEADING_ASSIGNED
        self._heading_assignments[callsign] = heading
        sid = self._sid_assignments.get(callsign)
        if sid:
            sid.is_vectored = True
            sid.vector_heading = heading
        self.log_status_change(
            callsign, prev.value if prev else None,
            DepartureState.HEADING_ASSIGNED.value,
            command_type="vector",
        )
        reason_text = f" {reason}" if reason else ""
        self._issue_command(
            "vector",
            callsign,
            heading=heading,
            heading_deg=heading,
            instruction=f"Fly heading {heading}{reason_text}",
        )

    def assign_speed(
        self,
        callsign: str,
        speed_knots: int,
        restriction_type: str = "maximum",
    ) -> None:
        if not self.is_controlling(callsign):
            return
        prev = self._aircraft_states.get(callsign)
        self._speed_restrictions[callsign] = speed_knots
        sid = self._sid_assignments.get(callsign)
        if sid:
            sid.speed_restriction = speed_knots
        self.log_status_change(
            callsign, prev.value if prev else None,
            self._aircraft_states.get(callsign, DepartureState.ENROUTE).value,
            command_type="speed",
        )
        if restriction_type == "maximum":
            instruction = f"Reduce to {speed_knots} knots"
        else:
            instruction = f"{restriction_type.capitalize()} speed {speed_knots} knots"
        self._issue_command(
            "speed",
            callsign,
            speed_knots=speed_knots,
            restriction_type=restriction_type,
            instruction=instruction,
        )

    def get_speed_restriction(self, callsign: str) -> Optional[int]:
        return self._speed_restrictions.get(callsign)

    def radar_contact(
        self,
        callsign: str,
        current_alt_ft: Optional[int] = None,
        sid_name: Optional[str] = None,
    ) -> None:
        if not self.is_controlling(callsign):
            self.accept_aircraft(callsign)
        prev = self._aircraft_states.get(callsign)
        self._aircraft_states[callsign] = DepartureState.RADAR_CONTACT
        self.log_status_change(
            callsign, prev.value if prev else None,
            DepartureState.RADAR_CONTACT.value,
            command_type="radar_contact",
        )
        alt = f" {current_alt_ft}ft" if current_alt_ft is not None else ""
        sid_text = f", climb via {sid_name}" if sid_name else ""
        self._issue_command(
            "radar_contact",
            callsign,
            current_altitude_ft=current_alt_ft,
            sid=sid_name or "",
            instruction=f"Radar contact{alt}{sid_text}",
        )

    def verify_altitude(
        self,
        callsign: str,
        reported_alt_ft: int,
    ) -> bool:
        sid = self._sid_assignments.get(callsign)
        if not sid:
            return True
        expected = sid.current_alt_ft
        if reported_alt_ft == expected:
            return True
        if reported_alt_ft < expected:
            self._issue_command(
                "altitude_correction",
                callsign,
                reported_alt_ft=reported_alt_ft,
                expected_alt_ft=expected,
                instruction=f"Climb to {expected}ft, currently {reported_alt_ft}ft",
            )
        else:
            self._issue_command(
                "altitude_correction",
                callsign,
                reported_alt_ft=reported_alt_ft,
                expected_alt_ft=expected,
                instruction=f"Maintain {expected}ft, currently {reported_alt_ft}ft",
            )
        return False

    def get_heading_assignment(self, callsign: str) -> Optional[float]:
        return self._heading_assignments.get(callsign)

    def maintain_altitude(
        self,
        callsign: str,
        alt_ft: int,
    ) -> None:
        if not self.is_controlling(callsign):
            self.accept_aircraft(callsign)
        prev = self._aircraft_states.get(callsign)
        self._aircraft_states[callsign] = DepartureState.CLIMB_CLEARED
        self.set_clearance_state(callsign, "maintain", alt=alt_ft)
        sid = self._sid_assignments.get(callsign)
        if sid:
            sid.current_alt_ft = alt_ft
        self.log_status_change(
            callsign, prev.value if prev else None,
            DepartureState.CLIMB_CLEARED.value,
            command_type="maintain",
        )
        self._issue_command(
            "maintain",
            callsign,
            altitude_ft=alt_ft,
            instruction=f"Maintain {alt_ft}ft",
        )

    def assign_climb(
        self,
        callsign: str,
        target_alt_ft: int,
    ) -> None:
        if not self.is_controlling(callsign):
            self.accept_aircraft(callsign)
        prev = self._aircraft_states.get(callsign)
        self._aircraft_states[callsign] = DepartureState.CLIMB_CLEARED
        self.set_clearance_state(callsign, "climb", target_alt=target_alt_ft)
        sid = self._sid_assignments.get(callsign)
        if sid:
            sid.current_alt_ft = target_alt_ft
        self.log_status_change(
            callsign, prev.value if prev else None,
            DepartureState.CLIMB_CLEARED.value,
            command_type="climb",
        )
        self._issue_command(
            "climb",
            callsign,
            target_altitude_ft=target_alt_ft,
            instruction=f"Climb to {target_alt_ft}ft",
        )

    def can_release_to_center(
        self,
        callsign: str,
        fix_name: Optional[str] = None,
        current_time: Optional[float] = None,
    ) -> bool:
        sid = self._sid_assignments.get(callsign)
        if not sid:
            return False
        fix = fix_name or sid.departure_fix
        if not fix:
            return True
        if fix not in self._last_fix_departure:
            return True
        now = current_time if current_time is not None else time.time()
        last_dep = self._last_fix_departure[fix]
        return (now - last_dep) >= self._departure_separation_s

    def handoff_to_center(
        self,
        callsign: str,
        center_controller: str,
        center_freq: float,
    ) -> None:
        if not self.is_controlling(callsign):
            return
        prev = self._aircraft_states.get(callsign)
        self._aircraft_states[callsign] = DepartureState.HANDOFF
        self.log_status_change(
            callsign, prev.value if prev else None,
            DepartureState.HANDOFF.value, command_type="contact_center",
        )
        self._issue_command(
            "contact_center",
            callsign,
            controller=center_controller,
            frequency=center_freq,
            instruction=f"Contact {center_controller} on {center_freq}",
        )
        self._propose_handoff(
            callsign,
            to_controller=center_controller,
            frequency=center_freq,
        )

    def release_to_center(
        self,
        callsign: str,
        fix_name: Optional[str] = None,
        current_time: Optional[float] = None,
    ) -> None:
        if not self.is_controlling(callsign):
            return
        sid = self._sid_assignments.get(callsign)
        fix = fix_name or (sid.departure_fix if sid else "")
        if fix:
            self._last_fix_departure[fix] = current_time if current_time is not None else time.time()
        self._aircraft_states.pop(callsign, None)
        self._sid_assignments.pop(callsign, None)
        self._heading_assignments.pop(callsign, None)
        self._speed_restrictions.pop(callsign, None)
        self.revoke_clearance(callsign)
        self.release_aircraft(callsign)

    def process(self, dt: float, context: Dict[str, Any]) -> None:
        now = time.time()
        fix_groups: Dict[str, List[str]] = {}
        for cs, sid in self._sid_assignments.items():
            if cs not in self._aircraft_states:
                continue
            state = self._aircraft_states[cs]
            if state == DepartureState.HANDOFF:
                continue
            fix = sid.departure_fix
            if fix:
                if fix not in fix_groups:
                    fix_groups[fix] = []
                fix_groups[fix].append(cs)

        for fix, acs in fix_groups.items():
            if len(acs) < 2:
                continue
            last = self._last_fix_departure.get(fix, 0.0)
            for ac in acs:
                if (now - last) < self._departure_separation_s:
                    self._issue_command(
                        "conflict_alert",
                        ac,
                        fix=fix,
                        instruction=f"Traffic ahead departing via {fix}, maintain separation",
                    )

    def _find_aircraft_at_fix(
        self, fix: str, exclude: str = ""
    ) -> Optional[str]:
        for cs, sid in self._sid_assignments.items():
            if cs != exclude and sid.departure_fix == fix:
                if cs in self._aircraft_states:
                    return cs
        return None
