# Examples

| File | Stack | Install extras |
|------|--------|----------------|
| [`openai_basic.py`](openai_basic.py) | OpenAI async client | `llm-obs[openai]` |
| [`langchain_basic.py`](langchain_basic.py) | LangChain + ChatOpenAI | `llm-obs[openai]` + `langchain` `langchain-openai` |
| [`crewai_basic.py`](crewai_basic.py) | CrewAI crew kickoff | `llm-obs[openai]` + `crewai` |
| [`litellm_basic.py`](litellm_basic.py) | LiteLLM `acompletion` | `llm-obs[openai]` + `litellm` |
| [`benchmark_overhead.py`](benchmark_overhead.py) | Local overhead (no API) | `llm-obs` only |

```bash
export INGEST_URL=http://localhost:4000
export INGEST_API_KEY=dev-key
export OPENAI_API_KEY=sk-...

python examples/openai_basic.py
```

Separate per-framework demo repos are planned; these snippets stay in-tree for now.
