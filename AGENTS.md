# AGENTS.md

## Cursor Cloud specific instructions

### What this repo is

Single-product **Odysseus** — FastAPI backend (`app.py` + `uvicorn`) and vanilla JS SPA in `static/`. User data lives under `data/` (gitignored). See `README.md` for feature overview and `docker-compose.yml` for the default bundled stack.

### One-time VM packages (not in the update script)

If `python3 -m venv` fails with `ensurepip is not available`:

```bash
sudo apt-get update && sudo apt-get install -y python3.12-venv tmux
```

**Docker** is required for ChromaDB, SearXNG, and ntfy as documented in README. In nested Cloud VMs, start the daemon once per session (if not already running):

```bash
sudo dockerd > /tmp/dockerd.log 2>&1 &
```

Use `sudo docker compose …` unless your user is in the `docker` group.

### Dependency refresh (automatic on VM startup)

Handled by the Cursor update script: recreate/use `venv`, `pip install` from `requirements.txt` + `requirements-optional.txt`, and `npm install` for Bombadil UI tests.

### Running supporting services (manual each session)

From repo root, after Docker is up:

```bash
sudo docker compose up -d chromadb searxng ntfy
```

- ChromaDB: `localhost:8100` (host) → vector memory
- SearXNG: `http://127.0.0.1:8080` (default web search)
- ntfy: `localhost:8091` (optional reminders)

Full stack including the app container: `sudo docker compose up -d --build` (see README).

### Running the dev server (manual)

```bash
cd /workspace   # or your clone path
source venv/bin/activate
export CHROMADB_HOST=localhost CHROMADB_PORT=8100
export SEARXNG_INSTANCE=http://127.0.0.1:8080
python setup.py   # first boot only; prints or uses ODYSSEUS_ADMIN_PASSWORD
uvicorn app:app --host 0.0.0.0 --port 7000
```

Open `http://localhost:7000`. Prefer tmux for long-running `uvicorn` (see Cloud Agent tmux rules).

Expected healthy startup log lines include `ChromaDB connected: localhost:8100` and `MemoryVectorStore initialized`. Without Chroma, the app still runs but memory vectors are degraded.

### Lint

No repo-wide ESLint/Ruff/Black config or CI lint job. Ad-hoc `eslint-disable` comments exist in some JS files only.

### Tests

```bash
source venv/bin/activate
export CHROMADB_HOST=localhost CHROMADB_PORT=8100
pytest
```

Optional UI E2E (needs app running + `npm install`): Bombadil spec in `tests/bombadil-spec.ts`.

As of setup verification: **261 passed**, 1 failure in `tests/test_model_routes.py::TestSetupProbeSafety::test_anthropic_probe_does_not_double_v1` (pre-existing mock/httpx issue).

### Smoke / hello-world

1. `GET /api/health` → `{"status":"healthy",...}`
2. `POST /api/auth/login` with admin credentials from `setup.py`
3. `POST /api/notes` then `GET /api/notes` (authenticated cookie session)

### Gotchas

- **Re-running `setup.py`** skips `auth.json` if it already exists; set `ODYSSEUS_ADMIN_PASSWORD` on first run to fix credentials.
- **Cookbook** on Linux needs `tmux` for background download/serve jobs.
- **LLM** is not bundled; chat/agent features need a configured provider in Settings (Ollama, OpenRouter, etc.).
- Bind to `127.0.0.1` instead of `0.0.0.0` when you only need local access (see README security notes).
