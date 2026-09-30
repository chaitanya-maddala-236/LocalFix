"""Run Qualcomm's end-to-end OWL-ViT recipe on a hosted Snapdragon X Elite.

Uses the fictional ACM-4200 vector illustration only. The AI Hub API token is
read with hidden input and injected into the client in memory; it is not saved
to a config file or written to the run record.
"""

from __future__ import annotations

import getpass
import json
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

import qai_hub as hub
import qai_hub.hub as hub_api
from qai_hub.client import Client


ROOT = Path(__file__).resolve().parents[1]
IMAGE = ROOT / "benchmark" / "qualcomm-aihub" / "acm4200-demo.png"
OUTPUT = ROOT / "benchmark" / "qualcomm-aihub" / "owl-vit-demo-output"
RUN_RECORD = ROOT / "benchmark" / "qualcomm-aihub" / "owl-vit-aihub-demo-run.json"


def main() -> int:
    if not IMAGE.is_file():
        print(f"Synthetic demo image not found: {IMAGE}")
        return 2

    token = getpass.getpass("Qualcomm AI Hub API token (hidden; memory only): ").strip()
    if not token:
        print("No token entered; no job was submitted.")
        return 2

    original_init = Client.__init__
    global_client = hub_api._global_client
    original_global_config = global_client._config
    start = time.perf_counter()
    start_epoch = time.time()
    started_at = datetime.now(timezone.utc).isoformat()
    submitted_jobs: list[dict[str, str]] = []
    patched_api_methods: list[tuple[object, str, object]] = []

    def track_job_api(module, name: str) -> None:
        original = getattr(module, name)

        def tracked(*args, **kwargs):
            result = original(*args, **kwargs)
            jobs = result if isinstance(result, list) else [result]
            for job in jobs:
                job_id = getattr(job, "job_id", None)
                if job_id:
                    submitted_jobs.append(
                        {"operation": name, "job_id": str(job_id), "url": str(getattr(job, "url", ""))}
                    )
            return result

        setattr(module, name, tracked)
        patched_api_methods.append((module, name, original))

    # qai-hub-models recipes use both explicit Client instances and the
    # module-level convenience functions. Those functions are bound to the
    # SDK's already-created global client, so initialize it directly in memory.
    global_client._config = hub.ClientConfig(api_token=token, verbose=False)
    for api_name in ("submit_compile_job", "submit_inference_job"):
        track_job_api(hub_api, api_name)
        track_job_api(hub, api_name)

    def init_with_ephemeral_token(self, *args, **kwargs):
        if not args and "config" not in kwargs:
            kwargs["config"] = hub.ClientConfig(api_token=token, verbose=False)
        return original_init(self, *args, **kwargs)

    Client.__init__ = init_with_ephemeral_token
    original_argv = sys.argv
    try:
        sys.argv = [
            "qai-hub-models",
            "demo",
            "owl_vit",
            "--eval-mode",
            "on-device",
            "--device",
            "Snapdragon X Elite CRD",
            "--runtime",
            "onnx",
            "--precision",
            "w8a16",
            "--inference-options=--compute_unit npu",
            "--image-path",
            str(IMAGE),
            "--text-queries",
            "a photo of a motor relay",
            "--output-dir",
            str(OUTPUT),
        ]
        from qai_hub_models_cli.cli import main as qai_hub_models_main

        try:
            qai_hub_models_main()
        except SystemExit as error:
            exit_code = int(error.code or 0)
            if exit_code:
                raise RuntimeError(f"Qualcomm model CLI exited with status {exit_code}.") from error
        output_files = sorted(
            path
            for path in OUTPUT.rglob("*")
            if path.is_file() and path.stat().st_mtime >= start_epoch
        ) if OUTPUT.exists() else []
        if not output_files:
            raise RuntimeError("Qualcomm demo completed without producing a detection overlay.")
        RUN_RECORD.write_text(
            json.dumps(
                {
                    "started_at_utc": started_at,
                    "completed_at_utc": datetime.now(timezone.utc).isoformat(),
                    "validation_kind": "ai_hub_hosted_on_device_model_demo",
                    "status": "completed",
                    "model": "OWL-ViT",
                    "precision": "w8a16",
                    "runtime": "ONNX Runtime",
                    "target_device": "Snapdragon X Elite CRD",
                    "requested_compute_unit": "NPU",
                    "input_fixture": "Synthetic fictional DemoTech ACM-4200 illustration",
                    "text_query": "a photo of a motor relay",
                    "wall_time_seconds": round(time.perf_counter() - start, 3),
                    "wall_time_note": "Includes model compile, job submission, remote execution, and result download; not inference latency.",
                    "jobs": submitted_jobs,
                    "output_files": [str(path.relative_to(ROOT)) for path in output_files],
                    "localfix_accuracy_validated": False,
                    "exact_hp_device_validated": False,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"Sanitized run record saved: {RUN_RECORD}")
        return 0
    except Exception as error:
        trace = "".join(traceback.format_exception(error)).replace(token, "[redacted]")
        print(f"AI Hub OWL-ViT demo failed ({type(error).__name__}):\n{trace}")
        RUN_RECORD.write_text(
            json.dumps(
                {
                    "started_at_utc": started_at,
                    "completed_at_utc": datetime.now(timezone.utc).isoformat(),
                    "validation_kind": "ai_hub_hosted_on_device_model_demo",
                    "status": "failed",
                    "model": "OWL-ViT",
                    "target_device": "Snapdragon X Elite CRD",
                    "input_fixture": "Synthetic fictional DemoTech ACM-4200 illustration",
                    "jobs": submitted_jobs,
                    "error_type": type(error).__name__,
                    "error": str(error).replace(token, "[redacted]"),
                    "localfix_accuracy_validated": False,
                    "exact_hp_device_validated": False,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return 1
    finally:
        Client.__init__ = original_init
        global_client._config = original_global_config
        for module, name, original in reversed(patched_api_methods):
            setattr(module, name, original)
        sys.argv = original_argv
        token = ""


if __name__ == "__main__":
    raise SystemExit(main())
