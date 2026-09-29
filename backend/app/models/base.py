from __future__ import annotations

import asyncio
import importlib.util
import json
import statistics
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class ModelUnavailableError(RuntimeError):
    """Raised when a requested on-device model is not installed or loadable."""


class ModelInputError(ValueError):
    """Raised when an adapter does not receive its model-specific input tensors."""


class ModelAdapter(ABC):
    stage: str
    state: str
    backend: str | None
    model_name: str | None
    precision: str | None

    @abstractmethod
    async def load(self) -> dict[str, Any]: ...

    @abstractmethod
    async def warmup(self) -> dict[str, Any]: ...

    @abstractmethod
    async def infer(self, inputs: dict[str, Any]) -> dict[str, Any]: ...

    @abstractmethod
    async def benchmark(self, repeats: int = 10) -> dict[str, Any]: ...

    @abstractmethod
    async def health(self) -> dict[str, Any]: ...


class OnnxRuntimeAdapter(ModelAdapter):
    """Generic ONNX adapter; task preprocessing/postprocessing remains model-specific."""

    def __init__(self, stage: str, config: dict[str, Any], models_dir: Path, providers_available: list[str]):
        self.stage = stage
        self.config = config
        self.models_dir = models_dir.resolve()
        self.providers_available = providers_available
        self.path = self._resolve_path(config.get("path"))
        self.model_name = self.path.name if self.path else None
        self.precision = config.get("precision")
        self.backend: str | None = None
        self.state = "NOT_INSTALLED" if self.path is None or not self.path.exists() else "LOADING"
        self.error: str | None = None
        self.session: Any = None
        self.started_at_ms: float | None = None
        self.last_latency_ms: float | None = None
        self.lock = asyncio.Lock()

    def _resolve_path(self, raw_path: str | None) -> Path | None:
        if not raw_path:
            return None
        candidate = (self.models_dir / raw_path).resolve()
        if self.models_dir not in candidate.parents and candidate != self.models_dir:
            raise ValueError(f"Model path for {self.stage} must remain inside {self.models_dir}")
        return candidate

    async def load(self) -> dict[str, Any]:
        async with self.lock:
            if not self.path or not self.path.is_file():
                self.state = "NOT_INSTALLED"
                self.session = None
                self.backend = None
                return await self.health()
            if importlib.util.find_spec("onnxruntime") is None:
                self.state = "ERROR"
                self.error = "ONNX Runtime is not installed in this environment."
                return await self.health()
            try:
                started = time.perf_counter()
                result = await asyncio.to_thread(self._create_session)
                self.session, providers = result
                self.started_at_ms = (time.perf_counter() - started) * 1000
                self.backend = "QNNExecutionProvider" if "QNNExecutionProvider" in providers else (providers[0] if providers else None)
                self.state = "READY"
                self.error = None
            except Exception as error:  # provider and model errors are surfaced in health, not hidden
                self.session = None
                self.state = "ERROR"
                self.error = f"{type(error).__name__}: {error}"
            return await self.health()

    def _create_session(self) -> tuple[Any, list[str]]:
        import onnxruntime as ort

        requested = self.config.get("providers") or []
        available = set(ort.get_available_providers())
        selected = [name for name in requested if name in available]
        if not selected:
            if "CPUExecutionProvider" not in available:
                raise RuntimeError("No configured inference provider is available")
            selected = ["CPUExecutionProvider"]
        elif "CPUExecutionProvider" in available and "CPUExecutionProvider" not in selected:
            selected.append("CPUExecutionProvider")
        session_options = ort.SessionOptions()
        session_options.enable_mem_pattern = True
        session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        provider_options = [
            {"backend_type": "htp"} if name == "QNNExecutionProvider" else {}
            for name in selected
        ]
        session = ort.InferenceSession(
            str(self.path), sess_options=session_options, providers=selected,
            provider_options=provider_options,
        )
        return session, session.get_providers()

    async def warmup(self) -> dict[str, Any]:
        if self.state != "READY" or self.session is None:
            return await self.health()
        try:
            feed = await asyncio.to_thread(self._dummy_inputs)
            started = time.perf_counter()
            await asyncio.to_thread(self.session.run, None, feed)
            self.last_latency_ms = (time.perf_counter() - started) * 1000
        except Exception as error:
            self.error = f"Warmup failed: {type(error).__name__}: {error}"
            self.state = "ERROR"
        return await self.health()

    def _dummy_inputs(self) -> dict[str, Any]:
        import numpy as np

        if self.session is None:
            raise ModelUnavailableError(f"{self.stage} is not loaded")
        feed: dict[str, Any] = {}
        for item in self.session.get_inputs():
            shape = [dimension if isinstance(dimension, int) and dimension > 0 else 1 for dimension in item.shape]
            if item.type == "tensor(string)":
                feed[item.name] = np.full(shape, "", dtype=object)
            elif item.type == "tensor(int64)":
                feed[item.name] = np.zeros(shape, dtype=np.int64)
            elif item.type == "tensor(int32)":
                feed[item.name] = np.zeros(shape, dtype=np.int32)
            else:
                feed[item.name] = np.zeros(shape, dtype=np.float32)
        return feed

    async def infer(self, inputs: dict[str, Any]) -> dict[str, Any]:
        if self.state != "READY" or self.session is None:
            raise ModelUnavailableError(f"{self.stage} model is {self.state.lower()}")
        if not inputs:
            raise ModelInputError(f"{self.stage} ONNX adapter requires model-specific preprocessed tensors")
        started = time.perf_counter()
        outputs = await asyncio.to_thread(self.session.run, None, inputs)
        self.last_latency_ms = (time.perf_counter() - started) * 1000
        output_names = [item.name for item in self.session.get_outputs()]
        return {name: value for name, value in zip(output_names, outputs)}

    async def benchmark(self, repeats: int = 10) -> dict[str, Any]:
        if self.state != "READY" or self.session is None:
            raise ModelUnavailableError(f"{self.stage} model is {self.state.lower()}")
        feed = await asyncio.to_thread(self._dummy_inputs)
        samples: list[float] = []
        for _ in range(repeats):
            started = time.perf_counter()
            await asyncio.to_thread(self.session.run, None, feed)
            samples.append((time.perf_counter() - started) * 1000)
        ordered = sorted(samples)
        p95_index = max(0, min(len(ordered) - 1, int(0.95 * len(ordered) + 0.5) - 1))
        return {
            "samples_ms": samples,
            "statistics_ms": {
                "mean": statistics.fmean(samples), "median": statistics.median(samples),
                "p95": ordered[p95_index], "min": min(samples), "max": max(samples),
            },
            "benchmark_kind": "synthetic_zero_tensor_smoke",
            "performance_claim_eligible": False,
        }

    async def health(self) -> dict[str, Any]:
        active = self.session.get_providers() if self.session is not None else []
        return {
            "stage": self.stage, "state": self.state, "model": self.model_name,
            "path_configured": bool(self.path), "file_present": bool(self.path and self.path.is_file()),
            "backend": self.backend, "active_providers": active,
            "available_providers": self.providers_available, "precision": self.precision,
            "load_ms": self.started_at_ms, "last_latency_ms": self.last_latency_ms, "error": self.error,
        }


class VisionModel(OnnxRuntimeAdapter):
    pass


class OCRModel(OnnxRuntimeAdapter):
    pass


class SpeechModel(OnnxRuntimeAdapter):
    pass


class EmbeddingModel(OnnxRuntimeAdapter):
    pass


class VLMModel(OnnxRuntimeAdapter):
    pass


class CapabilityAdapter(ModelAdapter):
    """Honest placeholder for a local SDK path whose vendor bridge is not bundled."""

    def __init__(self, stage: str, config: dict[str, Any], models_dir: Path, runtime_name: str):
        self.stage = stage
        self.runtime_name = runtime_name
        self.config = config
        self.path = (models_dir / config["path"]).resolve() if config.get("path") else None
        if self.path and models_dir.resolve() not in self.path.parents:
            raise ValueError(f"Model path for {stage} must remain inside {models_dir.resolve()}")
        self.model_name = self.path.name if self.path else None
        self.precision = config.get("precision")
        self.backend = None
        self.state = "NOT_INSTALLED" if not self.path or not self.path.exists() else "UNAVAILABLE"
        self.error = f"The {runtime_name} asset is present, but its SDK binding and task adapter are not configured."

    async def load(self) -> dict[str, Any]:
        if not self.path or not self.path.exists():
            self.state = "NOT_INSTALLED"
        else:
            self.state = "UNAVAILABLE"
        return await self.health()

    async def warmup(self) -> dict[str, Any]:
        return await self.health()

    async def infer(self, inputs: dict[str, Any]) -> dict[str, Any]:
        raise ModelUnavailableError(self.error)

    async def benchmark(self, repeats: int = 10) -> dict[str, Any]:
        raise ModelUnavailableError(self.error)

    async def health(self) -> dict[str, Any]:
        return {"stage": self.stage, "state": self.state, "model": self.model_name,
                "backend": self.runtime_name, "active_providers": [], "available_providers": [],
                "precision": self.precision, "error": self.error}


ADAPTER_TYPES: dict[str, type[OnnxRuntimeAdapter]] = {
    "vision": VisionModel, "ocr": OCRModel, "speech": SpeechModel,
    "embedding": EmbeddingModel, "reasoning": VLMModel,
}


def build_adapter(stage: str, config: dict[str, Any], models_dir: Path,
                  providers_available: list[str]) -> ModelAdapter:
    runtime_name = str(config.get("adapter", "onnx")).casefold()
    if runtime_name in {"qairt", "geniex", "qualcomm_ai_hub"}:
        return CapabilityAdapter(stage, config, models_dir, runtime_name)
    adapter_type = ADAPTER_TYPES.get(stage, OnnxRuntimeAdapter)
    return adapter_type(stage, config, models_dir, providers_available)


class ModelRegistry:
    def __init__(self, project_root: Path):
        self.project_root = project_root.resolve()
        self.models_dir = self.project_root / "models"
        self.manifest_path = Path(os_env("LOCALFIX_MODEL_MANIFEST", self.models_dir / "manifest.json")).resolve()
        self.config: dict[str, Any] = {}
        self.available_providers: list[str] = []
        self.adapters: dict[str, OnnxRuntimeAdapter] = {}
        self.last_measurements: dict[str, float | None] = {"vision": None, "ocr": None, "speech": None, "retrieval": None, "reasoning": None}
        self.reload_manifest()

    def reload_manifest(self) -> None:
        if self.manifest_path.exists():
            try:
                self.config = json.loads(self.manifest_path.read_text(encoding="utf-8")).get("models", {})
            except (OSError, json.JSONDecodeError):
                self.config = {}
        else:
            self.config = {}
        try:
            if importlib.util.find_spec("onnxruntime"):
                import onnxruntime as ort
                self.available_providers = list(ort.get_available_providers())
            else:
                self.available_providers = []
        except Exception:
            self.available_providers = []
        self.adapters = {
            stage: build_adapter(stage, config, self.models_dir, self.available_providers)
            for stage, config in self.config.items() if stage in ADAPTER_TYPES
        }

    async def load_all(self) -> None:
        for adapter in self.adapters.values():
            await adapter.load()
            await adapter.warmup()

    async def reload(self) -> None:
        self.reload_manifest()
        await self.load_all()

    def model_state(self, stage: str) -> str:
        adapter = self.adapters.get(stage)
        if adapter is None:
            return "unavailable"
        if adapter.state == "READY":
            return "ready"
        if adapter.state == "NOT_INSTALLED":
            return "missing"
        return "unavailable"

    async def runtime_payload(self, demo: bool = False) -> dict[str, Any]:
        details: dict[str, dict[str, Any]] = {}
        for stage, adapter in self.adapters.items():
            details[stage] = await adapter.health()
        qnn_active = any("QNNExecutionProvider" in info["active_providers"] and info["state"] == "READY" for info in details.values())
        cpu_active = any("CPUExecutionProvider" in info["active_providers"] and info["state"] == "READY" for info in details.values())
        backend = "QNN Execution Provider" if qnn_active else ("ONNX Runtime · CPU fallback" if cpu_active else "Unavailable · no model loaded")
        states = {stage: self.model_state(stage) for stage in ["vision", "ocr", "speech", "reasoning"]}
        precision = {stage: adapter.precision for stage, adapter in self.adapters.items()}
        return {
            "mode": "demo" if demo else "local", "simulated": demo, "backend": backend,
            "npu": "active" if qnn_active else "unavailable", "network": network_state(),
            "network_detail": "OS interface status; no connectivity probe or external request was made.",
            "models": states, "model_details": details, "latencyMs": self.last_measurements,
            "ramMb": process_ram_mb(), "precision": precision,
        }

    def record_latency(self, stage: str, elapsed_ms: float) -> None:
        self.last_measurements[stage] = round(elapsed_ms, 3)


def os_env(key: str, default: Any) -> str:
    import os
    return os.getenv(key, str(default))


def process_ram_mb() -> float | None:
    try:
        import psutil
        import os
        return round(psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024), 1)
    except Exception:
        return None


def network_state() -> str:
    try:
        import psutil
        interfaces = psutil.net_if_stats()
        physical = [stats.isup for name, stats in interfaces.items() if name.lower() not in {"lo", "loopback"}]
        if not physical:
            return "unknown"
        return "online" if any(physical) else "offline"
    except Exception:
        return "unknown"
