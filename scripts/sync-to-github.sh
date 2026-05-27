#!/usr/bin/env bash
# Sync local sdk/ to the standalone GitHub repo and push.
#
# Usage:
#   ./scripts/sync-to-github.sh
#   ./scripts/sync-to-github.sh https://github.com/repanareddysekhar/llm-obs.git

set -euo pipefail

REMOTE="${1:-https://github.com/repanareddysekhar/llm-obs.git}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CLONE_DIR="$(mktemp -d)"

cleanup() { rm -rf "$CLONE_DIR"; }
trap cleanup EXIT

git clone "$REMOTE" "$CLONE_DIR"
rsync -a --delete \
  --exclude '.git' \
  --exclude '.venv' \
  --exclude '__pycache__' \
  --exclude '*.egg-info' \
  --exclude '.pytest_cache' \
  --exclude '.ruff_cache' \
  "$ROOT/" "$CLONE_DIR/"

cd "$CLONE_DIR"
if git diff --quiet && git diff --cached --quiet; then
  echo "No changes to push."
  exit 0
fi

git add -A
git commit -m "${2:-Sync from llm-observability monorepo}"
git push origin main
echo "Synced to $REMOTE"
