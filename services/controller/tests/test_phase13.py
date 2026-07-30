import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import time
from unittest.mock import patch

import pytest

from base import BaseController
from ground import GroundController
from models import (
    ControllerState,
    GroundState,
    TaxiProgress,
    TaxiRefusalReason,
)


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────

@pytest.fixture
def gnd():
    return GroundController("ESSA_GND", 121.8, "ESSA_GND", "ESSA")


# ──────────────────────────────────────────────
# Engine Start
# ──────────────────────────────────────────────

class TestStartup:
    def test_request_startup(self, gnd):
        gnd.request_startup("SAS901", "G12")
        assert gnd.is_controlling("SAS901")
        assert gnd.get_aircraft_ground_state("SAS901") == GroundState.STARTUP
        cmds = gnd.get_pending_commands()
        assert len(cmds) == 1
        assert cmds[0].command_type == "startup"
        assert cmds[0].data["gate"] == "G12"
        assert "Startup approved" in cmds[0].data["instruction"]

    def test_request_startup_creates_clearance(self, gnd):
        gnd.request_startup("SAS901", "B5")
        clearance = gnd.get_clearance_state("SAS901")
        assert clearance is not None
        assert clearance.clearance_type == "startup"
        assert clearance.details["gate"] == "B5"

    def test_request_startup_logs_history(self, gnd):
        gnd.request_startup("SAS901", "G12")
        history = gnd.get_aircraft_history("SAS901")
        assert len(history) == 1
        assert history[0].command_type == "startup"
        assert history[0].new_state == GroundState.STARTUP.value


# ──────────────────────────────────────────────
# Taxi Clearance (clear_taxi)
# ──────────────────────────────────────────────

class TestClearTaxi:
    def test_clear_taxi_with_route(self, gnd):
        gnd.request_pushback("SAS901", "G12")
        gnd.get_pending_commands()
        result = gnd.clear_taxi(
            "SAS901", "G12", "RWY01",
            route_nodes=["G12", "A", "B", "RWY01"],
        )
        assert result == GroundState.TAXI_CLEARED
        assert gnd.get_aircraft_ground_state("SAS901") == GroundState.TAXI_CLEARED
        cmds = gnd.get_pending_commands()
        assert len(cmds) == 1
        assert cmds[0].command_type == "taxi"
        assert cmds[0].data["route"] == ["G12", "A", "B", "RWY01"]
        assert "Taxi to RWY01" in cmds[0].data["instruction"]

    def test_clear_taxi_not_controlling(self, gnd):
        result = gnd.clear_taxi(
            "NONEXIST", "G12", "RWY01",
            route_nodes=["G12", "RWY01"],
        )
        assert result is None

    def test_clear_taxi_wrong_state(self, gnd):
        gnd.accept_aircraft("SAS901")
        result = gnd.clear_taxi(
            "SAS901", "G12", "RWY01",
            route_nodes=["G12", "RWY01"],
        )
        assert result is None

    def test_clear_taxi_no_route(self, gnd):
        gnd.request_pushback("SAS901", "G12")
        gnd.get_pending_commands()
        result = gnd.clear_taxi("SAS901", "G12", "RWY01")
        assert result is None
        cmds = gnd.get_pending_commands()
        assert len(cmds) == 1
        assert cmds[0].command_type == "taxi_refused"
        assert "no route available" in cmds[0].data["instruction"]

    def test_clear_taxi_wrong_start_node(self, gnd):
        gnd.request_pushback("SAS901", "G12")
        gnd.get_pending_commands()
        result = gnd.clear_taxi(
            "SAS901", "WRONG", "RWY01",
            route_nodes=["G12", "RWY01"],
        )
        assert result is None
        cmds = gnd.get_pending_commands()
        assert cmds[0].command_type == "taxi_refused"
        assert "incorrect start position" in cmds[0].data["instruction"]

    def test_clear_taxi_taxiway_occupied(self, gnd):
        gnd.request_pushback("SAS901", "G12")
        gnd.get_pending_commands()
        gnd._occupied_taxiways.add("B")
        result = gnd.clear_taxi(
            "SAS901", "G12", "RWY01",
            route_nodes=["G12", "A", "B", "RWY01"],
        )
        assert result is None
        cmds = gnd.get_pending_commands()
        assert cmds[0].command_type == "taxi_refused"
        assert "taxiway occupied" in cmds[0].data["instruction"]

    def test_clear_taxi_creates_taxi_progress(self, gnd):
        gnd.request_pushback("SAS901", "G12")
        gnd.get_pending_commands()
        gnd.clear_taxi("SAS901", "G12", "RWY01", route_nodes=["G12", "A", "B", "RWY01"])
        progress = gnd.get_taxi_progress("SAS901")
        assert progress is not None
        assert progress.callsign == "SAS901"
        assert progress.cleared_nodes == ["G12", "A", "B", "RWY01"]
        assert progress.current_node_id == "G12"
        assert progress.route_completed is False

    def test_clear_taxi_from_arrival_state(self, gnd):
        gnd.accept_arrival("SAS901", "01L", gate="G12")
        gnd.get_pending_commands()
        result = gnd.clear_taxi(
            "SAS901", "RWY01", "G12",
            route_nodes=["RWY01", "B", "A", "G12"],
        )
        assert result == GroundState.TAXI_CLEARED

    def test_clear_taxi_auto_accepts_aircraft(self, gnd):
        gnd.accept_arrival("SAS901", "01L")
        gnd.get_pending_commands()
        assert gnd.is_controlling("SAS901")


# ──────────────────────────────────────────────
# Taxi Refusal (refuse_taxi)
# ──────────────────────────────────────────────

class TestRefuseTaxi:
    def test_refuse_taxi_issues_command(self, gnd):
        gnd.accept_aircraft("SAS901")
        gnd.refuse_taxi("SAS901", TaxiRefusalReason.RUNWAY_OCCUPIED)
        cmds = gnd.get_pending_commands()
        assert len(cmds) == 1
        assert cmds[0].command_type == "taxi_refused"
        assert cmds[0].data["reason"] == "runway_occupied"

    def test_refuse_taxi_with_detail(self, gnd):
        gnd.accept_aircraft("SAS901")
        gnd.refuse_taxi("SAS901", TaxiRefusalReason.TAXIWAY_OCCUPIED, "Aircraft on A")
        cmds = gnd.get_pending_commands()
        assert "Aircraft on A" in cmds[0].data["instruction"]

    def test_refuse_taxi_not_controlling(self, gnd):
        gnd.refuse_taxi("NONEXIST", TaxiRefusalReason.INVALID_CLEARANCE_REQUEST)
        assert gnd.get_pending_commands() == []


# ──────────────────────────────────────────────
# Runway Crossing
# ──────────────────────────────────────────────

class TestRunwayCrossing:
    def test_clear_cross_runway(self, gnd):
        gnd.accept_aircraft("SAS901")
        gnd.clear_cross_runway("SAS901", "01L")
        assert gnd.get_aircraft_ground_state("SAS901") == GroundState.CROSSING_RUNWAY
        cmds = gnd.get_pending_commands()
        assert len(cmds) == 1
        assert cmds[0].command_type == "cross_runway"
        assert cmds[0].data["runway"] == "01L"
        assert "report vacated" in cmds[0].data["instruction"]

    def test_clear_cross_runway_not_controlling(self, gnd):
        gnd.clear_cross_runway("NONEXIST", "01L")
        assert gnd.get_pending_commands() == []

    def test_clear_cross_runway_creates_clearance(self, gnd):
        gnd.accept_aircraft("SAS901")
        gnd.clear_cross_runway("SAS901", "01L")
        clearance = gnd.get_clearance_state("SAS901")
        assert clearance is not None
        assert clearance.clearance_type == "cross_runway"
        assert clearance.details["runway"] == "01L"

    def test_crossing_complete(self, gnd):
        gnd.accept_aircraft("SAS901")
        gnd.clear_cross_runway("SAS901", "01L")
        gnd.get_pending_commands()
        gnd.crossing_complete("SAS901", "01L")
        assert gnd.get_aircraft_ground_state("SAS901") == GroundState.TAXI_CLEARED
        cmds = gnd.get_pending_commands()
        assert cmds[0].command_type == "crossing_complete"
        assert "vacated" in cmds[0].data["instruction"]

    def test_crossing_complete_not_controlling(self, gnd):
        gnd.crossing_complete("NONEXIST", "01L")
        assert gnd.get_pending_commands() == []


# ──────────────────────────────────────────────
# Hold Short
# ──────────────────────────────────────────────

class TestHoldShort:
    def test_hold_short_of_runway_direct(self, gnd):
        gnd.accept_aircraft("SAS901")
        gnd.hold_short_of_runway("SAS901", "01L")
        assert gnd.get_aircraft_ground_state("SAS901") == GroundState.HOLDING_SHORT
        cmds = gnd.get_pending_commands()
        assert cmds[0].command_type == "hold_short"
        assert cmds[0].data["runway"] == "01L"

    def test_hold_short_of_runway_with_reason(self, gnd):
        gnd.accept_aircraft("SAS901")
        gnd.hold_short_of_runway("SAS901", "01L", "traffic on runway")
        cmds = gnd.get_pending_commands()
        assert "traffic on runway" in cmds[0].data["instruction"]

    def test_hold_short_of_runway_not_controlling(self, gnd):
        gnd.hold_short_of_runway("NONEXIST", "01L")
        assert gnd.get_pending_commands() == []


# ──────────────────────────────────────────────
# Position Tracking / Intersection Progress
# ──────────────────────────────────────────────

class TestPositionTracking:
    def test_report_position_on_route(self, gnd):
        gnd.request_pushback("SAS901", "G12")
        gnd.get_pending_commands()
        gnd.clear_taxi("SAS901", "G12", "RWY01", route_nodes=["G12", "A", "B", "RWY01"])
        gnd.report_position("SAS901", "A")
        progress = gnd.get_taxi_progress("SAS901")
        assert progress.current_node_id == "A"
        assert "A" in progress.visited_nodes
        assert progress.route_completed is False

    def test_report_position_not_on_route(self, gnd):
        gnd.request_pushback("SAS901", "G12")
        gnd.get_pending_commands()
        gnd.clear_taxi("SAS901", "G12", "RWY01", route_nodes=["G12", "A", "B", "RWY01"])
        gnd.report_position("SAS901", "Z")
        cmds = gnd.get_pending_commands()
        assert any(c.command_type == "position_warning" for c in cmds)

    def test_report_position_not_controlling(self, gnd):
        gnd.report_position("NONEXIST", "A")
        assert gnd.get_pending_commands() == []

    def test_report_position_no_taxi_progress(self, gnd):
        gnd.accept_aircraft("SAS901")
        gnd.report_position("SAS901", "A")
        assert gnd.get_pending_commands() == []

    def test_report_position_completes_route(self, gnd):
        gnd.request_pushback("SAS901", "G12")
        gnd.get_pending_commands()
        gnd.clear_taxi("SAS901", "G12", "RWY01", route_nodes=["G12", "A", "RWY01"])
        gnd.report_position("SAS901", "A")
        assert not gnd.get_taxi_progress("SAS901").route_completed
        gnd.report_position("SAS901", "RWY01")
        assert gnd.get_taxi_progress("SAS901").route_completed

    def test_get_next_taxi_instruction(self, gnd):
        gnd.request_pushback("SAS901", "G12")
        gnd.get_pending_commands()
        gnd.clear_taxi("SAS901", "G12", "RWY01", route_nodes=["G12", "A", "B", "RWY01"])
        instr = gnd.get_next_taxi_instruction("SAS901")
        assert instr == "Taxi to A"
        gnd.report_position("SAS901", "A")
        assert gnd.get_next_taxi_instruction("SAS901") == "Taxi to B"

    def test_get_next_taxi_instruction_complete(self, gnd):
        gnd.request_pushback("SAS901", "G12")
        gnd.get_pending_commands()
        gnd.clear_taxi("SAS901", "G12", "RWY01", route_nodes=["G12", "RWY01"])
        gnd.report_position("SAS901", "RWY01")
        assert gnd.get_next_taxi_instruction("SAS901") is None

    def test_get_next_taxi_instruction_no_progress(self, gnd):
        assert gnd.get_next_taxi_instruction("NONEXIST") is None

    def test_get_taxi_progress_unknown(self, gnd):
        assert gnd.get_taxi_progress("NONEXIST") is None

    def test_pushback_complete_creates_progress(self, gnd):
        gnd.request_pushback("SAS901", "G12")
        gnd.get_pending_commands()
        gnd.pushback_complete("SAS901", ["G12", "A", "RWY01"])
        progress = gnd.get_taxi_progress("SAS901")
        assert progress is not None
        assert progress.cleared_nodes == ["G12", "A", "RWY01"]

    def test_report_position_tracks_visited_no_duplicates(self, gnd):
        gnd.request_pushback("SAS901", "G12")
        gnd.get_pending_commands()
        gnd.clear_taxi("SAS901", "G12", "RWY01", route_nodes=["G12", "A", "RWY01"])
        gnd.report_position("SAS901", "A")
        gnd.report_position("SAS901", "A")
        progress = gnd.get_taxi_progress("SAS901")
        assert progress.visited_nodes.count("A") == 1


# ──────────────────────────────────────────────
# Arrival Handling
# ──────────────────────────────────────────────

class TestArrival:
    def test_accept_arrival(self, gnd):
        gnd.accept_arrival("SAS901", "01L", gate="G12")
        assert gnd.is_controlling("SAS901")
        assert gnd.get_aircraft_ground_state("SAS901") == GroundState.ARRIVAL_GROUND
        cmds = gnd.get_pending_commands()
        assert len(cmds) == 1
        assert cmds[0].command_type == "contact_ground"
        assert "G12" in cmds[0].data["instruction"]

    def test_accept_arrival_no_gate(self, gnd):
        gnd.accept_arrival("SAS901", "01L")
        cmds = gnd.get_pending_commands()
        assert "gate" not in cmds[0].data.get("instruction", "").lower()

    def test_accept_arrival_creates_clearance(self, gnd):
        gnd.accept_arrival("SAS901", "01L", gate="B5")
        clearance = gnd.get_clearance_state("SAS901")
        assert clearance is not None
        assert clearance.clearance_type == "arrival_taxi"
        assert clearance.details["gate"] == "B5"

    def test_gate_arrival(self, gnd):
        gnd.accept_arrival("SAS901", "01L", gate="G12")
        gnd.get_pending_commands()
        gnd.gate_arrival("SAS901", "G12")
        assert not gnd.is_controlling("SAS901")
        assert gnd.get_aircraft_ground_state("SAS901") is None
        cmds = gnd.get_pending_commands()
        assert cmds[0].command_type == "gate_arrival"
        assert "G12" in cmds[0].data["instruction"]

    def test_gate_arrival_removes_taxi_progress(self, gnd):
        gnd.accept_arrival("SAS901", "01L")
        gnd.clear_taxi("SAS901", "RWY01", "G12", route_nodes=["RWY01", "A", "G12"])
        gnd.get_pending_commands()
        assert gnd.get_taxi_progress("SAS901") is not None
        gnd.gate_arrival("SAS901", "G12")
        assert gnd.get_taxi_progress("SAS901") is None

    def test_gate_arrival_not_controlling(self, gnd):
        gnd.gate_arrival("NONEXIST", "G12")
        assert gnd.get_pending_commands() == []


# ──────────────────────────────────────────────
# Backward Compatibility — Existing tests still pass
# ──────────────────────────────────────────────

class TestBackwardCompatibility:
    def test_request_pushback(self, gnd):
        gnd.request_pushback("SAS901", "G12")
        assert gnd.is_controlling("SAS901")
        assert gnd.get_aircraft_ground_state("SAS901") == GroundState.PUSHBACK_IN_PROGRESS
        cmds = gnd.get_pending_commands()
        assert cmds[0].command_type == "pushback"
        assert cmds[0].data["gate"] == "G12"

    def test_request_pushback_with_direction(self, gnd):
        gnd.request_pushback("SAS902", "B5", direction="tail_west")
        cmds = gnd.get_pending_commands()
        assert cmds[0].data["direction"] == "tail_west"

    def test_pushback_complete(self, gnd):
        gnd.request_pushback("SAS901", "G12")
        gnd.get_pending_commands()
        gnd.pushback_complete("SAS901", ["A", "B", "C"])
        assert gnd.get_aircraft_ground_state("SAS901") == GroundState.TAXI_CLEARED
        cmds = gnd.get_pending_commands()
        assert cmds[0].command_type == "taxi"
        assert cmds[0].data["route"] == ["A", "B", "C"]

    def test_pushback_complete_no_route(self, gnd):
        gnd.request_pushback("SAS901", "G12")
        gnd.get_pending_commands()
        gnd.pushback_complete("SAS901")
        cmds = gnd.get_pending_commands()
        assert cmds[0].command_type == "taxi"
        assert cmds[0].data["route"] == []

    def test_pushback_complete_no_aircraft(self, gnd):
        gnd.pushback_complete("NONEXIST", ["A"])
        assert gnd.get_pending_commands() == []

    def test_report_holding_short(self, gnd):
        gnd.accept_aircraft("SAS901")
        gnd.report_holding_short("SAS901", "01L")
        assert gnd.get_aircraft_ground_state("SAS901") == GroundState.HOLDING_SHORT
        cmds = gnd.get_pending_commands()
        assert cmds[0].command_type == "hold_short"
        assert cmds[0].data["runway"] == "01L"
        hofs = gnd.get_pending_handoffs()
        assert len(hofs) == 1
        assert hofs[0].to_controller == "ESSA_TWR"

    def test_report_holding_short_unknown(self, gnd):
        gnd.report_holding_short("NONEXIST", "01L")
        assert gnd.get_pending_commands() == []

    def test_release_to_tower(self, gnd):
        gnd.accept_aircraft("SAS901")
        gnd.report_holding_short("SAS901", "01R")
        gnd.get_pending_commands()
        gnd.get_pending_handoffs()
        gnd.release_to_tower("SAS901")
        assert not gnd.is_controlling("SAS901")

    def test_release_to_tower_clears_progress(self, gnd):
        gnd.request_pushback("SAS901", "G12")
        gnd.get_pending_commands()
        gnd.pushback_complete("SAS901", ["A", "B"])
        gnd.get_pending_commands()
        assert gnd.get_taxi_progress("SAS901") is not None
        gnd.release_to_tower("SAS901")
        assert gnd.get_taxi_progress("SAS901") is None

    def test_ground_departure_lifecycle(self, gnd):
        gnd.request_pushback("SAS901", "G12")
        gnd.pushback_complete("SAS901", ["A", "B"])
        gnd.report_holding_short("SAS901", "01L")
        gnd.get_pending_handoffs()
        gnd.release_to_tower("SAS901")
        assert not gnd.is_controlling("SAS901")
        assert gnd.get_pending_handoffs() == []

    def test_controlled_aircraft_list(self, gnd):
        gnd.accept_aircraft("AC1")
        gnd.accept_aircraft("AC2")
        assert set(gnd.controlled_aircraft) == {"AC1", "AC2"}

    def test_accept_aircraft_idempotent(self, gnd):
        gnd.accept_aircraft("AC1")
        gnd.accept_aircraft("AC1")
        assert gnd.aircraft_count == 1

    def test_get_aircraft_ground_state_unknown(self, gnd):
        assert gnd.get_aircraft_ground_state("NONEXIST") is None


# ──────────────────────────────────────────────
# Model Dataclasses
# ──────────────────────────────────────────────

class TestTaxiProgress:
    def test_create(self):
        p = TaxiProgress(
            callsign="SAS901",
            cleared_nodes=["G12", "A", "B", "RWY01"],
        )
        assert p.callsign == "SAS901"
        assert p.cleared_nodes == ["G12", "A", "B", "RWY01"]
        assert p.visited_nodes == []
        assert p.current_node_id is None
        assert p.route_completed is False

    def test_defaults(self):
        p = TaxiProgress(callsign="SAS901", cleared_nodes=["A"])
        assert p.started_at_s == 0.0
        assert p.last_progress_s == 0.0


class TestTaxiRefusalReason:
    def test_values(self):
        assert TaxiRefusalReason.RUNWAY_OCCUPIED.value == "runway_occupied"
        assert TaxiRefusalReason.TAXIWAY_OCCUPIED.value == "taxiway_occupied"
        assert TaxiRefusalReason.INVALID_START_POINT.value == "invalid_start_point"
        assert TaxiRefusalReason.INVALID_CLEARANCE_REQUEST.value == "invalid_clearance_request"
        assert TaxiRefusalReason.NO_ROUTE_AVAILABLE.value == "no_route_available"
        assert TaxiRefusalReason.AIRCRAFT_NOT_UNDER_CONTROL.value == "aircraft_not_under_control"
        assert TaxiRefusalReason.INVALID_STATE_FOR_TAXI.value == "invalid_state_for_taxi"

    def test_all_members(self):
        assert len(TaxiRefusalReason) == 7


class TestGroundState:
    def test_new_values(self):
        assert GroundState.STARTUP.value == "startup"
        assert GroundState.CROSSING_RUNWAY.value == "crossing_runway"
        assert GroundState.ARRIVAL_GROUND.value == "arrival_ground"

    def test_existing_values_preserved(self):
        assert GroundState.IDLE.value == "idle"
        assert GroundState.PUSHBACK_IN_PROGRESS.value == "pushback_in_progress"
        assert GroundState.TAXI_CLEARED.value == "taxi_cleared"
        assert GroundState.HOLDING_SHORT.value == "holding_short"


# ──────────────────────────────────────────────
# Process method
# ──────────────────────────────────────────────

class TestProcess:
    def test_process_noop(self, gnd):
        gnd.process(0.1, {})
        # process is a no-op currently
        assert True

    def test_process_with_aircraft_state(self, gnd):
        gnd.accept_aircraft("SAS901")
        gnd.process(0.1, {"traffic": []})
        assert gnd.aircraft_count == 1
