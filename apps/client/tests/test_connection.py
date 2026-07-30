import pytest
from unittest.mock import MagicMock

from openatc.simconnect.models import SimConnectState


class TestConnectionManager:
    @pytest.mark.asyncio
    async def test_connect_and_stream(self, mock_client):
        from connection import SimConnectConnectionManager

        received = []

        mgr = SimConnectConnectionManager(
            client=mock_client,
            retry_delay_s=0.1,
            max_retries=1,
        )
        mgr.set_frame_callback(lambda f: received.append(f))

        import asyncio
        task = asyncio.create_task(mgr.run())
        await asyncio.sleep(0.1)
        await mgr.stop()
        try:
            await task
        except (asyncio.CancelledError, RuntimeError):
            pass

        assert len(received) > 0

    @pytest.mark.asyncio
    async def test_stop_while_disconnected(self, mock_client):
        from connection import SimConnectConnectionManager

        mgr = SimConnectConnectionManager(client=mock_client)
        await mgr.stop()
        assert mock_client.state == SimConnectState.DISCONNECTED

    @pytest.mark.asyncio
    async def test_set_frame_callback(self, mock_client):
        from connection import SimConnectConnectionManager

        mgr = SimConnectConnectionManager(client=mock_client)
        cb = MagicMock()
        mgr.set_frame_callback(cb)
        assert mgr._on_frame is cb
