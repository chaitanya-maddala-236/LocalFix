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

Snapdragon deployment requires native Windows ARM64, a compatible Qualcomm runtime/driver, a matching model export, and task preprocessing/decoding. This workspace runs on an Intel x64 Dell, so the target HP laptop has not been validated from this build host.

Use Python 3.11 ARM64 and the separate backend/requirements-snapdragon-arm64.txt environment:

~~~powershell
$env:LOCALFIX_PYTHON = 'C:/Path/To/Python311-arm64/python.exe'
cd D:/LocalFix/backend
./run-snapdragon.ps1
~~~

The launcher checks that ONNX Runtime exposes QNNExecutionProvider and requests the HTP backend. Runtime status reports active session providers. QNN provider presence is not proof that every node executes on NPU; collect the vendor placement/diagnostic output and task timings on the target.

Do not install the AMD64 CPU extras into the ARM64 environment. The LocalFix VLM adapter also supports a local GenieX OpenAI-compatible endpoint. This is the recommended multimodal-reasoning path for Qualcomm AI Hub's precompiled Windows ARM64 VLM bundles; it does not send field images, voice, or manuals to Workbench.

### Qualcomm AI Hub + GenieX VLM

The AI Hub Workbench API token is for account management and cloud compile/profile jobs. It is not needed by LocalFix at run time and must not be placed in the repository, model manifest, or a persistent AI Hub profile for this workflow. `backend/qualcomm_aihub_profiles.py` prompts with hidden input and performs a read-only device-profile lookup. A separate Python 3.11+ environment is recommended:

~~~powershell
cd D:/LocalFix
py -3.11 -m venv .venv-aihub
$env:TEMP = 'D:/LocalFix/.tmp-aihub'
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Force $env:TEMP | Out-Null
.\.venv-aihub\Scripts\python.exe -m pip install --no-cache-dir qai-hub
.\.venv-aihub\Scripts\python.exe backend/qualcomm_aihub_profiles.py
~~~

The profile lookup authenticates directly with the AI Hub API and prints public target names only. Qualcomm's current model catalog lists Qwen3-VL-4B-Instruct for Snapdragon X Elite, X Plus 8-Core, and X2 Elite reference profiles. A Snapdragon X Plus 10-Core issue reports that this AI Hub bundle is not currently available for that chipset; similar marketing names do not imply bundle compatibility. Reference-profile support is not proof that an arbitrary HP SKU or runtime package works, and profile metrics are not HP laptop measurements. Confirm the exact laptop chipset and `geniex model list` before deployment.

On the Snapdragon laptop, install Qualcomm's GenieX Windows ARM64 CLI using the model page's Quick Start. Download the model once while online into LocalFix's D: model directory, then run the app with its local GenieX server:

~~~powershell
cd D:/LocalFix
.\backend\setup-geniex-snapdragon.ps1 -PullModel
$env:LOCALFIX_PYTHON = 'C:/Path/To/NativeArm64Python311/python.exe'
.\backend\run-snapdragon.ps1 -GenieX
~~~

If the GenieX installer did not add its CLI to PATH, set `$env:LOCALFIX_GENIEX_EXE` to the full `geniex.exe` path before running setup. After the API starts, capture a non-sensitive photo of the DemoTech panel or the target equipment, then run a live verification from a second PowerShell window:

~~~powershell
.\backend\verify-snapdragon.ps1 -ImagePath 'D:\LocalFix\benchmark\acm4200-panel.jpg' -RunBenchmark
~~~

To verify with network adapters disabled, turn Wi-Fi/Ethernet off in Windows and add `-RequireOffline`. The script requires a real local GenieX answer that passes citation checks, exercises OCR and visual localization on the selected image, and saves a JSON record under `benchmark/snapdragon-runs/`. It does not disable networking itself. GenieX's OpenAI API does not report accelerator placement, so the record leaves NPU verification explicitly unverified unless another runtime reports an active QNN provider.

Setup pulls the model as `ai-hub-models/Qwen3-VL-4B-Instruct`. GenieX may advertise the loaded bundle under an API ID such as `qualcomm/Qwen3-VL-4B-Instruct:W4A16`; the launcher discovers that ID and removes the precision suffix before LocalFix sends chat requests. The launcher sets `GENIEX_DATADIR` to `D:/LocalFix/models/geniex`, starts the server on `127.0.0.1:18181` with NPU requested, verifies the expected model is exposed, and configures FastAPI to send multimodal requests to that loopback service. GenieX logs are written under `D:/LocalFix/logs/`. Once the model files are present, GenieX can run without internet. Diagnosis still requires local manual evidence; procedure steps remain generated from fixed, cited manual mappings and pass the existing safety acknowledgement.

LocalFix identifies GenieX as a local provider but reports NPU status as unverified because the GenieX OpenAI-compatible API does not expose provider placement to this app. A successful response is not by itself a measured performance comparison. Run the same task with NPU and CPU configurations on the physical HP laptop and retain the device, runtime, model, precision, provider, and raw task timings with the benchmark result. Do not use Workbench-hosted proxy results as measurements from that laptop.

## Evidence, safety, and VLM limits

The VLM can summarize retrieved text and describe an image, but it cannot propose a repair procedure. A diagnosis is shown only when it includes a valid manual evidence ID, achieves the configured conservative text-overlap threshold against that cited passage, and contains no detected action language. If it fails validation, LocalFix falls back only to the existing supported rule summary or returns insufficient evidence. These checks reduce risk but do not calibrate model truthfulness; technicians must inspect the cited source. `/vision/locate` can ask the local VLM for a named visual region, then rejects missing, malformed, non-normalized, or implausibly large coordinates. The UI labels any returned region as a model estimate and supplies no calibrated confidence. This is a useful fallback interaction, not a replacement for a validated task-trained detector.

## Model and package references

- [RapidOCR installation](https://rapidai.github.io/RapidOCRDocs/main/en/install_usage/rapidocr/install/)
- [RapidOCR usage](https://rapidai.github.io/RapidOCRDocs/main/install_usage/rapidocr/usage/)
- [FastEmbed repository](https://github.com/qdrant/fastembed)
- [FastEmbed semantic search](https://github.com/qdrant/fastembed/blob/main/README.md)
- [ONNX Runtime QNN Execution Provider](https://onnxruntime.ai/docs/execution-providers/QNN-ExecutionProvider.html)
- [Qualcomm AI Hub documentation](https://aihub.qualcomm.com/docs/)
- [Qualcomm AI Hub Qwen3-VL-4B-Instruct](https://aihub.qualcomm.com/models/qwen3_vl_4b_instruct)
- [Qualcomm AI Hub GenieX](https://github.com/qualcomm/GenieX)
- [Qualcomm AI Hub Workbench client configuration](https://workbench.aihub.qualcomm.com/docs/hub/generated/qai_hub.ClientConfig.html)
- [Ollama vision API](https://docs.ollama.com/capabilities/vision)
- [Ollama chat API](https://docs.ollama.com/api/chat)
- [Qwen3-VL 2B/4B model variants and sizes](https://ollama.com/library/qwen3-vl)
