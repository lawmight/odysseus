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
python -m pip install -r requirements.txt
for req in requirements-optional.txt requirements-cursor.txt; do
  if [[ -f "$req" ]]; then
    python -m pip install -r "$req"
  else
    echo "cloud-agent-install: skipping missing optional requirements file: $req"
  fi
done

if [[ -f package.json ]] && command -v npm >/dev/null 2>&1; then
  npm install --no-audit --no-fund
fi

# First-time data dir (no-op if auth.json already exists)
if [[ ! -f data/auth.json ]]; then
  if [[ -z "${ODYSSEUS_ADMIN_PASSWORD:-}" ]]; then
    if command -v openssl >/dev/null 2>&1; then
      _pw_suffix="$(openssl rand -hex 16)"
    else
      _pw_suffix="$(python3 -c 'import secrets; print(secrets.token_hex(16))')"
    fi
    export ODYSSEUS_ADMIN_PASSWORD="odysseus-${_pw_suffix}"
    unset _pw_suffix
    echo "cloud-agent-install: created admin password in ODYSSEUS_ADMIN_PASSWORD (value not logged)"
  fi
  python setup.py
fi

echo "cloud-agent-install: OK (venv + cursor-sdk + optional deps)"
