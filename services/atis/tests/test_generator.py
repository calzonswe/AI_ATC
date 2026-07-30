import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import struct
from dataclasses import dataclass
from typing import Optional

import pytest

from generator import AtisAudioGenerator


@dataclass
class FakeSynthesisResult:
    audio: bytes
    sample_rate: int = 22050
    duration_s: float = 0.0
    text: str = ""


class FakeTtsEngine:
    def __init__(self, sample_rate: int = 22050):
        self.sample_rate = sample_rate

    def synthesize(self, text: str) -> FakeSynthesisResult:
        duration_s = max(len(text) * 0.05, 0.5)
        num_samples = int(self.sample_rate * duration_s)
        audio = b"\x00\x00" * num_samples
        return FakeSynthesisResult(
            audio=audio,
            sample_rate=self.sample_rate,
            duration_s=duration_s,
            text=text,
        )


class TestAtisAudioGenerator:
    def test_init_defaults(self):
        gen = AtisAudioGenerator()
        assert gen.sample_rate == 22050

    def test_generate_wav_without_tts_returns_silence(self):
        gen = AtisAudioGenerator()
        wav = gen.generate_wav("ESSA ATIS Information Alpha")
        assert wav.startswith(b"RIFF")
        assert wav[8:12] == b"WAVE"

    def test_generate_wav_with_tts(self):
        tts = FakeTtsEngine()
        gen = AtisAudioGenerator(tts)
        wav = gen.generate_wav("ESSA ATIS Information Alpha")
        assert wav.startswith(b"RIFF")
        assert wav[8:12] == b"WAVE"

    def test_wav_header_format(self):
        gen = AtisAudioGenerator()
        wav = gen.generate_wav("Test")
        fmt = wav[12:16]
        assert fmt == b"fmt "
        assert struct.unpack("<H", wav[20:22])[0] == 1  # PCM
        assert struct.unpack("<H", wav[22:24])[0] == 1  # mono
        data_size = struct.unpack("<I", wav[40:44])[0]
        assert len(wav) == 44 + data_size

    def test_empty_text_returns_silence(self):
        gen = AtisAudioGenerator()
        wav = gen.generate_wav("")
        assert wav.startswith(b"RIFF")

    def test_set_tts_engine(self):
        gen = AtisAudioGenerator()
        tts = FakeTtsEngine()
        gen.set_tts_engine(tts)
        wav = gen.generate_wav("Test")
        assert wav.startswith(b"RIFF")

    def test_generate_wav_different_sample_rates(self):
        tts = FakeTtsEngine(sample_rate=16000)
        gen = AtisAudioGenerator(tts)
        wav = gen.generate_wav("Test ATIS")
        assert struct.unpack("<I", wav[24:28])[0] == 16000
        assert len(wav) > 44

    def test_generate_wav_22050_sample_rate(self):
        tts = FakeTtsEngine(sample_rate=22050)
        gen = AtisAudioGenerator(tts)
        wav = gen.generate_wav("Test ATIS")
        assert struct.unpack("<I", wav[24:28])[0] == 22050

    def test_tts_failure_falls_back_to_silence(self):
        class BrokenTts:
            def synthesize(self, text):
                raise RuntimeError("TTS failed")

        gen = AtisAudioGenerator(BrokenTts())
        wav = gen.generate_wav("Test")
        assert wav.startswith(b"RIFF")
