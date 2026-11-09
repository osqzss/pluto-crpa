# T2-D: Control for T2-C1, Same TX1 Output Power Without Array Gain

Date: 2026-11-09, 13:38-13:44. Unit, firmware, program, RF path and settings as T2-A (`results/t2_A.md`), except `--w 1,0,0,0 --shift 1 --out /tmp/t2_D` and TX1 attenuation 52.25 dB (`tx 60`, then `tx 52.25`; floor 50 dB). y = 2 x1 (OUT_SHIFT 1, +6.02 dB), minus 2.25 dB attenuation: TX1 output +3.77 dB against T2-A, the same as T2-C1 (+3.73 dB, `results/t2_C1.md`), but from RX1 alone. Same sequence; safe state confirmed in the crpa_ctl log.

## Receiver (u-blox)

`scripts/ubx_cn0.py results/t2_D.ubx --skip 60 --cut 10 --ref results/t1_ref_20261107_123927.ubx`

| | T2-A [1,0], 50 dB | **T2-D** 2 x1, 52.25 dB | T2-C1 [1,-1], 50 dB |
|---|---|---|---|
| TX1 output vs. T2-A | 0 dB | +3.77 dB | +3.73 dB |
| Mean C/N0 vs. reference | -2.76 dB | **-2.86 dB** (-3.1 to -2.3) | -0.96 dB |
| Per PRN vs. T2-A | | **-0.09 dB** (-0.2 to 0.0) | +1.80 dB (+1.2 to +2.0) |
| Per PRN vs. T2-C1 | | -1.90 dB (-2.0 to -1.5) | |
| 3D-fix epochs / final numSV / hAcc | 271 / 11 / 2.06 m | 265 / 11 / 2.07 m | 283 / 11 / 2.15 m |
| AGC | 2028 | 1638 | 1872 |
| Jamming indicator (mean, range) | 108 (95-115) | 102 (96-115) | 139 (130-146) |
| MON-HW noise | 99-117 | 112-113 | 121-122 |

Per PRN, T2-D: G26 48.0, G16 46.0, G31 45.0, G14 43.0, G03 42.7, G23 42.1, G29 41.0, G04 40.9, G32 39.0, G27 38.1, G09 37.8 dB-Hz.

## crpa_core (`results/t2_D_every100.csv`, `results/t2_D.txt`)

- 362136 blocks in 362.1 s; one 6-block gap at startup, none after. SAT_CNT 0, no FRAME_ERR or RES_DROP. Weights [0x7FFF, 0, 0, 0], OUT_SHIFT 1 throughout. Peak |x| at most 80 / 71, so |y| at most about 160.
- y - x1 = +6.02 dB before and during bladegps (x1 -42.55 / -41.32 dBFS).

## Result

**C/N0 does not depend on the TX1 output level in this range**: 3.77 dB more output from RX1 alone gives the T2-A value within 0.1 dB. So the 1.8-1.9 dB gain of T2-C1 is **array gain** from combining RX1 and RX2, of at most 3 dB for noise independent per channel.

The AGC did not match as intended: 1638 in T2-D against 1872 in T2-C1, three steps lower, so the receiver saw more in-band power in T2-D, although the total y power (full 10 MSPS band) matched within 0.05 dB. The spectral distribution must differ (in T2-C1 the independent noise adds +2.8 dB and the correlated part +5.8 dB; in T2-D both +6 dB); the logs do not resolve it. It does not affect the conclusion: T2-D had at least as much power at the receiver as T2-C1 and gained nothing.
