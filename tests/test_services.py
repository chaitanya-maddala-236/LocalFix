from __future__ import annotations

from pathlib import Path

from app.models.base import ModelRegistry
from app.services.retrieval import retrieve, supported_finding
from app.services.safety import classify_safety, safety_gate
from app.services.vision import classify_ocr_text, normalize_ocr_text


def test_ocr_normalization_preserves_fault_and_asset_tokens():
    normalized = normalize_ocr_text("acm 4200   sn 823919   e 07")
    assert "ACM-4200" in normalized
    assert "SN-823919" in normalized
    assert "E07" in normalized
    values = classify_ocr_text("ACM 4200 SN 823919 E 07")
    assert {item["kind"] for item in values} == {"model", "serial", "fault"}


def test_retrieval_ranks_manual_evidence_and_preserves_source_page(api_client):
    results = retrieve("Why is E07 showing motor feedback?", "DemoTech ACM-4200", 5)
    assert results
    assert results[0].page == 84
    assert results[0].document_name == "DemoTech ACM-4200 Service Manual 2026"
    assert results[0].source_hash


def test_retrieval_model_filter_does_not_mix_equipment(api_client):
    assert retrieve("E07 motor feedback", "Other-900", 5) == []


def test_evidence_validator_will_not_support_unrelated_finding(api_client):
    evidence = retrieve("E07 motor feedback", "DemoTech ACM-4200", 5)
    finding, _ = supported_finding("What is E99?", evidence)
    assert finding is None
    supported, _ = supported_finding("Explain E07 motor feedback", evidence)
    assert supported == "Motor-control feedback mismatch (E07)"


def test_safety_gate_requires_ack_for_restricted_action():
    action = "Stop the equipment and follow the site-approved isolation procedure."
    assert classify_safety(action) == "restricted"
    assert not safety_gate(action, source_backed=True, acknowledgement=False).allowed
    assert safety_gate(action, source_backed=True, acknowledgement=True).allowed
    assert not safety_gate("Inspect relay K2", source_backed=False, acknowledgement=True).allowed


def test_runtime_status_never_claims_missing_npu_model_is_active(tmp_path: Path):
    registry = ModelRegistry(Path(__file__).resolve().parents[1])
    import asyncio
    status = asyncio.run(registry.runtime_payload())
    assert status["npu"] == "unavailable"
    assert status["models"]["vision"] == "missing"
    assert status["ramMb"] is None or status["ramMb"] > 0


def test_initialize_database_keeps_source_page_numbers(api_client):
    page = api_client.get("/manuals/manual_acm4200_demo/pages/84")
    assert page.status_code == 200
    assert page.json()["page"] == 84
    assert "E07" in page.json()["text"]
