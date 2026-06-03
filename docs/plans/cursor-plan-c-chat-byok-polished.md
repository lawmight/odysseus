# Plan C: Cursor Chat BYOK — polished parity with other providers

**Status:** Shipped on `main` @ `3a1b985` (PR #2, 2026-06-02)  
**Target repo:** Odysseus (self-hosted AI workspace)  
**Related:** Plan A (adapter design), Plan B Phase 1 (Agent tab — [shipped](./README.md)), Plan C+ ([cursor-useful-tools-plan.md](./cursor-useful-tools-plan.md)), [CURSOR_INTEGRATION_VERIFICATION.md](./CURSOR_INTEGRATION_VERIFICATION.md)  
**Implementation reference:** merged via PR #2 → `main` (`3a1b985`)

---

## 1. Real goal (what we are actually building)

Ship a **Bring Your Own Cursor API Key** integration that feels **as polished as existing BYOK providers** (OpenAI-compat URLs, Anthropic, OpenRouter, etc.) for **Chat mode only**.

Success looks like:

1. An admin adds **Cursor (local)** under **Settings → Model Endpoints**, pastes a Cursor API key, picks a workspace directory, and selects a model (e.g. `composer-2.5`).
2. Any user starts a **Chat** session on that endpoint and gets streaming replies in the normal Odysseus UI (SSE `delta`, thinking, metrics, save to history, fallback chain).
3. Attachments behave like other vision-capable chats: **images reach the model** via the SDK (`UserMessage` / `SDKImage`), not only as stripped text.
4. Multi-turn chat **feels coherent** because we use the SDK’s **durable Agent** (`create` once, `resume` + `send` on follow-ups), not a new agent and full transcript replay every turn.
5. The change is **upstream-ready**: optional dependency, clear limitations, no broken Agent-tab experience.

**Explicit non-goals for Plan C:**

- Replacing Odysseus **Agent** mode with Cursor (that is Plan B).
- Cloud Agents with repo/PR workflows.
- Cookbook auto-register or “Cursor as HTTP `base_url`” without an adapter.
- Feature parity with Cursor IDE (MCP admin UI, cloud VMs, etc.) inside Odysseus v1.

---

## 2. How Plan A and PR #2 relate to Plan C

### Plan A (design doc)

Plan A correctly identified:

- Cursor is **not** OpenAI `/v1/chat/completions`; use `provider=cursor` + `cursor_adapter.py`.
- Hook `stream_llm()` for `cursor://local`.
- Optional `cursor-sdk>=0.1.6`, BYOK key on `ModelEndpoint`, model list via `GET /v1/models`.

Plan A also listed **Phase 3 hardening** and **session `agent_id` persistence** as equal priorities. Plan C **keeps** persistence, images, stop/cancel, and admin polish as **in-scope**; it **defers** REST SSE fallback, cloud runtime, and anything that only serves Plan B.

### PR #2 (what we tried)

| Area | PR #2 | Plan C target |
|------|-------|----------------|
| Adapter + `cursor://local` + admin preset | Done | Keep |
| `stream_llm()` branch | Done | Keep |
| Encrypted API key, model probe via `/v1/models` | Done | Keep |
| `supports_tools=false` on Cursor endpoints | Done | Keep + **enforce Chat-only in UX** |
| New `agents.create()` every turn + markdown transcript | Done | **Replace** with session `cursor_agent_id` + `Agent.resume()` |
| Images / `SDKImage` | Missing | **Add** (see §5) |
| `run.cancel()` for Stop | Missing | **Add** |
| `displayName` in picker | Missing | **Add** |
| BYOK help copy in admin | Minimal | **Add** |
| Agent tab with Cursor endpoint | Misleading (tools ignored) | **Block or warn** (see §6) |
| Utility / vision / compare using Cursor | Unrestricted | **Hide** from those pickers (see §6) |
| Cloud Agent bootstrap scripts in same PR | Extra | **Split** optional follow-up PR |

Plan C is **not** a rewrite: it is the **acceptance bar** for finishing PR #2 (or a follow-up PR on the same adapter).

---

## 3. Parity bar: “as good as other BYOK providers” (Chat only)

Compare against **default BYOK** (HTTP OpenAI-compat + Anthropic), not against Cursor IDE.

| User expectation | Default BYOK | Plan C requirement |
|------------------|--------------|-------------------|
| Add endpoint + API key in admin | Yes | Yes |
| Model list after save | `GET /models` (+ probe optional) | `GET https://api.cursor.com/v1/models` |
| Pick model in Chat | Yes | Yes; show **`displayName`**, store **`id`** |
| Stream text in UI | `stream_llm` SSE | Same SSE contract via adapter |
| Invalid key → readable error | `_format_upstream_error` tone | Adapter errors with same tone |
| Fallback model chain (Chat) | `stream_llm_with_fallback` | Must keep working through cursor branch |
| Attach image in Chat | `image_url` or vision sidecar | **`UserMessage` + `SDKImage`** on last user turn |
| Multi-turn context | Full `messages[]` each HTTP call | **`Agent.resume` + single new user message** (plus optional system/RAG prefix) |
| Stop / disconnect partial save | Chat path saves partial | **`run.cancel()`** + existing partial-save path |
| Works without extra install | Yes | **Optional** `requirements-cursor.txt`; clear error if missing |
| Same endpoint in Agent tab | Yes (tools) | **No** — Cursor not offered for Agent (§6) |
| Same endpoint for utility email summarize | Often | **No** — hide from non-Chat resolvers |

**Bridge / Docker:** Other providers only need HTTP. Cursor needs `cursor-sdk` **bridge on the Odysseus host** (or `CursorClient.connect` to a sidecar). Document this like a first-class requirement, not a footnote.

---

## 4. Architecture (unchanged from Plan A, refined)

```
Admin → ModelEndpoint(provider=cursor, base_url=cursor://local, api_key, provider_config.cwd)
                    ↓
Session (chat_mode=chat) → stream_llm_with_fallback → stream_llm
                    ↓
            cursor_adapter.stream_cursor_chat(...)
                    ↓
        AsyncClient.launch_bridge(workspace=cwd)
        Agent.create / Agent.resume(session.cursor_agent_id)
        run = agent.send(UserMessage(...))  # text + SDKImage[]
        async for event in run.messages(): → Odysseus SSE deltas
```

**Do not** route Agent mode through this path for v1 (see §7).

---

## 5. Implementation phases (Plan C scope)

### Phase 1 — Finish MVP parity (ship with upstream PR)

- [ ] **Session mapping:** persist `cursor_agent_id` on Odysseus session (DB column or JSON in session settings). First message: `agents.create()`. Follow-ups: `Agent.resume(id)` then `send()` only the new turn (and injected system/RAG block if needed).
- [ ] **Images:** map Odysseus `build_user_content()` / attachment paths to `UserMessage(text=..., images=[SDKImage.from_file(...)])` for the **current** user message. Reference: [Cursor Python SDK — images](https://cursor.com/docs/sdk/python#sdkimage).
- [ ] **Stream mapping:** keep `assistant` / `thinking` → SSE; ignore or single-line `tool_call` in Chat (no tool cards in Chat mode).
- [ ] **Stop:** wire `/api/chat/stop` or stream cancel to `await run.cancel()` when active run is Cursor-backed; guard terminal runs per SDK docs.
- [ ] **Chat-only guard:** if `chat_mode != "chat"` and endpoint is Cursor → clear error or auto-fallback to user’s default non-Cursor endpoint (pick one behavior and test).
- [ ] **Model metadata:** store `{id, displayName}` in `cached_models` (or parallel JSON); picker shows display name.
- [ ] **Admin copy:** BYOK billing note + link to Cursor API keys + workspace / `CURSOR_ALLOWED_WORKSPACE_ROOTS` help.
- [ ] **Tests:** resume second turn (mock SDK); image payload built from fixture path; cancel called on stop; Cursor hidden from agent resolver tests.

### Phase 2 — Polish & upstream hygiene

- [ ] **ACKNOWLEDGMENTS** entry for `cursor-sdk`.
- [ ] **README** section: Chat-only, optional install, bridge-in-Docker note, limitations vs Agent tab.
- [ ] **Rate limits / errors:** map 429 and common SDK exceptions to user-facing strings (mirror `_format_upstream_error` style).
- [ ] **Optional:** `SendOptions(local.force=True)` on send when previous run stuck (local only).
- [ ] **Split** Cloud Agent install/bootstrap from core feature PR if upstream wants a minimal diff.

### Phase 3 — Explicitly out of Plan C (was Plan A Phase 3 / REST)

- [ ] REST SSE client path + `410 stream_expired` recovery (only if SDK streaming proves insufficient).
- [ ] Cloud runtime (`CloudAgentOptions`, repos, PRs).
- [ ] Team Admin API key detection (nice-to-have early error).

---

## 6. Product rules (avoid “less good than others” traps)

1. **One sentence in UI:** “Cursor endpoints are for **Chat** only.”
2. **Model picker / session create:** do not list Cursor endpoints when mode is Agent, Compare, Research, or when resolving `utility` / `vision` / `task` unless product explicitly expands scope later.
3. **`supports_tools=false`** stays; never pass Odysseus tool schemas into `stream_cursor_chat`.
4. **Do not** implement Plan B inside the same PR as Plan C completion; see §7.

---

## 7. How to deal with Plan B (Agent tab)

Plan B remains **valid future work** but is **not part of the real goal**. This section is for maintainers and future agents.

### What Plan B is

A **second agent engine**: when `chat_mode == "agent"` and the session endpoint is `provider=cursor`, run `stream_cursor_agent_loop()` instead of `stream_agent_loop()`, mapping Cursor `tool_call` SDK events to Odysseus `tool_start` / `tool_output` / `agent_step` SSE so the existing Agent UI shows tool cards.

### Why Plan C does not include Plan B

| Issue | Explanation |
|-------|-------------|
| Different user promise | Chat BYOK = “talk to a model.” Agent = “run Odysseus tools + MCP.” |
| Double tooling | `stream_agent_loop` + Cursor tools in one turn duplicates work and breaks UX (Plan B §5). |
| PR size & review risk | Upstream reviewers will reject a PR that changes Chat + Agent + cloud bootstrap at once. |
| PR #2 lesson | Routing Cursor through `stream_llm` inside Agent mode **without** Plan B confuses users; better to **block** than half-ship. |

### Prerequisites before starting Plan B

Complete Plan C first, especially:

- Shared `cursor_adapter.py` (bridge lifecycle, auth, model list, errors).
- Session `cursor_agent_id` lifecycle (B reuses the same agent handle).
- Clear separation: `stream_cursor_chat` (Chat) vs `stream_cursor_agent_loop` (Agent) — two mappers, one bridge pool.

### How to implement Plan B later (summary)

1. Add `agent_engine` (or infer from `provider=cursor` + mode): `odysseus` | `cursor_local`.
2. In `chat_routes.py`, Agent branch: if `cursor_local` → `stream_cursor_agent_loop(...)`; **else** → existing `stream_agent_loop`.
3. **Never** call both loops in one turn.
4. Map `SDKToolUseMessage` (`status=running|completed`) → `tool_start` / `tool_output` (parse `args`/`result` defensively; schema unstable per SDK docs).
5. Inject memories/RAG/skills as **text prefix** on `send()`, not parallel Odysseus tool APIs.
6. Use `SendOptions(mode="agent")` / plan mode per product choice.
7. Hide Cursor from Compare/Research/background `stream_agent_loop` callers (Plan B §13).
8. Separate PR: `feat(agent): optional Cursor SDK engine for Agent mode` — depends on Plan C merged.

### What to do with Plan B doc until then

- Keep [cursor-agent-tab-integration-plan.md](./cursor-agent-tab-integration-plan.md) as **design reference**.
- Link from README: “Agent tab + Cursor = Plan B, not yet supported.”
- If a user selects Cursor in Agent mode before B exists, return HTTP 400 or UI toast: “Use Chat mode or pick an OpenAI-compatible endpoint for Agent.”

---

## 8. SDK facts Plan C relies on (verified)

| Topic | Detail | Source |
|-------|--------|--------|
| Package | `cursor-sdk>=0.1.6` | PyPI + [verification sheet](./CURSOR_INTEGRATION_VERIFICATION.md) |
| Images | `UserMessage`, `SDKImage.from_file`, dict `images[]` | [python.md — images](https://cursor.com/docs/sdk/python#sdkimage) |
| Context | Same `Agent`, multiple `send()` calls | [python.md — Sending messages](https://cursor.com/docs/sdk/python) |
| Resume | `Agent.resume(agent_id)` | [python.md — Resuming agents](https://cursor.com/docs/sdk/python) |
| Cancel | `run.cancel()` | [python.md — Cancelling a run](https://cursor.com/docs/sdk/python) |
| Chat SSE | `delta`, `thinking`, `[DONE]`, `event: error` | `src/llm_core.py` docstring |
| Admin keys | User + service account; not Team Admin | SDK docs |

Re-query Nia / docs before implementation if the SDK minor version bumps.

---

## 9. Testing checklist (Plan C acceptance)

- [ ] Add Cursor endpoint with valid key → models list non-empty; **display names** visible.
- [ ] Chat: first message creates agent; **second message** uses resume (no full transcript in prompt — verify via mock or log).
- [ ] Chat with **image attachment** → Cursor receives image (mock `send` payload includes `images`).
- [ ] Invalid key → friendly error (not raw JSON).
- [ ] Missing SDK / bridge → actionable setup message.
- [ ] Stop mid-stream → `cancel` invoked; partial assistant text saved.
- [ ] Fallback chain with Cursor as non-primary candidate still works.
- [x] Agent mode + Cursor endpoint → **blocked** with clear message *(Plan C era; superseded by Plan B Phase 1 — Agent now uses `stream_cursor_agent_loop`)*
- [ ] Utility resolver does not return Cursor endpoint by default.

---

## 10. Upstream PR packaging

**Title (suggested):** `feat(chat): Cursor BYOK provider with Chat parity (cursor-sdk)`

**Description bullets:**

- Optional `requirements-cursor.txt`; Chat-only Cursor endpoints.
- BYOK Cursor API key in Model Endpoints; local bridge + workspace path.
- Session-scoped agent resume, `SDKImage` attachments, stop/cancel, display names.
- Agent tab and background tasks: Cursor endpoints excluded until Plan B.

**Files (expected):** `src/providers/cursor_adapter.py`, `src/llm_core.py`, `routes/model_routes.py`, `routes/session_routes.py` (+ migration), `static` admin, `README.md`, `ACKNOWLEDGMENTS.md`, tests.

**Handoff prompt for an implementer:**

```
Implement Plan C from docs/plans/cursor-plan-c-chat-byok-polished.md.
Start from branch cursor/cursor-chat-provider-e76a if present.
Do not implement Plan B. Use cursor-sdk UserMessage/SDKImage and Agent.resume per session.
```

---

## 11. Decision log (why Plan C exists)

| Decision | Rationale |
|----------|-----------|
| Plan C supersedes A as *product* scope | A mixed MVP + hardening + agent_id without stating “polish = other BYOK in Chat.” |
| PR #2 is the codebase baseline | Avoid replanning adapter shape; close gaps. |
| Plan B deferred with explicit rules | Prevents half-integrated Agent mode and scope creep. |
| Images via SDK, not `image_url` in HTTP | Cursor API is agent/send-based; [SDKImage](https://cursor.com/docs/sdk/python#sdkimage) is canonical. |
| Chat-only enforcement | Honest parity; other providers work in Agent because they speak tools over HTTP. |

---

## 12. Nia / repo verification log

| Claim | Source |
|-------|--------|
| Plan A/B file paths | [`docs/plans/`](README.md) on `main` |
| PR #2 scope | Branch `cursor/cursor-chat-provider-e76a` |
| Odysseus Chat path | `routes/chat_routes.py` `chat_mode == "chat"` → `stream_llm_with_fallback` |
| Odysseus attachments | `src/chat_handler.py` `build_user_content` |
| SDK image API | https://cursor.com/docs/sdk/python#sdkimage |
