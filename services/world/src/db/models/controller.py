from sqlalchemy import String, Integer, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from typing import Optional
from ..base import Base


class Controller(Base):
    __tablename__ = "controllers"

    id: Mapped[int] = mapped_column(primary_key=True)
    callsign: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    type: Mapped[str] = mapped_column(
        String(16), nullable=False
    )
    frequency_mhz: Mapped[float] = mapped_column(Float, nullable=False)
    airport_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("airports.id", ondelete="SET NULL")
    )
    airspace_sector_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("airspace.id", ondelete="SET NULL")
    )
