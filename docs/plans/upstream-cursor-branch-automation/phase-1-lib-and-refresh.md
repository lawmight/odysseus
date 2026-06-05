# Phase 1: lib + refresh script

Back-link: [overview.md](./overview.md)

## Goal

Shared manifest and an idempotent refresh that merges upstream into the cursor branch only.

## Data structures

- `Target`: `main` | `dev` maps to upstream ref + fork branch name.
- `RefreshResult`: `up_to_date` | `merged` | `conflicts` | `error`.

## Changes

- `scripts/upstream-cursor-lib.sh` — constants, manifest path list, branch map, test runner.
- `scripts/refresh-upstream-cursor-branch.sh` — fetch, ancestor check, merge, test, optional push.

## Verification

Dry-run shows would-merge vs up-to-date. Conflicts exit non-zero with file list.
