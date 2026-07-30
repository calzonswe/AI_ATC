from __future__ import annotations

import logging
from typing import Optional

from pydantic_settings import BaseSettings

from models import PipelineConfig

logger = logging.getLogger(__name__)


class SpeechSettings(BaseSettings):
    model_config = {"extra": "ignore"}

    stt_model_size: str = "base"
    stt_device: str = "auto"
    stt_compute_type: str = "default"
    tts_voice_model: Optional[str] = None
    tts_voice_config: Optional[str] = None
    sample_rate: int = 16000
    vad_filter: bool = True
    phraseology_boost: bool = True

    @classmethod
    def from_pipeline_config(cls, config: PipelineConfig) -> SpeechSettings:
        return cls(**config.model_dump())


settings = SpeechSettings()
