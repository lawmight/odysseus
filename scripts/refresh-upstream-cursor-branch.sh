#!/usr/bin/env bash
# Merge latest upstream main/dev into the upstream-facing Cursor SDK branch only.
# Never merges origin/main (fork integration). Idempotent when already up to date.
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

# shellcheck source=scripts/upstream-cursor-lib.sh
source "$ROOT/scripts/upstream-cursor-lib.sh"

TARGET="main"
DRY_RUN=0
NO_PUSH=0
NO_TEST=0
NO_CONFORMANCE=0

usage() {
  cat <<'EOF'
Usage: bash scripts/refresh-upstream-cursor-branch.sh [options]

Merge pewdiepie-archdaemon/odysseus into the fork's upstream-facing Cursor branch.
Does NOT merge origin/main. Exits 0 when already up to date.

Options:
  --target main|dev   Upstream ref and cursor branch (default: main)
  --dry-run           Show actions without merge, test, or push
  --no-push           Merge and test locally; do not push
  --no-test           Skip cursor pytest subset after merge
  --no-conformance    Skip the manifest conformance check (polluted branch pre-carve)
  -h, --help          Show this help

Branch map:
  main -> cursor/upstream-cursor-provider-5b2d  (upstream main)
  dev  -> cursor/upstream-cursor-provider-dev-627e (upstream dev)

After conflicts: resolve and commit the merge on the cursor branch, run the cursor
test subset, then push the same branch. A re-run detects the committed local merge
and skips straight to push. See .cursor/skills/upstream-cursor-branch/SKILL.md.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target)
      [[ $# -ge 2 ]] || { echo "refresh-upstream-cursor-branch: --target requires a value" >&2; exit 1; }
      TARGET="${2}"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    --no-push) NO_PUSH=1; shift ;;
    --no-test) NO_TEST=1; shift ;;
    --no-conformance) NO_CONFORMANCE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "refresh-upstream-cursor-branch: unknown option: $1" >&2; usage >&2; exit 1 ;;
  esac
done

FORK_BRANCH="$(upstream_cursor_branch_for_target "$TARGET")"
UPSTREAM_REF="${UPSTREAM_REMOTE}/${TARGET}"

echo "== refresh-upstream-cursor-branch (target=${TARGET}, branch=${FORK_BRANCH}) =="

upstream_cursor_fetch
if [[ $DRY_RUN -eq 1 ]]; then
  echo "dry-run: fetched ${UPSTREAM_REMOTE} and origin"
fi

if ! git rev-parse --verify "${UPSTREAM_REF}^{commit}" >/dev/null 2>&1; then
  echo "refresh-upstream-cursor-branch: missing ${UPSTREAM_REF} (fetch ${UPSTREAM_REMOTE} ${TARGET})" >&2
  exit 1
fi

UPSTREAM_SHA="$(git rev-parse "${UPSTREAM_REF}")"

if ! git rev-parse --verify "origin/${FORK_BRANCH}^{commit}" >/dev/null 2>&1; then
  echo "refresh-upstream-cursor-branch: branch origin/${FORK_BRANCH} missing; run carve first:" >&2
  echo "  bash scripts/carve-upstream-cursor-branch.sh --target ${TARGET}" >&2
  exit 1
fi

BRANCH_SHA="$(git rev-parse "origin/${FORK_BRANCH}")"

# Classify local tip before the up-to-date early return so unpushed work is
# never silently ignored when origin already contains upstream.
NEED_MERGE=1
if git rev-parse --verify "refs/heads/${FORK_BRANCH}^{commit}" >/dev/null 2>&1; then
  LOCAL_SHA="$(git rev-parse "refs/heads/${FORK_BRANCH}")"
  if [[ "$LOCAL_SHA" != "$BRANCH_SHA" ]]; then
    if git merge-base --is-ancestor "$LOCAL_SHA" "$BRANCH_SHA" 2>/dev/null; then
      : # local is behind origin; safe to reset below
    elif upstream_cursor_is_up_to_date "$UPSTREAM_SHA" "$LOCAL_SHA" \
        && git merge-base --is-ancestor "$BRANCH_SHA" "$LOCAL_SHA" 2>/dev/null; then
      echo "local ${FORK_BRANCH} already contains ${UPSTREAM_REF} (resolved merge); skipping merge"
      NEED_MERGE=0
    else
      echo "refresh-upstream-cursor-branch: local ${FORK_BRANCH} has unpushed commits that do not include ${UPSTREAM_REF}." >&2
      echo "  Push them (git push origin ${FORK_BRANCH}) or reset the local branch, then re-run." >&2
      exit 1
    fi
  fi
fi

if upstream_cursor_is_up_to_date "$UPSTREAM_SHA" "$BRANCH_SHA"; then
  if [[ $NEED_MERGE -eq 0 ]]; then
    # Local tip already has upstream but origin does not yet — continue to test+push.
    :
  else
    echo "upstream sync: no new commits (${FORK_BRANCH} already contains ${UPSTREAM_REF} @ ${UPSTREAM_SHA:0:12})"
    exit 0
  fi
fi

# A local cursor branch may hold a committed conflict resolution from a prior
# run (NEED_MERGE=0 above). Resetting it to origin (checkout -B) would discard
# that merge, so we skip merge and check out the local tip instead.

if [[ $DRY_RUN -eq 1 ]]; then
  if [[ $NEED_MERGE -eq 0 ]]; then
    echo "dry-run: local merge already committed; would test and push ${FORK_BRANCH}"
  else
    echo "dry-run: would merge ${UPSTREAM_REF} into ${FORK_BRANCH}"
    git log --oneline "${BRANCH_SHA}..${UPSTREAM_SHA}" | head -20 || true
  fi
  exit 0
fi

if [[ -n "$(git status --porcelain)" ]]; then
  echo "refresh-upstream-cursor-branch: dirty worktree; commit/stash before refresh" >&2
  exit 1
fi

if [[ $NEED_MERGE -eq 1 ]]; then
  git checkout -B "$FORK_BRANCH" "origin/${FORK_BRANCH}"
  echo "merging ${UPSTREAM_REF} (${UPSTREAM_SHA:0:12}) into ${FORK_BRANCH}..."
  if ! git merge "$UPSTREAM_SHA" -m "merge: sync upstream ${TARGET} into ${FORK_BRANCH}"; then
    echo "refresh-upstream-cursor-branch: merge conflicts — resolve and commit on this branch, then re-run." >&2
    git diff --name-only --diff-filter=U >&2 || true
    exit 2
  fi
else
  git checkout "$FORK_BRANCH"
fi

if [[ $NO_CONFORMANCE -eq 0 ]]; then
  echo "checking manifest conformance against ${UPSTREAM_REF}..."
  if ! upstream_cursor_check_conformance "$UPSTREAM_SHA"; then
    echo "refresh-upstream-cursor-branch: conformance failed — branch carries paths outside the manifest." >&2
    echo "  Re-carve (bash scripts/carve-upstream-cursor-branch.sh --target ${TARGET}) or pass --no-conformance for a polluted branch you have not carved yet." >&2
    exit 3
  fi
fi

if [[ $NO_TEST -eq 0 ]]; then
  echo "running cursor test subset..."
  upstream_cursor_run_tests
fi

if [[ $NO_PUSH -eq 1 ]]; then
  echo "refresh-upstream-cursor-branch: OK (local merge; --no-push)"
  exit 0
fi

git push origin "$FORK_BRANCH"
echo "refresh-upstream-cursor-branch: OK (pushed ${FORK_BRANCH})"
