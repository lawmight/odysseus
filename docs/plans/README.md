# Cursor × Odysseus integration plans

| Plan | File | Purpose |
|------|------|---------|
| **A** | [cursor-chat-model-provider-plan.md](./cursor-chat-model-provider-plan.md) | First design: Cursor as a Chat adapter (`cursor-sdk`, `cursor://local`). |
| **B** | [cursor-agent-tab-integration-plan.md](./cursor-agent-tab-integration-plan.md) | Optional second engine for the **Agent** tab (Cursor tools, `tool_start` / `tool_output`). |
| **C** | [cursor-plan-c-chat-byok-polished.md](./cursor-plan-c-chat-byok-polished.md) | **Canonical goal** for upstream: Chat BYOK parity with other providers; defers B. |
| — | [CURSOR_INTEGRATION_VERIFICATION.md](./CURSOR_INTEGRATION_VERIFICATION.md) | API/SDK facts and handoff snippets (shared by A/B/C). |

**Implementation status (2026-06-01):** Chat adapter MVP lives on branch `cursor/cursor-chat-provider-e76a` ([PR #2](https://github.com/lawmight/odysseus/pull/2)). Use **Plan C** for what to finish before calling the integration “as polished as OpenRouter/Anthropic” in Chat.
