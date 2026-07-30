from __future__ import annotations

from typing import Any, Dict, List, Optional

from .base import BaseController
from .models import (
    ClearanceState,
    ControllerState,
    CraftClearance,
    DeliveryState,
    HoldingInstruction,
    MissedApproachProcedure,
)


class ClearanceDeliveryController(BaseController):
    _aircraft_states: Dict[str, DeliveryState]
    _craft_clearances: Dict[str, CraftClearance]
    _holding_instructions: Dict[str, HoldingInstruction]
    _missed_approach_procedures: Dict[str, MissedApproachProcedure]

    def __init__(
        self,
        callsign: str,
        frequency: float,
        sector_id: str,
        airport_icao: str,
    ):
        super().__init__(callsign, frequency, sector_id, airport_icao=airport_icao)
        self._aircraft_states: Dict[str, DeliveryState] = {}
        self._craft_clearances: Dict[str, CraftClearance] = {}
        self._holding_instructions: Dict[str, HoldingInstruction] = {}
        self._missed_approach_procedures: Dict[str, MissedApproachProcedure] = {}
        self._state = ControllerState.ACTIVE

    # ── Queries ──

    def get_aircraft_delivery_state(self, callsign: str) -> Optional[DeliveryState]:
        return self._aircraft_states.get(callsign)

    def get_craft_clearance(self, callsign: str) -> Optional[CraftClearance]:
        return self._craft_clearances.get(callsign)

    def get_holding_instruction(self, callsign: str) -> Optional[HoldingInstruction]:
        return self._holding_instructions.get(callsign)

    def get_missed_approach_procedure(
        self, callsign: str,
    ) -> Optional[MissedApproachProcedure]:
        return self._missed_approach_procedures.get(callsign)

    # ── CRAFT Clearance ──

    def issue_craft_clearance(
        self,
        callsign: str,
        destination: str,
        sid_name: str,
        initial_alt_ft: int,
        departure_freq: float,
        squawk: str,
        route: str = "",
        remarks: str = "",
    ) -> CraftClearance:
        self.accept_aircraft(callsign)
        clearance = CraftClearance(
            callsign=callsign,
            destination=destination,
            sid_name=sid_name,
            initial_altitude_ft=initial_alt_ft,
            departure_frequency_mhz=departure_freq,
            squawk=squawk,
            route=route,
            remarks=remarks,
        )
        self._craft_clearances[callsign] = clearance
        self._aircraft_states[callsign] = DeliveryState.CLEARANCE_ISSUED
        self.set_clearance_state(
            callsign, "craft_clearance",
            destination=destination,
            sid=sid_name,
            altitude=initial_alt_ft,
            frequency=departure_freq,
            squawk=squawk,
        )
        self.log_status_change(
            callsign, None, DeliveryState.CLEARANCE_ISSUED.value,
            command_type="craft_clearance",
        )
        text = self._format_craft_text(callsign, clearance)
        self._issue_command(
            "craft_clearance",
            callsign,
            destination=destination,
            sid=sid_name,
            initial_altitude_ft=initial_alt_ft,
            departure_frequency_mhz=departure_freq,
            squawk=squawk,
            instruction=text,
        )
        return clearance

    def request_readback(self, callsign: str) -> None:
        if self._aircraft_states.get(callsign) != DeliveryState.CLEARANCE_ISSUED:
            return
        self._aircraft_states[callsign] = DeliveryState.READBACK_PENDING
        self._issue_command(
            "readback_request",
            callsign,
            instruction=f"{callsign}, read back clearance",
        )

    def verify_readback(self, callsign: str, readback_text: str) -> bool:
        if self._aircraft_states.get(callsign) != DeliveryState.READBACK_PENDING:
            return False
        clearance = self._craft_clearances.get(callsign)
        if not clearance:
            return False
        verified = self._check_readback(clearance, readback_text)
        if verified:
            self._aircraft_states[callsign] = DeliveryState.READBACK_VERIFIED
            self.acknowledge_clearance(callsign)
            self.log_status_change(
                callsign, DeliveryState.READBACK_PENDING.value,
                DeliveryState.READBACK_VERIFIED.value,
                command_type="readback_verified",
            )
            self._issue_command(
                "readback_verified",
                callsign,
                instruction=f"{callsign}, readback correct",
            )
        else:
            self._issue_command(
                "readback_error",
                callsign,
                readback=readback_text,
                instruction=f"{callsign}, readback incorrect, say again clearance",
            )
        return verified

    def is_readback_verified(self, callsign: str) -> bool:
        return self._aircraft_states.get(callsign) == DeliveryState.READBACK_VERIFIED

    # ── Release to Ground ──

    def release_to_ground(self, callsign: str) -> None:
        if self._aircraft_states.get(callsign) != DeliveryState.READBACK_VERIFIED:
            return
        self._aircraft_states[callsign] = DeliveryState.RELEASED
        self.log_status_change(
            callsign, DeliveryState.READBACK_VERIFIED.value,
            DeliveryState.RELEASED.value,
            command_type="release_to_ground",
        )
        self._issue_command(
            "release_to_ground",
            callsign,
            instruction=(
                f"{callsign}, contact Ground on"
                f" {self.airport_icao}_GND"
            ),
        )
        self._propose_handoff(
            callsign,
            to_controller=f"{self.airport_icao}_GND",
            frequency=0.0,
        )

    # ── Holding Instructions ──

    def issue_holding_instruction(
        self,
        callsign: str,
        fix: str,
        altitude_ft: int,
        leg_direction: str = "left",
        inbound_heading: Optional[float] = None,
        outbound_heading: Optional[float] = None,
        leg_length: str = "1 minute",
        expected_approach_time: Optional[str] = None,
    ) -> HoldingInstruction:
        self.accept_aircraft(callsign)
        instruction = HoldingInstruction(
            callsign=callsign,
            fix=fix,
            altitude_ft=altitude_ft,
            leg_direction=leg_direction,
            inbound_heading=inbound_heading,
            outbound_heading=outbound_heading,
            leg_length=leg_length,
            expected_approach_time=expected_approach_time,
        )
        self._holding_instructions[callsign] = instruction
        self.set_clearance_state(
            callsign, "holding",
            fix=fix, altitude=altitude_ft,
            leg_direction=leg_direction,
        )
        prev = self._aircraft_states.get(callsign)
        self._aircraft_states[callsign] = (
            prev or DeliveryState.CLEARANCE_ISSUED
        )
        self.log_status_change(
            callsign, prev.value if prev else None,
            DeliveryState.CLEARANCE_ISSUED.value,
            command_type="holding_instruction",
        )
        leg_label = f"{leg_direction}-hand" if leg_direction else ""
        leg_len = f", {leg_length} legs" if leg_length else ""
        eat = (
            f", expect approach at {expected_approach_time}"
            if expected_approach_time else ""
        )
        hdg = f", inbound heading {inbound_heading}" if inbound_heading else ""
        self._issue_command(
            "holding_instruction",
            callsign,
            fix=fix,
            altitude_ft=altitude_ft,
            leg_direction=leg_direction,
            instruction=(
                f"{callsign}, hold at {fix}, {altitude_ft}ft"
                f", {leg_label} turns{leg_len}{hdg}{eat}"
            ),
        )
        return instruction

    # ── Missed Approach Procedures ──

    def issue_missed_approach(
        self,
        callsign: str,
        missed_point: str = "",
        climb_to_alt_ft: int = 3000,
        heading: Optional[float] = None,
        contact_frequency: Optional[float] = None,
        instructions: str = "",
    ) -> MissedApproachProcedure:
        self.accept_aircraft(callsign)
        procedure = MissedApproachProcedure(
            callsign=callsign,
            missed_approach_point=missed_point,
            climb_to_altitude_ft=climb_to_alt_ft,
            heading=heading,
            contact_frequency_mhz=contact_frequency,
            instructions=instructions,
        )
        self._missed_approach_procedures[callsign] = procedure
        self.set_clearance_state(
            callsign, "missed_approach",
            missed_point=missed_point,
            climb_alt=climb_to_alt_ft,
            heading=heading,
        )
        prev_state = self._aircraft_states.get(callsign)
        self.log_status_change(
            callsign,
            prev_state.value if prev_state else None,
            "missed_approach",
            command_type="missed_approach",
        )
        point = f" at {missed_point}" if missed_point else ""
        alt = f", climb to {climb_to_alt_ft}ft"
        hdg = f", heading {heading}" if heading else ""
        freq = f", contact {contact_frequency}" if contact_frequency else ""
        extra = f", {instructions}" if instructions else ""
        self._issue_command(
            "missed_approach",
            callsign,
            missed_point=missed_point,
            climb_altitude_ft=climb_to_alt_ft,
            heading=heading,
            contact_frequency_mhz=contact_frequency,
            instruction=f"{callsign}, missed approach{point}{alt}{hdg}{freq}{extra}",
        )
        return procedure

    def cancel_missed_approach(self, callsign: str) -> None:
        self._missed_approach_procedures.pop(callsign, None)
        self._issue_command(
            "cancel_missed_approach",
            callsign,
            instruction=(
                f"{callsign}, missed approach cancelled,"
                f" resume normal navigation"
            ),
        )

    # ── Release ──

    def release_aircraft(self, callsign: str) -> bool:
        self._aircraft_states.pop(callsign, None)
        self._craft_clearances.pop(callsign, None)
        self._holding_instructions.pop(callsign, None)
        self._missed_approach_procedures.pop(callsign, None)
        self.revoke_clearance(callsign)
        return super().release_aircraft(callsign)

    # ── Internal Helpers ──

    def _format_craft_text(
        self, callsign: str, clearance: CraftClearance,
    ) -> str:
        route = clearance.route or clearance.sid_name
        return (
            f"{callsign}, cleared to {clearance.destination} airport"
            f" via the {route} departure"
            f", climb to {clearance.initial_altitude_ft}ft"
            f", departure frequency {clearance.departure_frequency_mhz}"
            f", squawk {clearance.squawk}"
            f"{', ' + clearance.remarks if clearance.remarks else ''}"
        )

    def _check_readback(
        self, clearance: CraftClearance, readback: str,
    ) -> bool:
        rb_lower = readback.lower()
        checks = [
            clearance.destination.lower() in rb_lower,
            clearance.sid_name.lower() in rb_lower,
            str(clearance.initial_altitude_ft) in rb_lower,
            clearance.squawk in rb_lower,
        ]
        return all(checks)

    def process(self, dt: float, context: Dict[str, Any]) -> None:
        pass
