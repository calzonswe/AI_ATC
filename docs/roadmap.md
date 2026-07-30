# Implementation Roadmap

## Phase Overview

| Phase | Name | Duration | Status |
|-------|------|----------|--------|
| **0** | **Architecture Documentation** | **Week 1** | **✅ COMPLETE** |
| 1 | Monorepo Scaffolding | Week 1 | 🔲 Pending |
| 2 | Database Schema & Migrations | Week 2 | 🔲 Pending |
| 3 | SimConnect Client — Connection | Week 2 | 🔲 Pending |
| 4 | SimConnect Client — Telemetry Streaming | Week 3 | 🔲 Pending |
| 5 | ATC Engine — Core Framework | Week 3 | 🔲 Pending |
| 6 | ATC Engine — Ground Controller | Week 4 | 🔲 Pending |
| 7 | ATC Engine — Tower Controller | Week 4 | 🔲 Pending |
| 8 | ATC Engine — Departure Controller | Week 5 | 🔲 Pending |
| 9 | ATC Engine — Approach Controller | Week 5 | 🔲 Pending |
| 10 | ATC Engine — Center Controller | Week 6 | 🔲 Pending |
| 11 | Controller Handoff Protocol | Week 6 | 🔲 Pending |
| 12 | Web UI — Scaffolding & Connection | Week 7 | 🔲 Pending |
| 13 | Web UI — Strip Board & Radar Display | Week 7 | 🔲 Pending |
| 14 | Web UI — Radio Log & Settings | Week 8 | 🔲 Pending |
| 15 | Speech Pipeline — Whisper.cpp Integration | Week 8 | 🔲 Pending |
| 16 | Speech Pipeline — Piper TTS Integration | Week 9 | 🔲 Pending |
| 17 | Speech Pipeline — Audio Router & VAD | Week 9 | 🔲 Pending |
| 18 | LLM Proxy — Ollama Integration | Week 10 | 🔲 Pending |
| 19 | LLM Proxy — Context Management | Week 10 | 🔲 Pending |
| 20 | LLM Proxy — Phraseology Validation | Week 11 | 🔲 Pending |
| 21 | SimConnect Client — Audio Loopback | Week 11 | 🔲 Pending |
| 22 | End-to-End Integration Testing | Week 12 | 🔲 Pending |
| 23 | Performance Tuning & Latency Optimization | Week 13 | 🔲 Pending |
| 24 | Phraseology Coverage Expansion | Week 14 | 🔲 Pending |
| 25 | Deployment Automation & Documentation | Week 15 | 🔲 Pending |
| 26 | Release & User Acceptance Testing | Week 16 | 🔲 Pending |

## Phase Details

### Phase 0 — Architecture Documentation (✅ COMPLETE)

- [x] `docs/vision.md` — System philosophy and design principles
- [x] `docs/architecture.md` — System architecture, C4 diagrams, service boundaries
- [x] `docs/coding-standards.md` — Language-specific conventions
- [x] `docs/api.md` — REST API specification with JSON schemas
- [x] `docs/websocket.md` — WebSocket event schemas
- [x] `docs/protocol.md` — Protobuf and binary payload definitions
- [x] `docs/controller-system.md` — State machines for all ATC positions
- [x] `docs/speech.md` — STT/LLM/TTS pipeline design
- [x] `docs/database.md` — PostgreSQL + PostGIS schema
- [x] `docs/client.md` — SimConnect client specification
- [x] `docs/deployment.md` — Docker Compose topology
- [x] `docs/security.md` — Auth mechanics and security architecture
- [x] `docs/roadmap.md` — Phased implementation plan
- [x] `docs/decisions.md` — Architecture Decision Records

### Phase 1 — Monorepo Scaffolding

- Create `simconnect-client/` C# project with .NET 8
- Create `atc-engine/` Python project with FastAPI
- Create `speech-pipeline/` Python project
- Create `llm-proxy/` Python project
- Create `web-ui/` TypeScript React project with Vite
- Create `docker/` directory with initial Dockerfiles
- Create `protos/` directory with protobuf definitions
- Configure linting (ruff, dotnet format, ESLint) in CI
- Configure pre-commit hooks

### Phase 2 — Database Schema & Migrations

- Implement all tables from `docs/database.md`
- Create Alembic migration pipeline
- Seed airports, runways, frequencies for 10 major US airports
- Seed waypoints, airspace, airways for LAX/KLAX area
- Add PostGIS spatial indexes
- Implement asyncpg connection pool

### Phase 3 — SimConnect Client — Connection

- Implement SimConnect connection with auto-reconnect
- Register data definitions for aircraft state
- Handle MSFS connect/disconnect lifecycle
- Logging and health reporting

### Phase 4 — SimConnect Client — Telemetry Streaming

- Marshal SimConnect data to JSON
- Implement WebSocket publisher
- Implement NATS JetStream publisher
- Test telemetry at 10 Hz with minimal jitter

### Phase 5 — ATC Engine — Core Framework

- FastAPI application scaffold with middleware (CORS, auth, rate limiting)
- WebSocket connection manager
- Shared state models (aircraft, clearance, controller)
- gRPC server for internal communication
- Prometheus metrics endpoint

### Phase 6-10 — Controller State Machines

- Implement state machines per `docs/controller-system.md`
- Integration with telemetry input
- Separation rule enforcement
- Flight tracking and position correlation
- Unit tests for each state machine

### Phase 11 — Controller Handoff Protocol

- Implement inter-controller handshake
- Frequency change messaging
- Transfer of control responsibility
- Handoff timeout and escalation

### Phase 12-14 — Web UI

- React scaffold with routing
- WebSocket connection manager with auto-reconnect
- Strip board component (active flights list)
- Simple radar display (HTML5 Canvas or SVG)
- Radio transcript log
- Settings panel (frequency tuning, volume)

### Phase 15-17 — Speech Pipeline

- Whisper.cpp model loading and inference
- Streaming transcription with VAD
- Piper TTS model loading and streaming synthesis
- Audio router with jitter buffer management
- Radio effect DSP (bandpass, compression)

### Phase 18-20 — LLM Proxy

- Ollama HTTP client with connection pooling
- Context manager with sliding window prompt
- Phraseology validator rule engine
- Fallback template system
- Rate limiting and concurrency control

### Phase 21 — SimConnect Audio Loopback

- WASAPI microphone capture
- VAD trigger for push-to-talk
- WASAPI speaker playback
- Jitter buffer for TTS playback
- Resampling pipeline (48k ↔ 16k / 22.05k)

### Phase 22-26 — Integration & Release

- End-to-end test: MSFS → SimConnect → ATC Engine → LLM → TTS → MSFS
- Load testing with simulated traffic (50 aircraft)
- Latency profiling and optimization
- Phraseology rule expansion (IFR, VFR, emergency)
- Documentation finalization
- Performance benchmarks documented
