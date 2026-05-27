"""
LlamaIndex callback handler — traces LLM and embedding events via llm-obs spans.

Requires: pip install "llm-obs[llamaindex]"
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..context import get_conversation_id, get_session_id
from ..logging import get_logger

if TYPE_CHECKING:
    from ..client import ObservabilityClient

logger = get_logger("integrations.llamaindex")


def _llama_imports():
    try:
        from llama_index.core.callbacks.base_handler import BaseCallbackHandler
        from llama_index.core.callbacks.schema import CBEventType, EventPayload
    except ImportError:
        from llama_index.callbacks.base_handler import BaseCallbackHandler  # type: ignore
        from llama_index.callbacks.schema import CBEventType, EventPayload  # type: ignore
    return BaseCallbackHandler, CBEventType, EventPayload


def LlamaIndexObsHandler(obs: "ObservabilityClient") -> Any:
    """Build a LlamaIndex BaseCallbackHandler that records llm-obs spans."""
    BaseCallbackHandler, CBEventType, EventPayload = _llama_imports()

    class _ObsHandler(BaseCallbackHandler):
        def __init__(self) -> None:
            super().__init__(event_starts_to_ignore=[], event_ends_to_ignore=[])
            self._obs = obs
            self._spans: dict[str, Any] = {}

        def on_event_start(
            self,
            event_type: Any,
            payload: dict[str, Any] | None = None,
            event_id: str = "",
            parent_id: str = "",
            **kwargs: Any,
        ) -> None:
            if event_type not in (CBEventType.LLM, CBEventType.EMBEDDING):
                return
            payload = payload or {}
            model = str(payload.get(EventPayload.MODEL_NAME, "unknown"))
            provider = (
                "llamaindex-embedding"
                if event_type == CBEventType.EMBEDDING
                else "llamaindex"
            )
            messages = payload.get(EventPayload.MESSAGES)
            prompt = payload.get(EventPayload.PROMPT)
            request: dict[str, Any] = {}
            if messages is not None:
                request["messages"] = messages
            elif prompt is not None:
                request["prompt"] = str(prompt)[:2048]

            self._spans[event_id] = self._obs.start_span(
                provider=provider,
                model=model,
                request=request,
                conversation_id=get_conversation_id(),
                session_id=get_session_id(),
                metadata={"llamaindex_event": str(event_type)},
            )

        def on_event_end(
            self,
            event_type: Any,
            payload: dict[str, Any] | None = None,
            event_id: str = "",
            **kwargs: Any,
        ) -> None:
            span = self._spans.pop(event_id, None)
            if span is None:
                return
            payload = payload or {}
            response = payload.get(EventPayload.RESPONSE)
            if response is not None:
                span.append_output(str(response)[:2048])
            chat_msg = payload.get(EventPayload.CHAT_MESSAGE)
            if chat_msg is not None and hasattr(chat_msg, "content"):
                span.append_output(str(chat_msg.content)[:2048])
            span.end(status="success", streamed=False)

    return _ObsHandler()


def instrument_llamaindex(
    obs: "ObservabilityClient",
    callback_manager: Any | None = None,
) -> Any:
    """
    Register the observability handler on LlamaIndex Settings or a CallbackManager.

        from llm_obs import ObservabilityClient
        from llm_obs.integrations import instrument_llamaindex

        obs = ObservabilityClient()
        instrument_llamaindex(obs)
    """
    handler = LlamaIndexObsHandler(obs)
    if callback_manager is not None:
        callback_manager.add_handler(handler)
        return callback_manager

    try:
        from llama_index.core import Settings

        Settings.callback_manager.add_handler(handler)
        return Settings.callback_manager
    except ImportError:
        logger.warning("llama-index-core not installed — pip install \"llm-obs[llamaindex]\"")
        return None
