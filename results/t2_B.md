# T2-B: Fixed Weights [0,1] Through crpa_core, RX2 -> TX1

Date: 2026-11-09, 13:18-13:24. Unit, firmware, program, RF path and settings as T2-A (`results/t2_A.md`), except `--w 0,0,1,0 --out /tmp/t2_B`: w1 = 0, w2 = 0x7FFF, so y = x2 bit exactly. First RF check of RX2 through the PL: RX2 -> TX1 does not exist with the T1 loopback (`docs/interface.md`, Section 4). Same sequence: user on and at 50 dB, Claude Code restarted `bladegps`, logged the receiver and cold-started it about 30 s later; the user quit about 4.5 min after the cold start; safe state confirmed in the crpa_ctl log.

## Receiver (u-blox)

`scripts/ubx_cn0.py results/t2_B.ubx --skip 60 --cut 10 --ref results/t1_ref_20261107_123927.ubx`

| PRN | Reference | T2-B (RX2) | Difference | T2-A (RX1) |
|---|---|---|---|---|
| G26 | 50.8 | 48.0 | -2.8 | 47.9 |
| G16 | 49.0 | 46.0 | -3.0 | 46.0 |
| G31 | 48.0 | 45.0 | -3.0 | 45.0 |
| G14 | 46.0 | 43.0 | -3.0 | 43.1 |
| G03 | 45.0 | 42.1 | -2.9 | 42.9 |
| G23 | 45.0 | 42.0 | -3.0 | 42.3 |
| G04 | 44.0 | 40.9 | -3.0 | 41.0 |
| G29 | 43.7 | 41.0 | -2.7 | 41.0 |
| G32 | 42.0 | 39.0 | -3.0 | 39.1 |
| G27 | 41.0 | 38.0 | -3.0 | 38.2 |
| G09 | 40.5 | 37.7 | -2.8 | 38.0 |

| | T2-B (RX2) | T2-A (RX1) |
|---|---|---|
| Mean C/N0 vs. reference | **-2.94 dB** (-3.0 to -2.7) | -2.76 dB (-3.0 to -2.1) |
| Per PRN, B - A | mean -0.18 dB, -0.8 to 0.0 | |
| 3D-fix epochs / final numSV / hAcc | 247 / 11 / 2.08 m | 271 / 11 / 2.06 m |
| AGC | 2028 | 2028 |
| Jamming indicator (mean, range) | 109 (86-117) | 108 (95-115) |
| MON-HW noise | 111-130 | 99-117 |

## crpa_core (`results/t2_B_every100.csv`, `results/t2_B.txt`)

- 335627 blocks in 335.6 s; one 6-block gap at startup, none after. SAT_CNT 0 in every block, no FRAME_ERR or RES_DROP. Weights [0, 0, 0x7FFF, 0], OUT_SHIFT 0 throughout.
- Levels, 30 s means with bladegps running: x1 -41.30 to -41.33, x2 -41.69 to -41.71 dBFS, y = x2. Before bladegps: x1 -42.57, x2 -42.94. RX2 is 0.4 dB below RX1 in both cases, as in T2-A. Peak |x| at most 83 / 74.
- Full CSV (36 MB) kept locally, not committed.

## Result

**PASS.** RX2 through crpa_core reaches the receiver with the same C/N0 as RX1 within 0.2 dB on average (largest single PRN 0.8 dB, G03), below the 1 dB C/N0 resolution, with all 11 PRNs and a 3D fix. The 0.4 dB lower x2 level is a gain difference: it scales signal and noise alike and does not change C/N0. MON-HW noise reads about 12 counts higher than in T2-A; its meaning on the M8T is not documented here and it did not show in C/N0, AGC or the jamming indicator. Both channels and both weight registers now work end to end at RF.

## Inter-channel phase from R21 (T2-A and T2-B logs)

| Log | Window | \|rho\| | Phase of R21 = x2 conj(x1) |
|---|---|---|---|
| T2-A | before bladegps | 0.006 | (no common signal) |
| T2-A | bladegps on | 0.267 | 173.0 deg |
| T2-B | before bladegps | 0.148 | 173.0 deg (bladeRF carrier left from T2-A) |
| T2-B | bladegps on | 0.245 | 173.2 deg |

The common component (bladeRF carrier and simulated GPS through the splitter) reaches RX2 nearly in antiphase with RX1, the same in both runs. Cause not determined (splitter type or an inverted path). Consequences: w = [1,1] cancels the common signal, GPS included (about -18 dB); w = [1,-1] adds it in phase. In this setup the bladeRF carrier and the satellites share one inter-channel phase, so power inversion would null both: a T4 jammer must reach the two channels with a different relative phase. Next: T2-C1, w = [1,-1] (coherent), then T2-C2, w = [1,1] (destructive).
