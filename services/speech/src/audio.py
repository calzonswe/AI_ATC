from __future__ import annotations

import io
import struct
from typing import Optional, Tuple

import numpy as np

from models import AudioChunk


TARGET_SAMPLE_RATE = 16000
TARGET_CHANNELS = 1
TARGET_DTYPE = np.int16


def resample(
    audio: np.ndarray,
    orig_sr: int,
    target_sr: int = TARGET_SAMPLE_RATE,
) -> np.ndarray:
    if len(audio) == 0 or orig_sr == target_sr:
        return audio
    duration = len(audio) / orig_sr
    target_len = int(duration * target_sr)
    return np.interp(
        np.linspace(0, len(audio) - 1, target_len),
        np.arange(len(audio)),
        audio,
    )


def to_mono(audio: np.ndarray) -> np.ndarray:
    if audio.ndim == 1:
        return audio
    if audio.shape[1] == 1:
        return audio[:, 0]
    return np.mean(audio, axis=1)


def normalize(audio: np.ndarray, target_dtype=np.int16) -> np.ndarray:
    if audio.dtype == target_dtype:
        return audio
    if np.issubdtype(audio.dtype, np.floating):
        max_val = np.max(np.abs(audio))
        if max_val > 0:
            audio = audio / max_val
        if target_dtype == np.int16:
            return (audio * 32767).astype(np.int16)
    return audio.astype(target_dtype)


def prepare_for_stt(
    audio: np.ndarray,
    sample_rate: int,
    channels: int = 1,
) -> Tuple[np.ndarray, int]:
    if channels > 1:
        audio = to_mono(audio)
    audio = resample(audio, sample_rate, TARGET_SAMPLE_RATE)
    audio = normalize(audio, np.float32)
    return audio, TARGET_SAMPLE_RATE


def audio_to_int16_bytes(audio: np.ndarray) -> bytes:
    audio = normalize(audio, np.int16)
    return audio.tobytes()


def int16_bytes_to_audio(data: bytes) -> np.ndarray:
    return np.frombuffer(data, dtype=np.int16)


def _wav_header(sample_rate: int, data_size: int, num_channels: int = 1, bits_per_sample: int = 16) -> bytes:
    byte_rate = sample_rate * num_channels * bits_per_sample // 8
    block_align = num_channels * bits_per_sample // 8
    buf = io.BytesIO()
    buf.write(b"RIFF")
    buf.write(struct.pack("<I", 36 + data_size))
    buf.write(b"WAVE")
    buf.write(b"fmt ")
    buf.write(struct.pack("<I", 16))
    buf.write(struct.pack("<H", 1))
    buf.write(struct.pack("<H", num_channels))
    buf.write(struct.pack("<I", sample_rate))
    buf.write(struct.pack("<I", byte_rate))
    buf.write(struct.pack("<H", block_align))
    buf.write(struct.pack("<H", bits_per_sample))
    buf.write(b"data")
    buf.write(struct.pack("<I", data_size))
    return buf.getvalue()


def pcm_to_wav(audio: np.ndarray, sample_rate: int) -> bytes:
    audio_int16 = normalize(audio, np.int16)
    return _wav_header(sample_rate, len(audio_int16) * 2) + audio_int16.tobytes()


def pcm_bytes_to_wav(pcm_bytes: bytes, sample_rate: int) -> bytes:
    return _wav_header(sample_rate, len(pcm_bytes)) + pcm_bytes


def wav_to_pcm(wav_bytes: bytes) -> AudioChunk:
    if wav_bytes[:4] != b"RIFF":
        audio = int16_bytes_to_audio(wav_bytes)
        return AudioChunk(data=wav_bytes, sample_rate=TARGET_SAMPLE_RATE, channels=1)

    sample_rate = struct.unpack("<I", wav_bytes[24:28])[0]
    num_channels = struct.unpack("<H", wav_bytes[22:24])[0]
    bits_per_sample = struct.unpack("<H", wav_bytes[34:36])[0]
    data_start = 44
    data = wav_bytes[data_start:]
    return AudioChunk(
        data=data,
        sample_rate=sample_rate,
        channels=num_channels,
        dtype=f"int{bits_per_sample}",
    )


def chunk_generator(
    audio: np.ndarray,
    sample_rate: int,
    chunk_size_s: float = 0.1,
) -> AudioChunk:
    chunk_samples = int(sample_rate * chunk_size_s)
    total_samples = len(audio)
    offset = 0
    while offset < total_samples:
        end = min(offset + chunk_samples, total_samples)
        chunk_data = audio_to_int16_bytes(audio[offset:end])
        yield AudioChunk(
            data=chunk_data,
            sample_rate=sample_rate,
            channels=1,
        )
        offset = end
