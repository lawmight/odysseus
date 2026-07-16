# Cursor Python SDK upgrade playbook

Odysseus integrates with **`cursor-sdk`** (local bridge + agent streaming). The package is young and event shapes can change between releases. Treat SDK bumps as a small release, not a routine `pip install -U`.

**Current pin:** see [`requirements-cursor.txt`](../requirements-cursor.txt).

**Official docs:** [Cursor Python SDK](https://cursor.com/docs/sdk/python) · [Integrations / API keys](https://cursor.com/dashboard/integrations)

---

## When to run this

- Before merging a deliberate pin bump in `requirements-cursor.txt`
- After a Docker image rebuild or local install that changes the resolved SDK version
- When Chat or Agent Cursor behavior regresses (tools, images, resume, bridge)

Check PyPI:

```bash
pip index versions cursor-sdk
```

---

## Upgrade checklist

1. **Note versions** — record old and new `cursor-sdk` in the commit message or PR summary.
2. **Read upstream** — skim Cursor SDK / changelog for `tool_call`, `generateImage`, `UserMessage` / `SDKImage`, bridge, and `agents.resume` changes.
3. **Install in dev** — `pip install -r requirements-cursor.txt` (or the new pin) in `venv`; confirm import: `python -c "import cursor_sdk; print('ok')"`.
4. **Automated tests** — from repo root with venv active:
   ```bash
   pytest tests/test_cursor_adapter.py tests/test_model_routes.py \
     tests/test_cursor_chat_tool_events.py tests/test_cursor_agent.py \
     tests/test_cursor_mcp_bridge.py tests/test_cursor_agent_skills.py \
     tests/test_cursor_admin_ui.py tests/test_bg_monitor_cursor.py -q
   ```
5. **Manual smoke (Chat)** — use the README Cursor setup and send one prompt through a Cursor endpoint.
6. **Manual smoke (Agent)** — one Agent-mode prompt on a Cursor endpoint; confirm `tool_start` / `tool_output` cards (not native bash loop).
7. **Commit** — pin plus any code fixes in one focused PR.

---

## Pin policy

| Environment | Recommendation |
|-------------|----------------|
| **Production / Docker** | Exact or tight bounded pin (`>=0.1.6,<0.2`) until a version is verified |
| **Local dev** | Same as prod; avoid unbounded `>=` without re-running tests |
| **CI** | Install `requirements-cursor.txt` as written |

Loose pins let fresh VMs silently pick up breaking SDK releases. Prefer bumping the upper bound only after the checklist passes.

---

## Not in scope for SDK upgrades

- **Cursor Cloud Agents** (dashboard jobs, repos, PRs) — separate API; Odysseus v1 uses **local bridge only** (`cursor://local`).
