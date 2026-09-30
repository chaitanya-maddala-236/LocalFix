from __future__ import annotations

import importlib.util
import io
import threading
import time
from pathlib import Path
from typing import Any

from ..models.base import ModelUnavailableError
from ..schemas import OCRValue
from .vision import classify_ocr_text, normalize_ocr_text


class LocalOCREngine:
    """Offline OCR wrapper. RapidOCR's compact ONNX files ship with its wheel."""

    def __init__(self) -> None:
        self.engine: Any = None
        self.state = "NOT_INSTALLED"
        self.error: str | None = None
        self.load_ms: float | None = None
        self.last_latency_ms: float | None = None
        self._lock = threading.RLock()

    def load(self) -> dict[str, Any]:
        if self.state == "READY" and self.engine is not None:
            return self.health()
        if importlib.util.find_spec("rapidocr") is None:
            self.state = "NOT_INSTALLED"
            return self.health()
        try:
            from rapidocr import RapidOCR

            started = time.perf_counter()
            with self._lock:
                self.engine = RapidOCR()
            self.load_ms = round((time.perf_counter() - started) * 1000, 3)
            self.state = "READY"
            self.error = None
        except Exception as error:
            self.engine = None
            self.state = "ERROR"
            self.error = f"{type(error).__name__}: {error}"
        return self.health()

    def infer(self, image_bytes: bytes) -> tuple[list[OCRValue], float]:
        if self.state != "READY" or self.engine is None:
            raise ModelUnavailableError("Local OCR is not installed or could not be loaded. No text was fabricated.")
        import numpy as np
        from PIL import Image

        with Image.open(io.BytesIO(image_bytes)) as source:
            image = source.convert("RGB")
            width, height = image.size
            if width > 4096 or height > 4096 or width * height > 12_000_000:
                raise ValueError("Image dimensions exceed the local OCR limit of 4096 px or 12 megapixels.")
            # RapidOCR's OpenCV preprocessing expects BGR channel ordering.
            pixels = np.asarray(image)[:, :, ::-1].copy()

        started = time.perf_counter()
        with self._lock:
            result = self.engine(pixels)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        self.last_latency_ms = elapsed_ms
        if result is None or getattr(result, "txts", None) is None:
            return [], elapsed_ms

        values: list[OCRValue] = []
        seen: set[tuple[str, str]] = set()
        boxes = getattr(result, "boxes", None)
        scores = getattr(result, "scores", None)
        for index, raw_text in enumerate(result.txts):
            if not raw_text:
                continue
            box = None
            if boxes is not None and index < len(boxes):
                corners = np.asarray(boxes[index], dtype=np.float32)
                if corners.ndim == 2 and corners.shape[1] == 2:
                    x0 = max(0.0, min(1.0, float(corners[:, 0].min()) / width))
                    y0 = max(0.0, min(1.0, float(corners[:, 1].min()) / height))
                    x1 = max(x0, min(1.0, float(corners[:, 0].max()) / width))
                    y1 = max(y0, min(1.0, float(corners[:, 1].max()) / height))
                    box = (x0, y0, x1, y1)
            confidence = float(scores[index]) if scores is not None and index < len(scores) else None
            classified = classify_ocr_text(str(raw_text))
            for item in classified:
                key = (item["normalized"], item["kind"])
                if key in seen:
                    continue
                seen.add(key)
                values.append(OCRValue(
                    text=item["text"], normalized=item["normalized"], kind=item["kind"],
                    box=box, confidence=confidence,
                ))
        return values, elapsed_ms

    def health(self) -> dict[str, Any]:
        return {
            "stage": "ocr", "state": self.state, "model": "RapidOCR PP-OCRv6 small" if self.state == "READY" else None,
            "backend": "ONNX Runtime · CPU" if self.state == "READY" else None,
            "active_providers": ["CPUExecutionProvider"] if self.state == "READY" else [],
            "available_providers": [], "precision": "FP32", "load_ms": self.load_ms,
            "last_latency_ms": self.last_latency_ms, "error": self.error,
        }


def normalize_text_lines(values: list[OCRValue]) -> list[str]:
    return list(dict.fromkeys(normalize_ocr_text(value.text) for value in values if value.text.strip()))
