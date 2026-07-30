from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import numpy as np

from audio import prepare_for_stt
from models import TranscriptionResult

logger = logging.getLogger(__name__)


_PHRASEOLOGY_BOOST = (
    "Readback correct. Readback incorrect. "
    "Pushback approved. Taxi to runway. Hold short of runway. "
    "Line up and wait. Cleared for takeoff. Cleared to land. "
    "Go around. Contact departure. Contact approach. Contact center. "
    "Climb via SID. Descend via STAR. Fly heading. Maintain altitude. "
    "Request pushback. Request taxi. Request takeoff. "
    "Start-up approved. Cleared ILS approach. "
    "Roger. Wilco. Affirmative. Negative. "
    "Say again. Stand by. "
)


class SttEngine:
    def __init__(
        self,
        model_size: str = "base",
        device: str = "auto",
        compute_type: str = "default",
        vad_filter: bool = True,
        phraseology_boost: bool = True,
        vocabulary: Optional[List[str]] = None,
    ):
        self._model_size = model_size
        self._device = device
        self._compute_type = compute_type
        self._vad_filter = vad_filter
        self._phraseology_boost = phraseology_boost
        self._vocabulary: List[str] = vocabulary or []
        self._model: Any = None

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def load_model(self) -> None:
        if self._model is not None:
            return
        try:
            from faster_whisper import WhisperModel

            logger.info(
                "Loading Whisper model %s (device=%s, compute=%s)",
                self._model_size, self._device, self._compute_type,
            )
            self._model = WhisperModel(
                self._model_size,
                device=self._device,
                compute_type=self._compute_type,
            )
            logger.info("Whisper model loaded successfully")
        except ImportError:
            logger.warning(
                "faster-whisper not installed; STT disabled. "
                "Install with: pip install faster-whisper"
            )
            self._model = None
        except Exception as exc:
            logger.error("Failed to load Whisper model: %s", exc)
            self._model = None

    def unload_model(self) -> None:
        self._model = None

    def update_vocabulary(self, terms: List[str]) -> None:
        for term in terms:
            if term not in self._vocabulary:
                self._vocabulary.append(term)

    def transcribe(
        self,
        audio: np.ndarray,
        sample_rate: int,
        channels: int = 1,
        language: Optional[str] = "en",
    ) -> TranscriptionResult:
        if self._model is None:
            self.load_model()
        if self._model is None:
            return TranscriptionResult(
                text="",
                confidence=0.0,
                language=language or "en",
            )

        prepared_audio, prepared_sr = prepare_for_stt(audio, sample_rate, channels)

        initial_prompt = None
        hotwords = None

        if self._phraseology_boost:
            initial_prompt = _PHRASEOLOGY_BOOST
            if self._vocabulary:
                initial_prompt += " " + " ".join(self._vocabulary)
            hotwords = " ".join(self._vocabulary) if self._vocabulary else None

        segments, info = self._model.transcribe(
            prepared_audio,
            language=language,
            initial_prompt=initial_prompt,
            hotwords=hotwords,
            vad_filter=self._vad_filter,
            beam_size=5,
            word_timestamps=False,
        )

        segments_list = list(segments)
        text = " ".join(seg.text.strip() for seg in segments_list).strip()
        confidence = (
            sum(seg.avg_logprob for seg in segments_list) / len(segments_list)
            if segments_list
            else 0.0
        )

        return TranscriptionResult(
            text=text,
            confidence=float(confidence),
            language=info.language or language or "en",
            segments=[
                {
                    "start": seg.start,
                    "end": seg.end,
                    "text": seg.text,
                    "confidence": seg.avg_logprob,
                }
                for seg in segments_list
            ],
            duration_s=info.duration or 0.0,
        )

    def transcribe_bytes(
        self,
        audio_bytes: bytes,
        sample_rate: int,
        channels: int = 1,
        language: Optional[str] = "en",
    ) -> TranscriptionResult:
        audio = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32767.0
        return self.transcribe(audio, sample_rate, channels, language)
