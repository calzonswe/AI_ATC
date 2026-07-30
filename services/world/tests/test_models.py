from geoalchemy2 import WKTElement
from sqlalchemy import func, text


class TestAirportModel:
    def test_create_airport(self, session, sample_airport):
        from db.models.airport import Airport

        apt = session.get(Airport, sample_airport)
        assert apt is not None
        assert apt.icao_code == "ESSA"
        assert apt.iata_code == "ARN"
        assert apt.elevation_ft == 137

    def test_airport_geometry(self, session, sample_airport):
        from db.models.airport import Airport

        apt = session.get(Airport, sample_airport)
        assert apt.geometry is not None
        assert "POINT" in str(apt.geometry)


class TestRunwayModel:
    def test_create_runway(self, session, sample_airport):
        from db.models.runway import Runway

        rwy = Runway(
            airport_id=sample_airport,
            identifier="01L/19R",
            length_ft=10830,
            width_ft=148,
            surface="asphalt",
            heading=9.1,
            threshold_lat=59.6356,
            threshold_lon=17.9186,
            elevation_ft=130,
            ils_frequency=109.50,
            geometry=WKTElement(
                "LINESTRING(17.9186 59.6356, 17.9286 59.6456)",
                srid=4326,
            ),
        )
        session.add(rwy)
        session.commit()

        assert rwy.id is not None
        assert rwy.identifier == "01L/19R"


class TestFrequencyModel:
    def test_create_frequency(self, session, sample_airport):
        from db.models.frequency import Frequency

        freq = Frequency(
            airport_id=sample_airport,
            type="TOWER",
            frequency_mhz=118.300,
            callsign="Arlanda Tower",
        )
        session.add(freq)
        session.commit()

        assert freq.id is not None
        assert freq.frequency_mhz == 118.300


class TestWaypointModel:
    def test_create_waypoint(self, session):
        from db.models.waypoint import Waypoint

        wpt = Waypoint(
            identifier="ARN",
            region="ES",
            type="VOR",
            latitude=59.6494,
            longitude=17.9231,
            geometry=WKTElement("POINT(17.9231 59.6494)", srid=4326),
        )
        session.add(wpt)
        session.commit()

        assert wpt.id is not None
        assert wpt.identifier == "ARN"


class TestVORModel:
    def test_create_vor(self, session):
        from db.models.vor import VOR

        vor = VOR(
            identifier="ARN",
            frequency=117.40,
            latitude=59.6494,
            longitude=17.9231,
            geometry=WKTElement("POINT(17.9231 59.6494)", srid=4326),
        )
        session.add(vor)
        session.commit()

        assert vor.id is not None
        assert vor.frequency == 117.40


class TestAirspaceModel:
    def test_create_airspace(self, session):
        from db.models.airspace import Airspace

        airspace = Airspace(
            identifier="ESSS_CTA",
            name="Stockholm Control Area",
            class_type="C",
            floor_ft=0,
            ceiling_ft=24500,
            geometry=WKTElement(
                "MULTIPOLYGON((("
                "16.0 59.0, 18.0 59.0, 18.0 60.0, 16.0 60.0, 16.0 59.0"
                ")))",
                srid=4326,
            ),
        )
        session.add(airspace)
        session.commit()

        assert airspace.id is not None
        assert airspace.floor_ft == 0
        assert airspace.ceiling_ft == 24500
