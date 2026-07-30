# Security Architecture

## Threat Model

| Threat | Mitigation |
|--------|------------|
| Unauthorized API access | Bearer token auth, rate limiting |
| Pilot spoofing callsign | Session binding + telemetry cross-check |
| Audio replay attack | Per-session nonce in audio stream |
| Container breakout | Non-root containers, read-only root FS |
| LLM prompt injection | Input sanitization, context separation |
| Database exposure | Internal-only network, no public port |
| Man-in-the-middle | TLS for external-facing endpoints |

## Authentication

### API Token

All REST and WebSocket endpoints (except `/health` and `/metrics`) require a Bearer token:

```
Authorization: Bearer atc_eyJhbGciOiJIUzI1NiIs...
```

- **Generation**: Pre-shared key set via `ATC_API_TOKEN` environment variable
- **Format**: Opaque string, minimum 32 characters, alphanumeric + underscore
- **Rotation**: Generate new token, update env, restart containers
- **Validation**: Constant-time comparison using `secrets.compare_digest()`

```python
# FastAPI dependency
from fastapi import Header, HTTPException
from secrets import compare_digest
from starlette.websockets import WebSocket

SETTINGS = Settings()

async def verify_token(authorization: str = Header(...)) -> None:
    token = authorization.removeprefix("Bearer ")
    if not compare_digest(token, SETTINGS.atc_api_token):
        raise HTTPException(status_code=401, detail="invalid_token")

# WebSocket auth via query parameter
async def verify_ws_token(websocket: WebSocket) -> bool:
    token = websocket.query_params.get("token", "")
    if not compare_digest(token, SETTINGS.atc_api_token):
        await websocket.close(code=4001)
        return False
    return True
```

### Session Binding

When a WebSocket connection is established:

1. Client sends `connect` event with `session_id` (client-generated UUID4)
2. Server binds session to token identity
3. All subsequent `telemetry` and `radio_transmit` events from that session are attributed to the authenticated callsign
4. Server validates that `callsign` in telemetry matches the authenticated identity's active session

## CORS

```python
# FastAPI CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",           # Web UI dev
        "http://localhost:80",             # Web UI prod
        "http://web-ui:80",                # Docker internal
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
```

In production, `allow_origins` should be restricted to the Web UI origin only.

## Environment Variable Isolation

Services access secrets exclusively through environment variables. No secrets in code or config files.

```bash
# .env file (NOT committed to repo)
DB_PASSWORD=changeme_secure_random_64_chars
ATC_API_TOKEN=atc_secure_random_64_chars

# .env.example (committed — placeholder values only)
DB_PASSWORD=changeme
ATC_API_TOKEN=changeme
```

### `.gitignore` rules

```gitignore
# Environment files
.env
.env.local
.env.production
```

## Ollama API Proxying

The LLM Proxy (`llm-proxy`) sits between all services and Ollama to:

1. **Rate limit**: Max 2 concurrent inference requests
2. **Context management**: Strip system prompts of sensitive data
3. **Timeout enforcement**: Hard 30s per generation
4. **Input validation**: Reject prompts containing SQL injection, prompt injection patterns
5. **Audit log**: Log all inference requests (text only, no audio)

```python
class LLMProxyMiddleware:
    def __init__(self):
        self.semaphore = asyncio.Semaphore(2)
        self.timeout = 30.0
        self.blocklist = re.compile(r"(?i)(system|assistant): ignore|forget|override")
    
    async def forward(self, prompt: str) -> str:
        if self.blocklist.search(prompt):
            raise HTTPException(422, "prompt contains blocked patterns")
        async with self.semaphore:
            async with asyncio.timeout(self.timeout):
                return await self._ollama_generate(prompt)
```

## Audio Security

- Audio chunks include a per-session sequence number to prevent replay
- Audio stored in radio_logs has retention of 7 days (configurable)
- No PII (pilot name, real-world callsign) stored in logs

## Network Security

```mermaid
graph TB
  INTERNET((Internet))
  
  subgraph "Host Network"
    DMZ[Docker Host]
    WEB[Web UI :3000]
    API[ATC Engine :8200]
  end
  
  subgraph "Internal Network (172.20.0.0/16)"
    PG[PostgreSQL :5432]
    NA[NATS :4222]
    SP[Speech Pipeline]
    LP[LLM Proxy :8300]
    OL[Ollama :11434]
  end
  
  INTERNET -.-x DMZ
  WEB --> API
  API --> PG
  API --> NA
  API --> LP
  SP --> NA
  SP --> LP
  LP --> OL
```

**Rules**:
- PostgreSQL and NATS are internal-only (no `ports:` in Docker Compose for production)
- Ollama is internal-only (no external port mapping)
- Only Web UI (:3000) and ATC Engine API (:8200) are exposed to host
- SimConnect client connects to `localhost:8200` and `localhost:4222`

## Rate Limiting

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/api/v1/controllers/{controller_id}/clear")
@limiter.limit("30/minute")
async def submit_clearance(...): ...
```

| Endpoint | Rate Limit |
|----------|------------|
| `POST /clear` | 30/minute |
| `POST /controllers` | 10/minute |
| WebSocket connect | 5/minute per IP |
| WebSocket `radio_transmit` | 100/minute per session |

## Container Security

```dockerfile
# Non-root user
RUN addgroup --system --gid 1001 openatc && \
    adduser --system --uid 1001 openatc
USER openatc

# Read-only root filesystem (in compose)
security_opt:
  - no-new-privileges:true
read_only: true
tmpfs:
  - /tmp
```

## Secrets Management

For production (Kubernetes):

- Store secrets in **HashiCorp Vault** or **Kubernetes Secrets**
- Inject via `SECRET_` environment variables
- Rotate automatically with Vault agent sidecar

For local deployments:

- `.env` file with restricted permissions: `chmod 600 .env`
- Token generation script: `python -c "import secrets; print('atc_' + secrets.token_urlsafe(48))"`
