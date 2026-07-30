from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from .base import BaseController
from .models import (
    ClearanceState,
    ControllerState,
    GroundState,
    TaxiProgress,
    TaxiRefusalReason,
)


class GroundController(BaseController):
    _aircraft_states: Dict[str, GroundState]
    _taxi_progress: Dict[str, TaxiProgress]
    _occupied_taxiways: Set[str]

    def __init__(
        self,
        callsign: str,
        frequency: float,
        sector_id: str,
        airport_icao: str,
    ):
        super().__init__(callsign, frequency, sector_id, airport_icao=airport_icao)
        self._aircraft_states: Dict[str, GroundState] = {}
        self._taxi_progress: Dict[str, TaxiProgress] = {}
        self._occupied_taxiways: Set[str] = set()
        self._state = ControllerState.ACTIVE

    def get_aircraft_ground_state(self, callsign: str) -> Optional[GroundState]:
        return self._aircraft_states.get(callsign)

    def request_startup(self, callsign: str, gate: str) -> None:
        self.accept_aircraft(callsign)
        prev = self._aircraft_states.get(callsign)
        self._aircraft_states[callsign] = GroundState.STARTUP
        self.set_clearance_state(callsign, "startup", gate=gate)
        self.log_status_change(
            callsign, prev.value if prev else None,
            GroundState.STARTUP.value,
            command_type="startup",
        )
        self._issue_command(
            "startup",
            callsign,
            gate=gate,
            instruction=f"Startup approved at gate {gate}",
        )

    def request_pushback(
        self, callsign: str, gate: str, direction: str = "tail_east"
    ) -> None:
        self.accept_aircraft(callsign)
        prev = self._aircraft_states.get(callsign)
        self._aircraft_states[callsign] = GroundState.PUSHBACK_IN_PROGRESS
        self.set_clearance_state(callsign, "pushback", gate=gate, direction=direction)
        self.log_status_change(
            callsign, prev.value if prev else None,
            GroundState.PUSHBACK_IN_PROGRESS.value,
            command_type="pushback",
        )
        self._issue_command(
            "pushback",
            callsign,
            gate=gate,
            direction=direction,
            instruction=f"Pushback approved, {direction}",
        )

    def pushback_complete(
        self, callsign: str, taxi_route: Optional[List[str]] = None
    ) -> None:
        if not self.is_controlling(callsign):
            return
        prev = self._aircraft_states.get(callsign)
        self._aircraft_states[callsign] = GroundState.TAXI_CLEARED
        self.log_status_change(
            callsign, prev.value if prev else None,
            GroundState.TAXI_CLEARED.value,
            command_type="taxi",
        )
        self.acknowledge_clearance(callsign)
        route_str = " via " + " ".join(taxi_route) if taxi_route else ""
        self._issue_command(
            "taxi",
            callsign,
            route=taxi_route or [],
            instruction=f"Taxi to runway{route_str}",
        )
        if taxi_route:
            start_node = taxi_route[0]
            self._taxi_progress[callsign] = TaxiProgress(
                callsign=callsign,
                cleared_nodes=list(taxi_route),
                visited_nodes=[start_node],
                current_node_id=start_node,
            )

    def clear_taxi(
        self,
        callsign: str,
        from_node: str,
        to_node: str,
        route_nodes: Optional[List[str]] = None,
    ) -> Optional[GroundState]:
        if not self.is_controlling(callsign):
            return None

        state = self._aircraft_states.get(callsign)
        if state not in (
            GroundState.PUSHBACK_IN_PROGRESS,
            GroundState.TAXI_CLEARED,
            GroundState.ARRIVAL_GROUND,
        ):
            return None

        if not route_nodes:
            self._issue_command(
                "taxi_refused",
                callsign,
                reason=TaxiRefusalReason.NO_ROUTE_AVAILABLE.value,
                instruction="Unable to issue taxi clearance, no route available",
            )
            return None

        if route_nodes[0] != from_node:
            self._issue_command(
                "taxi_refused",
                callsign,
                reason=TaxiRefusalReason.INVALID_START_POINT.value,
                instruction="Unable to issue taxi, incorrect start position",
            )
            return None

        for node in route_nodes:
            if node in self._occupied_taxiways:
                self._issue_command(
                    "taxi_refused",
                    callsign,
                    reason=TaxiRefusalReason.TAXIWAY_OCCUPIED.value,
                    instruction=f"Unable to issue taxi, taxiway occupied at {node}",
                )
                return None

        prev = self._aircraft_states.get(callsign)
        self._aircraft_states[callsign] = GroundState.TAXI_CLEARED
        self.set_clearance_state(
            callsign, "taxi",
            from_node=from_node, to_node=to_node, route=route_nodes,
        )
        self.log_status_change(
            callsign, prev.value if prev else None,
            GroundState.TAXI_CLEARED.value,
            command_type="taxi",
        )
        route_desc = " via " + " ".join(route_nodes)
        self._issue_command(
            "taxi",
            callsign,
            from_node=from_node,
            to_node=to_node,
            route=route_nodes,
            instruction=f"Taxi to {to_node}{route_desc}",
        )
        start_node = route_nodes[0]
        self._taxi_progress[callsign] = TaxiProgress(
            callsign=callsign,
            cleared_nodes=list(route_nodes),
            visited_nodes=[start_node],
            current_node_id=start_node,
        )
        return GroundState.TAXI_CLEARED

    def refuse_taxi(
        self,
        callsign: str,
        reason: TaxiRefusalReason,
        detail: str = "",
    ) -> None:
        if not self.is_controlling(callsign):
            return
        self._issue_command(
            "taxi_refused",
            callsign,
            reason=reason.value,
            detail=detail,
            instruction=(
                f"Taxi clearance refused: {reason.value}"
                f"{' - ' + detail if detail else ''}"
            ),
        )

    def clear_cross_runway(self, callsign: str, runway: str) -> None:
        if not self.is_controlling(callsign):
            return
        prev = self._aircraft_states.get(callsign)
        self._aircraft_states[callsign] = GroundState.CROSSING_RUNWAY
        self.set_clearance_state(callsign, "cross_runway", runway=runway)
        self.log_status_change(
            callsign, prev.value if prev else None,
            GroundState.CROSSING_RUNWAY.value,
            command_type="cross_runway",
        )
        self._issue_command(
            "cross_runway",
            callsign,
            runway=runway,
            instruction=f"Cross runway {runway}, report vacated",
        )

    def crossing_complete(self, callsign: str, runway: str) -> None:
        if not self.is_controlling(callsign):
            return
        prev = self._aircraft_states.get(callsign)
        self._aircraft_states[callsign] = GroundState.TAXI_CLEARED
        self.log_status_change(
            callsign, prev.value if prev else None,
            GroundState.TAXI_CLEARED.value,
            command_type="crossing_complete",
        )
        self._issue_command(
            "crossing_complete",
            callsign,
            runway=runway,
            instruction=f"Runway {runway} vacated, continue taxi",
        )

    def report_holding_short(
        self, callsign: str, runway: str
    ) -> None:
        if not self.is_controlling(callsign):
            return
        prev = self._aircraft_states.get(callsign)
        self._aircraft_states[callsign] = GroundState.HOLDING_SHORT
        self.log_status_change(
            callsign, prev.value if prev else None,
            GroundState.HOLDING_SHORT.value,
            command_type="hold_short",
        )
        self._issue_command(
            "hold_short",
            callsign,
            runway=runway,
            instruction=f"Hold short of runway {runway}",
        )
        self._propose_handoff(
            callsign,
            to_controller=f"{self.airport_icao}_TWR",
            frequency=0.0,
        )

    def hold_short_of_runway(
        self, callsign: str, runway: str, reason: str = ""
    ) -> None:
        if not self.is_controlling(callsign):
            return
        prev = self._aircraft_states.get(callsign)
        self._aircraft_states[callsign] = GroundState.HOLDING_SHORT
        self.log_status_change(
            callsign, prev.value if prev else None,
            GroundState.HOLDING_SHORT.value,
            command_type="hold_short",
        )
        msg = f"Hold short of runway {runway}{' - ' + reason if reason else ''}"
        self._issue_command(
            "hold_short",
            callsign,
            runway=runway,
            reason=reason,
            instruction=msg,
        )

    def report_position(self, callsign: str, node_id: str) -> None:
        if not self.is_controlling(callsign):
            return
        progress = self._taxi_progress.get(callsign)
        if not progress:
            return
        if node_id not in progress.cleared_nodes:
            self._issue_command(
                "position_warning",
                callsign,
                reported_node=node_id,
                instruction=f"Position {node_id} not on cleared route",
            )
            return
        if node_id not in progress.visited_nodes:
            progress.visited_nodes.append(node_id)
        progress.current_node_id = node_id
        if node_id == progress.cleared_nodes[-1]:
            progress.route_completed = True

    def get_next_taxi_instruction(self, callsign: str) -> Optional[str]:
        progress = self._taxi_progress.get(callsign)
        if not progress or progress.route_completed:
            return None
        for node in progress.cleared_nodes:
            if node not in progress.visited_nodes:
                return f"Taxi to {node}"
        return None

    def get_taxi_progress(self, callsign: str) -> Optional[TaxiProgress]:
        return self._taxi_progress.get(callsign)

    def accept_arrival(self, callsign: str, runway: str, gate: str = "") -> None:
        self.accept_aircraft(callsign)
        self._aircraft_states[callsign] = GroundState.ARRIVAL_GROUND
        self.set_clearance_state(callsign, "arrival_taxi", runway=runway, gate=gate)
        self.log_status_change(
            callsign, None, GroundState.ARRIVAL_GROUND.value,
            command_type="contact_ground",
        )
        gate_str = f" to gate {gate}" if gate else ""
        self._issue_command(
            "contact_ground",
            callsign,
            runway=runway,
            gate=gate,
            instruction=(
                f"Contact Ground on {self.frequency},"
                f" taxi to stand{gate_str}"
            ),
        )

    def gate_arrival(self, callsign: str, gate: str) -> None:
        if not self.is_controlling(callsign):
            return
        self._aircraft_states.pop(callsign, None)
        self._taxi_progress.pop(callsign, None)
        self.revoke_clearance(callsign)
        self.release_aircraft(callsign)
        self._issue_command(
            "gate_arrival",
            callsign,
            gate=gate,
            instruction=f"Arrival at gate {gate}, engine shutdown approved",
        )

    def release_to_tower(self, callsign: str) -> None:
        self._aircraft_states.pop(callsign, None)
        self._taxi_progress.pop(callsign, None)
        self.revoke_clearance(callsign)
        self.release_aircraft(callsign)

    def process(self, dt: float, context: Dict[str, Any]) -> None:
        pass
