from __future__ import annotations

import re


def normalize_ocr_text(text: str) -> str:
    """Normalize spacing and punctuation while keeping uncertain characters intact."""
    normalized = text.upper().replace("\u2010", "-").replace("\u2011", "-").replace("\u2013", "-").replace("\u2014", "-")
    normalized = re.sub(r"\bE\s*[-:]?\s*(\d{2})\b", r"E\1", normalized)
    normalized = re.sub(r"\bACM\s*[- ]?\s*(\d{4})\b", r"ACM-\1", normalized)
    normalized = re.sub(r"\bSN\s*[- ]?\s*([A-Z0-9-]+)", r"SN-\1", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def classify_ocr_text(text: str) -> list[dict[str, str]]:
    normalized = normalize_ocr_text(text)
    results: list[dict[str, str]] = []
    for pattern, kind in ((r"\bACM-\d{4}\b", "model"), (r"\bSN-[A-Z0-9-]+\b", "serial"), (r"\bE\d{2}\b", "fault")):
        results.extend({"text": match, "normalized": match, "kind": kind} for match in re.findall(pattern, normalized))
    if not results and normalized:
        results.append({"text": text.strip(), "normalized": normalized, "kind": "other"})
    return results
