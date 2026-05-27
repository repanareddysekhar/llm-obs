# Vercel AI SDK bridge (design)

The Python `llm-obs` package targets Python LLM stacks. **Vercel AI SDK** runs in Node/Edge. Use a thin HTTP bridge that posts the same ingest event shape to your backend.

## Architecture

```text
Next.js / Edge (Vercel AI SDK)
    → @llm-obs/bridge (planned TS package) or custom fetch
    → POST /v1/ingest/batch  (your llm-obs-compatible API)
    → dashboard / OTLP / warehouse
```

## Event shape (matches Python SDK)

```json
{
  "events": [
    {
      "id": "01J8K9M2N3P4Q5R6S7T8U9V0W",
      "provider": "openai",
      "model": "gpt-4o-mini",
      "status": "success",
      "started_at": "2026-05-27T12:00:00+00:00",
      "ended_at": "2026-05-27T12:00:01+00:00",
      "latency_ms": 1240,
      "ttft_ms": 210,
      "streamed": true,
      "request": { "messages": [{ "role": "user", "content": "Hello" }] },
      "response": { "content": "Hi there!" },
      "usage": { "prompt_tokens": 8, "completion_tokens": 4 },
      "cost_usd": 0.00001,
      "environment": "production",
      "sdk_version": "bridge-0.1.0",
      "conversation_id": "chat-abc",
      "metadata": { "framework": "vercel-ai-sdk" }
    }
  ]
}
```

## Node snippet (manual bridge today)

```typescript
async function logInference(event: Record<string, unknown>) {
  await fetch(`${process.env.INGEST_URL}/v1/ingest/batch`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-obs-api-key": process.env.INGEST_API_KEY ?? "",
    },
    body: JSON.stringify({ events: [event] }),
  });
}
```

Wrap `streamText` / `generateText` completion handlers to call `logInference` with timing and usage from the AI SDK result object.

## Planned `@llm-obs/bridge` package

| Feature | Status |
|---------|--------|
| `wrapAISDK()` middleware | Planned |
| Streaming TTFT | Planned |
| PII redaction (port of Python patterns) | Planned |
| OTLP sidecar export | Planned |

Separate npm repo will be announced when the bridge reaches alpha. Until then, use the JSON contract above against any compatible ingest API.

## Security

- Never send raw API keys in `request` / `response` bodies.
- Redact PII in the bridge before POST (mirror Python `llm_obs.pii` rules).
- Use `INGEST_API_KEY` on server routes only — not `NEXT_PUBLIC_*`.
