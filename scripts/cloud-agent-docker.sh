#!/usr/bin/env bash
# Shared Docker bootstrap for Cloud Agent install/start.
# Nested Docker on Cursor VMs often needs: dockerd running, fuse-overlayfs,
# iptables-legacy, Compose v2 plugin, and sudo (ubuntu is frequently not in
# the docker group).
#
# Source this file; do not exec it.
# shellcheck shell=bash

# shellcheck disable=SC2034
ODYSSEUS_DOCKER="${ODYSSEUS_DOCKER:-docker}"

_odysseus_docker_info_ok() {
  docker info >/dev/null 2>&1 || sudo docker info >/dev/null 2>&1
}

_odysseus_detect_docker() {
  ODYSSEUS_DOCKER="docker"
  if docker info >/dev/null 2>&1; then
    return 0
  fi
  if sudo docker info >/dev/null 2>&1; then
    ODYSSEUS_DOCKER="sudo docker"
    return 0
  fi
  return 1
}

_odysseus_compose_available() {
  # Prefer Compose V2 plugin (`docker compose`). docker.io without
  # docker-compose-v2 makes `docker compose up -d` fail with exit 125
  # ("unknown shorthand flag: 'd'") and aborts Cloud Agent start under set -e.
  if command -v docker >/dev/null 2>&1; then
    if docker compose version >/dev/null 2>&1; then
      return 0
    fi
    if sudo docker compose version >/dev/null 2>&1; then
      return 0
    fi
  fi
  if command -v docker-compose >/dev/null 2>&1; then
    return 0
  fi
  return 1
}

# Run Compose against the repo. Usage: _odysseus_compose up -d chromadb …
# Soft-fails (returns non-zero) but never traps the caller unless they check.
_odysseus_compose() {
  if ! _odysseus_detect_docker; then
    return 1
  fi
  if docker compose version >/dev/null 2>&1 \
    || sudo docker compose version >/dev/null 2>&1; then
    # shellcheck disable=SC2086
    $ODYSSEUS_DOCKER compose "$@"
    return $?
  fi
  if command -v docker-compose >/dev/null 2>&1; then
    if [[ "$ODYSSEUS_DOCKER" == "sudo docker" ]]; then
      sudo docker-compose "$@"
    else
      docker-compose "$@"
    fi
    return $?
  fi
  echo "cloud-agent-docker: Compose v2 plugin missing (install docker-compose-v2)" >&2
  return 1
}

_odysseus_configure_nested_docker() {
  # Best-effort nested-Docker knobs from Cursor's cloud-agent Docker docs.
  if command -v fuse-overlayfs >/dev/null 2>&1; then
    if [[ ! -f /etc/docker/daemon.json ]] \
      || ! grep -q 'fuse-overlayfs' /etc/docker/daemon.json 2>/dev/null; then
      sudo mkdir -p /etc/docker
      printf '%s\n' '{' '  "storage-driver": "fuse-overlayfs"' '}' \
        | sudo tee /etc/docker/daemon.json >/dev/null || true
    fi
  fi
  if [[ -x /usr/sbin/iptables-legacy ]]; then
    sudo update-alternatives --set iptables /usr/sbin/iptables-legacy >/dev/null 2>&1 || true
    sudo update-alternatives --set ip6tables /usr/sbin/ip6tables-legacy >/dev/null 2>&1 || true
  fi
  if getent group docker >/dev/null 2>&1; then
    sudo usermod -aG docker "$(id -un)" 2>/dev/null || true
  fi
}

_odysseus_install_compose_plugin() {
  if _odysseus_compose_available; then
    return 0
  fi
  if ! command -v apt-get >/dev/null 2>&1; then
    return 1
  fi
  echo "cloud-agent-docker: installing Compose v2 plugin…"
  sudo apt-get update -qq || true
  # docker.io → docker-compose-v2; docker-ce → docker-compose-plugin
  if ! sudo DEBIAN_FRONTEND=noninteractive apt-get install -y docker-compose-v2; then
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y docker-compose-plugin || true
  fi
  _odysseus_compose_available
}

_odysseus_install_docker_packages() {
  if ! command -v apt-get >/dev/null 2>&1; then
    if command -v docker >/dev/null 2>&1 && command -v dockerd >/dev/null 2>&1; then
      return 0
    fi
    echo "cloud-agent-docker: docker/dockerd missing and apt-get unavailable" >&2
    return 1
  fi

  if ! command -v docker >/dev/null 2>&1 || ! command -v dockerd >/dev/null 2>&1; then
    echo "cloud-agent-docker: installing docker.io + fuse-overlayfs (needed for Chroma/SearXNG sidecars)…"
    sudo apt-get update -qq
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
      docker.io fuse-overlayfs iptables || {
      echo "cloud-agent-docker: apt install docker.io failed" >&2
      return 1
    }
  fi

  # Separate from docker.io so a missing compose package name never blocks dockerd.
  _odysseus_install_compose_plugin || true
  return 0
}

_odysseus_wait_docker() {
  local i
  for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
    if _odysseus_docker_info_ok; then
      return 0
    fi
    sleep 1
  done
  return 1
}

_odysseus_start_dockerd() {
  if _odysseus_docker_info_ok; then
    return 0
  fi
  sudo service docker start 2>/dev/null || true
  if _odysseus_wait_docker; then
    return 0
  fi
  if ! command -v dockerd >/dev/null 2>&1; then
    return 1
  fi
  echo "cloud-agent-docker: starting dockerd…"
  # Avoid duplicate daemons if a previous attempt is still coming up.
  if ! pgrep -x dockerd >/dev/null 2>&1; then
    sudo sh -c 'dockerd >/tmp/dockerd.log 2>&1 &'
  fi
  if _odysseus_wait_docker; then
    return 0
  fi
  echo "cloud-agent-docker: dockerd did not become ready; last log lines:" >&2
  sudo tail -n 40 /tmp/dockerd.log 2>/dev/null >&2 || true
  return 1
}

# Install (if needed), configure nested Docker, start daemon, set ODYSSEUS_DOCKER.
# Returns 0 when `docker info` works (with or without sudo).
_odysseus_ensure_docker() {
  _odysseus_install_docker_packages || true
  _odysseus_configure_nested_docker || true
  if _odysseus_start_dockerd && _odysseus_detect_docker; then
    if ! _odysseus_compose_available; then
      echo "cloud-agent-docker: warning — docker is up but Compose v2 is missing" >&2
    fi
    return 0
  fi
  _odysseus_detect_docker || true
  return 1
}
