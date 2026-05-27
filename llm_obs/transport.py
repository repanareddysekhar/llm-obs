from __future__ import annotations

import logging
import threading
import time
from typing import Any

import httpx

logger = logging.getLogger("llm_obs.transport")


class BatchTransport:
    """Buffers inference log payloads and flushes them in batches."""

    def __init__(
        self,
        endpoint: str,
        api_key: str | None = None,
        batch_size: int = 20,
        flush_interval_s: float = 2.0,
        max_retries: int = 3,
        on_error: Any = None,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.batch_size = batch_size
        self.flush_interval_s = flush_interval_s
        self.max_retries = max_retries
        self.on_error = on_error

        self._queue: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None
        self._client = httpx.Client(timeout=8.0)
        self._headers = {"Content-Type": "application/json"}
        if api_key:
            self._headers["x-obs-api-key"] = api_key
        self._start_timer()

    def enqueue(self, payload: dict[str, Any]) -> None:
        with self._lock:
            self._queue.append(payload)
            if len(self._queue) >= self.batch_size:
                batch = self._queue[:]
                self._queue.clear()
                self._send_async(batch)

    def flush(self) -> None:
        with self._lock:
            batch = self._queue[:]
            self._queue.clear()
        if batch:
            self._send_sync(batch)

    def shutdown(self) -> None:
        if self._timer:
            self._timer.cancel()
        self.flush()
        self._client.close()

    def _start_timer(self) -> None:
        self._timer = threading.Timer(self.flush_interval_s, self._on_timer)
        self._timer.daemon = True
        self._timer.start()

    def _on_timer(self) -> None:
        self.flush()
        self._start_timer()

    def _send_async(self, batch: list[dict[str, Any]]) -> None:
        t = threading.Thread(target=self._send_sync, args=(batch,), daemon=True)
        t.start()

    def _send_sync(self, batch: list[dict[str, Any]]) -> None:
        url = f"{self.endpoint}/v1/ingest/batch"
        body = {"events": batch}
        delay = 0.25
        for attempt in range(self.max_retries):
            try:
                resp = self._client.post(url, json=body, headers=self._headers)
                if resp.status_code < 500:
                    return
            except Exception as exc:
                logger.warning("Transport error (attempt %d): %s", attempt + 1, exc)
            time.sleep(delay)
            delay = min(delay * 2, 4.0)
        if self.on_error:
            try:
                self.on_error(f"Failed to send {len(batch)} events after {self.max_retries} retries")
            except Exception:
                pass
