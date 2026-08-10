"""Microphone recording and lightweight reference-audio cleanup."""

from __future__ import annotations

import threading
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd


class MicrophoneRecorder:
    """Capture mono microphone audio without blocking the user interface."""

    def __init__(self, sample_rate: int = 48_000) -> None:
        self.sample_rate = sample_rate
        self._frames: list[np.ndarray] = []
        self._lock = threading.Lock()
        self._stream: sd.InputStream | None = None

    @staticmethod
    def input_devices() -> list[tuple[int, str]]:
        devices: list[tuple[int, str]] = []
        for index, device in enumerate(sd.query_devices()):
            if int(device["max_input_channels"]) > 0:
                devices.append((index, str(device["name"])))
        return devices

    @property
    def is_recording(self) -> bool:
        return self._stream is not None

    def start(self, device_index: int | None = None) -> None:
        if self.is_recording:
            return

        with self._lock:
            self._frames.clear()

        def callback(indata: np.ndarray, frames: int, time, status) -> None:
            del frames, time
            if status:
                print(status)
            with self._lock:
                self._frames.append(indata[:, 0].copy())

        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            device=device_index,
            callback=callback,
        )
        self._stream.start()

    def stop_and_save(self, destination: Path) -> float:
        if self._stream is None:
            raise RuntimeError("No recording is currently active.")

        stream = self._stream
        self._stream = None
        stream.stop()
        stream.close()

        with self._lock:
            if not self._frames:
                raise RuntimeError("The microphone did not return any audio.")
            audio = np.concatenate(self._frames)

        audio = self._clean_audio(audio)
        duration = len(audio) / self.sample_rate
        if duration < 3:
            raise ValueError("The recording is too short. Record at least 3 seconds.")

        destination.parent.mkdir(parents=True, exist_ok=True)
        pcm = (audio * 32_767).astype("<i2")
        with wave.open(str(destination), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(pcm.tobytes())

        return duration

    def cancel(self) -> None:
        """Release the microphone without saving a partial recording."""
        stream = self._stream
        self._stream = None
        if stream is not None:
            stream.abort()
            stream.close()
        with self._lock:
            self._frames.clear()

    def _clean_audio(self, audio: np.ndarray) -> np.ndarray:
        audio = np.nan_to_num(audio.astype(np.float32, copy=False))
        peak = float(np.max(np.abs(audio))) if audio.size else 0.0
        if peak < 0.005:
            raise ValueError("The recording is silent or too quiet.")

        threshold = max(0.008, peak * 0.025)
        voiced = np.flatnonzero(np.abs(audio) >= threshold)
        if voiced.size:
            padding = int(self.sample_rate * 0.05)
            start = max(0, int(voiced[0]) - padding)
            end = min(len(audio), int(voiced[-1]) + padding + 1)
            audio = audio[start:end]

        maximum_samples = 30 * self.sample_rate
        if len(audio) > maximum_samples:
            audio = audio[:maximum_samples]

        peak = float(np.max(np.abs(audio)))
        return audio * (0.92 / peak)
