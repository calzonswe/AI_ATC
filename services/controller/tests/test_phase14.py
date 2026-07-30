import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import time
from unittest.mock import patch

import pytest

from base import BaseController
from models import (
    ControllerState,
    TowerState,
    TrafficAdvisory,
    TrafficAdvisoryType,
)
from tower import TowerController


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────

@pytest.fixture
def twr():
    return TowerController("ESSA_TWR", 118.5, "ESSA_TWR", "ESSA", ["01L", "19R"])


# ──────────────────────────────────────────────
# Separation Logic
# ──────────────────────────────────────────────

class TestSeparation:
    def test_can_clear_takeoff_empty_runway(self, twr):
        assert twr.can_clear_takeoff("01L") is True

    def test_can_clear_takeoff_occupied(self, twr):
        twr.accept_aircraft("SAS901")
        twr.clear_takeoff("SAS901", "01L")
        twr.get_pending_commands()
        assert twr.can_clear_takeoff("01L") is False

    def test_can_clear_takeoff_unknown_runway(self, twr):
        assert twr.can_clear_takeoff("NONEXIST") is False

    def test_can_clear_takeoff_departure_separation(self, twr):
        with patch("tower.time.time", return_value=1000.0):
            twr.accept_aircraft("SAS901")
            twr.clear_takeoff("SAS901", "01L")
            twr.departure_airborne("SAS901", "01L", 1000.0)
            twr.get_pending_commands()
            # departure just happened (time=1000, last_departure=1000), separation not met
            assert twr.can_clear_takeoff("01L") is False

    def test_can_clear_takeoff_after_separation_met(self, twr):
        twr.accept_aircraft("SAS901")
        twr.clear_takeoff("SAS901", "01L")
        twr.departure_airborne("SAS901", "01L", 0.0)
        twr.get_pending_commands()
        with patch("tower.time.time", return_value=1000.0):
            twr.runways["01L"].last_departure_time_s = 0.0
            assert twr.can_clear_takeoff("01L") is True

    def test_can_clear_landing_empty_runway(self, twr):
        assert twr.can_clear_landing("01L") is True

    def test_can_clear_landing_occupied(self, twr):
        twr.runways["01L"].is_occupied = True
        assert twr.can_clear_landing("01L") is False

    def test_can_clear_landing_departure_in_progress(self, twr):
        twr.runways["01L"].current_departure_callsign = "SAS901"
        assert twr.can_clear_landing("01L") is False

    def test_can_clear_landing_unknown_runway(self, twr):
        assert twr.can_clear_landing("NONEXIST") is False

    def test_clear_takeoff_auto_accepts(self, twr):
        twr.clear_takeoff("SAS901", "01L", "270/12kt")
        assert twr.is_controlling("SAS901")

    def test_clear_takeoff_uses_stored_wind(self, twr):
        twr.update_wind("270/12kt")
        twr.clear_takeoff("SAS901", "01L")
        cmds = twr.get_pending_commands()
        assert "270/12kt" in cmds[0].data["instruction"]

    def test_clear_landing_refused_when_occupied(self, twr):
        twr.runways["01L"].is_occupied = True
        twr.clear_landing("SAS901", "01L")
        assert twr.get_aircraft_tower_state("SAS901") == TowerState.GO_AROUND
        cmds = twr.get_pending_commands()
        assert cmds[0].command_type == "go_around"
        assert "not available" in cmds[0].data["instruction"]

    def test_clear_landing_refused_when_departure(self, twr):
        twr.accept_aircraft("DEP901")
        twr.clear_takeoff("DEP901", "01L")
        twr.get_pending_commands()
        twr.clear_landing("ARR902", "01L")
        assert twr.get_aircraft_tower_state("ARR902") == TowerState.GO_AROUND


# ──────────────────────────────────────────────
# Automated Go-Around in process()
# ──────────────────────────────────────────────

class TestProcessGoAround:
    def test_process_no_conflict_does_nothing(self, twr):
        twr.clear_landing("SAS901", "01L")
        twr.get_pending_commands()
        twr.process(1.0, {})
        assert twr.get_aircraft_tower_state("SAS901") == TowerState.LANDING_CLEARED
        assert twr.get_pending_commands() == []

    def test_process_detects_runway_occupied_by_departure(self, twr):
        twr.clear_landing("SAS901", "01L")
        twr.get_pending_commands()
        twr.runways["01L"].current_departure_callsign = "DEP456"
        twr.process(1.0, {})
        assert twr.get_aircraft_tower_state("SAS901") == TowerState.GO_AROUND
        cmds = twr.get_pending_commands()
        assert any(c.command_type == "go_around" for c in cmds)
        assert any("DEP456" in c.data.get("instruction", "") for c in cmds)

    def test_process_clears_stale_approaching_aircraft(self, twr):
        twr.clear_landing("SAS901", "01L")
        twr.get_pending_commands()
        twr._aircraft_states["SAS901"] = TowerState.LINE_UP
        twr.process(1.0, {})
        assert "SAS901" not in twr._approaching_aircraft

    def test_process_no_go_around_for_self_occupancy(self, twr):
        twr.clear_landing("SAS901", "01L")
        twr.get_pending_commands()
        twr.process(1.0, {})
        assert twr.get_aircraft_tower_state("SAS901") == TowerState.LANDING_CLEARED

    def test_process_multiple_approaches_one_conflict(self, twr):
        twr.clear_landing("SAS901", "01L")
        twr.get_pending_commands()
        twr.clear_landing("SAS902", "19R")
        twr.get_pending_commands()
        twr.runways["01L"].current_arrival_callsign = "OTHER"
        twr.process(1.0, {})
        assert twr.get_aircraft_tower_state("SAS901") == TowerState.GO_AROUND
        assert twr.get_aircraft_tower_state("SAS902") == TowerState.LANDING_CLEARED


# ──────────────────────────────────────────────
# Wind Updates
# ──────────────────────────────────────────────

class TestWind:
    def test_update_wind_stores_value(self, twr):
        twr.update_wind("270/12kt")
        assert twr._wind_info == "270/12kt"

    def test_update_wind_empty(self, twr):
        twr.update_wind("")
        assert twr._wind_info == ""

    def test_clear_takeoff_with_stored_wind(self, twr):
        twr.update_wind("270/12kt")
        twr.clear_takeoff("SAS901", "01L")
        cmds = twr.get_pending_commands()
        assert "270/12kt" in cmds[0].data["instruction"]

    def test_clear_takeoff_explicit_wind_overrides_stored(self, twr):
        twr.update_wind("270/12kt")
        twr.clear_takeoff("SAS901", "01L", wind_info="310/15G25")
        cmds = twr.get_pending_commands()
        assert "310/15G25" in cmds[0].data["instruction"]
        assert "270/12kt" not in cmds[0].data["instruction"]


# ──────────────────────────────────────────────
# Traffic Advisories
# ──────────────────────────────────────────────

class TestTrafficAdvisory:
    def test_issue_traffic_advisory(self, twr):
        advisory = twr.issue_traffic_advisory("SAS901", "SAS456", "10 o'clock, 5 miles")
        assert isinstance(advisory, TrafficAdvisory)
        assert advisory.advisory_type == TrafficAdvisoryType.TRAFFIC_IN_VICINITY
        assert advisory.target_callsign == "SAS901"
        assert advisory.traffic_callsign == "SAS456"
        assert advisory.issued_by == "ESSA_TWR"
        cmds = twr.get_pending_commands()
        assert cmds[0].command_type == "traffic_advisory"
        assert "SAS456" in cmds[0].data["instruction"]

    def test_issue_traffic_advisory_no_position(self, twr):
        advisory = twr.issue_traffic_advisory("SAS901", "SAS456")
        cmds = twr.get_pending_commands()
        assert cmds[0].command_type == "traffic_advisory"

    def test_circuit_instruction_left(self, twr):
        twr.issue_circuit_instruction("SAS901", "01L", "left")
        cmds = twr.get_pending_commands()
        assert cmds[0].command_type == "circuit"
        assert "left-hand" in cmds[0].data["instruction"]
        assert twr.is_controlling("SAS901")

    def test_circuit_instruction_right(self, twr):
        twr.issue_circuit_instruction("SAS902", "19R", "right")
        cmds = twr.get_pending_commands()
        assert "right-hand" in cmds[0].data["instruction"]

    def test_report_traffic(self, twr):
        twr.report_traffic("SAS901", "SAS456", "2", "5 miles", "3000ft")
        cmds = twr.get_pending_commands()
        assert cmds[0].command_type == "traffic_info"
        assert "2 o'clock" in cmds[0].data["instruction"]
        assert "3000ft" in cmds[0].data["instruction"]

    def test_report_traffic_no_altitude(self, twr):
        twr.report_traffic("SAS901", "SAS456", "10", "3 miles")
        cmds = twr.get_pending_commands()
        assert "10 o'clock" in cmds[0].data["instruction"]
        assert "3 miles" in cmds[0].data["instruction"]


# ──────────────────────────────────────────────
# TrafficAdvisory Dataclass
# ──────────────────────────────────────────────

class TestTrafficAdvisoryDataclass:
    def test_create(self):
        advisory = TrafficAdvisory(
            advisory_type=TrafficAdvisoryType.CIRCUIT_FINAL,
            target_callsign="SAS901",
            traffic_callsign="SAS456",
            position="5 mile final",
            instruction="Number 2, follow traffic",
            issued_by="ESSA_TWR",
        )
        assert advisory.advisory_type == TrafficAdvisoryType.CIRCUIT_FINAL
        assert advisory.target_callsign == "SAS901"
        assert advisory.instruction == "Number 2, follow traffic"

    def test_defaults(self):
        advisory = TrafficAdvisory(
            advisory_type=TrafficAdvisoryType.TRAFFIC_IN_VICINITY,
            target_callsign="SAS901",
            traffic_callsign="SAS456",
        )
        assert advisory.position == ""
        assert advisory.instruction == ""
        assert advisory.issued_by == ""


class TestTrafficAdvisoryType:
    def test_values(self):
        assert TrafficAdvisoryType.TRAFFIC_IN_VICINITY.value == "traffic_in_vicinity"
        assert TrafficAdvisoryType.CIRCUIT_JOIN.value == "circuit_join"
        assert TrafficAdvisoryType.CIRCUIT_DOWNWIND.value == "circuit_downwind"
        assert TrafficAdvisoryType.CIRCUIT_BASE.value == "circuit_base"
        assert TrafficAdvisoryType.CIRCUIT_FINAL.value == "circuit_final"
        assert TrafficAdvisoryType.PATTERN_ENTER.value == "pattern_enter"
        assert TrafficAdvisoryType.PATTERN_EXIT.value == "pattern_exit"
        assert TrafficAdvisoryType.LANDING_SEQUENCE.value == "landing_sequence"

    def test_all_members(self):
        assert len(TrafficAdvisoryType) == 8


# ──────────────────────────────────────────────
# Go Around — Enhanced
# ──────────────────────────────────────────────

class TestGoAround:
    def test_go_around_auto_accepts(self, twr):
        twr.go_around("SAS901", "01L")
        assert twr.is_controlling("SAS901")
        assert twr.get_aircraft_tower_state("SAS901") == TowerState.GO_AROUND

    def test_go_around_clears_approaching(self, twr):
        twr.clear_landing("SAS901", "01L")
        twr.get_pending_commands()
        assert "SAS901" in twr._approaching_aircraft
        twr.go_around("SAS901", "01L", "traffic")
        assert "SAS901" not in twr._approaching_aircraft

    def test_go_around_revokes_clearance(self, twr):
        twr.clear_landing("SAS901", "01L")
        twr.get_pending_commands()
        twr.go_around("SAS901", "01L")
        clearance = twr.get_clearance_state("SAS901")
        assert clearance is None or not clearance.is_active

    def test_go_around_only_clears_own_occupancy(self, twr):
        twr.clear_landing("SAS901", "01L")
        twr.runways["01L"].current_arrival_callsign = "SAS901"
        twr.runways["01L"].is_occupied = True
        twr.go_around("SAS901", "01L")
        assert twr.runways["01L"].is_occupied is False
        assert twr.runways["01L"].current_arrival_callsign is None

    def test_go_around_does_not_clear_other_occupancy(self, twr):
        twr.runways["01L"].is_occupied = True
        twr.runways["01L"].current_departure_callsign = "DEP901"
        twr.go_around("ARR902", "01L", "traffic")
        assert twr.runways["01L"].is_occupied is True
        assert twr.runways["01L"].current_departure_callsign == "DEP901"

    def test_go_around_issues_command(self, twr):
        twr.go_around("SAS901", "01L", "traffic on runway")
        cmds = twr.get_pending_commands()
        assert cmds[0].command_type == "go_around"
        assert "traffic on runway" in cmds[0].data.get("instruction", "")


# ──────────────────────────────────────────────
# Arrival — Enhanced
# ──────────────────────────────────────────────

class TestArrival:
    def test_arrival_landed_removes_approaching(self, twr):
        twr.clear_landing("SAS901", "01L")
        twr.get_pending_commands()
        assert "SAS901" in twr._approaching_aircraft
        twr.arrival_landed("SAS901", "01L", 100.0)
        assert "SAS901" not in twr._approaching_aircraft

    def test_arrival_landed_clears_runway_occupancy(self, twr):
        twr.clear_landing("SAS901", "01L")
        twr.get_pending_commands()
        assert twr.runways["01L"].is_occupied is True
        twr.arrival_landed("SAS901", "01L", 100.0)
        assert twr.runways["01L"].is_occupied is False

    def test_arrival_landed_handoff_to_ground(self, twr):
        twr.clear_landing("SAS901", "01L")
        twr.get_pending_commands()
        twr.arrival_landed("SAS901", "01L", 100.0)
        hofs = twr.get_pending_handoffs()
        assert len(hofs) == 1
        assert hofs[0].to_controller == "ESSA_GND"


# ──────────────────────────────────────────────
# Release to Departure
# ──────────────────────────────────────────────

class TestReleaseToDeparture:
    def test_release_to_departure(self, twr):
        twr.accept_from_ground("SAS901", "01L")
        twr.release_to_departure("SAS901")
        assert not twr.is_controlling("SAS901")
        assert twr.get_aircraft_tower_state("SAS901") is None

    def test_release_to_departure_clears_runway_tracking(self, twr):
        twr.accept_aircraft("SAS901")
        twr.clear_takeoff("SAS901", "01L")
        twr.release_to_departure("SAS901")
        assert twr._aircraft_runways.get("SAS901") is None

    def test_release_to_departure_nonexistent(self, twr):
        twr.release_to_departure("NONEXIST")
        assert twr.get_pending_commands() == []


# ──────────────────────────────────────────────
# Integration — Full Runway Lifecycle with Separation
# ──────────────────────────────────────────────

class TestIntegration:
    def test_departure_then_arrival_with_separation(self, twr):
        twr.clear_takeoff("DEP901", "01L", "270/10kt")
        twr.departure_airborne("DEP901", "01L", 100.0)
        twr.get_pending_commands()
        twr.get_pending_handoffs()
        assert twr.runways["01L"].is_occupied is False
        twr.clear_landing("ARR902", "01L")
        assert twr.get_aircraft_tower_state("ARR902") == TowerState.LANDING_CLEARED

    def test_landing_refused_takeoff_occupies_runway(self, twr):
        twr.clear_takeoff("DEP901", "01L")
        twr.get_pending_commands()
        twr.clear_landing("ARR902", "01L")
        assert twr.get_aircraft_tower_state("ARR902") == TowerState.GO_AROUND

    def test_clear_landing_after_arrival_landed(self, twr):
        twr.clear_landing("ARR901", "01L")
        twr.get_pending_commands()
        twr.arrival_landed("ARR901", "01L", 200.0)
        twr.get_pending_commands()
        twr.clear_landing("ARR902", "01L")
        assert twr.get_aircraft_tower_state("ARR902") == TowerState.LANDING_CLEARED


# ──────────────────────────────────────────────
# Backward Compatibility — Existing tests still work
# ──────────────────────────────────────────────

class TestBackwardCompatibility:
    def test_initial_state(self, twr):
        assert twr.callsign == "ESSA_TWR"
        assert twr.frequency == 118.5
        assert "01L" in twr.runways
        assert "19R" in twr.runways

    def test_accept_from_ground(self, twr):
        twr.accept_from_ground("SAS901", "01L")
        assert twr.is_controlling("SAS901")
        assert twr.get_aircraft_tower_state("SAS901") == TowerState.IDLE
        cmds = twr.get_pending_commands()
        assert cmds[0].command_type == "contact_tower"

    def test_line_up(self, twr):
        twr.accept_from_ground("SAS901", "01L")
        twr.get_pending_commands()
        twr.line_up("SAS901", "01L")
        assert twr.get_aircraft_tower_state("SAS901") == TowerState.LINE_UP
        cmds = twr.get_pending_commands()
        assert cmds[0].command_type == "line_up"

    def test_line_up_auto_accept(self, twr):
        twr.line_up("SAS901", "01L")
        assert twr.is_controlling("SAS901")

    def test_clear_takeoff_with_wind(self, twr):
        twr.accept_aircraft("SAS901")
        twr.clear_takeoff("SAS901", "01L", "260/10kt")
        assert twr.get_aircraft_tower_state("SAS901") == TowerState.TAKEOFF_CLEARED
        cmds = twr.get_pending_commands()
        assert cmds[0].command_type == "takeoff"
        assert "260/10kt" in cmds[0].data.get("instruction", "")
        assert twr.runways["01L"].is_occupied
        assert twr.runways["01L"].current_departure_callsign == "SAS901"

    def test_clear_takeoff_no_wind(self, twr):
        twr.accept_aircraft("SAS901")
        twr.clear_takeoff("SAS901", "01L")
        cmds = twr.get_pending_commands()
        assert cmds[0].command_type == "takeoff"
        assert "wind" not in cmds[0].data.get("instruction", "")

    def test_departure_airborne(self, twr):
        twr.accept_aircraft("SAS901")
        twr.clear_takeoff("SAS901", "01L")
        twr.get_pending_commands()
        twr.departure_airborne("SAS901", "01L", 100.0)
        assert not twr.is_controlling("SAS901")
        assert not twr.runways["01L"].is_occupied
        assert twr.runways["01L"].last_departure_time_s == 100.0
        hofs = twr.get_pending_handoffs()
        assert len(hofs) == 1
        assert hofs[0].to_controller == "ESSA_DEP"

    def test_clear_landing(self, twr):
        twr.clear_landing("SAS901", "01L")
        assert twr.get_aircraft_tower_state("SAS901") == TowerState.LANDING_CLEARED
        cmds = twr.get_pending_commands()
        assert cmds[0].command_type == "landing"
        assert twr.runways["01L"].is_occupied

    def test_go_around(self, twr):
        twr.go_around("SAS901", "01L", "traffic on runway")
        assert twr.get_aircraft_tower_state("SAS901") == TowerState.GO_AROUND
        cmds = twr.get_pending_commands()
        assert cmds[0].command_type == "go_around"
        assert "traffic on runway" in cmds[0].data.get("instruction", "")

    def test_arrival_landed(self, twr):
        twr.clear_landing("SAS901", "01L")
        twr.get_pending_commands()
        twr.arrival_landed("SAS901", "01L", 200.0)
        assert not twr.is_controlling("SAS901")
        assert not twr.runways["01L"].is_occupied
        assert twr.runways["01L"].last_arrival_time_s == 200.0
        hofs = twr.get_pending_handoffs()
        assert hofs[0].to_controller == "ESSA_GND"

    def test_departure_lifecycle(self, twr):
        twr.accept_from_ground("SAS901", "01L")
        twr.line_up("SAS901", "01L")
        twr.clear_takeoff("SAS901", "01L")
        twr.departure_airborne("SAS901", "01L", 300.0)
        assert twr.aircraft_count == 0

    def test_arrival_lifecycle(self, twr):
        twr.clear_landing("SAS901", "01L")
        twr.arrival_landed("SAS901", "01L", 400.0)
        assert twr.aircraft_count == 0

    def test_go_around_cycle(self, twr):
        twr.clear_landing("SAS901", "01L")
        twr.go_around("SAS901", "01L")
        assert twr.get_aircraft_tower_state("SAS901") == TowerState.GO_AROUND

    def test_process_noop(self, twr):
        twr.process(0.1, {})
        assert True
