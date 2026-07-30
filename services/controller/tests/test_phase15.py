import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import time
from unittest.mock import patch

import pytest

from base import BaseController
from departure import DepartureController
from models import (
    ControllerState,
    DepartureState,
    SIDAssignment,
    ClearanceState,
)


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────

@pytest.fixture
def dep():
    return DepartureController("ESSA_DEP", 119.4, "ESSA_DEP", "ESSA")


# ──────────────────────────────────────────────
# SID Assignment
# ──────────────────────────────────────────────

class TestSIDAssignment:
    def test_assign_sid_creates_assignment(self, dep):
        dep.assign_sid("SAS901", "NILUG2N", 6000, "NILUG")
        sid = dep.get_sid_assignment("SAS901")
        assert sid is not None
        assert sid.sid_name == "NILUG2N"
        assert sid.initial_alt_ft == 6000
        assert sid.departure_fix == "NILUG"

    def test_assign_sid_sets_state(self, dep):
        dep.assign_sid("SAS901", "NILUG2N", 6000)
        assert dep.get_aircraft_departure_state("SAS901") == DepartureState.ENROUTE

    def test_assign_sid_issues_command(self, dep):
        dep.assign_sid("SAS901", "NILUG2N", 6000)
        cmds = dep.get_pending_commands()
        assert len(cmds) == 1
        assert cmds[0].command_type == "climb_via_sid"
        assert "NILUG2N" in cmds[0].data["instruction"]
        assert "6000ft" in cmds[0].data["instruction"]

    def test_assign_sid_with_fix(self, dep):
        dep.assign_sid("SAS901", "NILUG2N", 6000, "NILUG")
        cmds = dep.get_pending_commands()
        assert "NILUG" in cmds[0].data["instruction"]

    def test_assign_sid_with_handoff_alt(self, dep):
        dep.assign_sid("SAS901", "NILUG2N", 6000, "NILUG", handoff_alt_ft=12000)
        sid = dep.get_sid_assignment("SAS901")
        assert sid.handoff_alt_ft == 12000
        cmds = dep.get_pending_commands()
        assert "12000ft" in cmds[0].data["instruction"]

    def test_assign_sid_auto_accepts(self, dep):
        assert not dep.is_controlling("SAS901")
        dep.assign_sid("SAS901", "NILUG2N", 6000)
        assert dep.is_controlling("SAS901")

    def test_assign_sid_creates_clearance(self, dep):
        dep.assign_sid("SAS901", "NILUG2N", 6000)
        clearance = dep.get_clearance_state("SAS901")
        assert clearance is not None
        assert clearance.clearance_type == "climb_via_sid"
        assert clearance.details["sid"] == "NILUG2N"

    def test_assign_sid_logs_history(self, dep):
        dep.assign_sid("SAS901", "NILUG2N", 6000)
        history = dep.get_aircraft_history("SAS901")
        assert len(history) == 1
        assert history[0].command_type == "climb_via_sid"
        assert history[0].new_state == DepartureState.ENROUTE.value

    def test_assign_sid_no_fix(self, dep):
        dep.assign_sid("SAS901", "NILUG2N", 6000)
        sid = dep.get_sid_assignment("SAS901")
        assert sid.departure_fix == ""

    def test_get_sid_assignment_unknown(self, dep):
        assert dep.get_sid_assignment("NONEXIST") is None


# ──────────────────────────────────────────────
# Accept From Tower
# ──────────────────────────────────────────────

class TestAcceptFromTower:
    def test_accept_from_tower_sets_state(self, dep):
        dep.accept_from_tower("SAS901")
        assert dep.is_controlling("SAS901")
        assert dep.get_aircraft_departure_state("SAS901") == DepartureState.INITIAL_CLIMB

    def test_accept_from_tower_issues_contact(self, dep):
        dep.accept_from_tower("SAS901")
        cmds = dep.get_pending_commands()
        assert cmds[0].command_type == "contact_departure"
        assert "119.4" in cmds[0].data["instruction"]

    def test_accept_from_tower_with_sid_info(self, dep):
        dep.accept_from_tower("SAS901", sid_info={
            "sid_name": "NILUG2N",
            "initial_alt_ft": 6000,
            "departure_fix": "NILUG",
        })
        sid = dep.get_sid_assignment("SAS901")
        assert sid is not None
        assert sid.sid_name == "NILUG2N"
        assert sid.departure_fix == "NILUG"

    def test_accept_from_tower_with_sid_creates_clearance(self, dep):
        dep.accept_from_tower("SAS901", sid_info={
            "sid_name": "NILUG2N",
            "initial_alt_ft": 6000,
        })
        clearance = dep.get_clearance_state("SAS901")
        assert clearance is not None
        assert clearance.clearance_type == "sid"

    def test_accept_from_tower_no_sid_info(self, dep):
        dep.accept_from_tower("SAS901")
        assert dep.get_sid_assignment("SAS901") is None

    def test_accept_from_tower_logs_history(self, dep):
        dep.accept_from_tower("SAS901")
        history = dep.get_aircraft_history("SAS901")
        assert len(history) == 1
        assert history[0].command_type == "contact_departure"


# ──────────────────────────────────────────────
# Heading Assignment (Radar Vectors)
# ──────────────────────────────────────────────

class TestHeading:
    def test_assign_heading_sets_state(self, dep):
        dep.accept_aircraft("SAS901")
        dep.assign_heading("SAS901", 270)
        assert dep.get_aircraft_departure_state("SAS901") == DepartureState.HEADING_ASSIGNED

    def test_assign_heading_stores_heading(self, dep):
        dep.accept_aircraft("SAS901")
        dep.assign_heading("SAS901", 270)
        assert dep.get_heading_assignment("SAS901") == 270

    def test_assign_heading_issues_command(self, dep):
        dep.accept_aircraft("SAS901")
        dep.assign_heading("SAS901", 270)
        cmds = dep.get_pending_commands()
        assert cmds[0].command_type == "vector"
        assert "270" in cmds[0].data["instruction"]

    def test_assign_heading_with_reason(self, dep):
        dep.accept_aircraft("SAS901")
        dep.assign_heading("SAS901", 270, "spacing")
        cmds = dep.get_pending_commands()
        assert "spacing" in cmds[0].data["instruction"]

    def test_assign_heading_updates_sid(self, dep):
        dep.assign_sid("SAS901", "NILUG2N", 6000, "NILUG")
        dep.get_pending_commands()
        dep.assign_heading("SAS901", 270)
        sid = dep.get_sid_assignment("SAS901")
        assert sid.is_vectored is True
        assert sid.vector_heading == 270

    def test_assign_heading_non_controlling(self, dep):
        dep.assign_heading("NONEXIST", 270)
        assert dep.get_pending_commands() == []

    def test_assign_heading_logs_history(self, dep):
        dep.accept_aircraft("SAS901")
        dep.assign_heading("SAS901", 270)
        history = dep.get_aircraft_history("SAS901")
        assert len(history) == 1
        assert history[0].command_type == "vector"

    def test_get_heading_assignment_unknown(self, dep):
        assert dep.get_heading_assignment("NONEXIST") is None


# ──────────────────────────────────────────────
# Speed Restrictions
# ──────────────────────────────────────────────

class TestSpeed:
    def test_assign_speed_stores_restriction(self, dep):
        dep.accept_aircraft("SAS901")
        dep.assign_speed("SAS901", 250)
        assert dep.get_speed_restriction("SAS901") == 250

    def test_assign_speed_issues_command(self, dep):
        dep.accept_aircraft("SAS901")
        dep.assign_speed("SAS901", 250)
        cmds = dep.get_pending_commands()
        assert cmds[0].command_type == "speed"
        assert "250" in cmds[0].data["instruction"]

    def test_assign_speed_maximum_default(self, dep):
        dep.accept_aircraft("SAS901")
        dep.assign_speed("SAS901", 250)
        cmds = dep.get_pending_commands()
        assert "Reduce to" in cmds[0].data["instruction"]

    def test_assign_speed_custom_type(self, dep):
        dep.accept_aircraft("SAS901")
        dep.assign_speed("SAS901", 210, "minimum")
        cmds = dep.get_pending_commands()
        assert "Minimum speed" in cmds[0].data["instruction"]

    def test_assign_speed_updates_sid(self, dep):
        dep.assign_sid("SAS901", "NILUG2N", 6000)
        dep.get_pending_commands()
        dep.assign_speed("SAS901", 250)
        sid = dep.get_sid_assignment("SAS901")
        assert sid.speed_restriction == 250

    def test_assign_speed_non_controlling(self, dep):
        dep.assign_speed("NONEXIST", 250)
        assert dep.get_pending_commands() == []

    def test_get_speed_restriction_unknown(self, dep):
        assert dep.get_speed_restriction("NONEXIST") is None

    def test_assign_speed_logs_history(self, dep):
        dep.accept_aircraft("SAS901")
        dep.assign_speed("SAS901", 250)
        history = dep.get_aircraft_history("SAS901")
        assert len(history) >= 1
        assert history[0].command_type == "speed"


# ──────────────────────────────────────────────
# Altitude Management
# ──────────────────────────────────────────────

class TestAltitude:
    def test_maintain_altitude_sets_state(self, dep):
        dep.accept_aircraft("SAS901")
        dep.maintain_altitude("SAS901", 6000)
        assert dep.get_aircraft_departure_state("SAS901") == DepartureState.CLIMB_CLEARED

    def test_maintain_altitude_issues_command(self, dep):
        dep.accept_aircraft("SAS901")
        dep.maintain_altitude("SAS901", 6000)
        cmds = dep.get_pending_commands()
        assert cmds[0].command_type == "maintain"
        assert "6000ft" in cmds[0].data["instruction"]

    def test_maintain_altitude_updates_sid(self, dep):
        dep.assign_sid("SAS901", "NILUG2N", 6000)
        dep.get_pending_commands()
        dep.maintain_altitude("SAS901", 8000)
        sid = dep.get_sid_assignment("SAS901")
        assert sid.current_alt_ft == 8000

    def test_maintain_altitude_auto_accepts(self, dep):
        dep.maintain_altitude("SAS901", 5000)
        assert dep.is_controlling("SAS901")

    def test_maintain_altitude_creates_clearance(self, dep):
        dep.accept_aircraft("SAS901")
        dep.maintain_altitude("SAS901", 6000)
        clearance = dep.get_clearance_state("SAS901")
        assert clearance is not None
        assert clearance.clearance_type == "maintain"

    def test_assign_climb_sets_state(self, dep):
        dep.accept_aircraft("SAS901")
        dep.assign_climb("SAS901", 10000)
        assert dep.get_aircraft_departure_state("SAS901") == DepartureState.CLIMB_CLEARED

    def test_assign_climb_issues_command(self, dep):
        dep.accept_aircraft("SAS901")
        dep.assign_climb("SAS901", 10000)
        cmds = dep.get_pending_commands()
        assert cmds[0].command_type == "climb"
        assert "10000ft" in cmds[0].data["instruction"]

    def test_assign_climb_updates_sid(self, dep):
        dep.assign_sid("SAS901", "NILUG2N", 6000)
        dep.get_pending_commands()
        dep.assign_climb("SAS901", 15000)
        sid = dep.get_sid_assignment("SAS901")
        assert sid.current_alt_ft == 15000

    def test_assign_climb_auto_accepts(self, dep):
        dep.assign_climb("SAS901", 15000)
        assert dep.is_controlling("SAS901")

    def test_assign_climb_creates_clearance(self, dep):
        dep.accept_aircraft("SAS901")
        dep.assign_climb("SAS901", 15000)
        clearance = dep.get_clearance_state("SAS901")
        assert clearance is not None
        assert clearance.clearance_type == "climb"

    def test_maintain_altitude_logs_history(self, dep):
        dep.accept_aircraft("SAS901")
        dep.maintain_altitude("SAS901", 6000)
        history = dep.get_aircraft_history("SAS901")
        assert len(history) == 1
        assert history[0].command_type == "maintain"

    def test_assign_climb_logs_history(self, dep):
        dep.accept_aircraft("SAS901")
        dep.assign_climb("SAS901", 15000)
        history = dep.get_aircraft_history("SAS901")
        assert len(history) == 1
        assert history[0].command_type == "climb"


# ──────────────────────────────────────────────
# Separation Logic
# ──────────────────────────────────────────────

class TestSeparation:
    def test_can_release_no_sid(self, dep):
        assert dep.can_release_to_center("NONEXIST") is False

    def test_can_release_no_fix(self, dep):
        dep.assign_sid("SAS901", "NILUG2N", 6000)
        assert dep.can_release_to_center("SAS901") is True

    def test_can_release_first_aircraft(self, dep):
        dep.assign_sid("SAS901", "NILUG2N", 6000, "NILUG")
        assert dep.can_release_to_center("SAS901") is True

    def test_can_release_after_separation_met(self, dep):
        dep.assign_sid("SAS901", "NILUG2N", 6000, "NILUG")
        dep.release_to_center("SAS901", current_time=0.0)
        dep.assign_sid("SAS902", "NILUG2N", 6000, "NILUG")
        with patch("time.time", return_value=200.0):
            assert dep.can_release_to_center("SAS902") is True

    def test_can_release_separation_not_met(self, dep):
        dep.assign_sid("SAS901", "NILUG2N", 6000, "NILUG")
        dep.release_to_center("SAS901", current_time=0.0)
        dep.assign_sid("SAS902", "NILUG2N", 6000, "NILUG")
        with patch("time.time", return_value=50.0):
            assert dep.can_release_to_center("SAS902") is False

    def test_can_release_different_fix_no_separation(self, dep):
        dep.assign_sid("SAS901", "NILUG2N", 6000, "NILUG")
        dep.release_to_center("SAS901", current_time=0.0)
        dep.assign_sid("SAS902", "PEPAX1N", 6000, "PEPAX")
        with patch("time.time", return_value=10.0):
            assert dep.can_release_to_center("SAS902") is True

    def test_can_release_custom_fix(self, dep):
        dep.assign_sid("SAS901", "NILUG2N", 6000, "NILUG")
        dep.release_to_center("SAS901", fix_name="NILUG", current_time=0.0)
        dep.assign_sid("SAS902", "NILUG2N", 6000, "NILUG")
        with patch("time.time", return_value=50.0):
            assert dep.can_release_to_center("SAS902", fix_name="NILUG") is False

    def test_custom_separation_time(self, dep):
        dep = DepartureController("ESSA_DEP", 119.4, "ESSA_DEP", "ESSA", departure_separation_s=300)
        dep.assign_sid("SAS901", "NILUG2N", 6000, "NILUG")
        dep.release_to_center("SAS901", current_time=0.0)
        dep.assign_sid("SAS902", "NILUG2N", 6000, "NILUG")
        with patch("time.time", return_value=200.0):
            assert dep.can_release_to_center("SAS902") is False
        with patch("time.time", return_value=350.0):
            assert dep.can_release_to_center("SAS902") is True


# ──────────────────────────────────────────────
# Handoff to Center
# ──────────────────────────────────────────────

class TestHandoff:
    def test_handoff_to_center_sets_state(self, dep):
        dep.accept_aircraft("SAS901")
        dep.handoff_to_center("SAS901", "ESSA_CTR", 124.2)
        assert dep.get_aircraft_departure_state("SAS901") == DepartureState.HANDOFF

    def test_handoff_to_center_issues_command(self, dep):
        dep.accept_aircraft("SAS901")
        dep.handoff_to_center("SAS901", "ESSA_CTR", 124.2)
        cmds = dep.get_pending_commands()
        assert cmds[0].command_type == "contact_center"
        assert "ESSA_CTR" in cmds[0].data["instruction"]

    def test_handoff_to_center_proposes_handoff(self, dep):
        dep.accept_aircraft("SAS901")
        dep.handoff_to_center("SAS901", "ESSA_CTR", 124.2)
        hofs = dep.get_pending_handoffs()
        assert len(hofs) == 1
        assert hofs[0].to_controller == "ESSA_CTR"
        assert hofs[0].frequency == 124.2

    def test_handoff_to_center_not_controlling(self, dep):
        dep.handoff_to_center("NONEXIST", "ESSA_CTR", 124.2)
        assert dep.get_pending_commands() == []
        assert dep.get_pending_handoffs() == []

    def test_handoff_logs_history(self, dep):
        dep.accept_aircraft("SAS901")
        dep.handoff_to_center("SAS901", "ESSA_CTR", 124.2)
        history = dep.get_aircraft_history("SAS901")
        assert len(history) == 1
        assert history[0].command_type == "contact_center"


# ──────────────────────────────────────────────
# Release to Center
# ──────────────────────────────────────────────

class TestReleaseToCenter:
    def test_release_to_center_removes_aircraft(self, dep):
        dep.accept_aircraft("SAS901")
        dep.release_to_center("SAS901")
        assert not dep.is_controlling("SAS901")

    def test_release_to_center_removes_state(self, dep):
        dep.assign_sid("SAS901", "NILUG2N", 6000)
        dep.release_to_center("SAS901")
        assert dep.get_aircraft_departure_state("SAS901") is None

    def test_release_to_center_removes_sid(self, dep):
        dep.assign_sid("SAS901", "NILUG2N", 6000)
        dep.release_to_center("SAS901")
        assert dep.get_sid_assignment("SAS901") is None

    def test_release_to_center_clears_heading(self, dep):
        dep.accept_aircraft("SAS901")
        dep.assign_heading("SAS901", 270)
        dep.release_to_center("SAS901")
        assert dep.get_heading_assignment("SAS901") is None

    def test_release_to_center_clears_speed(self, dep):
        dep.accept_aircraft("SAS901")
        dep.assign_speed("SAS901", 250)
        dep.release_to_center("SAS901")
        assert dep.get_speed_restriction("SAS901") is None

    def test_release_to_center_revokes_clearance(self, dep):
        dep.assign_sid("SAS901", "NILUG2N", 6000)
        dep.get_pending_commands()
        dep.release_to_center("SAS901")
        clearance = dep.get_clearance_state("SAS901")
        assert clearance is None or not clearance.is_active

    def test_release_to_center_tracks_fix_time(self, dep):
        dep.assign_sid("SAS901", "NILUG2N", 6000, "NILUG")
        dep.release_to_center("SAS901", current_time=500.0)
        assert dep._last_fix_departure.get("NILUG") == 500.0

    def test_release_to_center_not_controlling(self, dep):
        dep.release_to_center("NONEXIST")
        assert dep.get_pending_commands() == []

    def test_release_to_center_no_fix_no_error(self, dep):
        dep.accept_aircraft("SAS901")
        dep.release_to_center("SAS901")
        assert not dep.is_controlling("SAS901")


# ──────────────────────────────────────────────
# Process Method — Automated Conflict Detection
# ──────────────────────────────────────────────

class TestProcess:
    def test_process_no_conflict_does_nothing(self, dep):
        dep.assign_sid("SAS901", "NILUG2N", 6000, "NILUG")
        dep.get_pending_commands()
        dep.process(1.0, {})
        assert dep.get_pending_commands() == []

    def test_process_detects_same_fix_conflict(self, dep):
        dep.assign_sid("SAS901", "NILUG2N", 6000, "NILUG")
        dep.get_pending_commands()
        dep.release_to_center("SAS901", current_time=0.0)
        dep.assign_sid("SAS902", "NILUG2N", 6000, "NILUG")
        dep.get_pending_commands()
        dep.assign_sid("SAS903", "NILUG2N", 6000, "NILUG")
        dep.get_pending_commands()
        with patch("time.time", return_value=50.0):
            dep.process(1.0, {})
            cmds = dep.get_pending_commands()
            assert len(cmds) == 2
            assert all(c.command_type == "conflict_alert" for c in cmds)
            assert all("NILUG" in c.data["instruction"] for c in cmds)

    def test_process_no_conflict_after_separation(self, dep):
        dep.assign_sid("SAS901", "NILUG2N", 6000, "NILUG")
        dep.get_pending_commands()
        dep.release_to_center("SAS901", current_time=0.0)
        dep.assign_sid("SAS902", "NILUG2N", 6000, "NILUG")
        dep.get_pending_commands()
        with patch("time.time", return_value=200.0):
            dep.process(1.0, {})
            assert dep.get_pending_commands() == []

    def test_process_ignores_handoff_state(self, dep):
        dep.assign_sid("SAS901", "NILUG2N", 6000, "NILUG")
        dep.release_to_center("SAS901", current_time=0.0)
        dep.assign_sid("SAS902", "NILUG2N", 6000, "NILUG")
        dep.handoff_to_center("SAS902", "ESSA_CTR", 124.2)
        dep.get_pending_commands()
        dep.get_pending_handoffs()
        with patch("time.time", return_value=50.0):
            dep.process(1.0, {})
            assert dep.get_pending_commands() == []

    def test_process_different_fixes_no_conflict(self, dep):
        dep.assign_sid("SAS901", "NILUG2N", 6000, "NILUG")
        dep.get_pending_commands()
        dep.release_to_center("SAS901", current_time=0.0)
        dep.assign_sid("SAS902", "PEPAX1N", 6000, "PEPAX")
        dep.get_pending_commands()
        with patch("time.time", return_value=10.0):
            dep.process(1.0, {})
            assert dep.get_pending_commands() == []

    def test_process_multiple_aircraft_one_conflict(self, dep):
        dep.assign_sid("SAS901", "NILUG2N", 6000, "NILUG")
        dep.get_pending_commands()
        dep.release_to_center("SAS901", current_time=0.0)
        dep.assign_sid("SAS902", "PEPAX1N", 6000, "PEPAX")
        dep.get_pending_commands()
        dep.assign_sid("SAS903", "NILUG2N", 6000, "NILUG")
        dep.get_pending_commands()
        dep.assign_sid("SAS904", "PEPAX1N", 6000, "PEPAX")
        dep.get_pending_commands()
        dep.release_to_center("SAS903", current_time=0.0)
        with patch("time.time", return_value=50.0):
            dep.process(1.0, {})
            cmds = dep.get_pending_commands()
            assert len(cmds) == 2  # SAS904 and SAS902 both get alerts (released aircraft don't)

    def test_process_no_aircraft(self, dep):
        dep.process(1.0, {})
        assert dep.get_pending_commands() == []


# ──────────────────────────────────────────────
# Integration — Full Lifecycle
# ──────────────────────────────────────────────

class TestIntegration:
    def test_departure_full_lifecycle(self, dep):
        dep.accept_from_tower("SAS901")
        dep.get_pending_commands()
        dep.assign_sid("SAS901", "NILUG2N", 6000, "NILUG")
        dep.get_pending_commands()
        dep.assign_climb("SAS901", 12000)
        dep.get_pending_commands()
        dep.handoff_to_center("SAS901", "ESSA_CTR", 124.2)
        dep.get_pending_commands()
        hofs = dep.get_pending_handoffs()
        assert len(hofs) == 1
        dep.release_to_center("SAS901")
        assert not dep.is_controlling("SAS901")

    def test_vectored_departure_lifecycle(self, dep):
        dep.assign_sid("SAS901", "NILUG2N", 6000, "NILUG")
        dep.get_pending_commands()
        dep.assign_heading("SAS901", 270, "spacing")
        assert dep.get_heading_assignment("SAS901") == 270
        dep.get_pending_commands()
        dep.assign_speed("SAS901", 210)
        assert dep.get_speed_restriction("SAS901") == 210
        dep.get_pending_commands()
        dep.maintain_altitude("SAS901", 6000)
        dep.get_pending_commands()
        dep.handoff_to_center("SAS901", "ESSA_CTR", 124.2)
        dep.release_to_center("SAS901")
        assert not dep.is_controlling("SAS901")

    def test_accept_from_tower_then_assign_sid(self, dep):
        dep.accept_from_tower("SAS901", sid_info={
            "sid_name": "NILUG2N",
            "initial_alt_ft": 6000,
        })
        dep.get_pending_commands()
        dep.assign_climb("SAS901", 10000)
        assert dep.get_aircraft_departure_state("SAS901") == DepartureState.CLIMB_CLEARED

    def test_handoff_and_release_clean_state(self, dep):
        dep.assign_sid("SAS901", "NILUG2N", 6000, "NILUG")
        dep.assign_heading("SAS901", 270)
        dep.assign_speed("SAS901", 250)
        dep.get_pending_commands()
        dep.handoff_to_center("SAS901", "ESSA_CTR", 124.2)
        dep.get_pending_commands()
        dep.release_to_center("SAS901")
        assert dep.aircraft_count == 0
        assert dep.get_heading_assignment("SAS901") is None
        assert dep.get_speed_restriction("SAS901") is None
        assert dep.get_sid_assignment("SAS901") is None

    def test_separation_enforced_in_lifecycle(self, dep):
        dep.assign_sid("SAS901", "NILUG2N", 6000, "NILUG")
        dep.release_to_center("SAS901", current_time=0.0)
        dep.assign_sid("SAS902", "NILUG2N", 6000, "NILUG")
        with patch("time.time", return_value=50.0):
            assert dep.can_release_to_center("SAS902") is False

    def test_consecutive_releases_same_fix(self, dep):
        dep.assign_sid("SAS901", "NILUG2N", 6000, "NILUG")
        dep.release_to_center("SAS901", current_time=0.0)
        dep.assign_sid("SAS902", "NILUG2N", 6000, "NILUG")
        dep.release_to_center("SAS902", current_time=200.0)
        dep.assign_sid("SAS903", "NILUG2N", 6000, "NILUG")
        with patch("time.time", return_value=350.0):
            assert dep.can_release_to_center("SAS903") is True


# ──────────────────────────────────────────────
# Radar Contact
# ──────────────────────────────────────────────

class TestRadarContact:
    def test_radar_contact_sets_state(self, dep):
        dep.radar_contact("SAS901", 3000)
        assert dep.is_controlling("SAS901")
        assert dep.get_aircraft_departure_state("SAS901") == DepartureState.RADAR_CONTACT

    def test_radar_contact_issues_command(self, dep):
        dep.radar_contact("SAS901", 3000)
        cmds = dep.get_pending_commands()
        assert cmds[0].command_type == "radar_contact"
        assert "Radar contact" in cmds[0].data["instruction"]

    def test_radar_contact_includes_altitude(self, dep):
        dep.radar_contact("SAS901", 3000)
        cmds = dep.get_pending_commands()
        assert "3000ft" in cmds[0].data["instruction"]

    def test_radar_contact_no_altitude(self, dep):
        dep.radar_contact("SAS901")
        cmds = dep.get_pending_commands()
        assert "ft" not in cmds[0].data["instruction"]

    def test_radar_contact_with_sid(self, dep):
        dep.radar_contact("SAS901", 3000, sid_name="NILUG2N")
        cmds = dep.get_pending_commands()
        assert "NILUG2N" in cmds[0].data["instruction"]

    def test_radar_contact_auto_accepts(self, dep):
        assert not dep.is_controlling("SAS901")
        dep.radar_contact("SAS901")
        assert dep.is_controlling("SAS901")

    def test_radar_contact_logs_history(self, dep):
        dep.radar_contact("SAS901")
        history = dep.get_aircraft_history("SAS901")
        assert len(history) == 1
        assert history[0].command_type == "radar_contact"

    def test_radar_contact_after_accept_from_tower(self, dep):
        dep.accept_from_tower("SAS901")
        dep.get_pending_commands()
        dep.radar_contact("SAS901", 2500, "NILUG2N")
        assert dep.get_aircraft_departure_state("SAS901") == DepartureState.RADAR_CONTACT
        cmds = dep.get_pending_commands()
        assert cmds[0].command_type == "radar_contact"


# ──────────────────────────────────────────────
# Altitude Verification
# ──────────────────────────────────────────────

class TestVerifyAltitude:
    def test_verify_altitude_correct(self, dep):
        dep.assign_sid("SAS901", "NILUG2N", 6000)
        dep.get_pending_commands()
        assert dep.verify_altitude("SAS901", 6000) is True
        assert dep.get_pending_commands() == []

    def test_verify_altitude_below_sid(self, dep):
        dep.assign_sid("SAS901", "NILUG2N", 6000)
        dep.get_pending_commands()
        result = dep.verify_altitude("SAS901", 4000)
        assert result is False
        cmds = dep.get_pending_commands()
        assert cmds[0].command_type == "altitude_correction"
        assert "Climb to 6000ft" in cmds[0].data["instruction"]

    def test_verify_altitude_above_sid(self, dep):
        dep.assign_sid("SAS901", "NILUG2N", 6000)
        dep.get_pending_commands()
        dep.assign_climb("SAS901", 10000)
        dep.get_pending_commands()
        result = dep.verify_altitude("SAS901", 12000)
        assert result is False
        cmds = dep.get_pending_commands()
        assert "Maintain 10000ft" in cmds[0].data["instruction"]

    def test_verify_altitude_no_sid(self, dep):
        dep.accept_aircraft("SAS901")
        assert dep.verify_altitude("SAS901", 5000) is True
        assert dep.get_pending_commands() == []

    def test_verify_altitude_not_controlling(self, dep):
        assert dep.verify_altitude("NONEXIST", 5000) is True

    def test_verify_altitude_after_climb_adjustment(self, dep):
        dep.assign_sid("SAS901", "NILUG2N", 6000)
        dep.get_pending_commands()
        dep.assign_climb("SAS901", 15000)
        dep.get_pending_commands()
        assert dep.verify_altitude("SAS901", 15000) is True

    def test_verify_altitude_reports_current_alt_in_correction(self, dep):
        dep.assign_sid("SAS901", "NILUG2N", 6000)
        dep.get_pending_commands()
        dep.verify_altitude("SAS901", 2000)
        cmds = dep.get_pending_commands()
        assert "2000ft" in cmds[0].data["instruction"]
        assert "6000ft" in cmds[0].data["instruction"]

    def test_verify_altitude_does_not_change_clearance(self, dep):
        dep.assign_sid("SAS901", "NILUG2N", 6000)
        dep.get_pending_commands()
        clearance_before = dep.get_clearance_state("SAS901")
        assert clearance_before is not None
        assert clearance_before.clearance_type == "climb_via_sid"
        dep.verify_altitude("SAS901", 4000)
        clearance_after = dep.get_clearance_state("SAS901")
        assert clearance_after is clearance_before
        assert clearance_after.is_active is True


# ──────────────────────────────────────────────
# Scenario: Takeoff -> Departure -> Handoff to Center
# ──────────────────────────────────────────────

class TestScenario:
    def test_takeoff_to_center_scenario(self, dep):
        dep.accept_from_tower("SAS901")
        cmds = dep.get_pending_commands()
        assert cmds[0].command_type == "contact_departure"
        assert dep.get_aircraft_departure_state("SAS901") == DepartureState.INITIAL_CLIMB

        dep.radar_contact("SAS901", 2000, "NILUG2N")
        cmds = dep.get_pending_commands()
        assert cmds[0].command_type == "radar_contact"
        assert dep.get_aircraft_departure_state("SAS901") == DepartureState.RADAR_CONTACT

        dep.assign_sid("SAS901", "NILUG2N", 6000, "NILUG")
        cmds = dep.get_pending_commands()
        assert cmds[0].command_type == "climb_via_sid"
        assert "6000ft" in cmds[0].data["instruction"]
        assert dep.get_aircraft_departure_state("SAS901") == DepartureState.ENROUTE
        sid = dep.get_sid_assignment("SAS901")
        assert sid.sid_name == "NILUG2N"
        assert sid.departure_fix == "NILUG"

        dep.assign_climb("SAS901", 12000)
        cmds = dep.get_pending_commands()
        assert cmds[0].command_type == "climb"
        assert "12000ft" in cmds[0].data["instruction"]
        assert dep.get_sid_assignment("SAS901").current_alt_ft == 12000

        assert dep.verify_altitude("SAS901", 12000) is True

        dep.handoff_to_center("SAS901", "ESSA_CTR", 124.2)
        cmds = dep.get_pending_commands()
        assert cmds[0].command_type == "contact_center"
        assert dep.get_aircraft_departure_state("SAS901") == DepartureState.HANDOFF
        hofs = dep.get_pending_handoffs()
        assert len(hofs) == 1
        assert hofs[0].to_controller == "ESSA_CTR"

        dep.release_to_center("SAS901")
        assert not dep.is_controlling("SAS901")
        assert dep.get_aircraft_departure_state("SAS901") is None
        assert dep.aircraft_count == 0

    def test_takeoff_altitude_correction_scenario(self, dep):
        dep.accept_from_tower("SAS901")
        dep.get_pending_commands()

        dep.radar_contact("SAS901", 2000, "NILUG2N")
        dep.get_pending_commands()

        dep.assign_sid("SAS901", "NILUG2N", 6000, "NILUG")
        dep.get_pending_commands()

        result = dep.verify_altitude("SAS901", 3500)
        assert result is False
        cmds = dep.get_pending_commands()
        assert cmds[0].command_type == "altitude_correction"
        assert "Climb to 6000ft" in cmds[0].data["instruction"]

        dep.handoff_to_center("SAS901", "ESSA_CTR", 124.2)
        dep.release_to_center("SAS901")
        assert dep.aircraft_count == 0

    def test_radar_contact_then_vector_scenario(self, dep):
        dep.radar_contact("SAS901", 4000)
        dep.get_pending_commands()

        dep.assign_heading("SAS901", 270, "traffic")
        cmds = dep.get_pending_commands()
        assert cmds[0].command_type == "vector"
        assert "270" in cmds[0].data["instruction"]

        dep.assign_speed("SAS901", 250)
        cmds = dep.get_pending_commands()
        assert cmds[0].command_type == "speed"

        dep.maintain_altitude("SAS901", 4000)
        cmds = dep.get_pending_commands()
        assert "4000ft" in cmds[0].data["instruction"]

        dep.handoff_to_center("SAS901", "ESSA_CTR", 124.2)
        dep.release_to_center("SAS901")
        assert dep.aircraft_count == 0


# ──────────────────────────────────────────────
# Model Dataclass — SIDAssignment
# ──────────────────────────────────────────────

class TestSIDAssignmentDataclass:
    def test_create_with_all_fields(self):
        sid = SIDAssignment(
            sid_name="NILUG2N",
            initial_alt_ft=6000,
            departure_fix="NILUG",
            current_alt_ft=6000,
            is_vectored=True,
            vector_heading=270.0,
            speed_restriction=250,
            handoff_alt_ft=12000,
        )
        assert sid.sid_name == "NILUG2N"
        assert sid.initial_alt_ft == 6000
        assert sid.departure_fix == "NILUG"
        assert sid.current_alt_ft == 6000
        assert sid.is_vectored is True
        assert sid.vector_heading == 270.0
        assert sid.speed_restriction == 250
        assert sid.handoff_alt_ft == 12000

    def test_create_minimal(self):
        sid = SIDAssignment(sid_name="NILUG2N", initial_alt_ft=6000)
        assert sid.sid_name == "NILUG2N"
        assert sid.departure_fix == ""
        assert sid.current_alt_ft == 0
        assert sid.is_vectored is False
        assert sid.vector_heading is None
        assert sid.speed_restriction is None
        assert sid.handoff_alt_ft is None


# ──────────────────────────────────────────────
# DepartureState Enum
# ──────────────────────────────────────────────

class TestDepartureState:
    def test_new_values(self):
        assert DepartureState.HEADING_ASSIGNED.value == "heading_assigned"
        assert DepartureState.CLIMB_CLEARED.value == "climb_cleared"

    def test_existing_values_preserved(self):
        assert DepartureState.IDLE.value == "idle"
        assert DepartureState.INITIAL_CLIMB.value == "initial_climb"
        assert DepartureState.ENROUTE.value == "enroute"
        assert DepartureState.HANDOFF.value == "handoff"

    def test_all_members(self):
        assert len(DepartureState) == 7


# ──────────────────────────────────────────────
# Backward Compatibility — Existing tests still pass
# ──────────────────────────────────────────────

class TestBackwardCompatibility:
    def test_initial_state(self, dep):
        assert dep.callsign == "ESSA_DEP"
        assert dep.frequency == 119.4
        assert dep.sector_id == "ESSA_DEP"

    def test_accept_from_tower_basic(self, dep):
        dep.accept_from_tower("SAS901")
        assert dep.is_controlling("SAS901")
        assert dep.get_aircraft_departure_state("SAS901") == DepartureState.INITIAL_CLIMB

    def test_assign_sid_basic(self, dep):
        dep.assign_sid("SAS901", "NILUG2N", 6000)
        assert dep.get_aircraft_departure_state("SAS901") == DepartureState.ENROUTE

    def test_handoff_to_center_basic(self, dep):
        dep.accept_aircraft("SAS901")
        dep.handoff_to_center("SAS901", "ESSA_CTR", 124.2)
        assert dep.get_aircraft_departure_state("SAS901") == DepartureState.HANDOFF
        cmds = dep.get_pending_commands()
        assert cmds[0].command_type == "contact_center"

    def test_release_to_center_basic(self, dep):
        dep.assign_sid("SAS901", "NILUG2N", 6000)
        dep.get_pending_commands()
        dep.release_to_center("SAS901")
        assert not dep.is_controlling("SAS901")
        assert dep.get_aircraft_departure_state("SAS901") is None

    def test_process_noop_with_aircraft(self, dep):
        dep.accept_aircraft("SAS901")
        dep.process(0.1, {})
        assert dep.aircraft_count == 1

    def test_accept_aircraft_idempotent(self, dep):
        dep.accept_aircraft("AC1")
        dep.accept_aircraft("AC1")
        assert dep.aircraft_count == 1

    def test_get_aircraft_departure_state_unknown(self, dep):
        assert dep.get_aircraft_departure_state("NONEXIST") is None

    def test_controlled_aircraft_list(self, dep):
        dep.accept_aircraft("AC1")
        dep.accept_aircraft("AC2")
        assert set(dep.controlled_aircraft) == {"AC1", "AC2"}

    def test_departure_full_lifecycle_backwards(self, dep):
        dep.accept_from_tower("SAS901")
        dep.assign_sid("SAS901", "NILUG2N", 6000)
        dep.handoff_to_center("SAS901", "ESSA_CTR", 124.2)
        dep.release_to_center("SAS901")
        assert dep.aircraft_count == 0

    def test_process_noop_empty(self, dep):
        dep.process(0.1, {})
        assert True
