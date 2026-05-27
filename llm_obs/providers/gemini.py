"""
Google Gemini provider instrumentation.

Patches GenerativeModel.generate_content_async at class level.
Streaming runs the blocking Gemini iterator in a thread; a queue bridges
it to the async caller so the event loop is never blocked.
"""
from __future__ import annotations

import asyncio
import queue
import threading
from typing import TYPE_CHECKING, Any

from ..logging import get_logger

if TYPE_CHECKING:
    from ..client import ObservabilityClient

logger = get_logger("providers.gemini")

_patched = False


class _InstrumentedGeminiAsyncStream:
    """
    Runs the blocking Gemini streaming iterator in a background thread
    and exposes it as an async generator via a thread-safe queue.
    """

    def __init__(self, response_fn, span: Any) -> None:
        self._response_fn = response_fn
        self._span = span
        self._iter = self._generate()

    def __aiter__(self):
        return self._iter

    async def _generate(self):
        chunk_queue: queue.Queue = queue.Queue()
        first_token = True

        def _run():
            try:
                response = self._response_fn()
                for chunk in response:
                    text = ""
                    try:
                        text = chunk.text
                    except Exception:
                        pass
                    chunk_queue.put(("chunk", text))
                usage = None
                try:
                    um = response.usage_metadata
                    usage = {
                        "prompt_tokens": um.prompt_token_count,
                        "completion_tokens": um.candidates_token_count,
                    }
                except Exception:
                    pass
                chunk_queue.put(("done", usage))
            except Exception as exc:
                chunk_queue.put(("error", exc))

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

        try:
            while True:
                try:
                    kind, value = await asyncio.to_thread(chunk_queue.get, True, 0.05)
                except queue.Empty:
                    continue

                if kind == "chunk":
                    if value:
                        if first_token:
                            self._span.set_ttft()
                            first_token = False
                        self._span.append_output(value)
                    yield value

                elif kind == "done":
                    if value:
                        self._span.set_usage(
                            prompt_tokens=value.get("prompt_tokens"),
                            completion_tokens=value.get("completion_tokens"),
                        )
                    if not self._span._ended:
                        self._span.end(status="success", streamed=True)
                    return

                elif kind == "error":
                    raise value

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

    def __getattr__(self, name: str) -> Any:
        return getattr(self, name)


def _build_chat_and_prompt(model_instance: Any, messages: list[dict]) -> tuple:
    """Convert messages list into Gemini chat history + last user message."""
    system_parts = [m["content"] for m in messages if m["role"] == "system"]
    system_instruction = system_parts[0] if system_parts else None
    convo = [m for m in messages if m["role"] != "system"]
    history = [
        {"role": "model" if m["role"] == "assistant" else "user", "parts": [m["content"]]}
        for m in convo[:-1]
    ]
    last_msg = convo[-1]["content"] if convo else ""
    return system_instruction, history, last_msg


def _make_patched_generate(obs: "ObservabilityClient", original):
    from ..context import get_conversation_id, get_session_id

    async def patched(self_inner, contents: Any, **kwargs: Any) -> Any:
        model_name = getattr(self_inner, "model_name", "gemini")
        # contents may be a plain string or a messages list
        if isinstance(contents, list) and contents and isinstance(contents[0], dict):
            messages = contents
            system_instruction, history, last_msg = _build_chat_and_prompt(self_inner, messages)
            chat = self_inner.start_chat(history=history)
            prompt_repr = last_msg[:500]
            def _call():
                return chat.send_message(last_msg, stream=kwargs.get("stream", False))
        else:
            prompt_repr = str(contents)[:500]
            def _call():
                return original(self_inner, contents, **kwargs)

        span = obs.start_span(
            provider="google",
            model=model_name,
            request={"prompt": prompt_repr},
            conversation_id=get_conversation_id(),
            session_id=get_session_id(),
        )

        if kwargs.get("stream"):
            return _InstrumentedGeminiAsyncStream(_call, span)

        try:
            response = await asyncio.to_thread(_call)
            content = ""
            try:
                content = response.text
            except Exception:
                pass
            span.append_output(content)
            try:
                um = response.usage_metadata
                span.set_usage(
                    prompt_tokens=um.prompt_token_count,
                    completion_tokens=um.candidates_token_count,
                )
            except Exception:
                pass
            span.end(status="success", streamed=False)
            return response
        except Exception as exc:
            span.set_error(type(exc).__name__, str(exc)[:500])
            span.end(status="error")
            raise

    return patched


def patch_gemini_class(obs: "ObservabilityClient") -> bool:
    global _patched
    if _patched:
        return True
    try:
        import google.generativeai as genai
        original = genai.GenerativeModel.generate_content_async
        genai.GenerativeModel.generate_content_async = _make_patched_generate(obs, original)
        _patched = True
        logger.debug("Patched google.generativeai.GenerativeModel.generate_content_async")
        return True
    except ImportError:
        return False


def wrap_gemini(model_instance: Any, obs: "ObservabilityClient") -> Any:
    """Explicit instance-level wrap (alternative to auto_instrument)."""
    from ..context import get_conversation_id, get_session_id
    original_generate = model_instance.generate_content

    def instrumented(contents: Any, **kwargs: Any) -> Any:
        model_name = getattr(model_instance, "model_name", "gemini")
        span = obs.start_span(
            provider="google",
            model=model_name,
            request={"prompt": str(contents)[:500]},
            conversation_id=get_conversation_id(),
            session_id=get_session_id(),
        )
        try:
            result = original_generate(contents, **kwargs)
            if kwargs.get("stream"):
                return _wrap_gemini_sync_stream(result, span)
            content = result.text if hasattr(result, "text") else ""
            span.append_output(content)
            try:
                um = result.usage_metadata
                span.set_usage(um.prompt_token_count, um.candidates_token_count)
            except Exception:
                pass
            span.end(status="success", streamed=False)
            return result
        except Exception as exc:
            span.set_error(type(exc).__name__, str(exc)[:500])
            span.end(status="error")
            raise

    model_instance.generate_content = instrumented
    return model_instance


def _wrap_gemini_sync_stream(stream: Any, span: Any):
    first_token = True
    try:
        for chunk in stream:
            text = chunk.text if hasattr(chunk, "text") else ""
            if text:
                if first_token:
                    span.set_ttft()
                    first_token = False
                span.append_output(text)
            yield chunk
    except Exception as exc:
        span.set_error(type(exc).__name__, str(exc)[:500])
        span.end(status="error", streamed=True)
        raise
    finally:
        if not span._ended:
            span.end(status="success", streamed=True)
