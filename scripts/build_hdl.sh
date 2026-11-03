#!/usr/bin/env bash
# Build the Pluto HDL project and save utilization/timing reports.
# Usage: VIVADO_SETTINGS=/path/to/settings64.sh ./scripts/build_hdl.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
: "${VIVADO_SETTINGS:?set VIVADO_SETTINGS to .../Vivado/settings64.sh}"

# Vivado/Vitis settings scripts reference unset variables; relax nounset while sourcing
set +u
source "$VIVADO_SETTINGS"
set -u

PROJ="$ROOT/fw/hdl/projects/pluto"
make -C "$PROJ"

STAMP="$(date +%Y%m%d-%H%M)_$(git -C "$ROOT/fw/hdl" rev-parse --short HEAD)"
OUT="$ROOT/results/hdl/$STAMP"
vivado -mode batch -nojournal -nolog \
  -source "$ROOT/scripts/report_util.tcl" -tclargs "$PROJ/pluto.xpr" "$OUT"
echo "reports: $OUT"
