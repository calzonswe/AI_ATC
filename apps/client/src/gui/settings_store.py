from __future__ import annotations

from typing import Dict

from PySide6.QtCore import QSettings

from .state import ClientState, dict_to_state, state_to_dict

SETTINGS_ORG = "OpenATC"
SETTINGS_APP = "Client"


class SettingsStore:
    def __init__(self, org: str = SETTINGS_ORG, app: str = SETTINGS_APP):
        self._settings = QSettings(org, app)

    def save(self, state: ClientState) -> None:
        flat = state_to_dict(state)
        for key, value in flat.items():
            self._settings.setValue(key, value)

    def restore(self) -> ClientState:
        keys = [
            "server_ip", "server_port", "callsign", "aircraft_type",
            "mic_device", "speaker_device", "ptt_key",
            "mic_volume", "speaker_volume",
            "com1_freq", "com2_freq", "transponder_code",
            "simbrief_pilot_id",
        ]
        data: Dict[str, str] = {}
        for key in keys:
            val = self._settings.value(key, "")
            if val is not None:
                data[key] = str(val)
        return dict_to_state(data)

    def clear(self) -> None:
        self._settings.clear()
