import asyncio
import signal
import structlog

from openatc.simconnect import MockSimConnectClient

from .config import settings
from .connection import SimConnectConnectionManager
from .websocket_client import TelemetryWebSocketClient

logger = structlog.get_logger(__name__)


def setup_logging():
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer()
            if settings.log_level == "debug"
            else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    import logging

    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
    )


async def main():
    setup_logging()
    logger.info(
        "client_starting",
        callsign=settings.callsign,
        ws_url=settings.ws_url,
        rate_hz=settings.telemetry_rate_hz,
        use_mock=settings.use_mock,
    )

    if settings.use_mock:
        sim_client = MockSimConnectClient(callsign=settings.callsign)
    else:
        from openatc.simconnect import SimConnectClientBase
        sim_client = SimConnectClientBase()

    ws_client = TelemetryWebSocketClient(
        ws_url=settings.ws_url,
        token=settings.ws_token,
        rate_hz=settings.telemetry_rate_hz,
    )

    connection_mgr = SimConnectConnectionManager(
        client=sim_client,
        retry_delay_s=settings.connect_retry_delay_s,
        max_retries=settings.connect_max_retries,
    )

    connection_mgr.set_frame_callback(ws_client.enqueue)

    stop_event = asyncio.Event()

    def _handle_signal():
        logger.info("signal_received, shutting down")
        stop_event.set()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _handle_signal)
        except NotImplementedError:
            pass

    async with asyncio.TaskGroup() as tg:
        tg.create_task(ws_client.run(), name="ws_client")
        tg.create_task(connection_mgr.run(), name="simconnect")

        await asyncio.get_event_loop().run_in_executor(None, stop_event.wait)

    logger.info("client_stopped")


if __name__ == "__main__":
    asyncio.run(main())
