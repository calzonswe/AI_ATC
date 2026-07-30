import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from structlog import get_logger

from .settings import settings
from .logging_config import setup_logging
setup_logging()
from .middleware.cors import setup_cors
from .middleware.timing import RequestTimingMiddleware
from .middleware.auth import JWTValidationMiddleware
from .auth.service import jwt_service
from .routes.health import router as health_router
from .routes.metrics import router as metrics_router
from .routes.auth import router as auth_router
from .ws.telemetry import router as ws_router
from .admin import router as admin_router

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("server_starting", version="0.1.0", log_level=settings.log_level)

    app.state.ollama_url = settings.ollama_url
    app.state.ollama_model = settings.ollama_model
    app.state.redis_url = settings.redis_url
    app.state.qdrant_url = settings.qdrant_url

    yield

    logger.info("server_stopped")


app = FastAPI(
    title="OpenATC Server",
    version="0.1.0",
    lifespan=lifespan,
)

setup_cors(app)
app.add_middleware(RequestTimingMiddleware)
app.add_middleware(JWTValidationMiddleware, jwt_service=jwt_service)


@app.middleware("http")
async def trace_id_middleware(request: Request, call_next):
    trace_id = request.headers.get("X-Trace-ID", uuid.uuid4().hex[:16])
    request.state.trace_id = trace_id
    response = await call_next(request)
    response.headers["X-Trace-ID"] = trace_id
    return response


ADMIN_STATIC = Path(__file__).resolve().parent / "admin" / "static"
app.mount("/admin/static", StaticFiles(directory=str(ADMIN_STATIC)), name="admin_static")

app.include_router(health_router)
app.include_router(metrics_router)
app.include_router(auth_router)
app.include_router(ws_router)
app.include_router(admin_router)
