from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QLabel,
    QWidget,
)


class RadioWidget(QGroupBox):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__("Radio Information", parent)
        self._com1_label = QLabel("118.300 MHz")
        self._com2_label = QLabel("121.800 MHz")
        self._facility_label = QLabel("—")
        self._squawk_label = QLabel("2000")
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QFormLayout(self)
        layout.addRow("COM1:", self._com1_label)
        layout.addRow("COM2:", self._com2_label)
        layout.addRow("Tuned Facility:", self._facility_label)
        layout.addRow("Transponder:", self._squawk_label)

        for label in (self._com1_label, self._com2_label,
                      self._facility_label, self._squawk_label):
            label.setStyleSheet("font-weight: bold; font-size: 14px;")

    def set_com1(self, freq: float) -> None:
        self._com1_label.setText(f"{freq:.3f} MHz")

    def set_com2(self, freq: float) -> None:
        self._com2_label.setText(f"{freq:.3f} MHz")

    def set_facility(self, facility: str) -> None:
        self._facility_label.setText(facility if facility else "—")

    def set_squawk(self, code: str) -> None:
        self._squawk_label.setText(code)
