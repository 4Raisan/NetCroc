#!/usr/bin/env bash
# NetCroc source setup for Linux and macOS. Does not change DNS or connect a VPN.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${NETCROC_PYTHON:-python3}"
if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo 'Python is missing. Install Python 3.12–3.14, then run this setup again.'
  echo 'macOS with Homebrew: brew install python@3.13 python-tk@3.13'
  echo 'Ubuntu/Debian: sudo apt install python3 python3-venv python3-tk'
  exit 1
fi
"$PYTHON" -c 'import sys; assert (3,12)<=sys.version_info[:2]<(3,15), "Python 3.12–3.14 is required"'
if ! "$PYTHON" -c 'import tkinter,venv' >/dev/null 2>&1; then
  echo 'Python GUI support is missing.'
  echo 'Ubuntu/Debian: sudo apt install python3-tk python3-venv'
  echo 'macOS with Homebrew: brew install python-tk@3.13; NETCROC_PYTHON=python3.13 ./NetCroc-Setup.sh'
  exit 1
fi
if [[ "${1:-}" == '--check' ]]; then echo 'Python, Tk and venv checks passed.';exit 0;fi
"$PYTHON" -m venv "$ROOT/.venv"
"$ROOT/.venv/bin/python" -m pip install --upgrade pip
"$ROOT/.venv/bin/python" -m pip install -r "$ROOT/src/requirements.txt"
"$ROOT/.venv/bin/python" -c 'import tkinter,PIL,psutil,paramiko,pystray,keyring'
echo 'NetCroc is ready. Optional: install wireguard-tools for WireGuard VPN.'
if [[ "$(uname -s)" == 'Darwin' ]]; then echo 'macOS: brew install wireguard-tools';else echo 'Ubuntu/Debian: sudo apt install wireguard-tools libsecret-1-0';fi
exec "$ROOT/.venv/bin/python" "$ROOT/src/app.py"
