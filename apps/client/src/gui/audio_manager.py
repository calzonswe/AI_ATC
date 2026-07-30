from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable, List, Optional

import numpy as np

from .state import AudioDeviceInfo

AudioCallback = Callable[[np.ndarray], None]


class AudioManagerBase(ABC):
    @abstractmethod
    def list_input_devices(self) -> List[AudioDeviceInfo]: ...
    @abstractmethod
    def list_output_devices(self) -> List[AudioDeviceInfo]: ...
    @abstractmethod
    def start_capture(self, device_name: str, callback: AudioCallback) -> None: ...
    @abstractmethod
    def stop_capture(self) -> None: ...
    @abstractmethod
    def is_capturing(self) -> bool: ...
    @abstractmethod
    def play_audio(self, device_name: str, audio_data: np.ndarray) -> None: ...


class AudioManager(AudioManagerBase):
    def __init__(self, sample_rate: int = 22050):
        self._sample_rate = sample_rate
        self._capture_stream = None
        self._output_stream = None

    def list_input_devices(self) -> List[AudioDeviceInfo]:
        import sounddevice as sd
        devices: List[AudioDeviceInfo] = []
        for i, dev in enumerate(sd.query_devices()):
            if dev["max_input_channels"] > 0:
                devices.append(AudioDeviceInfo(
                    name=dev["name"], index=i,
                    max_input_channels=dev["max_input_channels"],
                ))
        return devices

    def list_output_devices(self) -> List[AudioDeviceInfo]:
        import sounddevice as sd
        devices: List[AudioDeviceInfo] = []
        for i, dev in enumerate(sd.query_devices()):
            if dev["max_output_channels"] > 0:
                devices.append(AudioDeviceInfo(
                    name=dev["name"], index=i,
                    max_output_channels=dev["max_output_channels"],
                ))
        return devices

    def start_capture(self, device_name: str, callback: AudioCallback) -> None:
        import sounddevice as sd
        if self._capture_stream is not None:
            self.stop_capture()
        device_idx = self._resolve_device_index(device_name, input=True)
        self._capture_stream = sd.InputStream(
            samplerate=self._sample_rate,
            device=device_idx,
            channels=1,
            dtype="int16",
            callback=lambda indata, frames, time_info, status: callback(indata.copy()),
            blocksize=1024,
        )
        self._capture_stream.start()

    def stop_capture(self) -> None:
        if self._capture_stream:
            self._capture_stream.stop()
            self._capture_stream.close()
            self._capture_stream = None

    def is_capturing(self) -> bool:
        return self._capture_stream is not None and self._capture_stream.active

    def play_audio(self, device_name: str, audio_data: np.ndarray) -> None:
        import sounddevice as sd
        device_idx = self._resolve_device_index(device_name, input=False)
        sd.play(audio_data, samplerate=self._sample_rate, device=device_idx)

    def _resolve_device_index(self, name: str, input: bool) -> Optional[int]:
        import sounddevice as sd
        devices = sd.query_devices()
        for i, dev in enumerate(devices):
            if name in dev["name"]:
                if input and dev["max_input_channels"] > 0:
                    return i
                if not input and dev["max_output_channels"] > 0:
                    return i
        return None
