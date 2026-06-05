# Upstream cursor integration — file manifest

Use this list when carving a PR to **pewdiepie-archdaemon/odysseus**. Rebase onto current upstream `main` (or `dev` if maintainers prefer), then apply only these paths from the lawmight fork.

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
tests/test_cursor_plan_c.py
tests/test_cursor_plan_c_plus.py
tests/test_model_routes.py   # cursor-related tests only if file is mixed
```

## Docs (upstream-facing; trim fork URLs)

```
README.md                           # "Cursor as a provider" section only
ACKNOWLEDGMENTS.md                  # cursor-sdk row
docs/CURSOR_SDK_UPGRADES.md
docs/plans/CURSOR_INTEGRATION_VERIFICATION.md
docs/plans/CURSOR_PRE_PLAN_B_SMOKE.md
```

Optional: subset of `docs/plans/cursor-*.md` if maintainers want design history.

## Carve command (from lawmight branch with cursor work)

```bash
git fetch upstream main
git checkout -b cursor/upstream-cursor-provider-1d61 upstream/main

# Apply cursor tree from lawmight (adjust SOURCE ref)
SOURCE=cursor/cursor-pr-cleanup-1d61
git checkout "$SOURCE" -- \
  requirements-cursor.txt \
  src/providers/cursor_adapter.py \
  src/providers/cursor_agent.py \
  src/providers/cursor_mcp.py \
  routes/model_routes.py \
  routes/chat_routes.py \
  static/index.html \
  static/js/admin.js \
  tests/test_cursor_adapter.py \
  tests/test_cursor_admin_ui.py \
  tests/test_cursor_agent.py \
  tests/test_cursor_agent_skills.py \
  tests/test_cursor_chat_tool_events.py \
  tests/test_cursor_mcp_bridge.py \
  tests/test_cursor_plan_c.py \
  tests/test_cursor_plan_c_plus.py \
  docs/CURSOR_SDK_UPGRADES.md \
  docs/plans/CURSOR_INTEGRATION_VERIFICATION.md \
  docs/plans/CURSOR_PRE_PLAN_B_SMOKE.md \
  ACKNOWLEDGMENTS.md

# README: merge Cursor section manually if upstream README diverged
```

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
  tests/test_cursor_plan_c.py tests/test_cursor_plan_c_plus.py \
  tests/test_cursor_admin_ui.py tests/test_cursor_agent.py -q
```
