from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from .base import BaseController
from .manager import ControllerManager
from .models import AircraftHandoff, FlightContext


class HandoffManager:
    _contexts: Dict[str, FlightContext]
    _ctrl_mgr: Optional[ControllerManager]
    _handoff_cache: List[AircraftHandoff]

    def __init__(self, controller_manager: Optional[ControllerManager] = None):
        self._contexts: Dict[str, FlightContext] = {}
        self._ctrl_mgr = controller_manager
        self._handoff_cache: List[AircraftHandoff] = []

    def set_controller_manager(self, mgr: ControllerManager) -> None:
        self._ctrl_mgr = mgr

    # ──────────────────────────────────────────
    # Flight Context Management
    # ──────────────────────────────────────────

    def register_flight(self, callsign: str, **kwargs: Any) -> FlightContext:
        ctx = FlightContext(callsign=callsign, **kwargs)
        self._contexts[callsign] = ctx
        return ctx

    def get_context(self, callsign: str) -> Optional[FlightContext]:
        return self._contexts.get(callsign)

    def update_context(self, callsign: str, **kwargs: Any) -> None:
        ctx = self._contexts.get(callsign)
        if ctx:
            for k, v in kwargs.items():
                setattr(ctx, k, v)

    def add_history(
        self, callsign: str, controller: str,
        action: str, details: Optional[Dict[str, Any]] = None,
    ) -> None:
        ctx = self._contexts.get(callsign)
        if ctx:
            ctx.history.append({
                "timestamp": time.time(),
                "controller": controller,
                "action": action,
                "details": details or {},
            })

    # ──────────────────────────────────────────
    # Handoff Trigger Checks
    # ──────────────────────────────────────────

    def check_altitude(
        self, callsign: str,
        threshold_ft: float, above: bool = True,
    ) -> bool:
        ctx = self._contexts.get(callsign)
        if not ctx:
            return False
        return ctx.current_alt_ft >= threshold_ft if above else ctx.current_alt_ft <= threshold_ft

    def check_spatial(
        self, callsign: str,
        distance_to_boundary_nm: float, threshold_nm: float,
    ) -> bool:
        return 0.0 <= distance_to_boundary_nm <= threshold_nm

    def check_clearance(
        self, callsign: str,
        clearance_type: str, controller: BaseController,
    ) -> bool:
        clr = controller.get_clearance_state(callsign)
        if not clr:
            return False
        return clr.clearance_type == clearance_type and clr.is_active

    # ──────────────────────────────────────────
    # Frequency Change Instruction
    # ──────────────────────────────────────────

    def _issue_frequency_change(
        self, source: BaseController, callsign: str,
        target_name: str, freq: float,
    ) -> None:
        source._issue_command(
            "frequency_change",
            callsign,
            controller=target_name,
            frequency=freq,
            instruction=f"Contact {target_name} on {freq}",
        )

    # ──────────────────────────────────────────
    # Transition: Ground -> Tower
    # ──────────────────────────────────────────

    def transition_ground_to_tower(
        self, ground: BaseController, callsign: str,
        tower_callsign: str, tower_freq: float, runway: str,
    ) -> Optional[AircraftHandoff]:
        if not ground.is_controlling(callsign):
            return None
        self.update_context(callsign,
                            previous_controller=ground.callsign,
                            current_controller=tower_callsign,
                            assigned_runway=runway,
                            current_alt_ft=0.0)
        self.add_history(callsign, ground.callsign, "transition_ground_to_tower",
                         {"runway": runway, "tower": tower_callsign, "freq": tower_freq})
        self._issue_frequency_change(ground, callsign, tower_callsign, tower_freq)
        ground.report_holding_short(callsign, runway)
        handoffs = ground.get_pending_handoffs()
        handoff = handoffs[0] if handoffs else None
        if handoff:
            self._handoff_cache.append(handoff)
        return handoff

    # ──────────────────────────────────────────
    # Transition: Tower (departure) -> Departure
    # ──────────────────────────────────────────

    def transition_tower_to_departure(
        self, tower: BaseController, callsign: str,
        departure_callsign: str, departure_freq: float,
        runway: str, alt_ft: float, sid_name: str = "",
    ) -> Optional[AircraftHandoff]:
        if not tower.is_controlling(callsign):
            return None
        ctx_kwargs = dict(
            previous_controller=tower.callsign,
            current_controller=departure_callsign,
            assigned_runway=runway,
            current_alt_ft=alt_ft,
        )
        if sid_name:
            ctx_kwargs["sid_name"] = sid_name
        self.update_context(callsign, **ctx_kwargs)
        self.add_history(callsign, tower.callsign, "transition_tower_to_departure",
                         {"runway": runway, "altitude": alt_ft, "sid": sid_name,
                          "departure": departure_callsign, "freq": departure_freq})
        self._issue_frequency_change(tower, callsign, departure_callsign, departure_freq)
        tower.departure_airborne(callsign, runway, time.time())
        handoffs = tower.get_pending_handoffs()
        handoff = handoffs[0] if handoffs else None
        if handoff:
            self._handoff_cache.append(handoff)
        return handoff

    # ──────────────────────────────────────────
    # Transition: Departure -> Center
    # ──────────────────────────────────────────

    def transition_departure_to_center(
        self, departure: BaseController, callsign: str,
        center_callsign: str, center_freq: float, alt_ft: float,
    ) -> Optional[AircraftHandoff]:
        if not departure.is_controlling(callsign):
            return None
        self.update_context(callsign,
                            previous_controller=departure.callsign,
                            current_controller=center_callsign,
                            current_alt_ft=alt_ft)
        self.add_history(callsign, departure.callsign, "transition_departure_to_center",
                         {"altitude": alt_ft, "center": center_callsign, "freq": center_freq})
        departure.handoff_to_center(callsign, center_callsign, center_freq)
        handoffs = departure.get_pending_handoffs()
        handoff = handoffs[0] if handoffs else None
        if handoff:
            self._handoff_cache.append(handoff)
        return handoff

    # ──────────────────────────────────────────
    # Transition: Center -> Approach
    # ──────────────────────────────────────────

    def transition_center_to_approach(
        self, center: BaseController, callsign: str,
        approach_callsign: str, approach_freq: float,
        alt_ft: float, star_info: Optional[Dict[str, Any]] = None,
    ) -> Optional[AircraftHandoff]:
        if not center.is_controlling(callsign):
            return None
        star_name = (star_info or {}).get("star_name", "")
        approach_runway = (star_info or {}).get("approach_runway", "")
        ctx_kwargs = dict(
            previous_controller=center.callsign,
            current_controller=approach_callsign,
            current_alt_ft=alt_ft,
            assigned_runway=approach_runway or None,
        )
        if star_name:
            ctx_kwargs["star_name"] = star_name
        self.update_context(callsign, **ctx_kwargs)
        self.add_history(callsign, center.callsign, "transition_center_to_approach",
                         {"altitude": alt_ft, "star_info": star_info,
                          "approach": approach_callsign, "freq": approach_freq})
        center.handoff_to_approach(callsign, approach_callsign, approach_freq)
        handoffs = center.get_pending_handoffs()
        handoff = handoffs[0] if handoffs else None
        if handoff:
            self._handoff_cache.append(handoff)
        return handoff

    # ──────────────────────────────────────────
    # Transition: Approach -> Tower
    # ──────────────────────────────────────────

    def transition_approach_to_tower(
        self, approach: BaseController, callsign: str,
        tower_callsign: str, tower_freq: float, runway: str,
    ) -> Optional[AircraftHandoff]:
        if not approach.is_controlling(callsign):
            return None
        self.update_context(callsign,
                            previous_controller=approach.callsign,
                            current_controller=tower_callsign,
                            assigned_runway=runway)
        self.add_history(callsign, approach.callsign, "transition_approach_to_tower",
                         {"runway": runway, "tower": tower_callsign, "freq": tower_freq})
        approach.handoff_to_tower(callsign, tower_callsign, tower_freq)
        handoffs = approach.get_pending_handoffs()
        handoff = handoffs[0] if handoffs else None
        if handoff:
            self._handoff_cache.append(handoff)
        return handoff

    # ──────────────────────────────────────────
    # Transition: Tower (arrival) -> Ground
    # ──────────────────────────────────────────

    def transition_tower_to_ground(
        self, tower: BaseController, callsign: str,
        ground_callsign: str, ground_freq: float,
        runway: str, gate: str = "",
    ) -> Optional[AircraftHandoff]:
        if not tower.is_controlling(callsign):
            return None
        self.update_context(callsign,
                            previous_controller=tower.callsign,
                            current_controller=ground_callsign,
                            assigned_runway=runway,
                            gate=gate or None)
        self.add_history(callsign, tower.callsign, "transition_tower_to_ground",
                         {"runway": runway, "gate": gate,
                          "ground": ground_callsign, "freq": ground_freq})
        self._issue_frequency_change(tower, callsign, ground_callsign, ground_freq)
        tower.arrival_landed(callsign, runway, time.time())
        handoffs = tower.get_pending_handoffs()
        handoff = handoffs[0] if handoffs else None
        if handoff:
            self._handoff_cache.append(handoff)
        return handoff

    # ──────────────────────────────────────────
    # Handoff Routing via ControllerManager
    # ──────────────────────────────────────────

    def route_handoff(self, handoff: AircraftHandoff) -> bool:
        if not self._ctrl_mgr:
            return False
        result = self._ctrl_mgr.route_handoff(handoff)
        if result:
            self.add_history(
                handoff.callsign, handoff.from_controller,
                "handoff_accepted",
                {"to": handoff.to_controller, "frequency": handoff.frequency},
            )
        return result

    def process_all_pending_handoffs(self) -> int:
        if not self._ctrl_mgr:
            return 0
        count = 0
        handoffs = self._ctrl_mgr.collect_handoffs()
        for h in handoffs:
            if self._ctrl_mgr.route_handoff(h):
                self.add_history(
                    h.callsign, h.from_controller,
                    "handoff_accepted",
                    {"to": h.to_controller, "frequency": h.frequency},
                )
                count += 1
        for h in self._handoff_cache:
            if self._ctrl_mgr.route_handoff(h):
                self.add_history(
                    h.callsign, h.from_controller,
                    "handoff_accepted",
                    {"to": h.to_controller, "frequency": h.frequency},
                )
                count += 1
        self._handoff_cache.clear()
        return count

    def get_full_history(self, callsign: str) -> List[Dict[str, Any]]:
        ctx = self._contexts.get(callsign)
        if not ctx:
            return []
        return list(ctx.history)
