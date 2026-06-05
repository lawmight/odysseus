# Plan B v2: Cursor SDK engine for Odysseus Agent mode

**Status:** **Phase 1 plus B2a-B3 follow-ups shipped**; Cloud Cursor agents remain out of scope for Odysseus v1.
**Target repo:** Odysseus
**Reconciled against:** `main` @ `2a0e5de` (2026-06-04), [`cursor-sdk-capability-matrix.md`](./cursor-sdk-capability-matrix.md)

> This is the **second pass**. The original Plan B was written before Plan A/C/C+ and before Phase 1 existed, so several "future" phases were either already solved by shared adapter work or need a different framing. The capability matrix is the machine-readable gap list; this doc is the human roadmap and decision log.

---

## 1. Status and scope

| Layer | State | Where |
|-------|-------|-------|
| Agent mode routes to Cursor engine | shipped | [`routes/chat_routes.py`](../../routes/chat_routes.py) agent branch (`_detect_provider == "cursor"`) |
| Cursor agent stream loop | shipped | [`src/providers/cursor_agent.py`](../../src/providers/cursor_agent.py) `stream_cursor_agent_loop` |
| Tool events -> Agent UI cards | shipped | `cursor_agent_tool_call_chunks` -> `tool_start` / `tool_output` |
| Durable agent resume | shipped (shared with Chat) | `sessions.cursor_agent_id`, `cursor_adapter.build_cursor_user_message` |
| Context (memory / RAG / web) into the agent prompt | mostly shipped via shared preface | see Section 5 |
| Skills semantics on Cursor engine | shipped | Section 5.2 |
| Background auto-continue on Cursor sessions | shipped guard | Section 5.3 |
| Tool mapper dedupe | shipped | Section 5.4 |
| MCP into the Cursor agent | shipped opt-in; disabled by default | Section 6 |
| Cloud Cursor agents in Odysseus | wont-fix v1 | Section 7 |

**v2 covers:** finishing the documentation of Phase 1 as-built, reframing Phase 2 around what already exists, and documenting the shipped follow-ups ([`cursor-agent-tab-backlog.md`](./cursor-agent-tab-backlog.md)). Cloud runtime remains outside this plan.

---

## 2. Goal (unchanged intent)

Add an optional **Cursor agent engine** for Odysseus Agent mode (`chat_mode == "agent"`) so power users can run Cursor's own agent (tools, thinking, plan mode) from the Odysseus UI with their own `CURSOR_API_KEY`, alongside the native [`src/agent_loop.py`](../../src/agent_loop.py) engine.

**Invariant (still true):** never run the native `stream_agent_loop` and the Cursor agent in the same turn. They each carry their own tool ecosystem; running both duplicates work and confuses the UI.

---

## 3. Relationship to Plan A / C / C+

Plan A/C built a **shared adapter** ([`src/providers/cursor_adapter.py`](../../src/providers/cursor_adapter.py)) and a **Chat mapper** (`stream_cursor_chat`). Plan B reuses the adapter and adds an **Agent mapper** (`stream_cursor_agent_loop`). One bridge pool, two mappers.

| Concern | Chat (Plan A/C/C+) | Agent (Plan B) |
|---------|--------------------|----------------|
| Entry | `stream_llm` -> `stream_cursor_chat` | `stream_cursor_agent_loop` |
| Send mode | default | `SendOptions(mode="agent")` |
| Tool policy | allowlist (`CURSOR_CHAT_TOOL_ALLOWLIST` = `{generateImage}`) | all tools -> generic `tool_start` / `tool_output` |
| `generateImage` -> gallery | yes (`cursor_tool_call_chunks`) | yes (delegates to shared gallery path) |
| Bridge / resume / cancel / images | shared `cursor_adapter` | shared `cursor_adapter` |
| Heartbeat SSE | shared pattern | `_heartbeat_interval_sec` in `cursor_agent.py` |

Anything in the "shared" rows is **inherited** and must not be re-specified or reimplemented in Plan B work.

---

## 4. As-built Phase 1 (do not redo)

`stream_cursor_agent_loop` ([`src/providers/cursor_agent.py`](../../src/providers/cursor_agent.py)) already:

- validates the endpoint and SDK availability, then resolves the API key and workspace `cwd` via the shared adapter helpers;
- builds the send payload with `build_cursor_user_message(messages, resume=...)`, so the **system prefix + last user message + image attachments** reach the agent on every turn (same helper Chat uses);
- creates a new Cursor agent or resumes `cursor_agent_id`, emitting `cursor_agent_id` SSE on first create so [`routes/chat_routes.py`](../../routes/chat_routes.py) can persist it via `session_manager.set_cursor_agent_id`;
- sends with `{"model": model, "mode": "agent"}`;
- streams `assistant` -> `delta`, `thinking` -> `delta` + `thinking: true`, `tool_call` -> `cursor_agent_tool_call_chunks`, `error` -> SSE error;
- delegates Cursor Agent `generateImage` completions to the shared gallery path when the workspace is known, so the Agent thread receives `/api/generated-image/...` metadata like Chat;
- enforces an optional `max_tool_calls` budget (from `agent_max_tool_calls` setting) and emits `budget_exceeded`;
- optionally passes enabled Odysseus MCP DB rows to `SendOptions.mcp_servers` when `cursor_agent_mcp_from_db` is explicitly enabled;
- emits a periodic `: heartbeat` comment so the tunnel stays alive during long tool runs;
- registers the run for `cancel_cursor_run` (Stop button) and cleans up on disconnect;
- emits `usage` with `total_time` on completion, then `[DONE]`.

### 4.1 SSE contract differences from the native loop

| Event | Native `stream_agent_loop` | Cursor agent | Note |
|-------|----------------------------|--------------|------|
| Completion metrics | `type: metrics` | `type: usage` (`total_time` only) | `chat_routes` agent branch handles `usage`; token counts may be absent |
| Round markers | `type: agent_step` with `round` | not emitted | UI tolerates absence; Cursor runs as one `send()` |
| Tool cards | `tool_start` / `tool_output` | same shape | parity |

### 4.2 Phase 1 acceptance checklist (manual desk QA)

These were never closed and are **QA, not research**:

- [ ] Agent mode + Cursor endpoint: tool cards appear (`tool_start` / `tool_output`).
- [ ] Multi-turn: second message resumes the same `cursor_agent_id`, context preserved.
- [ ] Stop button cancels the run (`cancel_cursor_run`).
- [ ] Native endpoint still uses `stream_agent_loop` (regression).
- [ ] Rapid double-send handled gracefully (no `agent_busy` crash).
- [ ] Compare / Research / incognito do not invoke the Cursor engine.

Automated coverage today: [`tests/test_cursor_agent.py`](../../tests/test_cursor_agent.py) (mapper + heartbeat + Agent `generateImage` gallery + routing), [`tests/test_cursor_agent_skills.py`](../../tests/test_cursor_agent_skills.py), [`tests/test_bg_monitor_cursor.py`](../../tests/test_bg_monitor_cursor.py), and [`tests/test_cursor_mcp_bridge.py`](../../tests/test_cursor_mcp_bridge.py).

---

## 5. Context and Odysseus features (reframed Phase 2)

The original Phase 2 said "prepend memories/RAG into `send()`." Most of that already happens, because Agent mode builds the same context preface as before and passes `ctx.messages` straight into the Cursor loop.

### 5.1 Context injection (mostly shipped)

Flow:

```
chat_routes prepare_chat (agent_mode=True)
  -> ChatProcessor.prepare_context  (memory + RAG + web + URL fetch)   src/chat_processor.py
  -> ctx.messages                                                       (system preface + history)
  -> stream_cursor_agent_loop(messages)
  -> build_cursor_user_message(resume=...)                              src/providers/cursor_adapter.py
        resume:    "System instructions: <prefix>" + last user + images
        first turn: full transcript via build_cursor_prompt + images
```

So memory, RAG documents, and web results already reach the Cursor agent as system/context text. **No rebuild of `build_cursor_user_message` is needed.** v2 task here is documentation: state clearly that Cursor agent context is delivered as prompt text (not Odysseus tool APIs), and that on resume the SDK agent also holds prior conversation memory.

Vision is shipped too: `build_cursor_user_message` already attaches `SDKImage` from attachments (matrix Section 7). Remaining image edge cases (`SDKImage.url_image` for remote URLs) stay backlog, not Plan B v1.

### 5.2 Skills (product decision -> D4)

[`ChatProcessor.prepare_context`](../../src/chat_processor.py) injects a **skills index** in native agent mode that instructs the model to call `manage_skills(action='view', ...)`. The Cursor agent **cannot call Odysseus tools**, so Cursor agent sessions omit that tool-oriented skills index. Native Agent sessions still receive it.

### 5.3 Background auto-continue (small code -> B2c)

[`src/bg_monitor.py`](../../src/bg_monitor.py) detects Cursor-backed sessions before `_drain_agent` and skips native auto-continue with a log note. This avoids running `stream_agent_loop` against a `cursor://local` endpoint. A full Cursor follow-up path remains future work if product needs it.

### 5.4 Tool mapper hygiene (optional -> B2d)

There are still two public mappers: `cursor_tool_call_chunks` (Chat, allowlist + `generateImage` gallery) and `cursor_agent_tool_call_chunks` (Agent, all tools, generic). They now share internal helpers in `cursor_adapter` for tool-call extraction, `tool_start` / `tool_output` construction, result formatting, and exit-code extraction. This keeps Chat and Agent policies separate while removing the duplicated low-level SSE logic.

---

## 6. MCP (Phase 3 - documented default plus opt-in DB bridge)

| Approach | v2 stance |
|----------|-----------|
| Workspace `.cursor/mcp.json` in the agent `cwd` | **Default.** The bridge runs in `cwd`, so MCP servers configured there are picked up by the Cursor agent. |
| Map Odysseus `McpServer` DB rows -> `SendOptions(mcp_servers=...)` | **Implemented opt-in.** Set `cursor_agent_mcp_from_db: true` in `data/settings.json`. Enabled stdio/SSE/HTTP rows are serialized by `src/providers/cursor_mcp.py`; rows with per-tool disabled lists are skipped. |
| `agent.reload()` after MCP file edits | Backlog note (matrix `agent.reload`). |

The DB bridge is disabled by default because MCP commands, URLs, and stdio environment values are passed to the Cursor bridge/runtime. See Decision D2.

---

## 7. Cloud Cursor agents (Phase 4 appendix - wont-fix v1)

The Cloud Agents API (repos, auto-create-PR, hosted VMs) is a separate product surface. The capability matrix marks all `cloud.*` rows `n/a` / `wont-fix` for Odysseus v1. If Odysseus ever wants this, it should be a **new plan** ("Cursor Cloud Agents in Odysseus"), not a Plan B phase. For now Odysseus uses the **local bridge** only. See Decision D3.

---

## 8. Callers that must stay native

Cursor must not leak into these paths; they call the LLM separately and have no Cursor mapping:

| Path | Guard | File |
|------|-------|------|
| Compare | mode guard | [`routes/chat_routes.py`](../../routes/chat_routes.py) |
| Deep Research | mode guard | [`routes/chat_routes.py`](../../routes/chat_routes.py), [`routes/research_routes.py`](../../routes/research_routes.py) |
| Utility / vision resolver | `exclude_cursor` | [`src/endpoint_resolver.py`](../../src/endpoint_resolver.py) |
| Background task HTTP | no `cursor://` HTTP fallback | [`src/endpoint_resolver.py`](../../src/endpoint_resolver.py) |
| Background auto-continue | skip guard | [`src/bg_monitor.py`](../../src/bg_monitor.py) |

---

## 9. Testing and QA

Automated (run after any Plan B change):

```bash
pytest tests/test_cursor_agent.py tests/test_cursor_chat_tool_events.py \
       tests/test_cursor_adapter.py -q
```

Manual desk QA: Section 4.2 checklist (needs a real `CURSOR_API_KEY` and the SDK bridge on the Odysseus host).

---

## 10. Upstream PR packaging (2026)

### 10.1 What is already on fork `main`

| Work | Commit / PR |
|------|-------------|
| Plan A/C Chat BYOK | `3a1b985` (PR #2) |
| Plan C+ generateImage in Chat | folded into `main` |
| Plan B Phase 1 Agent engine | `0a70975` ([#17](https://github.com/lawmight/odysseus/pull/17)) |

### 10.2 Upstream handoff (pewdiepie-archdaemon/odysseus)

[`CONTRIBUTING.md`](../../CONTRIBUTING.md) points contributors at `pewdiepie-archdaemon/odysseus`. The Cursor work lives on `lawmight/odysseus`. For an upstream review, prefer a **two-PR narrative** unless the fork diff is already squashed:

1. `feat(chat): Cursor BYOK provider with Chat parity (cursor-sdk)` - Plan A/C + C+.
2. `feat(agent): optional Cursor SDK engine for Agent mode` - Plan B Phase 1, depends on (1).

Follow-ups B2a-B3 are small Agent-polish changes layered on top of (2). B4 remains a separate future product plan.

**Reviewer guide to include in the PR body:**

- Large diff; optional dependency `requirements-cursor.txt` (feature is inert without the SDK).
- The SDK bridge runs on the Odysseus host, not inside the default Docker image.
- opencode acknowledgment unchanged ([`ACKNOWLEDGMENTS.md`](../../ACKNOWLEDGMENTS.md)); Plan B adds Cursor as an alternate engine, it does not replace the native loop.
- This **supersedes** the old Plan C guidance to "block Agent + Cursor" - Agent is supported since Phase 1.

No push to upstream is part of this documentation pass.

---

## 11. Nia / repo verification log

| Claim | Source |
|-------|--------|
| Agent SSE: `tool_start`, `tool_output`, `agent_step` | [`src/agent_loop.py`](../../src/agent_loop.py) |
| Agent route branches on Cursor provider | [`routes/chat_routes.py`](../../routes/chat_routes.py) `_detect_provider` |
| Cursor tool_call envelope | Nia `abe7140b` |
| `SendOptions(mode=)`, plan/agent modes | Nia `71741e4c` |
| `cursor-sdk` 0.1.6, AsyncClient | PyPI + Nia `71741e4c` |
| Plan B v2 reconciled against `main` @ `2a0e5de` | this pass (2026-06-04) |

Re-query Nia / docs only when `cursor-sdk` bumps past 0.1.6.

---

## 12. Decision log

These are the roadcrosses that need a human (maintainer) decision. Recommended defaults reflect a balanced stance; change the Decision column to steer future work.

| ID | Question | Recommended default | Decision | Blocks |
|----|----------|---------------------|----------|--------|
| D1 | Should the Agent engine surface `generateImage` via the gallery like Chat (C+)? | Yes - reuse the shared publish path | **yes; shipped** | B2a |
| D2 | Wire Odysseus MCP admin (`McpServer`) into the Cursor agent? | Default to `.cursor/mcp.json`; DB mapping requires explicit opt-in because it shares MCP config/secrets with Cursor | **opt-in shipped; default off** | B3 |
| D3 | Support cloud Cursor agents inside Odysseus? | No for v1 (wont-fix); separate plan if ever wanted | _default_ | B4 |
| D4 | What do skills mean on a Cursor agent session? | Omit the `manage_skills` index; optionally inject skill bodies as read-only text | **omit index; shipped** | B2b |
| D5 | Add an `agent_engine` DB column, or infer the engine? | Infer from `provider=cursor` + `chat_mode=agent`; no migration | _default_ | - |
| D6 | One upstream PR or two? | Two (Chat, then Agent) unless the fork diff is already squashed | _default_ | upstream review |

---

## 13. Backlog

See [`cursor-agent-tab-backlog.md`](./cursor-agent-tab-backlog.md) for shipped B2a-B3 details and deferred B4 scope.
