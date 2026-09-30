"""Profile the same OWL-ViT ONNX asset on hosted Snapdragon NPU and CPU.

The API token is requested with hidden input and is never written to disk.
The same synthetic tensors are used for both runs; outputs are a runtime smoke
check, not an equipment detection accuracy evaluation.
"""

from __future__ import annotations

import argparse
import getpass
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import qai_hub as hub
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = (
    ROOT
    / "models"
    / "qualcomm"
    / "owl-vit"
    / "owl_vit-onnx-w8a16"
    / "owl_vit.onnx"
)
DEFAULT_OUTPUT = ROOT / "benchmark" / "qualcomm-aihub" / "owl-vit-xelite-profile.json"


def _status_text(status: Any) -> str:
    value = getattr(status, "value", None)
    return str(value if value is not None else status)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--device", default="Snapdragon X Elite CRD")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--timeout", type=int, default=3600)
    args = parser.parse_args()

    if not args.model.is_file():
        parser.error(f"Model asset not found: {args.model}")

    token = getpass.getpass(
        "Enter a Qualcomm AI Hub API token (hidden; used only for this run): "
    ).strip()
    if not token:
        print("No token entered; no job was submitted.")
        return 2

    record: dict[str, Any] = {
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "validation_kind": "ai_hub_npu_vs_cpu_profile_synthetic_inputs",
        "model": "OWL-ViT",
        "precision": "w8a16",
        "model_path": str(args.model),
        "target_device": args.device,
        "host_note": "Qualcomm-hosted reference device; not an HP laptop measurement.",
        "accuracy_note": "Synthetic fixed-shape inputs; no detection-quality claim.",
        "runs": [],
    }

    try:
        client = hub.Client(hub.ClientConfig(api_token=token, verbose=False))
        matches = client.get_devices(name=args.device)
        if not matches:
            raise RuntimeError(f"AI Hub did not return target device {args.device!r}.")

        # Match the model asset's declared [1,3,768,768], [1,16], [1,16] inputs.
        # Pixel values are centered on the asset's quantization zero point.
        inputs = {
            "pixel_values": [np.full((1, 3, 768, 768), 29825, dtype=np.uint16)],
            "input_ids": [np.zeros((1, 16), dtype=np.int32)],
            "attention_mask": [np.ones((1, 16), dtype=np.int32)],
        }
        device = hub.Device(args.device)
        all_succeeded = True
        for unit in ("npu", "cpu"):
            run: dict[str, Any] = {"compute_unit": unit}
            try:
                job = client.submit_inference_job(
                    model=str(args.model),
                    device=device,
                    inputs=inputs,
                    profile=True,
                    options=f"--compute_unit {unit}",
                    name=f"LocalFix OWL-ViT Snapdragon {unit.upper()} model smoke",
                )
                run["job_id"] = job.job_id
                run["job_url"] = str(job.url)
                print(f"Submitted {unit.upper()} job {job.job_id}: {job.url}")
                status = job.wait(timeout=args.timeout)
                run["status"] = _status_text(status)
                run["success"] = bool(getattr(status, "success", False))
                if not run["success"]:
                    all_succeeded = False
                try:
                    run["profile"] = job.download_profile()
                except Exception as error:  # Keep the job/status if profile export fails.
                    run["profile_download_error"] = type(error).__name__
                try:
                    output_data = job.download_output_data()
                    run["output_shapes"] = {
                        name: [list(np.asarray(tensor).shape) for tensor in tensors]
                        for name, tensors in output_data.items()
                    }
                except Exception as error:  # The profile can still be useful without outputs.
                    run["output_download_error"] = type(error).__name__
            except Exception as error:
                all_succeeded = False
                run["success"] = False
                run["error_type"] = type(error).__name__
                run["error"] = str(error).replace(token, "[redacted]")
            record["runs"].append(run)

        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(record, indent=2, ensure_ascii=False, default=str) + "\n",
            encoding="utf-8",
        )
        print(f"NPU and CPU jobs recorded; both succeeded: {all_succeeded}")
        print(f"Saved sanitized run record: {args.output}")
        return 0 if all_succeeded else 1
    except Exception as error:
        message = str(error).replace(token, "[redacted]")
        print(f"AI Hub validation failed ({type(error).__name__}): {message}")
        return 1
    finally:
        token = ""


if __name__ == "__main__":
    raise SystemExit(main())
