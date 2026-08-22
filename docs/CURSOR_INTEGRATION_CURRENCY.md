# Cursor integration currency (assessment + fix plan)

Assessment date: **2026-07-30**.  
Branch assessed: `cursor/upstream-cursor-provider-dev-627e` @ `88fbbe16`.  
Companion playbook: [`CURSOR_SDK_UPGRADES.md`](./CURSOR_SDK_UPGRADES.md).

## Verdict

| Dimension | Status |
|---|---|
| Git vs `upstream/dev` | **Current** (0 behind after 2026-07-30 merge) |
| Git vs `upstream/main` | No missing functionality (1 commit is duplicate/squashed history) |
| `cursor-sdk` in production | **Stale** — installed `0.1.9`, pin `>=0.1.6,<0.2`, PyPI latest `1.0.26` |
| Automated compatibility with `1.0.26` | **Green** — 233 focused tests passed in an isolated venv; bridge launch/close smoked |
| Live billable Chat/Agent on `1.0.26` | **Not yet proven** |

Recommendation: keep serving on `0.1.9` until a short cutover window; then pin exact `cursor-sdk==1.0.26` with rollback ready.

## Integration surface

| Area | Role |
|---|---|
| `src/providers/cursor_adapter.py` | Model discovery, workspace allowlist, bridge LRU, Chat streaming, create/resume, images, cancel |
| `src/providers/cursor_agent.py` | Agent-mode streaming, tool cards, tool budget, MCP send options |
| `src/providers/cursor_mcp.py` | Opt-in DB→Cursor MCP serialization (stdio/SSE/HTTP) |
| `routes/model_routes.py` / `routes/chat_routes.py` | Endpoint setup, API-key probe, Chat/Agent dispatch, stop |
| `src/llm_core.py` / `src/endpoint_resolver.py` | Provider detection; exclude Cursor from HTTP-only utility paths |
| `core/database.py` / `core/session_manager.py` | Endpoint metadata + durable `cursor_agent_id` |
| `app.py` | Close cached bridges on shutdown |
| UI (`static/…`) | Cursor endpoint picker + workspace cwd |
| Tests | `tests/test_cursor_*.py` plus related model/llm/bg-monitor coverage |

Local launch isolation (this machine): Cursor instance on `:7000` with dedicated `~/odysseus/.venv`; stock on `:7001` via `odysseus-stock`. Helpers: `odysseus-cursor`, `odysseus-stock`.

## Break / risk map

| Item | Severity | Evidence / note |
|---|---|---|
| Pin `<0.2` blocks `1.0.26` | High (process) | `pip`/`uv` conflict until pin changes |
| Bundled bridge/auth internals differ in 1.x | Medium | Public Python signatures (`AsyncClient.launch_bridge`, `agents.create`/`resume`, `LocalAgentOptions`, `UserMessage`, `SDKImage`) stayed compatible in probe; live `agent.send()` still needed |
| Docs/CI lag | Medium | Playbook still shows `<0.2`; CI installs `requirements.txt` only and is non-blocking for Cursor |
| `CURSOR_BRIDGE_CACHE_MAX` default (4) | Medium on low-RAM hosts | Prefer `1` at cutover |
| `cursor_agent_mcp_from_db` | Low if left off | Hidden/default-off; forwards server cmds/env when enabled |
| Missing upstream/main work | None | Tree-equivalent to already-merged `dev` history |

## Phased fix plan

1. **Hold production on `0.1.9`** until cutover is scheduled (no functional git lag).
2. **Change pin** to exact `cursor-sdk==1.0.26` in `requirements-cursor.txt` (avoid wide `>=1,<2` while the bridge is vendored).
3. **Refresh** [`CURSOR_SDK_UPGRADES.md`](./CURSOR_SDK_UPGRADES.md): isolated probe venv, full test list (include `tests/test_llm_core_cursor.py`), CI truth.
4. **CI**: focused job that installs base + Cursor requirements, runs the Cursor suite, runs `pip check`, and is blocking. Optional scheduled “latest 1.x” probe.
5. **Parallel venv** under `nice`/`ionice`: install new pin, re-run suite + bridge smoke; do not touch the running service’s venv until swap.
6. **User-timed restart** of `odysseus.service` / `odysseus-cursor restart`; keep prior `0.1.9` venv for immediate rollback.
7. **Cutover knobs**: `CURSOR_BRIDGE_CACHE_MAX=1`; leave `cursor_agent_mcp_from_db` disabled unless explicitly approved.
8. **Live smoke**: one Chat and one Agent prompt (resume + tool/image event).

## User vs agent

**User**

- Approve SDK cutover window and observe billable Chat/Agent smoke.
- Decide whether DB-backed MCP should ever be enabled.

**Agent (after approval)**

- Land pin + playbook + CI changes.
- Build/validate parallel venv; prepare rollback; perform short service cutover.

## Related Hermes work

Hermes Cursor provider port onto latest `main` is a separate major port (not a rebase). See the Hermes fork plan: `docs/plans/cursor-provider-main-port.md` on branch `cursor/cursor-provider-port-plan-00ff` in `lawmight/hermes-agent`.
