# Benchmark protocol

## What is measured

- SQLite FTS5 retrieval latency on the local ACM-4200 manual.
- Model adapter session cold-load time and one warm-up observation.
- Ten or more repeat inference timings for an installed ONNX model's synthetic zero-tensor smoke input.
- API process resident memory, current OS network-interface state, and provider list where available.
- A future task benchmark may add vision, OCR, ASR, VLM first-token and token-throughput only when proper local fixtures, preprocessors, decoders, and actual model assets are present.

## How to run

Open Reports & Runtime → AI Runtime → **Run benchmark**, or call `POST /benchmark/run` with `{"repeats":10,"stages":["vision","ocr","speech","retrieval","reasoning"]}`. The API accepts 10–100 repeats and returns raw samples, mean, median, p95, min, max, provider, model, benchmark kind, cold-start and warm-up values, RAM, and external request count.

Retrieval samples execute local SQLite queries. ONNX smoke measurements execute real model sessions using model-shaped zero tensors, so they are useful for adapter health only. They are marked `performance_claim_eligible: false`; they do not represent natural image/audio/text inference, user-perceived latency, accuracy, or Snapdragon superiority. Missing models return unavailable entries, not zeros.

## Fair NPU versus CPU comparison

Use the same model hash, precision, graph, fixtures, repeat count, power mode, and warm-up policy on the same device. Verify active provider from the ONNX session, not from manifest preference. Run NPU and CPU separately; preserve each raw result. Report thermal/power mode and memory alongside latency. The comparison table remains “not measured” until both paths have comparable task inputs. Cloud is not implemented and must not be presented as a measured baseline.

## Current limitations

No candidate model weights are bundled. No full task-level image, OCR, speech, VLM, or end-to-end measurements exist at this stage. No NPU metric is emitted unless the runtime provider exposes one. Demo mode never injects benchmark data. The API reports zero external network requests because it contains no cloud inference path; localhost API traffic remains local loopback traffic.
