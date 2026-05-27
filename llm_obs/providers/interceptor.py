"""
Provider instrumentation registration.

Sanitization does NOT happen here — see guard.py (stream_chat entry point)
or call sanitize_messages_for_llm() before direct SDK usage.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..client import ObservabilityClient


def install_provider_interceptors(obs: "ObservabilityClient") -> list[str]:
    """Register observability patches on installed LLM SDKs."""
    from .openai import patch_openai_class
    from .anthropic import patch_anthropic_class
    from .gemini import patch_gemini_class
    from .bedrock import patch_bedrock_client

    patched = []
    if patch_openai_class(obs):
        patched.append("openai")
    if patch_anthropic_class(obs):
        patched.append("anthropic")
    if patch_gemini_class(obs):
        patched.append("gemini")
    if patch_bedrock_client(obs):
        patched.append("bedrock")
    return patched
