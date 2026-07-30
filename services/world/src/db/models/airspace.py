from sqlalchemy import String, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from geoalchemy2 import Geography

from typing import Optional
from ..base import Base


class Airspace(Base):
    __tablename__ = "airspace"

    id: Mapped[int] = mapped_column(primary_key=True)
    identifier: Mapped[str] = mapped_column(String(16), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    class_type: Mapped[str] = mapped_column(
        "class", String(2), nullable=False
    )

    floor_ft: Mapped[int] = mapped_column(Integer, nullable=False)
    ceiling_ft: Mapped[int] = mapped_column(Integer, nullable=False)
    controller_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("controllers.id", ondelete="SET NULL")
    )

    geometry: Mapped[Geography] = mapped_column(
        Geography("MULTIPOLYGON", srid=4326), nullable=False
    )
