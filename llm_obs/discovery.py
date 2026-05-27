"""
URL-based provider and model discovery.

Any HTTP(S) URL can be registered — ngrok tunnels, private VPC IPs, localhost,
cloud APIs, Bedrock shorthands, etc. Probing is best-effort; if nothing responds
we still register the endpoint as OpenAI-compatible so chat can try it.

LLM_ENDPOINTS syntax (comma-separated):
  http://10.0.1.5:8080
  https://abc123.ngrok.io|my-api-key
  my-vpc=http://10.0.1.5:8080|my-api-key          # optional alias for UI
  openai_compatible://http://10.0.1.5:8080        # force provider type
  ollama://http://localhost:11434
  bedrock://us-east-1

Legacy (when LLM_ENDPOINTS is empty): OPENAI_API_KEY, ANTHROPIC_API_KEY,
GOOGLE_API_KEY, OLLAMA_BASE_URL, BEDROCK_ENABLED, BEDROCK_RUNTIME_URL.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Literal
from urllib.parse import urlparse

from .logging import get_logger

logger = get_logger("discovery")

ProviderType = Literal[
    "openai",
    "anthropic",
    "google",
    "ollama",
    "openai_compatible",
    "bedrock",
    "unknown",
]

_URL_PROVIDER_MAP = [
    ("api.openai.com", "openai"),
    ("api.anthropic.com", "anthropic"),
    ("generativelanguage.googleapis.com", "google"),
    ("openai.azure.com", "openai"),
]

_PROVIDER_SCHEME_PREFIXES = (
    "openai_compatible://",
    "openai://",
    "ollama://",
    "anthropic://",
    "google://",
    "bedrock://",
    "bedrock:",
)


@dataclass
class EndpointSpec:
    url: str
    api_key: str | None = None
    provider_hint: ProviderType | None = None
    alias: str | None = None


@dataclass
class DiscoveredProvider:
    """One configured LLM endpoint."""

    provider: ProviderType
    base_url: str
    key: str
    models: list[str] = field(default_factory=list)
    api_key: str | None = None
    meta: dict = field(default_factory=dict)


def discover_from_env() -> list[DiscoveredProvider]:
    discovered: list[DiscoveredProvider] = []

    endpoints_raw = os.environ.get("LLM_ENDPOINTS", "").strip()
    if endpoints_raw:
        for raw in [u.strip() for u in endpoints_raw.split(",") if u.strip()]:
            discovered.append(detect_provider(raw))

    if not endpoints_raw:
        if os.environ.get("OPENAI_API_KEY"):
            discovered.append(DiscoveredProvider(
                provider="openai",
                key="openai",
                base_url="https://api.openai.com",
                models=_known_cloud_models("openai"),
                api_key=os.environ["OPENAI_API_KEY"],
            ))
        if os.environ.get("ANTHROPIC_API_KEY"):
            discovered.append(DiscoveredProvider(
                provider="anthropic",
                key="anthropic",
                base_url="https://api.anthropic.com",
                models=_known_cloud_models("anthropic"),
                api_key=os.environ["ANTHROPIC_API_KEY"],
            ))
        if os.environ.get("GOOGLE_API_KEY"):
            discovered.append(DiscoveredProvider(
                provider="google",
                key="google",
                base_url="https://generativelanguage.googleapis.com",
                models=_known_cloud_models("google"),
                api_key=os.environ["GOOGLE_API_KEY"],
            ))
        ollama_url = os.environ.get("OLLAMA_BASE_URL", "").strip()
        if ollama_url:
            discovered.append(detect_provider(ollama_url))

        bedrock_url = os.environ.get("BEDROCK_RUNTIME_URL", "").strip()
        if bedrock_url or _bedrock_enabled_in_env():
            if not bedrock_url:
                region = os.environ.get("AWS_REGION", "us-east-1")
                bedrock_url = f"https://bedrock-runtime.{region}.amazonaws.com"
            discovered.append(detect_provider(bedrock_url))

    return _dedupe_keys(discovered)


def detect_provider(
    raw: str,
    api_key: str | None = None,
    provider_hint: ProviderType | None = None,
) -> DiscoveredProvider:
    """
    Classify and probe a URL. Always returns a usable DiscoveredProvider for
    HTTP(S) URLs — never None.
    """
    alias: str | None = None
    if provider_hint is None and api_key is None:
        spec = _parse_endpoint_spec(raw)
        if spec.url != raw or spec.api_key or spec.provider_hint or spec.alias:
            raw = spec.url
            api_key = spec.api_key
            provider_hint = spec.provider_hint
            alias = spec.alias

    url = _normalize_url(raw)

    if provider_hint == "bedrock" or _is_bedrock_url(url):
        return _discover_bedrock(url)

    if provider_hint in ("openai", "anthropic", "google", "ollama", "openai_compatible"):
        probed = _probe_url(url, api_key)
        if probed and probed.provider == provider_hint:
            if alias:
                probed.key = alias
            return probed
        result = _fallback_provider(url, api_key, provider_hint)
        if alias:
            result.key = alias
        return result

    for pattern, provider in _URL_PROVIDER_MAP:
        if pattern in url:
            result = DiscoveredProvider(
                provider=provider,  # type: ignore[arg-type]
                key=alias or provider,
                base_url=url,
                models=_known_cloud_models(provider),
                api_key=api_key,
            )
            return result

    probed = _probe_url(url, api_key)
    if probed:
        if alias:
            probed.key = alias
        return probed

    result = _fallback_provider(url, api_key, "openai_compatible")
    if alias:
        result.key = alias
    return result


def to_providers_dict(discovered: list[DiscoveredProvider]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for d in discovered:
        result.setdefault(d.key, [])
        for m in d.models:
            if m not in result[d.key]:
                result[d.key].append(m)
    return result


def openai_base_url(base_url: str) -> str:
    """Build OpenAI client base_url from a discovered endpoint base."""
    base = base_url.rstrip("/")
    if base.endswith("/v1"):
        return base
    return f"{base}/v1"


# ── Parsing ───────────────────────────────────────────────────────────────────

def _parse_endpoint_spec(raw: str) -> EndpointSpec:
    text = raw.strip()
    provider_hint: ProviderType | None = None
    alias: str | None = None
    api_key: str | None = None

    for prefix in _PROVIDER_SCHEME_PREFIXES:
        if text.lower().startswith(prefix):
            provider_hint = _scheme_to_provider(prefix)
            text = text[len(prefix):]
            break

    if "://" in text and not text.lower().startswith(("http://", "https://")):
        scheme, rest = text.split("://", 1)
        if scheme.lower() in ("openai_compatible", "openai", "ollama", "anthropic", "google", "bedrock"):
            provider_hint = _scheme_to_provider(scheme.lower() + "://")
            text = rest

    if "=" in text and not text.lower().startswith(("http://", "https://")):
        name, rest = text.split("=", 1)
        if name and not name.lower().startswith(("http", "bedrock")):
            alias = name.strip()
            text = rest.strip()

    if "|" in text:
        text, api_key = text.split("|", 1)
        text = text.strip()
        api_key = api_key.strip() or None

    return EndpointSpec(
        url=_normalize_url(text),
        api_key=api_key,
        provider_hint=provider_hint,
        alias=alias,
    )


def _scheme_to_provider(prefix: str) -> ProviderType:
    p = prefix.lower().rstrip(":/")
    if p in ("openai_compatible", "openai"):
        return "openai_compatible" if p == "openai_compatible" else "openai"
    if p == "bedrock":
        return "bedrock"
    if p in ("ollama", "anthropic", "google"):
        return p  # type: ignore[return-value]
    return "openai_compatible"


def _normalize_url(url: str) -> str:
    url = url.strip().rstrip("/")
    if url.lower().startswith("bedrock://") or url.lower().startswith("bedrock:"):
        return url
    if not url.startswith(("http://", "https://")):
        url = f"http://{url}"
    return url


def _endpoint_key(url: str, provider: ProviderType) -> str:
    if provider in ("openai", "anthropic", "google", "bedrock", "ollama"):
        return provider
    parsed = urlparse(url)
    host = (parsed.hostname or "endpoint").replace(".", "_")
    port = parsed.port
    suffix = f"_{port}" if port else ""
    return f"custom_{host}{suffix}"


def _default_models() -> list[str]:
    default = os.environ.get("LLM_DEFAULT_MODEL", "").strip()
    if default:
        return [default]
    return ["default"]


def _fallback_provider(
    url: str,
    api_key: str | None,
    provider: ProviderType,
) -> DiscoveredProvider:
    key = _endpoint_key(url, provider)
    logger.info(
        "Registered %s at %s without probe confirmation (key=%s) — will use OpenAI-compatible client",
        provider,
        url,
        key,
    )
    return DiscoveredProvider(
        provider=provider,
        key=key,
        base_url=url,
        models=_default_models(),
        api_key=api_key,
        meta={"detected_via": "fallback", "probe_ok": False},
    )


def _dedupe_keys(items: list[DiscoveredProvider]) -> list[DiscoveredProvider]:
    seen: set[str] = set()
    out: list[DiscoveredProvider] = []
    for d in items:
        key = d.key
        n = 2
        while key in seen:
            key = f"{d.key}_{n}"
            n += 1
        d.key = key
        seen.add(key)
        out.append(d)
    return out


# ── Bedrock ───────────────────────────────────────────────────────────────────

def _discover_bedrock(url: str) -> DiscoveredProvider:
    region = _bedrock_region_from_url(url)
    models = _list_bedrock_models(region)
    base = url if url.startswith("http") else f"https://bedrock-runtime.{region}.amazonaws.com"
    logger.info("Detected Bedrock at %s (region=%s, %d models)", base, region, len(models))
    return DiscoveredProvider(
        provider="bedrock",
        key="bedrock",
        base_url=base,
        models=models,
        meta={"region": region},
    )


def _is_bedrock_url(url: str) -> bool:
    u = url.lower().strip()
    if u.startswith("bedrock://") or u.startswith("bedrock:"):
        return True
    return "bedrock" in u and ("amazonaws.com" in u or ".api.aws" in u)


def _bedrock_region_from_url(url: str) -> str:
    u = url.strip()
    if u.lower().startswith("bedrock://"):
        region = u[10:].strip("/").split("/")[0]
        return region or os.environ.get("AWS_REGION", "us-east-1")
    if u.lower().startswith("bedrock:"):
        region = u[8:].strip("/").split("/")[0]
        return region or os.environ.get("AWS_REGION", "us-east-1")
    patterns = [
        r"bedrock(?:-runtime|-agent-runtime)?\.([a-z0-9-]+)\.vpce\.amazonaws\.com",
        r"bedrock(?:-runtime|-agent-runtime)?\.([a-z0-9-]+)\.amazonaws\.com",
        r"bedrock(?:-runtime|-agent-runtime)?\.([a-z0-9-]+)\.api\.aws",
    ]
    for pat in patterns:
        m = re.search(pat, u.lower())
        if m:
            return m.group(1)
    return os.environ.get("AWS_REGION", "us-east-1")


def _bedrock_enabled_in_env() -> bool:
    flag = os.environ.get("BEDROCK_ENABLED", "").strip().lower()
    if flag in ("1", "true", "yes", "on"):
        return True
    return bool(os.environ.get("BEDROCK_RUNTIME_URL", "").strip())


def _list_bedrock_models(region: str | None = None) -> list[str]:
    region = region or os.environ.get("AWS_REGION", "us-east-1")
    try:
        import boto3
        client = boto3.client("bedrock", region_name=region)
        resp = client.list_foundation_models(byOutputModality="TEXT")
        models = [
            m["modelId"]
            for m in resp.get("modelSummaries", [])
            if m.get("responseStreamingSupported", False)
        ]
        return models or _bedrock_model_fallback()
    except Exception as exc:
        logger.warning("Bedrock model listing failed: %s", exc)
        return _bedrock_model_fallback()


def _bedrock_model_fallback() -> list[str]:
    return [
        "anthropic.claude-3-5-sonnet-20241022-v2:0",
        "anthropic.claude-3-5-haiku-20241022-v1:0",
        "anthropic.claude-3-haiku-20240307-v1:0",
        "meta.llama3-8b-instruct-v1:0",
        "meta.llama3-70b-instruct-v1:0",
        "amazon.titan-text-express-v1",
        "mistral.mistral-7b-instruct-v0:2",
    ]


# ── HTTP probing ──────────────────────────────────────────────────────────────

def _probe_url(url: str, api_key: str | None) -> DiscoveredProvider | None:
    import httpx

    headers: dict[str, str] = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    timeout = float(os.environ.get("LLM_PROBE_TIMEOUT", "5.0"))

    ollama = _probe_ollama(url, headers, timeout)
    if ollama:
        ollama.api_key = api_key
        return ollama

    compat = _probe_openai_compatible(url, headers, timeout, api_key)
    if compat:
        return compat

    return None


def _probe_ollama(url: str, headers: dict[str, str], timeout: float) -> DiscoveredProvider | None:
    import httpx

    for path in ("/api/tags", "/api/tags/"):
        try:
            resp = httpx.get(f"{url.rstrip('/')}{path}", headers=headers, timeout=timeout)
            if resp.status_code == 200:
                data = resp.json()
                if "models" in data:
                    models = [m["name"] for m in data["models"]]
                    logger.info("Detected Ollama at %s (%d models)", url, len(models))
                    return DiscoveredProvider(
                        provider="ollama",
                        key="ollama",
                        base_url=url,
                        models=models or _ollama_common_fallback(),
                        meta={"detected_via": "api/tags", "probe_ok": True},
                    )
        except Exception:
            continue
    return None


def _probe_openai_compatible(
    url: str,
    headers: dict[str, str],
    timeout: float,
    api_key: str | None,
) -> DiscoveredProvider | None:
    import httpx

    base = url.rstrip("/")
    candidates = [
        f"{base}/v1/models",
        f"{base}/models",
    ]
    if base.endswith("/v1"):
        candidates.insert(0, f"{base}/models")

    for endpoint in candidates:
        try:
            resp = httpx.get(endpoint, headers=headers, timeout=timeout)
            if resp.status_code != 200:
                continue
            data = resp.json()
            raw = data.get("data") or data.get("models") or []
            models = []
            for m in raw:
                if isinstance(m, dict):
                    models.append(m.get("id") or m.get("name") or str(m))
                else:
                    models.append(str(m))
            models = [m for m in models if m]
            logger.info("Detected OpenAI-compatible endpoint at %s (%d models)", url, len(models))
            return DiscoveredProvider(
                provider="openai_compatible",
                key=_endpoint_key(url, "openai_compatible"),
                base_url=url,
                models=models or _default_models(),
                api_key=api_key,
                meta={"detected_via": endpoint, "probe_ok": True},
            )
        except Exception:
            continue
    return None


def _known_cloud_models(provider: str) -> list[str]:
    return {
        "openai": ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini", "gpt-4.1"],
        "anthropic": ["claude-3-5-haiku-latest", "claude-3-5-sonnet-latest", "claude-sonnet-4-5"],
        "google": ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash"],
    }.get(provider, [])


def _ollama_common_fallback() -> list[str]:
    return [
        "gemma3:4b", "gemma3:1b", "llama3.2", "llama3.1:8b",
        "mistral", "phi3", "qwen2.5:7b", "deepseek-r1:7b",
    ]
