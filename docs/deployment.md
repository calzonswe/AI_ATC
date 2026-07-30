# Deployment

## Docker Compose Topology

```yaml
version: "3.8"

services:
  postgres:
    image: postgis/postgis:16-3.4
    container_name: openatc-postgres
    restart: unless-stopped
    environment:
      POSTGRES_DB: openatc
      POSTGRES_USER: openatc
      POSTGRES_PASSWORD: ${DB_PASSWORD:?error}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./docker/postgres/init:/docker-entrypoint-initdb.d
    ports:
      - "5432:5432"
    networks:
      - openatc-net
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U openatc"]
      interval: 10s
      timeout: 5s
      retries: 5

  nats:
    image: nats:2.10-alpine
    container_name: openatc-nats
    restart: unless-stopped
    command: ["-js", "--sd", "/data", "-m", "8222"]
    volumes:
      - nats_data:/data
    ports:
      - "4222:4222"   # client
      - "8222:8222"   # HTTP monitoring
    networks:
      - openatc-net

  atc-engine:
    build:
      context: .
      dockerfile: docker/atc-engine.Dockerfile
    container_name: openatc-engine
    restart: unless-stopped
    depends_on:
      postgres:
        condition: service_healthy
      nats:
        condition: service_started
    environment:
      DB_DSN: postgresql+asyncpg://openatc:${DB_PASSWORD}@postgres:5432/openatc
      NATS_URL: nats://nats:4222
      OLLAMA_BASE_URL: http://ollama:11434
      ATC_API_TOKEN: ${ATC_API_TOKEN:?error}
      LOG_LEVEL: ${LOG_LEVEL:-info}
    ports:
      - "8200:8200"   # REST + WebSocket API
      - "8201:8201"   # gRPC (internal)
    volumes:
      - ./atc-engine/src:/app/src:ro
    networks:
      - openatc-net
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8200/api/v1/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  speech-pipeline:
    build:
      context: .
      dockerfile: docker/speech-pipeline.Dockerfile
    container_name: openatc-speech
    restart: unless-stopped
    depends_on:
      nats:
        condition: service_started
    environment:
      NATS_URL: nats://nats:4222
      OLLAMA_BASE_URL: http://ollama:11434
      WHISPER_MODEL_PATH: /models/whisper
      PIPER_MODEL_PATH: /models/piper
      LOG_LEVEL: ${LOG_LEVEL:-info}
    volumes:
      - model_data:/models:ro
      - ./speech-pipeline/src:/app/src:ro
    networks:
      - openatc-net
    # GPU passthrough (NVIDIA)
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

  llm-proxy:
    build:
      context: .
      dockerfile: docker/llm-proxy.Dockerfile
    container_name: openatc-llm
    restart: unless-stopped
    environment:
      OLLAMA_BASE_URL: http://ollama:11434
      ATC_API_TOKEN: ${ATC_API_TOKEN:?error}
      LOG_LEVEL: ${LOG_LEVEL:-info}
    ports:
      - "8300:8300"
    networks:
      - openatc-net

  ollama:
    image: ollama/ollama:0.3.6
    container_name: openatc-ollama
    restart: unless-stopped
    volumes:
      - ollama_data:/root/.ollama
    ports:
      - "11434:11434"
    networks:
      - openatc-net
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    entrypoint: >
      sh -c "ollama serve &
             sleep 5 &&
             ollama pull llama3.1:8b &&
             wait"

  web-ui:
    build:
      context: .
      dockerfile: docker/web-ui.Dockerfile
    container_name: openatc-web
    restart: unless-stopped
    depends_on:
      - atc-engine
    environment:
      VITE_ATC_API_URL: http://localhost:8200
      VITE_ATC_WS_URL: ws://localhost:8200/api/v1/ws
    ports:
      - "3000:80"
    networks:
      - openatc-net

volumes:
  postgres_data:
  nats_data:
  ollama_data:
  model_data:
    driver: local
    driver_opts:
      type: none
      device: ${MODELS_PATH:-/opt/openatc/models}
      o: bind

networks:
  openatc-net:
    driver: bridge
```

## Networking

```mermaid
graph TB
  subgraph Host Network
    MSFS[MSFS + SimConnect Client]
    BROWSER[Browser - Web UI]
  end
  
  subgraph Docker Network (172.20.0.0/16)
    direction TB
    PG[postgres:5432]
    NA[nats:4222]
    AE[atc-engine:8200]
    SP[speech-pipeline]
    LP[llm-proxy:8300]
    OL[ollama:11434]
    WEB[web-ui:80]
  end
  
  MSFS -->|ws://localhost:8200| AE
  MSFS -->|nats://localhost:4222| NA
  BROWSER -->|http://localhost:3000| WEB
  BROWSER -->|ws://localhost:8200| AE
  AE -->|:5432| PG
  AE -->|:4222| NA
  SP -->|:4222| NA
  SP -->|:11434| OL
  LP -->|:11434| OL
  AE -->|:8300| LP
```

| Port | Service | Access Level |
|------|---------|-------------|
| `5432` | PostgreSQL | Internal only |
| `4222` | NATS | Internal + SimConnect host |
| `8222` | NATS monitoring | Internal only |
| `8200` | ATC Engine API | Host (REST + WebSocket) |
| `8201` | ATC Engine gRPC | Internal only |
| `8300` | LLM Proxy | Internal only |
| `11434` | Ollama | Internal only |
| `3000` | Web UI | Host (HTTP) |

## Volume Mounts

| Volume | Container Path | Host Path | Purpose |
|--------|---------------|-----------|---------|
| `postgres_data` | `/var/lib/postgresql/data` | Docker volume | Persistent database |
| `nats_data` | `/data` | Docker volume | JetStream persistence |
| `ollama_data` | `/root/.ollama` | Docker volume | LLM model storage |
| `model_data` | `/models` | `$MODELS_PATH` (default `/opt/openatc/models`) | STT/TTS model files (read-only) |
| Source mounts | `/app/src` (ro) | `./{service}/src` | Hot-reload during development |

## GPU Passthrough

### NVIDIA

Requires `nvidia-container-toolkit` installed on host:

```bash
# Install (Ubuntu/Debian)
sudo apt-get install nvidia-container-toolkit
sudo systemctl restart docker

# Verify
docker run --rm --gpus all nvidia/cuda:12.2-base nvidia-smi
```

In `docker-compose.yml`, the `speech-pipeline` and `ollama` services include:

```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: all
          capabilities: [gpu]
```

### AMD (ROCm) — Experimental

```yaml
environment:
  - HSA_OVERRIDE_GFX_VERSION=10.3.0
  - ROCR_VISIBLE_DEVICES=0
devices:
  - /dev/kfd
  - /dev/dri
```

### CPU-Only Fallback

All services function (slower) without GPU. Set `OLLAMA_USE_GPU=false` and omit deploy sections.

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DB_PASSWORD` | Yes | — | PostgreSQL password |
| `ATC_API_TOKEN` | Yes | — | Bearer token for API auth |
| `LOG_LEVEL` | No | `info` | `debug`, `info`, `warning`, `error` |
| `MODELS_PATH` | No | `/opt/openatc/models` | Host path to ML models |
| `OLLAMA_BASE_URL` | Yes | `http://ollama:11434` | Ollama server URL |
| `NATS_URL` | Yes | `nats://nats:4222` | NATS server URL |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | No | — | OpenTelemetry collector |

## Startup Order

```mermaid
sequenceDiagram
  participant D as Docker Compose
  participant PG as PostgreSQL
  participant NA as NATS
  participant AE as ATC Engine
  participant SP as Speech Pipeline
  participant OL as Ollama
  participant LP as LLM Proxy
  participant WEB as Web UI

  D->>PG: Start
  PG-->>D: Healthy
  D->>NA: Start
  NA-->>D: Ready
  D->>AE: Start (depends: PG, NA)
  AE->>AE: Run migrations (Alembic)
  AE-->>D: Healthy
  D->>OL: Start
  OL->>OL: Serve + Pull models
  OL-->>D: Ready
  D->>SP: Start (depends: NA)
  D->>LP: Start (depends: OL)
  D->>WEB: Start (depends: AE)
```

## Dockerfiles

### atc-engine.Dockerfile

```dockerfile
FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY atc-engine/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY atc-engine /app
WORKDIR /app

EXPOSE 8200
HEALTHCHECK CMD curl -f http://localhost:8200/api/v1/health || exit 1
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8200"]
```

### speech-pipeline.Dockerfile

```dockerfile
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake libasound2-dev && \
    rm -rf /var/lib/apt/lists/*

COPY speech-pipeline/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY speech-pipeline /app
WORKDIR /app

CMD ["python", "-m", "src.main"]
```

## Production Considerations

- **Docker Compose** is for single-host deployments (development / home lab)
- **Production multi-host**: Kubernetes or Nomad with service mesh (Consul + Envoy)
- **Logging**: All services log to stdout; use `docker compose logs` or Loki/Grafana
- **Metrics**: Prometheus scrape at `atc-engine:8200/api/v1/metrics`
- **Backup**: `pg_dump` via cron; NATS JetStream data via file-level backup
- **Updates**: `docker compose pull && docker compose up -d` for rolling updates
