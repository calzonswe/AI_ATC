import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pytest
from shapely.geometry import Point

from frequency_manager import (
    ControllerFacility,
    FrequencyManager,
    _haversine_nm,
)


ESSA_LAT = 59.6494
ESSA_LON = 17.9231

ESSA_FREQUENCIES = [
    {"type": "GROUND", "frequency_mhz": 121.800, "callsign": "Arlanda Ground"},
    {"type": "TOWER", "frequency_mhz": 118.300, "callsign": "Arlanda Tower"},
    {"type": "DEPARTURE", "frequency_mhz": 125.200, "callsign": "Arlanda Departure"},
    {"type": "APPROACH", "frequency_mhz": 124.000, "callsign": "Arlanda Approach"},
    {"type": "ATIS", "frequency_mhz": 128.425, "callsign": "Arlanda ATIS"},
]


@pytest.fixture
def manager() -> FrequencyManager:
    mgr = FrequencyManager()
    mgr.load_airport_frequencies("ESSA", ESSA_LAT, ESSA_LON, ESSA_FREQUENCIES)
    return mgr


# ──────────────────────────────────────────────
# _haversine_nm
# ──────────────────────────────────────────────

class TestHaversine:
    def test_zero_distance(self):
        assert _haversine_nm(59.65, 17.92, 59.65, 17.92) == 0.0

    def test_known_distance(self):
        dist = _haversine_nm(59.65, 17.92, 59.80, 17.92)
        assert dist == pytest.approx(9.0, abs=0.5)

    def test_symmetric(self):
        d1 = _haversine_nm(59.65, 17.92, 60.0, 18.0)
        d2 = _haversine_nm(60.0, 18.0, 59.65, 17.92)
        assert d1 == pytest.approx(d2)


# ──────────────────────────────────────────────
# ControllerFacility
# ──────────────────────────────────────────────

class TestControllerFacility:
    def test_create(self):
        fac = ControllerFacility(
            facility_type="GROUND",
            controller_callsign="ESSA_GND",
            frequency_mhz=121.8,
            airport_icao="ESSA",
            latitude=59.65,
            longitude=17.92,
            range_nm=5.0,
        )
        assert fac.facility_type == "GROUND"
        assert fac.controller_callsign == "ESSA_GND"
        assert fac.frequency_mhz == 121.8


# ──────────────────────────────────────────────
# FrequencyManager — Basic Setup
# ──────────────────────────────────────────────

class TestFrequencyManagerSetup:
    def test_empty_manager_returns_none(self):
        mgr = FrequencyManager()
        result = mgr.resolve_frequency(121.8, Point(ESSA_LON, ESSA_LAT))
        assert result is None

    def test_add_facility(self, manager):
        fac = manager.resolve_frequency(121.8, Point(ESSA_LON, ESSA_LAT))
        assert fac is not None
        assert fac.facility_type == "GROUND"
        assert fac.controller_callsign == "Arlanda Ground"
        assert fac.frequency_mhz == 121.8
        assert fac.airport_icao == "ESSA"

    def test_remove_facility(self, manager):
        manager.remove_facility(121.8, "Arlanda Ground")
        result = manager.resolve_frequency(121.8, Point(ESSA_LON, ESSA_LAT))
        assert result is None

    def test_clear_facilities(self, manager):
        manager.clear_facilities()
        for f in [121.8, 118.3, 125.2, 124.0, 128.425]:
            assert manager.resolve_frequency(f, Point(ESSA_LON, ESSA_LAT)) is None

    def test_add_duplicate_facility(self, manager):
        manager.add_facility(ControllerFacility(
            facility_type="GROUND",
            controller_callsign="ESSA_GND_2",
            frequency_mhz=121.800,
            airport_icao="ESSA",
            latitude=ESSA_LAT,
            longitude=ESSA_LON,
            range_nm=5.0,
        ))
        fac = manager.resolve_frequency(121.8, Point(ESSA_LON, ESSA_LAT))
        assert fac is not None
        assert fac.controller_callsign in ("Arlanda Ground", "ESSA_GND_2")


# ──────────────────────────────────────────────
# FrequencyManager — Frequency Resolution
# ──────────────────────────────────────────────

class TestFrequencyResolution:
    def test_tune_121_800_at_essa_returns_ground(self, manager):
        fac = manager.resolve_frequency(121.8, Point(ESSA_LON, ESSA_LAT))
        assert fac is not None
        assert fac.facility_type == "GROUND"
        assert "Ground" in fac.controller_callsign

    def test_tune_118_300_at_essa_returns_tower(self, manager):
        fac = manager.resolve_frequency(118.3, Point(ESSA_LON, ESSA_LAT))
        assert fac is not None
        assert fac.facility_type == "TOWER"

    def test_tune_125_200_at_essa_returns_departure(self, manager):
        fac = manager.resolve_frequency(125.2, Point(ESSA_LON, ESSA_LAT))
        assert fac is not None
        assert fac.facility_type == "DEPARTURE"

    def test_tune_124_000_at_essa_returns_approach(self, manager):
        fac = manager.resolve_frequency(124.0, Point(ESSA_LON, ESSA_LAT))
        assert fac is not None
        assert fac.facility_type == "APPROACH"

    def test_tune_128_425_at_essa_returns_atis(self, manager):
        fac = manager.resolve_frequency(128.425, Point(ESSA_LON, ESSA_LAT))
        assert fac is not None
        assert fac.facility_type == "ATIS"

    def test_tune_unassigned_frequency_returns_none(self, manager):
        fac = manager.resolve_frequency(133.0, Point(ESSA_LON, ESSA_LAT))
        assert fac is None

    def test_tune_121_800_far_from_essa_returns_none(self, manager):
        nav_center = Point(-74.006, 40.7128)
        fac = manager.resolve_frequency(121.8, nav_center)
        assert fac is None, "Should not reach ESSA Ground from New York"


# ──────────────────────────────────────────────
# FrequencyManager — Range / Proximity
# ──────────────────────────────────────────────

class TestRangeAndProximity:
    def test_inside_ground_range(self, manager):
        on_apron = Point(ESSA_LON + 0.01, ESSA_LAT + 0.01)
        fac = manager.resolve_frequency(121.8, on_apron)
        assert fac is not None
        assert fac.facility_type == "GROUND"

    def test_outside_ground_range_inside_tower_range(self, manager):
        lat = 59.78
        lon = 18.0
        ground_dist = _haversine_nm(ESSA_LAT, ESSA_LON, lat, lon)
        assert ground_dist > 5.0
        assert ground_dist < 30.0
        position = Point(lon, lat)
        fac = manager.resolve_frequency(121.8, position)
        assert fac is None, "Ground range exceeded"

    def test_atis_has_large_range(self, manager):
        position = Point(18.5, 59.8)
        fac = manager.resolve_frequency(128.425, position)
        assert fac is not None
        assert fac.facility_type == "ATIS"

    def test_departure_range(self, manager):
        position = Point(18.3, 59.9)
        fac = manager.resolve_frequency(125.2, position)
        assert fac is not None
        assert fac.facility_type == "DEPARTURE"

    def test_outside_all_ranges(self, manager):
        position = Point(25.0, 60.0)
        for freq in [121.8, 118.3, 125.2, 124.0]:
            fac = manager.resolve_frequency(freq, position)
            assert fac is None, f"Frequency {freq} should be out of range"


# ──────────────────────────────────────────────
# FrequencyManager — Overlap Resolution
# ──────────────────────────────────────────────

class TestFrequencyOverlap:
    def test_same_freq_closest_wins(self, manager):
        manager.add_facility(ControllerFacility(
            facility_type="TOWER",
            controller_callsign="ESSA_TWR",
            frequency_mhz=121.800,
            airport_icao="ESSA",
            latitude=ESSA_LAT + 0.5,
            longitude=ESSA_LON,
            range_nm=50.0,
        ))
        near_ground = Point(ESSA_LON, ESSA_LAT)
        fac = manager.resolve_frequency(121.8, near_ground)
        assert fac is not None
        assert fac.controller_callsign == "Arlanda Ground"

    def test_far_from_ground_near_tower_gets_tower(self, manager):
        manager.add_facility(ControllerFacility(
            facility_type="TOWER",
            controller_callsign="ESSA_TWR",
            frequency_mhz=121.800,
            airport_icao="ESSA",
            latitude=ESSA_LAT + 0.5,
            longitude=ESSA_LON,
            range_nm=50.0,
        ))
        near_tower = Point(ESSA_LON, ESSA_LAT + 0.5)
        fac = manager.resolve_frequency(121.8, near_tower)
        assert fac is not None
        assert fac.controller_callsign == "ESSA_TWR"

    def test_equal_distance_first_added_used(self, manager):
        lat_offset = 0.1
        lon_offset = 0.1
        manager.add_facility(ControllerFacility(
            facility_type="TOWER",
            controller_callsign="ESSA_TWR_DUP",
            frequency_mhz=121.800,
            airport_icao="ESSA",
            latitude=ESSA_LAT + lat_offset,
            longitude=ESSA_LON + lon_offset,
            range_nm=30.0,
        ))
        d1 = _haversine_nm(ESSA_LAT, ESSA_LON, ESSA_LAT + lat_offset, ESSA_LON + lon_offset)
        d0 = 0.0
        assert d1 > d0
        fac = manager.resolve_frequency(121.8, Point(ESSA_LON, ESSA_LAT))
        assert fac is not None
        assert fac.controller_callsign == "Arlanda Ground"

    def test_closest_facility_of_same_type(self, manager):
        manager.add_facility(ControllerFacility(
            facility_type="GROUND",
            controller_callsign="ARN_GND_2",
            frequency_mhz=121.800,
            airport_icao="ARN2",
            latitude=ESSA_LAT + 2.0,
            longitude=ESSA_LON,
            range_nm=100.0,
        ))
        d2 = _haversine_nm(ESSA_LAT, ESSA_LON, ESSA_LAT + 2.0, ESSA_LON)
        d0 = _haversine_nm(ESSA_LAT, ESSA_LON, ESSA_LAT, ESSA_LON)
        assert d2 > d0
        fac = manager.resolve_frequency(121.8, Point(ESSA_LON, ESSA_LAT))
        assert fac is not None
        assert fac.controller_callsign == "Arlanda Ground"


# ──────────────────────────────────────────────
# FrequencyManager — Ownership Tracking
# ──────────────────────────────────────────────

class TestOwnershipTracking:
    def test_initial_owner_none(self, manager):
        assert manager.get_owner("SAS901") is None

    def test_set_owner(self, manager):
        manager.set_owner("SAS901", "ESSA_GND")
        assert manager.get_owner("SAS901") == "ESSA_GND"

    def test_release_owner(self, manager):
        manager.set_owner("SAS901", "ESSA_GND")
        released = manager.release_owner("SAS901")
        assert released == "ESSA_GND"
        assert manager.get_owner("SAS901") is None

    def test_release_nonexistent_owner(self, manager):
        released = manager.release_owner("NONEXIST")
        assert released is None

    def test_overwrite_owner(self, manager):
        manager.set_owner("SAS901", "ESSA_GND")
        manager.set_owner("SAS901", "ESSA_TWR")
        assert manager.get_owner("SAS901") == "ESSA_TWR"

    def test_owner_does_not_affect_frequency_resolution(self, manager):
        manager.set_owner("SAS901", "ESSA_GND")
        fac = manager.resolve_frequency(118.3, Point(ESSA_LON, ESSA_LAT))
        assert fac is not None
        assert fac.facility_type == "TOWER"


# ──────────────────────────────────────────────
# FrequencyManager — Bulk Loading
# ──────────────────────────────────────────────

class TestBulkLoading:
    def test_load_airport_frequencies(self):
        mgr = FrequencyManager()
        mgr.load_airport_frequencies("ESSA", ESSA_LAT, ESSA_LON, ESSA_FREQUENCIES)
        assert mgr.resolve_frequency(121.8, Point(ESSA_LON, ESSA_LAT)) is not None
        assert mgr.resolve_frequency(118.3, Point(ESSA_LON, ESSA_LAT)) is not None
        assert mgr.resolve_frequency(125.2, Point(ESSA_LON, ESSA_LAT)) is not None
        assert mgr.resolve_frequency(124.0, Point(ESSA_LON, ESSA_LAT)) is not None
        assert mgr.resolve_frequency(128.425, Point(ESSA_LON, ESSA_LAT)) is not None

    def test_load_airport_frequencies_skips_bad_data(self):
        mgr = FrequencyManager()
        bad_data = [
            {"type": "", "frequency_mhz": 121.8},
            {"type": "GROUND", "frequency_mhz": 0.0},
            {"type": "", "frequency_mhz": 0.0},
        ]
        mgr.load_airport_frequencies("TEST", 0, 0, bad_data)
        assert mgr.resolve_frequency(121.8, Point(0, 0)) is None

    def test_load_controller_frequencies(self):
        mgr = FrequencyManager()
        controllers = [
            {
                "type": "CENTER",
                "callsign": "ESSA_CTR",
                "frequency_mhz": 135.5,
                "latitude": 60.0,
                "longitude": 18.0,
                "range_nm": 200,
            },
            {
                "type": "APPROACH",
                "callsign": "ESSA_APP",
                "frequency_mhz": 124.0,
                "latitude": ESSA_LAT,
                "longitude": ESSA_LON,
                "range_nm": 50,
            },
        ]
        mgr.load_controller_frequencies(controllers)
        assert mgr.resolve_frequency(135.5, Point(18.0, 60.0)) is not None
        assert mgr.resolve_frequency(124.0, Point(ESSA_LON, ESSA_LAT)) is not None

    def test_load_controller_frequencies_skips_bad_data(self):
        mgr = FrequencyManager()
        bad = [
            {"type": "CENTER", "callsign": "", "frequency_mhz": 135.5},
            {"type": "", "callsign": "TEST", "frequency_mhz": 135.5},
            {"frequency_mhz": 0.0, "callsign": "TEST", "type": "CENTER"},
        ]
        mgr.load_controller_frequencies(bad)
        assert mgr.find_facilities() == []

    def test_load_airport_names_controllers(self):
        mgr = FrequencyManager()
        mgr.load_airport_frequencies("ESSA", ESSA_LAT, ESSA_LON, [
            {"type": "GROUND", "frequency_mhz": 121.8},
        ])
        fac = mgr.resolve_frequency(121.8, Point(ESSA_LON, ESSA_LAT))
        assert fac is not None
        assert fac.controller_callsign == "ESSA_GROUND"


# ──────────────────────────────────────────────
# FrequencyManager — find_facilities
# ──────────────────────────────────────────────

class TestFindFacilities:
    def test_find_all(self, manager):
        all_facs = manager.find_facilities()
        assert len(all_facs) == 5

    def test_find_by_type(self, manager):
        towers = manager.find_facilities(facility_type="TOWER")
        assert len(towers) == 1
        assert towers[0].controller_callsign == "Arlanda Tower"

    def test_find_by_airport(self, manager):
        essa_facs = manager.find_facilities(airport_icao="ESSA")
        assert len(essa_facs) == 5

    def test_find_by_type_and_airport(self, manager):
        facs = manager.find_facilities(facility_type="ATIS", airport_icao="ESSA")
        assert len(facs) == 1

    def test_find_nonexistent_type(self, manager):
        assert manager.find_facilities(facility_type="CENTER") == []


# ──────────────────────────────────────────────
# Integration — Complete Scenario: Pilot tunes ESSA Ground
# ──────────────────────────────────────────────

class TestIntegration:
    def test_essa_ground_pilot_transmission(self, manager):
        callsign = "SAS901"
        tuned_freq = 121.800
        aircraft_position = Point(ESSA_LON + 0.005, ESSA_LAT + 0.005)

        fac = manager.resolve_frequency(tuned_freq, aircraft_position)
        assert fac is not None
        assert fac.facility_type == "GROUND"
        assert fac.airport_icao == "ESSA"
        assert fac.controller_callsign == "Arlanda Ground"

        manager.set_owner(callsign, fac.controller_callsign)
        assert manager.get_owner(callsign) == "Arlanda Ground"

    def test_essa_tower_handoff_from_ground(self, manager):
        callsign = "SAS901"

        manager.set_owner(callsign, "Arlanda Ground")
        manager.release_owner(callsign)
        manager.set_owner(callsign, "Arlanda Tower")

        assert manager.get_owner(callsign) == "Arlanda Tower"

        fac = manager.resolve_frequency(118.3, Point(ESSA_LON, ESSA_LAT))
        assert fac is not None
        assert fac.facility_type == "TOWER"

    def test_tune_radio_silence(self, manager):
        fac = manager.resolve_frequency(133.0, Point(ESSA_LON, ESSA_LAT))
        assert fac is None
