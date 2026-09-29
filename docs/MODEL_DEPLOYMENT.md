# Local model deployment

## Adapter boundary

Each local stage implements `load()`, `warmup()`, `infer()`, `benchmark()`, and `health()`:

- `VisionModel`
- `OCRModel`
- `SpeechModel`
- `EmbeddingModel`
- `VLMModel`

The current common ONNX adapter can inspect/load an operator-supplied ONNX asset and select from provider names reported by the installed ONNX Runtime. QNN is preferred only when present, then CPU fallback. Runtime telemetry comes from the active session provider list. A model file on disk alone is not reported as ready.

## Add a model asset

1. Obtain a model and any required tokenizer/preprocessor from its official publisher; confirm the model license and Snapdragon Windows compatibility.
2. Place the asset inside `D:\LocalFix\models`.
3. Edit `models/manifest.json` with its relative path, precision, runtime adapter, and provider preference.
4. Install the matching local runtime/provider package using the vendor's instructions. Do not replace a production runtime package with a CPU-only build and expect NPU acceleration.
5. Implement and test model-specific input preprocessing, output decoding, tensor names/shapes, normalization, and safety validation for that model.
6. Select **Reload models**. Check `/runtime/status` for file presence, session state, active providers, load time, precision, and errors.
7. Run the benchmark. A zero-tensor ONNX smoke result is not a task benchmark and is explicitly marked ineligible for performance claims.

Do not put credentials or an internet model-download step in the application. Model weights remain in the controlled local `models/` directory. The app never silently claims QNN based on Snapdragon hardware identity.

## Qualcomm paths

- **ONNX Runtime**: supported adapter interface. On Snapdragon, the adapter requests QNN's HTP backend and includes CPU as the explicit fallback provider. Runtime reports the providers active in the loaded session; that does not prove every graph operator ran on the NPU. Validate the exported graph and operator placement on the target before making performance claims.
- **Qualcomm AI Hub assets**: use only assets exported for the target Snapdragon device/runtime. Add them as an ONNX model only when the package actually contains a compatible ONNX graph and any needed auxiliary files; otherwise add an asset-specific adapter.
- **QAIRT**: keep a separate adapter for QAIRT context binaries and SDK interfaces. The base repository does not bundle proprietary SDK bindings; runtime reports unavailable until a local QAIRT adapter is supplied and verified.
- **GenieX**: treat as a replaceable local generative runtime adapter for compatible LLM/VLM assets. No GenieX backend is claimed active in this baseline.

### Native Windows on Snapdragon setup

The ordinary `backend/requirements.txt` is the CPU development environment. For a native Windows ARM64 Snapdragon install, use Python **3.11.x ARM64** and the separate QNN environment:

```powershell
$env:LOCALFIX_PYTHON = 'C:\Path\To\Python311-arm64\python.exe'
cd D:\LocalFix\backend
.\run-snapdragon.ps1
```

The script checks the interpreter architecture/version and verifies that `QNNExecutionProvider` is exposed before serving the API. Its dependencies are in `requirements-snapdragon-arm64.txt` (`onnxruntime-qnn` and NumPy 1.26.4). If the device vendor package or driver setup differs, follow the official [ONNX Runtime QNN Execution Provider guide](https://onnxruntime.ai/docs/execution-providers/QNN-ExecutionProvider.html). The official guide's Windows Snapdragon Python wheel requirements are version-specific; do not reuse the x64 CPU requirements in the ARM64 environment.

Qualcomm AI Hub can export models for supported device/runtime targets; confirm the exact asset, precision, operator coverage, and licensing for the HP laptop before configuring a manifest entry. See the [Qualcomm AI Hub documentation](https://dev.aihub.qualcomm.com/docs/) for supported workflows. QNN session activation is a backend selection signal, not evidence that all layers executed on NPU; benchmark the actual application model and inspect provider/runtime diagnostics.

The model manifest includes the `adapter` field. Supported ONNX models can load generically, but task endpoints remain disabled until the stage-specific preprocessing/decode implementation is complete. Model availability and execution-provider status are separate.

## Current stage status

| Stage | Adapter interface | Pre/postprocessor included | Default state |
|---|---|---|---|
| Vision detector / open vocabulary | Yes | No | Missing model |
| OCR | Yes | OCR token normalization/classification helpers only | Missing model |
| Speech | Yes | No local audio decoder | Missing model |
| Embeddings | Yes | No tokenizer/vector similarity path | Missing model |
| VLM reasoning | Yes | No generation adapter | Missing model |

An API request for an unavailable or incomplete adapter returns a structured error. It will not use browser cloud speech, remote inference, or guessed output as fallback.
