# T5b Plan: Wideband, Swept and Pulsed Jammers

Written 2026-11-18 from `docs/t5b_proposal.md` and its review. Stage T5b
is between T5 and T6 in `docs/pluto-crpa-plan.md`, Section 8.2. The setup is
the T4/T5 setup (`docs/t4_plan.md`, Section 2; `docs/t5_plan.md`, Section 2),
and the T4/T5 rules, tools and run procedure apply unless this file says
otherwise.

Status: **P1 done (2026-11-18), next P2.** All proposals of Section 9
decided by the user as written. P0 done: tools of Section 4 written and
tested offline, waveform files generated, hardware checks of Section 4.7
done without RF ("P0 state" at the end of Section 4). P1 done after a power
cycle, with RX gain 60 written once (Section 2.7): the bench is as in T5.

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

### 2.7 Measured in P1 (2026-11-18, V3, RX-only)

After a Pluto power cycle (boot state seen: fs 30.72 MSPS, AGC). The first
run wrote TX safe, LO L1 + 3 MHz, fs 10 MSPS, bw 9 MHz and RX gain 60 once;
the later runs were `--passive` (nothing written). bladeRF connected,
B205mini idle, jammer attenuators 30 + 20 dB. Logs: `results/t3_t5b_P1_noise_20261118-142542.txt` (noise only, 5
captures, raw captures kept in `tmp/t5b_cap/`), `results/t3_t5b_P1_gps_20261118-142608.txt` (`bladegps -e
brdc3300.18n` on, 10 captures), `results/t3_t5b_P1_after_20261118-142627.txt` (after `bladegps` quit, 3 captures).
No clipping; TX safe at the start and end of every run.

| Quantity | T5b P1 | T5 P1 (gain 60) |
|---|---|---|
| Noise x1 / x2 | -42.56 / -42.90 dBFS | -42.50 / -42.81 |
| Noise in L1 +/- 1 MHz, x1 / x2 (`--band 0,2e6`) | -49.83 / -50.09 dBFS | - |
| GPS on: \|rho\| | 0.165 | 0.168 |
| Carrier over floor x1 / x2 | 37.8 / 37.4 dB | 38.1 / 37.7 |
| Carrier phase, x2/x1 | 167.64 deg, -0.61 dB | 167.9 deg, -0.69 dB |
| GPS on, L1 +/- 1 MHz x1 / x2 | -46.72 / -47.13 dBFS, coherence 0.50, phase 167.8 deg | - |
| Lines at L1 and L1 + 200 kHz, noise only and after `bladegps` | 1.4 to 2.3 dB over the floor (noise) | about 2 dB |

- The bench is as in T5: noise within 0.1 dB, GPS path phase within 0.3 deg
  and 0.1 dB. No residual carrier after `bladegps` quit.
- Load stays **24 LSB^2** (x1 noise 15.2 LSB rms, 0.1 x 231 = 23).
- The noise in L1 +/- 1 MHz is the `--band-ref` for the N runs with
  `--band 0,2e6` (-49.83,-50.09); other bands get their reference from the
  raw noise captures or from the noise part of each N run.

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

- `--waveform FILE.sc16`: reads the file and its sidecar `FILE.json`,
  checks size and sha256, keeps it in memory as fc32 (int16 / 32768) and
  loops it into the TX stream in 10000-sample chunks. The CPU format stays
  fc32 as in the CW path: the UHD Python examples on this host (UHD 4.6)
  send complex64 buffers only, and how a numpy buffer is passed with CPU
  format sc16 is not documented here. The fc32 to sc16 conversion in UHD
  costs nothing measurable. `--rate` is taken from the sidecar; `--rate` and
  `--ampl` together with `--waveform` are refused. `--freq` is the centre of
  the waveform.
- `--lo-offset=HZ` (write it with `=` for negative values):
  `TuneRequest(freq, lo_off)`, present in the installed Python API
  (`help(uhd.types.TuneRequest)`). The RF frequency is read back and must be
  freq + offset within 1 kHz, else the run ends with `JAMMER OFF`. Limit
  +/- 30 MHz.
- TX underflows and sequence errors from `recv_async_msg` (as in the UHD
  example `benchmark_rate.py`) are counted and logged on every STATE and
  STATUS line and at the end. A waveform with underflows is not the waveform
  in the file; P2 checks that the count stays at 0 at each rate.
- The dry run also prints the TX rate range of the device.
- Logs the file name, sha256 and the sidecar parameters.
- Without `--waveform` the CW path is unchanged.
- The offline tests (`scripts/test_t4_jammer.py`, stand-in `uhd`) get cases
  for looping, rate check, LO offset and exit handling with a waveform.

### 4.3 `scripts/t3_phase.py` (extension)

- `--band OFFSET,WIDTH`: power of x1, x2 (raw) or y, x1 (`--cap y`) in a band
  relative to -delta (Hann-averaged periodogram, dBFS like p1 / p2), phase
  and coherence of the band cross-spectrum, and its phase slope in deg/MHz
  (fit to 32 sub-band sums; a delay tau gives -360 tau x 1e6 deg/MHz).
  `--band-ref P1,P2`: the noise in the same band from a noise-only run;
  then the excess powers and `band_ratio_db` = jammer in x1 over jammer in
  y with `--cap y`, the wideband null depth. Selftest: slope within
  0.07 deg/MHz of 1.2 ns in one capture with the jammer 14 dB over the noise
  in the band (std about 0.06 per capture), within 0.02 deg/MHz of 20 ns;
  ratio and excess within 0.02 dB; a 40 dB null read as 40.0 dB.
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

### P0 state (2026-11-18)

Written and tested offline, no hardware:
- `scripts/t5b_waveform.py`, tests `scripts/test_t5b_waveform.py` (12
  tests, about 1 s): 99 % bandwidth within 2 % for 0.1 to 2 MHz noise, chirp
  instantaneous frequency, chip boundaries, main-lobe filter, pulse gate and
  duty, whole periods, loop continuity of an offset tone, refusal on
  clipping, sidecar sha256. Default constant-envelope level -6.02 dBFS (the
  T4/T5 CW amplitude 0.5), noise -15 dBFS. Example crest factors: noise 11
  to 12 dB, filtered PN 2.4 dB, chirp and CW 0 dB.
- `scripts/t4_jammer.py --waveform --lo-offset` and underflow count; tests
  `scripts/test_t4_jammer.py` now 23 (9 new: refusals, dry run, the sent
  samples equal the file looped in order across the wrap, LO offset not
  taken ends with `JAMMER OFF`, CW path unchanged, underflows counted).
- `scripts/t3_phase.py --band --band-ref --save`; `--seq selftest` passes
  with the band checks.
- `scripts/t5b_stap.py`; `--selftest` (about 8 s): tau 1.201 ns for 1.2 ns,
  single-weight null 47.2 dB at 2 MHz against 47.2 dB from Section 2.3,
  3 taps 58.7 dB, delay removed 67.9 dB, array delay 58.7 dB against 58.8.
  A run on synthetic files through the CLI with the jammer only 17 dB over
  the total noise gives 33.6 dB for every case: there the null is limited by
  J/N (as the T4/T5 model, about 2 x J/N - 2 dB), not by the delay.
  **So the S runs need the jammer near its clip onset** (J/N60 about 30 for
  noise) for the delay limit to show at 1 and 2 MHz; at 0.1 and 0.5 MHz the
  J/N limit will dominate.
- `requirements.txt`: matplotlib 3.10.0 added (PSD PNG of the generator,
  plot of `t5b_stap.py`); installed in `.venv/` by the user.
- `t5b_waveform.py --lowpass HZ` added after the first PSD check: the fast
  chirp (10 us) has lines every 100 kHz out to the 8 MSPS edge (about
  -33 dBc each, 1 % of the power outside +/- 1.3 MHz), and 0.1 ms pulses
  have gating sidebands to 2 MHz; at the Pluto these would be cut at the low
  passband edge (L1 - 1.5 MHz) and aliased. CH-f and the 0.1 ms pulsed files
  are limited to +/- 1.2 MHz. 13 tests.
- Waveform set: `scripts/t5b_make_waveforms.sh` writes the 18 files of
  Section 2.5 to `tmp/t5b/` (551 MB, about 40 s). Rates 8 MSPS (group A),
  8.184 MSPS for PN (8 samples per chip), 16 MSPS for N5 and N10 (0.5 s).
  Measured: noise crest 11.7 to 12.3 dB and bw99 within 0.05 % of B; PN
  bw99 1.60 MHz, crest 2.9 dB; CH-m / CH-s bw99 1.97 / 1.98 MHz; CH-f bw99
  2.2 MHz, crest 1.2 dB after the low-pass; pulsed files at the stated duty
  (CW -16.0 dBFS mean, -6.02 in the pulse; N1 -25.0 / -15.0).
- Bug found in the first Pluto run and fixed: the `t3_phase.py` row format
  lacked one field for the band columns (the selftest does not reach
  `measure()`); the two empty logs of that run were deleted.

### 4.7 Checks in P0 (no RF)

Done on 2026-11-18 (after the user connected the devices):
- **B205mini** (serial 3297659), `t4_jammer.py` dry runs with N1 (8 MSPS),
  PN (8.184 MSPS) and N10 (16 MSPS), `--lo-offset=-6e6`: device opened,
  sidecars checked, nothing tuned or streamed. TX rate range 31.25 kHz to
  16 MSPS at the default master clock, so 16 MSPS is the top for group W.
  Logs `tmp/t5b_dry_*.txt`. A dry run does not tune: whether `lo_off` is
  honoured, whether the exact rates are set, and underflows are seen in the
  first P2 run with the go (the script stops before streaming if rate or LO
  are not as requested). LO leakage is measured first without an offset
  (Section 2.5); if an offset is needed, note that L1 - 6 MHz lands at
  -9 MHz in the Pluto baseband and aliases to +1 MHz at 10 MSPS behind the
  analog filter, so the offset is chosen from the P2 spectrum.
- **Pluto** (CRPA unit): found in its boot state (fs 30.72 MSPS, bw 18 MHz,
  TX LO on at 2450 MHz, TX attenuation 10 dB, AGC), so the driver already
  takes bw 18 MHz at 30.72 MSPS (`rf_bandwidth_available` 0.2 to 56 MHz).
  `t3_phase.py --fs 30720000 --bw 18000000 --gain 60 --band 0,10e6 --save`
  (3 captures, RX-only, TX safe; no source started by Claude): noise
  -39.4 dBFS per channel (+3.1 dB over 10 MSPS / 9 MHz), x2/x1 -0.22 dB,
  |rho| 0.009, no clipping; raw captures and sidecar written to
  `tmp/t5b_cap/`. Then back to fs 10 MSPS, bw 9 MHz, gain 60: noise in
  L1 +/- 1 MHz -49.9 / -50.1 dBFS, x2/x1 -0.28 dB. Logs
  `results/t3_t5b_P0_W_20261118-141757.txt`,
  `results/t3_t5b_P0_A_20261118-141800.txt`. State left: TX LO powered
  down at 2450 MHz, TX attenuation 89.75 dB, RX at L1 + 3 MHz, 10 MSPS,
  9 MHz, gain 60 manual.
- **u-blox M8T**, read-only polls: CFG-GNSS has GPS L1C/A and Galileo E1
  enabled (GLONASS, BeiDou, SBAS, QZSS, IMES off). CFG-ITFM config
  0x2d62acf3, config2 0x31e: by the M8 protocol layout the enable bit (31)
  is 0, so the interference monitor is off; thresholds and algorithm bits at
  the recommended values. The CW jamming indicator of MON-HW was reported in
  T1 to T5 all the same. The CW detection and removal is part of the
  baseband and has no setting here. The front-end bandwidth is not in the
  configuration and was not taken from documentation; Section 2.2 keeps it
  as unknown. Nothing changed.


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

### P2 run list (proposed to the user on 2026-11-18; P2-a to P2-d done 2026-11-21, P2-W later; one go per run)

State after P1: Pluto at L1 + 3 MHz, 10 MSPS, 9 MHz, RX gain 60 manual
(written once after the power cycle), TX LO down, TX attenuation 89.75 dB;
bladeRF connected and idle; B205mini through 30 + 20 dB. Check this state
read-only before P2-a (if the Pluto was power-cycled, the first capture run
must be non-passive to write LO, fs and gain once).

Per waveform, host side: `python3 scripts/t4_jammer.py --on --ext-att 50
--max-gain <top step + 3> --waveform tmp/t5b/X.sc16 --freq 1575420000
--gain off --log results/t5b_P2_<id>_jammer.txt` reading a FIFO (CW: the
T4/T5 path without `--waveform`, default `--freq` L1 + 200 kHz). First the
off step, 3 captures (band reference); then per step `gain G` to the FIFO,
1 s, and `t3_phase.py --passive --count 3 --cw-offset 0,200e3 --cw-span
15e3 --band 0,<band> --spurs 5 --save tmp/t5b_cap --label t5b_P2_<id>_g<G>`;
at the end `quit` (`JAMMER OFF` in the log) and 3 captures for a residual
line. Expected scale: CW J/N60 = gain - 35 dB (T5); noise files 9 dB lower
drive, about gain - 44 dB; Gaussian clip onset near J/N60 31 (gain about 75).

| Run | Waveforms | B205mini gain ladder (dB) | Band | Time |
|---|---|---|---|---|
| P2-a | CW (L1 + 200 kHz) | 55, 65, 75; same-day check: gain 65 gives J/N60 30.0 +/- 1 | lines | 1 min |
| P2-a | N1 | 55, 60, 65, 67.5, 70, 72.5, 74, 75, 76, 77, then 1 dB steps to the first clipped step + 1 | 1.2 MHz | 2 min |
| P2-b | N0.1, N0.5, N2 | as N1 | 0.12 / 0.6 / 2.4 MHz | 5 min |
| P2-c | PN, CH-f, CH-m, CH-s | 55, 60, 65, 67.5, 70, 72.5, 75, 76, 77, 78, then to the first clipped step + 1 | 2.4 MHz | 6 min |
| P2-d | P-CW and P-N1, 0.1 / 1 / 10 / 100 ms | in-pulse J/N60 about 20 and 30: P-CW 55 and 65, P-N1 64 and 74; 5 captures per step (a 105 ms capture holds one 100 ms period) | 2.4 MHz | 6 min |
| P2-W | N5, N10 (16 MSPS) | later, before the group W runs: Pluto at 30.72 MSPS with its own noise reference; power cycle before and after | | |

P2-a is the first transmission of a waveform file: stop after it and report
(exact rate and LO as requested, underflow count 0 on every STATE line,
LO leakage line at L1 against the jammer power; an LO offset only if the
leakage is above -30 dBc). Stop rules as T5: underflows above 0, a level
more than 3 dB from the expected value at the CW anchor, `JAMMER OFF` not
confirmed, TX not safe, any unexpected error. Clipping is not a stop
condition in P2: each ladder ends one step past the first clipped step. Raw
captures about 1.5 GB in `tmp/t5b_cap/`.

**Jammer replaced (2026-11-21).** The B205mini was replaced by a B206mini
(serial 352F132; `docs/b206mini_check.md`, results `results/b206mini_check.md`).
Its check C3 is the CW part of P2-a: CW gain 65 gives J/N60 29.8 (same-day
check met), every CW step within 0.4 dB of the B205mini, clip from 78.5 dB;
the ladders above apply unchanged, with "B205mini gain" read as B206mini
gain. C3 also gave N1 at 65 / 75 dB (J/N60 20.6 / 30.2, one clipped sample at
75), N10 at 16 MSPS without underflow, LO leakage about -40 dBc (no LO
offset). **P2-a done 2026-11-21** (`results/t5b.md`): N1 J/N60 = gain - 44.6
dB to 70 dB, Gaussian clip onset at gain 76 (J/N60 30.9), phase slope in
L1 +/- 0.6 MHz +0.08 to +0.15 deg/MHz (tau about -0.2 to -0.4 ns, not the
1.2 ns of Section 2.3; for the S runs), no LO offset needed. **P2-b done
2026-11-21:** N0.1, N0.5, N2 on the same gain scale as N1 (within 0.2 dB),
first clipped samples at J/N60 30.9 to 32.9, N0.1 limited to J/N60 30.1 by
spectral regrowth (skirt +1 dB at gain 76), slope with N2 +0.10 to +0.17
deg/MHz (tau about -0.3 to -0.45 ns), level-dependent. **P2-c done
2026-11-21:** PN and chirps follow CW 0.5 to 0.7 dB lower; clip onset chirps
gain 78 (J/N60 41.5), PN gain 76 (39.7); slope +0.20 to +0.22 deg/MHz at
J/N60 34 to 41. **P2-d done 2026-11-21:** pulsed files at the in-pulse level
of the continuous ones (P-CW 19.5 / 29.5, P-N1 19.3 / 29.0), duty 0.10 to
0.11; finding: off-time level +0.6 dB over the noise at P-N1 gain 74 (B206mini
output with zero samples at high gain, common to both channels). P2 done for
group A (P2-W later). **P3 done 2026-11-21:** D 101.2 / 101.4 deg (CW, J/N60
20 / 35), 102.2 +/- 0.6 / 103.1 +/- 1.4 deg (N1, J/N60 10 / 19), predicted
101.6; phi_G 167.55 / 167.33 deg before / after. Carrier phase under N1 taken
offline with the jammer background removed (the 3-bin line phase of
`t3_phase.py` is biased by a wideband jammer). Next: S-V3 (Section 8; GPS
off, bladeRF unplugged; needs the go).
Bench after C3: Pluto
power-cycled and set once (L1 + 3 MHz, 10 MSPS, 9 MHz, gain 60, TX safe),
bladeRF unplugged; noise x1 / x2 -42.52 / -42.81 dBFS, L1 +/- 1 MHz
-49.79 dBFS.

### P3 plan (written 2026-11-21; run the same day, results in `results/t5b.md`)

Purpose: D (GPS carrier phase against jammer phase, x2/x1) in V3 with the
B206mini, for CW as in T5 P3 and for N1, with both sources on together, and
a check that neither source changes the other's phase. D sets the GPS loss
with PI (T4 / T5: D 100.5 deg gives +0.4 dB predicted). Pluto RX-only; no
`crpa_ctl`; u-blox not used.

**Prediction.** D = 360 - (phi_G - phi_J). From the separate measurements of
today's bench: phi_G 167.64 deg (T5b P1, 2026-11-18, same cabling) and phi_J
-90.8 deg (C3 and P2, B206mini) give **D about 101.6 deg** (T5 P3 with the
B205mini: phi_J -91.2 / -91.3 deg, D 100.4 / 100.5). The 0.5 deg change of
phi_J between the units and the days is the only expected difference.

**Bench.** As P2 (V3, jammer 30 + 20 dB, Pluto at L1 + 3 MHz, 10 MSPS, 9 MHz,
gain 60, TX safe, set once after today's power cycle). **The user plugs the
bladeRF back into USB** (GPS path through 40 dB to SPL1, as in T5b P1). GPS:
`./bladegps -e brdc3300.18n` in `~/Work/bladeGPS`, TX gain unchanged, stdin
from a FIFO, stopped with `q` and by PID if needed. Jammer: `t4_jammer.py
--on --ext-att 50`, FIFO, `quit`.

**Steps** (one run, one go; captures `t3_phase.py --passive --gain 60
--cw-offset 0,200e3 --cw-span 15e3 --spurs 5 --save tmp/t5b_cap`; `--band
0,1.2e6 --band-ref=<P2 N1 off step>` for the N1 steps):

| Step | Sources | Captures | Gives |
|---|---|---|---|
| P3-0 | bladeRF plugged in, `bladegps` not started, B206mini closed | 3 | noise and any bladeRF carrier before the run |
| P3-1 | `bladegps` alone | 10 | phi_G, ratio, carrier over the floor, against T5b P1 (167.64 deg, -0.61 dB, 37.8 dB) |
| P3-2 | + CW jammer, gain 55 (J/N60 about 19.8) | 15 | phi_G and phi_J together: D at J/N60 20 (T5 P3: 100.5 deg) |
| P3-3 | CW gain 70 (J/N60 about 34.9) | 15 | D at J/N60 35 (T5: 100.4 deg), carrier over the floor next to a strong jammer |
| P3-4 | CW `quit`; N1 jammer started, gain 55 (J/N60 10.4) | 15 | phi_G at L1 inside the N1 band (carrier about 17 dB over the jammer density), band phase of N1: D for N1 |
| P3-5 | N1 gain 64 (J/N60 about 19.3) | 15 | as P3-4, carrier about 8 dB over the jammer density |
| P3-6 | N1 `quit`, `bladegps` alone | 5 | phi_G after the jammer runs |
| P3-7 | `bladegps` stopped (`q`) | 3 | residual: known bladeRF carrier after exit (`docs/test-equipment.md`, Section 4) |

N1 is not run at J/N60 30: with the carrier about 38 dB over the noise per
FFT bin and N1 about 29.5 dB over the noise density at J/N60 20, the
carrier would be under the jammer density at J/N60 30 and its phase not
readable. The N1 band phase is the same from J/N60 10 to 32 in P2 (-90.7 to
-91.1 deg), so D at the N run levels follows from P3-4 / P3-5 and P2.

**Evaluation.** D per step from phi_G (line at offset 0) and phi_J (line at
200 kHz for CW, band phase of `--band 0,1.2e6` for N1); with the saved
captures also phi_J of N1 in the bins next to L1 (+/- 15 kHz), to compare D
at L1 with D from the whole band. Pass: D within 1.5 deg of 101.6 for all
steps and phi_G within 0.5 deg between P3-1 and P3-6.

**Stops.** As P2 (underflow, `JAMMER OFF` not confirmed, TX not safe, any
error), and `bladegps` exiting before P3-7. Clipping is not expected (CW at
J/N60 35, N1 at 19.3).

**Time.** About 4 min of RF; raw captures about 0.6 GB.

**After P3.** S-V3 (Section 8): GPS off, so the bladeRF is unplugged again
before S-V3 (its carrier stays after `bladegps` exits).

### S-V3 plan (written 2026-11-21)

**Status 2026-11-21: S-V3a done** (results in `results/t5b.md`, "S-V3a"):
N21 is not the cause of the level-dependent tau (the fit is unbiased; the
dependence is in the hardware, cause open). The multi-tap results were not a
bug: null depth is the wrong figure for L > 1 (temporal notch), so
`t5b_stap.py` now gives the noise gain and the GPS loss. One weight: GPS
loss -0.5 to -0.6 dB at J/N60 25 to 30 for N0.1 to N2, unchanged with the
delay removed or replaced by the array delay: not wideband-limited at the
J/N the B206mini reaches. Multi-tap: no gain. S-V3b (hardware) is not
needed for these questions: dropped (agreed with the user 2026-11-21); S-V1 stays. The text below
is the plan as written; its table predates the tool change.

**What P2 already gives.** The S-V3 bench state (V3, GPS off with the bladeRF
unplugged, capture mux at reset, no `crpa_ctl`, RX gain 60) is the P2 state,
and P2 saved raw captures of N0.1, N0.5, N1, N2 at J/N60 10 to 33 with a
noise-only step per file (3 captures each instead of 10). `t5b_stap.py` on
them (2026-11-21, offline; scratch CSV, not committed):

| Jammer (J/N60 30, gain 75) | tau fit | Phase residual | Amplitude slope | 1-weight null | Limit: tau alone | Limit: amplitude slope alone | Both |
|---|---|---|---|---|---|---|---|
| N0.1 | -0.38 ns | 0.008 deg | -0.045 dB/MHz | 57.7 dB | 83 | 76 | 76 |
| N0.5 | -0.40 | 0.008 | -0.049 | 56.5 | 69 | 62 | 61 |
| N1 | -0.39 | 0.008 | -0.048 | 52.5 | 63 | 56 | 55 |
| N2 | -0.37 | 0.019 | -0.048 | 48.8 | 57 | 50 | 49 |

(Amplitude-slope limit for a flat jammer of width B: -10 log10((s B / 8.686)^2
/ 12), s in dB/MHz, B in MHz.) Findings:
- **The bench delay is about -0.39 ns, not 1.2 ns** (Section 2.3), with a
  0.008 deg rms phase residual: a pure delay fits well.
- **The single-weight null over 1 to 2 MHz is limited by the inter-channel
  amplitude slope (-0.05 dB/MHz) more than by the delay**; the two together
  give 55 / 49 dB against 52.5 / 48.8 measured (N1 / N2). N0.1 and N0.5 are
  limited by J/N.
- **tau depends on the level** (-0.5 to -0.8 ns at J/N60 15, -0.2 to -0.3 at
  25, -0.4 at 30). `fit_h` subtracts the noise powers (N11, N22) but not the
  noise cross-spectrum N21; with |rho| about 0.01 of correlated receiver noise
  this biases the phase slope at low J/N. Candidate cause, to be checked.
- **The multi-tap results are not usable as they stand:** 3 / 5 / 9 taps give
  27 to 65 dB, often below one weight, and not monotonic in L, against the
  synthetic selftest where 3 taps beat 1. Suspected: the evaluation
  (residual = P_y - N_y with N_y from another capture through the same
  weights; with temporal taps N_y can be much larger than the residual
  jammer), or the temporal prediction of x1 by its own taps. To be checked
  before any tap result is used.

**S-V3a, offline (no RF; Claude):**
1. `t5b_stap.py`: subtract the noise cross-spectrum N21 in `fit_h`; check on
   the P2 captures whether tau becomes level-independent.
2. Print the amplitude-slope limit and the combined model next to the
   delay limit.
3. Multi-tap check: synthetic data built from the measured H(f) (delay,
   amplitude slope, phase) and the measured noise (noise-only captures,
   including their correlation), at the P2 levels; compare 1 / 3 / 5 / 9 taps
   with the known truth; inspect the noise gain of the weights and the
   x1-only temporal prediction. Fix the evaluation if it is the cause; add the
   case to the selftest.
4. Re-run on all P2 captures; table of tau, amplitude slope, null depth
   against B, taps and J/N60; offline tests (`--selftest`) pass.

**S-V3b, hardware (only if S-V3a leaves the statistics short; needs the go):**
the run of the table below as decided (noise only, then N0.1, N0.5, N1, N2
at J/N60 30, 10 captures each, `--save`), bladeRF unplugged first, about
3 min of RF. 10 captures give train / test pairs for the multi-tap
evaluation that 3 do not. Pluto RX-only, B206mini through 30 + 20 dB.

**S-V1** (decided) stays after the receiver runs (Section 8, step 7): it
needs the user to recable the jammer legs to V1; it separates the cable part
of tau from the Pluto and fixture part, and now also tells whether the
amplitude slope is in the Pluto (expected: the cable gives none).

### N, F and P run plan (written 2026-11-21; decided by the user the same day as proposed: N runs grouped with GPS off, F ladders from J/N60 -12, offline comparison against the P2 captures; a go per run)

Order of Section 8: the N runs first (RX-only, they set the P ladders and the
CW same-day check), then the F and P runs of the receiver subset. Setup as
P2 / P3: V3, jammer attenuators 30 + 20 dB (`--ext-att 50`), Pluto gain 60
as set in this power cycle, B206mini. Procedure as T5 G60-N / G60-F / G60-P
(`results/t5.md`): the user starts `crpa_ctl` (and types CONDUCTED, `tx 60`,
`tx 50`, "on" in F / P); Claude runs the jammer, `bladegps`, `ubx_log.py`,
the captures and the analysis; stop by PID.

**Level scale (P2, J/N60 against gain).** Noise files and P-N1 in the pulse:
gain - 44.6 dB to 70 dB, then the P2 table. PN, chirps and P-CW in the pulse:
gain - 35.8 dB to 70 dB, then the P2 table. CW: gain - 35.2 (C3). Below
55 dB: 1 dB per dB (as T5; C3 checked CW linear from 35 dB). Steps above the
P2 ladder (marked +): about 1 dB per dB, extrapolated; the 3 dB level stop
applies only to steps inside the P2 table.

#### N runs: RX-only, `crpa_ctl` dry run, GPS off (proposed: bladeRF unplugged)

GPS off because with `bladegps` on, the GPS signal in L1 +/- 1 MHz is
3 dB over the noise (P1), and it would swamp the residual of a wideband
jammer in y. Grouped as P2, one go and one `crpa_ctl` dry run per group:
`crpa_ctl run --mode pi --load 24 --cap-sel --duration 1200 --out
/tmp/t5b_N<x>` (user), then per file: jammer start, an off step, gain steps,
`off`, `quit`. Per step 10 captures `t3_phase.py --passive --cap y
--cw-offset 0,200e3 --cw-span 15e3 --spurs 6 --save` (plus `--band` of the
file), about 15 s; the underflow check and `JAMMER OFF` as P2.

| Run | Files | Gains (J/N60) | `--max-gain` |
|---|---|---|---|
| N-a | CW (`--freq` L1 + 200 kHz) | 55, 60, 65, 70, 72.5, 75, 77.5, 80 +, 82 + (19.8, 24.8, 29.8, 34.9, 37.0, 39.4, 41.7, +, +); 65 to 82 as T5 G60-N | 85 |
| N-b | N0.1, N0.5, N1, N2 | 65, 70, 75, 76, 78 +, 80 + (20.4, 25.5, 30.0, 30.9 = clip onset, about 32.9, 34.9) | 83 |
| N-c | PN; CH-f, CH-m, CH-s | PN: 55, 60, 65, 70, 72.5, 75, 76, 78 +, 80 + (19.3 ... 38.8, 39.7 = onset); chirps: 55, 60, 65, 70, 72.5, 75, 77, 78, 80 +, 82 + (19.2 ... 40.5, 41.5 = onset) | 83 / 85 |
| N-d | P-CW and P-N1, 0.1 / 1 / 10 / 100 ms | in the pulse 20 / 30 (/ 39 for P-CW): P-CW 55, 65, 75; P-N1 65, 75 | 78 |

Gives: null depth against J/N60 per waveform (CW: line in x1 over line in
y, against T5 G60-N within 1 dB as the same-day check that decides whether
CW F / P are taken from T5); for wideband files the residual in y in the band
over the y noise. The y noise is n_x1 + |w2|^2 n_x2 in the band, from the
off-step captures and |w2| of the CSV. S-V3a predicts a residual about 19 dB
under the noise at J/N60 30, near the precision of 10 captures, so these
null depths may be lower bounds; that answers the GPS question already (the
residual does not matter). Chirps and pulsed: null per block from the
`crpa_ctl` CSV (every block) around pulse onsets and against the chirp
period; residual in y during and after the pulse (also the off-time floor of
P-N1 at 74, P2-d). Clipping and SAT_CNT only in the steps marked +.

The offline criterion of Section 7 ("for the same captures") cannot be met
literally: with the mux on y, the captures hold y and x1, not x2. Proposed:
compare the hardware null with the offline single weight of the P2 captures
at the same file and gain (`results/t5b_S-V3a.csv`).

About 3 to 4 min per file, 12 to 25 min per run.

**Status 2026-11-21:** N-a, N-b and N-c done (`results/t5b.md`). For the wideband
null, the y noise must come from the weights (n_y = |w1|^2 n11 + |w2|^2 n22 +
2 Re(conj(w1) w2 conj(n21))), not from the off step; with it the residual is
measurable (0.1 to 0.4 dB of the noise at J/N60 30) and the nulls are values.

#### F runs (fixed w = [1,0]) and P runs (PI, load 24): receiver subset, `bladegps` on

**Prediction for the F ladder (new).** With fixed weights the u-blox sees
the jammer through the Pluto, and its noise is mainly the Pluto noise relayed
(T5 reference 5.1 dB under T1). For a flat jammer of width B at L1 the
effective density over the C/A main lobe is J/N60 + 10 log10(fs / B x
int_B S_g): +8.8 dB for N1, +6.5 dB for N2, +8.6 dB for PN. The 6 dB C/N0
point is where that reaches 4.8 dB, so **J/N60 about -4 to -2 (N1, PN) and
-2 to 0 (N2)**, against 13 to 16 dB for CW (the M8 removes CW). The planned
F ladder (Section 6: from J/N60 10) would start with the fix already lost.
CH-s: between noise-like (-2) and CW-like (13 to 16), depending on whether
the M8 treats a 20 kHz/ms sweep as CW: a finding. P-N1 (10 ms, duty 10 %):
mean power 10 dB under the pulse, so about +6 to +8 in the pulse if the M8
does not blank pulses.

| Run | Jammer (B206mini gain; J/N60) | `--max-gain` |
|---|---|---|
| F-N1, F-N2 | off 180 s (reference), then 3 dB steps from J/N60 -12 to +15 (gain 32.6 to 59.6 by -44.6), 60 s each; off 90 s | 63 |
| F-PN | as F-N1, gain 23.8 to 50.8 (by -35.8) | 54 |
| F-CH-s | J/N60 -12 to +30 (gain 23.8 to 65.8), 60 s each | 69 |
| F-P-N1-10ms | in the pulse -6 to +30 (gain 38.6 to 75) | 78 |

The 30 s fix-loss rule of Section 3 ends every F ladder after the fix is lost
(`off`, then the recovery part), so the long ladders cost time only while the
fix holds. Run time up to 15 to 20 min.

| Run | Jammer before `crpa_ctl` starts, cold start under it, 120 s | 60 s steps | Then |
|---|---|---|---|
| P-N1, P-N2 | gain 70 (J/N60 25.5) | 72.5, 74.5, 76 (30.9, onset), 78 +, 80 + | 70 for 60 s, off 60 s |
| P-PN | 70 (34.4) | 72.5, 75, 76 (39.7, onset), 78 +, 80 + | as above |
| P-CH-s | 70 (34.3) | 72.5, 75, 77, 78 (41.5, onset), 80 +, 82 + | as above |
| P-P-N1-10ms, and the same with `--alpha 0.9` | 70 (in the pulse 25.5) | 72.5, 74.5, 76, 78 +, 80 + | as above |

`--max-gain` top + 3. About 10 min per run. If an N run shows a hardware
limit below the clip onset, the P run of that waveform ends 4 dB above that
limit instead (as T5).

Evaluation: `t5_steps.py --cal` from the scale above; 6 dB and fix-loss
points with and without PI, improvement P - F per waveform next to CW (T5:
26 to 29 dB at the 6 dB point). Prediction: P holds to the clip onset
(J/N60 31 for noise, 39.7 PN, 41.5 CH-s), so the improvement at the 6 dB
point is **more than 31 to 35 dB for noise and PN**, larger than for CW,
because without suppression the wideband jammer hurts the u-blox more.

**CW F / P:** taken from T5 G60-F / G60-P if N-a agrees with T5 G60-N within
1 dB at every unclipped step; otherwise repeated with the T5 ladders.
N-a (2026-11-21): within 0.6 dB at 65 to 75, 2.2 dB deeper at 77.5 (0.4 dB
lower drive just under full scale). **Decided by the user: CW F / P taken
from T5.**

**Runs and order:** N-a, N-b, N-c, N-d (bladeRF unplugged; about 1.5 h
together); evaluation; then (bladeRF back in, P3-0 style idle check first)
F-N1, P-N1, F-N2, P-N2, F-PN, P-PN, F-CH-s, P-CH-s, F-P-N1-10ms,
P-P-N1-10ms, P-P-N1-10ms alpha 0.9: 11 runs, about 2.5 h. Group W (N5, N10
at 30.72 MSPS) after P2-W, separate.

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
