# Visual assets

Add marketing and README media here.

| Asset | Purpose | Suggested spec |
|-------|---------|----------------|
| `demo.gif` | README hero — 20s screen recording | 1280×720, show `auto_instrument()` + one chat + ingest log line |
| `architecture.png` | Exported from `architecture.mmd` | SVG/PNG for docs |
| `dashboard-traces.png` | Killer visual — trace list | From your ingest UI |
| `dashboard-tokens.png` | Token usage panel | Same session |
| `dashboard-latency.png` | p50/p99 latency | Same session |
| `dashboard-failures.png` | Error rate / failed spans | Optional failure injection |

Until files exist, the README uses Mermaid + ASCII fallbacks.

**Record demo.gif (macOS):**

```bash
# QuickTime → New Screen Recording, or:
ffmpeg -f avfoundation -i "1" -t 20 -r 15 demo.gif
```

Replace `architecture.mmd` export:

```bash
# https://mermaid.live — paste docs/assets/architecture.mmd → Export PNG
```
