"""
Single choke point for outbound LLM sanitization.

All PII redaction before data is sent to an LLM provider happens here.
Call sanitize_messages_for_llm() at the application entry point (stream_chat,
your own code) — not inside individual provider adapters.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .client import ObservabilityClient


def _enabled(obs: "ObservabilityClient | None") -> bool:
    return obs is not None and obs.redact_pii and obs._pii_redact_fn is not None


def sanitize_messages_for_llm(messages: list[dict]) -> list[dict]:
    """Redact PII from a chat messages list before any LLM provider call."""
    from .client import get_active_client
    obs = get_active_client()
    if not _enabled(obs):
        try:
            from .pii import redact_messages
            redacted, _ = redact_messages(messages)
            return redacted
        except ImportError:
            return messages
    import copy
    redacted, _ = obs._pii_redact_fn(copy.deepcopy(messages))
    return redacted


def redact_text(text: str) -> str:
    """Redact PII from a plain string. Respects ObservabilityClient.redact_pii."""
    if not text:
        return text
    from .client import get_active_client
    obs = get_active_client()
    if obs is not None and not obs.redact_pii:
        return text
    try:
        from .pii import redact
        redacted, _ = redact(text)
        return redacted
    except ImportError:
        return text


def sanitize_text_for_llm(text: str) -> str:
    """Redact PII from a plain string before it is sent to an LLM provider."""
    return redact_text(text)
