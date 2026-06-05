# Fork-only files (lawmight / Cloud Agent)

These paths support **lawmight/odysseus** Cloud Agent workflows and fork CI. **Exclude them** from upstream cursor integration PRs to **pewdiepie-archdaemon/odysseus**.

## Cloud Agent bootstrap

| Path | Purpose |
|------|---------|
| [AGENTS.md](../../AGENTS.md) | Cursor Cloud Agent VM guide |
| [.cursor/environment.json](../../.cursor/environment.json) | Cloud environment install/start hooks |
| [.cursor/BUGBOT.md](../../.cursor/BUGBOT.md) | Fork review rules |
| [scripts/cloud-agent-install.sh](../../scripts/cloud-agent-install.sh) | VM bootstrap (venv, optional cursor-sdk) |
| [scripts/cloud-agent-start.sh](../../scripts/cloud-agent-start.sh) | `ODYSSEUS_RUNTIME` docker vs dev |
| [scripts/cloud-agent-services.sh](../../scripts/cloud-agent-services.sh) | Sidecars + host dev-server |

## Fork CI / PR workflow

| Path | Purpose |
|------|---------|
| [docs/guides/UPSTREAM_PR_GUIDELINES.md](../guides/UPSTREAM_PR_GUIDELINES.md) | Fork PR playbook |
| [docs/guides/CI_PARITY.md](../guides/CI_PARITY.md) | Fork vs upstream CI comparison |
| [scripts/ci-preflight.sh](../../scripts/ci-preflight.sh) | Local preflight |
| [scripts/ci-parity-report.sh](../../scripts/ci-parity-report.sh) | CI parity report |
| [scripts/ci-secret-scan.sh](../../scripts/ci-secret-scan.sh) | Secret scan helper |
| [scripts/scaffold-pr-body.sh](../../scripts/scaffold-pr-body.sh) | PR body scaffold |
| [scripts/validate-pr-body.js](../../scripts/validate-pr-body.js) | PR description validator |
| [.github/workflows/pr-description-check.yml](../../.github/workflows/pr-description-check.yml) | Five-check workflow |
| [.github/pr-body-scaffold.md](../../.github/pr-body-scaffold.md) | Scaffold template |

## Fork bookkeeping (not product)

| Path | Purpose |
|------|---------|
| [docs/plans/merged-pr-23-cursor-sdk-upgrades.md](../plans/merged-pr-23-cursor-sdk-upgrades.md) | Merged PR record |

## Upstream cursor PR

See [UPSTREAM_CURSOR_PR_FILES.md](../guides/UPSTREAM_CURSOR_PR_FILES.md) for the file set to include when opening a cursor integration PR upstream.
