# Cursor Python SDK — upgrade playbook

Odysseus integrates with **`cursor-sdk`** (local bridge + agent streaming). The package is young and event shapes can change between releases. Treat SDK bumps as a small release, not a routine `pip install -U`.

**Current pin:** see [`requirements-cursor.txt`](../requirements-cursor.txt) (bounded range around the version verified in [`CURSOR_INTEGRATION_VERIFICATION.md`](plans/CURSOR_INTEGRATION_VERIFICATION.md)).

**Living spec:** [`docs/plans/cursor-sdk-capability-matrix.md`](plans/cursor-sdk-capability-matrix.md) — update status rows after each verified upgrade.

**Official docs:** [Cursor Python SDK](https://cursor.com/docs/sdk/python) · [Integrations / API keys](https://cursor.com/dashboard/integrations)

---

## When to run this

- Before merging a deliberate pin bump in `requirements-cursor.txt`
- After a Cloud Agent / Docker image rebuild that may have pulled a newer SDK (`>=` without upper bound previously)
- When Chat or Agent Cursor behavior regresses (tools, images, resume, bridge)

Check PyPI:

```bash
pip index versions cursor-sdk
```

---

## Upgrade checklist

1. **Note versions** — record old and new `cursor-sdk` in the matrix header (date + version).
2. **Read upstream** — skim Cursor SDK / changelog for `tool_call`, `generateImage`, `UserMessage` / `SDKImage`, bridge, and `agents.resume` changes.
3. **Install in dev** — `pip install -r requirements-cursor.txt` (or the new pin) in `venv`; confirm import: `python -c "import cursor_sdk; print('ok')"`.
4. **Automated tests** — from repo root with venv active:
   ```bash
   pytest tests/test_cursor_adapter.py tests/test_model_routes.py \
     tests/test_cursor_plan_c.py tests/test_cursor_plan_c_plus.py \
     tests/test_cursor_agent.py tests/test_bg_monitor_cursor.py -q
   ```
5. **Manual smoke (Chat)** — use the checklist in README § “Cursor as a provider” or ask for the pre–Plan B backlog tour before large Agent changes.
6. **Manual smoke (Agent)** — one Agent-mode prompt on a Cursor endpoint; confirm `tool_start` / `tool_output` cards (not native bash loop).
7. **Update docs** — matrix maintenance section, verification sheet “Verified versions” table if the pin changed.
8. **Commit** — pin + matrix header + any code fixes in one focused PR.

---

## Pin policy

| Environment | Recommendation |
|-------------|----------------|
| **Production / Docker** | Exact or tight bounded pin (`>=0.1.6,<0.2`) until a version is verified |
| **Local dev** | Same as prod; avoid unbounded `>=` without re-running tests |
| **CI** | Install `requirements-cursor.txt` as written |

Loose pins let fresh VMs silently pick up breaking SDK releases. Prefer bumping the upper bound only after the checklist passes.

---

## What breaks most often

| Area | Symptom | Odysseus touchpoints |
|------|---------|----------------------|
| `generateImage` result shape | Image saves on disk but UI stuck on “Generating” | `cursor_adapter.cursor_tool_call_chunks`, `publish_cursor_generated_image` |
| `tool_call` statuses | Tools never complete in UI | `stream_cursor_chat`, `stream_cursor_agent_loop` |
| Bridge lifecycle | 502 / “bridge not found” | `cursor_adapter._get_bridge_client` |
| Resume / `agent_id` | Follow-up turns start fresh agent | `session_manager`, `stream_cursor_chat` |
| Model list API | Settings shows 0 models | `model_routes`, `list_cursor_model_entries` |

---

## Not in scope for SDK upgrades

- **Cursor Cloud Agents** (dashboard jobs, repos, PRs) — separate API; Odysseus v1 uses **local bridge only** (`cursor://local`). See [`cursor-sdk-capability-matrix.md`](plans/cursor-sdk-capability-matrix.md) rows `runtime.cloud_*` and `cloud.*`.

---

## Nia doc IDs (re-index after major SDK releases)

| ID | Resource |
|----|----------|
| `71741e4c` | Cursor Python SDK |
| `abe7140b` | Cloud Agents REST API (reference only; not used for Chat v1) |
