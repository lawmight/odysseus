# Plan B backlog: Cursor Agent engine follow-ups

Ordered implementation epics that follow [Plan B v2](./cursor-agent-tab-integration-plan.md). B2a-B3 are implemented; B4 remains a separate future plan. Decision IDs refer to the Plan B v2 Decision log (Section 12).

| Epic | Priority | Status | Decision |
|------|----------|--------|----------|
| B2a `generateImage` in Agent | P1 | **shipped** | D1 |
| B2b Skills semantics on Cursor agent | P1 | **shipped** | D4 |
| B2c `bg_monitor` Cursor guard | P1 | **shipped** | - |
| B2d Tool mapper dedupe | P2 | **shipped** | - |
| B3 MCP DB -> SDK | P3 | **shipped, disabled by default** | D2 |
| B4 Cloud Cursor agents | P4 / wont-fix v1 | deferred / separate plan | D3 |

---

## B2a - generateImage in Agent (P1, D1)

**Goal:** when the Cursor agent emits a `generateImage` `tool_call`, surface the image in the Agent thread the same way Chat does (gallery URL via `/api/generated-image/...`), instead of a generic text `tool_output`.

**Status:** shipped. `cursor_agent_tool_call_chunks` delegates `generateImage` to the shared Chat/gallery mapper when the workspace is known.

**Files:**

- [`src/providers/cursor_agent.py`](../../src/providers/cursor_agent.py) `cursor_agent_tool_call_chunks` - delegate the `generateImage` case to the shared Chat mapper.
- [`src/providers/cursor_adapter.py`](../../src/providers/cursor_adapter.py) `cursor_tool_call_chunks` / `publish_cursor_generated_image` - reuse; keep bytes + gallery logic in the adapter (no layer bleed per [`.cursor/BUGBOT.md`](../../.cursor/BUGBOT.md)).
- [`src/providers/cursor_agent.py`](../../src/providers/cursor_agent.py) `stream_cursor_agent_loop` - pass `workspace` / `model` / `session_id` / `owner` to the mapper.

**Acceptance test:** extend [`tests/test_cursor_agent.py`](../../tests/test_cursor_agent.py), mirroring the gallery assertions in [`tests/test_cursor_chat_tool_events.py`](../../tests/test_cursor_chat_tool_events.py) (image bytes -> `image_url` under `/api/generated-image/`). Matrix rows: `stream.tool_call`, `tool.generateImage`.

---

## B2b - Skills semantics on Cursor agent (P1, D4)

**Goal:** stop telling the Cursor agent to call `manage_skills` (a tool it cannot use). Omit the skills index for Cursor agent sessions; optionally inject a capped number of skill bodies as read-only context.

**Status:** shipped. Cursor Agent context omits the `manage_skills` index; native Agent sessions still receive it.

**Files:** [`src/chat_processor.py`](../../src/chat_processor.py) `prepare_context` (the `agent_mode and ... skills_manager` block), gated by a flag derived from provider detection in [`routes/chat_routes.py`](../../routes/chat_routes.py).

**Acceptance test:** preface output for a Cursor agent session contains no `manage_skills` index block. Matrix row: `ody.chat_only_guard` notes.

---

## B2c - bg_monitor Cursor guard (P1)

**Goal:** the background-job auto-continue must not run the native `stream_agent_loop` against a Cursor session.

**Status:** shipped. Cursor-backed follow-ups are marked handled with a log note instead of invoking the native loop.

**Files:** [`src/bg_monitor.py`](../../src/bg_monitor.py) `_run_followup` / `_drain_agent` - detect Cursor sessions (reuse `_detect_provider` / `is_cursor_url`) and skip with a logged system note rather than running the wrong engine.

**Acceptance test:** new `tests/test_bg_monitor_cursor.py` - a Cursor session is skipped (native loop not invoked). Matrix row: `ody.chat_only_guard`.

---

## B2d - Tool mapper dedupe (P2, timeboxed)

**Goal:** a single `tool_call -> SSE` mapper parameterized by allowlist and image handling, replacing the near-duplicate `cursor_tool_call_chunks` and `cursor_agent_tool_call_chunks`.

**Status:** shipped. Public Chat and Agent mapper wrappers remain separate, but they share extraction, start/output chunk construction, result formatting, and exit-code helpers in [`src/providers/cursor_adapter.py`](../../src/providers/cursor_adapter.py). Chat still keeps the `generateImage`-only allowlist.

---

## B3 - MCP DB -> SDK (P3, D2)

**Goal:** optionally map Odysseus `McpServer` rows to `SendOptions(mcp_servers=...)` for the Cursor agent.

**Status:** shipped as an explicit opt-in. By default Cursor Agent uses Cursor workspace/user MCP config such as `.cursor/mcp.json`. Set `cursor_agent_mcp_from_db: true` in `data/settings.json` to pass enabled Odysseus MCP DB rows to Cursor SDK `SendOptions.mcp_servers`.

**Safety notes:** enabling this shares MCP commands, URLs, and stdio environment values with the Cursor bridge/runtime. Rows with per-tool disabled lists are skipped because Cursor SDK inline MCP config cannot represent Odysseus' per-tool hiding policy. Matrix rows: `mcp.*`.

---

## B4 - Cloud Cursor agents (P4 / wont-fix v1, D3)

**Goal:** if ever desired, support cloud Cursor agents (repos, auto-create-PR). Out of scope for Odysseus v1; track as a separate plan, not a Plan B phase. Matrix rows: `cloud.*`, `rest.*`.
