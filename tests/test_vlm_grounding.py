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


def test_geniex_refuses_remote_endpoints(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOCALFIX_VLM_PROVIDER", "geniex")
    monkeypatch.setenv("LOCALFIX_VLM_URL", "https://example.com/v1")
    with pytest.raises(ValueError, match="loopback only"):
        LocalVLMEngine("Qwen3-VL-4B-Instruct")


def test_geniex_discovers_configured_local_model_and_streams_multimodal_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import base64
    import json

    monkeypatch.setenv("LOCALFIX_VLM_PROVIDER", "geniex")
    monkeypatch.setenv("LOCALFIX_VLM_MODEL", "Qwen3-VL-4B-Instruct")

    class ModelsResponse:
        def raise_for_status(self) -> None:
            pass

        @staticmethod
        def json() -> dict[str, object]:
            return {"data": [{"id": "Qwen3-VL-4B-Instruct"}]}

    monkeypatch.setattr(httpx, "get", lambda *args, **kwargs: ModelsResponse())
    engine = LocalVLMEngine()
    assert engine.load()["state"] == "READY"

    response_payload = json.dumps({
        "answer": "E07 indicates a motor feedback signal mismatch.",
        "cited_evidence_ids": ["ev_84"],
        "visual_observation": "A display is visible.",
    })
    events = [
        "data: " + json.dumps({"model": "Qwen3-VL-4B-Instruct", "choices": [{"delta": {"content": response_payload[:28]}}]}),
        "data: " + json.dumps({"choices": [{"delta": {"content": response_payload[28:]}}]}),
        "data: " + json.dumps({"choices": [], "usage": {"completion_tokens": 12}}),
        "data: [DONE]",
    ]

    class StreamingResponse:
        def __enter__(self) -> "StreamingResponse":
            return self

        def __exit__(self, *args: object) -> None:
            pass

        def raise_for_status(self) -> None:
            pass

        @staticmethod
        def iter_lines() -> list[str]:
            return events

    captured: dict[str, object] = {}

    def stream(method: str, url: str, **kwargs: object) -> StreamingResponse:
        captured.update(method=method, url=url, **kwargs)
        return StreamingResponse()

    monkeypatch.setattr(httpx, "stream", stream)
    image = b"local demo image"
    result = engine.infer(
        "Why is E07 showing?", [], EVIDENCE, image_bytes=image, mime_type="image/png"
    )

    assert captured["method"] == "POST"
    assert captured["url"] == "http://127.0.0.1:18181/v1/chat/completions"
    request_body = captured["json"]
    user_content = request_body["messages"][1]["content"]
    assert request_body["enable_think"] is False
    assert user_content[1]["image_url"]["url"] == (
        "data:image/png;base64," + base64.b64encode(image).decode("ascii")
    )
    assert result["raw"]["cited_evidence_ids"] == ["ev_84"]
    assert validate_grounded_response(result["raw"], EVIDENCE) is not None
