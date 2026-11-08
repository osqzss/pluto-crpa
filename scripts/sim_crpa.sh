#!/usr/bin/env bash
# Simulate crpa_core with Vivado xsim against the model vectors (model/vectors/).
#   dp:   crpa_dp_tb on every vector case, with regular and irregular adc_valid
#   core: crpa_core_tb (AXI-Lite, CDC, muxes, flags), at two l_clk rates
# Regenerates the vectors first. Prints one PASS/FAIL line per run and exits non-zero
# on any failure.
# Usage: VIVADO_SETTINGS=/path/to/settings64.sh ./scripts/sim_crpa.sh [dp|core|all] [log]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
: "${VIVADO_SETTINGS:?set VIVADO_SETTINGS to .../Vivado/settings64.sh}"
WHAT="${1:-all}"
LOG="${2:-}"
[ -z "$LOG" ] || LOG="$(realpath -m "$LOG")"

set +u
source "$VIVADO_SETTINGS"
set -u

PY="$ROOT/.venv/bin/python"
[ -x "$PY" ] || PY=python3
"$PY" "$ROOT/model/gen_vectors.py" > /dev/null

LIB="$ROOT/fw/hdl/library"
RTL="$ROOT/ip/crpa_core/rtl"
TB="$ROOT/ip/crpa_core/tb"
VEC="$ROOT/model/vectors"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"

OUT="$WORK/summary.txt"
: > "$OUT"
fail=0

run() {   # snapshot, plusargs...
  local snap="$1"; shift
  local res
  res="$(xsim "$snap" -R --onfinish quit $(printf -- '-testplusarg %s ' "$@") 2>&1 | grep -E '^(PASS|FAIL|ERROR)' || true)"
  [ -n "$res" ] || res="FAIL no result line ($snap $*)"
  res="${res//$ROOT\//}"
  echo "$res" | tee -a "$OUT"
  echo "$res" | grep -q '^PASS' || fail=1
}

if [ "$WHAT" = dp ] || [ "$WHAT" = all ]; then
  xvlog "$RTL/crpa_dp.v" "$TB/crpa_dp_tb.v" > xvlog_dp.out 2>&1 || { cat xvlog_dp.out; exit 1; }
  xelab -debug off crpa_dp_tb -s dp_sim > xelab_dp.out 2>&1 || { cat xelab_dp.out; exit 1; }
  for c in unity corners random cw_loop; do
    run dp_sim "VEC=$VEC/$c" GAP=0
    run dp_sim "VEC=$VEC/$c" GAP=3 SEED=7
  done
fi

if [ "$WHAT" = core ] || [ "$WHAT" = all ]; then
  xvlog -i "$LIB/common" "$LIB/common/up_axi.v" "$LIB/common/up_xfer_cntrl.v" \
    "$LIB/common/up_xfer_status.v" "$RTL/crpa_dp.v" "$RTL/crpa_core.v" \
    "$TB/crpa_core_tb.v" > xvlog_core.out 2>&1 || { cat xvlog_core.out; exit 1; }
  xelab -debug off crpa_core_tb -s core_sim > xelab_core.out 2>&1 || { cat xelab_core.out; exit 1; }
  run core_sim "VEC=$VEC/core" LCLK_NS=16.276
  run core_sim "VEC=$VEC/core" LCLK_NS=50.000
fi

[ -z "$LOG" ] || cp "$OUT" "$LOG"
exit $fail
