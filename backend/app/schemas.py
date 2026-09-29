from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: Literal["ready", "degraded"]
    version: str
    database: Literal["ready", "error"]


class RuntimeStatus(BaseModel):
    mode: Literal["local", "demo"] = "local"
    simulated: bool = False
    backend: str
    npu: Literal["active", "unavailable", "unknown"]
    network: Literal["offline", "online", "unknown"]
    network_detail: str
    models: dict[str, Literal["ready", "missing", "unavailable"]]
    model_details: dict[str, dict[str, Any]]
    latencyMs: dict[str, float | None]
    ramMb: float | None
    precision: dict[str, str | None]


class VisionRequest(BaseModel):
    image_base64: str | None = Field(default=None, max_length=30_000_000)
    demo_scene: str | None = None


class Detection(BaseModel):
    label: str
    confidence: float = Field(ge=0, le=1)
    box: tuple[float, float, float, float]


class VisionResponse(BaseModel):
    detections: list[Detection]
    model: str | None
    backend: str | None
    simulated: bool = False


class OCRRequest(BaseModel):
    image_base64: str | None = Field(default=None, max_length=30_000_000)


class OCRValue(BaseModel):
    text: str
    normalized: str
    kind: Literal["model", "serial", "fault", "other"]
    box: tuple[float, float, float, float] | None = None


class OCRResponse(BaseModel):
    values: list[OCRValue]
    model: str | None
    backend: str | None
    simulated: bool = False


class SpeechRequest(BaseModel):
    audio_base64: str = Field(min_length=16, max_length=40_000_000)
    content_type: str = "audio/wav"


class SpeechResponse(BaseModel):
    transcript: str
    language: str | None = None
    model: str
    backend: str
    simulated: bool = False


class IngestResponse(BaseModel):
    document_id: str
    document_name: str
    source_hash: str
    pages: int
    indexed_pages: int
    chunks: int
    warnings: list[str] = Field(default_factory=list)


class ManualSummary(BaseModel):
    document_id: str
    document_name: str
    equipment_model: str | None
    page_count: int
    indexed_at: str


class Evidence(BaseModel):
    id: str
    document_id: str
    document_name: str
    page: int
    section: str
    equipment_model: str | None
    text: str
    retrieval_score: float
    source_hash: str
    source_type: Literal["manual", "observation"] = "manual"


class RetrieveRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    equipment_model: str | None = None
    top_k: int = Field(default=5, ge=1, le=20)


class RetrieveResponse(BaseModel):
    query: str
    evidence: list[Evidence]
    retrieval: str = "sqlite_fts5"


class DiagnoseRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    equipment_model: str | None = None
    observations: list[str] = Field(default_factory=list, max_length=30)
    evidence_ids: list[str] = Field(default_factory=list, max_length=20)


class DiagnosisResponse(BaseModel):
    status: Literal["supported_summary", "insufficient_evidence", "blocked"]
    finding: str | None
    explanation: str
    evidence: list[Evidence]
    unsupported_claims: list[str] = Field(default_factory=list)
    model: str | None = None
    simulated: bool = False


class ProcedureRequest(BaseModel):
    equipment_model: str = "DemoTech ACM-4200"
    diagnosis: str
    evidence_ids: list[str] = Field(min_length=1, max_length=20)
    case_id: str | None = None


class ProcedureStep(BaseModel):
    index: int
    action: str
    reason: str
    safety_level: Literal["routine", "caution", "restricted"]
    requires_acknowledgement: bool
    source_document_id: str
    source_document: str
    source_page: int
    section: str


class ProcedureResponse(BaseModel):
    status: Literal["ready", "insufficient_evidence", "blocked"]
    steps: list[ProcedureStep]
    safety_notice: str
    simulated: bool = False


class CaseStep(BaseModel):
    index: int
    action: str
    safety_level: str = "routine"
    completed: bool = False
    source_document_id: str | None = None
    source_page: int | None = None


class CaseCreate(BaseModel):
    equipment_model: str = "DemoTech ACM-4200"
    serial_number: str | None = None
    fault_code: str | None = None
    diagnosis: str | None = None
    status: Literal["In progress", "Resolved"] = "In progress"
    technician: str = "Local Technician"
    notes: str = ""
    resolution: str | None = None
    evidence: list[Evidence] = Field(default_factory=list)
    steps: list[CaseStep] = Field(default_factory=list)
    simulated: bool = False


class CaseResponse(CaseCreate):
    case_id: str
    created_at: str
    updated_at: str


class CaseListResponse(BaseModel):
    items: list[CaseResponse]
    total: int


class ReportRequest(BaseModel):
    case_id: str
    format: Literal["pdf", "markdown", "json"] = "pdf"


class BenchmarkRequest(BaseModel):
    stages: list[str] = Field(default_factory=lambda: ["vision", "ocr", "speech", "retrieval", "reasoning"])
    repeats: int = Field(default=10, ge=10, le=100)


class BenchmarkResult(BaseModel):
    operation: str
    available: bool
    provider: str | None
    model: str | None
    benchmark_kind: str | None = None
    samples_ms: list[float] = Field(default_factory=list)
    statistics_ms: dict[str, float] = Field(default_factory=dict)
    cold_start_ms: float | None = None
    warmup_ms: float | None = None
    performance_claim_eligible: bool = False
    error: str | None = None


class BenchmarkResponse(BaseModel):
    started_at: str
    finished_at: str
    repeats: int
    results: list[BenchmarkResult]
    system_ram_mb: float | None
    network_requests: int = 0


class RuntimeActionResponse(BaseModel):
    ok: bool
    message: str
    runtime: RuntimeStatus
