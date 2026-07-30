from fastapi import APIRouter, Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST, Counter, Histogram, Gauge

router = APIRouter(tags=["metrics"])

http_requests_total = Counter(
    "atc_http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)

http_request_duration_seconds = Histogram(
    "atc_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

active_websocket_connections = Gauge(
    "atc_active_websocket_connections",
    "Number of active WebSocket connections",
)

active_http_requests = Gauge(
    "atc_active_http_requests",
    "Number of active HTTP requests",
)


@router.get("/metrics")
async def metrics():
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
