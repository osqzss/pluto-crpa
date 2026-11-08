# T1 step 6: Delta and fs sweep, RX1 -> TX1 pass-through

Date: 2026-11-08, 10:59-11:50. Unit: second Pluto, serial 1044734c96050011f2ff2100408f4f2ac3. Reference: `results/t1_reference.md`. Procedure: `docs/pluto-crpa-plan.md`, Section 11, T1 step 6.

## Common settings
- Simulator: bladeRF x40, `./bladegps -e brdc3300.18n` (in `~/Work/bladeGPS`), TX gain 17 dB, restarted for every run, so each run starts at the same simulated time (2018/11/26 00:00:00). The bladeRF carrier at L1 is present in every run, as in the reference.
- RF path, confirmed by the user: bladeRF -> 40 dB -> 2-way splitter -> RX1, RX2. Pluto TX1 -> DC block -> u-blox M8T, no external attenuator.
- Pluto: RX gain manual 60 dB on both channels, TX1 attenuation 50 dB (`--tx-att 80`, then `tx 60`, `tx 50`; `--min-tx-att 50`), TX2 attenuation 89.75 dB. RX LO = TX LO = L1 + Delta.
- Receiver: u-blox M8T (SPG 3.01, protocol 18), cold start (`ubxtool -p COLDBOOT`) after the pass-through was at 50 dB. Raw log through gpsd, `gpspipe -R`.
- Control: the user ran `t1_passthrough.py --on` and typed the confirmation for each run; Claude Code started `bladegps`, the receiver log and the cold start. Every run ended with the safe state confirmed in its log and by `--check`.
- Analysis: `scripts/ubx_cn0.py <run>.ubx --skip 60 --ref results/t1_ref_20261107_123927.ubx`. The first 60 s of each log (about 30 s before the cold start plus acquisition) are dropped; C/N0 is averaged per PRN over the epochs where the SV is used in the fix. MON-HW is taken from 60 s into the log up to 20 s before its end (after `quit`). With this script the reference mean is 45.0 dB-Hz (G26 50.8, the table in `results/t1_reference.md` says 50.7; rounding).

## Results

| Run | Delta (MHz) | fs (MSPS) | bw (MHz) | TX LO leakage at | Mean C/N0 vs. reference (dB) | Range (dB) | 3D-fix epochs | AGC | Jamming ind. (mean, range) | ADC ch0/1 (dBFS) |
|---|---|---|---|---|---|---|---|---|---|---|
| A1 | +3 | 10 | 9 | 1578.42 | -2.74 | -2.1 to -3.0 | 153 | 2028 | 109 (92-114) | -41.2 |
| A2 | +3 | 16 | 9 | 1578.42 | -2.42 | -2.0 to -3.0 | 199 | 2028 | 104 (96-108) | -40.6 |
| A3 | +3 | 20 | 9 | 1578.42 | -2.50 | -2.1 to -3.0 | 158 | 2028 | 109 (94-115) | -40.6 |
| A4 | +3 | 30.72 | 9 | 1578.42 | -2.62 | -2.0 to -3.0 | 177 | 2028 | 103 (93-107) | -40.6 |
| B1 | +2 | 16 | 14 | 1577.42 | -2.52 | -2.0 to -3.0 | 175 | 1950 | **156 (89-162)** | -40.1 |
| B2 | +3 | 16 | 14 | 1578.42 | -2.59 | -2.0 to -3.0 | 178 | 2028 | 102 (96-108) | -40.1 |
| B3 | +4 | 16 | 14 | 1579.42 | -2.62 | -2.0 to -3.0 | 176 | 2106 | 104 (101-108) | -40.1 |
| B4 | +5 | 16 | 14 | 1580.42 | -2.78 | -2.1 to -3.0 | 154 | 2184 | 105 (99-111) | -40.2 |
| B5 | -3 | 16 | 14 | 1572.42 | -2.59 | -2.1 to -2.9 | 176 | 1950 | 104 (85-109) | -40.1 |
| A1' | +3 | 10 | 9 | 1578.42 | -2.83 | -2.2 to -3.0 | 180 | 2028 | 108 (103-115) | -41.4 |

All runs: 11 PRNs used (the same 11 as the reference), final numSV 11, hAcc 2.04-2.25 m, no ADC clipping at start or end. Reference: AGC 3432, jamming indicator 125-141. Run B on 2026-11-07 (Delta +3, fs 10, same path): -2.9 dB, AGC 2028.

Files: `results/t1_sweep_<run>.txt` (Pluto control log) and `results/t1_sweep_<run>.ubx` (raw receiver log); A1' is `A1r`.

## Findings
1. **C/N0 does not depend on fs, bandwidth or Delta in the ranges tested.** All runs are -2.4 to -2.8 dB against the reference, a spread of 0.4 dB, below the 1 dB C/N0 resolution of the receiver. A1 and A1' agree within 0.1 dB, so the setup did not drift over 50 min. All are inside the 3-5 dB limit.
2. **fs 10-30.72 MSPS (A1-A4, bw 9 MHz): no effect** on C/N0, AGC or the jamming indicator. **bw 9 vs. 14 MHz (A2 vs. B2): no effect.**
3. **Delta +2 MHz raises the MON-HW jamming indicator** to about 156, against 102-109 in every other run, with no C/N0 loss. B1 differs from B2 only in Delta, so the cause is the 2 MHz offset. The likely source is the TX LO leakage at L1 + 2 MHz, closer to the center of the receiver passband; the image at L1 + 2 Delta is a less likely source, since B3 puts the LO leakage at the same L1 + 4 MHz without a rise. Not confirmed by a spectrum measurement.
4. **AGC depends on Delta only.** AGC is reported in steps of 78 (1950 = 25 x 78, ..., 3432 = 44 x 78). It is one step higher (less in-band power) per 1 MHz from +2 to +5 MHz, and Delta -3 MHz gives the same value as +2 MHz, so the receiver band is not symmetric about L1 for this interference. AGC stays 16-19 steps below the reference in every run, which is the pass-through noise and has a larger effect than Delta.
5. LO leakage and image levels were not measured: the receiver shows only their effect. Only TX1 attenuation 50 dB was tested.

## Decision proposed
Keep **Delta = +3 MHz, fs = 10 MSPS, bw = 9 MHz** (plan Section 4.1): no setting tested is better by a margin the receiver can resolve, 10 MSPS has the lowest `l_clk` (20 MHz), and +3 MHz avoids the jamming indicator rise seen at +2 MHz. Delta +4 or +5 MHz lowers in-band power by one AGC step each, but needs bw > 10 MHz and fs > 10 MSPS. Avoid |Delta| <= 2 MHz. The user decides.
