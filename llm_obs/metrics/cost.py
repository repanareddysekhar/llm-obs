"""
Deterministic cost computation inside the SDK.
Cost is calculated before the payload leaves the process — no worker needed.
"""
from __future__ import annotations

PRICE_TABLE: dict[str, dict[str, float]] = {
    # OpenAI
    "openai:gpt-4o-mini":                {"input": 0.15 / 1e6, "output": 0.60 / 1e6},
    "openai:gpt-4.1-mini":               {"input": 0.40 / 1e6, "output": 1.60 / 1e6},
    "openai:gpt-4o":                     {"input": 2.50 / 1e6, "output": 10.00 / 1e6},
    "openai:gpt-4.1":                    {"input": 2.00 / 1e6, "output": 8.00 / 1e6},
    # Anthropic (direct)
    "anthropic:claude-3-5-haiku-latest":   {"input": 0.80 / 1e6,  "output": 4.00 / 1e6},
    "anthropic:claude-3-5-sonnet-latest":  {"input": 3.00 / 1e6,  "output": 15.00 / 1e6},
    "anthropic:claude-sonnet-4-5":         {"input": 3.00 / 1e6,  "output": 15.00 / 1e6},
    # Google
    "google:gemini-1.5-flash":             {"input": 0.075 / 1e6, "output": 0.30 / 1e6},
    "google:gemini-1.5-pro":              {"input": 1.25 / 1e6,  "output": 5.00 / 1e6},
    "google:gemini-2.0-flash":            {"input": 0.10 / 1e6,  "output": 0.40 / 1e6},
    # AWS Bedrock — Anthropic models
    "bedrock:anthropic.claude-3-5-sonnet-20241022-v2:0": {"input": 3.00 / 1e6, "output": 15.00 / 1e6},
    "bedrock:anthropic.claude-3-5-haiku-20241022-v1:0":  {"input": 0.80 / 1e6, "output": 4.00 / 1e6},
    "bedrock:anthropic.claude-3-haiku-20240307-v1:0":    {"input": 0.25 / 1e6, "output": 1.25 / 1e6},
    "bedrock:anthropic.claude-3-sonnet-20240229-v1:0":   {"input": 3.00 / 1e6, "output": 15.00 / 1e6},
    # AWS Bedrock — Amazon Titan
    "bedrock:amazon.titan-text-express-v1":  {"input": 0.20 / 1e6, "output": 0.60 / 1e6},
    "bedrock:amazon.titan-text-lite-v1":     {"input": 0.15 / 1e6, "output": 0.20 / 1e6},
    "bedrock:amazon.titan-text-premier-v1:0":{"input": 0.50 / 1e6, "output": 1.50 / 1e6},
    # AWS Bedrock — Meta Llama
    "bedrock:meta.llama3-8b-instruct-v1:0":  {"input": 0.22 / 1e6, "output": 0.22 / 1e6},
    "bedrock:meta.llama3-70b-instruct-v1:0": {"input": 0.99 / 1e6, "output": 0.99 / 1e6},
    "bedrock:meta.llama3-1-8b-instruct-v1:0":{"input": 0.22 / 1e6, "output": 0.22 / 1e6},
    "bedrock:meta.llama3-1-70b-instruct-v1:0":{"input": 0.72 / 1e6,"output": 0.72 / 1e6},
    # AWS Bedrock — Mistral
    "bedrock:mistral.mistral-7b-instruct-v0:2": {"input": 0.15 / 1e6, "output": 0.20 / 1e6},
    "bedrock:mistral.mixtral-8x7b-instruct-v0:1":{"input": 0.45 / 1e6,"output": 0.70 / 1e6},
}

# Estimated local compute cost for Ollama (GPU amortisation, ~$0.10–0.40/hr)
OLLAMA_PRICE_TABLE: dict[str, dict[str, float]] = {
    # Sub-2B — minimal power draw
    "gemma3:1b":        {"input": 0.02 / 1e6, "output": 0.02 / 1e6},
    "llama3.2:1b":      {"input": 0.02 / 1e6, "output": 0.02 / 1e6},
    "phi3:mini":        {"input": 0.02 / 1e6, "output": 0.02 / 1e6},
    "gemma2:2b":        {"input": 0.02 / 1e6, "output": 0.02 / 1e6},
    "deepseek-r1:1.5b": {"input": 0.02 / 1e6, "output": 0.02 / 1e6},
    # 4B–8B mid-tier
    "gemma3:4b":        {"input": 0.08 / 1e6, "output": 0.08 / 1e6},
    "gemma2:9b":        {"input": 0.08 / 1e6, "output": 0.08 / 1e6},
    "llama3.2":         {"input": 0.08 / 1e6, "output": 0.08 / 1e6},
    "llama3.1:8b":      {"input": 0.08 / 1e6, "output": 0.08 / 1e6},
    "mistral":          {"input": 0.08 / 1e6, "output": 0.08 / 1e6},
    "mistral:7b":       {"input": 0.08 / 1e6, "output": 0.08 / 1e6},
    "phi3":             {"input": 0.08 / 1e6, "output": 0.08 / 1e6},
    "qwen2.5:7b":       {"input": 0.08 / 1e6, "output": 0.08 / 1e6},
    "deepseek-r1:7b":   {"input": 0.08 / 1e6, "output": 0.08 / 1e6},
    "codellama:7b":     {"input": 0.08 / 1e6, "output": 0.08 / 1e6},
    "codellama":        {"input": 0.08 / 1e6, "output": 0.08 / 1e6},
    # 12B+ higher GPU utilisation
    "gemma3:12b":       {"input": 0.20 / 1e6, "output": 0.20 / 1e6},
    "llama3.1":         {"input": 0.20 / 1e6, "output": 0.20 / 1e6},
    "mistral-nemo":     {"input": 0.20 / 1e6, "output": 0.20 / 1e6},
    "qwen2.5":          {"input": 0.20 / 1e6, "output": 0.20 / 1e6},
}
_OLLAMA_DEFAULT = {"input": 0.08 / 1e6, "output": 0.08 / 1e6}


def compute_cost(
    provider: str,
    model: str,
    prompt_tokens: int | None,
    completion_tokens: int | None,
) -> float | None:
    """
    Deterministically compute cost_usd in the SDK before the payload is shipped.
    Returns None if token counts are unavailable or the model isn't in the price table.
    """
    if prompt_tokens is None or completion_tokens is None:
        return None

    p = provider.lower()
    m = model.lower()

    if p == "ollama":
        base = m.split(":latest")[0]
        prices = OLLAMA_PRICE_TABLE.get(base) or OLLAMA_PRICE_TABLE.get(m) or _OLLAMA_DEFAULT
        return prices["input"] * prompt_tokens + prices["output"] * completion_tokens

    key = f"{p}:{m}"
    prices = PRICE_TABLE.get(key)
    if not prices:
        return None
    return prices["input"] * prompt_tokens + prices["output"] * completion_tokens
