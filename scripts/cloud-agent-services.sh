#!/usr/bin/env bash
# Helper for Cloud Agent terminals: Docker sidecars + optional uvicorn.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

DOCKER="docker"
if ! docker info >/dev/null 2>&1; then
  if sudo docker info >/dev/null 2>&1; then
    DOCKER="sudo docker"
  fi
fi

_start_dockerd() {
  if docker info >/dev/null 2>&1 || sudo docker info >/dev/null 2>&1; then
    return 0
  fi
  if command -v dockerd >/dev/null 2>&1; then
    echo "Starting dockerd (may need sudo)…"
    sudo dockerd >/tmp/dockerd.log 2>&1 &
    sleep 3
  fi
}

cmd="${1:-}"

case "$cmd" in
  start)
    _start_dockerd || true
    if $DOCKER info >/dev/null 2>&1; then
      $DOCKER compose up -d chromadb searxng ntfy
      echo "Sidecars up (Chroma 8100, SearXNG 8080, ntfy 8091)."
    else
      echo "Docker unavailable — app runs without vector memory / SearXNG sidecars."
      echo "Fix: sudo apt install docker.io && sudo usermod -aG docker \"\$USER\" (new session), or use dashboard snapshot with Docker."
    fi
    ;;
  dev-server)
    # shellcheck disable=SC1091
    source venv/bin/activate
    export CHROMADB_HOST="${CHROMADB_HOST:-localhost}"
    export CHROMADB_PORT="${CHROMADB_PORT:-8100}"
    export SEARXNG_INSTANCE="${SEARXNG_INSTANCE:-http://127.0.0.1:8080}"
    exec uvicorn app:app --host 127.0.0.1 --port 7000
    ;;
  *)
    echo "Usage: $0 {start|dev-server}" >&2
    exit 1
    ;;
esac
