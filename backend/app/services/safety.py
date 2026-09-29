from __future__ import annotations

import re
from dataclasses import dataclass


RESTRICTED_ACTION = re.compile(r"\b(energized|voltage|isolate|isolation|open (?:the )?(?:enclosure|cover|cabinet)|remove|disconnect|bypass|electrical test|continuity test)\b", re.IGNORECASE)
CAUTION_ACTION = re.compile(r"\b(inspect|check|observe|verify|confirm|visual)\b", re.IGNORECASE)


@dataclass(frozen=True)
class SafetyDecision:
    allowed: bool
    classification: str
    requires_acknowledgement: bool
    message: str


def classify_safety(action: str) -> str:
    if RESTRICTED_ACTION.search(action):
        return "restricted"
    if CAUTION_ACTION.search(action):
        return "caution"
    return "routine"


def safety_gate(action: str, source_backed: bool, acknowledgement: bool) -> SafetyDecision:
    level = classify_safety(action)
    if not source_backed:
        return SafetyDecision(False, level, level == "restricted", "No source supports this step; blocked.")
    if level == "restricted" and not acknowledgement:
        return SafetyDecision(False, level, True, "Technician acknowledgement is required before displaying this restricted step as actionable.")
    return SafetyDecision(True, level, level == "restricted", "Allowed for review with the cited source and technician controls.")
