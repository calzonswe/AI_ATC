# Database Schema

## Technology

- **PostgreSQL 16** with **PostGIS 3.4** extension
- Connection via `asyncpg` (async pool)
- Migrations via **Alembic** (raw SQL, no ORM)
- Connection string: `postgresql+asyncpg://openatc:${DB_PASSWORD}@postgres:5432/openatc`

## Entity-Relationship Diagram

```mermaid
erDiagram
  AIRPORT ||--o{ RUNWAY : has
  AIRPORT ||--o{ FREQUENCY : has
  AIRPORT ||--o{ SID : defines
  AIRPORT ||--o{ STAR : defines
  AIRPORT ||--o{ CONTROLLER_POSITION : hosts
  AIRPORT ||--o{ PARKING_SPOT : has
  
  FLIGHT ||--o| FLIGHT_PLAN : has
  FLIGHT ||--o{ FLIGHT_TRACK : generates
  FLIGHT ||--o{ RADIO_LOG : produces
  FLIGHT ||--|| AIRCRAFT_TYPE : is_type
  
  CONTROLLER_POSITION ||--o{ RADIO_LOG : records
  CONTROLLER_POSITION ||--o{ CLEARANCE : issues
  
  RUNWAY ||--o{ APPROACH : has
  
  WAYPOINT }o--o{ SID : composes
  WAYPOINT }o--o{ STAR : composes
  
  AIRSPACE ||--o{ WAYPOINT : contains
  AIRSPACE ||--o{ AIRWAY : contains
```

## Schema Definitions

### `airports`

```sql
CREATE TABLE airports (
    id              SERIAL PRIMARY KEY,
    icao            VARCHAR(4) NOT NULL UNIQUE,
    iata            VARCHAR(3),
    name            VARCHAR(255) NOT NULL,
    lat             DOUBLE PRECISION NOT NULL,
    lon             DOUBLE PRECISION NOT NULL,
    elevation_ft    INTEGER NOT NULL,
    timezone_str    VARCHAR(64) NOT NULL,
    magnetic_var    REAL,  -- degrees, positive east
    geometry        GEOGRAPHY(POINT, 4326),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_airports_icao ON airports (icao);
CREATE INDEX idx_airports_geom ON airports USING GIST (geometry);
```

### `runways`

```sql
CREATE TABLE runways (
    id              SERIAL PRIMARY KEY,
    airport_id      INTEGER NOT NULL REFERENCES airports(id) ON DELETE CASCADE,
    designation     VARCHAR(5) NOT NULL,  -- e.g., "24L", "07R"
    surface         VARCHAR(32) NOT NULL DEFAULT 'concrete',
    length_ft       INTEGER NOT NULL,
    width_ft        INTEGER NOT NULL,
    heading         REAL NOT NULL,  -- magnetic heading in degrees
    threshold_lat   DOUBLE PRECISION NOT NULL,
    threshold_lon   DOUBLE PRECISION NOT NULL,
    elevation_ft    INTEGER NOT NULL,
    ils_frequency   REAL,  -- MHz, NULL if no ILS
    ils_heading     REAL,  -- degrees
    ils_channel     VARCHAR(4),
    geometry        GEOGRAPHY(LINESTRING, 4326),
    UNIQUE (airport_id, designation)
);

CREATE INDEX idx_runways_airport ON runways (airport_id);
```

### `frequencies`

```sql
CREATE TABLE frequencies (
    id              SERIAL PRIMARY KEY,
    airport_id      INTEGER NOT NULL REFERENCES airports(id) ON DELETE CASCADE,
    type            VARCHAR(16) NOT NULL,  -- ground, tower, departure, approach, center, atis
    frequency_mhz   REAL NOT NULL,
    callsign        VARCHAR(64),
    UNIQUE (airport_id, type)
);
```

### `parking_spots`

```sql
CREATE TABLE parking_spots (
    id              SERIAL PRIMARY KEY,
    airport_id      INTEGER NOT NULL REFERENCES airports(id) ON DELETE CASCADE,
    identifier      VARCHAR(8) NOT NULL,  -- e.g., "B12", "G7"
    lat             DOUBLE PRECISION NOT NULL,
    lon             DOUBLE PRECISION NOT NULL,
    type            VARCHAR(16) NOT NULL DEFAULT 'gate',  -- gate, ramp, hangar, remote
    airline_codes   TEXT[],  -- preferred airlines
    radius_m        REAL NOT NULL DEFAULT 15,
    UNIQUE (airport_id, identifier)
);
```

### `aircraft_types`

```sql
CREATE TABLE aircraft_types (
    icao_code       VARCHAR(4) PRIMARY KEY,  -- e.g., "B738", "A320"
    manufacturer     VARCHAR(64) NOT NULL,
    model           VARCHAR(64) NOT NULL,
    wake_category   VARCHAR(2) NOT NULL,  -- L, M, H, J (Light, Medium, Heavy, Super)
    engine_count    SMALLINT NOT NULL DEFAULT 2,
    engine_type     VARCHAR(16) NOT NULL DEFAULT 'jet',  -- jet, turboprop, piston
    max_range_nm    INTEGER,
    cruise_speed_kn INTEGER,
    max_altitude_ft INTEGER
);
```

### `flight_plans`

```sql
CREATE TABLE flight_plans (
    id                  SERIAL PRIMARY KEY,
    callsign            VARCHAR(16) NOT NULL,
    aircraft_type       VARCHAR(4) NOT NULL REFERENCES aircraft_types(icao_code),
    departure_airport   VARCHAR(4) NOT NULL REFERENCES airports(icao),
    arrival_airport     VARCHAR(4) NOT NULL REFERENCES airports(icao),
    alternate_airport   VARCHAR(4) REFERENCES airports(icao),
    cruise_altitude_ft  INTEGER NOT NULL,
    route               TEXT NOT NULL,  -- raw route string
    estimated_departure TIMESTAMPTZ NOT NULL,
    estimated_arrival   TIMESTAMPTZ,
    fuel_minutes        INTEGER NOT NULL DEFAULT 0,
    passengers          INTEGER DEFAULT 0,
    status              VARCHAR(16) NOT NULL DEFAULT 'filed',  -- filed, active, cancelled, complete
    filed_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    activated_at        TIMESTAMPTZ,
    UNIQUE (callsign, status)  -- only one active plan per callsign
);

CREATE INDEX idx_fp_callsign ON flight_plans (callsign);
CREATE INDEX idx_fp_status ON flight_plans (status);
```

### `flights`

```sql
CREATE TABLE flights (
    id              SERIAL PRIMARY KEY,
    callsign        VARCHAR(16) NOT NULL UNIQUE,
    flight_plan_id  INTEGER REFERENCES flight_plans(id),
    aircraft_type   VARCHAR(4) REFERENCES aircraft_types(icao_code),
    departure_airport VARCHAR(4),
    arrival_airport   VARCHAR(4),
    state           VARCHAR(32) NOT NULL DEFAULT 'preflight',
    -- preflight, pushback, taxi, departure, climb, cruise, descent, approach, landing, taxi_in, parked
    controller_id   VARCHAR(32),  -- current controlling position
    squawk_code     VARCHAR(4),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### `flight_tracks`

```sql
-- Time-series flight positions, partitioned by month
CREATE TABLE flight_tracks (
    id              BIGSERIAL,
    callsign        VARCHAR(16) NOT NULL,
    lat             DOUBLE PRECISION NOT NULL,
    lon             DOUBLE PRECISION NOT NULL,
    altitude_msl_ft DOUBLE PRECISION NOT NULL,
    altitude_agl_ft DOUBLE PRECISION,
    heading         REAL NOT NULL,
    speed_gs_kn     REAL NOT NULL,
    speed_ias_kn    REAL,
    vertical_speed  REAL,
    on_ground       BOOLEAN NOT NULL DEFAULT FALSE,
    recorded_at     TIMESTAMPTZ NOT NULL,
    geometry        GEOGRAPHY(POINT, 4326)
) PARTITION BY RANGE (recorded_at);

CREATE INDEX idx_tracks_callsign ON flight_tracks (callsign, recorded_at DESC);
CREATE INDEX idx_tracks_geom ON flight_tracks USING GIST (geometry);

-- Monthly partitions
CREATE TABLE flight_tracks_2026_07 PARTITION OF flight_tracks
    FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');
CREATE TABLE flight_tracks_2026_08 PARTITION OF flight_tracks
    FOR VALUES FROM ('2026-08-01') TO ('2026-09-01');
```

### `controller_positions`

```sql
CREATE TABLE controller_positions (
    id              VARCHAR(32) PRIMARY KEY,  -- e.g., "KLAX_GND"
    callsign        VARCHAR(64) NOT NULL,
    type            VARCHAR(16) NOT NULL,  -- ground, tower, departure, approach, center
    frequency_mhz   REAL NOT NULL,
    state           VARCHAR(16) NOT NULL DEFAULT 'offline',
    airport_icao    VARCHAR(4) NOT NULL REFERENCES airports(icao),
    llm_enabled     BOOLEAN NOT NULL DEFAULT TRUE,
    state_machine   JSONB,  -- current state machine snapshot
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### `clearances`

```sql
CREATE TABLE clearances (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    controller_id   VARCHAR(32) NOT NULL REFERENCES controller_positions(id),
    target_callsign VARCHAR(16) NOT NULL,
    clearance_type  VARCHAR(32) NOT NULL,
    parameters      JSONB,
    transmission_text TEXT,
    source          VARCHAR(16) NOT NULL DEFAULT 'llm',  -- llm, template, manual
    state_machine_transition VARCHAR(32),
    accepted        BOOLEAN NOT NULL DEFAULT TRUE,
    issued_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_clearances_controller ON clearances (controller_id, issued_at DESC);
CREATE INDEX idx_clearances_callsign ON clearances (target_callsign, issued_at DESC);
```

### `radio_logs`

```sql
CREATE TABLE radio_logs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    controller_id   VARCHAR(32) NOT NULL REFERENCES controller_positions(id),
    callsign        VARCHAR(16) NOT NULL,
    direction       VARCHAR(8) NOT NULL,  -- inbound, outbound
    text            TEXT NOT NULL,
    audio_available BOOLEAN NOT NULL DEFAULT FALSE,
    audio_path      TEXT,  -- path to stored .wav file (optional)
    frequency_mhz   REAL NOT NULL,
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_radio_controller ON radio_logs (controller_id, recorded_at DESC);
CREATE INDEX idx_radio_callsign ON radio_logs (callsign, recorded_at DESC);
```

### `waypoints`

```sql
CREATE TABLE waypoints (
    id              SERIAL PRIMARY KEY,
    identifier      VARCHAR(8) NOT NULL,  -- e.g., "SXC", "LAX"
    lat             DOUBLE PRECISION NOT NULL,
    lon             DOUBLE PRECISION NOT NULL,
    region          VARCHAR(4),  -- FIR region code
    type            VARCHAR(16) NOT NULL DEFAULT 'waypoint',
    -- waypoint, vor, vordme, ndb, fix, airport
    frequency       REAL,  -- for navaids
    geometry        GEOGRAPHY(POINT, 4326),
    UNIQUE (identifier, region)
);

CREATE INDEX idx_waypoints_geom ON waypoints USING GIST (geometry);
CREATE INDEX idx_waypoints_id ON waypoints (identifier);
```

### `airways`

```sql
CREATE TABLE airways (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(8) NOT NULL,  -- e.g., "J1", "V23"
    type            VARCHAR(4) NOT NULL DEFAULT 'J',  -- J (jet), V (victor), Q, T
    from_wpt_id     INTEGER NOT NULL REFERENCES waypoints(id),
    to_wpt_id       INTEGER NOT NULL REFERENCES waypoints(id),
    min_altitude_ft INTEGER,
    max_altitude_ft INTEGER,
    direction       VARCHAR(4),  -- forward, backward, both
    geometry        GEOGRAPHY(LINESTRING, 4326),
    UNIQUE (name, from_wpt_id, to_wpt_id)
);
```

### `sid_star` (Procedures)

```sql
CREATE TABLE sid_star (
    id              SERIAL PRIMARY KEY,
    airport_id      INTEGER NOT NULL REFERENCES airports(id) ON DELETE CASCADE,
    name            VARCHAR(16) NOT NULL,  -- e.g., "LAXX8", "KIMMO1"
    type            VARCHAR(4) NOT NULL,  -- SID or STAR
    runways         TEXT[],  -- applicable runways
    waypoints       JSONB NOT NULL,  -- ordered array of waypoint identifiers
    altitude_restrictions JSONB,
    speed_restrictions    JSONB,
    UNIQUE (airport_id, name)
);
```

### `airspace`

```sql
CREATE TABLE airspace (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(64) NOT NULL,
    type            VARCHAR(16) NOT NULL,  -- class_a, class_b, class_c, class_d, class_e, class_g
    floor_ft        INTEGER NOT NULL,  -- MSL
    ceiling_ft      INTEGER NOT NULL,  -- MSL
    geometry        GEOGRAPHY(POLYGON, 4326) NOT NULL,
    controller_id   VARCHAR(32) REFERENCES controller_positions(id),
    UNIQUE (name, type)
);

CREATE INDEX idx_airspace_geom ON airspace USING GIST (geometry);
```

## PostGIS Usage

- **Distance queries**: Separation checks use `ST_Distance(geom1, geom2)` in meters, converted to NM
- **Containment**: `ST_Contains(airspace.geometry, flight.geometry)` for sector awareness
- **Bearing**: `ST_Azimuth()` for heading calculations
- **Nearest runway**: `ST_Distance()` ordered by proximity for approach sequencing

## Migration Strategy

- Alembic with versioned migrations (raw SQL, no autogenerate)
- Naming convention: `YYYYMMDD_HHMM_description.sql`
- All schema changes backward-compatible for one version
- Read replicas for flight_tracks queries; primary for all writes

## Connection Pool Configuration

```python
# Example asyncpg pool config
databases: {
  default: {
    pool_size: 10,
    max_overflow: 20,
    pool_timeout: 30,
    pool_recycle: 300,
    ssl: false,  # internal network
  }
}
```
