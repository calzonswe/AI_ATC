import sys
from pathlib import Path

SIMCONNECT_SRC = Path(__file__).resolve().parent.parent.parent / "packages" / "simconnect" / "src"
CLIENT_SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SIMCONNECT_SRC))
sys.path.insert(0, str(CLIENT_SRC))

import pytest
from openatc.simconnect.mock import MockSimConnectClient


@pytest.fixture(scope="session")
def qapp():
    """Session-scoped QApplication for qtbot tests."""
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.fixture
def mock_client():
    return MockSimConnectClient(callsign="TEST123")


@pytest.fixture
def telemetry_frame():
    from openatc.simconnect.models import TelemetryFrame, PositionData, MotionData, RadioData
    return TelemetryFrame(
        callsign="TEST123",
        position=PositionData(lat=59.65, lon=17.92, alt_msl_ft=5000, heading_mag=180),
        motion=MotionData(ias_kn=200, groundspeed_kn=210, vertical_speed_fpm=500, on_ground=False),
        radios=RadioData(com1_freq_mhz=118.300, transponder_code="2000"),
        recorded_at=1_000_000.0,
    )
