# Plan C+ polish — follow-up work

**Status:** Shipped (PRs #13–#15 or branch stack `cursor/plan-c-plus-polish-pr*-4811`)  
**Prerequisite:** Plan C+ v1 shipped on `main` ([cursor-useful-tools-plan.md](./cursor-useful-tools-plan.md), PR #12 + `6b3fcc0` path fix)  
**Non-goals:** Plan B (Agent tab), expanding Cursor tool allowlist without product sign-off

---

## 1. Why this plan exists

Plan C+ v1 delivers live `generateImage` in Chat (SSE + gallery URL). Optional polish closes UX and maintainability gaps without changing scope to Plan B.

| Gap | User impact | Engineering impact |
|-----|-------------|-------------------|
| No `tool_events` on Cursor Chat save | Image bubble missing after reload | Diverges from native `do_generate_image` path |
| Duplicate gallery-save logic | None visible | 4 call sites; drift on metadata fields |
| Source-grep / weak route tests | Regressions slip through | False confidence on forwarding |
| Adapter still owns publish orchestration | None visible | Thermo review: layer bleed |

---

## 2. Recommended PR stack (small, ordered)

Ship as **3 stacked PRs** (or one if you prefer a single review). Each PR is landable alone.

```
main
 └── PR-1  tool_events persistence (highest user value)
      └── PR-2  canonical gallery helper migration
           └── PR-3  tests + docs + small adapter cleanup
```

---

## 3. PR-1 — Persist `tool_events` for Cursor Chat image turns

### Goal

After refresh, Cursor-generated images render from session history like the built-in `do_generate_image` shortcut path.

### Current behavior

- **Native image shortcut** (`chat_routes.py` ~819–825): saves `metadata.tool_events` with `image_url`, `image_id`, etc.
- **Cursor Chat stream** (~870–933): forwards `tool_start` / `tool_output` live but `save_assistant_response(...)` is called **without** `tool_events`.

Frontend already supports reload: `static/js/chatRenderer.js` reads `metadata.tool_events` and builds image bubbles.

### Implementation sketch

1. In the `chat_mode == "chat"` loop, accumulate tool events while streaming:
   - On forwarded `tool_output` with `image_url`, append one event dict matching native shape:
     - `round`, `tool`, `command`, `output`, `exit_code`, `image_url`, `image_id`, `image_prompt`, `image_model`, …
   - Optionally record `tool_start` only if needed for history UI (check `chatRenderer.js` — likely output-only is enough).
2. On `[DONE]`, pass `tool_events=captured` into `save_assistant_response` when non-empty.
3. Do **not** duplicate tool rows into `full_response` text unless product wants a caption; image bubble comes from metadata.

### Files

| File | Change |
|------|--------|
| `routes/chat_routes.py` | Collect events; pass to `save_assistant_response` |
| `tests/test_cursor_chat_tool_events.py` | Mock stream -> assert saved session metadata |

### Acceptance

| Check | How |
|-------|-----|
| Live reload | Cursor Chat → generate image → hard refresh → bubble still visible |
| Incognito | No `tool_events` persisted when incognito |
| Native path | Existing `do_generate_image` save unchanged (regression test) |

### Risk

Low. Same metadata contract as existing image shortcut.

---

## 4. PR-2 — Canonical `save_generated_image_bytes` migration

### Goal

One gallery write path; consistent `GalleryImage` fields (`size`, `quality`, `file_size`, `owner`).

### Call sites today

| Location | Status |
|----------|--------|
| `routes/gallery_helpers.py` | **Canonical** (`save_generated_image_bytes`) |
| `src/providers/cursor_adapter.py` | Uses canonical |
| `src/ai_interaction.py` | Inline `_save_to_gallery` (×2 branches) |
| `mcp_servers/image_gen_server.py` | Inline mkdir + DB insert |

### Implementation sketch

1. Extend `save_generated_image_bytes` only if needed (e.g. `file_size`, `quality` already optional).
2. Replace `ai_interaction` inner `_save_to_gallery` with helper import; preserve return shape callers expect (`image_url`, `image_id`, …).
3. Replace `image_gen_server` block similarly.
4. **Do not** move Cursor SSE assembly into `chat_routes` in this PR unless trivial; adapter can keep `cursor_tool_call_chunks` if it only calls the helper.

### Files

| File | Change |
|------|--------|
| `routes/gallery_helpers.py` | Minor API tweaks if needed |
| `src/ai_interaction.py` | Dedupe |
| `mcp_servers/image_gen_server.py` | Dedupe |
| Tests touching gallery rows | Update mocks if any |

### Acceptance

| Check | How |
|-------|-----|
| Cursor image gen | Still works (PR-1 + adapter) |
| Built-in / MCP image gen | Same URLs and gallery rows |
| pytest | `tests/test_cursor_chat_tool_events.py`, any gallery tests |

### Risk

Medium (touch production image paths). Run focused tests + one manual MCP/builtin gen if configured.

---

## 5. PR-3 — Tests, docs, adapter cleanup

### Goal

Lock behavior with real assertions; align docs; optional thin adapter.

### 5.1 Behavioral chat-route test

Replace or supplement `inspect.getsource` tests in `test_cursor_chat_tool_events.py`:

- Drive `chat_stream` generator with a monkeypatched `stream_llm_with_fallback` that yields synthetic `tool_start` / `tool_output` chunks.
- Assert yielded SSE includes `image_url`.
- Optional: assert `save_assistant_response` received `tool_events` (after PR-1).

### 5.2 Docs

| Doc | Update |
|-----|--------|
| `docs/plans/cursor-useful-tools-plan.md` | Link polish plan; note reload persistence when PR-1 lands |
| `docs/plans/README.md` | Row for C+ polish |
| `docs/plans/cursor-sdk-capability-matrix.md` | Footnote on `tool.generateImage` persistence if applicable |

### 5.3 Optional adapter cleanup (defer if noisy)

- Pass `owner` from `stream_cursor_chat` / `cursor_meta` into `publish_cursor_generated_image`.
- Add debug log (INFO) when SDK result has `status != success` or missing `value.filePath` (no secrets).

### Acceptance

| Check | How |
|-------|-----|
| No source-grep-only tests for critical paths | Grep `getsource` in Cursor chat tests |
| `pytest tests/test_cursor_chat_tool_events.py tests/test_cursor_adapter.py -q` | Green |

---

## 6. Explicitly out of scope (unless product opens)

| Item | Route |
|------|--------|
| More Cursor tools in Chat (`run_terminal_cmd`, etc.) | Plan B or new allowlist ADR |
| Move all publish logic to `chat_routes` | Larger refactor; not required for polish |
| Plan B Agent tab | [cursor-agent-tab-integration-plan.md](./cursor-agent-tab-integration-plan.md) |
| Cloud Agents API / PR automation | Matrix `cloud.*` rows |

---

## 7. Verification matrix (full polish done)

| Scenario | Expected |
|----------|----------|
| Cursor Chat image | Live bubble + `GENERATE_IMAGE` success |
| Reload session | Image bubble from `tool_events` |
| Gallery | Row under `data/generated_images/` + `/api/generated-image/…` |
| Agent + Cursor | Uses the Cursor engine (`stream_cursor_agent_loop`, Plan B Phase 1) — not blocked |
| Builtin image shortcut | Unchanged |
| pytest | `test_cursor_chat_tool_events.py`, `test_cursor_adapter.py`, route test |

---

## 8. Handoff prompt

```
Implement Plan C+ polish per docs/plans/cursor-plan-c-plus-polish.md.
Start with PR-1 (tool_events on Cursor Chat save), then PR-2 gallery dedupe, then PR-3 tests/docs.
Branch from main; one PR per slice preferred.
```

---

## 9. Effort shape (technical, not calendar)

| PR | Touch surface | Invasiveness |
|----|---------------|--------------|
| PR-1 | `chat_routes` loop + one test | Small |
| PR-2 | `ai_interaction`, `image_gen_server`, helper | Medium |
| PR-3 | Tests + docs only (+ optional logs) | Small |

**Suggested default:** ship **PR-1 only** if you want one quick win; stack PR-2/3 when you have review bandwidth.
