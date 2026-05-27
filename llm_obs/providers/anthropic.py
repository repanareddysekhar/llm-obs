"""
Anthropic provider instrumentation.

Patches AsyncMessages.create at class level.
Streaming uses _InstrumentedAnthropicAsyncStream which wraps the raw event
iterator returned by create(stream=True).
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..logging import get_logger

if TYPE_CHECKING:
    from ..client import ObservabilityClient

logger = get_logger("providers.anthropic")

_patched = False


class _InstrumentedAnthropicAsyncStream:
    """
    Wraps Anthropic's async streaming response.
    Iterates raw events, extracts text/usage, then ends the span.
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
            async for event in self._stream:
                etype = type(event).__name__

                if etype == "RawContentBlockDeltaEvent":
                    text = getattr(event.delta, "text", "")
                    if text:
                        if first_token:
                            self._span.set_ttft()
                            first_token = False
                        self._span.append_output(text)

                elif etype == "RawMessageStartEvent":
                    usage = getattr(getattr(event, "message", None), "usage", None)
                    if usage:
                        self._span.set_usage(
                            prompt_tokens=getattr(usage, "input_tokens", None)
                        )

                elif etype == "RawMessageDeltaEvent":
                    usage = getattr(event, "usage", None)
                    if usage:
                        self._span.set_usage(
                            completion_tokens=getattr(usage, "output_tokens", None)
                        )

                yield event

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
        elif hasattr(self._stream, "aclose"):
            await self._stream.aclose()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._stream, name)


def _make_patched_create(obs: "ObservabilityClient", original):
    from ..context import get_conversation_id, get_session_id

    async def patched(self_inner, **kwargs: Any) -> Any:
        model = kwargs.get("model", "unknown")
        messages = kwargs.get("messages", [])
        span = obs.start_span(
            provider="anthropic",
            model=model,
            request={
                "messages": [
                    {"role": m.get("role"), "content": str(m.get("content", ""))[:500]}
                    for m in messages
                ],
                "max_tokens": kwargs.get("max_tokens"),
            },
            conversation_id=get_conversation_id(),
            session_id=get_session_id(),
        )
        try:
            result = await original(self_inner, **kwargs)
            if kwargs.get("stream"):
                return _InstrumentedAnthropicAsyncStream(result, span)
            else:
                usage = getattr(result, "usage", None)
                if usage:
                    span.set_usage(
                        prompt_tokens=getattr(usage, "input_tokens", None),
                        completion_tokens=getattr(usage, "output_tokens", None),
                    )
                content = "".join(
                    getattr(b, "text", "") for b in getattr(result, "content", [])
                )
                span.append_output(content)
                span.end(
                    status="success",
                    finish_reason=getattr(result, "stop_reason", None),
                    streamed=False,
                )
                return result
        except Exception as exc:
            span.set_error(type(exc).__name__, str(exc)[:500])
            span.end(status="error")
            raise

    return patched


def patch_anthropic_class(obs: "ObservabilityClient") -> bool:
    global _patched
    if _patched:
        return True
    try:
        from anthropic.resources.messages import AsyncMessages
        original = AsyncMessages.create
        AsyncMessages.create = _make_patched_create(obs, original)
        _patched = True
        logger.debug("Patched anthropic.AsyncMessages.create")
        return True
    except ImportError:
        return False


def wrap_anthropic(client: Any, obs: "ObservabilityClient") -> Any:
    """Explicit instance-level wrap (alternative to auto_instrument)."""
    from ..context import get_conversation_id, get_session_id
    original_create = client.messages.create

    async def instrumented(**kwargs: Any) -> Any:
        model = kwargs.get("model", "unknown")
        messages = kwargs.get("messages", [])
        span = obs.start_span(
            provider="anthropic",
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
                return _InstrumentedAnthropicAsyncStream(result, span)
            else:
                usage = getattr(result, "usage", None)
                if usage:
                    span.set_usage(
                        prompt_tokens=getattr(usage, "input_tokens", None),
                        completion_tokens=getattr(usage, "output_tokens", None),
                    )
                content = "".join(
                    getattr(b, "text", "") for b in getattr(result, "content", [])
                )
                span.append_output(content)
                span.end(status="success", finish_reason=getattr(result, "stop_reason", None))
                return result
        except Exception as exc:
            span.set_error(type(exc).__name__, str(exc)[:500])
            span.end(status="error")
            raise

    client.messages.create = instrumented
    return client
