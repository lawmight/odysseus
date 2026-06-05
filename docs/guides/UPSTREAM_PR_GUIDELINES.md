# Upstream PR guidelines (lawmight fork)

How to open pull requests that match **pewdiepie-archdaemon/odysseus** maintainer expectations and pass **lawmight/odysseus** CI. Written for humans and Cursor Cloud Agents.

**Related:** [CI_PARITY.md](./CI_PARITY.md) (auto-generated gate comparison), [CONTRIBUTING.md](../../CONTRIBUTING.md), [`.github/pull_request_template.md`](../../.github/pull_request_template.md).

---

## Two targets, one habit

| Step | Fork PR (`lawmight/odysseus`) | Upstream PR (`pewdiepie-archdaemon/odysseus`) |
|------|-------------------------------|-----------------------------------------------|
| Preflight | `bash scripts/ci-preflight.sh --fork` | `bash scripts/ci-preflight.sh --upstream` |
| Issue link | Fork has **issues disabled** — use upstream issue `#NNN` in body | Open/search issues on **upstream** first |
| Automated gates | `test`, `syntax`, `secrets`, `docker-*`, Check PR description | Check PR description (+ manual checks per CONTRIBUTING) |
| Size | Small, focused | Same — upstream merges are usually 1–2 files |

**Rule of thumb:** Green on the fork is a **superset** of upstream’s automated bar today. Upstream still expects an issue-first workflow and a complete PR template.

---

## Evidence from merged upstream PRs

Sample: **50** recently merged PRs on `pewdiepie-archdaemon/odysseus` (2026-06-04).

| Pattern | Approx. share |
|---------|----------------|
| Title starts with `fix:` | ~76% |
| `≤2` files and `<150` additions | ~92% |
| Includes test changes | Very common for `routes/` / `src/` fixes |
| Touches `static/js/` | ~14/80 in a wider sample — always needs visual verification |

**Titles:** `fix(scope): …`, `fix: …`, `feat: …`, `docs: …`, `ci: …`. Avoid vague titles like “update code” or “misc fixes”.

**Anti-patterns seen in closed/rejected work (fork lessons):**

- PR body says “docs only” when runtime code changed ([#23](https://github.com/lawmight/odysseus/pull/23)).
- Template placeholders left in Summary / Linked Issue / How to Test.
- Huge merge branches without a single integration story.
- Multiple AI review bots duplicating Bugbot (see CONTRIBUTING).

---

## Before you open a PR

### Everyone

1. Search [upstream issues](https://github.com/pewdiepie-archdaemon/odysseus/issues) and [upstream PRs](https://github.com/pewdiepie-archdaemon/odysseus/pulls).
2. One bug or feature per PR; no drive-by refactors.
3. Run preflight (see below).
4. Scaffold and validate the PR body locally:

   ```bash
   bash scripts/scaffold-pr-body.sh --issue NNNN --summary "What changed and why" -o pr-body.md
   node scripts/validate-pr-body.js --explain pr-body.md
   ```

### LLM / Cloud Agents

Upstream CONTRIBUTING asks agents to **open an issue first** describing the problem, then a PR. Bulk auto-generated PRs that skip visual/style rules are closed without review.

For **Cursor-specific** work on the fork, also read [`.cursor/BUGBOT.md`](../../.cursor/BUGBOT.md), [docs/CURSOR_SDK_UPGRADES.md](../CURSOR_SDK_UPGRADES.md), and [docs/plans/README.md](../plans/README.md). Upstream only needs that context when you contribute Cursor adapter changes upstream.

---

## The five checks

The **Check PR description** workflow fails the PR (merge **UNSTABLE**) when any of these are missing. Local `node scripts/validate-pr-body.js` uses the same rules.

| # | Check | Requirement | Common failure |
|---|-------|-------------|----------------|
| 1 | **Summary** | ≥ 20 characters after stripping HTML comments | Placeholder text, or only "fix" / "docs only" |
| 2 | **Linked Issue** | `#NNN` or `/issues/NNN` in that section | Empty `Fixes #`; fork has issues disabled |
| 3 | **Type of Change** | At least one `- [x]` checkbox | All boxes left `[ ]` |
| 4 | **Checklist** | `- [x] I searched` present in body | Duplicate-search line not checked |
| 5 | **How to Test** | At least one numbered step (`1. …`) | "TBD", empty section, bullets only |

**Scaffold a passing body:**

```bash
bash scripts/scaffold-pr-body.sh --issue 1958 --summary "One paragraph: what changed and why." -o pr-body.md
node scripts/validate-pr-body.js --explain pr-body.md
bash scripts/ci-preflight.sh --fork --pr-body pr-body.md
```

Template source: [`.github/pr-body-scaffold.md`](../../.github/pr-body-scaffold.md). Optional git hook: `scripts/git-hooks/pre-push-pr-body.sample`.

## Required PR description (enforced by bot)

The workflow [`.github/scripts/check-pr-description.js`](../../.github/scripts/check-pr-description.js) runs on both repos. All five checks above must pass.

Copy structure from [`.github/pull_request_template.md`](../../.github/pull_request_template.md). Do not rely on auto-generated review summaries (Sourcery/Cubic/CodeRabbit) as your only description.

**Fork note:** Issues are disabled on `lawmight/odysseus`. Link **upstream** issue numbers (e.g. `Fixes pewdiepie-archdaemon/odysseus#1234` or `Part of #1234` if discussing upstream).

---

## Local preflight

```bash
# Full fork gate (default)
bash scripts/ci-preflight.sh --fork

# Upstream-oriented (skips Docker unless compose/Dockerfile changed on branch)
bash scripts/ci-preflight.sh --upstream

# Uses ./pr-body.md automatically when present, or pass --pr-body FILE
bash scripts/ci-preflight.sh --fork --require-pr-body
```

Refresh [CI_PARITY.md](./CI_PARITY.md):

```bash
bash scripts/ci-parity-report.sh
```

---

## Backend / API changes

- Add or update tests under `tests/` (upstream almost always does for behavior fixes).
- Run `python -m pytest -q --tb=short` (or full preflight).
- Run `python -m py_compile app.py routes/*.py src/*.py`.
- If you changed `static/js/*.js`, run `node --check` on those files.

---

## UI / visual changes

Required when you touch **HTML, CSS, `static/js/`**, or anything that changes what users see.

1. Run the app (`docker compose up` or `uvicorn` / Cloud Agent dev server on port **7000**).
2. Complete the **Visual / UI changes** section in the PR template (screenshot/clip, style match, no emoji in UI, etc.).
3. Add numbered **How to Test** steps that a reviewer can follow without your machine.

### Cursor Cloud Agent: video and screenshots in PRs

Videos and images are **in addition to** How to Test steps, not a replacement.

1. **Start Odysseus on the VM**

   ```bash
   bash scripts/cloud-agent-services.sh dev-server
   # or: source venv/bin/activate && uvicorn app:app --host 0.0.0.0 --port 7000
   ```

   See [AGENTS.md](../../AGENTS.md) for port forwarding (7000).

2. **Record** a short walkthrough (before/after for fixes). Save under the agent artifacts directory, e.g. `/opt/cursor/artifacts/` or your workspace artifacts path.

3. **Embed in the PR body** (paths are rewritten when the PR is created from a Cloud Agent):

   ```html
   ### Screenshots / clips

   <video src="/opt/cursor/artifacts/demo-my-feature.mp4" controls></video>

   <img alt="Settings after fix" src="/opt/cursor/artifacts/settings-model-count.png" />
   ```

4. **Mobile:** add a second capture only when layout is responsive or mobile-specific.

5. **Style:** reuse existing CSS variables and components; no Unicode emoji in UI; monochrome SVG icons per CONTRIBUTING.

---

## Fork vs upstream checklist

| Check | Fork | Upstream |
|-------|------|----------|
| `bash scripts/ci-preflight.sh` | `--fork` | `--upstream` |
| `node scripts/validate-pr-body.js` | Yes | Yes |
| Issue opened (agents) | On upstream repo | On upstream repo |
| Linked Issue in PR | Upstream `#NNN` | `Fixes #NNN` |
| pytest / syntax / secrets | CI enforced | Manual (CONTRIBUTING) |
| Docker config/build | CI enforced | Manual when Docker touched |
| UI clip/screenshot | Strongly recommended | Required for visual changes |
| Cursor plan docs | When changing adapter | Only if contributing Cursor upstream |

---

## Opening an upstream PR from the fork

1. Branch from current `main`, keep diff small.
2. Run `bash scripts/ci-preflight.sh --upstream`.
3. Push to **your fork**; open PR with **base** `pewdiepie-archdaemon/odysseus:main`.
4. Use a complete PR body (validate locally first).
5. Respond to `Check PR description` and maintainer review; do not merge until upstream approves.

After upstream merges, sync your fork’s `main` and re-run `bash scripts/ci-parity-report.sh` to detect new upstream workflows.

---

## Optional PR body template (minimal)

```markdown
## Summary

One paragraph: what changed and why (≥ 20 characters).

## Linked Issue

Fixes pewdiepie-archdaemon/odysseus#NNNN

## Type of Change

- [x] Bug fix (non-breaking — fixes a confirmed issue)

## Checklist

- [x] I searched open issues and PRs — this is not a duplicate.
- [x] This PR targets `main`
- [x] My changes are limited to the scope described above.
- [x] I actually ran the app and verified the change works end-to-end.

## How to Test

1. …
2. …

## Visual / UI changes

(Only if applicable — attach clip/screenshot below.)
```

---

## Maintainer labels (upstream)

When description checks are enabled, upstream may use: `ready for review`, `needs work`, `needs more info`. The bot applies them when labels exist; it does not create labels automatically.
