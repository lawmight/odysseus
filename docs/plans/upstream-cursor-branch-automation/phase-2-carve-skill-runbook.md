# Phase 2: carve, skill, runbook

Back-link: [overview.md](./overview.md)

## Goal

One-time branch rebuild, agent skill, and human Cursor Automations instructions.

## Changes

- `scripts/carve-upstream-cursor-branch.sh` — upstream base + manifest checkout from `--source`.
- `.cursor/skills/upstream-cursor-branch/SKILL.md` — rules for agents and automations.
- `docs/cloud/UPSTREAM_CURSOR_BRANCH.md` — dashboard setup the agent cannot do.

## Verification

Skill references match script flags. Runbook prompt matches refresh script entrypoint.
