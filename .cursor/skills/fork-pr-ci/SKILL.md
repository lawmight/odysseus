---
name: fork-pr-ci
description: >-
  lawmight/odysseus fork PR and CI gates. Use before creating or updating any
  pull request on this repo, when CI shows "Check PR description" failure, or
  when branch protection blocks merge. Scaffolds PR bodies that pass the five
  description checks and runs local preflight matching GitHub Actions.
---

# Fork PR CI (lawmight/odysseus)

GitHub blocks merge when **Check PR description** fails, even if test/syntax/docker are green. Cloud agents often fail by improvising the PR body instead of using the scaffold.

## When to use

- Before `ManagePullRequest` / `gh pr create`
- After opening a PR that shows **UNSTABLE** or red **Check PR description**
- Before telling the user a PR is ready to merge

## The five checks (enforced bot)

Same rules as [`.github/scripts/check-pr-description.js`](../../.github/scripts/check-pr-description.js) and [docs/guides/UPSTREAM_PR_GUIDELINES.md](../../docs/guides/UPSTREAM_PR_GUIDELINES.md#the-five-checks).

| # | Section | Pass condition | Agent mistake |
|---|---------|----------------|---------------|
| 1 | **Summary** | ≥ 20 characters (comments stripped) | "docs only", "fix", placeholder text |
| 2 | **Linked Issue** | `#NNN` or `/issues/NNN` in that section | `N/A`, empty, no issue number |
| 3 | **Type of Change** | At least one `- [x]` in that section | Wrong labels like "Documentation update" without matching scaffold boxes |
| 4 | **Checklist** | Exact substring `- [x] I searched` anywhere in body | Custom checklist lines that omit duplicate-search |
| 5 | **How to Test** | ≥ 30 characters in section; use numbered steps | Empty, "TBD", bullets only |

Fork issues are disabled. Link an **upstream** issue: `Part of #1234` or `Fixes #1234` (pewdiepie-archdaemon/odysseus). Placeholder `Part of #0000` passes the bot but replace before human review when possible.

## Required workflow (do not skip)

```bash
# 1. Write body from scaffold — never improvise from pull_request_template.md alone
bash scripts/scaffold-pr-body.sh \
  --issue NNNN \
  --summary "One paragraph: what changed and why (20+ chars)." \
  -o pr-body.md

# 2. Edit pr-body.md: fill How to Test numbered steps; adjust type checkbox if not docs-only

# 3. Validate locally (must exit 0)
node scripts/validate-pr-body.js --explain pr-body.md

# 4. Run code gates
bash scripts/ci-preflight.sh --fork --require-pr-body

# 5. Open or update PR using ONLY the validated pr-body.md content as the description body
#    Do not paste Cubic/Sourcery/CodeRabbit summaries as the only description.
```

`pr-body.md` is gitignored. Read it and pass its **full text** to `ManagePullRequest` `body` (no CURSOR_AGENT wrappers needed in the file; the tool adds metadata separately).

## GitHub Actions jobs on fork PRs

| Job | Workflow | Required for merge? | What it does |
|-----|----------|---------------------|--------------|
| **Check PR description** | `pr-description-check.yml` | **Yes** (branch protection) | Five checks above |
| syntax | `ci.yml` | Yes | `compileall` + `node --check` on static JS |
| test | `ci.yml` | Often yes | `pytest -q` with requirements-cursor.txt |
| secrets | `ci.yml` | Yes | `scripts/ci-secret-scan.sh` |
| docker-config / docker-build | `docker.yml` | Yes | compose config + image build |
| docker-smoke | `docker.yml` | Skipped on most PRs | Only when configured |
| CodeRabbit / cubic / Sourcery | External | Informational | Do not satisfy description bot |

`test` has `continue-on-error: true` in workflow but may still show red; fix real failures anyway.

## Adapting an existing failing PR

```bash
gh pr view <N> --repo lawmight/odysseus --json body -q .body > /tmp/pr-raw.md
# If body has <!-- CURSOR_AGENT_PR_BODY_BEGIN --> markers, replace inner content with scaffold output

bash scripts/scaffold-pr-body.sh --issue NNNN --summary "..." -o pr-body.md
# merge your real How to Test steps into pr-body.md
node scripts/validate-pr-body.js --explain pr-body.md

gh pr edit <N> --repo lawmight/odysseus --body-file pr-body.md
# or ManagePullRequest update_pr with validated body
```

Re-run checks: `gh pr checks <N> --repo lawmight/odysseus`

## Upstream PRs (pewdiepie-archdaemon/odysseus)

Use `bash scripts/ci-preflight.sh --upstream` and the same five-check body (upstream uses the same validator). Carve manifest: [UPSTREAM_CURSOR_PR_FILES.md](../../docs/guides/UPSTREAM_CURSOR_PR_FILES.md).

## Encode lessons (meta)

If you fail the same check twice in one session, stop improvising bodies. The scaffold exists because agents repeat the same two errors: **N/A Linked Issue** and **missing `- [x] I searched`**.
