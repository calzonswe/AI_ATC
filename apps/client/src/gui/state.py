from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class ClientStatus(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass
class AudioDeviceInfo:
    name: str
    index: int
    max_input_channels: int = 0
    max_output_channels: int = 0


@dataclass
class ClientState:
    status: ClientStatus = ClientStatus.DISCONNECTED
    server_ip: str = "127.0.0.1"
    server_port: int = 8000
    session_id: str = ""
    callsign: str = "SAS123"
    aircraft_type: str = "A320"
    mic_device: Optional[str] = None
    speaker_device: Optional[str] = None
    ptt_key: str = "Space"
    mic_volume: float = 1.0
    speaker_volume: float = 1.0
    is_transmitting: bool = False
    last_error: str = ""
    com1_freq: float = 118.300
    com2_freq: float = 121.800
    tuned_facility: str = ""
    transponder_code: str = "2000"
    available_mics: List[AudioDeviceInfo] = field(default_factory=list)
    available_speakers: List[AudioDeviceInfo] = field(default_factory=list)


def state_to_dict(state: ClientState) -> Dict[str, str]:
    return {
        "server_ip": state.server_ip,
        "server_port": str(state.server_port),
        "callsign": state.callsign,
        "aircraft_type": state.aircraft_type,
        "mic_device": state.mic_device or "",
        "speaker_device": state.speaker_device or "",
        "ptt_key": state.ptt_key,
        "mic_volume": str(state.mic_volume),
        "speaker_volume": str(state.speaker_volume),
        "com1_freq": str(state.com1_freq),
        "com2_freq": str(state.com2_freq),
        "transponder_code": state.transponder_code,
    }


def dict_to_state(data: Dict[str, str]) -> ClientState:
    return ClientState(
        server_ip=data.get("server_ip") or "127.0.0.1",
        server_port=_int_or(data.get("server_port"), 8000),
        callsign=data.get("callsign") or "SAS123",
        aircraft_type=data.get("aircraft_type") or "A320",
        mic_device=data.get("mic_device") or None,
        speaker_device=data.get("speaker_device") or None,
        ptt_key=data.get("ptt_key") or "Space",
        mic_volume=_float_or(data.get("mic_volume"), 1.0),
        speaker_volume=_float_or(data.get("speaker_volume"), 1.0),
        com1_freq=_float_or(data.get("com1_freq"), 118.300),
        com2_freq=_float_or(data.get("com2_freq"), 121.800),
        transponder_code=data.get("transponder_code") or "2000",
    )


def _int_or(val: Optional[str], default: int) -> int:
    if not val:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _float_or(val: Optional[str], default: float) -> float:
    if not val:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default
