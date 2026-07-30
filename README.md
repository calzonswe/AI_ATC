# OpenATC

**Offline, local-first AI Air Traffic Control system for Microsoft Flight Simulator.**

OpenATC provides realistic ATC experiences powered by local LLMs (via Ollama). It simulates controller positions, processes pilot speech, and manages aircraft through all flight phases — all running on your own hardware with no internet dependency.

## Features

- **AI-Powered ATC** — Realistic controller responses via local LLMs (Qwen3, Llama, etc.)
- **Full Flight Lifecycle** — Startup, pushback, taxi, takeoff, climb, cruise, descent, ILS approach, landing, taxi to gate
- **Multiple Controller Positions** — GROUND, TOWER, DEPARTURE, APPROACH, CENTER, ATIS, DELIVERY
- **World Simulation Engine** — Aircraft tracking, conflict detection, weather, waypoints
- **Speech Pipeline** — Whisper STT → LLM → TTS for natural voice communication
- **Desktop GUI Client** — PySide6-based radio panel with PTT keybinding, available as standalone `.exe`
- **SimConnect Integration** — Real-time telemetry from MSFS 2020/2024 (mock mode for testing)
- **Admin Dashboard** — Real-time metrics, aircraft tracking, system monitoring
- **Docker Deployment** — One-command infrastructure setup (Postgres, Redis, Qdrant, Ollama, Whisper)

## Quick Start

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (with WSL2 on Windows)
- [Ollama](https://ollama.com) — or let Docker run it automatically (see below)
- NVIDIA GPU recommended for Whisper STT; graceful CPU fallback

### 1. Start the Entire Backend (Zero-Install)

```bash
git clone https://github.com/your-org/openatc.git
cd openatc
cp .env.example .env
# Edit .env to set your Ollama model (default: qwen3:30b)
docker compose up -d --build
```

This single command provisions everything:

| Service | Role | Port |
|---|---|---|
| `ollama` | LLM inference (Qwen3, Llama, etc.) | 11434 |
| `whisper-stt` | Speech-to-text (faster-whisper) | 9000 |
| `postgres` | Primary database (PostGIS) | 5432 |
| `redis` | Message broker / cache | 6379 |
| `qdrant` | Vector database for procedures | 6333 |
| `controller-service` | ATC state machines + LLM integration | 8100 |
| `fastapi-server` | WebSocket API + Admin dashboard | 8000 |
| `adminer` | Database management UI | 8080 |

The `ollama` container **automatically pulls the configured model** on startup — no manual `ollama pull` needed.

**GPU Support:** The compose file includes `deploy.resources.reservations` for NVIDIA GPUs on the `ollama` and `whisper-stt` services. If no GPU is detected, they gracefully fall back to CPU.

### 2. Build the Windows Client (.exe)

On your gaming PC, build a single standalone `.exe`:

```powershell
# From PowerShell (Windows):
.\scripts\build_exe.ps1
```

Or from WSL/macOS:

```bash
./scripts/build_exe.sh
```

Output: `apps/client/dist/OpenATC_Client/OpenATC_Client.exe`

Copy the entire `dist/OpenATC_Client/` folder to any Windows PC and run `OpenATC_Client.exe` — no Python or dependencies required.

### 3. Connect and Fly

1. Launch `OpenATC_Client.exe` on your gaming PC
2. Enter the Docker host's IP address (e.g., `192.168.1.50`) and port `8000`
3. Set your callsign and aircraft type
4. Configure Push-To-Talk key (default: Space)
5. Click **Connect**
6. Fly your flight plan — the GUI shows radio frequencies, controller handoffs, and PTT status

### Admin Dashboard

Open http://localhost:8000/api/v1/admin/dashboard

Default credentials: `admin` / `atc_admin_secret` (configured in `.env`)

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────────┐
│  MSFS        │────▶│  Client .exe │────▶│  FastAPI Server  │
│  SimConnect  │     │  (Gaming PC) │     │  (Docker)        │
└──────────────┘     └──────────────┘     └────────┬─────────┘
                                                    │
                    ┌───────────────────────────────┼──────────────┐
                    │                               │              │
           ┌────────▼────────┐            ┌─────────▼──────┐      │
           │  Controller     │            │  World Engine  │      │
           │  Service        │◀───────────│  Service       │      │
           │  (LLM + State)  │            │  (Simulation)  │      │
           └────────┬────────┘            └────────┬───────┘      │
                    │                              │              │
           ┌────────▼────────┐            ┌─────────▼───────┐     │
           │  Ollama (LLM)   │            │  Postgres /     │     │
           │  Whisper (STT)  │            │  Redis / Qdrant │     │
           │  TTS Engine     │            │  (Infra)        │     │
           └─────────────────┘            └─────────────────┘     │
```

## Configuration

Copy `.env.example` to `.env` and customize:

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_URL` | `http://ollama:11434` | Ollama host (Docker internal) |
| `OLLAMA_MODEL` | `qwen3:30b` | LLM model (auto-pulled on startup) |
| `WHISPER_URL` | `http://whisper-stt:9000` | Whisper STT service URL |
| `WHISPER_MODEL_SIZE` | `base` | Model size: tiny/base/small/medium/large |
| `POSTGRES_*` | — | Database credentials |
| `ATC_API_TOKEN` | — | API bearer token |
| `AUTH_JWT_SECRET` | — | JWT signing key (change me!) |
| `AUTH_ADMIN_USERNAME` | `admin` | Admin dashboard login |
| `AUTH_ADMIN_PASSWORD` | `atc_admin_secret` | Admin dashboard password |
| `LOG_LEVEL` | `info` | Log verbosity |

## Building the Client .exe (Detailed)

### Requirements for building

- Python 3.10+ with `pip`
- Windows, macOS, or Linux

### Build steps

```bash
# 1. Install build tools
pip install pyinstaller

# 2. Install runtime dependencies
pip install PySide6 sounddevice numpy

# 3. Build the executable
cd apps/client
pyinstaller --clean --noconfirm build_exe.spec
```

The built executable will be at `apps/client/dist/OpenATC_Client/OpenATC_Client.exe`.

### For Windows gaming PCs

No Python or dependencies needed on the target PC — just copy the `dist/OpenATC_Client/` folder and run the `.exe`. The client connects to the Docker backend over your local network.

## Development

### Setup

```bash
make setup           # One-command dev environment setup
source .venv/bin/activate
```

### Testing

```bash
make test-all        # All tests (server + client + e2e)
make test-e2e        # End-to-end flight simulation
make test-cov        # With coverage report
```

### Linting & Type Checking

```bash
make lint            # Ruff check
make lint-fix        # Auto-fix issues
uv run pyright       # Type checking
```

## Project Structure

```
├── apps/
│   ├── server/          # FastAPI WebSocket + HTTP API server
│   └── client/          # SimConnect client (CLI + PySide6 GUI)
├── services/
│   ├── controller/      # ATC controller state machines + LLM
│   ├── world/           # World simulation engine
│   ├── speech/          # STT → LLM → TTS audio pipeline
│   ├── atis/            # ATIS broadcast generation
│   └── navigation/      # ILS, vectors, taxi routing, holds
├── packages/
│   ├── simconnect/      # SimConnect abstraction (real + mock)
│   ├── protocol/        # Message protocol definitions
│   └── common/          # Shared utilities
├── docker/
│   ├── docker-compose.yml   # Full backend orchestration
│   ├── Dockerfile.server
│   ├── Dockerfile.controller
│   ├── Dockerfile.whisper
│   ├── ollama-init.sh       # Auto-model-pull on startup
│   └── whisper_service.py   # Whisper STT FastAPI service
├── tests/e2e/           # End-to-end flight simulation tests
├── scripts/
│   ├── setup.sh         # Dev environment bootstrap
│   ├── build_exe.sh     # Unix client build
│   └── build_exe.ps1    # Windows client build
├── .env.example         # Environment template
├── Makefile             # Common commands
└── docker-compose.yml   # Root compose (includes docker/)
```

## License

MIT
