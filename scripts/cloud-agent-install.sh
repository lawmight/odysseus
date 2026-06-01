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

_py_minor="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"

_venv_usable() {
  [[ -f venv/bin/activate ]] && [[ -x venv/bin/pip ]]
}

_ensure_python_venv_package() {
  if _venv_usable; then
    return 0
  fi
  if python3 -m venv /tmp/odysseus-venv-probe >/dev/null 2>&1 \
    && [[ -f /tmp/odysseus-venv-probe/bin/activate ]]; then
    rm -rf /tmp/odysseus-venv-probe
    return 0
  fi
  rm -rf /tmp/odysseus-venv-probe 2>/dev/null || true

  if command -v apt-get >/dev/null 2>&1; then
    echo "cloud-agent-install: installing python${_py_minor}-venv (required for pip in venv)…"
    sudo apt-get update -qq
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
      "python${_py_minor}-venv" tmux
    return 0
  fi

  echo "cloud-agent-install: python3-venv missing — install python${_py_minor}-venv and tmux, then re-run." >&2
  exit 1
}

_ensure_python_venv_package

if [[ -d venv ]] && ! _venv_usable; then
  echo "cloud-agent-install: removing broken venv (missing activate or pip — usually python3-venv was not installed)" >&2
  rm -rf venv
fi

if [[ ! -d venv ]]; then
  python3 -m venv venv
fi

if ! _venv_usable; then
  echo "cloud-agent-install: venv still broken after create; check python3-venv / disk space." >&2
  exit 1
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
    export ODYSSEUS_ADMIN_PASSWORD_FILE="data/admin-password.txt"
    install -d -m 700 data
    (umask 077 && printf '%s\n' "$ODYSSEUS_ADMIN_PASSWORD" > "$ODYSSEUS_ADMIN_PASSWORD_FILE")
    echo "cloud-agent-install: created admin password at $ODYSSEUS_ADMIN_PASSWORD_FILE (value not logged)"
  else
    echo "cloud-agent-install: using ODYSSEUS_ADMIN_PASSWORD from environment (value not logged)"
  fi
  python setup.py
fi

echo "cloud-agent-install: OK (venv + cursor-sdk + optional deps)"
