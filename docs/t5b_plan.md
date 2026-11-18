# T5b Plan: Wideband, Swept and Pulsed Jammers

Written 2026-11-18 from `docs/t5b_proposal.md` and its review. Stage T5b
is between T5 and T6 in `docs/pluto-crpa-plan.md`, Section 8.2. The setup is
the T4/T5 setup (`docs/t4_plan.md`, Section 2; `docs/t5_plan.md`, Section 2),
and the T4/T5 rules, tools and run procedure apply unless this file says
otherwise.

Status: **decided (2026-11-18), not started.** All proposals of Section 9
decided by the user as written. Next: P0 (tools of Section 4 with offline
tests, checks of Section 4.7). No code written, no RF run.

Changes against the proposal (agreed by the user on 2026-11-18):
- Two CW tones (proposal item e) dropped. Both tones would come from one
  B205mini through one pair of legs, so they would share one direction and
  one weight would null both. A test of more jammers than degrees of freedom
  needs a second, independently cabled jammer source (Section 10).
- The jammer is sent by `scripts/t4_jammer.py` (UHD Python API), extended to
  loop a waveform file, not by `tx_samples_from_file`. The schedule, stdin
  commands, `--ext-att` / `--max-gain` checks, `JAMMER OFF` on every exit and
  the offline tests are kept. No separate transmit wrapper.
- There is no T5 "runner" to extend. The T5 run procedure (FIFOs, PIDs,
  `ubx_log.py`, `crpa_ctl` started by the user) and `scripts/t5_steps.py`
  are reused.
- File naming as before: `docs/t5b_plan.md`, `results/t5b_<run>...`, summary
  `results/t5b.md`, scripts `scripts/t5b_*.py`.

---

## 1. What T5b has to settle

1. **Null depth against jammer bandwidth** for one complex weight per
   element, and what limits it: the inter-channel transfer mismatch across
   the band (H(f) = x2 / x1 of the jammer), split into the part from the
   bench cabling and the part from the Pluto and the fixture.
2. Whether a short FIR per channel (space-time processing, 3 / 5 / 9 taps)
   recovers the null, from raw captures, offline. This is input for the
   multi-element design decision.
3. **J/S improvement of PI against fixed weights for non-CW jammers**
   (noise, matched-spectrum PN, chirp, pulsed), in the same way as T5:
   6 dB C/N0 point and fix-loss point, with and without PI.
4. **Behaviour of the 1 ms weight loop** for time-varying jammers: a pulsed
   jammer with a period longer than one block, and chirps whose sweep is slow
   or fast against one block.
5. How the u-blox M8T's own CW detection and removal affects the
   fixed-weight results: CW against noise of the same power.

---

## 2. Setup

### 2.1 Bench

As T5 G60 (`results/t5.md`): V3 cabling (jammer leg to CMB1 / RX1 50 cm,
leg to CMB2 / RX2 25 cm, D 100.5 deg), jammer attenuators 30 + 20 dB, RX
gain 60 dB, Delta +3 MHz, fs 10 MSPS, bw 9 MHz, INT_LEN 10000, alpha 0,
load 24, TX1 attenuation 50 dB, OUT_SHIFT 0, bladeGPS unchanged. **RX gain
50 is not repeated** (Section 9): T5 showed it moves every limit by
the 9.9 dB gain step and adds nothing waveform-specific.

Bench state at the end of T5: V3, attenuators 20 + 20 dB, RX gain last set to
50. So P0 includes changing the attenuators back to 30 + 20, a Pluto power
cycle and writing RX gain 60 once (T3: gain writes shift RX1 by up to 0.3 dB
until a power cycle).

### 2.2 Band available to the jammer

At fs 10 MSPS, bw 9 MHz and LO = L1 + 3 MHz, the passband in RF is about
**L1 - 1.5 MHz to L1 + 7.5 MHz**: L1 is at -3 MHz in baseband, and below it
only 1.5 MHz remains before the analog filter edge (Nyquist is at -5 MHz).
A jammer centred on L1 therefore fits only if its 99 % band is within about
+/- 1 MHz (0.5 MHz margin). Wider jammers are cut on the low side and partly
aliased, so they would measure the filters and not the null.

- **Group A (fs 10 MSPS, standard):** jammers centred on L1, 99 % bandwidth
  up to 2 MHz.
- **Group W (fs 30.72 MSPS; S and N runs, F / P for N5 optional;
  Section 9):** bw 18 MHz, Delta +3 MHz, passband about L1 - 6 to L1 + 12 MHz, so noise of 5 and 10 MHz centred on
  L1 fits. INT_LEN 30720 keeps 1 ms blocks. P0 checks that the driver
  accepts bw 18 MHz on the AD9363 and that `crpa_ctl` and `t3_phase.py`
  run at this rate (T1 ran the pass-through at 30.72 MSPS with bw 14 MHz).
  New noise level and load from a P1 at this setting.

The u-blox front end is narrower than the Pluto passband (value not checked
here; take it from the M8 hardware documentation in P0). The jammer power
that reaches its correlators is therefore less than the J/N60 in 9 MHz for
the widest jammers. This affects the F results of different bandwidths at
the same J/N60, not the null depth.

### 2.3 Inter-channel delay of the bench

T3-G: about 2.3 cm of coax is 65 deg at L1, so the velocity factor is about
0.67 and the 25 cm extra in the V3 jammer leg is a delay of **about 1.2 ns**.
The jammer's inter-channel phase therefore changes by about **0.45 deg/MHz**
across the band. One complex weight can only match it at one frequency.
For a flat jammer of bandwidth B and a pure delay tau, the residual
fraction is about (2 pi tau B)^2 / 12, so the null depth limit is

    ND_tau = -10 log10((2 pi tau B)^2 / 12)

| B (MHz) | 0.1 | 0.5 | 1 | 2 | 5 | 10 |
|---|---|---|---|---|---|---|
| ND_tau, bench V3 (tau 1.2 ns) | 73 | 59 | 53 | 47 | 39 | 33 |
| ND_tau, real lambda/2 array, endfire (tau 0.32 ns) | 85 | 71 | 65 | 59 | 51 | 45 |

These are estimates, before the Pluto and fixture mismatch (analog filters
of the two channels, combiners) is added. The V3 bench is about 4 times more
dispersive than a real two-element array at lambda/2. **Results must
therefore separate the bench delay from the hardware mismatch** before they
are used for the multi-element decision:

- Estimate H(f) from the cross-spectrum of raw x1 / x2 captures with a noise
  jammer (Section 6, run S), and fit a delay and an amplitude slope.
- Repeat the S captures in **V1** (both jammer legs 25 cm, D 2.9 deg in T4):
  the cable delay is near zero there, so what remains is the Pluto and
  fixture part. GPS is off in the S runs, so D does not matter for them
  (decided, Section 9).

The GPS path has the same kind of dispersion, but the C/A signal is narrow
against it; no effect expected.

### 2.4 Jammer scale

**J/N60 as in T5**, the main axis: jammer power at the RX port over the noise
power in 9 MHz at RX gain 60, from the x1 level, (P_x1 - P_noise) / P_noise
with P_noise from P1. It works for any waveform whose 99 % band is inside the
passband, so wideband jammers need no separate band integration. In group W
the noise is in 18 MHz; it is reported as J/N30 there, with the conversion
stated.

**J/S** is reported as a derived column with the T5 estimate,
J/S = J/N60 + 29.5 dB (element C/N0 about 40 dB-Hz, noise in 9 MHz), and
the definition is stated in `results/t5b.md`. The GPS power at the RX port
is below the noise and is not measured. The improvement is a difference of
two J values and does not depend on this estimate.

### 2.5 Waveforms

Generated by `scripts/t5b_waveform.py` (Section 4.1), streamed by
`t4_jammer.py --waveform`. Centre L1 unless stated; optional
`--offset HZ` for the whole waveform.

| Id | Waveform | Parameters (group A) | Level in the file |
|---|---|---|---|
| CW | CW, the T4/T5 path (constant baseband, `--freq` L1 + 200 kHz) | as T5 | amplitude 0.5 (-6 dBFS) |
| N0.1 / N0.5 / N1 / N2 | band-limited complex Gaussian noise | B (99 % power) 0.1, 0.5, 1, 2 MHz | -15 dBFS rms |
| PN | random BPSK, 1.023 Mcps, filtered to the main lobe +/- 1.023 MHz | chip rate option | -6 dBFS rms |
| CH-f / CH-m / CH-s | linear sawtooth chirp, span 2 MHz (L1 +/- 1 MHz) | period 10 us / 1 ms / 100 ms | -6 dBFS rms (constant envelope) |
| P-x | pulsed CW (L1 + 200 kHz) or pulsed N1 | period 0.1 / 1 / 10 / 100 ms, duty 10 % (and 50 %) | as the base waveform, during the pulse |
| N5 / N10 (group W) | noise as above | B 5, 10 MHz | -15 dBFS rms |

- **Levels.** Constant-envelope waveforms use the CW drive of T5 (-6 dBFS),
  so the T5 table "B205mini gain to J/N60" carries over approximately; P2
  measures it for each waveform anyway. Gaussian noise at -15 dBFS rms has a
  per-component rms of -18 dBFS. Its largest sample in 10^8 is about 6 sigma
  (15.6 dB), so it stays below full scale. The generator refuses any file that
  clips, and records RMS, peak and crest factor.
- **Sample rate.** B205mini rate per waveform, at least about 4 x the
  bandwidth; PN at 4.092 MSPS (4 samples per chip), unless P0 shows that
  the B205mini cannot set it exactly. Rates and the USB 3 limit are checked in P0
  from the device (`get_tx_rates`), not assumed.
- **File length.** An integer number of chirp periods, pulse periods and PN
  code periods, and long enough that a loop restart is not a feature in
  1 ms blocks (at least 1 s, unless that is too large; Section 4.1).
- **LO leakage.** For modulated waveforms the B205mini LO leakage would sit
  at the jammer centre. It reaches both channels through the same legs, so
  PI nulls it with the jammer; it matters only for the F runs (u-blox CW
  removal). P2 measures its level against the waveform. If it is above
  -30 dBc, tune with an LO offset (`uhd.types.TuneRequest(target, lo_off)`,
  present in the installed UHD 4.6 Python API; whether the B205mini honours
  it is checked in P0) so that the leakage falls outside the Pluto passband.

### 2.6 Level estimates

| Quantity | Value | From |
|---|---|---|
| Noise in x1, gain 60 | -42.55 dBFS | T5 P2 |
| ADC clip onset, CW | J/N60 42.2 | T5 P2 |
| ADC clip onset, Gaussian noise (first clipped sample in 3.1 M) | about 11 dB lower, J/N60 about 31 | crest of a complex Gaussian: a component reaches about 5.3 sigma = 11.5 dB above the total rms |
| ADC clip onset, chirp / filtered PN | J/N60 about 40 to 42 | constant or near-constant envelope |
| B205mini gain for a given J/N60, noise at -15 dBFS | about 9 dB more than CW | 9 dB lower drive |

The B205mini compressed by 0.4 dB above 70 dB with CW (T4). A crest factor
of 10 dB makes compression and spectral regrowth start earlier. P2 records the
spectrum at each step and does not use waveforms above the point where the
skirts rise by more than 1 dB. If the noise ladder runs out of B205mini gain
below the Gaussian clip onset, the attenuators go to 20 + 20 (the T5 floor
of 40 dB holds: worst case -27 dBm at the Pluto RX).

---

## 3. Safety

The rules of `docs/test-equipment.md`, Section 2, `docs/t4_plan.md`,
Section 3 and `docs/t5_plan.md`, Section 3 apply unchanged:

- One go per run. Claude Code runs `bladegps`, the jammer and the logger;
  the user starts `crpa_ctl --on` and types CONDUCTED; processes are stopped
  by PID. No B205mini, bladeRF or Pluto TX start without the go for that run.
- `t4_jammer.py --on` keeps `--ext-att` (floor 40) and `--max-gain`
  (top step plus 3 dB, from P2 for that waveform). The `--waveform` path
  shares the exit handling: end of burst, gain at minimum, `JAMMER OFF`.
- Worst case at the Pluto RX: the crest factor raises the peak power. With
  40 dB of attenuation, full B205mini gain (about +20 dBm, CW) and a 12 dB
  crest factor the peak is about -15 dBm. That is still 17 dB below the AD9363
  absolute maximum of +2.5 dBm peak. At 50 dB it is about -25 dBm peak.
- Each ladder starts at the lowest level. Stop rules as T5 (FRAME_ERR, safe
  state not confirmed, jammer level more than 3 dB from the P2 table,
  SAT_CNT or PEAK 2047 outside steps marked +). New: in F runs, if the fix
  has been lost for **30 s** (decided) before the planned last step, Claude
  sends `off` to the jammer and the run continues with the recovery part.

---

## 4. Tools

All changes are tested offline before P1, as in T4 and T5.

### 4.1 `scripts/t5b_waveform.py` (new, `.venv/bin/python`)

- Writes interleaved int16 I/Q (sc16) to `tmp/t5b/` (git-ignored), with a
  JSON sidecar: all parameters, sample rate, length, seed, RMS dBFS, peak,
  crest factor, 99 % bandwidth, sha256 of the data. Also a PSD plot as PNG
  (needs matplotlib in `requirements.txt`, pinned; decided, Section 9; the
  user installs it into `.venv/`).
- Waveforms of Section 2.5, parameters on the command line; refuses to write
  if any sample clips.
- Tests `scripts/test_t5b_waveform.py`: 99 % bandwidth, chirp instantaneous
  frequency and period, chip rate, pulse period and duty, crest factor, file
  length (integer number of periods), no clipping, sidecar contents.

### 4.2 `scripts/t4_jammer.py` (extension)

- `--waveform FILE`: reads the sc16 file and its sidecar, keeps it in memory
  and loops it into the TX stream with CPU format sc16 (no float
  conversion); `--rate` is taken from the sidecar, and a mismatch is refused.
  `--freq` is then the centre of the waveform.
- `--lo-offset HZ`: `TuneRequest(freq, lo_off)`; actual RF and DSP
  frequencies are read back and logged.
- Logs the file name, sha256 and the sidecar parameters.
- Without `--waveform` the CW path is unchanged.
- The offline tests (`scripts/test_t4_jammer.py`, stand-in `uhd`) get cases
  for looping, rate check, LO offset and exit handling with a waveform.

### 4.3 `scripts/t3_phase.py` (extension)

- `--band OFFSET,WIDTH`: power of x1, x2 (raw) or y, x1 (`--cap y`) in a band
  relative to -delta, minus the noise in the same band from a reference
  capture. Gives the wideband null depth = band power in x1 over band power
  in y, after noise subtraction.
- `--save DIR`: raw captures as `.npy` with the settings in a JSON sidecar,
  for the offline analysis of Section 4.5 (to `tmp/t5b_cap/`, git-ignored;
  only derived results are committed).

### 4.4 `scripts/t5_steps.py`

`--cal` per waveform from P2. No other change expected.

### 4.5 `scripts/t5b_stap.py` (new, `.venv/bin/python`, offline)

From raw x1 / x2 captures with a noise jammer and GPS off:
- H(f) = S21 / S11 per FFT bin across the jammer band; fit of a delay and
  amplitude slope; coherence.
- Null depth of the optimal single complex weight (as PI with the load used
  on hardware) and of a space-time combiner with 3, 5 and 9 taps per channel
  (power minimization with the constraint on the centre tap of element 1),
  against B. Evaluated on a second capture, not on the one used for the
  weights.
- The same with H(f) of the measurement with the fitted bench delay removed,
  and with a delay of a real lambda/2 array put in its place.
- Checked against synthetic data with a known delay (the formula of
  Section 2.3).

### 4.6 `sw/app/crpa_ctl`

No change. Group W uses `--fs 30720000 --int-len 30720` (options exist).

### 4.7 Checks in P0 (no RF)

- B205mini: TX rate range and the exact rates in Section 2.5; behaviour of
  `lo_off` (UHD dry run, nothing streamed).
- Group W only: AD9363 bw 18 MHz accepted; `t3_phase.py --fs 30720000`.
- u-blox M8T front-end bandwidth and the CW detection / removal settings in
  the receiver configuration (read only, from `docs/test-equipment.md`,
  Section 6.2 and the M8 documentation).

---

## 5. Predictions

- **Null depth (N runs).** min(the J/N-limited model value of T4/T5,
  ND_tau of Section 2.3 with the measured tau, the T5 hardware ceiling near
  75 dB). For N1 and N2 at J/N60 30: about 53 / 47 dB on the bench, below the
  58 dB of CW. For N0.1 and CW: as T5.
- **Chirps.** CH-f (10 us) and CH-m (1 ms) fill the 2 MHz within one block,
  so the null is as for N2. CH-s (100 ms) moves 20 kHz per block, so each
  block is nearly narrowband and the null should approach CW, as long as the
  loop follows the drift of the weight (0.45 deg/MHz); the one-block lag
  should cost nothing measurable.
- **Pulsed.** Period 0.1 ms: averaged in a block, null as for the base
  waveform at its mean power. Period 10 and 100 ms: at each pulse onset the
  weights come from a jammer-free block, so the jammer gets through for up to
  about 2 blocks per pulse (one block of integration plus the PS update).
  The u-blox sees a residual pulsed jammer with about 2 ms per period.
  Smoothing (alpha 0.9) should hold the null over the off time; one
  parameter run (decided).
- **F runs.** Without suppression, noise of the same J/N60 should hurt more
  than CW, because the M8 removes CW. This difference is reported per
  waveform.
- **P runs.** C/N0 loss with PI from the residual jammer in y: about
  10 log10(1 + residual J/N), with the residual measured in the N run of the
  same waveform. Limit for noise: the earlier clip onset (about J/N60 31) and
  the null depth of Section 2.3.

---

## 6. Steps and runs

Who acts: U = user, C = Claude Code. RX-only = no Pluto transmission. Host
side as T5 (FIFOs, PIDs in files, `ubx_log.py`, cold start and `t0`
together).

### Preparation

| Step | Content | RF on | Who |
|---|---|---|---|
| P0 | Decisions of Section 9; tools of Section 4 and offline tests; checks of Section 4.7; waveform files generated and their PSD checked; attenuators 30 + 20; power cycle, RX gain 60 once | none | C; U cables |
| P1 | Noise only (bladeRF unplugged), 5 captures; then GPS alone, 10 captures: noise, \|rho\|, compared with T5 P1 | bladeRF | C after the go |
| P2 | Each waveform alone, RX-only: B205mini gain ladder in 2.5 dB steps from J/N60 about 10 to the clip onset, 3 captures each with clip counts, `--band`, `--spurs`; LO leakage line; skirts. Anchor: CW at gain 65 gives J/N60 30.0 +/- 1 dB (T5) | B205mini | C after the go |
| P3 | Both on, CW and N1, 30 captures: D in V3 (expected 100.5 deg), and D of N1 in the band (the phase slope) | both | C after the go |

### RX-only runs

| Run | Pluto | Jammer | Gives |
|---|---|---|---|
| S-V3 | capture mux at reset, no `crpa_ctl`; `t3_phase.py --save` | GPS off (bladeRF unplugged). Noise only, then N0.1, N0.5, N1, N2 at J/N60 30, 10 captures each | H(f), tau, offline null depth against B and taps (Section 4.5) |
| S-V1 | as S-V3, after recabling to V1 (U) | as S-V3 | Pluto and fixture part of H(f) without the cable delay |
| N-x | dry run, PI, load 24, `--cap-sel --duration 600`, passive captures | per waveform: J/N60 20, 25, 30, 35, then 2 dB steps to its clip onset, +2 and +4 (marked +), 40 s each | Null depth on hardware against J and waveform; residual in y |

N-x for: CW (repeat of T5 G60-N, short, same-day check), N0.1, N0.5, N1, N2,
PN, CH-f, CH-m, CH-s, P-CW and P-N1 at periods 0.1 / 1 / 10 / 100 ms (duty
10 %). About 15 runs of 6 to 10 min.

### Receiver runs (subset)

| Run | Pluto | Jammer | Gives |
|---|---|---|---|
| F-x | `--on`, fixed [1,0] | off 180 s (reference), then J/N60 10, 13, ... in 3 dB steps to 2 steps after the predicted fix loss, 60 s each; off 90 s | 6 dB and fix-loss points without suppression |
| P-x | `--on`, PI, load 24 | on at J/N60 25 (noise) or 35 (constant envelope) before `crpa_ctl` starts, cold start under it, 120 s; 2 dB steps to the clip onset + 4 dB (top two marked +), 60 s each; back to the start level 60 s; off 60 s | TTFF under the jammer; 6 dB and fix-loss points with PI; recovery |

F and P for: **N1, N2, PN, CH-s, P-N1 (10 ms)** (decided). CW is taken from
T5 G60-F / G60-P if the same-day CW N run agrees with T5 within 1 dB.
Otherwise CW F and P are repeated. 10 runs of 10 to 15 min.

Also (decided): P-x with alpha 0.9 for P-N1 (10 ms); group W at 30.72 MSPS
with P1 and P2, S and N runs for N2, N5 and N10.

Optional: F / P for N5 in group W.

---

## 7. Records and evaluation

- Raw files named `results/t5b_<run>...` as T5; CSV every 100th row
  committed, full CSVs git-ignored (add `results/t5b_*.csv` patterns as in
  T5). Waveform files and raw captures stay in `tmp/` (git-ignored); their
  sidecars and sha256 are copied into the run logs.
- Every log records all hardware settings (`docs/test-equipment.md`,
  Section 2), the waveform sidecar, the B205mini gain and the attenuators as
  entered by the user.
- Per F and P run, the `t5_steps.py` table: J/N60, J/S estimate, mean and
  per-SV C/N0 against the run reference and T1, SVs used, fix, AGC, jamming
  indicator, x1 and y level, PEAK, SAT_CNT, missed blocks, \|w2\|.
- Summary `results/t5b.md`:
  - P2: J/N60 per B205mini gain per waveform, clip onset, LO leakage,
    regrowth;
  - S: H(f), fitted tau and amplitude slope (V3 and V1), offline null depth
    against B for 1, 3, 5, 9 taps, as measured and scaled to a real array
    (plot);
  - N: null depth against J/N60 per waveform, against Section 5;
  - F and P: 6 dB and fix-loss points, improvement P minus F per waveform,
    next to CW from T5; the effect of the M8 CW removal on the F results;
  - pulsed and chirp: weight-loop behaviour (null per block around pulse
    onsets, from the CSV).

Pass criteria (decided, Section 9):

| Item | Criterion |
|---|---|
| Recorded | Null depth against B (hardware and offline, V3, and V1 if decided); 6 dB and fix-loss points with and without PI for the receiver subset |
| Null depth | Hardware N runs within 3 dB of min(model, ND_tau with the measured tau) up to the clip onset of each waveform; a larger gap is a finding to explain |
| Offline | Offline single-weight null depth within 3 dB of the hardware N run for the same captures and B |
| Integrity | As T5: no FRAME_ERR, no gap after startup, safe state and `JAMMER OFF` confirmed in every run; SAT_CNT and PEAK 2047 only in steps marked + |

Then update plan Sections 8.2 (add T5b), 8.3 (null depth against bandwidth;
inter-channel delay and mismatch), 9.3 (new scripts and options), 10 and 11,
and `docs/test-equipment.md` (B205mini waveform use, gain tables).

---

## 8. Order of work

1. Decisions of Section 9 (done, 2026-11-18).
2. P0: tools and offline tests, checks, waveform files, bench state.
3. P1, P2, P3 (RX-only except the sources).
4. S-V3 and its offline analysis: this sets how far the bench can show a
   wideband null at all, before the receiver runs are fixed.
5. N runs; evaluate against Section 5.
6. F and P runs for the subset.
7. S-V1 (recabling) and optional runs.
8. `results/t5b.md`, plan update.

---

## 9. Decisions (user)

Decided by the user on 2026-11-18: all ten as proposed.

| # | Question | Decision |
|---|---|---|
| 1 | RX gain | 60 only |
| 2 | Group W (fs 30.72 MSPS, B 5 and 10 MHz) | S and N runs only; F / P for N5 optional |
| 3 | S runs in V1 as well | Yes, after the V3 receiver runs |
| 4 | Receiver subset | N1, N2, PN, CH-s, P-N1 (10 ms); CW from T5 if the CW N run agrees |
| 5 | Fix-loss stop in F runs | Fix lost 30 s before the last planned step: jammer `off`, go on with recovery |
| 6 | matplotlib for the PSD PNG | Add a pinned version to `requirements.txt` (user installs) |
| 7 | Levels in the files | Constant envelope -6 dBFS (as CW), noise -15 dBFS rms |
| 8 | Alpha 0.9 run for the pulsed jammer | Yes, one run |
| 9 | Baseline without the Pluto | Not now (Section 10) |
| 10 | Pass criteria | As Section 7 |

---

## 10. Not in this plan

- Two jammers, or more jammers than degrees of freedom. This needs a second
  jammer source with its own legs (the first Pluto's TX is not checked) and
  more than two elements to null both.
- Moving jammers (needs a variable phase in one leg or a two-element
  simulator, plan Section 10.2).
- A baseline without the Pluto (jammer combined into the T1 reference path
  to the u-blox), to separate the u-blox's own tolerance from the Pluto. Its
  J level would come from the B205mini gain table only (decided: not now).
- RX gain 50, external LNA, higher bladeGPS level.
- Over-the-air (T6).
