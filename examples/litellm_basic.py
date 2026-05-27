"""
LiteLLM — OpenAI-compatible path; auto_instrument patches openai when LiteLLM uses it.

For proxy mode, point LiteLLM at your model and ensure openai SDK is installed.

Requires: pip install "llm-obs[openai]" litellm
Env: OPENAI_API_KEY (or provider keys), INGEST_URL (optional)
"""
import asyncio
import os

import litellm

from llm_obs import ObservabilityClient, set_obs_context


async def main() -> None:
    obs = ObservabilityClient(
        endpoint=os.environ.get("INGEST_URL", "http://localhost:4000"),
        api_key=os.environ.get("INGEST_API_KEY"),
    )
    obs.auto_instrument()
    set_obs_context(conversation_id="demo-litellm-1")

    response = await litellm.acompletion(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Say hello in five words."}],
    )
    print(response.choices[0].message.content)
    obs.flush()


if __name__ == "__main__":
    asyncio.run(main())
