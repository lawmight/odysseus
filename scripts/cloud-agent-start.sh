#!/usr/bin/env bash
# Cloud Agent startup: ODYSSEUS_RUNTIME=docker (default) | dev
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

RUNTIME="${ODYSSEUS_RUNTIME:-docker}"
RUNTIME="${RUNTIME,,}"

DOCKER="docker"

_truthy() {
  case "${1:-}" in 1|true|TRUE|yes|YES|on|ON) return 0 ;; *) return 1 ;; esac
}

_should_install_cursor() {
  if _truthy "${ODYSSEUS_INSTALL_CURSOR:-}"; then
    return 0
  fi
  if [[ -n "${CLOUD_AGENT_ALL_SECRET_NAMES:-}" ]] || [[ -n "${CURSOR_API_KEY:-}" ]]; then
    return 0
  fi
  return 1
}

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

_cmd_start_docker() {
  _start_dockerd || true
  _detect_docker
  if ! $DOCKER info >/dev/null 2>&1; then
    echo "Docker unavailable — set ODYSSEUS_RUNTIME=dev for host uvicorn without sidecars." >&2
    exit 1
  fi
  if _should_install_cursor; then
    export INSTALL_CURSOR=true
    if ! _truthy "${ODYSSEUS_DOCKER_BUILD:-}"; then
      export ODYSSEUS_DOCKER_BUILD=1
      echo "cloud-agent-start: INSTALL_CURSOR=true (Cloud Agent / ODYSSEUS_INSTALL_CURSOR); rebuilding image once"
    fi
  fi
  _compose_args=(compose up -d)
  if [[ "${ODYSSEUS_DOCKER_BUILD:-}" =~ ^(1|true|yes|on)$ ]]; then
    _compose_args+=(--build)
    echo "cloud-agent-start: docker compose up -d --build (ODYSSEUS_DOCKER_BUILD set)"
  else
    echo "cloud-agent-start: docker compose up -d (set ODYSSEUS_DOCKER_BUILD=1 to rebuild images)"
  fi
  $DOCKER "${_compose_args[@]}"
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
    echo "  ODYSSEUS_RUNTIME=docker|dev  (default: docker)" >&2
    echo "  ODYSSEUS_DOCKER_BUILD=1      rebuild images when runtime=docker" >&2
    exit 1
    ;;
esac
