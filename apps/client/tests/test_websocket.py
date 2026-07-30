import pytest


class TestWebSocketClient:
    @pytest.mark.asyncio
    async def test_queue_frame(self, telemetry_frame):
        from websocket_client import TelemetryWebSocketClient

        ws = TelemetryWebSocketClient("ws://localhost:0000", rate_hz=10)
        await ws.enqueue(telemetry_frame)
        assert ws._queue.qsize() == 1

    @pytest.mark.asyncio
    async def test_queue_maxsize(self, telemetry_frame):
        from websocket_client import TelemetryWebSocketClient

        ws = TelemetryWebSocketClient("ws://localhost:0000", rate_hz=10)

        for _ in range(200):
            await ws.enqueue(telemetry_frame)

        assert ws._queue.qsize() <= 100

    @pytest.mark.asyncio
    async def test_stop(self, telemetry_frame):
        from websocket_client import TelemetryWebSocketClient

        ws = TelemetryWebSocketClient("ws://localhost:0000", rate_hz=10)
        await ws.enqueue(telemetry_frame)
        await ws.stop()
        assert ws._running is False
