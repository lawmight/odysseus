# Cursor × Odysseus integration plans

| Plan | File | Purpose |
|------|------|---------|
| **A** | [cursor-chat-model-provider-plan.md](./cursor-chat-model-provider-plan.md) | First design: Cursor as a Chat adapter (`cursor-sdk`, `cursor://local`). |
| **B** | [cursor-agent-tab-integration-plan.md](./cursor-agent-tab-integration-plan.md) | Optional second engine for the **Agent** tab (Cursor tools, `tool_start` / `tool_output`). |
| **C** | [cursor-plan-c-chat-byok-polished.md](./cursor-plan-c-chat-byok-polished.md) | **Canonical goal** for upstream: Chat BYOK parity with other providers; defers B. |
| **Ship** | [cursor-merge-and-ship-plan.md](./cursor-merge-and-ship-plan.md) | **Shipped** on `main` @ `3a1b985` (PR #2, 2026-06-02). |
| **C+** | [cursor-useful-tools-plan.md](./cursor-useful-tools-plan.md) | **Shipped:** Cursor `generateImage` in Chat (`image_url` via gallery). |
| **C+ polish** | [cursor-plan-c-plus-polish.md](./cursor-plan-c-plus-polish.md) | Follow-up: reload persistence, gallery dedupe, stronger tests. |
| **Matrix** | [cursor-sdk-capability-matrix.md](./cursor-sdk-capability-matrix.md) | SDK feature inventory vs Odysseus status (gaps, C+, B). |
| — | [CURSOR_INTEGRATION_VERIFICATION.md](./CURSOR_INTEGRATION_VERIFICATION.md) | API/SDK facts and handoff snippets (shared by A/B/C). |

**Implementation status (2026-06-03):** Plan A/C Chat BYOK **shipped on `main`**. Plan C+ **`generateImage` in Chat** shipped. Next: [cursor-agent-tab-integration-plan.md](./cursor-agent-tab-integration-plan.md) (Plan B).
