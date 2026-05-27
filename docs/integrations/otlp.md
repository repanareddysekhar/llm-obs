# OpenTelemetry (OTLP) export

Every completed inference span can be mirrored to an OTLP/HTTP collector (Jaeger, Grafana Tempo, Honeycomb, etc.).

## Install

```bash
pip install "llm-obs[otlp]"
```

## Enable

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318/v1/traces
export OTEL_SERVICE_NAME=my-llm-app
# optional
export LLM_OBS_OTLP_ENABLED=true
```

```python
from llm_obs import ObservabilityClient

obs = ObservabilityClient(otlp_enabled=True)
obs.auto_instrument()
```

HTTP ingest (`INGEST_URL`) and OTLP export run **in parallel** — use either or both.

## Span attributes

| Attribute | Source |
|-----------|--------|
| `gen_ai.system` | provider |
| `gen_ai.request.model` | model |
| `gen_ai.usage.input_tokens` | prompt tokens |
| `gen_ai.usage.output_tokens` | completion tokens |
| `llm_obs.latency_ms` | wall-clock latency |
| `llm_obs.ttft_ms` | time to first token |
| `llm_obs.status` | success / error / cancelled |

See `llm_obs.exporters.otlp.payload_to_otel_attributes` for the full mapping.
