# Cursor integration — manual smoke (Chat + Agent)

Use this while Odysseus is running with a **Cursor (local)** endpoint and your API key configured. Goal: confidence for a full Cursor Chat + Agent integration tour (Plan B B2a-B3 follow-ups are shipped; Cloud Cursor agents remain separate).

**Environment:** Chat at `http://127.0.0.1:7000` (port-forwarded). Keep the tab **focused** during long tool runs (image gen) so SSE `tool_output` is not missed.

---

## Setup (once)

- [ ] Settings → Add Models → **Cursor (local)** → key set → badge shows **N/N models enabled** (not `0/0`)
- [ ] New chat → model picker shows **composer-2.5** (or another Cursor model)
- [ ] Endpoint URL in session is `cursor://local`

---

## Chat mode (Plan A / C / C+)

| # | Test | Pass criteria |
|---|------|----------------|
| 1 | **Short reply** | “Reply with exactly: pong” → contains `pong`, finishes with metrics / no error banner |
| 2 | **Multi-turn** | Second message references first (“what did I just ask?”) → correct context (resume / same agent) |
| 3 | **Stop** | Long prompt → click Stop mid-stream → partial text saved or clean stop, no stuck spinner |
| 4 | **Image gen** | “Generate a simple red circle PNG” → `generate_image` tool completes, image bubble, Gallery entry; if UI stuck on Generating, hard-refresh shows image |
| 5 | **Image attach** | Attach a small PNG + “describe this image” → model describes it (SDK image path, not 502) |
| 6 | **Tab / SSE** | Repeat image gen; stay on tab until done → tool card flips to done without refresh |

---

## Agent mode (Plan B Phase 1)

| # | Test | Pass criteria |
|---|------|----------------|
| 7 | **Switch mode** | Same session or new → **Agent** mode + Cursor model |
| 8 | **Tool cards** | “List files in the workspace root” (or small read-only task) → `tool_start` / `tool_output` thread, not silent failure |
| 9 | **No wrong engine** | No bash-only Odysseus loop pretending to be Cursor; errors mention Cursor/bridge if bridge down |

---

## Must *not* use Cursor (by design)

| # | Test | Pass criteria |
|---|------|----------------|
| 10 | **Compare** | Compare mode with only Cursor configured → skipped or clear message, no hung compare |
| 11 | **Deep Research** | Research with Cursor-only → does not route to `cursor://local` |

---

## Admin / ops

| # | Test | Pass criteria |
|---|------|----------------|
| 12 | **Disable endpoint** | Toggle endpoint off → model picker hides Cursor models |
| 13 | **Billing sanity** | Usage visible under [Integrations](https://cursor.com/dashboard/integrations); **no** new row required on [Cloud Agents](https://cursor.com/dashboard/cloud-agents) dashboard for local chat |
| 14 | **SDK import** | On host: `python -c "import cursor_sdk"` in venv → OK |

---

## After code or SDK changes

Run [`CURSOR_SDK_UPGRADES.md`](../CURSOR_SDK_UPGRADES.md) pytest subset, then re-run rows **1, 2, 4, 7, 8** as a minimum.
