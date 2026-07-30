from __future__ import annotations

import logging
from typing import Optional

from openatc.speech.audio import pcm_bytes_to_wav

logger = logging.getLogger(__name__)


class AtisAudioGenerator:
    def __init__(self, tts_engine: Optional[object] = None):
        self._tts = tts_engine
        self._sample_rate: int = 22050

    def set_tts_engine(self, engine: object) -> None:
        self._tts = engine

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    def generate_wav(self, text: str) -> bytes:
        if not text:
            return self._silent_wav(1.0)

        if self._tts is not None:
            try:
                result = self._tts.synthesize(text)
                if result and result.audio and len(result.audio) > 0:
                    self._sample_rate = result.sample_rate
                    return self._pcm_to_wav(result.audio, result.sample_rate)
            except Exception as exc:
                logger.warning("TTS synthesis failed: %s", exc)

        return self._silent_wav(1.0)

    def _silent_wav(self, duration_s: float) -> bytes:
        num_samples = int(self._sample_rate * duration_s)
        audio = b"\x00\x00" * num_samples
        return self._pcm_to_wav(audio, self._sample_rate)

    def _pcm_to_wav(self, pcm_bytes: bytes, sample_rate: int) -> bytes:
        return pcm_bytes_to_wav(pcm_bytes, sample_rate)
