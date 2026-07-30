import asyncio
import structlog

import websockets
from websockets.asyncio.client import connect as ws_connect

from openatc.simconnect import TelemetryFrame

logger = structlog.get_logger(__name__)


class TelemetryWebSocketClient:
    """WebSocket client that streams telemetry frames to the ATC Engine.

    Handles connection lifecycle with exponential backoff reconnection.
    """

    def __init__(
        self,
        ws_url: str,
        token: str = "",
        rate_hz: float = 10.0,
    ):
        self._ws_url = ws_url
        self._token = token
        self._interval_s = 1.0 / max(rate_hz, 1.0)
        self._queue: asyncio.Queue[TelemetryFrame] = asyncio.Queue(maxsize=100)
        self._running = False
        self._ws = None

    async def enqueue(self, frame: TelemetryFrame):
        try:
            self._queue.put_nowait(frame)
        except asyncio.QueueFull:
            logger.warning("telemetry_queue_full, dropping frame")

    async def run(self):
        self._running = True
        retry_count = 0

        while self._running:
            try:
                headers = {}
                if self._token:
                    headers["Authorization"] = f"Bearer {self._token}"

                async with ws_connect(
                    self._ws_url,
                    additional_headers=headers,
                    ping_interval=10,
                    ping_timeout=5,
                    close_timeout=3,
                ) as ws:
                    self._ws = ws
                    logger.info(
                        "ws_connected",
                        url=self._ws_url,
                    )
                    retry_count = 0

                    await self._stream_loop(ws)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(
                    "ws_error",
                    error=str(exc),
                    retry_count=retry_count,
                )
                retry_count += 1
                delay = min(5.0 * (1.5 ** min(retry_count, 8)), 60.0)
                logger.info("ws_reconnecting", delay_s=round(delay, 1))
                await asyncio.sleep(delay)

        self._running = False

    async def stop(self):
        self._running = False
        if self._ws:
            await self._ws.close()

    async def _stream_loop(self, ws):
        while self._running:
            try:
                frame = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=self._interval_s,
                )
                payload = frame.to_dict()
                await ws.send_json(payload)
            except asyncio.TimeoutError:
                continue
            except websockets.exceptions.ConnectionClosed:
                logger.warning("ws_connection_closed")
                raise
