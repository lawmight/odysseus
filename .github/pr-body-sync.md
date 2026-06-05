<!-- CURSOR_AGENT_PR_BODY_BEGIN -->
## Summary

New companion branch for upstream **`dev`** (distinct from upstream `main`). Same fork sync as the main-targeting branch, but merges **`dev-upstream/dev`** instead of `main-upstream/main`.

Layers:
1. **Your fork work** — merged `origin/main`.
2. **Upstream dev** — merged `dev-upstream/dev` (18 commits from pewdiepie-archdaemon/odysseus dev).
3. **Cursor provider carve** — same conflict resolutions as the main-upstream branch.

Use this branch when preparing an upstream PR against `dev`; use `cursor/upstream-cursor-provider-5b2d` for upstream `main`.

## Linked Issue

Part of #2815
## Target branch

- [x] This PR targets **`main`** (fork integration branch).

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

1. Check out this branch.
2. Run Cursor provider tests (same as main-targeting branch).
3. Compare divergence vs main branch: `git log --oneline cursor/upstream-cursor-provider-5b2d..cursor/upstream-cursor-provider-dev-627e` and reverse.
<!-- CURSOR_AGENT_PR_BODY_END -->

<div><a href="https://cursor.com/agents/bc-ba84dfae-f856-48ca-ac93-986e14fa627e"><picture><source media="(prefers-color-scheme: dark)" srcset="https://cursor.com/assets/images/open-in-web-dark.png"><source media="(prefers-color-scheme: light)" srcset="https://cursor.com/assets/images/open-in-web-light.png"><img alt="Open in Web" width="114" height="28" src="https://cursor.com/assets/images/open-in-web-dark.png"></picture></a>&nbsp;<a href="https://cursor.com/background-agent?bcId=bc-ba84dfae-f856-48ca-ac93-986e14fa627e"><picture><source media="(prefers-color-scheme: dark)" srcset="https://cursor.com/assets/images/open-in-cursor-dark.png"><source media="(prefers-color-scheme: light)" srcset="https://cursor.com/assets/images/open-in-cursor-light.png"><img alt="Open in Cursor" width="131" height="28" src="https://cursor.com/assets/images/open-in-cursor-dark.png"></picture></a>&nbsp;</div>



<!-- This is an auto-generated description by cubic. -->
---
## Summary by cubic
Adds a workspace mode that confines agent file/shell tools to a chosen server folder and introduces MCP Streamable HTTP transport with OAuth 2.0. Improves safety, multi‑tenant correctness, and remote MCP connectivity.

- **New Features**
  - Workspace confinement: pick a folder (UI modal or `/workspace`/`/ws`), hard‑bound file tools to it, and run bash/python with cwd there; admin‑only server browser at GET `/api/workspace/browse`.
  - MCP Streamable HTTP + OAuth: new `http` transport with discovery, dynamic client registration, PKCE, refresh; encrypted `oauth_tokens` column and migration; background connect publishes `needs_auth` and `auth_url`; UI flow with polling and paste‑back.
  - Chat emoji shortcodes: convert `:shortcode:` to Unicode before SVG icons; scoped to chat (email/docs unchanged).
  - Always‑available edit/write: add `edit_file` and `write_file` to the default tool set (still admin‑gated).
  - Context window cache: key by (endpoint, model) to avoid cross‑endpoint collisions.

- **Bug Fixes**
  - Email AI caches: owner‑scoped keys and queries; legacy rows migrated; task cache clearing respects owner.
  - CalDAV sync: do not prune locally created events; add `origin="caldav"` and gate prune by origin.
  - Memory extractor: prevent cross‑tenant drops from vector dedup; only dedup when the match is the same owner.
  - LLM payloads: tolerate missing/None system message content for Anthropic.
  - MCP prompt hardening: sanitize and cap tool param names/types to avoid prompt distortion.
  - Workspace enforcement: grep/glob/ls/edit_file resolve inside the workspace; outside paths are rejected; bash/python honor workspace cwd.

<sup>Written for commit 7d2c2079503578ab1b783de60ef0b23db01fc78f. Summary will update on new commits.</sup>

<a href="https://cubic.dev/pr/lawmight/odysseus/pull/37?utm_source=github" target="_blank" rel="noopener noreferrer" data-no-image-dialog="true"><picture><source media="(prefers-color-scheme: dark)" srcset="https://cubic.dev/buttons/review-in-cubic-dark.svg"><source media="(prefers-color-scheme: light)" srcset="https://cubic.dev/buttons/review-in-cubic-light.svg"><img alt="Review in cubic" src="https://cubic.dev/buttons/review-in-cubic-dark.svg"></picture></a>

<!-- End of auto-generated description by cubic. -->


