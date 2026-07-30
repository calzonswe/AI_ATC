from sqlalchemy.orm import DeclarativeBase
from geoalchemy2 import Geography


class Base(DeclarativeBase):
    pass


# Register Geography type with SQLAlchemy
# (geoalchemy2 handles this via its own setup)
