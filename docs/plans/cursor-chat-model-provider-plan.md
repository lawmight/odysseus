# Plan A: Cursor as Chat Model Provider (Odysseus)

**Status:** Shipped on `main` @ `3a1b985` (PR #2, 2026-06-02)  
**Target repo:** Odysseus (self-hosted AI workspace)  
**Verified against:** Odysseus workspace `@ workspace` (2026-06-01), Cursor docs via Nia (`abe7140b`, `71741e4c`), PyPI `cursor-sdk==0.1.6`

---

## 1. Goal

Let admins add a **Cursor** endpoint in **Settings → Model Endpoints** (BYO `CURSOR_API_KEY`), pick Cursor models (e.g. `composer-2.5`) in the **Chat** tab (`chat_mode == "chat"`), and stream replies through the existing Odysseus UI—without pretending Cursor is OpenAI `/v1/chat/completions`.

**Out of scope for v1:** Cloud Agents with repo/PR workflows, replacing Odysseus Agent tab, Cookbook auto-register.

---

## 2. Why this is an adapter (not a URL preset)

| Odysseus today | Cursor |
|----------------|--------|
| HTTP POST `…/chat/completions` with `messages[]` | Durable **Agent** + per-turn **Run** |
| Mostly stateless per request | `agent.send()` retains conversation |
| `stream_llm()` in `src/llm_core.py` | `run.messages()` / REST SSE `/v1/agents/{id}/runs/{runId}/stream` |
| Chat mode: `tools=None` | Agent may still emit `tool_call` events internally |

**Do not** set `base_url = https://api.cursor.com/v1` and reuse `_probe_endpoint()` against `/models` on a generic OpenAI client without a Cursor-specific branch—it will not speak the same protocol as local vLLM/Ollama.

---

## 3. SDK and dependency choice

| Item | Verified value |
|------|----------------|
| Package | `cursor-sdk` on PyPI |
| Latest version (checked 2026-06-01) | **0.1.6** |
| Install (official docs) | `uv pip install cursor-sdk` or `pip install cursor-sdk>=0.1.6` |
| Odysseus runtime | Python **3.11+** (README); dev VM had 3.12.3 |
| Recommended integration | **Python SDK `AsyncClient`** (docs: “recommended for servers, bots, and concurrent agent orchestration”) |
| TypeScript SDK | **Not** recommended for Odysseus (would require a sidecar) |

**Optional extra in `requirements.txt`:**

```text
# requirements-cursor.txt (or extras_require["cursor"])
cursor-sdk>=0.1.6
```

Import guard pattern:

```python
try:
    from cursor_sdk import AsyncClient, LocalAgentOptions
    CURSOR_SDK_AVAILABLE = True
except ImportError:
    CURSOR_SDK_AVAILABLE = False
```

---

## 4. Authentication (BYOK)

| Source | Detail |
|--------|--------|
| Env var | `CURSOR_API_KEY` (SDK default) |
| Odysseus storage | Existing `ModelEndpoint.api_key` (`EncryptedText` in `core/database.py`) |
| Key types (SDK docs) | **User API key** (Dashboard → API Keys / Integrations); **Service account** (Team settings) |
| **Not supported** | Team **Admin** API keys (explicit in Python + TS SDK docs) |
| REST auth | Cloud Agents API v1 accepts **Basic** (`curl -u YOUR_API_KEY:`) and **Bearer** (per API overview linked from endpoints doc) |

**User-facing copy:** “Bring your Cursor API key; usage bills to your Cursor account (same pools as IDE / Cloud Agents).”

---

## 5. Cursor APIs to use

### 5.1 Model discovery

```http
GET https://api.cursor.com/v1/models
Authorization: Basic <api_key>   # or Bearer
```

Response: `items[].id`, `displayName`, `parameters`, `variants` (Nia-verified from Cloud Agents endpoints doc).

SDK equivalent:

```python
# Inside async client after launch_bridge or connect
models = await client.models.list()
```

### 5.2 Runtime modes for Chat v1

| Mode | Use in v1? | Notes |
|------|------------|-------|
| **Local** (`LocalAgentOptions(cwd=…)`) | **Yes (primary)** | Requires `AsyncClient.launch_bridge(workspace=…)` on Odysseus host |
| **Cloud** (`CloudAgentOptions(repos=[…])`) | **No (defer)** | Needs repo URL, branch, billing; poor fit for generic chat |

### 5.3 Local agent flow (canonical)

```python
import os
from cursor_sdk import AsyncClient, LocalAgentOptions

async with await AsyncClient.launch_bridge(workspace=os.getcwd()) as client:
    async with await client.agents.create(
        model="composer-2.5",          # from GET /v1/models
        api_key=api_key_from_endpoint,
        local=LocalAgentOptions(cwd=workspace_path),
    ) as agent:
        run = await agent.send(prompt_text)
        async for message in run.messages():
            if message.type == "assistant":
                for block in message.message.content:
                    if block.type == "text":
                        # map to Odysseus SSE (see §7)
                        ...
```

**Official quick-start model IDs (docs):** `composer-2.5`, `composer-2` (list may include `claude-*-thinking`, etc.—always fetch live via `/v1/models`).

### 5.4 Session ↔ Cursor agent mapping

- One Odysseus **session** → one Cursor `agent_id` (`agent-…` local, `bc-…` cloud).
- Store mapping (new column or JSON settings):
  - **Option A:** `sessions.cursor_agent_id` (migration)
  - **Option B:** `settings["cursor_agents"][session_id] = agent_id`
- First chat message: `agents.create()`; follow-ups: `Agent.resume(agent_id)` or keep handle in process cache keyed by session (cache must survive only within worker—prefer DB).

### 5.5 Concurrency pitfalls (Nia-verified)

| Error | When | Mitigation |
|-------|------|------------|
| `409 agent_busy` | Second `POST …/runs` while run is `CREATING` or `RUNNING` | Serialize runs per `agent_id`; await `run.wait()` before next user message |
| `410 stream_expired` | SSE retention elapsed | Fall back to `GET …/runs/{runId}` for terminal `result` |
| Stream consumable once | `run.messages()` shares one iterator | Do not double-consume; use `run.iter_text()` OR `run.messages()`, not both |

---

## 6. Odysseus integration map

### 6.1 Data model

Extend `ModelEndpoint` (`core/database.py`):

```python
# New column (migration)
provider = Column(String, nullable=True, default="openai_compat")
# Values: "openai_compat" | "anthropic" | "cursor"

# Optional JSON for Cursor-only config (workspace path, runtime)
provider_config = Column(Text, nullable=True)  # JSON: {"runtime":"local","cwd":"/path"}
```

**Endpoint convention for UI preset “Cursor (local)”:**

- `base_url`: sentinel `cursor://local` (not probed as HTTP)
- `api_key`: Cursor API key
- `provider_config`: `{"cwd": "/workspace"}` or admin-configured path

### 6.2 Files to touch

| File | Change |
|------|--------|
| `core/database.py` | Migration: `provider`, `provider_config`; optional `sessions.cursor_agent_id` |
| `src/providers/cursor_adapter.py` | **New:** list models, stream chat, error formatting |
| `src/llm_core.py` | Early branch in `stream_llm()` if URL/sentinel or endpoint provider is `cursor` |
| `src/endpoint_resolver.py` | `resolve_endpoint*`: pass through cursor sentinel; do not call `build_chat_url()` for cursor |
| `routes/model_routes.py` | Preset, probe skip, model list via Cursor API |
| `routes/chat_routes.py` | Chat branch already calls `stream_llm_with_fallback`—no change if adapter is inside `stream_llm` |
| `static/` (admin UI) | “Add Cursor endpoint” template, workspace path field |
| `requirements.txt` or extra | `cursor-sdk>=0.1.6` optional |
| `README.md` | Bridge install, Cursor key link, limitations |

### 6.3 Chat path (existing)

```693:710:routes/chat_routes.py
            elif chat_mode == "chat":
                ...
                    async for chunk in stream_llm_with_fallback(
                        _chat_candidates,
                        messages,
                        ...
                        tools=None,
                    ):
```

Adapter must implement the **same SSE contract** as `stream_llm()`:

```604:615:src/llm_core.py
    Yields SSE chunks:
      - data: {"delta": "text"}           — text content
      - data: {"type": "tool_calls", ...}  — accumulated native tool calls (before DONE)
      - event: error                       — errors
      - data: [DONE]                       — end of stream
```

---

## 7. Stream translation spec

### 7.1 Cursor → Odysseus (Chat mode)

| Cursor event (`run.messages()` or REST SSE) | Odysseus output |
|---------------------------------------------|-----------------|
| `assistant` text blocks | `data: {"delta": "<text>"}\n\n` |
| `thinking` | `data: {"delta": "…", "thinking": true}\n\n` (frontend already handles `thinking` in some paths—see `chat_routes.py` compare/research) |
| `tool_call` | **Suppress or summarize** in chat mode (user did not ask for tools). Optional: single line `data: {"type": "status", "message": "…"}` if needed |
| Terminal / `run.wait()` | `data: {"type": "usage", "data": {...}}\n\n` if duration available; else estimated metrics (chat path already estimates if no usage) |
| Error | `event: error\ndata: {"status": 401, "text": "Cursor rejected the API key…"}\n\n` (mirror `_format_upstream_error` tone) |
| End | `data: [DONE]\n\n` |

Use existing `clean_thinking_for_save()` when persisting assistant messages.

### 7.2 Prompt construction from Odysseus history

Odysseus `messages` are OpenAI-shaped (`role`, `content`). For Cursor **chat-only**:

1. Merge system messages into a preamble (same as `stream_llm` does).
2. Serialize prior user/assistant turns into markdown transcript **or** rely on Cursor agent memory after first `send()` (preferred after agent created).
3. Last user turn → primary `agent.send()` text; attach images via `UserMessage` / `images[]` if session has vision attachments (SDK supports base64 images).

**Do not** pass Odysseus tool definitions to Cursor in chat mode.

---

## 8. Model endpoint admin UX

1. Admin → Add endpoint → **Provider: Cursor (local)**.
2. Fields: Name, API key, Workspace directory (`cwd`, default `os.getcwd()` or configurable data dir).
3. On save: `GET /v1/models` with key → populate `cached_models` JSON on `ModelEndpoint`.
4. Skip HTTP probe (`_probe_endpoint`) for `cursor://local`.
5. Model picker shows `displayName` but stores `id` (e.g. `composer-2.5`).

---

## 9. Implementation phases

### Phase 1 — Backend adapter (MVP)

- [ ] Migration + `provider` column
- [ ] `cursor_adapter.py`: `list_models(api_key)`, `stream_cursor_chat(session_id, model, messages, api_key, cwd)`
- [ ] Bridge lifecycle: one `AsyncClient` per process (or per worker) with `launch_bridge(workspace=cwd)`
- [ ] Hook in `stream_llm()` when `url.startswith("cursor://")` or resolved provider is `cursor`
- [ ] Session → `agent_id` persistence
- [ ] Tests: mock SDK or recorded fixtures; auth error mapping

### Phase 2 — Admin UI + docs

- [ ] Preset in model settings JS
- [ ] README section: bridge, key dashboard link, Docker note (bridge inside container)

### Phase 3 — Hardening

- [ ] Cancel: map Odysseus stop button → `run.cancel()` / `POST …/cancel`
- [ ] Reconnect partial streams (`410` handling)
- [ ] Rate limit messaging from Cursor API

---

## 10. Things to be careful about

1. **Bridge on server:** Local Cursor agents need the SDK bridge running where Odysseus runs (Docker image must include Cursor CLI/bridge or document host-side bridge + `CursorClient.connect(base_url=…)`).
2. **Not BYOK to OpenAI/Anthropic directly:** Cursor key bills Cursor; underlying model routing is Cursor’s.
3. **409 agent_busy:** Must not parallelize two sends on same `agent_id` (double-click send, tab race).
4. **Tool call schema unstable:** SDK docs warn `args`/`result` on tool events are not stable—do not deeply parse in chat mode.
5. **Team Admin keys:** Reject early with clear error if detected.
6. **API beta:** Cloud Agents API v1 is **public beta**—pin SDK version, expect breaking changes.
7. **Metrics:** Cursor may not return OpenAI-style `usage`; chat route already estimates tokens when missing—document as “estimated”.
8. **Security:** `cwd` must be constrained to allowed paths (no arbitrary admin path → path traversal on host).
9. **Chat adapter stays Chat-only**—the Agent tab is routed through the separate `stream_cursor_agent_loop` engine, not this chat adapter (Plan B Phase 1 shipped; see [Plan B v2](./cursor-agent-tab-integration-plan.md)).

---

## 11. Testing checklist

- [ ] Add Cursor endpoint with valid key → models list non-empty
- [ ] Chat session: first message creates agent, second message resumes context
- [ ] Streaming deltas appear in UI; `[DONE]` saved to DB
- [ ] Invalid key → friendly error (not raw JSON)
- [ ] Missing bridge → actionable setup error
- [ ] Stop generation mid-stream → partial save (existing `clean_thinking_for_save` path)
- [ ] Fallback chain: Cursor endpoint as non-primary in `stream_llm_with_fallback` still works

---

## 12. PR packaging (upstream Odysseus)

- Title: `feat(models): Cursor SDK adapter for Chat mode (local runtime)`
- Optional dependency: `pip install -r requirements-cursor.txt`
- ACKNOWLEDGMENTS: Cursor SDK license note if required
- Keep diff isolated: no changes to `agent_loop.py` in Plan A

---

## 13. Reference snippets (verified doc shapes)

**Install:**

```bash
pip install "cursor-sdk>=0.1.6"
```

**List models (REST):**

```bash
curl -sS -u "$CURSOR_API_KEY:" https://api.cursor.com/v1/models
```

**Async stream (SDK):**

```python
async for message in run.messages():
    if message.type == "assistant":
        for block in message.message.content:
            if block.type == "text":
                yield f'data: {json.dumps({"delta": block.text})}\n\n'
```

**Cloud SSE event types (if implementing REST fallback):** `status`, `assistant`, `thinking`, `tool_call`, `result`, `done`, `error` (Nia-verified from endpoints doc).

---

## 14. Nia verification log

| Claim | Source |
|-------|--------|
| `GET /v1/models` fields | Nia → `abe7140b` (endpoints.md) |
| `409 agent_busy`, SSE events, `410 stream_expired` | Nia → `abe7140b` |
| `cursor-sdk` install, `AsyncClient`, `composer-2.5` | Nia → `71741e4c` (python.md) |
| PyPI version **0.1.6** | Local `pip index versions cursor-sdk` |
| Odysseus `stream_llm` SSE contract | Repo `src/llm_core.py:604-615` |
| Chat uses `stream_llm_with_fallback`, `tools=None` | Repo `routes/chat_routes.py:693-710` |
