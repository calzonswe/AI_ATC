# Architecture Decision Records (ADR)

## ADR Template

```markdown
# ADR-NNN: <Title>

## Status

[Proposed | Accepted | Superseded | Deprecated]

## Context

What is the issue motivating this decision? What constraints are in play?

## Decision

What is the change being made? What are we doing and why?

## Consequences

What becomes easier or harder? What trade-offs are being made?

## Compliance

How will compliance with this decision be enforced? (linting, CI checks, code review)

## Notes

Any links, references, or follow-up decisions.
```

---

## ADR-001: Monorepo with Strict Service Boundaries

### Status

Accepted

### Context

The system consists of multiple services (SimConnect client, ATC engine, speech pipeline, LLM proxy, web UI) that must be independently deployable and testable. A monorepo simplifies dependency management and CI while maintaining separation.

### Decision

Use a single monorepo with each service in its own top-level directory. Each service has its own `pyproject.toml` / `.csproj` / `package.json`. Cross-service communication is exclusively over gRPC, WebSocket, or NATS — never via shared in-process memory or direct file I/O.

### Consequences

- **Easier**: Shared protobuf definitions, unified CI/CD, cross-service refactoring
- **Harder**: Requires disciplined interface boundaries, no shortcut imports between services
- **Risk**: Monorepo size growth; mitigated by CI caching

### Compliance

- CI enforces: no cross-service imports in Python (ruff `TID253`), C# (project reference restrictions), TypeScript (path aliases)

---

## ADR-002: PostgreSQL + PostGIS over Specialized Spatial Database

### Status

Accepted

### Context

The system needs to store geospatial data (airports, waypoints, airspace polygons, flight tracks) and run spatial queries (containment, distance, bearing). Options considered: PostgreSQL + PostGIS, CockroachDB + PostGIS, DuckDB, SQLite + SpatiaLite.

### Decision

Use PostgreSQL 16 with PostGIS 3.4. CockroachDB was rejected due to PostGIS incompatibility for production use. DuckDB/SQLite were rejected due to need for concurrent write access (track ingestion, clearance logging).

### Consequences

- **Easier**: Rich spatial query support, well-known tooling, Alembic migrations
- **Harder**: Schema changes require migration management; no horizontal scaling without read replicas
- **Mitigation**: Flight tracks partitioned by month for query performance; read replicas for analytical queries

### Compliance

- All spatial queries must use PostGIS functions (not application-level calculation)
- All schema changes must have a corresponding Alembic migration

---

## ADR-003: Deterministic State Machines for Controller Logic

### Status

Accepted

### Context

ATC safety depends on correct, predictable behavior. LLM outputs are non-deterministic and may hallucinate. We must ensure that safety-critical decisions (separation, runway assignment) never depend on LLM output.

### Decision

Implement all ATC controller logic as deterministic, pure-Python state machines with explicit transitions and guards. The LLM generates only natural-language radio call text, which is validated against the current state machine before transmission. The state machine can function with zero LLM dependency (template-based fallback).

### Consequences

- **Easier**: Verification through unit tests (100% coverage for state machines); predictable behavior under load
- **Harder**: No AI-generated creative clearances; state machine must anticipate all valid transitions
- **Trade-off**: Accepts limited flexibility in exchange for safety guarantees

### Compliance

- State machine transitions must be unit-tested for all valid/invalid event combinations
- Code review required for any state machine modification
- Integration tests verify: LLM cannot override state machine

---

## ADR-004: NATS JetStream for Internal Messaging

### Status

Accepted

### Context

Services need a message broker for:
1. Telemetry streaming (high-throughput, many-to-one)
2. Audio streaming (real-time, low-latency)
3. Event notifications (handoff, state changes)

Options: NATS JetStream, RabbitMQ, Redis Streams, Kafka.

### Decision

Use NATS JetStream. Kafka was rejected as too heavy for single-host deployment. RabbitMQ was rejected for weaker streaming/audio support. Redis Streams lacks persistence guarantees. NATS provides:
- At-least-once delivery via JetStream
- Pub/sub and request-reply patterns
- Low latency (~1ms) suitable for audio
- Built-in object store for model distribution (future)

### Consequences

- **Easier**: Simple deployment (single binary), low resource usage, good streaming support
- **Harder**: Smaller ecosystem than Kafka; fewer client libraries
- **Trade-off**: Accepts weaker ordering guarantees (partition-level only) for performance

### Compliance

- All audio streaming must use JetStream (persistent) with explicit ACK
- Telemetry may use core NATS (at-most-once) with subscriber-side dedup

---

## ADR-005: Whisper.cpp + Piper TTS for Local Speech

### Status

Accepted

### Context

Speech-to-text and text-to-speech must run entirely offline with no cloud API dependency. Must run on consumer GPUs (6-12GB VRAM) and support streaming.

### Decision

Use Whisper.cpp for STT (GGML format models, large-v3-q5_0) and Piper for TTS (ONNX models). Compared to alternatives:
- **Whisper.cpp vs faster-whisper**: Whisper.cpp has better GPU support via CUDA; faster-whisper (CTranslate2) is faster on CPU
- **Piper vs Coqui TTS**: Piper is actively maintained, smaller models, faster inference
- **Piper vs Espeak**: Piper produces natural prosody; espeak is robotic

### Consequences

- **Easier**: Both projects have Python bindings; models are permissively licensed; GPU acceleration via CUDA
- **Harder**: Whisper.cpp large-v3 requires ~4GB VRAM; Piper medium requires ~500MB
- **Mitigation**: Model quantization (q5_0 for Whisper, low for Piper); CPU-only fallback

### Compliance

- STT/TTS must use the pipeline interface defined in `docs/speech.md`
- Models are version-pinned in Docker Compose configuration

---

## ADR-006: FastAPI with asyncpg (No ORM)

### Status

Accepted

### Context

The ATC Engine needs high-throughput database access for telemetry ingestion and flight tracking. An ORM would add overhead and complexity for what is essentially high-frequency writes and spatial queries.

### Decision

Use raw SQL with `asyncpg` for database access. Alembic handles migrations (with raw SQL, not autogenerate). No ORM layer.

### Consequences

- **Easier**: Full control over query performance; can use PostGIS functions directly; lower overhead
- **Harder**: More boilerplate for CRUD operations; no migration autogeneration
- **Mitigation**: Repository pattern to encapsulate SQL; typed query builders for common operations

### Compliance

- All database access must go through repository classes (no raw `conn.execute()` in route handlers)
- SQL in repositories must have type-annotated return types

---

## ADR-007: C# .NET for SimConnect Client

### Status

Accepted

### Context

The SimConnect SDK is a native COM library exposed to .NET via `Microsoft.FlightSimulator.SimConnect`. The reference implementation is C#. Using another language would require P/Invoke or a custom IPC bridge.

### Decision

Implement the SimConnect client in C# .NET 8. This is the only non-Python service. All other services communicate with it via WebSocket (telemetry) and NATS (audio).

### Consequences

- **Easier**: Direct SimConnect SDK usage; well-documented patterns from MSFS community
- **Harder**: Mixed-language monorepo; CI needs .NET SDK + Python
- **Mitigation**: All cross-service contracts are language-agnostic (JSON, protobuf, PCM audio)

### Compliance

- SimConnect client must implement the `TelemetryFrame` schema from `docs/protocol.md`
- Audio must use the wire format from `docs/protocol.md`

---

## ADR-008: WebSocket for SimConnect ↔ ATC Engine

### Status

Accepted

### Context

The SimConnect client runs outside Docker on the host (MSFS machine). It needs a real-time bidirectional connection to the ATC Engine. Options: gRPC, WebSocket, raw TCP.

### Decision

Use WebSocket (WSS in production) for telemetry and events. gRPC was rejected because:
- HTTP/2 not always available on host network configuration
- .NET gRPC client has more complex setup
- WebSocket is simpler for JSON streaming and works through proxies

### Consequences

- **Easier**: Simple setup, works through firewalls/proxies, easy to debug with browser tools
- **Harder**: No built-in schema validation (mitigated by Pydantic server-side)
- **Trade-off**: WebSocket frame overhead (2-10 bytes) vs gRPC/Protobuf is negligible for 10Hz telemetry

### Compliance

- All WebSocket messages must follow the envelope in `docs/websocket.md`
- Server must validate all incoming messages against Pydantic schemas

---

## ADR-009: Ollama with 8B+ Parameter Models as Minimum

### Status

Accepted

### Context

The LLM must generate realistic ATC phraseology across diverse scenarios. Smaller models (<7B) produce unacceptably high error rates for specialized ATC terminology.

### Decision

Mandate minimum 8B parameter models (llama3.1:8b minimum; qwen2.5:14b or mixtral:8x7b recommended). Larger models improve phraseology accuracy and reduce hallucination. All models run via Ollama for unified API and GPU support.

### Consequences

- **Easier**: Better quality outputs; Ollama handles model downloading and quantization
- **Harder**: Requires 8-16GB VRAM for acceptable performance; 32GB+ recommended for 14B+ models
- **Fallback**: Template-based responses work without LLM; system degrades gracefully

### Compliance

- LLM inference goes through the LLM Proxy (never direct to Ollama from other services)
- Phraseology validator must catch and reject invalid LLM outputs

---

## ADR-010: OpenTelemetry for Observability

### Status

Accepted

### Context

Distributed tracing across 5+ services requires a unified observability framework. Need to track request latencies through the speech pipeline (STT → LLM → TTS) and identify bottlenecks.

### Decision

Use OpenTelemetry (OTEL) for distributed tracing and metrics export. Each service exports traces and metrics via OTLP or Prometheus. Key traces: WebSocket message processing, audio pipeline, LLM inference.

### Consequences

- **Easier**: Standard protocol for traces/metrics; works with many backends (Jaeger, Grafana, Datadog)
- **Harder**: More dependencies; requires collector deployment for production
- **Trade-off**: OTEL overhead (~1% latency) is acceptable for observability

### Compliance

- Each service must create spans for every external operation (DB query, HTTP call, NATS publish)
- Audio pipeline must record per-chunk latency histograms
