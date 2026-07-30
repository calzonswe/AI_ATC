from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QLineEdit,
    QWidget,
)


class FlightInfoWidget(QGroupBox):
    callsign_changed = Signal(str)
    aircraft_type_changed = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__("Flight Information", parent)
        self._callsign_input = QLineEdit("SAS123")
        self._aircraft_combo = QComboBox()
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QFormLayout(self)
        self._callsign_input.setMaxLength(8)
        self._callsign_input.setPlaceholderText("e.g. SAS123")
        layout.addRow("Callsign:", self._callsign_input)

        self._aircraft_combo.addItems([
            "A320", "B737", "B747", "B777", "B787",
            "A330", "A340", "A350", "A380", "C172", "Other",
        ])
        self._aircraft_combo.setEditable(True)
        layout.addRow("Aircraft Type:", self._aircraft_combo)

        self._callsign_input.textChanged.connect(self.callsign_changed.emit)
        self._aircraft_combo.currentTextChanged.connect(self.aircraft_type_changed.emit)

    @property
    def callsign(self) -> str:
        return self._callsign_input.text().strip().upper()

    @callsign.setter
    def callsign(self, value: str) -> None:
        self._callsign_input.setText(value.upper())

    @property
    def aircraft_type(self) -> str:
        return self._aircraft_combo.currentText().strip().upper()

    @aircraft_type.setter
    def aircraft_type(self, value: str) -> None:
        idx = self._aircraft_combo.findText(value.upper())
        if idx >= 0:
            self._aircraft_combo.setCurrentIndex(idx)
        else:
            self._aircraft_combo.setCurrentText(value.upper())
