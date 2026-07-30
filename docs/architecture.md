# System Architecture

## Monorepo Service Boundaries

```
openatc/
├── apps/
│   ├── server/                 # FastAPI entrypoint — REST + WebSocket gateway
│   │   ├── src/
│   │   └── tests/
│   └── client/                 # SimConnect / external client application
│       ├── src/
│       └── tests/
├── services/
│   ├── controller/             # ATC controller logic engine — deterministic state machines
│   │   ├── src/
│   │   └── tests/
│   ├── world/                  # World state manager — airspace, airports, weather, traffic
│   │   ├── src/
│   │   └── tests/
│   ├── navigation/             # Spatial / routing calculation engine
│   │   ├── src/
│   │   └── tests/
│   ├── speech/                 # Whisper.cpp STT + Piper TTS integration service
│   │   ├── src/
│   │   └── tests/
│   └── atis/                   # ATIS broadcast service
│       ├── src/
│       └── tests/
├── packages/
│   ├── common/                 # Shared models, utilities, base classes
│   │   ├── src/
│   │   └── tests/
│   ├── protocol/               # WebSocket/RPC schemas and protocol definitions
│   │   ├── src/
│   │   └── tests/
│   ├── simconnect/             # SimConnect bindings and interface wrappers
│   │   ├── src/
│   │   └── tests/
│   └── shared/                 # Shared UI / core constants
│       ├── src/
│       └── tests/
├── docker/                     # Dockerfiles and service build contexts
├── scripts/                    # Dev, build, and database migration scripts
├── docs/                       # Architecture documentation (Phase 0)
└── tests/                      # End-to-end and integration tests
```

## System Context (C4 Level 1)

```mermaid
C4Context
  Person(pilot, "Pilot", "MSFS user interacting via radio")
  System_Ext(msfs, "Microsoft Flight Simulator", "SimConnect API")

  Boundary_Boundary("openatc", "AI-ATC System") {
    System(simconnect, "SimConnect Client", "C# — reads aircraft state, injects audio")
    System(engine, "ATC Engine", "Python — controller state machines, separation logic")
    System(speech, "Speech Pipeline", "Python — STT → LLM → TTS streaming")
    System(llm, "LLM Proxy", "Python — Ollama context management & prompt pipeline")
    System(ui, "Web UI", "TypeScript — pilot dashboard & radio overlay")
  }

  Rel(pilot, msfs, "Files")
  Rel(pilot, ui, "Configures / monitors")
  Rel(msfs, simconnect, "SimConnect protocol")
  Rel(simconnect, engine, "gRPC / WebSocket telemetry")
  Rel(simconnect, speech, "Audio loopback stream")
  Rel(engine, speech, "Radio event triggers")
  Rel(speech, llm, "HTTP generate requests")
  Rel(engine, ui, "WebSocket state push")
```

## Container Diagram (C4 Level 2)

```mermaid
C4Container
  Person(pilot, "Pilot", "MSFS user")

  System_Boundary(simconnect_boundary, "SimConnect Client") {
    Container(connector, "SimConnect Connector", "C#", "Reads aircraft position, attitude, engine state")
    Container(audio_loopback, "Audio Loopback", "C#", "Captures pilot mic, plays TTS audio")
    Container(telemetry_publisher, "Telemetry Publisher", "C#", "Streams JSON telemetry over WebSocket")
  }

  System_Boundary(engine_boundary, "Apps Layer") {
    Container(server, "API Server", "Python / FastAPI", "REST + WebSocket gateway, request routing")
    Container(client_app, "Client App", "Python / C#", "SimConnect connector and audio loopback")
  }

  System_Boundary(services_boundary, "Services Layer") {
    Container(controller, "Controller Service", "Python", "Ground, Tower, Departure, Approach, Center state machines")
    Container(world, "World Service", "Python", "Airspace, airports, weather, traffic state")
    Container(navigation, "Navigation Service", "Python", "SID/STAR, separation, great-circle routing")
    Container(speech, "Speech Service", "Python / C++", "Whisper.cpp STT + Piper TTS orchestration")
    Container(atis, "ATIS Service", "Python", "Automated weather & airport information broadcast")
  }

  System_Boundary(packages_boundary, "Packages Layer") {
    Container(common, "Common", "Python", "Shared models, utilities, base classes")
    Container(protocol, "Protocol", "Python", "WebSocket/RPC schemas, protobuf definitions")
    Container(simconnect_pkg, "SimConnect", "Python", "SimConnect bindings and interface wrappers")
    Container(shared, "Shared", "Python", "UI/core constants")
  }

  System_Boundary(infra_boundary, "Infrastructure") {
    ContainerDb(postgis, "PostgreSQL + PostGIS", "Database", "Airspace, waypoints, flight plans")
    Container(ollama, "Ollama", "Go", "Local LLM inference server")
  }

  Rel(pilot, connector, "Uses")
  Rel(connector, client_app, "Runs")
  Rel(client_app, server, "ws://", "WebSocket telemetry + audio")
  Rel(server, controller, "gRPC / import", "Delegates ATC logic")
  Rel(server, world, "gRPC / import", "Queries world state")
  Rel(server, navigation, "gRPC / import", "Routing calculations")
  Rel(server, speech, "gRPC / import", "Triggers STT/TTS")
  Rel(server, atis, "gRPC / import", "ATIS generation")
  Rel(server, postgis, "SQL", "asyncpg")
  Rel(server, ollama, "HTTP", "LLM inference (via protocol)")
  Rel(controller, common, "Uses")
  Rel(world, common, "Uses")
  Rel(navigation, common, "Uses")
  Rel(speech, common, "Uses")
  Rel(atis, common, "Uses")
  Rel(server, common, "Uses")
  Rel(server, protocol, "Uses")
  Rel(client_app, simconnect_pkg, "Uses")
```

## Data Flow — Pilot Radio Call End-to-End

```mermaid
sequenceDiagram
  participant P as Pilot (MSFS)
  participant CL as apps/client
  participant SRV as apps/server
  participant CTRL as services/controller
 participant SP as services/speech
  participant OLL as Ollama (docker)

  P->>CL: Push-to-talk audio (mic)
  CL->>SRV: ws:// radio_transmit (PCM audio)
  SRV->>SP: Transcribe request
  SP->>SP: Whisper.cpp STT
  SP->>SRV: Transcribed text
  SRV->>CTRL: Validate + determine controller
  CTRL->>CTRL: Run state machine
  CTRL->>SRV: Clearance intent
  SRV->>SP: Synthesize request
  SP->>OLL: HTTP /api/generate (context)
  OLL->>SP: Generated response text
  SP->>SP: Validate phraseology
  SP->>SP: Piper TTS synthesis
  SP->>SRV: PCM + transcript
  SRV->>CL: atc_audio (PCM playback)
  CL->>P: Radio call audio in MSFS
```

## Data Flow — Telemetry Ingestion

```mermaid
sequenceDiagram
  participant MSFS as MSFS SimConnect
  participant CL as apps/client
  participant SRV as apps/server
  participant W as services/world
  participant DB as PostgreSQL

  loop Every 100ms
    MSFS->>CL: SimObject data
    CL->>CL: Marshal to JSON
    CL->>SRV: ws:// telemetry frame
    SRV->>W: Update world state
    W->>DB: Persist flight track (batch)
  end
```

## Technology Stack

| Component | Location | Language/Runtime | Key Libraries |
|-----------|----------|-----------------|---------------|
| API Server | `apps/server` | Python 3.12 | FastAPI, asyncpg, pydantic, httpx |
| Client App | `apps/client` | Python 3.12 / C# .NET | websockets, httpx |
| Controller Service | `services/controller` | Python 3.12 | asyncpg, pydantic |
| World Service | `services/world` | Python 3.12 | asyncpg, pydantic |
| Navigation Service | `services/navigation` | Python 3.12 | geographiclib, shapely |
| Speech Service | `services/speech` | Python 3.12 / C++ (Whisper.cpp / Piper) | whisper-cpp-python, piper-tts, numpy |
| ATIS Service | `services/atis` | Python 3.12 | openatc-speech |
| Common Package | `packages/common` | Python 3.12 | pydantic |
| Protocol Package | `packages/protocol` | Python 3.12 | pydantic, grpcio |
| SimConnect Package | `packages/simconnect` | Python 3.12 | pydantic |
| Shared Package | `packages/shared` | Python 3.12 | pydantic |
| Database | `docker` (PostgreSQL) | PostgreSQL 16 + PostGIS 3.4 | — |
| LLM Server | `docker` (Ollama) | Go (Ollama) | llama.cpp backend |
