from sqlalchemy import String, Integer, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from geoalchemy2 import Geography

from typing import Optional
from ..base import Base


class Runway(Base):
    __tablename__ = "runways"

    id: Mapped[int] = mapped_column(primary_key=True)
    airport_id: Mapped[int] = mapped_column(
        ForeignKey("airports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    identifier: Mapped[str] = mapped_column(String(5), nullable=False)
    length_ft: Mapped[int] = mapped_column(Integer, nullable=False)
    width_ft: Mapped[int] = mapped_column(Integer, nullable=False)
    surface: Mapped[str] = mapped_column(String(32), nullable=False, default="concrete")
    heading: Mapped[float] = mapped_column(Float, nullable=False)
    threshold_lat: Mapped[float] = mapped_column(Float, nullable=False)
    threshold_lon: Mapped[float] = mapped_column(Float, nullable=False)
    elevation_ft: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ils_frequency: Mapped[Optional[float]] = mapped_column(Float)
    ils_heading: Mapped[Optional[float]] = mapped_column(Float)
    ils_channel: Mapped[Optional[str]] = mapped_column(String(4))

    geometry: Mapped[Geography] = mapped_column(
        Geography("LINESTRING", srid=4326), nullable=False
    )

    airport = relationship("Airport", back_populates="runways")
