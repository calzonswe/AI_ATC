import sys
from pathlib import Path
SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

import pytest

from openatc.simconnect.mock import MockSimConnectClient
from openatc.simconnect.models import SimConnectState


class TestMockClient:
    @pytest.mark.asyncio
    async def test_connect(self):
        client = MockSimConnectClient(callsign="SAS123")
        assert client.state == SimConnectState.DISCONNECTED
        await client.connect()
        assert client.state == SimConnectState.CONNECTED

    @pytest.mark.asyncio
    async def test_disconnect(self):
        client = MockSimConnectClient()
        await client.connect()
        await client.disconnect()
        assert client.state == SimConnectState.DISCONNECTED

    @pytest.mark.asyncio
    async def test_read_frame_returns_none_when_disconnected(self):
        client = MockSimConnectClient()
        frame = await client.read_frame()
        assert frame is None

    @pytest.mark.asyncio
    async def test_read_frame_returns_frame_when_connected(self):
        client = MockSimConnectClient(callsign="SAS123")
        await client.connect()
        frame = await client.read_frame()
        assert frame is not None
        assert frame.callsign == "SAS123"
        assert frame.position.lat != 0.0
        assert frame.position.lon != 0.0
        assert frame.motion.ias_kn >= 0

    @pytest.mark.asyncio
    async def test_callsign_property(self):
        client = MockSimConnectClient(callsign="ABC456")
        assert client.callsign == "ABC456"

    @pytest.mark.asyncio
    async def test_simulated_flight_progresses(self):
        client = MockSimConnectClient()
        await client.connect()

        frames = []
        for _ in range(10):
            frame = await client.read_frame()
            if frame:
                frames.append(frame)

        assert len(frames) > 0
        assert frames[0].position.lat != 0.0

    @pytest.mark.asyncio
    async def test_stream_invokes_callback(self):
        client = MockSimConnectClient()
        await client.connect()

        received = []

        async def collect():
            await client.stream(callback=lambda f: received.append(f), interval_s=0.01)

        import asyncio
        task = asyncio.create_task(collect())
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, RuntimeError):
            pass

        await client.disconnect()
        assert len(received) > 0
