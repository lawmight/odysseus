#!/usr/bin/env bash
# Helper for Cloud Agent terminals: Docker sidecars + optional uvicorn.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# shellcheck disable=SC1091
source "$ROOT/scripts/cloud-agent-docker.sh"

cmd="${1:-}"

case "$cmd" in
  start)
    if _odysseus_ensure_docker; then
      # shellcheck disable=SC2086
      $ODYSSEUS_DOCKER compose up -d chromadb searxng ntfy
      echo "Sidecars up (Chroma 8100, SearXNG 8080, ntfy 8091)."
    else
      echo "cloud-agent-services: notice — Docker not ready; continuing without Chroma/SearXNG sidecars."
      echo "cloud-agent-services: Odysseus Chat/Agent still work; vector memory and web search stay degraded until Docker is available."
      if [[ -f /tmp/dockerd.log ]]; then
        echo "cloud-agent-services: see /tmp/dockerd.log for daemon errors."
      fi
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
    if _odysseus_detect_docker; then
      # shellcheck disable=SC2086
      if $ODYSSEUS_DOCKER compose ps --status running odysseus 2>/dev/null | grep -q odysseus; then
        echo "cloud-agent-services: stopping Compose odysseus so host uvicorn can bind :${_port}"
        # shellcheck disable=SC2086
        $ODYSSEUS_DOCKER compose stop odysseus >/dev/null || true
      fi
    fi
    exec uvicorn app:app --host "$_bind" --port "$_port"
    ;;
  *)
    echo "Usage: $0 {start|dev-server}" >&2
    exit 1
    ;;
esac
