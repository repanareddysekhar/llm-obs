"""
LlamaIndex — dedicated callback handler.

Requires: pip install "llm-obs[llamaindex]"
Env: OPENAI_API_KEY (or your LLM provider), INGEST_URL
"""
import os

from llama_index.core import Document, VectorStoreIndex

from llm_obs import ObservabilityClient
from llm_obs.integrations import instrument_llamaindex


def main() -> None:
    obs = ObservabilityClient(
        endpoint=os.environ.get("INGEST_URL", "http://localhost:4000"),
        api_key=os.environ.get("INGEST_API_KEY"),
    )
    instrument_llamaindex(obs)

    # Minimal in-memory index (no files required)
    docs = [Document(text="llm-obs traces LlamaIndex LLM and embedding calls.")]
    index = VectorStoreIndex.from_documents(docs)
    query_engine = index.as_query_engine()
    response = query_engine.query("What does llm-obs trace?")
    print(response)
    obs.flush()


if __name__ == "__main__":
    main()
