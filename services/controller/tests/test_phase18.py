import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from unittest.mock import patch

import pytest

from approach import ApproachController
from center import CenterController
from departure import DepartureController
from ground import GroundController
from handoff import HandoffManager
from manager import ControllerManager
from models import (
    ApproachState,
    CenterState,
    DepartureState,
    FlightContext,
    GroundState,
    TowerState,
)
from tower import TowerController


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────

@pytest.fixture
def controllers():
    gnd = GroundController("ESSA_GND", 121.8, "ESSA_GND", "ESSA")
    twr = TowerController("ESSA_TWR", 118.5, "ESSA_TWR", "ESSA", ["01L", "19R"])
    dep = DepartureController("ESSA_DEP", 124.3, "ESSA_DEP", "ESSA")
    ctr = CenterController("ESSA_CTR", 135.5, "ESSA_CTR", "Stockholm Center")
    app = ApproachController("ESSA_APP", 119.7, "ESSA_APP", "ESSA")
    return {
        "gnd": gnd,
        "twr": twr,
        "dep": dep,
        "ctr": ctr,
        "app": app,
    }


@pytest.fixture
def ctrl_mgr(controllers):
    mgr = ControllerManager()
    for c in controllers.values():
        mgr.add_controller(c)
    return mgr


@pytest.fixture
def hm(ctrl_mgr):
    mgr = HandoffManager(ctrl_mgr)
    return mgr


# ──────────────────────────────────────────────
# FlightContext
# ──────────────────────────────────────────────

class TestFlightContext:
    def test_create_with_all_fields(self):
        ctx = FlightContext(
            callsign="SAS901",
            aircraft_type="B738",
            origin="ESSA",
            destination="EKCH",
            current_alt_ft=35000,
            assigned_runway="01L",
            sid_name="ARN1N",
            star_name="KOGOS2A",
            approach_type="ils",
            gate="G12",
            current_controller="ESSA_CTR",
            previous_controller="ESSA_DEP",
            history=[{"action": "test"}],
        )
        assert ctx.callsign == "SAS901"
        assert ctx.aircraft_type == "B738"
        assert ctx.current_alt_ft == 35000
        assert len(ctx.history) == 1

    def test_create_minimal(self):
        ctx = FlightContext(callsign="SAS901")
        assert ctx.callsign == "SAS901"
        assert ctx.aircraft_type == ""
        assert ctx.history == []


# ──────────────────────────────────────────────
# Context Management
# ──────────────────────────────────────────────

class TestContextManagement:
    def test_register_flight(self, hm):
        ctx = hm.register_flight("SAS901", aircraft_type="B738", origin="ESSA")
        assert ctx.callsign == "SAS901"
        assert ctx.aircraft_type == "B738"
        assert hm.get_context("SAS901") is ctx

    def test_get_context_unknown(self, hm):
        assert hm.get_context("NONEXIST") is None

    def test_update_context(self, hm):
        hm.register_flight("SAS901")
        hm.update_context("SAS901", current_alt_ft=35000, assigned_runway="01L")
        ctx = hm.get_context("SAS901")
        assert ctx.current_alt_ft == 35000
        assert ctx.assigned_runway == "01L"

    def test_update_context_unknown(self, hm):
        hm.update_context("NONEXIST", current_alt_ft=10000)  # should not raise

    def test_add_history(self, hm):
        hm.register_flight("SAS901")
        hm.add_history("SAS901", "ESSA_GND", "pushback", {"gate": "G12"})
        ctx = hm.get_context("SAS901")
        assert len(ctx.history) == 1
        assert ctx.history[0]["action"] == "pushback"
        assert ctx.history[0]["details"]["gate"] == "G12"

    def test_add_history_unknown(self, hm):
        hm.add_history("NONEXIST", "CTRL", "test")  # should not raise

    def test_get_full_history(self, hm):
        hm.register_flight("SAS901")
        hm.add_history("SAS901", "GND", "pushback")
        hm.add_history("SAS901", "TWR", "takeoff")
        history = hm.get_full_history("SAS901")
        assert len(history) == 2

    def test_get_full_history_unknown(self, hm):
        assert hm.get_full_history("NONEXIST") == []


# ──────────────────────────────────────────────
# Trigger Checks
# ──────────────────────────────────────────────

class TestTriggerChecks:
    def test_check_altitude_above(self, hm):
        hm.register_flight("SAS901", current_alt_ft=35000)
        assert hm.check_altitude("SAS901", 30000, above=True) is True
        assert hm.check_altitude("SAS901", 40000, above=True) is False

    def test_check_altitude_below(self, hm):
        hm.register_flight("SAS901", current_alt_ft=5000)
        assert hm.check_altitude("SAS901", 10000, above=False) is True
        assert hm.check_altitude("SAS901", 3000, above=False) is False

    def test_check_altitude_unknown(self, hm):
        assert hm.check_altitude("NONEXIST", 10000) is False

    def test_check_spatial_within(self, hm):
        assert hm.check_spatial("SAS901", 30.0, 50.0) is True

    def test_check_spatial_beyond(self, hm):
        assert hm.check_spatial("SAS901", 100.0, 50.0) is False

    def test_check_spatial_negative(self, hm):
        assert hm.check_spatial("SAS901", -1.0, 50.0) is False

    def test_check_clearance_matches(self, hm, controllers):
        hm.register_flight("SAS901")
        controllers["dep"].accept_aircraft("SAS901")
        controllers["dep"].set_clearance_state("SAS901", "climb", target_alt=35000)
        assert hm.check_clearance("SAS901", "climb", controllers["dep"]) is True

    def test_check_clearance_no_match(self, hm, controllers):
        hm.register_flight("SAS901")
        controllers["dep"].accept_aircraft("SAS901")
        controllers["dep"].set_clearance_state("SAS901", "climb", target_alt=35000)
        assert hm.check_clearance("SAS901", "descend", controllers["dep"]) is False

    def test_check_clearance_no_clearance(self, hm, controllers):
        hm.register_flight("SAS901")
        assert hm.check_clearance("SAS901", "climb", controllers["dep"]) is False


# ──────────────────────────────────────────────
# Transition: Ground -> Tower
# ──────────────────────────────────────────────

class TestGroundToTower:
    def test_transition_proposes_handoff(self, hm, controllers):
        gnd = controllers["gnd"]
        gnd.request_pushback("SAS901", "G12")
        gnd.pushback_complete("SAS901", ["A", "B"])
        gnd.get_pending_commands()
        handoff = hm.transition_ground_to_tower(gnd, "SAS901", "ESSA_TWR", 118.5, "01L")
        assert handoff is not None
        assert handoff.to_controller == "ESSA_TWR"
        assert gnd.get_aircraft_ground_state("SAS901") == GroundState.HOLDING_SHORT

    def test_transition_issues_frequency_change(self, hm, controllers):
        gnd = controllers["gnd"]
        gnd.request_pushback("SAS901", "G12")
        gnd.pushback_complete("SAS901", ["A", "B"])
        gnd.get_pending_commands()
        hm.transition_ground_to_tower(gnd, "SAS901", "ESSA_TWR", 118.5, "01L")
        cmds = gnd.get_pending_commands()
        freq_commands = [c for c in cmds if c.command_type == "frequency_change"]
        assert len(freq_commands) == 1
        assert "118.5" in freq_commands[0].data["instruction"]

    def test_transition_updates_context(self, hm, controllers):
        gnd = controllers["gnd"]
        hm.register_flight("SAS901")
        gnd.request_pushback("SAS901", "G12")
        gnd.pushback_complete("SAS901", ["A", "B"])
        gnd.get_pending_commands()
        hm.transition_ground_to_tower(gnd, "SAS901", "ESSA_TWR", 118.5, "01L")
        ctx = hm.get_context("SAS901")
        assert ctx.current_controller == "ESSA_TWR"
        assert ctx.previous_controller == "ESSA_GND"
        assert ctx.assigned_runway == "01L"

    def test_transition_not_controlling(self, hm, controllers):
        gnd = controllers["gnd"]
        handoff = hm.transition_ground_to_tower(gnd, "NONEXIST", "ESSA_TWR", 118.5, "01L")
        assert handoff is None

    def test_transition_adds_history(self, hm, controllers):
        gnd = controllers["gnd"]
        hm.register_flight("SAS901")
        gnd.request_pushback("SAS901", "G12")
        gnd.pushback_complete("SAS901", ["A", "B"])
        gnd.get_pending_commands()
        hm.transition_ground_to_tower(gnd, "SAS901", "ESSA_TWR", 118.5, "01L")
        history = hm.get_full_history("SAS901")
        assert any(h["action"] == "transition_ground_to_tower" for h in history)

    def test_full_handoff_ground_to_tower(self, hm, ctrl_mgr, controllers):
        gnd = controllers["gnd"]
        twr = controllers["twr"]
        hm.register_flight("SAS901")
        gnd.request_pushback("SAS901", "G12")
        gnd.pushback_complete("SAS901", ["A", "B"])
        gnd.get_pending_commands()
        handoff = hm.transition_ground_to_tower(gnd, "SAS901", "ESSA_TWR", 118.5, "01L")
        assert handoff is not None
        hm.route_handoff(handoff)
        assert not gnd.is_controlling("SAS901")
        assert twr.is_controlling("SAS901")


# ──────────────────────────────────────────────
# Transition: Tower (departure) -> Departure
# ──────────────────────────────────────────────

class TestTowerToDeparture:
    def test_transition_proposes_handoff(self, hm, controllers):
        twr = controllers["twr"]
        twr.accept_from_ground("SAS901", "01L")
        twr.line_up("SAS901", "01L")
        twr.clear_takeoff("SAS901", "01L")
        twr.get_pending_commands()
        twr.get_pending_handoffs()
        handoff = hm.transition_tower_to_departure(
            twr, "SAS901", "ESSA_DEP", 124.3, "01L", 5000, "ARN1N",
        )
        assert handoff is not None
        assert handoff.to_controller == "ESSA_DEP"

    def test_transition_issues_frequency_change(self, hm, controllers):
        twr = controllers["twr"]
        twr.accept_from_ground("SAS901", "01L")
        twr.line_up("SAS901", "01L")
        twr.clear_takeoff("SAS901", "01L")
        twr.get_pending_commands()
        twr.get_pending_handoffs()
        hm.transition_tower_to_departure(twr, "SAS901", "ESSA_DEP", 124.3, "01L", 5000)
        cmds = twr.get_pending_commands()
        freq_commands = [c for c in cmds if c.command_type == "frequency_change"]
        assert len(freq_commands) == 1
        assert "124.3" in freq_commands[0].data["instruction"]

    def test_transition_updates_context(self, hm, controllers):
        twr = controllers["twr"]
        hm.register_flight("SAS901")
        twr.accept_from_ground("SAS901", "01L")
        twr.line_up("SAS901", "01L")
        twr.clear_takeoff("SAS901", "01L")
        twr.get_pending_commands()
        twr.get_pending_handoffs()
        hm.transition_tower_to_departure(twr, "SAS901", "ESSA_DEP", 124.3, "01L", 5000, "ARN1N")
        ctx = hm.get_context("SAS901")
        assert ctx.current_controller == "ESSA_DEP"
        assert ctx.previous_controller == "ESSA_TWR"
        assert ctx.assigned_runway == "01L"
        assert ctx.current_alt_ft == 5000
        assert ctx.sid_name == "ARN1N"

    def test_transition_not_controlling(self, hm, controllers):
        twr = controllers["twr"]
        handoff = hm.transition_tower_to_departure(
            twr, "NONEXIST", "ESSA_DEP", 124.3, "01L", 5000,
        )
        assert handoff is None


# ──────────────────────────────────────────────
# Transition: Departure -> Center
# ──────────────────────────────────────────────

class TestDepartureToCenter:
    def test_transition_proposes_handoff(self, hm, controllers):
        dep = controllers["dep"]
        dep.accept_from_tower("SAS901")
        dep.assign_sid("SAS901", "ARN1N", 5000)
        dep.get_pending_commands()
        handoff = hm.transition_departure_to_center(
            dep, "SAS901", "ESSA_CTR", 135.5, 10000,
        )
        assert handoff is not None
        assert handoff.to_controller == "ESSA_CTR"
        assert dep.get_aircraft_departure_state("SAS901") == DepartureState.HANDOFF

    def test_transition_updates_context(self, hm, controllers):
        dep = controllers["dep"]
        hm.register_flight("SAS901", sid_name="ARN1N")
        dep.accept_from_tower("SAS901")
        dep.assign_sid("SAS901", "ARN1N", 5000)
        dep.get_pending_commands()
        hm.transition_departure_to_center(dep, "SAS901", "ESSA_CTR", 135.5, 10000)
        ctx = hm.get_context("SAS901")
        assert ctx.current_controller == "ESSA_CTR"
        assert ctx.previous_controller == "ESSA_DEP"
        assert ctx.current_alt_ft == 10000


# ──────────────────────────────────────────────
# Transition: Center -> Approach
# ──────────────────────────────────────────────

class TestCenterToApproach:
    def test_transition_proposes_handoff(self, hm, controllers):
        ctr = controllers["ctr"]
        ctr.accept_from_departure("SAS901", 30000)
        ctr.get_pending_commands()
        handoff = hm.transition_center_to_approach(
            ctr, "SAS901", "ESSA_APP", 119.7, 8000,
            star_info={"star_name": "KOGOS2A", "approach_runway": "01L"},
        )
        assert handoff is not None
        assert handoff.to_controller == "ESSA_APP"
        assert ctr.get_aircraft_center_state("SAS901") == CenterState.HANDOFF

    def test_transition_updates_context(self, hm, controllers):
        ctr = controllers["ctr"]
        hm.register_flight("SAS901")
        ctr.accept_from_departure("SAS901", 30000)
        ctr.get_pending_commands()
        hm.transition_center_to_approach(
            ctr, "SAS901", "ESSA_APP", 119.7, 8000,
            star_info={"star_name": "KOGOS2A", "approach_runway": "01L"},
        )
        ctx = hm.get_context("SAS901")
        assert ctx.current_controller == "ESSA_APP"
        assert ctx.previous_controller == "ESSA_CTR"
        assert ctx.current_alt_ft == 8000
        assert ctx.star_name == "KOGOS2A"
        assert ctx.assigned_runway == "01L"

    def test_transition_without_star(self, hm, controllers):
        ctr = controllers["ctr"]
        hm.register_flight("SAS901")
        ctr.accept_from_departure("SAS901", 30000)
        ctr.get_pending_commands()
        hm.transition_center_to_approach(ctr, "SAS901", "ESSA_APP", 119.7, 8000)
        ctx = hm.get_context("SAS901")
        assert ctx.star_name == ""
        assert ctx.assigned_runway is None


# ──────────────────────────────────────────────
# Transition: Approach -> Tower
# ──────────────────────────────────────────────

class TestApproachToTower:
    def test_transition_proposes_handoff(self, hm, controllers):
        app = controllers["app"]
        app.accept_from_center("SAS901", 8000)
        app.clear_ils("SAS901", "01L", 110.3)
        app.get_pending_commands()
        handoff = hm.transition_approach_to_tower(
            app, "SAS901", "ESSA_TWR", 118.5, "01L",
        )
        assert handoff is not None
        assert handoff.to_controller == "ESSA_TWR"
        assert app.get_aircraft_approach_state("SAS901") == ApproachState.FINAL

    def test_transition_updates_context(self, hm, controllers):
        app = controllers["app"]
        hm.register_flight("SAS901", approach_type="ils")
        app.accept_from_center("SAS901", 8000)
        app.clear_ils("SAS901", "01L", 110.3)
        app.get_pending_commands()
        hm.transition_approach_to_tower(app, "SAS901", "ESSA_TWR", 118.5, "01L")
        ctx = hm.get_context("SAS901")
        assert ctx.current_controller == "ESSA_TWR"
        assert ctx.previous_controller == "ESSA_APP"
        assert ctx.assigned_runway == "01L"


# ──────────────────────────────────────────────
# Transition: Tower (arrival) -> Ground
# ──────────────────────────────────────────────

class TestTowerToGround:
    def test_transition_proposes_handoff(self, hm, controllers):
        twr = controllers["twr"]
        twr.clear_landing("SAS901", "01L")
        twr.get_pending_commands()
        handoff = hm.transition_tower_to_ground(
            twr, "SAS901", "ESSA_GND", 121.8, "01L", "G12",
        )
        assert handoff is not None
        assert handoff.to_controller == "ESSA_GND"

    def test_transition_issues_frequency_change(self, hm, controllers):
        twr = controllers["twr"]
        twr.clear_landing("SAS901", "01L")
        twr.get_pending_commands()
        hm.transition_tower_to_ground(twr, "SAS901", "ESSA_GND", 121.8, "01L", "G12")
        cmds = twr.get_pending_commands()
        freq_commands = [c for c in cmds if c.command_type == "frequency_change"]
        assert len(freq_commands) == 1
        assert "121.8" in freq_commands[0].data["instruction"]

    def test_transition_updates_context(self, hm, controllers):
        twr = controllers["twr"]
        hm.register_flight("SAS901")
        twr.clear_landing("SAS901", "01L")
        twr.get_pending_commands()
        hm.transition_tower_to_ground(twr, "SAS901", "ESSA_GND", 121.8, "01L", "G12")
        ctx = hm.get_context("SAS901")
        assert ctx.current_controller == "ESSA_GND"
        assert ctx.previous_controller == "ESSA_TWR"
        assert ctx.assigned_runway == "01L"
        assert ctx.gate == "G12"


# ──────────────────────────────────────────────
# Handoff Routing
# ──────────────────────────────────────────────

class TestHandoffRouting:
    def test_route_handoff_via_ctrl_mgr(self, hm, ctrl_mgr, controllers):
        gnd = controllers["gnd"]
        twr = controllers["twr"]
        hm.register_flight("SAS901")
        gnd.accept_aircraft("SAS901")
        gnd._propose_handoff("SAS901", "ESSA_TWR", 118.5)
        handoffs = gnd.get_pending_handoffs()
        assert len(handoffs) == 1
        result = hm.route_handoff(handoffs[0])
        assert result is True
        assert not gnd.is_controlling("SAS901")
        assert twr.is_controlling("SAS901")

    def test_route_handoff_adds_history(self, hm, ctrl_mgr, controllers):
        gnd = controllers["gnd"]
        hm.register_flight("SAS901")
        gnd.accept_aircraft("SAS901")
        gnd._propose_handoff("SAS901", "ESSA_TWR", 118.5)
        handoffs = gnd.get_pending_handoffs()
        hm.route_handoff(handoffs[0])
        history = hm.get_full_history("SAS901")
        assert any(h["action"] == "handoff_accepted" for h in history)

    def test_route_handoff_no_manager(self, controllers):
        hm = HandoffManager()
        gnd = controllers["gnd"]
        gnd.accept_aircraft("SAS901")
        gnd._propose_handoff("SAS901", "ESSA_TWR", 118.5)
        handoffs = gnd.get_pending_handoffs()
        result = hm.route_handoff(handoffs[0])
        assert result is False

    def test_process_all_pending_handoffs(self, hm, ctrl_mgr, controllers):
        gnd = controllers["gnd"]
        twr = controllers["twr"]
        hm.register_flight("SAS901")
        gnd.accept_aircraft("SAS901")
        gnd._propose_handoff("SAS901", "ESSA_TWR", 118.5)
        count = hm.process_all_pending_handoffs()
        assert count == 1
        assert twr.is_controlling("SAS901")

    def test_process_all_no_handoffs(self, hm):
        count = hm.process_all_pending_handoffs()
        assert count == 0


# ──────────────────────────────────────────────
# End-to-End Full Flight Loop
# ──────────────────────────────────────────────

class TestEndToEnd:
    def _build_airport(self):
        gnd = GroundController("ESSA_GND", 121.8, "ESSA_GND", "ESSA")
        twr = TowerController("ESSA_TWR", 118.5, "ESSA_TWR", "ESSA", ["01L", "19R"])
        dep = DepartureController("ESSA_DEP", 124.3, "ESSA_DEP", "ESSA")
        ctr = CenterController("ESSA_CTR", 135.5, "ESSA_CTR", "Stockholm Center")
        app = ApproachController("ESSA_APP", 119.7, "ESSA_APP", "ESSA")
        mgr = ControllerManager()
        for c in [gnd, twr, dep, ctr, app]:
            mgr.add_controller(c)
        hm = HandoffManager(mgr)
        return {
            "gnd": gnd, "twr": twr, "dep": dep,
            "ctr": ctr, "app": app,
            "mgr": mgr, "hm": hm,
        }

    def test_full_flight_loop(self):
        env = self._build_airport()
        gnd = env["gnd"]
        twr = env["twr"]
        dep = env["dep"]
        ctr = env["ctr"]
        app = env["app"]
        mgr = env["mgr"]
        hm = env["hm"]

        callsign = "SAS901"

        # --- Register flight ---
        hm.register_flight(callsign, aircraft_type="B738", origin="ESSA", destination="EKCH")

        # === PHASE 1: Ground (departure) ===
        gnd.request_pushback(callsign, "G12")
        gnd.pushback_complete(callsign, ["A", "B", "RWY01L"])
        assert gnd.get_aircraft_ground_state(callsign) == GroundState.TAXI_CLEARED
        gnd.get_pending_commands()

        # === TRANSITION 1: Ground -> Tower ===
        handoff = hm.transition_ground_to_tower(gnd, callsign, "ESSA_TWR", 118.5, "01L")
        assert handoff is not None
        assert handoff.to_controller == "ESSA_TWR"

        # Route handoff
        assert hm.route_handoff(handoff)
        assert not gnd.is_controlling(callsign)
        assert twr.is_controlling(callsign)

        # === PHASE 2: Tower (departure) ===
        # Tower manages the departure: line up, takeoff
        twr.accept_from_ground(callsign, "01L")
        twr.line_up(callsign, "01L")
        twr.clear_takeoff(callsign, "01L")
        assert twr.get_aircraft_tower_state(callsign) == TowerState.TAKEOFF_CLEARED
        twr.get_pending_commands()

        # === TRANSITION 2: Tower -> Departure ===
        handoff = hm.transition_tower_to_departure(
            twr, callsign, "ESSA_DEP", 124.3, "01L", 5000, "ARN1N",
        )
        assert handoff is not None
        assert handoff.to_controller == "ESSA_DEP"

        # Twr.departure_airborne already released aircraft. Route handoff for DEP side.
        assert hm.route_handoff(handoff)
        assert dep.is_controlling(callsign)

        # === PHASE 3: Departure ===
        dep.accept_from_tower(callsign, {"sid_name": "ARN1N", "initial_alt_ft": 5000})
        dep.assign_sid(callsign, "ARN1N", 5000)
        dep.radar_contact(callsign, 7000, "ARN1N")
        assert dep.get_aircraft_departure_state(callsign) == DepartureState.RADAR_CONTACT
        dep.assign_climb(callsign, 10000)
        dep.get_pending_commands()

        # === TRANSITION 3: Departure -> Center ===
        handoff = hm.transition_departure_to_center(
            dep, callsign, "ESSA_CTR", 135.5, 10000,
        )
        assert handoff is not None
        assert handoff.to_controller == "ESSA_CTR"

        assert hm.route_handoff(handoff)
        assert ctr.is_controlling(callsign)

        # === PHASE 4: Center ===
        ctr.accept_from_departure(callsign, 10000)
        ctr.assign_airway(callsign, "M852", "ARN", "KOGOS",
                          fixes=["ARN", "XILAN", "KOGOS"], flight_level=350)
        assert ctr.get_aircraft_center_state(callsign) == CenterState.CRUISE
        ctr.assign_climb(callsign, 35000)
        ctr.get_pending_commands()

        # Cruise + TOD
        ctr.assign_descent(callsign, 8000, "KOGOS2A")
        assert ctr.get_aircraft_center_state(callsign) == CenterState.DESCENT_CLEARED
        ctr.get_pending_commands()

        # === TRANSITION 4: Center -> Approach ===
        handoff = hm.transition_center_to_approach(
            ctr, callsign, "ESSA_APP", 119.7, 8000,
            star_info={"star_name": "KOGOS2A", "approach_runway": "01L"},
        )
        assert handoff is not None
        assert handoff.to_controller == "ESSA_APP"

        assert hm.route_handoff(handoff)
        assert app.is_controlling(callsign)

        # === PHASE 5: Approach ===
        app.accept_from_center(callsign, 8000,
                               star_info={"star_name": "KOGOS2A", "approach_runway": "01L"})
        app.assign_descent(callsign, 3000)
        app.vector_to_ils(callsign, 45, 3000)
        app.clear_ils(callsign, "01L", 110.3)
        assert app.get_aircraft_approach_state(callsign) == ApproachState.ILS_CLEARED
        app.get_pending_commands()

        # === TRANSITION 5: Approach -> Tower ===
        handoff = hm.transition_approach_to_tower(
            app, callsign, "ESSA_TWR", 118.5, "01L",
        )
        assert handoff is not None
        assert handoff.to_controller == "ESSA_TWR"

        assert hm.route_handoff(handoff)
        assert twr.is_controlling(callsign)  # twr now controls for landing

        # === PHASE 6: Tower (arrival) ===
        twr.clear_landing(callsign, "01L")
        assert twr.get_aircraft_tower_state(callsign) == TowerState.LANDING_CLEARED
        twr.get_pending_commands()

        # === TRANSITION 6: Tower -> Ground (arrival) ===
        handoff = hm.transition_tower_to_ground(
            twr, callsign, "ESSA_GND", 121.8, "01L", "G12",
        )
        assert handoff is not None
        assert handoff.to_controller == "ESSA_GND"

        assert hm.route_handoff(handoff)
        assert gnd.is_controlling(callsign)

        # === PHASE 7: Ground (arrival) ===
        gnd.accept_arrival(callsign, "01L", "G12")
        assert gnd.get_aircraft_ground_state(callsign) == GroundState.ARRIVAL_GROUND
        gnd.gate_arrival(callsign, "G12")
        assert not gnd.is_controlling(callsign)

        # === VERIFY FLIGHT CONTEXT ===
        ctx = hm.get_context(callsign)
        assert ctx is not None
        assert ctx.current_controller == "ESSA_GND"
        assert ctx.previous_controller == "ESSA_TWR"
        assert ctx.assigned_runway == "01L"
        assert ctx.gate == "G12"
        assert ctx.sid_name == "ARN1N"
        assert ctx.star_name == "KOGOS2A"
        assert ctx.aircraft_type == "B738"

        # === VERIFY COMPLETE HISTORY ===
        history = hm.get_full_history(callsign)
        expected_actions = [
            "transition_ground_to_tower",
            "handoff_accepted",
            "transition_tower_to_departure",
            "handoff_accepted",
            "transition_departure_to_center",
            "handoff_accepted",
            "transition_center_to_approach",
            "handoff_accepted",
            "transition_approach_to_tower",
            "handoff_accepted",
            "transition_tower_to_ground",
            "handoff_accepted",
        ]
        recorded_actions = [h["action"] for h in history]
        for action in expected_actions:
            assert action in recorded_actions, f"Missing history entry: {action}"

        # === VERIFY EARTH RETURNED TO GROUND ===
        assert gnd.aircraft_count == 0

    def test_flight_loop_via_process_all(self):
        """Same loop but using process_all_pending_handoffs for routing."""
        env = self._build_airport()
        gnd = env["gnd"]
        twr = env["twr"]
        dep = env["dep"]
        ctr = env["ctr"]
        app = env["app"]
        mgr = env["mgr"]
        hm = env["hm"]

        callsign = "SAS902"
        hm.register_flight(callsign)

        # Ground -> Tower
        gnd.request_pushback(callsign, "G12")
        gnd.pushback_complete(callsign, ["A", "B"])
        gnd.get_pending_commands()
        hm.transition_ground_to_tower(gnd, callsign, "ESSA_TWR", 118.5, "01L")
        assert hm.process_all_pending_handoffs() == 1
        assert twr.is_controlling(callsign)

        # Tower -> Departure
        twr.accept_from_ground(callsign, "01L")
        twr.line_up(callsign, "01L")
        twr.clear_takeoff(callsign, "01L")
        twr.get_pending_commands()
        hm.transition_tower_to_departure(twr, callsign, "ESSA_DEP", 124.3, "01L", 5000)
        assert hm.process_all_pending_handoffs() == 1
        assert dep.is_controlling(callsign)

        # Departure -> Center
        dep.accept_from_tower(callsign, {"sid_name": "ARN1N", "initial_alt_ft": 5000})
        dep.assign_sid(callsign, "ARN1N", 5000)
        dep.get_pending_commands()
        hm.transition_departure_to_center(dep, callsign, "ESSA_CTR", 135.5, 10000)
        assert hm.process_all_pending_handoffs() == 1
        assert ctr.is_controlling(callsign)

        # Center -> Approach
        ctr.accept_from_departure(callsign, 10000)
        ctr.assign_airway(callsign, "M852", "ARN", "KOGOS")
        ctr.assign_descent(callsign, 8000)
        ctr.get_pending_commands()
        hm.transition_center_to_approach(ctr, callsign, "ESSA_APP", 119.7, 8000)
        assert hm.process_all_pending_handoffs() == 1
        assert app.is_controlling(callsign)

        # Approach -> Tower
        app.accept_from_center(callsign, 8000)
        app.clear_ils(callsign, "01L", 110.3)
        app.get_pending_commands()
        hm.transition_approach_to_tower(app, callsign, "ESSA_TWR", 118.5, "01L")
        assert hm.process_all_pending_handoffs() == 1
        assert twr.is_controlling(callsign)

        # Tower -> Ground
        twr.clear_landing(callsign, "01L")
        twr.get_pending_commands()
        hm.transition_tower_to_ground(twr, callsign, "ESSA_GND", 121.8, "01L")
        assert hm.process_all_pending_handoffs() == 1
        assert gnd.is_controlling(callsign)

        gnd.accept_arrival(callsign, "01L")
        gnd.gate_arrival(callsign, "G14")
        assert gnd.aircraft_count == 0

        ctx = hm.get_context(callsign)
        assert ctx.current_controller == "ESSA_GND"

    def test_context_preserved_across_full_loop(self):
        """Verify flight context survives the entire loop intact."""
        env = self._build_airport()
        gnd = env["gnd"]
        twr = env["twr"]
        dep = env["dep"]
        ctr = env["ctr"]
        app = env["app"]
        gnd = env["gnd"]
        mgr = env["mgr"]
        hm = env["hm"]

        callsign = "SAS903"
        hm.register_flight(callsign, aircraft_type="A320", origin="ESSA", destination="ENGM",
                           sid_name="ARN1N", star_name="KOGOS2A")

        # Fast-cycle through all transitions
        gnd.request_pushback(callsign, "G12")
        gnd.pushback_complete(callsign, ["A", "B"])
        gnd.get_pending_commands()
        hm.transition_ground_to_tower(gnd, callsign, "ESSA_TWR", 118.5, "01L")
        hm.process_all_pending_handoffs()

        twr.accept_from_ground(callsign, "01L")
        twr.line_up(callsign, "01L")
        twr.clear_takeoff(callsign, "01L")
        twr.get_pending_commands()
        hm.transition_tower_to_departure(twr, callsign, "ESSA_DEP", 124.3, "01L", 5000)
        hm.process_all_pending_handoffs()

        dep.accept_from_tower(callsign, {"sid_name": "ARN1N", "initial_alt_ft": 5000})
        dep.assign_sid(callsign, "ARN1N", 5000)
        dep.get_pending_commands()
        hm.transition_departure_to_center(dep, callsign, "ESSA_CTR", 135.5, 10000)
        hm.process_all_pending_handoffs()

        ctr.accept_from_departure(callsign, 10000)
        ctr.assign_airway(callsign, "M852", "ARN", "KOGOS")
        ctr.assign_descent(callsign, 8000)
        ctr.get_pending_commands()
        hm.transition_center_to_approach(ctr, callsign, "ESSA_APP", 119.7, 8000)
        hm.process_all_pending_handoffs()

        app.accept_from_center(callsign, 8000)
        app.clear_ils(callsign, "01L", 110.3)
        app.get_pending_commands()
        hm.transition_approach_to_tower(app, callsign, "ESSA_TWR", 118.5, "01L")
        hm.process_all_pending_handoffs()

        twr.clear_landing(callsign, "01L")
        twr.get_pending_commands()
        hm.transition_tower_to_ground(twr, callsign, "ESSA_GND", 121.8, "01L", "G12")
        hm.process_all_pending_handoffs()

        ctx = hm.get_context(callsign)
        assert ctx.callsign == "SAS903"
        assert ctx.aircraft_type == "A320"
        assert ctx.origin == "ESSA"
        assert ctx.destination == "ENGM"
        assert ctx.sid_name == "ARN1N"
        assert ctx.star_name == "KOGOS2A"
        assert ctx.assigned_runway == "01L"
        assert ctx.gate == "G12"
        assert ctx.current_controller == "ESSA_GND"

        # 6 transitions + 6 handoff_accepted + pushback = 13+ history entries
        history = hm.get_full_history(callsign)
        assert len(history) >= 12
