from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Callable


class SimConnectState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass
class PositionData:
    lat: float = 0.0
    lon: float = 0.0
    alt_msl_ft: float = 0.0
    alt_agl_ft: float = 0.0
    heading_true: float = 0.0
    heading_mag: float = 0.0
    pitch_deg: float = 0.0
    bank_deg: float = 0.0


@dataclass
class MotionData:
    ias_kn: float = 0.0
    groundspeed_kn: float = 0.0
    vertical_speed_fpm: float = 0.0
    mach: float = 0.0
    on_ground: bool = True


@dataclass
class RadioData:
    com1_freq_mhz: float = 118.000
    com2_freq_mhz: float = 118.000
    transponder_code: str = "1200"
    transponder_mode: str = "alt"


@dataclass
class TelemetryFrame:
    callsign: str = ""
    position: PositionData = field(default_factory=PositionData)
    motion: MotionData = field(default_factory=MotionData)
    radios: RadioData = field(default_factory=RadioData)
    sim_time_s: float = 0.0
    recorded_at: float = 0.0

    def to_dict(self) -> dict:
        return {
            "event": "telemetry_update",
            "callsign": self.callsign,
            "position": {
                "lat": round(self.position.lat, 6),
                "lon": round(self.position.lon, 6),
                "alt_msl": round(self.position.alt_msl_ft, 1),
                "alt_agl": round(self.position.alt_agl_ft, 1),
                "heading": round(self.position.heading_mag, 1),
                "pitch": round(self.position.pitch_deg, 1),
                "bank": round(self.position.bank_deg, 1),
            },
            "motion": {
                "ias": round(self.motion.ias_kn, 1),
                "groundspeed": round(self.motion.groundspeed_kn, 1),
                "vertical_speed": round(self.motion.vertical_speed_fpm, 1),
                "on_ground": self.motion.on_ground,
            },
            "radios": {
                "com1": round(self.radios.com1_freq_mhz, 3),
                "com2": round(self.radios.com2_freq_mhz, 3),
                "squawk": self.radios.transponder_code,
                "squawk_mode": self.radios.transponder_mode,
            },
            "sim_time": self.sim_time_s,
            "ts": int(self.recorded_at * 1000),
        }


SimConnectCallback = Callable[[TelemetryFrame], None]
"""Callback signature invoked on each telemetry update cycle."""
