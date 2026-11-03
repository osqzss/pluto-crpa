#!/usr/bin/env bash
# One-time setup: make the custom IP visible to the ADI hdl library.
# Usage: ./scripts/setup.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LIB="$ROOT/fw/hdl/library"

if [ ! -d "$LIB" ]; then
  echo "error: $LIB not found. Run 'git submodule update --init' in fw/ first." >&2
  exit 1
fi

ln -sfn "$ROOT/ip/crpa_core" "$LIB/crpa_core"

# Exclude the link from the hdl repository (do not commit it)
EXCL="$(git -C "$ROOT/fw/hdl" rev-parse --git-path info/exclude)"
case "$EXCL" in /*) ;; *) EXCL="$ROOT/fw/hdl/$EXCL" ;; esac
mkdir -p "$(dirname "$EXCL")"
grep -qx "library/crpa_core" "$EXCL" 2>/dev/null || echo "library/crpa_core" >> "$EXCL"

echo "linked: $LIB/crpa_core -> $ROOT/ip/crpa_core"
