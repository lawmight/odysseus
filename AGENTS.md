# AGENTS.md

## Cursor Cloud specific instructions

Odysseus is a **Python 3.11+ FastAPI** app with a static JS frontend (no frontend build step). See `README.md` for full product docs.

### Services (Docker Compose — recommended)

| Service | Port | Purpose |
|---------|------|---------|
| **odysseus** | 7000 | Main app (UI + API) |
| **chromadb** | 8100 (host) | Vector memory / skills |
| **searxng** | 8080 (localhost only) | Web search |
| **ntfy** | 8091 | Push reminders (optional) |

On Cloud VMs, Docker often requires `sudo` and the daemon may be stopped on boot:

```bash
sudo service docker start
cp .env.example .env   # first time only
sudo docker compose up -d --build
```

Healthy vector memory logs should include `ChromaDB connected` and `MemoryVectorStore initialized` (`sudo docker compose logs odysseus`).

### Manual dev (without rebuilding the app container)

```bash
source venv/bin/activate
uvicorn app:app --host 0.0.0.0 --port 7000
```

Point `CHROMADB_HOST` / `CHROMADB_PORT` at a running Chroma instance (Compose maps **8100→8000** on the host). SearXNG should be reachable at `http://localhost:8080` unless you change `SEARXNG_INSTANCE` in `.env`.

### Auth for local testing

After `python setup.py`, credentials live in `data/auth.json`. Initial admin password is printed once on first create. Re-running setup skips user creation if `auth.json` exists.

### Lint

No project-wide linter is configured.

### Tests

```bash
source venv/bin/activate
pytest
```

Optional JS-related tests: `pytest tests/test_compare_js.py` (needs Node). Bombadil E2E: see `tests/bombadil-spec.ts` and `npm install`.

### Build

- **Docker image:** `sudo docker compose build`
- **Frontend:** none (static files under `static/`)

### Gotchas

- **Docker socket permissions:** use `sudo docker compose …` if you see `permission denied` on `/var/run/docker.sock`.
- **LLM features** need a configured provider in Settings (or env); the stack runs without one, but chat/agent/research will not generate until configured.
- **Cookbook on Linux** needs `tmux` on the host for background downloads/serves.
- Pip installs in `venv` do not hot-reload inside a running Odysseus **container**; rebuild/restart the container after dependency changes when using Compose.
