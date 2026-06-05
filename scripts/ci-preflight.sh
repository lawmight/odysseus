#!/usr/bin/env bash
# Run local checks before opening a PR (fork and/or upstream expectations).
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

MODE="fork"
PR_BODY=""
SKIP_DOCKER=0
SKIP_JS=0
REQUIRE_PR_BODY=0
NO_DOCKER_AUTODETECT=0
FORCE_DOCKER=0

usage() {
  cat <<'EOF'
Usage: bash scripts/ci-preflight.sh [options]

Options:
  --fork                  Full fork gate: pytest, syntax, secrets, docker (default)
  --upstream              Upstream-oriented: pytest, syntax, secrets; docker if Docker files changed
  --pr-body FILE          Validate PR description with scripts/validate-pr-body.js
  --require-pr-body       Fail if neither --pr-body nor pr-body.md is present / valid
  --skip-docker           Skip docker compose config and image build
  --force-docker          Run docker checks even in --upstream mode
  --no-docker-autodetect  In --upstream mode, never auto-skip docker (same as --force-docker)
  --skip-js               Skip node --check on static/js
  -h, --help              Show this help

Also validates ./pr-body.md when present. Regenerates docs/guides/CI_PARITY.md when gh is available.

The PR description bot enforces five rules — see docs/guides/UPSTREAM_PR_GUIDELINES.md#the-five-checks.
EOF
}

pr_body_warning() {
  cat <<'EOF' >&2
warning: no pr-body.md and no --pr-body — the PR description bot may fail with up to 5 issues:
  1. Summary too short
  2. Linked Issue missing (#NNN)
  3. Type of Change unchecked
  4. Checklist duplicate-search unchecked
  5. How to Test missing numbered steps
Fix: bash scripts/scaffold-pr-body.sh --issue NNNN --summary "..." -o pr-body.md
     node scripts/validate-pr-body.js --explain pr-body.md
EOF
}

docker_files_changed() {
  local range="$1"
  [[ -n "$range" ]] && git diff --name-only $range 2>/dev/null | grep -qE '(^docker-compose|^Dockerfile|/\.docker)'
}

resolve_diff_range() {
  if git rev-parse --verify origin/main >/dev/null 2>&1; then
    echo "origin/main...HEAD"
    return
  fi
  if git rev-parse --verify main >/dev/null 2>&1; then
    local base
    base="$(git merge-base main HEAD 2>/dev/null || true)"
    if [[ -n "$base" ]]; then
      echo "${base}...HEAD"
      return
    fi
  fi
  if git rev-parse --verify HEAD~1 >/dev/null 2>&1; then
    echo "HEAD~1..HEAD"
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --fork) MODE="fork"; shift ;;
    --upstream) MODE="upstream"; shift ;;
    --pr-body) PR_BODY="${2:-}"; shift 2 ;;
    --require-pr-body) REQUIRE_PR_BODY=1; shift ;;
    --skip-docker) SKIP_DOCKER=1; shift ;;
    --force-docker) FORCE_DOCKER=1; shift ;;
    --no-docker-autodetect) NO_DOCKER_AUTODETECT=1; FORCE_DOCKER=1; shift ;;
    --skip-js) SKIP_JS=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 2 ;;
  esac
done

if [[ "$MODE" == "upstream" && "$SKIP_DOCKER" -eq 0 && "$FORCE_DOCKER" -eq 0 ]]; then
  range="$(resolve_diff_range)"
  if [[ -n "$range" ]] && ! docker_files_changed "$range"; then
    SKIP_DOCKER=1
  fi
fi

echo "== ci-preflight (mode=${MODE}) =="

if command -v gh >/dev/null 2>&1; then
  bash scripts/ci-parity-report.sh docs/guides/CI_PARITY.md || true
fi

if [[ -z "$PR_BODY" && -f "${ROOT}/pr-body.md" ]]; then
  PR_BODY="${ROOT}/pr-body.md"
fi

if [[ -n "$PR_BODY" ]]; then
  echo "-- PR body"
  node scripts/validate-pr-body.js "$PR_BODY"
elif [[ "$REQUIRE_PR_BODY" -eq 1 ]]; then
  pr_body_warning
  exit 1
else
  pr_body_warning
fi

if [[ -f venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
fi

echo "-- pytest"
python -m pytest -q --tb=short

echo "-- Python syntax"
shopt -s nullglob
py_files=(app.py)
py_files+=(routes/*.py)
py_files+=(src/*.py)
if ((${#py_files[@]})); then
  python -m py_compile "${py_files[@]}"
else
  echo "skip: no Python files matched"
fi

if [[ "$SKIP_JS" -eq 0 ]]; then
  echo "-- JavaScript syntax"
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
