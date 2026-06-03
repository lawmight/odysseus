#!/usr/bin/env bash
# Scan the tree for likely committed secrets. Tightens SECURITY.md patterns to
# reduce false positives (e.g. HTML ids like task-form-* matching sk-).
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

PATTERN='( (^|[^A-Za-z0-9])sk-[A-Za-z0-9_-]{20,}|xox[baprs]-[0-9A-Za-z-]{10,}|AIza[0-9A-Za-z_-]{20,}|Bearer [A-Za-z0-9._~+/-]{20,})'

matches="$(git grep -n -I -E "$PATTERN" -- . ':!static/lib/**' ':!package-lock.json' || true)"

if [[ -n "$matches" ]]; then
  echo "Possible secrets found (see SECURITY.md):"
  echo "$matches"
  exit 1
fi

echo "No secret patterns matched."
