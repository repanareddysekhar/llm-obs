# llm-obs

Lightweight Python SDK for LLM inference logging and observability.

Auto-instruments OpenAI, Anthropic, Google Gemini, AWS Bedrock, Ollama, and any OpenAI-compatible endpoint — zero changes to your LLM call code.

**Vendor-neutral:** send logs to any HTTP ingestion API that accepts the SDK payload (including self-hosted stacks). The [Repana LLM observability](https://github.com/repanareddysekhar/llm-observability) platform is one compatible backend, not a requirement.

---

## Related projects

| Project | What it is |
| --- | --- |
| **This repo (`llm-obs`)** | Open-source Python SDK (MIT) |
| **[llm-observability](https://github.com/repanareddysekhar/llm-observability)** | Full stack: ingestion API, worker, dashboard (may stay private or partially open) |

---

## Install

```bash
# Core SDK
pip install llm-obs

# With provider extras
pip install "llm-obs[openai]"
pip install "llm-obs[anthropic]"
pip install "llm-obs[gemini]"
pip install "llm-obs[bedrock]"
pip install "llm-obs[all]"
```

---

## Quickstart — one line

```python
from llm_obs import ObservabilityClient

obs = ObservabilityClient(
    endpoint="http://localhost:4000",   # your ingestion API
    api_key="dev-key",
)
obs.auto_instrument()   # patches all installed LLM libraries automatically
```

From this point, every LLM call in your app is logged automatically. No other changes needed.

---

## Stream chat

```python
from llm_obs import stream_chat, set_obs_context

# Set conversation context (picked up automatically by the SDK)
set_obs_context(conversation_id="conv-123")

# Unified streaming across all providers
async for chunk in stream_chat(provider="openai", model="gpt-4o-mini", messages=[
    {"role": "user", "content": "Explain Redis in one sentence."}
]):
    print(chunk, end="", flush=True)
```

---

## Provider detection from URL

```python
from llm_obs import detect_provider, available_providers
import os

os.environ["LLM_ENDPOINTS"] = "http://localhost:11434"  # Ollama, vLLM, or any URL

# SDK probes the URL and detects what's running
providers = available_providers()
# → {"ollama": ["gemma3:4b", "llama3.2", ...]}
```

Supported URL detection:
- **Ollama** — detected via `GET /api/tags`
- **vLLM / LiteLLM / LocalAI** — detected via `GET /v1/models`
- **AWS Bedrock** — detected from URL pattern (`amazonaws.com`)
- **OpenAI / Anthropic / Google** — detected from known API URL patterns
- **Private VPC** — probed automatically

---

## What gets logged per call

| Field | Description |
|---|---|
| `provider` / `model` | Who served the request |
| `latency_ms` | Total wall-clock time |
| `ttft_ms` | Time-to-first-token (streaming) |
| `prompt_tokens` / `completion_tokens` | Token usage |
| `cost_usd` | Computed from built-in price table |
| `status` | `success`, `error`, `cancelled` |
| `request` / `response` | PII-redacted payloads |
| `conversation_id` | Linked via `set_obs_context()` |

---

## PII redaction

PII is redacted **in-process before data leaves via HTTP** — email, phone, SSN, credit cards (Luhn), API keys, IPv4, URL secrets.

```python
obs = ObservabilityClient(..., redact_pii=True)   # default: True
```

---

## Manual span

```python
span = obs.start_span(
    provider="openai",
    model="gpt-4o-mini",
    request={"messages": [{"role": "user", "content": "Hello"}]},
    conversation_id="conv-123",
)
span.set_ttft(ms=210)
span.set_usage(prompt_tokens=42, completion_tokens=11)
span.end(status="success", streamed=True)
```

---

## License

MIT
