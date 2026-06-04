# Contributing to Odysseus

Thanks for helping. The project is moving quickly, so the best contributions are focused, easy to review, and easy to test.

## Before You Start

- Search existing issues and pull requests before opening a new one.
- Prefer one bug fix or feature per pull request.
- Avoid broad rewrites, formatting-only changes, or moving many files unless the issue is specifically about structure.
- If you want to work on a large feature, open an issue first and describe the approach.

## Setup

Docker is the recommended path for normal testing:

```bash
git clone https://github.com/pewdiepie-archdaemon/odysseus.git
cd odysseus
cp .env.example .env
docker compose up -d --build
```

Manual development uses Python 3.11+ (CI uses 3.12):

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app:app --host 0.0.0.0 --port 7000
```

Windows is not actively tested. Docker on Linux or a Linux/macOS manual install is the safer path for now.

## Running Checks

Run the smallest relevant checks for your change, or use the combined preflight script:

```bash
bash scripts/scaffold-pr-body.sh --issue NNNN --summary "What changed and why" -o pr-body.md
node scripts/validate-pr-body.js --explain pr-body.md   # same rules as the PR description bot
bash scripts/ci-preflight.sh --fork --require-pr-body   # uses pr-body.md when present
bash scripts/ci-preflight.sh --upstream                 # upstream-oriented (see docs/guides/UPSTREAM_PR_GUIDELINES.md)
```

Optional: install `scripts/git-hooks/pre-push-pr-body.sample` as `.git/hooks/pre-push` to validate `pr-body.md` before every push.

Individual commands:

```bash
python -m pytest
python -m py_compile app.py routes/*.py src/*.py
node --check static/js/<file-you-changed>.js
```

For Docker-related changes:

```bash
docker compose config
docker compose up -d --build
docker compose logs --tail=120 odysseus
```

Mention what you ran in the pull request description. If you could not run a check, say so.

## Continuous Integration

Every pull request to `main` runs [GitHub Actions](.github/workflows/) checks:

| Check | Workflow | What it does |
|-------|----------|--------------|
| `test` | [ci.yml](.github/workflows/ci.yml) | Full `pytest` suite (Python 3.12, Node 20 for JS tests) |
| `syntax` | [ci.yml](.github/workflows/ci.yml) | `py_compile` on Python modules; `node --check` on `static/js/*.js` |
| `secrets` | [ci.yml](.github/workflows/ci.yml) | Scans for committed API keys and tokens ([scripts/ci-secret-scan.sh](scripts/ci-secret-scan.sh)) |
| `docker-config` | [docker.yml](.github/workflows/docker.yml) | `docker compose config` |
| `docker-build` | [docker.yml](.github/workflows/docker.yml) | `docker build` for the Odysseus image |

Dependabot opens weekly PRs for Python, npm, and Docker base image updates ([dependabot.yml](.github/dependabot.yml)).

### Branch protection (maintainers)

After workflows are enabled on GitHub, configure **Settings → Branches → `main`**:

**Required status checks**

- `test`
- `syntax`
- `secrets`
- `docker-config`
- `docker-build`

**Cursor Bugbot (optional)**

- Add the `Cursor Bugbot` check if you want every PR to receive an AI review.
- By default Bugbot reports `neutral` when it finds issues — it does **not** block merge unless you enable **fail on unresolved issues** in the [Bugbot dashboard](https://cursor.com/docs/bugbot).
- Odysseus-specific review rules live in [`.cursor/BUGBOT.md`](.cursor/BUGBOT.md).

**Recommended review stack**

- **CI** — deterministic merge gate (tests, syntax, secrets, Docker).
- **Bugbot** — primary AI PR reviewer (bugs, security, Odysseus invariants).
- **Thermos / thermo-nuclear skills** — optional pre-PR maintainability audit in Cursor for large changes.
- **Human review** — product intent, UX, and operational sign-off.

Do not enable multiple general AI PR reviewers (CodeRabbit, Cubic, Graphite AI, etc.) on the same repo while Bugbot is active — they duplicate comments without adding coverage CI and Bugbot already provide.

Manual smoke (not on every PR): trigger the `docker-smoke` job via **Actions → Docker → Run workflow**.

## Pull request guides

- [Upstream PR guidelines](docs/guides/UPSTREAM_PR_GUIDELINES.md) — the five description checks, scaffold workflow, Cloud Agent video demos, fork vs upstream.
- [CI parity report](docs/guides/CI_PARITY.md) — auto-generated comparison with `pewdiepie-archdaemon/odysseus` (run `bash scripts/ci-parity-report.sh` to refresh).

## Pull Requests

Good pull requests usually include:

- A short explanation of the bug or feature.
- The files or areas changed.
- Manual test steps or automated test results from running the actual app, not just the test suite.
- Screenshots or short recordings for UI changes.
- Links to related issues, for example `Fixes #123`.

Please keep PRs small. Large PRs that mix unrelated cleanup, formatting, refactors, and behavior changes are much harder to review.

> **Auto-generated PRs.** If you are running an LLM agent (Devin, Cursor, OpenHands, Claude Code, etc.) against this repo: please open an issue describing the problem first instead of opening a PR directly. Bulk agent-generated PRs that don't match the project's visual style or contribution format will be closed without review, even when the underlying fix is correct.

## Style and visual changes

Odysseus has an intentional visual style. PRs that ignore it will be closed without merge, no matter how correct the underlying code is.

Before submitting any change that affects what the app looks like — buttons, icons, fonts, colors, spacing, layout, CSS, HTML, SVG, or any `static/js/` module that draws to the DOM — please:

1. **Run the app locally** and view the change in a browser. Type-checks and unit tests are not enough.
2. **Attach a screenshot or short clip** of the change in the running app. Add a mobile screenshot too if the change affects mobile.
3. **Match the existing visual language.** Specifically:
   - Reuse existing CSS variables (`--red`, `--fg`, `--bg`, `--card`, `--border`, …). Do not introduce new color values, font sizes, or spacing units.
   - Reuse existing button, input, card, and border classes. Don't invent parallel styling for similar widgets.
   - **No Unicode emoji in UI or code.** Use inline SVG (matching the monochrome icon style already in `static/index.html`) or plain text.
   - Monospaced font (`Fira Code`) for primary UI text. Don't override.
   - Dark theme is the default; any light-mode work goes through the existing theme system, not hard-coded.
4. **Don't add parallel components.** If a similar widget already exists in the app, extend it instead of writing a new one.

If you are unsure whether a change is "visual," it is. Default to attaching a screenshot.

## Issue Reports

For bugs, include:

- Install method: Docker, manual Python, WSL, etc.
- OS, browser, and device if relevant.
- Exact steps to reproduce.
- Expected behavior and actual behavior.
- Logs, screenshots, or terminal output.

For model-serving issues, include:

- Backend: Ollama, vLLM, SGLang, llama.cpp, LM Studio, etc.
- Model name.
- GPU/CPU and operating system.
- Cookbook task logs or server logs.

Issues with only "help", "does not work", or a screenshot without context may be closed as not actionable.

## Security

Do not post secrets, API keys, private logs, personal documents, or public IPs in issues or pull requests.

For security reports, follow [SECURITY.md](SECURITY.md).

