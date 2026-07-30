from __future__ import annotations

import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import numpy as np
import structlog
from fastapi import FastAPI, HTTPException, Request
from faster_whisper import WhisperModel
from pydantic import BaseModel

logger = structlog.get_logger(__name__)

MODEL_SIZE = os.environ.get("WHISPER_MODEL_SIZE", "base")
DEVICE = os.environ.get("WHISPER_DEVICE", "auto")
COMPUTE_TYPE = os.environ.get("WHISPER_COMPUTE_TYPE", "default")
SERVICE_PORT = int(os.environ.get("SERVICE_PORT", "9000"))

model: WhisperModel | None = None
_start_time: float = 0.0


class TranscriptionRequest(BaseModel):
    audio_base64: str
    sample_rate: int = 16000


class TranscriptionResponse(BaseModel):
    text: str
    language: str
    duration_s: float
    inference_ms: float
    timestamp: str


class HealthResponse(BaseModel):
    status: str
    model: str
    device: str
    uptime_s: float


@asynccontextmanager
async def lifespan(app: FastAPI):
    global model, _start_time
    _start_time = time.time()
    logger.info("whisper_starting", model=MODEL_SIZE, device=DEVICE)
    try:
        model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
        logger.info("whisper_model_loaded", model=MODEL_SIZE, device=DEVICE)
    except Exception as exc:
        logger.error("whisper_load_failed", error=str(exc))
        model = None
    yield
    logger.info("whisper_stopped")


app = FastAPI(
    title="OpenATC Whisper STT Service",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(
        status="healthy" if model is not None else "degraded",
        model=MODEL_SIZE,
        device=str(model.model.device if model else DEVICE),
        uptime_s=round(time.time() - _start_time, 1),
    )


@app.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe(req: TranscriptionRequest, request: Request):
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    import base64

    try:
        pcm_bytes = base64.b64decode(req.audio_base64)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid base64 audio") from exc

    audio_array = (
        np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    )

    t0 = time.time()
    segments, info = model.transcribe(
        audio_array,
        beam_size=5,
        language=None,
        vad_filter=True,
    )
    segments_list = list(segments)
    inference_ms = round((time.time() - t0) * 1000, 1)

    text = " ".join(seg.text.strip() for seg in segments_list)

    return TranscriptionResponse(
        text=text,
        language=info.language,
        duration_s=round(info.duration, 2),
        inference_ms=inference_ms,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
