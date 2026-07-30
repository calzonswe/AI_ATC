import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import time
from unittest.mock import patch

import pytest

from models import TowerState, VfrCircuitProgress
from tower import TowerController


@pytest.fixture
def twr():
    return TowerController("ESSA_TWR", 118.5, "ESSA_TWR", "ESSA", ["01L", "19R"])


# ──────────────────────────────────────────────
# VFR Circuit Progress
# ──────────────────────────────────────────────

class TestVfrCircuitProgress:
    def test_create(self):
        p = VfrCircuitProgress(callsign="SAS901", runway="01L")
        assert p.callsign == "SAS901"
        assert p.runway == "01L"
        assert p.pattern_direction == "left"
        assert p.circuit_count == 0
        assert p.touch_and_go_count == 0

    def test_custom_direction(self):
        p = VfrCircuitProgress(callsign="SAS901", runway="19R",
                                pattern_direction="right")
        assert p.pattern_direction == "right"

    def test_leg_updates(self):
        p = VfrCircuitProgress(callsign="SAS901", runway="01L")
        p.current_leg = "downwind"
        assert p.current_leg == "downwind"
        p.current_leg = "base"
        assert p.current_leg == "base"

    def test_counters(self):
        p = VfrCircuitProgress(callsign="SAS901", runway="01L")
        p.circuit_count = 3
        p.touch_and_go_count = 2
        assert p.circuit_count == 3
        assert p.touch_and_go_count == 2


# ──────────────────────────────────────────────
# TowerState VFR Values
# ──────────────────────────────────────────────

class TestTowerStateVfr:
    def test_downwind_value(self):
        assert TowerState.DOWNWIND.value == "downwind"

    def test_base_value(self):
        assert TowerState.BASE.value == "base"

    def test_final_approach_value(self):
        assert TowerState.FINAL_APPROACH.value == "final_approach"

    def test_touch_and_go_value(self):
        assert TowerState.TOUCH_AND_GO.value == "touch_and_go"

    def test_option_value(self):
        assert TowerState.OPTION.value == "option"

    def test_low_approach_value(self):
        assert TowerState.LOW_APPROACH.value == "low_approach"

    def test_stop_and_go_value(self):
        assert TowerState.STOP_AND_GO.value == "stop_and_go"

    def test_full_stop_value(self):
        assert TowerState.FULL_STOP.value == "full_stop"

    def test_overhead_join_value(self):
        assert TowerState.OVERHEAD_JOIN.value == "overhead_join"


# ──────────────────────────────────────────────
# VFR Pattern Reporting
# ──────────────────────────────────────────────

class TestVfrPatternReporting:
    def test_report_downwind(self, twr):
        twr.report_downwind("SAS901", "01L")
        assert twr.get_aircraft_tower_state("SAS901") == TowerState.DOWNWIND
        assert twr.is_controlling("SAS901")

    def test_report_downwind_issues_command(self, twr):
        twr.report_downwind("SAS901", "01L")
        cmds = twr.get_pending_commands()
        assert any("report base" in c.data.get("instruction", "") for c in cmds)

    def test_report_downwind_auto_accepts(self, twr):
        twr.report_downwind("SAS901", "01L")
        assert twr.is_controlling("SAS901")

    def test_report_base(self, twr):
        twr.report_downwind("SAS901", "01L")
        twr.get_pending_commands()
        twr.report_base("SAS901", "01L")
        assert twr.get_aircraft_tower_state("SAS901") == TowerState.BASE

    def test_report_base_not_controlling(self, twr):
        twr.report_base("SAS901", "01L")  # no-op, not controlling
        assert twr.get_aircraft_tower_state("SAS901") is None

    def test_report_base_issues_command(self, twr):
        twr.report_downwind("SAS901", "01L")
        twr.get_pending_commands()
        twr.report_base("SAS901", "01L")
        cmds = twr.get_pending_commands()
        assert any("report final" in c.data.get("instruction", "") for c in cmds)

    def test_report_final(self, twr):
        twr.report_downwind("SAS901", "01L")
        twr.get_pending_commands()
        twr.report_base("SAS901", "01L")
        twr.get_pending_commands()
        twr.report_final("SAS901", "01L")
        assert twr.get_aircraft_tower_state("SAS901") == TowerState.FINAL_APPROACH

    def test_report_final_not_controlling(self, twr):
        twr.report_final("SAS901", "01L")
        assert twr.get_aircraft_tower_state("SAS901") is None

    def test_report_final_issues_command(self, twr):
        twr.report_downwind("SAS901", "01L")
        twr.get_pending_commands()
        twr.report_base("SAS901", "01L")
        twr.get_pending_commands()
        twr.report_final("SAS901", "01L")
        cmds = twr.get_pending_commands()
        assert any("cleared to land" in c.data.get("instruction", "") for c in cmds)

    def test_full_pattern_calls_log_state_changes(self, twr):
        twr.report_downwind("SAS901", "01L")
        twr.get_pending_commands()
        twr.report_base("SAS901", "01L")
        twr.get_pending_commands()
        twr.report_final("SAS901", "01L")
        twr.get_pending_commands()
        assert twr.get_aircraft_tower_state("SAS901") == TowerState.FINAL_APPROACH
        assert twr.is_controlling("SAS901")


# ──────────────────────────────────────────────
# VFR Pattern Clearances
# ──────────────────────────────────────────────

class TestVfrClearances:
    def test_clear_touch_and_go(self, twr):
        twr.clear_touch_and_go("SAS901", "01L")
        assert twr.get_aircraft_tower_state("SAS901") == TowerState.TOUCH_AND_GO

    def test_clear_touch_and_go_issues_command(self, twr):
        twr.clear_touch_and_go("SAS901", "01L")
        cmds = twr.get_pending_commands()
        assert any("cleared touch-and-go" in c.data.get("instruction", "") for c in cmds)

    def test_clear_touch_and_go_occupies_runway(self, twr):
        twr.clear_touch_and_go("SAS901", "01L")
        assert twr.runways["01L"].is_occupied is True

    def test_clear_option(self, twr):
        twr.clear_option("SAS901", "01L")
        assert twr.get_aircraft_tower_state("SAS901") == TowerState.OPTION

    def test_clear_option_issues_command(self, twr):
        twr.clear_option("SAS901", "01L")
        cmds = twr.get_pending_commands()
        assert any("cleared option" in c.data.get("instruction", "") for c in cmds)

    def test_clear_option_occupies_runway(self, twr):
        twr.clear_option("SAS901", "01L")
        assert twr.runways["01L"].is_occupied is True

    def test_clear_low_approach(self, twr):
        twr.clear_low_approach("SAS901", "01L")
        assert twr.get_aircraft_tower_state("SAS901") == TowerState.LOW_APPROACH

    def test_clear_low_approach_issues_command(self, twr):
        twr.clear_low_approach("SAS901", "01L")
        cmds = twr.get_pending_commands()
        assert any("cleared low approach" in c.data.get("instruction", "") for c in cmds)

    def test_clear_low_approach_does_not_occupy_runway(self, twr):
        twr.clear_low_approach("SAS901", "01L")
        assert twr.runways["01L"].is_occupied is False

    def test_clear_stop_and_go(self, twr):
        twr.clear_stop_and_go("SAS901", "01L")
        assert twr.get_aircraft_tower_state("SAS901") == TowerState.STOP_AND_GO

    def test_clear_stop_and_go_issues_command(self, twr):
        twr.clear_stop_and_go("SAS901", "01L")
        cmds = twr.get_pending_commands()
        assert any("cleared stop-and-go" in c.data.get("instruction", "") for c in cmds)

    def test_clear_stop_and_go_occupies_runway(self, twr):
        twr.clear_stop_and_go("SAS901", "01L")
        assert twr.runways["01L"].is_occupied is True

    def test_clear_full_stop(self, twr):
        twr.clear_full_stop("SAS901", "01L")
        assert twr.get_aircraft_tower_state("SAS901") == TowerState.FULL_STOP

    def test_clear_full_stop_issues_command(self, twr):
        twr.clear_full_stop("SAS901", "01L")
        cmds = twr.get_pending_commands()
        assert any("cleared full stop" in c.data.get("instruction", "") for c in cmds)

    def test_clear_full_stop_occupies_runway(self, twr):
        twr.clear_full_stop("SAS901", "01L")
        assert twr.runways["01L"].is_occupied is True

    def test_clear_full_stop_sets_arrival(self, twr):
        twr.clear_full_stop("SAS901", "01L")
        assert twr.runways["01L"].current_arrival_callsign == "SAS901"

    def test_clear_full_stop_occupied_runway_goes_around(self, twr):
        twr.clear_full_stop("SAS901", "01L")
        twr.get_pending_commands()
        twr.clear_full_stop("SAS902", "01L")  # runway occupied
        assert twr.get_aircraft_tower_state("SAS902") == TowerState.GO_AROUND

    def test_clear_touch_and_go_sets_clearance(self, twr):
        twr.clear_touch_and_go("SAS901", "01L")
        clr = twr.get_clearance_state("SAS901")
        assert clr is not None
        assert clr.clearance_type == "touch_and_go"
        assert clr.is_active is True


# ──────────────────────────────────────────────
# Overhead Join
# ──────────────────────────────────────────────

class TestOverheadJoin:
    def test_issue_overhead_join(self, twr):
        twr.issue_overhead_join("SAS901", "01L")
        assert twr.get_aircraft_tower_state("SAS901") == TowerState.OVERHEAD_JOIN
        assert twr.is_controlling("SAS901")

    def test_issue_overhead_join_issues_command(self, twr):
        twr.issue_overhead_join("SAS901", "01L")
        cmds = twr.get_pending_commands()
        assert any("overhead join approved" in c.data.get("instruction", "") for c in cmds)

    def test_overhead_join_right_pattern(self, twr):
        twr.issue_overhead_join("SAS901", "01L", pattern_direction="right")
        cmds = twr.get_pending_commands()
        assert any("break right-hand" in c.data.get("instruction", "") for c in cmds)

    def test_overhead_join_creates_circuit(self, twr):
        twr.issue_overhead_join("SAS901", "01L")
        assert "SAS901" in twr._vfr_circuits
        assert twr._vfr_circuits["SAS901"].current_leg == "overhead"

    def test_overhead_join_custom_altitude(self, twr):
        twr.issue_overhead_join("SAS901", "01L", break_alt_ft=1500)
        cmds = twr.get_pending_commands()
        assert any("1500 feet" in c.data.get("instruction", "") for c in cmds)


# ──────────────────────────────────────────────
# Pattern Entry and Exit
# ──────────────────────────────────────────────

class TestPatternEntryExit:
    def test_issue_pattern_entry_downwind(self, twr):
        twr.issue_pattern_entry("SAS901", "01L", "downwind")
        assert twr.is_controlling("SAS901")
        cmds = twr.get_pending_commands()
        assert any("enter left-hand pattern" in c.data.get("instruction", "") for c in cmds)

    def test_issue_pattern_entry_right(self, twr):
        twr.issue_pattern_entry("SAS901", "01L", "base", pattern_direction="right")
        cmds = twr.get_pending_commands()
        assert any("enter right-hand pattern" in c.data.get("instruction", "") for c in cmds)

    def test_issue_pattern_entry_init_circuit(self, twr):
        twr.issue_pattern_entry("SAS901", "01L")
        assert "SAS901" in twr._vfr_circuits

    def test_issue_pattern_exit(self, twr):
        twr.init_vfr_circuit("SAS901", "01L")
        twr.issue_pattern_exit("SAS901", "01L")
        cmds = twr.get_pending_commands()
        assert any("exit" in c.data.get("instruction", "") for c in cmds)

    def test_issue_pattern_exit_not_controlling(self, twr):
        twr.issue_pattern_exit("SAS901", "01L")  # no-op not crash

    def test_init_vfr_circuit(self, twr):
        p = twr.init_vfr_circuit("SAS901", "01L", "right")
        assert isinstance(p, VfrCircuitProgress)
        assert p.callsign == "SAS901"
        assert p.pattern_direction == "right"
        assert twr.is_controlling("SAS901")


# ──────────────────────────────────────────────
# Circuit Continuation and Completion
# ──────────────────────────────────────────────

class TestCircuitContinuation:
    def test_circuit_touch_and_go_complete(self, twr):
        twr.clear_touch_and_go("SAS901", "01L")
        twr.get_pending_commands()
        twr.circuit_touch_and_go_complete("SAS901", "01L")
        assert twr.get_aircraft_tower_state("SAS901") == TowerState.DOWNWIND
        assert twr.runways["01L"].is_occupied is False

    def test_circuit_touch_and_go_complete_counts(self, twr):
        twr.init_vfr_circuit("SAS901", "01L")
        twr.clear_touch_and_go("SAS901", "01L")
        twr.get_pending_commands()
        twr.circuit_touch_and_go_complete("SAS901", "01L")
        progress = twr._vfr_circuits["SAS901"]
        assert progress.circuit_count == 1
        assert progress.touch_and_go_count == 1
        assert progress.current_leg == "downwind"

    def test_circuit_full_stop_complete(self, twr):
        twr.clear_full_stop("SAS901", "01L")
        twr.get_pending_commands()
        twr.circuit_full_stop_complete("SAS901", "01L")
        assert not twr.is_controlling("SAS901")
        assert "SAS901" not in twr._vfr_circuits
        assert twr.runways["01L"].is_occupied is False

    def test_circuit_full_stop_complete_proposes_handoff(self, twr):
        twr.clear_full_stop("SAS901", "01L")
        twr.get_pending_commands()
        twr.circuit_full_stop_complete("SAS901", "01L")
        handoffs = twr.get_pending_handoffs()
        assert len(handoffs) == 1
        assert handoffs[0].to_controller == "ESSA_GND"

    def test_multiple_circuits(self, twr):
        twr.init_vfr_circuit("SAS901", "01L")
        # Circuit 1: touch-and-go
        twr.clear_touch_and_go("SAS901", "01L")
        twr.get_pending_commands()
        twr.circuit_touch_and_go_complete("SAS901", "01L")
        # Circuit 2: touch-and-go
        twr.clear_touch_and_go("SAS901", "01L")
        twr.get_pending_commands()
        twr.circuit_touch_and_go_complete("SAS901", "01L")
        progress = twr._vfr_circuits["SAS901"]
        assert progress.circuit_count == 2
        assert progress.touch_and_go_count == 2
        assert twr.is_controlling("SAS901")

    def test_full_pattern_with_full_stop(self, twr):
        twr.report_downwind("SAS901", "01L")
        twr.get_pending_commands()
        twr.report_base("SAS901", "01L")
        twr.get_pending_commands()
        twr.report_final("SAS901", "01L")
        twr.get_pending_commands()
        twr.clear_full_stop("SAS901", "01L")
        assert twr.get_aircraft_tower_state("SAS901") == TowerState.FULL_STOP

    def test_full_pattern_with_touch_and_go(self, twr):
        twr.report_downwind("SAS901", "01L")
        twr.get_pending_commands()
        twr.report_base("SAS901", "01L")
        twr.get_pending_commands()
        twr.report_final("SAS901", "01L")
        twr.get_pending_commands()
        twr.clear_touch_and_go("SAS901", "01L")
        assert twr.get_aircraft_tower_state("SAS901") == TowerState.TOUCH_AND_GO


# ──────────────────────────────────────────────
# VFR Traffic Advisories
# ──────────────────────────────────────────────

class TestVfrTrafficAdvisories:
    def test_issue_traffic_advisory_for_vfr(self, twr):
        twr.report_downwind("SAS901", "01L")
        twr.get_pending_commands()
        advisory = twr.issue_traffic_advisory("SAS901", "SAS902", "2 miles ahead")
        assert advisory.target_callsign == "SAS901"
        assert advisory.traffic_callsign == "SAS902"

    def test_traffic_advisory_in_pattern(self, twr):
        twr.init_vfr_circuit("SAS901", "01L")
        twr.issue_traffic_advisory("SAS901", "SAS903", "same direction")
        cmds = twr.get_pending_commands()
        assert any("traffic" in c.data.get("instruction", "") for c in cmds)

    def test_report_traffic_for_vfr(self, twr):
        twr.report_downwind("SAS901", "01L")
        twr.get_pending_commands()
        twr.report_traffic("SAS901", "N12345", "10 o'clock", "3 miles", "1500 feet")
        cmds = twr.get_pending_commands()
        assert any("10 o'clock" in c.data.get("instruction", "") for c in cmds)


# ──────────────────────────────────────────────
# Separation and Conflict Detection (VFR)
# ──────────────────────────────────────────────

class TestVfrSeparation:
    def test_full_stop_added_to_approaching(self, twr):
        twr.clear_full_stop("SAS901", "01L")
        assert "SAS901" in twr._approaching_aircraft

    def test_process_full_stop_conflict(self, twr):
        twr.clear_full_stop("SAS901", "01L")
        twr.get_pending_commands()
        twr.clear_takeoff("SAS902", "01L")  # departure occupies runway
        twr.get_pending_commands()
        with patch.object(time, "time", return_value=100.0):
            twr.process(1.0, {})
        assert twr.get_aircraft_tower_state("SAS901") == TowerState.GO_AROUND

    def test_process_no_conflict_vfr(self, twr):
        twr.clear_full_stop("SAS901", "01L")
        twr.get_pending_commands()
        with patch.object(time, "time", return_value=100.0):
            twr.process(1.0, {})
        assert twr.get_aircraft_tower_state("SAS901") == TowerState.FULL_STOP


# ──────────────────────────────────────────────
# VFR Circuit Lifecycle Integration
# ──────────────────────────────────────────────

class TestVfrCircuitLifecycle:
    def test_overhead_join_then_circuit(self, twr):
        twr.issue_overhead_join("SAS901", "01L", "left", 1500)
        twr.get_pending_commands()
        assert twr.get_aircraft_tower_state("SAS901") == TowerState.OVERHEAD_JOIN
        # After break, aircraft reports downwind
        twr.report_downwind("SAS901", "01L")
        assert twr.get_aircraft_tower_state("SAS901") == TowerState.DOWNWIND
        twr.get_pending_commands()
        twr.report_base("SAS901", "01L")
        twr.get_pending_commands()
        twr.report_final("SAS901", "01L")
        twr.get_pending_commands()
        twr.clear_touch_and_go("SAS901", "01L")
        assert twr.get_aircraft_tower_state("SAS901") == TowerState.TOUCH_AND_GO

    def test_circuit_with_multiple_touch_and_go(self, twr):
        twr.init_vfr_circuit("SAS901", "01L")
        for _ in range(3):
            twr.clear_touch_and_go("SAS901", "01L")
            twr.get_pending_commands()
            twr.circuit_touch_and_go_complete("SAS901", "01L")
        progress = twr._vfr_circuits["SAS901"]
        assert progress.circuit_count == 3
        assert progress.touch_and_go_count == 3

    def test_pattern_entry_then_full_stop(self, twr):
        twr.issue_pattern_entry("SAS901", "01L", "downwind")
        twr.get_pending_commands()
        twr.report_downwind("SAS901", "01L")
        twr.get_pending_commands()
        twr.report_base("SAS901", "01L")
        twr.get_pending_commands()
        twr.report_final("SAS901", "01L")
        twr.get_pending_commands()
        twr.clear_full_stop("SAS901", "01L")
        assert twr.get_aircraft_tower_state("SAS901") == TowerState.FULL_STOP

    def test_vfr_circuit_does_not_affect_ifr_operations(self, twr):
        twr.init_vfr_circuit("SAS901", "01L")
        twr.report_downwind("SAS902", "19R")
        assert twr.is_controlling("SAS901")
        assert twr.is_controlling("SAS902")
        assert twr.get_aircraft_tower_state("SAS901") is None  # init does not set a leg
        assert twr.get_aircraft_tower_state("SAS902") == TowerState.DOWNWIND
        # VFR circuit does not block IFR departure on different runway
        assert twr.can_clear_takeoff("19R") is True
