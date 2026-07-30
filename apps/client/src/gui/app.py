from __future__ import annotations

from typing import Optional

import numpy as np
from PySide6.QtCore import QTimer
from PySide6.QtGui import QAction, QCloseEvent, QKeyEvent
from PySide6.QtWidgets import (
    QMainWindow,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from .audio_manager import AudioManager, AudioManagerBase
from .audio_widget import AudioWidget
from .connection_widget import ConnectionWidget
from .flight_info_widget import FlightInfoWidget
from .ptt_manager import PTTManager
from .radio_widget import RadioWidget
from .settings_store import SettingsStore
from .simbrief_widget import SimBriefWidget
from .state import ClientState, ClientStatus
from .websocket_bridge import WebSocketBridge


class MainWindow(QMainWindow):
    def __init__(
        self,
        state: Optional[ClientState] = None,
        settings_store: Optional[SettingsStore] = None,
        audio_manager: Optional[AudioManagerBase] = None,
        websocket_bridge: Optional[WebSocketBridge] = None,
    ):
        super().__init__()
        self._state = state or ClientState()
        self._settings = settings_store or SettingsStore()
        self._audio = audio_manager or AudioManager()
        self._ws = websocket_bridge or WebSocketBridge()
        self._ptt_manager = PTTManager()

        self._audio_capture_timer = QTimer(self)
        self._audio_capture_timer.setInterval(100)

        self._build_ui()
        self._connect_signals()
        self._restore_settings()
        self._refresh_audio_devices()

    def _build_ui(self) -> None:
        self.setWindowTitle("OpenATC Client")
        self.setMinimumSize(480, 520)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(12)
        layout.setContentsMargins(12, 12, 12, 12)

        self._connection_widget = ConnectionWidget()
        layout.addWidget(self._connection_widget)

        self._flight_widget = FlightInfoWidget()
        layout.addWidget(self._flight_widget)

        self._audio_widget = AudioWidget(self._ptt_manager)
        layout.addWidget(self._audio_widget)

        self._radio_widget = RadioWidget()
        layout.addWidget(self._radio_widget)

        self._simbrief_widget = SimBriefWidget()
        layout.addWidget(self._simbrief_widget)

        layout.addStretch()

        self._build_menu()
        self.statusBar().showMessage("Disconnected")

    def _build_menu(self) -> None:
        menu = self.menuBar()
        file_menu = menu.addMenu("&File")

        save_action = QAction("&Save Settings", self)
        save_action.triggered.connect(self._save_settings)
        file_menu.addAction(save_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        help_menu = menu.addMenu("&Help")
        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _connect_signals(self) -> None:
        self._connection_widget.connect_requested.connect(self._on_connect)
        self._connection_widget.disconnect_requested.connect(self._on_disconnect)

        self._flight_widget.callsign_changed.connect(self._on_callsign_changed)
        self._flight_widget.aircraft_type_changed.connect(self._on_aircraft_changed)

        self._simbrief_widget.flight_plan_fetched.connect(self._on_flight_plan_fetched)
        self._simbrief_widget.pilot_id_changed.connect(self._on_simbrief_pilot_changed)

        self._audio_widget.mic_device_changed.connect(self._on_mic_changed)
        self._audio_widget.speaker_device_changed.connect(self._on_speaker_changed)
        self._audio_widget.ptt_key_changed.connect(self._on_ptt_key_changed)
        self._audio_widget.mic_volume_changed.connect(self._on_mic_vol_changed)
        self._audio_widget.speaker_volume_changed.connect(self._on_speaker_vol_changed)

        self._ptt_manager.ptt_changed.connect(self._on_ptt_toggle)
        self._audio_capture_timer.timeout.connect(self._on_capture_timer)

        if hasattr(self._ws, "connected_signal"):
            self._ws.connected_signal.connect(self._on_ws_connected)
        if hasattr(self._ws, "disconnected_signal"):
            self._ws.disconnected_signal.connect(self._on_ws_disconnected)
        if hasattr(self._ws, "error_signal"):
            self._ws.error_signal.connect(self._on_ws_error)
        if hasattr(self._ws, "message_received"):
            self._ws.message_received.connect(self._on_ws_message)

    def _restore_settings(self) -> None:
        restored = self._settings.restore()
        self._state.server_ip = restored.server_ip
        self._state.server_port = restored.server_port
        self._state.callsign = restored.callsign
        self._state.aircraft_type = restored.aircraft_type
        self._state.mic_device = restored.mic_device
        self._state.speaker_device = restored.speaker_device
        self._state.ptt_key = restored.ptt_key
        self._state.mic_volume = restored.mic_volume
        self._state.speaker_volume = restored.speaker_volume
        self._state.com1_freq = restored.com1_freq
        self._state.com2_freq = restored.com2_freq
        self._state.transponder_code = restored.transponder_code
        self._state.simbrief_pilot_id = restored.simbrief_pilot_id

        self._connection_widget._ip_input.setText(self._state.server_ip)
        self._connection_widget._port_input.setValue(self._state.server_port)
        self._connection_widget.set_callsign(self._state.callsign)
        self._flight_widget.callsign = self._state.callsign
        self._flight_widget.aircraft_type = self._state.aircraft_type
        self._simbrief_widget.pilot_id = self._state.simbrief_pilot_id

        self._audio_widget.set_ptt_key(self._state.ptt_key)
        self._audio_widget.set_mic_volume(self._state.mic_volume)
        self._audio_widget.set_speaker_volume(self._state.speaker_volume)
        self._radio_widget.set_com1(self._state.com1_freq)
        self._radio_widget.set_com2(self._state.com2_freq)
        self._radio_widget.set_squawk(self._state.transponder_code)

    def _save_settings(self) -> None:
        self._settings.save(self._state)
        self.statusBar().showMessage("Settings saved", 3000)

    def _refresh_audio_devices(self) -> None:
        try:
            mics = self._audio.list_input_devices()
            spk = self._audio.list_output_devices()
            self._state.available_mics = mics
            self._state.available_speakers = spk
            self._audio_widget.populate_devices(mics, spk)
        except Exception:  # noqa: S110
            pass

    def _on_connect(self, ip: str, port: int, callsign: str) -> None:
        self._state.status = ClientStatus.CONNECTING
        self._connection_widget.set_status(ClientStatus.CONNECTING)
        self.statusBar().showMessage(f"Connecting to {ip}:{port}...")

        ok = self._ws.connect_to_server(ip, port, callsign)
        if not ok:
            self._state.status = ClientStatus.ERROR
            self._state.last_error = "WebSocket not available"
            self._connection_widget.set_status(
                ClientStatus.ERROR, "WebSocket not available"
            )
            self.statusBar().showMessage("Connection failed: WebSocket not available")

    def _on_disconnect(self) -> None:
        self._ws.disconnect()
        self._state.status = ClientStatus.DISCONNECTED
        self._connection_widget.set_status(ClientStatus.DISCONNECTED)
        self.statusBar().showMessage("Disconnected")

    def _on_ws_connected(self) -> None:
        self._state.status = ClientStatus.CONNECTED
        self._connection_widget.set_status(ClientStatus.CONNECTED)
        self.statusBar().showMessage(
            f"Connected to {self._state.server_ip}:{self._state.server_port}"
        )
        self._ws.send_connect(self._state.callsign, self._state.aircraft_type)
        if self._state.flight_plan:
            self._ws.send_flight_plan(self._state.flight_plan)

    def _on_ws_disconnected(self) -> None:
        self._state.status = ClientStatus.DISCONNECTED
        self._connection_widget.set_status(ClientStatus.DISCONNECTED)
        self.statusBar().showMessage("Disconnected")

    def _on_ws_error(self, error: str) -> None:
        self._state.status = ClientStatus.ERROR
        self._state.last_error = error
        self._connection_widget.set_status(ClientStatus.ERROR, error)
        self.statusBar().showMessage(f"Error: {error}")

    def _on_ws_message(self, message: str) -> None:
        import json
        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            return
        msg_type = data.get("type", "")
        if msg_type == "connected":
            sid = data.get("session_id", "")
            self._state.session_id = sid
            self.statusBar().showMessage(f"Session: {sid}")
        elif msg_type == "controller_state":
            self._update_radio_from_controller(data)
        elif msg_type == "atc_audio":
            self._handle_atc_audio(data)

    def _update_radio_from_controller(self, data: dict) -> None:
        freq = data.get("frequency", 0)
        facility = data.get("callsign", "")
        if freq:
            self._radio_widget.set_com1(freq)
            self._state.com1_freq = freq
        if facility:
            self._radio_widget.set_facility(facility)
            self._state.tuned_facility = facility

    def _handle_atc_audio(self, data: dict) -> None:
        import base64
        b64 = data.get("audio", "")
        if not b64:
            return
        try:
            pcm_bytes = base64.b64decode(b64)
            audio_array = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            speaker = self._state.speaker_device
            if speaker:
                self._audio.play_audio(speaker, audio_array)
        except Exception:  # noqa: S110
            pass

    def _on_callsign_changed(self, callsign: str) -> None:
        self._state.callsign = callsign.upper()

    def _on_aircraft_changed(self, aircraft: str) -> None:
        self._state.aircraft_type = aircraft.upper()

    def _on_flight_plan_fetched(self, flight_plan) -> None:
        fp_dict = {
            "pilot_id": flight_plan.pilot_id,
            "origin": flight_plan.origin,
            "destination": flight_plan.destination,
            "aircraft_type": flight_plan.aircraft_type,
            "cruise_altitude": flight_plan.cruise_altitude,
            "route": flight_plan.route,
            "waypoints": flight_plan.waypoints,
            "estimated_time": flight_plan.estimated_time,
            "fuel": flight_plan.fuel,
            "weights": flight_plan.weights,
        }
        self._state.flight_plan = fp_dict
        if self._state.status == ClientStatus.CONNECTED:
            self._ws.send_flight_plan(fp_dict)
        self.statusBar().showMessage(
            f"Flight plan loaded: {flight_plan.origin} → {flight_plan.destination}",
            5000,
        )

    def _on_simbrief_pilot_changed(self, pilot_id: str) -> None:
        self._state.simbrief_pilot_id = pilot_id

    def _on_mic_changed(self, device: str) -> None:
        self._state.mic_device = device

    def _on_speaker_changed(self, device: str) -> None:
        self._state.speaker_device = device

    def _on_ptt_key_changed(self, key_str: str) -> None:
        self._state.ptt_key = key_str
        self._ptt_manager.key_sequence = self._ptt_manager.key_sequence_from_str(key_str)

    def _on_mic_vol_changed(self, vol: float) -> None:
        self._state.mic_volume = vol

    def _on_speaker_vol_changed(self, vol: float) -> None:
        self._state.speaker_volume = vol

    def _on_ptt_toggle(self, active: bool) -> None:
        self._state.is_transmitting = active
        if active:
            self._start_audio_capture()
        else:
            self._stop_audio_capture()

    def _start_audio_capture(self) -> None:
        mic = self._state.mic_device
        if not mic:
            return
        try:
            self._audio.start_capture(mic, self._on_audio_data)
        except Exception:  # noqa: S110
            pass

    def _stop_audio_capture(self) -> None:
        self._audio.stop_capture()

    def _on_audio_data(self, data: np.ndarray) -> None:
        if self._state.status == ClientStatus.CONNECTED:
            freq = self._state.com1_freq
            self._ws.send_audio(data * self._state.mic_volume, freq)

    def _on_capture_timer(self) -> None:
        pass

    def keyPressEvent(self, event: Optional[QKeyEvent]) -> None:  # noqa: N802
        if event:
            self._ptt_manager.handle_key_press(event.key(), event.modifiers())
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event: Optional[QKeyEvent]) -> None:  # noqa: N802
        if event:
            self._ptt_manager.handle_key_release(event.key(), event.modifiers())
            super().keyReleaseEvent(event)

    def closeEvent(self, event: Optional[QCloseEvent]) -> None:  # noqa: N802
        self._save_settings()
        self._ws.disconnect()
        self._audio.stop_capture()
        if event:
            event.accept()

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "About OpenATC Client",
            "OpenATC Client v0.1.0\n\n"
            "Desktop GUI for connecting to the OpenATC ATC simulation server.\n\n"
            "Configure your connection, audio devices, and PTT settings "
            "to communicate with ATC controllers."
        )
