#!/usr/bin/env bash
# Simulate the unmodified axi_ad9361 core with ip/crpa_core/tb/ad9361_if_tb.v, for both
# rx frame alignments, and print the facts recorded in docs/interface.md.
# Usage: VIVADO_SETTINGS=/path/to/settings64.sh ./scripts/sim_ad9361_if.sh [log file]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
: "${VIVADO_SETTINGS:?set VIVADO_SETTINGS to .../Vivado/settings64.sh}"
LOG="${1:-}"
[ -z "$LOG" ] || LOG="$(realpath -m "$LOG")"

# Vivado settings scripts reference unset variables; relax nounset while sourcing
set +u
source "$VIVADO_SETTINGS"
set -u

LIB="$ROOT/fw/hdl/library"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"

# Source list as in library/axi_ad9361/axi_ad9361_ip.tcl
SRC=()
for f in ad_rst ad_pnmon ad_dds_cordic_pipe ad_dds_sine_cordic ad_dds_sine ad_dds_2 ad_dds_1 \
         ad_dds ad_datafmt ad_iqcor ad_addsub ad_tdd_control ad_pps_receiver up_axi \
         up_xfer_cntrl up_xfer_status up_clock_mon up_delay_cntrl up_adc_common \
         up_adc_channel up_dac_common up_dac_channel up_tdd_cntrl; do
  SRC+=("$LIB/common/$f.v")
done
for f in ad_data_clk ad_data_in ad_data_out ad_dcfilter ad_mul; do
  SRC+=("$LIB/xilinx/common/$f.v")
done
for f in xilinx/axi_ad9361_lvds_if xilinx/axi_ad9361_cmos_if axi_ad9361_rx_pnmon \
         axi_ad9361_rx_channel axi_ad9361_rx axi_ad9361_tx_channel axi_ad9361_tx \
         axi_ad9361_tdd axi_ad9361_tdd_if axi_ad9361; do
  SRC+=("$LIB/axi_ad9361/$f.v")
done

XGLBL="$(dirname "$(command -v vivado)")/../data/verilog/src/glbl.v"
xvlog -i "$LIB/common" -i "$LIB/axi_ad9361" "${SRC[@]}" "$XGLBL" \
  "$ROOT/ip/crpa_core/tb/ad9361_if_tb.v" > xvlog.out 2>&1 || { cat xvlog.out; exit 1; }

STATUS=0
: > result.txt
for ALIGN in 0 1; do
  xelab -L unisims_ver -L unimacro_ver -generic_top "FRAME_ALIGN=$ALIGN" \
    -debug off -s "tb_$ALIGN" work.ad9361_if_tb work.glbl > xelab.out 2>&1 \
    || { cat xelab.out; exit 1; }
  xsim "tb_$ALIGN" -R > xsim.out 2>&1 || { cat xsim.out; exit 1; }
  grep -E '^(INFO |PASS |FAIL |RESULT )' xsim.out | grep -v 'INFO: ' >> result.txt
  echo >> result.txt
  grep -q '^RESULT PASS' xsim.out || STATUS=1
done

if [ -z "$LOG" ]; then cat result.txt; else tee "$LOG" < result.txt; fi
exit "$STATUS"
