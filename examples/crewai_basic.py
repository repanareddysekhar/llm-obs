"""
CrewAI — instrument once at startup; Crew agents using OpenAI/Anthropic are traced.

Requires: pip install "llm-obs[openai]" crewai
Env: OPENAI_API_KEY, INGEST_URL (optional)

Note: Call auto_instrument() before importing crew modules when possible.
"""
import os

from llm_obs import ObservabilityClient, set_obs_context


def main() -> None:
    obs = ObservabilityClient(
        endpoint=os.environ.get("INGEST_URL", "http://localhost:4000"),
        api_key=os.environ.get("INGEST_API_KEY"),
    )
    obs.auto_instrument()
    set_obs_context(conversation_id="demo-crewai-1")

    from crewai import Agent, Task, Crew, Process

    researcher = Agent(
        role="Researcher",
        goal="Answer briefly",
        backstory="You are concise.",
        verbose=False,
    )
    task = Task(
        description="Say hello in five words.",
        expected_output="A short greeting.",
        agent=researcher,
    )
    crew = Crew(agents=[researcher], tasks=[task], process=Process.sequential)
    result = crew.kickoff()
    print(result)
    obs.flush()


if __name__ == "__main__":
    main()
