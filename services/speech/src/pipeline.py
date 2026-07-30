from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Generator, List, Optional

import numpy as np

from audio import prepare_for_stt
from models import AudioChunk, PipelineConfig, SynthesisResult, TranscriptionResult
from stt import SttEngine
from tts import TtsEngine

logger = logging.getLogger(__name__)


LlmCallback = Callable[[str, Dict[str, Any]], str]


class AudioPipeline:
    def __init__(
        self,
        config: Optional[PipelineConfig] = None,
        stt_engine: Optional[SttEngine] = None,
        tts_engine: Optional[TtsEngine] = None,
        llm_callback: Optional[LlmCallback] = None,
    ):
        cfg = config or PipelineConfig()
        self.stt = stt_engine or SttEngine(
            model_size=cfg.stt_model_size,
            device=cfg.stt_device,
            compute_type=cfg.stt_compute_type,
            vad_filter=cfg.vad_filter,
            phraseology_boost=cfg.phraseology_boost,
        )
        self.tts = tts_engine or TtsEngine(
            voice_model=cfg.tts_voice_model,
            voice_config=cfg.tts_voice_config,
        )
        self.llm_callback: Optional[LlmCallback] = llm_callback
        self._context: Dict[str, Any] = {}
        self._vocabulary: List[str] = []

    def update_context(self, **kwargs: Any) -> None:
        self._context.update(kwargs)

    def update_vocabulary(self, terms: List[str]) -> None:
        for term in terms:
            if term not in self._vocabulary:
                self._vocabulary.append(term)
        self.stt.update_vocabulary(terms)

    def set_llm_callback(self, callback: LlmCallback) -> None:
        self.llm_callback = callback

    def process_audio(
        self,
        audio: np.ndarray,
        sample_rate: int,
        channels: int = 1,
        context: Optional[Dict[str, Any]] = None,
    ) -> SynthesisResult:
        if context:
            self._context.update(context)

        transcription = self.stt.transcribe(audio, sample_rate, channels)
        if not transcription.text:
            logger.info("No speech detected in audio")
            return SynthesisResult(audio=b"", sample_rate=self.tts.sample_rate)

        logger.info(
            "STT: %.1fs audio -> '%s' (conf=%.2f)",
            transcription.duration_s, transcription.text, transcription.confidence,
        )

        response_text = self._call_llm(transcription.text)
        if not response_text:
            return SynthesisResult(audio=b"", sample_rate=self.tts.sample_rate)

        synthesis = self.tts.synthesize(response_text)
        logger.info(
            "TTS: '%s' -> %.1fs audio (%d bytes)",
            response_text, synthesis.duration_s, len(synthesis.audio),
        )
        return synthesis

    def process_audio_stream(
        self,
        audio: np.ndarray,
        sample_rate: int,
        channels: int = 1,
        context: Optional[Dict[str, Any]] = None,
    ) -> Generator[AudioChunk, None, None]:
        if context:
            self._context.update(context)

        transcription = self.stt.transcribe(audio, sample_rate, channels)
        if not transcription.text:
            return

        response_text = self._call_llm(transcription.text)
        if not response_text:
            return

        yield from self.tts.synthesize_stream(response_text)

    def process_audio_bytes(
        self,
        audio_bytes: bytes,
        sample_rate: int,
        channels: int = 1,
        context: Optional[Dict[str, Any]] = None,
    ) -> SynthesisResult:
        audio = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32767.0
        return self.process_audio(audio, sample_rate, channels, context)

    def _call_llm(self, transcription: str) -> str:
        if self.llm_callback:
            try:
                return self.llm_callback(transcription, self._context)
            except Exception as exc:
                logger.error("LLM callback error: %s", exc)
                return ""
        logger.warning("No LLM callback configured; returning transcription as-is")
        return transcription
