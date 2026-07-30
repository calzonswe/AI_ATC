from sqlalchemy import String, Integer, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from geoalchemy2 import Geography

from typing import Optional
from ..base import Base


class Taxiway(Base):
    __tablename__ = "taxiways"

    id: Mapped[int] = mapped_column(primary_key=True)
    airport_id: Mapped[int] = mapped_column(
        ForeignKey("airports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(16), nullable=False)
    width_ft: Mapped[Optional[int]] = mapped_column(Integer)

    geometry: Mapped[Geography] = mapped_column(
        Geography("LINESTRING", srid=4326), nullable=False
    )

    airport = relationship("Airport", back_populates="taxiways")
