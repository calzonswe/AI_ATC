import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from unittest.mock import patch

import pytest

from models import PatternConflict, TowerState, VfrCircuitProgress
from tower import TowerController


@pytest.fixture
def twr():
    return TowerController("ESSA_TWR", 118.5, "ESSA_TWR", "ESSA", ["01L", "19R"])


# ──────────────────────────────────────────────
# Pattern Aircraft Tracking
# ──────────────────────────────────────────────

class TestPatternAircraftTracking:
    def test_get_pattern_aircraft_on_leg(self, twr):
        twr.init_vfr_circuit("SAS901", "01L")
        twr.init_vfr_circuit("SAS902", "01L")
        twr.report_downwind("SAS901", "01L")
        twr.get_pending_commands()
        twr.report_downwind("SAS902", "01L")
        twr.get_pending_commands()
        on_leg = twr.get_pattern_aircraft_on_leg("01L", "downwind")
        assert "SAS901" in on_leg
        assert "SAS902" in on_leg

    def test_get_pattern_aircraft_on_leg_empty(self, twr):
        assert twr.get_pattern_aircraft_on_leg("01L", "downwind") == []

    def test_get_pattern_aircraft_on_leg_leg_filter(self, twr):
        twr.init_vfr_circuit("SAS901", "01L")
        twr.init_vfr_circuit("SAS902", "01L")
        twr.report_downwind("SAS901", "01L")
        twr.get_pending_commands()
        twr.report_downwind("SAS902", "01L")
        twr.get_pending_commands()
        assert len(twr.get_pattern_aircraft_on_leg("01L", "base")) == 0
        assert len(twr.get_pattern_aircraft_on_leg("01L", "downwind")) == 2

    def test_get_all_pattern_aircraft(self, twr):
        twr.init_vfr_circuit("SAS901", "01L")
        twr.init_vfr_circuit("SAS902", "19R")
        pattern_01L = twr.get_all_pattern_aircraft("01L")
        pattern_19R = twr.get_all_pattern_aircraft("19R")
        assert "SAS901" in pattern_01L
        assert "SAS902" in pattern_19R
        assert "SAS902" not in pattern_01L

    def test_get_all_pattern_aircraft_empty(self, twr):
        assert twr.get_all_pattern_aircraft("01L") == {}

    def test_tracking_different_runways_independent(self, twr):
        twr.init_vfr_circuit("SAS901", "01L")
        twr.init_vfr_circuit("SAS902", "19R")
        twr.report_downwind("SAS901", "01L")
        twr.get_pending_commands()
        twr.report_base("SAS902", "19R")
        twr.get_pending_commands()
        assert twr.get_pattern_aircraft_on_leg("01L", "downwind") == ["SAS901"]
        assert twr.get_pattern_aircraft_on_leg("19R", "base") == ["SAS902"]

    def test_tracking_after_leg_change(self, twr):
        twr.init_vfr_circuit("SAS901", "01L")
        twr.report_downwind("SAS901", "01L")
        twr.get_pending_commands()
        assert len(twr.get_pattern_aircraft_on_leg("01L", "downwind")) == 1
        twr.report_base("SAS901", "01L")
        twr.get_pending_commands()
        assert len(twr.get_pattern_aircraft_on_leg("01L", "downwind")) == 0
        assert len(twr.get_pattern_aircraft_on_leg("01L", "base")) == 1


# ──────────────────────────────────────────────
# Extended Downwind
# ──────────────────────────────────────────────

class TestExtendedDownwind:
    def test_issue_extend_downwind(self, twr):
        twr.report_downwind("SAS901", "01L")
        twr.get_pending_commands()
        twr.issue_extend_downwind("SAS901", "01L")
        assert "SAS901" in twr._extended_downwind

    def test_issue_extend_downwind_issues_command(self, twr):
        twr.report_downwind("SAS901", "01L")
        twr.get_pending_commands()
        twr.issue_extend_downwind("SAS901", "01L")
        cmds = twr.get_pending_commands()
        assert any("extend downwind" in c.data.get("instruction", "") for c in cmds)

    def test_issue_extend_downwind_not_downwind(self, twr):
        twr.issue_extend_downwind("SAS901", "01L")
        assert "SAS901" not in twr._extended_downwind

    def test_issue_extend_downwind_not_controlling(self, twr):
        twr.init_vfr_circuit("SAS901", "01L")
        twr.issue_extend_downwind("SAS901", "01L")
        assert "SAS901" not in twr._extended_downwind

    def test_cancel_extend_downwind(self, twr):
        twr.report_downwind("SAS901", "01L")
        twr.get_pending_commands()
        twr.issue_extend_downwind("SAS901", "01L")
        twr.get_pending_commands()
        twr.cancel_extend_downwind("SAS901", "01L")
        assert "SAS901" not in twr._extended_downwind

    def test_cancel_extend_downwind_issues_command(self, twr):
        twr.report_downwind("SAS901", "01L")
        twr.get_pending_commands()
        twr.cancel_extend_downwind("SAS901", "01L")
        cmds = twr.get_pending_commands()
        assert any("turn base now" in c.data.get("instruction", "") for c in cmds)

    def test_extend_downwind_multiple_aircraft(self, twr):
        twr.report_downwind("SAS901", "01L")
        twr.get_pending_commands()
        twr.report_downwind("SAS902", "01L")
        twr.get_pending_commands()
        twr.issue_extend_downwind("SAS901", "01L")
        twr.issue_extend_downwind("SAS902", "01L")
        assert "SAS901" in twr._extended_downwind
        assert "SAS902" in twr._extended_downwind


# ──────────────────────────────────────────────
# Aircraft Sequencing
# ──────────────────────────────────────────────

class TestAircraftSequencing:
    def test_sequence_first_aircraft(self, twr):
        twr.init_vfr_circuit("SAS901", "01L")
        seq = twr.sequence_aircraft("SAS901", "01L")
        assert seq == 1
        cmds = twr.get_pending_commands()
        assert any("number 1" in c.data.get("instruction", "") for c in cmds)

    def test_sequence_second_aircraft(self, twr):
        twr.init_vfr_circuit("SAS901", "01L")
        twr.get_pending_commands()
        twr.sequence_aircraft("SAS901", "01L")
        twr.get_pending_commands()
        twr.init_vfr_circuit("SAS902", "01L")
        seq = twr.sequence_aircraft("SAS902", "01L")
        assert seq == 2
        cmds = twr.get_pending_commands()
        instrs = [c.data.get("instruction", "") for c in cmds]
        assert any("number 2" in ins for ins in instrs)
        assert any("follow" in ins for ins in instrs)

    def test_sequence_third_aircraft(self, twr):
        twr.init_vfr_circuit("SAS901", "01L")
        twr.init_vfr_circuit("SAS902", "01L")
        twr.init_vfr_circuit("SAS903", "01L")
        twr.get_pending_commands()
        twr.sequence_aircraft("SAS901", "01L")
        twr.get_pending_commands()
        twr.sequence_aircraft("SAS902", "01L")
        twr.get_pending_commands()
        seq = twr.sequence_aircraft("SAS903", "01L")
        assert seq == 3
        cmds = twr.get_pending_commands()
        instrs = [c.data.get("instruction", "") for c in cmds]
        assert any("number 3" in ins for ins in instrs)
        assert any("follow" in ins for ins in instrs)

    def test_sequence_then_report_downwind(self, twr):
        twr.init_vfr_circuit("SAS901", "01L")
        twr.get_pending_commands()
        twr.sequence_aircraft("SAS901", "01L")
        twr.get_pending_commands()
        twr.report_downwind("SAS901", "01L")
        assert twr.get_aircraft_tower_state("SAS901") == TowerState.DOWNWIND
        assert twr._sequence_numbers.get("SAS901") == 1

    def test_sequence_numbers_increment_globally(self, twr):
        twr.sequence_aircraft("SAS901", "01L")
        twr.get_pending_commands()
        twr.sequence_aircraft("SAS902", "19R")
        twr.get_pending_commands()
        twr.sequence_aircraft("SAS903", "01L")
        twr.get_pending_commands()
        assert twr._sequence_numbers["SAS901"] == 1
        assert twr._sequence_numbers["SAS902"] == 2
        assert twr._sequence_numbers["SAS903"] == 3

    def test_sequence_aircraft_not_in_circuit(self, twr):
        seq = twr.sequence_aircraft("SAS901", "01L")
        assert seq == 1
        cmds = twr.get_pending_commands()
        assert any("number 1" in c.data.get("instruction", "") for c in cmds)


# ──────────────────────────────────────────────
# Pattern Conflict Detection
# ──────────────────────────────────────────────

class TestPatternConflictDetection:
    def test_conflict_same_leg_downwind(self, twr):
        twr.init_vfr_circuit("SAS901", "01L")
        twr.init_vfr_circuit("SAS902", "01L")
        twr.report_downwind("SAS901", "01L")
        twr.get_pending_commands()
        twr.report_downwind("SAS902", "01L")
        twr.get_pending_commands()
        conflicts = twr.detect_pattern_conflicts("01L")
        same_leg = [c for c in conflicts if c.conflict_type == "same_leg"]
        assert len(same_leg) >= 1
        assert same_leg[0].leg == "downwind"
        assert same_leg[0].severity == "warning"

    def test_no_conflict_single_aircraft(self, twr):
        twr.init_vfr_circuit("SAS901", "01L")
        twr.report_downwind("SAS901", "01L")
        twr.get_pending_commands()
        conflicts = twr.detect_pattern_conflicts("01L")
        assert len(conflicts) == 0

    def test_no_conflict_different_legs(self, twr):
        twr.init_vfr_circuit("SAS901", "01L")
        twr.init_vfr_circuit("SAS902", "01L")
        twr.report_downwind("SAS901", "01L")
        twr.get_pending_commands()
        twr.report_base("SAS902", "01L")
        twr.get_pending_commands()
        conflicts = twr.detect_pattern_conflicts("01L")
        same_leg = [c for c in conflicts if c.conflict_type == "same_leg"]
        assert len(same_leg) == 0

    def test_critical_conflict_on_final(self, twr):
        twr.init_vfr_circuit("SAS901", "01L")
        twr.init_vfr_circuit("SAS902", "01L")
        twr.report_downwind("SAS901", "01L")
        twr.get_pending_commands()
        twr.report_base("SAS901", "01L")
        twr.get_pending_commands()
        twr.report_final("SAS901", "01L")
        twr.get_pending_commands()
        twr.report_downwind("SAS902", "01L")
        twr.get_pending_commands()
        twr.report_base("SAS902", "01L")
        twr.get_pending_commands()
        twr.report_final("SAS902", "01L")
        twr.get_pending_commands()
        conflicts = twr.detect_pattern_conflicts("01L")
        critical = [c for c in conflicts if c.severity == "critical"]
        assert len(critical) >= 1
        assert critical[0].leg == "final"

    def test_merge_conflict_approaching_with_pattern(self, twr):
        twr.clear_full_stop("SAS901", "01L")
        twr.get_pending_commands()
        twr.init_vfr_circuit("SAS902", "01L")
        twr.report_downwind("SAS902", "01L")
        twr.get_pending_commands()
        twr.report_base("SAS902", "01L")
        twr.get_pending_commands()
        twr.report_final("SAS902", "01L")
        twr.get_pending_commands()
        conflicts = twr.detect_pattern_conflicts("01L")
        merge = [c for c in conflicts if c.conflict_type == "merge"]
        assert len(merge) >= 1
        assert merge[0].severity == "critical"

    def test_no_conflict_empty_pattern(self, twr):
        conflicts = twr.detect_pattern_conflicts("01L")
        assert len(conflicts) == 0


# ──────────────────────────────────────────────
# Process: Pattern Conflict Auto-Resolution
# ──────────────────────────────────────────────

class TestProcessPatternConflicts:
    def test_process_no_conflict_no_change(self, twr):
        twr.clear_full_stop("SAS901", "01L")
        twr.get_pending_commands()
        with patch.object(__import__("time"), "time", return_value=100.0):
            twr.process(1.0, {})
        assert twr.get_aircraft_tower_state("SAS901") == TowerState.FULL_STOP

    def test_process_merge_conflict_auto_go_around(self, twr):
        twr.clear_full_stop("SAS901", "01L")
        twr.get_pending_commands()
        twr.init_vfr_circuit("SAS902", "01L")
        twr.report_downwind("SAS902", "01L")
        twr.get_pending_commands()
        twr.report_base("SAS902", "01L")
        twr.get_pending_commands()
        twr.report_final("SAS902", "01L")
        twr.get_pending_commands()
        with patch.object(__import__("time"), "time", return_value=100.0):
            twr.process(1.0, {})
        assert twr.get_aircraft_tower_state("SAS901") == TowerState.GO_AROUND

    def test_process_same_leg_warning_no_auto_action(self, twr):
        twr.init_vfr_circuit("SAS901", "01L")
        twr.init_vfr_circuit("SAS902", "01L")
        twr.report_downwind("SAS901", "01L")
        twr.get_pending_commands()
        twr.report_downwind("SAS902", "01L")
        twr.get_pending_commands()
        with patch.object(__import__("time"), "time", return_value=100.0):
            twr.process(1.0, {})
        assert twr.get_aircraft_tower_state("SAS901") == TowerState.DOWNWIND
        assert twr.get_aircraft_tower_state("SAS902") == TowerState.DOWNWIND

    def test_process_only_one_go_around_per_cycle(self, twr):
        twr.clear_full_stop("SAS901", "01L")
        twr.get_pending_commands()
        twr.init_vfr_circuit("SAS902", "01L")
        twr.report_downwind("SAS902", "01L")
        twr.get_pending_commands()
        twr.report_base("SAS902", "01L")
        twr.get_pending_commands()
        twr.report_final("SAS902", "01L")
        twr.get_pending_commands()
        with patch.object(__import__("time"), "time", return_value=100.0):
            twr.process(1.0, {})
        twr.get_pending_commands()
        assert twr.runways["01L"].is_occupied is False
        assert twr.runways["01L"].current_arrival_callsign is None


# ──────────────────────────────────────────────
# Multiple Aircraft Pattern Lifecycle
# ──────────────────────────────────────────────

class TestMultiAircraftPatternLifecycle:
    def test_two_aircraft_full_pattern(self, twr):
        twr.init_vfr_circuit("SAS901", "01L")
        twr.init_vfr_circuit("SAS902", "01L")
        twr.sequence_aircraft("SAS901", "01L")
        twr.get_pending_commands()
        twr.sequence_aircraft("SAS902", "01L")
        twr.get_pending_commands()
        twr.report_downwind("SAS901", "01L")
        twr.get_pending_commands()
        twr.report_downwind("SAS902", "01L")
        twr.get_pending_commands()
        twr.report_base("SAS901", "01L")
        twr.get_pending_commands()
        twr.report_base("SAS902", "01L")
        twr.get_pending_commands()
        twr.report_final("SAS901", "01L")
        twr.get_pending_commands()
        twr.report_final("SAS902", "01L")
        twr.get_pending_commands()
        assert twr.get_aircraft_tower_state("SAS901") == TowerState.FINAL_APPROACH
        assert twr.get_aircraft_tower_state("SAS902") == TowerState.FINAL_APPROACH
        assert len(twr.get_pattern_aircraft_on_leg("01L", "final")) == 2

    def test_two_aircraft_different_runways(self, twr):
        twr.init_vfr_circuit("SAS901", "01L")
        twr.init_vfr_circuit("SAS902", "19R")
        twr.report_downwind("SAS901", "01L")
        twr.get_pending_commands()
        twr.report_downwind("SAS902", "19R")
        twr.get_pending_commands()
        twr.report_base("SAS901", "01L")
        twr.get_pending_commands()
        twr.report_final("SAS902", "19R")
        twr.get_pending_commands()
        assert twr.get_pattern_aircraft_on_leg("01L", "base") == ["SAS901"]
        assert twr.get_pattern_aircraft_on_leg("19R", "final") == ["SAS902"]

    def test_extend_downwind_then_sequencing(self, twr):
        twr.init_vfr_circuit("SAS901", "01L")
        twr.init_vfr_circuit("SAS902", "01L")
        twr.sequence_aircraft("SAS901", "01L")
        twr.get_pending_commands()
        twr.sequence_aircraft("SAS902", "01L")
        twr.get_pending_commands()
        twr.report_downwind("SAS901", "01L")
        twr.get_pending_commands()
        twr.report_downwind("SAS902", "01L")
        twr.get_pending_commands()
        twr.issue_extend_downwind("SAS902", "01L")
        twr.get_pending_commands()
        assert "SAS902" in twr._extended_downwind
        twr.cancel_extend_downwind("SAS902", "01L")
        cmds = twr.get_pending_commands()
        assert any("turn base now" in c.data.get("instruction", "") for c in cmds)

    def test_vfr_ifr_coexistence(self, twr):
        twr.init_vfr_circuit("SAS901", "01L")
        twr.report_downwind("SAS901", "01L")
        twr.get_pending_commands()
        assert twr.can_clear_takeoff("19R") is True
        twr.line_up("BAW123", "19R")
        twr.get_pending_commands()
        twr.clear_takeoff("BAW123", "19R")
        twr.get_pending_commands()
        assert twr.get_aircraft_tower_state("BAW123") == TowerState.TAKEOFF_CLEARED
        assert twr.get_aircraft_tower_state("SAS901") == TowerState.DOWNWIND

    def test_circuit_full_stop_with_traffic_in_pattern(self, twr):
        twr.init_vfr_circuit("SAS901", "01L")
        twr.init_vfr_circuit("SAS902", "01L")
        twr.report_downwind("SAS901", "01L")
        twr.get_pending_commands()
        twr.report_downwind("SAS902", "01L")
        twr.get_pending_commands()
        twr.report_base("SAS901", "01L")
        twr.get_pending_commands()
        twr.report_final("SAS901", "01L")
        twr.get_pending_commands()
        twr.clear_full_stop("SAS901", "01L")
        twr.get_pending_commands()
        assert twr.get_aircraft_tower_state("SAS901") == TowerState.FULL_STOP
        assert twr.get_aircraft_tower_state("SAS902") == TowerState.DOWNWIND
        assert "SAS901" in twr._approaching_aircraft
        twr.circuit_full_stop_complete("SAS901", "01L")
        assert "SAS901" not in twr._vfr_circuits
        assert "SAS902" in twr._vfr_circuits

    @pytest.mark.parametrize("count", [2, 3, 5])
    def test_multiple_aircraft_in_pattern(self, twr, count):
        for i in range(count):
            cs = f"SAS90{i+1}"
            twr.init_vfr_circuit(cs, "01L")
            twr.sequence_aircraft(cs, "01L")
            twr.get_pending_commands()
            twr.report_downwind(cs, "01L")
            twr.get_pending_commands()
        assert len(twr.get_pattern_aircraft_on_leg("01L", "downwind")) == count
        assert twr._next_sequence_number == count + 1

    def test_multiple_touch_and_go_with_traffic(self, twr):
        twr.init_vfr_circuit("SAS901", "01L")
        twr.init_vfr_circuit("SAS902", "01L")
        twr.report_downwind("SAS901", "01L")
        twr.get_pending_commands()
        twr.report_downwind("SAS902", "01L")
        twr.get_pending_commands()
        twr.clear_touch_and_go("SAS901", "01L")
        twr.get_pending_commands()
        twr.circuit_touch_and_go_complete("SAS901", "01L")
        twr.get_pending_commands()
        assert twr.get_aircraft_tower_state("SAS901") == TowerState.DOWNWIND
        assert twr.get_aircraft_tower_state("SAS902") == TowerState.DOWNWIND
        assert twr._vfr_circuits["SAS901"].touch_and_go_count == 1
        assert len(twr.get_pattern_aircraft_on_leg("01L", "downwind")) == 2
