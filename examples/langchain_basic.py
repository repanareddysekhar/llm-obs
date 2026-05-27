"""
LangChain — works via underlying OpenAI/Anthropic clients patched by auto_instrument.

Requires: pip install "llm-obs[openai]" langchain langchain-openai
Env: OPENAI_API_KEY, INGEST_URL (optional)
"""
import os

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from llm_obs import ObservabilityClient, set_obs_context


def main() -> None:
    obs = ObservabilityClient(
        endpoint=os.environ.get("INGEST_URL", "http://localhost:4000"),
        api_key=os.environ.get("INGEST_API_KEY"),
    )
    obs.auto_instrument()

    set_obs_context(conversation_id="demo-langchain-1")
    llm = ChatOpenAI(model="gpt-4o-mini")
    out = llm.invoke([HumanMessage(content="Say hello in five words.")])
    print(out.content)
    obs.flush()


if __name__ == "__main__":
    main()
