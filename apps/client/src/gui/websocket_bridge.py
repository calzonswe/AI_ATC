from __future__ import annotations

import base64
import json
from typing import Callable, Dict, Optional

import numpy as np

try:
    from PySide6.QtCore import QObject, QUrl, Signal
    from PySide6.QtWebSockets import QWebSocket
    HAS_QT_WS = True
except ImportError:
    HAS_QT_WS = False
    QObject = object

WSMessageCallback = Callable[[Dict], None]


class WebSocketBridge(QObject if HAS_QT_WS else object):
    connected_signal = Signal() if HAS_QT_WS else None
    disconnected_signal = Signal() if HAS_QT_WS else None
    message_received = Signal(str) if HAS_QT_WS else None
    error_signal = Signal(str) if HAS_QT_WS else None

    def __init__(self, parent=None):
        if HAS_QT_WS:
            super().__init__(parent)
        self._ws: Optional["QWebSocket"] = None
        self._message_handler: Optional[WSMessageCallback] = None
        self._url: str = ""

    @property
    def is_connected(self) -> bool:
        if HAS_QT_WS and self._ws:
            return self._ws.state() == QWebSocket.State.ConnectedState
        return False

    def connect_to_server(self, ip: str, port: int, callsign: str) -> bool:
        if not HAS_QT_WS:
            return False
        self._url = f"ws://{ip}:{port}/ws/v1/telemetry?client_id={callsign}"
        self._ws = QWebSocket()
        self._ws.connected.connect(self._on_connected)
        self._ws.disconnected.connect(self._on_disconnected)
        self._ws.textMessageReceived.connect(self._on_message)
        self._ws.errorOccurred.connect(self._on_error)
        self._ws.open(QUrl(self._url))
        return True

    def disconnect(self) -> None:
        if HAS_QT_WS and self._ws:
            self._ws.close()
            self._ws = None

    def send_message(self, msg: Dict) -> None:
        if not HAS_QT_WS or not self._ws:
            return
        if self._ws.state() == QWebSocket.State.ConnectedState:
            self._ws.sendTextMessage(json.dumps(msg))

    def send_audio(self, audio_data: np.ndarray, frequency: float) -> None:
        pcm_bytes = audio_data.tobytes()
        b64 = base64.b64encode(pcm_bytes).decode("ascii")
        self.send_message({
            "type": "radio_transmit",
            "audio": b64,
            "frequency": frequency,
            "sample_rate": 22050,
        })

    def send_connect(self, callsign: str, aircraft_type: str) -> None:
        self.send_message({
            "type": "connect",
            "callsign": callsign,
            "client_type": "pilot",
            "aircraft_type": aircraft_type,
        })

    def set_message_handler(self, handler: WSMessageCallback) -> None:
        self._message_handler = handler

    def _on_connected(self) -> None:
        if self.connected_signal:
            self.connected_signal.emit()

    def _on_disconnected(self) -> None:
        if self.disconnected_signal:
            self.disconnected_signal.emit()

    def _on_message(self, message: str) -> None:
        if self.message_received:
            self.message_received.emit(message)
        if self._message_handler:
            try:
                data = json.loads(message)
                self._message_handler(data)
            except json.JSONDecodeError:
                pass

    def _on_error(self, error) -> None:
        if self.error_signal:
            self.error_signal.emit(str(error))
