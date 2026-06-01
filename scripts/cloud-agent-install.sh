#!/usr/bin/env bash
# Idempotent Cloud Agent / dev VM bootstrap for Odysseus.
# Referenced from .cursor/environment.json (runs at project root on each fresh agent).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! command -v python3 >/dev/null 2>&1; then
  echo "cloud-agent-install: python3 not found" >&2
  exit 1
fi

# venv (Cloud VMs sometimes lack python3-venv on first boot)
if ! python3 -m venv --help >/dev/null 2>&1; then
  echo "cloud-agent-install: python3-venv missing — run: sudo apt-get install -y python3.12-venv tmux" >&2
  exit 1
fi

if [[ ! -d venv ]]; then
  python3 -m venv venv
fi
# shellcheck disable=SC1091
source venv/bin/activate

python -m pip install -U pip wheel
python -m pip install -r requirements.txt -r requirements-optional.txt -r requirements-cursor.txt

if [[ -f package.json ]] && command -v npm >/dev/null 2>&1; then
  npm install --no-audit --no-fund
fi

# First-time data dir (no-op if auth.json already exists)
if [[ ! -f data/auth.json ]]; then
  if [[ -z "${ODYSSEUS_ADMIN_PASSWORD:-}" ]]; then
    export ODYSSEUS_ADMIN_PASSWORD="odysseus-$(openssl rand -hex 4 2>/dev/null || echo change-me)"
    echo "cloud-agent-install: created admin password (save it): ${ODYSSEUS_ADMIN_PASSWORD}"
  fi
  python setup.py
fi

echo "cloud-agent-install: OK (venv + cursor-sdk + optional deps)"
