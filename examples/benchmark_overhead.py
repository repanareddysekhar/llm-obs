#!/usr/bin/env python3
"""
Measure llm-obs instrumentation overhead (no live LLM calls).

Run: python examples/benchmark_overhead.py
"""
from __future__ import annotations

import statistics
import sys
import time
import tracemalloc

# Allow running from repo root without install
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))

from llm_obs import ObservabilityClient


class _NoopTransport:
    def enqueue(self, payload: dict) -> None:
        pass

    def flush(self) -> None:
        pass


def _make_client() -> ObservabilityClient:
    obs = ObservabilityClient(endpoint="http://127.0.0.1:9", redact_pii=True)
    obs._transport = _NoopTransport()  # type: ignore[assignment]
    return obs


def bench_span_end(n: int = 5000) -> tuple[float, float]:
    obs = _make_client()
    latencies: list[float] = []
    for _ in range(n):
        t0 = time.perf_counter()
        span = obs.start_span(provider="openai", model="gpt-4o-mini", request={"messages": []})
        span.set_usage(prompt_tokens=10, completion_tokens=5)
        span.end(status="success")
        latencies.append((time.perf_counter() - t0) * 1000)
    p50 = statistics.median(latencies)
    p99 = sorted(latencies)[int(n * 0.99) - 1]
    return p50, p99


def bench_pii_redact(n: int = 2000) -> float:
    from llm_obs.guard import redact_text

    sample = "Contact alice@example.com or call 555-123-4567. Card 4111111111111111."
    t0 = time.perf_counter()
    for _ in range(n):
        redact_text(sample)
    return (time.perf_counter() - t0) / n * 1000


def main() -> None:
    tracemalloc.start()
    span_p50, span_p99 = bench_span_end()
    pii_ms = bench_pii_redact()
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    print("llm-obs overhead benchmark (local, no network flush)")
    print(f"  span create+end (p50):  {span_p50:.3f} ms")
    print(f"  span create+end (p99):  {span_p99:.3f} ms")
    print(f"  PII redact (per call):  {pii_ms:.3f} ms")
    print(f"  peak traced memory:     {peak / 1024:.1f} KiB")


if __name__ == "__main__":
    main()
