# Upstream Cursor branch automation

Back-link: this plan validates the approach before tooling lands.

## Context

The fork maintains long-lived branches (`cursor/upstream-cursor-provider-5b2d`, `cursor/upstream-cursor-provider-dev-627e`) for an upstream PR that adds Cursor SDK as a third LLM provider. Upstream `main` and `dev` move continuously. Merging fork `main` or opening sync PRs into the cursor branch polluted history (~110 commits, much unrelated) and recreated the same painful merge loop.

## Scope

**In**

- Idempotent `refresh-upstream-cursor-branch.sh` (merge upstream only into the cursor branch, push, cursor test subset)
- One-time `carve-upstream-cursor-branch.sh` (rebuild branch from upstream base + manifest paths)
- Shared manifest in `scripts/upstream-cursor-lib.sh`
- Skill `.cursor/skills/upstream-cursor-branch/SKILL.md`
- Human runbook `docs/cloud/UPSTREAM_CURSOR_BRANCH.md` (Cursor Automations dashboard steps)

**Out**

- Merging fork `main` into cursor branches (explicitly forbidden)
- Mirror branches (`main-upstream/*`, `dev-upstream/*`)
- Fork sync PRs for upstream drift
- Automated conflict resolution (agent resolves; script exits with conflict list)

## Alternatives

| Approach | Verdict |
|----------|---------|
| Hourly merge fork `main` + upstream into cursor branch | **Slop.** Reintroduces fork noise upstream maintainers will reject. |
| Mirror branches + sync PRs | **Slop.** Same merge loop, more PRs to triage. |
| Merge upstream only into cursor branch; carve to reset | **Chosen.** Matches upstream PR intent; automation stays idempotent. |
| Rebase cursor branch hourly | Rejected for now. Force-push risk on shared branch; merge is safer for Cloud Agent automation. |

## Principles applied

- **Build the lever:** scripts + skill, not a 200-line automation prompt alone.
- **Make operations idempotent:** exit 0 when upstream is already an ancestor of the cursor branch.
- **Separate before serializing:** refresh never touches fork `main`; carve never merges fork `main`.
- **Encode lessons in structure:** FORK_ONLY_MANIFEST exclusion is enforced in skill + runbook, not memory.
- **Laziness protocol:** two scripts, one lib, no new services.

## Phases

1. [phase-1-lib-and-refresh.md](./phase-1-lib-and-refresh.md)
2. [phase-2-carve-skill-runbook.md](./phase-2-carve-skill-runbook.md)

## Verification

```bash
bash scripts/refresh-upstream-cursor-branch.sh --target main --dry-run
bash scripts/carve-upstream-cursor-branch.sh --target main --dry-run
source venv/bin/activate && pytest tests/test_cursor_adapter.py -q
```
