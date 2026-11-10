# T3 Plan: Inter-Channel Amplitude and Phase

Written 2026-11-10. Stage T3 of `docs/pluto-crpa-plan.md`, Section 8.2: the same
signal on both channels through the in-phase splitter; measure the amplitude
ratio and phase of RX2 against RX1. Pass criterion of the plan: phase
difference recorded per retune.

Status: **done** on 2026-11-10, all runs (`results/t3.md`). F was run as three power cycles, F1 with a 30 min log from boot; H warm; G without a power cycle, in the same boot as F3. The fixture part found in G is not small, so the 180 deg ambiguity of Section 5 is not resolved.

---

## 1. What T3 has to settle

T2 gave one value: the common signal reaches RX2 at 173 deg relative to RX1 and
0.4 dB lower, the same in four runs (`results/t2_B.md`, `results/t2_C2.md`).
T3 has to show whether that value can be relied on, and where it comes from.

1. Repeatability: does the phase move on a retune, a sample rate change, a
   restart of the application or a reboot?
2. Origin: is the 173 deg inside the Pluto, or in the splitter and cables?
3. Dependence: does it change with Delta, RX gain or time (warm-up)?

The result does not gate power inversion, which needs no calibration
(`docs/fixed_point.md`). It matters for the T4 jammer path (plan Section 10.2)
and for later beam steering.

---

## 2. Setup

```
bladeRF TX -> 40 dB -> 2-way in-phase splitter -> Pluto RX1, RX2
Pluto TX1 -> DC block -> u-blox M8T (as cabled for T2; not used in T3)
```

- Unit: second Pluto, the CRPA unit (`docs/test-equipment.md`, Section 7).
- Source: the bladeRF as in T2: its carrier at L1 plus the simulated GPS
  (`./bladegps -e brdc3300.18n`). In T2 this gave |rho| about 0.25.
- Pluto settings unless a run says otherwise: Delta +3 MHz, fs 10 MSPS,
  bw 9 MHz, RX gain 60 dB manual on both channels.
- The u-blox receiver is not needed.

## 3. Safety

- **No Pluto transmission.** T3 is RX-only. No `crpa_ctl --on`, no CONDUCTED
  step. `t3_phase.py` powers the TX LO down and sets both TX attenuations to
  89.75 dB at the start, never writes the TX LO frequency, and reads the TX
  state back at the end of every run.
- The bladeRF does transmit (conducted, through 40 dB). Claude Code starts
  `bladegps` only after the user's go, as in T2. The bladeRF carrier stays on
  after `bladegps` exits; for T3-0 the bladeRF must be unplugged from USB.
- A bandwidth write or a sample rate change runs a TX quad calibration, which
  powers the TX LO up for a moment at its parked frequency, at maximum
  attenuation (`docs/interface.md`, Section 5). The script writes the
  bandwidth only when it differs. T3-C (rate changes) cannot avoid it;
  `scripts/if_check.py` already does the same.

---

## 4. Method

Tool: `scripts/t3_phase.py`, on the host over libiio (`iio_attr`,
`iio_readdev`), so no ssh login is needed and Claude Code can run the loops.

Per capture (default 2^20 samples, 0.1 s at 10 MSPS), after removing the mean:

- Wideband, as `crpa_core` integrates it: R11, R22, R21 = sum x2 conj(x1).
  Reported: level of x1 and x2 (dBFS), ratio x2/x1 (dB), |rho|, phase of R21.
  This is the value power inversion sees.
- CW: the same ratio and phase in the three FFT bins (65536 points, Hann) of
  the strongest line within 200 kHz of -Delta, i.e. the bladeRF carrier alone,
  with its SNR over the local floor.
- Also logged per row: RX LO, fs, gain, AD9363 temperature, peak |x|.

Expected resolution with |rho| = 0.25: about 0.2 deg per capture wideband,
better on the carrier line.

Precondition: the capture mux of `crpa_core` must be at reset (raw ADC data on
all four streams). It cannot be read over libiio, so start from a reboot or
from `crpa_ctl off`.

Phase convention: phase = arg(R21) = phase of x2 relative to x1; i0/q0 = RX1,
i1/q1 = RX2 (`results/t1_rx_unit_compare.md`).

---

## 5. Runs

| Run | Content | Command (`.venv/bin/python scripts/t3_phase.py ...`) | Who acts |
|---|---|---|---|
| T3-0 | bladeRF unplugged: |rho| with no common signal (floor, internal coupling) | `--seq one --count 10 --label 0` | User unplugs |
| T3-A | Baseline, about 60 s, no retune: scatter and drift | `--seq one --count 60 --interval 0.5 --label A` | Claude Code |
| T3-B1 | Retune: 30 times RX LO to 2400 MHz and back | `--seq retune --count 30 --label B1` | Claude Code |
| T3-B2 | Rewrite of the same RX LO frequency, 30 times | `--seq rewrite --count 30 --label B2` | Claude Code |
| T3-C | fs 10 -> 30.72 -> 10 MSPS, 10 times | `--seq fs --count 10 --label C` | Claude Code |
| T3-D1 | Delta +2, +3, +4, +5, -3 MHz, 5 captures each | `--seq delta --per 5 --label D1` | Claude Code |
| T3-D2 | RX gain 40 to 70 dB in 5 dB steps, 5 captures each | `--seq gain --per 5 --label D2` | Claude Code |
| T3-E | Cross-check against the PL: `crpa_ctl run --duration 20 --out /tmp/t3_E` (dry run), R21 from its CSV against T3-A; then `crpa_ctl off` | - | User runs ssh and `scp -O` |
| T3-F | Reboot or power cycle, 3 times; 10 captures after each | `--seq one --count 10 --label F1` (F2, F3) | User reboots |
| T3-G | Splitter legs swapped between RX1 and RX2; repeat T3-A | `--seq one --count 60 --interval 0.5 --label G` | User recables |
| T3-H | Optional: 30 min from power-up, one capture every 10 s | `--seq one --count 180 --interval 10 --label H` | Claude Code |

Notes:

- T3-0 is also the first test of the script against the Pluto.
- T3-D2: at 70 dB check the peak column for clipping (full scale 2047); at
  40 dB |rho| drops if quantization noise becomes visible.
- T3-F: after a reboot the RX settings are back at defaults and the TX LO is
  powered on at 2450 MHz; the script puts the TX side in the safe state first.
- T3-G separates the Pluto from the fixture. With phase_A before and phase_G
  after the swap: Pluto part = (phase_A + phase_G) / 2, fixture part =
  (phase_A - phase_G) / 2, and the same for the ratio in dB. The half-sum has
  a 180 deg ambiguity; it is resolved by assuming the fixture part is the
  small one (in-phase splitter, equal cables).
- Restore the T2 cabling after T3-G and note it in the log.

---

## 6. Records and evaluation

- Raw logs: `results/t3_<label>_<date>-<time>.txt`, written by the script with
  the command, settings, tracking flags and TX state.
- Summary: `results/t3.md` with one table row per run: mean and spread of the
  wideband and CW phase, ratio, |rho|, and the settings (plan Section 12).
- Pass: T3-B to T3-F recorded. Expected: a constant phase, because both
  channels share one LO in one chip. A spread above about 2 deg across
  retunes, rate changes or reboots, or a jump, is a finding: stop and report
  before going on.
- Then update plan Sections 8.2, 10 and 11, and the open item "Inter-channel
  phase not measured" in Section 10.2.

---

## 7. Not in this plan

- A frequency sweep of the source (phase against frequency, delay mismatch).
  The T1 comparison found a delay difference of about 0.1 ns, which is below
  0.1 deg over the C/A main lobe. If T3-D1 shows a dependence on Delta, add a
  B205mini tone as a second, stepped source (needs its own safety review).
- The T4 jammer path with a different inter-channel phase than the satellites
  (plan Section 10.2).
