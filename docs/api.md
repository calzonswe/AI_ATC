# REST API Specification (OpenAPI 3.1)

Base URL: `http://localhost:8200/api/v1`

All endpoints require `Authorization: Bearer <token>` header unless marked `(public)`.

---

## Endpoints

### `GET /health` (public)

**Response `200`**

```json
{
  "status": "ok",
  "version": "0.1.0",
  "services": {
    "database": "connected",
    "ollama": "connected",
    "simconnect": "connected"
  },
  "uptime_seconds": 3600
}
```

---

### `GET /controllers`

List all active ATC controllers and their current state.

**Response `200`**

```json
{
  "controllers": [
    {
      "id": "KLAX_GND",
      "callsign": "KLAX_Ground",
      "type": "ground",
      "frequency_mhz": 121.7,
      "state": "active",
      "airport_icao": "KLAX",
      "active_traffic_count": 12,
      "current_state_machine": "ground_active"
    },
    {
      "id": "KLAX_TWR",
      "callsign": "KLAX_Tower",
      "type": "tower",
      "frequency_mhz": 118.3,
      "state": "active",
      "airport_icao": "KLAX",
      "active_traffic_count": 5,
      "current_state_machine": "tower_active"
    }
  ]
}
```

---

### `POST /controllers`

Create/spawn a new controller position.

**Request Body**

```json
{
  "type": "ground",
  "airport_icao": "KLAX",
  "frequency_mhz": 121.7,
  "callsign": "KLAX_Ground",
  "config": {
    "voice_profile": "female_en_us",
    "llm_enabled": true,
    "auto_sequence": true
  }
}
```

**Response `201`**

```json
{
  "id": "KLAX_GND",
  "callsign": "KLAX_Ground",
  "type": "ground",
  "frequency_mhz": 121.7,
  "state": "spawning",
  "airport_icao": "KLAX"
}
```

---

### `DELETE /controllers/{controller_id}`

Decommission a controller position.

**Response `204`**

---

### `GET /controllers/{controller_id}/state`

Get detailed state machine view.

**Response `200`**

```json
{
  "controller_id": "KLAX_GND",
  "state_machine": "ground_active",
  "state_machine_version": 42,
  "last_transition": "2026-07-29T10:32:15Z",
  "active_aircraft": [
    {
      "callsign": "UAL123",
      "state": "pushback",
      "parking_spot": "B12",
      "assigned_route": ["B12", "A", "RWY24L"],
      "hold_short_of": null,
      "last_contact": "2026-07-29T10:31:00Z"
    }
  ],
  "pending_clearances": [
    {
      "aircraft_id": "UAL123",
      "clearance_type": "pushback_approved",
      "direction": "tail_north"
    }
  ]
}
```

---

### `POST /controllers/{controller_id}/clear`

Issue a clearance from an external source (e.g., manual admin override).

**Request Body**

```json
{
  "target_callsign": "UAL123",
  "clearance_type": "takeoff_clearance",
  "parameters": {
    "runway": "24L",
    "wind_direction": 240,
    "wind_speed_kn": 8
  }
}
```

**Response `200`**

```json
{
  "accepted": true,
  "clearance_id": "clr_abc123",
  "state_machine_transition": "clear_for_takeoff",
  "generated_transmission": "UAL123, runway 24L, cleared for takeoff, wind 240 at 8."
}
```

---

### `GET /flights`

Query active tracked flights.

**Query Parameters**

| Param | Type | Description |
|-------|------|-------------|
| `callsign` | string | Filter by callsign (partial) |
| `controller_id` | string | Filter by controlling position |
| `state` | string | Filter by aircraft state |
| `limit` | integer | Max results (default 50, max 500) |
| `offset` | integer | Pagination offset |

**Response `200`**

```json
{
  "total": 42,
  "flights": [
    {
      "callsign": "UAL123",
      "icao_aircraft_type": "B738",
      "departure": "KLAX",
      "arrival": "KJFK",
      "assigned_controller": "KLAX_TWR",
      "state": "landing_clearance",
      "position": {
        "lat": 33.9425,
        "lon": -118.4081,
        "alt_ft": 1500,
        "heading": 240,
        "speed_kn": 180
      },
      "flight_plan": {
        "cruise_alt": 35000,
        "route": ["LAX", "SXC", "LAS", "JFK"],
        "eta": "2026-07-29T14:30:00Z"
      }
    }
  ]
}
```

---

### `PUT /flights/{callsign}/flight-plan`

Submit or update a flight plan.

**Request Body**

```json
{
  "aircraft_type": "B738",
  "departure": "KLAX",
  "arrival": "KJFK",
  "alternate": "KEWR",
  "cruise_altitude_ft": 35000,
  "route": "LAX SXC LAS JFK",
  "estimated_departure": "2026-07-29T12:00:00Z",
  "fuel_minutes": 240,
  "passengers": 150
}
```

**Response `200`**

```json
{
  "callsign": "UAL123",
  "status": "accepted",
  "flight_plan_id": "fp_xyz789"
}
```

---

### `POST /clearances/validate`

Validate a clearance string against phraseology rules without executing.

**Request Body**

```json
{
  "clearance_text": "UAL123, runway 24L, cleared for takeoff",
  "context": {
    "controller_type": "tower",
    "airport_icao": "KLAX",
    "active_runway": "24L"
  }
}
```

**Response `200`**

```json
{
  "valid": true,
  "warnings": [],
  "normalized": "UAL123, runway 24L, cleared for takeoff."
}
```

---

### `GET /airspace/{airport_icao}`

Get airspace structure and geometry for an airport.

**Response `200`**

```json
{
  "airport_icao": "KLAX",
  "lat": 33.9425,
  "lon": -118.4081,
  "elevation_ft": 125,
  "runways": [
    {
      "designation": "24L",
      "surface": "concrete",
      "length_ft": 8925,
      "heading": 242,
      "threshold_lat": 33.9425,
      "threshold_lon": -118.4081,
      "ils_frequency_mhz": 109.3
    }
  ],
  "frequencies": {
    "ground": 121.7,
    "tower": 118.3,
    "departure": 125.2,
    "approach": 124.0
  },
  "sids": ["LAXX8", "ORCK9"],
  "stars": ["KIMMO1", "SHIVE1"]
}
```

---

### `GET /metrics` (public, Prometheus format)

Returns Prometheus-formatted metrics.

**Response `200`** — `text/plain; version=0.0.4`

```
atc_radio_calls_total{controller="KLAX_TWR"} 245
atc_llm_inference_duration_ms{quantile="0.95"} 3200
atc_audio_pipeline_latency_ms{stage="stt"} 850
atc_active_aircraft 17
```

---

## Error Responses

All errors follow RFC 9457 (Problem Details):

```json
{
  "type": "https://errors.openatc.dev/clearance-validation-failed",
  "title": "Clearance Validation Failed",
  "status": 422,
  "detail": "Takeoff clearance requires active runway assignment",
  "instance": "/api/v1/controllers/KLAX_TWR/clear",
  "errors": [
    {
      "field": "parameters.runway",
      "message": "field required"
    }
  ]
}
```

| Status | Meaning |
|--------|---------|
| 400 | Bad request — malformed body |
| 401 | Missing or invalid auth token |
| 403 | Valid token but insufficient scope |
| 404 | Resource not found |
| 409 | Conflict — e.g., controller already exists |
| 422 | Validation failure |
| 429 | Rate limited |
| 500 | Internal server error |
| 503 | Service unavailable (Ollama or DB down) |

## Authentication

All `POST`, `PUT`, `DELETE` endpoints require a Bearer token issued at deployment time. See `security.md` for token generation and rotation.
