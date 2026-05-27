"""
OpenAI provider instrumentation.

auto_instrument path:  patch_openai_class(obs) patches AsyncCompletions.create
                       at class level — all AsyncOpenAI instances are covered.

explicit wrap path:    wrap_openai(client, obs) patches a single instance.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..logging import get_logger

if TYPE_CHECKING:
    from ..client import ObservabilityClient

logger = get_logger("providers.openai")

_patched = False


class _InstrumentedAsyncStream:
    """
    Transparent async wrapper around OpenAI's AsyncStream.
    Yields identical chunks to the caller while recording TTFT, usage, and output.
    Handles cancellation via .close().
    """

    def __init__(self, stream: Any, span: Any) -> None:
        self._stream = stream
        self._span = span
        self._iter = self._generate()

    def __aiter__(self):
        return self._iter

    async def _generate(self):
        first_token = True
        try:
            async for chunk in self._stream:
                if chunk.choices:
                    delta = chunk.choices[0].delta
                    if delta and delta.content:
                        if first_token:
                            self._span.set_ttft()
                            first_token = False
                        self._span.append_output(delta.content)
                # Usage arrives in trailing chunk (stream_options include_usage)
                if hasattr(chunk, "usage") and chunk.usage:
                    self._span.set_usage(
                        prompt_tokens=chunk.usage.prompt_tokens,
                        completion_tokens=chunk.usage.completion_tokens,
                    )
                yield chunk
            if not self._span._ended:
                self._span.end(status="success", streamed=True)
        except GeneratorExit:
            if not self._span._ended:
                self._span.end(status="cancelled", streamed=True)
            raise
        except Exception as exc:
            self._span.set_error(type(exc).__name__, str(exc)[:500])
            if not self._span._ended:
                self._span.end(status="error", streamed=True)
            raise

    async def close(self) -> None:
        if not self._span._ended:
            self._span.end(status="cancelled", streamed=True)
        if hasattr(self._stream, "close"):
            await self._stream.close()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._stream, name)


def _detect_provider_from_client(completions_self: Any) -> str:
    """
    Infer the real provider from the AsyncOpenAI client's base_url.
    Ollama and other OpenAI-compatible endpoints use AsyncOpenAI with a custom base_url.
    """
    try:
        base_url = str(getattr(getattr(completions_self, "_client", None), "base_url", ""))
        if not base_url or "api.openai.com" in base_url:
            return "openai"
        # Ollama always runs on port 11434 or has 'ollama' in the URL
        if "11434" in base_url or "ollama" in base_url.lower():
            return "ollama"
        # Azure OpenAI
        if "openai.azure.com" in base_url:
            return "openai"
        # Everything else with a non-OpenAI base_url is OpenAI-compatible
        return "openai_compatible"
    except Exception:
        return "openai"


def _make_patched_create(obs: "ObservabilityClient", original):
    """Return an async patched version of AsyncCompletions.create."""
    from ..context import get_conversation_id, get_session_id

    async def patched(self_inner, **kwargs: Any) -> Any:
        # Detect real provider from the client's base_url — not hardcoded
        provider = _detect_provider_from_client(self_inner)
        model = kwargs.get("model", "unknown")
        messages = kwargs.get("messages", [])
        span = obs.start_span(
            provider=provider,
            model=model,
            request={
                "messages": [
                    {"role": m.get("role"), "content": str(m.get("content", ""))[:500]}
                    for m in messages
                ],
                "temperature": kwargs.get("temperature"),
                "max_tokens": kwargs.get("max_tokens"),
            },
            conversation_id=get_conversation_id(),
            session_id=get_session_id(),
        )
        try:
            result = await original(self_inner, **kwargs)
            if kwargs.get("stream"):
                return _InstrumentedAsyncStream(result, span)
            else:
                if result.usage:
                    span.set_usage(result.usage.prompt_tokens, result.usage.completion_tokens)
                if result.choices:
                    span.append_output(result.choices[0].message.content or "")
                span.end(status="success", streamed=False)
                return result
        except Exception as exc:
            span.set_error(type(exc).__name__, str(exc)[:500])
            span.end(status="error")
            raise

    return patched


def patch_openai_class(obs: "ObservabilityClient") -> bool:
    """
    Patch openai.resources.chat.completions.AsyncCompletions.create at class level.
    All AsyncOpenAI instances created after this call are automatically instrumented.
    """
    global _patched
    if _patched:
        return True
    try:
        from openai.resources.chat.completions import AsyncCompletions
        original = AsyncCompletions.create
        AsyncCompletions.create = _make_patched_create(obs, original)
        _patched = True
        logger.debug("Patched openai.AsyncCompletions.create")
        return True
    except ImportError:
        return False


def wrap_openai(client: Any, obs: "ObservabilityClient") -> Any:
    """Explicit instance-level wrap (alternative to auto_instrument)."""
    from ..context import get_conversation_id, get_session_id
    original_create = client.chat.completions.create
    provider = _detect_provider_from_client(client.chat.completions)

    async def instrumented(**kwargs: Any) -> Any:
        model = kwargs.get("model", "unknown")
        messages = kwargs.get("messages", [])
        span = obs.start_span(
            provider=provider,
            model=model,
            request={
                "messages": [
                    {"role": m.get("role"), "content": str(m.get("content", ""))[:500]}
                    for m in messages
                ],
            },
            conversation_id=get_conversation_id(),
            session_id=get_session_id(),
        )
        try:
            result = await original_create(**kwargs)
            if kwargs.get("stream"):
                return _InstrumentedAsyncStream(result, span)
            else:
                if result.usage:
                    span.set_usage(result.usage.prompt_tokens, result.usage.completion_tokens)
                if result.choices:
                    span.append_output(result.choices[0].message.content or "")
                span.end(status="success", streamed=False)
                return result
        except Exception as exc:
            span.set_error(type(exc).__name__, str(exc)[:500])
            span.end(status="error")
            raise

    client.chat.completions.create = instrumented
    return client
