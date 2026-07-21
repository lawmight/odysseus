#!/usr/bin/env bash
# Helper for Cloud Agent terminals: Docker sidecars + optional uvicorn.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

DOCKER="docker"

_detect_docker() {
  DOCKER="docker"
  if ! docker info >/dev/null 2>&1; then
    if sudo docker info >/dev/null 2>&1; then
      DOCKER="sudo docker"
    fi
  fi
}

_detect_docker

_start_dockerd() {
  if docker info >/dev/null 2>&1 || sudo docker info >/dev/null 2>&1; then
    return 0
  fi
  if command -v dockerd >/dev/null 2>&1; then
    echo "Starting dockerd (may need sudo)…"
    sudo sh -c 'dockerd >/tmp/dockerd.log 2>&1 &'
    sleep 3
  fi
}

cmd="${1:-}"

case "$cmd" in
  start)
    _start_dockerd || true
    _detect_docker
    if $DOCKER info >/dev/null 2>&1; then
      $DOCKER compose up -d chromadb searxng ntfy
      echo "Sidecars up (Chroma 8100, SearXNG 8080, ntfy 8091)."
    else
      echo "Docker unavailable — app runs without vector memory / SearXNG sidecars."
      echo "Fix: sudo apt install docker.io && sudo usermod -aG docker \"\$USER\" (new session), or use dashboard snapshot with Docker."
    fi
    ;;
  dev-server)
    if [[ ! -f venv/bin/activate ]]; then
      echo "venv not found; run: bash scripts/cloud-agent-install.sh" >&2
      exit 1
    fi
    # shellcheck disable=SC1091
    source venv/bin/activate
    export CHROMADB_HOST="${CHROMADB_HOST:-localhost}"
    export CHROMADB_PORT="${CHROMADB_PORT:-8100}"
    export SEARXNG_INSTANCE="${SEARXNG_INSTANCE:-http://127.0.0.1:8080}"
    # 0.0.0.0 on Cloud VMs helps Cursor port forwarding reattach after client VPN
    # or routing changes (ERR_EMPTY_RESPONSE on localhost:7000). Override with
    # APP_BIND=127.0.0.1 if you need loopback-only on a shared host.
    _bind="${APP_BIND:-0.0.0.0}"
    _port="${APP_PORT:-7000}"
    # Leftover Compose `odysseus` from a prior ODYSSEUS_RUNTIME=docker boot steals
    # :7000 and makes the host uvicorn terminal exit immediately — Long-running
    # agents then look "stuck" with no UI. Stop only the app container; keep sidecars.
    _detect_docker
    if $DOCKER info >/dev/null 2>&1; then
      if $DOCKER compose ps --status running odysseus 2>/dev/null | grep -q odysseus; then
        echo "cloud-agent-services: stopping Compose odysseus so host uvicorn can bind :${_port}"
        $DOCKER compose stop odysseus >/dev/null || true
      fi
    fi
    exec uvicorn app:app --host "$_bind" --port "$_port"
    ;;
  *)
    echo "Usage: $0 {start|dev-server}" >&2
    exit 1
    ;;
esac
