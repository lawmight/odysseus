# Contributor guides

| Document | Description |
|----------|-------------|
| [UPSTREAM_PR_GUIDELINES.md](./UPSTREAM_PR_GUIDELINES.md) | PR acceptance playbook — **the five checks**, scaffold workflow, Cloud Agent video |
| [UPSTREAM_CURSOR_PR_FILES.md](./UPSTREAM_CURSOR_PR_FILES.md) | Cursor upstream carve manifest and staging branch |
| [CI_PARITY.md](./CI_PARITY.md) | Auto-generated CI/check comparison (run `bash scripts/ci-parity-report.sh`) |

**Scripts:** `scripts/scaffold-pr-body.sh`, `scripts/validate-pr-body.js --explain`, `scripts/ci-preflight.sh --require-pr-body`

**Agents:** [`.cursor/skills/fork-pr-ci/SKILL.md`](../../.cursor/skills/fork-pr-ci/SKILL.md) — PR description bot + local preflight workflow.
