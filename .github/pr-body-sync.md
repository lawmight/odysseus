<!-- CURSOR_AGENT_PR_BODY_BEGIN -->
## Summary

Updates `cursor/upstream-cursor-provider-5b2d` in three layers:

1. **Your fork work** — merged `origin/main` (149 commits since the original carve point).
2. **Upstream main** — merged `main-upstream/main` (27 additional commits from pewdiepie-archdaemon/odysseus).
3. **Cursor provider carve** — preserved the three upstream-integration commits and resolved merge conflicts in `routes/chat_routes.py` (Cursor agent loop + upstream `workspace` param) and `tests/test_edit_file.py`.

Also configures remotes `main-upstream` and `dev-upstream` for clearer upstream tracking.

## Linked Issue

Part of #2815
## Target branch

- [x] This PR targets **`main`** (fork integration branch). Upstream contribution PR will be opened separately against pewdiepie-archdaemon/odysseus `dev`.

## Type of Change

- [ ] Bug fix (non-breaking — fixes a confirmed issue)
- [x] New feature (non-breaking — adds new behaviour)
- [ ] Breaking change (changes or removes existing behaviour)
- [ ] Refactor / cleanup (behaviour unchanged)
- [ ] Documentation only
- [ ] CI / tooling / configuration

## Checklist

- [x] I searched [open issues](https://github.com/pewdiepie-archdaemon/odysseus/issues) and [open PRs](https://github.com/pewdiepie-archdaemon/odysseus/pulls) — this is not a duplicate.
- [x] This PR targets `main`
- [x] My changes are limited to the scope described above — no unrelated refactors or whitespace changes mixed in.

## How to Test

1. Fetch remotes: `git fetch origin main-upstream dev-upstream` (after adding remotes locally).
2. Check out this branch and run Cursor provider tests:
   ```bash
   pytest tests/test_cursor_adapter.py tests/test_model_routes.py \
     tests/test_cursor_chat_tool_events.py tests/test_cursor_agent.py -q
   ```
3. Verify agent mode still routes Cursor endpoints through `stream_cursor_agent_loop` and non-Cursor endpoints through `stream_agent_loop` with `workspace`.
<!-- CURSOR_AGENT_PR_BODY_END -->

<div><a href="https://cursor.com/agents/bc-ba84dfae-f856-48ca-ac93-986e14fa627e"><picture><source media="(prefers-color-scheme: dark)" srcset="https://cursor.com/assets/images/open-in-web-dark.png"><source media="(prefers-color-scheme: light)" srcset="https://cursor.com/assets/images/open-in-web-light.png"><img alt="Open in Web" width="114" height="28" src="https://cursor.com/assets/images/open-in-web-dark.png"></picture></a>&nbsp;<a href="https://cursor.com/background-agent?bcId=bc-ba84dfae-f856-48ca-ac93-986e14fa627e"><picture><source media="(prefers-color-scheme: dark)" srcset="https://cursor.com/assets/images/open-in-cursor-dark.png"><source media="(prefers-color-scheme: light)" srcset="https://cursor.com/assets/images/open-in-cursor-light.png"><img alt="Open in Cursor" width="131" height="28" src="https://cursor.com/assets/images/open-in-cursor-dark.png"></picture></a>&nbsp;</div>



<!-- This is an auto-generated description by cubic. -->
---
## Summary by cubic
Syncs `cursor/upstream-cursor-provider-5b2d` with `main` and `main-upstream`, preserving the Cursor provider carve, and ships several platform improvements: workspace-constrained tools, Cookbook serve scheduling/lifecycle, MCP Streamable HTTP + OAuth, and multiple reliability fixes.

- **New Features**
  - Workspace confinement for agent tools with an admin-only directory browser, input-bar pill, and `/workspace` (`/ws`) command. File tools and bash/python run inside the chosen folder.
  - Cookbook serves: schedule via ScheduledTask (`cookbook_serve`), auto-stop at window end, robust Stop (verifies kill), orphan tmux adoption, persistent log tailing, and Ollama auto port-pick. New `tail_serve_output` tool exposed to agents and skills.
  - MCP Streamable HTTP transport with OAuth 2.0: dynamic registration, PKCE, refresh, and a paste-back flow. Adds encrypted `oauth_tokens` column and a UI that guides auth and polls until connected.
  - Tooling/UX: `write_file` and `edit_file` are always available (still admin-gated); edit_file now honors workspace. Notes creation returns `note_id` so chat renders a “View note” link. Chat renders `:shortcode:` emoji. Model picker shows offline endpoints dimmed.

- **Bug Fixes**
  - CalDAV sync no longer prunes locally-created events; only rows with `origin="caldav"` are pruned.
  - Auto-memory vector dedup only suppresses facts when the match belongs to the same owner (prevents cross-tenant drops).
  - System messages with missing/None `content` no longer crash Anthropic payload build.
  - Context-window cache is keyed by `(endpoint, model)` so different endpoints for the same model don’t collide.
  - Email AI caches are owner-scoped with a lightweight migration for legacy rows; email routes/pollers query per-owner.

<sup>Written for commit 3d6e53c1e79a5ce4c19d1054fda82b25822c97e4. Summary will update on new commits.</sup>

<a href="https://cubic.dev/pr/lawmight/odysseus/pull/36?utm_source=github" target="_blank" rel="noopener noreferrer" data-no-image-dialog="true"><picture><source media="(prefers-color-scheme: dark)" srcset="https://cubic.dev/buttons/review-in-cubic-dark.svg"><source media="(prefers-color-scheme: light)" srcset="https://cubic.dev/buttons/review-in-cubic-light.svg"><img alt="Review in cubic" src="https://cubic.dev/buttons/review-in-cubic-dark.svg"></picture></a>

<!-- End of auto-generated description by cubic. -->


