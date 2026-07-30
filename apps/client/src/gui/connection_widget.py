from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .state import ClientStatus


class ConnectionWidget(QWidget):
    connect_requested = Signal(str, int, str)
    disconnect_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._status_label = QLabel("Disconnected")
        self._connect_btn = QPushButton("Connect")
        self._ip_input = QLineEdit("127.0.0.1")
        self._port_input = QSpinBox()
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        header = QLabel("Connection Settings")
        header.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(header)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Server IP:"))
        self._ip_input.setMinimumWidth(140)
        row1.addWidget(self._ip_input)
        row1.addWidget(QLabel("Port:"))
        self._port_input.setRange(1024, 65535)
        self._port_input.setValue(8000)
        row1.addWidget(self._port_input)
        row1.addStretch()
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        self._status_label.setStyleSheet(
            "color: #cc4444; font-weight: bold;"
        )
        row2.addWidget(self._status_label)
        row2.addStretch()
        row2.addWidget(self._connect_btn)
        layout.addLayout(row2)

        self._connect_btn.clicked.connect(self._on_connect_clicked)

    def set_status(self, status: ClientStatus, error: str = "") -> None:
        if status == ClientStatus.CONNECTED:
            self._status_label.setText("Connected")
            self._status_label.setStyleSheet("color: #44cc44; font-weight: bold;")
            self._connect_btn.setText("Disconnect")
            self._ip_input.setEnabled(False)
            self._port_input.setEnabled(False)
        elif status == ClientStatus.CONNECTING:
            self._status_label.setText("Connecting...")
            self._status_label.setStyleSheet("color: #cccc44; font-weight: bold;")
            self._connect_btn.setEnabled(False)
        elif status == ClientStatus.ERROR:
            self._status_label.setText(f"Error: {error}")
            self._status_label.setStyleSheet("color: #cc4444; font-weight: bold;")
            self._connect_btn.setText("Connect")
            self._connect_btn.setEnabled(True)
            self._ip_input.setEnabled(True)
            self._port_input.setEnabled(True)
        else:
            self._status_label.setText("Disconnected")
            self._status_label.setStyleSheet("color: #cc4444; font-weight: bold;")
            self._connect_btn.setText("Connect")
            self._connect_btn.setEnabled(True)
            self._ip_input.setEnabled(True)
            self._port_input.setEnabled(True)

    def set_callsign(self, callsign: str) -> None:
        self._callsign = callsign

    def _on_connect_clicked(self) -> None:
        if self._connect_btn.text() == "Disconnect":
            self.disconnect_requested.emit()
        else:
            ip = self._ip_input.text().strip()
            port = self._port_input.value()
            cs = getattr(self, "_callsign", "SAS123")
            self.connect_requested.emit(ip, port, cs)
