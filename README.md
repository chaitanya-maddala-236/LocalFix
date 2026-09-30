# LocalFix

**Your field engineer. Offline. On-device. Evidence-first.**

LocalFix is a focused field-service copilot for the fictional DemoTech ACM-4200 motor controller. It combines a live camera input path, local OCR and speech, local manual retrieval, source-checked summaries, safety acknowledgement, case history, and service reports.

## What works now

- Six coordinated screens and a clearly labeled simulated Demo Mode.
- Real webcam/image capture in Local Runtime. Frames stay in memory and go only to the loopback API.
- RapidOCR PP-OCRv6 on ONNX Runtime CPU, with normalized equipment/fault values, boxes, and OCR scores.
- Local microphone capture and English faster-whisper tiny.en transcription on CPU. No browser/cloud fallback.
- SQLite FTS5 plus BGE-small-en-v1.5 local embeddings, combined with reciprocal-rank fusion. Source page numbers and document hashes are preserved.
- Scanned-PDF OCR when the local OCR engine is installed.
- A configurable YOLOv8 ONNX detector adapter and decoder; trained ACM-4200 component weights are still required.
- Local Qwen3-VL multimodal inference through an Ollama server bound to loopback. Generated summaries must cite a retrieved source and pass evidence-overlap and action-language checks; procedures remain manual-gated.
- An optional GenieX OpenAI-compatible loopback adapter for Qualcomm AI Hub Qwen3-VL bundles on native Windows ARM64. The runtime path is prepared but has not been exercised on the HP target.
- Manual-grounded rule summaries and source-backed fixed procedure steps. Missing evidence blocks unsupported findings.
- Local cases, report exports, runtime health, upload limits, and structured logs that omit raw image/audio.

## What still needs target hardware or assets

This build host is an Intel Windows AMD64 Dell, not the HP Snapdragon laptop. The Qualcomm AI Hub token was used for a read-only authentication/device-profile lookup and was not saved. QNN/GenieX setup has not been run on Snapdragon. OCR, ASR, embeddings, and the configured Qwen3-VL 2B run locally without a validated NPU backend here.

No task-trained component detector weights or OWL-V2 open-vocabulary model are configured. “Show motor relay” can use the local VLM to return a conservative image-region estimate, clearly labeled as a model estimate without a calibrated score; dedicated detector results remain unavailable. A real QNN-vs-CPU comparison must be measured on the target device with the same task model and inputs.

## Screens

1. / — Operations Home
2. /diagnose — Live camera and technician input
3. /evidence — Manual viewer and source inspector
4. /procedure — Safety-gated cited steps
5. /cases — Local case history
6. /reports — Report and Runtime/Benchmark tabs

See [ARCHITECTURE.md](ARCHITECTURE.md) for diagrams, API, state machine, schema, wireframes, deployment, and benchmark design.

## Run on D:

Requirements: Node.js 20+ and Python 3.11+ on Windows.

~~~powershell
cd D:/LocalFix/backend
./run.ps1
~~~

This creates D:/LocalFix/.venv and starts FastAPI on 127.0.0.1:8000.

~~~powershell
cd D:/LocalFix/frontend
npm install
npm run dev
~~~

Open http://127.0.0.1:5173. Vite proxies API calls to the loopback backend.

## Optional local models for the AMD64 development host

The base setup does not download weights. To install optional local OCR, ASR, and semantic retrieval dependencies/assets:

~~~powershell
cd D:/LocalFix/backend
./setup-local-ai.ps1
~~~

The script installs pinned packages and explicitly downloads BGE-small-en-v1.5 and faster-whisper tiny.en to the ignored local models directory. RapidOCR PP-OCRv6 model files ship in its installed package. One-time model download needs internet; inference afterward uses local files. The setup script refuses ARM64 because these optional wheels were tested on AMD64 only.

To install local multimodal reasoning and place all runtime/model files on D:, run:

~~~powershell
cd D:/LocalFix/backend
./setup-local-vlm.ps1
~~~

The default is `qwen3-vl:2b-instruct-q4_K_M` because this 16 GB build host has limited available RAM. Override `LOCALFIX_VLM_MODEL` before setup for a larger locally supported tag; setup records that choice in the model manifest. The adapter accepts only loopback HTTP and does not use cloud models. The local runtime is not a QNN/NPU backend.

## Offline workflow

Start the local AI runtime and backend, confirm Runtime shows the expected models, then disconnect Wi-Fi. OCR, English transcription, semantic/manual search, local image-plus-text reasoning, procedures, cases, and reports work without a cloud service. Missing assets stay unavailable; there is no cloud fallback.

## Snapdragon deployment

For Qualcomm AI Hub multimodal reasoning, install GenieX for Windows ARM64 on the HP. Download the precompiled model once while online, then use LocalFix's GenieX mode:

~~~powershell
cd D:/LocalFix
.\backend\setup-geniex-snapdragon.ps1 -PullModel
$env:LOCALFIX_PYTHON = 'C:/Path/To/NativeArm64Python311/python.exe'
.\backend\run-snapdragon.ps1 -GenieX
~~~

The API key is not needed in this local runtime flow. The Workbench token is for cloud model management and optional profiling only; do not put it in the app. LocalFix connects to GenieX through `127.0.0.1`. It marks accelerator placement unverified unless runtime telemetry confirms it.

For ONNX stages, use native Windows ARM64 Python 3.11 and `backend/run-snapdragon.ps1` without `-GenieX`; it checks the QNN Execution Provider and requests HTP for compatible ONNX sessions. QNN provider discovery does not prove every operator ran on the NPU.

See [docs/MODEL_DEPLOYMENT.md](docs/MODEL_DEPLOYMENT.md). This host cannot validate Snapdragon QNN, QAIRT, GenieX, Qualcomm AI Hub assets, target thermals, or power. Ollama CPU inference is a separate fallback and does not establish NPU performance.

## Benchmark

Reports → Runtime accepts optional local image/audio fixtures and runs ten real repetitions for available OCR, object detection, ASR, VLM reasoning, and retrieval. OCR can use a synthetic label fixture for latency only, not accuracy. ASR needs a local audio clip; vision and VLM need a local image. Missing models produce unavailable rows. Generic zero-tensor ONNX smoke runs are ineligible for performance claims.

See [docs/BENCHMARK.md](docs/BENCHMARK.md). This AMD64 host supports CPU measurements only and cannot produce the Snapdragon NPU-vs-CPU comparison.

## Build and docs

From D:/LocalFix, run D:/LocalFix/.venv/Scripts/python.exe -m pytest. From D:/LocalFix/frontend, run npm run build.

- [Architecture](ARCHITECTURE.md)
- [UI specification](docs/UI_SPEC.md)
- [Model deployment](docs/MODEL_DEPLOYMENT.md)
- [Benchmark protocol](docs/BENCHMARK.md)
- [Safety](docs/SAFETY.md)
- [Data and model licenses](docs/DATA_LICENSES.md)
- [Demo script](docs/DEMO_SCRIPT.md)

## Limitations

The local VLM is small and its outputs are not calibrated; evidence checks can reject unsupported wording but cannot prove model truthfulness. VLM localization is a visual estimate and may fail to find a component; it is not a trained detector or calibrated bounding-box model. Speech is English-only and not guaranteed in noisy sites. OCR/ASR/embeddings use CPU in this setup. The fictional procedure is training content only and must never guide real repairs. LocalFix is not a certified safety system.
