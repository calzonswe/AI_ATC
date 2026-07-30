from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from .base import BaseController
from .models import ApproachState, STARAssignment


class ApproachController(BaseController):
    _aircraft_states: Dict[str, ApproachState]
    _star_assignments: Dict[str, STARAssignment]
    _speed_restrictions: Dict[str, int]
    _landing_sequence: Dict[str, int]
    _runway_assignments: Dict[str, str]
    _last_landing_time: Dict[str, float]

    def __init__(
        self,
        callsign: str,
        frequency: float,
        sector_id: str,
        airport_icao: str,
        approach_separation_s: int = 120,
    ):
        super().__init__(callsign, frequency, sector_id, airport_icao=airport_icao)
        self._aircraft_states: Dict[str, ApproachState] = {}
        self._star_assignments: Dict[str, STARAssignment] = {}
        self._speed_restrictions: Dict[str, int] = {}
        self._landing_sequence: Dict[str, int] = {}
        self._runway_assignments: Dict[str, str] = {}
        self._last_landing_time: Dict[str, float] = {}
        self._approach_separation_s = approach_separation_s

    # ──────────────────────────────────────────
    # Queries
    # ──────────────────────────────────────────

    def get_aircraft_approach_state(self, callsign: str) -> Optional[ApproachState]:
        return self._aircraft_states.get(callsign)

    def get_star_assignment(self, callsign: str) -> Optional[STARAssignment]:
        return self._star_assignments.get(callsign)

    def get_speed_restriction(self, callsign: str) -> Optional[int]:
        return self._speed_restrictions.get(callsign)

    def get_landing_sequence(self, callsign: str) -> Optional[int]:
        return self._landing_sequence.get(callsign)

    def get_approach_runway(self, callsign: str) -> Optional[str]:
        return self._runway_assignments.get(callsign)

    # ──────────────────────────────────────────
    # Accept from Center
    # ──────────────────────────────────────────

    def accept_from_center(
        self, callsign: str, alt_ft: float,
        star_info: Optional[dict] = None,
    ) -> None:
        self.accept_aircraft(callsign)
        self._aircraft_states[callsign] = ApproachState.VECTORING
        self.log_status_change(
            callsign, None, ApproachState.VECTORING.value,
            command_type="contact_approach",
        )
        if star_info:
            approach_runway = star_info.get("approach_runway", "")
            star = STARAssignment(
                star_name=star_info.get("star_name", ""),
                initial_alt_ft=star_info.get("initial_alt_ft", int(alt_ft)),
                approach_runway=approach_runway,
                current_alt_ft=star_info.get("initial_alt_ft", int(alt_ft)),
                intercept_distance_nm=star_info.get("intercept_distance_nm", 10.0),
            )
            self._star_assignments[callsign] = star
            if approach_runway:
                self._runway_assignments[callsign] = approach_runway
            self.set_clearance_state(
                callsign, "star",
                star_name=star.star_name,
                alt=star.initial_alt_ft,
                runway=star.approach_runway,
            )
        self._issue_command(
            "contact_approach",
            callsign,
            frequency=self.frequency,
            altitude_ft=alt_ft,
            instruction=f"Contact Approach on {self.frequency}",
        )

    # ──────────────────────────────────────────
    # STAR Assignment
    # ──────────────────────────────────────────

    def assign_star(
        self,
        callsign: str,
        star_name: str,
        alt_ft: int,
        approach_runway: str = "",
        intercept_distance_nm: float = 10.0,
    ) -> None:
        if not self.is_controlling(callsign):
            self.accept_aircraft(callsign)
        prev = self._aircraft_states.get(callsign)
        self._aircraft_states[callsign] = ApproachState.VECTORING
        star = STARAssignment(
            star_name=star_name,
            initial_alt_ft=alt_ft,
            approach_runway=approach_runway,
            current_alt_ft=alt_ft,
            intercept_distance_nm=intercept_distance_nm,
        )
        self._star_assignments[callsign] = star
        if approach_runway:
            self._runway_assignments[callsign] = approach_runway
        self.set_clearance_state(
            callsign, "descend_via_star",
            star=star_name, alt=alt_ft, runway=approach_runway,
        )
        self.log_status_change(
            callsign, prev.value if prev else None,
            ApproachState.VECTORING.value, command_type="assign_star",
        )
        rwy = f" runway {approach_runway}" if approach_runway else ""
        self._issue_command(
            "assign_star",
            callsign,
            star=star_name,
            altitude_ft=alt_ft,
            runway=approach_runway,
            instruction=f"Descend via {star_name} STAR{rwy}, {alt_ft}ft",
        )

    # ──────────────────────────────────────────
    # Radar Vectors
    # ──────────────────────────────────────────

    def vector_to_ils(
        self, callsign: str, heading: float, alt_ft: int,
        intercept_distance_nm: float = 10.0,
    ) -> None:
        if not self.is_controlling(callsign):
            self.accept_aircraft(callsign)
        prev = self._aircraft_states.get(callsign)
        self._aircraft_states[callsign] = ApproachState.VECTORING
        star = self._star_assignments.get(callsign)
        if star:
            star.vector_heading = heading
        self.log_status_change(
            callsign, prev.value if prev else None,
            ApproachState.VECTORING.value, command_type="vector",
        )
        heading_str = f"{int(heading):03d}"
        self._issue_command(
            "vector",
            callsign,
            heading=heading,
            heading_deg=heading,
            altitude_ft=alt_ft,
            instruction=f"Fly heading {heading_str}, descend to {alt_ft}ft",
        )

    # ──────────────────────────────────────────
    # Speed Control
    # ──────────────────────────────────────────

    def assign_speed(
        self,
        callsign: str,
        speed_knots: int,
        restriction_type: str = "maximum",
    ) -> None:
        if not self.is_controlling(callsign):
            return
        self._speed_restrictions[callsign] = speed_knots
        star = self._star_assignments.get(callsign)
        if star:
            star.speed_restriction = speed_knots
        self.log_status_change(
            callsign,
            self._aircraft_states.get(callsign, ApproachState.VECTORING).value,
            self._aircraft_states.get(callsign, ApproachState.VECTORING).value,
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

    # ──────────────────────────────────────────
    # Altitude Management
    # ──────────────────────────────────────────

    def assign_descent(
        self,
        callsign: str,
        target_alt_ft: int,
    ) -> None:
        if not self.is_controlling(callsign):
            self.accept_aircraft(callsign)
        prev = self._aircraft_states.get(callsign)
        self._aircraft_states[callsign] = ApproachState.DESCENT_CLEARED
        self.set_clearance_state(callsign, "descend", target_alt=target_alt_ft)
        star = self._star_assignments.get(callsign)
        if star:
            star.current_alt_ft = target_alt_ft
        self.log_status_change(
            callsign, prev.value if prev else None,
            ApproachState.DESCENT_CLEARED.value,
            command_type="descend",
        )
        self._issue_command(
            "descend",
            callsign,
            target_altitude_ft=target_alt_ft,
            instruction=f"Descend to {target_alt_ft}ft",
        )

    def maintain_altitude(
        self,
        callsign: str,
        alt_ft: int,
    ) -> None:
        if not self.is_controlling(callsign):
            self.accept_aircraft(callsign)
        prev = self._aircraft_states.get(callsign)
        self._aircraft_states[callsign] = ApproachState.DESCENT_CLEARED
        self.set_clearance_state(callsign, "maintain", alt=alt_ft)
        star = self._star_assignments.get(callsign)
        if star:
            star.current_alt_ft = alt_ft
        self.log_status_change(
            callsign, prev.value if prev else None,
            ApproachState.DESCENT_CLEARED.value,
            command_type="maintain",
        )
        self._issue_command(
            "maintain",
            callsign,
            altitude_ft=alt_ft,
            instruction=f"Maintain {alt_ft}ft",
        )

    # ──────────────────────────────────────────
    # Holding
    # ──────────────────────────────────────────

    def assign_hold(
        self, callsign: str, fix: str, altitude_ft: int,
        expected_approach_time: Optional[str] = None,
    ) -> None:
        self.accept_aircraft(callsign)
        prev = self._aircraft_states.get(callsign)
        self._aircraft_states[callsign] = ApproachState.HOLDING
        self.set_clearance_state(callsign, "hold", fix=fix, altitude=altitude_ft)
        self.log_status_change(
            callsign, prev.value if prev else None,
            ApproachState.HOLDING.value, command_type="hold",
        )
        eat = f", expected approach at {expected_approach_time}" if expected_approach_time else ""
        self._issue_command(
            "hold",
            callsign,
            fix=fix,
            altitude_ft=altitude_ft,
            instruction=f"Hold at {fix}, {altitude_ft}ft{eat}",
        )

    # ──────────────────────────────────────────
    # Approach Clearances
    # ──────────────────────────────────────────

    def clear_ils(self, callsign: str, runway: str, ils_freq: float) -> None:
        if not self.is_controlling(callsign):
            self.accept_aircraft(callsign)
        prev = self._aircraft_states.get(callsign)
        self._aircraft_states[callsign] = ApproachState.ILS_CLEARED
        self._runway_assignments[callsign] = runway
        self.set_clearance_state(
            callsign, "ils_approach", runway=runway, ils_freq=ils_freq,
        )
        self.log_status_change(
            callsign, prev.value if prev else None,
            ApproachState.ILS_CLEARED.value, command_type="clear_ils",
        )
        self._issue_command(
            "clear_ils",
            callsign,
            runway=runway,
            ils_frequency=ils_freq,
            instruction=f"Cleared ILS approach runway {runway}, frequency {ils_freq}",
        )

    def clear_visual(
        self,
        callsign: str,
        runway: str,
    ) -> None:
        if not self.is_controlling(callsign):
            self.accept_aircraft(callsign)
        prev = self._aircraft_states.get(callsign)
        self._aircraft_states[callsign] = ApproachState.VISUAL_CLEARED
        self._runway_assignments[callsign] = runway
        self.set_clearance_state(
            callsign, "visual_approach", runway=runway,
        )
        self.log_status_change(
            callsign, prev.value if prev else None,
            ApproachState.VISUAL_CLEARED.value, command_type="clear_visual",
        )
        self._issue_command(
            "clear_visual",
            callsign,
            runway=runway,
            instruction=f"Cleared visual approach runway {runway}",
        )

    def clear_rnav(
        self,
        callsign: str,
        runway: str,
        rnav_type: str = "RNP",
    ) -> None:
        if not self.is_controlling(callsign):
            self.accept_aircraft(callsign)
        prev = self._aircraft_states.get(callsign)
        self._aircraft_states[callsign] = ApproachState.RNAV_CLEARED
        self._runway_assignments[callsign] = runway
        self.set_clearance_state(
            callsign, "rnav_approach", runway=runway, rnav_type=rnav_type,
        )
        self.log_status_change(
            callsign, prev.value if prev else None,
            ApproachState.RNAV_CLEARED.value, command_type="clear_rnav",
        )
        self._issue_command(
            "clear_rnav",
            callsign,
            runway=runway,
            rnav_type=rnav_type,
            instruction=f"Cleared {rnav_type} approach runway {runway}",
        )

    # ──────────────────────────────────────────
    # Landing Sequencing
    # ──────────────────────────────────────────

    def assign_landing_sequence(
        self,
        callsign: str,
        sequence_number: int,
        runway: str = "",
    ) -> None:
        if not self.is_controlling(callsign):
            self.accept_aircraft(callsign)
        prev = self._aircraft_states.get(callsign)
        self._aircraft_states[callsign] = ApproachState.APPROACH_SEQUENCE
        self._landing_sequence[callsign] = sequence_number
        if runway:
            self._runway_assignments[callsign] = runway
        self.log_status_change(
            callsign, prev.value if prev else None,
            ApproachState.APPROACH_SEQUENCE.value,
            command_type="sequence",
        )
        suffix = "st" if sequence_number == 1 else "nd" if sequence_number == 2 else "rd" if sequence_number == 3 else "th"
        rwy = f" runway {runway}" if runway else ""
        self._issue_command(
            "sequence",
            callsign,
            sequence_number=sequence_number,
            runway=runway,
            instruction=f"Number {sequence_number}{suffix}{rwy}, follow traffic",
        )

    # ──────────────────────────────────────────
    # Handoff to Tower
    # ──────────────────────────────────────────

    def can_handoff_to_tower(
        self,
        callsign: str,
        runway: Optional[str] = None,
        current_time: Optional[float] = None,
    ) -> bool:
        rwy = runway or self._runway_assignments.get(callsign)
        if not rwy:
            return True
        if rwy not in self._last_landing_time:
            return True
        now = current_time if current_time is not None else time.time()
        last = self._last_landing_time[rwy]
        return (now - last) >= self._approach_separation_s

    def handoff_to_tower(
        self,
        callsign: str,
        tower_controller: str,
        tower_freq: float,
    ) -> None:
        if not self.is_controlling(callsign):
            return
        prev = self._aircraft_states.get(callsign)
        self._aircraft_states[callsign] = ApproachState.FINAL
        self.log_status_change(
            callsign, prev.value if prev else None,
            ApproachState.FINAL.value, command_type="contact_tower",
        )
        self._issue_command(
            "contact_tower",
            callsign,
            controller=tower_controller,
            frequency=tower_freq,
            instruction=f"Contact Tower on {tower_freq}",
        )
        self._propose_handoff(
            callsign,
            to_controller=tower_controller,
            frequency=tower_freq,
        )

    def release_to_tower(
        self,
        callsign: str,
        runway: Optional[str] = None,
        current_time: Optional[float] = None,
    ) -> None:
        if not self.is_controlling(callsign):
            return
        rwy = runway or self._runway_assignments.get(callsign)
        if rwy:
            self._last_landing_time[rwy] = current_time if current_time is not None else time.time()
        self._aircraft_states.pop(callsign, None)
        self._star_assignments.pop(callsign, None)
        self._speed_restrictions.pop(callsign, None)
        self._landing_sequence.pop(callsign, None)
        self._runway_assignments.pop(callsign, None)
        self.revoke_clearance(callsign)
        self.release_aircraft(callsign)

    # ──────────────────────────────────────────
    # Go Around
    # ──────────────────────────────────────────

    def go_around(self, callsign: str, reason: str = "") -> None:
        if not self.is_controlling(callsign):
            self.accept_aircraft(callsign)
        prev = self._aircraft_states.get(callsign)
        self._aircraft_states[callsign] = ApproachState.GO_AROUND
        self.log_status_change(
            callsign, prev.value if prev else None,
            ApproachState.GO_AROUND.value, command_type="go_around_vector",
        )
        msg = f"Go around{' - ' + reason if reason else ''}"
        self._issue_command(
            "go_around_vector",
            callsign,
            reason=reason,
            instruction=msg,
        )

    # ──────────────────────────────────────────
    # Process — Automated Conflict Detection
    # ──────────────────────────────────────────

    def process(self, dt: float, context: Dict[str, Any]) -> None:
        now = time.time()
        runway_groups: Dict[str, List[str]] = {}
        for cs, state in self._aircraft_states.items():
            if state == ApproachState.FINAL:
                continue
            rwy = self._runway_assignments.get(cs)
            if rwy:
                if rwy not in runway_groups:
                    runway_groups[rwy] = []
                runway_groups[rwy].append(cs)

        for rwy, acs in runway_groups.items():
            if rwy not in self._last_landing_time:
                continue
            last = self._last_landing_time[rwy]
            for ac in acs:
                if (now - last) < self._approach_separation_s:
                    self._issue_command(
                        "approach_conflict",
                        ac,
                        runway=rwy,
                        instruction=f"Traffic ahead on approach to runway {rwy}, maintain separation",
                    )
