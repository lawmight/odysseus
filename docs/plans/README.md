# Cursor integration (fork)

Shipped on `main`. This folder is an index only. Design archives live in git history.

## Operational docs

| Doc | Purpose |
|-----|---------|
| [CURSOR_SDK_UPGRADES.md](../CURSOR_SDK_UPGRADES.md) | SDK pin bumps and regression tests |
| [guides/UPSTREAM_CURSOR_PR_FILES.md](../guides/UPSTREAM_CURSOR_PR_FILES.md) | Paths to carve for upstream PR |
| [guides/UPSTREAM_PR_GUIDELINES.md](../guides/UPSTREAM_PR_GUIDELINES.md) | Fork PR workflow |

**Upstream staging branch:** see [guides/UPSTREAM_CURSOR_PR_FILES.md](../guides/UPSTREAM_CURSOR_PR_FILES.md).

## Shipped on main

- Chat BYOK (`cursor://local`, optional `requirements-cursor.txt`)
- Agent engine (`stream_cursor_agent_loop`)
- Chat `generateImage` and session `tool_events` reload
- Background auto-continue skip for Cursor sessions
- Odysseus MCP DB bridge (opt-in via `cursor_agent_mcp_from_db`)

## Out of scope (v1)

- Cursor Cloud Agents (dashboard jobs, repo automation, cloud PR workflows)
