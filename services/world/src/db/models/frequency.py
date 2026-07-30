from sqlalchemy import String, Integer, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from typing import Optional
from ..base import Base


class Frequency(Base):
    __tablename__ = "frequencies"

    id: Mapped[int] = mapped_column(primary_key=True)
    airport_id: Mapped[int] = mapped_column(
        ForeignKey("airports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(
        String(16), nullable=False
    )
    frequency_mhz: Mapped[float] = mapped_column(Float, nullable=False)
    callsign: Mapped[Optional[str]] = mapped_column(String(64))

    airport = relationship("Airport", back_populates="frequencies")
