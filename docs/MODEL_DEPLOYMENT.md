# Local model deployment

## Active AMD64 CPU stages

The optional development profile is installed only on the Windows AMD64 build host:

| Stage | Model/runtime | Current status |
| --- | --- | --- |
| OCR | RapidOCR PP-OCRv6 small via ONNX Runtime CPU | Installed and locally exercised on synthetic ACM-4200 label images |
| Speech | faster-whisper tiny.en via CTranslate2, int8 CPU | Installed and loaded locally; English model only |
| Retrieval | BAAI/bge-small-en-v1.5 via FastEmbed/ONNX Runtime CPU | Installed; vectors stored in SQLite and fused with FTS5 |
| Equipment detector | Project-trained YOLOv8 ONNX via ONNX Runtime | Decoder implemented; weights absent |
| Open-vocabulary detector | OWL-V2 | Not configured |
| Multimodal generation | Qwen3-VL 2B Instruct Q4_K_M through local Ollama API | Adapter implemented; model setup is explicit; local CPU path is being validated |

Install the optional profile from PowerShell:

~~~powershell
cd D:/LocalFix/backend
./setup-local-ai.ps1
~~~

This explicitly installs pinned packages and downloads the BGE and faster-whisper assets to D:/LocalFix/models. RapidOCR's compact detector/classifier/recognizer ONNX assets are bundled in the installed Python package. The backend never downloads model files. To check local assets without network access, run D:/LocalFix/.venv/Scripts/python.exe D:/LocalFix/backend/setup_local_models.py.

The optional profile is refused on ARM64; it was exercised only on this AMD64 development machine. It does not select QNN or establish Snapdragon support.

## Optional local multimodal reasoning

The diagnosis service can use a loopback-only Ollama server for actual image-plus-text generation. On this 16 GB AMD64 build host, the configured model is `qwen3-vl:2b-instruct-q4_K_M`; set `LOCALFIX_VLM_MODEL=qwen3-vl:4b-instruct-q4_K_M` on a machine with adequate memory before setup to pull the larger candidate instead. The Ollama binary and weights live under the ignored `models/` tree on D:.

~~~powershell
cd D:/LocalFix/backend
./setup-local-vlm.ps1
~~~

The setup script obtains the official Windows runtime for x64 or ARM64, verifies the Ollama Inc. code signature, sets the model store to D:, binds the service to loopback, disables Ollama cloud models for a server it starts, and downloads only the selected local model. `backend/run.ps1` starts the installed local runtime when present. `/diagnose` sends a selected/captured frame, local observations, the question, and retrieved manual passages only to `127.0.0.1`; non-loopback VLM endpoints and cloud model tags are refused. There is no VLM call without manual evidence.

Generated answers must cite IDs from the retrieved evidence and pass a conservative source-language overlap check. Procedure generation remains separately gated and never consumes VLM-generated steps. A short visual description is labeled as a model observation, not a diagnosis or calibrated probability. The host currently has constrained free RAM, so the 2B model is the default; model choice and runtime loading must be reevaluated for the target device.

The Ollama adapter does not invoke QNN or prove Snapdragon acceleration. Qualcomm AI Hub / QAIRT / GenieX deployment still needs a dedicated target-compatible generation adapter and on-device validation. A loaded model tag alone is not proof of NPU execution.

## Local image and voice paths

Live Diagnose requests browser camera/microphone permission only after technician input. Captured image/audio bytes are held in browser memory and posted to 127.0.0.1 through the Vite proxy. The backend does not persist or log raw media.

OCR uses PP-OCRv6 model assets installed with RapidOCR and ONNX Runtime CPU. Image dimensions are limited to 4096 px and 12 megapixels. OCR returns normalized asset/fault tokens, boxes, confidence scores, model, and backend.

Speech uses the local tiny.en model with CTranslate2 int8 CPU and local_files_only enabled. Microphone clips are limited to 25 MB in the API and the UI auto-stops recording at 30 seconds. The model is English-only; verify every transcription, especially serial numbers and fault codes.

Scanned PDF pages without extractable text are rendered locally and passed through OCR. The source page index remains the original PDF page number. Empty/unreadable pages stay visible in the ingestion result.

## Semantic retrieval

FastEmbed loads BAAI/bge-small-en-v1.5 from D:/LocalFix/models/embeddings with local_files_only enabled and CPUExecutionProvider. Document vectors are float32 blobs in SQLite and tagged with their embedding model. Retrieval applies the equipment filter, runs FTS5 and cosine similarity, then fuses rankings with weighted reciprocal-rank fusion. FTS5 remains available when semantic assets are missing.

Embedding model files are local-only at runtime. Network access is used only by the explicit setup script when invoked with its download flag.

## Configure the equipment detector

The vision adapter accepts a YOLOv8 ONNX export with NCHW float32 or float16 input and raw YOLOv8 predictions. The decoder supports [1, 4+C, N] and [1, N, 4+C] output layouts, letterbox inversion, confidence filtering, and non-maximum suppression.

1. Build a legally sourced/labeled dataset for the fictional ACM-4200 view. Do not treat the existing illustration as real equipment data.
2. Train/export a YOLOv8 model with exactly the class order in models/manifest.json: motor_relay, fuse, connector, control_board, display, warning_label, model_label.
3. Export ONNX at 640 x 640 with an output layout supported above. Validate decoded boxes on held-out photos before field use.
4. Place the licensed model at D:/LocalFix/models/vision/acm4200.onnx and set models.vision.path to vision/acm4200.onnx in the manifest.
5. Reload models and inspect /runtime/status. The task route rejects missing assets, incompatible inputs, and unsupported output shapes; no detection is fabricated.

The trained detector adapter covers closed-set YOLOv8 only. A separate `/vision/locate` path asks the local multimodal model for a named image region and validates its normalized box; this remains an uncalibrated VLM estimate, not an OWL-V2 or task-trained detector result.

## Snapdragon / QNN

Snapdragon deployment requires native Windows ARM64, a compatible Qualcomm runtime/driver, a matching model export, and task preprocessing/decoding. The build host is AMD64 and has not run this path on the target HP laptop.

Use Python 3.11 ARM64 and the separate backend/requirements-snapdragon-arm64.txt environment:

~~~powershell
$env:LOCALFIX_PYTHON = 'C:/Path/To/Python311-arm64/python.exe'
cd D:/LocalFix/backend
./run-snapdragon.ps1
~~~

The launcher checks that ONNX Runtime exposes QNNExecutionProvider and requests the HTP backend. Runtime status reports the active session providers. QNN provider presence is not proof that every node executes on NPU; collect the vendor placement/diagnostic output and task timings on the target.

Do not install the AMD64 CPU extras into the ARM64 environment. For ARM64, select Qualcomm AI Hub assets compatible with the exact HP Snapdragon generation and Windows runtime. Integrate them only after checking required auxiliary files, licensing, precision, operator coverage, and task adapter. QAIRT and GenieX need their vendor SDK bindings and separate adapters; their names in the manifest alone do not mean they work.

## Evidence, safety, and VLM limits

The VLM can summarize retrieved text and describe an image, but it cannot propose a repair procedure. A diagnosis is shown only when it includes a valid manual evidence ID, achieves the configured conservative text-overlap threshold against that cited passage, and contains no detected action language. If it fails validation, LocalFix falls back only to the existing supported rule summary or returns insufficient evidence. These checks reduce risk but do not calibrate model truthfulness; technicians must inspect the cited source. `/vision/locate` can ask the local VLM for a named visual region, then rejects missing, malformed, non-normalized, or implausibly large coordinates. The UI labels any returned region as a model estimate and supplies no calibrated confidence. This is a useful fallback interaction, not a replacement for a validated task-trained detector.

## Model and package references

- [RapidOCR installation](https://rapidai.github.io/RapidOCRDocs/main/en/install_usage/rapidocr/install/)
- [RapidOCR usage](https://rapidai.github.io/RapidOCRDocs/main/install_usage/rapidocr/usage/)
- [FastEmbed repository](https://github.com/qdrant/fastembed)
- [FastEmbed semantic search](https://github.com/qdrant/fastembed/blob/main/README.md)
- [ONNX Runtime QNN Execution Provider](https://onnxruntime.ai/docs/execution-providers/QNN-ExecutionProvider.html)
- [Qualcomm AI Hub documentation](https://aihub.qualcomm.com/docs/)
- [Ollama vision API](https://docs.ollama.com/capabilities/vision)
- [Ollama chat API](https://docs.ollama.com/api/chat)
- [Qwen3-VL 2B/4B model variants and sizes](https://ollama.com/library/qwen3-vl)
