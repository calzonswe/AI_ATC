import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pytest

from approach import ApproachController
from atis import AtisController
from base import BaseController
from center import CenterController
from departure import DepartureController
from factory import ControllerFactory
from ground import GroundController
from models import (
    ApproachState,
    CenterState,
    ControllerCommand,
    ControllerPosition,
    ControllerState,
    DepartureState,
    GroundState,
    TowerState,
)
from tower import TowerController


# ──────────────────────────────────────────────
# BaseController
# ──────────────────────────────────────────────

class TestBaseController:
    def test_initial_state(self):
        class TestCtrl(BaseController):
            def process(self, dt, context):
                pass
        ctrl = TestCtrl("TEST", 118.0, "SECTOR_1")
        assert ctrl.callsign == "TEST"
        assert ctrl.frequency == 118.0
        assert ctrl.sector_id == "SECTOR_1"
        assert ctrl.state == ControllerState.IDLE
        assert ctrl.aircraft_count == 0
        assert ctrl.controlled_aircraft == []

    def test_accept_and_release_aircraft(self):
        class TestCtrl(BaseController):
            def process(self, dt, context):
                pass
        ctrl = TestCtrl("TEST", 118.0, "S1")
        ctrl.accept_aircraft("SAS901")
        assert ctrl.is_controlling("SAS901")
        assert ctrl.aircraft_count == 1
        assert ctrl.release_aircraft("SAS901")
        assert not ctrl.is_controlling("SAS901")
        assert ctrl.aircraft_count == 0

    def test_release_nonexistent_returns_false(self):
        class TestCtrl(BaseController):
            def process(self, dt, context):
                pass
        ctrl = TestCtrl("TEST", 118.0, "S1")
        assert not ctrl.release_aircraft("NONEXIST")

    def test_issue_command(self):
        class TestCtrl(BaseController):
            def process(self, dt, context):
                pass
        ctrl = TestCtrl("TEST", 118.0, "S1")
        ctrl._issue_command("pushback", "SAS901", gate="G12")
        cmds = ctrl.get_pending_commands()
        assert len(cmds) == 1
        cmd = cmds[0]
        assert cmd.command_type == "pushback"
        assert cmd.target_callsign == "SAS901"
        assert cmd.source == "TEST"
        assert cmd.data["gate"] == "G12"

    def test_get_pending_commands_clears_queue(self):
        class TestCtrl(BaseController):
            def process(self, dt, context):
                pass
        ctrl = TestCtrl("TEST", 118.0, "S1")
        ctrl._issue_command("test", "AC1")
        ctrl.get_pending_commands()
        assert ctrl.get_pending_commands() == []

    def test_propose_handoff(self):
        class TestCtrl(BaseController):
            def process(self, dt, context):
                pass
        ctrl = TestCtrl("TEST", 118.0, "S1")
        ctrl._propose_handoff("SAS901", "ESSA_TWR", 118.5)
        hofs = ctrl.get_pending_handoffs()
        assert len(hofs) == 1
        h = hofs[0]
        assert h.callsign == "SAS901"
        assert h.from_controller == "TEST"
        assert h.to_controller == "ESSA_TWR"
        assert h.frequency == 118.5

    def test_state_property(self):
        class TestCtrl(BaseController):
            def process(self, dt, context):
                pass
        ctrl = TestCtrl("TEST", 118.0, "S1")
        ctrl.state = ControllerState.ACTIVE
        assert ctrl.state == ControllerState.ACTIVE


# ──────────────────────────────────────────────
# GroundController
# ──────────────────────────────────────────────

class TestGroundController:
    @pytest.fixture
    def gnd(self):
        return GroundController("ESSA_GND", 121.8, "ESSA_GND", "ESSA")

    def test_initial_state(self, gnd):
        assert gnd.callsign == "ESSA_GND"
        assert gnd.frequency == 121.8
        assert gnd.airport_icao == "ESSA"
        assert gnd.state == ControllerState.ACTIVE

    def test_request_pushback(self, gnd):
        gnd.request_pushback("SAS901", "G12")
        assert gnd.is_controlling("SAS901")
        assert gnd.get_aircraft_ground_state("SAS901") == GroundState.PUSHBACK_IN_PROGRESS
        cmds = gnd.get_pending_commands()
        assert len(cmds) == 1
        assert cmds[0].command_type == "pushback"
        assert cmds[0].data["gate"] == "G12"
        assert cmds[0].data["direction"] == "tail_east"

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
        assert len(cmds) == 1
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
        assert len(cmds) == 1
        assert cmds[0].command_type == "hold_short"
        assert cmds[0].data["runway"] == "01L"
        hofs = gnd.get_pending_handoffs()
        assert len(hofs) == 1
        assert hofs[0].to_controller == "ESSA_TWR"

    def test_report_holding_short_unknown_aircraft(self, gnd):
        gnd.report_holding_short("NONEXIST", "01L")
        assert gnd.get_pending_commands() == []

    def test_release_to_tower(self, gnd):
        gnd.accept_aircraft("SAS901")
        gnd.report_holding_short("SAS901", "01R")
        gnd.get_pending_commands()
        gnd.get_pending_handoffs()
        gnd.release_to_tower("SAS901")
        assert not gnd.is_controlling("SAS901")

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
# TowerController
# ──────────────────────────────────────────────

class TestTowerController:
    @pytest.fixture
    def twr(self):
        return TowerController("ESSA_TWR", 118.5, "ESSA_TWR", "ESSA", ["01L", "19R"])

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
        assert len(cmds) == 1
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

    def test_clear_takeoff(self, twr):
        twr.accept_aircraft("SAS901")
        twr.clear_takeoff("SAS901", "01L", "260/10kt")
        assert twr.get_aircraft_tower_state("SAS901") == TowerState.TAKEOFF_CLEARED
        cmds = twr.get_pending_commands()
        assert cmds[0].command_type == "takeoff"
        assert "260/10kt" in cmds[0].data.get("instruction", "")
        assert twr.runways["01L"].is_occupied
        assert twr.runways["01L"].current_departure_callsign == "SAS901"

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
        assert len(hofs) == 1
        assert hofs[0].to_controller == "ESSA_GND"

    def test_departure_takeoff_landing_lifecycle(self, twr):
        twr.accept_from_ground("SAS901", "01L")
        twr.line_up("SAS901", "01L")
        twr.clear_takeoff("SAS901", "01L")
        twr.departure_airborne("SAS901", "01L", 300.0)
        assert twr.aircraft_count == 0

    def test_arrival_landing_lifecycle(self, twr):
        twr.clear_landing("SAS901", "01L")
        twr.arrival_landed("SAS901", "01L", 400.0)
        assert twr.aircraft_count == 0

    def test_go_around_cycle(self, twr):
        twr.clear_landing("SAS901", "01L")
        twr.go_around("SAS901", "01L")
        assert twr.get_aircraft_tower_state("SAS901") == TowerState.GO_AROUND

    def test_clear_takeoff_no_wind(self, twr):
        twr.accept_aircraft("SAS901")
        twr.clear_takeoff("SAS901", "01L")
        cmds = twr.get_pending_commands()
        assert cmds[0].command_type == "takeoff"
        assert "wind" not in cmds[0].data.get("instruction", "")


# ──────────────────────────────────────────────
# DepartureController
# ──────────────────────────────────────────────

class TestDepartureController:
    @pytest.fixture
    def dep(self):
        return DepartureController("ESSA_DEP", 124.3, "ESSA_DEP", "ESSA")

    def test_initial_state(self, dep):
        assert dep.callsign == "ESSA_DEP"
        assert dep.state == ControllerState.ACTIVE

    def test_accept_from_tower(self, dep):
        dep.accept_from_tower("SAS901")
        assert dep.is_controlling("SAS901")
        assert dep.get_aircraft_departure_state("SAS901") == DepartureState.INITIAL_CLIMB
        cmds = dep.get_pending_commands()
        assert cmds[0].command_type == "contact_departure"

    def test_assign_sid(self, dep):
        dep.accept_aircraft("SAS901")
        dep.assign_sid("SAS901", "ARN1N", 5000)
        assert dep.get_aircraft_departure_state("SAS901") == DepartureState.ENROUTE
        cmds = dep.get_pending_commands()
        assert cmds[0].command_type == "climb_via_sid"
        assert cmds[0].data["sid"] == "ARN1N"

    def test_assign_sid_auto_accepts(self, dep):
        dep.assign_sid("SAS901", "ARN1N", 5000)
        assert dep.is_controlling("SAS901")

    def test_handoff_to_center(self, dep):
        dep.accept_aircraft("SAS901")
        dep.handoff_to_center("SAS901", "ESSA_CTR", 135.5)
        assert dep.get_aircraft_departure_state("SAS901") == DepartureState.HANDOFF
        cmds = dep.get_pending_commands()
        assert cmds[0].command_type == "contact_center"
        assert cmds[0].data["frequency"] == 135.5
        hofs = dep.get_pending_handoffs()
        assert len(hofs) == 1
        assert hofs[0].to_controller == "ESSA_CTR"

    def test_release_to_center(self, dep):
        dep.accept_aircraft("SAS901")
        dep.release_to_center("SAS901")
        assert not dep.is_controlling("SAS901")

    def test_departure_lifecycle(self, dep):
        dep.accept_from_tower("SAS901")
        dep.assign_sid("SAS901", "ARN1N", 5000)
        dep.handoff_to_center("SAS901", "ESSA_CTR", 135.5)
        dep.release_to_center("SAS901")
        assert dep.aircraft_count == 0


# ──────────────────────────────────────────────
# ApproachController
# ──────────────────────────────────────────────

class TestApproachController:
    @pytest.fixture
    def app(self):
        return ApproachController("ESSA_APP", 119.7, "ESSA_APP", "ESSA")

    def test_initial_state(self, app):
        assert app.callsign == "ESSA_APP"
        assert app.frequency == 119.7

    def test_accept_from_center(self, app):
        app.accept_from_center("SAS901", 8000)
        assert app.is_controlling("SAS901")
        assert app.get_aircraft_approach_state("SAS901") == ApproachState.VECTORING
        cmds = app.get_pending_commands()
        assert cmds[0].command_type == "contact_approach"

    def test_vector_to_ils(self, app):
        app.accept_aircraft("SAS901")
        app.vector_to_ils("SAS901", 270, 3000, 12.5)
        assert app.get_aircraft_approach_state("SAS901") == ApproachState.VECTORING
        cmds = app.get_pending_commands()
        assert cmds[0].command_type == "vector"
        assert cmds[0].data["heading"] == 270

    def test_vector_to_ils_auto_accepts(self, app):
        app.vector_to_ils("SAS901", 270, 3000, 12.5)
        assert app.is_controlling("SAS901")

    def test_assign_hold(self, app):
        app.assign_hold("SAS901", "ARN", 8000, "14:30")
        assert app.get_aircraft_approach_state("SAS901") == ApproachState.HOLDING
        cmds = app.get_pending_commands()
        assert cmds[0].command_type == "hold"
        assert cmds[0].data["fix"] == "ARN"
        assert "14:30" in cmds[0].data.get("instruction", "")

    def test_assign_hold_no_eta(self, app):
        app.assign_hold("SAS901", "ARN", 8000)
        cmds = app.get_pending_commands()
        assert cmds[0].command_type == "hold"
        assert "expected approach" not in cmds[0].data.get("instruction", "")

    def test_clear_ils(self, app):
        app.accept_aircraft("SAS901")
        app.clear_ils("SAS901", "01L", 110.3)
        assert app.get_aircraft_approach_state("SAS901") == ApproachState.ILS_CLEARED
        cmds = app.get_pending_commands()
        assert cmds[0].command_type == "clear_ils"
        assert cmds[0].data["ils_frequency"] == 110.3

    def test_handoff_to_tower(self, app):
        app.accept_aircraft("SAS901")
        app.handoff_to_tower("SAS901", "ESSA_TWR", 118.5)
        assert app.get_aircraft_approach_state("SAS901") == ApproachState.FINAL
        cmds = app.get_pending_commands()
        assert cmds[0].command_type == "contact_tower"
        hofs = app.get_pending_handoffs()
        assert len(hofs) == 1
        assert hofs[0].to_controller == "ESSA_TWR"

    def test_release_to_tower(self, app):
        app.accept_aircraft("SAS901")
        app.release_to_tower("SAS901")
        assert not app.is_controlling("SAS901")

    def test_go_around(self, app):
        app.go_around("SAS901", "missed approach")
        assert app.get_aircraft_approach_state("SAS901") == ApproachState.GO_AROUND
        cmds = app.get_pending_commands()
        assert cmds[0].command_type == "go_around_vector"
        assert "missed approach" in cmds[0].data.get("instruction", "")

    def test_go_around_auto_accepts(self, app):
        app.go_around("SAS901")
        assert app.is_controlling("SAS901")

    def test_approach_lifecycle(self, app):
        app.accept_from_center("SAS901", 8000)
        app.vector_to_ils("SAS901", 270, 3000, 12.0)
        app.clear_ils("SAS901", "01L", 110.3)
        app.handoff_to_tower("SAS901", "ESSA_TWR", 118.5)
        app.release_to_tower("SAS901")
        assert app.aircraft_count == 0


# ──────────────────────────────────────────────
# CenterController
# ──────────────────────────────────────────────

class TestCenterController:
    @pytest.fixture
    def ctr(self):
        return CenterController("ESSA_CTR", 135.5, "ESSA_CTR", "Stockholm Center")

    def test_initial_state(self, ctr):
        assert ctr.callsign == "ESSA_CTR"
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


# ──────────────────────────────────────────────
# ControllerFactory
# ──────────────────────────────────────────────

class TestControllerFactory:
    def test_create_ground(self):
        ctrl = ControllerFactory.create(
            ControllerPosition.GROUND, "ESSA_GND", 121.8, "ESSA_GND", airport_icao="ESSA"
        )
        assert isinstance(ctrl, GroundController)
        assert ctrl.callsign == "ESSA_GND"

    def test_create_tower(self):
        ctrl = ControllerFactory.create(
            ControllerPosition.TOWER, "ESSA_TWR", 118.5, "ESSA_TWR",
            airport_icao="ESSA", runways=["01L", "19R"],
        )
        assert isinstance(ctrl, TowerController)
        assert ctrl.callsign == "ESSA_TWR"

    def test_create_departure(self):
        ctrl = ControllerFactory.create(
            ControllerPosition.DEPARTURE, "ESSA_DEP", 124.3, "ESSA_DEP", airport_icao="ESSA"
        )
        assert isinstance(ctrl, DepartureController)

    def test_create_approach(self):
        ctrl = ControllerFactory.create(
            ControllerPosition.APPROACH, "ESSA_APP", 119.7, "ESSA_APP", airport_icao="ESSA"
        )
        assert isinstance(ctrl, ApproachController)

    def test_create_center(self):
        ctrl = ControllerFactory.create(
            ControllerPosition.CENTER, "ESSA_CTR", 135.5, "ESSA_CTR",
        )
        assert isinstance(ctrl, CenterController)

    def test_create_ground_no_airport_raises(self):
        with pytest.raises(ValueError, match="airport_icao"):
            ControllerFactory.create(
                ControllerPosition.GROUND, "GND", 121.8, "GND"
            )

    def test_create_all_for_airport(self):
        ctrls = ControllerFactory.create_all_for_airport(
            "ESSA",
            runways=["01L", "19R"],
            frequencies={"tower": 118.5, "ground": 121.8},
        )
        assert len(ctrls) == 7
        for pos in ControllerPosition:
            assert pos in ctrls
        assert ctrls[ControllerPosition.TOWER].frequency == 118.5

    def test_create_all_controllers_have_correct_types(self):
        ctrls = ControllerFactory.create_all_for_airport("ESSA")
        assert isinstance(ctrls[ControllerPosition.GROUND], GroundController)
        assert isinstance(ctrls[ControllerPosition.TOWER], TowerController)
        assert isinstance(ctrls[ControllerPosition.DEPARTURE], DepartureController)
        assert isinstance(ctrls[ControllerPosition.APPROACH], ApproachController)
        assert isinstance(ctrls[ControllerPosition.ATIS], AtisController)
        assert isinstance(ctrls[ControllerPosition.CENTER], CenterController)
