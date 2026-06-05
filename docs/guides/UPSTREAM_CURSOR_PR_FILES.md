# Upstream cursor integration — file manifest

Use this list when carving a PR to **pewdiepie-archdaemon/odysseus**. Rebase onto current upstream `main` (or `dev` if maintainers prefer), then apply only these paths from the lawmight fork.

**Live staging branch (fork):** `cursor/upstream-cursor-provider-5b2d` — carved from `upstream/main` @ fork `main`, excludes fork-only Copilot hooks and Cloud Agent paths.

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

When carving full files from fork `main`, **remove fork-only GitHub Copilot imports** from `app.py`, `src/llm_core.py`, and `src/endpoint_resolver.py` (upstream has no `src/copilot.py`).

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

## Carve command (from lawmight branch with cursor work)

```bash
git remote add upstream https://github.com/pewdiepie-archdaemon/odysseus.git 2>/dev/null || true
git fetch upstream main origin main

git checkout -b cursor/upstream-cursor-provider-5b2d upstream/main

SOURCE=origin/main
git checkout "$SOURCE" -- \
  requirements-cursor.txt \
  src/providers/cursor_adapter.py \
  src/providers/cursor_agent.py \
  src/providers/cursor_mcp.py \
  src/llm_core.py \
  src/endpoint_resolver.py \
  src/bg_monitor.py \
  src/chat_processor.py \
  core/models.py \
  core/database.py \
  core/session_manager.py \
  app.py \
  routes/model_routes.py \
  routes/chat_routes.py \
  routes/chat_helpers.py \
  routes/gallery_helpers.py \
  static/index.html \
  static/js/admin.js \
  tests/test_cursor_adapter.py \
  tests/test_cursor_admin_ui.py \
  tests/test_cursor_agent.py \
  tests/test_cursor_agent_skills.py \
  tests/test_cursor_chat_tool_events.py \
  tests/test_cursor_mcp_bridge.py \
  tests/test_llm_core_cursor.py \
  tests/test_bg_monitor_cursor.py \
  tests/test_model_routes.py \
  tests/test_endpoint_resolver.py \
  docs/CURSOR_SDK_UPGRADES.md \
  ACKNOWLEDGMENTS.md

# Strip fork-only Copilot hooks from carved glue (upstream has no src/copilot.py)
# README: merge Cursor section manually if upstream README diverged
```

Or refresh the live staging branch: `git fetch origin cursor/upstream-cursor-provider-5b2d && git checkout cursor/upstream-cursor-provider-5b2d`.

Resolve conflicts in `routes/*.py` and `tests/test_model_routes.py` by keeping upstream non-cursor behavior.

## PR body must mention

- Optional `requirements-cursor.txt`; feature inert without SDK on the **uvicorn host**
- Default Docker image unchanged; bridge runs where Odysseus runs
- BYOK Cursor API key in Settings; usage bills on the user's Cursor account

## Verify

```bash
source venv/bin/activate
pip install -r requirements.txt -r requirements-cursor.txt
pytest tests/test_cursor_adapter.py tests/test_model_routes.py \
  tests/test_cursor_chat_tool_events.py tests/test_cursor_admin_ui.py \
  tests/test_cursor_agent.py tests/test_cursor_agent_skills.py \
  tests/test_cursor_mcp_bridge.py tests/test_llm_core_cursor.py \
  tests/test_bg_monitor_cursor.py -q
```
