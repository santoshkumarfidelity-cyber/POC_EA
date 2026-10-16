"""Prompt-injection detection, evidence sanitization and answer
validation. Document text is always treated as data, never instructions."""

import re

_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+|any\s+)?(previous|prior|above)\s+instructions",
    r"system\s+prompt",
    r"reveal\s+(your\s+)?(secrets|instructions|prompt)",
    r"exfiltrat",
    r"do\s+not\s+follow\s+(your\s+)?(rules|instructions)",
    r"you\s+are\s+now\s+",
    r"forget\s+(everything|all)",
    r"override\s+(your\s+)?(instructions|rules|policy)",
]
_COMPILED = [re.compile(p, re.IGNORECASE) for p in _INJECTION_PATTERNS]


def detect_prompt_injection(text: str) -> list[str]:
    hits = []
    for pat, rx in zip(_INJECTION_PATTERNS, _COMPILED):
        if rx.search(text or ""):
            hits.append(pat)
    return hits


def sanitize_evidence(items: list[dict]) -> tuple[list[dict], list[str]]:
    """Drop evidence whose content contains embedded instructions and
    return warnings describing what was blocked."""
    clean, warnings = [], []
    for item in items:
        hits = detect_prompt_injection(
            " ".join([item.get("title", ""), item.get("content_text", ""),
                      item.get("excerpt", "")]))
        if hits:
            warnings.append(
                f"Blocked evidence {item.get('title', item.get('artifact_id'))!r}: "
                f"injection patterns detected ({len(hits)})")
            continue
        clean.append(item)
    return clean, warnings


def validate_answer(answer: str, citations: list) -> bool:
    """Grounded answers require nonempty text and at least one citation."""
    return bool(answer and answer.strip()) and len(citations) >= 1
