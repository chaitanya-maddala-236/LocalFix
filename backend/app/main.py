from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import io
import json
import logging
import os
import re
import statistics
import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import fitz
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import Response

from .database import DATA_DIR, PROJECT_ROOT, connect, initialize_database, now_iso, insert_manual_document
from .models.base import ModelInputError, ModelRegistry, ModelUnavailableError
from .schemas import (
    BenchmarkRequest, BenchmarkResponse, BenchmarkResult, CaseCreate, CaseListResponse,
    CaseResponse, DiagnoseRequest, DiagnosisResponse, IngestResponse, ManualSummary,
    OCRRequest, OCRResponse, OCRValue, ProcedureRequest, ProcedureResponse, ProcedureStep,
    ReportRequest, RetrieveRequest, RetrieveResponse, RuntimeActionResponse, RuntimeStatus,
    SpeechRequest, SpeechResponse, VisionRequest, VisionResponse, Detection, LocateRequest, LocateResponse,
)
from .services.cases import create_case, get_case, list_cases
from .services.embeddings import LocalEmbeddingIndex, hybrid_retrieve
from .services.local_ocr import LocalOCREngine
from .services.local_speech import LocalSpeechEngine
from .services.local_vlm import LocalVLMEngine, validate_grounded_response
from .services.reports import markdown_report, pdf_report, report_payload
from .services.retrieval import clear_retrieval_cache, get_evidence_by_ids, get_page, list_manuals, retrieve, supported_finding
from .services.safety import safety_gate

registry = ModelRegistry(PROJECT_ROOT)
ocr_engine = LocalOCREngine()
speech_config = registry.local_services.get("speech", {})
speech_engine = LocalSpeechEngine(PROJECT_ROOT, speech_config.get("model_path"))
retrieval_config = registry.local_services.get("retrieval", {})
embedding_index = LocalEmbeddingIndex(
    PROJECT_ROOT, retrieval_config.get("model_name", "BAAI/bge-small-en-v1.5"),
)
reasoning_config = registry.local_services.get("reasoning", {})
vlm_engine = LocalVLMEngine(reasoning_config.get("model", "qwen3-vl:2b-instruct-q4_K_M"), reasoning_config.get("url", "http://127.0.0.1:11434"))
MAX_UPLOAD_BYTES = int(os.getenv("LOCALFIX_MAX_UPLOAD_MB", "50")) * 1024 * 1024
logger = logging.getLogger("localfix.operations")
logging.basicConfig(level=os.getenv("LOCALFIX_LOG_LEVEL", "INFO").upper(), format="%(message)s")


def retrieve_local(query: str, equipment_model: str | None, top_k: int):
    if embedding_index.state == "READY":
        return hybrid_retrieve(query, equipment_model, top_k, embedding_index, retrieve)
    return retrieve(query, equipment_model, top_k)


def extract_pdf_pages(payload: bytes) -> tuple[list[tuple[int, str]], list[int]]:
    pdf = fitz.open(stream=payload, filetype="pdf")
    if pdf.needs_pass:
        pdf.close()
        raise HTTPException(status_code=422, detail={"code": "ENCRYPTED_PDF", "message": "Encrypted PDFs are not supported."})
    if pdf.page_count > 500:
        pdf.close()
        raise HTTPException(status_code=413, detail={"code": "TOO_MANY_PAGES", "message": "Manuals are limited to 500 pages."})
    pages: list[tuple[int, str]] = []
    ocr_pages: list[int] = []
    try:
        for index, page in enumerate(pdf):
            text = page.get_text("text").strip()
            if not text and ocr_engine.state == "READY":
                scale = min(2.0, 2200 / max(page.rect.width, page.rect.height))
                pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
                recognized, _ = ocr_engine.infer(pixmap.tobytes("png"))
                text = "\n".join(value.text for value in recognized).strip()
                if text:
                    ocr_pages.append(index + 1)
            pages.append((index + 1, text))
    finally:
        pdf.close()
    return pages, ocr_pages


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    clear_retrieval_cache()
    await registry.load_all()
    await asyncio.gather(
        asyncio.to_thread(ocr_engine.load),
        asyncio.to_thread(speech_engine.load),
        asyncio.to_thread(embedding_index.load),
    )
    if embedding_index.state == "READY":
        await asyncio.to_thread(embedding_index.embed_unindexed)
    yield


app = FastAPI(
    title="LocalFix Local API", version="0.1.0",
    description="Loopback-only API for source-grounded, on-device field support.",
    lifespan=lifespan,
)


@app.middleware("http")
async def structured_operation_log(request, call_next):
    started = time.perf_counter()
    status_code = 500
    error_class = None
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    except Exception as error:
        error_class = type(error).__name__
        raise
    finally:
        path = request.url.path
        stage = next((name for name in ("vision", "ocr", "speech", "retrieve", "diagnose", "procedure", "benchmark") if path.startswith(f"/{name}")), None)
        adapter = registry.adapters.get("reasoning" if stage == "diagnose" else stage) if stage else None
        logger.info(json.dumps({
            "timestamp": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "operation": f"{request.method} {path}", "model": getattr(adapter, "model_name", None),
            "backend": getattr(adapter, "backend", None), "latency_ms": round((time.perf_counter() - started) * 1000, 3),
            "success": 200 <= status_code < 400, "status_code": status_code, "error": error_class,
        }, separators=(",", ":")))


@app.exception_handler(ModelUnavailableError)
async def model_unavailable_handler(_, error: ModelUnavailableError):
    return Response(
        content=json.dumps({"detail": {"code": "MODEL_UNAVAILABLE", "message": str(error)}}),
        status_code=503, media_type="application/json",
    )


@app.exception_handler(ModelInputError)
async def model_input_error_handler(_, error: ModelInputError):
    return Response(
        content=json.dumps({"detail": {"code": "MODEL_ADAPTER_INCOMPLETE", "message": str(error)}}),
        status_code=422, media_type="application/json",
    )


@app.get("/health")
async def health() -> dict[str, Any]:
    try:
        with connect() as connection:
            connection.execute("SELECT 1").fetchone()
        database = "ready"
    except Exception:
        database = "error"
    return {"status": "ready" if database == "ready" else "degraded", "version": app.version, "database": database}


@app.get("/runtime/status", response_model=RuntimeStatus)
async def runtime_status() -> dict[str, Any]:
    payload = await registry.runtime_payload()
    local_stages = {
        "ocr": await asyncio.to_thread(ocr_engine.health),
        "speech": await asyncio.to_thread(speech_engine.health),
        "embedding": await asyncio.to_thread(embedding_index.health),
        "reasoning": await asyncio.to_thread(vlm_engine.load),
    }
    for stage, detail in local_stages.items():
        payload["model_details"][stage] = detail
        payload["models"][stage] = "ready" if detail["state"] == "READY" else (
            "missing" if detail["state"] in {"NOT_INSTALLED", "MODEL_REQUIRED"} else "unavailable"
        )
    if ocr_engine.last_latency_ms is not None:
        payload["latencyMs"]["ocr"] = ocr_engine.last_latency_ms
    if speech_engine.last_latency_ms is not None:
        payload["latencyMs"]["speech"] = speech_engine.last_latency_ms
    if vlm_engine.last_latency_ms is not None:
        payload["latencyMs"]["reasoning"] = vlm_engine.last_latency_ms
    payload["precision"]["reasoning"] = vlm_engine.precision
    if vlm_engine.state == "READY" and "QNNExecutionProvider" not in payload["model_details"]["reasoning"]["active_providers"]:
        payload["backend"] = "GenieX local · accelerator unverified" if vlm_engine.provider == "geniex" else "Local AI · VLM runtime (accelerator unverified)"
        if vlm_engine.provider == "geniex" and payload["npu"] != "active":
            payload["npu"] = "unknown"
    payload["retrieval"] = {
        "mode": "hybrid_rrf" if embedding_index.state == "READY" else "sqlite_fts5",
        "semantic": embedding_index.state == "READY",
        "embedding_model": embedding_index.model_name if embedding_index.state == "READY" else None,
    }
    if payload["backend"].startswith("Unavailable") and any(stage["state"] == "READY" for stage in local_stages.values()):
        payload["backend"] = "Local CPU AI stages active"
    return payload


@app.post("/vision/detect", response_model=VisionResponse)
async def vision_detect(request: VisionRequest) -> VisionResponse:
    if request.demo_scene == "acm4200_demo":
        return VisionResponse(model="SIMULATED · no model", backend="DEMO ONLY", simulated=True, detections=[
            Detection(label="motor_relay", confidence=0.0, box=(0.56, 0.47, 0.68, 0.60)),
            Detection(label="display", confidence=0.0, box=(0.29, 0.18, 0.53, 0.37)),
            Detection(label="model_label", confidence=0.0, box=(0.66, 0.17, 0.76, 0.29)),
        ])
    if request.image_base64 is None:
        raise HTTPException(status_code=422, detail={"code": "IMAGE_REQUIRED", "message": "Provide a camera frame or imported image."})
    encoded = request.image_base64.partition(",")[2] if "," in request.image_base64 else request.image_base64
    try:
        image_bytes = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as error:
        raise HTTPException(status_code=422, detail={"code": "INVALID_IMAGE", "message": "Image payload must be base64 encoded."}) from error
    if not image_bytes or len(image_bytes) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail={"code": "IMAGE_TOO_LARGE", "message": "Image must be under 20 MB."})
    adapter = registry.adapters.get("vision")
    if adapter is None or adapter.state != "READY":
        raise ModelUnavailableError("Vision model is not installed. No detections were fabricated.")
    if not hasattr(adapter, "detect_image"):
        raise ModelInputError("The configured vision adapter does not implement image detection.")
    try:
        detections = await adapter.detect_image(image_bytes)
    except ValueError as error:
        raise HTTPException(status_code=422, detail={"code": "DETECTION_FAILED", "message": str(error)}) from error
    registry.record_latency("vision", adapter.last_latency_ms or 0.0)
    return VisionResponse(detections=detections, model=adapter.model_name, backend=adapter.backend, simulated=False)


@app.post("/vision/locate", response_model=LocateResponse)
async def vision_locate(request: LocateRequest) -> LocateResponse:
    encoded = request.image_base64.partition(",")[2] if "," in request.image_base64 else request.image_base64
    try:
        image_bytes = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as error:
        raise HTTPException(status_code=422, detail={"code": "INVALID_IMAGE", "message": "Image payload must be base64 encoded."}) from error
    if not image_bytes or len(image_bytes) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail={"code": "IMAGE_TOO_LARGE", "message": "Image must be under 20 MB."})
    await asyncio.to_thread(vlm_engine.load)
    if vlm_engine.state != "READY":
        raise ModelUnavailableError("Local VLM component localization is unavailable. No location was fabricated.")
    result = await asyncio.to_thread(vlm_engine.locate_component, image_bytes, request.target)
    registry.record_latency("reasoning", result["latency_ms"])
    provider = "GenieX" if vlm_engine.provider == "geniex" else "Ollama"
    return LocateResponse(
        found=result["found"], target=result["target"], box=result["box"],
        model=result["model"], backend=f"{provider} · local VLM visual estimate",
        latency_ms=result["latency_ms"], simulated=False,
    )


@app.post("/vision/ocr", response_model=OCRResponse)
async def vision_ocr(request: OCRRequest) -> OCRResponse:
    if request.image_base64 is None:
        raise HTTPException(status_code=422, detail={"code": "IMAGE_REQUIRED", "message": "Provide an image or use the explicit demo_scene in /vision/detect."})
    encoded = request.image_base64.partition(",")[2] if "," in request.image_base64 else request.image_base64
    try:
        image_bytes = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as error:
        raise HTTPException(status_code=422, detail={"code": "INVALID_IMAGE", "message": "Image payload must be base64 encoded."}) from error
    if not image_bytes or len(image_bytes) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail={"code": "IMAGE_TOO_LARGE", "message": "Image must be under 20 MB."})
    try:
        values, elapsed_ms = await asyncio.to_thread(ocr_engine.infer, image_bytes)
    except ModelUnavailableError:
        raise
    except Exception as error:
        raise HTTPException(status_code=422, detail={"code": "OCR_FAILED", "message": f"Local OCR could not read this image ({type(error).__name__})."}) from error
    registry.record_latency("ocr", elapsed_ms)
    return OCRResponse(values=values, model="RapidOCR PP-OCRv6 small", backend="ONNX Runtime · CPU", simulated=False)


@app.post("/speech/transcribe", response_model=SpeechResponse)
async def speech_transcribe(request: SpeechRequest) -> SpeechResponse:
    encoded = request.audio_base64.partition(",")[2] if "," in request.audio_base64 else request.audio_base64
    try:
        audio_bytes = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as error:
        raise HTTPException(status_code=422, detail={"code": "INVALID_AUDIO", "message": "Audio payload must be base64 encoded."}) from error
    if not audio_bytes or len(audio_bytes) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail={"code": "AUDIO_TOO_LARGE", "message": "Audio must be under 25 MB."})
    try:
        transcript, language, elapsed_ms = await asyncio.to_thread(speech_engine.transcribe, audio_bytes, request.content_type)
    except ModelUnavailableError:
        raise
    except Exception as error:
        raise HTTPException(status_code=422, detail={"code": "TRANSCRIPTION_FAILED", "message": f"Local speech recognition failed ({type(error).__name__})."}) from error
    registry.record_latency("speech", elapsed_ms)
    return SpeechResponse(transcript=transcript, language=language, model=speech_engine.model_path.name,
                          backend="CTranslate2 · CPU", simulated=False)


@app.post("/manuals/ingest", response_model=IngestResponse)
async def manuals_ingest(file: UploadFile = File(...)) -> IngestResponse:
    filename = file.filename or "manual.pdf"
    sanitized = re.sub(r"[^A-Za-z0-9._ -]", "_", Path(filename).name).strip(" .")[:120]
    if not sanitized or Path(sanitized).suffix.casefold() != ".pdf":
        raise HTTPException(status_code=415, detail={"code": "UNSUPPORTED_FILE", "message": "Only PDF manuals are accepted."})
    payload = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(payload) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail={"code": "FILE_TOO_LARGE", "message": f"PDF exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)} MB."})
    if not payload.startswith(b"%PDF-"):
        raise HTTPException(status_code=415, detail={"code": "INVALID_PDF", "message": "File signature is not a PDF."})
    try:
        pages, ocr_pages = await asyncio.to_thread(extract_pdf_pages, payload)
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=422, detail={"code": "PDF_PARSE_FAILED", "message": f"Could not parse PDF: {type(error).__name__}."}) from error
    source_hash = hashlib.sha256(payload).hexdigest()
    document_id = f"manual_{source_hash[:16]}"
    full_text = "\n".join(page_text for _, page_text in pages)
    model_match = re.search(r"\bACM-4200\b", full_text, flags=re.IGNORECASE)
    equipment_model = "DemoTech ACM-4200" if model_match else None
    indexed_pages, chunks_count = await asyncio.to_thread(insert_manual_document, document_id, sanitized, source_hash, equipment_model, pages)
    clear_retrieval_cache()
    if embedding_index.state == "READY":
        await asyncio.to_thread(embedding_index.embed_document, document_id)
    warnings = []
    if ocr_pages:
        warnings.append(f"Local OCR extracted text from scanned source pages: {', '.join(map(str, ocr_pages[:20]))}.")
    empty_pages = [number for number, text in pages if not text]
    if empty_pages:
        warnings.append(f"Pages {', '.join(map(str, empty_pages[:20]))} contain no extractable text and remain page-preserved; local OCR found no text or is unavailable.")
    return IngestResponse(document_id=document_id, document_name=sanitized, source_hash=source_hash,
                          pages=len(pages), indexed_pages=indexed_pages, chunks=chunks_count, warnings=warnings)


@app.get("/manuals", response_model=list[ManualSummary])
async def manuals_list() -> list[dict[str, Any]]:
    return list_manuals()


@app.get("/manuals/{document_id}/pages/{page}")
async def manuals_page(document_id: str, page: int) -> dict[str, Any]:
    result = get_page(document_id, page)
    if result is None:
        raise HTTPException(status_code=404, detail={"code": "PAGE_NOT_FOUND", "message": "Manual page was not found."})
    return result


@app.post("/retrieve", response_model=RetrieveResponse)
async def retrieve_manual_evidence(request: RetrieveRequest) -> RetrieveResponse:
    started = time.perf_counter()
    results = await asyncio.to_thread(retrieve_local, request.query, request.equipment_model, request.top_k)
    registry.record_latency("retrieval", (time.perf_counter() - started) * 1000)
    return RetrieveResponse(query=request.query, evidence=results,
                            retrieval="hybrid_rrf" if embedding_index.state == "READY" else "sqlite_fts5")


@app.post("/diagnose", response_model=DiagnosisResponse)
async def diagnose(request: DiagnoseRequest) -> DiagnosisResponse:
    query = " ".join([request.question, *request.observations])
    if request.evidence_ids:
        evidence = await asyncio.to_thread(get_evidence_by_ids, request.evidence_ids)
    else:
        evidence = await asyncio.to_thread(retrieve_local, query, request.equipment_model, 5)
    finding, explanation = supported_finding(query, evidence)
    if not evidence:
        return DiagnosisResponse(status="insufficient_evidence", finding=None, explanation=explanation, evidence=[], unsupported_claims=[])
    if not request.image_base64 and not finding:
        return DiagnosisResponse(status="insufficient_evidence", finding=None, explanation=explanation, evidence=evidence, unsupported_claims=[])
    model_detail = await asyncio.to_thread(vlm_engine.load)
    if model_detail["state"] == "READY":
        image_bytes = None
        if request.image_base64:
            encoded = request.image_base64.partition(",")[2] if "," in request.image_base64 else request.image_base64
            try:
                image_bytes = base64.b64decode(encoded, validate=True)
            except (ValueError, binascii.Error) as error:
                raise HTTPException(status_code=422, detail={"code": "INVALID_IMAGE", "message": "Diagnosis image must be base64 encoded."}) from error
            if not image_bytes or len(image_bytes) > 20 * 1024 * 1024:
                raise HTTPException(status_code=413, detail={"code": "IMAGE_TOO_LARGE", "message": "Diagnosis images must be under 20 MB."})
        evidence_payload = [item.model_dump() for item in evidence]
        try:
            vlm_result = await asyncio.to_thread(
                vlm_engine.infer, request.question, request.observations, evidence_payload,
                image_bytes, request.image_mime_type,
            )
        except ModelUnavailableError:
            vlm_result = None
        if vlm_result:
            validated = validate_grounded_response(vlm_result.get("raw"), evidence_payload)
            registry.record_latency("reasoning", float(vlm_result["latency_ms"]))
            if validated:
                return DiagnosisResponse(
                    status="supported_summary", finding=finding or "Manual-grounded response",
                    explanation=validated["answer"], evidence=evidence, unsupported_claims=[],
                    model=str(vlm_result["model"]), answer_origin="local_vlm_validated",
                    visual_observation=validated["visual_observation"], evidence_coverage=validated["evidence_coverage"],
                )
    if not finding:
        return DiagnosisResponse(status="insufficient_evidence", finding=None, explanation=explanation, evidence=evidence, unsupported_claims=[])
    return DiagnosisResponse(status="supported_summary", finding=finding, explanation=explanation, evidence=evidence, unsupported_claims=[])


@app.post("/procedure", response_model=ProcedureResponse)
async def procedure(request: ProcedureRequest) -> ProcedureResponse:
    evidence = await asyncio.to_thread(get_evidence_by_ids, request.evidence_ids)
    if not evidence:
        return ProcedureResponse(status="insufficient_evidence", steps=[], safety_notice="No traceable manual evidence is available; no procedure was generated.")
    fault_evidence = next((item for item in evidence if "e07" in item.text.casefold() and "feedback" in item.text.casefold()), None)
    if not fault_evidence:
        return ProcedureResponse(status="insufficient_evidence", steps=[], safety_notice="The selected source passages do not support the E07 visual-check sequence.")
    safe_source = await asyncio.to_thread(get_page, fault_evidence.document_id, 8)
    checklist_source = await asyncio.to_thread(get_page, fault_evidence.document_id, 116)
    if not safe_source or "site-approved isolation" not in safe_source["text"].casefold():
        return ProcedureResponse(status="blocked", steps=[], safety_notice="The required safety source could not be verified, so the procedure is blocked.")
    source_document = fault_evidence.document_name
    page_text = fault_evidence.text.casefold()
    if "motor relay k2" not in page_text or "connector seating" not in page_text:
        return ProcedureResponse(status="blocked", steps=[], safety_notice="Required source language for the visual checks is missing; no candidate steps were generated.")
    steps = [
        ProcedureStep(index=1, action="Stop the equipment and follow the applicable site-approved isolation and verification procedure. Confirm the safe state before service access.", reason="The manual's safety section requires technician-confirmed safe state; LocalFix cannot verify isolation.", safety_level="restricted", requires_acknowledgement=True, source_document_id=fault_evidence.document_id, source_document=source_document, source_page=8, section="Safety — required safe service state"),
        ProcedureStep(index=2, action="Visually observe the motor relay K2 indicator and record its visible state.", reason="Section 4.2 lists this as a limited visual observation for E07.", safety_level="caution", requires_acknowledgement=False, source_document_id=fault_evidence.document_id, source_document=source_document, source_page=84, section=fault_evidence.section),
        ProcedureStep(index=3, action="Inspect the external connector seating for visible condition only; stop if further access is required.", reason="Section 4.2 names connector seating as a visual check and excludes removal or electrical testing.", safety_level="caution", requires_acknowledgement=False, source_document_id=fault_evidence.document_id, source_document=source_document, source_page=84, section=fault_evidence.section),
        ProcedureStep(index=4, action="Record observations and the final result in the service case.", reason="The service checklist requires observations and source references to be preserved.", safety_level="routine", requires_acknowledgement=False, source_document_id=fault_evidence.document_id, source_document=source_document, source_page=116 if checklist_source else 84, section="Service checklist · Section 8.1"),
    ]
    for step in steps:
        source_page = await asyncio.to_thread(get_page, step.source_document_id, step.source_page)
        decision = safety_gate(step.action, source_backed=bool(source_page and source_page["text"]), acknowledgement=False)
        if not decision.allowed and not decision.requires_acknowledgement:
            return ProcedureResponse(status="blocked", steps=[], safety_notice=decision.message)
        step.safety_level = decision.classification
        step.requires_acknowledgement = decision.requires_acknowledgement
    return ProcedureResponse(status="ready", steps=steps, safety_notice="Fictional training material. Technician confirmation is required before the restricted step; follow applicable site procedures.")


@app.post("/cases", response_model=CaseResponse, status_code=201)
async def cases_create(request: CaseCreate) -> CaseResponse:
    return await asyncio.to_thread(create_case, request)


@app.get("/cases", response_model=CaseListResponse)
async def cases_list(q: str | None = Query(default=None, max_length=200), limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0)) -> CaseListResponse:
    items, total = await asyncio.to_thread(list_cases, q, limit, offset)
    return CaseListResponse(items=items, total=total)


@app.get("/cases/{case_id}", response_model=CaseResponse)
async def cases_get(case_id: str) -> CaseResponse:
    result = await asyncio.to_thread(get_case, case_id)
    if result is None:
        raise HTTPException(status_code=404, detail={"code": "CASE_NOT_FOUND", "message": "Case was not found."})
    return result


@app.post("/reports/generate")
async def reports_generate(request: ReportRequest) -> Response:
    case = await asyncio.to_thread(get_case, request.case_id)
    if case is None:
        raise HTTPException(status_code=404, detail={"code": "CASE_NOT_FOUND", "message": "Case was not found."})
    runtime = await registry.runtime_payload()
    payload = report_payload(case, runtime)
    safe_id = re.sub(r"[^A-Za-z0-9_-]", "_", case.case_id)
    if request.format == "pdf":
        output = await asyncio.to_thread(pdf_report, payload)
        return Response(content=output, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="LocalFix_{safe_id}.pdf"'})
    if request.format == "markdown":
        return Response(content=markdown_report(payload), media_type="text/markdown; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="LocalFix_{safe_id}.md"'})
    return Response(content=json.dumps(payload, ensure_ascii=False, indent=2), media_type="application/json", headers={"Content-Disposition": f'attachment; filename="LocalFix_{safe_id}.json"'})


@app.post("/benchmark/run", response_model=BenchmarkResponse)
async def benchmark_run(request: BenchmarkRequest) -> BenchmarkResponse:
    started_at = datetime.now(UTC).isoformat(timespec="seconds")
    results: list[BenchmarkResult] = []
    for stage in request.stages:
        if stage == "retrieval":
            samples: list[float] = []
            for _ in range(request.repeats):
                started = time.perf_counter()
                await asyncio.to_thread(retrieve_local, "E07 motor feedback", "DemoTech ACM-4200", 5)
                samples.append((time.perf_counter() - started) * 1000)
            ordered = sorted(samples)
            hybrid = embedding_index.state == "READY"
            results.append(BenchmarkResult(operation=stage, available=True,
                                           provider="FastEmbed + SQLite FTS5 · CPU" if hybrid else "SQLite FTS5 · CPU",
                                           model=embedding_index.model_name if hybrid else None,
                                           benchmark_kind="hybrid_semantic_retrieval" if hybrid else "fts5_keyword_retrieval",
                                           samples_ms=samples,
                                           statistics_ms={"mean": statistics.fmean(samples), "median": statistics.median(samples),
                                                          "p95": ordered[max(0, int(.95 * len(ordered) + .5) - 1)], "min": min(samples), "max": max(samples)},
                                           performance_claim_eligible=True))
            continue
        if stage == "ocr":
            if ocr_engine.state != "READY":
                results.append(BenchmarkResult(operation=stage, available=False, provider=None, model=None,
                                               error="Local OCR is not installed; no benchmark numbers were fabricated."))
                continue
            try:
                image_bytes = decode_benchmark_image(request.image_base64)
                _, warmup_ms = await asyncio.to_thread(ocr_engine.infer, image_bytes)
                samples = []
                for _ in range(request.repeats):
                    _, elapsed_ms = await asyncio.to_thread(ocr_engine.infer, image_bytes)
                    samples.append(elapsed_ms)
                results.append(build_benchmark_result(
                    stage, samples, "ONNX Runtime · CPU", "RapidOCR PP-OCRv6 small",
                    "ocr_local_image_fixture", cold_start_ms=ocr_engine.load_ms, warmup_ms=warmup_ms,
                ))
            except Exception as error:
                results.append(BenchmarkResult(operation=stage, available=False, provider="ONNX Runtime · CPU",
                                               model="RapidOCR PP-OCRv6 small",
                                               error=f"{type(error).__name__}: {error}"))
            continue
        if stage == "speech":
            if speech_engine.state != "READY":
                results.append(BenchmarkResult(operation=stage, available=False, provider=None, model=None,
                                               error="Local speech model is not installed; no benchmark numbers were fabricated."))
                continue
            if not request.audio_base64:
                results.append(BenchmarkResult(operation=stage, available=False, provider="CTranslate2 · CPU",
                                               model=speech_engine.model_path.name, benchmark_kind="local_audio_fixture_required",
                                               error="Choose a local audio sample in the runtime benchmark panel; audio is sent only to the loopback backend."))
                continue
            try:
                audio_bytes = decode_benchmark_audio(request.audio_base64)
                _, _, warmup_ms = await asyncio.to_thread(speech_engine.transcribe, audio_bytes, request.audio_content_type)
                samples = []
                for _ in range(request.repeats):
                    _, _, elapsed_ms = await asyncio.to_thread(speech_engine.transcribe, audio_bytes, request.audio_content_type)
                    samples.append(elapsed_ms)
                results.append(build_benchmark_result(
                    stage, samples, "CTranslate2 · CPU", speech_engine.model_path.name,
                    "asr_local_audio_fixture", cold_start_ms=speech_engine.load_ms, warmup_ms=warmup_ms,
                ))
            except Exception as error:
                results.append(BenchmarkResult(operation=stage, available=False, provider="CTranslate2 · CPU",
                                               model=speech_engine.model_path.name,
                                               error=f"{type(error).__name__}: {error}"))
            continue
        if stage == "vision":
            adapter = registry.adapters.get("vision")
            if adapter is None or adapter.state != "READY":
                results.append(BenchmarkResult(operation=stage, available=False, provider=None, model=None,
                                               error="A compatible task-ready local detector is not installed."))
                continue
            if not request.image_base64:
                results.append(BenchmarkResult(operation=stage, available=False, provider=adapter.backend,
                                               model=adapter.model_name, benchmark_kind="local_image_fixture_required",
                                               error="Choose a local equipment image in the runtime benchmark panel."))
                continue
            try:
                image_bytes = decode_benchmark_image(request.image_base64)
                await adapter.detect_image(image_bytes)
                warmup_ms = adapter.last_latency_ms
                samples = []
                for _ in range(request.repeats):
                    await adapter.detect_image(image_bytes)
                    samples.append(float(adapter.last_latency_ms or 0.0))
                results.append(build_benchmark_result(
                    stage, samples, adapter.backend, adapter.model_name, "detector_local_image_fixture",
                    cold_start_ms=adapter.started_at_ms, warmup_ms=warmup_ms,
                ))
            except Exception as error:
                results.append(BenchmarkResult(operation=stage, available=False, provider=adapter.backend,
                                               model=adapter.model_name, error=f"{type(error).__name__}: {error}"))
            continue
        if stage == "reasoning":
            vlm_status = await asyncio.to_thread(vlm_engine.load)
            if vlm_status["state"] != "READY":
                results.append(BenchmarkResult(operation=stage, available=False, provider=None,
                                               model=None, benchmark_kind="local_vlm_image_manual_query",
                                               error="Local VLM service/model is not ready; no benchmark numbers were fabricated."))
                continue
            if not request.image_base64:
                results.append(BenchmarkResult(operation=stage, available=False, provider="Ollama · loopback local runtime",
                                               model=vlm_engine.model_name, benchmark_kind="local_image_fixture_required",
                                               error="Choose a local equipment image for the image-plus-manual VLM benchmark."))
                continue
            try:
                image_bytes = decode_benchmark_image(request.image_base64)
                evidence = await asyncio.to_thread(retrieve_local, "E07 motor feedback relay", "DemoTech ACM-4200", 5)
                if not evidence:
                    raise ValueError("No local manual evidence is indexed for the VLM benchmark.")
                evidence_payload = [item.model_dump() for item in evidence]
                warmup = await asyncio.to_thread(
                    vlm_engine.infer, "What does E07 mean? Summarize only what these manual passages support.",
                    [], evidence_payload, image_bytes, "image/jpeg",
                )
                samples: list[float] = []
                throughputs: list[float] = []
                first_token_samples: list[float] = []
                validated_runs = 0
                for _ in range(request.repeats):
                    measured = await asyncio.to_thread(
                        vlm_engine.infer, "What does E07 mean? Summarize only what these manual passages support.",
                        [], evidence_payload, image_bytes, "image/jpeg",
                    )
                    samples.append(float(measured["latency_ms"]))
                    if measured.get("tokens_per_second") is not None:
                        throughputs.append(float(measured["tokens_per_second"]))
                    if measured.get("first_token_ms") is not None:
                        first_token_samples.append(float(measured["first_token_ms"]))
                    if validate_grounded_response(measured.get("raw"), evidence_payload):
                        validated_runs += 1
                benchmark = build_benchmark_result(
                    stage, samples, "Ollama · loopback local runtime", vlm_engine.model_name,
                    "vlm_image_plus_manual_local_fixture", cold_start_ms=warmup.get("model_load_ms"),
                    warmup_ms=float(warmup["latency_ms"]),
                )
                benchmark.tokens_per_second = statistics.fmean(throughputs) if throughputs else None
                benchmark.first_token_samples_ms = first_token_samples
                benchmark.first_token_latency_ms = statistics.fmean(first_token_samples) if first_token_samples else None
                benchmark.evidence_validated_runs = validated_runs
                results.append(benchmark)
            except Exception as error:
                results.append(BenchmarkResult(operation=stage, available=False,
                                               provider="Ollama · loopback local runtime", model=vlm_engine.model_name,
                                               benchmark_kind="vlm_image_plus_manual_local_fixture",
                                               error=f"{type(error).__name__}: {error}"))
            continue
        adapter = registry.adapters.get(stage)
        if adapter is None or adapter.state != "READY":
            results.append(BenchmarkResult(operation=stage, available=False, provider=None, model=None,
                                           error="Model not installed or unavailable; no benchmark numbers were fabricated."))
            continue
        try:
            measurement = await adapter.benchmark(request.repeats)
            results.append(BenchmarkResult(operation=stage, available=True, provider=adapter.backend,
                                           model=adapter.model_name, benchmark_kind=measurement["benchmark_kind"],
                                           samples_ms=measurement["samples_ms"], statistics_ms=measurement["statistics_ms"],
                                           cold_start_ms=adapter.started_at_ms, warmup_ms=adapter.last_latency_ms,
                                           performance_claim_eligible=measurement["performance_claim_eligible"]))
        except Exception as error:
            results.append(BenchmarkResult(operation=stage, available=False, provider=adapter.backend,
                                           model=adapter.model_name, error=f"{type(error).__name__}: {error}"))
    return BenchmarkResponse(started_at=started_at, finished_at=datetime.now(UTC).isoformat(timespec="seconds"),
                             repeats=request.repeats, results=results, system_ram_mb=(await registry.runtime_payload())["ramMb"],
                             network_requests=0)


def decode_benchmark_image(payload: str | None) -> bytes:
    if payload:
        encoded = payload.partition(",")[2] if "," in payload else payload
        try:
            image_bytes = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error) as error:
            raise ValueError("Benchmark image must be base64 encoded.") from error
        if not image_bytes or len(image_bytes) > 20 * 1024 * 1024:
            raise ValueError("Benchmark images must be under 20 MB.")
        return image_bytes
    # Reproducible synthetic label fixture: useful for latency checks, not OCR accuracy claims.
    from PIL import Image, ImageDraw, ImageFont
    image = Image.new("RGB", (1600, 520), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=100)
    draw.text((70, 45), "DemoTech ACM-4200", fill="black", font=font)
    draw.text((70, 200), "FAULT E07", fill="black", font=font)
    draw.text((70, 355), "SERIAL SN-823919", fill="black", font=font)
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def decode_benchmark_audio(payload: str) -> bytes:
    encoded = payload.partition(",")[2] if "," in payload else payload
    try:
        audio_bytes = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as error:
        raise ValueError("Benchmark audio must be base64 encoded.") from error
    if not audio_bytes or len(audio_bytes) > 25 * 1024 * 1024:
        raise ValueError("Benchmark audio must be under 25 MB.")
    return audio_bytes


def build_benchmark_result(stage: str, samples: list[float], provider: str, model: str,
                           benchmark_kind: str, *, cold_start_ms: float | None,
                           warmup_ms: float | None) -> BenchmarkResult:
    ordered = sorted(samples)
    return BenchmarkResult(
        operation=stage, available=True, provider=provider, model=model,
        benchmark_kind=benchmark_kind, samples_ms=samples,
        statistics_ms={"mean": statistics.fmean(samples), "median": statistics.median(samples),
                       "p95": ordered[max(0, int(.95 * len(ordered) + .5) - 1)],
                       "min": min(samples), "max": max(samples)},
        cold_start_ms=cold_start_ms, warmup_ms=warmup_ms,
        performance_claim_eligible=True,
    )


@app.post("/runtime/models/reload", response_model=RuntimeActionResponse)
async def runtime_reload() -> RuntimeActionResponse:
    await registry.reload()
    reasoning = registry.local_services.get("reasoning", {})
    vlm_engine.configure(reasoning.get("model", "qwen3-vl:2b-instruct-q4_K_M"), reasoning.get("url", "http://127.0.0.1:11434"))
    await asyncio.gather(
        asyncio.to_thread(ocr_engine.load),
        asyncio.to_thread(speech_engine.load),
        asyncio.to_thread(embedding_index.load),
        asyncio.to_thread(vlm_engine.load),
    )
    if embedding_index.state == "READY":
        await asyncio.to_thread(embedding_index.embed_unindexed)
    payload = await runtime_status()
    return RuntimeActionResponse(ok=True, message="Model manifest reloaded; only configured local assets were inspected.", runtime=payload)


@app.delete("/runtime/cache", response_model=RuntimeActionResponse)
async def runtime_clear_cache() -> RuntimeActionResponse:
    count = clear_retrieval_cache()
    payload = await runtime_status()
    return RuntimeActionResponse(ok=True, message=f"Cleared {count} LocalFix retrieval cache entries.", runtime=payload)
