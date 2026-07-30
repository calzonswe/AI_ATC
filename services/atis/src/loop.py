from __future__ import annotations

import logging
import time
from typing import Generator, Optional

from generator import AtisAudioGenerator

logger = logging.getLogger(__name__)


CHUNK_SIZE_S = 0.1


class AtisBroadcastLoop:
    def __init__(self, generator: AtisAudioGenerator, chunk_size_s: float = CHUNK_SIZE_S):
        self._generator = generator
        self._chunk_size_s = chunk_size_s
        self._current_wav: bytes = b""
        self._sample_rate: int = 22050
        self._identifier: str = ""
        self._last_update_s: float = 0.0
        self._update_interval_s: float = 30.0

    @property
    def identifier(self) -> str:
        return self._identifier

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    def update_broadcast(self, text: str, identifier: str) -> None:
        wav = self._generator.generate_wav(text)
        if wav:
            self._current_wav = wav
            self._identifier = identifier
            self._sample_rate = self._generator.sample_rate
            self._last_update_s = time.time()
            logger.info(
                "ATIS %s updated: %d bytes WAV", identifier, len(wav),
            )

    def stream_loop(self) -> Generator[bytes, None, None]:
        while True:
            if not self._current_wav:
                yield b""
                continue

            header_size = 44
            data = self._current_wav[header_size:]
            chunk_samples = int(self._sample_rate * self._chunk_size_s)
            chunk_bytes = chunk_samples * 2
            offset = 0
            while offset < len(data):
                end = min(offset + chunk_bytes, len(data))
                yield data[offset:end]
                offset = end

    def get_wav_bytes(self) -> bytes:
        return self._current_wav

    def is_stale(self, max_age_s: float = 120.0) -> bool:
        return (time.time() - self._last_update_s) > max_age_s
