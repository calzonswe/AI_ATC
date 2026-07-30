from sqlalchemy import String, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from geoalchemy2 import Geography

from typing import Optional
from ..base import Base


class Airway(Base):
    __tablename__ = "airways"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(4), nullable=False, default="J")

    geometry: Mapped[Geography] = mapped_column(
        Geography("LINESTRING", srid=4326), nullable=False
    )

    segments = relationship("AirwaySegment", back_populates="airway", cascade="all, delete-orphan")


class AirwaySegment(Base):
    __tablename__ = "airway_segments"

    id: Mapped[int] = mapped_column(primary_key=True)
    airway_id: Mapped[int] = mapped_column(
        ForeignKey("airways.id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_wpt_id: Mapped[int] = mapped_column(
        ForeignKey("waypoints.id", ondelete="CASCADE"), nullable=False
    )
    to_wpt_id: Mapped[int] = mapped_column(
        ForeignKey("waypoints.id", ondelete="CASCADE"), nullable=False
    )
    min_altitude_ft: Mapped[Optional[int]] = mapped_column(Integer)
    max_altitude_ft: Mapped[Optional[int]] = mapped_column(Integer)

    airway = relationship("Airway", back_populates="segments")
