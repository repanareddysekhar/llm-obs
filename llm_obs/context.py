"""
Async-safe context variables for passing observability metadata through the
call stack without threading explicit parameters through every layer.

Usage in the web service (set once per request, before the LLM call):

    from llm_obs.context import set_obs_context
    set_obs_context(conversation_id=str(conv.id))

The SDK providers read these automatically via get_conversation_id().
"""
from __future__ import annotations

from contextvars import ContextVar

_conversation_id_var: ContextVar[str | None] = ContextVar("llm_obs_conv_id", default=None)
_session_id_var: ContextVar[str | None] = ContextVar("llm_obs_session_id", default=None)


def set_obs_context(
    conversation_id: str | None = None,
    session_id: str | None = None,
) -> None:
    """Set per-request observability context. Call once before the LLM call."""
    if conversation_id is not None:
        _conversation_id_var.set(conversation_id)
    if session_id is not None:
        _session_id_var.set(session_id)


def get_conversation_id() -> str | None:
    return _conversation_id_var.get()


def get_session_id() -> str | None:
    return _session_id_var.get()


def clear_obs_context() -> None:
    _conversation_id_var.set(None)
    _session_id_var.set(None)
