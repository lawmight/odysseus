# Merged PR #23 — Cursor SDK upgrades + endpoint model count fix

**PR:** [lawmight/odysseus#23](https://github.com/lawmight/odysseus/pull/23)  
**Merge commit:** `7188279` on `main` (2026-06-04)

This file is the canonical description for #23. The GitHub PR body still contains auto-generated review comments that cannot be edited from the Cloud Agent token.

## Summary

Fixes Cursor model endpoints showing **0/0** in Settings when Plan C caches `{id, displayName}` objects, and adds documentation plus a bounded `cursor-sdk` pin so future upgrades do not break Chat/Agent paths silently.

## Type of change

- Bug fix (model endpoint list visibility for Cursor)
- Documentation (upgrade playbook, pre–Plan B smoke checklist)
- Dependency pin hygiene (`cursor-sdk>=0.1.6,<0.2`; PyPI still at 0.1.6)

## Changes

| Area | Detail |
|------|--------|
| **Bug fix** | `routes/model_routes.py` — pass string model IDs into `_visible_models` for Cursor list / create-duplicate / default-chat paths |
| **Tests** | `test_list_model_endpoints_cursor_objects_count_as_visible` |
| **Docs** | [CURSOR_SDK_UPGRADES.md](../CURSOR_SDK_UPGRADES.md); README / AGENTS / matrix cross-links |
| **Deps** | `requirements-cursor.txt`, `requirements-optional.txt` |

## How to verify

1. `source venv/bin/activate && python -m pytest tests/test_model_routes.py::test_list_model_endpoints_cursor_objects_count_as_visible -q`
2. In Settings, open a Cursor endpoint with Plan C `{id, displayName}` cache entries; confirm the row shows the correct model count (not `0/0`).
3. Use [CURSOR_SDK_UPGRADES.md](../CURSOR_SDK_UPGRADES.md) when bumping `cursor-sdk`.

## UI

No `static/` changes. Settings model counts are fixed via API responses only.
