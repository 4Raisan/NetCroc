#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DEST="${HOME}/.local/bin"
mkdir -p -- "$DEST"
cp -- "$ROOT/NetCroc" "$DEST/NetCroc"
chmod 755 "$DEST/NetCroc"
printf 'Installed NetCroc to %s\nLaunch: %s\n' "$DEST" "$DEST/NetCroc"
