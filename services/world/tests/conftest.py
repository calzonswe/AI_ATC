import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session as SASession
from geoalchemy2 import WKTElement

from db.base import Base


@pytest.fixture
def engine():
    e = create_engine("sqlite://", echo=False)

    @event.listens_for(e, "connect")
    def _load_spatialite(dbapi_conn, connection_record):
        try:
            dbapi_conn.enable_load_extension(True)
            dbapi_conn.load_extension("/usr/lib/mod_spatialite.so")
        except Exception:
            pass

    Base.metadata.create_all(e)
    return e


@pytest.fixture
def session(engine):
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


@pytest.fixture
def sample_airport(session: SASession) -> int:
    from db.models.airport import Airport

    apt = Airport(
        icao_code="ESSA",
        iata_code="ARN",
        name="Stockholm Arlanda Airport",
        elevation_ft=137,
        latitude=59.6494,
        longitude=17.9231,
        geometry=WKTElement("POINT(17.9231 59.6494)", srid=4326),
        timezone_str="Europe/Stockholm",
        magnetic_var=5.5,
    )
    session.add(apt)
    session.commit()
    return apt.id
