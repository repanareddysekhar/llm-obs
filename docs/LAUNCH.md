# Launch checklist (maintainers)

Use this after the standalone repo is on GitHub and CI is green.

## 1. PyPI (primary distribution)

1. Create account: https://pypi.org/account/register/
2. Create project `llm-obs` (or claim if name taken).
3. Generate API token (scope: project `llm-obs`).
4. Configure **trusted publishing** on PyPI (required for the current workflow):
   - PyPI → **Account settings** → **Publishing** → Add trusted publisher
   - PyPI project name: `llm-obs` (create the project first if needed)
   - Owner: `repanareddysekhar`
   - Repository: `llm-obs`
   - Workflow: `publish.yml`
   - Environment: `pypi`
   - GitHub repo → **Settings → Environments** → create environment named `pypi` (no secrets required for trusted publishing)
   - Docs: https://docs.pypi.org/trusted-publishers/
5. Tag release `v0.1.3` on GitHub → `publish.yml` uploads the wheel.

Verify: `pip install llm-obs`

## 2. GitHub repo polish

- [ ] Description: *Lightweight Python SDK for LLM inference logging and observability*
- [ ] Topics: `llm`, `observability`, `openai`, `anthropic`, `python`, `tracing`, `pii`
- [ ] Enable Issues and Discussions (optional)
- [ ] Pin README quickstart

## 3. HackerOne (security, not marketing)

[HackerOne Community Edition](https://www.hackerone.com/product/community-edition) is for **vulnerability disclosure**, not announcing the SDK.

Apply after you have:

- Public repo with OSI license (MIT ✓)
- `SECURITY.md` in root ✓
- Ability to respond to reports within ~7 days

Then link the program URL in `SECURITY.md`.

## 4. Social / community (copy-paste drafts)

### Show HN (news.ycombinator.com/submit)

**Title:** Show HN: llm-obs – Python SDK for LLM call logging with PII redaction

**Text:** We open-sourced a small SDK that auto-instruments OpenAI/Anthropic/Gemini/Bedrock (and Ollama-compatible URLs), batches inference metadata to any HTTP ingest endpoint, and redacts PII before it leaves the process. MIT, `pip install llm-obs`. Repo: <your-repo-url>

### X / Twitter

> Shipped the open-source `llm-obs` Python SDK: one-line `auto_instrument()` for OpenAI, Anthropic, Gemini, Bedrock + Ollama-style endpoints. PII redacted in-process, logs to any HTTP ingest API. MIT · pip install llm-obs · <repo-url>

### LinkedIn / Dev.to

Expand the README quickstart + link to architecture of PII + batch transport.

## 5. Monorepo sync

The private/full `llm-observability` repo can depend on the published package:

```bash
pip install llm-obs==0.1.3
```

Or git submodule / subtree from `llm-obs` for co-development.
