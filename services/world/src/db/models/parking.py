from sqlalchemy import String, Integer, Float, ForeignKey, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from geoalchemy2 import Geography

from typing import Optional
from ..base import Base


class Parking(Base):
    __tablename__ = "parking"

    id: Mapped[int] = mapped_column(primary_key=True)
    airport_id: Mapped[int] = mapped_column(
        ForeignKey("airports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(8), nullable=False)
    type: Mapped[str] = mapped_column(
        String(16), nullable=False, default="gate"
    )
    airline_codes: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    radius_m: Mapped[int] = mapped_column(Integer, nullable=False, default=15)

    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    geometry: Mapped[Geography] = mapped_column(
        Geography("POINT", srid=4326), nullable=False
    )

    airport = relationship("Airport", back_populates="parking_spots")
