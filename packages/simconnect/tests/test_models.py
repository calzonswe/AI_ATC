import sys
from pathlib import Path
SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

from openatc.simconnect.models import (
    TelemetryFrame, PositionData, MotionData, RadioData, SimConnectState,
)


class TestTelemetryFrame:
    def test_frame_defaults(self):
        frame = TelemetryFrame()
        assert frame.callsign == ""
        assert frame.position.lat == 0.0
        assert frame.motion.ias_kn == 0.0
        assert frame.radios.transponder_code == "1200"

    def test_to_dict_structure(self):
        frame = TelemetryFrame(
            callsign="SAS123",
            position=PositionData(lat=59.65, lon=17.92, alt_msl_ft=1200, heading_mag=180),
            motion=MotionData(ias_kn=140, groundspeed_kn=145, on_ground=False),
            radios=RadioData(com1_freq_mhz=118.300, transponder_code="2000"),
            recorded_at=1_000_000.0,
        )
        d = frame.to_dict()
        assert d["event"] == "telemetry_update"
        assert d["callsign"] == "SAS123"
        assert d["position"]["lat"] == 59.65
        assert d["position"]["lon"] == 17.92
        assert d["position"]["alt_msl"] == 1200.0
        assert d["position"]["heading"] == 180.0
        assert d["motion"]["ias"] == 140.0
        assert d["motion"]["groundspeed"] == 145.0
        assert d["motion"]["on_ground"] is False
        assert d["radios"]["com1"] == 118.3
        assert d["radios"]["squawk"] == "2000"
        assert d["ts"] == 1_000_000_000

    def test_to_dict_rounding(self):
        frame = TelemetryFrame(
            position=PositionData(lat=59.65123456, lon=17.91865432),
            motion=MotionData(ias_kn=140.5678, groundspeed_kn=145.1234),
        )
        d = frame.to_dict()
        assert d["position"]["lat"] == 59.651235
        assert d["position"]["lon"] == 17.918654
        assert d["motion"]["ias"] == 140.6
        assert d["motion"]["groundspeed"] == 145.1

    def test_on_ground_default(self):
        frame = TelemetryFrame()
        assert frame.motion.on_ground is True

    def test_simconnect_state_enum(self):
        assert SimConnectState.DISCONNECTED.value == "disconnected"
        assert SimConnectState.CONNECTED.value == "connected"
        assert SimConnectState.CONNECTING.value == "connecting"
        assert SimConnectState.ERROR.value == "error"
