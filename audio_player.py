"""Non-blocking audio playback inside the desktop application."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf


class AudioPlayer:
    @staticmethod
    def play_file(path: Path) -> float:
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        samples, sample_rate = sf.read(path, dtype="float32", always_2d=False)
        return AudioPlayer.play_samples(samples, int(sample_rate))

    @staticmethod
    def play_samples(samples: np.ndarray, sample_rate: int) -> float:
        audio = np.asarray(samples, dtype=np.float32)
        if audio.size == 0:
            raise ValueError("The audio is empty.")
        sd.stop()
        sd.play(audio, samplerate=sample_rate, blocking=False)
        return len(audio) / sample_rate

    @staticmethod
    def stop() -> None:
        sd.stop()
