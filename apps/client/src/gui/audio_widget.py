from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent, QKeySequence
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from .ptt_manager import PTTManager


class PTTKeyCaptureButton(QPushButton):
    key_captured = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__("Click to set PTT key...", parent)
        self._capturing = False
        self.setCheckable(True)
        self.setMinimumWidth(160)
        self.clicked.connect(self._start_capture)
        self.setToolTip("Click then press the key you want to use for Push-To-Talk")

    def _start_capture(self) -> None:
        self._capturing = True
        self.setText("Press a key...")
        self.setStyleSheet("background-color: #ffffcc;")

    def set_key_text(self, text: str) -> None:
        self._capturing = False
        self.setText(text)
        self.setStyleSheet("")

    def keyPressEvent(self, event: Optional[QKeyEvent]) -> None:  # noqa: N802
        if event and self._capturing:
            seq = QKeySequence(event.key() | int(event.modifiers()))
            key_str = seq.toString()
            if key_str:
                self._capturing = False
                self.setText(key_str)
                self.setStyleSheet("")
                self.key_captured.emit(key_str)
                event.accept()
                return
        super().keyPressEvent(event)


class AudioWidget(QWidget):
    mic_device_changed = Signal(str)
    speaker_device_changed = Signal(str)
    ptt_key_changed = Signal(str)
    mic_volume_changed = Signal(float)
    speaker_volume_changed = Signal(float)

    def __init__(
        self,
        ptt_manager: PTTManager,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._ptt_manager = ptt_manager
        self._mic_combo = QComboBox()
        self._speaker_combo = QComboBox()
        self._ptt_button = PTTKeyCaptureButton()
        self._ptt_indicator = QLabel("● Idle")
        self._mic_slider = QSlider(Qt.Orientation.Horizontal)
        self._speaker_slider = QSlider(Qt.Orientation.Horizontal)
        self._build_ui()

        self._ptt_manager.ptt_changed.connect(self._on_ptt_toggle)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QLabel("Audio Settings")
        header.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(header)

        # Microphone selection
        mic_layout = QHBoxLayout()
        mic_layout.addWidget(QLabel("Microphone:"))
        self._mic_combo.setMinimumWidth(200)
        mic_layout.addWidget(self._mic_combo)
        mic_layout.addStretch()
        layout.addLayout(mic_layout)

        # Speaker selection
        spk_layout = QHBoxLayout()
        spk_layout.addWidget(QLabel("Speaker:"))
        self._speaker_combo.setMinimumWidth(200)
        spk_layout.addWidget(self._speaker_combo)
        spk_layout.addStretch()
        layout.addLayout(spk_layout)

        # PTT keybinding
        ptt_layout = QHBoxLayout()
        ptt_layout.addWidget(QLabel("PTT Key:"))
        self._ptt_button.setMinimumWidth(160)
        ptt_layout.addWidget(self._ptt_button)
        ptt_layout.addStretch()
        layout.addLayout(ptt_layout)

        # PTT indicator
        ind_layout = QHBoxLayout()
        ind_layout.addWidget(QLabel("Status:"))
        self._ptt_indicator.setStyleSheet(
            "color: #888888; font-weight: bold; font-size: 16px;"
        )
        ind_layout.addWidget(self._ptt_indicator)
        ind_layout.addStretch()
        layout.addLayout(ind_layout)

        # Mic volume
        vol_layout = QHBoxLayout()
        vol_layout.addWidget(QLabel("Mic Volume:"))
        self._mic_slider.setRange(0, 100)
        self._mic_slider.setValue(100)
        self._mic_slider.setMinimumWidth(120)
        vol_layout.addWidget(self._mic_slider)
        self._mic_vol_label = QLabel("100%")
        vol_layout.addWidget(self._mic_vol_label)
        layout.addLayout(vol_layout)

        # Speaker volume
        spk_vol_layout = QHBoxLayout()
        spk_vol_layout.addWidget(QLabel("Spk Volume:"))
        self._speaker_slider.setRange(0, 100)
        self._speaker_slider.setValue(100)
        self._speaker_slider.setMinimumWidth(120)
        spk_vol_layout.addWidget(self._speaker_slider)
        self._spk_vol_label = QLabel("100%")
        spk_vol_layout.addWidget(self._spk_vol_label)
        layout.addLayout(spk_vol_layout)

        # Connections
        self._mic_combo.currentTextChanged.connect(self.mic_device_changed.emit)
        self._speaker_combo.currentTextChanged.connect(self.speaker_device_changed.emit)
        self._ptt_button.key_captured.connect(self.ptt_key_changed.emit)
        self._mic_slider.valueChanged.connect(self._on_mic_volume)
        self._speaker_slider.valueChanged.connect(self._on_speaker_volume)

    def populate_devices(self, mics, speakers) -> None:
        current_mic = self._mic_combo.currentText()
        current_spk = self._speaker_combo.currentText()
        self._mic_combo.clear()
        self._speaker_combo.clear()

        for d in mics:
            self._mic_combo.addItem(d.name)
        for d in speakers:
            self._speaker_combo.addItem(d.name)

        if mics:
            idx = self._mic_combo.findText(current_mic)
            self._mic_combo.setCurrentIndex(max(0, idx))
        if speakers:
            idx = self._speaker_combo.findText(current_spk)
            self._speaker_combo.setCurrentIndex(max(0, idx))

    def set_ptt_key(self, key_str: str) -> None:
        self._ptt_button.set_key_text(key_str)

    def set_mic_volume(self, vol: float) -> None:
        self._mic_slider.blockSignals(True)
        self._mic_slider.setValue(int(vol * 100))
        self._mic_slider.blockSignals(False)
        self._mic_vol_label.setText(f"{int(vol * 100)}%")

    def set_speaker_volume(self, vol: float) -> None:
        self._speaker_slider.blockSignals(True)
        self._speaker_slider.setValue(int(vol * 100))
        self._speaker_slider.blockSignals(False)
        self._spk_vol_label.setText(f"{int(vol * 100)}%")

    def _on_ptt_toggle(self, active: bool) -> None:
        if active:
            self._ptt_indicator.setText("● TRANSMITTING")
            self._ptt_indicator.setStyleSheet(
                "color: #cc2222; font-weight: bold; font-size: 16px;"
            )
        else:
            self._ptt_indicator.setText("● Idle")
            self._ptt_indicator.setStyleSheet(
                "color: #888888; font-weight: bold; font-size: 16px;"
            )

    def _on_mic_volume(self, value: int) -> None:
        vol = value / 100.0
        self._mic_vol_label.setText(f"{value}%")
        self.mic_volume_changed.emit(vol)

    def _on_speaker_volume(self, value: int) -> None:
        vol = value / 100.0
        self._spk_vol_label.setText(f"{value}%")
        self.speaker_volume_changed.emit(vol)
