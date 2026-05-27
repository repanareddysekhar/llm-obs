# Repository security

## When workflows run

| Workflow | Trigger | What it does |
|----------|---------|----------------|
| **CI** (`ci.yml`) | Push to `main` | Lint + tests on Python 3.11 and 3.12 |
| **CI** (`ci.yml`) | Pull request targeting `main` | Same checks on the PR branch |
| **Publish to PyPI** (`publish.yml`) | GitHub Release **published** | Builds and uploads to PyPI (uses `pypi` environment) |
| **Publish to PyPI** (`publish.yml`) | **Run workflow** (manual) | Same as above; only if you are allowed on the `pypi` environment |

CI does **not** deploy. Only **Publish to PyPI** can upload packages.

## Who can run pipelines?

| Actor | CI workflow | Publish workflow |
|-------|-------------|------------------|
| **You** (repo owner) | Yes | Yes (if `pypi` environment allows you) |
| **Collaborators** with Write | Yes on push/PR | Manual run only if you add them to `pypi` environment reviewers (not recommended) |
| **Outside contributors** (fork PR) | CI only, if repo allows fork workflows | No publish secrets/OIDC; cannot use `pypi` environment |
| **Random internet users** | Cannot push to `main` if branch protection is on | Cannot create releases or approve `pypi` |

### Recommended GitHub settings

**Settings → Actions → General**

- *Fork pull request workflows*: **Run workflows from fork pull requests** → **Require approval for first-time contributors** (or disable if you do not want fork CI).
- *Workflow permissions*: **Read repository contents** for GITHUB_TOKEN (default). Publish uses OIDC to PyPI, not a long-lived token in the repo.

**Settings → Actions → General → Workflow permissions**

- Keep **Read** unless a workflow needs write (yours do not).

**Environment `pypi`** (critical for PyPI)

- **Required reviewers**: only you (`repanareddysekhar`).
- **Deployment branches**: **Selected branches** → `main` only (or restrict tags via rules below).
- Optional: **Wait timer** 0, no self-approval bypass if you add more admins later.

**Settings → Collaborators**

- Give **Read** to contributors; **Write** only to people you trust to merge after your review.

## Code ownership and PR reviews

`/.github/CODEOWNERS` marks **@repanareddysekhar** as owner of all files.

With branch protection (see below), every PR needs **your approval** before merge to `main`.

## Branch protection on `main`

Enable in **Settings → Branches → Add rule** for `main`:

- [x] Require a pull request before merging
- [x] Require approvals: **1**
- [x] Require review from Code Owners
- [x] Require status checks to pass: **test** (or all CI jobs)
- [x] Require branches to be up to date before merging
- [x] Do not allow bypassing the above settings
- [ ] Restrict who can push to matching branches (optional: only you)

## Releases and PyPI

- Creating a **Release** triggers publish. Restrict who can publish releases: **Settings → Actions** does not cover this; use **only owner creates releases** habit, or enable **Restrict release creation** if available on your plan.
- After a bad upload, bump version (PyPI cannot replace the same version).

## Trusted publishing

PyPI trusted publisher is bound to `repanareddysekhar/llm-obs` + workflow `publish.yml` + environment `pypi`. A fork cannot satisfy those claims for your project.
