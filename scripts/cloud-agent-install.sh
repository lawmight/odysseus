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

if [[ -f requirements-optional.txt ]]; then
  python -m pip install -r requirements-optional.txt
else
  echo "cloud-agent-install: skipping missing optional requirements file: requirements-optional.txt"
fi

_cursor_installed=0
if _should_install_cursor && [[ -f requirements-cursor.txt ]]; then
  python -m pip install -r requirements-cursor.txt
  _cursor_installed=1
elif [[ -f requirements-cursor.txt ]]; then
  echo "cloud-agent-install: skipping requirements-cursor.txt (set ODYSSEUS_INSTALL_CURSOR=1 or use a Cloud Agent env to install)"
fi

if [[ -f package.json ]] && command -v npm >/dev/null 2>&1; then
  npm install --no-audit --no-fund
fi

# First-time data dir (no-op if auth.json already exists)
if [[ ! -f data/auth.json ]]; then
  python setup.py
fi

if [[ "$_cursor_installed" == 1 ]]; then
  echo "cloud-agent-install: OK (venv + optional deps + cursor-sdk)"
else
  echo "cloud-agent-install: OK (venv + optional deps)"
fi
