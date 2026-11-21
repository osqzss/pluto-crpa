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

### P2-d pulsed CW and pulsed N1 (2026-11-21, 13:55 to 13:58)

Two runs of four files each, as P2-b, 5 captures per step (105 ms each, so a
capture holds at least one 100 ms period), fixed steps for an in-pulse J/N60
of about 20 and 30: P-CW at gain 55 and 65 (`--max-gain 68`), P-N1 at 64 and
74 (`--max-gain 77`). The +/- 3 dB level stop was off for this run (the mean
of one capture of a 100 ms period depends on whether it holds one or two
pulses); the other stop rules applied. Files: P-CW-{0.1,1,10,100}ms (CW at
L1 + 200 kHz inside the file, centre L1; 0.1 ms low-passed to 1.2 MHz),
P-N1-{0.1,1,10,100}ms (N1 gated; 0.1 ms low-passed), duty 10 %, in-pulse
level as the continuous files (-6.02 / -15 dBFS), 8 MSPS. Logs
`results/t3_t5b_P2_P-*_*.txt`, `results/t5b_P2_P-*_jammer_*.txt`. No
underflow on any of the 56 STATUS and stop lines; `JAMMER OFF` after each
file; no clipped sample; no line after each `quit`.

In-pulse levels from the saved raw captures (scratch analysis: x1 power in
10 us blocks, blocks above the geometric mean of the noise and the 99th
percentile are "on", one block either side of each edge left out; J/N60 in
the pulse against N = -42.52 dBFS):

| File | Gain | Mean J/N60 (log) | Duty seen | In-pulse J/N60 | x2/x1 in pulse | Off level x1 (dBFS) |
|---|---|---|---|---|---|---|
| P-CW-0.1ms | 55 / 65 | 9.5 / 19.6 | not resolved | (19.5 / 29.6 from mean + 10 dB) | -0.11 / -0.12 dB, -90.8 / -90.7 deg | - |
| P-CW-1ms | 55 / 65 | 9.5 / 19.5 | 0.110 | 19.5 / 29.5 | -0.11 / -0.12, -90.8 / -90.7 | -42.52 / -42.49 |
| P-CW-10ms | 55 / 65 | 9.6 / 19.6 | 0.096 to 0.106 | 19.5 / 29.5 | as above | -42.52 / -42.48 |
| P-CW-100ms | 55 / 65 | 9.3 / 19.7 | 0.095 to 0.142 | 19.5 / 29.5 | as above | -42.52 / -42.46 |
| P-N1-0.1ms | 64 / 74 | 9.3 / 19.0 | not resolved | (19.3 / 29.0 from mean + 10 dB) | -0.10 / -0.11, -90.8 / -90.7 | - |
| P-N1-1ms | 64 / 74 | 9.3 / 19.0 | 0.101 to 0.110 | 19.3 / 29.0 | -0.11 / -0.11, -90.8 / -90.7 | -42.49 / **-41.86** |
| P-N1-10ms | 64 / 74 | 9.3 / 19.1 | 0.096 to 0.106 | 19.3 / 28.9 | as above | -42.49 / **-41.90** |
| P-N1-100ms | 64 / 74 | 9.4 / 19.1 | 0.095 to 0.142 | 19.3 / 29.0 | as above | -42.49 / **-41.89** |

- **In-pulse levels as the continuous files:** P-CW 19.5 / 29.5 (CW at
  8 MSPS: the PN / chirp scale, 29.2 to 29.3 at gain 65), P-N1 19.3 / 29.0
  (N1: 19.4 at 64, 29.1 at 74 from the P2-a table). The mean levels are
  10.0 dB lower (duty 10 %). In-pulse x2/x1 phase and ratio as continuous.
- **0.1 ms period:** the 10 us pulses equal one analysis block, so on and
  off are not separated at this resolution; the mean is the useful number,
  and the in-pulse level follows as mean + 10 dB.
- **Duty seen** 0.10 to 0.11 for 1 to 100 ms (0.142 where a 105 ms capture
  held two 10 ms pulses of the 100 ms file).
- **Finding: the off-time level at P-N1 gain 74 is 0.6 dB above the noise**
  (-41.86 to -41.90 against -42.52 dBFS, all three resolved periods), while
  at gain 64 and for P-CW at 65 it is within 0.05 dB. The file is zero in
  the off-time, so this is B206mini output with zero samples at high TX
  gain: added power about -50.5 dBFS at x1, 8.0 dB under the receiver noise
  in 9 MHz. It is common to both channels (the jammer path), so PI should
  null it with the jammer; it raises the floor seen by the u-blox in F runs
  without suppression at the high steps. Not seen as such in the continuous
  runs (hidden under the jammer). To check in the N runs: residual in y in
  the off-time.

**P2 done for group A** (P2-W, N5 and N10 at 30.72 MSPS, follows before the
group W runs). Clean levels for the N runs, J/N60 in the jammer (in-pulse
for P-x): CW to 41.7, PN to 38.8, chirps to 40.5, Gaussian noise to 30
(N0.1 to 30.1 by regrowth), pulsed as their base waveform.

## P3: GPS and jammer together, Pluto RX-only (2026-11-21, 14:03 to 14:05)

Plan: `docs/t5b_plan.md`, "P3 plan". Bench as P2; bladeRF plugged back in by
the user; `bladegps -e brdc3300.18n` (in `~/Work/bladeGPS`, TX gain
unchanged) through 40 dB, B206mini through 30 + 20 dB. Captures `--passive
--cw-offset 0,200e3 --cw-span 15e3 --spurs 5 --save tmp/t5b_cap` (N1 steps
also `--band 0,1.2e6`). Logs `results/t3_t5b_P3_*_20261121-140*.txt`,
`results/t5b_P3_{cw,N1}_jammer_20261121-140349.txt`,
`results/t5b_P3_bladegps_20261121-140349.txt`. No clipping; no underflow on
any of the 12 STATUS / stop lines; `JAMMER OFF` after each jammer;
`bladegps` stopped with `q` ("Done!"), 71.6 s simulated.

**Carrier phase under a wideband jammer.** The CW line measurement of
`t3_phase.py` (3 bins of 153 Hz) takes the N1 jammer in those bins with the
carrier, which pulls the carrier phase towards the jammer phase: 169.5 deg at
N1 gain 55 and about 185 deg at gain 64 (raw log values -165 to 180; their
plain mean -80 in the runner output is a wrap artefact). So phi_G was taken
offline from the saved raw captures (scratch analysis): Hann FFT over the
whole capture (9.54 Hz bins), carrier = strongest bin within 1 kHz of
L1, X2 conj(X1) summed over 7 bins, minus the mean cross-spectrum of the
bins 30 Hz to 3 kHz either side (the jammer at the carrier) times 7;
circular means. Same method for all steps; for GPS alone and CW it equals the
raw value within 0.01 deg.

| Step | Sources | Carrier over local background (7 bins) | phi_G x2/x1 (std per capture) | GPS ratio | phi_J x2/x1 | D |
|---|---|---|---|---|---|---|
| P3-0 | bladeRF idle | (no carrier: 2.4 dB, noise) | - | - | - | - |
| P3-1 | GPS alone, 10 captures | 42.8 dB | 167.55 (0.17) | -0.53 dB | - | - |
| P3-2 | + CW gain 55 (J/N60 about 19.8) | 42.7 dB | 168.12 (0.21) | -0.61 | -90.66 (line, 200 kHz) | **101.2** |
| P3-3 | CW gain 70 (J/N60 about 34.9) | 40.9 dB | 168.01 (0.26) | -0.60 | -90.55 | **101.4** |
| P3-4 | N1 gain 55 (J/N60 10.4) | 22.9 dB | 166.77 (2.13; mean +/- 0.55) | -0.60 | -91.07 (local, at L1) | **102.2 +/- 0.6** |
| P3-5 | N1 gain 64 (J/N60 about 19.3) | 14.2 dB | 166.29 (5.56; mean +/- 1.4) | -0.64 | -90.65 (local) | **103.1 +/- 1.4** |
| P3-6 | GPS alone, 5 captures | 42.5 dB | 167.33 (0.20) | -0.53 | - | - |
| P3-7 | `bladegps` stopped | (1.7 dB: no carrier left) | - | - | - | - |

D = 360 - (phi_G - phi_J). The N1 band phase over L1 +/- 0.6 MHz is -91.81
at gain 55 (biased by the carrier inside the band at J/N60 10) and -90.76 at
64; P2 without GPS gave -91.14 / -90.8 at the same gains.

- **D in V3 with the B206mini: 101.2 / 101.4 deg (CW), 102.2 +/- 0.6 /
  103.1 +/- 1.4 deg (N1)**, against 101.6 predicted from the separate
  measurements and 100.4 / 100.5 in T5 P3 (B205mini, phi_J 0.6 deg more
  negative). Pass criterion (within 1.5 deg of 101.6): met by all four, N1 at
  gain 64 at the edge within its uncertainty.
- phi_G before and after the jammer runs: 167.55 / 167.33 deg (pass: within
  0.5 deg), against 167.64 in T5b P1 (2026-11-18).
- With the CW jammer streaming phi_G is 0.5 deg higher (168.1 / 168.0 at
  J/N60 20 and 35, the same at both levels); T5 P3 saw the same sign
  (+0.3 to +0.45 deg against P1). Not level-dependent, so not a coupling of
  the jammer power; possibly the B206mini TX port state (streaming against
  idle) changing the combiner network. With N1 the shift is not resolved
  (166.8 +/- 0.6, 166.3 +/- 1.4).
- Carrier over the floor 1.9 dB lower next to the CW at J/N60 35 (T5: 1.3 dB):
  the floor rise around the jammer, as in P2.
- With these D the GPS loss with PI is as in T4 / T5: about +0.4 dB against
  w = [1, 0] with the jammer off (`docs/t4_plan.md`, Section 5; cos D changes
  by less than 0.05 between 100.5 and 103 deg).
- **Tool note for the P and N runs with wideband jammers:** the carrier line
  phase of `t3_phase.py` is biased once the jammer density in the 3 line bins
  is within about 20 dB of the carrier; use the saved captures with the
  background removal above.

## S-V3a: wideband transfer and null depth from the P2 captures, offline (2026-11-21)

Plan: `docs/t5b_plan.md`, "S-V3 plan". No RF. The P2 noise-ladder captures
(V3, GPS off, bladeRF unplugged, capture mux at reset, RX gain 60, 3 captures
of 1048576 samples per step, a noise-only step per file) are the S-V3 bench
state. `scripts/t5b_stap.py` (changed, see below) on N0.1, N0.5, N1, N2 at
gains 60 / 65 / 70 / 75 (J/N60 about 15 / 20 / 25 / 30), band = the jammer
width; rows in `results/t5b_S-V3a.csv`.

**Tool changes** (`t5b_stap.py`; `--selftest` PASS, 10 checks, about 10 s):
- The noise cross-spectrum N21 is subtracted from S21 in the H(f) fit
  (correlated receiver noise, |rho| 0.005 to 0.012 in the band). It changes
  tau by at most 0.02 ns, so it is not the cause of the level dependence.
- The single-weight limit is printed for the delay, the amplitude slope and
  both (new selftest check: 0.5 dB/MHz over 2 MHz gives 29.6 dB, as the
  formula).
- For every tap count also the noise gain |w|^2 and the **GPS loss**: C/N0
  of a correlator after the combiner over x1 alone with the jammer off, C/A
  main lobe, GPS x2/x1 = 167.5 deg / -0.53 dB (P3), `--gps` to change it.
  Negative = better than one element without a jammer. New selftest check
  against the analytic value for one weight (0.08 dB against 0.06 dB).

**Why null depth misled for L > 1.** On synthetic data without a delay
(white noise, J/N60 30, 1 MHz), 3 taps gave a 40 dB null against > 57 dB
for one weight, with the noise gain 0.9 dB instead of 3.1 dB. Output budget
in the band (dB re the in-band noise of x1): 1 tap: residual jammer -19.1,
noise +3.1; 3 taps: residual +0.2, noise -0.6; 9 taps: residual -17.0,
noise -1.7. The x1 taps predict the band-limited jammer in x1 (a temporal
notch), which trades residual jammer for full-band noise and notches a GPS
signal in the band too. This is correct power minimization, not a bug; null
depth is not the figure for L > 1, the GPS loss is.

**Tau estimator check.** Synthetic captures with the measured H(f) (tau
-0.39 ns, -0.048 dB/MHz) on the real noise captures, N2: fitted tau -0.43 /
-0.38 / -0.38 / -0.39 / -0.40 ns at J/N60 10 / 15 / 20 / 25 / 30. The fit is
unbiased, so the level dependence below is in the hardware.

**Results (measured case; J/N60 30 = gain 75):**

| Jammer | tau (ns) at gain 60 / 65 / 70 / 75 | Amplitude slope at 75 (dB/MHz) | 1-weight null at 75 | Model limit (delay + slope) | 1-weight GPS loss at 65 / 70 / 75 | 3 / 5 / 9 taps GPS loss at 75 |
|---|---|---|---|---|---|---|
| N0.1 | -0.49 / -0.24 / -0.27 / -0.38 | -0.045 | 57.7 dB | 75.6 | -0.36 / -0.53 / -0.60 | -0.61 / -0.62 / -0.42 |
| N0.5 | -0.53 / -0.52 / -0.17 / -0.40 | -0.049 | 56.5 | 61.0 | -0.34 / -0.52 / -0.55 | -0.18 / +1.07 / -0.04 |
| N1 | -0.69 / -0.48 / -0.23 / -0.39 | -0.048 | 52.5 | 55.1 | -0.38 / -0.52 / -0.53 | +1.81 / +0.19 / -0.54 |
| N2 | -0.78 / -0.48 / -0.28 / -0.37 | -0.048 | 48.8 | 49.2 | -0.50 / -0.58 / -0.60 | +0.52 / -0.64 / -0.33 |

- **One weight is not wideband-limited on this bench at reachable J/N.** The
  GPS loss with one weight is -0.5 to -0.6 dB at J/N60 25 to 30 for all four
  widths: the jammer is removed from the correlator and what is left is the
  PI combination of the GPS signal for D about 101 deg (analytic -0.5 dB;
  T4: about +0.4 dB against w = [1, 0]). With the delay removed or replaced
  by the lambda/2 array delay the loss changes by less than 0.07 dB. A
  48.8 dB null at J/N60 30 leaves the residual about 19 dB under the
  noise; the delay / slope limit would start to cost C/N0 only at J/N60 of
  about 45 and more (2 MHz), above what the B206mini delivers unclipped
  (32.9 for noise, P2).
- **The single-weight null over 1 to 2 MHz follows the delay plus amplitude
  slope model**: 52.5 / 48.8 dB against 55.1 / 49.2 (N1 / N2). The
  amplitude slope (-0.05 dB/MHz) limits more than the delay (63 / 57 dB
  alone).
- **Multi-tap combiners give no gain here** and are erratic from 3
  captures (+1.8 dB at N1 3 taps, +1.1 dB at N0.5 5 taps): their benefit
  would only show where one weight is limited, which these levels do not
  reach. Not pursued; `crpa_core` is a single weight.
- **tau and the amplitude slope depend on the level, together**: -0.7 to
  -1.1 ns and -0.08 to -0.10 dB/MHz at J/N60 10 to 15, smallest at J/N60
  25 to 29 (-0.2 to -0.3 ns, -0.04), and -0.45 to -0.6 ns above 30 (PN and
  chirps up to J/N60 40, same values at the same J/N60 for all five
  waveforms); the phase at the band centre moves -90.95 to -90.6 deg with
  it. Not an estimator effect (check above) and not the noise cross-spectrum.
  Cause open (Pluto RX chain against level, or the B206mini output); S-V1
  (jammer legs recabled) can separate the cable from the rest. For the null
  depth it is a few dB at most at the levels where one weight matters.

## N-a: CW null depth with PI, RX-only, same-day check against T5 (2026-11-21, 14:40 to 14:45)

`crpa_ctl run --mode pi --load 24 --cap-sel --duration 600 --out
/tmp/t5b_Na` (dry run, by the user; quit by the user at 267 s, after the
run; safe state confirmed). bladeRF unplugged, B206mini CW at L1 + 200 kHz
through 30 + 20 dB (`--max-gain 85`). Per step 10 passive captures of y
(ch0/1) and x1 (ch2/3), `--cap y --cw-offset 0,200e3 --cw-span 15e3
--spurs 6 --save`. Logs `results/t3_t5b_N-a_CW_*_20261121-14*.txt`,
`results/t5b_N-a_CW_jammer_20261121-144050.txt`, `results/t5b_N-a.txt`
(crpa_ctl), `results/t5b_N-a_every100.csv`. No underflow on any STATUS
line; `JAMMER OFF` confirmed; no line in x1 after the jammer (2.7 dB);
sat_blocks 0 throughout; PEAK 2048 only at 80 and 82 (marked +); 2220 of
265218 blocks missed, all during the captures (as T4 / T5).

| Gain | J/N60 (x1) | Null depth (x1 line over y line) | T5 G60-N | y | w2 (w1 about 0.985 to 0.999) |
|---|---|---|---|---|---|
| off | - | - | - | -42.57 dBFS | \|w2\| 0.002 to 0.03 |
| 55 | 19.5 | 38.8 dB | - | -39.58 | +0.013 + 1.000j |
| 60 | 24.6 | 48.8 | - | -39.65 | +0.010 + 1.000j |
| 65 | 29.6 | 58.4 | 57.8 | -39.73 | +0.009 + 1.000j |
| 70 | 34.6 | 67.3 | 67.3 | -39.62 | +0.010 + 1.000j |
| 72.5 | 36.7 | 71.7 | 71.2 | -39.58 | +0.011 + 1.000j |
| 75 | 39.1 | 75.1 | 74.7 | -39.51 | +0.012 + 1.000j |
| 77.5 | 41.4 | 76.4 | 74.2 | -38.09 (T5 -35.91) | +0.012 + 1.000j |
| 80 + | clipped | 64.1 | 62.1 | -30.37 | +0.023 + 0.999j |
| 82 + | clipped | 66.8 | 64.0 | -31.55 | |

- The null grows 10 dB per 5 dB of J/N60 to J/N60 39 and stops near 75 dB,
  as T5 (the hardware ceiling): the B206mini does not change it.
- Same-day check (Section 6, "CW F / P"): within 0.6 dB of T5 G60-N at 65 to
  75. At 77.5, just under full scale (x1 -1.09 dBFS, T5 -0.73), the null is
  2.2 dB deeper and y 2.2 dB lower than in T5; the clipped steps 2.0 / 2.8 dB
  deeper. The difference is in the favourable direction and follows the
  0.4 dB lower drive near full scale.

## N-b: noise null depth with PI, RX-only (2026-11-21, 14:52 to 14:58)

`crpa_ctl run --mode pi --load 24 --cap-sel --duration 1500 --out
/tmp/t5b_Nb` (dry run, by the user; quit at 420 s, after the run; safe state
confirmed, no FRAME_ERR). bladeRF unplugged. Files N0.1 / N0.5 / N1 / N2,
each: off step, gains 65 / 70 / 75 / 76 (clip onset) / 78 + / 80 +, `off`,
`quit`, after step; 10 captures per step, `--cap y --band 0,B` (B = 0.12 /
0.6 / 1.2 / 2.4 MHz) `--save`. Logs `results/t3_t5b_N-b_*_20261121-14*.txt`,
`results/t5b_N-b_*_jammer_20261121-145227.txt`, `results/t5b_N-b.txt`
(crpa_ctl), `results/t5b_N-b_every100.csv`. Levels within 0.1 dB of P2; no
underflow on any of the 60 STATUS / stop lines; `JAMMER OFF` after each
file; x1 clipped: 0 to 2 samples at 76, 40 to 107 at 78, 1143 to 2325 at
80 (of 10.5 M); y never clipped.

**Null depth = jammer in x1 over jammer in y, in the band.** With PI on, y
holds the noise of both channels (|w2| = 1.000, |w1| 0.984 to 0.999), about
2.9 dB more than the off step, so the band reference of the off step does
not apply to y (the `band_ratio_db` column of the logs understates the null
by up to 13 dB). The y noise was computed as
n_y = |w1|^2 n11 + |w2|^2 n22 + 2 Re(conj(w1) w2 conj(n21)), with n11 from
the off step of the same file, n22 / n11 and the correlated part n21 / n11
from the P2 off captures of the same band, and the weights from the
`crpa_ctl` CSV on each step's x1 plateau (scratch analysis). The residual
(y band power less n_y) is 0.09 to 0.36 dB of n_y at J/N60 30, above its
uncertainty (0.02 dB drift, 3 sigma), so all values are values, not bounds.

| J/N60 (gain) | N0.1 | N0.5 | N1 | N2 |
|---|---|---|---|---|
| 20 (65) | 39.9 dB (offline 40.4) | 39.9 (40.1) | 39.6 (39.5) | 37.1 (38.2) |
| 25 (70) | 50.0 (50.1) | 49.5 (49.8) | 48.5 (48.3) | 44.8 (46.0) |
| 30 (75) | 57.3 (57.7) | 55.6 (56.5) | 53.6 (52.5) | 48.0 (48.8) |
| 31 (76, clip onset) | 58.3 | 56.5 | 54.2 | 48.0 |
| 33 (78 +) | 53.3 | 53.5 | 51.1 | 47.3 |
| 35 (80 +, clipped) | 39.3 | 40.0 | 40.4 | 39.6 |
| Model at J/N60 30: J/N limit (CW, N-a: 58.4) with the delay + amplitude-slope limit (S-V3a) | 58.3 | 56.5 | 53.4 | 48.7 |

(Offline: single weight on the P2 captures at the same gain, S-V3a.)

- **Hardware agrees with offline within 1.2 dB at every step** (criterion
  of Section 7, compared against the P2 captures as decided: 3 dB, met) and
  **with the model within 1 dB at J/N60 30** (criterion: 3 dB, met). The
  model is the J/N-limited CW null combined with the S-V3a limit of the
  delay (-0.39 ns) and the amplitude slope (-0.05 dB/MHz). With the delay
  alone (Section 2.3, ND_tau: 63 / 57.5 dB for N1 / N2) N2 would miss by
  9.5 dB: the amplitude slope between the channels is what limits the
  wideband null on this bench.
- Up to J/N60 25 the noise null is the CW null (10 dB per 5 dB of J/N60);
  from J/N60 30 the wider files flatten at their mismatch limit.
- The clip onset (76) costs nothing; at the first + step (J/N60 33, tens of
  clipped samples per 10 M) the null drops by 0.7 to 5 dB; at J/N60 35 it is
  39 to 40 dB for every width (the clipping distortion in x1 is not in x2
  in the same form and cannot be nulled).
- The residual jammer in y at J/N60 30 is 0.09 to 0.36 dB of the noise in
  the band (N1: 0.086 dB, -17 dB): for the u-blox the jammer is gone up to the
  clip onset, as S-V3a predicted.

## N-c: PN and chirp null depth with PI, RX-only (2026-11-21, 15:03 to 15:11)

`crpa_ctl run --mode pi --load 24 --cap-sel --duration 1500 --out
/tmp/t5b_Nc` (dry run, by the user; quit after the run, safe state
confirmed, no FRAME_ERR). bladeRF unplugged. PN: off, gains 55 / 60 / 65 /
70 / 72.5 / 75 / 76 (clip onset) / 78 + / 80 +; CH-f, CH-m, CH-s: off, 55 /
60 / 65 / 70 / 72.5 / 75 / 77 / 78 (clip onset) / 80 + / 82 +; after step;
10 captures per step, `--cap y --band 0,2.4e6 --save`. Logs
`results/t3_t5b_N-c_*_20261121-15*.txt`,
`results/t5b_N-c_*_jammer_20261121-150314.txt`, `results/t5b_N-c.txt`,
`results/t5b_N-c_every100.csv`. Levels within 0.1 dB of P2; no underflow;
`JAMMER OFF` after each file; x1 clipped at the onset steps (PN 431,
CH-f 20405, CH-m 101, CH-s 62 of 10.5 M; P2: 824 / 23680 / 228 / 132) and
in the + steps (0.27 to 0.72 M); y never clipped. Null depth with the y noise
from the weights, as N-b; offline: single weight on the P2 captures of the
same file and gain (`t5b_stap.py --taps 1`, band 2.4 MHz).

| J/N60 (gain) | PN | CH-f | CH-m | CH-s |
|---|---|---|---|---|
| 19 (55) | 35.6 dB (offline 35.7) | 35.6 (35.7) | 35.5 (35.8) | 35.6 (35.4) |
| 24 (60) | 42.3 | 43.5 | 43.6 | 43.3 |
| 29 (65) | 48.8 (49.1) | > 51.4 (52.0) | 51.3 (50.9) | > 51.5 (51.6) |
| 34 (70) | 49.3 (49.3) | 47.5 (47.3) | 47.0 (46.8) | **52.8 (47.2)** |
| 36 (72.5) | 50.3 | 47.3 | 47.2 | **54.0** |
| 39 (75) | 49.3 (49.3) | 47.8 (47.7) | 47.8 (47.6) | **54.3 (48.1)** |
| 39.7 / 40.5 (76 PN, 77 chirps) | 46.7 (onset) | 46.5 | 46.4 | 53.8 |
| 41.5 (78, chirp onset) | - | 41.5 | 42.6 | 44.4 |
| + steps (PN 78 / 80, chirps 80 / 82) | 21.8 / 28.4 | 22.2 / 34.2 | 28.3 / 34.6 | 30.9 / 36.9 |

- **PN, CH-f and CH-m: hardware equals the offline single weight within
  0.6 dB** (criterion 3 dB: met). They fill the 2 MHz within one 1 ms block,
  so they behave as N2: the null stops at 47 to 50 dB from J/N60 29 up, the
  delay + amplitude-slope limit at the level-dependent tau of these levels
  (S-V3a: tau -0.53 to -0.56 ns and -0.05 to -0.06 dB/MHz from J/N60 34; the
  null dips from 51 to 47 between 65 and 70, as tau moves from -0.2 to
  -0.55 ns).
- **CH-s (100 ms sweep): 52.8 to 54.3 dB from J/N60 34 to 40, 5.6 to
  6.2 dB deeper than one fixed weight over the whole sweep (offline).** The
  1 ms loop follows the sweep (20 kHz per block), so each block sees a nearly
  narrowband jammer, as predicted in Section 5. It does not reach the CW null
  (67 to 75 dB at these levels): what limits it is not resolved here. The
  per-block y estimate of the CSV shows single blocks about 1 dB high every
  100 blocks (the 2 MHz jump at the sawtooth wrap) at gain 70; they
  account for about 5 % of the residual, so the wrap is not the main limit.
- Residual in y up to the clip onset: 0.05 to 0.8 dB of the noise in
  the band (PN, CH-f, CH-m up to 2.0 dB at J/N60 40.5); beyond the onset PI
  no longer helps: y rises by 13 to 25 dB of the band noise at the first +
  step (y up to -18 dBFS), as CW in T5. PN fails first (crest factor).

## N-d: pulsed CW and pulsed N1 with PI, RX-only (2026-11-21, 15:17 to 15:26)

`crpa_ctl run --mode pi --load 24 --cap-sel --duration 1500 --out
/tmp/t5b_Nd` (dry run, by the user, alpha 0; one dry run for both parts,
safe state confirmed, no FRAME_ERR). bladeRF unplugged. P-CW at gains 55 /
65 / 75 (in the pulse J/N60 19.5 / 29.5 / about 39), P-N1 at 65 / 75 (20 /
30); duty 10 %; 10 captures per step, `--cap y --band 0,1.2e6 --save`. Logs
`results/t3_t5b_N-d_*_20261121-15*.txt`,
`results/t5b_N-d_*_jammer_20261121-15*.txt`, `results/t5b_N-d.txt`,
`results/t5b_N-d_every100.csv`. No clipping, no underflow, `JAMMER OFF`
after every file.

**Stop and rerun.** The first part (P-CW 0.1, 1, 10 ms) stopped at
15:19:16 on the runner's check "y at least 3 dB under x1 at the first step"
for P-CW-10ms: y was 0.3 dB under x1. Not a fault (PI was active, see below):
the check assumed that PI nulls every waveform. Jammer stopped by the runner,
`JAMMER OFF` confirmed. Rerun after the user's go (15:21 to 15:26), same dry
run: P-N1 0.1 / 1 ms with the check, then P-CW 10 / 100 ms and P-N1 10 /
100 ms without it.

Mean levels over the captures (x1 J/N60 is the mean, 10 dB under the pulse):

| File (pulse length) | Gains | y (dBFS) | Result |
|---|---|---|---|
| P-CW-0.1ms (10 us), P-CW-1ms (100 us) | 55 / 65 / 75 | -39.9 / -39.7 / -39.7 | y at the two-channel noise: nulled |
| P-N1-0.1ms, P-N1-1ms | 65 / 75 | -39.8 / -39.7 | nulled |
| P-CW-10ms (1 ms) | 55 / 65 / 75 | -38.3 / -31.9 / -25.1 | mostly not nulled |
| P-N1-10ms (1 ms) | 65 / 75 | -32.7 / -24.5 | not nulled (y 1 to 2 dB under x1) |
| P-CW-100ms (10 ms) | 55 / 65 / 75 | -41.4 / -38.2 / -32.1 | nulled except the onset |
| P-N1-100ms (10 ms) | 65 / 75 | -39.4 / -33.6 | nulled except the onset |

**Per block (crpa_ctl CSV, top step, alpha 0):**

| File | Blocks per pulse | First block of the pulse: x1 / y (dBFS) | Later blocks: x1 / y | Block after the pulse: \|w2\| |
|---|---|---|---|---|
| P-CW-10ms | 2 (1025 of 1047 pulses), 1 | -17.5 / -18.4 (0.9 dB) | -3.6 / -35.8 | 0.10 |
| P-N1-10ms | 2 (1024 of 1046), 1 | -13.9 / -15.0 (1.1 dB) | -18.7 / -39.7 | 0.12 |
| P-CW-100ms | 11 (93 of 107), 9 to 10 | -13.9 / -14.7 (0.8 dB) | -3.5 / -39.3 to -39.4 | 0.09 |
| P-N1-100ms | 11 (90 of 106), 8 to 10 | -13.7 / -14.4 (0.7 dB) | -12.7 / -39.5 | 0.08 |

(y "-39.4" is the two-channel noise with \|w2\| = 1, as in the continuous
runs: the jammer is under the noise in those blocks.)

- **The weight loop lags by exactly one block:** the first block that holds
  any part of a pulse is passed with less than 1.1 dB of suppression; from
  the second block on, the pulse is nulled as a continuous jammer. With
  alpha 0, one jammer-free block brings the weights back to about [1, 0]
  (\|w2\| 0.08 to 0.12), so every pulse starts unprotected.
- **What leaks is the pulse energy in its first block.** 1 ms pulses
  (10 ms period) straddle two blocks; the split depends on how the pulses
  fall on the 1 ms block grid, which drifts only slowly (independent
  clocks): in this run P-CW-10ms had most of the pulse in the second block
  (mean y -25 dBFS, about 12 dB suppression overall), P-N1-10ms most in the
  first (1 to 2 dB). 10 ms pulses leak one block in ten (overall about
  17 to 24 dB). Pulses of 100 us and shorter (0.1 and 1 ms periods) are in
  every block and are nulled as their mean power.
- Section 5 predicted up to about 2 leaked blocks per pulse; measured: 1.
  For a 1 ms pulse that is most of the pulse. Whether `--alpha 0.9` (R
  smoothed, decay 0.9 per block) holds the weights over the 9 off blocks of
  the 10 ms period (jammer part of R still 0.39 of the pulse value at the
  next onset) is the question of the alpha 0.9 run; over the 90 off blocks of
  the 100 ms period it decays to 8e-5, so the onset block would leak there
  as with alpha 0.

## N-e: pulsed N1 with PI and alpha 0.9, RX-only (2026-11-21, 15:29 to 15:31)

Added by the user's decision after N-d. `crpa_ctl run --mode pi --load 24
--alpha 0.9 --cap-sel --duration 600 --out /tmp/t5b_Ne` (dry run, by the
user; safe state confirmed, no FRAME_ERR). P-N1-10ms and P-N1-100ms at
gains 65 / 75 (in the pulse J/N60 20 / 30), as N-d; first-step check off.
Logs `results/t3_t5b_N-e_*_20261121-153*.txt`,
`results/t5b_N-e_*_jammer_20261121-152956.txt`, `results/t5b_N-e.txt`,
`results/t5b_N-e_every100.csv`. No clipping, no underflow, `JAMMER OFF`
after both files.

| File, gain | Mean y, alpha 0.9 (N-e) | Mean y, alpha 0 (N-d) | \|w2\| before the onset | First block of the pulse: x1 / y | Second block: y |
|---|---|---|---|---|---|
| P-N1-10ms, 65 | -39.62 dBFS | -32.65 | 0.87 | -23.0 / -37.1 | -39.7 |
| P-N1-10ms, 75 | **-39.66** | -24.53 | 0.99 | -13.7 / **-39.1** | -39.7 |
| P-N1-100ms, 65 | -38.81 | -39.40 | 0.03 | -22.6 / -22.8 | -38.0 (third: -39.2) |
| P-N1-100ms, 75 | -33.36 | -33.61 | 0.14 | -13.2 / -14.5 | -39.2 |

- **10 ms period: alpha 0.9 holds the weights over the 9 off blocks**
  (\|w2\| 0.99 at J/N60 30, 0.87 at 20), so the onset block is nulled too:
  y at the two-channel noise at J/N60 30 (onset block 0.6 dB over it), and
  about 14 dB suppression in the onset block at J/N60 20. The 1 ms pulses
  that passed with alpha 0 are removed.
- **100 ms period: no gain.** After 90 off blocks the jammer part of R has
  decayed (\|w2\| 0.03 / 0.14 at the onset), so the onset block leaks as
  with alpha 0; at J/N60 20 the smoothing also slows the convergence (second
  block 1.7 dB over the noise, third 0.5 dB), mean y 0.6 dB higher than with
  alpha 0.
- As predicted from the decay 0.9^n (Section "N-d"): alpha trades the
  convergence time at an onset for memory over the off time; a pulse period
  of up to about 20 to 30 blocks at these levels is covered.
- For the P runs: P-P-N1-10ms with alpha 0 is expected to give the u-blox
  most of the jammer (the F-run level, mean J/N60 10 dB under the pulse),
  and with alpha 0.9 to suppress it.

## F-N1: fixed w = [1, 0], N1 ladder, receiver run (2026-11-21, 15:37 to 15:54)

Host side (Claude Code, `f_run.sh`, temporary): idle check with the
bladeRF plugged in (line at L1 1.97 dB: quiet), `bladegps -e brdc3300.18n`
(carrier 37.9 dB, phase 167.66 deg), `ubx_log.py`, `t4_jammer.py --on
--ext-att 50 --max-gain 63 --gain off --waveform tmp/t5b/N1.sc16`. The user
started `crpa_ctl run --on --tx-att 80 --min-tx-att 50 --mode fixed --w
1,0,0,0 --csv-every 10 --out /tmp/t5b_FN1`, CONDUCTED, `tx 60`, `tx 50`;
then `t0` and the cold start together (T0 1795243121.224). Jammer steps by
stdin commands from t0 (not `--schedule`, so that the 30 s fix-loss rule's
`off` is final): off to 200 s, then gain 32.5 to 59.5 in 3 dB steps (J/N60
-12.1 to +14.9 by gain - 44.6), about 60 s each, off at 804 s, quit at
898 s. Files: `t5b_F-N1.ubx` (+ `.idx`), `t5b_F-N1_jammer.txt`,
`t5b_F-N1_bladegps.txt`, `t5b_F-N1.txt` (crpa_ctl), `t5b_F-N1_every100.csv`,
`t3_t5b_F-N1_{idle,gps}_*.txt`. No underflow, `JAMMER OFF` confirmed,
`bladegps` "Done", safe state; no FRAME_ERR, no missed block, no
saturation. Table from `t5_steps.py --cal` (gain - 44.6); the x1 column
confirms the scale (step 10: x1 -27.59 dBFS = J/N60 14.8).

| Step | Jammer | J/N60 or x1 over ref. | Window (s) | C/N0 against ref. | Against T1 | PRNs | SVs used | 3D fix | AGC | Jamming ind. | x1 / y dBFS | Peak | Sat. blocks | Missed | \|w2\| | STATUS |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | off | +0.0 dB | 60 to 197 | +0.00 dB | -5.18 dB | 11 | 11 to 11 | 137 of 137 | 2028 to 2028 | 63 to 112 | -41.91 / -41.91 | 71 | 0 | 0 | 0.000 | 1 |
| 1 | 32.5 dB | -12.1 | 217 to 258 | -1.74 dB | -6.92 dB | 11 | 11 to 11 | 41 of 41 | 2028 to 2028 | 62 to 111 | -41.71 / -41.71 | 70 | 0 | 0 | 0.000 | 1 |
| 2 | 35.5 dB | -9.1 | 278 to 315 | -3.11 dB | -8.29 dB | 11 | 11 to 11 | 37 of 37 | 2028 to 2028 | 102 to 111 | -41.51 / -41.51 | 72 | 0 | 0 | 0.000 | 1 |
| 3 | 38.5 dB | -6.1 | 335 to 376 | -4.57 dB | -9.75 dB | 11 | 11 to 11 | 41 of 41 | 2028 to 2028 | 103 to 111 | -41.15 / -41.15 | 79 | 0 | 0 | 0.000 | 1 |
| 4 | 41.5 dB | -3.1 | 396 to 438 | -6.86 dB | -12.04 dB | 11 | 11 to 11 | 42 of 42 | 2028 to 2028 | 104 to 111 | -40.49 / -40.49 | 83 | 0 | 0 | 0.000 | 1 |
| 5 | 44.5 dB | -0.1 | 458 to 499 | -9.24 dB | -14.42 dB | 11 | 11 to 11 | 41 of 41 | 1872 to 1872 | 80 to 87 | -39.40 / -39.40 | 88 | 0 | 0 | 0.000 | 1 |
| 6 | 47.5 dB | 2.9 | 519 to 556 | -12.15 dB | -17.34 dB | 11 | 11 to 11 | 37 of 37 | 1872 to 1872 | 47 to 86 | -37.80 / -37.80 | 113 | 0 | 0 | 0.000 | 1 |
| 7 | 50.5 dB | 5.9 | 576 to 618 | -15.14 dB | -20.32 dB | 11 | 11 to 11 | 42 of 42 | 1482 to 1482 | 33 to 49 | -35.62 / -35.62 | 142 | 0 | 0 | 0.000 | 1 |
| 8 | 53.5 dB | 8.9 | 638 to 675 | -18.23 dB | -23.41 dB | 11 | 11 to 11 | 37 of 37 | 1326 to 1326 | 26 to 41 | -33.12 / -33.12 | 184 | 0 | 0 | 0.000 | 1 |
| 9 | 56.5 dB | 11.9 | 695 to 737 | -22.22 dB | -27.40 dB | 11 | 9 to 11 | 42 of 42 | 936 to 936 | 17 to 45 | -30.45 / -30.45 | 264 | 0 | 0 | 0.000 | 1 |
| 10 | 59.5 dB | 14.9 | 757 to 799 | -25.14 dB | -30.39 dB | 9 | 7 to 9 | 42 of 42 | 780 to 780 | 15 to 45 | -27.59 / -27.59 | 371 | 0 | 0 | 0.000 | 1 |
| 11 | off | -0.1 dB | 819 to 893 | -0.16 dB | -5.34 dB | 11 | 11 to 11 | 74 of 74 | 2106 to 2106 | 113 to 124 | -41.96 / -41.97 | 69 | 0 | 0 | 0.000 | 1 |

- **Reference: -5.18 dB against T1** (T5 G60-F: -5.13 dB), 11 SVs.
- **6 dB point without suppression: J/N60 -6.1 to -3.1 (about -3.5 by
  interpolation)**, predicted -4 to -2 (Section 6, "F runs"): N1 noise
  costs the u-blox 17 to 19 dB more than CW (T5 G60-F: 13 to 16), as the
  overlap with the C/A main lobe and the M8's CW removal suggest.
- From J/N60 -3 up the C/N0 falls about 1 dB per dB of jammer (the jammer
  dominates the noise).
- **The fix was not lost up to J/N60 +14.9** (C/N0 -25.1 dB against the
  reference, 7 to 9 SVs used, 3D fix in every epoch): the fix-loss point is
  a lower bound, above +15. The ladder was too short (planned to end about 2
  steps after the predicted loss, but the loss came later than assumed).
- AGC from 2028 down to 780; the jamming indicator falls from about 110 to
  15 to 45 (it does not rise with noise).
- Recovery: -0.16 dB, 11 SVs, in the 74 s window after the jammer.

## F-N1b: fixed w = [1, 0], N1 from J/N60 +9, fix-loss point (2026-11-21, 15:57 to 16:08)

Added after F-N1 (decided by the user). As F-N1: idle check (line at L1
1.37 dB), `bladegps` (carrier 36.9 dB, phase 167.73 deg), `crpa_ctl run --on
--tx-att 80 --min-tx-att 50 --mode fixed --w 1,0,0,0 --csv-every 10 --out
/tmp/t5b_FN1b` (user, CONDUCTED, `tx 60`, `tx 50`), `t0` and cold start
together (T0 1795244315.121), off to 200 s, then gain 53.5 to 74.5 planned
(J/N60 8.9 to 29.6), `--max-gain 77.5`. **The 30 s fix-loss rule ended the
ladder at t = 464 s** (fix lost for 32 s at gain 65.5): `off`, 90 s recovery,
quit. Files: `t5b_F-N1b.ubx` (+ `.idx`), `t5b_F-N1b_jammer.txt`,
`t5b_F-N1b_bladegps.txt`, `t5b_F-N1b.txt`, `t5b_F-N1b_every100.csv`,
`t3_t5b_F-N1b_{idle,gps}_*.txt`. No underflow, `JAMMER OFF` confirmed,
safe state; no missed block, no saturation; x1 confirms the scale (gain
65.5: -21.74 dBFS = J/N60 20.7).

| Step | Jammer | J/N60 or x1 over ref. | Window (s) | C/N0 against ref. | Against T1 | PRNs | SVs used | 3D fix | AGC | Jamming ind. | x1 / y dBFS | Peak | Sat. blocks | Missed | \|w2\| | STATUS |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | off | +0.0 dB | 60 to 197 | +0.00 dB | -5.27 dB | 11 | 11 to 11 | 138 of 138 | 2028 to 2028 | 59 to 112 | -41.97 / -41.97 | 74 | 0 | 0 | 0.000 | 1 |
| 1 | 53.5 dB | 8.9 | 217 to 259 | -18.47 dB | -23.74 dB | 11 | 11 to 11 | 41 of 41 | 1248 to 1248 | 22 to 43 | -33.15 / -33.15 | 189 | 0 | 0 | 0.000 | 1 |
| 2 | 56.5 dB | 11.9 | 279 to 315 | -22.01 dB | -27.28 dB | 11 | 10 to 11 | 36 of 36 | 936 to 936 | 21 to 39 | -30.48 / -30.48 | 246 | 0 | 0 | 0.000 | 1 |
| 3 | 59.5 dB | 14.9 | 335 to 376 | -25.36 dB | -30.63 dB | 11 | 7 to 11 | 42 of 42 | 780 to 780 | 16 to 49 | -27.62 / -27.62 | 320 | 0 | 0 | 0.000 | 1 |
| 4 | 62.5 dB | 17.9 | 396 to 438 | -28.36 dB | -33.70 dB | 5 | 3 to 4 | 3 of 41 | 312 to 312 | 13 to 44 | -24.69 / -24.69 | 444 | 0 | 0 | 0.000 | 1 |
| 5 | 65.5 dB | 20.9 | 458 to 479 | -31.46 dB | -36.93 dB | 3 | 0 to 3 | 0 of 22 | 0 to 0 | 10 to 38 | -21.74 / -21.74 | 623 | 0 | 0 | 0.000 | 1 |
| 6 | off | -0.0 dB | 499 to 572 | -0.23 dB | -5.51 dB | 11 | 11 to 11 | 72 of 72 | 2106 to 2106 | 68 to 127 | -41.97 / -41.97 | 66 | 0 | 0 | 0.000 | 1 |

(Step 5 window ends at the rule's `off`, 479 s.)

- Reference -5.27 dB against T1 (F-N1: -5.18).
- **Repeatable:** at J/N60 8.9 / 11.9 / 14.9 the C/N0 is within 0.25 dB
  of F-N1 (-18.47 / -22.01 / -25.36 against -18.23 / -22.22 / -25.14).
- **Fix-loss point without suppression: J/N60 +14.9 to +17.9.** At 17.9
  the 3D fix holds in 3 of 41 epochs (2D, 3 to 4 SVs); at 20.9 no fix
  (0 to 3 SVs, AGC 0), the rule switched the jammer off after 32 s.
  The C/N0 at the loss is about 25 to 28 dB under the reference.
- Recovery -0.23 dB, 11 SVs, 3D fix in all 72 epochs.
- **F for N1 (F-N1 with F-N1b): 6 dB point J/N60 -6.1 to -3.1, fix lost
  between +14.9 and +17.9.** T5 CW (G60-F): 6 dB point 13 to 16, so N1
  is 17 to 19 dB more harmful at the 6 dB point.

## P-N1: PI, load 24, cold start under N1, receiver run (2026-11-21, 16:10 to 16:21)

As T5 G60-P: idle check (1.60 dB), `bladegps` (carrier 36.5 dB, phase
167.51 deg), `ubx_log.py`, then the jammer on at gain 70 (J/N60 25.5) from
16:10:42, before `crpa_ctl`; the user started `crpa_ctl run --on --tx-att
80 --min-tx-att 50 --mode pi --load 24 --csv-every 10 --out /tmp/t5b_PN1`,
CONDUCTED, `tx 60`, `tx 50`; then `t0` and the cold start (T0
1795245075.073). Steps by stdin from t0: 70 to 140 s, then 72.5 / 74.5 / 76
(clip onset) / 78 + / 80 + / 70, about 60 s each, off at 504 s, quit at
598 s; `--max-gain 83`. Files: `t5b_P-N1.ubx` (+ `.idx`),
`t5b_P-N1_jammer.txt`, `t5b_P-N1_bladegps.txt`, `t5b_P-N1.txt`,
`t5b_P-N1_every100.csv`, `t3_t5b_P-N1_{idle,gps}_*.txt`. No underflow,
`JAMMER OFF`, safe state; no missed block, no saturated block, no FRAME_ERR;
PEAK 2048 only at 78 and 80 (marked +). Table from `t5_steps.py`
(reference: step 6, the return to 70; first window from 30 s); "Against
F-N1" is against the F-N1 reference window (-5.18 dB against T1), as T5.

| Step | Gain | J/N60 | Against F-N1 | Against T1 | SVs used | 3D fix | AGC | Jamming ind. | x1 / y (dBFS) | Peak | \|w2\| |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 (cold start) | 70 | 25.5 | +0.26 dB | -4.92 dB | 0 to 11 | 105 of 108 | 1950 | 90 to 103 | -17.19 / -38.95 | 1054 | 1.011 |
| 1 | 72.5 | 27.6 | +0.32 | -4.86 | 11 | 41 of 41 | 1950 | 91 to 101 | -15.12 / -38.96 | 1331 | 1.012 |
| 2 | 74.5 | 29.6 | +0.30 | -4.88 | 11 | 41 of 41 | 1950 | 91 to 100 | -13.20 / -38.96 | 1653 | 1.013 |
| 3 | 76 | 30.9 (onset) | +0.29 | -4.89 | 11 | 36 of 36 | 1950 | 91 to 101 | -11.83 / -38.94 | 2005 | 1.013 |
| 4 + | 78 | 32.9 | +0.14 | -5.04 | 11 | 42 of 42 | 1950 | 90 to 100 | -9.87 / -38.82 | 2048 | 1.013 |
| 5 + | 80 | 34.9 | +0.01 | -5.17 | 11 | 41 of 41 | 1950 | 92 to 103 | -7.92 / -37.24 | 2048 | 1.013 |
| 6 | 70 | 25.5 | +0.09 | -5.09 | 11 | 42 of 42 | 1950 | 90 to 101 | -17.23 / -38.97 | 1071 | 1.011 |
| 7 | off | - | -1.34 | -6.52 | 11 | 73 of 73 | 2106 | 115 to 125 | -41.99 / -42.07 | 72 | 0.125 |

- **TTFF under N1 at J/N60 25.5: 31.3 s** (NAV-STATUS; F-N1 / F-N1b
  without jammer: 30.2 / 30.7 s).
- **3D fix with 11 SVs at every level up to J/N60 34.9** (two steps past the
  clip onset), C/N0 +0.26 to +0.32 dB against the fixed-weight reference up
  to the onset: the PI gain for D about 101 deg (prediction +0.4 dB, T5
  G60-P +0.3 to +0.7), so the jammer costs nothing measurable. y stays at
  -38.95 dBFS (the two-channel noise) to the onset, as in N-b.
- Past the onset: +0.14 dB at 32.9 and 0.0 dB at 34.9 (y -37.24 dBFS, the
  null about 40 dB, N-b): clipping costs 0.15 to 0.3 dB here.
- Recovery at 70: +0.09 dB. Jammer off with PI: -1.34 dB against F-N1
  (T4 V3-P: -0.9 dB): with no jammer the weights adapt to GPS and noise
  (\|w2\| 0.125).
- **N1, PI against fixed weights: 6 dB point from J/N60 -6.1 to -3.1 (F) to
  beyond 34.9 (P, not reached): improvement more than 38 dB; fix loss from
  14.9 to 17.9 (F) to beyond 34.9: more than 17 to 20 dB.** Both lower
  bounds, limited by the jammer level (the B206mini gain of the + steps).
  T5 CW at gain 60: 26 to 29 dB and more than 14 to 21 dB.
