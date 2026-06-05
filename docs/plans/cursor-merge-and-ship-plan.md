# Cursor integration — merge & ship plan

**Status:** **Historical** — Plan A/C, Plan C+, and Plan B Phase 1 are shipped on `main`. Remote `cursor/*` branches were pruned; **`main` is the only integration line.**  
**Date:** 2026-06-02 (updated 2026-06-03)  
**Related:** Plan A/C ([cursor-plan-c-chat-byok-polished.md](./cursor-plan-c-chat-byok-polished.md)), [Plan B](./cursor-agent-tab-integration-plan.md) (Phase 2–4 next)

**Next work:** see the [Plan B v2 reframe](./cursor-agent-tab-integration-plan.md) and [backlog](./cursor-agent-tab-backlog.md). PR #2 / #8 branch map below is archival only.

---

## 1. Decision log (2026-06-02)

| Decision | Rationale |
|----------|-----------|
| **Plan A + Plan C are “finished” for Chat BYOK** | Validated on Cloud Agent desk: endpoint, picker, streaming, resume, model switch, dashboard billing, image **input** via SDKImage. |
| **PR #8 is superseded** | Its branch is fully contained in `cursor/merge-upstream-pr8-91e4`; merge branch is 92 commits ahead. Do not merge PR #8 as a separate unit. |
| **PR #2 remains the umbrella into `main`** | Single integration PR; fold the merge branch into it (or replace its head) before landing on `main`. |
| **Cursor `generateImage` / useful tools are out of scope for A/C** | Separate follow-up (Plan C+ or Plan D — see §6). Not Plan B (Agent tab engine). |

---

## 2. Branch & PR map (current)

```text
main
  ↑
PR #2  cursor/cursor-chat-provider-e76a   (OPEN → main)  “feat(models): Cursor chat provider adapter”
  ↑
PR #8  cursor/cursor-plan-c-polish-7d86  (DRAFT → PR #2 branch)  STALE — superseded
  ↑
       cursor/merge-upstream-pr8-91e4      (NO PR yet)  CANONICAL WORKING LINE
```

### What each line contains

| Ref | Branch | PR | vs `main` | Notes |
|-----|--------|-----|-----------|--------|
| **Canonical** | `cursor/merge-upstream-pr8-91e4` | — | ~320 commits | PR #2 + PR #8 + upstream `main` rebase + Jun 2 fixes |
| **Umbrella** | `cursor/cursor-chat-provider-e76a` | [#2](https://github.com/lawmight/odysseus/pull/2) | ~226 commits | Original adapter; **0 commits** only on PR #2 (merge branch is strict superset) |
| **Stale stack** | `cursor/cursor-plan-c-polish-7d86` | [#8](https://github.com/lawmight/odysseus/pull/8) | stacked on #2 | Plan C polish tip at `94d2f75`; **fully merged** into canonical branch |

### Jun 2 commits on canonical branch (after PR #8 merge)

| Commit | Summary |
|--------|---------|
| `37bd1da` | `merge: upstream main + PR #8 Cursor Plan C` |
| `d0287b4` | merge fix: drop stale `_anthropic_models_url`; probe test alignment |
| `c38daa3` | **Fix:** Cursor models missing from chat picker (`/api/models` dict crash) |
| `5e61861` | **Fix:** Cursor image attachments → SDKImage (not Vision sidecar); no `cursor://` HTTP fallback for task/auto-name |

### Validated on desk (2026-06-02)

- [x] Cursor endpoint + model picker
- [x] Chat streaming, follow-ups, new messages
- [x] Model switch mid-session
- [x] Usage in Cursor dashboard
- [x] Image **attach** + describe (SDKImage path)
- [ ] Stop/cancel mid-stream (implemented earlier; not re-tested this session)
- [ ] Agent mode + Cursor → blocked error (implemented; not re-tested this session)

---

## 3. Ship phases

### Phase 0 — Freeze scope (now)

**Goal:** Stop opening parallel Cursor integration PRs until canonical branch is folded into PR #2.

- Treat **`cursor/merge-upstream-pr8-91e4`** as the only integration branch for new Cursor Chat fixes.
- No new stacked PRs onto `cursor-plan-c-polish-7d86`.
- Plan B (Agent tab) and Cursor tool surfacing (`generateImage`, etc.) stay **out of this merge**.

**Exit:** Team agrees Plan A/C Chat BYOK scope is closed except merge hygiene.

---

### Phase 1 — GitHub housekeeping

**Goal:** Remove confusion from stale PR #8; document canonical branch on PR #2.

| Step | Action | Owner |
|------|--------|-------|
| 1.1 | **Close PR #8** with comment: *Superseded by `cursor/merge-upstream-pr8-91e4` (includes Plan C + picker + SDKImage fixes).* | Human |
| 1.2 | **Update PR #2 description** — add “Current integration tip: `cursor/merge-upstream-pr8-91e4`” and link to this plan. | Human / agent |
| 1.3 | Optional: delete or archive remote branch `cursor/cursor-plan-c-polish-7d86` after PR #8 closed (non-blocking). | Human |

**Exit:** One obvious integration story: PR #2 → `main`, fed by merge branch.

---

### Phase 2 — Fold canonical branch into PR #2

**Goal:** PR #2 diff against `main` reflects all Plan A/C work + upstream + Jun 2 fixes.

Pick **one** approach:

#### Option A — Replace PR #2 head (recommended)

```bash
git checkout cursor/cursor-chat-provider-e76a
git merge --ff-only cursor/merge-upstream-pr8-91e4
# or: git reset --hard cursor/merge-upstream-pr8-91e4  (if ff-only fails; coordinate first)
git push origin cursor/cursor-chat-provider-e76a
```

PR #2 updates automatically; CI runs on the full stack.

#### Option B — Stacked PR (merge branch → PR #2 branch)

Open **new PR**: `cursor/merge-upstream-pr8-91e4` → `cursor/cursor-chat-provider-e76a`.  
Merge when green; then PR #2 → `main` as today.

**Exit:** `cursor/cursor-chat-provider-e76a` tip equals (or matches) `cursor/merge-upstream-pr8-91e4`.

---

### Phase 3 — Pre-merge checklist (PR #2 → `main`)

**Goal:** Merge only when integration is reviewable and green.

| Check | Command / note |
|-------|----------------|
| Tests | `pytest tests/test_cursor_adapter.py tests/test_cursor_chat_tool_events.py tests/test_model_routes.py -q` |
| Full suite | `pytest` (or CI) |
| Manual smoke | Cursor endpoint → chat → follow-up → attach image → model switch |
| Agent guard | Agent mode + Cursor endpoint → clear error (not silent failure) |
| Docs | README Cursor section matches behavior; Plan C status note in [README](./README.md) |
| Diff size | Expect large PR (~17k+ lines vs early PR #2); reviewer guidance in PR body |
| No secrets | No `CURSOR_API_KEY` in commits; `data/` gitignored |

**Exit:** PR #2 approved + CI green → merge to `main`.

---

### Phase 4 — Post-merge cleanup

| Step | Action |
|------|--------|
| 4.1 | Delete merged branches: `cursor/merge-upstream-pr8-91e4`, `cursor/cursor-plan-c-polish-7d86` (optional) |
| 4.2 | Update [docs/plans/README.md](./README.md) status: “Shipped on `main` as of …” |
| 4.3 | Mark Plan A/C docs **Status: Shipped** (or link to release commit) |

---

## 4. What is *not* in this merge

| Item | Plan | When |
|------|------|------|
| Cursor **`generateImage`** in chat UI | Plan C+ / tools plan (§6) | After merge |
| Full Cursor **Agent tab** (tools, MCP cards) | Plan B | Separate PR |
| Cloud Agents API (repos, PRs) | Out of scope | — |
| Compare / Research / utility on Cursor | Excluded by design | — |

---

## 5. Stale / historical refs (do not use for new work)

| Ref | Status |
|-----|--------|
| PR #7 `cursor/merge-upstream-cursor-provider-0330` | **Merged** — earlier rebase attempt |
| PR #3, #4 cloud-agent bootstrap | Merged / closed |
| PR #5 fix-cloud-install-script | Closed |
| PR #6 Plan C docs only | Closed (docs folded into stack) |
| `origin/cursor/cursor-chat-provider-e76a` @ Jun 1 | **Behind** canonical branch |

---

## 6. Follow-up: Cursor useful tools (Plan C+)

**Not part of A/C ship.** See [cursor-useful-tools-plan.md](./cursor-useful-tools-plan.md) for the full Plan C+ doc.

Handoff prompt when ready:

```
Implement Cursor useful tools (generateImage first) per docs/plans/cursor-useful-tools-plan.md.
Branch from main.
```

---

## 7. One-page summary

```text
DONE (Plan A/C Chat):  cursor/merge-upstream-pr8-91e4
STALE:                 PR #8 → close
UMBRELLA:              PR #2 → main (update head from merge branch, then merge)
LATER:                 Cursor generateImage + useful tools; Plan B Agent tab
```

---

## 8. Nia / repo verification log

| Claim | Source |
|-------|--------|
| PR #2 open, base `main` | `gh pr view 2` 2026-06-02 |
| PR #8 draft, base `cursor/cursor-chat-provider-e76a` | `gh pr view 8` 2026-06-02 |
| Merge branch ⊃ PR #2 ⊃ PR #8 | `git rev-list --count` on VM 2026-06-02 |
| Jun 2 fixes | commits `c38daa3`, `5e61861` on `cursor/merge-upstream-pr8-91e4` |
