# LocalFix

**Your field engineer. Offline. On-device. Evidence-first.**

LocalFix is an offline-first field technician copilot prototype focused on the fictional DemoTech ACM-4200 industrial motor controller. It combines a polished six-screen technician console, a local FastAPI/SQLite service, page-preserving manual ingestion and retrieval, safety-gated procedures, case history, report export, and replaceable local model adapters.

## Why it exists

Field technicians often have to identify a machine, read a fault code, find the correct manual passage, choose a safe next check, and document the result while working with poor connectivity. LocalFix makes that workflow demonstrable on the device: evidence stays local, every retrieved chunk retains its original source page, and unsupported findings are blocked.

## What is implemented

- Six primary screens: Operations Home, Live Diagnose, Evidence Inspector, Procedure, Cases, and Reports & Runtime.
- An explicit **Demo Mode** built from synthetic ACM-4200 artwork, sample OCR/detection/evidence, and sample cases. Every simulated signal is labeled. Demo timings are blank.
- A **Local Runtime** connection that reads backend telemetry, local cases, retrieved evidence, and installed-model state. Missing model preprocessing/decoding is surfaced as unavailable rather than replaced by sample inference.
- FastAPI endpoints for health, runtime, vision/OCR/speech adapters, PDF ingestion, FTS5 retrieval, grounded summaries, source-backed procedure steps, cases, reports, and benchmarks.
- SQLite storage for documents, source pages, chunks, cases, evidence, and procedure steps.
- A configurable ONNX Runtime adapter that selects QNN only if the installed provider and model report it active; CPU fallback is identified separately.
- PDF and Markdown/JSON service report export, local diagnostics export, and an original 16-page fictional manual excerpt with selected source pagination.
- Keyboard-focus styling, labeled controls, responsive layout, smooth state transitions, and reduced-motion support.

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for the system diagram, component tree, REST contract, SQLite schema, wireframes, state machine, inference flow, Snapdragon deployment plan, and benchmark protocol.

## Screens

1. `/` — Operations Home
2. `/diagnose` — Live Diagnose
3. `/evidence` — Evidence and Manual Viewer (also supports local PDF ingestion)
4. `/procedure` — Safety-gated troubleshooting timeline
5. `/cases` — Searchable case history
6. `/reports` — Service report export and runtime settings tabs

## Setup on Windows

Install Node.js 20+ and Python 3.11+ for the standard Windows development setup (the source is typed for Python 3.10+). Install the frontend and backend dependencies once while connected. After that, the application itself makes no external inference or manual-storage requests.

### 1. Start the local API

Open PowerShell:

```powershell
cd D:\LocalFix\backend
.\run.ps1
```

On first launch, `run.ps1` creates `D:\LocalFix\.venv`, installs `backend\requirements.txt`, initializes `data\localfix.sqlite3`, and starts FastAPI on `127.0.0.1:8000`. Keep the window open. The API binds to loopback only.

### 2. Start the frontend

In another PowerShell window:

```powershell
cd D:\LocalFix\frontend
npm install
npm run dev
```

Open the local Vite address shown in the terminal (normally `http://127.0.0.1:5173`). The Vite proxy forwards `/api` requests to the loopback backend.

### Demo without the backend

The frontend starts in Demo Mode and can demonstrate its preloaded synthetic scenario without a camera, microphone, model, or backend. Keep the `DEMO MODE` label visible when presenting simulated outputs. Choose **Local Runtime** in the top bar to inspect actual backend/model status.

## Manual ingestion and offline use

Open **Manuals & evidence** and add a PDF while Local Runtime is connected. PDF ingestion is capped at 50 MB and 500 pages, extracts text locally, preserves original PDF page indices, hashes the source, and indexes page-linked chunks in SQLite FTS5. Pages without extractable text remain recorded with their page number and produce an OCR-unavailable warning. No PDF is uploaded anywhere.

Once dependencies and model files are present, turn Wi-Fi off and continue using the loopback frontend/backend. The offline path has no cloud fallback. Windows network-interface status is reported without a connectivity probe; LocalFix does not make an internet request to decide whether it is offline.

## Model setup

See [docs/MODEL_DEPLOYMENT.md](docs/MODEL_DEPLOYMENT.md). No model weights are bundled or downloaded. Edit `models/manifest.json` to point to locally held, licensed ONNX files under `D:\LocalFix\models`. Runtime readiness requires both a present model and a successful runtime session. Generic tensor execution is not enough to enable image/audio products: model-specific preprocessing and output decoding are required, and the API explicitly reports the missing adapter stage.

## Benchmarking

Use **Reports & Runtime → AI Runtime → Run benchmark** or `POST /benchmark/run`. Retrieval benchmarks use real local SQLite queries. ONNX adapters, when configured, run a 10-repeat synthetic tensor smoke benchmark and mark it **not eligible for performance claims**. Cold-load and warm-up telemetry are separate. Vision/OCR/ASR/VLM task-quality and end-to-end latency remain unavailable until task preprocessors, decoders, and local model assets are installed.

See [docs/BENCHMARK.md](docs/BENCHMARK.md).

## Tests

From the project root, with backend requirements installed:

```powershell
D:\LocalFix\.venv\Scripts\python.exe -m pytest
```

Frontend production type-check/build:

```powershell
cd D:\LocalFix\frontend
npm run build
```

## Snapdragon deployment

For native Windows on Snapdragon, use ARM64 Python 3.11.x, set `LOCALFIX_PYTHON` to that interpreter, and launch `backend\run-snapdragon.ps1`. This installs the separate QNN-compatible requirements, verifies that the QNN Execution Provider is available, and requests its HTP backend for loaded ONNX models. The standard requirements target CPU development. `NPU ACTIVE` appears only when a loaded model session lists `QNNExecutionProvider` as active; this provider signal does not establish that every model operation ran on the NPU. No models are bundled, and task preprocessors/decoders remain a separate requirement.

See [docs/MODEL_DEPLOYMENT.md](docs/MODEL_DEPLOYMENT.md). QAIRT/GenieX integrations require their vendor runtime bindings and model-specific preprocessors; until those are supplied, the capability reports unavailable.

## Documentation

- [Architecture](ARCHITECTURE.md)
- [UI specification](docs/UI_SPEC.md)
- [Model deployment](docs/MODEL_DEPLOYMENT.md)
- [Benchmark protocol](docs/BENCHMARK.md)
- [Safety model](docs/SAFETY.md)
- [Data licenses](docs/DATA_LICENSES.md)
- [Competition demo script](docs/DEMO_SCRIPT.md)

## Limitations

- The default interface is a polished simulation, clearly marked as such.
- The repo contains adapter interfaces and runtime/provider discovery, not bundled vision, OCR, speech, embedding, or VLM weights.
- Vision/OCR/ASR/VLM model-specific preprocessing and output decoders are not implemented yet. The API returns explicit unavailable/adapter-incomplete errors instead of fabricated live outputs.
- FTS5 keyword retrieval is implemented. The embedding column and `EmbeddingModel` adapter are ready for an operator-supplied local embedding model, but semantic embedding search is not enabled.
- Scanned-only PDF pages are preserved and warned about; OCR conversion for such pages awaits an installed, configured local OCR pipeline.
- The sample troubleshooting content is fictional training material and must never be used on real equipment.
- This is a local engineering prototype, not a certified repair or safety system.
