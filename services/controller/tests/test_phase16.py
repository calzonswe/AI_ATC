import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import time
from unittest.mock import patch

import pytest

from approach import ApproachController
from base import BaseController
from models import (
    ApproachState,
    STARAssignment,
)


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────

@pytest.fixture
def app():
    return ApproachController("ESSA_APP", 119.7, "ESSA_APP", "ESSA")


# ──────────────────────────────────────────────
# Accept From Center
# ──────────────────────────────────────────────

class TestAcceptFromCenter:
    def test_accept_from_center_sets_state(self, app):
        app.accept_from_center("SAS901", 12000)
        assert app.is_controlling("SAS901")
        assert app.get_aircraft_approach_state("SAS901") == ApproachState.VECTORING

    def test_accept_from_center_issues_contact(self, app):
        app.accept_from_center("SAS901", 12000)
        cmds = app.get_pending_commands()
        assert cmds[0].command_type == "contact_approach"
        assert "119.7" in cmds[0].data["instruction"]

    def test_accept_from_center_with_star_info(self, app):
        app.accept_from_center("SAS901", 12000, star_info={
            "star_name": "KOGOS2A",
            "initial_alt_ft": 12000,
            "approach_runway": "01L",
        })
        star = app.get_star_assignment("SAS901")
        assert star is not None
        assert star.star_name == "KOGOS2A"
        assert star.approach_runway == "01L"

    def test_accept_from_center_with_star_creates_clearance(self, app):
        app.accept_from_center("SAS901", 12000, star_info={
            "star_name": "KOGOS2A",
            "initial_alt_ft": 12000,
        })
        clearance = app.get_clearance_state("SAS901")
        assert clearance is not None
        assert clearance.clearance_type == "star"

    def test_accept_from_center_no_star_info(self, app):
        app.accept_from_center("SAS901", 12000)
        assert app.get_star_assignment("SAS901") is None

    def test_accept_from_center_logs_history(self, app):
        app.accept_from_center("SAS901", 12000)
        history = app.get_aircraft_history("SAS901")
        assert len(history) == 1
        assert history[0].command_type == "contact_approach"


# ──────────────────────────────────────────────
# STAR Assignment
# ──────────────────────────────────────────────

class TestSTARAssignment:
    def test_assign_star_creates_assignment(self, app):
        app.assign_star("SAS901", "KOGOS2A", 12000, "01L")
        star = app.get_star_assignment("SAS901")
        assert star is not None
        assert star.star_name == "KOGOS2A"
        assert star.initial_alt_ft == 12000
        assert star.approach_runway == "01L"

    def test_assign_star_sets_state(self, app):
        app.assign_star("SAS901", "KOGOS2A", 12000)
        assert app.get_aircraft_approach_state("SAS901") == ApproachState.VECTORING

    def test_assign_star_issues_command(self, app):
        app.assign_star("SAS901", "KOGOS2A", 12000, "01L")
        cmds = app.get_pending_commands()
        assert len(cmds) == 1
        assert cmds[0].command_type == "assign_star"
        assert "KOGOS2A" in cmds[0].data["instruction"]
        assert "12000ft" in cmds[0].data["instruction"]

    def test_assign_star_with_runway(self, app):
        app.assign_star("SAS901", "KOGOS2A", 12000, "01L")
        cmds = app.get_pending_commands()
        assert "01L" in cmds[0].data["instruction"]
        assert app.get_approach_runway("SAS901") == "01L"

    def test_assign_star_custom_intercept_distance(self, app):
        app.assign_star("SAS901", "KOGOS2A", 12000, "01L", intercept_distance_nm=15.0)
        star = app.get_star_assignment("SAS901")
        assert star.intercept_distance_nm == 15.0

    def test_assign_star_auto_accepts(self, app):
        assert not app.is_controlling("SAS901")
        app.assign_star("SAS901", "KOGOS2A", 12000)
        assert app.is_controlling("SAS901")

    def test_assign_star_creates_clearance(self, app):
        app.assign_star("SAS901", "KOGOS2A", 12000, "01L")
        clearance = app.get_clearance_state("SAS901")
        assert clearance is not None
        assert clearance.clearance_type == "descend_via_star"
        assert clearance.details["star"] == "KOGOS2A"

    def test_assign_star_logs_history(self, app):
        app.assign_star("SAS901", "KOGOS2A", 12000)
        history = app.get_aircraft_history("SAS901")
        assert len(history) == 1
        assert history[0].command_type == "assign_star"

    def test_get_star_assignment_unknown(self, app):
        assert app.get_star_assignment("NONEXIST") is None


# ──────────────────────────────────────────────
# Radar Vectors
# ──────────────────────────────────────────────

class TestVector:
    def test_vector_to_ils_sets_state(self, app):
        app.vector_to_ils("SAS901", 270, 3000)
        assert app.get_aircraft_approach_state("SAS901") == ApproachState.VECTORING

    def test_vector_to_ils_issues_command(self, app):
        app.vector_to_ils("SAS901", 270, 3000)
        cmds = app.get_pending_commands()
        assert cmds[0].command_type == "vector"
        assert "270" in cmds[0].data["instruction"]
        assert "3000ft" in cmds[0].data["instruction"]

    def test_vector_to_ils_auto_accepts(self, app):
        app.vector_to_ils("SAS901", 270, 3000)
        assert app.is_controlling("SAS901")

    def test_vector_updates_star_heading(self, app):
        app.assign_star("SAS901", "KOGOS2A", 12000)
        app.get_pending_commands()
        app.vector_to_ils("SAS901", 270, 3000)
        star = app.get_star_assignment("SAS901")
        assert star.vector_heading == 270

    def test_vector_logs_history(self, app):
        app.vector_to_ils("SAS901", 270, 3000)
        history = app.get_aircraft_history("SAS901")
        assert len(history) == 1
        assert history[0].command_type == "vector"


# ──────────────────────────────────────────────
# Speed Control
# ──────────────────────────────────────────────

class TestSpeed:
    def test_assign_speed_stores_restriction(self, app):
        app.accept_aircraft("SAS901")
        app.assign_speed("SAS901", 220)
        assert app.get_speed_restriction("SAS901") == 220

    def test_assign_speed_issues_command(self, app):
        app.accept_aircraft("SAS901")
        app.assign_speed("SAS901", 220)
        cmds = app.get_pending_commands()
        assert cmds[0].command_type == "speed"
        assert "220" in cmds[0].data["instruction"]

    def test_assign_speed_maximum_default(self, app):
        app.accept_aircraft("SAS901")
        app.assign_speed("SAS901", 220)
        cmds = app.get_pending_commands()
        assert "Reduce to" in cmds[0].data["instruction"]

    def test_assign_speed_minimum(self, app):
        app.accept_aircraft("SAS901")
        app.assign_speed("SAS901", 180, "minimum")
        cmds = app.get_pending_commands()
        assert "Minimum speed" in cmds[0].data["instruction"]

    def test_assign_speed_updates_star(self, app):
        app.assign_star("SAS901", "KOGOS2A", 12000)
        app.get_pending_commands()
        app.assign_speed("SAS901", 220)
        star = app.get_star_assignment("SAS901")
        assert star.speed_restriction == 220

    def test_assign_speed_non_controlling(self, app):
        app.assign_speed("NONEXIST", 220)
        assert app.get_pending_commands() == []

    def test_get_speed_restriction_unknown(self, app):
        assert app.get_speed_restriction("NONEXIST") is None


# ──────────────────────────────────────────────
# Altitude Management
# ──────────────────────────────────────────────

class TestAltitude:
    def test_assign_descent_sets_state(self, app):
        app.accept_aircraft("SAS901")
        app.assign_descent("SAS901", 5000)
        assert app.get_aircraft_approach_state("SAS901") == ApproachState.DESCENT_CLEARED

    def test_assign_descent_issues_command(self, app):
        app.accept_aircraft("SAS901")
        app.assign_descent("SAS901", 5000)
        cmds = app.get_pending_commands()
        assert cmds[0].command_type == "descend"
        assert "5000ft" in cmds[0].data["instruction"]

    def test_assign_descent_updates_star(self, app):
        app.assign_star("SAS901", "KOGOS2A", 12000)
        app.get_pending_commands()
        app.assign_descent("SAS901", 5000)
        star = app.get_star_assignment("SAS901")
        assert star.current_alt_ft == 5000

    def test_assign_descent_auto_accepts(self, app):
        app.assign_descent("SAS901", 5000)
        assert app.is_controlling("SAS901")

    def test_assign_descent_creates_clearance(self, app):
        app.accept_aircraft("SAS901")
        app.assign_descent("SAS901", 5000)
        clearance = app.get_clearance_state("SAS901")
        assert clearance is not None
        assert clearance.clearance_type == "descend"

    def test_maintain_altitude_sets_state(self, app):
        app.accept_aircraft("SAS901")
        app.maintain_altitude("SAS901", 5000)
        assert app.get_aircraft_approach_state("SAS901") == ApproachState.DESCENT_CLEARED

    def test_maintain_altitude_issues_command(self, app):
        app.accept_aircraft("SAS901")
        app.maintain_altitude("SAS901", 5000)
        cmds = app.get_pending_commands()
        assert cmds[0].command_type == "maintain"
        assert "5000ft" in cmds[0].data["instruction"]

    def test_maintain_altitude_updates_star(self, app):
        app.assign_star("SAS901", "KOGOS2A", 12000)
        app.get_pending_commands()
        app.maintain_altitude("SAS901", 7000)
        star = app.get_star_assignment("SAS901")
        assert star.current_alt_ft == 7000

    def test_maintain_altitude_auto_accepts(self, app):
        app.maintain_altitude("SAS901", 5000)
        assert app.is_controlling("SAS901")

    def test_maintain_altitude_creates_clearance(self, app):
        app.accept_aircraft("SAS901")
        app.maintain_altitude("SAS901", 5000)
        clearance = app.get_clearance_state("SAS901")
        assert clearance is not None
        assert clearance.clearance_type == "maintain"


# ──────────────────────────────────────────────
# Holding
# ──────────────────────────────────────────────

class TestHold:
    def test_assign_hold_sets_state(self, app):
        app.assign_hold("SAS901", "KOGOS", 8000)
        assert app.get_aircraft_approach_state("SAS901") == ApproachState.HOLDING

    def test_assign_hold_issues_command(self, app):
        app.assign_hold("SAS901", "KOGOS", 8000)
        cmds = app.get_pending_commands()
        assert cmds[0].command_type == "hold"
        assert "KOGOS" in cmds[0].data["instruction"]
        assert "8000ft" in cmds[0].data["instruction"]

    def test_assign_hold_with_eat(self, app):
        app.assign_hold("SAS901", "KOGOS", 8000, expected_approach_time="12:30")
        cmds = app.get_pending_commands()
        assert "12:30" in cmds[0].data["instruction"]

    def test_assign_hold_auto_accepts(self, app):
        app.assign_hold("SAS901", "KOGOS", 8000)
        assert app.is_controlling("SAS901")

    def test_assign_hold_creates_clearance(self, app):
        app.assign_hold("SAS901", "KOGOS", 8000)
        clearance = app.get_clearance_state("SAS901")
        assert clearance is not None
        assert clearance.clearance_type == "hold"
        assert clearance.details["fix"] == "KOGOS"


# ──────────────────────────────────────────────
# ILS Approach Clearance
# ──────────────────────────────────────────────

class TestILS:
    def test_clear_ils_sets_state(self, app):
        app.accept_aircraft("SAS901")
        app.clear_ils("SAS901", "01L", 110.3)
        assert app.get_aircraft_approach_state("SAS901") == ApproachState.ILS_CLEARED

    def test_clear_ils_issues_command(self, app):
        app.accept_aircraft("SAS901")
        app.clear_ils("SAS901", "01L", 110.3)
        cmds = app.get_pending_commands()
        assert cmds[0].command_type == "clear_ils"
        assert "110.3" in cmds[0].data["instruction"]
        assert "01L" in cmds[0].data["instruction"]

    def test_clear_ils_tracks_runway(self, app):
        app.accept_aircraft("SAS901")
        app.clear_ils("SAS901", "01L", 110.3)
        assert app.get_approach_runway("SAS901") == "01L"

    def test_clear_ils_creates_clearance(self, app):
        app.accept_aircraft("SAS901")
        app.clear_ils("SAS901", "01L", 110.3)
        clearance = app.get_clearance_state("SAS901")
        assert clearance is not None
        assert clearance.clearance_type == "ils_approach"
        assert clearance.details["runway"] == "01L"


# ──────────────────────────────────────────────
# Visual Approach Clearance
# ──────────────────────────────────────────────

class TestVisual:
    def test_clear_visual_sets_state(self, app):
        app.clear_visual("SAS901", "01L")
        assert app.get_aircraft_approach_state("SAS901") == ApproachState.VISUAL_CLEARED

    def test_clear_visual_issues_command(self, app):
        app.clear_visual("SAS901", "01L")
        cmds = app.get_pending_commands()
        assert cmds[0].command_type == "clear_visual"
        assert "visual approach" in cmds[0].data["instruction"]
        assert "01L" in cmds[0].data["instruction"]

    def test_clear_visual_tracks_runway(self, app):
        app.clear_visual("SAS901", "01L")
        assert app.get_approach_runway("SAS901") == "01L"

    def test_clear_visual_auto_accepts(self, app):
        app.clear_visual("SAS901", "01L")
        assert app.is_controlling("SAS901")

    def test_clear_visual_creates_clearance(self, app):
        app.clear_visual("SAS901", "01L")
        clearance = app.get_clearance_state("SAS901")
        assert clearance is not None
        assert clearance.clearance_type == "visual_approach"


# ──────────────────────────────────────────────
# RNAV Approach Clearance
# ──────────────────────────────────────────────

class TestRNAV:
    def test_clear_rnav_sets_state(self, app):
        app.clear_rnav("SAS901", "01L")
        assert app.get_aircraft_approach_state("SAS901") == ApproachState.RNAV_CLEARED

    def test_clear_rnav_issues_command(self, app):
        app.clear_rnav("SAS901", "01L", "RNP")
        cmds = app.get_pending_commands()
        assert cmds[0].command_type == "clear_rnav"
        assert "RNP approach" in cmds[0].data["instruction"]
        assert "01L" in cmds[0].data["instruction"]

    def test_clear_rnav_with_type(self, app):
        app.clear_rnav("SAS901", "19R", "RNAV")
        cmds = app.get_pending_commands()
        assert "RNAV" in cmds[0].data["instruction"]

    def test_clear_rnav_auto_accepts(self, app):
        app.clear_rnav("SAS901", "01L")
        assert app.is_controlling("SAS901")

    def test_clear_rnav_creates_clearance(self, app):
        app.clear_rnav("SAS901", "01L", "RNP")
        clearance = app.get_clearance_state("SAS901")
        assert clearance is not None
        assert clearance.clearance_type == "rnav_approach"
        assert clearance.details["rnav_type"] == "RNP"

    def test_clear_rnav_tracks_runway(self, app):
        app.clear_rnav("SAS901", "19R")
        assert app.get_approach_runway("SAS901") == "19R"


# ──────────────────────────────────────────────
# Landing Sequencing
# ──────────────────────────────────────────────

class TestSequencing:
    def test_assign_landing_sequence_sets_state(self, app):
        app.assign_landing_sequence("SAS901", 1)
        assert app.get_aircraft_approach_state("SAS901") == ApproachState.APPROACH_SEQUENCE

    def test_assign_landing_sequence_number_one(self, app):
        app.assign_landing_sequence("SAS901", 1)
        assert app.get_landing_sequence("SAS901") == 1
        cmds = app.get_pending_commands()
        assert "1st" in cmds[0].data["instruction"]

    def test_assign_landing_sequence_number_two(self, app):
        app.assign_landing_sequence("SAS901", 2)
        cmds = app.get_pending_commands()
        assert "2nd" in cmds[0].data["instruction"]

    def test_assign_landing_sequence_number_three(self, app):
        app.assign_landing_sequence("SAS901", 3)
        cmds = app.get_pending_commands()
        assert "3rd" in cmds[0].data["instruction"]

    def test_assign_landing_sequence_number_four(self, app):
        app.assign_landing_sequence("SAS901", 4)
        cmds = app.get_pending_commands()
        assert "4th" in cmds[0].data["instruction"]

    def test_assign_landing_sequence_with_runway(self, app):
        app.assign_landing_sequence("SAS901", 2, runway="01L")
        assert app.get_landing_sequence("SAS901") == 2
        assert app.get_approach_runway("SAS901") == "01L"
        cmds = app.get_pending_commands()
        assert "01L" in cmds[0].data["instruction"]

    def test_assign_landing_sequence_auto_accepts(self, app):
        app.assign_landing_sequence("SAS901", 1)
        assert app.is_controlling("SAS901")

    def test_get_landing_sequence_unknown(self, app):
        assert app.get_landing_sequence("NONEXIST") is None


# ──────────────────────────────────────────────
# Handoff to Tower
# ──────────────────────────────────────────────

class TestHandoff:
    def test_handoff_to_tower_sets_state(self, app):
        app.accept_aircraft("SAS901")
        app.handoff_to_tower("SAS901", "ESSA_TWR", 118.5)
        assert app.get_aircraft_approach_state("SAS901") == ApproachState.FINAL

    def test_handoff_to_tower_issues_command(self, app):
        app.accept_aircraft("SAS901")
        app.handoff_to_tower("SAS901", "ESSA_TWR", 118.5)
        cmds = app.get_pending_commands()
        assert cmds[0].command_type == "contact_tower"
        assert "Tower" in cmds[0].data["instruction"]
        assert "118.5" in cmds[0].data["instruction"]

    def test_handoff_to_tower_proposes_handoff(self, app):
        app.accept_aircraft("SAS901")
        app.handoff_to_tower("SAS901", "ESSA_TWR", 118.5)
        hofs = app.get_pending_handoffs()
        assert len(hofs) == 1
        assert hofs[0].to_controller == "ESSA_TWR"

    def test_handoff_to_tower_not_controlling(self, app):
        app.handoff_to_tower("NONEXIST", "ESSA_TWR", 118.5)
        assert app.get_pending_commands() == []

    def test_handoff_logs_history(self, app):
        app.accept_aircraft("SAS901")
        app.handoff_to_tower("SAS901", "ESSA_TWR", 118.5)
        history = app.get_aircraft_history("SAS901")
        assert len(history) == 1
        assert history[0].command_type == "contact_tower"


# ──────────────────────────────────────────────
# Release to Tower
# ──────────────────────────────────────────────

class TestReleaseToTower:
    def test_release_to_tower_removes_aircraft(self, app):
        app.accept_aircraft("SAS901")
        app.release_to_tower("SAS901")
        assert not app.is_controlling("SAS901")

    def test_release_to_tower_removes_state(self, app):
        app.assign_star("SAS901", "KOGOS2A", 12000)
        app.release_to_tower("SAS901")
        assert app.get_aircraft_approach_state("SAS901") is None

    def test_release_to_tower_removes_star(self, app):
        app.assign_star("SAS901", "KOGOS2A", 12000)
        app.release_to_tower("SAS901")
        assert app.get_star_assignment("SAS901") is None

    def test_release_to_tower_clears_speed(self, app):
        app.accept_aircraft("SAS901")
        app.assign_speed("SAS901", 220)
        app.release_to_tower("SAS901")
        assert app.get_speed_restriction("SAS901") is None

    def test_release_to_tower_clears_sequence(self, app):
        app.assign_landing_sequence("SAS901", 1)
        app.release_to_tower("SAS901")
        assert app.get_landing_sequence("SAS901") is None

    def test_release_to_tower_tracks_landing_time(self, app):
        app.clear_ils("SAS901", "01L", 110.3)
        app.release_to_tower("SAS901", current_time=500.0)
        assert app._last_landing_time.get("01L") == 500.0

    def test_release_to_tower_not_controlling(self, app):
        app.release_to_tower("NONEXIST")
        assert app.get_pending_commands() == []

    def test_release_to_tower_no_runway(self, app):
        app.accept_aircraft("SAS901")
        app.release_to_tower("SAS901")
        assert not app.is_controlling("SAS901")


# ──────────────────────────────────────────────
# Go Around
# ──────────────────────────────────────────────

class TestGoAround:
    def test_go_around_sets_state(self, app):
        app.go_around("SAS901", "traffic on runway")
        assert app.get_aircraft_approach_state("SAS901") == ApproachState.GO_AROUND

    def test_go_around_issues_command(self, app):
        app.go_around("SAS901", "traffic on runway")
        cmds = app.get_pending_commands()
        assert cmds[0].command_type == "go_around_vector"
        assert "traffic on runway" in cmds[0].data["instruction"]

    def test_go_around_auto_accepts(self, app):
        app.go_around("SAS901")
        assert app.is_controlling("SAS901")

    def test_go_around_no_reason(self, app):
        app.go_around("SAS901")
        cmds = app.get_pending_commands()
        assert "Go around" in cmds[0].data["instruction"]


# ──────────────────────────────────────────────
# Separation Logic
# ──────────────────────────────────────────────

class TestSeparation:
    def test_can_handoff_no_runway(self, app):
        app.accept_aircraft("SAS901")
        assert app.can_handoff_to_tower("SAS901") is True

    def test_can_handoff_first_aircraft(self, app):
        app.clear_ils("SAS901", "01L", 110.3)
        assert app.can_handoff_to_tower("SAS901") is True

    def test_can_handoff_after_separation_met(self, app):
        app.clear_ils("SAS901", "01L", 110.3)
        app.release_to_tower("SAS901", current_time=0.0)
        app.clear_ils("SAS902", "01L", 110.3)
        with patch("time.time", return_value=200.0):
            assert app.can_handoff_to_tower("SAS902") is True

    def test_can_handoff_separation_not_met(self, app):
        app.clear_ils("SAS901", "01L", 110.3)
        app.release_to_tower("SAS901", current_time=0.0)
        app.clear_ils("SAS902", "01L", 110.3)
        with patch("time.time", return_value=50.0):
            assert app.can_handoff_to_tower("SAS902") is False

    def test_can_handoff_different_runway(self, app):
        app.clear_ils("SAS901", "01L", 110.3)
        app.release_to_tower("SAS901", current_time=0.0)
        app.clear_ils("SAS902", "19R", 109.7)
        with patch("time.time", return_value=10.0):
            assert app.can_handoff_to_tower("SAS902") is True

    def test_custom_separation_time(self, app):
        app = ApproachController("ESSA_APP", 119.7, "ESSA_APP", "ESSA", approach_separation_s=180)
        app.clear_ils("SAS901", "01L", 110.3)
        app.release_to_tower("SAS901", current_time=0.0)
        app.clear_ils("SAS902", "01L", 110.3)
        with patch("time.time", return_value=100.0):
            assert app.can_handoff_to_tower("SAS902") is False
        with patch("time.time", return_value=200.0):
            assert app.can_handoff_to_tower("SAS902") is True


# ──────────────────────────────────────────────
# Process — Automated Conflict Detection
# ──────────────────────────────────────────────

class TestProcess:
    def test_process_no_conflict_does_nothing(self, app):
        app.clear_ils("SAS901", "01L", 110.3)
        app.get_pending_commands()
        app.process(1.0, {})
        assert app.get_pending_commands() == []

    def test_process_detects_same_runway_conflict(self, app):
        app.clear_ils("SAS901", "01L", 110.3)
        app.get_pending_commands()
        app.release_to_tower("SAS901", current_time=0.0)
        app.clear_ils("SAS902", "01L", 110.3)
        app.get_pending_commands()
        app.clear_ils("SAS903", "01L", 110.3)
        app.get_pending_commands()
        with patch("time.time", return_value=50.0):
            app.process(1.0, {})
            cmds = app.get_pending_commands()
            assert len(cmds) == 2
            assert all(c.command_type == "approach_conflict" for c in cmds)

    def test_process_ignores_final_state(self, app):
        app.clear_ils("SAS901", "01L", 110.3)
        app.get_pending_commands()
        app.release_to_tower("SAS901", current_time=0.0)
        app.clear_ils("SAS902", "01L", 110.3)
        app.handoff_to_tower("SAS902", "ESSA_TWR", 118.5)
        app.get_pending_commands()
        app.get_pending_handoffs()
        app.clear_ils("SAS903", "01L", 110.3)
        app.get_pending_commands()
        with patch("time.time", return_value=50.0):
            app.process(1.0, {})
            cmds = app.get_pending_commands()
            assert len(cmds) == 1
            assert cmds[0].command_type == "approach_conflict"
            assert "SAS903" in cmds[0].target_callsign

    def test_process_different_runways_no_conflict(self, app):
        app.clear_ils("SAS901", "01L", 110.3)
        app.get_pending_commands()
        app.release_to_tower("SAS901", current_time=0.0)
        app.clear_ils("SAS902", "19R", 109.7)
        app.get_pending_commands()
        with patch("time.time", return_value=10.0):
            app.process(1.0, {})
            assert app.get_pending_commands() == []

    def test_process_no_aircraft(self, app):
        app.process(1.0, {})
        assert app.get_pending_commands() == []


# ──────────────────────────────────────────────
# Integration — Full Lifecycle
# ──────────────────────────────────────────────

class TestIntegration:
    def test_arrival_full_lifecycle(self, app):
        app.accept_from_center("SAS901", 12000)
        app.get_pending_commands()
        app.assign_star("SAS901", "KOGOS2A", 12000, "01L")
        app.get_pending_commands()
        app.assign_descent("SAS901", 5000)
        app.get_pending_commands()
        app.vector_to_ils("SAS901", 270, 3000)
        app.get_pending_commands()
        app.clear_ils("SAS901", "01L", 110.3)
        app.get_pending_commands()
        app.handoff_to_tower("SAS901", "ESSA_TWR", 118.5)
        app.get_pending_commands()
        hofs = app.get_pending_handoffs()
        assert len(hofs) == 1
        app.release_to_tower("SAS901")
        assert not app.is_controlling("SAS901")

    def test_star_to_visual_lifecycle(self, app):
        app.assign_star("SAS901", "KOGOS2A", 12000, "01L")
        app.get_pending_commands()
        app.assign_speed("SAS901", 220)
        app.get_pending_commands()
        app.assign_descent("SAS901", 4000)
        app.get_pending_commands()
        app.maintain_altitude("SAS901", 3000)
        app.get_pending_commands()
        app.clear_visual("SAS901", "01L")
        assert app.get_aircraft_approach_state("SAS901") == ApproachState.VISUAL_CLEARED
        app.get_pending_commands()
        app.handoff_to_tower("SAS901", "ESSA_TWR", 118.5)
        app.release_to_tower("SAS901")
        assert app.aircraft_count == 0

    def test_sequenced_arrivals(self, app):
        app.assign_landing_sequence("SAS901", 1, "01L")
        app.get_pending_commands()
        app.assign_landing_sequence("SAS902", 2, "01L")
        app.get_pending_commands()
        assert app.get_landing_sequence("SAS901") == 1
        assert app.get_landing_sequence("SAS902") == 2
        app.clear_ils("SAS901", "01L", 110.3)
        app.handoff_to_tower("SAS901", "ESSA_TWR", 118.5)
        app.release_to_tower("SAS901", current_time=100.0)
        assert app.aircraft_count == 1
        app.clear_ils("SAS902", "01L", 110.3)
        with patch("time.time", return_value=100.0):
            assert app.can_handoff_to_tower("SAS902") is False
        with patch("time.time", return_value=250.0):
            assert app.can_handoff_to_tower("SAS902") is True

    def test_accept_from_center_with_star(self, app):
        app.accept_from_center("SAS901", 12000, star_info={
            "star_name": "KOGOS2A",
            "initial_alt_ft": 12000,
            "approach_runway": "01L",
            "intercept_distance_nm": 12.0,
        })
        star = app.get_star_assignment("SAS901")
        assert star.star_name == "KOGOS2A"
        assert star.intercept_distance_nm == 12.0
        assert app.get_approach_runway("SAS901") == "01L"

    def test_rnav_approach_lifecycle(self, app):
        app.assign_star("SAS901", "KOGOS2A", 12000, "01L")
        app.get_pending_commands()
        app.assign_speed("SAS901", 200)
        app.get_pending_commands()
        app.clear_rnav("SAS901", "01L", "RNP")
        assert app.get_aircraft_approach_state("SAS901") == ApproachState.RNAV_CLEARED
        app.get_pending_commands()
        app.handoff_to_tower("SAS901", "ESSA_TWR", 118.5)
        app.release_to_tower("SAS901")
        assert app.aircraft_count == 0

    def test_separation_enforced(self, app):
        app.clear_ils("SAS901", "01L", 110.3)
        app.release_to_tower("SAS901", current_time=0.0)
        app.clear_ils("SAS902", "01L", 110.3)
        with patch("time.time", return_value=50.0):
            assert app.can_handoff_to_tower("SAS902") is False

    def test_handoff_and_release_clean_state(self, app):
        app.assign_star("SAS901", "KOGOS2A", 12000, "01L")
        app.assign_speed("SAS901", 220)
        app.assign_landing_sequence("SAS901", 1)
        app.get_pending_commands()
        app.handoff_to_tower("SAS901", "ESSA_TWR", 118.5)
        app.get_pending_commands()
        app.release_to_tower("SAS901")
        assert app.aircraft_count == 0
        assert app.get_star_assignment("SAS901") is None
        assert app.get_speed_restriction("SAS901") is None
        assert app.get_landing_sequence("SAS901") is None


# ──────────────────────────────────────────────
# Scenario: STAR to ILS intercept and Tower handoff
# ──────────────────────────────────────────────

class TestScenario:
    def test_star_to_ils_to_tower_scenario(self, app):
        app.accept_from_center("SAS901", 12000)
        cmds = app.get_pending_commands()
        assert cmds[0].command_type == "contact_approach"
        assert app.get_aircraft_approach_state("SAS901") == ApproachState.VECTORING

        app.assign_star("SAS901", "KOGOS2A", 12000, "01L")
        cmds = app.get_pending_commands()
        assert cmds[0].command_type == "assign_star"
        star = app.get_star_assignment("SAS901")
        assert star.star_name == "KOGOS2A"
        assert star.approach_runway == "01L"
        assert app.get_approach_runway("SAS901") == "01L"

        app.assign_descent("SAS901", 5000)
        cmds = app.get_pending_commands()
        assert cmds[0].command_type == "descend"
        assert "5000ft" in cmds[0].data["instruction"]
        assert app.get_star_assignment("SAS901").current_alt_ft == 5000

        app.assign_speed("SAS901", 220)
        cmds = app.get_pending_commands()
        assert cmds[0].command_type == "speed"
        assert app.get_speed_restriction("SAS901") == 220

        app.assign_landing_sequence("SAS901", 1, "01L")
        cmds = app.get_pending_commands()
        assert "1st" in cmds[0].data["instruction"]
        assert app.get_landing_sequence("SAS901") == 1

        app.vector_to_ils("SAS901", 45, 3000)
        cmds = app.get_pending_commands()
        assert cmds[0].command_type == "vector"
        assert "045" in cmds[0].data["instruction"]

        app.clear_ils("SAS901", "01L", 110.3)
        cmds = app.get_pending_commands()
        assert cmds[0].command_type == "clear_ils"
        assert app.get_aircraft_approach_state("SAS901") == ApproachState.ILS_CLEARED
        clearance = app.get_clearance_state("SAS901")
        assert clearance.clearance_type == "ils_approach"
        assert clearance.details["runway"] == "01L"

        app.handoff_to_tower("SAS901", "ESSA_TWR", 118.5)
        cmds = app.get_pending_commands()
        assert cmds[0].command_type == "contact_tower"
        assert app.get_aircraft_approach_state("SAS901") == ApproachState.FINAL
        hofs = app.get_pending_handoffs()
        assert len(hofs) == 1
        assert hofs[0].to_controller == "ESSA_TWR"

        app.release_to_tower("SAS901")
        assert not app.is_controlling("SAS901")
        assert app.aircraft_count == 0


# ──────────────────────────────────────────────
# Model Dataclass — STARAssignment
# ──────────────────────────────────────────────

class TestSTARAssignmentDataclass:
    def test_create_with_all_fields(self):
        star = STARAssignment(
            star_name="KOGOS2A",
            initial_alt_ft=12000,
            approach_runway="01L",
            current_alt_ft=12000,
            speed_restriction=220,
            intercept_distance_nm=12.0,
            vector_heading=270.0,
        )
        assert star.star_name == "KOGOS2A"
        assert star.initial_alt_ft == 12000
        assert star.approach_runway == "01L"
        assert star.current_alt_ft == 12000
        assert star.speed_restriction == 220
        assert star.intercept_distance_nm == 12.0
        assert star.vector_heading == 270.0

    def test_create_minimal(self):
        star = STARAssignment(star_name="KOGOS2A", initial_alt_ft=12000)
        assert star.star_name == "KOGOS2A"
        assert star.approach_runway == ""
        assert star.current_alt_ft == 0
        assert star.speed_restriction is None
        assert star.intercept_distance_nm == 10.0
        assert star.vector_heading is None


# ──────────────────────────────────────────────
# ApproachState Enum
# ──────────────────────────────────────────────

class TestApproachState:
    def test_new_values(self):
        assert ApproachState.DESCENT_CLEARED.value == "descent_cleared"
        assert ApproachState.RNAV_CLEARED.value == "rnav_cleared"
        assert ApproachState.VISUAL_CLEARED.value == "visual_cleared"
        assert ApproachState.APPROACH_SEQUENCE.value == "approach_sequence"

    def test_existing_values_preserved(self):
        assert ApproachState.IDLE.value == "idle"
        assert ApproachState.VECTORING.value == "vectoring"
        assert ApproachState.HOLDING.value == "holding"
        assert ApproachState.ILS_CLEARED.value == "ils_cleared"
        assert ApproachState.FINAL.value == "final"
        assert ApproachState.GO_AROUND.value == "go_around"

    def test_all_members(self):
        assert len(ApproachState) == 10


# ──────────────────────────────────────────────
# Backward Compatibility — Existing tests still pass
# ──────────────────────────────────────────────

class TestBackwardCompatibility:
    def test_initial_state(self, app):
        assert app.callsign == "ESSA_APP"
        assert app.frequency == 119.7
        assert app.sector_id == "ESSA_APP"

    def test_accept_from_center_basic(self, app):
        app.accept_from_center("SAS901", 12000)
        assert app.is_controlling("SAS901")
        assert app.get_aircraft_approach_state("SAS901") == ApproachState.VECTORING

    def test_vector_to_ils_basic(self, app):
        app.vector_to_ils("SAS901", 270, 3000)
        assert app.is_controlling("SAS901")
        assert app.get_aircraft_approach_state("SAS901") == ApproachState.VECTORING

    def test_assign_hold_basic(self, app):
        app.assign_hold("SAS901", "KOGOS", 8000)
        assert app.get_aircraft_approach_state("SAS901") == ApproachState.HOLDING
        assert app.is_controlling("SAS901")

    def test_clear_ils_basic(self, app):
        app.accept_aircraft("SAS901")
        app.clear_ils("SAS901", "01L", 110.3)
        assert app.get_aircraft_approach_state("SAS901") == ApproachState.ILS_CLEARED
        cmds = app.get_pending_commands()
        assert cmds[0].command_type == "clear_ils"

    def test_handoff_to_tower_basic(self, app):
        app.accept_aircraft("SAS901")
        app.handoff_to_tower("SAS901", "ESSA_TWR", 118.5)
        assert app.get_aircraft_approach_state("SAS901") == ApproachState.FINAL

    def test_release_to_tower_basic(self, app):
        app.accept_aircraft("SAS901")
        app.release_to_tower("SAS901")
        assert not app.is_controlling("SAS901")

    def test_go_around_basic(self, app):
        app.go_around("SAS901", "traffic")
        assert app.get_aircraft_approach_state("SAS901") == ApproachState.GO_AROUND

    def test_accept_aircraft_idempotent(self, app):
        app.accept_aircraft("AC1")
        app.accept_aircraft("AC1")
        assert app.aircraft_count == 1

    def test_get_aircraft_approach_state_unknown(self, app):
        assert app.get_aircraft_approach_state("NONEXIST") is None

    def test_process_noop_with_aircraft(self, app):
        app.accept_aircraft("SAS901")
        app.process(0.1, {})
        assert app.aircraft_count == 1

    def test_process_noop_empty(self, app):
        app.process(0.1, {})
        assert True
