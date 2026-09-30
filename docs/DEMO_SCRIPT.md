# LocalFix competition demo script

## Preparation

- On this AMD64 development machine, run backend/setup-local-ai.ps1 while online to install local OCR, English ASR, and semantic retrieval assets.
- Start Ollama, the API, and Vite app. Check Runtime lists OCR, Speech, Embedding, and Qwen3-VL 2B Instruct as local; Vision weights stay unavailable.
- Use the built-in fictional ACM-4200 illustration as the OCR sample. It is synthetic; its label text is intentionally present for the local OCR path.
- Keep the demo/manual disclaimer visible. No simulated detector or NPU result may be presented as real; a local VLM answer is real model output but must pass evidence checks and is not calibrated.
- On the Snapdragon HP, follow the GenieX setup in MODEL_DEPLOYMENT.md. The AI Hub API token is for model-management work only; LocalFix and the on-device GenieX server do not need it during the demo.

## Live CPU path (about 3 minutes)

1. Open Local Runtime → Diagnose. The default camera-stage artwork is labeled as a synthetic demo feed.
2. Click Scan. The frontend rasterizes the locally bundled illustration, passes it to the installed local OCR engine through the loopback API, and overlays OCR boxes. Read out the actual model/fault/serial values returned. If a value is wrong or missing, show that result honestly; do not substitute demo text.
3. Ask by typing: “Why is this machine showing E07?” If the microphone and local ASR model are available, record the question and review the local English transcript before asking.
4. Show that SQLite FTS5 plus local BGE embeddings retrieves the ACM-4200 service-manual passage and retains its page number. Open Evidence to inspect the source text.
5. Open the candidate procedure. Pause at the safety gate and explain that only the technician can acknowledge the site-approved safe state. Complete a case and generate the local report.
6. Open Reports → Runtime. Run the 10-sample OCR/retrieval benchmark. Select an audio fixture to measure speech and a local image to measure VLM response, first-token latency, and throughput. Vision detector remains unavailable without trained weights.
7. Turn Wi-Fi off while leaving the local API and frontend running. Scan, ask the same question, open the manual, and generate the report again. OCR, ASR, and retrieval use local assets.

## Demo simulation (optional visual narrative)

Switch to Demo Mode only when illustrating the complete fictional user story. Camera boxes, voice phrase, relay localization, response text, and measurements in Demo Mode are simulated. The labels are visible in the interface. Use it to narrate the future “Show Me” experience, not as evidence of model accuracy or hardware performance.

## Current competition boundary

The live local path on the AMD64 host proves OCR, speech, local hybrid manual search, Qwen3-VL image-plus-manual inference, evidence checks, procedures, reports, and offline operation. On the Snapdragon HP, repeat the same workflow with the GenieX model and verify the selected accelerator on that device. Real component localization still requires a task-trained detector and held-out equipment photos.

## Safe phrasing

Say only what the live machine reports. The Intel build host is CPU-only. On the HP, GenieX requests Qualcomm AI Engine Direct/NPU, while LocalFix labels placement unverified until device telemetry and repeatable task timings are recorded. The detector still needs trained component weights.

Do not claim a diagnosed failure is a repair instruction. The fictional manual and procedure exist to exercise the product flow only.
