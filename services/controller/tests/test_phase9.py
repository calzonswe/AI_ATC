import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pytest
from shapely.geometry import Point

from approach import ApproachController
from atis import AtisController
from base import BaseController
from center import CenterController
from departure import DepartureController
from factory import ControllerFactory
from ground import GroundController
from manager import ControllerManager
from models import (
    ApproachState,
    AtisBroadcast,
    CenterState,
    ClearanceState,
    ControllerCommand,
    ControllerPosition,
    ControllerState,
    DepartureState,
    FlightStatusRecord,
    GroundState,
    TowerState,
)
from tower import TowerController


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────

@pytest.fixture
def ground():
    return GroundController("ESSA_GND", 121.8, "ESSA_GND", "ESSA")


@pytest.fixture
def tower():
    return TowerController("ESSA_TWR", 118.5, "ESSA_TWR", "ESSA", ["01L", "19R"])


@pytest.fixture
def departure():
    return DepartureController("ESSA_DEP", 124.3, "ESSA_DEP", "ESSA")


@pytest.fixture
def approach():
    return ApproachController("ESSA_APP", 119.7, "ESSA_APP", "ESSA")


@pytest.fixture
def center():
    return CenterController("ESSA_CTR", 135.5, "ESSA_CTR", "Stockholm Center")


@pytest.fixture
def atis():
    return AtisController("ESSA_ATIS", 128.425, "ESSA_ATIS", "ESSA")


@pytest.fixture
def manager():
    mgr = ControllerManager()
    mgr.add_controller(GroundController("ESSA_GND", 121.8, "ESSA_GND", "ESSA"))
    mgr.add_controller(TowerController("ESSA_TWR", 118.5, "ESSA_TWR", "ESSA", ["01L", "19R"]))
    mgr.add_controller(DepartureController("ESSA_DEP", 124.3, "ESSA_DEP", "ESSA"))
    mgr.add_controller(ApproachController("ESSA_APP", 119.7, "ESSA_APP", "ESSA"))
    mgr.add_controller(AtisController("ESSA_ATIS", 128.425, "ESSA_ATIS", "ESSA"))
    mgr.add_controller(CenterController("ESSA_CTR", 135.5, "ESSA_CTR"))
    return mgr


# ──────────────────────────────────────────────
# BaseController — Flight History Log
# ──────────────────────────────────────────────

class TestFlightHistory:
    def test_log_status_change(self, ground):
        ground.request_pushback("SAS901", "G12")
        history = ground.get_aircraft_history("SAS901")
        assert len(history) >= 1
        record = history[0]
        assert record.callsign == "SAS901"
        assert record.controller_callsign == "ESSA_GND"
        assert record.new_state == "pushback_in_progress"

    def test_multiple_status_changes(self, ground):
        ground.request_pushback("SAS901", "G12")
        ground.pushback_complete("SAS901", ["A", "B"])
        ground.report_holding_short("SAS901", "01L")
        history = ground.get_aircraft_history("SAS901")
        assert len(history) == 3
        assert history[1].new_state == "taxi_cleared"
        assert history[2].new_state == "holding_short"

    def test_history_per_aircraft(self, ground):
        ground.request_pushback("SAS901", "G12")
        ground.request_pushback("SAS902", "B5")
        assert len(ground.get_aircraft_history("SAS901")) == 1
        assert len(ground.get_aircraft_history("SAS902")) == 1
        assert len(ground.get_aircraft_history("NONEXIST")) == 0

    def test_get_all_history(self, ground):
        ground.request_pushback("SAS901", "G12")
        ground.request_pushback("SAS902", "B5")
        all_h = ground.get_all_history()
        assert "SAS901" in all_h
        assert "SAS902" in all_h

    def test_clear_history_single(self, ground):
        ground.request_pushback("SAS901", "G12")
        ground.request_pushback("SAS902", "B5")
        ground.clear_history("SAS901")
        assert ground.get_aircraft_history("SAS901") == []
        assert len(ground.get_aircraft_history("SAS902")) == 1

    def test_clear_all_history(self, ground):
        ground.request_pushback("SAS901", "G12")
        ground.request_pushback("SAS902", "B5")
        ground.clear_history()
        assert ground.get_all_history() == {}

    def test_log_status_change_command_type(self, ground):
        ground.request_pushback("SAS901", "G12")
        record = ground.get_aircraft_history("SAS901")[0]
        assert record.command_type == "pushback"

    def test_tower_logs_landing_clearance(self, tower):
        tower.clear_landing("SAS901", "01L")
        history = tower.get_aircraft_history("SAS901")
        assert len(history) >= 1
        assert history[0].command_type == "landing"


# ──────────────────────────────────────────────
# BaseController — Clearance State Machine
# ──────────────────────────────────────────────

class TestClearanceStateMachine:
    def test_set_clearance(self, ground):
        ground.accept_aircraft("SAS901")
        ground.request_pushback("SAS901", "G12")
        clearance = ground.get_clearance_state("SAS901")
        assert clearance is not None
        assert clearance.clearance_type == "pushback"
        assert clearance.issued_by == "ESSA_GND"
        assert clearance.is_active
        assert not clearance.acknowledged

    def test_acknowledge_clearance(self, ground):
        ground.accept_aircraft("SAS901")
        ground.request_pushback("SAS901", "G12")
        assert ground.acknowledge_clearance("SAS901")
        clearance = ground.get_clearance_state("SAS901")
        assert clearance.acknowledged

    def test_acknowledge_nonexistent_clearance(self, ground):
        assert not ground.acknowledge_clearance("NONEXIST")

    def test_revoke_clearance(self, ground):
        ground.accept_aircraft("SAS901")
        ground.request_pushback("SAS901", "G12")
        assert ground.revoke_clearance("SAS901")
        clearance = ground.get_clearance_state("SAS901")
        assert not clearance.is_active

    def test_revoke_twice_fails(self, ground):
        ground.accept_aircraft("SAS901")
        ground.request_pushback("SAS901", "G12")
        assert ground.revoke_clearance("SAS901")
        assert not ground.revoke_clearance("SAS901")

    def test_revoke_nonexistent(self, ground):
        assert not ground.revoke_clearance("NONEXIST")

    def test_tower_takeoff_clearance(self, tower):
        tower.accept_aircraft("SAS901")
        tower.clear_takeoff("SAS901", "01L")
        clearance = tower.get_clearance_state("SAS901")
        assert clearance.clearance_type == "takeoff"

    def test_center_climb_clearance(self, center):
        center.assign_climb("SAS901", 35000)
        clearance = center.get_clearance_state("SAS901")
        assert clearance.clearance_type == "climb"
        assert clearance.details["target_alt"] == 35000

    def test_approach_ils_clearance(self, approach):
        approach.accept_aircraft("SAS901")
        approach.clear_ils("SAS901", "01L", 110.3)
        clearance = approach.get_clearance_state("SAS901")
        assert clearance.clearance_type == "ils_approach"
        assert clearance.details["ils_freq"] == 110.3

    def test_departure_sid_clearance(self, departure):
        departure.assign_sid("SAS901", "ARN1N", 5000)
        clearance = departure.get_clearance_state("SAS901")
        assert clearance.clearance_type == "climb_via_sid"
        assert clearance.details["sid"] == "ARN1N"


# ──────────────────────────────────────────────
# AtisController
# ──────────────────────────────────────────────

class TestAtisController:
    def test_initial_state(self, atis):
        assert atis.callsign == "ESSA_ATIS"
        assert atis.frequency == 128.425
        assert atis.airport_icao == "ESSA"
        assert atis.broadcast is None

    def test_update_broadcast(self, atis):
        broadcast = atis.update_broadcast(
            identifier="K",
            metar="ESSA 281350Z 26010KT 9999 FEW025 18/12 Q1015",
            runways_in_use=["01L", "01R"],
            approach_in_use="ILS 01L",
            notices=["CAUTION: construction near taxiway A"],
        )
        assert broadcast is not None
        assert broadcast.identifier == "K"
        assert broadcast.airport_icao == "ESSA"
        assert "01L" in broadcast.runways_in_use
        assert "CAUTION" in broadcast.notices[0]

    def test_broadcast_creates_command(self, atis):
        atis.update_broadcast("J", "METAR")
        cmds = atis.get_pending_commands()
        assert len(cmds) == 1
        assert cmds[0].command_type == "atis_broadcast"

    def test_broadcast_logs_history(self, atis):
        atis.update_broadcast("L", "METAR")
        history = atis.get_aircraft_history("ATIS")
        assert len(history) >= 1

    def test_get_broadcast_text(self, atis):
        atis.update_broadcast(
            identifier="M",
            metar="ESSA 281400Z 27012KT 9999 SCT030 17/11 Q1015",
            runways_in_use=["01L"],
            approach_in_use="ILS 01L",
            notices=["WORK IN PROGRESS"],
        )
        text = atis.get_broadcast_text()
        assert "ESSA ATIS M" in text
        assert "Runways in use: 01L" in text
        assert "WORK IN PROGRESS" in text

    def test_get_broadcast_text_no_broadcast(self, atis):
        assert atis.get_broadcast_text() == ""

    def test_broadcast_empty_notices(self, atis):
        atis.update_broadcast("N", "METAR")
        text = atis.get_broadcast_text()
        assert "ATIS N" in text

    def test_is_stale_initially(self, atis):
        assert atis.is_stale()

    def test_is_stale_after_update(self, atis):
        atis.update_broadcast("P", "METAR")
        assert not atis.is_stale(max_age_s=120.0)

    def test_state_transition(self, atis):
        assert atis.state == ControllerState.ACTIVE
        atis.update_broadcast("Q", "METAR")
        assert atis.state == ControllerState.ACTIVE


# ──────────────────────────────────────────────
# ControllerManager
# ──────────────────────────────────────────────

class TestControllerManager:
    def test_add_and_get_controller(self, manager):
        ctrl = manager.get_controller("ESSA_GND")
        assert ctrl is not None
        assert ctrl.callsign == "ESSA_GND"

    def test_get_nonexistent(self, manager):
        assert manager.get_controller("NONEXIST") is None

    def test_all_controllers(self, manager):
        assert len(manager.all_controllers) == 6

    def test_controller_count(self, manager):
        assert manager.controller_count == 6

    def test_get_by_position(self, manager):
        gnd = manager.get_by_position(ControllerPosition.GROUND)
        assert gnd is not None
        assert isinstance(gnd, GroundController)

    def test_get_by_position_with_airport(self, manager):
        gnd = manager.get_by_position(ControllerPosition.GROUND, "ESSA")
        assert gnd is not None
        assert gnd.callsign == "ESSA_GND"

    def test_get_by_position_wrong_airport(self, manager):
        gnd = manager.get_by_position(ControllerPosition.GROUND, "KJFK")
        assert gnd is None

    def test_get_controllers_for_airport(self, manager):
        essa_ctrls = manager.get_controllers_for_airport("ESSA")
        assert len(essa_ctrls) == 5
        assert all(c.airport_icao == "ESSA" for c in essa_ctrls)

    def test_process_all(self, manager):
        manager.process_all(0.1, {})

    def test_collect_commands(self, manager):
        gnd = manager.get_controller("ESSA_GND")
        gnd.request_pushback("SAS901", "G12")
        cmds = manager.collect_commands()
        assert len(cmds) >= 1

    def test_collect_handoffs(self, manager):
        gnd = manager.get_controller("ESSA_GND")
        gnd.accept_aircraft("SAS901")
        gnd.report_holding_short("SAS901", "01L")
        hofs = manager.collect_handoffs()
        assert len(hofs) >= 1

    def test_route_handoff(self, manager):
        gnd = manager.get_controller("ESSA_GND")
        twr = manager.get_controller("ESSA_TWR")
        gnd.accept_aircraft("SAS901")

        from models import AircraftHandoff
        handoff = AircraftHandoff(
            callsign="SAS901",
            from_controller="ESSA_GND",
            to_controller="ESSA_TWR",
            frequency=118.5,
        )
        assert manager.route_handoff(handoff)
        assert handoff.accepted
        assert not gnd.is_controlling("SAS901")
        assert twr.is_controlling("SAS901")

    def test_route_handoff_to_nonexistent(self, manager):
        from models import AircraftHandoff
        handoff = AircraftHandoff(
            callsign="SAS901",
            from_controller="ESSA_GND",
            to_controller="NONEXIST",
            frequency=0.0,
        )
        assert not manager.route_handoff(handoff)
        assert not handoff.accepted

    def test_get_all_history(self, manager):
        gnd = manager.get_controller("ESSA_GND")
        gnd.request_pushback("SAS901", "G12")
        twr = manager.get_controller("ESSA_TWR")
        twr.clear_landing("SAS902", "01L")

        all_h = manager.get_all_history()
        assert "SAS901" in all_h
        assert "SAS902" in all_h

    def test_get_aircraft_history_across_controllers(self, manager):
        gnd = manager.get_controller("ESSA_GND")
        gnd.request_pushback("SAS901", "G12")
        twr = manager.get_controller("ESSA_TWR")
        twr.clear_landing("SAS901", "01L")

        history = manager.get_aircraft_history("SAS901")
        assert len(history) == 2

    def test_get_clearance_state_across_controllers(self, manager):
        dep = manager.get_controller("ESSA_DEP")
        dep.assign_sid("SAS901", "ARN1N", 5000)
        clearance = manager.get_clearance_state("SAS901")
        assert clearance is not None
        assert clearance.clearance_type == "climb_via_sid"


# ──────────────────────────────────────────────
# ControllerManager — Create from DB Config
# ──────────────────────────────────────────────

class TestManagerCreateFromDB:
    def test_create_from_db_config_basic(self):
        mgr = ControllerManager()
        mgr.create_from_db_config(
            airports=[{
                "icao_code": "ESSA",
                "latitude": 59.6494,
                "longitude": 17.9231,
                "runways": [
                    {"identifier": "01L"},
                    {"identifier": "19R"},
                ],
                "frequencies": [
                    {"type": "GROUND", "frequency_mhz": 121.8},
                    {"type": "TOWER", "frequency_mhz": 118.3},
                    {"type": "DEPARTURE", "frequency_mhz": 125.2},
                    {"type": "APPROACH", "frequency_mhz": 124.0},
                    {"type": "ATIS", "frequency_mhz": 128.425},
                ],
            }],
            controllers=[
                {"callsign": "ESSA_CTR", "type": "CENTER", "frequency_mhz": 135.5},
            ],
        )
        assert mgr.controller_count == 6
        assert mgr.get_controller("ESSA_GND") is not None
        assert mgr.get_controller("ESSA_TWR") is not None
        assert mgr.get_controller("ESSA_DEP") is not None
        assert mgr.get_controller("ESSA_APP") is not None
        assert mgr.get_controller("ESSA_ATIS") is not None
        assert mgr.get_controller("ESSA_CTR") is not None

    def test_create_from_db_config_no_duplicates(self):
        mgr = ControllerManager()
        mgr.add_controller(GroundController("ESSA_GND", 121.8, "ESSA_GND", "ESSA"))
        mgr.create_from_db_config(
            airports=[{
                "icao_code": "ESSA",
                "latitude": 59.6494,
                "longitude": 17.9231,
                "runways": [{"identifier": "01L"}],
                "frequencies": [{"type": "GROUND", "frequency_mhz": 121.8}],
            }],
            controllers=[],
        )
        assert mgr.controller_count == 5

    def test_create_from_db_config_empty(self):
        mgr = ControllerManager()
        mgr.create_from_db_config(airports=[], controllers=[])
        assert mgr.controller_count == 0

    def test_create_from_db_config_uses_frequencies(self):
        mgr = ControllerManager()
        mgr.create_from_db_config(
            airports=[{
                "icao_code": "ESSA",
                "latitude": 59.6494,
                "longitude": 17.9231,
                "runways": [{"identifier": "01L"}],
                "frequencies": [
                    {"type": "GROUND", "frequency_mhz": 121.800},
                    {"type": "TOWER", "frequency_mhz": 118.300},
                ],
            }],
            controllers=[],
        )
        gnd = mgr.get_controller("ESSA_GND")
        assert gnd is not None
        assert gnd.frequency == 121.8
        twr = mgr.get_controller("ESSA_TWR")
        assert twr is not None
        assert twr.frequency == 118.3


# ──────────────────────────────────────────────
# FlightStatusRecord Dataclass
# ──────────────────────────────────────────────

class TestFlightStatusRecord:
    def test_create(self):
        record = FlightStatusRecord(
            timestamp_s=100.0,
            callsign="SAS901",
            controller_callsign="ESSA_GND",
            previous_state=None,
            new_state="pushback_in_progress",
            command_type="pushback",
        )
        assert record.callsign == "SAS901"
        assert record.command_type == "pushback"

    def test_sort_by_timestamp(self):
        r1 = FlightStatusRecord(100.0, "AC1", "CTRL", None, "a", "cmd1")
        r2 = FlightStatusRecord(200.0, "AC1", "CTRL", "a", "b", "cmd2")
        r3 = FlightStatusRecord(150.0, "AC1", "CTRL", "b", "c", "cmd3")
        sorted_r = sorted([r1, r2, r3], key=lambda r: r.timestamp_s)
        assert sorted_r[0].timestamp_s == 100.0
        assert sorted_r[1].timestamp_s == 150.0
        assert sorted_r[2].timestamp_s == 200.0


# ──────────────────────────────────────────────
# ClearanceState Dataclass
# ──────────────────────────────────────────────

class TestClearanceStateDataclass:
    def test_create(self):
        c = ClearanceState(
            clearance_type="takeoff",
            issued_by="ESSA_TWR",
            is_active=True,
            acknowledged=False,
            issued_at_s=500.0,
            details={"runway": "01L"},
        )
        assert c.clearance_type == "takeoff"
        assert c.details["runway"] == "01L"

    def test_defaults(self):
        c = ClearanceState(clearance_type="taxi", issued_by="ESSA_GND")
        assert c.is_active
        assert not c.acknowledged


# ──────────────────────────────────────────────
# AtisBroadcast Dataclass
# ──────────────────────────────────────────────

class TestAtisBroadcastDataclass:
    def test_create(self):
        b = AtisBroadcast(
            airport_icao="ESSA",
            identifier="K",
            frequency_mhz=128.425,
            timestamp_s=1000.0,
            metar="ESSA METAR",
            runways_in_use=["01L"],
            approach_in_use="ILS 01L",
            notices=["CAUTION"],
        )
        assert b.airport_icao == "ESSA"
        assert b.identifier == "K"
        assert "01L" in b.runways_in_use

    def test_defaults(self):
        b = AtisBroadcast(
            airport_icao="ESSA",
            identifier="A",
            frequency_mhz=128.425,
        )
        assert b.runways_in_use == []
        assert b.notices == []


# ──────────────────────────────────────────────
# ControllerFactory — DB Config
# ──────────────────────────────────────────────

class TestFactoryFromDB:
    def test_create_from_db_airports(self):
        result = ControllerFactory.create_from_db_airports([
            {
                "icao_code": "ESSA",
                "runways": [{"identifier": "01L"}, {"identifier": "19R"}],
                "frequencies": [
                    {"type": "GROUND", "frequency_mhz": 121.8},
                    {"type": "TOWER", "frequency_mhz": 118.3},
                    {"type": "DEPARTURE", "frequency_mhz": 125.2},
                    {"type": "APPROACH", "frequency_mhz": 124.0},
                    {"type": "ATIS", "frequency_mhz": 128.425},
                ],
            },
            {
                "icao_code": "ESNB",
                "runways": [{"identifier": "01"}],
                "frequencies": [{"type": "GROUND", "frequency_mhz": 122.0}],
            },
        ])
        assert "ESSA" in result
        assert "ESNB" in result
        assert len(result["ESSA"]) == 7
        assert len(result["ESNB"]) == 7

    def test_create_from_db_airports_skips_missing_icao(self):
        result = ControllerFactory.create_from_db_airports([
            {"runways": [], "frequencies": []},
        ])
        assert result == {}

    def test_create_from_db_controllers(self):
        result = ControllerFactory.create_from_db_controllers([
            {"callsign": "ESSA_GND", "type": "GROUND", "frequency_mhz": 121.8, "airport_icao": "ESSA"},
            {"callsign": "ESSA_CTR", "type": "CENTER", "frequency_mhz": 135.5},
        ])
        assert len(result) == 2
        assert "ESSA_GND" in result
        assert "ESSA_CTR" in result
        assert isinstance(result["ESSA_GND"], GroundController)
        assert isinstance(result["ESSA_CTR"], CenterController)

    def test_create_from_db_controllers_skips_bad_data(self):
        result = ControllerFactory.create_from_db_controllers([
            {"callsign": "", "type": "GROUND", "frequency_mhz": 121.8, "airport_icao": "ESSA"},
            {"callsign": "TEST", "type": "GROUND", "frequency_mhz": 0.0, "airport_icao": "ESSA"},
            {"callsign": "NO_ICAO", "type": "GROUND", "frequency_mhz": 121.8},
        ])
        assert result == {}

    def test_factory_create_atis(self):
        ctrl = ControllerFactory.create(
            ControllerPosition.ATIS,
            "ESSA_ATIS", 128.425, "ESSA_ATIS",
            airport_icao="ESSA",
        )
        assert isinstance(ctrl, AtisController)
        assert ctrl.callsign == "ESSA_ATIS"

    def test_factory_create_atis_no_airport_raises(self):
        with pytest.raises(ValueError, match="airport_icao"):
            ControllerFactory.create(
                ControllerPosition.ATIS, "ATIS", 128.425, "ATIS",
            )


# ──────────────────────────────────────────────
# Integration — Full Controller Lifecycle
# ──────────────────────────────────────────────

class TestFullLifecycle:
    def test_departure_full_lifecycle_with_manager(self, manager):
        gnd = manager.get_controller("ESSA_GND")
        twr = manager.get_controller("ESSA_TWR")
        dep = manager.get_controller("ESSA_DEP")
        ctr = manager.get_controller("ESSA_CTR")

        gnd.request_pushback("SAS901", "G12")
        gnd.pushback_complete("SAS901", ["A", "B"])
        gnd.report_holding_short("SAS901", "01L")

        handoff = gnd.get_pending_handoffs()[0]
        manager.route_handoff(handoff)

        twr.line_up("SAS901", "01L")
        twr.clear_takeoff("SAS901", "01L", "260/10kt")
        twr.departure_airborne("SAS901", "01L", 100.0)

        dep_handoff = twr.get_pending_handoffs()[0]
        manager.route_handoff(dep_handoff)

        dep.assign_sid("SAS901", "ARN1N", 5000)
        dep.handoff_to_center("SAS901", "ESSA_CTR", 135.5)

        ctr_handoff = dep.get_pending_handoffs()[0]
        manager.route_handoff(ctr_handoff)

        ctr.maintain_altitude("SAS901", 35000)
        ctr.assign_climb("SAS901", 37000)
        ctr.assign_descent("SAS901", 8000, "ARN1N")

        assert gnd.aircraft_count == 0
        assert twr.aircraft_count == 0
        assert dep.aircraft_count == 0
        assert ctr.aircraft_count == 1

        history = manager.get_aircraft_history("SAS901")
        assert len(history) >= 6

        cmds = manager.collect_commands()
        assert len(cmds) >= 1

    def test_approach_full_lifecycle(self, manager):
        app = manager.get_controller("ESSA_APP")
        twr = manager.get_controller("ESSA_TWR")

        app.accept_from_center("SAS901", 8000)
        app.vector_to_ils("SAS901", 270, 3000, 12.0)
        app.clear_ils("SAS901", "01L", 110.3)
        app.handoff_to_tower("SAS901", "ESSA_TWR", 118.5)

        handoff = manager.collect_handoffs()[0]
        manager.route_handoff(handoff)

        twr.clear_landing("SAS901", "01L")

        assert app.aircraft_count == 0
        assert twr.aircraft_count == 1

    def test_atis_integration(self, manager):
        atis = manager.get_controller("ESSA_ATIS")

        atis.update_broadcast(
            identifier="K",
            metar="ESSA 281400Z 27012KT 9999 FEW025 17/11 Q1015",
            runways_in_use=["01L", "01R"],
            approach_in_use="ILS 01L",
        )
        broadcast = atis.broadcast
        assert broadcast is not None
        assert broadcast.identifier == "K"

        text = atis.get_broadcast_text()
        assert "ESSA ATIS K" in text
        assert "ILS 01L" in text

        cmds = manager.collect_commands()
        assert any(c.command_type == "atis_broadcast" for c in cmds)
