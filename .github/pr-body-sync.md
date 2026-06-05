<!-- CURSOR_AGENT_PR_BODY_BEGIN -->
## Summary

New companion branch for upstream **`dev`** (distinct from upstream `main`). Same fork sync as the main-targeting branch, but merges **`dev-upstream/dev`** instead of `main-upstream/main`.

Layers:
1. **Your fork work** — merged `origin/main`.
2. **Upstream dev** — merged `dev-upstream/dev` (18 commits from pewdiepie-archdaemon/odysseus dev).
3. **Cursor provider carve** — same conflict resolutions as the main-upstream branch.

Use this branch when preparing an upstream PR against `dev`; use `cursor/upstream-cursor-provider-5b2d` for upstream `main`.

## Linked Issue

Part of #2815
## Target branch

- [x] This PR targets **`main`** (fork integration branch).

## Type of Change

- [ ] Bug fix (non-breaking — fixes a confirmed issue)
- [x] New feature (non-breaking — adds new behaviour)
- [ ] Breaking change (changes or removes existing behaviour)
- [ ] Refactor / cleanup (behaviour unchanged)
- [ ] Documentation only
- [ ] CI / tooling / configuration

## Checklist

- [x] I searched [open issues](https://github.com/pewdiepie-archdaemon/odysseus/issues) and [open PRs](https://github.com/pewdiepie-archdaemon/odysseus/pulls) — this is not a duplicate.
- [x] This PR targets `main`
- [x] My changes are limited to the scope described above — no unrelated refactors or whitespace changes mixed in.

## How to Test

1. Check out this branch.
2. Run Cursor provider tests (same as main-targeting branch).
3. Compare divergence vs main branch: `git log --oneline cursor/upstream-cursor-provider-5b2d..cursor/upstream-cursor-provider-dev-627e` and reverse.
<!-- CURSOR_AGENT_PR_BODY_END -->
