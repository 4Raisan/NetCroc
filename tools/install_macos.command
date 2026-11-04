#!/bin/bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "$0")" && pwd)"
DEST="$HOME/Applications"
mkdir -p "$DEST"
/usr/bin/ditto "$ROOT/NetCroc.app" "$DEST/NetCroc.app"
echo "Installed NetCroc to $DEST/NetCroc.app. Open it from Finder; macOS may ask for approval."
