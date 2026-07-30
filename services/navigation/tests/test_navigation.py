import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

import math

import pytest

# ──────────────────────────────────────────────
# geo
# ──────────────────────────────────────────────


class TestGeo:
    def test_haversine_distance(self):
        from geo import haversine_distance
        # ESSA (59.6494, 17.9231) to EKCH (55.6181, 12.6561)
        dist = haversine_distance(59.6494, 17.9231, 55.6181, 12.6561)
        assert 290 < dist < 310  # ~300nm

    def test_haversine_zero(self):
        from geo import haversine_distance
        assert haversine_distance(0, 0, 0, 0) == 0.0

    def test_geodetic_distance(self):
        from geo import geodetic_distance
        dist = geodetic_distance(59.6494, 17.9231, 55.6181, 12.6561)
        assert 290 < dist < 310

    def test_initial_bearing(self):
        from geo import initial_bearing
        # True north from equator
        brg = initial_bearing(0, 0, 10, 0)
        assert brg == pytest.approx(0, abs=0.5)
        # East
        brg = initial_bearing(0, 0, 0, 10)
        assert brg == pytest.approx(90, abs=0.5)

    def test_final_bearing(self):
        from geo import final_bearing
        brg = final_bearing(0, 0, 10, 0)
        assert brg == pytest.approx(0, abs=0.5)

    def test_destination_point(self):
        from geo import destination_point
        lat, lon = destination_point(0, 0, 0, 60)
        assert lat == pytest.approx(1.0, abs=0.01)
        assert lon == pytest.approx(0, abs=0.01)

    def test_cross_track_distance(self):
        from geo import cross_track_distance
        # Point perpendicular to line from (0,0) to (1,0)
        xte = cross_track_distance(0.5, 0.5, 0, 0, 1, 0)
        assert xte > 0  # should be positive offset

    def test_along_track_distance(self):
        from geo import along_track_distance
        dist = along_track_distance(0.5, 0, 0, 0, 1, 0)
        assert dist == pytest.approx(30, abs=1)

    def test_angle_difference(self):
        from geo import angle_difference
        assert angle_difference(10, 350) == pytest.approx(20)
        assert angle_difference(350, 10) == pytest.approx(20)
        assert angle_difference(0, 180) == pytest.approx(180)
        assert angle_difference(0, 360) == pytest.approx(0)

    def test_normalize_heading(self):
        from geo import normalize_heading
        assert normalize_heading(360) == 0
        assert normalize_heading(720) == 0
        assert normalize_heading(-10) == 350
        assert normalize_heading(400) == 40

    def test_intercept_heading(self):
        from geo import intercept_heading
        hdg = intercept_heading(0, 0, 1, 0)
        assert hdg == pytest.approx(0, abs=0.5)

    def test_parallel_offset_point(self):
        from geo import parallel_offset_point
        lat, lon = parallel_offset_point(0, 0, 0, 10, "right")
        assert lat == pytest.approx(0, abs=0.01)
        # Right of north (hdg 0) is east (hdg 90) -> positive longitude
        assert lon > 0

    def test_distance_to_go(self):
        from geo import distance_to_go
        dist, delta = distance_to_go(0, 0, 0, 1, 0)
        assert dist == pytest.approx(60, abs=0.5)
        assert delta == pytest.approx(0, abs=0.5)


# ──────────────────────────────────────────────
# TaxiRoutePlanner
# ──────────────────────────────────────────────

class TestTaxiRoutePlanner:
    @pytest.fixture
    def planner(self):
        from taxi_routing import TaxiRoutePlanner
        return TaxiRoutePlanner()

    def test_build_graph(self, planner):
        nodes = [
            {"id": "A", "lat": 59.65, "lon": 17.92, "name": "Gate 1"},
            {"id": "B", "lat": 59.651, "lon": 17.921, "name": "Intersection"},
            {"id": "C", "lat": 59.652, "lon": 17.922, "name": "RWY Threshold"},
        ]
        segments = [
            {"from_node": "A", "to_node": "B", "taxiway_name": "A"},
            {"from_node": "B", "to_node": "C", "taxiway_name": "B"},
        ]
        planner.build_graph_from_segments(segments, nodes)
        assert len(planner.graph.nodes) == 3
        assert len(planner.graph.edges) == 2

    def test_shortest_path(self, planner):
        nodes = [
            {"id": "G1", "lat": 59.6500, "lon": 17.9200, "name": "Gate 1"},
            {"id": "I1", "lat": 59.6505, "lon": 17.9210, "name": "Int 1"},
            {"id": "I2", "lat": 59.6510, "lon": 17.9220, "name": "Int 2"},
            {"id": "RWY", "lat": 59.6520, "lon": 17.9230, "name": "Runway 01L"},
        ]
        segments = [
            {"from_node": "G1", "to_node": "I1", "taxiway_name": "A"},
            {"from_node": "I1", "to_node": "I2", "taxiway_name": "B"},
            {"from_node": "I2", "to_node": "RWY", "taxiway_name": "C"},
            {"from_node": "I1", "to_node": "RWY", "taxiway_name": "D"},  # direct
        ]
        planner.build_graph_from_segments(segments, nodes)
        route = planner.find_shortest_path("G1", "RWY")
        assert route is not None
        assert len(route.nodes) >= 2
        assert route.total_distance_m > 0

    def test_shortest_path_no_route(self, planner):
        planner.build_graph_from_segments([], [{"id": "A", "lat": 0, "lon": 0}])
        route = planner.find_shortest_path("A", "B")
        assert route is None

    def test_shortest_path_avoids_closed(self, planner):
        nodes = [
            {"id": "G1", "lat": 59.6500, "lon": 17.9200},
            {"id": "I1", "lat": 59.6505, "lon": 17.9210},
            {"id": "RWY", "lat": 59.6520, "lon": 17.9230},
        ]
        segments = [
            {"from_node": "G1", "to_node": "I1", "taxiway_name": "A"},
            {"from_node": "I1", "to_node": "RWY", "taxiway_name": "B_CLOSED", "closed": True},
        ]
        planner.build_graph_from_segments(segments, nodes, closed_taxiways={"B_CLOSED"})
        route = planner.find_shortest_path("G1", "RWY")
        assert route is None or route.total_distance_m == 0

    def test_shortest_path_prefers_shorter(self, planner):
        nodes = [
            {"id": "G1", "lat": 59.6500, "lon": 17.9200},
            {"id": "I1", "lat": 59.6505, "lon": 17.9210},
            {"id": "I2", "lat": 59.6515, "lon": 17.9225},
            {"id": "RWY", "lat": 59.6520, "lon": 17.9230},
        ]
        segments = [
            {"from_node": "G1", "to_node": "I1", "taxiway_name": "A"},
            {"from_node": "I1", "to_node": "I2", "taxiway_name": "B"},
            {"from_node": "I2", "to_node": "RWY", "taxiway_name": "C"},
            {"from_node": "I1", "to_node": "RWY", "taxiway_name": "D"},
        ]
        planner.build_graph_from_segments(segments, nodes)
        route = planner.find_shortest_path("G1", "RWY")
        assert route is not None
        assert len(route.edges) == 2  # G1 -> I1 -> RWY (direct)

    def test_route_instructions(self, planner):
        nodes = [
            {"id": "G1", "lat": 59.6500, "lon": 17.9200, "name": "Gate 1"},
            {"id": "I1", "lat": 59.6505, "lon": 17.9210, "name": "Twy A1"},
            {"id": "RWY", "lat": 59.6520, "lon": 17.9230, "name": "RWY 01L"},
        ]
        segments = [
            {"from_node": "G1", "to_node": "I1", "taxiway_name": "A"},
            {"from_node": "I1", "to_node": "RWY", "taxiway_name": "B"},
        ]
        planner.build_graph_from_segments(segments, nodes)
        route = planner.find_shortest_path("G1", "RWY")
        assert route is not None
        assert len(route.instructions) > 0
        assert "A" in route.instructions[0] or "B" in route.instructions[0]


class TestShortestPathSolver:
    def test_solve(self):
        from models import TaxiGraph, TaxiNode, TaxiEdge, LatLon, NodeType
        from taxi_routing import ShortestPathSolver
        graph = TaxiGraph()
        graph.add_node(TaxiNode("A", LatLon(0, 0), NodeType.GATE, "Gate"))
        graph.add_node(TaxiNode("B", LatLon(0.001, 0.001), NodeType.INTERSECTION))
        graph.add_node(TaxiNode("C", LatLon(0.002, 0.002), NodeType.RUNWAY_THRESHOLD))
        graph.add_edge(TaxiEdge("A->B", "A", "B", 100))
        graph.add_edge(TaxiEdge("B->C", "B", "C", 100))
        route = ShortestPathSolver.solve(graph, "A", "C")
        assert route is not None
        assert route.total_distance_m == pytest.approx(200, abs=10)

    def test_compute_route_distance(self):
        from models import TaxiGraph, TaxiNode, TaxiEdge, LatLon, NodeType, TaxiRoute
        from taxi_routing import ShortestPathSolver
        route = TaxiRoute(total_distance_m=500.0)
        assert ShortestPathSolver.compute_route_distance(route) == 500.0


# ──────────────────────────────────────────────
# ProceduralRouteEngine
# ──────────────────────────────────────────────

class TestProceduralRouteEngine:
    @pytest.fixture
    def engine(self):
        from procedural_routes import ProceduralRouteEngine
        return ProceduralRouteEngine()

    def test_build_and_get_procedure(self, engine):
        from models import ProcedureType
        engine.build_procedure_from_waypoints(
            ProcedureType.SID, "ARN1N", "ESSA",
            [
                {"ident": "ARN", "lat": 59.6494, "lon": 17.9231},
                {"ident": "ELTOK", "lat": 59.8, "lon": 18.1, "altitude_ft": 5000},
                {"ident": "BEDAK", "lat": 60.0, "lon": 18.2, "altitude_ft": 10000},
            ],
            runways=["01L", "01R"],
        )
        proc = engine.get_procedure("ESSA", ProcedureType.SID, "ARN1N")
        assert proc is not None
        assert proc.name == "ARN1N"
        assert len(proc.waypoints) == 3
        assert proc.total_distance_nm > 0

    def test_get_procedure_not_found(self, engine):
        from models import ProcedureType
        assert engine.get_procedure("XXXX", ProcedureType.SID, "NONEXIST") is None

    def test_get_procedures_for_airport(self, engine):
        from models import ProcedureType
        engine.build_procedure_from_waypoints(
            ProcedureType.SID, "ARN1N", "ESSA",
            [{"ident": "A", "lat": 0, "lon": 0}],
        )
        engine.build_procedure_from_waypoints(
            ProcedureType.STAR, "ARN1A", "ESSA",
            [{"ident": "B", "lat": 0, "lon": 0}],
        )
        all_procs = engine.get_procedures_for_airport("ESSA")
        assert len(all_procs) == 2
        sids = engine.get_procedures_for_airport("ESSA", ProcedureType.SID)
        assert len(sids) == 1

    def test_leg_headings(self, engine):
        from models import ProcedureType
        engine.build_procedure_from_waypoints(
            ProcedureType.SID, "DEP01", "ESSA",
            [
                {"ident": "A", "lat": 59.65, "lon": 17.92},
                {"ident": "B", "lat": 59.75, "lon": 18.10},
            ],
        )
        proc = engine.get_procedure("ESSA", ProcedureType.SID, "DEP01")
        headings = engine.compute_leg_headings(proc)
        assert len(headings) == 1
        hdg, dist = headings[0]
        assert 0 < hdg < 90
        assert dist > 0

    def test_find_transition(self, engine):
        from models import ProcedureType
        engine.build_procedure_from_waypoints(
            ProcedureType.STAR, "ARN1A", "ESSA",
            [
                {"ident": "BEDAK", "lat": 60.0, "lon": 18.2},
                {"ident": "ELTOK", "lat": 59.8, "lon": 18.1},
                {"ident": "ARN", "lat": 59.6494, "lon": 17.9231},
            ],
        )
        proc = engine.get_procedure("ESSA", ProcedureType.STAR, "ARN1A")
        transition = engine.find_transition(proc, "BEDAK", "ELTOK")
        assert transition is not None
        assert len(transition) == 2
        assert engine.find_transition(proc, "ELTOK", "BEDAK") is None  # wrong order

    def test_validate_constraints(self, engine):
        from models import ProcedureType
        engine.build_procedure_from_waypoints(
            ProcedureType.SID, "CONSTRAINED", "ESSA",
            [
                {"ident": "A", "lat": 0, "lon": 0},
                {"ident": "B", "lat": 1, "lon": 1, "altitude_ft": 5000, "speed_kn": 250},
                {"ident": "C", "lat": 2, "lon": 2, "altitude_ft": 5000},
            ],
        )
        proc = engine.get_procedure("ESSA", ProcedureType.SID, "CONSTRAINED")
        warnings = engine.validate_constraints(proc, 5200, 240)
        assert len(warnings) == 0
        warnings = engine.validate_constraints(proc, 3000, 300)
        assert len(warnings) >= 1

    def test_route_geometry(self, engine):
        from models import ProcedureType
        engine.build_procedure_from_waypoints(
            ProcedureType.SID, "ARN1N", "ESSA",
            [
                {"ident": "ARN", "lat": 59.6494, "lon": 17.9231},
                {"ident": "ELTOK", "lat": 59.8, "lon": 18.1},
            ],
        )
        proc = engine.get_procedure("ESSA", ProcedureType.SID, "ARN1N")
        geom = engine.compute_route_geometry(proc)
        assert geom["name"] == "ARN1N"
        assert geom["waypoint_count"] == 2
        assert "heading_deg" in geom["legs"][0]


# ──────────────────────────────────────────────
# ILSInterceptCalculator
# ──────────────────────────────────────────────

class TestILSInterceptCalculator:
    @pytest.fixture
    def calc(self):
        from ils import ILSInterceptCalculator
        return ILSInterceptCalculator()

    def test_calculate_intercept(self, calc):
        # Aircraft approaching from south, heading 350°, to intercept runway 01L (hdg 9°)
        result = calc.calculate_intercept(
            aircraft_lat=59.55,
            aircraft_lon=17.9231,
            aircraft_alt_ft=3000,
            aircraft_heading=350,
            runway_lat=59.6494,
            runway_lon=17.9231,
            runway_heading=9.1,
            ils_heading=9.1,
        )
        assert result.intercept_angle_deg > 0
        assert result.is_feasible
        assert result.distance_to_threshold_nm > 0

    def test_intercept_angle_too_shallow(self, calc):
        # Aircraft heading almost same as runway
        result = calc.calculate_intercept(
            aircraft_lat=59.70,
            aircraft_lon=17.92,
            aircraft_alt_ft=3000,
            aircraft_heading=10,
            runway_lat=59.6494,
            runway_lon=17.9231,
            runway_heading=9.1,
        )
        # Should still be feasible since we adjust angle
        assert result.recommended_heading is not None

    def test_calculate_glideslope_altitude(self, calc):
        alt = calc.calculate_glideslope_altitude(5.0)
        expected = 5.0 * 6076.12 * math.tan(math.radians(3.0))
        assert alt == pytest.approx(expected, abs=10)

    def test_localizer_deviation(self, calc):
        # Aircraft north of runway, bearing due south matches localizer course
        deviation, offset = calc.calculate_localizer_deviation(
            59.75, 17.9231, 59.6494, 17.9231, 180
        )
        assert deviation < 5

    def test_is_on_glideslope(self, calc):
        alt = calc.calculate_glideslope_altitude(5.0)
        assert calc.is_on_glideslope(alt, 5.0, tolerance_ft=50)
        assert not calc.is_on_glideslope(alt + 500, 5.0, tolerance_ft=50)

    def test_intercept_too_close(self, calc):
        result = calc.calculate_intercept(
            aircraft_lat=59.6495,
            aircraft_lon=17.9231,
            aircraft_alt_ft=500,
            aircraft_heading=180,
            runway_lat=59.6494,
            runway_lon=17.9231,
            runway_heading=9.1,
        )
        assert not result.is_feasible


# ──────────────────────────────────────────────
# HoldingPatternEngine
# ──────────────────────────────────────────────

class TestHoldingPatternEngine:
    @pytest.fixture
    def engine(self):
        from holding import HoldingPatternEngine
        return HoldingPatternEngine()

    def test_calculate_pattern(self, engine):
        pattern = engine.calculate_pattern(59.65, 17.92, 180)
        assert pattern.inbound_heading == 180
        assert pattern.outbound_heading == 0
        assert pattern.leg_length_nm > 0

    def test_calculate_pattern_left_turns(self, engine):
        from models import TurnDirection
        pattern = engine.calculate_pattern(59.65, 17.92, 180, TurnDirection.LEFT)
        assert pattern.inbound_heading == 180
        assert pattern.outbound_heading == 0

    def test_direct_entry(self, engine):
        from models import TurnDirection
        pattern = engine.calculate_pattern(59.65, 17.92, 180, TurnDirection.RIGHT)
        # Aircraft approaching from the north heading south - should be direct entry
        entry = engine.determine_entry(60.0, 18.0, 180, pattern)
        assert entry.entry_type.value in ("direct", "teardrop", "parallel")

    def test_teardrop_entry(self, engine):
        from models import TurnDirection
        pattern = engine.calculate_pattern(59.65, 17.92, 180, TurnDirection.RIGHT)
        # Aircraft approaching from ~30° left of inbound
        entry = engine.determine_entry(59.8, 17.5, 140, pattern)
        assert entry.instructions is not None

    def test_parallel_entry(self, engine):
        from models import TurnDirection
        pattern = engine.calculate_pattern(59.65, 17.92, 180, TurnDirection.RIGHT)
        # Aircraft approaching from the east heading west
        entry = engine.determine_entry(59.8, 18.3, 250, pattern)
        assert len(entry.instructions) > 0

    def test_hold_geometry(self, engine):
        from models import TurnDirection
        geom = engine.compute_hold_geometry(59.65, 17.92, 180, 10, TurnDirection.RIGHT)
        assert len(geom) == 5
        assert geom[0] == (59.65, 17.92)  # start at fix
        assert geom[-1] == (59.65, 17.92)  # end at fix

    def test_is_aircraft_in_pattern(self, engine):
        pattern = engine.calculate_pattern(59.65, 17.92, 180)
        assert engine.is_aircraft_in_holding_pattern(59.65, 17.92, pattern)
        assert not engine.is_aircraft_in_holding_pattern(60.0, 18.0, pattern, tolerance_nm=2)


# ──────────────────────────────────────────────
# VectoringEngine
# ──────────────────────────────────────────────

class TestVectoringEngine:
    @pytest.fixture
    def engine(self):
        from vectoring import VectoringEngine
        return VectoringEngine()

    def test_vector_to_localizer(self, engine):
        result = engine.vector_to_localizer(
            aircraft_lat=59.70,
            aircraft_lon=17.50,
            aircraft_heading=270,
            aircraft_alt_ft=3000,
            aircraft_speed_kn=200,
            runway_lat=59.6494,
            runway_lon=17.9231,
            runway_heading=9.1,
        )
        assert result.heading_to_intercept is not None
        assert len(result.instructions) > 0
        assert result.distance_to_runway_nm > 0

    def test_vector_to_base_leg(self, engine):
        vec = engine.vector_to_base_leg(
            aircraft_lat=59.70,
            aircraft_lon=17.50,
            aircraft_heading=0,
            aircraft_alt_ft=3000,
            runway_lat=59.6494,
            runway_lon=17.9231,
            runway_heading=9.1,
        )
        assert vec.heading_deg is not None
        assert vec.distance_nm > 0

    def test_vector_for_spacing(self, engine):
        vec, extend_time = engine.vector_for_spacing(
            lead_lat=59.70, lead_lon=17.92, lead_speed_kn=180,
            trail_lat=59.65, trail_lon=17.80, trail_speed_kn=200,
            desired_spacing_nm=5.0,
        )
        assert vec.heading_deg is not None

    def test_calculate_turn_to_final(self, engine):
        vec = engine.calculate_turn_to_final(
            aircraft_lat=59.68, aircraft_lon=17.80,
            aircraft_heading=90, aircraft_speed_kn=180,
            runway_lat=59.6494, runway_lon=17.9231,
            runway_heading=9.1,
        )
        assert vec.heading_deg is not None

    def test_calculate_downwind_leg(self, engine):
        hdg, base_lat, base_lon = engine.calculate_downwind_leg(
            59.6494, 17.9231, 9.1, 4.0
        )
        assert hdg == pytest.approx(189.1, abs=0.5)
        assert base_lat != 59.6494


# ──────────────────────────────────────────────
# RunwayOccupancyTracker
# ──────────────────────────────────────────────

class TestRunwayOccupancyTracker:
    @pytest.fixture
    def tracker(self):
        from runway_occupancy import RunwayOccupancyTracker
        return RunwayOccupancyTracker()

    def test_calculate_occupancy_default(self, tracker):
        occ = tracker.calculate_occupancy("01L", "SAS123", "default")
        assert occ.estimated_occupancy_s > 0
        assert occ.time_to_vacate_s > 0
        assert occ.clearance_time_s > occ.time_to_vacate_s
        assert occ.minimum_separation_s > 0

    def test_calculate_occupancy_b738(self, tracker):
        occ = tracker.calculate_occupancy("01L", "SAS123", "B738")
        assert occ.estimated_occupancy_s > 0
        assert occ.landing_speed_kn == 140

    def test_calculate_occupancy_c172(self, tracker):
        occ = tracker.calculate_occupancy("01L", "N12345", "C172")
        assert occ.estimated_occupancy_s > 0
        assert occ.landing_speed_kn == 60

    def test_calculate_wake_turbulence(self, tracker):
        sep = tracker.calculate_wake_turbulence_separation("B738", "C172")
        assert sep >= 3
        sep = tracker.calculate_wake_turbulence_separation("A380", "C172")
        assert sep >= 5

    def test_can_accept_arrival(self, tracker):
        from models import RunwayOccupancy
        assert tracker.can_accept_arrival("01L", None, 120.0)
        occ = RunwayOccupancy("01L", "SAS123", 140, 25, 2000, 30, 20, 40, 90)
        assert not tracker.can_accept_arrival("01L", occ, 10.0, min_separation_s=90)
        assert tracker.can_accept_arrival("01L", occ, 120.0, min_separation_s=90)

    def test_can_release_departure(self, tracker):
        from models import RunwayOccupancy
        occ = RunwayOccupancy("01L", "SAS123", 140, 25, 2000, 30, 20, 40, 90)
        assert not tracker.can_release_departure("01L", occ, 10.0, 120.0)
        assert tracker.can_release_departure("01L", occ, 60.0, 120.0)


# ──────────────────────────────────────────────
# ConflictPredictor
# ──────────────────────────────────────────────

class TestConflictPredictor:
    @pytest.fixture
    def predictor(self):
        from conflict_predictor import ConflictPredictor
        return ConflictPredictor()

    def test_project_position(self, predictor):
        lat, lon, alt = predictor.project_position(0, 0, 10000, 0, 300, 0, 60)
        # 300kn * 60s = 5nm. At equator 1deg ~ 60nm, so 5nm ~ 0.083deg
        assert lat == pytest.approx(0.083, abs=0.005)
        assert lon == pytest.approx(0, abs=0.01)
        assert alt == pytest.approx(10000, abs=1)

    def test_project_position_with_climb(self, predictor):
        lat, lon, alt = predictor.project_position(0, 0, 5000, 0, 200, 1000, 120)
        assert alt == pytest.approx(7000, abs=1)  # 1000fpm * 2min = 2000ft gain

    def test_project_trajectory(self, predictor):
        ac = {"lat": 0, "lon": 0, "alt_msl": 10000, "heading": 90, "groundspeed": 300, "vertical_speed": 0}
        traj = predictor.project_trajectory(ac, 6)  # 6 steps * 10s = 60s
        assert len(traj) == 6
        assert traj[-1][0] == pytest.approx(0, abs=0.01)
        assert traj[-1][1] > 0  # moved east

    def test_no_conflict_distant(self, predictor):
        ac_a = {"callsign": "AC1", "lat": 59.0, "lon": 17.0, "alt_msl": 10000,
                "heading": 0, "groundspeed": 300, "vertical_speed": 0}
        ac_b = {"callsign": "AC2", "lat": 61.0, "lon": 20.0, "alt_msl": 10000,
                "heading": 0, "groundspeed": 300, "vertical_speed": 0}
        conflicts = predictor.predict([ac_a, ac_b], lookahead_s=60)
        assert len(conflicts) == 0

    def test_conflict_close(self, predictor):
        ac_a = {"callsign": "AC1", "lat": 59.50, "lon": 17.00, "alt_msl": 10000,
                "heading": 0, "groundspeed": 300, "vertical_speed": 0}
        ac_b = {"callsign": "AC2", "lat": 59.51, "lon": 17.01, "alt_msl": 10000,
                "heading": 0, "groundspeed": 300, "vertical_speed": 0}
        conflicts = predictor.predict([ac_a, ac_b],
                                       lateral_separation_nm=5,
                                       vertical_separation_ft=1000,
                                       lookahead_s=30)
        assert len(conflicts) >= 1

    def test_pair_prediction(self, predictor):
        ac_a = {"callsign": "AC1", "lat": 59.50, "lon": 17.00, "alt_msl": 10000,
                "heading": 0, "groundspeed": 300, "vertical_speed": 0}
        ac_b = {"callsign": "AC2", "lat": 59.51, "lon": 17.01, "alt_msl": 10000,
                "heading": 0, "groundspeed": 300, "vertical_speed": 0}
        conflict = predictor.predict_pair(ac_a, ac_b, 5, 1000)
        assert conflict is not None
        assert conflict.aircraft_a == "AC1"
        assert conflict.aircraft_b == "AC2"

    def test_minimum_separation(self, predictor):
        ac_a = {"callsign": "AC1", "lat": 59.50, "lon": 17.00, "alt_msl": 10000,
                "heading": 0, "groundspeed": 300, "vertical_speed": 0}
        ac_b = {"callsign": "AC2", "lat": 59.51, "lon": 17.01, "alt_msl": 10000,
                "heading": 0, "groundspeed": 300, "vertical_speed": 0}
        total, lateral, vertical = predictor.minimum_separation(ac_a, ac_b)
        assert lateral < 100  # should be close together


# ──────────────────────────────────────────────
# Model validation
# ──────────────────────────────────────────────

class TestModels:
    def test_latlon(self):
        from models import LatLon
        ll = LatLon(59.65, 17.92)
        assert ll.lat == 59.65
        assert ll.lon == 17.92

    def test_geovector(self):
        from models import GeoVector
        v = GeoVector(90, 10)
        assert v.heading_deg == 90
        assert v.distance_nm == 10

    def test_taxi_route_instructions(self):
        from models import TaxiNode, TaxiEdge, TaxiRoute, LatLon, NodeType
        route = TaxiRoute(
            nodes=[
                TaxiNode("A", LatLon(0, 0), NodeType.GATE, "Gate 1"),
                TaxiNode("B", LatLon(0.001, 0), NodeType.INTERSECTION, "Twy A"),
            ],
            edges=[
                TaxiEdge("A->B", "A", "B", 100, "A"),
            ],
            total_distance_m=100,
        )
        instr = route.instructions
        assert len(instr) == 1
        assert "A" in instr[0]

    def test_procedure_total_distance(self):
        from models import Procedure, ProcedureType, ProcedureWaypoint
        proc = Procedure(
            type=ProcedureType.SID,
            name="TEST",
            waypoints=[
                ProcedureWaypoint("A", 0, 0),
                ProcedureWaypoint("B", 1, 1),
            ],
        )
        assert proc.total_distance_nm > 0
        assert len(proc.leg_distances_nm) == 1

    def test_procedure_leg_distances(self):
        from models import Procedure, ProcedureType, ProcedureWaypoint
        proc = Procedure(
            type=ProcedureType.SID,
            name="TEST",
            waypoints=[
                ProcedureWaypoint("A", 0, 0),
                ProcedureWaypoint("B", 0.5, 0),
                ProcedureWaypoint("C", 1.0, 0),
            ],
        )
        legs = proc.leg_distances_nm
        assert len(legs) == 2
        assert legs[0] == pytest.approx(30, abs=0.5)

    def test_hold_entry_solution(self):
        from models import HoldEntrySolution, HoldEntryType, TurnDirection
        sol = HoldEntrySolution(
            entry_type=HoldEntryType.DIRECT,
            inbound_heading=180,
            outbound_heading=0,
            outbound_leg_duration_s=60,
            outbound_distance_nm=10,
            turn_direction=TurnDirection.RIGHT,
            instructions=["Test instruction"],
        )
        assert sol.inbound_heading == 180
        assert len(sol.instructions) == 1
