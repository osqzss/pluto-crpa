# T5 Plan: Jammer Power Sweep, J/S Improvement

Written 2026-11-18. Stage T5 of `docs/pluto-crpa-plan.md`, Section 8.2:
jammer power sweep, pass criterion "J/S improvement vs. no suppression".
The setup is the T4 setup (`docs/t4_plan.md`, Section 2), and the T4 rules,
tools and run procedure apply unless this file says otherwise.

Status: **decided by the user (2026-11-18): all proposals of Section 9 as
written.** **P0 done** (2026-11-18): tools tested offline and `crpa_ctl`
write check on the Pluto (Section 4, "P0 state"); recabled to V3 by the
user, jammer attenuators 30 + 20 dB. **P1 done** (2026-11-18, Section 2.0).
**P2 at gain 60 done** (Section 2.0b): clip onset J/N60 42.2 dB at B205mini
78 dB, no compression before it, D 100.9 deg from P1 and P2. **P3 done**:
D 100.5 deg with both on, predicted C/N0 change with PI +0.4 dB. **G60-N,
G60-F, G60-P done** (2026-11-18, `results/t5.md`): improvement 26 to 29 dB
at the 6 dB point, more than 14 to 21 dB at the fix-loss point (PI kept the
fix beyond the clip onset). **P2 at gain 50 done** (Section 2.0c): gain
step 9.88 dB, clip onset J/N60 52.1 dB. Next: G50-N, G50-F, G50-P.

All levels below are estimates from T3, T4 and the model until P1 and P2
have measured them.

---

## 1. What T5 has to settle

1. The jammer level at which the receiver fails **without** suppression
   (fixed w = [1,0]) and **with** power inversion (PI), in the same cabling,
   at the same RX gain, on the same day. The difference is the J/S
   improvement.
2. What limits PI in hardware. The model (`results/t3_model.txt`, A and B2)
   says nothing does until the ADC clips: null depth grows as about
   2 x J/N - 2 dB and collapses at clipping. T4 matched the model up to
   J/N 30 dB. T5 has to find where hardware departs from it (analog
   compression before ADC full scale, IQ image, spurs, phase noise of the
   jammer) or confirm that ADC clipping comes first.
3. How much the limit moves with a lower RX gain, and what that costs in
   C/N0 (the AD9363 noise figure rises as the gain goes down, T3-D2).

Not in T5: modulated or wideband jammers, two jammers, moving jammers, the D
dependence (done in T4), over-the-air (T6).

---

## 2. Setup

As T4 (`docs/t4_plan.md`, Section 2), with these choices:

- **Cabling: V3** (50 cm jammer leg to CMB1 / RX1, no adapter), D 100 deg.
  At D 100 deg PI costs the satellites nothing (+0.4 dB predicted, +0.3 to
  +0.7 dB measured), so the failure point of PI is set by the hardware and
  not by the geometry. The bench is in V5 at the end of T4: the 3 cm
  adapter in the leg to CMB2 / RX2 comes out (decide, Section 9).
- Unit, fs, Delta, bw, INT_LEN 10000, alpha 0, TX1 attenuation 50 dB,
  bladeGPS TX gain, jammer frequency L1 + 200 kHz: unchanged from T4.
- **RX gain: 60 dB and 50 dB** (decide, Section 9). 55 dB only if P1 shows
  a reason.
- **Jammer attenuation: 30 + 20 = 50 dB** for gain 60 (the T4 floor), and
  **20 + 20 = 40 dB** for the top of the gain-50 sweep (needs a change of
  the floor; decide, Section 9). The attenuators sit before SPL2, so D does
  not change with them.
- **Diagonal load per gain:** 0.1 x the noise power per sample measured in
  P1 at that gain (24 LSB^2 at 60 dB; about 8 at 50 dB if the noise is
  9 LSB rms).
- **Output level:** at gain 50 the noise in y is about 6 dB lower, and so is
  the u-blox input. OUT_SHIFT 1 (+6 dB) restores it; TX attenuation cannot
  go below 50 dB. In the F runs OUT_SHIFT 1 halves the output headroom: x1
  must stay below about -6 dBFS for no output saturation, which holds up to
  the fixed-weight failure point (Section 2.1). Decide, Section 9.

### 2.0 Measured in P1 (2026-11-18, V3, RX-only)

Logs: `results/t5_P1_noise_*.txt` (bladeRF connected, `bladegps` not
running, B205mini idle, 5 captures per gain), `results/t5_P1_gps_*.txt`
(`bladegps` on, 10 per gain), `results/t5_P1_after_*.txt` (after `bladegps`
quit). No clipping anywhere; TX side safe at start and end of every set.

| RX gain | Noise x1 / x2 | x1 rms | Load 0.1 x P1 | GPS on: \|rho\| | GPS SNR against gain 60 | Carrier over floor x1 / x2 | Carrier phase, x2/x1 |
|---|---|---|---|---|---|---|---|
| 60 dB | -42.50 / -42.81 dBFS | 15.4 LSB | 23.6 LSB^2 | 0.168 | 0 | 38.1 / 37.7 dB | 167.9 deg, -0.69 dB |
| 55 dB | -45.34 / -46.68 | 11.1 | 12.3 | 0.125 | -1.5 dB | 37.4 / 37.2 | 167.8, -0.57 |
| 50 dB | -47.78 / -49.80 | 8.4 | 7.0 | 0.079 | -3.7 dB | 35.6 / 36.3 | 168.1, -0.69 |
| 45 dB | -47.75 / -50.86 | 8.4 | 7.0 | 0.024 | -9.1 dB | 31.9 / 32.5 | 170.5, -0.47 |

- GPS SNR from \|rho\| as rho / (1 - rho). Gain 50 costs 3.7 dB (estimate
  3.6), gain 45 9.1 dB: **gain 50 confirmed** as the lower gain. Load at
  gain 50: **7 LSB^2**; at 60: 24 (unchanged).
- The x1 noise stops falling below 50 dB (-47.8 dBFS at 50 and 45), as in
  T3-D2. At low gain x1 is 2.0 dB (50) and 3.1 dB (45) above x2: the known
  ch0/1 excess (plan Section 10.2), so the noise is not equal on the two
  elements at gain 50; Gn of Section 5 uses the measured values.
- Noise only: no line at the carrier or the jammer frequency (about 2 dB
  over the floor, i.e. noise) before and after `bladegps`; \|rho\| 0.004
  to 0.009.
- GPS path at gain 60: carrier phase 167.9 deg, -0.69 dB, against 167.72 deg
  and -0.64 dB in T4 V3 P3: the V3 cabling is back within 0.2 deg.
- Several RX gain writes were made (P1 sequences); power-cycle the Pluto
  before P2.

### 2.0b Measured in P2 at gain 60 (2026-11-18, after a power cycle)

Jammer alone (`bladegps` off), 30 + 20 dB, amplitude 0.5, 3 passive captures
per step. Logs `results/t5_P2_r60_g*.txt`, `results/t5_P2_r60f_g*.txt`
(0.5 dB steps near the onset), jammer logs `results/t5_P2_r60*_jammer.txt`.
Noise before: -42.55 / -42.86 dBFS (`results/t5_P2_pre_*.txt`, the first set
after the power cycle, which wrote LO, fs and gain once). J/N60 =
(P_x1 - P_noise) / P_noise.

| B205mini gain | x1 dBFS | J/N60 | Step | Peak | Clipped (x1 / x2, of 3.1 M) | Floor near the line, x1, 20 / 100 / 500 kHz |
|---|---|---|---|---|---|---|
| 55 | -22.53 | 20.0 | - | 207 | 0 | 0.0 / -0.2 / -0.3 dB |
| 57.5 | -19.98 | 22.5 | +2.55 | 255 | 0 | 0.0 / 0.0 / -0.2 |
| 60 | -17.54 | 25.0 | +2.44 | 325 | 0 | 0.0 / -0.2 / -0.2 |
| 62.5 | -15.07 | 27.5 | +2.47 | 418 | 0 | 0.3 / -0.1 / 0.2 |
| 65 | -12.55 | 30.0 | +2.52 | 534 | 0 | 0.7 / 0.6 / 0.1 |
| 67.5 | -9.91 | 32.6 | +2.63 | 705 | 0 | 1.2 / 0.9 / 0.6 |
| 70 | -7.54 | 35.0 | +2.37 | 907 | 0 | 1.6 / 1.4 / 0.9 |
| 72.5 | -5.38 | 37.2 | +2.16 | 1149 | 0 | 2.3 / 2.0 / 1.1 |
| 75 | -3.01 | 39.5 | +2.37 | 1502 | 0 | 3.3 / 3.5 / 1.8 |
| 77.5 | -0.66 / -0.61 | 41.9 / 42.0 | +2.35 | 1981 / 1991 | 0 | 4.0 / 3.7 / 2.2 |
| 78 | -0.14 | about 42.4 | +0.5 | 2047 | 55155 / 2137 | - |
| 78.5 | 0.49 | clipped | - | 2067 | 1631365 / 996852 | - |
| 79, 80, 82.5, 85 | 0.9 | clipped | - | 2056 to 2066 | 2.4 M | - |

- **Anchor:** gain 65 gives J/N60 30.0 (T4 L5, gain 75 at 60 dB: 30.5):
  passes (+/- 1 dB).
- **Clip onset at gain 60: B205mini 78 dB, J/N60 42.2 +/- 0.25 dB** (model:
  between 42 and 44). x1 clips first (jammer 0.19 dB stronger than in x2).
- **No analog compression before the ADC clips:** the line follows the
  B205mini gain within 2.16 to 2.63 dB per 2.5 dB step up to 77.5 dB. The
  shortfall at 70 to 75 dB is the same as in T4, where the Pluto input was
  10 dB lower, so it is the B205mini.
- Jammer phase x2 against x1 -91.2 deg (-91.14 to -91.34 over 22 dB of
  level), line ratio -0.19 dB. With phi_G 167.9 deg (P1): D = 100.9 deg.
- **Floor near the line rises with the jammer**, equally in both channels:
  +1.6 dB at J/N60 35, +4 dB at 42 (20 kHz from the line), less further
  out. Whether PI removes it is a question for G60-N (skirt columns of y).
- Lines (`--spurs`): the jammer's 2nd harmonic at +/-4.389 MHz in baseband
  (2 x -2.806 MHz aliased by fs), 20 to 36 dB over the floor, after
  re-transmission at L1 + 7.4 MHz; sidebands at +/-4 kHz of the jammer,
  growing with it (12 to 28 dB); DC 18 to 21 dB, constant. The IQ image at
  +2.8 MHz is not among the six strongest lines at any level. In clipping
  (78.5 dB and up): the 3rd harmonic at -1.583 MHz (63 to 65 dB) and other
  products.
- Residual check after `quit`: no line at either frequency.
- The first start of the jammer script did not reach its start state within
  the 8 s of the wrapper (firmware and FPGA load after the power cycle took
  13 s); the wrapper sent quit, nothing was transmitted
  (`results/t5_P2_r60_jammer_nostart.txt`). Wait up to 60 s.

**P3 (2026-11-18, 09:14 to 09:16):** `bladegps` and the jammer on together,
RX gain 60, 15 passive captures at B205mini 55 dB (J/N60 20) and 15 at
70 dB (J/N60 35); logs `results/t5_P3_g55.txt`, `results/t5_P3_g70.txt`,
`results/t5_P3_jammer.txt`. No clipping.

| Jammer | GPS carrier phase, x2/x1 | Jammer phase, x2/x1 | D | Carrier over the floor |
|---|---|---|---|---|
| 55 dB | 168.21 deg (std 0.24), -0.70 dB | -91.31 deg (std 0.01), -0.17 dB | **100.5 deg** | 36.4 dB |
| 70 dB | 168.35 deg (std 0.30), -0.72 dB | -91.21 deg (std 0.00), -0.19 dB | **100.4 deg** | 35.1 dB |

- D 100.4 to 100.5 deg: equal to the separate measurement (P1 and P2,
  100.9 deg) and to T4 V3 (100.0 / 100.2 deg); no dependence on the jammer
  level over 15 dB. The carrier line is 1.3 dB lower against the floor at
  70 dB: the floor rise next to the jammer of P2.
- Section 5 of `docs/t4_plan.md` with these values: Gs +3.48 dB, Gn
  +3.10 dB, **C/N0 change with PI +0.4 dB** against w = [1,0] with the jammer
  off (T4 V3: same prediction, +0.3 to +0.7 dB measured).
- Both sources stopped after the captures (`q`, `quit`), both exited by
  themselves.

**Ladders for G60** (B205mini gain at 50 dB; J/N60 from the table, below
55 dB by 1 dB per dB as in T4):

| Run | J/N60 steps | B205mini gain |
|---|---|---|
| G60-F | 10, 13, 16, 19, 22, 25, 28, 31 | 45, 48, 51, 54, 57, 60, 63, 66 |
| G60-N | 30, 35, 37.2, 39.5, 41.9, then + steps | 65, 70, 72.5, 75, 77.5; + at 80 and 82 (onset + 2 and + 4 dB of gain) |
| G60-P | cold start at 35, then 37.2, 39.5, 41.9, + steps, back to 35 | 70; 72.5, 75, 77.5; + at 80 and 82; 70 |

Above 78 dB the ADC is saturated, so the + steps have no measured J/N60;
they are reported by B205mini gain. `--max-gain` for the G60 runs: 85.

### 2.0c Measured in P2 at gain 50 (2026-11-18, after a power cycle)

First set after the power cycle (writes gain 50): noise -47.3 / -49.6 dBFS
(`results/t5_P2_pre50_*.txt`; P1 read -47.8 / -49.8). Jammer alone, 3
passive captures per step. Part a with 30 + 20 = 50 dB
(`results/t5_P2_r50a_*`), part b with 20 + 20 = 40 dB changed by the user
(`results/t5_P2_r50b_*`, 0.5 dB steps near the onset in `results/t5_P2_r50bf_*`).

**RX gain step 60 -> 50 dB: 9.88 dB** (jammer line at B205mini 70 / 72.5 /
75 / 77.5 dB through 50 dB: 9.85 / 9.92 / 9.88 / 9.88 dB lower than in the
gain-60 P2). J/N60 at gain 50 = P_x1 + 9.88 dB - (-42.55 dBFS).

| Att. | B205mini | x1 dBFS | J/N60 | Peak | Floor near the line x1, 20 / 100 / 500 kHz |
|---|---|---|---|---|---|
| 50 | 70 | -17.40 | 35.0 | 305 | 0.7 / 0.6 / 0.5 dB |
| 50 | 72.5 | -15.27 | 37.2 | 381 | 1.1 / 0.8 / 0.5 |
| 50 | 75 | -12.87 | 39.6 | 494 | 2.1 / 2.0 / 1.1 |
| 50 | 77.5 | -10.56 | 41.9 | 637 | 3.6 / 3.0 / 2.0 |
| 50 | 80 | -8.14 | 44.3 | 829 | 5.0 / 4.7 / 3.1 |
| 50 | 82.5 | -5.85 | 46.6 | 1072 | 7.0 / 6.2 / 4.4 |
| 50 | 85 | -3.58 | 48.8 | 1387 | 8.6 / 8.1 / 5.8 |
| 40 | 72.5 | -5.34 | 47.1 | 1135 | 7.0 / 6.8 / 5.0 |
| 40 | 75 | -2.96 | 49.5 | 1489 | 8.9 / 8.8 / 6.9 |
| 40 | 77.5 | -0.60 | 51.8 | 1971 | 9.5 / 9.1 / 7.4 |
| 40 | 78 | -0.11 | clip onset (23061 / 1039 of 3.1 M clipped) | 2048 | - |
| 40 | 78.5 and up | 0.3 to 0.94 | clipped | 2048 to 2055 | - |

- **Clip onset at gain 50: B205mini 78 dB at 40 dB, J/N60 52.1 +/- 0.25
  dB**, i.e. 9.9 dB above gain 60, as the gain step says. The clipping
  level in dBFS is the same at both gains.
- Overlap of the two attenuator settings: 40 dB at 72.5 / 75 dB reads
  0.5 / 0.7 dB above 50 dB at 82.5 / 85 dB (attenuator tolerance or the
  B205mini near its top); the runs use the measured levels.
- **Floor next to the jammer grows with the jammer power, not with the ADC
  level**: at J/N60 41.9 it is +3.6 dB at gain 50 and +4.0 dB at gain 60;
  at J/N60 51.8 +9.5 dB at 20 kHz and still +7.4 dB at 500 kHz, equal in
  both channels. It comes with the jammer (B205mini phase and wideband
  noise, or reciprocal mixing on the common Pluto LO), so PI should remove it
  as at gain 60 (G60-N); G50-N checks this.
- The 2nd harmonic at +/-4.388 MHz is 33 to 39 dB over the floor; in
  clipping the 3rd harmonic -1.582 MHz at 64 to 66 dB.

**Ladders for G50** (RX gain 50, `--shift 1`, load 8 = 0.1 x the noise power
at -47.3 dBFS; jammer attenuators stay at 40 dB for all three runs; below
72.5 dB J/N60 = B205mini gain - 25.4 dB, from the 72.5 / 75 dB points and
the 1 dB per dB slope seen in T4 and P2):

| Run | J/N60 steps | B205mini gain at 40 dB |
|---|---|---|
| G50-F | 10, 13, 16, 19, 22, 25, 28, 31 | 35.5, 38.5, 41.5, 44.5, 47.5, 50.5, 53.5, 56.5 |
| G50-N | 35, 40, 44.5, 47.1, 49.5, 51.8, then + steps | 60.5, 65.5, 70, 72.5, 75, 77.5; + at 80 and 82 |
| G50-P | cold start at 45, then 47.1, 49.5, 51.8, + steps, back to 45 | 70.5; 72.5, 75, 77.5; + at 80 and 82; 70.5 |

`--max-gain`: 60 for G50-F, 85 for G50-N and G50-P. The F steps get their
J/N60 from the x1 level of each window as a check.

### 2.1 Jammer scale and level estimates

**Jammer axis: J/N60** = jammer power at the RX port over the noise power in
9 MHz at RX gain 60 dB, as measured in T4 P2. It is a measure of jammer
power at the port, independent of the RX gain used in a run, so F and P
results at different gains share one axis. At gain g the jammer line in
dBFS is measured and referred back with the gain step measured in P2
(Section 6, not assumed to be exactly 60 - g).

J/S estimate: with N0 the Pluto noise at gain 60 and a C/N0 of about 40
dB-Hz at the element (V3-F reference, -5.1 dB against T1),
J/S = J/N60 + 10 log10(9e6) - 40 = J/N60 + 29.5 dB. The improvement is a
difference of two J values and does not depend on this estimate.

| Quantity | Gain 60 | Gain 50 | From |
|---|---|---|---|
| Noise in x1 | -42.5 dBFS (15 LSB rms) | about -47 dBFS (9 LSB) | T3-0, T3-D2 |
| GPS common part, \|rho\| | 0.17 | about 0.09 | T4 P1, T3-D2 scaled |
| Reference C/N0 against gain 60 | 0 | about -3.6 dB | \|rho\| in T3-D2 |
| ADC clip onset (CW peak plus noise at 2047) | J/N60 about 41 | about 51 | T4 P2 peak 566 at J/N60 30.5; model B2 |
| J/N60 at B205mini gain 75, 50 dB att. | 40.5 | 40.5 | T4 P2 + 10 dB |
| J/N60 at B205mini gain 75, 40 dB att. | 50.5 | 50.5 | T4 P2 + 20 dB |

- B205mini gains above 70 dB compressed by 0.4 dB in T4 (75 dB gave
  4.6 dB for 5); beyond 75 dB nothing is known. The ladder is set from the
  P2 measurement, not from the gain values.
- Below gain 50 the noise stops falling (-48.4 dBFS at 40 dB, T3-D2): the
  ADC and baseband noise dominate, so each further dB of headroom costs a dB
  of C/N0. At gain 45 the reference would be near 31 dB-Hz, too low to
  measure a failure point. Hence 50 as the lower gain.

---

## 3. Safety

The rules of `docs/test-equipment.md`, Section 2 and `docs/t4_plan.md`,
Section 3 apply. Changes:

- **Jammer attenuation 40 dB** (if decided): worst case B205mini at full
  gain (about +20 dBm) through 40 + 7 dB is -27 dBm at the Pluto RX ports.
  The ADC clips; the AD9363 absolute maximum is +2.5 dBm peak at the RF
  inputs (datasheet Rev. D, Table 10), so the margin is about 30 dB. A CW has
  no crest factor; the same holds for the 50 dB setting (-37 dBm). `t4_jammer.py --ext-att` floor
  from 50 to 40 dB, and `--max-gain` set from P2 to the gain of the top step
  plus 3 dB, as in T4.
- **Pluto TX1 into the u-blox:** unchanged, at most about -43 dBm with a
  full-scale DAC at 50 dB attenuation, OUT_SHIFT does not change full scale.
  When PI fails above the clip onset, y carries the jammer up to full scale;
  that stays within this worst case.
- **Stop rules:** PEAK >= 2047 (ADC clipping) and SAT_CNT > 0 are expected
  in the steps above the clip onset and are recorded, not stopped on, but
  only in steps planned as "over the limit" (marked + in Section 6) and for
  at most 120 s per run. Stop and report as in T4 on: FRAME_ERR; safe state
  not confirmed; a jammer level more than 3 dB from the P2 table; SAT_CNT
  or PEAK at 2047 in a step that is not marked +.
- One go per run; Claude Code runs `bladegps`, the jammer and the logger,
  the user starts `crpa_ctl --on` and types CONDUCTED; kill by PID.

---

## 4. Tools

Changes are tested offline before P1, as in T4.

### 4.1 `scripts/t3_phase.py` (extension)

- Clip count per channel: samples with \|i\| or \|q\| >= 2047 per capture.
- `--spurs N`: the N strongest lines in each channel outside the bladeRF
  carrier and the jammer (+/- 2 bins), with frequency and level over the
  floor. Shows the jammer image (+2.8 MHz in baseband, L1 + 5.8 MHz after
  re-transmission), harmonics and intermodulation, in x1 and in y.
- Floor next to the jammer: noise level in x1 and y at 20 kHz, 100 kHz and
  500 kHz from the line, to see a phase-noise skirt and whether PI removes
  it.

### 4.2 `scripts/t5_steps.py` (new)

T4 built one C/N0 window per step by hand. T5 has 8 to 12 steps per run, so
a summarizer: reads the jammer log (steps with host times and T0), the
u-blox log (through `ubx_cn0.py --from/--to`) and the `crpa_ctl` CSV, and
writes one row per step: J/N60, mean C/N0 against the run reference and
against T1, SVs used, fix type, AGC, jamming indicator, x1 and y level,
PEAK max, SAT_CNT sum, missed blocks, \|w2\|. Windows as T4: 15 s after a
step to 5 s before the next. Checked by recomputing the V3-F and V3-P tables
of `results/t4.md`.

### 4.3 `sw/app/crpa_ctl` (small change, decide)

Open item from T4 V3-A: CSV and log writes are not checked, and `/tmp`
filled up. T5 runs last up to 15 min (about 900000 blocks). Proposed: check
every write and stop to the safe state on failure; use `--csv-every 10` in
the receiver runs (the N runs keep 1). Rebuild with the firmware toolchain
and copy to `/mnt/jffs2` (user).

### 4.4 `scripts/t4_jammer.py`

`--ext-att` floor 40 instead of 50 (only if decided); offline tests updated.
No other change: the schedule already takes any gain steps.

### P0 state (2026-11-18)

- `t4_jammer.py`: `--ext-att` floor 40 dB; 17 offline tests pass.
- `t3_phase.py`: columns `clip1`, `clip2` and six skirt columns appended
  (earlier columns unchanged), `--spurs N` as `# spurs` lines, totals in the
  summary. Selftest passes, with new cases for a partly clipped tone, a
  spur list (image at +2.8 MHz and a line at 1.6 MHz found, the jammer
  excluded) and a synthetic skirt (23.8 / 10.2 / 1.0 dB at 20 / 100 /
  500 kHz, clean line within 0.3 dB).
- `t5_steps.py`: written. On the T4 files it reproduces the V3-F table and
  the V3-P table of `results/t4.md` (C/N0 against T1, x1 and y levels, AGC,
  jamming indicator; the CSV offset fitted with 0.21 / 0.18 dB scatter).
- `crpa_ctl`: every CSV row and log line checked, CSV flushed and checked
  every `--monitor` interval; a failed write stops the run to the safe state
  with `CSV write failed` or `log write failed`; errors at close reported and
  the exit code set. Cross-built without warnings; `make test` 4156 weight
  sets, 0 mismatches. **On the Pluto (2026-11-18, `results/t5_p0_crpa_ctl.txt`):**
  on a 64 kB tmpfs the run stopped with `CSV write failed: No space left on
  device` before the first 2 s summary, safe state confirmed, rc 1; a normal
  20 s PI dry run (load 24) ran 20002 blocks with 5 missed at startup only
  (as before), no saturation, x1 / x2 -42.5 / -42.8 dBFS, |w2| 0.004 to
  0.024 on noise; `crpa_ctl off` confirmed the safe state. Steps 1 to 3
  below are done; recabling (step 4) is open.
- Model: `model/sim_pi.py t5` (section G) with the raw null column,
  `results/t5_model.txt`.

Hardware part of P0, for the user:

1. Copy the new binary: `scp -O sw/app/crpa_ctl pluto:/mnt/jffs2/crpa_ctl`.
2. Write test, dry run, no transmission, on a 64 kB tmpfs:
   `ssh pluto 'mkdir -p /tmp/full && mount -t tmpfs -o size=64k tmpfs /tmp/full && /mnt/jffs2/crpa_ctl run --duration 30 --out /tmp/full/x; echo rc=$?; umount /tmp/full'`.
   Expected: `CSV write failed ... No space left on device` within about
   2 s, the confirmed safe state, rc 1.
3. Normal dry run as in T4 P0 (`crpa_ctl run --mode pi --load 24 --duration
   20 --out /tmp/t5_p0`): no error, CSV complete; then `crpa_ctl off`.
4. Recabling to V3: remove the 3 cm adapter from the jammer leg to CMB2 /
   RX2; 50 cm cable in the leg to CMB1 / RX1 stays. Jammer attenuators
   30 + 20 dB.

---

## 5. Predictions

### 5.1 Fixed weights

From V3-F (gain 60): C/N0 loss 4.0 dB at J/N60 10, 9.9 dB at 20, fix lost
at 30. A fit of C/N0_eff = 1 / (1 / C/N0 + J / (Q Rc S)) to these points
puts the 6 dB loss near J/N60 13 to 15 dB and the loss of the fix between
22 and 28 dB (the two points do not fit one Q; the spread is the range). At gain 50 the reference is about 3.6 dB lower, so both points move
down by up to that amount. The F ladder therefore needs 3 dB steps from
J/N60 10 to 31.

### 5.2 Power inversion

- Null depth (model `model/sim_pi.py t5`, `results/t5_model.txt`, load 0.1 x
  noise power as in hardware, "raw" = line in x1 over line in y as measured
  in T4): 20.2 / 39.3 / 58.8 dB at J/N 10.1 / 20.0 / 29.6, then 68.1 / 77.0 /
  84.9 / 87.7 dB at 34 / 38 / 41 / 42 (gain 60, 15 LSB). T4 measured 18.9 /
  38.1 / 57.1 dB: **1.2 to 1.7 dB below the matched model, a constant
  offset**, not a floor that grows with J. (T4 compared with the load-1 table
  of `docs/fixed_point.md`, normalized by the noise gain of the weights; the
  two differences, 4.6 dB of load and -3 dB of normalization, nearly cancel,
  so the T4 conclusion stands.) The residual jammer in y falls as the jammer
  rises: about -46 dB under the noise at J/N 42 in the model; hardware is
  not expected to follow that far (Section 5.3).
- C/N0 with PI stays at the Gs / Gn value of V3 (+0.4 dB against the F
  reference) up to the clip onset, then collapses within 2 to 3 dB (model:
  null 67.6 dB at J/N 35, 32.8 dB at 40 with clipping, 16 LSB noise).
- Failure point of PI, if ADC clipping is the limit: the model clips
  between J/N 42 and 44 at 15 LSB (gain 60) and between 46 and 48 at 9 LSB,
  i.e. J/N60 52 to 54 at gain 50 with a 10 dB gain step. At 44 / 48 the
  null falls to 46 / 54 dB raw and C/N0 out by 11 / 10 dB; at J/N 50 (9 LSB)
  to 32 dB. The P2 clip onset replaces these.
- **Improvement** (fix lost, P against F): about 13 to 19 dB at gain 60 and
  about 23 to 32 dB at gain 50 if clipping is the limit. Less means a hardware
  limit before clipping; Section 7 lists what to look at.

### 5.3 Candidate hardware limits before clipping

Each has a signature in the N runs:

| Candidate | Signature | Estimate |
|---|---|---|
| AD9363 analog compression | J line in x1 grows less than the B205mini gain step while PEAK is below 2047; null depth stops growing | unknown; the gain table splits gain between LNA, mixer and TIA |
| IQ image of the jammer | line at +2.8 MHz in baseband in x1 and x2, with a different phase per channel, so not nulled; in y it goes to L1 + 5.8 MHz, outside the C/A main lobe | about -50 dBc with quadrature tracking: at J/N 50 the image is near the noise |
| Jammer phase-noise skirt | floor in x1 rises near the line at high J; in y it is nulled except for the delay difference of the legs (25 cm, about 1.2 ns: -62 dB at 100 kHz, -42 dB at 1 MHz) | B205mini about -100 dBc/Hz at 100 kHz: at J/N60 50 the skirt is about 20 dB over N0 in x1, far below the noise in y |
| Weight quantization | null depth stops at the Q1.15 limit | below -90 dB, not reached |
| Spurs of the ADC or the B205mini | lines in the `--spurs` list that grow faster than J | unknown |

---

## 6. Steps and runs

Who acts: U = user, C = Claude Code. RX-only = no Pluto transmission.
Power-cycle the Pluto before the gain-60 group and set the gain once per
group: RX gain writes shift RX1 by up to 0.3 dB until a power cycle (T3).

### Preparation

| Step | Content | RF on | Who |
|---|---|---|---|
| P0 | Decisions of Section 9; tools of Section 4 and offline tests; `crpa_ctl` rebuilt if decided; cabling back to V3; attenuators 30 + 20 on the jammer | none | C; U cables |
| P1 | RX gain 60, 55, 50, 45: noise only (bladeRF unplugged), 5 captures each; then GPS alone, 10 captures each: noise, \|rho\|, carrier over the floor, peak. Gives the load per gain and confirms the choice of 50 | bladeRF | C after the go |
| P2 | Jammer alone, RX-only, at gain 60 with 50 dB: B205mini gain from 55 to the clip onset in 2.5 dB steps, 3 captures each, with clip counts and `--spurs`; anchor: gain 65 must give J/N60 30.9 +/- 1 dB (T4 + 10 dB). Then gain 50: the same and on up to the top, with 40 dB from the step where 50 dB runs out (two common gains of the B205mini for the overlap). Measured RX gain step from the same jammer gain at both RX gains. Residual-line check after stop | B205mini | C after the go; U changes the attenuator |
| P3 | Both on at gain 60, 30 captures: D in V3 (expected 100 deg) | both | C after the go |

P2 sets the ladders of all runs: J/N60 per B205mini gain and attenuator, the
clip onset per RX gain, and whether the line grows linearly up to it. If the
line stops growing before PEAK reaches 2047, that is the first finding of T5
(analog compression), and the PI ladder ends there plus 3 dB.

### Runs per RX gain (G60 first, then G50)

Each run: one go. Host side as T4 (`docs/t4_plan.md`, Section 6, "as
executed"): FIFOs, PIDs in files, `ubx_log.py`, cold start and `t0`
together, 60 s per step.

| Run | Pluto | Jammer (from t = 0) | Gives |
|---|---|---|---|
| Gg-N | dry run, PI, `--load` of P1, `--cap-sel --duration 600` | J/N60 30, 35, then 2 dB steps to the clip onset, then +2 and +4 (marked +); 40 s each; continuous captures of y and x1 with `--spurs` | Null depth against J up to the break; residual and spurs in y; weights |
| Gg-F | `--on`, fixed [1,0], `--shift` per Section 9 | off to 180 s (reference), then J/N60 10, 13, 16, 19, 22, 25, 28, 31, 60 s each; off 90 s | F reference; 6 dB point and fix-loss point without suppression; recovery |
| Gg-P | `--on`, PI, `--load` of P1 | on at J/N60 35 (G60) or 45 (G50) **before** `crpa_ctl` starts, cold start under it; 120 s; then 2 dB steps up to the clip onset + 4 dB (top two marked +), 60 s each; then back to 35 / 45 for 60 s (recovery), off 60 s | TTFF under the jammer; 6 dB point and fix-loss point with PI; recovery after overload |

- Run time 10 to 15 min each; 6 runs plus P1 to P3. G60 needs 50 dB of
  jammer attenuation only; G50 needs the change to 40 dB for the top of N
  and P (U changes it between runs, never during one).
- If Gg-N shows a hardware limit below the clip onset, Gg-P ends 4 dB above
  that limit instead.
- A second Gg-P with the cold start at the highest level that held (the
  acquisition limit, not only the tracking limit) is optional, after the
  first results.
- Gain 60 G60-F repeats V3-F with finer steps; V3-F stays as a cross-check.

---

## 7. Records and evaluation

- Raw files as T4, named `results/t5_<run>...`; CSV every 100th row
  committed (`_every100.csv`, from the `--csv-every 10` CSV: every 10th).
- Summary `results/t5.md`:
  - P1: noise, \|rho\|, carrier SNR, load per RX gain;
  - P2: ladder per RX gain and attenuator, measured RX gain step, clip
    onset, linearity, spurs and image against J;
  - N: null depth against J/N60 per gain, against the model curve for the
    measured noise (`model/sim_pi.py` run for 15 and 9 LSB rms with the
    same J values; add those cases to the script);
  - F and P: per step the `t5_steps.py` table; the J/N60 (and J/S estimate)
    at the 6 dB point and at the loss of the fix, each as an interval of one
    step; **improvement = P minus F** per gain, for both points;
  - the J/S improvement against RX gain, and the C/N0 cost of the lower
    gain.

Pass criteria (proposed, decide in Section 9):

| Item | Criterion |
|---|---|
| Recorded | Fix-loss and 6 dB points with and without PI, at two RX gains |
| Improvement | At gain 60, fix-loss point with PI at least 10 dB above the fixed-weight one |
| PI limit | PI holds the fix up to within 3 dB of the clip onset measured in P2, at each gain; a lower limit is a finding to explain (Section 5.3), not a failure of T5 |
| Null depth | Within 3 dB of the model value up to the clip onset (T4 criterion), against the raw column of `results/t5_model.txt` (load 0.1 x noise, line in x1 over line in y) for the noise measured in P1 |
| Integrity | No FRAME_ERR, no gap after startup, safe state confirmed in every run; SAT_CNT and PEAK 2047 only in steps marked + |

Then update plan Sections 8.2, 10 and 11, `docs/fixed_point.md` (RX gain
row: measured headroom) and `docs/test-equipment.md` (jammer attenuation
floor, B205mini gain table above 75 dB).

---

## 8. Order of work

1. Decisions of Section 9.
2. P0: tools, offline tests, `crpa_ctl` change, recabling.
3. P1, power cycle, P2 at gain 60, P3. (One session, RX-only except the
   sources.)
4. G60-N, G60-F, G60-P; evaluate; report.
5. P2 at gain 50 (with the attenuator change), G50-N, G50-F, G50-P.
6. `results/t5.md`, plan update.

---

## 9. Decisions (user)

Decided by the user on 2026-11-18: all eight as proposed.

| # | Question | Decision |
|---|---|---|
| 1 | Cabling | V3 (D 100 deg): PI costs no C/N0, so the limit seen is the hardware's. Remove the adapter of V5 |
| 2 | RX gains | 60 and 50 dB |
| 3 | Jammer attenuation | 50 dB (30 + 20) at gain 60; 40 dB (20 + 20) for the top of the gain-50 sweep, with the `--ext-att` floor lowered to 40 |
| 4 | Steps over the limit | ADC clipping and output saturation allowed in steps marked +, at most 120 s per run |
| 5 | Output level at gain 50 | OUT_SHIFT 1 in both F and P |
| 6 | `crpa_ctl` | Write check added before T5; `--csv-every 10` in F and P runs |
| 7 | Failure points | 6 dB below the F reference, and loss of the 3D fix; one step (2 or 3 dB) resolution |
| 8 | Pass criteria | As Section 7 |

---

## 10. Not in this plan

- Modulated, swept or pulsed jammers; two jammers (needs more than two
  elements to null both); moving jammers and short blocks (open item
  `crpa_ctl` at INT_LEN 1000).
- An external LNA in front of the Pluto. With one, the system noise is set
  by the LNA and a lower Pluto gain would cost little C/N0; the gain-50
  result here is the worst case of the conducted bench.
- Raising the bladeGPS level to emulate a higher C/N0 at the element.
- Over-the-air (T6), two-element simulator (plan Section 10.2).
