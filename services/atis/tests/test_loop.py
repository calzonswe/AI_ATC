import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import itertools
import struct

import pytest

from generator import AtisAudioGenerator
from loop import AtisBroadcastLoop


class FakeTtsEngine:
    def __init__(self, sample_rate: int = 22050):
        self.sample_rate = sample_rate

    def synthesize(self, text: str):
        duration_s = max(len(text) * 0.05, 0.5)
        num_samples = int(self.sample_rate * duration_s)
        audio = b"\x00\x00" * num_samples
        from types import SimpleNamespace
        return SimpleNamespace(
            audio=audio,
            sample_rate=self.sample_rate,
            duration_s=duration_s,
            text=text,
        )


class TestAtisBroadcastLoop:
    def test_init(self):
        gen = AtisAudioGenerator()
        loop = AtisBroadcastLoop(gen)
        assert loop.identifier == ""
        assert loop.get_wav_bytes() == b""

    def test_update_broadcast_generates_wav(self):
        gen = AtisAudioGenerator(FakeTtsEngine())
        loop = AtisBroadcastLoop(gen)
        loop.update_broadcast("ESSA ATIS Information Alpha", "Alpha")
        assert loop.identifier == "Alpha"
        wav = loop.get_wav_bytes()
        assert wav.startswith(b"RIFF")
        assert wav[8:12] == b"WAVE"

    def test_update_broadcast_twice(self):
        gen = AtisAudioGenerator(FakeTtsEngine())
        loop = AtisBroadcastLoop(gen)
        loop.update_broadcast("ESSA ATIS Information Alpha", "Alpha")
        loop.update_broadcast("ESSA ATIS Information Bravo", "Bravo")
        assert loop.identifier == "Bravo"

    def test_stream_loop_returns_chunks(self):
        gen = AtisAudioGenerator(FakeTtsEngine())
        loop = AtisBroadcastLoop(gen)
        loop.update_broadcast("ESSA ATIS Information Alpha", "Alpha")
        chunks = list(itertools.islice(loop.stream_loop(), 10))
        assert len(chunks) == 10
        wav = loop.get_wav_bytes()
        header_size = 44
        expected_per_chunk = int(loop.sample_rate * loop._chunk_size_s) * 2
        total_looped = sum(len(c) for c in chunks)
        expected_total = (len(wav) - header_size)
        assert total_looped == expected_per_chunk * 10

    def test_stream_loop_empty_returns_empty(self):
        gen = AtisAudioGenerator()
        loop = AtisBroadcastLoop(gen)
        chunks = list(itertools.islice(loop.stream_loop(), 3))
        assert len(chunks) == 3
        assert all(c == b"" for c in chunks)

    def test_sample_rate_propagation(self):
        gen = AtisAudioGenerator(FakeTtsEngine(sample_rate=16000))
        loop = AtisBroadcastLoop(gen)
        loop.update_broadcast("Test", "Alpha")
        assert loop.sample_rate == 16000

    def test_is_stale_initially(self):
        gen = AtisAudioGenerator()
        loop = AtisBroadcastLoop(gen)
        assert loop.is_stale() is True

    def test_is_stale_after_update(self):
        gen = AtisAudioGenerator(FakeTtsEngine())
        loop = AtisBroadcastLoop(gen)
        loop.update_broadcast("Test", "Alpha")
        assert loop.is_stale(max_age_s=0) is True
        assert loop.is_stale(max_age_s=300) is False
