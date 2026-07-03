# Upstream Cursor branch — human setup

This runbook covers steps **you** do in Cursor and GitHub. Cloud Agents can run the scripts; they cannot create Automations in your dashboard.

**Skill for agents:** [`.cursor/skills/upstream-cursor-branch/SKILL.md`](../../.cursor/skills/upstream-cursor-branch/SKILL.md)

## What this solves

You maintain one branch per upstream target for the Cursor SDK upstream PR:

| Branch | Purpose |
|--------|---------|
| `cursor/upstream-cursor-provider-5b2d` | Upstream PR against `main` |
| `cursor/upstream-cursor-provider-dev-627e` | Upstream PR against `dev` |

The refresh tooling merges **upstream only** into that branch. It does **not** merge fork `main` and does **not** open lawmight sync PRs.

## Design rationale

| Approach | Verdict |
|----------|---------|
| Merge fork `main` + upstream into cursor branch | **Rejected.** Reintroduces fork noise upstream maintainers will reject. |
| Mirror branches + sync PRs | **Rejected.** Same merge loop, more PRs to triage. |
| Merge upstream only into cursor branch; carve to reset | **Chosen.** Matches upstream PR intent; refresh stays idempotent. |
| Rebase cursor branch on a schedule | Rejected for now. Force-push risk on a shared branch; merge is safer for automation. |

## One-time: clean a polluted branch (recommended once)

Your cursor branch may contain fork sync merges (~110 commits). Re-carve once:

```bash
cd /path/to/odysseus
bash scripts/carve-upstream-cursor-branch.sh \
  --target main \
  --source origin/cursor/upstream-cursor-provider-5b2d
```

Review the diff. Upstream ships its own `src/copilot.py` (since Jun 2026), so **reconcile** fork and upstream Copilot code paths in `app.py`, `src/llm_core.py`, `src/endpoint_resolver.py` — keep both providers working, delete neither side. Carved manifest files may also lag APIs that newer upstream code imports (known case: `src/ai_interaction.py` on upstream imports `resolve_endpoint_runtime` from `src/endpoint_resolver.py`); the built-in test run fails on these — port the upstream API into the carved file. Merge README Cursor section manually if needed. Then push:

```bash
bash scripts/carve-upstream-cursor-branch.sh \
  --target main \
  --source origin/cursor/upstream-cursor-provider-5b2d \
  --push
```

Or push manually after review: `git push --force-with-lease origin cursor/upstream-cursor-provider-5b2d`.

Repeat for `dev` if you use the dev-targeting branch (review locally, then add `--push` when ready):

```bash
bash scripts/carve-upstream-cursor-branch.sh --target dev \
  --source origin/cursor/upstream-cursor-provider-dev-627e
```

## Keeping the branch fresh

The branch's only consumer is the upstream PR, so freshness matters when you are about to touch that PR — not every hour. Pick one of these, in order of preference:

### Default: refresh on demand

Before polishing or updating the upstream PR:

```bash
bash scripts/refresh-upstream-cursor-branch.sh --target main
bash scripts/refresh-upstream-cursor-branch.sh --target dev   # if you use the dev branch
```

Zero standing infrastructure, no spend limits, no credentials parked in a scheduler.

### Standing option: GitHub Actions cron

The happy path (`fetch` + ancestor check, usually "no new commits") is deterministic and needs no LLM. A scheduled workflow that runs `refresh-upstream-cursor-branch.sh --target main` daily and fails the job on exit 2 (conflicts) or exit 3 (conformance) covers it for free; escalate to an agent only when the job fails. The scripts need no changes to support this.

### Alternative: scheduled Cursor Automation

Only if you want conflicts resolved unattended. Caveats first:

- **Cost:** automations run as Cloud Agents (Max Mode); most runs are no-ops you still pay for. Set spend limits in [Cloud Agents settings](https://cursor.com/dashboard/cloud-agents). Prefer `0 8 * * *` (daily) over hourly.
- **Trust:** the VM holds a write token for `lawmight/odysseus` plus any injected secrets, and the refresh installs and executes freshly merged upstream code (pip install + pytest). A malicious upstream commit gets code execution with those credentials on the next run. Only enable this if you accept that trust relationship.

Setup: [cursor.com/automations](https://cursor.com/automations) → **Create automation** → Scheduled trigger, repository `lawmight/odysseus`, disable the **Open pull request** tool, strong model. Prompt:

```text
Run the upstream Cursor branch refresh. Read .cursor/skills/upstream-cursor-branch/SKILL.md first.

1. bash scripts/refresh-upstream-cursor-branch.sh --target main
2. If exit 0 with "no new commits" — stop silently (no comment, no PR).
3. If exit 2 (merge conflicts) — resolve the conflicts, COMMIT the merge on the same cursor branch, then re-run the refresh script; it detects the committed merge, checks conformance, runs tests, and pushes. Do NOT merge origin/main. Do NOT reset the branch to origin after resolving. Do NOT open a lawmight PR.
4. If exit 3 (conformance) — the branch carries paths outside the manifest; stop and report. Do not push.
5. Optionally run: bash scripts/refresh-upstream-cursor-branch.sh --target dev (same rules).

Never merge origin/main into cursor/upstream-cursor-provider-* branches.
Never add docs/cloud/FORK_ONLY_MANIFEST.md paths.
```

## One-time: Cloud environment install script

Ensure your [Cloud Agents environment](https://cursor.com/dashboard/cloud-agents/environments) install script includes:

```bash
bash scripts/cloud-agent-install.sh
```

The refresh script needs `venv` and `requirements-cursor.txt` for tests.

## GitHub permissions

The Cloud Agent service account (or your account for private automations) needs **write** access to `lawmight/odysseus` so it can push to `cursor/upstream-cursor-provider-*` branches.

## Daily work (you)

```bash
git fetch --multiple origin upstream
git checkout cursor/upstream-cursor-provider-5b2d
git pull origin cursor/upstream-cursor-provider-5b2d
# polish Cursor SDK integration
git push origin cursor/upstream-cursor-provider-5b2d
```

Push before running the refresh script: it refuses to run over unpushed local commits (so it never discards them).

Dry-run preview of a refresh:

```bash
bash scripts/refresh-upstream-cursor-branch.sh --target main --dry-run
```

## When ready: open upstream PR

1. Push final polish to `cursor/upstream-cursor-provider-5b2d`.
2. Open PR on **pewdiepie-archdaemon/odysseus** (base `main` or `dev`).
3. Run `bash scripts/ci-preflight.sh --upstream` before submit.
4. Use [UPSTREAM_PR_GUIDELINES.md](../guides/UPSTREAM_PR_GUIDELINES.md) for the body.

Do not merge fork-only files listed in [FORK_ONLY_MANIFEST.md](./FORK_ONLY_MANIFEST.md).

## What agents cannot do for you

| Task | Who |
|------|-----|
| Create Cursor Automations in dashboard | You |
| Set Cloud Agent spend limits | You |
| Add `CURSOR_API_KEY` to Secrets | You |
| Open PR on pewdiepie-archdaemon/odysseus (maintainer merge) | You, when ready |
| Approve force-push to shared branch without your OK | You — carve uses `--force-with-lease` |

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `branch origin/cursor/... missing` | Run carve script once |
| Merge conflicts on every refresh | Re-carve once; then conflicts should be rare |
| Refresh exits 3 (conformance) | Branch differs from upstream outside the manifest — re-carve, or `--no-conformance` for a polluted branch you have not carved yet |
| Refresh refuses: unpushed local commits | Push (or reset) the local cursor branch first; the guard prevents discarding your work |
| Tests fail after refresh or carve | Usually manifest drift: upstream code imports an API missing from a carved manifest file (known case: `resolve_endpoint_runtime` in `src/endpoint_resolver.py`). Port the upstream API into the carved file; never merge fork main to "fix" |
| Automation opens fork PRs | Disable Open pull request tool; fix prompt |
| Branch has 100+ unrelated commits | Re-carve; consider squash before upstream PR |
