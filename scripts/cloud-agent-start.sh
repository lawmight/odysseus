#!/usr/bin/env bash
# Cloud Agent startup: ODYSSEUS_RUNTIME=dev (default) | docker
# Default is host uvicorn + sidecars. Full Compose (including the odysseus
# app container) is opt-in via ODYSSEUS_RUNTIME=docker — that path waits on
# SearXNG healthchecks and is a common source of slow/failed Long-running
# agent launches when nested Docker is flaky.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

RUNTIME="${ODYSSEUS_RUNTIME:-dev}"
RUNTIME="${RUNTIME,,}"

DOCKER="docker"

_detect_docker() {
  DOCKER="docker"
  if ! docker info >/dev/null 2>&1; then
    if sudo docker info >/dev/null 2>&1; then
      DOCKER="sudo docker"
    fi
  fi
}

_start_dockerd() {
  sudo service docker start 2>/dev/null || true
  if docker info >/dev/null 2>&1 || sudo docker info >/dev/null 2>&1; then
    return 0
  fi
  if command -v dockerd >/dev/null 2>&1; then
    echo "Starting dockerd (may need sudo)…"
    sudo sh -c 'dockerd >/tmp/dockerd.log 2>&1 &'
    sleep 3
  fi
}

_compose_up() {
  # Cap wait so a stuck SearXNG healthcheck cannot block agent launch forever
  # (compose waits on depends_on: service_healthy before starting odysseus).
  local -a args=("$@")
  local timeout_s="${ODYSSEUS_COMPOSE_TIMEOUT:-180}"
  if command -v timeout >/dev/null 2>&1; then
    # timeout(1) returns 124 on expiry; treat that as a soft failure.
    if ! timeout "$timeout_s" $DOCKER "${args[@]}"; then
      local rc=$?
      echo "cloud-agent-start: docker compose timed out or failed (exit $rc, limit ${timeout_s}s)" >&2
      return "$rc"
    fi
    return 0
  fi
  $DOCKER "${args[@]}"
}

_cmd_start_docker() {
  _start_dockerd || true
  _detect_docker
  if ! $DOCKER info >/dev/null 2>&1; then
    echo "Docker unavailable — falling back to sidecars-only start (set ODYSSEUS_RUNTIME=dev explicitly)." >&2
    exec bash "$ROOT/scripts/cloud-agent-services.sh" start
  fi
  _compose_args=(compose up -d)
  if [[ "${ODYSSEUS_DOCKER_BUILD:-}" =~ ^(1|true|yes|on)$ ]]; then
    _compose_args+=(--build)
    echo "cloud-agent-start: docker compose up -d --build (ODYSSEUS_DOCKER_BUILD set)"
  else
    echo "cloud-agent-start: docker compose up -d (set ODYSSEUS_DOCKER_BUILD=1 to rebuild images)"
  fi
  if ! _compose_up "${_compose_args[@]}"; then
    echo "cloud-agent-start: full Compose failed — falling back to sidecars only." >&2
    $DOCKER compose up -d chromadb searxng ntfy || true
    echo "Sidecars attempted; use ODYSSEUS_RUNTIME=dev + host uvicorn if the app is down."
    return 0
  fi
}

_cmd_start_dev() {
  exec bash "$ROOT/scripts/cloud-agent-services.sh" start
}

_cmd_terminal() {
  case "$RUNTIME" in
    dev)
      exec bash "$ROOT/scripts/cloud-agent-services.sh" dev-server
      ;;
    docker)
      echo "cloud-agent-start: ODYSSEUS_RUNTIME=docker — app runs in Compose (port 7000). Terminal idle."
      exec sleep infinity
      ;;
    *)
      echo "cloud-agent-start: unknown ODYSSEUS_RUNTIME=$RUNTIME (expected docker or dev)" >&2
      exit 1
      ;;
  esac
}

cmd="${1:-start}"

case "$cmd" in
  start)
    case "$RUNTIME" in
      docker) _cmd_start_docker ;;
      dev) _cmd_start_dev ;;
      *)
        echo "cloud-agent-start: unknown ODYSSEUS_RUNTIME=$RUNTIME (expected docker or dev)" >&2
        exit 1
        ;;
    esac
    ;;
  terminal)
    _cmd_terminal
    ;;
  *)
    echo "Usage: $0 {start|terminal}" >&2
    echo "  ODYSSEUS_RUNTIME=dev|docker  (default: dev)" >&2
    echo "  ODYSSEUS_DOCKER_BUILD=1      rebuild images when runtime=docker" >&2
    echo "  ODYSSEUS_COMPOSE_TIMEOUT=180 max seconds for docker compose up" >&2
    exit 1
    ;;
esac
