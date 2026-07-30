from sqlalchemy import String, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB

from typing import Optional
from ..base import Base


class Procedure(Base):
    __tablename__ = "procedures"

    id: Mapped[int] = mapped_column(primary_key=True)
    airport_id: Mapped[int] = mapped_column(
        ForeignKey("airports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(
        String(8), nullable=False
    )
    name: Mapped[str] = mapped_column(String(16), nullable=False)
    runways: Mapped[list[str] | None] = mapped_column(JSONB)
    waypoint_sequence: Mapped[list[dict] | None] = mapped_column(JSONB)
    altitude_restrictions: Mapped[list[dict] | None] = mapped_column(JSONB)
    speed_restrictions: Mapped[list[dict] | None] = mapped_column(JSONB)

    airport = relationship("Airport", back_populates="procedures")
