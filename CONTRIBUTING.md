# Contributing

Thanks for helping improve `llm-obs`.

## Development setup

```bash
git clone https://github.com/<org-or-user>/llm-obs.git
cd llm-obs
python -m venv .venv
source .venv/bin/activate
pip install -e ".[all,dev]"
```

Install dev extras (tests, lint) if present:

```bash
pip install pytest ruff
```

## Tests

```bash
pytest
```

## Pull requests

1. Open an issue for large changes, or comment on an existing one.
2. Keep PRs focused — one logical change per PR.
3. Add or update tests when behavior changes.
4. Ensure `pytest` and `ruff check .` pass locally.

## Releases

Maintainers tag `vX.Y.Z` on `main`; CI publishes to PyPI. Version bumps live in `pyproject.toml` and `llm_obs/client.py` (`sdk_version` default).
