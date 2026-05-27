from __future__ import annotations

import re
from typing import Any

from .luhn import luhn_valid
from .patterns import PATTERNS, PIIPattern


def _redact_string(text: str) -> tuple[str, dict[str, int]]:
    """Redact PII from a string. Returns (redacted_text, detections_map)."""
    detections: dict[str, int] = {}

    for pii in PATTERNS:
        def replace(m: re.Match, p: PIIPattern = pii) -> str:
            raw = m.group(0)
            # Extra validation for credit cards
            if p.name == "credit_card":
                digits_only = re.sub(r"[\s\-]", "", raw)
                if not (13 <= len(digits_only) <= 19 and luhn_valid(digits_only)):
                    return raw
            detections[p.name] = detections.get(p.name, 0) + 1
            # Support backreferences (e.g. r"\1[REDACTED]") in placeholder
            if r"\1" in p.placeholder:
                return m.expand(p.placeholder)
            return p.placeholder

        text = pii.pattern.sub(replace, text)

    return text, detections


def redact(text: str) -> tuple[str, list[dict[str, int]]]:
    """
    Redact PII from text.
    Returns (redacted_text, [{"type": ..., "count": ...}])
    """
    redacted, det_map = _redact_string(text)
    detections = [{"type": k, "count": v} for k, v in det_map.items()]
    return redacted, detections


def redact_deep(value: Any) -> tuple[Any, list[dict[str, int]]]:
    """Recursively redact PII from nested dicts/lists/strings."""
    all_detections: dict[str, int] = {}

    def _walk(obj: Any) -> Any:
        if isinstance(obj, str):
            result, det_map = _redact_string(obj)
            for k, v in det_map.items():
                all_detections[k] = all_detections.get(k, 0) + v
            return result
        if isinstance(obj, dict):
            return {k: _walk(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_walk(item) for item in obj]
        return obj

    result = _walk(value)
    detections = [{"type": k, "count": v} for k, v in all_detections.items()]
    return result, detections


def redact_messages(messages: list[dict]) -> tuple[list[dict], list[dict[str, int]]]:
    """Redact PII from a chat messages list before sending to an LLM provider."""
    import copy
    return redact_deep(copy.deepcopy(messages))
