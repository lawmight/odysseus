---
name: upstream-cursor-branch
description: >-
  Maintain lawmight/odysseus upstream-facing Cursor SDK branches
  (cursor/upstream-cursor-provider-5b2d, cursor/upstream-cursor-provider-dev-627e).
  Use when syncing with pewdiepie-archdaemon/odysseus, resolving merge conflicts on
  those branches, running scheduled upstream refresh automations, or polishing the
  upstream Cursor provider PR. Never merge origin/main into these branches.
---

# Upstream Cursor branch (lawmight fork)

Long-lived branches for the **upstream PR** that adds Cursor SDK as a third LLM provider. These branches are **not** fork integration branches.

| Target | Branch | Tracks |
|--------|--------|--------|
| upstream `main` | `cursor/upstream-cursor-provider-5b2d` | pewdiepie-archdaemon/odysseus `main` |
| upstream `dev` | `cursor/upstream-cursor-provider-dev-627e` | pewdiepie-archdaemon/odysseus `dev` |

Human runbook (carve, scheduling options, troubleshooting): [docs/cloud/UPSTREAM_CURSOR_BRANCH.md](../../docs/cloud/UPSTREAM_CURSOR_BRANCH.md)

## When to use

- Scheduled or manual **upstream refresh** (new commits on upstream `main` / `dev`)
- **Polishing** Cursor SDK work before opening PR to pewdiepie-archdaemon/odysseus
- **One-time cleanup** when the cursor branch picked up fork sync merge noise
- Cloud Agent automation that must **not** open fork sync PRs

## Hard rules

1. **Never** `git merge origin/main` into a cursor upstream branch.
2. **Never** add paths from [docs/cloud/FORK_ONLY_MANIFEST.md](../../docs/cloud/FORK_ONLY_MANIFEST.md) (AGENTS.md, cloud-agent scripts, fork CI, etc.). The refresh script enforces this: it fails (exit 3) when the branch differs from upstream outside `UPSTREAM_CURSOR_MANIFEST`.
3. **Never** open a lawmight/odysseus PR just to sync upstream — push to the same cursor branch.
4. Exit silently when upstream has no new commits (idempotent refresh).

## Commands (prefer scripts over improvising git)

```bash
# Refresh entrypoint — merge upstream only, check conformance, test, push
bash scripts/refresh-upstream-cursor-branch.sh --target main

# Same for upstream dev branch
bash scripts/refresh-upstream-cursor-branch.sh --target dev

# Dry-run (no merge/push)
bash scripts/refresh-upstream-cursor-branch.sh --target main --dry-run

# One-time rebuild from upstream base + manifest paths (after fork noise polluted history)
bash scripts/carve-upstream-cursor-branch.sh --target main --source origin/cursor/upstream-cursor-provider-5b2d
```

## Conflict resolution

Read [docs/guides/UPSTREAM_CURSOR_PR_FILES.md](../../docs/guides/UPSTREAM_CURSOR_PR_FILES.md).

On refresh exit 2: resolve the conflicts, **commit the merge on the cursor branch**, then re-run the refresh script. The re-run detects the committed local merge, skips straight to conformance check + tests, and pushes. Do not reset the branch to origin after resolving.

| Area | Rule |
|------|------|
| `src/providers/cursor_*.py`, `requirements-cursor.txt` | Keep cursor integration |
| Shared glue (`routes/chat_routes.py`, `app.py`, `src/llm_core.py`, `src/endpoint_resolver.py`) | Upstream non-cursor behavior **plus** cursor code paths side by side |
| `routes/*.py`, `tests/test_model_routes.py` | Upstream behavior; preserve cursor tests/branches |
| Copilot code paths | **Reconcile** — upstream ships its own `src/copilot.py` (since Jun 2026); keep both providers working, delete neither side |
| Manifest files lagging upstream APIs (e.g. `resolve_endpoint_runtime` in `src/endpoint_resolver.py`) | Port the upstream API into the carved file; the cursor test subset catches missing imports |
| Fork-only manifest paths | **Do not add** |

## Verify after merge or carve

```bash
bash scripts/refresh-upstream-cursor-branch.sh --target main --no-push --no-test
# or rely on built-in test run:
bash scripts/refresh-upstream-cursor-branch.sh --target main --no-push
```

Cursor pytest subset runs automatically unless `--no-test`.

## Workflow for humans

```bash
git checkout cursor/upstream-cursor-provider-5b2d
git pull origin cursor/upstream-cursor-provider-5b2d
# polish cursor SDK
git push origin cursor/upstream-cursor-provider-5b2d
```

Branch from **cursor upstream branch** for cursor-only tasks. Do not branch from `cursor/upstream-*` staging names for unrelated fork work.

## Opening the upstream PR (when ready)

Target **pewdiepie-archdaemon/odysseus**, not lawmight. Run `bash scripts/ci-preflight.sh --upstream`. Carve manifest: [UPSTREAM_CURSOR_PR_FILES.md](../../docs/guides/UPSTREAM_CURSOR_PR_FILES.md).

Consider squashing or re-carving before submit if history contains old fork sync merges.
