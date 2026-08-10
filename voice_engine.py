"""Lazy-loading Chatterbox voice-cloning inference and MP3 export."""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from pathlib import Path

import lameenc
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parent
MODEL_CACHE = PROJECT_ROOT / "models" / "huggingface"
MODEL_REPOSITORY = MODEL_CACHE / "hub" / "models--ResembleAI--chatterbox"
REQUIRED_MODEL_FILES = {
    "ve.safetensors",
    "t3_cfg.safetensors",
    "s3gen.safetensors",
    "tokenizer.json",
    "conds.pt",
}


@dataclass(frozen=True)
class GenerationResult:
    path: Path
    samples: np.ndarray
    sample_rate: int


class VoiceEngine:
    def __init__(self) -> None:
        self._model = None
        self._torch = None
        self._load_lock = threading.Lock()
        self.device: str | None = None

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def load(self) -> str:
        if self._model is not None:
            return self.device or "unknown"

        with self._load_lock:
            if self._model is not None:
                return self.device or "unknown"

            # Model files stay next to the project and are never committed.
            MODEL_CACHE.mkdir(parents=True, exist_ok=True)
            os.environ["HF_HOME"] = str(MODEL_CACHE)

            import torch
            from chatterbox.tts import ChatterboxTTS

            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            self._torch = torch
            local_snapshot = self._find_local_snapshot()
            if local_snapshot is not None:
                self._model = ChatterboxTTS.from_local(local_snapshot, device=self.device)
            else:
                self._model = ChatterboxTTS.from_pretrained(device=self.device)
        return self.device

    @staticmethod
    def _find_local_snapshot() -> Path | None:
        snapshots = MODEL_REPOSITORY / "snapshots"
        if not snapshots.exists():
            return None

        candidates = sorted(
            (path for path in snapshots.iterdir() if path.is_dir()),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for candidate in candidates:
            present = {path.name for path in candidate.iterdir() if path.is_file()}
            if REQUIRED_MODEL_FILES.issubset(present):
                return candidate
        return None

    def generate_mp3(
        self,
        text: str,
        reference_audio: Path,
        destination: Path,
        exaggeration: float = 0.5,
        cfg_weight: float = 0.5,
        temperature: float = 0.8,
    ) -> GenerationResult:
        text = " ".join(text.split())
        if not text:
            raise ValueError("Enter some text to generate.")
        if len(text) > 1_000:
            raise ValueError("Keep the first version below 1,000 characters per generation.")
        if not reference_audio.exists():
            raise FileNotFoundError("Record or import a reference voice first.")
        if not 0.25 <= exaggeration <= 1.5:
            raise ValueError("Expressiveness must be between 0.25 and 1.50.")
        if not 0.0 <= cfg_weight <= 1.0:
            raise ValueError("Guidance must be between 0.00 and 1.00.")
        if not 0.1 <= temperature <= 1.5:
            raise ValueError("Temperature must be between 0.10 and 1.50.")

        self.load()
        assert self._model is not None
        assert self._torch is not None

        with self._torch.inference_mode():
            waveform = self._model.generate(
                text,
                audio_prompt_path=str(reference_audio),
                exaggeration=exaggeration,
                cfg_weight=cfg_weight,
                temperature=temperature,
            )

        samples = waveform.squeeze().detach().float().cpu().numpy()
        sample_rate = int(self._model.sr)
        destination.parent.mkdir(parents=True, exist_ok=True)
        self._write_mp3(samples, sample_rate, destination)
        return GenerationResult(destination, samples, sample_rate)

    @staticmethod
    def _write_mp3(samples: np.ndarray, sample_rate: int, destination: Path) -> None:
        samples = np.nan_to_num(samples)
        samples = np.clip(samples, -1.0, 1.0)
        pcm = (samples * 32_767).astype("<i2").tobytes()

        encoder = lameenc.Encoder()
        encoder.set_bit_rate(192)
        encoder.set_in_sample_rate(sample_rate)
        encoder.set_channels(1)
        encoder.set_quality(2)
        encoded = encoder.encode(pcm) + encoder.flush()
        destination.write_bytes(encoded)
