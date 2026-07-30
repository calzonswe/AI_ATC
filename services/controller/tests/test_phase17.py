import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import time
from unittest.mock import patch

import pytest

from center import CenterController
from models import (
    AirwayAssignment,
    AltitudeChangeRequest,
    CenterState,
)


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────

@pytest.fixture
def ctr():
    return CenterController(
        "ESSA_CTR", 135.5, "ESSA_CTR", "Stockholm Center",
    )


@pytest.fixture
def ctr_tod_20():
    return CenterController(
        "ESSA_CTR", 135.5, "ESSA_CTR", "Stockholm Center",
        tod_distance_nm=20.0,
    )


# ──────────────────────────────────────────────
# Airway Tracking
# ──────────────────────────────────────────────

class TestAirwayAssignment:
    def test_assign_airway_creates_assignment(self, ctr):
        ctr.accept_aircraft("SAS901")
        ctr.assign_airway("SAS901", "M852", "ARN", "KOGOS",
                          fixes=["ARN", "XILAN", "KOGOS"], flight_level=350)
        airway = ctr.get_airway_assignment("SAS901")
        assert airway is not None
        assert airway.airway_name == "M852"
        assert airway.entry_fix == "ARN"
        assert airway.exit_fix == "KOGOS"
        assert airway.fixes == ["ARN", "XILAN", "KOGOS"]
        assert airway.assigned_flight_level == 350

    def test_assign_airway_sets_cruise_state(self, ctr):
        ctr.accept_aircraft("SAS901")
        ctr.assign_airway("SAS901", "M852", "ARN", "KOGOS")
        assert ctr.get_aircraft_center_state("SAS901") == CenterState.CRUISE

    def test_assign_airway_issues_command(self, ctr):
        ctr.accept_aircraft("SAS901")
        ctr.assign_airway("SAS901", "M852", "ARN", "KOGOS", flight_level=350)
        cmds = ctr.get_pending_commands()
        assert cmds[0].command_type == "assign_airway"
        assert "M852" in cmds[0].data["instruction"]
        assert "ARN" in cmds[0].data["instruction"]
        assert "KOGOS" in cmds[0].data["instruction"]
        assert "FL350" in cmds[0].data["instruction"]

    def test_assign_airway_auto_accepts(self, ctr):
        ctr.assign_airway("SAS901", "M852", "ARN", "KOGOS")
        assert ctr.is_controlling("SAS901")

    def test_assign_airway_creates_clearance(self, ctr):
        ctr.accept_aircraft("SAS901")
        ctr.assign_airway("SAS901", "M852", "ARN", "KOGOS", flight_level=350)
        clearance = ctr.get_clearance_state("SAS901")
        assert clearance is not None
        assert clearance.clearance_type == "airway"
        assert clearance.details["airway"] == "M852"
        assert clearance.details["flight_level"] == 350

    def test_assign_airway_default_fixes(self, ctr):
        ctr.accept_aircraft("SAS901")
        ctr.assign_airway("SAS901", "M852", "ARN", "KOGOS")
        airway = ctr.get_airway_assignment("SAS901")
        assert airway.fixes == ["ARN", "KOGOS"]

    def test_assign_airway_logs_history(self, ctr):
        ctr.accept_aircraft("SAS901")
        ctr.assign_airway("SAS901", "M852", "ARN", "KOGOS")
        history = ctr.get_aircraft_history("SAS901")
        assert len(history) == 1
        assert history[0].command_type == "assign_airway"

    def test_get_airway_assignment_unknown(self, ctr):
        assert ctr.get_airway_assignment("NONEXIST") is None

    def test_advance_along_airway_updates_index(self, ctr):
        ctr.accept_aircraft("SAS901")
        ctr.assign_airway("SAS901", "M852", "ARN", "KOGOS",
                          fixes=["ARN", "XILAN", "KOGOS"])
        ctr.get_pending_commands()
        ctr.advance_along_airway("SAS901", "XILAN")
        airway = ctr.get_airway_assignment("SAS901")
        assert airway.current_fix_index == 1

    def test_advance_along_airway_issues_command(self, ctr):
        ctr.accept_aircraft("SAS901")
        ctr.assign_airway("SAS901", "M852", "ARN", "KOGOS",
                          fixes=["ARN", "XILAN", "KOGOS"])
        ctr.get_pending_commands()
        ctr.advance_along_airway("SAS901", "XILAN")
        cmds = ctr.get_pending_commands()
        assert cmds[0].command_type == "position_report"
        assert "XILAN" in cmds[0].data["instruction"]

    def test_advance_along_airway_no_assignment(self, ctr):
        ctr.advance_along_airway("NONEXIST", "XILAN")
        assert ctr.get_pending_commands() == []

    def test_get_next_airway_fix_returns_next(self, ctr):
        ctr.accept_aircraft("SAS901")
        ctr.assign_airway("SAS901", "M852", "ARN", "KOGOS",
                          fixes=["ARN", "XILAN", "KOGOS"])
        assert ctr.get_next_airway_fix("SAS901") == "XILAN"

    def test_get_next_airway_fix_after_advance(self, ctr):
        ctr.accept_aircraft("SAS901")
        ctr.assign_airway("SAS901", "M852", "ARN", "KOGOS",
                          fixes=["ARN", "XILAN", "KOGOS"])
        ctr.advance_along_airway("SAS901", "XILAN")
        assert ctr.get_next_airway_fix("SAS901") == "KOGOS"

    def test_get_next_airway_fix_at_end(self, ctr):
        ctr.accept_aircraft("SAS901")
        ctr.assign_airway("SAS901", "M852", "ARN", "KOGOS",
                          fixes=["ARN", "KOGOS"])
        ctr.advance_along_airway("SAS901", "KOGOS")
        assert ctr.get_next_airway_fix("SAS901") is None

    def test_get_next_airway_fix_unknown(self, ctr):
        assert ctr.get_next_airway_fix("NONEXIST") is None

    def test_update_sector_distance(self, ctr):
        ctr.accept_aircraft("SAS901")
        ctr.assign_airway("SAS901", "M852", "ARN", "KOGOS", distance_to_exit_nm=100.0)
        ctr.update_sector_distance("SAS901", 45.0)
        airway = ctr.get_airway_assignment("SAS901")
        assert airway.distance_to_exit_nm == 45.0

    def test_update_sector_distance_no_assignment(self, ctr):
        ctr.update_sector_distance("NONEXIST", 45.0)  # should not raise


# ──────────────────────────────────────────────
# Altitude Change Requests
# ──────────────────────────────────────────────

class TestAltitudeChangeRequest:
    def test_request_altitude_change_creates_request(self, ctr):
        ctr.accept_aircraft("SAS901")
        ctr.request_altitude_change("SAS901", 37000, 35000, "winds")
        req = ctr.get_pending_altitude_request("SAS901")
        assert req is not None
        assert req.requested_alt_ft == 37000
        assert req.current_alt_ft == 35000
        assert req.reason == "winds"

    def test_request_altitude_change_issues_command(self, ctr):
        ctr.accept_aircraft("SAS901")
        ctr.request_altitude_change("SAS901", 37000, 35000)
        cmds = ctr.get_pending_commands()
        assert cmds[0].command_type == "altitude_request"
        assert "37000" in cmds[0].data["instruction"]
        assert "35000" in cmds[0].data["instruction"]

    def test_request_altitude_change_not_controlling(self, ctr):
        ctr.request_altitude_change("NONEXIST", 37000, 35000)
        assert ctr.get_pending_altitude_request("NONEXIST") is None
        assert ctr.get_pending_commands() == []

    def test_approve_altitude_change_climb(self, ctr):
        ctr.accept_aircraft("SAS901")
        ctr.request_altitude_change("SAS901", 37000, 35000)
        ctr.get_pending_commands()
        ctr.approve_altitude_change("SAS901")
        req = ctr.get_pending_altitude_request("SAS901")
        assert req.approved is True
        assert req.responded_at_s is not None
        assert ctr.get_aircraft_center_state("SAS901") == CenterState.CLIMB_CLEARED

    def test_approve_altitude_change_issues_command(self, ctr):
        ctr.accept_aircraft("SAS901")
        ctr.request_altitude_change("SAS901", 37000, 35000)
        ctr.get_pending_commands()
        ctr.approve_altitude_change("SAS901")
        cmds = ctr.get_pending_commands()
        assert cmds[0].command_type == "approve_altitude"
        assert "37000" in cmds[0].data["instruction"]

    def test_approve_altitude_change_creates_clearance(self, ctr):
        ctr.accept_aircraft("SAS901")
        ctr.request_altitude_change("SAS901", 37000, 35000)
        ctr.get_pending_commands()
        ctr.approve_altitude_change("SAS901")
        clearance = ctr.get_clearance_state("SAS901")
        assert clearance is not None
        assert clearance.clearance_type == "altitude_change"
        assert clearance.details["target_alt"] == 37000

    def test_approve_no_request(self, ctr):
        ctr.approve_altitude_change("NONEXIST")  # should not raise
        assert ctr.get_pending_commands() == []

    def test_approve_altitude_change_descend(self, ctr):
        ctr.accept_aircraft("SAS901")
        ctr.assign_airway("SAS901", "M852", "ARN", "KOGOS")
        ctr.get_pending_commands()
        ctr.request_altitude_change("SAS901", 30000, 35000)
        ctr.get_pending_commands()
        ctr.approve_altitude_change("SAS901")
        assert ctr.get_aircraft_center_state("SAS901") == CenterState.CRUISE

    def test_deny_altitude_change(self, ctr):
        ctr.accept_aircraft("SAS901")
        ctr.request_altitude_change("SAS901", 37000, 35000)
        ctr.get_pending_commands()
        ctr.deny_altitude_change("SAS901", "traffic")
        req = ctr.get_pending_altitude_request("SAS901")
        assert req.approved is False
        assert req.responded_at_s is not None

    def test_deny_altitude_change_issues_command(self, ctr):
        ctr.accept_aircraft("SAS901")
        ctr.request_altitude_change("SAS901", 37000, 35000)
        ctr.get_pending_commands()
        ctr.deny_altitude_change("SAS901", "traffic")
        cmds = ctr.get_pending_commands()
        assert cmds[0].command_type == "deny_altitude"
        assert "Unable altitude" in cmds[0].data["instruction"]
        assert "traffic" in cmds[0].data["instruction"]

    def test_deny_altitude_change_no_reason(self, ctr):
        ctr.accept_aircraft("SAS901")
        ctr.request_altitude_change("SAS901", 37000, 35000)
        ctr.get_pending_commands()
        ctr.deny_altitude_change("SAS901")
        cmds = ctr.get_pending_commands()
        assert cmds[0].command_type == "deny_altitude"
        assert "traffic" not in cmds[0].data["instruction"]

    def test_deny_no_request(self, ctr):
        ctr.deny_altitude_change("NONEXIST")  # should not raise

    def test_get_pending_altitude_request_unknown(self, ctr):
        assert ctr.get_pending_altitude_request("NONEXIST") is None

    def test_altitude_request_logs_history(self, ctr):
        ctr.accept_aircraft("SAS901")
        ctr.request_altitude_change("SAS901", 37000, 35000)
        history = ctr.get_aircraft_history("SAS901")
        assert len(history) == 1
        assert history[0].command_type == "altitude_request"

    def test_approve_altitude_logs_history(self, ctr):
        ctr.accept_aircraft("SAS901")
        ctr.request_altitude_change("SAS901", 37000, 35000)
        ctr.get_pending_commands()
        ctr.approve_altitude_change("SAS901")
        history = ctr.get_aircraft_history("SAS901")
        assert len(history) == 2
        assert history[1].command_type == "approve_altitude"

    def test_deny_altitude_logs_history(self, ctr):
        ctr.accept_aircraft("SAS901")
        ctr.request_altitude_change("SAS901", 37000, 35000)
        ctr.get_pending_commands()
        ctr.deny_altitude_change("SAS901")
        history = ctr.get_aircraft_history("SAS901")
        assert len(history) == 2
        assert history[1].command_type == "deny_altitude"


# ──────────────────────────────────────────────
# Top of Descent
# ──────────────────────────────────────────────

class TestTopOfDescent:
    def test_clear_top_of_descent_sets_state(self, ctr):
        ctr.accept_aircraft("SAS901")
        ctr.clear_top_of_descent("SAS901", 8000, "KOGOS")
        assert ctr.get_aircraft_center_state("SAS901") == CenterState.DESCENT_CLEARED

    def test_clear_top_of_descent_issues_command(self, ctr):
        ctr.accept_aircraft("SAS901")
        ctr.clear_top_of_descent("SAS901", 8000, "KOGOS", "ARN1N")
        cmds = ctr.get_pending_commands()
        assert cmds[0].command_type == "top_of_descent"
        assert "KOGOS" in cmds[0].data["instruction"]
        assert "8000ft" in cmds[0].data["instruction"]
        assert "ARN1N" in cmds[0].data["instruction"]

    def test_clear_top_of_descent_no_star(self, ctr):
        ctr.accept_aircraft("SAS901")
        ctr.clear_top_of_descent("SAS901", 8000, "KOGOS")
        cmds = ctr.get_pending_commands()
        assert "via" not in cmds[0].data["instruction"]

    def test_clear_top_of_descent_auto_accepts(self, ctr):
        ctr.clear_top_of_descent("SAS901", 8000, "KOGOS")
        assert ctr.is_controlling("SAS901")

    def test_clear_top_of_descent_creates_clearance(self, ctr):
        ctr.accept_aircraft("SAS901")
        ctr.clear_top_of_descent("SAS901", 8000, "KOGOS", "ARN1N")
        clearance = ctr.get_clearance_state("SAS901")
        assert clearance is not None
        assert clearance.clearance_type == "top_of_descent"
        assert clearance.details["descent_point"] == "KOGOS"

    def test_clear_top_of_descent_logs_history(self, ctr):
        ctr.accept_aircraft("SAS901")
        ctr.clear_top_of_descent("SAS901", 8000, "KOGOS")
        history = ctr.get_aircraft_history("SAS901")
        assert len(history) == 1
        assert history[0].command_type == "top_of_descent"

    def test_estimate_top_of_descent_with_airway(self, ctr):
        ctr.accept_aircraft("SAS901")
        ctr.assign_airway("SAS901", "M852", "ARN", "KOGOS", distance_to_exit_nm=100.0)
        # 35000 - 8000 = 27000 / 300 = 90nm needed, 100nm available = 10nm margin
        remaining = ctr.estimate_top_of_descent("SAS901", 8000, 35000, 100.0)
        assert remaining == 10

    def test_estimate_top_of_descent_exactly_at_tod(self, ctr):
        ctr.accept_aircraft("SAS901")
        ctr.assign_airway("SAS901", "M852", "ARN", "KOGOS", distance_to_exit_nm=100.0)
        # 35000 - 8000 = 27000 / 300 = 90nm needed, 90nm available = 0 margin
        remaining = ctr.estimate_top_of_descent("SAS901", 8000, 35000, 90.0)
        assert remaining == 0

    def test_estimate_top_of_descent_past_tod(self, ctr):
        ctr.accept_aircraft("SAS901")
        ctr.assign_airway("SAS901", "M852", "ARN", "KOGOS", distance_to_exit_nm=100.0)
        # 35000 - 8000 = 27000 / 300 = 90nm needed, 50nm available = past TOD
        remaining = ctr.estimate_top_of_descent("SAS901", 8000, 35000, 50.0)
        assert remaining == 0

    def test_estimate_top_of_descent_no_airway(self, ctr):
        result = ctr.estimate_top_of_descent("SAS901", 8000, 35000, 100.0)
        assert result is None

    def test_estimate_top_of_descent_already_below(self, ctr):
        ctr.accept_aircraft("SAS901")
        ctr.assign_airway("SAS901", "M852", "ARN", "KOGOS", distance_to_exit_nm=100.0)
        remaining = ctr.estimate_top_of_descent("SAS901", 8000, 5000, 100.0)
        assert remaining == 100


# ──────────────────────────────────────────────
# Adjacent Center Handoffs
# ──────────────────────────────────────────────

class TestAdjacentCenterHandoff:
    def test_handoff_to_adjacent_center_sets_state(self, ctr):
        ctr.accept_aircraft("SAS901")
        ctr.handoff_to_adjacent_center("SAS901", "ESSA_CTR_N", 135.7)
        assert ctr.get_aircraft_center_state("SAS901") == CenterState.HANDOFF

    def test_handoff_to_adjacent_center_issues_command(self, ctr):
        ctr.accept_aircraft("SAS901")
        ctr.handoff_to_adjacent_center("SAS901", "ESSA_CTR_N", 135.7)
        cmds = ctr.get_pending_commands()
        assert cmds[0].command_type == "contact_center"
        assert "ESSA_CTR_N" in cmds[0].data["instruction"]
        assert "135.7" in cmds[0].data["instruction"]

    def test_handoff_to_adjacent_center_proposes_handoff(self, ctr):
        ctr.accept_aircraft("SAS901")
        ctr.handoff_to_adjacent_center("SAS901", "ESSA_CTR_N", 135.7)
        hofs = ctr.get_pending_handoffs()
        assert len(hofs) == 1
        assert hofs[0].to_controller == "ESSA_CTR_N"

    def test_handoff_to_adjacent_center_not_controlling(self, ctr):
        ctr.handoff_to_adjacent_center("NONEXIST", "ESSA_CTR_N", 135.7)
        assert ctr.get_pending_commands() == []

    def test_handoff_to_adjacent_logs_history(self, ctr):
        ctr.accept_aircraft("SAS901")
        ctr.handoff_to_adjacent_center("SAS901", "ESSA_CTR_N", 135.7)
        history = ctr.get_aircraft_history("SAS901")
        assert len(history) == 1
        assert history[0].command_type == "contact_center"

    def test_release_to_adjacent_center_removes_aircraft(self, ctr):
        ctr.accept_aircraft("SAS901")
        ctr.assign_airway("SAS901", "M852", "ARN", "KOGOS")
        ctr.request_altitude_change("SAS901", 37000, 35000)
        ctr.release_to_adjacent_center("SAS901")
        assert not ctr.is_controlling("SAS901")

    def test_release_to_adjacent_center_removes_state(self, ctr):
        ctr.accept_aircraft("SAS901")
        ctr.assign_airway("SAS901", "M852", "ARN", "KOGOS")
        ctr.release_to_adjacent_center("SAS901")
        assert ctr.get_aircraft_center_state("SAS901") is None

    def test_release_to_adjacent_center_removes_airway(self, ctr):
        ctr.accept_aircraft("SAS901")
        ctr.assign_airway("SAS901", "M852", "ARN", "KOGOS")
        ctr.release_to_adjacent_center("SAS901")
        assert ctr.get_airway_assignment("SAS901") is None

    def test_release_to_adjacent_center_clears_requests(self, ctr):
        ctr.accept_aircraft("SAS901")
        ctr.request_altitude_change("SAS901", 37000, 35000)
        ctr.release_to_adjacent_center("SAS901")
        assert ctr.get_pending_altitude_request("SAS901") is None

    def test_release_to_adjacent_center_tracks_sector_time(self, ctr):
        ctr.accept_aircraft("SAS901")
        ctr.assign_airway("SAS901", "M852", "ARN", "KOGOS")
        ctr.release_to_adjacent_center("SAS901", current_time=500.0)
        assert ctr._last_sector_release_time.get("KOGOS") == 500.0

    def test_release_to_adjacent_center_not_controlling(self, ctr):
        ctr.release_to_adjacent_center("NONEXIST")
        assert ctr.get_pending_commands() == []

    def test_release_to_adjacent_center_no_airway(self, ctr):
        ctr.accept_aircraft("SAS901")
        ctr.release_to_adjacent_center("SAS901")
        assert not ctr.is_controlling("SAS901")

    def test_can_handoff_to_adjacent_no_airway(self, ctr):
        ctr.accept_aircraft("SAS901")
        assert ctr.can_handoff_to_adjacent_center("SAS901") is True

    def test_can_handoff_to_adjacent_first_aircraft(self, ctr):
        ctr.accept_aircraft("SAS901")
        ctr.assign_airway("SAS901", "M852", "ARN", "KOGOS")
        assert ctr.can_handoff_to_adjacent_center("SAS901") is True

    def test_can_handoff_to_adjacent_separation_met(self, ctr):
        ctr.accept_aircraft("SAS901")
        ctr.assign_airway("SAS901", "M852", "ARN", "KOGOS")
        ctr.release_to_adjacent_center("SAS901", current_time=0.0)
        ctr.accept_aircraft("SAS902")
        ctr.assign_airway("SAS902", "M852", "ARN", "KOGOS")
        ctr.get_pending_commands()
        with patch("time.time", return_value=200.0):
            assert ctr.can_handoff_to_adjacent_center("SAS902") is True

    def test_can_handoff_to_adjacent_separation_not_met(self, ctr):
        ctr.accept_aircraft("SAS901")
        ctr.assign_airway("SAS901", "M852", "ARN", "KOGOS")
        ctr.release_to_adjacent_center("SAS901", current_time=0.0)
        ctr.accept_aircraft("SAS902")
        ctr.assign_airway("SAS902", "M852", "ARN", "KOGOS")
        with patch("time.time", return_value=50.0):
            assert ctr.can_handoff_to_adjacent_center("SAS902") is False

    def test_can_handoff_to_adjacent_different_exit_fix(self, ctr):
        ctr.accept_aircraft("SAS901")
        ctr.assign_airway("SAS901", "M852", "ARN", "KOGOS")
        ctr.release_to_adjacent_center("SAS901", current_time=0.0)
        ctr.accept_aircraft("SAS902")
        ctr.assign_airway("SAS902", "N872", "ARN", "XILAN")
        with patch("time.time", return_value=10.0):
            assert ctr.can_handoff_to_adjacent_center("SAS902") is True

    def test_accept_from_adjacent_center(self, ctr):
        ctr.accept_from_adjacent_center("SAS901", 35000)
        assert ctr.is_controlling("SAS901")
        assert ctr.get_aircraft_center_state("SAS901") == CenterState.ENROUTE
        cmds = ctr.get_pending_commands()
        assert cmds[0].command_type == "contact_center"
        assert "ESSA_CTR" in cmds[0].data["instruction"]


# ──────────────────────────────────────────────
# Process — Automated TOD Advisory
# ──────────────────────────────────────────────

class TestProcess:
    def test_process_triggers_tod_advisory(self, ctr_tod_20):
        ctr_tod_20.accept_aircraft("SAS901")
        ctr_tod_20.assign_airway(
            "SAS901", "M852", "ARN", "KOGOS",
            fixes=["ARN", "XILAN", "KOGOS"],
            distance_to_exit_nm=15.0,
        )
        ctr_tod_20.get_pending_commands()
        ctr_tod_20.process(1.0, {})
        cmds = ctr_tod_20.get_pending_commands()
        assert len(cmds) >= 1
        assert cmds[0].command_type == "top_of_descent_advisory"
        assert "KOGOS" in cmds[0].data["instruction"]

    def test_process_no_advisory_far_from_boundary(self, ctr_tod_20):
        ctr_tod_20.accept_aircraft("SAS901")
        ctr_tod_20.assign_airway(
            "SAS901", "M852", "ARN", "KOGOS",
            distance_to_exit_nm=100.0,
        )
        ctr_tod_20.get_pending_commands()
        ctr_tod_20.process(1.0, {})
        cmds = ctr_tod_20.get_pending_commands()
        assert cmds == []

    def test_process_skips_descent_cleared(self, ctr_tod_20):
        ctr_tod_20.accept_aircraft("SAS901")
        ctr_tod_20.assign_airway(
            "SAS901", "M852", "ARN", "KOGOS",
            distance_to_exit_nm=10.0,
        )
        ctr_tod_20.get_pending_commands()
        ctr_tod_20.assign_descent("SAS901", 8000)
        ctr_tod_20.get_pending_commands()
        ctr_tod_20.process(1.0, {})
        cmds = ctr_tod_20.get_pending_commands()
        assert cmds == []

    def test_process_skips_handoff(self, ctr_tod_20):
        ctr_tod_20.accept_aircraft("SAS901")
        ctr_tod_20.assign_airway(
            "SAS901", "M852", "ARN", "KOGOS",
            distance_to_exit_nm=10.0,
        )
        ctr_tod_20.get_pending_commands()
        ctr_tod_20.handoff_to_adjacent_center("SAS901", "ESSA_CTR_N", 135.7)
        ctr_tod_20.get_pending_commands()
        ctr_tod_20.process(1.0, {})
        cmds = ctr_tod_20.get_pending_commands()
        assert cmds == []

    def test_process_skips_no_airway(self, ctr_tod_20):
        ctr_tod_20.accept_aircraft("SAS901")
        ctr_tod_20.process(1.0, {})
        assert ctr_tod_20.get_pending_commands() == []

    def test_process_empty(self, ctr):
        ctr.process(1.0, {})
        assert ctr.get_pending_commands() == []

    def test_process_custom_tod_distance(self, ctr):
        ctr = CenterController("CTR", 135.5, "CTR", tod_distance_nm=80.0)
        ctr.accept_aircraft("SAS901")
        ctr.assign_airway("SAS901", "M852", "ARN", "KOGOS", distance_to_exit_nm=70.0)
        ctr.get_pending_commands()
        ctr.process(1.0, {})
        cmds = ctr.get_pending_commands()
        assert len(cmds) == 1
        assert cmds[0].command_type == "top_of_descent_advisory"


# ──────────────────────────────────────────────
# Integration — Full Lifecycle
# ──────────────────────────────────────────────

class TestIntegration:
    def test_full_enroute_lifecycle(self, ctr):
        ctr.accept_from_departure("SAS901", 10000)
        ctr.get_pending_commands()
        ctr.assign_airway("SAS901", "M852", "ARN", "KOGOS",
                          fixes=["ARN", "XILAN", "KOGOS"], flight_level=350)
        ctr.get_pending_commands()
        ctr.advance_along_airway("SAS901", "XILAN")
        ctr.get_pending_commands()
        ctr.assign_descent("SAS901", 8000, "ARN1N")
        ctr.get_pending_commands()
        ctr.handoff_to_approach("SAS901", "ESSA_APP", 119.7)
        ctr.get_pending_commands()
        hofs = ctr.get_pending_handoffs()
        assert len(hofs) == 1
        ctr.release_to_approach("SAS901")
        assert not ctr.is_controlling("SAS901")

    def test_altitude_request_lifecycle(self, ctr):
        ctr.accept_from_departure("SAS901", 10000)
        ctr.assign_airway("SAS901", "M852", "ARN", "KOGOS", flight_level=350)
        ctr.get_pending_commands()
        ctr.request_altitude_change("SAS901", 37000, 35000, "winds")
        ctr.get_pending_commands()
        ctr.approve_altitude_change("SAS901")
        cmds = ctr.get_pending_commands()
        assert "37000" in cmds[0].data["instruction"]
        assert ctr.get_aircraft_center_state("SAS901") == CenterState.CLIMB_CLEARED

    def test_sector_handoff_lifecycle(self, ctr):
        ctr.accept_from_departure("SAS901", 10000)
        ctr.assign_airway("SAS901", "M852", "ARN", "KOGOS")
        ctr.get_pending_commands()
        ctr.handoff_to_adjacent_center("SAS901", "ESSA_CTR_N", 135.7)
        hofs = ctr.get_pending_handoffs()
        assert len(hofs) == 1
        assert hofs[0].to_controller == "ESSA_CTR_N"
        ctr.release_to_adjacent_center("SAS901")
        assert not ctr.is_controlling("SAS901")

    def test_adjacent_center_to_approach(self, ctr):
        ctr.accept_from_adjacent_center("SAS901", 35000)
        ctr.assign_airway("SAS901", "M852", "ARN", "KOGOS")
        ctr.get_pending_commands()
        ctr.clear_top_of_descent("SAS901", 8000, "KOGOS", "ARN1N")
        ctr.get_pending_commands()
        ctr.handoff_to_approach("SAS901", "ESSA_APP", 119.7)
        ctr.release_to_approach("SAS901")
        assert ctr.aircraft_count == 0

    def test_process_and_release_clean_state(self, ctr_tod_20):
        ctr_tod_20.accept_aircraft("SAS901")
        ctr_tod_20.assign_airway(
            "SAS901", "M852", "ARN", "KOGOS",
            distance_to_exit_nm=10.0,
        )
        ctr_tod_20.request_altitude_change("SAS901", 37000, 35000)
        ctr_tod_20.get_pending_commands()
        ctr_tod_20.process(1.0, {})
        ctr_tod_20.get_pending_commands()
        ctr_tod_20.release_to_adjacent_center("SAS901")
        assert ctr_tod_20.aircraft_count == 0
        assert ctr_tod_20.get_airway_assignment("SAS901") is None
        assert ctr_tod_20.get_pending_altitude_request("SAS901") is None

    def test_consecutive_sector_releases(self, ctr):
        ctr.accept_aircraft("SAS901")
        ctr.assign_airway("SAS901", "M852", "ARN", "KOGOS")
        ctr.release_to_adjacent_center("SAS901", current_time=100.0)
        ctr.accept_aircraft("SAS902")
        ctr.assign_airway("SAS902", "M852", "ARN", "KOGOS")
        with patch("time.time", return_value=150.0):
            assert ctr.can_handoff_to_adjacent_center("SAS902") is False
        with patch("time.time", return_value=250.0):
            assert ctr.can_handoff_to_adjacent_center("SAS902") is True


# ──────────────────────────────────────────────
# Model Dataclasses
# ──────────────────────────────────────────────

class TestAirwayAssignmentDataclass:
    def test_create_with_all_fields(self):
        airway = AirwayAssignment(
            airway_name="M852",
            entry_fix="ARN",
            exit_fix="KOGOS",
            fixes=["ARN", "XILAN", "KOGOS"],
            current_fix_index=1,
            assigned_flight_level=350,
            distance_to_exit_nm=50.0,
        )
        assert airway.airway_name == "M852"
        assert airway.entry_fix == "ARN"
        assert airway.exit_fix == "KOGOS"
        assert airway.fixes == ["ARN", "XILAN", "KOGOS"]
        assert airway.current_fix_index == 1
        assert airway.assigned_flight_level == 350
        assert airway.distance_to_exit_nm == 50.0

    def test_create_minimal(self):
        airway = AirwayAssignment(airway_name="M852", entry_fix="ARN", exit_fix="KOGOS")
        assert airway.airway_name == "M852"
        assert airway.fixes == []
        assert airway.current_fix_index == 0
        assert airway.assigned_flight_level == 0


class TestAltitudeChangeRequestDataclass:
    def test_create_with_all_fields(self):
        req = AltitudeChangeRequest(
            callsign="SAS901",
            requested_alt_ft=37000,
            current_alt_ft=35000,
            reason="winds",
            approved=True,
            responded_at_s=100.0,
        )
        assert req.callsign == "SAS901"
        assert req.requested_alt_ft == 37000
        assert req.current_alt_ft == 35000
        assert req.reason == "winds"
        assert req.approved is True

    def test_create_minimal(self):
        req = AltitudeChangeRequest(
            callsign="SAS901", requested_alt_ft=37000, current_alt_ft=35000,
        )
        assert req.reason == ""
        assert req.approved is None
        assert req.responded_at_s is None


# ──────────────────────────────────────────────
# CenterState Enum
# ──────────────────────────────────────────────

class TestCenterState:
    def test_new_values(self):
        assert CenterState.CRUISE.value == "cruise"
        assert CenterState.CLIMB_CLEARED.value == "climb_cleared"

    def test_existing_values_preserved(self):
        assert CenterState.IDLE.value == "idle"
        assert CenterState.ENROUTE.value == "enroute"
        assert CenterState.DESCENT_CLEARED.value == "descent_cleared"
        assert CenterState.HANDOFF.value == "handoff"

    def test_all_members(self):
        assert len(CenterState) == 6


# ──────────────────────────────────────────────
# Backward Compatibility
# ──────────────────────────────────────────────

class TestBackwardCompatibility:
    def test_initial_state(self, ctr):
        assert ctr.callsign == "ESSA_CTR"
        assert ctr.frequency == 135.5
        assert ctr.sector_id == "ESSA_CTR"
        assert ctr.facility_name == "Stockholm Center"

    def test_accept_from_departure(self, ctr):
        ctr.accept_from_departure("SAS901", 10000)
        assert ctr.is_controlling("SAS901")
        assert ctr.get_aircraft_center_state("SAS901") == CenterState.ENROUTE
        cmds = ctr.get_pending_commands()
        assert cmds[0].command_type == "contact_center"

    def test_maintain_altitude(self, ctr):
        ctr.maintain_altitude("SAS901", 35000)
        assert ctr.get_aircraft_center_state("SAS901") == CenterState.ENROUTE
        cmds = ctr.get_pending_commands()
        assert cmds[0].command_type == "maintain"
        assert cmds[0].data["altitude_ft"] == 35000

    def test_assign_climb(self, ctr):
        ctr.assign_climb("SAS901", 35000, 1013)
        assert ctr.get_aircraft_center_state("SAS901") == CenterState.ENROUTE
        cmds = ctr.get_pending_commands()
        assert cmds[0].command_type == "climb"
        assert cmds[0].data["target_altitude_ft"] == 35000

    def test_assign_climb_no_qnh(self, ctr):
        ctr.assign_climb("SAS901", 35000)
        cmds = ctr.get_pending_commands()
        assert "QNH" not in cmds[0].data.get("instruction", "")

    def test_assign_descent(self, ctr):
        ctr.assign_descent("SAS901", 8000, "ARN1N")
        assert ctr.get_aircraft_center_state("SAS901") == CenterState.DESCENT_CLEARED
        cmds = ctr.get_pending_commands()
        assert cmds[0].command_type == "descend"
        assert cmds[0].data["star"] == "ARN1N"

    def test_assign_descent_no_star(self, ctr):
        ctr.assign_descent("SAS901", 8000)
        cmds = ctr.get_pending_commands()
        assert cmds[0].command_type == "descend"

    def test_handoff_to_approach(self, ctr):
        ctr.accept_aircraft("SAS901")
        ctr.handoff_to_approach("SAS901", "ESSA_APP", 119.7)
        assert ctr.get_aircraft_center_state("SAS901") == CenterState.HANDOFF
        cmds = ctr.get_pending_commands()
        assert cmds[0].command_type == "contact_approach"
        assert cmds[0].data["frequency"] == 119.7
        hofs = ctr.get_pending_handoffs()
        assert len(hofs) == 1
        assert hofs[0].to_controller == "ESSA_APP"

    def test_release_to_approach(self, ctr):
        ctr.accept_aircraft("SAS901")
        ctr.release_to_approach("SAS901")
        assert not ctr.is_controlling("SAS901")

    def test_accept_from_adjacent_center(self, ctr):
        ctr.accept_from_adjacent_center("SAS901", 35000)
        assert ctr.is_controlling("SAS901")
        assert ctr.get_aircraft_center_state("SAS901") == CenterState.ENROUTE
        cmds = ctr.get_pending_commands()
        assert cmds[0].command_type == "contact_center"

    def test_center_overflight_lifecycle(self, ctr):
        ctr.accept_from_departure("SAS901", 10000)
        ctr.maintain_altitude("SAS901", 35000)
        ctr.assign_climb("SAS901", 37000)
        ctr.assign_descent("SAS901", 8000, "ARN1N")
        ctr.handoff_to_approach("SAS901", "ESSA_APP", 119.7)
        ctr.release_to_approach("SAS901")
        assert ctr.aircraft_count == 0

    def test_process_noop(self, ctr):
        ctr.process(1.0, {})
        assert True

    def test_accept_aircraft_idempotent(self, ctr):
        ctr.accept_aircraft("AC1")
        ctr.accept_aircraft("AC1")
        assert ctr.aircraft_count == 1

    def test_get_aircraft_center_state_unknown(self, ctr):
        assert ctr.get_aircraft_center_state("NONEXIST") is None
