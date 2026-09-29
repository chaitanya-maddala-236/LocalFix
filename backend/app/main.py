from __future__ import annotations

import asyncio
import hashlib
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
    SpeechRequest, SpeechResponse, VisionRequest, VisionResponse, Detection,
)
from .services.cases import create_case, get_case, list_cases
from .services.reports import markdown_report, pdf_report, report_payload
from .services.retrieval import clear_retrieval_cache, get_evidence_by_ids, get_page, list_manuals, retrieve, supported_finding
from .services.safety import safety_gate

registry = ModelRegistry(PROJECT_ROOT)
MAX_UPLOAD_BYTES = int(os.getenv("LOCALFIX_MAX_UPLOAD_MB", "50")) * 1024 * 1024
logger = logging.getLogger("localfix.operations")
logging.basicConfig(level=os.getenv("LOCALFIX_LOG_LEVEL", "INFO").upper(), format="%(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    await registry.load_all()
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
    return await registry.runtime_payload()


@app.post("/vision/detect", response_model=VisionResponse)
async def vision_detect(request: VisionRequest) -> VisionResponse:
    if request.demo_scene == "acm4200_demo":
        return VisionResponse(model="SIMULATED · no model", backend="DEMO ONLY", simulated=True, detections=[
            Detection(label="motor_relay", confidence=0.0, box=(0.56, 0.47, 0.68, 0.60)),
            Detection(label="display", confidence=0.0, box=(0.29, 0.18, 0.53, 0.37)),
            Detection(label="model_label", confidence=0.0, box=(0.66, 0.17, 0.76, 0.29)),
        ])
    adapter = registry.adapters.get("vision")
    if adapter is None or adapter.state != "READY":
        raise ModelUnavailableError("Vision model is not installed. No detections were fabricated.")
    raise ModelInputError("The configured model needs a model-specific image preprocessor and output decoder before live detection can be enabled.")


@app.post("/vision/ocr", response_model=OCRResponse)
async def vision_ocr(request: OCRRequest) -> OCRResponse:
    if request.image_base64 is None:
        raise HTTPException(status_code=422, detail={"code": "IMAGE_REQUIRED", "message": "Provide an image or use the explicit demo_scene in /vision/detect."})
    adapter = registry.adapters.get("ocr")
    if adapter is None or adapter.state != "READY":
        raise ModelUnavailableError("OCR model is not installed. No text was fabricated.")
    raise ModelInputError("The configured OCR model needs a model-specific image preprocessor and text decoder before live OCR can be enabled.")


@app.post("/speech/transcribe", response_model=SpeechResponse)
async def speech_transcribe(_: SpeechRequest) -> SpeechResponse:
    adapter = registry.adapters.get("speech")
    if adapter is None or adapter.state != "READY":
        raise ModelUnavailableError("Speech model is not installed. Audio was not sent to a remote service.")
    raise ModelInputError("The configured speech model needs a local audio preprocessor and decoder before transcription can be enabled.")


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
        pdf = fitz.open(stream=payload, filetype="pdf")
        if pdf.needs_pass:
            raise HTTPException(status_code=422, detail={"code": "ENCRYPTED_PDF", "message": "Encrypted PDFs are not supported."})
        if pdf.page_count > 500:
            raise HTTPException(status_code=413, detail={"code": "TOO_MANY_PAGES", "message": "Manuals are limited to 500 pages."})
        pages = [(index + 1, page.get_text("text").strip()) for index, page in enumerate(pdf)]
        pdf.close()
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
    warnings = []
    empty_pages = [number for number, text in pages if not text]
    if empty_pages:
        warnings.append(f"Pages {', '.join(map(str, empty_pages[:20]))} contain no extractable text and remain page-preserved; local OCR preprocessing/model is not configured.")
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
    results = await asyncio.to_thread(retrieve, request.query, request.equipment_model, request.top_k)
    registry.record_latency("retrieval", (time.perf_counter() - started) * 1000)
    return RetrieveResponse(query=request.query, evidence=results)


@app.post("/diagnose", response_model=DiagnosisResponse)
async def diagnose(request: DiagnoseRequest) -> DiagnosisResponse:
    query = " ".join([request.question, *request.observations])
    if request.evidence_ids:
        evidence = await asyncio.to_thread(get_evidence_by_ids, request.evidence_ids)
    else:
        evidence = await asyncio.to_thread(retrieve, query, request.equipment_model, 5)
    finding, explanation = supported_finding(query, evidence)
    if not evidence:
        return DiagnosisResponse(status="insufficient_evidence", finding=None, explanation=explanation, evidence=[], unsupported_claims=[])
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
                await asyncio.to_thread(retrieve, "E07 motor feedback", "DemoTech ACM-4200", 5)
                samples.append((time.perf_counter() - started) * 1000)
            ordered = sorted(samples)
            results.append(BenchmarkResult(operation=stage, available=True, provider="SQLite FTS5 · CPU", model=None,
                                           benchmark_kind="local_database_query", samples_ms=samples,
                                           statistics_ms={"mean": statistics.fmean(samples), "median": statistics.median(samples),
                                                          "p95": ordered[max(0, int(.95 * len(ordered) + .5) - 1)], "min": min(samples), "max": max(samples)},
                                           performance_claim_eligible=True))
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


@app.post("/runtime/models/reload", response_model=RuntimeActionResponse)
async def runtime_reload() -> RuntimeActionResponse:
    await registry.reload()
    payload = await registry.runtime_payload()
    return RuntimeActionResponse(ok=True, message="Model manifest reloaded; only configured local assets were inspected.", runtime=payload)


@app.delete("/runtime/cache", response_model=RuntimeActionResponse)
async def runtime_clear_cache() -> RuntimeActionResponse:
    count = clear_retrieval_cache()
    payload = await registry.runtime_payload()
    return RuntimeActionResponse(ok=True, message=f"Cleared {count} LocalFix retrieval cache entries.", runtime=payload)
