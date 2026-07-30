import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import io
import struct
from unittest.mock import MagicMock, PropertyMock, patch

import numpy as np
import pytest

from audio import (
    AudioChunk,
    audio_to_int16_bytes,
    chunk_generator,
    int16_bytes_to_audio,
    normalize,
    pcm_to_wav,
    prepare_for_stt,
    resample,
    to_mono,
    wav_to_pcm,
)
from models import PipelineConfig, SynthesisResult, TranscriptionResult
from pipeline import AudioPipeline
from stt import SttEngine
from tts import TtsEngine


# ═══════════════════════════════════════════════
# Audio Utilities
# ═══════════════════════════════════════════════

class TestResample:
    def test_same_rate_unchanged(self):
        audio = np.array([0.0, 0.5, 1.0, -0.5], dtype=np.float32)
        result = resample(audio, 16000, 16000)
        np.testing.assert_array_equal(result, audio)

    def test_downsample(self):
        audio = np.sin(np.linspace(0, 2 * np.pi, 1600))
        result = resample(audio, 16000, 8000)
        assert len(result) == 800

    def test_upsample(self):
        audio = np.sin(np.linspace(0, 2 * np.pi, 800))
        result = resample(audio, 8000, 16000)
        assert len(result) == 1600

    def test_empty_audio(self):
        audio = np.array([], dtype=np.float32)
        result = resample(audio, 16000, 8000)
        assert len(result) == 0


class TestToMono:
    def test_mono_unchanged(self):
        audio = np.array([0.0, 0.5, 1.0], dtype=np.float32)
        result = to_mono(audio)
        np.testing.assert_array_equal(result, audio)

    def test_stereo_to_mono(self):
        audio = np.array([[0.0, 1.0], [0.5, 0.5]], dtype=np.float32)
        result = to_mono(audio)
        assert result.ndim == 1
        assert result[0] == 0.5
        assert result[1] == 0.5

    def test_single_channel_stereo(self):
        audio = np.array([[0.0], [0.5], [1.0]], dtype=np.float32)
        result = to_mono(audio)
        assert result.ndim == 1
        np.testing.assert_array_equal(result, [0.0, 0.5, 1.0])


class TestNormalize:
    def test_int16_unchanged(self):
        audio = np.array([0, 100, -100], dtype=np.int16)
        result = normalize(audio, np.int16)
        np.testing.assert_array_equal(result, audio)

    def test_float_to_int16(self):
        audio = np.array([0.0, 0.5, 1.0, -1.0], dtype=np.float32)
        result = normalize(audio, np.int16)
        assert result.dtype == np.int16
        assert result[0] == 0
        assert result[2] == 32767
        assert result[3] == -32767  # -1.0 * 32767 = -32767

    def test_float_normalization(self):
        audio = np.array([0.0, 0.25, 0.5], dtype=np.float32)
        result = normalize(audio, np.float32)
        assert np.max(np.abs(result)) <= 1.0


class TestPcmToWav:
    def test_creates_valid_wav_header(self):
        audio = np.array([0, 100, -100, 200], dtype=np.int16)
        wav = pcm_to_wav(audio, 16000)
        assert wav[:4] == b"RIFF"
        assert wav[8:12] == b"WAVE"
        fmt_chunk_size = struct.unpack("<I", wav[16:20])[0]
        assert fmt_chunk_size == 16
        audio_format = struct.unpack("<H", wav[20:22])[0]
        assert audio_format == 1
        channels = struct.unpack("<H", wav[22:24])[0]
        assert channels == 1
        sample_rate = struct.unpack("<I", wav[24:28])[0]
        assert sample_rate == 16000
        bits_per_sample = struct.unpack("<H", wav[34:36])[0]
        assert bits_per_sample == 16

    def test_roundtrip(self):
        original = np.array([0, 100, -100, 200], dtype=np.int16)
        wav = pcm_to_wav(original, 16000)
        chunk = wav_to_pcm(wav)
        assert chunk.sample_rate == 16000
        assert chunk.channels == 1
        reconstructed = np.frombuffer(chunk.data, dtype=np.int16)
        np.testing.assert_array_equal(reconstructed, original)


class TestWavToPcm:
    def test_raw_pcm_passthrough(self):
        data = b"\x00\x00\x01\x00"
        chunk = wav_to_pcm(data)
        assert chunk.data == data

    def test_wav_parsing(self):
        audio = np.array([0, 100, -100], dtype=np.int16)
        wav = pcm_to_wav(audio, 16000)
        chunk = wav_to_pcm(wav)
        assert chunk.sample_rate == 16000
        assert chunk.channels == 1
        assert chunk.dtype == "int16"
        reconstructed = np.frombuffer(chunk.data, dtype=np.int16)
        np.testing.assert_array_equal(reconstructed, audio)


class TestPrepareForStt:
    def test_mono_float32_output(self):
        audio = np.array([0.0, 0.5, -0.5], dtype=np.float32)
        result, sr = prepare_for_stt(audio, 16000)
        assert sr == 16000
        assert result.dtype == np.float32

    def test_stereo_to_mono(self):
        audio = np.array([[0.0, 1.0], [0.5, 0.5]], dtype=np.float32)
        result, sr = prepare_for_stt(audio, 16000, channels=2)
        assert sr == 16000
        assert result.ndim == 1

    def test_int16_to_float32(self):
        audio = np.array([0, 32767, -32768], dtype=np.int16)
        result, sr = prepare_for_stt(audio, 16000)
        assert result.dtype == np.float32
        assert abs(result[0]) <= 1.0


class TestAudioToInt16Bytes:
    def test_float_to_bytes(self):
        audio = np.array([0.0, 0.5, 1.0], dtype=np.float32)
        result = audio_to_int16_bytes(audio)
        assert isinstance(result, bytes)
        assert len(result) == 6  # 3 samples * 2 bytes

    def test_int16_to_bytes(self):
        audio = np.array([0, 100], dtype=np.int16)
        result = audio_to_int16_bytes(audio)
        assert len(result) == 4


class TestInt16BytesToAudio:
    def test_roundtrip(self):
        original = np.array([0, 100, -100, 32767], dtype=np.int16)
        data = original.tobytes()
        result = int16_bytes_to_audio(data)
        np.testing.assert_array_equal(result, original)


class TestChunkGenerator:
    def test_generates_chunks(self):
        audio = np.zeros(16000, dtype=np.int16)
        chunks = list(chunk_generator(audio, 16000, chunk_size_s=0.1))
        assert len(chunks) == 10
        for chunk in chunks:
            assert isinstance(chunk, AudioChunk)
            assert chunk.sample_rate == 16000
            assert chunk.channels == 1
            assert len(chunk.data) == 3200  # 0.1s * 16000 * 2 bytes

    def test_partial_last_chunk(self):
        audio = np.zeros(100, dtype=np.int16)
        chunks = list(chunk_generator(audio, 16000, chunk_size_s=0.1))
        assert len(chunks) == 1
        assert len(chunks[0].data) == 200  # 100 * 2

    def test_empty_audio(self):
        audio = np.array([], dtype=np.int16)
        chunks = list(chunk_generator(audio, 16000))
        assert len(chunks) == 0


# ═══════════════════════════════════════════════
# SttEngine
# ═══════════════════════════════════════════════

class TestSttEngineInit:
    def test_default_init(self):
        engine = SttEngine()
        assert engine._model_size == "base"
        assert engine._vad_filter is True
        assert engine._phraseology_boost is True
        assert engine._vocabulary == []
        assert engine.is_loaded is False

    def test_custom_init(self):
        engine = SttEngine(
            model_size="tiny",
            device="cpu",
            compute_type="int8",
            vad_filter=False,
            phraseology_boost=False,
            vocabulary=["SAS901", "ESSA"],
        )
        assert engine._model_size == "tiny"
        assert engine._vocabulary == ["SAS901", "ESSA"]

    def test_update_vocabulary(self):
        engine = SttEngine()
        engine.update_vocabulary(["SAS901", "ESSA"])
        assert "SAS901" in engine._vocabulary
        assert "ESSA" in engine._vocabulary

    def test_update_vocabulary_deduplicates(self):
        engine = SttEngine(vocabulary=["SAS901"])
        engine.update_vocabulary(["SAS901"])
        assert engine._vocabulary == ["SAS901"]

    def test_load_model_no_whisper(self):
        with patch.dict("sys.modules", {"faster_whisper": None}):
            with patch("builtins.__import__", side_effect=ImportError):
                engine = SttEngine()
                engine.load_model()
                assert engine.is_loaded is False

    def test_unload_model(self):
        engine = SttEngine()
        engine._model = MagicMock()
        engine.unload_model()
        assert engine.is_loaded is False

    def test_transcribe_without_model_returns_empty(self):
        engine = SttEngine()
        result = engine.transcribe(np.zeros(1600, dtype=np.float32), 16000)
        assert isinstance(result, TranscriptionResult)
        assert result.text == ""

    def test_transcribe_bytes_without_model_returns_empty(self):
        engine = SttEngine()
        result = engine.transcribe_bytes(b"\x00\x00" * 800, 16000)
        assert isinstance(result, TranscriptionResult)
        assert result.text == ""


# ═══════════════════════════════════════════════
# TtsEngine
# ═══════════════════════════════════════════════

class TestTtsEngineInit:
    def test_default_init(self):
        engine = TtsEngine()
        assert engine.voice_model is None
        assert engine.sample_rate == 22050
        assert engine.is_loaded is False

    def test_custom_init(self):
        engine = TtsEngine(
            voice_model="/models/voice.onnx",
            voice_config="/models/voice.json",
            sample_rate=16000,
        )
        assert engine.voice_model == "/models/voice.onnx"
        assert engine.sample_rate == 16000

    def test_unload_voice(self):
        engine = TtsEngine()
        engine._voice = MagicMock()
        engine._config = MagicMock()
        engine.unload_voice()
        assert engine.is_loaded is False
        assert engine._config is None

    def test_synthesize_empty_text(self):
        engine = TtsEngine()
        result = engine.synthesize("")
        assert isinstance(result, SynthesisResult)
        assert result.audio == b""

    def test_synthesize_no_voice_returns_empty(self):
        engine = TtsEngine()
        result = engine.synthesize("Hello")
        assert isinstance(result, SynthesisResult)
        assert result.audio == b""

    def test_synthesize_stream_no_voice_produces_nothing(self):
        engine = TtsEngine()
        chunks = list(engine.synthesize_stream("Hello"))
        assert chunks == []

    def test_synthesize_stream_empty_text(self):
        engine = TtsEngine()
        chunks = list(engine.synthesize_stream(""))
        assert chunks == []


# ═══════════════════════════════════════════════
# AudioPipeline
# ═══════════════════════════════════════════════

class TestAudioPipeline:
    def test_init_defaults(self):
        pipeline = AudioPipeline()
        assert pipeline.stt is not None
        assert pipeline.tts is not None
        assert pipeline.llm_callback is None

    def test_update_context(self):
        pipeline = AudioPipeline()
        pipeline.update_context(callsign="SAS901", airport="ESSA")
        assert pipeline._context["callsign"] == "SAS901"

    def test_update_vocabulary(self):
        pipeline = AudioPipeline()
        pipeline.update_vocabulary(["SAS901", "ESSA"])
        assert "SAS901" in pipeline._vocabulary
        assert "SAS901" in pipeline.stt._vocabulary

    def test_set_llm_callback(self):
        pipeline = AudioPipeline()
        callback = MagicMock()
        pipeline.set_llm_callback(callback)
        assert pipeline.llm_callback is callback

    def test_process_audio_no_speech(self):
        stt = MagicMock()
        stt.transcribe.return_value = TranscriptionResult(text="", confidence=0.0)
        pipeline = AudioPipeline(stt_engine=stt)
        result = pipeline.process_audio(np.zeros(1600, dtype=np.float32), 16000)
        assert isinstance(result, SynthesisResult)
        assert result.audio == b""

    def test_process_audio_full_roundtrip(self):
        stt = MagicMock()
        stt.transcribe.return_value = TranscriptionResult(
            text="taxi to runway zero one left",
            confidence=0.95,
            duration_s=2.0,
        )
        tts = MagicMock()
        tts.sample_rate = 22050
        tts.synthesize.return_value = SynthesisResult(
            audio=b"\x00\x00" * 1000,
            sample_rate=22050,
            duration_s=1.0,
            text="SAS901, TAXI TO RUNWAY 01L",
        )
        llm = MagicMock(return_value="SAS901, TAXI TO RUNWAY 01L")

        pipeline = AudioPipeline(stt_engine=stt, tts_engine=tts, llm_callback=llm)
        result = pipeline.process_audio(np.zeros(1600, dtype=np.float32), 16000)

        assert len(result.audio) > 0
        assert result.duration_s == 1.0
        llm.assert_called_once()

    def test_process_audio_with_context(self):
        stt = MagicMock()
        stt.transcribe.return_value = TranscriptionResult(
            text="contact departure",
            confidence=0.9,
        )
        tts = MagicMock()
        tts.sample_rate = 22050
        tts.synthesize.return_value = SynthesisResult(
            audio=b"\x00\x00" * 100,
            sample_rate=22050,
            duration_s=0.1,
        )

        llm = MagicMock(return_value="SAS901, CONTACT DEPARTURE 124.3")

        pipeline = AudioPipeline(stt_engine=stt, tts_engine=tts, llm_callback=llm)
        result = pipeline.process_audio(
            np.zeros(1600, dtype=np.float32), 16000,
            context={"callsign": "SAS901", "frequency": "124.3"},
        )

        assert len(result.audio) > 0
        assert pipeline._context["callsign"] == "SAS901"

    def test_process_audio_stream_full_roundtrip(self):
        stt = MagicMock()
        stt.transcribe.return_value = TranscriptionResult(
            text="cleared for takeoff",
            confidence=0.95,
        )
        tts = MagicMock()
        tts.sample_rate = 22050
        chunk1 = AudioChunk(data=b"\x00\x00" * 500, sample_rate=22050, channels=1)
        chunk2 = AudioChunk(data=b"\x00\x00" * 500, sample_rate=22050, channels=1)
        tts.synthesize_stream.return_value = iter([chunk1, chunk2])

        llm = MagicMock(return_value="SAS901, CLEARED FOR TAKEOFF RUNWAY 01L")

        pipeline = AudioPipeline(stt_engine=stt, tts_engine=tts, llm_callback=llm)
        chunks = list(pipeline.process_audio_stream(
            np.zeros(1600, dtype=np.float32), 16000,
        ))

        assert len(chunks) == 2
        assert all(isinstance(c, AudioChunk) for c in chunks)

    def test_process_audio_bytes(self):
        stt = MagicMock()
        stt.transcribe.return_value = TranscriptionResult(
            text="line up and wait",
            confidence=0.9,
        )
        tts = MagicMock()
        tts.sample_rate = 22050
        tts.synthesize.return_value = SynthesisResult(
            audio=b"\x00\x00" * 200,
            sample_rate=22050,
            duration_s=0.2,
        )

        pipeline = AudioPipeline(stt_engine=stt, tts_engine=tts)
        pipeline.set_llm_callback(MagicMock(return_value="SAS901, LINE UP AND WAIT"))
        audio_bytes = b"\x00\x00" * 800
        result = pipeline.process_audio_bytes(audio_bytes, 16000)

        assert len(result.audio) > 0

    def test_no_llm_callback_returns_transcription(self):
        stt = MagicMock()
        stt.transcribe.return_value = TranscriptionResult(
            text="taxi to runway", confidence=0.9,
        )
        tts = MagicMock()
        tts.sample_rate = 22050
        tts.synthesize.return_value = SynthesisResult(
            audio=b"\x00\x00" * 100,
            sample_rate=22050,
            duration_s=0.1,
        )

        pipeline = AudioPipeline(stt_engine=stt, tts_engine=tts)
        result = pipeline.process_audio(np.zeros(1600, dtype=np.float32), 16000)

        # Without callback, transcription text is returned as response
        assert len(result.audio) > 0

    def test_llm_callback_error_handled(self):
        stt = MagicMock()
        stt.transcribe.return_value = TranscriptionResult(
            text="hello", confidence=0.9,
        )
        pipeline = AudioPipeline(stt_engine=stt)
        pipeline.set_llm_callback(MagicMock(side_effect=RuntimeError("LLM down")))
        result = pipeline.process_audio(np.zeros(1600, dtype=np.float32), 16000)
        assert result.audio == b""


# ═══════════════════════════════════════════════
# PipelineConfig
# ═══════════════════════════════════════════════

class TestPipelineConfig:
    def test_defaults(self):
        cfg = PipelineConfig()
        assert cfg.stt_model_size == "base"
        assert cfg.stt_device == "auto"
        assert cfg.sample_rate == 16000
        assert cfg.vad_filter is True
        assert cfg.phraseology_boost is True
        assert cfg.tts_voice_model is None

    def test_custom_values(self):
        cfg = PipelineConfig(
            stt_model_size="tiny",
            stt_device="cpu",
            vad_filter=False,
            phraseology_boost=False,
        )
        assert cfg.stt_model_size == "tiny"
        assert cfg.vad_filter is False


# ═══════════════════════════════════════════════
# AudioChunk model
# ═══════════════════════════════════════════════

class TestAudioChunk:
    def test_create(self):
        chunk = AudioChunk(data=b"\x00\x00", sample_rate=16000, channels=1)
        assert chunk.data == b"\x00\x00"
        assert chunk.sample_rate == 16000
        assert chunk.dtype == "int16"

    def test_default_dtype(self):
        chunk = AudioChunk(data=b"", sample_rate=16000)
        assert chunk.dtype == "int16"


# ═══════════════════════════════════════════════
# SttEngine: phraseology boost
# ═══════════════════════════════════════════════

class TestPhraseologyBoost:
    def test_vocabulary_updates_used_in_transcribe(self):
        engine = SttEngine(phraseology_boost=True)
        engine._model = MagicMock()
        engine._model.transcribe.return_value = (
            iter([]),
            MagicMock(language="en", duration=0.0),
        )
        engine.update_vocabulary(["SAS901", "BARK1A"])
        engine.transcribe(np.zeros(1600, dtype=np.float32), 16000)

        call_kwargs = engine._model.transcribe.call_args
        assert call_kwargs is not None
        kwargs = call_kwargs[1] if len(call_kwargs.args) <= 1 else {}
        assert "initial_prompt" in kwargs
        assert "SAS901" in kwargs["initial_prompt"]
        assert "hotwords" in kwargs
        assert "SAS901" in kwargs["hotwords"]

    def test_phraseology_boost_disabled(self):
        engine = SttEngine(phraseology_boost=False)
        engine._model = MagicMock()
        engine._model.transcribe.return_value = (
            iter([]),
            MagicMock(language="en", duration=0.0),
        )
        engine.transcribe(np.zeros(1600, dtype=np.float32), 16000)

        call_kwargs = engine._model.transcribe.call_args
        assert call_kwargs is not None
        kwargs = call_kwargs[1] if len(call_kwargs.args) <= 1 else {}
        # hotwords should not be present when vocabulary is empty
        assert kwargs.get("hotwords") is None


# ═══════════════════════════════════════════════
# Pipeline with mocked config
# ═══════════════════════════════════════════════

class TestPipelineWithConfig:
    def test_pipeline_from_config(self):
        cfg = PipelineConfig(
            stt_model_size="tiny",
            stt_device="cpu",
            vad_filter=False,
            phraseology_boost=False,
        )
        pipeline = AudioPipeline(config=cfg)
        assert pipeline.stt._model_size == "tiny"
        assert pipeline.stt._vad_filter is False
        assert pipeline.stt._phraseology_boost is False
