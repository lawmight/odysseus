# Plan B: Cursor SDK for Odysseus Agent Tab

**Status:** Design / pre-implementation  
**Target repo:** Odysseus  
**Verified against:** Odysseus workspace (2026-06-01), Nia (`abe7140b`, `71741e4c`), PyPI `cursor-sdk==0.1.6`

---

## 1. Goal

Add an optional **“Cursor Agent”** backend for Odysseus’s **Agent** mode (`chat_mode != "chat"`, uses `stream_agent_loop()` today), so power users can run Cursor’s full agent (tools, thinking, MCP, plan mode) from the Odysseus UI—BYO `CURSOR_API_KEY`—alongside the existing native loop.

**Clarification:** README credits [opencode](https://github.com/anomalyco/opencode) as architectural inspiration; the **implemented** agent is **`src/agent_loop.py`** + **`src/agent_tools.py`** (Python), not a subprocess to the opencode binary. This plan adds Cursor as an **alternate agent engine**, not “install opencode again.”

---

## 2. Relationship to Plan A (Chat provider)

| Aspect | Plan A (Chat) | Plan B (Agent tab) |
|--------|---------------|-------------------|
| Entry | `stream_llm()` / chat_mode `"chat"` | `stream_agent_loop()` / agent mode |
| Odysseus tools | Disabled (`tools=None`) | **Conflict risk** — Cursor runs its own tools |
| User expectation | Q&A, fast | Multi-step tasks, tool cards |
| v1 runtime | Local `launch_bridge` | Local + optional Cloud (later) |

**Recommendation:** Ship Plan A first; Plan B reuses `cursor_adapter` session/bridge plumbing but **different** stream mapper (tool events → Odysseus `tool_start` / `tool_output`).

---

## 3. SDK choice (same as Plan A)

| Item | Value |
|------|-------|
| Package | `cursor-sdk>=0.1.6` (PyPI latest verified 2026-06-01) |
| Async API | `AsyncClient.launch_bridge`, `AsyncAgent.send`, `AsyncRun.messages()` |
| Models | From `GET https://api.cursor.com/v1/models` or `client.models.list()` |
| Example model IDs | `composer-2.5`, `composer-2` (always refresh from API) |

```python
from cursor_sdk import AsyncClient, LocalAgentOptions, SendOptions

async with await AsyncClient.launch_bridge(workspace=cwd) as client:
    async with await client.agents.create(
        model="composer-2.5",
        api_key=api_key,
        local=LocalAgentOptions(cwd=cwd),
    ) as agent:
        run = await agent.send(
            user_prompt,
            SendOptions(mode="agent"),  # or "plan" for plan-first
        )
        async for msg in run.messages():
            ...
```

**Plan mode (SDK):** `mode="plan"` on create or `SendOptions(mode="agent")` on follow-up (Nia-verified python.md).

---

## 4. Odysseus Agent architecture today

### 4.1 Entry point

```784:807:routes/chat_routes.py
            else:
                # ── Agent mode: full agent loop with tools ──
                ...
                    async for chunk in stream_agent_loop(
                        sess.endpoint_url,
                        sess.model,
                        messages,
                        headers=sess.headers,
                        ...
                        session_id=session,
                        ...
                    ):
```

### 4.2 Native loop contract

```1237:1245:src/agent_loop.py
    Yields SSE events:
      - data: {"delta": "text"}
      - data: {"type": "tool_start", "tool": "...", ...}
      - data: {"type": "tool_output", "tool": "...", ...}
      - data: {"type": "agent_step", "round": N}
      - data: {"type": "metrics", "data": {...}}
      - data: [DONE]
```

Frontend handlers: `static/js/chat.js` (`tool_start`, `tool_output`, `agent_step`), `static/js/chatStream.js`, compare stream.

### 4.3 Native tool ecosystem

- Built-ins in `src/agent_tools.py` + `TOOL_SECTIONS` in `agent_loop.py`
- MCP via `get_mcp_manager()` in agent loop
- RAG tool selection, memory, skills injection via `chat_processor.py` (`agent_mode=True`)

**Cursor agent has its own tools** (`read_file`, `run_terminal_cmd`, `mcp`, etc.). Running **both** loops (Odysseus `stream_agent_loop` + Cursor tools) in one turn will duplicate work and confuse UX.

---

## 5. Design decision: three agent backends

Introduce `agent_engine` on endpoint or session:

| Engine | Behavior |
|--------|----------|
| `odysseus` (default) | Current `stream_agent_loop()` |
| `cursor_local` | Cursor SDK local bridge |
| `cursor_cloud` (later) | Cloud Agents API with repo config |

**Selection:** `ModelEndpoint.provider == "cursor"` AND `chat_mode == "agent"` → `stream_cursor_agent_loop()`.

When Cursor engine is active:

- **Disable** Odysseus native tool loop for that request (do not call `stream_llm` with tools inside agent_loop).
- Optionally still inject **read-only** context (memories, RAG) into the **prompt text** prefix, not as parallel tool APIs.

---

## 6. Stream mapping: Cursor → Odysseus Agent UI

### 6.1 Cursor SDK message types (Nia-verified)

| `message.type` | Map to |
|----------------|--------|
| `assistant` (text blocks) | `data: {"delta": text}` |
| `thinking` | `data: {"delta": text, "thinking": true}` |
| `tool_call` (`status`: running/completed) | See below |
| `status` | Optional status line in UI |
| `system` | Ignore or log |

### 6.2 Tool events

Cursor `tool_call` envelope (REST/SSE, Nia-verified):

```typescript
interface ToolCallEventData {
  callId: string;
  name: string;       // e.g. read_file, run_terminal_cmd, mcp
  status: "running" | "completed";
  args?: JsonValue;
  result?: JsonValue;
  truncated?: { args?: true; result?: true };
}
```

**Map to Odysseus:**

| Cursor | Odysseus |
|--------|----------|
| `status: "running"` | `data: {"type": "tool_start", "tool": name, "command": short_args_summary}` |
| `status: "completed"` | `data: {"type": "tool_output", "tool": name, "output": stringify(result)[:N]}` |

**Caveats (docs):** Tool `args`/`result` shapes are **not stable**—treat as untyped; stringify defensively; never `eval`.

### 6.3 “Rounds”

Odysseus uses `agent_step` with `round` for multi-round native loop. Cursor runs are one `send()` with internal steps:

- Emit `data: {"type": "agent_step", "round": 1}` at run start (optional).
- Or map `on_step` / `StepCompleted` from `SendOptions(on_step=…)` to increment round (SDK).

### 6.4 Metrics

On `run.wait()`:

```python
result.status       # finished | error | cancelled | expired
result.duration_ms
result.result       # final text
```

Emit:

```python
yield f'data: {json.dumps({"type": "metrics", "data": {
    "response_time": result.duration_ms / 1000,
    "model": model_id,
    "usage_source": "cursor",
}})}\n\n'
```

Token counts may be unavailable—UI already tolerates estimates.

---

## 7. New module layout

```
src/
  providers/
    cursor_adapter.py      # shared: bridge, agent resume, list_models
    cursor_chat.py         # Plan A: stream_cursor_chat → stream_llm contract
    cursor_agent.py        # Plan B: stream_cursor_agent_loop → agent_loop contract
```

### 7.1 `stream_cursor_agent_loop()` signature

Mirror `stream_agent_loop` kwargs where sensible:

```python
async def stream_cursor_agent_loop(
    endpoint_url: str,       # cursor://local
    model: str,
    messages: list[dict],
    *,
    api_key: str,
    cwd: str,
    session_id: str | None = None,
    temperature: float = 0.3,   # may map to model.params if supported
    max_tool_calls: int = 0,    # interpret as Cursor-side budget hint only
    owner: str | None = None,
) -> AsyncGenerator[str, None]:
```

### 7.2 Branch in `chat_routes.py`

```python
if _is_cursor_endpoint(sess.endpoint_url):
    from src.providers.cursor_agent import stream_cursor_agent_loop
    chunk_iter = stream_cursor_agent_loop(...)
else:
    chunk_iter = stream_agent_loop(...)
```

---

## 8. MCP and skills

| Feature | Native agent | Cursor agent |
|---------|--------------|--------------|
| Odysseus MCP servers (`McpServer` DB) | Wired in agent_loop | **Not automatic** — pass via `SendOptions(mcp_servers=…)` or `.cursor/mcp.json` in `cwd` |
| Skills (`skills_manager`) | Injected in agent_mode | Inject skill **text** into prompt only, or configure Cursor project rules |
| Memory / RAG | Tools + context | Prefix context in first `send()` |

**v1 recommendation:** Document that Cursor Agent mode uses **workspace `.cursor/mcp.json`** for MCP, not the Odysseus MCP admin UI—unless you implement explicit `mcp_servers` mapping from `McpServer` rows (Phase 3).

---

## 9. Cloud Agents (Phase 2+)

Cloud API (Nia-verified):

- `POST /v1/agents` — create agent + initial run
- `POST /v1/agents/{id}/runs` — follow-up (409 if busy)
- `GET /v1/agents/{id}/runs/{runId}/stream` — SSE

Requires UI for:

- GitHub repo URL, `startingRef`, `autoCreatePR`
- Link-out to `agent.url` on cursor.com

Odysseus settings panel extension:

```json
{
  "runtime": "cloud",
  "repos": [{"url": "https://github.com/org/repo", "startingRef": "main"}],
  "auto_create_pr": false
}
```

**Billing:** Same Cursor usage pools; SDK runs tagged “SDK” in dashboard (per python.md).

---

## 10. Database and settings

Reuse Plan A columns:

- `ModelEndpoint.provider = "cursor"`
- `ModelEndpoint.provider_config` JSON

Add session fields:

```sql
ALTER TABLE sessions ADD COLUMN cursor_agent_id TEXT;
ALTER TABLE sessions ADD COLUMN agent_engine TEXT DEFAULT 'odysseus';
```

Or store in `settings` keyed by `session_id` to avoid migration (weaker for multi-worker).

---

## 11. Admin UX

1. Model endpoint: **Cursor Agent (local)** — API key + workspace path.
2. Toggle per endpoint: **Allow in Agent tab** / **Allow in Chat only** (two flags in `provider_config`).
3. Global setting (optional): `default_agent_engine` = `odysseus` | `cursor`.

Chat mode selector unchanged; engine picked by endpoint + mode.

---

## 12. Implementation phases

### Phase 1 — Parallel engine (local)

- [ ] `stream_cursor_agent_loop()` with tool_start/tool_output mapping
- [ ] `chat_routes.py` branch on cursor endpoint + agent mode
- [ ] Disable `stream_agent_loop` when cursor active
- [ ] Session `cursor_agent_id` persistence + resume
- [ ] Manual test: file edit tool shows in UI

### Phase 2 — Context injection

- [ ] Prepend memories/RAG/system preset into `send()` text
- [ ] Vision: map Odysseus attachments to `UserMessage(images=…)`

### Phase 3 — MCP bridge

- [ ] Export Odysseus `McpServer` configs → `SendOptions(mcp_servers=…)` per run
- [ ] Document security (secrets in env)

### Phase 4 — Cloud

- [ ] `cursor_cloud` engine + repo UI
- [ ] REST SSE client path (optional if SDK cloud is enough)

---

## 13. Things to be careful about

1. **Double agent loops:** Never call `stream_agent_loop` and Cursor tools in the same turn.
2. **409 agent_busy:** Agent tab users spam clicks — queue sends per session.
3. **Workspace safety:** Cursor local agent can run shell commands in `cwd`—treat `cwd` as a security boundary (same as Odysseus shell tools).
4. **Unstable tool payloads:** Do not build Odysseus tool routing on Cursor `name` beyond display.
5. **Compare / Research / Tasks:** Each calls LLM separately—decide if Cursor endpoints appear there (default: **hide** for v1).
6. **Background jobs:** `src/bg_monitor.py` uses `stream_agent_loop` — exclude cursor endpoints or implement cursor variant.
7. **Public beta API:** Pin `cursor-sdk` version; monitor Cloud Agents changelog.
8. **Team Admin API keys:** Not supported — validate and error.
9. **Bridge in Docker:** Same as Plan A; document clearly.
10. **Acknowledgments:** README says “built on opencode”—PR should say “optional Cursor agent engine via cursor-sdk” without removing opencode credit.

---

## 14. Testing checklist

- [ ] Agent mode + Cursor endpoint: tool cards appear (`tool_start` / `tool_output`)
- [ ] Multi-turn: second message uses same `agent_id`, context preserved
- [ ] Stop button cancels run (`run.cancel()`)
- [ ] Native endpoint still uses `stream_agent_loop` (regression)
- [ ] Skills/memory: verify injected context appears in reply (manual)
- [ ] `agent_busy`: rapid double-send handled gracefully
- [ ] Incognito / compare / research do not accidentally invoke cursor engine

---

## 15. PR strategy (upstream)

- **Depends on:** Plan A shared `cursor_adapter.py` (bridge + models + auth)
- **Title:** `feat(agent): optional Cursor SDK engine for Agent mode`
- Split commits: adapter shared → chat → agent
- Feature flag: `provider=cursor` only when `cursor-sdk` installed

---

## 16. Reference: Odysseus vs Cursor tool UX

**Native (today):**

```python
# agent_loop yields after executing Odysseus tools locally
yield f'data: {json.dumps({"type": "tool_start", "tool": tool_name, ...})}\n\n'
# ... execute ...
yield f'data: {json.dumps({"type": "tool_output", "tool": tool_name, "output": out})}\n\n'
```

**Cursor (map from SDK):**

```python
elif message.type == "tool_call":
    if message.status == "running":
        yield f'data: {json.dumps({"type": "tool_start", "tool": message.name, "command": _brief(message.args)})}\n\n'
    elif message.status in ("completed", "error"):
        yield f'data: {json.dumps({"type": "tool_output", "tool": message.name, "output": _brief(message.result)})}\n\n'
```

(Exact attribute names: confirm against `cursor-sdk==0.1.6` types in implementation—SDK uses `SDKToolUseMessage` with `call_id`, `name`, `status`, `args`, `result`.)

---

## 17. Nia verification log

| Claim | Source |
|-------|--------|
| Agent SSE: `tool_start`, `tool_output`, `agent_step` | Repo `src/agent_loop.py:1237-1245` |
| Agent route uses `stream_agent_loop` | Repo `routes/chat_routes.py:784-807` |
| Cursor tool_call envelope | Nia `abe7140b` |
| `409 agent_busy`, stream events | Nia `abe7140b` |
| `SendOptions(mode=)`, plan/agent modes | Nia `71741e4c` |
| `cursor-sdk` 0.1.6, AsyncClient | PyPI + Nia `71741e4c` |
| opencode not in `src/` | Repo grep (acknowledgment only) |

---

## 18. Open questions for maintainers

1. Should Cursor Agent **replace** or **complement** native agent for default installs?
2. Is running Cursor bridge inside official Docker image acceptable license/size-wise?
3. Should cloud Cursor agents appear in Odysseus at all, or link out to cursor.com?
4. Do we map Odysseus MCP servers automatically (security review)?
