# Cursor Python SDK upgrade playbook

Odysseus integrates with **`cursor-sdk`** (local bridge + agent streaming). The package is young and event shapes can change between releases. Treat SDK bumps as a small release, not a routine `pip install -U`.

**Current pin:** see [`requirements-cursor.txt`](../requirements-cursor.txt).  
**Currency assessment + cutover plan:** [`CURSOR_INTEGRATION_CURRENCY.md`](./CURSOR_INTEGRATION_CURRENCY.md) (2026-07-30: git current on `upstream/dev`; prod still on `0.1.9` while `1.0.26` passed isolated automated probes).

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
| **Production / Docker** | Exact pin of a verified version (today: `0.1.9`; planned cutover: `1.0.26` per currency doc). Avoid wide `>=1,<2` while the bridge is vendored. |
| **Local / probe** | Isolated venv (do not mutate the running service venv); same pin as the candidate cutover |
| **CI** | Should install `requirements.txt` **and** `requirements-cursor.txt`, then run the Cursor-focused suite + `pip check` (see currency doc; current CI may not do this yet) |

Loose pins let fresh VMs silently pick up breaking SDK releases. Prefer bumping only after the checklist and a live Chat/Agent smoke pass.

---

## Not in scope for SDK upgrades

- **Cursor Cloud Agents** (dashboard jobs, repos, PRs) — separate API; Odysseus v1 uses **local bridge only** (`cursor://local`).
