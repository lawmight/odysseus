# Cursor × Odysseus integration — verification sheet

**Generated:** 2026-06-01  
**Purpose:** Hand to another agent implementing Plan A or Plan B. All items below were cross-checked against the Odysseus repo and Nia-indexed Cursor documentation unless marked “local only”.

---

## Plan files

| File | Description |
|------|-------------|
| `docs/plans/cursor-chat-model-provider-plan.md` | Plan A — Chat tab model provider |
| `docs/plans/cursor-agent-tab-integration-plan.md` | Plan B — Agent tab Cursor engine |
| `docs/plans/cursor-sdk-capability-matrix.md` | SDK × Odysseus capability matrix |
| `docs/plans/CURSOR_INTEGRATION_VERIFICATION.md` | This verification sheet |

---

## Verified versions and packages

| Item | Verified value | How verified |
|------|----------------|--------------|
| `cursor-sdk` (PyPI) | **0.1.6** (also 0.1.0–0.1.5 exist) | `pip index versions cursor-sdk` on agent VM |
| Install command (docs) | `uv pip install cursor-sdk` | Nia source `71741e4c` (python.md) |
| Recommended pin | `cursor-sdk>=0.1.6` | PyPI latest + docs examples |
| Odysseus Python | **3.11+** (README) | `README.md` |
| Odysseus stack | FastAPI, httpx, SQLAlchemy | `requirements.txt` |
| Cloud Agents API | **v1 public beta** | Nia `abe7140b` (endpoints.md intro) |

---

## Verified API surface (Cursor)

| Endpoint / behavior | Detail | Nia doc ID |
|-------------------|--------|------------|
| `GET https://api.cursor.com/v1/models` | Returns `items[].id`, `displayName`, `parameters`, `variants` | `abe7140b` |
| `POST /v1/agents` | Create agent + initial run | `abe7140b` |
| `POST /v1/agents/{id}/runs` | Follow-up; **409 `agent_busy`** if run CREATING/RUNNING | `abe7140b` |
| `GET …/runs/{runId}/stream` | SSE: `status`, `assistant`, `thinking`, `tool_call`, `result`, `done`, `error` | `abe7140b` |
| Stream retention | **410 `stream_expired`** after retention window | `abe7140b` |
| Auth | Basic (`-u KEY:`) documented; API overview also cites Bearer | `abe7140b` + endpoints intro |
| Example model IDs | `composer-2`, `composer-2.5`, `claude-4.6-sonnet-thinking` (in examples) | `abe7140b` |

---

## Verified SDK surface (Python)

| Item | Detail | Nia doc ID |
|------|--------|------------|
| Imports | `from cursor_sdk import AsyncClient, LocalAgentOptions, Agent` | `71741e4c` |
| Async pattern | `async with await AsyncClient.launch_bridge(workspace=…) as client` | `71741e4c` |
| Model string | `model="composer-2.5"` in `agents.create()` | `71741e4c` |
| Stream | `async for message in run.messages()`; types `assistant`, `thinking`, `tool_call` | `71741e4c` |
| Modes | `mode="plan"` / `SendOptions(mode="agent")` | `71741e4c` |
| Keys not supported | Team **Admin** API keys | `71741e4c` |
| Billing note | SDK usage appears under SDK tag in team dashboard | `71741e4c` |

---

## Verified Odysseus integration points (repo)

| Item | Location | Lines (approx) |
|------|----------|----------------|
| Chat SSE contract | `src/llm_core.py` `stream_llm` docstring | 604–615 |
| Chat mode entry | `routes/chat_routes.py` `stream_llm_with_fallback`, `tools=None` | 693–710 |
| Agent mode entry | `routes/chat_routes.py` `stream_agent_loop` | 784–807 |
| Agent SSE contract | `src/agent_loop.py` `stream_agent_loop` docstring | 1237–1245 |
| Model endpoint schema | `core/database.py` `ModelEndpoint` | 311–332 |
| Endpoint CRUD | `routes/model_routes.py` `create_model_endpoint` | 808–888 |
| Session DB `mode` | `core/database.py` `Session.mode` | 109 |
| opencode | README/ACK only; **no** `src/` usage | grep |

---

## Code snippets — accuracy checklist

### Snippet 1: PyPI install (use in plans/PR)

```bash
pip install "cursor-sdk>=0.1.6"
```

✅ Matches PyPI latest as of 2026-06-01.

### Snippet 2: List models (REST)

```bash
curl -sS -u "$CURSOR_API_KEY:" https://api.cursor.com/v1/models
```

✅ Matches Nia `abe7140b` (Basic auth example). Bearer also valid per API overview reference in endpoints doc.

### Snippet 3: Async local agent (SDK)

```python
from cursor_sdk import AsyncClient, LocalAgentOptions

async with await AsyncClient.launch_bridge(workspace=os.getcwd()) as client:
    async with await client.agents.create(
        model="composer-2.5",
        api_key=api_key,
        local=LocalAgentOptions(cwd=os.getcwd()),
    ) as agent:
        run = await agent.send("Hello")
        print(await run.text())
```

✅ Matches Nia `71741e4c` (structure and `await` on context managers).

### Snippet 4: Odysseus chat delta (target output)

```python
yield f'data: {json.dumps({"delta": text})}\n\n'
```

✅ Matches `stream_llm` contract in `src/llm_core.py`.

### Snippet 5: Odysseus tool_start (agent UI)

```python
yield f'data: {json.dumps({"type": "tool_start", "tool": name, "command": cmd})}\n\n'
```

✅ Matches `agent_loop` / `static/js/chat.js` expectations.

---

## Critical warnings (do not skip)

1. **Not OpenAI-compatible** — Do not register Cursor as a normal `base_url` without `provider=cursor` adapter.
2. **409 agent_busy** — One active run per Cursor agent; serialize user sends per session.
3. **410 stream_expired** — Poll `GET` run for final `result` if SSE dies.
4. **Tool payload instability** — Cursor docs: tool `args`/`result` schemas can change; parse defensively.
5. **Bridge required for local** — `launch_bridge` must run on the Odysseus host (Docker implications).
6. **Plan B tool conflict** — Do not run `stream_agent_loop` and Cursor tools together.
7. **API beta** — Pin SDK; expect Cloud Agents v1 changes.
8. **Admin API keys** — Reject unsupported key types with clear UI copy.
9. **BYOK meaning** — User supplies Cursor key; not direct OpenAI/Anthropic BYOK.
10. **Metrics** — Token usage may be missing; Odysseus chat path already estimates usage when absent.

---

## Nia sources indexed for this work

| Source ID | URL | Status |
|-----------|-----|--------|
| `5c39f490-db62-4a02-a6df-8db343f8b597` | `lawmight/odysseus` @ `main` | indexed (repo) |
| `abe7140b-c0c5-4e3b-899c-04826a0d02a5` | https://cursor.com/docs/cloud-agent/api/endpoints.md | completed |
| `71741e4c-d188-415c-b114-0c6a5b656526` | https://cursor.com/docs/sdk/python.md | completed |
| `a064b4a5-31f7-456a-aae3-d0ceabd712cf` | https://cursor.com/docs/api.md | processing at write time |

Full SDK × Odysseus mapping: [cursor-sdk-capability-matrix.md](./cursor-sdk-capability-matrix.md).

Re-query Nia before implementation if `api.md` indexing completed (for rate limits and auth edge cases).

---

## Integration status @ `main` (2026-06-03)

| Item | Status |
|------|--------|
| Plan A/C/C+ Chat | Shipped |
| Plan B Phase 1 (`stream_cursor_agent_loop`) | Shipped ([#17](https://github.com/lawmight/odysseus/pull/17)) |
| Agent + Cursor endpoint | Agent mode uses Cursor SDK engine; tool events map to `tool_start` / `tool_output` |
| Compare / Research + Cursor | Still excluded (utility resolver / mode guards) |

Pre–Plan B gate (`0696a03`, Agent blocked): archival — see [docs/plans/README.md](./README.md#post-plan-b-phase-1-current).

---

## Suggested handoff prompt for another agent

```
Continue Cursor integration on main per docs/plans/README.md.
Plan A/C/C+ and Plan B Phase 1 are shipped; next work is Plan B Phase 2–4
(context injection, MCP bridge, cloud) in docs/plans/cursor-agent-tab-integration-plan.md.
Use cursor-sdk>=0.1.6 (requirements-cursor.txt). Follow this verification sheet for API contracts.
```
