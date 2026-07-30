from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class TranscriptionResult:
    text: str
    confidence: float = 0.0
    language: str = "en"
    segments: List[dict] = field(default_factory=list)
    duration_s: float = 0.0


@dataclass
class SynthesisResult:
    audio: bytes
    sample_rate: int = 22050
    duration_s: float = 0.0
    text: str = ""


@dataclass
class AudioChunk:
    data: bytes
    sample_rate: int
    channels: int = 1
    dtype: str = "int16"


@dataclass
class PipelineConfig:
    stt_model_size: str = "base"
    stt_device: str = "auto"
    stt_compute_type: str = "default"
    tts_voice_model: Optional[str] = None
    tts_voice_config: Optional[str] = None
    sample_rate: int = 16000
    vad_filter: bool = True
    phraseology_boost: bool = True
