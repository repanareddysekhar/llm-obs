"""
OpenAI — zero-touch auto instrumentation.

Requires: pip install "llm-obs[openai]"
Env: OPENAI_API_KEY, INGEST_URL (optional), INGEST_API_KEY (optional)
"""
import asyncio
import os

from openai import AsyncOpenAI

from llm_obs import ObservabilityClient, set_obs_context


async def main() -> None:
    obs = ObservabilityClient(
        endpoint=os.environ.get("INGEST_URL", "http://localhost:4000"),
        api_key=os.environ.get("INGEST_API_KEY"),
    )
    obs.auto_instrument()

    set_obs_context(conversation_id="demo-openai-1")
    client = AsyncOpenAI()
    resp = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Say hello in five words."}],
    )
    print(resp.choices[0].message.content)
    obs.flush()


if __name__ == "__main__":
    asyncio.run(main())
