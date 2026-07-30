from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from structlog import get_logger

from ..routes.metrics import active_websocket_connections
from .metrics_collector import aircraft_store, metrics_collector

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])
logger = get_logger(__name__)

_controller_states = [
    {
        "callsign": "ESSA_TWR",
        "position": "TOWER",
        "frequency_mhz": 118.500,
        "status": "online",
        "airport_icao": "ESSA",
        "active_aircraft_count": 2,
        "uptime_seconds": 3600,
    },
    {
        "callsign": "ESSA_GND",
        "position": "GROUND",
        "frequency_mhz": 121.800,
        "status": "online",
        "airport_icao": "ESSA",
        "active_aircraft_count": 1,
        "uptime_seconds": 3600,
    },
    {
        "callsign": "ESSA_DEP",
        "position": "DEPARTURE",
        "frequency_mhz": 119.200,
        "status": "online",
        "airport_icao": "ESSA",
        "active_aircraft_count": 2,
        "uptime_seconds": 1800,
    },
    {
        "callsign": "ESSA_APP",
        "position": "APPROACH",
        "frequency_mhz": 124.300,
        "status": "online",
        "airport_icao": "ESSA",
        "active_aircraft_count": 3,
        "uptime_seconds": 900,
    },
    {
        "callsign": "ESSA_CTR",
        "position": "CENTER",
        "frequency_mhz": 127.800,
        "status": "online",
        "airport_icao": "",
        "active_aircraft_count": 5,
        "uptime_seconds": 7200,
    },
]


class LLMMetricRecord(BaseModel):
    latency_ms: float
    tokens_per_sec: float


class AudioMetricRecord(BaseModel):
    stt_ms: float
    tts_ms: float
    total_ms: float


# ──────────────────────────────────────────────
# Dashboard page (HTML)
# ──────────────────────────────────────────────

templates = Jinja2Templates(
    directory=__file__.rsplit("/", 1)[0] + "/templates"
)


@router.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
async def admin_dashboard(request: Request):
    return templates.TemplateResponse(request, "dashboard.html")


# ──────────────────────────────────────────────
# Metrics API
# ──────────────────────────────────────────────

@router.get("/metrics")
async def get_metrics():
    return metrics_collector.get_summary()


# ──────────────────────────────────────────────
# Aircraft API
# ──────────────────────────────────────────────

@router.get("/aircraft")
async def get_aircraft():
    active = aircraft_store.get_active()
    return {
        "count": len(active),
        "aircraft": active,
    }


# ──────────────────────────────────────────────
# Controllers API
# ──────────────────────────────────────────────

@router.get("/controllers")
async def get_controllers():
    ws_count = active_websocket_connections._value.get()
    return {
        "count": len(_controller_states),
        "controllers": _controller_states,
        "websocket_connections": ws_count,
    }


# ──────────────────────────────────────────────
# LLM Metrics Injection
# ──────────────────────────────────────────────

@router.post("/metrics/llm")
async def record_llm_metric(body: LLMMetricRecord):
    metrics_collector.record_llm_request(body.latency_ms, body.tokens_per_sec)
    return {"status": "ok"}


@router.post("/metrics/audio")
async def record_audio_metric(body: AudioMetricRecord):
    metrics_collector.record_audio_pipeline(body.stt_ms, body.tts_ms, body.total_ms)
    return {"status": "ok"}


# ──────────────────────────────────────────────
# SSE Event Stream
# ──────────────────────────────────────────────

@router.get("/events")
async def admin_events():
    async def event_generator():
        while True:
            summary = metrics_collector.get_summary()
            payload = json.dumps(summary, default=str)
            yield f"data: {payload}\n\n"
            await asyncio.sleep(2)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
