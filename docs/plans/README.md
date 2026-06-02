# Cursor × Odysseus integration plans

| Plan | File | Purpose |
|------|------|---------|
| **A** | [cursor-chat-model-provider-plan.md](./cursor-chat-model-provider-plan.md) | First design: Cursor as a Chat adapter (`cursor-sdk`, `cursor://local`). |
| **B** | [cursor-agent-tab-integration-plan.md](./cursor-agent-tab-integration-plan.md) | Optional second engine for the **Agent** tab (Cursor tools, `tool_start` / `tool_output`). |
| **C** | [cursor-plan-c-chat-byok-polished.md](./cursor-plan-c-chat-byok-polished.md) | **Canonical goal** for upstream: Chat BYOK parity with other providers; defers B. |
| **Ship** | [cursor-merge-and-ship-plan.md](./cursor-merge-and-ship-plan.md) | **Active:** branch/PR cleanup, fold into PR #2, merge to `main`. |
| — | [CURSOR_INTEGRATION_VERIFICATION.md](./CURSOR_INTEGRATION_VERIFICATION.md) | API/SDK facts and handoff snippets (shared by A/B/C). |

**Implementation status (2026-06-02):** Plan A/C Chat BYOK is **done on branch `cursor/merge-upstream-pr8-91e4`** (includes PR #8 content + Jun 2 picker/SDKImage fixes). **PR [#8](https://github.com/lawmight/odysseus/pull/8) is superseded.** **PR [#2](https://github.com/lawmight/odysseus/pull/2)** remains the umbrella into `main` — see [cursor-merge-and-ship-plan.md](./cursor-merge-and-ship-plan.md).
