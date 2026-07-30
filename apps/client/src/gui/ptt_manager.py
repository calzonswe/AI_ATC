from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QKeySequence

PTTCallback = Callable[[bool], None]


class PTTManager(QObject):
    ptt_changed = Signal(bool)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._key_sequence: Optional[QKeySequence] = QKeySequence("Space")
        self._active = False
        self._callback: Optional[PTTCallback] = None

    @property
    def key_sequence(self) -> Optional[QKeySequence]:
        return self._key_sequence

    @key_sequence.setter
    def key_sequence(self, ks: Optional[QKeySequence]) -> None:
        self._key_sequence = ks

    def key_sequence_from_str(self, key_str: str) -> QKeySequence:
        return QKeySequence(key_str)

    def handle_key_press(self, key: int, modifiers) -> None:
        if not self._key_sequence:
            return
        seq = QKeySequence(Qt.Key(key) | Qt.KeyboardModifier(modifiers))
        if seq.matches(self._key_sequence) != QKeySequence.SequenceMatch.ExactMatch:
            return
        if not self._active:
            self._active = True
            self.ptt_changed.emit(True)
            if self._callback:
                self._callback(True)

    def handle_key_release(self, key: int, modifiers) -> None:
        if not self._key_sequence:
            return
        seq = QKeySequence(Qt.Key(key) | Qt.KeyboardModifier(modifiers))
        if seq.matches(self._key_sequence) != QKeySequence.SequenceMatch.ExactMatch:
            return
        if self._active:
            self._active = False
            self.ptt_changed.emit(False)
            if self._callback:
                self._callback(False)

    def set_callback(self, callback: PTTCallback) -> None:
        self._callback = callback

    @property
    def is_active(self) -> bool:
        return self._active
