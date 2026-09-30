# Data and license register

## Original assets

- The fictional DemoTech ACM-4200 manual is authored for LocalFix. Printed page identifiers demonstrate page-preserving citation; the content is not an actual service manual or repair guidance.
- The ACM-4200 SVG illustration and OCR label fixture are synthetic project assets. Embedded detection rectangles in annotations.json are illustrative only, not validated training labels.
- Demo case/OCR/evidence records are synthetic fixtures. No proprietary manuals, commercial equipment photos, or pretrained model weights are stored in the repository.

## Optional model downloads

Model files are fetched only when the operator explicitly runs backend/setup-local-ai.ps1 or backend/setup-local-vlm.ps1. They are stored under the ignored local models directory and are not committed or re-distributed by LocalFix.

| Asset | Publisher/source | Runtime | Distribution note |
| --- | --- | --- | --- |
| RapidOCR PP-OCRv6 package model files | RapidAI RapidOCR Python package | ONNX Runtime CPU | Review upstream package and model notices before redistribution |
| BAAI/bge-small-en-v1.5 embedding model | BAAI model family via FastEmbed model catalog | ONNX Runtime CPU | Review upstream model card/license and FastEmbed catalog terms |
| faster-whisper tiny.en weights | Systran converted Whisper checkpoint | CTranslate2 CPU | Review the upstream Whisper and conversion model terms before redistribution |
| Qwen3-VL 2B Instruct Q4_K_M | Alibaba Qwen model via official Ollama library | Ollama local runtime | Official Ollama tag lists Apache License 2.0; preserve model card and registry details for the exact tag |
| Qwen3-VL-4B-Instruct | Qualcomm AI Hub model catalog, downloaded into GenieX cache during target setup | GenieX / Qualcomm AI Engine Direct | Model page lists Apache-2.0; verify the selected precision, target compatibility, current model terms, and bundled runtime notices before redistribution |
| Ollama Windows runtime | Ollama Inc. official portable release | Loopback API | Verify Authenticode signature before use; review bundled notices before redistribution |

Upstream references: [RapidOCR documentation](https://rapidai.github.io/RapidOCRDocs/main/en/install_usage/rapidocr/install/), [BGE-small model card](https://huggingface.co/BAAI/bge-small-en-v1.5), [faster-whisper repository](https://github.com/SYSTRAN/faster-whisper), [FastEmbed repository](https://github.com/qdrant/fastembed), [Qwen3-VL official Ollama library](https://ollama.com/library/qwen3-vl), [Qwen3-VL-4B-Instruct AI Hub model page](https://aihub.qualcomm.com/models/qwen3_vl_4b_instruct), [GenieX runtime](https://github.com/qualcomm/GenieX), [Ollama Windows runtime](https://github.com/ollama/ollama/blob/main/docs/windows.mdx). Verify license/version terms before bundling a model or shipping the installer.

## Dataset boundary

data/synthetic/annotations.json records normalized xyxy boxes for seven classes over one original vector illustration. It makes the UI demo reproducible; it is far too small and artificial for training or claiming component-detection accuracy. Build a real detector dataset only from authorized, consented images, then review annotations and train/validate with a held-out set.

The name DemoTech and model ACM-4200 are fictional demo identifiers. Review trademarks in the distribution jurisdictions before release. LocalFix is a prototype and the manual is not operational guidance.
