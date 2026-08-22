# Odysseus Cursor — today test checklist

**Goal today:** dogfood the Cursor build end-to-end. Unpolished OK. Fix only blockers that stop you using it.

**Instance (this box)**

| | |
|---|---|
| URL | http://127.0.0.1:7000 |
| Path | `~/odysseus` |
| Service | `odysseus.service` / helper `odysseus-cursor` |
| Admin user | `tomcoustols` |
| Stock (ignore today) | `~/odysseus-standard` :7001 — leave off |

**Helpers**

```bash
odysseus-cursor status
odysseus-cursor health
# restart only if needed:
odysseus-cursor restart
```

**Pass rule:** check the box only when you personally saw it work. Note fails in the Notes section at the bottom.

---

## 0. Preflight (5 min)

- [ ] `odysseus-cursor health` → `{"status":"healthy",...}`
- [ ] `systemctl --user is-active odysseus.service` → `active`
- [ ] Browser: open http://127.0.0.1:7000 (not 7001)
- [ ] Login as `tomcoustols` (reset password via agent if locked out — don't invent a password)
- [ ] Confirm shell has Cursor key available for setup if needed:  
      `[ -n "$CURSOR_API_KEY" ] && echo "key ok len=${#CURSOR_API_KEY}"`  
      (Key lives in Hermes env; UI may need you to paste Dashboard → Integrations key into the Cursor endpoint.)

---

## 1. Cursor endpoint setup (10–15 min)

In the UI (Models / Endpoints / admin — wherever endpoints live):

- [ ] Create or open a **Cursor** endpoint
- [ ] Base / URL is local bridge style (`cursor://local` or whatever the UI shows for Cursor — not a fake OpenAI URL)
- [ ] API key saved (Cursor Dashboard → Integrations)
- [ ] **Probe / refresh models** succeeds (list not empty)
- [ ] Pick at least one real model from the list (e.g. composer / whatever the probe returns — don't invent slugs)
- [ ] Set **workspace / cwd** to a real folder you own (start simple: `/home/Tom/odysseus` or a tiny scratch dir)
- [ ] Save endpoint; reload page; endpoint still selected

**Blocker if fail:** model list empty, probe 401/403, or no Cursor provider in UI → stop and fix setup before chat.

---

## 2. Chat mode smoke (core proof)

- [ ] New chat, **Chat** mode (not Agent)
- [ ] Cursor endpoint + model selected
- [ ] Prompt: `Reply with exactly: odysseus-cursor-ok`  
      → stream completes, exact-ish reply, no hang
- [ ] Second turn in same thread: `What did I just ask you to reply?`  
      → context held (or note if Cursor sessions don't resume — record truth)
- [ ] **Stop / cancel** mid-stream works (start a longer prompt, hit stop)
- [ ] Error path: wrong key or empty key briefly → readable error, not silent spin (optional if you don't want to break the good key)

**Pass criteria:** one clean billable/subscription Chat turn. That's the spine.

---

## 3. Agent mode smoke (tool cards)

- [ ] Same or new session, switch to **Agent** mode on Cursor endpoint
- [ ] Prompt that forces a tool: e.g.  
      `In the workspace cwd, list the top-level files and name README.md if present. Do not invent paths.`
- [ ] UI shows **tool cards** (`tool_start` / `tool_output` style) — not Odysseus native bash loop only
- [ ] Final answer references real files from the workspace
- [ ] No crash / endless spinner; session still usable after

**Optional stretch (only if core Agent works):**

- [ ] Image tool path if Chat allowlists `generateImage` (skip if flaky)
- [ ] Resume / follow-up after Agent turn still works

---

## 4. Workspace / allowlist edge cases

- [ ] Valid cwd works (from §1)
- [ ] Rejected / blocked path behaves clearly (try something outside allowlist if UI has one — e.g. `/etc` or random path)
- [ ] Switch cwd to a second real project folder → one short Agent list-files prompt still works

---

## 5. Stability & box hygiene (while testing)

- [ ] After Chat + Agent: `free -h` still usable (note available MiB)
- [ ] `odysseus-cursor health` still healthy
- [ ] No second Odysseus on 7001 unless you started it on purpose
- [ ] If UI dies: `odysseus-cursor restart` → health green → login still works
- [ ] journal noise check (optional):  
      `journalctl --user -u odysseus.service -n 40 --no-pager`  
      → note real errors only (ignore routine rate-limit cleanup)

---

## 6. “I actually use it” (the point of today)

Do **three real tasks** in Odysseus Cursor (not smoke prompts). Check each when done:

- [ ] Task A: _______________________________ (e.g. summarize a local file / plan a small change)
- [ ] Task B: _______________________________
- [ ] Task C: _______________________________

After each: 1-line note — worked / quirk / blocker.

---

## 7. Capture quirks (don't fix everything today)

For each fail or weirdness, one line:

| # | What you did | What happened | Blocker? Y/N |
|---|--------------|---------------|--------------|
| 1 | | | |
| 2 | | | |
| 3 | | | |

Only fix **Y** blockers today. Park the rest.

---

## 8. End-of-day done bar (unpolished ship)

Call today a win if **all** of these are true:

- [ ] Login → Cursor endpoint → **Chat works**
- [ ] **Agent + tool card works** once
- [ ] ≥1 real task done in the app (from §6)
- [ ] Quirks table filled (even if empty)
- [ ] Decision locked (pick one):  
  - [ ] **Ship on SDK 0.1.9** for now (no cutover this week)  
  - [ ] **Schedule 1.0.26 cutover** later (don't start mid-dogfood unless Chat/Agent is broken on 0.1.9)

Optional pride:

- [ ] 1 screenshot of Chat or Agent working
- [ ] 5–10 line personal note: `docs/CURSOR_HOWTO.md` (start, model pick, known breaks)

**Out of scope today:** Hermes Cursor provider port, stock :7001, SDK major bump, MCP-from-DB, polish UI, money/Calendly.

---

## Notes (freeform)

```
date:
branch (git -C ~/odysseus status -sb):
sdk (pip show cursor-sdk | rg Version):
chat model used:
agent model used:
available RAM after tests:
```

---

## If you're stuck — ping Hermes with

1. Screenshot or exact error text  
2. Whether failure is login / endpoint probe / Chat / Agent  
3. `odysseus-cursor health` + last 20 journal lines (no secrets)
