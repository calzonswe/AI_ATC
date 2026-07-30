from typing import Optional
import asyncio
import structlog

from openatc.simconnect import (
    SimConnectClientBase,
    SimConnectState,
    MockSimConnectClient,
    TelemetryFrame,
    SimConnectCallback,
)

logger = structlog.get_logger(__name__)


class SimConnectConnectionManager:
    """Manages the lifecycle of a SimConnect client with reconnection.

    Uses exponential backoff when SimConnect or MSFS is unavailable.
    Supports both real and mock client implementations.
    """

    def __init__(
        self,
        client: SimConnectClientBase,
        retry_delay_s: float = 5.0,
        max_retries: int = 0,
    ):
        self._client = client
        self._retry_delay = retry_delay_s
        self._max_retries = max_retries
        self._running = False
        self._on_frame: Optional[SimConnectCallback] = None

    def set_frame_callback(self, callback: SimConnectCallback):
        self._on_frame = callback

    async def run(self):
        """Connect and stream, reconnecting on disconnection."""
        self._running = True
        retry_count = 0

        while self._running:
            try:
                await self._client.connect()
                logger.info(
                    "simconnect_connected",
                    state=self._client.state.value,
                    callsign=self._client.callsign,
                )
                retry_count = 0

                await self._client.stream(
                    callback=self._on_frame or self._default_callback,
                    interval_s=0.05,
                )

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(
                    "simconnect_error",
                    error=str(exc),
                    retry_count=retry_count,
                )
                await self._safe_disconnect()

                retry_count += 1
                if 0 < self._max_retries <= retry_count:
                    logger.error("simconnect_max_retries_reached")
                    break

                delay = self._retry_delay * (1.5 ** min(retry_count, 10))
                logger.info(
                    "simconnect_reconnecting",
                    delay_s=round(delay, 1),
                )
                await asyncio.sleep(delay)

        self._running = False

    async def stop(self):
        self._running = False
        await self._safe_disconnect()

    async def _safe_disconnect(self):
        try:
            if self._client.state == SimConnectState.CONNECTED:
                await self._client.disconnect()
        except Exception as exc:
            logger.warning("simconnect_disconnect_error", error=str(exc))

    def _default_callback(self, frame: TelemetryFrame):
        logger.debug("telemetry_frame", callsign=frame.callsign)
