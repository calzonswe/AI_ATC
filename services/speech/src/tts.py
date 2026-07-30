from __future__ import annotations

import logging
import os
from typing import Any, Generator, Optional

import numpy as np

from audio import audio_to_int16_bytes
from models import AudioChunk, SynthesisResult

logger = logging.getLogger(__name__)


class TtsEngine:
    def __init__(
        self,
        voice_model: Optional[str] = None,
        voice_config: Optional[str] = None,
        sample_rate: int = 22050,
    ):
        self.voice_model = voice_model
        self.voice_config = voice_config
        self.sample_rate = sample_rate
        self._voice: Any = None
        self._config: Any = None

    @property
    def is_loaded(self) -> bool:
        return self._voice is not None

    def load_voice(self) -> None:
        if self._voice is not None:
            return
        try:
            import piper

            if self.voice_model and os.path.isfile(self.voice_model):
                logger.info("Loading Piper voice: %s", self.voice_model)
                self._voice = piper.PiperVoice.load(
                    self.voice_model,
                    config_path=self.voice_config,
                )
                self._config = self._voice.config
                self.sample_rate = self._config.sample_rate if hasattr(self._config, "sample_rate") else 22050
                logger.info("Piper voice loaded (sample_rate=%d)", self.sample_rate)
            else:
                logger.warning(
                    "No Piper voice model provided or file not found at %s; "
                    "TTS disabled. Download a voice from "
                    "https://huggingface.co/rhasspy/piper-voices",
                    self.voice_model,
                )
                self._voice = None
        except ImportError:
            logger.warning(
                "piper-tts not installed; TTS disabled. "
                "Install with: pip install piper-tts"
            )
            self._voice = None
        except Exception as exc:
            logger.error("Failed to load Piper voice: %s", exc)
            self._voice = None

    def unload_voice(self) -> None:
        self._voice = None
        self._config = None

    def synthesize(
        self,
        text: str,
        length_scale: Optional[float] = None,
        noise_scale: Optional[float] = None,
        noise_w_scale: Optional[float] = None,
    ) -> SynthesisResult:
        if not text:
            return SynthesisResult(audio=b"", sample_rate=self.sample_rate)

        if self._voice is None:
            self.load_voice()

        if self._voice is None:
            logger.warning("TTS unavailable; returning empty audio")
            return SynthesisResult(audio=b"", sample_rate=self.sample_rate)

        return self._synthesize_with_piper(
            text, length_scale, noise_scale, noise_w_scale,
        )

    def synthesize_stream(
        self,
        text: str,
        length_scale: Optional[float] = None,
        noise_scale: Optional[float] = None,
        noise_w_scale: Optional[float] = None,
    ) -> Generator[AudioChunk, None, None]:
        if not text:
            return

        if self._voice is None:
            self.load_voice()
        if self._voice is None:
            return

        try:
            import piper

            syn_config = piper.SynthesisConfig(
                length_scale=length_scale,
                noise_scale=noise_scale,
                noise_w_scale=noise_w_scale,
            )

            audio_stream = self._voice.synthesize(text, syn_config)

            for chunk in audio_stream:
                chunk_data = chunk.audio_int16_bytes
                if chunk_data:
                    yield AudioChunk(
                        data=chunk_data,
                        sample_rate=self.sample_rate,
                        channels=1,
                    )
        except Exception as exc:
            logger.error("Piper synthesis stream error: %s", exc)

    def _synthesize_with_piper(
        self,
        text: str,
        length_scale: Optional[float] = None,
        noise_scale: Optional[float] = None,
        noise_w_scale: Optional[float] = None,
    ) -> SynthesisResult:
        try:
            import piper

            syn_config = piper.SynthesisConfig(
                length_scale=length_scale,
                noise_scale=noise_scale,
                noise_w_scale=noise_w_scale,
            )

            audio_chunks: list = []
            for chunk in self._voice.synthesize(text, syn_config):
                audio_chunks.append(chunk)

            if not audio_chunks:
                return SynthesisResult(audio=b"", sample_rate=self.sample_rate)

            all_audio = np.concatenate([c.audio_int16_array for c in audio_chunks])
            duration_s = len(all_audio) / self.sample_rate

            return SynthesisResult(
                audio=audio_to_int16_bytes(all_audio),
                sample_rate=self.sample_rate,
                duration_s=duration_s,
                text=text,
            )
        except Exception as exc:
            logger.error("Piper synthesis error: %s", exc)
            return SynthesisResult(audio=b"", sample_rate=self.sample_rate)
