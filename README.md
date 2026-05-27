# llm-obs

**Flight recorder for LLM apps** — local-first inference tracing with PII redaction before anything leaves your process.

[![PyPI](https://img.shields.io/pypi/v/llm-obs.svg)](https://pypi.org/project/llm-obs/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/pypi/pyversions/llm-obs.svg)](https://pypi.org/project/llm-obs/)

> One line instruments OpenAI, Anthropic, Gemini, and Bedrock. Ship traces, token usage, latency, and failures to **any** HTTP ingest API — no vendor lock-in.

<p align="center">
  <video src="docs/assets/demo.mp4" controls width="720" alt="llm-obs demo — chat, traces, and dashboard">
    <a href="docs/assets/demo.mp4">Watch demo video</a>
  </video>
</p>
<p align="center">
  <sub>SDK instrumentation → chat → inference logs &amp; dashboard (optional <a href="https://github.com/repanareddysekhar/llm-observability">llm-observability</a> backend)</sub>
</p>

---

## Why this exists

LLM apps fail in ways traditional APM misses: silent prompt regressions, runaway token cost, PII leaking into logs, and “slow” that is really time-to-first-token.

**llm-obs** is a lightweight Python SDK that:

- Records **every inference** as a structured span (provider, model, tokens, cost, latency, TTFT, status).
- **Redacts PII in-process** before HTTP export.
- **Batches asynchronously** so your hot path stays fast.
- Stays **vendor-neutral** — your ingest endpoint, your dashboard, your data residency.

Think **OpenTelemetry-native AI tracing** in spirit (span model today; OTLP export on the [roadmap](#roadmap)). Not another hosted “AI observability platform” you have to buy to get value.

---

## Quickstart (< 2 minutes)

```bash
pip install "llm-obs[openai]"
export OPENAI_API_KEY=sk-...
export INGEST_URL=http://localhost:4000   # any compatible ingest API
export INGEST_API_KEY=dev-key             # optional
```

```python
from llm_obs import ObservabilityClient

obs = ObservabilityClient()   # reads INGEST_URL / INGEST_API_KEY from env
obs.auto_instrument()         # patches installed LLM SDKs — one time at startup

# existing code unchanged; every completion is now traced
```

```python
# asyncio + openai example — see examples/openai_basic.py
import asyncio
from openai import AsyncOpenAI

async def main():
    client = AsyncOpenAI()
    r = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Hello"}],
    )
    print(r.choices[0].message.content)

asyncio.run(main())
```

Flush on shutdown: `obs.flush()` (or rely on batch timer).

---

## Killer visual — one inference, four signals

Each span your SDK emits can surface in a log detail view like this — **latency**, **TTFT**, **streamed**, **status**, and **redacted I/O**:

<p align="center">
  <img src="docs/assets/dashboard-log-detail.png" alt="Log detail: latency 13373ms, TTFT 398ms, streamed, input/output preview" width="820" />
</p>

| Signal | Where it shows |
|--------|----------------|
| **Traces** | Inference logs table — time, provider/model, status, latency |
| **Tokens & cost** | Dashboard totals + per-row when usage is present |
| **Latency** | Per-request ms + dashboard p50 / p95 charts |
| **Failures** | Status column + dashboard error rate |

---

## Screenshots

| View | What you see |
|------|----------------|
| **Chat** | Multi-turn UI with provider/model picker (Ollama, OpenAI, etc.) |
| **Dashboard** | Request volume, error rate, p50/p95 latency, TTFT, estimated cost |
| **Logs** | Filterable trace list with latency and response preview |
| **Log detail** | Full span: TTFT, streaming flag, input/output (PII-redacted in transit) |

<p align="center">
  <img src="docs/assets/dashboard-chat.png" alt="Chat interface" width="400" />
  &nbsp;
  <img src="docs/assets/dashboard-overview.png" alt="Inference dashboard — latency and error rate" width="400" />
</p>
<p align="center">
  <img src="docs/assets/dashboard-traces.png" alt="Inference logs table" width="820" />
</p>

Asset map: [docs/assets/README.md](docs/assets/README.md)

---

## Architecture

```mermaid
flowchart LR
  subgraph App["Your LLM app"]
    FW[LangChain · CrewAI · LiteLLM · raw SDKs]
  end
  subgraph SDK["llm-obs (in-process)"]
    AI[auto_instrument]
    SP[InferenceSpan]
    PII[PII redaction]
    BT[batch + retry]
  end
  subgraph Sink["Your stack"]
    API[Any HTTP ingest]
    DB[(Dashboard / warehouse)]
  end
  FW --> AI --> SP --> PII --> BT --> API --> DB
```

Source: [docs/assets/architecture.mmd](docs/assets/architecture.mmd)

---

## Features

| Feature | Description |
|---------|-------------|
| **Auto-instrument** | Monkey-patch OpenAI, Anthropic, Gemini, Bedrock at startup |
| **Unified streaming** | `stream_chat()` across providers + Ollama-compatible URLs |
| **Inference spans** | Latency, TTFT, tokens, USD cost, status, errors |
| **PII redaction** | Email, phone, SSN, cards (Luhn), API keys, IPv4, URL secrets — before HTTP |
| **Batch transport** | Configurable batch size + flush interval; non-blocking enqueue |
| **Context linking** | `set_obs_context(conversation_id=…, session_id=…)` |
| **Endpoint discovery** | Probe Ollama, vLLM, LiteLLM proxy URLs via `LLM_ENDPOINTS` |
| **Vendor-neutral** | Works with self-hosted ingest; no required SaaS |

---

## Supported frameworks & providers

### Providers (first-class patches)

| Provider | Install extra | Auto-instrument target |
|----------|---------------|-------------------------|
| OpenAI | `llm-obs[openai]` | `AsyncOpenAI` completions |
| Anthropic | `llm-obs[anthropic]` | `AsyncAnthropic` messages |
| Google Gemini | `llm-obs[gemini]` | `GenerativeModel` async |
| AWS Bedrock | `llm-obs[bedrock]` | `bedrock-runtime` invoke + stream |
| Ollama / vLLM / LiteLLM proxy | `llm-obs[openai]` or core | OpenAI-compatible `/v1` URLs |

### Frameworks (via underlying SDKs)

| Framework | Status | How |
|-----------|--------|-----|
| **LangChain** | Works today | `auto_instrument()` — [examples/langchain_basic.py](examples/langchain_basic.py) |
| **LiteLLM** | Works today | OpenAI path — [examples/litellm_basic.py](examples/litellm_basic.py) |
| **CrewAI** | Works today | [examples/crewai_basic.py](examples/crewai_basic.py) |
| **LlamaIndex** | Callback handler | `instrument_llamaindex()` — [examples/llamaindex_basic.py](examples/llamaindex_basic.py) |
| **Hugging Face / TGI** | HF InferenceClient + OpenAI-compat TGI | `auto_instrument()` — [examples/huggingface_basic.py](examples/huggingface_basic.py) |
| **OpenTelemetry** | OTLP/HTTP export | `pip install "llm-obs[otlp]"` — [docs/integrations/otlp.md](docs/integrations/otlp.md) |
| **Vercel AI SDK** | HTTP bridge contract | [docs/integrations/vercel-ai-sdk.md](docs/integrations/vercel-ai-sdk.md) |

Examples: [`examples/`](examples/)

---

## Benchmarks

Local overhead (no network, noop transport) — run yourself:

```bash
python examples/benchmark_overhead.py
```

| Metric | Typical (dev machine) | Notes |
|--------|----------------------|--------|
| Span create + end (p50) | ~0.06 ms | Per inference, in-process |
| Span create + end (p99) | ~0.08 ms | |
| PII redact (per string) | ~0.02 ms | Depends on payload size |
| Batch enqueue | ~µs | Hot path; flush is background thread |
| Memory (SDK + benchmark) | ~7 MiB traced peak | Excludes LLM SDK heaps |

End-to-end latency overhead on real calls is usually **sub-millisecond** vs multi-second LLM RTT. Re-run benchmarks after upgrades and publish results in release notes.

---

## Install

```bash
pip install llm-obs
pip install "llm-obs[all]"    # all provider extras
```

| Extra | Packages |
|-------|----------|
| `openai` | openai |
| `anthropic` | anthropic |
| `gemini` | google-generativeai |
| `bedrock` | boto3 |

---

## Examples

| Example | Command |
|---------|---------|
| OpenAI | `python examples/openai_basic.py` |
| LangChain | `python examples/langchain_basic.py` |
| CrewAI | `python examples/crewai_basic.py` |
| LiteLLM | `python examples/litellm_basic.py` |

---

## Configuration

| Env var | Default | Purpose |
|---------|---------|---------|
| `INGEST_URL` | `http://localhost:4000` | Ingest API base URL |
| `INGEST_API_KEY` | — | `x-obs-api-key` header |
| `ENVIRONMENT` | `dev` | Tagged on every span |
| `LLM_ENDPOINTS` | — | Comma-separated URLs to probe (Ollama, vLLM, …) |

```python
obs = ObservabilityClient(
    endpoint="https://ingest.example.com",
    api_key="secret",
    redact_pii=True,          # default
    batch_size=20,
    flush_interval_s=2.0,
)
```

---

## Manual spans

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

## Roadmap

**Integrations (in-repo examples first; separate demo repos later):**

- [x] LangChain — example in `examples/`
- [x] LiteLLM — example in `examples/`
- [x] CrewAI — example in `examples/`
- [x] LlamaIndex callback handler
- [x] OpenTelemetry OTLP exporter
- [x] Hugging Face InferenceClient (TGI via OpenAI-compatible URL)
- [ ] Vercel AI SDK — `@llm-obs/bridge` npm package (HTTP contract [documented](docs/integrations/vercel-ai-sdk.md))

**Docs & media:**

- [x] `docs/assets/demo.mp4` — product demo video
- [x] Dashboard screenshots (chat · overview · traces · log detail)

---

## Related projects

| Project | What it is |
|---------|------------|
| **This repo (`llm-obs`)** | Open-source Python SDK (MIT) — **you are here** |
| **[llm-observability](https://github.com/repanareddysekhar/llm-observability)** | Optional full stack: ingest API, worker, dashboard |

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Security: [SECURITY.md](SECURITY.md).

---

## License

MIT — see [LICENSE](LICENSE).
