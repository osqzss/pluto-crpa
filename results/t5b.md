# T5b results: wideband, swept and pulsed jammers

Plan: `docs/t5b_plan.md`. Jammer: USRP B206mini (serial 352F132) since
2026-11-21, which replaced the B205mini and matches it
(`results/b206mini_check.md`); "gain" below is the B206mini TX gain.

## P2: each waveform alone, Pluto RX-only

Bench for all of P2: V3, jammer attenuators 30 + 20 dB (`--ext-att 50`), Pluto
(CRPA unit) at L1 + 3 MHz, 10 MSPS, bw 9 MHz, RX gain 60 manual (written once
after the power cycle of 2026-11-21), TX LO powered down, TX attenuation
89.75 dB at the start and end of every capture; bladeRF unplugged. Captures
`t3_phase.py --passive --count 3`, raw captures in `tmp/t5b_cap/` (not
committed). J/N60 = 10 log10(10^((P_x1 - N)/10) - 1) with N = -42.52 dBFS (C3
init, 2026-11-21).

### P2-a CW (2026-11-21, as B206mini check C3)

The CW part of P2-a was run as C3 of the B206mini check
(`results/b206mini_check.md`, table there): gain 65 gives J/N60 29.8
(same-day check, 30.0 +/- 1: met); J/N60 = gain - 35 dB below 70 dB, within
0.4 dB of T5; ADC clip from 78.5 dB (J/N60 between 41.7 and 42.7).

### P2-a N1 (2026-11-21, 13:39 to 13:40)

Waveform `tmp/t5b/N1.sc16`: band-limited complex Gaussian noise, B 1 MHz
(99 %), -15 dBFS rms, crest 12.3 dB, 8 MSPS, 1 s loop, sha256
`db32a066e208203dc16de38c1306c6feadf3b3c89b2dfdd4438228ccb076a5df`; centre
L1, no LO offset; `--max-gain 80`. Captures with `--cw-offset 0,200e3
--cw-span 15e3 --spurs 5 --band 0,1.2e6 --band-ref=-52.05,-52.21` (band
reference from the off step of the same run). Logs:
`results/t3_t5b_P2_N1_*_20261121-1339*.txt` / `-1340*.txt`, jammer
`results/t5b_P2_N1_jammer_20261121-133945.txt`.

An earlier attempt at 13:39:04 stopped at the first step
(`results/t5b_P2_N1_jammer_20261121-133904.txt`, off step log
`results/t3_t5b_P2_N1_off_20261121-133916.txt`): the runner passed the
negative `--band-ref` value without `=`, so `t3_phase.py` refused it. Gain 55
was on for about 1 s (8.93 M samples); then `JAMMER OFF`, no underflow. One
attempt before that stopped before the jammer was started (a wrong Pluto
state read in the runner, nothing transmitted).

| Gain (dB) | x1 dBFS | J/N60 | Jammer in L1 +/- 0.6 MHz, x1 (dBFS) | x2/x1 in band | Coherence | Phase x2/x1 | Phase slope (deg/MHz) | Clipped x1 / x2 (of 3.1 M) |
|---|---|---|---|---|---|---|---|---|
| off | -42.56 | - | - | - | 0.013 | - | - | 0 / 0 |
| 55 | -31.72 | 10.4 | -32.11 | -0.06 dB | 0.9900 | -91.14 deg | +0.42 +/- 0.05 | 0 / 0 |
| 60 | -26.97 | 15.4 | -27.09 | -0.08 | 0.9968 | -90.96 | +0.25 +/- 0.01 | 0 / 0 |
| 65 | -22.05 | **20.4** | -22.10 | -0.10 | 0.9990 | -90.82 | +0.17 +/- 0.02 | 0 / 0 |
| 67.5 | -19.39 | 23.1 | -19.43 | -0.11 | 0.9995 | -90.75 | +0.09 +/- 0.03 | 0 / 0 |
| 70 | -17.00 | 25.5 | -17.03 | -0.12 | 0.9997 | -90.71 | +0.08 +/- 0.01 | 0 / 0 |
| 72.5 | -14.88 | 27.6 | -14.90 | -0.12 | 0.9998 | -90.71 | +0.09 +/- 0.01 | 0 / 0 |
| 74 | -13.45 | 29.1 | -13.46 | -0.11 | 0.9999 | -90.72 | +0.11 +/- 0.01 | 0 / 0 |
| 75 | -12.48 | **30.0** | -12.49 | -0.11 | 0.9999 | -90.73 | +0.14 +/- 0.01 | 0 / 0 |
| 76 | -11.58 | 30.9 | -11.59 | -0.11 | 0.9999 | -90.73 | +0.15 +/- 0.01 | **2** / 0 |
| 77 | -10.60 | 31.9 | -10.60 | -0.11 | 0.9999 | -90.74 | +0.15 +/- 0.00 | 9 / 9 |
| after `quit` | -42.55 | - | - | - | 0.013 | - | - | 0 / 0 |

(Slope: mean +/- standard deviation of the 3 captures.)

- **Scale:** J/N60 = gain - 44.6 dB up to 70 dB (9.6 dB more gain than CW for
  the same J/N60, from the 9 dB lower drive), then the same compression as
  CW: 2.1 / 2.4 dB per 2.5 dB to 75 dB, 0.9 and 1.0 dB per 1 dB above. C3 at
  65 / 75 dB gave 20.6 / 30.2, so the level repeats within 0.2 dB.
- **Clip onset (Gaussian noise): gain 76, J/N60 30.9** (2 clipped samples of
  3.1 M in x1); gain 77 / J/N60 31.9: 9 per channel. Predicted near 31
  (Section 2.6). C3 saw 1 sample at gain 75 (J/N60 30.2), so the first
  clipped samples appear between J/N60 30 and 31. Ladder ended one step past
  the first clipped step.
- **Jammer in the band:** practically all of x1 above the noise is in
  L1 +/- 0.6 MHz (the band excess equals x1 within 0.4 dB at 55 dB and
  0.1 dB from 65 dB up). Skirts at 20 / 100 / 500 kHz from L1 follow the
  jammer level (inside the noise band), no regrowth step seen; the 500 kHz
  point is 2 to 3 dB under the 20 kHz point from 65 to 75 dB, the band edge
  of the 1 MHz noise.
- **Phase x2/x1 -90.7 to -91.1 deg, ratio -0.06 to -0.12 dB, coherence up to
  0.9999**, as the CW jammer (C3: -90.8 deg, -0.10 dB).
- **Phase slope across L1 +/- 0.6 MHz: +0.08 to +0.15 deg/MHz** from J/N60
  23 up (the lower steps read higher: +0.42 at J/N60 10, +0.25 at 15; not
  explained, the coherence is still 0.990 / 0.997 there). A pure delay gives -360 tau x 1e6
  deg/MHz, so this is **tau about -0.2 to -0.4 ns** (x2 ahead of x1). The
  sign agrees with V3 (the jammer leg to RX1 is 25 cm longer), but Section
  2.3 expected about 1.2 ns (+0.43 deg/MHz). The difference is a finding for
  the S runs, which fit H(f) over a wider band and separate the cable from
  the Pluto and fixture part (V1). The slope rises from 70 to 77 dB, as the
  B206mini compresses; that is not resolved here.
- **LO leakage at L1:** the strongest bin within 15 kHz of L1 is 5.0 dB over
  the jammer spectrum at 55 dB (an estimated -36 dBc against the total
  jammer power) and 2.7 to 3.4 dB from 60 dB up (no line above the jammer
  spectrum). C3 gave about -40 dBc with N10. Below the -30 dBc limit of
  Section 2.5: no LO offset.
- **Stream:** 8 MSPS set exactly, no underflow, sequence error or other event
  on any STATUS line or at the stop; `JAMMER OFF` confirmed; no line at L1 or
  L1 + 200 kHz after `quit` (2.1 / 1.7 dB, noise).

For the N1 N run: J/N60 20 / 25 / 30 at gain about 64.6 / 69.6 / 75, clip
onset at gain 76 (J/N60 30.9); the + steps (clip onset + 2 and + 4 dB of
J/N60) need gains above 77, beyond this ladder, and are set from the
compression seen here when that run is planned.

### P2-b N0.1, N0.5, N2 (2026-11-21, 13:44 to 13:46)

One run, the three files in turn, each with its own jammer start, off step
(band reference) and `quit`. Files (Gaussian noise, -15 dBFS rms, 8 MSPS,
1 s, centre L1, no LO offset): N0.1 (bw99 99.96 kHz, crest 11.7 dB, sha256
`bcedbdf8...`), N0.5 (500.0 kHz, 12.1 dB, `7bdca228...`), N2 (1999.9 kHz,
12.3 dB, `ce56c059...`); full sha256 in the jammer logs. Captures as P2-a
with `--band 0,0.12e6` / `0,0.6e6` / `0,2.4e6` and the band reference from
the off step of the same file. Logs `results/t3_t5b_P2_{N0.1,N0.5,N2}_*.txt`,
`results/t5b_P2_{N0.1,N0.5,N2}_jammer_20261121-134404.txt`. 8 MSPS exact,
no underflow, sequence error or other event; `JAMMER OFF` after each file;
no line after each `quit`.

J/N60 per gain (N1 from P2-a for comparison):

| Gain (dB) | 55 | 60 | 65 | 67.5 | 70 | 72.5 | 74 | 75 | 76 | 77 | 78 | 79 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| N0.1 | 10.4 | 15.4 | 20.5 | 23.2 | 25.5 | 27.6 | 29.1 | 30.1 | 30.9 | 32.0 | 32.9 c | 33.8 c |
| N0.5 | 10.4 | 15.4 | 20.4 | 23.1 | 25.5 | 27.6 | 29.1 | 30.0 | 30.9 | 31.9 c | 32.9 c | |
| N1 | 10.4 | 15.4 | 20.4 | 23.1 | 25.5 | 27.6 | 29.1 | 30.0 | 30.9 c | 31.9 c | | |
| N2 | 10.2 | 15.2 | 20.2 | 22.9 | 25.3 | 27.4 | 28.8 | 29.8 | 30.7 | 31.7 c | 32.7 c | |

(c: clipped samples in the step.) Clipped samples, x1 / x2 of 3.1 M, at the
first two clipped steps: N0.1 93 / 82 (78), 523 / 445 (79); N0.5 14 / 10
(77), 58 / 46 (78); N1 2 / 0 (76), 9 / 9 (77); N2 5 / 4 (77), 46 / 31 (78).

- **One scale for all noise widths:** J/N60 within 0.1 dB for N0.1 to N1;
  N2 0.2 dB lower (its band edge at L1 - 1 MHz is 0.5 MHz from the Pluto
  passband edge). J/N60 = gain - 44.6 dB to 70 dB for all.
- **Gaussian clip onset:** first clipped samples at J/N60 30.9 to 32.9
  (gain 76 to 78), predicted about 31. The step where the first few samples
  clip is a matter of chance at this count; 5 to 93 clipped samples per
  3.1 M are reached at J/N60 31.7 to 32.9 for all four. N runs: steps up to J/N60 30
  are clean for every width.
- **Spectral regrowth (N0.1, skirt at 100 kHz from L1, outside its band):**
  +0.6 / +0.8 / +1.2 / +1.6 dB at gain 74 / 75 / 76 / 77, before any
  clipping, then +3.4 and +11.9 dB at 78 and 79 (clipped). By the rule of
  Section 2.6 (no use above a skirt rise of 1 dB), **N0.1 is limited to gain
  75 (J/N60 30.1)**. N0.5 (skirt at 500 kHz): +0.7 / +0.9 / +1.2 dB at 76 /
  77 / 78, limit gain 77 (J/N60 31.9, already clipped). N1 and N2 have no
  skirt point outside their band within the analysis (500 kHz); their
  regrowth is not measured here.
- **Inter-channel:** phase x2/x1 -90.6 to -91.2 deg, ratio -0.05 to -0.14 dB
  in band, coherence to 0.9999 / 1.0000 for all, as N1 and CW.
- **Phase slope:** N2 over L1 +/- 1.2 MHz: +0.10 to +0.17 deg/MHz from
  J/N60 23 up (standard deviation of 3 captures 0.001 to 0.008), N0.5 +0.06
  to +0.17; N0.1 too narrow for a slope (spread 0.03 to 0.16). Same as N1:
  **tau about -0.3 to -0.45 ns**, not 1.2 ns. All widths show the same level
  dependence: highest at J/N60 10 (+0.38 to +0.57), lowest near J/N60 25
  (+0.06 to +0.10), rising again to +0.17 at the clip onset. The jammer path
  up to the splitter is common to both channels, so a level-dependent slope
  must come from the Pluto (or the correlated noise of the two channels at
  low J/N, |rho| about 0.01 without a jammer). Open for the S runs.
- **LO leakage at L1:** visible with N2 (lowest spectral density): the
  strongest bin within 15 kHz of L1 is 7.0 / 5.0 / 5.7 / 5.4 dB over the
  jammer spectrum at gain 55 / 60 / 70 / 72.5 dB, 2.6 to 3.5 dB elsewhere
  (statistical level). Estimated about -35 to -37 dBc against the total
  jammer power; N0.1, N0.5: not visible. Below -30 dBc: no LO offset.

**P2 so far, for the N runs:** CW and all Gaussian noise widths have one
gain scale (noise 9.6 dB more gain than CW for the same J/N60); clean up to
J/N60 30 (noise) and 41.7 (CW); N0.1 limited to J/N60 30.1 by regrowth.

### P2-c PN, CH-f, CH-m, CH-s (2026-11-21, 13:49 to 13:53)

One run, the four files in turn, as P2-b, `--band 0,2.4e6`, `--max-gain 83`.
Files (all -6.02 dBFS rms, the CW drive; centre L1, no LO offset): PN
(random BPSK 1.023 Mcps, main-lobe filtered, 8.184 MSPS, bw99 1.60 MHz,
crest 2.9 dB, sha256 `8e5daf77...`), CH-f (sawtooth chirp L1 +/- 1 MHz,
period 10 us, low-pass 1.2 MHz, bw99 2.2 MHz, crest 1.2 dB, `9a9f88e1...`),
CH-m (1 ms, 1.97 MHz, 0 dB, `7ec85e4a...`), CH-s (100 ms, 1.98 MHz, 0 dB,
`93d4df4a...`). Logs `results/t3_t5b_P2_{PN,CH-f,CH-m,CH-s}_*.txt`,
`results/t5b_P2_{PN,CH-f,CH-m,CH-s}_jammer_20261121-134947.txt`. No
underflow, sequence error or other event; `JAMMER OFF` after each file, no
line after each `quit`. Rates: 8 MSPS exact; PN reads 8184000.1 Hz
(0.01 ppm, inside the 1 Hz check of the script).

J/N60 per gain (c: clipped samples; CW from C3 for comparison):

| Gain (dB) | 55 | 60 | 65 | 67.5 | 70 | 72.5 | 75 | 76 | 77 | 78 | 79 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| PN | 19.3 | 24.3 | 29.3 | 32.0 | 34.4 | 36.4 | 38.8 | 39.7 c | 40.7 c | | |
| CH-f | 19.2 | 24.2 | 29.2 | 31.9 | 34.3 | 36.3 | 38.7 | 39.6 | 40.6 | 41.6 c | 42.6 c |
| CH-m | 19.2 | 24.2 | 29.2 | 31.9 | 34.3 | 36.3 | 38.7 | 39.6 | 40.5 | 41.5 c | 42.5 c |
| CH-s | 19.1 | 24.2 | 29.2 | 31.9 | 34.3 | 36.3 | 38.7 | 39.6 | 40.5 | 41.5 c | 42.5 c |
| CW (C3) | 19.8 (55) | | 29.8 | | 34.9 | 37.0 | 39.4 | | 41.7 (77.5) | 42.7 c (78.5) | |

Clipped samples, x1 / x2 of 3.1 M: PN 824 / 329 (76), 48117 / 39761 (77);
CH-f 23680 / 15615 (78); CH-m 228 / 29 (78); CH-s 132 / 6 (78); all three
chirps 0.25 to 0.34 M at 79.

- **Scale:** the constant-envelope files follow CW, 0.5 to 0.7 dB lower
  (J/N60 = gain - 35.8 dB below 70 dB, CW gain - 35.2). The cause is not
  separated here (2 MHz waveforms at 8 MSPS against the CW line at 1 MSPS;
  N2 was also 0.2 dB below N1); it is inside the +/- 1 dB of the T5 table.
  Compression as CW from 70 dB.
- **Clip onset:** chirps at gain 78 (J/N60 41.5 to 41.6), as CW (between
  41.7 and 42.7); PN 2 dB earlier, at gain 76 (J/N60 39.7), as its 2.9 dB
  crest factor suggests. Predicted 40 to 42 (Section 2.6). Clean steps for
  the N runs: PN to J/N60 38.8, chirps to 40.5.
- **Inter-channel:** phase x2/x1 -90.6 to -90.8 deg, ratio -0.08 to -0.16 dB,
  coherence to 1.0000 below clipping, as all other waveforms. At gain 79
  (heavy clipping) CH-f and CH-m move to -91.4 / -91.7 deg and coherence
  0.995.
- **Phase slope over L1 +/- 1.2 MHz:** all four +0.20 to +0.22 deg/MHz at
  J/N60 34 to 41 (standard deviation 0.000 to 0.004), +0.06 to +0.08 at
  J/N60 29, +0.17 to +0.26 at J/N60 19. The same level dependence as the
  noise files, with the minimum near J/N60 25 to 29 and +0.2 deg/MHz (tau
  about -0.55 ns) at the high levels.
- **LO leakage:** not readable from the chirps: the line search at L1 finds
  the chirps' own spectral lines (CH-f: lines every 100 kHz, 53 to 70 dB
  over the floor, the strongest spurs at L1 + 0.6 / + 0.7 / - 0.6 / + 0.5 MHz
  at gain 75, each 5.4 kHz low as the line offset; CH-m: about 20 dB;
  CH-s: 1 to 10 dB). PN: no line at L1
  (2.4 to 3.0 dB, statistical level).
