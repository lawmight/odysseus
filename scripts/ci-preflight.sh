#!/usr/bin/env bash
# Run local checks before opening a PR (fork and/or upstream expectations).
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

MODE="fork"
PR_BODY=""
SKIP_DOCKER=0
SKIP_JS=0

usage() {
  cat <<'EOF'
Usage: bash scripts/ci-preflight.sh [options]

Options:
  --fork          Full fork gate: pytest, syntax, secrets, docker (default)
  --upstream      Upstream-oriented: pytest, syntax, secrets; docker only if compose/Dockerfile changed
  --pr-body FILE  Validate PR description with scripts/validate-pr-body.js
  --skip-docker   Skip docker compose config and image build
  --skip-js       Skip node --check on static/js
  -h, --help      Show this help

Also updates docs/guides/CI_PARITY.md when gh is available.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --fork) MODE="fork"; shift ;;
    --upstream) MODE="upstream"; shift ;;
    --pr-body) PR_BODY="${2:-}"; shift 2 ;;
    --skip-docker) SKIP_DOCKER=1; shift ;;
    --skip-js) SKIP_JS=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 2 ;;
  esac
done

if [[ "$MODE" == "upstream" ]]; then
  if git diff --name-only origin/main...HEAD 2>/dev/null | grep -qE '^(docker-compose|Dockerfile|\.docker)'; then
    :
  elif git diff --name-only HEAD~1..HEAD 2>/dev/null | grep -qE '^(docker-compose|Dockerfile|\.docker)'; then
    :
  else
    SKIP_DOCKER=1
  fi
fi

echo "== ci-preflight (mode=${MODE}) =="

if command -v gh >/dev/null 2>&1; then
  bash scripts/ci-parity-report.sh docs/guides/CI_PARITY.md || true
fi

if [[ -n "$PR_BODY" ]]; then
  echo "-- PR body"
  node scripts/validate-pr-body.js "$PR_BODY"
fi

if [[ -f venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
fi

echo "-- pytest"
python -m pytest -q --tb=short

echo "-- Python syntax"
python -m py_compile app.py routes/*.py src/*.py

if [[ "$SKIP_JS" -eq 0 ]]; then
  echo "-- JavaScript syntax"
  shopt -s nullglob
  files=(static/js/*.js)
  if ((${#files[@]})); then
    for f in "${files[@]}"; do
      node --check "$f"
    done
  fi
fi

echo "-- secret scan"
bash scripts/ci-secret-scan.sh

if [[ "$SKIP_DOCKER" -eq 0 ]]; then
  echo "-- docker compose config"
  docker compose config >/dev/null
  echo "-- docker build"
  docker build -t odysseus-ci:local .
fi

echo "ci-preflight: OK"
