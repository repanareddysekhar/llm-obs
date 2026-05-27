"""
AWS Bedrock provider instrumentation.

Bedrock uses boto3 — there is no dedicated client class, just a generic
boto3.client("bedrock-runtime"). Provider is auto-detected from the model ID prefix.

Auto-instrumentation patches botocore's _make_api_call so all bedrock-runtime
calls are captured. Explicit wrapping via wrap_bedrock(client) is also supported.

Provider detection from model ID:
  anthropic.*  → "anthropic"
  amazon.*     → "amazon"
  meta.*       → "meta"
  mistral.*    → "mistral"
  cohere.*     → "cohere"
  ai21.*       → "ai21"
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from ..logging import get_logger

if TYPE_CHECKING:
    from ..client import ObservabilityClient

logger = get_logger("providers.bedrock")

_patched = False

_BEDROCK_OPERATIONS = {"InvokeModel", "InvokeModelWithResponseStream"}

_PROVIDER_PREFIXES = [
    ("anthropic.", "anthropic"),
    ("amazon.",    "amazon"),
    ("meta.",      "meta"),
    ("mistral.",   "mistral"),
    ("cohere.",    "cohere"),
    ("ai21.",      "ai21"),
]


def _detect_provider(model_id: str) -> str:
    mid = model_id.lower()
    for prefix, provider in _PROVIDER_PREFIXES:
        if mid.startswith(prefix):
            return provider
    return "bedrock"


def _extract_messages(body: dict) -> list[dict]:
    """Best-effort extraction of messages from the Bedrock request body."""
    if "messages" in body:
        return [
            {"role": m.get("role", "user"), "content": str(m.get("content", ""))[:500]}
            for m in body["messages"]
        ]
    if "prompt" in body:
        return [{"role": "user", "content": str(body["prompt"])[:500]}]
    if "inputText" in body:
        return [{"role": "user", "content": str(body["inputText"])[:500]}]
    return []


def _extract_usage(response_body: dict) -> tuple[int | None, int | None]:
    """Extract token counts from various Bedrock response formats."""
    # Anthropic via Bedrock
    usage = response_body.get("usage", {})
    if usage:
        return usage.get("input_tokens"), usage.get("output_tokens")
    # Amazon Titan
    if "inputTextTokenCount" in response_body:
        return (
            response_body.get("inputTextTokenCount"),
            response_body.get("results", [{}])[0].get("tokenCount"),
        )
    return None, None


def patch_bedrock_client(obs: "ObservabilityClient") -> bool:
    """
    Patch botocore.client.BaseClient._make_api_call to intercept
    bedrock-runtime InvokeModel calls at the SDK level.
    """
    global _patched
    if _patched:
        return True
    try:
        import botocore.client
        from ..context import get_conversation_id, get_session_id

        original_make_api_call = botocore.client.BaseClient._make_api_call

        def patched_make_api_call(self_inner, operation_name: str, api_params: dict):
            service = getattr(getattr(self_inner, "meta", None), "service_model", None)
            service_name = getattr(service, "service_name", "") if service else ""

            if service_name != "bedrock-runtime" or operation_name not in _BEDROCK_OPERATIONS:
                return original_make_api_call(self_inner, operation_name, api_params)

            model_id = api_params.get("modelId", "unknown")
            provider = _detect_provider(model_id)

            body_raw = api_params.get("body", b"{}")
            try:
                body = json.loads(body_raw) if isinstance(body_raw, (bytes, str)) else body_raw
            except Exception:
                body = {}

            span = obs.start_span(
                provider="bedrock",
                model=model_id,
                request={"messages": _extract_messages(body), "provider_family": provider},
                conversation_id=get_conversation_id(),
                session_id=get_session_id(),
                metadata={"bedrock_operation": operation_name},
            )

            try:
                result = original_make_api_call(self_inner, operation_name, api_params)
                # Non-streaming: parse body for usage
                if operation_name == "InvokeModel":
                    try:
                        resp_body = json.loads(result.get("body").read())
                        prompt_tokens, completion_tokens = _extract_usage(resp_body)
                        if prompt_tokens is not None:
                            span.set_usage(prompt_tokens, completion_tokens)
                        content = (
                            resp_body.get("content", [{}])[0].get("text", "")
                            or resp_body.get("results", [{}])[0].get("outputText", "")
                            or resp_body.get("generation", "")
                        )
                        span.append_output(content[:2048])
                    except Exception:
                        pass
                span.end(status="success", streamed=(operation_name == "InvokeModelWithResponseStream"))
                return result
            except Exception as exc:
                span.set_error(type(exc).__name__, str(exc)[:500])
                span.end(status="error")
                raise

        botocore.client.BaseClient._make_api_call = patched_make_api_call
        _patched = True
        logger.debug("Patched botocore.client.BaseClient._make_api_call for bedrock-runtime")
        return True
    except ImportError:
        return False


def wrap_bedrock(client: Any, obs: "ObservabilityClient") -> Any:
    """
    Explicit instance-level wrap for a boto3 bedrock-runtime client.
    Instruments invoke_model and invoke_model_with_response_stream.
    """
    from ..context import get_conversation_id, get_session_id

    original_invoke = client.invoke_model
    original_stream = client.invoke_model_with_response_stream

    def _make_span(model_id: str, body: dict) -> Any:
        provider = _detect_provider(model_id)
        return obs.start_span(
            provider="bedrock",
            model=model_id,
            request={"messages": _extract_messages(body), "provider_family": provider},
            conversation_id=get_conversation_id(),
            session_id=get_session_id(),
        )

    def instrumented_invoke(**kwargs: Any) -> Any:
        model_id = kwargs.get("modelId", "unknown")
        body_raw = kwargs.get("body", b"{}")
        try:
            body = json.loads(body_raw)
        except Exception:
            body = {}
        span = _make_span(model_id, body)
        try:
            result = original_invoke(**kwargs)
            try:
                resp_body = json.loads(result["body"].read())
                prompt_tokens, completion_tokens = _extract_usage(resp_body)
                if prompt_tokens is not None:
                    span.set_usage(prompt_tokens, completion_tokens)
                content = (
                    resp_body.get("content", [{}])[0].get("text", "")
                    or resp_body.get("results", [{}])[0].get("outputText", "")
                    or resp_body.get("generation", "")
                )
                span.append_output(content[:2048])
            except Exception:
                pass
            span.end(status="success", streamed=False)
            return result
        except Exception as exc:
            span.set_error(type(exc).__name__, str(exc)[:500])
            span.end(status="error")
            raise

    def instrumented_stream(**kwargs: Any) -> Any:
        model_id = kwargs.get("modelId", "unknown")
        body_raw = kwargs.get("body", b"{}")
        try:
            body = json.loads(body_raw)
        except Exception:
            body = {}
        span = _make_span(model_id, body)
        try:
            result = original_stream(**kwargs)
            span.end(status="success", streamed=True)
            return result
        except Exception as exc:
            span.set_error(type(exc).__name__, str(exc)[:500])
            span.end(status="error")
            raise

    client.invoke_model = instrumented_invoke
    client.invoke_model_with_response_stream = instrumented_stream
    return client
