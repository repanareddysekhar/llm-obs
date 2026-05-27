from llm_obs.exporters.otlp import payload_to_otel_attributes


def test_payload_to_otel_attributes_maps_core_fields():
    payload = {
        "id": "01JTEST",
        "provider": "openai",
        "model": "gpt-4o-mini",
        "status": "success",
        "latency_ms": 1200,
        "ttft_ms": 180,
        "streamed": True,
        "cost_usd": 0.00042,
        "environment": "dev",
        "sdk_version": "0.1.4",
        "conversation_id": "conv-1",
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        "request": {"messages": [{"role": "user", "content": "hi"}]},
        "response": {"content": "hello"},
    }
    attrs = payload_to_otel_attributes(payload)
    assert attrs["gen_ai.system"] == "openai"
    assert attrs["gen_ai.request.model"] == "gpt-4o-mini"
    assert attrs["gen_ai.usage.input_tokens"] == 10
    assert attrs["gen_ai.usage.output_tokens"] == 5
    assert attrs["llm_obs.latency_ms"] == 1200
    assert attrs["llm_obs.conversation_id"] == "conv-1"


def test_payload_to_otel_attributes_error():
    payload = {
        "provider": "openai",
        "model": "gpt-4o",
        "status": "error",
        "error": {"type": "RateLimitError", "message": "too many requests"},
    }
    attrs = payload_to_otel_attributes(payload)
    assert attrs["llm_obs.error.type"] == "RateLimitError"
