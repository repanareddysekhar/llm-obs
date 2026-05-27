"""
Hugging Face Inference API + Text Generation Inference (TGI) instrumentation.

Requires: pip install "llm-obs[huggingface]"
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..context import get_conversation_id, get_session_id
from ..logging import get_logger

if TYPE_CHECKING:
    from ..client import ObservabilityClient

logger = get_logger("providers.huggingface")

_hf_patched = False
_tgi_patched = False


def patch_huggingface_client(obs: "ObservabilityClient") -> bool:
    """Patch huggingface_hub.InferenceClient.chat_completion and text_generation."""
    global _hf_patched
    if _hf_patched:
        return True
    try:
        from huggingface_hub import InferenceClient
    except ImportError:
        return False

    if getattr(InferenceClient.chat_completion, "_llm_obs_patched", False):
        _hf_patched = True
        return True

    original_chat = InferenceClient.chat_completion
    original_text = InferenceClient.text_generation

    def patched_chat(self: Any, *args: Any, **kwargs: Any) -> Any:
        model = kwargs.get("model") or (args[0] if args else "unknown")
        messages = kwargs.get("messages", [])
        span = obs.start_span(
            provider="huggingface",
            model=str(model),
            request={"messages": messages},
            conversation_id=get_conversation_id(),
            session_id=get_session_id(),
        )
        try:
            result = original_chat(self, *args, **kwargs)
            if hasattr(result, "choices") and result.choices:
                msg = result.choices[0].message
                content = getattr(msg, "content", str(msg))
                span.append_output(str(content)[:2048])
            if hasattr(result, "usage") and result.usage:
                span.set_usage(
                    prompt_tokens=getattr(result.usage, "prompt_tokens", None),
                    completion_tokens=getattr(result.usage, "completion_tokens", None),
                )
            span.end(status="success")
            return result
        except Exception as exc:
            span.set_error(type(exc).__name__, str(exc))
            span.end(status="error")
            raise

    def patched_text(self: Any, *args: Any, **kwargs: Any) -> Any:
        model = kwargs.get("model") or "unknown"
        prompt = kwargs.get("prompt") or (args[0] if args else "")
        span = obs.start_span(
            provider="huggingface",
            model=str(model),
            request={"prompt": str(prompt)[:2048]},
            conversation_id=get_conversation_id(),
            session_id=get_session_id(),
        )
        try:
            result = original_text(self, *args, **kwargs)
            span.append_output(str(result)[:2048])
            span.end(status="success")
            return result
        except Exception as exc:
            span.set_error(type(exc).__name__, str(exc))
            span.end(status="error")
            raise

    InferenceClient.chat_completion = patched_chat  # type: ignore[method-assign]
    InferenceClient.text_generation = patched_text  # type: ignore[method-assign]
    InferenceClient.chat_completion._llm_obs_patched = True  # type: ignore[attr-defined]
    _hf_patched = True
    logger.debug("Patched huggingface_hub.InferenceClient")
    return True


def patch_tgi_openai_client(obs: "ObservabilityClient") -> bool:
    """
    Patch OpenAI client when base_url points at a TGI OpenAI-compatible server.
    Reuses openai instrumentation; call detect_provider() to tag provider as tgi.
    """
    global _tgi_patched
    from .openai import patch_openai_class

    if patch_openai_class(obs):
        _tgi_patched = True
        return True
    return False


def wrap_huggingface(client: Any, obs: "ObservabilityClient") -> Any:
    """Instance-level wrap (same patches as class-level for InferenceClient)."""
    patch_huggingface_client(obs)
    return client
