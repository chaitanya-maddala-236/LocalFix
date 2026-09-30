# LocalFix benchmark protocol

## What the API measures

Reports → Runtime runs ten serial repetitions for each requested stage and returns raw samples, mean, median, p95, min, max, load time, warmup time, model, provider, benchmark kind, and whether the result is eligible for latency claims.

| Stage | Workload | Current availability |
| --- | --- | --- |
| OCR | Real local RapidOCR on selected image, or deterministic generated ACM-4200 label | CPU ready on AMD64 profile; generated label is for latency only, not accuracy |
| Retrieval | SQLite FTS5, plus BGE embedding similarity and RRF when the local encoder is ready | CPU ready on AMD64 profile |
| Speech | Ten transcriptions of the selected local audio sample | Requires speech weights and a selected audio file |
| Vision | Ten YOLOv8 detections on selected local image | Requires a task-ready detector model |
| Reasoning | Ten local VLM image-plus-manual generations | Requires the loopback VLM and a selected local image; reports measured response and first-token latency; token/s and model-load time appear only when the runtime supplies those measurements |

Benchmark image/audio files are passed as base64 to the loopback API only and discarded after the request. The API never writes them to its data directory or logs. Do not choose sensitive audio/images on a shared device.

## Run a repeatable local benchmark

1. Switch from Demo Mode to Local Runtime.
2. Open Reports → Runtime.
3. Optionally select a representative, non-sensitive image and/or audio recording using the local fixture controls.
4. Click Run benchmark. OCR will use a deterministic synthetic label when no image is selected; vision and VLM are reported unavailable until an image is selected; speech needs a local audio file.
5. Save the returned JSON and record host power profile, network state, ambient conditions, model file hashes, and application revision alongside it.
6. Repeat after a process restart to capture cold model-load telemetry; the benchmark request itself records startup model load time separately from a task warmup and the ten task samples.

Measurements are serial; all available stages run task-specific local model operations. VLM first-token time is measured from request start to the first nonempty content token; response latency covers the complete generation. Token throughput and model-load time are reported only when supplied by the active runtime. The synthetic OCR fixture makes no recognition-quality claim. The benchmark does not calculate ASR word error rate or detector accuracy; those require labeled speech and image sets. The response reports zero external network requests for the local inference task path; explicit setup-time model downloads are outside this benchmark.

## Cold and warm timings

Model load time is captured by each local adapter during startup or reload. The benchmark performs one warmup task on the same fixture, then ten measured tasks. The VLM's reported cold-load duration comes from the inference runtime; if the model was already resident, this can be zero. CPU-stage samples include the model task operation; image-to-base64 encoding and browser capture are not included. Vision samples include decode/preprocess/model/decode inside the adapter. Retrieval samples include the backend hybrid query and SQLite/vector scan. Report cold load and warm task data separately.

## Interpreting result eligibility

Only task-backed outputs are marked performance-claim eligible. Generic ONNX zero-tensor smoke benchmarks remain ineligible. OCR synthetic-fixture numbers are only label-fixture latency, and they do not show accuracy on a real panel. Retrieval measurements are database/model-search latency, not diagnosis quality. Missing stages are returned as unavailable with no fabricated timing.

## Snapdragon comparison still required

This development host is Windows AMD64 and reports NPU unavailable. It cannot produce a Snapdragon measurement. On the HP laptop, use identical model, quantization, input fixture, precision, and software revision for GenieX/QAIRT NPU and CPU fallback if that model supports both. If it does not, label results as different-model runs instead of a same-model comparison. Run at least ten warm samples after separately recording cold load and warmup. Record GenieX compute selection, QNN operator placement where available, RAM/UMA, power mode, and thermal state. GenieX's HTTP API does not provide accelerator-placement telemetry to LocalFix, so retain the runtime diagnostics separately and do not claim NPU superiority from model availability or API success alone.

This Windows AMD64 host can measure OCR, speech, hybrid retrieval, and local Qwen3-VL CPU fallback after the model is installed. Vision detection still needs trained component weights. QNN and a same-model NPU/CPU comparison remain target-device work; Ollama measurements do not count as QNN or NPU measurements.
