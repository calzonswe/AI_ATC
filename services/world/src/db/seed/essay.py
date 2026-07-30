"""Seed data for Stockholm Arlanda Airport (ESSA).

Run with: python -m services.world.src.db.seed.essay
"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from geoalchemy2 import WKTElement

from ..models import (
    Airport, Runway, Taxiway, Parking, Frequency,
    Waypoint, VOR, NDB, Airway, AirwaySegment, Procedure,
    Airspace, Controller,
)


ESSA_DATA = {
    "airport": {
        "icao_code": "ESSA",
        "iata_code": "ARN",
        "name": "Stockholm Arlanda Airport",
        "elevation_ft": 137,
        "latitude": 59.6494,
        "longitude": 17.9231,
        "timezone_str": "Europe/Stockholm",
        "magnetic_var": 5.5,
    },
    "runways": [
        {
            "identifier": "01L/19R",
            "length_ft": 10830,
            "width_ft": 148,
            "surface": "asphalt",
            "heading": 9.1,
            "threshold_lat": 59.6356, "threshold_lon": 17.9186,
            "elevation_ft": 130,
            "ils_frequency": 109.50, "ils_heading": 8.0,
        },
        {
            "identifier": "01R/19L",
            "length_ft": 10827,
            "width_ft": 148,
            "surface": "asphalt",
            "heading": 8.7,
            "threshold_lat": 59.6378, "threshold_lon": 17.9511,
            "elevation_ft": 130,
            "ils_frequency": 110.30, "ils_heading": 9.0,
        },
        {
            "identifier": "08/26",
            "length_ft": 8202,
            "width_ft": 148,
            "surface": "asphalt",
            "heading": 76.0,
            "threshold_lat": 59.6503, "threshold_lon": 17.9147,
            "elevation_ft": 120,
            "ils_frequency": 109.90, "ils_heading": 77.0,
        },
    ],
    "frequencies": [
        {"type": "GROUND", "frequency_mhz": 121.800, "callsign": "Arlanda Ground"},
        {"type": "TOWER", "frequency_mhz": 118.300, "callsign": "Arlanda Tower"},
        {"type": "DEPARTURE", "frequency_mhz": 125.200, "callsign": "Arlanda Departure"},
        {"type": "APPROACH", "frequency_mhz": 124.000, "callsign": "Arlanda Approach"},
        {"type": "ATIS", "frequency_mhz": 128.425, "callsign": "Arlanda ATIS"},
    ],
    "parking": [
        {"name": "G1", "type": "gate", "latitude": 59.6475, "longitude": 17.9280, "radius_m": 20},
        {"name": "G2", "type": "gate", "latitude": 59.6477, "longitude": 17.9285, "radius_m": 20},
        {"name": "G3", "type": "gate", "latitude": 59.6479, "longitude": 17.9290, "radius_m": 20},
        {"name": "R1", "type": "ramp", "latitude": 59.6520, "longitude": 17.9350, "radius_m": 30},
        {"name": "R2", "type": "ramp", "latitude": 59.6525, "longitude": 17.9360, "radius_m": 30},
    ],
    "waypoints": [
        {"identifier": "ARN", "region": "ES", "type": "VOR", "latitude": 59.6494, "longitude": 17.9231},
        {"identifier": "ELTOK", "region": "ES", "type": "fix", "latitude": 59.8000, "longitude": 18.1000},
        {"identifier": "NILUG", "region": "ES", "type": "fix", "latitude": 59.5000, "longitude": 17.7000},
        {"identifier": "BEDAK", "region": "ES", "type": "fix", "latitude": 60.0000, "longitude": 18.2000},
        {"identifier": "XILAN", "region": "ES", "type": "fix", "latitude": 59.3000, "longitude": 17.5000},
    ],
    "vors": [
        {"identifier": "ARN", "frequency": 117.40, "latitude": 59.6494, "longitude": 17.9231},
    ],
    "ndbs": [
        {"identifier": "AR", "frequency": 370.0, "latitude": 59.6600, "longitude": 17.9400},
    ],
}


def _make_point(lat: float, lon: float) -> WKTElement:
    return WKTElement(f"POINT({lon} {lat})", srid=4326)


def _make_linestring(coords: list[tuple[float, float]]) -> WKTElement:
    pts = ", ".join(f"{lon} {lat}" for lat, lon in coords)
    return WKTElement(f"LINESTRING({pts})", srid=4326)


async def seed(dsn: str):
    engine = create_async_engine(dsn, echo=True)
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: None)

    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as session:
        apt_data = ESSA_DATA["airport"]
        airport = Airport(
            icao_code=apt_data["icao_code"],
            iata_code=apt_data["iata_code"],
            name=apt_data["name"],
            elevation_ft=apt_data["elevation_ft"],
            latitude=apt_data["latitude"],
            longitude=apt_data["longitude"],
            geometry=_make_point(apt_data["latitude"], apt_data["longitude"]),
            timezone_str=apt_data["timezone_str"],
            magnetic_var=apt_data["magnetic_var"],
        )
        session.add(airport)
        await session.flush()

        for rwy in ESSA_DATA["runways"]:
            runway = Runway(
                airport_id=airport.id,
                identifier=rwy["identifier"],
                length_ft=rwy["length_ft"],
                width_ft=rwy["width_ft"],
                surface=rwy["surface"],
                heading=rwy["heading"],
                threshold_lat=rwy["threshold_lat"],
                threshold_lon=rwy["threshold_lon"],
                elevation_ft=rwy["elevation_ft"],
                ils_frequency=rwy.get("ils_frequency"),
                ils_heading=rwy.get("ils_heading"),
                geometry=_make_linestring([
                    (rwy["threshold_lat"], rwy["threshold_lon"]),
                    (rwy["threshold_lat"] + 0.01, rwy["threshold_lon"] + 0.01),
                ]),
            )
            session.add(runway)

        for freq in ESSA_DATA["frequencies"]:
            frequency = Frequency(
                airport_id=airport.id,
                type=freq["type"],
                frequency_mhz=freq["frequency_mhz"],
                callsign=freq["callsign"],
            )
            session.add(frequency)

        for spot in ESSA_DATA["parking"]:
            parking = Parking(
                airport_id=airport.id,
                name=spot["name"],
                type=spot["type"],
                latitude=spot["latitude"],
                longitude=spot["longitude"],
                geometry=_make_point(spot["latitude"], spot["longitude"]),
                radius_m=spot["radius_m"],
            )
            session.add(parking)

        for wpt in ESSA_DATA["waypoints"]:
            waypoint = Waypoint(
                identifier=wpt["identifier"],
                region=wpt["region"],
                type=wpt["type"],
                latitude=wpt["latitude"],
                longitude=wpt["longitude"],
                geometry=_make_point(wpt["latitude"], wpt["longitude"]),
            )
            session.add(waypoint)

        for v in ESSA_DATA["vors"]:
            vor = VOR(
                identifier=v["identifier"],
                frequency=v["frequency"],
                latitude=v["latitude"],
                longitude=v["longitude"],
                geometry=_make_point(v["latitude"], v["longitude"]),
            )
            session.add(vor)

        for n in ESSA_DATA["ndbs"]:
            ndb = NDB(
                identifier=n["identifier"],
                frequency=n["frequency"],
                latitude=n["latitude"],
                longitude=n["longitude"],
                geometry=_make_point(n["latitude"], n["longitude"]),
            )
            session.add(ndb)

        await session.commit()
        print(f"Seeded {apt_data['icao_code']} ({apt_data['name']})")

    await engine.dispose()


if __name__ == "__main__":
    dsn = "postgresql+asyncpg://atc_admin:atc_password_secret@localhost:5432/ai_atc"
    asyncio.run(seed(dsn))
