from __future__ import annotations

from typing import Dict, Optional

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .simbrief_client import SimBriefFlightPlan, fetch_flight_plan


class SimBriefWorker(QThread):
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, pilot_id: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._pilot_id = pilot_id

    def run(self) -> None:
        try:
            flight_plan = fetch_flight_plan(self._pilot_id)
            self.finished.emit(flight_plan)
        except Exception as exc:
            self.error.emit(str(exc))


class SimBriefWidget(QGroupBox):
    flight_plan_fetched = Signal(object)
    pilot_id_changed = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__("SimBrief Flight Plan", parent)
        self._pilot_input = QLineEdit()
        self._fetch_btn = QPushButton("Fetch Latest Flight Plan")
        self._summary = QTextEdit()
        self._worker: Optional[SimBriefWorker] = None
        self._flight_plan: Optional[SimBriefFlightPlan] = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        row = QHBoxLayout()
        self._pilot_input.setPlaceholderText("SimBrief Pilot ID (username)")
        row.addWidget(self._pilot_input, 1)
        row.addWidget(self._fetch_btn)
        layout.addLayout(row)

        self._summary.setReadOnly(True)
        self._summary.setPlaceholderText(
            "Click 'Fetch Latest Flight Plan' to load your route..."
        )
        self._summary.setMaximumHeight(160)
        layout.addWidget(self._summary)

        self._pilot_input.textChanged.connect(self.pilot_id_changed.emit)
        self._fetch_btn.clicked.connect(self._on_fetch)

    @property
    def pilot_id(self) -> str:
        return self._pilot_input.text().strip()

    @pilot_id.setter
    def pilot_id(self, value: str) -> None:
        self._pilot_input.setText(value)

    @property
    def flight_plan(self) -> Optional[SimBriefFlightPlan]:
        return self._flight_plan

    def _on_fetch(self) -> None:
        pid = self.pilot_id
        if not pid:
            self._summary.setText("Please enter a Pilot ID first.")
            return
        self._fetch_btn.setEnabled(False)
        self._fetch_btn.setText("Fetching...")
        self._summary.setText("Fetching flight plan from SimBrief...")

        self._worker = SimBriefWorker(pid, self)
        self._worker.finished.connect(self._on_fetch_success)
        self._worker.error.connect(self._on_fetch_error)
        self._worker.start()

    def _on_fetch_success(self, flight_plan: SimBriefFlightPlan) -> None:
        self._flight_plan = flight_plan
        self._summary.setText(flight_plan.summary())
        self._fetch_btn.setEnabled(True)
        self._fetch_btn.setText("Fetch Latest Flight Plan")
        self.flight_plan_fetched.emit(flight_plan)

    def _on_fetch_error(self, error: str) -> None:
        self._summary.setText(f"Failed to fetch flight plan:\n{error}")
        self._fetch_btn.setEnabled(True)
        self._fetch_btn.setText("Fetch Latest Flight Plan")

    def clear_flight_plan(self) -> None:
        self._flight_plan = None
        self._summary.clear()
        self._summary.setPlaceholderText(
            "Click 'Fetch Latest Flight Plan' to load your route..."
        )
