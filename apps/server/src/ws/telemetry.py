import json

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..admin.metrics_collector import aircraft_store
from ..routes.metrics import active_websocket_connections

router = APIRouter()
logger = structlog.get_logger(__name__)


class ConnectionManager:
    def __init__(self):
        self._connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self._connections[client_id] = websocket
        active_websocket_connections.inc()
        logger.info("ws_connected", client_id=client_id, total=len(self._connections))

    def disconnect(self, client_id: str):
        self._connections.pop(client_id, None)
        active_websocket_connections.dec()
        logger.info("ws_disconnected", client_id=client_id, total=len(self._connections))

    async def send_json(self, client_id: str, data: dict):
        ws = self._connections.get(client_id)
        if ws:
            await ws.send_json(data)

    async def broadcast(self, data: dict):
        for ws in list(self._connections.values()):
            try:
                await ws.send_json(data)
            except Exception:  # noqa: S110
                pass

    @property
    def active_count(self) -> int:
        return len(self._connections)


manager = ConnectionManager()


@router.websocket("/ws/v1/telemetry")
async def telemetry_ws(websocket: WebSocket):
    client_id = websocket.query_params.get("client_id", "anon")
    await manager.connect(websocket, client_id)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "detail": "invalid JSON"})
                continue

            msg_type = msg.get("type", "")

            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})

            elif msg_type == "subscribe":
                channel = msg.get("channel", "")
                await websocket.send_json({
                    "type": "subscribed",
                    "channel": channel,
                })

            elif msg_type == "telemetry":
                logger.debug("ws_telemetry", client_id=client_id, data=msg.get("data"))
                data = msg.get("data") or msg
                if isinstance(data, dict) and data.get("callsign"):
                    aircraft_store.update(data["callsign"], data)
                await websocket.send_json({"type": "telemetry_ack"})

            elif msg_type == "connect":
                callsign = msg.get("callsign", client_id)
                logger.info("ws_client_connect", client_id=client_id, callsign=callsign)
                aircraft_store.update(callsign, {
                    "callsign": callsign,
                    "client_type": msg.get("client_type", "pilot"),
                    "aircraft_type": msg.get("aircraft_type", ""),
                })
                await websocket.send_json({
                    "type": "connected",
                    "session_id": client_id,
                })

            else:
                await websocket.send_json({
                    "type": "error",
                    "detail": f"unknown message type: {msg_type}",
                })

    except WebSocketDisconnect:
        manager.disconnect(client_id)
        aircraft_store.remove(client_id)
    except Exception as exc:
        logger.error("ws_error", client_id=client_id, error=str(exc))
        manager.disconnect(client_id)
        aircraft_store.remove(client_id)
