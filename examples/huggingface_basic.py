"""
Hugging Face Inference API — auto_instrument patches InferenceClient.

Requires: pip install "llm-obs[huggingface]"
Env: HF_TOKEN or HUGGINGFACEHUB_API_TOKEN, INGEST_URL
"""
import os

from huggingface_hub import InferenceClient

from llm_obs import ObservabilityClient, set_obs_context


def main() -> None:
    obs = ObservabilityClient(
        endpoint=os.environ.get("INGEST_URL", "http://localhost:4000"),
        api_key=os.environ.get("INGEST_API_KEY"),
    )
    obs.auto_instrument()

    set_obs_context(conversation_id="demo-hf-1")
    client = InferenceClient()
    out = client.text_generation(
        "Say hello in five words.",
        model="meta-llama/Llama-3.2-3B-Instruct",
        max_new_tokens=32,
    )
    print(out)
    obs.flush()


if __name__ == "__main__":
    main()
