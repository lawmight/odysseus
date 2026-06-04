# Plan C+: Cursor useful tools in Chat

**Status:** Shipped (generateImage v1)  
**Target repo:** Odysseus (self-hosted AI workspace)  
**Related:** [cursor-plan-c-chat-byok-polished.md](./cursor-plan-c-chat-byok-polished.md) (shipped), [cursor-agent-tab-integration-plan.md](./cursor-agent-tab-integration-plan.md) (Plan B — deferred), [cursor-merge-and-ship-plan.md](./cursor-merge-and-ship-plan.md) §6  
**Branch from:** `main` after `3a1b985`

---

## 1. Goal

Surface **Cursor-native tool output** in Odysseus **Chat mode** without full Plan B (Agent tab engine). First target: **`generateImage`** — when the Cursor SDK emits a `tool_call` with that name, show the generated image in the existing chat bubble UI.

Success looks like:

1. User asks for an image in Chat on a Cursor endpoint.
2. Odysseus streams tool progress (optional) and renders the result as an **`image_url`** SSE event (same path as other vision/image bubbles in `static/js/chat.js`).
3. Generated assets are served from Odysseus uploads/gallery (or a documented bridge path), not raw filesystem paths in the browser.
4. Agent mode + Cursor was blocked at Plan C+ ship time; Plan B Phase 1 later added Agent support (this plan remains Chat-focused).
5. Session reload shows image bubbles via `metadata.tool_events` (see [cursor-plan-c-plus-polish.md](./cursor-plan-c-plus-polish.md)).

---

## 2. Non-goals

| Item | Plan |
|------|------|
| Full Agent tab Cursor engine | Plan B |
| Cloud Agents API (repos, PRs) | Out of scope |
| Every Cursor IDE tool | Policy per §4 |
| Compare / Research / utility on Cursor | Excluded by design |

---

## 3. Implementation sketch

### 3.1 Adapter (`src/providers/cursor_adapter.py`)

In `stream_cursor_chat`, handle SDK events:

- `tool_call` start → optional SSE `tool_start` (if Chat UI supports it for Cursor).
- `tool_call` complete for `generateImage` → resolve asset path from bridge/SDK payload.
- Emit SSE compatible with existing chat.js handlers: `tool_output` and/or `image_url`.

See capability matrix row **`tool.generateImage`** in [cursor-sdk-capability-matrix.md](./cursor-sdk-capability-matrix.md).

Reference: Cursor SDK already emits `tool_call` with `name: "generateImage"` on image-gen prompts; Plan A/C adapter currently ignores `tool_call` in Chat.

### 3.2 Asset serving

- Copy or symlink generated file into Odysseus uploads/gallery path.
- Return a URL the frontend can load (same pattern as user attachments and gallery images).
- Do not expose arbitrary local paths to the client.

### 3.3 Frontend

- Reuse existing `image_url` bubble rendering in Chat.
- No new Agent-tab tool cards required for v1.

### 3.4 Tests

- Unit: mock SDK `tool_call` stream → assert SSE shape includes `image_url` or `tool_output`.
- Regression: Compare/Research still skip Cursor endpoints (Agent uses Cursor engine since Plan B Phase 1).

---

## 4. Policy: which tools in Chat vs Plan B

| Tool / behavior | Chat (C+) | Agent (Plan B, shipped Phase 1) |
|-----------------|-----------|----------------|
| `generateImage` | **Yes** (v1) | Generic tool card today; gallery parity tracked as backlog B2a (decision D1) |
| Shell / file edit / MCP cards | No | **Yes** — full Cursor tools via `stream_cursor_agent_loop` |
| Arbitrary `tool_call` passthrough | No — allowlist | **Yes** — all tools mapped to `tool_start` / `tool_output` |

Start with an **allowlist** (`generateImage` only). Expand only with explicit product decision.

---

## 5. Handoff prompt

```
Implement Cursor useful tools (generateImage first) per docs/plans/cursor-useful-tools-plan.md.
Branch from main.
```

---

## 6. Verification checklist

| Check | How |
|-------|-----|
| Image gen in Chat | Cursor endpoint → prompt “generate a simple red circle PNG” → image bubble |
| No path leak | Response URLs are under Odysseus uploads/gallery, not `file://` |
| Mode guards | Compare/Research + Cursor → skipped; Agent + Cursor → streams via SDK |
| Tests | `pytest tests/test_cursor_plan_c.py tests/test_cursor_adapter.py -q` + new tool tests |
