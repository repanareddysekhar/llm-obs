"""
Export llm-obs inference payloads as OpenTelemetry spans (OTLP/HTTP).

Enable via ObservabilityClient(otlp_enabled=True) or OTEL_EXPORTER_OTLP_ENDPOINT.
Requires: pip install "llm-obs[otlp]"
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger("llm_obs.exporters.otlp")

# Semantic conventions (OpenTelemetry gen_ai / llm)
_ATTR_PREFIX = "llm_obs"


def payload_to_otel_attributes(payload: dict[str, Any]) -> dict[str, Any]:
    """Map an llm-obs ingest payload to OpenTelemetry span attributes."""
    attrs: dict[str, Any] = {
        "gen_ai.system": payload.get("provider", ""),
        "gen_ai.request.model": payload.get("model", ""),
        f"{_ATTR_PREFIX}.span_id": payload.get("id", ""),
        f"{_ATTR_PREFIX}.status": payload.get("status", ""),
        f"{_ATTR_PREFIX}.environment": payload.get("environment", ""),
        f"{_ATTR_PREFIX}.sdk_version": payload.get("sdk_version", ""),
    }
    if payload.get("conversation_id"):
        attrs[f"{_ATTR_PREFIX}.conversation_id"] = payload["conversation_id"]
    if payload.get("session_id"):
        attrs[f"{_ATTR_PREFIX}.session_id"] = payload["session_id"]
    if payload.get("latency_ms") is not None:
        attrs[f"{_ATTR_PREFIX}.latency_ms"] = payload["latency_ms"]
    if payload.get("ttft_ms") is not None:
        attrs[f"{_ATTR_PREFIX}.ttft_ms"] = payload["ttft_ms"]
    if payload.get("streamed") is not None:
        attrs[f"{_ATTR_PREFIX}.streamed"] = payload["streamed"]
    if payload.get("cost_usd") is not None:
        attrs[f"{_ATTR_PREFIX}.cost_usd"] = payload["cost_usd"]

    usage = payload.get("usage") or {}
    if usage.get("prompt_tokens") is not None:
        attrs["gen_ai.usage.input_tokens"] = usage["prompt_tokens"]
    if usage.get("completion_tokens") is not None:
        attrs["gen_ai.usage.output_tokens"] = usage["completion_tokens"]

    if payload.get("error"):
        err = payload["error"]
        attrs[f"{_ATTR_PREFIX}.error.type"] = err.get("type", "")
        attrs[f"{_ATTR_PREFIX}.error.message"] = err.get("message", "")

    # Compact JSON for request/response (truncated in payload already)
    if payload.get("request"):
        attrs[f"{_ATTR_PREFIX}.request"] = _json_attr(payload["request"])
    resp = payload.get("response")
    if resp:
        attrs[f"{_ATTR_PREFIX}.response"] = _json_attr(resp)

    return attrs


def _json_attr(obj: Any, max_len: int = 4096) -> str:
    try:
        s = json.dumps(obj, default=str)
    except Exception:
        s = str(obj)
    return s[:max_len]


def _parse_iso_to_ns(iso: str | None) -> int | None:
    if not iso:
        return None
    from datetime import datetime

    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return int(dt.timestamp() * 1_000_000_000)
    except Exception:
        return None


class OTLPExporter:
    """Lazy OTLP/HTTP span exporter wrapping the OpenTelemetry SDK."""

    def __init__(
        self,
        endpoint: str | None = None,
        headers: dict[str, str] | None = None,
        service_name: str = "llm-obs",
    ) -> None:
        self._endpoint = (
            endpoint
            or os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
            or os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
            or "http://localhost:4318/v1/traces"
        )
        self._headers = headers or _headers_from_env()
        self._service_name = (
            service_name
            or os.environ.get("OTEL_SERVICE_NAME", "llm-obs")
        )
        self._provider: Any = None
        self._tracer: Any = None
        self._initialized = False

    def _ensure_initialized(self) -> bool:
        if self._initialized:
            return self._tracer is not None
        self._initialized = True
        try:
            from opentelemetry import trace
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                OTLPSpanExporter,
            )
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
        except ImportError:
            logger.warning(
                "OTLP export disabled — install with: pip install \"llm-obs[otlp]\""
            )
            return False

        resource = Resource.create({"service.name": self._service_name})
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(
            endpoint=self._endpoint,
            headers=self._headers or None,
        )
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        self._provider = provider
        self._tracer = trace.get_tracer("llm_obs")
        return True

    def export(self, payload: dict[str, Any]) -> None:
        if not self._ensure_initialized() or not self._tracer:
            return

        from opentelemetry.trace import Status, StatusCode

        attrs = payload_to_otel_attributes(payload)
        span_name = f"{payload.get('provider', 'llm')}.{payload.get('model', 'inference')}"

        start_ns = _parse_iso_to_ns(payload.get("started_at"))
        end_ns = _parse_iso_to_ns(payload.get("ended_at"))

        span = self._tracer.start_span(
            span_name,
            start_time=start_ns,
            attributes={k: v for k, v in attrs.items() if v is not None and v != ""},
        )

        status = payload.get("status", "success")
        if status == "error":
            span.set_status(Status(StatusCode.ERROR))
        elif status == "cancelled":
            span.set_status(Status(StatusCode.ERROR, "cancelled"))
        else:
            span.set_status(Status(StatusCode.OK))

        if end_ns and start_ns:
            span.end(end_time=end_ns)
        else:
            span.end()

    def shutdown(self) -> None:
        if self._provider and hasattr(self._provider, "shutdown"):
            self._provider.shutdown()


def _headers_from_env() -> dict[str, str]:
    raw = os.environ.get("OTEL_EXPORTER_OTLP_HEADERS", "")
    headers: dict[str, str] = {}
    for part in raw.split(","):
        if "=" in part:
            k, v = part.split("=", 1)
            headers[k.strip()] = v.strip()
    return headers
