# Bugbot rules for Odysseus

Project-specific review context for [Cursor Bugbot](https://cursor.com/docs/bugbot). CI runs pytest and secret scans; this file covers invariants those gates cannot express.

## Security and auth

- New API routes must respect the existing privilege model: admin-only tools (shell, Python, file read/write, MCP management, API tokens, webhooks, model/cookbook serving, backup/vault, app settings) stay admin-gated unless the PR explicitly documents a deliberate change with migration notes.
- Non-admin users must not gain access to privileged agent tools by accident (indirect imports, shared helpers, or default-on flags).
- Do not commit secrets, live `.env` values, `data/` artifacts, or API keys (`CURSOR_API_KEY`, provider tokens, webhook secrets). Flag any diff that adds credential-like strings under tracked paths.

## Cursor adapter boundaries

- The Cursor provider path is **Chat mode only**. Changes must not silently enable Agent-tab capabilities (tool loops, MCP cards, unrestricted workspace tools) through the chat adapter.
- `src/providers/cursor_adapter.py` and related routes should not widen `CURSOR_ALLOWED_WORKSPACE_ROOTS` behavior without an explicit security note.
- Image and attachment handling must stay on supported SDK paths; avoid HTTP fallbacks that bypass Cursor SDK contracts.

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
