import datetime
from sqlalchemy import String, Integer, Float, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from geoalchemy2 import Geography

from typing import Optional
from ..base import Base


class Airport(Base):
    __tablename__ = "airports"

    id: Mapped[int] = mapped_column(primary_key=True)
    icao_code: Mapped[str] = mapped_column(String(4), unique=True, nullable=False, index=True)
    iata_code: Mapped[Optional[str]] = mapped_column(String(3))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    elevation_ft: Mapped[int] = mapped_column(Integer, nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    geometry: Mapped[Geography] = mapped_column(
        Geography("POINT", srid=4326), nullable=False
    )
    timezone_str: Mapped[str] = mapped_column(String(64), nullable=False)
    magnetic_var: Mapped[Optional[float]] = mapped_column(Float)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    runways = relationship("Runway", back_populates="airport", cascade="all, delete-orphan")
    taxiways = relationship("Taxiway", back_populates="airport", cascade="all, delete-orphan")
    parking_spots = relationship("Parking", back_populates="airport", cascade="all, delete-orphan")
    frequencies = relationship("Frequency", back_populates="airport", cascade="all, delete-orphan")
    procedures = relationship("Procedure", back_populates="airport", cascade="all, delete-orphan")
