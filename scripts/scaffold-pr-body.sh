#!/usr/bin/env bash
# Emit a PR body that passes validate-pr-body.js / the GitHub description bot.
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
SCAFFOLD="${ROOT}/.github/pr-body-scaffold.md"
OUT=""
ISSUE="0000"
SUMMARY="Describe what changed and why in one paragraph (at least twenty characters for the PR description bot)."

usage() {
  cat <<'EOF'
Usage: bash scripts/scaffold-pr-body.sh [options]

Writes a PR description to stdout or pr-body.md (repo root).

Options:
  -o, --output FILE   Write to FILE (default: stdout)
  --issue N           Upstream issue number for Linked Issue (default: 0000 — replace before merge)
  --summary TEXT      Summary section text (must be >= 20 characters)
  -h, --help          Show this help

Examples:
  bash scripts/scaffold-pr-body.sh > pr-body.md
  bash scripts/scaffold-pr-body.sh --issue 1958 --summary "Fix model list 0/0 display" -o pr-body.md
  node scripts/validate-pr-body.js pr-body.md
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -o|--output) OUT="${2:-}"; shift 2 ;;
    --issue) ISSUE="${2:-}"; shift 2 ;;
    --summary) SUMMARY="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 2 ;;
  esac
done

if [[ ! -f "$SCAFFOLD" ]]; then
  echo "scaffold-pr-body: missing $SCAFFOLD" >&2
  exit 1
fi

if [[ ${#SUMMARY} -lt 20 ]]; then
  echo "scaffold-pr-body: --summary must be at least 20 characters" >&2
  exit 1
fi

export SCAFFOLD_FILE="$SCAFFOLD" SCAFFOLD_SUMMARY="$SUMMARY" SCAFFOLD_ISSUE="$ISSUE"
body="$(python3 - <<'PY'
from pathlib import Path
import os
text = Path(os.environ["SCAFFOLD_FILE"]).read_text()
text = text.replace("SUMMARY_PLACEHOLDER", os.environ["SCAFFOLD_SUMMARY"])
text = text.replace("ISSUE_PLACEHOLDER", os.environ["SCAFFOLD_ISSUE"])
print(text, end="")
PY
)"

if [[ -n "$OUT" ]]; then
  printf '%s\n' "$body" > "$OUT"
  echo "Wrote ${OUT}" >&2
else
  printf '%s\n' "$body"
fi
