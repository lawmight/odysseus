# Cursor × Odysseus integration plans

| Plan | File | Purpose |
|------|------|---------|
| **A** | [cursor-chat-model-provider-plan.md](./cursor-chat-model-provider-plan.md) | First design: Cursor as a Chat adapter (`cursor-sdk`, `cursor://local`). |
| **B** | [cursor-agent-tab-integration-plan.md](./cursor-agent-tab-integration-plan.md) | Optional second engine for the **Agent** tab (Cursor tools, `tool_start` / `tool_output`). |
| **C** | [cursor-plan-c-chat-byok-polished.md](./cursor-plan-c-chat-byok-polished.md) | **Canonical goal** for upstream: Chat BYOK parity with other providers; defers B. |
| **Ship** | [cursor-merge-and-ship-plan.md](./cursor-merge-and-ship-plan.md) | **Shipped** on `main` @ `3a1b985` (PR #2, 2026-06-02). |
| **C+** | [cursor-useful-tools-plan.md](./cursor-useful-tools-plan.md) | **Shipped:** Cursor `generateImage` in Chat (`image_url` via gallery). |
| **C+ polish** | [cursor-plan-c-plus-polish.md](./cursor-plan-c-plus-polish.md) | **Shipped:** reload `tool_events`, gallery dedupe, stronger tests. |
| **Matrix** | [cursor-sdk-capability-matrix.md](./cursor-sdk-capability-matrix.md) | SDK feature inventory vs Odysseus status (gaps, C+, B). |
| — | [CURSOR_INTEGRATION_VERIFICATION.md](./CURSOR_INTEGRATION_VERIFICATION.md) | API/SDK facts and handoff snippets (shared by A/B/C). |

**Implementation status (2026-06-03):** Plan A/C Chat BYOK **shipped on `main`**. Plan C+ **`generateImage` in Chat** shipped. Pre–Plan B cleanup **complete**. Next: [cursor-agent-tab-integration-plan.md](./cursor-agent-tab-integration-plan.md) (Plan B).

---

## Pre–Plan B gate (recorded)

| Check | Result |
|-------|--------|
| **Commit** | `0696a03` on `main` (2026-06-03) |
| **Full pytest** | `1484 passed, 1 skipped` (`python -m pytest -q`) |
| **Agent + Cursor** | Blocked with HTTP 400 “Chat only” (expected until Plan B) |
| **Plan B code** | **Not started** |
| **CI** | GitHub Actions on `main` ([workflows](https://github.com/lawmight/odysseus/actions/workflows/ci.yml)); enable required checks per [CONTRIBUTING.md](../../CONTRIBUTING.md#branch-protection-maintainers) |

**Cleanup PRs:** [#15](https://github.com/lawmight/odysseus/pull/15) lockfile, [#16](https://github.com/lawmight/odysseus/pull/16) CI, optional SDK + `ci: data/` fix on `main`.

### Entry criteria before Plan B Phase 1

- [x] `main` clean; `package.json` name pins lockfile
- [x] Full pytest green locally @ `0696a03`
- [x] Docs on `main` under `docs/plans/` (no `plan-docs-efe9` pointers)
- [ ] GitHub required status checks enabled (maintainer)
- [ ] Plan B product defaults in first Plan B PR description (`SendOptions(mode="agent")`, Compare/Research stay blocked)
