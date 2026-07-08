# Upstream cursor integration — file manifest

Use this list when carving a PR to **pewdiepie-archdaemon/odysseus**. Rebase onto current upstream `main` (or `dev` if maintainers prefer), then apply only these paths from the lawmight fork.

**Live staging branch (fork):** `cursor/upstream-cursor-provider-5b2d` — carved from `upstream/main` @ fork `main`; keep fork Cloud Agent / fork-only paths out of the carve. Upstream ships its own `src/copilot.py`, so reconcile Copilot glue in carved files (keep both providers; delete neither side).

**Do not include** paths listed in [FORK_ONLY_MANIFEST.md](../cloud/FORK_ONLY_MANIFEST.md).

## Recommended PR split

1. **`feat(chat): Cursor BYOK + Plan C/C+`** — adapter, chat streaming, admin UI, tests below (chat-focused).
2. **`feat(agent): Cursor Agent engine`** (optional second PR) — `cursor_agent.py`, agent route branches, agent tests.

## Core runtime

```
requirements-cursor.txt
src/providers/cursor_adapter.py
src/providers/cursor_agent.py
src/providers/cursor_mcp.py
```

## Integration glue (required; not in original manifest)

```
src/llm_core.py
src/endpoint_resolver.py
src/bg_monitor.py
src/chat_processor.py
core/models.py
core/database.py
core/session_manager.py
app.py                        # close_cursor_bridges() on shutdown only
routes/chat_helpers.py        # tool_event_from_chat_tool_output for Chat tool_events
routes/gallery_helpers.py     # save_generated_image_bytes for generateImage
```

When carving full files from fork `main`, **reconcile Copilot code paths** in `app.py`, `src/llm_core.py`, and `src/endpoint_resolver.py` — upstream ships its own `src/copilot.py` (since Jun 2026), so keep both providers working and delete neither side. Also port any upstream APIs the carved files lag behind (known case: `resolve_endpoint_runtime` in `src/endpoint_resolver.py`, imported by upstream's `src/ai_interaction.py`).

## Routes (review for non-cursor hunks before upstream)

```
routes/model_routes.py    # Cursor provider, SDK gate, include_meta
routes/chat_routes.py     # stream_cursor_chat / stream_cursor_agent_loop branches
```

## Admin UI

```
static/index.html         # cursor://local preset, workspace row, hints
static/js/admin.js        # provider picker, cursor_sdk_available
```

## Tests

```
tests/test_cursor_adapter.py
tests/test_cursor_admin_ui.py
tests/test_cursor_agent.py
tests/test_cursor_agent_skills.py
tests/test_cursor_chat_tool_events.py
tests/test_cursor_mcp_bridge.py
tests/test_llm_core_cursor.py
tests/test_bg_monitor_cursor.py
tests/test_model_routes.py   # cursor-related tests only if file is mixed
tests/test_endpoint_resolver.py
```

## Docs (upstream-facing; trim fork URLs)

```
README.md                           # "Cursor as a provider" section only
ACKNOWLEDGMENTS.md                  # cursor-sdk row
docs/CURSOR_SDK_UPGRADES.md
```

## Carving and refreshing

The machine-readable manifest lives in `UPSTREAM_CURSOR_MANIFEST` in [scripts/upstream-cursor-lib.sh](../../scripts/upstream-cursor-lib.sh) — the single source of truth. Preview it (and which paths a source ref is missing) with:

```bash
bash scripts/carve-upstream-cursor-branch.sh --target main --dry-run
```

One-time rebuild (upstream base + manifest paths only):

```bash
bash scripts/carve-upstream-cursor-branch.sh --target main --source origin/main
```

Refresh the live staging branch:

```bash
bash scripts/refresh-upstream-cursor-branch.sh --target main
```

See [docs/cloud/UPSTREAM_CURSOR_BRANCH.md](../cloud/UPSTREAM_CURSOR_BRANCH.md) and `.cursor/skills/upstream-cursor-branch/SKILL.md`.

Resolve conflicts in `routes/*.py` and `tests/test_model_routes.py` by keeping upstream non-cursor behavior.

## PR body must mention

- Optional `requirements-cursor.txt`; feature inert without SDK on the **uvicorn host**
- Default Docker image unchanged; bridge runs where Odysseus runs
- BYOK Cursor API key in Settings; usage bills on the user's Cursor account

## Verify

Run the cursor test subset defined once in `upstream_cursor_run_tests` ([scripts/upstream-cursor-lib.sh](../../scripts/upstream-cursor-lib.sh)):

```bash
source scripts/upstream-cursor-lib.sh && upstream_cursor_run_tests
```
