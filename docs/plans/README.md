# Cursor × Odysseus integration plans

| Plan | File | Purpose |
|------|------|---------|
| **A** | [cursor-chat-model-provider-plan.md](./cursor-chat-model-provider-plan.md) | First design: Cursor as a Chat adapter (`cursor-sdk`, `cursor://local`). |
| **B (v2)** | [cursor-agent-tab-integration-plan.md](./cursor-agent-tab-integration-plan.md) | Optional second engine for the **Agent** tab (Cursor tools, `tool_start` / `tool_output`). **Phase 1 shipped;** v2 reframes Phases 2–4 and holds the [Decision log](./cursor-agent-tab-integration-plan.md#12-decision-log). |
| **B backlog** | [cursor-agent-tab-backlog.md](./cursor-agent-tab-backlog.md) | Ordered Agent-engine follow-up epics (B2a–B4) with files and tests. |
| **C** | [cursor-plan-c-chat-byok-polished.md](./cursor-plan-c-chat-byok-polished.md) | **Canonical goal** for upstream: Chat BYOK parity with other providers; defers B. |
| **Ship** | [cursor-merge-and-ship-plan.md](./cursor-merge-and-ship-plan.md) | **Shipped** on `main` @ `3a1b985` (PR #2, 2026-06-02). |
| **C+** | [cursor-useful-tools-plan.md](./cursor-useful-tools-plan.md) | **Shipped:** Cursor `generateImage` in Chat (`image_url` via gallery). |
| **C+ polish** | [cursor-plan-c-plus-polish.md](./cursor-plan-c-plus-polish.md) | **Shipped:** reload `tool_events`, gallery dedupe, stronger tests. |
| **Matrix** | [cursor-sdk-capability-matrix.md](./cursor-sdk-capability-matrix.md) | SDK feature inventory vs Odysseus status (gaps, C+, B). |
| **Upgrades** | [CURSOR_SDK_UPGRADES.md](../CURSOR_SDK_UPGRADES.md) | Pin policy, checklist, and regression hotspots when `cursor-sdk` changes. |
| **Smoke** | [CURSOR_PRE_PLAN_B_SMOKE.md](./CURSOR_PRE_PLAN_B_SMOKE.md) | Manual Chat + Agent checks before Plan B backlog (B2a–B4). |
| — | [CURSOR_INTEGRATION_VERIFICATION.md](./CURSOR_INTEGRATION_VERIFICATION.md) | API/SDK facts and handoff snippets (shared by A/B/C). |
| **Ship #23** | [merged-pr-23-cursor-sdk-upgrades.md](./merged-pr-23-cursor-sdk-upgrades.md) | **Shipped** @ `7188279` ([#23](https://github.com/lawmight/odysseus/pull/23)): Cursor 0/0 model count fix + SDK upgrade docs. |

## Guides (PRs and CI)

| Guide | Purpose |
|-------|---------|
| [UPSTREAM_PR_GUIDELINES.md](../guides/UPSTREAM_PR_GUIDELINES.md) | How to pass upstream + fork review (template, preflight, Cloud Agent video demos). |
| [CI_PARITY.md](../guides/CI_PARITY.md) | Fork vs `pewdiepie-archdaemon/odysseus` workflow parity (regenerate with `bash scripts/ci-parity-report.sh`). |

**Implementation status (2026-06-04):** Plan A/C Chat BYOK, Plan C+, and **Plan B Phase 1** (Cursor Agent engine) **shipped on `main`** ([#17](https://github.com/lawmight/odysseus/pull/17)). **PR #23** added the Cursor endpoint list fix, [upgrade playbook](../CURSOR_SDK_UPGRADES.md), and [pre–Plan B smoke](./CURSOR_PRE_PLAN_B_SMOKE.md) on `main` @ `7188279`. Plan B was given a [v2 second pass](./cursor-agent-tab-integration-plan.md): Phase 2 context injection is mostly already covered by the shared preface; remaining work (skills semantics, background-job guard, optional `generateImage` parity, MCP, cloud) is tracked in the [backlog](./cursor-agent-tab-backlog.md) and gated on the [Decision log](./cursor-agent-tab-integration-plan.md#12-decision-log).

---

## Post–Plan B Phase 1 (current)

| Check | Result |
|-------|--------|
| **Commit** | `0a70975` on `main` — `feat(agent): Cursor SDK engine for Agent mode (Plan B Phase 1)` |
| **Agent + Cursor** | Routes through `stream_cursor_agent_loop` in Agent mode |
| **Still excluded** | Compare / Research / utility resolvers skip Cursor (by design); background auto-continue guard tracked as backlog B2c |
| **Next** | Plan B v2 backlog (B2a–B4) per the [Decision log](./cursor-agent-tab-integration-plan.md#12-decision-log) |
| **CI** | GitHub Actions on `main` ([workflows](https://github.com/lawmight/odysseus/actions/workflows/ci.yml)) |

### Pre–Plan B gate (archival)

Recorded at `0696a03`: full pytest green, Agent blocked until Plan B — superseded by Phase 1 above.
