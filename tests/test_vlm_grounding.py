from __future__ import annotations

import pytest
import httpx

from app.services.local_vlm import LocalVLMEngine, validate_grounded_response


EVIDENCE = [{
    "id": "ev_84", "text": "Fault E07 indicates a motor feedback signal mismatch. Inspect relay K2 status and connector seating.",
    "page": 84, "section": "4.2",
}]


def test_vlm_summary_requires_known_citation_and_source_overlap() -> None:
    accepted = validate_grounded_response({
        "answer": "E07 indicates a motor feedback signal mismatch.",
        "cited_evidence_ids": ["ev_84"],
        "visual_observation": "A control display is visible.",
    }, EVIDENCE)
    assert accepted is not None
    assert accepted["cited_evidence_ids"] == ["ev_84"]
    assert accepted["evidence_coverage"] >= 0.5


def test_vlm_summary_rejects_unknown_citations_and_unsafe_actions() -> None:
    assert validate_grounded_response({
        "answer": "E07 indicates a motor feedback signal mismatch.", "cited_evidence_ids": ["invented"],
    }, EVIDENCE) is None
    assert validate_grounded_response({
        "answer": "Disconnect the controller to inspect the relay.", "cited_evidence_ids": ["ev_84"],
    }, EVIDENCE) is None


def test_vlm_refuses_remote_endpoints() -> None:
    with pytest.raises(ValueError, match="loopback only"):
        LocalVLMEngine(base_url="https://example.com")


def test_vlm_does_not_treat_a_different_tag_as_the_configured_model(monkeypatch: pytest.MonkeyPatch) -> None:
    class TagsResponse:
        def raise_for_status(self) -> None:
            pass

        @staticmethod
        def json() -> dict[str, object]:
            return {"models": [{"name": "qwen3-vl:2b", "details": {"quantization_level": "Q4_K_M"}}]}

    monkeypatch.setattr(httpx, "get", lambda *args, **kwargs: TagsResponse())
    engine = LocalVLMEngine("qwen3-vl:2b-instruct-q4_K_M")
    assert engine.load()["state"] == "MODEL_REQUIRED"
