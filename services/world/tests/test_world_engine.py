import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

import math
import time

import pytest
from shapely.geometry import Polygon


# ---------------------------------------------------------------------------
# EventBus
# ---------------------------------------------------------------------------

class TestEventBus:
    def test_subscribe_and_publish(self):
        from pubsub import EventBus, EventType
        bus = EventBus()
        received = []

        def handler(ev):
            received.append(ev)

        bus.subscribe(EventType.AIRCRAFT_POSITION_UPDATED, handler)
        bus.publish(EventType.AIRCRAFT_POSITION_UPDATED, {"callsign": "SAS123"})

        assert len(received) == 1
        assert received[0].data["callsign"] == "SAS123"

    def test_wildcard_handler(self):
        from pubsub import EventBus, EventType
        bus = EventBus()
        received = []

        def handler(ev):
            received.append(ev.type)

        bus.subscribe_all(handler)
        bus.publish(EventType.CONFLICT_DETECTED, {})
        bus.publish(EventType.CONFLICT_RESOLVED, {})

        assert received == [EventType.CONFLICT_DETECTED, EventType.CONFLICT_RESOLVED]

    def test_unsubscribe(self):
        from pubsub import EventBus, EventType
        bus = EventBus()
        received = []

        def handler(ev):
            received.append(ev)

        bus.subscribe(EventType.CONFLICT_DETECTED, handler)
        bus.unsubscribe(EventType.CONFLICT_DETECTED, handler)
        bus.publish(EventType.CONFLICT_DETECTED, {})

        assert len(received) == 0

    def test_no_handler_for_type(self):
        from pubsub import EventBus, EventType
        bus = EventBus()
        bus.publish(EventType.CONFLICT_DETECTED, {})  # should not raise


# ---------------------------------------------------------------------------
# AircraftManager
# ---------------------------------------------------------------------------

class TestAircraftManager:
    def test_add_aircraft(self):
        from managers.aircraft import AircraftManager
        mgr = AircraftManager()
        frame = {
            "callsign": "SAS123",
            "position": {"lat": 59.65, "lon": 17.92, "alt_msl": 3000, "heading": 90},
            "motion": {"groundspeed": 250, "vertical_speed": 0, "on_ground": False},
            "radios": {"squawk": "1200"},
            "ts": 0,
        }
        ac = mgr.add_or_update(frame)
        assert ac.callsign == "SAS123"
        assert ac.position.lat == 59.65
        assert ac.motion.groundspeed_kn == 250
        assert mgr.count == 1

    def test_update_aircraft(self):
        from managers.aircraft import AircraftManager
        mgr = AircraftManager()
        frame1 = {
            "callsign": "SAS123",
            "position": {"lat": 59.65, "lon": 17.92, "alt_msl": 3000, "heading": 90},
            "motion": {"groundspeed": 250, "vertical_speed": 0, "on_ground": False},
            "ts": 0,
        }
        frame2 = {
            "callsign": "SAS123",
            "position": {"lat": 59.66, "lon": 17.93, "alt_msl": 3500, "heading": 92},
            "motion": {"groundspeed": 260, "vertical_speed": 500, "on_ground": False},
            "ts": 5000,
        }
        mgr.add_or_update(frame1)
        ac = mgr.add_or_update(frame2)
        assert ac.position.lat == 59.66
        assert ac.motion.groundspeed_kn == 260
        assert mgr.count == 1

    def test_get_and_remove(self):
        from managers.aircraft import AircraftManager
        mgr = AircraftManager()
        frame = {
            "callsign": "SAS123",
            "position": {},
            "motion": {},
            "ts": 0,
        }
        mgr.add_or_update(frame)
        assert mgr.get("SAS123") is not None
        mgr.remove("SAS123")
        assert mgr.get("SAS123") is None
        assert mgr.count == 0

    def test_get_all(self):
        from managers.aircraft import AircraftManager
        mgr = AircraftManager()
        for i in range(3):
            mgr.add_or_update({
                "callsign": f"AC{i}",
                "position": {},
                "motion": {},
                "ts": float(i),
            })
        assert len(mgr.get_all()) == 3

    def test_missing_callsign_raises(self):
        from managers.aircraft import AircraftManager
        mgr = AircraftManager()
        with pytest.raises(ValueError, match="callsign"):
            mgr.add_or_update({"position": {}})

    def test_get_nearby(self):
        from managers.aircraft import AircraftManager
        mgr = AircraftManager()
        mgr.add_or_update({
            "callsign": "NEAR",
            "position": {"lat": 59.65, "lon": 17.92, "alt_msl": 3000, "heading": 90},
            "motion": {"groundspeed": 250, "vertical_speed": 0, "on_ground": False},
            "ts": 0,
        })
        mgr.add_or_update({
            "callsign": "FAR",
            "position": {"lat": 60.00, "lon": 18.00, "alt_msl": 3000, "heading": 90},
            "motion": {"groundspeed": 250, "vertical_speed": 0, "on_ground": False},
            "ts": 0,
        })
        nearby = mgr.get_nearby(59.65, 17.92, 5)
        callsigns = {ac.callsign for ac in nearby}
        assert "NEAR" in callsigns
        assert "FAR" not in callsigns

    def test_predict_trajectory(self):
        from managers.aircraft import AircraftManager
        mgr = AircraftManager()
        mgr.add_or_update({
            "callsign": "SAS123",
            "position": {"lat": 59.65, "lon": 17.92, "alt_msl": 10000, "heading": 0},
            "motion": {"groundspeed": 300, "vertical_speed": 0, "on_ground": False},
            "ts": 0,
        })
        points = mgr.predict_trajectory("SAS123", 60.0)
        assert len(points) > 0
        assert points[-1].lat > 59.65  # heading 0 = north
        assert abs(points[-1].alt_msl_ft - 10000) < 1

    def test_predict_trajectory_unknown_aircraft(self):
        from managers.aircraft import AircraftManager
        mgr = AircraftManager()
        assert mgr.predict_trajectory("GHOST", 60) == []

    def test_event_bus_integration(self):
        from pubsub import EventBus, EventType
        from managers.aircraft import AircraftManager
        bus = EventBus()
        received = []
        bus.subscribe(EventType.AIRCRAFT_POSITION_UPDATED, lambda e: received.append(e))
        mgr = AircraftManager(event_bus=bus)
        mgr.add_or_update({
            "callsign": "SAS123",
            "position": {"lat": 59.65, "lon": 17.92},
            "motion": {},
            "ts": 0,
        })
        assert len(received) == 1
        assert received[0].data["callsign"] == "SAS123"


# ---------------------------------------------------------------------------
# AirportManager
# ---------------------------------------------------------------------------

class TestAirportManager:
    def test_load_airport(self):
        from managers.airport import AirportManager
        mgr = AirportManager()
        runways = [
            {"identifier": "01L/19R", "heading": 9.1, "length_ft": 10830},
            {"identifier": "08/26", "heading": 76.0, "length_ft": 8202},
        ]
        state = mgr.load_airport("ESSA", elevation_ft=137, magnetic_var=5.5, runways=runways)
        assert state.icao == "ESSA"
        assert len(state.runways) == 2
        assert mgr.get("essa") is not None  # case-insensitive

    def test_get_unknown_airport(self):
        from managers.airport import AirportManager
        mgr = AirportManager()
        assert mgr.get("XXXX") is None

    def test_crosswind_calculation(self):
        from managers.airport import AirportManager
        crosswind = AirportManager.calculate_crosswind(270, 20, 270)
        assert crosswind == pytest.approx(0.0, abs=0.5)
        crosswind = AirportManager.calculate_crosswind(270, 20, 180)
        assert crosswind == pytest.approx(20.0, abs=0.5)

    def test_headwind_calculation(self):
        from managers.airport import AirportManager
        hw = AirportManager.calculate_headwind(270, 20, 270)
        assert hw == pytest.approx(20.0, abs=0.5)
        hw = AirportManager.calculate_headwind(270, 20, 90)
        assert hw == pytest.approx(-20.0, abs=0.5)

    def test_determine_active_runways(self):
        from runtime.weather import WindData
        from managers.airport import AirportManager
        mgr = AirportManager()
        runways = [
            {"identifier": "01L/19R", "heading": 9.1, "length_ft": 10830},
            {"identifier": "08/26", "heading": 76.0, "length_ft": 8202},
        ]
        mgr.load_airport("ESSA", runways=runways)
        wind = WindData(direction=10, speed_kn=15)
        dep, arr = mgr.determine_active_runways("ESSA", wind)
        assert dep is not None
        assert arr is not None

    def test_update_runway_state(self):
        from runtime.airport import RunwaySurfaceCondition, OperationalMode
        from managers.airport import AirportManager
        mgr = AirportManager()
        runways = [{"identifier": "01L/19R", "heading": 9.1, "length_ft": 10830}]
        mgr.load_airport("ESSA", runways=runways)
        mgr.update_runway_state(
            "ESSA", "01L/19R",
            active_for_departure=True,
            surface_condition=RunwaySurfaceCondition.WET,
        )
        rwy = mgr.get("ESSA").runways["01L/19R"]
        assert rwy.active_for_departure is True
        assert rwy.surface_condition == RunwaySurfaceCondition.WET

    def test_get_active_runway(self):
        from runtime.weather import WindData
        from managers.airport import AirportManager
        mgr = AirportManager()
        runways = [{"identifier": "01L/19R", "heading": 9.1, "length_ft": 10830}]
        mgr.load_airport("ESSA", runways=runways)
        mgr.determine_active_runways("ESSA", WindData(direction=10, speed_kn=10))
        assert mgr.get_active_runway_for_departure("ESSA") is not None
        assert mgr.get_active_runway_for_departure("XXXX") is None


# ---------------------------------------------------------------------------
# WeatherManager
# ---------------------------------------------------------------------------

class TestWeatherManager:
    def test_set_and_get_metar(self):
        from runtime.weather import MetarData, WindData, CloudLayer
        from managers.weather import WeatherManager
        mgr = WeatherManager()
        metar = MetarData(
            icao="ESSA",
            time=1000.0,
            wind=WindData(direction=270, speed_kn=20, gust_kn=28),
            visibility_m=8000,
            qnh_hpa=1013,
            temperature_c=10,
            dewpoint_c=5,
            clouds=[CloudLayer(coverage="BKN", altitude_ft=3000)],
        )
        mgr.set_metar(metar)
        stored = mgr.get("essa")
        assert stored is not None
        assert stored.wind.direction == 270
        assert stored.wind.speed_kn == 20

    def test_set_metar_from_dict(self):
        from managers.weather import WeatherManager
        mgr = WeatherManager()
        mgr.set_metar_from_dict({
            "icao": "ESSA",
            "time": 1000.0,
            "wind": {"direction": 270, "speed_kn": 15},
            "visibility_m": 10000,
            "qnh_hpa": 1015,
            "temperature_c": 12,
            "dewpoint_c": 8,
            "clouds": [],
        })
        stored = mgr.get("ESSA")
        assert stored.qnh_hpa == 1015

    def test_get_wind(self):
        from runtime.weather import MetarData, WindData
        from managers.weather import WeatherManager
        mgr = WeatherManager()
        mgr.set_metar(MetarData(
            icao="ESSA", time=0, visibility_m=9999, qnh_hpa=1013,
            temperature_c=15, dewpoint_c=10,
            wind=WindData(direction=180, speed_kn=10),
        ))
        wind = mgr.get_wind("ESSA")
        assert wind is not None
        assert wind.direction == 180

    def test_get_wind_unknown(self):
        from managers.weather import WeatherManager
        mgr = WeatherManager()
        assert mgr.get_wind("XXXX") is None

    def test_get_qnh_default(self):
        from managers.weather import WeatherManager
        mgr = WeatherManager()
        assert mgr.get_qnh("XXXX") == 1013.25

    def test_calculate_runway_wind(self):
        from runtime.weather import MetarData, WindData
        from managers.weather import WeatherManager
        mgr = WeatherManager()
        mgr.set_metar(MetarData(
            icao="ESSA", time=0, visibility_m=9999, qnh_hpa=1013,
            temperature_c=15, dewpoint_c=10,
            wind=WindData(direction=270, speed_kn=20),
        ))
        cross, head = mgr.calculate_runway_wind("ESSA", 270)
        assert cross == pytest.approx(0, abs=0.5)
        assert head == pytest.approx(20, abs=0.5)

    def test_clear(self):
        from runtime.weather import MetarData, WindData
        from managers.weather import WeatherManager
        mgr = WeatherManager()
        mgr.set_metar(MetarData(
            icao="ESSA", time=0, visibility_m=9999, qnh_hpa=1013,
            temperature_c=15, dewpoint_c=10,
            wind=WindData(direction=0, speed_kn=0),
        ))
        mgr.clear("ESSA")
        assert mgr.get("ESSA") is None
        assert mgr.airport_count == 0


# ---------------------------------------------------------------------------
# SectorManager
# ---------------------------------------------------------------------------

ESSA_CTR_POLY = Polygon([
    (16.0, 59.0), (18.0, 59.0), (18.0, 60.0), (16.0, 60.0), (16.0, 59.0)
])


class TestSectorManager:
    def test_add_and_find_sector(self):
        from runtime.sector import AirspaceVolume
        from managers.sector import SectorManager
        mgr = SectorManager()
        vol = AirspaceVolume(
            sector_id=1, floor_ft=0, ceiling_ft=24500, polygon=ESSA_CTR_POLY,
        )
        mgr.add_sector(vol)
        sid = mgr.find_sector_for_position(59.5, 17.0, 10000)
        assert sid == 1

    def test_find_sector_outside(self):
        from runtime.sector import AirspaceVolume
        from managers.sector import SectorManager
        mgr = SectorManager()
        mgr.add_sector(AirspaceVolume(
            sector_id=1, floor_ft=0, ceiling_ft=24500, polygon=ESSA_CTR_POLY,
        ))
        sid = mgr.find_sector_for_position(61.0, 20.0, 10000)
        assert sid is None

    def test_find_sector_altitude_out_of_range(self):
        from runtime.sector import AirspaceVolume
        from managers.sector import SectorManager
        mgr = SectorManager()
        mgr.add_sector(AirspaceVolume(
            sector_id=1, floor_ft=0, ceiling_ft=10000, polygon=ESSA_CTR_POLY,
        ))
        sid = mgr.find_sector_for_position(59.5, 17.0, 15000)
        assert sid is None

    def test_assign_aircraft_to_sector(self):
        from runtime.sector import AirspaceVolume
        from managers.sector import SectorManager
        mgr = SectorManager()
        mgr.add_sector(AirspaceVolume(
            sector_id=1, floor_ft=0, ceiling_ft=50000, polygon=ESSA_CTR_POLY,
        ))
        mgr.assign_aircraft_to_sector("SAS123", 1)
        assert mgr.get_sector_of_aircraft("SAS123") == 1
        assert "SAS123" in mgr.get_aircraft_in_sector(1)

    def test_update_aircraft_position_changes_sector(self):
        from runtime.sector import AirspaceVolume
        from managers.sector import SectorManager
        outside_poly = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
        mgr = SectorManager()
        mgr.add_sector(AirspaceVolume(
            sector_id=1, floor_ft=0, ceiling_ft=50000, polygon=outside_poly,
        ))
        sid = mgr.update_aircraft_position("SAS123", 59.5, 17.0, 10000)
        assert sid == -1  # not in any sector

    def test_set_controller_and_frequency(self):
        from runtime.sector import AirspaceVolume
        from managers.sector import SectorManager
        mgr = SectorManager()
        mgr.add_sector(AirspaceVolume(
            sector_id=1, floor_ft=0, ceiling_ft=50000, polygon=ESSA_CTR_POLY,
        ))
        mgr.set_controller(1, "ESSA_APP")
        mgr.set_frequency(1, 124.0)
        assignments = mgr.get_all_assignments()
        assert assignments[0].controller_callsign == "ESSA_APP"
        assert assignments[0].frequency_mhz == 124.0

    def test_remove_sector(self):
        from runtime.sector import AirspaceVolume
        from managers.sector import SectorManager
        mgr = SectorManager()
        mgr.add_sector(AirspaceVolume(
            sector_id=1, floor_ft=0, ceiling_ft=50000, polygon=ESSA_CTR_POLY,
        ))
        mgr.assign_aircraft_to_sector("SAS123", 1)
        mgr.remove_sector(1)
        assert mgr.get_sector_of_aircraft("SAS123") is None
        assert len(mgr.get_all_sectors()) == 0

    def test_event_on_sector_change(self):
        from pubsub import EventBus, EventType
        from runtime.sector import AirspaceVolume
        from managers.sector import SectorManager
        bus = EventBus()
        events = []
        bus.subscribe_all(lambda e: events.append(e))
        mgr = SectorManager(event_bus=bus)
        mgr.add_sector(AirspaceVolume(
            sector_id=1, floor_ft=0, ceiling_ft=50000, polygon=ESSA_CTR_POLY,
        ))
        mgr.assign_aircraft_to_sector("SAS123", 1)
        types = [e.type for e in events]
        assert EventType.AIRCRAFT_ENTERED_SECTOR in types


# ---------------------------------------------------------------------------
# ConflictManager
# ---------------------------------------------------------------------------

class TestConflictManager:
    def test_no_conflict_distant_aircraft(self):
        from runtime.aircraft import ActiveAircraft, PositionData, MotionData
        from managers.conflict import ConflictManager
        mgr = ConflictManager()
        a = ActiveAircraft(
            callsign="AC1",
            position=PositionData(lat=59.0, lon=17.0, alt_msl_ft=10000),
            motion=MotionData(groundspeed_kn=250),
        )
        b = ActiveAircraft(
            callsign="AC2",
            position=PositionData(lat=60.0, lon=18.0, alt_msl_ft=10000),
            motion=MotionData(groundspeed_kn=250),
        )
        assert mgr.check_pair(a, b) is None

    def test_conflict_close_aircraft(self):
        from runtime.aircraft import ActiveAircraft, PositionData, MotionData
        from managers.conflict import ConflictManager
        mgr = ConflictManager(lateral_separation_nm=5, vertical_separation_ft=1000)
        a = ActiveAircraft(
            callsign="AC1",
            position=PositionData(lat=59.5, lon=17.0, alt_msl_ft=10000),
            motion=MotionData(groundspeed_kn=250),
        )
        b = ActiveAircraft(
            callsign="AC2",
            position=PositionData(lat=59.505, lon=17.001, alt_msl_ft=10050),
            motion=MotionData(groundspeed_kn=250),
        )
        conflict = mgr.check_pair(a, b)
        assert conflict is not None
        assert conflict.aircraft_a == "AC1"
        assert conflict.aircraft_b == "AC2"
        assert conflict.severity in ("warning", "critical")
        assert conflict.lateral_distance_nm < 5

    def test_vertical_separation_ok(self):
        from runtime.aircraft import ActiveAircraft, PositionData, MotionData
        from managers.conflict import ConflictManager
        mgr = ConflictManager(lateral_separation_nm=5, vertical_separation_ft=1000)
        a = ActiveAircraft(
            callsign="AC1",
            position=PositionData(lat=59.5, lon=17.0, alt_msl_ft=10000),
        )
        b = ActiveAircraft(
            callsign="AC2",
            position=PositionData(lat=59.5, lon=17.0, alt_msl_ft=12000),
        )
        assert mgr.check_pair(a, b) is None

    def test_check_all_no_conflicts(self):
        from runtime.aircraft import ActiveAircraft, PositionData
        from managers.conflict import ConflictManager
        mgr = ConflictManager()
        a = ActiveAircraft(callsign="AC1", position=PositionData(lat=59.0, lon=17.0))
        b = ActiveAircraft(callsign="AC2", position=PositionData(lat=61.0, lon=20.0))
        conflicts = mgr.check_all([a, b])
        assert len(conflicts) == 0

    def test_check_all_with_conflicts(self):
        from runtime.aircraft import ActiveAircraft, PositionData, MotionData
        from managers.conflict import ConflictManager
        mgr = ConflictManager(lateral_separation_nm=5, vertical_separation_ft=1000)
        a = ActiveAircraft(
            callsign="AC1",
            position=PositionData(lat=59.5, lon=17.0, alt_msl_ft=10000),
            motion=MotionData(groundspeed_kn=250),
        )
        b = ActiveAircraft(
            callsign="AC2",
            position=PositionData(lat=59.505, lon=17.001, alt_msl_ft=10050),
            motion=MotionData(groundspeed_kn=250),
        )
        conflicts = mgr.check_all([a, b])
        assert len(conflicts) == 1

    def test_event_on_conflict(self):
        from pubsub import EventBus, EventType
        from runtime.aircraft import ActiveAircraft, PositionData, MotionData
        from managers.conflict import ConflictManager
        bus = EventBus()
        events = []
        bus.subscribe_all(lambda e: events.append(e))
        mgr = ConflictManager(
            event_bus=bus, lateral_separation_nm=5, vertical_separation_ft=1000,
        )
        a = ActiveAircraft(
            callsign="AC1",
            position=PositionData(lat=59.5, lon=17.0, alt_msl_ft=10000),
            motion=MotionData(groundspeed_kn=250),
        )
        b = ActiveAircraft(
            callsign="AC2",
            position=PositionData(lat=59.505, lon=17.001, alt_msl_ft=10050),
            motion=MotionData(groundspeed_kn=250),
        )
        mgr.check_all([a, b])
        types = [e.type for e in events]
        assert EventType.CONFLICT_DETECTED in types

    def test_conflict_resolved_event(self):
        from pubsub import EventBus, EventType
        from runtime.aircraft import ActiveAircraft, PositionData, MotionData
        from managers.conflict import ConflictManager
        bus = EventBus()
        events = []
        bus.subscribe_all(lambda e: events.append(e))
        mgr = ConflictManager(
            event_bus=bus, lateral_separation_nm=5, vertical_separation_ft=1000,
        )
        a = ActiveAircraft(
            callsign="AC1",
            position=PositionData(lat=59.5, lon=17.0, alt_msl_ft=10000),
            motion=MotionData(groundspeed_kn=250),
        )
        b = ActiveAircraft(
            callsign="AC2",
            position=PositionData(lat=59.505, lon=17.001, alt_msl_ft=10050),
            motion=MotionData(groundspeed_kn=250),
        )
        mgr.check_all([a, b])
        # Move them apart
        a.position.lat = 61.0
        a.position.lon = 20.0
        b.position.lat = 50.0
        b.position.lon = 10.0
        mgr.check_all([a, b])
        types = [e.type for e in events]
        assert EventType.CONFLICT_DETECTED in types
        assert EventType.CONFLICT_RESOLVED in types


# ---------------------------------------------------------------------------
# WorldEngine integration
# ---------------------------------------------------------------------------

class TestWorldEngine:
    def test_initialize(self):
        from engine import WorldEngine
        engine = WorldEngine()
        engine.initialize()
        summary = engine.get_state_summary()
        assert summary["initialized"] is True

    def test_process_telemetry(self):
        from engine import WorldEngine
        engine = WorldEngine()
        frame = {
            "callsign": "SAS123",
            "position": {"lat": 59.65, "lon": 17.92, "alt_msl": 3000, "heading": 90},
            "motion": {"groundspeed": 250, "vertical_speed": 0, "on_ground": False},
            "radios": {"squawk": "1200"},
            "ts": 1000,
        }
        ac = engine.process_telemetry(frame)
        assert ac is not None
        assert ac.callsign == "SAS123"
        assert engine.aircraft_manager.count == 1

    def test_batch_telemetry(self):
        from engine import WorldEngine
        engine = WorldEngine()
        frames = [
            {"callsign": f"AC{i}", "position": {}, "motion": {}, "ts": float(i)}
            for i in range(5)
        ]
        results = engine.process_batch_telemetry(frames)
        assert len(results) == 5
        assert engine.aircraft_manager.count == 5

    def test_set_flight_plan(self):
        from engine import WorldEngine
        engine = WorldEngine()
        engine.process_telemetry({
            "callsign": "SAS123", "position": {}, "motion": {}, "ts": 0,
        })
        engine.set_flight_plan("SAS123", {
            "departure": "ESSA",
            "arrival": "EKCH",
            "route": ["ARN", "NILUG", "BEDAK"],
            "cruise_alt_ft": 37000,
            "cruise_speed_kn": 450,
            "aircraft_type": "B738",
        })
        ac = engine.aircraft_manager.get("SAS123")
        assert ac.flight_plan is not None
        assert ac.flight_plan.departure == "ESSA"
        assert ac.flight_plan.arrival == "EKCH"

    def test_set_aircraft_state(self):
        from engine import WorldEngine
        from runtime.aircraft import AircraftState
        engine = WorldEngine()
        engine.process_telemetry({
            "callsign": "SAS123", "position": {}, "motion": {}, "ts": 0,
        })
        engine.set_aircraft_state("SAS123", "taxi")
        ac = engine.aircraft_manager.get("SAS123")
        assert ac.state == AircraftState.TAXI
        assert ac.previous_state == AircraftState.CRUISE

    def test_get_aircraft_state(self):
        from engine import WorldEngine
        engine = WorldEngine()
        engine.process_telemetry({
            "callsign": "SAS123",
            "position": {"lat": 59.65, "lon": 17.92, "alt_msl": 3000},
            "motion": {"groundspeed": 250},
            "ts": 0,
        })
        state = engine.get_aircraft_state("SAS123")
        assert state is not None
        assert state["callsign"] == "SAS123"
        assert state["position"]["lat"] == 59.65
        assert engine.get_aircraft_state("GHOST") is None

    def test_weather_integration(self):
        from engine import WorldEngine
        engine = WorldEngine()
        engine.set_metar_from_dict({
            "icao": "ESSA",
            "time": 1000.0,
            "wind": {"direction": 270, "speed_kn": 15},
            "visibility_m": 10000,
            "qnh_hpa": 1013,
            "temperature_c": 10,
            "dewpoint_c": 5,
            "clouds": [],
        })
        wind = engine.weather_manager.get_wind("ESSA")
        assert wind is not None
        assert wind.direction == 270

    def test_load_airport_and_sector(self):
        from engine import WorldEngine
        engine = WorldEngine()
        engine.load_airport_from_db_model(
            "ESSA", elevation_ft=137, magnetic_var=5.5,
            runways=[{"identifier": "01L/19R", "heading": 9.1, "length_ft": 10830}],
        )
        assert engine.airport_manager.get("ESSA") is not None
        engine.load_sector_from_db_model(
            sector_id=1, floor_ft=0, ceiling_ft=24500,
            polygon_coords=[[16, 59], [18, 59], [18, 60], [16, 60], [16, 59]],
            identifier="ESSS_CTA",
        )
        assert len(engine.sector_manager.get_all_sectors()) == 1

    def test_full_cycle(self):
        from engine import WorldEngine
        from shapely.geometry import Polygon

        engine = WorldEngine()
        engine.load_airport_from_db_model(
            "ESSA", elevation_ft=137, magnetic_var=5.5,
            runways=[
                {"identifier": "01L/19R", "heading": 9.1, "length_ft": 10830},
                {"identifier": "08/26", "heading": 76.0, "length_ft": 8202},
            ],
        )
        engine.load_sector_from_db_model(
            sector_id=1, floor_ft=0, ceiling_ft=50000,
            polygon_coords=[[16, 59], [18, 59], [18, 60], [16, 60], [16, 59]],
            identifier="ESSS_CTA",
        )
        engine.set_metar_from_dict({
            "icao": "ESSA", "time": 0, "wind": {"direction": 10, "speed_kn": 10},
            "visibility_m": 9999, "qnh_hpa": 1013, "temperature_c": 10, "dewpoint_c": 5,
            "clouds": [],
        })
        engine.determine_airport_runways("ESSA")
        engine.process_telemetry({
            "callsign": "SAS123",
            "position": {"lat": 59.65, "lon": 17.92, "alt_msl": 3000, "heading": 90},
            "motion": {"groundspeed": 250, "vertical_speed": 0, "on_ground": False},
            "radios": {"squawk": "1200"},
            "ts": 0,
        })
        state = engine.get_aircraft_state("SAS123")
        assert state is not None
        assert state["sector_id"] == 1
        engine.tick()
        summary = engine.get_state_summary()
        assert summary["aircraft_count"] == 1
        assert summary["tick_count"] == 1
