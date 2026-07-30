"""Initial schema — all tables with PostGIS spatial columns

Revision ID: 001
Revises:
Create Date: 2026-07-29
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
import geoalchemy2

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\"")

    op.create_table(
        "airports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("icao_code", sa.String(4), nullable=False),
        sa.Column("iata_code", sa.String(3), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("elevation_ft", sa.Integer(), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("geometry", geoalchemy2.Geography("POINT", srid=4326), nullable=False),
        sa.Column("timezone_str", sa.String(64), nullable=False),
        sa.Column("magnetic_var", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_airports_icao", "airports", ["icao_code"])
    op.create_index("idx_airports_geom", "airports", ["geometry"], postgresql_using="gist")

    op.create_table(
        "runways",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("airport_id", sa.Integer(), sa.ForeignKey("airports.id", ondelete="CASCADE"), nullable=False),
        sa.Column("identifier", sa.String(5), nullable=False),
        sa.Column("length_ft", sa.Integer(), nullable=False),
        sa.Column("width_ft", sa.Integer(), nullable=False),
        sa.Column("surface", sa.String(32), nullable=False, server_default="concrete"),
        sa.Column("heading", sa.Float(), nullable=False),
        sa.Column("threshold_lat", sa.Float(), nullable=False),
        sa.Column("threshold_lon", sa.Float(), nullable=False),
        sa.Column("elevation_ft", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ils_frequency", sa.Float(), nullable=True),
        sa.Column("ils_heading", sa.Float(), nullable=True),
        sa.Column("ils_channel", sa.String(4), nullable=True),
        sa.Column("geometry", geoalchemy2.Geography("LINESTRING", srid=4326), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_runways_airport", "runways", ["airport_id"])
    op.create_index("idx_runways_geom", "runways", ["geometry"], postgresql_using="gist")

    op.create_table(
        "taxiways",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("airport_id", sa.Integer(), sa.ForeignKey("airports.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(16), nullable=False),
        sa.Column("width_ft", sa.Integer(), nullable=True),
        sa.Column("geometry", geoalchemy2.Geography("LINESTRING", srid=4326), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_taxiways_airport", "taxiways", ["airport_id"])
    op.create_index("idx_taxiways_geom", "taxiways", ["geometry"], postgresql_using="gist")

    op.create_table(
        "parking",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("airport_id", sa.Integer(), sa.ForeignKey("airports.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(8), nullable=False),
        sa.Column("type", sa.String(16), nullable=False, server_default="gate"),
        sa.Column("airline_codes", sa.ARRAY(sa.String()), nullable=True),
        sa.Column("radius_m", sa.Integer(), nullable=False, server_default="15"),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("geometry", geoalchemy2.Geography("POINT", srid=4326), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_parking_airport", "parking", ["airport_id"])
    op.create_index("idx_parking_geom", "parking", ["geometry"], postgresql_using="gist")

    op.create_table(
        "frequencies",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("airport_id", sa.Integer(), sa.ForeignKey("airports.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("frequency_mhz", sa.Float(), nullable=False),
        sa.Column("callsign", sa.String(64), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_frequencies_airport", "frequencies", ["airport_id"])

    op.create_table(
        "waypoints",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("identifier", sa.String(8), nullable=False),
        sa.Column("region", sa.String(4), nullable=True),
        sa.Column("type", sa.String(16), nullable=False, server_default="waypoint"),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("geometry", geoalchemy2.Geography("POINT", srid=4326), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_waypoints_id", "waypoints", ["identifier"])
    op.create_index("idx_waypoints_geom", "waypoints", ["geometry"], postgresql_using="gist")

    op.create_table(
        "vors",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("identifier", sa.String(8), nullable=False),
        sa.Column("frequency", sa.Float(), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("geometry", geoalchemy2.Geography("POINT", srid=4326), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_vors_id", "vors", ["identifier"], unique=True)
    op.create_index("idx_vors_geom", "vors", ["geometry"], postgresql_using="gist")

    op.create_table(
        "ndbs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("identifier", sa.String(8), nullable=False),
        sa.Column("frequency", sa.Float(), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("geometry", geoalchemy2.Geography("POINT", srid=4326), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_ndbs_id", "ndbs", ["identifier"], unique=True)
    op.create_index("idx_ndbs_geom", "ndbs", ["geometry"], postgresql_using="gist")

    op.create_table(
        "airways",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(8), nullable=False),
        sa.Column("type", sa.String(4), nullable=False, server_default="J"),
        sa.Column("geometry", geoalchemy2.Geography("LINESTRING", srid=4326), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_airways_name", "airways", ["name"])
    op.create_index("idx_airways_geom", "airways", ["geometry"], postgresql_using="gist")

    op.create_table(
        "airway_segments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("airway_id", sa.Integer(), sa.ForeignKey("airways.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_wpt_id", sa.Integer(), sa.ForeignKey("waypoints.id", ondelete="CASCADE"), nullable=False),
        sa.Column("to_wpt_id", sa.Integer(), sa.ForeignKey("waypoints.id", ondelete="CASCADE"), nullable=False),
        sa.Column("min_altitude_ft", sa.Integer(), nullable=True),
        sa.Column("max_altitude_ft", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_airway_seg_airway", "airway_segments", ["airway_id"])

    op.create_table(
        "procedures",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("airport_id", sa.Integer(), sa.ForeignKey("airports.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.String(8), nullable=False),
        sa.Column("name", sa.String(16), nullable=False),
        sa.Column("runways", sa.JSON(), nullable=True),
        sa.Column("waypoint_sequence", sa.JSON(), nullable=True),
        sa.Column("altitude_restrictions", sa.JSON(), nullable=True),
        sa.Column("speed_restrictions", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_procedures_airport", "procedures", ["airport_id"])

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("password_hash", sa.String(256), nullable=False),
        sa.Column("role", sa.String(16), nullable=False, server_default="pilot"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_users_username", "users", ["username"], unique=True)

    op.create_table(
        "controllers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("callsign", sa.String(64), nullable=False),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("frequency_mhz", sa.Float(), nullable=False),
        sa.Column("airport_id", sa.Integer(), sa.ForeignKey("airports.id", ondelete="SET NULL"), nullable=True),
        sa.Column("airspace_sector_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_controllers_callsign", "controllers", ["callsign"], unique=True)

    op.create_table(
        "airspace",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("identifier", sa.String(16), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("class", sa.String(2), nullable=False),
        sa.Column("floor_ft", sa.Integer(), nullable=False),
        sa.Column("ceiling_ft", sa.Integer(), nullable=False),
        sa.Column("controller_id", sa.Integer(), sa.ForeignKey("controllers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("geometry", geoalchemy2.Geography("MULTIPOLYGON", srid=4326), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_airspace_id", "airspace", ["identifier"], unique=True)
    op.create_index("idx_airspace_geom", "airspace", ["geometry"], postgresql_using="gist")

    op.create_table(
        "sessions",
        sa.Column("token", sa.String(256), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("active_aircraft_callsign", sa.String(16), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("token"),
    )
    op.create_index("idx_sessions_user", "sessions", ["user_id"])

    op.create_foreign_key(
        "fk_airspace_controller",
        "airspace", "controllers",
        ["controller_id"], ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_controllers_airspace",
        "controllers", "airspace",
        ["airspace_sector_id"], ["id"],
        ondelete="SET NULL",
    )


def downgrade():
    op.drop_table("sessions")
    op.drop_table("airspace")
    op.drop_table("controllers")
    op.drop_table("users")
    op.drop_table("procedures")
    op.drop_table("airway_segments")
    op.drop_table("airways")
    op.drop_table("ndbs")
    op.drop_table("vors")
    op.drop_table("waypoints")
    op.drop_table("frequencies")
    op.drop_table("parking")
    op.drop_table("taxiways")
    op.drop_table("runways")
    op.drop_table("airports")
