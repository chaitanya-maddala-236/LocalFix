from __future__ import annotations

import importlib.util
import io
import os
import threading
import time
from pathlib import Path
from typing import Any

from ..models.base import ModelUnavailableError


class LocalSpeechEngine:
    """faster-whisper CPU adapter. Model loading and decoding are strictly local."""

    def __init__(self, project_root: Path, configured_path: str | None = None) -> None:
        configured = os.getenv("LOCALFIX_SPEECH_MODEL") or configured_path
        if configured:
            candidate = Path(configured)
            self.model_path = candidate.resolve() if candidate.is_absolute() else (project_root / "models" / candidate).resolve()
        else:
            self.model_path = project_root / "models" / "speech" / "tiny.en"
        self.model: Any = None
        self.state = "NOT_INSTALLED"
        self.error: str | None = None
        self.load_ms: float | None = None
        self.last_latency_ms: float | None = None
        self._project_root = project_root.resolve()
        self._lock = threading.RLock()

    def load(self) -> dict[str, Any]:
        if self.state == "READY" and self.model is not None:
            return self.health()
        if importlib.util.find_spec("faster_whisper") is None:
            self.state = "NOT_INSTALLED"
            return self.health()
        if not self.model_path.is_dir() or not (self.model_path / "model.bin").is_file():
            self.state = "MODEL_REQUIRED"
            return self.health()
        try:
            from faster_whisper import WhisperModel

            started = time.perf_counter()
            self.model = WhisperModel(
                str(self.model_path), device="cpu", compute_type=os.getenv("LOCALFIX_ASR_COMPUTE_TYPE", "int8"),
                cpu_threads=max(1, min(8, (os.cpu_count() or 4) // 2)), local_files_only=True,
            )
            self.load_ms = round((time.perf_counter() - started) * 1000, 3)
            self.state = "READY"
            self.error = None
        except Exception as error:
            self.model = None
            self.state = "ERROR"
            self.error = f"{type(error).__name__}: {error}"
        return self.health()

    def transcribe(self, audio_bytes: bytes, content_type: str) -> tuple[str, str | None, float]:
        if self.state != "READY" or self.model is None:
            raise ModelUnavailableError("A local speech model is not installed. Audio was not sent to a remote service.")
        started = time.perf_counter()
        with self._lock:
            segments, info = self.model.transcribe(
                io.BytesIO(audio_bytes), beam_size=1, vad_filter=True,
                condition_on_previous_text=False,
            )
            transcript = " ".join(segment.text.strip() for segment in segments).strip()
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        self.last_latency_ms = elapsed_ms
        return transcript, getattr(info, "language", None), elapsed_ms

    def health(self) -> dict[str, Any]:
        return {
            "stage": "speech", "state": self.state,
            "model": self.model_path.name if self.state == "READY" else None,
            "path_configured": True, "file_present": (self.model_path / "model.bin").is_file(),
            "backend": "CTranslate2 · CPU" if self.state == "READY" else None,
            "active_providers": ["CPU"] if self.state == "READY" else [],
            "available_providers": [], "precision": "int8 CPU" if self.state == "READY" else None,
            "load_ms": self.load_ms, "last_latency_ms": self.last_latency_ms,
            "error": self.error,
        }
