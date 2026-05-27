from .client import ObservabilityClient
from .guard import redact_text
from .context import set_obs_context, get_conversation_id, get_session_id, clear_obs_context
from .streaming import stream_chat, available_providers
from .discovery import discover_from_env, detect_provider, DiscoveredProvider
from .providers.openai import wrap_openai
from .providers.anthropic import wrap_anthropic
from .providers.gemini import wrap_gemini
from .providers.bedrock import wrap_bedrock
from .providers.huggingface import wrap_huggingface

__all__ = [
    # ── Primary interface ──────────────────────────────────────────
    "ObservabilityClient",   # init + auto_instrument — all you need in your app
    "redact_text",           # PII redaction helper (runs in the client process)
    "stream_chat",           # unified streaming across all providers
    "available_providers",   # check which providers are configured
    # ── Context (per-request metadata) ────────────────────────────
    "set_obs_context",
    "get_conversation_id",
    "get_session_id",
    "clear_obs_context",
    # ── Discovery ─────────────────────────────────────────────────
    "discover_from_env",
    "detect_provider",
    "DiscoveredProvider",
    # ── Explicit wraps (alternative to auto_instrument) ───────────
    "wrap_openai",
    "wrap_anthropic",
    "wrap_gemini",
    "wrap_bedrock",
    "wrap_huggingface",
]

# Optional integrations (import from llm_obs.integrations)
def __getattr__(name: str):
    if name in ("LlamaIndexObsHandler", "instrument_llamaindex"):
        from .integrations import llamaindex as _li

        return getattr(_li, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
