Task: T5b wideband and swept jammer evaluation (conducted setup)

Context
- T4/T5 with a CW jammer are done. Over-the-air jamming is not possible,
  so we stay with the conducted setup and evaluate other jammer types.
- Jammer source: USRP B205mini (UHD), as for the CW tests. GPS source and
  receiver as before (docs/test-equipment.md).
- Safety rules in docs/test-equipment.md Section 2 apply. Do not transmit
  on your own: every run that starts the B205mini, the GPS simulator or
  Pluto TX needs my confirmation in the session.

Step 1: investigate and report (no new code yet)
1. How the CW jammer tests were run: scripts, CLI, log format, results
   directory, how J/S was defined and calibrated. List what can be reused.
2. The jammer wiring used for T4/T5 (from the plan and results docs):
   how the jammer reaches RX1 and RX2 and how the inter-channel phase
   offset was made. Ask me to confirm the current cabling.
3. UHD on this host: path and options of tx_samples_from_file (check
   --help; do not guess), supported --type values, LO offset support,
   and the B205mini sample rate limits over USB 3.
4. How to capture raw RX1/RX2 data from the Pluto with the current
   firmware (capture mux, Section 6.2) for offline analysis.
Then propose the file layout, CLI and test matrix, and wait for my OK.

Step 2: jammer waveform generator (scripts/jam_gen.py)
- Uses numpy via $PY (plan Section 9.3). Output: interleaved int16 I/Q
  (sc16) for tx_samples_from_file --type short.
- Waveforms (parameters on the command line):
  a. band-limited complex Gaussian noise, bandwidth B (e.g. 0.1, 1, 2,
     5, 10 MHz)
  b. random BPSK PN (matched-spectrum jammer), chip rate (default
     1.023 Mcps)
  c. linear chirp: span and sweep period (e.g. 10 us, 1 ms, 100 ms),
     sawtooth; file length an integer number of periods
  d. pulsed: any of the above or CW, with period and duty cycle
  e. two CW tones at given offsets (exceeds the 2-element degrees of
     freedom when the tones come from different directions)
  f. optional frequency offset of the whole waveform from L1
- Set the RMS level in dBFS; refuse to write if any sample clips.
  Defaults: -15 dBFS for Gaussian noise, -3 dBFS for constant-envelope
  waveforms.
- Write a JSON sidecar per file with all parameters, RMS, peak and crest
  factor, and a PSD plot (PNG) for a visual check.
- Files are large: write them to a git-ignored directory.
- Unit tests: bandwidth (99% power), chirp instantaneous frequency,
  chip rate, crest factor, file length, no clipping.

Step 3: jammer transmit wrapper
- Start/stop tx_samples_from_file with --repeat in the background;
  dry run by default, --on to transmit after an interactive setup
  confirmation. Always stop the TX process on exit, Ctrl-C or error.
- Record the full command line, B205mini gain, and the external
  attenuator values I enter.

Step 4: level calibration
- Calibrate the jammer power at the Pluto RX input for each waveform
  (same method as for CW, adapted for wideband signals: integrate the
  power over the waveform bandwidth). Report J/S as total jammer power
  over total GPS signal power at the RX input, and state the definition
  in the results.
- Check that the Pluto RX stays out of saturation at the highest J/S
  (RSSI, ADC peak, crpa_core saturation counters).

Step 5: test runner and analysis
- Extend the existing T5 runner (do not duplicate it) to sweep:
  waveform x J/S x {CRPA off (w=[1,0]), CRPA on (PI)}, and a baseline
  without Pluto in the path where meaningful.
- Per run, log: u-blox fix, numSV, per-SV C/N0, MON-HW AGC and jamInd,
  crpa_core covariance, weights, output power and saturation counters,
  and all hardware settings.
- Summary per waveform: C/N0 vs J/S, J/S at loss of fix, null depth,
  improvement of CRPA on vs off, comparison with the CW results.
- Note that the u-blox M8 has built-in CW detection and removal; report
  CW and wideband results with this in mind.

Step 6 (offline, no TX change): channel mismatch and wideband null depth
- With a noise jammer only (GPS off), capture raw RX1/RX2 for several
  bandwidths. Compute the achievable null depth for a single complex
  weight and for FIR combiners with 3, 5 and 9 taps per channel. Plot
  null depth vs bandwidth and estimate the inter-channel transfer
  mismatch. This is input for the multi-element design decision
  (space-time processing or not).

Output and documentation
- results/t5b/<date>-<time>/ for each run; a summary report
  results/t5b_summary.md with plots.
- docs/t5b_procedure.md: wiring, level setting, run commands.
- Update the plan: Section 8.2 (add T5b), 8.3 if new metrics, 9.3
  (new scripts), 10 and 11.

Rules
- Follow Section 12 of the plan (ASCII English, SPDX headers, etc.).
- Ask before long or high-power runs; start each sweep from the lowest
  J/S and stop the sweep when the receiver loses fix for <N> s.
  