# AGENTS.md — Odysseus on Cursor Cloud Agents

Guide for humans and agents working in this repo on **Cursor Cloud** (desktop VM or headless).

Odysseus is a **Python 3.11+ FastAPI** app with a static JS frontend (no frontend build step). See `README.md` for full product docs.

## Cursor Cloud specific instructions

Quick reference for agents on a prepared Cloud VM (after the `install` / update script). Secrets, Cursor provider, and PR workflow are documented in the sections below.

| Goal | Command |
|------|---------|
| Refresh Python/Node deps | `bash scripts/cloud-agent-install.sh` |
| Full stack (recommended) | `cp .env.example .env` then `sudo docker compose up -d --build` |
| Sidecars only + host app | `bash scripts/cloud-agent-services.sh start` then `bash scripts/cloud-agent-services.sh dev-server` |
| Tests | `source venv/bin/activate && python -m pytest -q` |
| Lint | None configured (see **Lint** below) |

**Runtime mode:** set `ODYSSEUS_RUNTIME` in the Cloud environment dashboard (no JSON edits):

| Value | Behavior |
|-------|----------|
| `dev` (default) | `start` brings up sidecars only; the **odysseus** terminal runs host `uvicorn` |
| `docker` | `start` runs full Compose stack on port **7000** (waits on SearXNG health; slower / flakier on nested Docker) |

Optional: `ODYSSEUS_DOCKER_BUILD=1` with `docker` mode runs `docker compose up -d --build` on boot (slower; use when images are stale). Prefer `dev` for Long-running Cloud Agents.

**UI:** `http://127.0.0.1:7000`. First-boot admin password is printed by `setup.py` (or in `docker compose logs odysseus` for Compose). User `admin` unless `ODYSSEUS_ADMIN_USER` is set. Rebuild/restart the `odysseus` container after changing Python deps in Compose mode.

**Docker on Cloud VMs:** Nested Docker needs `fuse-overlayfs` and `iptables-legacy` ([Cursor setup — Running Docker](https://cursor.com/docs/cloud-agent/setup#running-docker)). `scripts/cloud-agent-docker.sh` (sourced by install/start) installs `docker.io` when missing, configures fuse-overlayfs, starts `dockerd`, and prefers `sudo docker` when the user is not in the `docker` group. Verify with `sudo docker run --rm hello-world`. Logs should show `storage-driver=fuse-overlayfs` and `ChromaDB connected`. A notice that sidecars are skipped is **non-fatal** — Chat/Agent still run; only vector memory / SearXNG stay degraded.

**Port forwarding:** Dev server binds `0.0.0.0:7000` by default (`scripts/cloud-agent-services.sh dev-server`). After VPN/routing changes, re-forward port 7000 in Cursor if the browser shows `ERR_EMPTY_RESPONSE`.

## What you cannot expect the agent to do

| Task | Who does it |
|------|-------------|
| Add `CURSOR_API_KEY` to the Cloud Agent **Secrets** tab | **You** (Cursor dashboard) |
| Create or rotate API keys on cursor.com | **You** |
| Grant Docker socket access without `sudo` | **You** (snapshot / VM policy) or use `sudo docker` |
| See secrets added **after** this chat started | Start a **new** Cloud Agent run |

The agent reads `process.env` only. If `CURSOR_API_KEY` is missing there, live Cursor chat tests will be skipped.

## Secrets: why your API key might be invisible

On this VM, allowed secret names are exposed as:

```bash
echo "$CLOUD_AGENT_ALL_SECRET_NAMES"
```

If `CURSOR_API_KEY` is missing from that list, the VM did **not** receive it — even when the Cloud Agents dashboard **Secrets** table shows the row.

### Dashboard shows the secret, but the VM still does not

On some runs only **Personal**-scoped secrets are injected. Example: `ALLOW_VERCEL_CHAT` appears in `CLOUD_AGENT_ALL_SECRET_NAMES` and is set, while `CURSOR_API_KEY` was added with **Environment** scope and never appears in the list or in `env`.

**Workaround:** delete the Environment-scoped `CURSOR_API_KEY`, re-add it as **Personal** scope (same name and `key_…` value), then start a **new** Cloud Agent task and re-run the verify command below.

If Personal scope still fails, it is likely a Cursor platform issue — contact support with: secret visible in dashboard, `CLOUD_AGENT_ALL_SECRET_NAMES` omits it, fresh agent run.

### Fix (dashboard — ~2 minutes)

1. Open [Cloud Agents setup](https://cursor.com/dashboard/cloud-agents) (or **Cursor Settings → Cloud Agents → your environment → Secrets**).
2. Add a secret with **Name** exactly: `CURSOR_API_KEY`  
   **Value**: your key from [Integrations](https://cursor.com/dashboard/integrations) (`key_…` format). Prefer **Personal** scope if Environment-scoped secrets are not injected on your workspace.
3. Ensure the secret is attached to the **same environment** this repo uses (not only another team/repo group).
4. **Start a new Cloud Agent** (new task). Secrets are injected at VM boot; editing secrets mid-chat often does not update a running VM.

### Verify (agent or you in terminal)

```bash
test -n "$CURSOR_API_KEY" && echo "CURSOR_API_KEY is set (${#CURSOR_API_KEY} chars)" || echo "NOT SET"
```

Do **not** paste the key into chat or commit it to git. Use the Secrets tab or a local `.env` (gitignored).

### Optional: repo `.env` for local/desktop only

```bash
cp .env.example .env
# add CURSOR_API_KEY=key_...   (never commit)
```

Odysseus admin UI can also store the key on a **Model Endpoint** row (encrypted in `data/app.db`).

---

## Cloud environment dashboard install script

If you configure an environment at [Cloud Agents → Environments → Configure](https://cursor.com/dashboard/cloud-agents/environments) (e.g. `github.com/lawmight/odysseus`), the **Install script** field runs when the VM is prepared. It is separate from the repo’s [`.cursor/environment.json`](.cursor/environment.json) `install` hook (which runs again on each new agent if present).

**Replace the old three-line script** (`python3 -m venv` + `venv/bin/pip install -r requirements.txt` + `npm install`). On Ubuntu Cloud VMs it usually fails because **`python3.12-venv` is not installed**: `python3 -m venv` leaves a broken `venv/` (no `venv/bin/activate`, no pip), so every agent shows “install script failed”.

**Recommended dashboard script** (installs system packages, removes a broken venv, then runs the repo bootstrap):

```bash
set -euo pipefail
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y python3.12-venv tmux
if [[ -d venv ]] && [[ ! -f venv/bin/activate ]]; then rm -rf venv; fi
bash scripts/cloud-agent-install.sh
```

If `scripts/cloud-agent-install.sh` is not on your default branch yet, use this **inline** install instead:

```bash
set -euo pipefail
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y python3.12-venv tmux
[[ -d venv ]] && [[ ! -f venv/bin/activate ]] && rm -rf venv
python3 -m venv venv
source venv/bin/activate
python -m pip install -U pip wheel
python -m pip install -r requirements.txt
[[ -f requirements-optional.txt ]] && python -m pip install -r requirements-optional.txt
if [[ -n "${CLOUD_AGENT_ALL_SECRET_NAMES:-}" ]] || [[ -n "${CURSOR_API_KEY:-}" ]] || [[ "${ODYSSEUS_INSTALL_CURSOR:-}" =~ ^(1|true|yes|on)$ ]]; then
  [[ -f requirements-cursor.txt ]] && python -m pip install -r requirements-cursor.txt
fi
[[ -f package.json ]] && command -v npm >/dev/null && npm install --no-audit --no-fund
if [[ ! -f data/auth.json ]]; then
  python setup.py
fi
echo "install: OK"
```

After saving, **start a new Cloud Agent** (new task). Editing the script mid-chat does not fix VMs that already failed install.

---

## Startup script (`install` in `.cursor/environment.json`)

Cursor runs the **`install`** command from [`.cursor/environment.json`](.cursor/environment.json) on each fresh machine **before** the agent works:

```json
"install": "bash scripts/cloud-agent-install.sh"
```

That script (idempotent):

- Creates/uses `venv`
- Installs `requirements.txt` and `requirements-optional.txt` (warm-skips when `venv/.odysseus-install-stamp` matches)
- Installs **`requirements-cursor.txt`** (`cursor-sdk`) when a Cloud Agent env is detected (`CLOUD_AGENT_ALL_SECRET_NAMES`, `CURSOR_API_KEY`) or when `ODYSSEUS_INSTALL_CURSOR=1`
- Runs `npm install` if Node is present
- Runs `python setup.py` once if `data/auth.json` is missing (temp admin password printed to install logs)
- Force a full refresh with `ODYSSEUS_FORCE_INSTALL=1`

You do **not** need to hand-run `pip install -r requirements-cursor.txt` if `install` already installed cursor-sdk — check:

```bash
source venv/bin/activate && python -c "import cursor_sdk; print('cursor-sdk OK')"
```

To change bootstrap behavior, edit `scripts/cloud-agent-install.sh` and commit; the next Cloud Agent boot re-runs `install`.

**`start`** / **`terminals`** in `environment.json` call `scripts/cloud-agent-start.sh`, which reads **`ODYSSEUS_RUNTIME`**:

- **`dev`** (default): sidecars via `cloud-agent-services.sh start`; the **odysseus** terminal runs `dev-server` (host uvicorn). Stops a leftover Compose `odysseus` container if it holds port 7000.
- **`docker`**: full Compose stack (`docker compose up -d`; add `ODYSSEUS_DOCKER_BUILD=1` to rebuild). Soft-falls back to sidecars if Docker/compose fails or hits `ODYSSEUS_COMPOSE_TIMEOUT` (default 180s).

Set `ODYSSEUS_RUNTIME` in the Cloud environment dashboard so you do not edit JSON when switching modes.

### Long-running Cloud Agents (why launches feel stuck)

Cursor’s **Long-running** harness ([cursor.com/agents](https://cursor.com/agents) → model picker → Long-running) uses the same `.cursor/environment.json` hooks. Common launch pain on this repo:

1. **Stale / unused snapshot** — do **not** pin an old `snapshot` ID in `environment.json` unless you just saved it from the dashboard. A bad pin falls back to just-in-time boots (`build: null`) and re-runs heavy `install`. After a good agent run: Cloud Agents → Environments → save a new snapshot, then commit the new `snapshot` id (optional; `agentCanUpdateSnapshot` is enabled).
2. **`ODYSSEUS_RUNTIME=docker`** — full Compose waits on SearXNG health before starting `odysseus` (can sit ~2 minutes, then fail). Keep dashboard secret `ODYSSEUS_RUNTIME=dev` for Long-running work.
3. **Docker missing on JIT VMs** — without a saved snapshot, some pods have no `dockerd`. Install/start now apt-install `docker.io` + start the daemon. Plugin-cache `ENOENT` / noVNC `Press Ctrl-C to exit` lines in setup logs are Cursor platform noise, not Odysseus failures.
4. **Port 7000 fight** — leftover `workspace-odysseus-1` from a docker-mode boot blocks host uvicorn; `dev-server` now stops that container first.
5. **Empty chat after green setup** — if setup logs show `[START] Exit code: 0` but the agent never sends a first message (status `ERROR`, empty transcript), that is a Cursor platform attach failure (cancel + retry). Not fixed by repo scripts.

Verify a launch locally on the VM:

```bash
bash scripts/cloud-agent-install.sh   # expect warm skip on second run
ODYSSEUS_RUNTIME=dev bash scripts/cloud-agent-start.sh start
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:7000/api/auth/status
```

---

## Docker (Compose)

Odysseus does not require Docker for the Cursor adapter, but **vector memory** and **web search** expect services from `docker-compose.yml`.

| Service | Port | Purpose |
|---------|------|---------|
| **odysseus** | 7000 | Main app (UI + API) |
| **chromadb** | 8100 (host) | Vector memory / skills |
| **searxng** | 8080 (localhost only) | Web search |
| **ntfy** | 8091 | Push reminders (optional) |

On Cloud VMs, Docker often requires `sudo` and the daemon may be stopped on boot:

```bash
sudo service docker start   # or: sudo dockerd >/tmp/dockerd.log 2>&1 &
cp .env.example .env        # first time only
sudo docker compose up -d --build
```

Healthy vector memory logs should include `ChromaDB connected` and `MemoryVectorStore initialized` (`sudo docker compose logs odysseus`).

### Sidecars only (manual uvicorn on the host)

```bash
sudo docker compose up -d chromadb searxng ntfy
```

Or use the helper:

```bash
bash scripts/cloud-agent-services.sh start
```

Host ports: Chroma **8100**, SearXNG **127.0.0.1:8080**, ntfy **8091**. Compose maps Chroma **8100→8000** inside the network.

### Permission gotcha

If `docker ps` says *permission denied*, use `sudo docker …` or add your user to the `docker` group in a **snapshot** / custom environment. The agent cannot change group membership for you.

### App env when sidecars are up

```bash
export CHROMADB_HOST=localhost CHROMADB_PORT=8100
export SEARXNG_INSTANCE=http://127.0.0.1:8080
```

---

## Running Odysseus manually

```bash
source venv/bin/activate
export CHROMADB_HOST=localhost CHROMADB_PORT=8100
export SEARXNG_INSTANCE=http://127.0.0.1:8080
uvicorn app:app --host 127.0.0.1 --port 7000
```

Open `http://localhost:7000`. First boot: run `setup.py` or rely on `cloud-agent-install.sh`.

### Port forwarding and VPN (Cloud Agent UI)

Odysseus listens on port **7000**; [`.cursor/environment.json`](.cursor/environment.json) declares it for Cursor’s forwarder. The Cloud dev server binds **`0.0.0.0:7000`** (see `scripts/cloud-agent-services.sh dev-server`) so the tunnel can reconnect after client-side VPN or routing changes.

If the browser shows **ERR_EMPTY_RESPONSE** or “connection was reset” on `http://127.0.0.1:7000/` after a VPN profile switch:

1. Confirm the agent is running: `curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:7000/api/auth/status` on the VM (expect `200`).
2. In Cursor, open the **plug** icon (port forwarding) on the agent tab → close stale **7000** forwards → forward **7000** again (or toggle auto-forward).
3. Restart the dev server: `bash scripts/cloud-agent-services.sh dev-server` (or restart the `odysseus` terminal).

Set `APP_BIND=127.0.0.1` only if you intentionally want loopback-only on the VM.

### Auth for local testing

After `python setup.py`, credentials live in `data/auth.json`. Initial admin password is printed once on first create (Docker: `docker compose logs odysseus`). Re-running setup skips user creation if `auth.json` exists.

### Lint

No project-wide linter is configured.

### Pull requests (before `gh pr create` or ManagePullRequest)

Read [`.cursor/skills/fork-pr-ci/SKILL.md`](.cursor/skills/fork-pr-ci/SKILL.md) and run the scaffold workflow. The **Check PR description** workflow enforces five rules (Summary, Linked Issue, Type of Change, checklist, How to Test). See [docs/guides/UPSTREAM_PR_GUIDELINES.md](docs/guides/UPSTREAM_PR_GUIDELINES.md#the-five-checks).

```bash
bash scripts/scaffold-pr-body.sh --issue NNNN --summary "What changed and why (20+ chars)." -o pr-body.md
node scripts/validate-pr-body.js --explain pr-body.md
bash scripts/ci-preflight.sh --fork --require-pr-body
```

Do not paste Sourcery/Cubic/CodeRabbit summaries as the only PR body. `pr-body.md` is gitignored.

### Tests

```bash
source venv/bin/activate
python -m pytest -q
```

CI on every PR to `main` runs the full suite (see [CONTRIBUTING.md](CONTRIBUTING.md#continuous-integration)). For Cursor-only iteration:

```bash
pytest tests/test_cursor_adapter.py tests/test_model_routes.py tests/test_cursor_chat_tool_events.py tests/test_cursor_agent.py -q
```

Optional JS-related tests: `pytest tests/test_compare_js.py` (needs Node). Bombadil E2E: see `tests/bombadil-spec.ts` and `npm install`.

### Live Cursor smoke (needs `CURSOR_API_KEY`)

```bash
source venv/bin/activate
export CURSOR_API_KEY='key_…'   # or from Secrets tab
python - <<'PY'
import asyncio, os
from src.providers import cursor_adapter

async def main():
    key = os.environ["CURSOR_API_KEY"]
    print("models:", cursor_adapter.list_cursor_models(key)[:5])
    chunks = []
    async for c in cursor_adapter.stream_cursor_chat(
        "composer-2.5", [{"role": "user", "content": "Reply with exactly: pong"}], key, cwd="/workspace"
    ):
        chunks.append(c)
        if len(chunks) > 30: break
    print("".join(chunks[-3:]))

asyncio.run(main())
PY
```

### Build

- **Docker image:** `sudo docker compose build`
- **Frontend:** none (static files under `static/`)

### Gotchas

- **Docker socket permissions:** use `sudo docker compose …` if you see `permission denied` on `/var/run/docker.sock`.
- **LLM features** need a configured provider in Settings (or env); the stack runs without one, but chat/agent/research will not generate until configured.
- **Cookbook on Linux** needs `tmux` on the host for background downloads/serves.
- Pip installs in `venv` do not hot-reload inside a running Odysseus **container**; rebuild/restart the container after dependency changes when using Compose.

---

## Cursor provider (Chat + Agent)

| Install context | Cursor SDK |
|-----------------|------------|
| Core only | `pip install -r requirements.txt` — not included |
| Optional features | `+ requirements-optional.txt` |
| Cursor Chat | `+ requirements-cursor.txt` or `ODYSSEUS_INSTALL_CURSOR=1` during cloud install |
| Cloud Agent VM | Auto when Cloud Agent env is detected |
| Docker Compose | Not in the default image; optional `RUN pip install -r requirements-cursor.txt` in a custom layer |

- Install: `requirements-cursor.txt` (optional; auto on Cloud Agent VMs when env is detected)
- Admin: **Settings → Add Models → API → Cursor (local)** (hidden until SDK is installed), workspace under `CURSOR_ALLOWED_WORKSPACE_ROOTS` (default: repo root)
- Model listing uses the Cursor HTTP API; **Chat streaming** requires the SDK bridge on the Odysseus host
- **Chat** and **Agent** modes support Cursor when the session uses a Cursor endpoint. Agent mode renders Cursor tool calls as Agent tool cards, including `generateImage` gallery URLs via `/api/generated-image/...`.
- Cursor Agent MCP defaults to Cursor's workspace/user config (for example `.cursor/mcp.json`). Passing enabled Odysseus MCP DB rows to Cursor is disabled by default; set `cursor_agent_mcp_from_db: true` only after reviewing that MCP commands/URLs/env values are shared with the Cursor bridge/runtime.

See [`docs/plans/README.md`](docs/plans/README.md) for Cursor integration status and upstream staging branch. **Agent tab + Cursor** Phase 1 plus B2a–B3 follow-ups are shipped; Cloud Cursor agents remain out of scope.

**SDK upgrades:** [`docs/CURSOR_SDK_UPGRADES.md`](docs/CURSOR_SDK_UPGRADES.md) — bounded pin in `requirements-cursor.txt`; re-run the checklist before bumping. PyPI latest as of doc authoring: `0.1.6` (no newer release required an immediate code change).

---

## One-time VM packages

If `python3 -m venv` fails:

```bash
sudo apt-get update && sudo apt-get install -y python3.12-venv tmux
```

Cookbook background jobs need `tmux`.
