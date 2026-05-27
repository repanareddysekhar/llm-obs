from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from .id import new_id
from .metrics.cost import compute_cost

if TYPE_CHECKING:
    from .client import ObservabilityClient


@dataclass
class InferenceSpan:
    id: str = field(default_factory=new_id)
    conversation_id: str | None = None
    session_id: str | None = None
    provider: str = ""
    model: str = ""
    request: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    _client: "ObservabilityClient | None" = field(default=None, repr=False)
    _started_at: float = field(default_factory=time.monotonic, repr=False)
    _started_iso: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(), repr=False
    )
    _ttft_ms: int | None = field(default=None, repr=False)
    _output_chunks: list[str] = field(default_factory=list, repr=False)
    _usage: dict[str, int] = field(default_factory=dict, repr=False)
    _error: dict[str, str] | None = field(default=None, repr=False)
    _ended: bool = field(default=False, repr=False)

    def set_ttft(self, ms: int | None = None) -> None:
        if self._ttft_ms is None:
            self._ttft_ms = (
                ms if ms is not None
                else int((time.monotonic() - self._started_at) * 1000)
            )

    def append_output(self, chunk: str) -> None:
        self._output_chunks.append(chunk)

    def set_usage(
        self,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
    ) -> None:
        if prompt_tokens is not None:
            self._usage["prompt_tokens"] = prompt_tokens
        if completion_tokens is not None:
            self._usage["completion_tokens"] = completion_tokens

    def set_error(self, error_type: str, message: str, code: str | None = None) -> None:
        self._error = {"type": error_type, "message": message[:500]}
        if code:
            self._error["code"] = code

    def set_metadata(self, **kwargs: Any) -> None:
        self.metadata.update(kwargs)

    def end(
        self,
        status: str = "success",
        finish_reason: str | None = None,
        streamed: bool = False,
    ) -> None:
        if self._ended:
            return
        self._ended = True

        ended_at = datetime.now(timezone.utc).isoformat()
        latency_ms = int((time.monotonic() - self._started_at) * 1000)
        full_output = "".join(self._output_chunks)

        prompt_tokens = self._usage.get("prompt_tokens")
        completion_tokens = self._usage.get("completion_tokens")

        # Cost computed deterministically in the SDK — no worker needed
        cost_usd = compute_cost(
            self.provider, self.model, prompt_tokens, completion_tokens
        )

        payload: dict[str, Any] = {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "session_id": self.session_id,
            "provider": self.provider,
            "model": self.model,
            "status": status,
            "started_at": self._started_iso,
            "ended_at": ended_at,
            "latency_ms": latency_ms,
            "ttft_ms": self._ttft_ms,
            "streamed": streamed,
            "request": self.request,
            "response": {
                "content": full_output[:2048],
                "finish_reason": finish_reason,
            },
            "usage": self._usage or None,
            "cost_usd": cost_usd,
            "error": self._error,
            "metadata": self.metadata or None,
        }

        if self._client:
            self._client.log(payload)
