#!/usr/bin/env bash
# Shared constants for upstream-facing Cursor SDK branches (lawmight fork).
set -euo pipefail

UPSTREAM_URL="${UPSTREAM_URL:-https://github.com/pewdiepie-archdaemon/odysseus.git}"
UPSTREAM_REMOTE="${UPSTREAM_REMOTE:-upstream}"

# Manifest paths for upstream PR (see docs/guides/UPSTREAM_CURSOR_PR_FILES.md).
UPSTREAM_CURSOR_MANIFEST=(
  requirements-cursor.txt
  src/providers/cursor_adapter.py
  src/providers/cursor_agent.py
  src/providers/cursor_mcp.py
  src/llm_core.py
  src/endpoint_resolver.py
  src/bg_monitor.py
  src/chat_processor.py
  core/models.py
  core/database.py
  core/session_manager.py
  app.py
  routes/model_routes.py
  routes/chat_routes.py
  routes/chat_helpers.py
  routes/gallery_helpers.py
  static/index.html
  static/js/admin.js
  tests/test_cursor_adapter.py
  tests/test_cursor_admin_ui.py
  tests/test_cursor_agent.py
  tests/test_cursor_agent_skills.py
  tests/test_cursor_chat_tool_events.py
  tests/test_cursor_mcp_bridge.py
  tests/test_llm_core_cursor.py
  tests/test_bg_monitor_cursor.py
  tests/test_model_routes.py
  tests/test_endpoint_resolver.py
  docs/CURSOR_SDK_UPGRADES.md
  ACKNOWLEDGMENTS.md
)
# README.md is upstream-facing but merged manually when upstream README diverged (not in array).

upstream_cursor_branch_for_target() {
  local target="${1:-main}"
  case "$target" in
    main) echo "cursor/upstream-cursor-provider-5b2d" ;;
    dev)  echo "cursor/upstream-cursor-provider-dev-627e" ;;
    *)
      echo "upstream-cursor-lib: unknown target '$target' (expected main or dev)" >&2
      return 1
      ;;
  esac
}

upstream_cursor_ensure_remote() {
  if git remote get-url "$UPSTREAM_REMOTE" >/dev/null 2>&1; then
    return 0
  fi
  git remote add "$UPSTREAM_REMOTE" "$UPSTREAM_URL"
}

upstream_cursor_fetch() {
  upstream_cursor_ensure_remote
  git fetch "$UPSTREAM_REMOTE" --prune
  git fetch origin --prune
}

upstream_cursor_run_tests() {
  if [[ ! -d venv ]]; then
    echo "upstream-cursor-lib: venv missing; run bash scripts/cloud-agent-install.sh" >&2
    return 1
  fi
  # shellcheck disable=SC1091
  source venv/bin/activate
  python -m pip install -q -r requirements.txt
  [[ -f requirements-cursor.txt ]] && python -m pip install -q -r requirements-cursor.txt
  python -m pytest -q \
    tests/test_cursor_adapter.py \
    tests/test_model_routes.py \
    tests/test_cursor_chat_tool_events.py \
    tests/test_cursor_admin_ui.py \
    tests/test_cursor_agent.py \
    tests/test_cursor_agent_skills.py \
    tests/test_cursor_mcp_bridge.py \
    tests/test_llm_core_cursor.py \
    tests/test_bg_monitor_cursor.py \
    tests/test_endpoint_resolver.py
}

upstream_cursor_is_up_to_date() {
  local upstream_ref="$1"
  local branch_ref="$2"
  git merge-base --is-ancestor "$upstream_ref" "$branch_ref" 2>/dev/null
}
