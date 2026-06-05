# Bugbot rules for Odysseus

Project-specific review context for [Cursor Bugbot](https://cursor.com/docs/bugbot). CI runs pytest and secret scans; this file covers invariants those gates cannot express.

Before opening a PR, follow [docs/guides/UPSTREAM_PR_GUIDELINES.md](../docs/guides/UPSTREAM_PR_GUIDELINES.md), read [`.cursor/skills/fork-pr-ci/SKILL.md`](../.cursor/skills/fork-pr-ci/SKILL.md), run `bash scripts/scaffold-pr-body.sh` + `node scripts/validate-pr-body.js pr-body.md`, then `bash scripts/ci-preflight.sh --require-pr-body`. Do not use bot-generated PR summaries as the only description.

## Security and auth

- New API routes must respect the existing privilege model: admin-only tools (shell, Python, file read/write, MCP management, API tokens, webhooks, model/cookbook serving, backup/vault, app settings) stay admin-gated unless the PR explicitly documents a deliberate change with migration notes.
- Non-admin users must not gain access to privileged agent tools by accident (indirect imports, shared helpers, or default-on flags).
- Do not commit secrets, live `.env` values, `data/` artifacts, or API keys (`CURSOR_API_KEY`, provider tokens, webhook secrets). Flag any diff that adds credential-like strings under tracked paths.

## Cursor adapter boundaries

- The Cursor integration has **two separate paths**: the **Chat mapper** (`stream_cursor_chat`, allowlisted tools only via `CURSOR_CHAT_TOOL_ALLOWLIST`) and the **Agent engine** (`stream_cursor_agent_loop`, Plan B Phase 1, full Cursor tools). Keep them separate — do not route Agent tool loops through the Chat adapter, and do not widen the Chat allowlist to Agent-style tools without product sign-off.
- The Chat allowlist (`CURSOR_CHAT_TOOL_ALLOWLIST`) must not grow to shell/file/MCP tools through the chat path; those belong to the Agent engine.
- `src/providers/cursor_adapter.py` and related routes should not widen `CURSOR_ALLOWED_WORKSPACE_ROOTS` behavior without an explicit security note.
- Image and attachment handling must stay on supported SDK paths; avoid HTTP fallbacks that bypass Cursor SDK contracts.
- Cursor endpoints must stay excluded from Compare, Deep Research, utility/vision resolvers, and background auto-continue. Enforced in `routes/chat_routes.py`, `routes/research_routes.py`, `src/bg_monitor.py`, `src/endpoint_resolver.py`, and related resolvers.
- The optional Odysseus MCP DB -> Cursor Agent bridge must remain explicit opt-in (`cursor_agent_mcp_from_db`). Do not silently pass MCP DB commands, URLs, headers, env values, or per-tool-disabled servers to Cursor.

## Layering and maintainability

- Provider adapters under `src/providers/` must not own UI orchestration, session persistence, or gallery save logic. Flag **layer bleed** when adapter code writes to the DB, renders UI state, or duplicates route-level orchestration.
- Prefer reusing canonical helpers in `src/` and `routes/` instead of one-off copies (especially gallery/tool_events paths).
- Large refactors that push a file past ~1000 lines should split into focused modules first.

## Tests

- Changes under `routes/` or `src/` should include or update pytest coverage in `tests/`. Flag backend behavior changes with no corresponding test updates unless the PR explains why (docs-only moves, pure renames with unchanged behavior).
- Do not suggest "run pytest" as the primary review finding — GitHub Actions CI already runs the full suite.

## Docker and deployment

- Port, bind address, or Cloud Agent port-forward changes must update `.cursor/environment.json`, `docker-compose.yml`, and relevant docs (`README.md`, `AGENTS.md`, `CONTRIBUTING.md`) together.
- Compose service wiring (ChromaDB, SearXNG, ntfy) must stay internal-only; do not expose sidecar ports on `0.0.0.0` without an explicit ops justification.

## Review tone

- Prefer high-signal findings: auth regressions, privilege escalation, adapter boundary violations, missing tests for behavior changes, and deployment footguns.
- Skip nits already covered by deterministic CI (syntax, secret grep, docker compose config).
