from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Optional
from unittest.mock import MagicMock, PropertyMock, patch

import numpy as np
import pytest
from PySide6.QtCore import Qt, QUrl
from PySide6.QtWidgets import QApplication

from gui.app import MainWindow
from gui.audio_manager import AudioManagerBase
from gui.audio_widget import AudioWidget
from gui.connection_widget import ConnectionWidget
from gui.flight_info_widget import FlightInfoWidget
from gui.radio_widget import RadioWidget
from gui.settings_store import SETTINGS_ORG, SETTINGS_APP, SettingsStore
from gui.state import (
    AudioDeviceInfo,
    ClientState,
    ClientStatus,
    dict_to_state,
    state_to_dict,
)


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────

@pytest.fixture
def mock_audio_manager():
    mgr = MagicMock(spec=AudioManagerBase)
    mgr.list_input_devices.return_value = [
        AudioDeviceInfo(name="MacBook Air Microphone", index=0, max_input_channels=1),
        AudioDeviceInfo(name="External Mic", index=1, max_input_channels=2),
    ]
    mgr.list_output_devices.return_value = [
        AudioDeviceInfo(name="MacBook Air Speakers", index=0, max_output_channels=2),
        AudioDeviceInfo(name="Headphones", index=1, max_output_channels=2),
    ]
    mgr.is_capturing.return_value = False
    return mgr


@pytest.fixture
def mock_websocket_bridge():
    """Creates a mock WebSocket bridge with signal-like attributes."""
    mock = MagicMock()
    mock.connected_signal = MagicMock()
    mock.disconnected_signal = MagicMock()
    mock.error_signal = MagicMock()
    mock.message_received = MagicMock()
    mock.is_connected = False
    return mock


@pytest.fixture
def mock_settings_store(tmp_path):
    """Use QSettings with a temporary file for testing."""
    store = MagicMock(spec=SettingsStore)
    store.restore.return_value = ClientState()
    return store


@pytest.fixture
def gui_state():
    return ClientState(
        server_ip="192.168.1.10",
        server_port=9090,
        callsign="TEST999",
        aircraft_type="B747",
        mic_device="External Mic",
        speaker_device="Headphones",
        ptt_key="F1",
        mic_volume=0.75,
        speaker_volume=0.5,
        com1_freq=125.500,
        com2_freq=126.700,
        transponder_code="1234",
    )


# ──────────────────────────────────────────────
# State & Settings Tests
# ──────────────────────────────────────────────

class TestClientState:
    def test_default_state(self):
        s = ClientState()
        assert s.status == ClientStatus.DISCONNECTED
        assert s.server_ip == "127.0.0.1"
        assert s.server_port == 8000
        assert s.callsign == "SAS123"
        assert s.aircraft_type == "A320"
        assert s.mic_volume == 1.0
        assert s.speaker_volume == 1.0
        assert s.ptt_key == "Space"
        assert not s.is_transmitting

    def test_state_to_dict_roundtrip(self, gui_state):
        d = state_to_dict(gui_state)
        assert d["server_ip"] == "192.168.1.10"
        assert d["server_port"] == "9090"
        assert d["callsign"] == "TEST999"
        assert d["aircraft_type"] == "B747"
        assert d["ptt_key"] == "F1"
        assert d["mic_volume"] == "0.75"
        assert d["speaker_volume"] == "0.5"

        restored = dict_to_state(d)
        assert restored.server_ip == gui_state.server_ip
        assert restored.server_port == gui_state.server_port
        assert restored.callsign == gui_state.callsign
        assert restored.aircraft_type == gui_state.aircraft_type
        assert restored.ptt_key == gui_state.ptt_key
        assert restored.mic_volume == gui_state.mic_volume
        assert restored.speaker_volume == gui_state.speaker_volume

    def test_state_to_dict_handles_none_device(self):
        s = ClientState(mic_device=None, speaker_device=None)
        d = state_to_dict(s)
        assert d["mic_device"] == ""
        assert d["speaker_device"] == ""

    def test_dict_to_state_handles_empty(self):
        restored = dict_to_state({})
        assert restored.server_ip == "127.0.0.1"
        assert restored.callsign == "SAS123"
        assert restored.mic_device is None


class TestSettingsStore:
    def test_save_and_restore_roundtrip(self, qapp, gui_state):
        store = SettingsStore(org="OpenATC_Test", app="Client_Test")
        store.clear()
        store.save(gui_state)
        restored = store.restore()

        assert restored.server_ip == gui_state.server_ip
        assert restored.server_port == gui_state.server_port
        assert restored.callsign == gui_state.callsign
        assert restored.aircraft_type == gui_state.aircraft_type
        assert restored.ptt_key == gui_state.ptt_key
        assert abs(restored.mic_volume - gui_state.mic_volume) < 0.01
        assert abs(restored.speaker_volume - gui_state.speaker_volume) < 0.01
        assert abs(restored.com1_freq - gui_state.com1_freq) < 0.001
        assert restored.transponder_code == gui_state.transponder_code
        store.clear()

    def test_restore_defaults_when_empty(self, qapp):
        store = SettingsStore(org="OpenATC_Test", app="Client_Empty")
        store.clear()
        restored = store.restore()
        assert restored.server_ip == "127.0.0.1"
        assert restored.server_port == 8000
        assert restored.callsign == "SAS123"

    def test_clear_removes_all(self, qapp, gui_state):
        store = SettingsStore(org="OpenATC_Test", app="Client_Clear")
        store.save(gui_state)
        store.clear()
        restored = store.restore()
        assert restored.server_ip != gui_state.server_ip


# ──────────────────────────────────────────────
# Widget Tests (require qtbot / display)
# ──────────────────────────────────────────────

class TestConnectionWidget:
    def test_initial_state(self, qtbot):
        w = ConnectionWidget()
        qtbot.add_widget(w)
        assert w._status_label.text() == "Disconnected"
        assert w._connect_btn.text() == "Connect"

    def test_set_status_connected(self, qtbot):
        w = ConnectionWidget()
        qtbot.add_widget(w)
        w.set_status(ClientStatus.CONNECTED)
        assert "Connected" in w._status_label.text()
        assert w._connect_btn.text() == "Disconnect"

    def test_set_status_disconnected(self, qtbot):
        w = ConnectionWidget()
        qtbot.add_widget(w)
        w.set_status(ClientStatus.CONNECTED)
        w.set_status(ClientStatus.DISCONNECTED)
        assert "Disconnected" in w._status_label.text()
        assert w._connect_btn.text() == "Connect"

    def test_set_status_error(self, qtbot):
        w = ConnectionWidget()
        qtbot.add_widget(w)
        w.set_status(ClientStatus.ERROR, "connection refused")
        assert "Error" in w._status_label.text()
        assert "connection refused" in w._status_label.text()

    def test_connect_signal(self, qtbot):
        w = ConnectionWidget()
        qtbot.add_widget(w)
        w._callsign = "SAS123"
        results = []
        w.connect_requested.connect(lambda ip, port, cs: results.append((ip, port, cs)))
        w._connect_btn.click()
        assert len(results) == 1
        assert results[0] == ("127.0.0.1", 8000, "SAS123")

    def test_disconnect_signal(self, qtbot):
        w = ConnectionWidget()
        qtbot.add_widget(w)
        w.set_status(ClientStatus.CONNECTED)
        results = []
        w.disconnect_requested.connect(lambda: results.append(True))
        w._connect_btn.click()
        assert results == [True]


class TestFlightInfoWidget:
    def test_initial_state(self, qtbot):
        w = FlightInfoWidget()
        qtbot.add_widget(w)
        assert w.callsign == "SAS123"
        assert w.aircraft_type == "A320"

    def test_set_callsign(self, qtbot):
        w = FlightInfoWidget()
        qtbot.add_widget(w)
        w.callsign = "ABC456"
        assert w.callsign == "ABC456"

    def test_set_aircraft_type(self, qtbot):
        w = FlightInfoWidget()
        qtbot.add_widget(w)
        w.aircraft_type = "B777"
        assert w.aircraft_type == "B777"

    def test_set_aircraft_type_custom(self, qtbot):
        w = FlightInfoWidget()
        qtbot.add_widget(w)
        w.aircraft_type = "F16"
        assert w.aircraft_type == "F16"

    def test_callsign_changed_signal(self, qtbot):
        w = FlightInfoWidget()
        qtbot.add_widget(w)
        signals = []
        w.callsign_changed.connect(lambda s: signals.append(s))
        w._callsign_input.setText("NEWCS")
        qtbot.wait(50)
        assert any("NEWCS" in s for s in signals)


class TestRadioWidget:
    def test_initial_state(self, qtbot):
        w = RadioWidget()
        qtbot.add_widget(w)
        assert "118.300" in w._com1_label.text()
        assert "121.800" in w._com2_label.text()
        assert "2000" in w._squawk_label.text()

    def test_set_com1(self, qtbot):
        w = RadioWidget()
        qtbot.add_widget(w)
        w.set_com1(125.500)
        assert "125.500" in w._com1_label.text()

    def test_set_com2(self, qtbot):
        w = RadioWidget()
        qtbot.add_widget(w)
        w.set_com2(136.975)
        assert "136.975" in w._com2_label.text()

    def test_set_facility(self, qtbot):
        w = RadioWidget()
        qtbot.add_widget(w)
        w.set_facility("ESSA_TWR")
        assert "ESSA_TWR" in w._facility_label.text()

    def test_set_squawk(self, qtbot):
        w = RadioWidget()
        qtbot.add_widget(w)
        w.set_squawk("7500")
        assert "7500" in w._squawk_label.text()


# ──────────────────────────────────────────────
# MainWindow Integration Tests
# ──────────────────────────────────────────────

class TestMainWindow:
    def test_window_opens_with_defaults(self, qtbot, mock_audio_manager,
                                          mock_websocket_bridge, mock_settings_store):
        window = MainWindow(
            state=ClientState(),
            settings_store=mock_settings_store,
            audio_manager=mock_audio_manager,
            websocket_bridge=mock_websocket_bridge,
        )
        qtbot.add_widget(window)
        assert window.windowTitle() == "OpenATC Client"
        assert window._state.status == ClientStatus.DISCONNECTED

    def test_restores_saved_state(self, qtbot, mock_audio_manager,
                                   mock_websocket_bridge, gui_state):
        saved_state = ClientState(
            server_ip="10.0.0.1", server_port=8080,
            callsign="SAVED01", aircraft_type="B737",
            ptt_key="F2", mic_volume=0.5, speaker_volume=0.3,
            com1_freq=118.100, com2_freq=128.300, transponder_code="4321",
        )
        store = MagicMock(spec=SettingsStore)
        store.restore.return_value = saved_state

        window = MainWindow(
            state=gui_state,
            settings_store=store,
            audio_manager=mock_audio_manager,
            websocket_bridge=mock_websocket_bridge,
        )
        qtbot.add_widget(window)
        assert window._state.server_ip == "10.0.0.1"
        assert window._state.server_port == 8080
        assert window._state.callsign == "SAVED01"
        assert window._state.aircraft_type == "B737"
        assert window._state.ptt_key == "F2"

    def test_connect_triggers_websocket(self, qtbot, mock_audio_manager,
                                          mock_websocket_bridge, mock_settings_store):
        mock_websocket_bridge.connect_to_server.return_value = True

        window = MainWindow(
            settings_store=mock_settings_store,
            audio_manager=mock_audio_manager,
            websocket_bridge=mock_websocket_bridge,
        )
        qtbot.add_widget(window)

        window._on_connect("10.0.0.1", 8000, "TEST01")
        mock_websocket_bridge.connect_to_server.assert_called_once_with(
            "10.0.0.1", 8000, "TEST01"
        )

    def test_disconnect_calls_ws_disconnect(self, qtbot, mock_audio_manager,
                                              mock_websocket_bridge, mock_settings_store):
        window = MainWindow(
            settings_store=mock_settings_store,
            audio_manager=mock_audio_manager,
            websocket_bridge=mock_websocket_bridge,
        )
        qtbot.add_widget(window)
        window._on_disconnect()
        mock_websocket_bridge.disconnect.assert_called_once()

    def test_ws_connected_sends_identity(self, qtbot, mock_audio_manager,
                                           mock_websocket_bridge, mock_settings_store):
        window = MainWindow(
            settings_store=mock_settings_store,
            audio_manager=mock_audio_manager,
            websocket_bridge=mock_websocket_bridge,
        )
        qtbot.add_widget(window)
        window._state.callsign = "PILOT01"
        window._state.aircraft_type = "A380"
        window._on_ws_connected()
        mock_websocket_bridge.send_connect.assert_called_once_with("PILOT01", "A380")

    def test_ws_message_connected_updates_session(self, qtbot, mock_audio_manager,
                                                    mock_websocket_bridge,
                                                    mock_settings_store):
        window = MainWindow(
            settings_store=mock_settings_store,
            audio_manager=mock_audio_manager,
            websocket_bridge=mock_websocket_bridge,
        )
        qtbot.add_widget(window)
        msg = json.dumps({"type": "connected", "session_id": "ses_001"})
        window._on_ws_message(msg)
        assert window._state.session_id == "ses_001"

    def test_ws_message_controller_state_updates_radio(self, qtbot,
                                                         mock_audio_manager,
                                                         mock_websocket_bridge,
                                                         mock_settings_store):
        window = MainWindow(
            settings_store=mock_settings_store,
            audio_manager=mock_audio_manager,
            websocket_bridge=mock_websocket_bridge,
        )
        qtbot.add_widget(window)
        msg = json.dumps({
            "type": "controller_state",
            "callsign": "ESSA_TWR",
            "frequency": 118.500,
        })
        window._on_ws_message(msg)
        assert window._state.tuned_facility == "ESSA_TWR"
        assert abs(window._state.com1_freq - 118.500) < 0.001

    def test_ptt_toggle_starts_stops_capture(self, qtbot, mock_audio_manager,
                                               mock_websocket_bridge,
                                               mock_settings_store):
        window = MainWindow(
            settings_store=mock_settings_store,
            audio_manager=mock_audio_manager,
            websocket_bridge=mock_websocket_bridge,
        )
        qtbot.add_widget(window)
        window._state.mic_device = "External Mic"

        window._on_ptt_toggle(True)
        mock_audio_manager.start_capture.assert_called_once()

        window._on_ptt_toggle(False)
        mock_audio_manager.stop_capture.assert_called_once()

    def test_settings_saved_on_close(self, qtbot, mock_audio_manager,
                                      mock_websocket_bridge, mock_settings_store):
        window = MainWindow(
            state=ClientState(callsign="CLOSE01"),
            settings_store=mock_settings_store,
            audio_manager=mock_audio_manager,
            websocket_bridge=mock_websocket_bridge,
        )
        qtbot.add_widget(window)
        window.close()
        mock_settings_store.save.assert_called_once()

    def test_ptt_keybinding_triggers_transmission(self, qtbot, mock_audio_manager,
                                                    mock_websocket_bridge,
                                                    mock_settings_store):
        from PySide6.QtGui import Qt as QtGui
        window = MainWindow(
            settings_store=mock_settings_store,
            audio_manager=mock_audio_manager,
            websocket_bridge=mock_websocket_bridge,
        )
        qtbot.add_widget(window)
        window._state.mic_device = "Mic"

        from PySide6.QtGui import QKeyEvent
        press = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key_Space,
                          Qt.KeyboardModifier.NoModifier)
        window.keyPressEvent(press)
        assert window._state.is_transmitting

        release = QKeyEvent(QKeyEvent.Type.KeyRelease, Qt.Key_Space,
                            Qt.KeyboardModifier.NoModifier)
        window.keyReleaseEvent(release)
        assert not window._state.is_transmitting

    def test_audio_devices_refreshed(self, qtbot, mock_audio_manager,
                                      mock_websocket_bridge, mock_settings_store):
        window = MainWindow(
            settings_store=mock_settings_store,
            audio_manager=mock_audio_manager,
            websocket_bridge=mock_websocket_bridge,
        )
        qtbot.add_widget(window)
        mock_audio_manager.list_input_devices.assert_called()
        mock_audio_manager.list_output_devices.assert_called()
