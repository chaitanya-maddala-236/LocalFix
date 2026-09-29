from __future__ import annotations

import io

import fitz
from pydantic import ValidationError
import pytest

from app.schemas import BenchmarkRequest


def test_health_and_runtime_are_structured(api_client):
    health = api_client.get("/health")
    runtime = api_client.get("/runtime/status")
    assert health.status_code == 200 and health.json()["database"] == "ready"
    assert runtime.status_code == 200
    assert runtime.json()["simulated"] is False
    assert runtime.json()["npu"] == "unavailable"


def test_manual_ingestion_then_retrieval_preserves_pdf_page(api_client):
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((72, 72), "Demo ACM-4200 Fault E07 motor feedback mismatch. Record the displayed code.")
    buffer = io.BytesIO()
    pdf.save(buffer)
    pdf.close()
    response = api_client.post("/manuals/ingest", files={"file": ("field manual.pdf", buffer.getvalue(), "application/pdf")})
    assert response.status_code == 200
    document_id = response.json()["document_id"]
    page_result = api_client.get(f"/manuals/{document_id}/pages/1")
    assert page_result.status_code == 200
    assert page_result.json()["page"] == 1
    retrieval = api_client.post("/retrieve", json={"query": "E07 motor feedback", "equipment_model": "DemoTech ACM-4200"})
    assert retrieval.status_code == 200
    assert retrieval.json()["evidence"][0]["page"] == 1


def test_retrieval_diagnosis_and_procedure_flow_uses_cited_pages(api_client):
    diagnosis = api_client.post("/diagnose", json={"question": "Why is E07 showing motor feedback?", "equipment_model": "DemoTech ACM-4200"})
    assert diagnosis.status_code == 200
    body = diagnosis.json()
    assert body["status"] == "supported_summary"
    assert body["finding"] == "Motor-control feedback mismatch (E07)"
    assert body["evidence"]
    procedure = api_client.post("/procedure", json={"diagnosis": body["finding"], "evidence_ids": [item["id"] for item in body["evidence"]]})
    assert procedure.status_code == 200
    result = procedure.json()
    assert result["status"] == "ready"
    assert result["steps"][0]["safety_level"] == "restricted"
    assert result["steps"][0]["requires_acknowledgement"] is True
    assert [step["source_page"] for step in result["steps"]] == [8, 84, 84, 116]


def test_case_creation_and_report_generation(api_client):
    diagnosis = api_client.post("/diagnose", json={"question": "Explain E07 motor feedback", "equipment_model": "DemoTech ACM-4200"}).json()
    payload = {"equipment_model": "DemoTech ACM-4200", "serial_number": "SN-823919", "fault_code": "E07",
               "diagnosis": diagnosis["finding"], "status": "Resolved", "technician": "Test Technician",
               "notes": "Visual state recorded.", "resolution": "Resolved", "simulated": True,
               "evidence": diagnosis["evidence"], "steps": []}
    created = api_client.post("/cases", json=payload)
    assert created.status_code == 201
    case_id = created.json()["case_id"]
    read = api_client.get(f"/cases/{case_id}")
    assert read.status_code == 200 and len(read.json()["evidence"]) > 0
    report = api_client.post("/reports/generate", json={"case_id": case_id, "format": "pdf"})
    assert report.status_code == 200
    assert report.content.startswith(b"%PDF-")
    assert "attachment" in report.headers["content-disposition"]


def test_invalid_benchmark_repeat_count_is_rejected():
    with pytest.raises(ValidationError):
        BenchmarkRequest(repeats=3)


def test_bad_manual_upload_is_rejected_without_writing(api_client):
    response = api_client.post("/manuals/ingest", files={"file": ("../../unsafe.exe", b"bad", "application/octet-stream")})
    assert response.status_code == 415

