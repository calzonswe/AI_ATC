from sqlalchemy import String, Integer, Float
from sqlalchemy.orm import Mapped, mapped_column
from geoalchemy2 import Geography

from typing import Optional
from ..base import Base


class Waypoint(Base):
    __tablename__ = "waypoints"

    id: Mapped[int] = mapped_column(primary_key=True)
    identifier: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    region: Mapped[Optional[str]] = mapped_column(String(4))
    type: Mapped[str] = mapped_column(
        String(16), nullable=False, default="waypoint"
    )

    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    geometry: Mapped[Geography] = mapped_column(
        Geography("POINT", srid=4326), nullable=False
    )
