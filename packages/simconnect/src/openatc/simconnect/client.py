from typing import Optional
import abc
from .models import TelemetryFrame, SimConnectState, SimConnectCallback


class SimConnectClientBase(abc.ABC):
    """Abstract interface for a SimConnect client.

    Subclasses implement platform-specific connection to MSFS/P3D
    SimConnect (real) or provide synthetic data for testing (mock).
    """

    @abc.abstractmethod
    async def connect(self) -> None:
        """Establish connection to the simulator."""

    @abc.abstractmethod
    async def disconnect(self) -> None:
        """Tear down connection."""

    @abc.abstractmethod
    async def read_frame(self) -> Optional[TelemetryFrame]:
        """Read a single telemetry frame from the simulator.

        Returns None if no new data is available (non-blocking).
        """

    @property
    @abc.abstractmethod
    def state(self) -> SimConnectState:
        """Current connection state."""

    @property
    @abc.abstractmethod
    def callsign(self) -> str:
        """Aircraft callsign or tail number extracted from simulator."""

    async def stream(
        self,
        callback: SimConnectCallback,
        interval_s: float = 0.05,
    ) -> None:
        """Continuously read frames and invoke callback at the given interval.

        This is a convenience wrapper around read_frame() for the common
        use-case of streaming telemetry at a fixed rate.
        """
        import asyncio

        while self.state == SimConnectState.CONNECTED:
            frame = await self.read_frame()
            if frame is not None:
                callback(frame)
            await asyncio.sleep(interval_s)
