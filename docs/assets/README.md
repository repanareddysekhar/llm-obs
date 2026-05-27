# Visual assets

Stable filenames for README and docs. **Do not use spaces** in new filenames.

| File | Source (original) | Used for |
|------|-------------------|----------|
| [`demo.mp4`](demo.mp4) | `chatbot-llm-observability.mp4` | README hero — SDK + chat + dashboard flow |
| [`dashboard-chat.png`](dashboard-chat.png) | Screenshot 2026-05-21 10.59.43 PM | Chat UI (Ollama / model picker) |
| [`dashboard-overview.png`](dashboard-overview.png) | Screenshot 2026-05-21 10.59.52 PM | Inference dashboard — latency, throughput, error rate, cost |
| [`dashboard-traces.png`](dashboard-traces.png) | Screenshot 2026-05-21 10.59.57 PM | Inference logs table (all traces) |
| [`dashboard-log-detail.png`](dashboard-log-detail.png) | Screenshot 2026-05-21 11.00.02 PM | Single trace — TTFT, latency, streamed, I/O preview |
| [`architecture.mmd`](architecture.mmd) | — | Mermaid source for architecture diagram |

## Optional exports

```bash
# GIF from demo.mp4 (for README mirrors that only accept GIF)
ffmpeg -i demo.mp4 -vf "fps=12,scale=1280:-1" -t 20 demo.gif
```

## Reference backend

Screenshots are from the optional [llm-observability](https://github.com/repanareddysekhar/llm-observability) dashboard ingesting `llm-obs` spans. Any compatible HTTP ingest + UI works the same way.
