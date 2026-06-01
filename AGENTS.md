# AGENTS.md — Odysseus on Cursor Cloud Agents

Guide for humans and agents working in this repo on **Cursor Cloud** (desktop VM or headless).

Odysseus is a **Python 3.11+ FastAPI** app with a static JS frontend (no frontend build step). See `README.md` for full product docs.

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

If you only see `ALLOW_VERCEL_CHAT`, then **`CURSOR_API_KEY` is not registered for this Cloud Agent environment** — even if you created a key elsewhere.

### Fix (dashboard — ~2 minutes)

1. Open [Cloud Agents setup](https://cursor.com/dashboard/cloud-agents) (or **Cursor Settings → Cloud Agents → your environment → Secrets**).
2. Add a secret with **Name** exactly: `CURSOR_API_KEY`  
   **Value**: your key from [Integrations](https://cursor.com/dashboard/integrations) (`key_…` format).
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
for req in requirements-optional.txt requirements-cursor.txt; do
  [[ -f "$req" ]] && python -m pip install -r "$req"
done
[[ -f package.json ]] && command -v npm >/dev/null && npm install --no-audit --no-fund
if [[ ! -f data/auth.json ]]; then
  export ODYSSEUS_ADMIN_PASSWORD="${ODYSSEUS_ADMIN_PASSWORD:-odysseus-$(openssl rand -hex 16 2>/dev/null || python3 -c 'import secrets; print(secrets.token_hex(16))')}"
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
- Installs `requirements.txt`, `requirements-optional.txt`, and **`requirements-cursor.txt`** (`cursor-sdk`)
- Runs `npm install` if Node is present
- Runs `python setup.py` once if `data/auth.json` is missing

You do **not** need to hand-run `pip install -r requirements-cursor.txt` if `install` has already succeeded — check:

```bash
source venv/bin/activate && python -c "import cursor_sdk; print('cursor-sdk OK')"
```

To change bootstrap behavior, edit `scripts/cloud-agent-install.sh` and commit; the next Cloud Agent boot re-runs `install`.

Optional **`start`** / **`terminals`** in `environment.json` call `scripts/cloud-agent-services.sh` to bring up Docker sidecars and uvicorn (see below).

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

### Auth for local testing

After `python setup.py`, credentials live in `data/auth.json`. Initial admin password is printed once on first create. Re-running setup skips user creation if `auth.json` exists.

### Lint

No project-wide linter is configured.

### Tests

```bash
source venv/bin/activate
pytest
```

Cursor-specific: `pytest tests/test_cursor_adapter.py tests/test_model_routes.py -q`

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

## Cursor chat provider (Plan A)

- Install: `requirements-cursor.txt` (included in `cloud-agent-install.sh`)
- Admin: **Settings → Model Endpoints → Cursor (local)**, workspace under `CURSOR_ALLOWED_WORKSPACE_ROOTS` (default: repo root)
- Chat mode only; Agent tab still uses OpenAI-compatible / Anthropic endpoints

See plan docs on branch `origin/cursor/plan-docs-efe9` under `docs/plans/`.

---

## One-time VM packages

If `python3 -m venv` fails:

```bash
sudo apt-get update && sudo apt-get install -y python3.12-venv tmux
```

Cookbook background jobs need `tmux`.
