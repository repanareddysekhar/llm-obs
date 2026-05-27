"""
Unified streaming interface for all LLM providers.

The web app (or any client) calls stream_chat() — that's it.
All provider-specific logic lives here in the SDK.
Providers are auto-detected from URLs via discovery.py.

Environment variables:
  LLM_ENDPOINTS   comma-separated URLs (new-style, recommended)
                  e.g. "http://localhost:11434,http://private-vpc:8080"
  Legacy keys still supported: OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.
"""
from __future__ import annotations

import asyncio
import os
from typing import AsyncIterator, Any

from .logging import get_logger
from .guard import sanitize_messages_for_llm
from .discovery import (
    DiscoveredProvider,
    discover_from_env,
    to_providers_dict,
    openai_base_url,
    _bedrock_region_from_url,
)

logger = get_logger("streaming")

# Populated lazily on first call
_discovered_cache: list[DiscoveredProvider] | None = None


def _get_discovered() -> list[DiscoveredProvider]:
    global _discovered_cache
    if _discovered_cache is None:
        _discovered_cache = discover_from_env()
    return _discovered_cache


def _find_endpoint(key: str) -> DiscoveredProvider | None:
    """Resolve UI/API provider key to a discovered endpoint."""
    for d in _get_discovered():
        if d.key == key:
            return d
    for d in _get_discovered():
        if d.provider == key:
            return d
    return None


def available_providers() -> dict[str, list[str]]:
    """
    Returns {provider: [models]} based on URLs detected from env.
    Used by the web UI to build provider/model dropdowns.
    """
    return to_providers_dict(_get_discovered())


async def stream_chat(
    provider: str,
    model: str,
    messages: list[dict],
    cancel_event: asyncio.Event | None = None,
) -> AsyncIterator[str]:
    """
    Unified async streaming entry point. Yields text delta chunks.
    Provider config (URL, API key) resolved from discovered providers.
    Observability injected transparently by auto_instrument().

    PII is sanitized here once, before any provider SDK is called.
    """
    messages = sanitize_messages_for_llm(messages)
    info = _find_endpoint(provider)
    if not info:
        available = [d.key for d in _get_discovered()]
        raise ValueError(f"Unknown endpoint {provider!r}. Available: {available}")

    route = info.provider
    if route in ("openai", "openai_compatible", "ollama"):
        async for chunk in _openai_compat_stream(info, model, messages, cancel_event):
            yield chunk
    elif route == "anthropic":
        async for chunk in _anthropic_stream(model, messages, cancel_event, info):
            yield chunk
    elif route == "google":
        async for chunk in _gemini_stream(model, messages, cancel_event, info):
            yield chunk
    elif route == "bedrock":
        async for chunk in _bedrock_stream(model, messages, cancel_event, info):
            yield chunk
    else:
        raise ValueError(f"Unsupported provider type: {route!r}")


async def _openai_compat_stream(
    info: DiscoveredProvider,
    model: str,
    messages: list[dict],
    cancel_event: asyncio.Event | None,
) -> AsyncIterator[str]:
    """
    Handles OpenAI, Ollama, vLLM, LiteLLM, ngrok, private VPC, and any OpenAI-compatible endpoint.
    """
    from openai import AsyncOpenAI

    if info.base_url and "api.openai.com" not in info.base_url:
        base_url = openai_base_url(info.base_url)
        api_key = info.api_key or "no-key"
    else:
        base_url = None
        api_key = info.api_key or os.environ.get("OPENAI_API_KEY")

    client = AsyncOpenAI(base_url=base_url, api_key=api_key)
    stream = await client.chat.completions.create(
        model=model,
        messages=messages,
        stream=True,
        stream_options={"include_usage": True},
    )
    async for chunk in stream:
        if cancel_event and cancel_event.is_set():
            await stream.close()
            return
        if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


async def _anthropic_stream(
    model: str,
    messages: list[dict],
    cancel_event: asyncio.Event | None,
    info: DiscoveredProvider | None = None,
) -> AsyncIterator[str]:
    from anthropic import AsyncAnthropic

    info = info or _find_endpoint("anthropic")
    api_key = (info.api_key if info else None) or os.environ.get("ANTHROPIC_API_KEY")
    client = AsyncAnthropic(api_key=api_key)

    system = next((m["content"] for m in messages if m["role"] == "system"), None)
    user_messages = [m for m in messages if m["role"] != "system"]
    kwargs: dict[str, Any] = {
        "model": model, "messages": user_messages, "max_tokens": 2048, "stream": True,
    }
    if system:
        kwargs["system"] = system

    stream = await client.messages.create(**kwargs)
    async for event in stream:
        if cancel_event and cancel_event.is_set():
            await stream.close()
            return
        if type(event).__name__ == "RawContentBlockDeltaEvent":
            text = getattr(event.delta, "text", "")
            if text:
                yield text


async def _gemini_stream(
    model: str,
    messages: list[dict],
    cancel_event: asyncio.Event | None,
    info: DiscoveredProvider | None = None,
) -> AsyncIterator[str]:
    import google.generativeai as genai

    info = info or _find_endpoint("google")
    api_key = (info.api_key if info else None) or os.environ.get("GOOGLE_API_KEY")
    genai.configure(api_key=api_key)

    system_parts = [m["content"] for m in messages if m["role"] == "system"]
    convo = [m for m in messages if m["role"] != "system"]
    history = [
        {"role": "model" if m["role"] == "assistant" else "user", "parts": [m["content"]]}
        for m in convo[:-1]
    ]
    gemini_model = genai.GenerativeModel(
        model, system_instruction=system_parts[0] if system_parts else None
    )
    response = await gemini_model.generate_content_async(messages, stream=True)
    async for chunk in response:
        if cancel_event and cancel_event.is_set():
            return
        try:
            if chunk.text:
                yield chunk.text
        except Exception:
            pass


async def _bedrock_stream(
    model: str,
    messages: list[dict],
    cancel_event: asyncio.Event | None,
    info: DiscoveredProvider | None = None,
) -> AsyncIterator[str]:
    """Stream from AWS Bedrock."""
    import json
    import boto3

    info = info or _find_endpoint("bedrock")
    region = os.environ.get("AWS_REGION", "us-east-1")
    if info and info.meta.get("region"):
        region = info.meta["region"]
    elif info and info.base_url:
        region = _bedrock_region_from_url(info.base_url)
    bedrock = boto3.client("bedrock-runtime", region_name=region)

    system = next((m["content"] for m in messages if m["role"] == "system"), None)
    user_messages = [m for m in messages if m["role"] != "system"]
    body: dict[str, Any] = {
        "anthropic_version": "bedrock-2023-05-31",
        "messages": user_messages,
        "max_tokens": 2048,
    }
    if system:
        body["system"] = system

    response = await asyncio.to_thread(
        bedrock.invoke_model_with_response_stream,
        modelId=model,
        body=json.dumps(body),
    )
    for event in response.get("body", []):
        if cancel_event and cancel_event.is_set():
            return
        chunk = event.get("chunk", {})
        if chunk:
            data = json.loads(chunk.get("bytes", b"{}"))
            if data.get("type") == "content_block_delta":
                text = data.get("delta", {}).get("text", "")
                if text:
                    yield text
