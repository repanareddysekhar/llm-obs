#!/usr/bin/env bash
# Push sdk/ contents to a standalone GitHub repo (open-source home for llm-obs).
#
# Usage:
#   ./scripts/push-standalone-repo.sh git@github.com:YOUR_ORG/llm-obs.git
#
# Prerequisites:
#   - Empty public repo created on GitHub (no README/license — or force-push once).
#   - git, rsync installed.

set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <git-remote-url>" >&2
  exit 1
fi

REMOTE="$1"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STAGE="$(mktemp -d)"

cleanup() { rm -rf "$STAGE"; }
trap cleanup EXIT

rsync -a \
  --exclude '.venv' \
  --exclude '__pycache__' \
  --exclude '*.egg-info' \
  --exclude '.pytest_cache' \
  --exclude '.ruff_cache' \
  "$ROOT/" "$STAGE/"

cd "$STAGE"
git init -b main
git add -A
git commit -m "$(cat <<'EOF'
Initial open-source release of llm-obs SDK.

MIT-licensed Python SDK for LLM inference logging, PII redaction,
and multi-provider auto-instrumentation.
EOF
)"
git remote add origin "$REMOTE"
git push -u origin main

echo "Pushed to $REMOTE"
