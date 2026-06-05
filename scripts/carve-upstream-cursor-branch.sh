#!/usr/bin/env bash
# Rebuild an upstream-facing Cursor SDK branch from upstream base + manifest paths.
# Use for one-time cleanup when the cursor branch picked up fork sync noise.
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

# shellcheck source=scripts/upstream-cursor-lib.sh
source "$ROOT/scripts/upstream-cursor-lib.sh"

TARGET="main"
SOURCE=""
DRY_RUN=0
NO_PUSH=1
NO_TEST=0
FORCE=0
DO_PUSH=0

usage() {
  cat <<'EOF'
Usage: bash scripts/carve-upstream-cursor-branch.sh [options]

Reset the cursor branch to upstream/<target>, then checkout manifest paths from --source.
Does NOT merge origin/main wholesale — only paths in UPSTREAM_CURSOR_MANIFEST.

Options:
  --target main|dev     Upstream ref to branch from (default: main)
  --source REF          Git ref for manifest files (default: origin/<cursor-branch> or origin/main)
  --dry-run             Print plan only
  --no-push             Commit locally; do not push (default)
  --push                Push with --force-with-lease after carve (review diff first)
  --no-test             Skip cursor pytest subset
  --force               Allow overwriting a dirty worktree
  -h, --help            Show this help

After carve: remove fork-only Copilot imports from app.py, src/llm_core.py,
src/endpoint_resolver.py if present (upstream has no src/copilot.py).
Merge README Cursor section manually if upstream README diverged.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target)
      [[ $# -ge 2 ]] || { echo "carve-upstream-cursor-branch: --target requires a value" >&2; exit 1; }
      TARGET="${2}"; shift 2 ;;
    --source)
      [[ $# -ge 2 ]] || { echo "carve-upstream-cursor-branch: --source requires a value" >&2; exit 1; }
      SOURCE="${2}"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    --no-push) NO_PUSH=1; DO_PUSH=0; shift ;;
    --push) NO_PUSH=0; DO_PUSH=1; shift ;;
    --no-test) NO_TEST=1; shift ;;
    --force) FORCE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "carve-upstream-cursor-branch: unknown option: $1" >&2; usage >&2; exit 1 ;;
  esac
done

FORK_BRANCH="$(upstream_cursor_branch_for_target "$TARGET")"
UPSTREAM_REF="${UPSTREAM_REMOTE}/${TARGET}"

if [[ -z "$SOURCE" ]]; then
  if git rev-parse --verify "origin/${FORK_BRANCH}^{commit}" >/dev/null 2>&1; then
    SOURCE="origin/${FORK_BRANCH}"
  else
    SOURCE="origin/main"
  fi
fi

echo "== carve-upstream-cursor-branch (target=${TARGET}, branch=${FORK_BRANCH}, source=${SOURCE}) =="

if [[ $DRY_RUN -eq 1 ]]; then
  echo "dry-run: would reset to ${UPSTREAM_REF} and checkout ${#UPSTREAM_CURSOR_MANIFEST[@]} manifest paths from ${SOURCE}"
  printf '  %s\n' "${UPSTREAM_CURSOR_MANIFEST[@]}"
  exit 0
fi

if [[ $FORCE -eq 0 ]] && [[ -n "$(git status --porcelain)" ]]; then
  echo "carve-upstream-cursor-branch: dirty worktree; commit/stash or pass --force" >&2
  exit 1
fi

upstream_cursor_fetch

if ! git rev-parse --verify "${UPSTREAM_REF}^{commit}" >/dev/null 2>&1; then
  echo "carve-upstream-cursor-branch: missing ${UPSTREAM_REF}" >&2
  exit 1
fi

if ! git rev-parse --verify "${SOURCE}^{commit}" >/dev/null 2>&1; then
  echo "carve-upstream-cursor-branch: missing source ref ${SOURCE}" >&2
  exit 1
fi

git checkout -B "$FORK_BRANCH" "$UPSTREAM_REF"

missing=()
staged=()
for path in "${UPSTREAM_CURSOR_MANIFEST[@]}"; do
  if git cat-file -e "${SOURCE}:${path}" 2>/dev/null; then
    git checkout "$SOURCE" -- "$path"
    staged+=("$path")
  else
    missing+=("$path")
  fi
done

if [[ ${#missing[@]} -gt 0 ]]; then
  echo "carve-upstream-cursor-branch: warning — paths missing from ${SOURCE}:" >&2
  printf '  %s\n' "${missing[@]}" >&2
fi

if [[ ${#staged[@]} -eq 0 ]]; then
  echo "carve-upstream-cursor-branch: no manifest paths found in ${SOURCE}" >&2
  exit 1
fi

if ! git diff --cached --quiet || ! git diff --quiet; then
  git commit -m "feat(cursor): carve upstream ${TARGET} Cursor SDK integration from ${SOURCE}"
else
  echo "carve-upstream-cursor-branch: no file changes after carve (already aligned?)"
fi

if [[ $NO_TEST -eq 0 ]]; then
  echo "running cursor test subset..."
  upstream_cursor_run_tests
fi

if [[ $DO_PUSH -eq 0 ]]; then
  echo "carve-upstream-cursor-branch: OK (local commit; review diff, strip Copilot imports, then --push)"
  exit 0
fi

git push --force-with-lease origin "$FORK_BRANCH"
echo "carve-upstream-cursor-branch: OK (force-with-lease push ${FORK_BRANCH})"
