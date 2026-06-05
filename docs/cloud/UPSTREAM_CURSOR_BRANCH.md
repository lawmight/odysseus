# Upstream Cursor branch — human setup

This runbook covers steps **you** do in Cursor and GitHub. Cloud Agents can run the scripts; they cannot create Automations in your dashboard.

**Skill for agents:** [`.cursor/skills/upstream-cursor-branch/SKILL.md`](../../.cursor/skills/upstream-cursor-branch/SKILL.md)

## What this solves

You maintain one branch per upstream target for the Cursor SDK upstream PR:

| Branch | Purpose |
|--------|---------|
| `cursor/upstream-cursor-provider-5b2d` | Upstream PR against `main` |
| `cursor/upstream-cursor-provider-dev-627e` | Upstream PR against `dev` |

Hourly automation merges **upstream only** into that branch. It does **not** merge fork `main` and does **not** open lawmight sync PRs.

## One-time: clean a polluted branch (recommended once)

Your cursor branch may contain fork sync merges (~110 commits). Re-carve once:

```bash
cd /path/to/odysseus
bash scripts/carve-upstream-cursor-branch.sh \
  --target main \
  --source origin/cursor/upstream-cursor-provider-5b2d
```

Review the diff. Remove any Copilot imports from `app.py`, `src/llm_core.py`, `src/endpoint_resolver.py` if the carve pulled them in. Merge README Cursor section manually if needed. Then push:

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

## One-time: Cursor Automation (hourly refresh)

1. Open [cursor.com/automations](https://cursor.com/automations) → **Create automation**.
2. **Trigger:** Scheduled → `0 * * * *` (every hour) or `0 */6 * * *` (every 6 hours if you prefer less churn).
3. **Repository:** `lawmight/odysseus`.
4. **Tools:** disable **Open pull request**. No fork PRs for sync.
5. **Model:** your preferred strong model (conflict resolution).
6. **Prompt** (paste):

```text
Run the upstream Cursor branch refresh. Read .cursor/skills/upstream-cursor-branch/SKILL.md first.

1. bash scripts/refresh-upstream-cursor-branch.sh --target main
2. If exit 0 with "no new commits" — stop silently (no comment, no PR).
3. If exit 2 (merge conflicts) — resolve conflicts per the skill, run tests, push same branch. Do NOT merge origin/main. Do NOT open a lawmight PR.
4. Optionally run: bash scripts/refresh-upstream-cursor-branch.sh --target dev (same rules).

Never merge origin/main into cursor/upstream-cursor-provider-* branches.
Never add docs/cloud/FORK_ONLY_MANIFEST.md paths.
```

7. **Billing:** automations run as Cloud Agents (Max Mode). Set spend limits in [Cloud Agents settings](https://cursor.com/dashboard/cloud-agents).

### Optional second automation for upstream dev only

If hourly dev refresh is too noisy, run dev refresh once daily (`0 8 * * *`) with `--target dev` only.

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
git fetch origin upstream
git checkout cursor/upstream-cursor-provider-5b2d
git pull origin cursor/upstream-cursor-provider-5b2d
# polish Cursor SDK integration
git push origin cursor/upstream-cursor-provider-5b2d
```

Automation keeps upstream merged underneath. You only resolve conflicts when upstream touches the same files as your cursor work.

## Manual refresh (without waiting for automation)

```bash
bash scripts/refresh-upstream-cursor-branch.sh --target main
bash scripts/refresh-upstream-cursor-branch.sh --target dev
```

Dry-run:

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
| Merge conflicts every hour | Re-carve once; then conflicts should be rare |
| Tests fail after refresh | Fix cursor integration; do not merge fork main to "fix" |
| Automation opens fork PRs | Disable Open pull request tool; fix prompt |
| Branch has 100+ unrelated commits | Re-carve; consider squash before upstream PR |
