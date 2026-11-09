# T2-A: Fixed Weights [1,0] Through crpa_core, RX1 -> TX1

Date: 2026-11-09, 13:05-13:11. Unit: second Pluto (CRPA unit), Rev C, AD9363A, `mode=2r2t`. Firmware: linux `a26ff66`, hdl `ad150ddd5` (`results/t6a_dt_check.md`). Program: `sw/app/crpa_ctl` at parent `51ec026` (default `--rt 40`). Reference: `results/t1_reference.md`.

## Setup

- RF path, as in T1 (confirmed by the user): bladeRF -> 40 dB -> 2-way splitter -> RX1, RX2. Pluto TX1 -> DC block -> u-blox M8T, no external attenuator.
- Simulator: bladeRF x40, `./bladegps -e brdc3300.18n`, restarted for this run (same simulated start time as T1). The bladeRF carrier at L1 is present, as in the reference and T1.
- Pluto: `crpa_ctl run --on --tx-att 80 --min-tx-att 50 --mode fixed --w 1,0,0,0 --out /tmp/t2_A`, run by the user over `ssh -t` with the CONDUCTED confirmation, then `tx 60`, `tx 50`. Delta +3 MHz, fs 10 MSPS, bw 9 MHz, RX gain 60 dB manual on both, TX1 attenuation 50 dB, TX2 89.75 dB. crpa_core CTRL = COV_EN | DAC_SEL, TX `data_sel` 2 on all channels, w1 = 0x7FFF, w2 = 0, OUT_SHIFT 0, INT_LEN 10000 (1 ms).
- The only difference from T1 A1: the path goes through crpa_core (`data_sel` 2, `DAC_SEL`) instead of the AD9363 internal loopback (`data_sel` 8). With w1 = 0x7FFF, y = x1 bit exactly (`docs/fixed_point.md`).
- Sequence: user turned on and reached 50 dB; Claude Code started `bladegps` and `gpspipe -R`, sent `ubxtool -p COLDBOOT` about 30 s later, and the user quit about 4.5 min after the cold start. Safe state confirmed in the crpa_ctl log.

## Receiver (u-blox)

`scripts/ubx_cn0.py results/t2_A.ubx --skip 60 --cut 10 --ref results/t1_ref_20261107_123927.ubx`

| PRN | Reference | T2-A | Difference |
|---|---|---|---|
| G26 | 50.8 | 47.9 | -2.9 |
| G16 | 49.0 | 46.0 | -2.9 |
| G31 | 48.0 | 45.0 | -3.0 |
| G14 | 46.0 | 43.1 | -2.9 |
| G03 | 45.0 | 42.9 | -2.1 |
| G23 | 45.0 | 42.3 | -2.7 |
| G04 | 44.0 | 41.0 | -3.0 |
| G29 | 43.7 | 41.0 | -2.7 |
| G32 | 42.0 | 39.1 | -2.9 |
| G27 | 41.0 | 38.2 | -2.8 |
| G09 | 40.5 | 38.0 | -2.5 |

| | T2-A (crpa_core) | T1 A1 (loopback) | T1 A1' |
|---|---|---|---|
| Mean C/N0 vs. reference | **-2.76 dB** (-3.0 to -2.1) | -2.75 dB | -2.83 dB |
| 3D-fix epochs | 271 | 173 | 199 |
| Final numSV / hAcc | 11 / 2.06 m | 11 / 2.09 m | 11 / 2.22 m |
| AGC | 2028 | 2028 | 2028 |
| Jamming indicator (mean, range) | 108 (95-115) | 109 (92-114) | 108 (103-115 in the sweep table; 0-115 recomputed, a 0 at the start) |

T1 values recomputed with the same command; they agree with `results/t1_sweep.md` within 0.01 dB.

## crpa_core (`results/t2_A_every100.csv`, `results/t2_A.txt`)

- 433483 blocks in 433.5 s. One gap of 6 blocks at startup (set-up report, first block discarded); **none after it** with SCHED_FIFO 40, also during the `tx` commands.
- SAT_CNT 0 in every block; STATUS FRAME_ERR and RES_DROP never set; weights [0x7FFF, 0, 0, 0], OUT_SHIFT 0 throughout.
- Levels, 30 s means: x1 -42.56, x2 -42.94 dBFS before bladegps started (about 90 s after the start); -41.14 to -41.26 and -41.52 to -41.66 dBFS after. T1 A1: ADC ch0/1 -41.2 dBFS. Peak |x| at most 79 of 2047.
- The full CSV (46 MB) is kept locally as `results/t2_A.csv`, not committed; `t2_A_every100.csv` holds every 100th block.

## Analysis change

`scripts/ubx_cn0.py` gained `--cut DB`: the log is kept up to the last epoch whose mean C/N0 over the used SVs is within DB of the median epoch mean, so the fading epochs after `quit` (C/N0 8-17 dB-Hz while still flagged used) are dropped, and MON-HW with them (counted back from the end of the log, since the receiver time is wrong before the first fix). With `--cut 10` the script reproduces every T1 sweep value within 0.01 dB; without it, T1 A1 reads -3.62 dB and T2-A -2.94 dB. The T1 numbers were evaluated with the tail removed by hand; `--cut 10` is the standard from now on.

## Result

**PASS.** The crpa_core path with w = [1,0] gives the same C/N0 as the T1 loopback path (-2.76 vs. -2.75 dB against the reference), with all 11 PRNs and a 3D fix, no saturation and no frame errors. crpa_core adds no measurable loss. Next: T2-B, w = [0,1] (RX2 -> TX1, not possible in T1), and T2-C, w = [1,1].
