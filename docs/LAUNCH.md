# Launch checklist (maintainers)

Use this after the standalone repo is on GitHub and CI is green.

## 1. Deploy from GitHub to PyPI

Your repo already has [`.github/workflows/publish.yml`](https://github.com/repanareddysekhar/llm-obs/blob/main/.github/workflows/publish.yml). It uses **trusted publishing** (no API token in GitHub secrets).

### A. Link PyPI to GitHub (one-time)

On [pypi.org/project/llm-obs](https://pypi.org/project/llm-obs/) (or **Publishing** in account settings):

1. **Add a new trusted publisher**
2. Fill in exactly:

| Field | Value |
|-------|--------|
| PyPI Project Name | `llm-obs` |
| Owner | `repanareddysekhar` |
| Repository name | `llm-obs` |
| Workflow name | `publish.yml` |
| Environment name | `pypi` |

3. On GitHub: [llm-obs → Settings → Environments](https://github.com/repanareddysekhar/llm-obs/settings/environments) — ensure an environment named **`pypi`** exists (you already have this).

Official guide: [PyPI trusted publishers](https://docs.pypi.org/trusted-publishers/).

### B. Run the deploy

**Option 1 — Manual (after trusted publisher is saved):**

GitHub → **Actions** → **Publish to PyPI** → **Run workflow** → Run on `main`.

Or:

```bash
gh workflow run publish.yml -R repanareddysekhar/llm-obs
```

**Option 2 — On every release (automatic):**

```bash
# bump version in pyproject.toml + llm_obs/client.py first, then:
git tag v0.1.4
git push origin v0.1.4
gh release create v0.1.4 -R repanareddysekhar/llm-obs --generate-notes
```

Publishing runs when the release is **published** (not draft).

### C. Verify

```bash
pip install llm-obs
pip show llm-obs
```

Check [pypi.org/project/llm-obs](https://pypi.org/project/llm-obs/) shows the new version and release files.

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
pip install llm-obs==0.1.4
```

Or git submodule / subtree from `llm-obs` for co-development.
