#!/bin/bash
# T5b: generate the waveform set of docs/t5b_plan.md, Section 2.5, into tmp/t5b/
# (git-ignored). Each file has a .json sidecar and a .png PSD. About 1 min.
# Rates: 8 MSPS for group A (4 x the widest 2 MHz), 8.184 MSPS for PN (8 samples
# per chip), 16 MSPS for group W (10 MHz noise). Pulsed CW is a tone at +200 kHz
# from the centre, so t4_jammer.py --freq L1 puts it at L1 + 200 kHz as in T4/T5.
# The fast chirp and the 0.1 ms pulses are limited to +/- 1.2 MHz (--lowpass):
# their line spectrum and gating sidebands would otherwise reach the 8 MSPS edge
# and, at the Pluto, the low edge of the passband (L1 - 1.5 MHz).
# Usage: ./scripts/t5b_make_waveforms.sh [OUTDIR]
set -euo pipefail
cd "$(dirname "$0")/.."
OUT=${1:-tmp/t5b}
PY=.venv/bin/python
G=scripts/t5b_waveform.py
mkdir -p "$OUT"

gen() { echo "+ $*"; "$PY" "$G" "$@"; }

for b in 0.1 0.5 1 2; do
    gen noise --bw ${b}e6 --rate 8e6 --out "$OUT/N$b"
done
gen pn --rate 8.184e6 --out "$OUT/PN"
gen chirp --span 2e6 --period 10e-6 --rate 8e6 --lowpass 1.2e6 --out "$OUT/CH-f"
gen chirp --span 2e6 --period 1e-3 --rate 8e6 --out "$OUT/CH-m"
gen chirp --span 2e6 --period 100e-3 --rate 8e6 --out "$OUT/CH-s"
for p in 0.1 1 10 100; do
    lp=()
    [ "$p" = 0.1 ] && lp=(--lowpass 1.2e6)
    gen cw --offset 200e3 --rate 8e6 --pulse-period ${p}e-3 --duty 0.1 "${lp[@]}" --out "$OUT/P-CW-${p}ms"
    gen noise --bw 1e6 --rate 8e6 --pulse-period ${p}e-3 --duty 0.1 "${lp[@]}" --out "$OUT/P-N1-${p}ms"
done
for b in 5 10; do
    gen noise --bw ${b}e6 --rate 16e6 --length 0.5 --out "$OUT/N$b"
done
