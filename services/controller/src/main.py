from fastapi import FastAPI
from contextlib import asynccontextmanager

from .settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.ollama_url = settings.ollama_url
    app.state.ollama_model = settings.ollama_model
    app.state.redis_url = settings.redis_url
    yield


app = FastAPI(title="OpenATC Controller", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "controller-service",
        "ollama_url": settings.ollama_url,
        "ollama_model": settings.ollama_model,
    }
