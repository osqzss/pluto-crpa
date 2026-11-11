# T4 Plan: Conducted CW Jammer, Power Inversion

Written 2026-11-10. Stage T4 of `docs/pluto-crpa-plan.md`, Section 8.2: a
conducted CW jammer into both channels with a phase offset against the
satellites, power inversion (PI) enabled. Metrics of the plan: null depth and
C/N0 recovery. The setup and its reasons are in the plan, Section 11 (T4);
this file adds the levels, tools, runs, pass criteria and safety.

Status: **measurements done (2026-11-11), all pass criteria met**; summary
in `results/t4.md`. History: decided by the user (2026-11-10, Section 9); P0
and P1 done.
P1 (2026-11-10, variant V1, RX-only): noise -42.47 / -42.77 dBFS, |rho|
0.005; GPS path phi_G 166.5 deg wideband and 165.7 deg on the carrier, g_G
-0.76 dB, |rho| 0.174, GPS and carrier 6.8 dB under the noise in x1 (2.9 dB
lower than in the T2 cabling); no carrier after `bladegps` quit; nothing from
the B205mini idle, before or after UHD opened it. A second bladeRF line lies
about 181 kHz above its carrier (21 dB over the floor, 19 kHz from the jammer
frequency). Logs: `results/t4_P1*.txt`, `results/t4_P2_pre_*.txt`.
**P2 and P3 done for V1** (2026-11-10, Section 2.2): ladder calibrated, L5
reached with 60 dB, no residual line. **D is 2.9 deg in V1**, so PI would
null the satellites with the jammer (predicted C/N0 change about -27 dB).
**V3** (jammer leg to RX1 50 cm instead of 25 cm): **D = 100.0 deg**,
predicted C/N0 change with PI +0.4 dB. **V3-N done** (`results/t4.md`):
null depth 18.9 / 38.1 / 57.1 dB at L3 / L4 / L5, equal to the model values;
the first criterion (J/N + 10 dB) was missed by 1.2 dB at L3, where the model
gives 18 dB; the criterion is now "within 3 dB of the model value" (user,
2026-11-11) and V3-N passes it at all three levels. **V3-F done**: reference -5.1 dB
against T1; C/N0 -0.4 / -0.9 / -4.0 / -9.9 dB at L1 to L4 and the fix lost at
L5. **V3-P done** (2026-11-11, after a P3 repeat: D 100.2 deg): 3D fix with
11 SVs at every level, cold start under L5 with TTFF 28.8 s, C/N0 +0.7 /
+0.6 / +0.3 dB at L5 / L4 / L3 against the V3-F reference (prediction
+0.4 dB), -0.9 dB with the jammer off. **V3-L done** (2026-11-11): null depth 19.6 /
18.9 / 14.8 / 5.3 dB at L3 and 57.9 / 57.2 / 52.4 / 37.9 dB at L5 for load
0 / 24 / 240 / 2400; load 24 kept. **V3-A done**: 38.1 dB at L4 with
alpha 0, alpha 0.9 and INT_LEN 1000 alike; alpha 0 and INT_LEN 10000 kept;
at INT_LEN 1000 the PS misses blocks. **V1-N done** (25 cm leg back, D
3.2 deg): jammer null 20.1 / 40.0 / 59.0 dB at L3 / L4 / L5, and the bladeRF
carrier 25 dB lower in y than in x1 (prediction 24.6 dB): with D near 0 PI
nulls the GPS path with the jammer. **V4** (3 cm SMA adapter in the 25 cm
leg to RX1): D 73.0 deg, P3 only. **V5** (50 cm to RX1, adapter in the leg
to RX2): **D 29.5 deg**; V5-N 19.8 / 39.3 / 58.2 dB, carrier -6.5 dB in y;
V5-F reference -5.28 dB against T1, fix lost at L5; **V5-P**: 3D fix at
every level, C/N0 -8.1 / -8.2 / -8.2 dB at L3 / L4 / L5 against the
reference (prediction -9.2 dB). T4 is complete as measured; open points in
Section 6.

All levels below are estimates from T2 and T3 data until step P2 has measured
them.

---

## 1. What T4 has to settle

1. Null depth of PI on a real CW jammer, against the jammer level (the model
   gives 18 / 37 / 57 dB at J/N 10 / 20 / 30 dB as upper bounds,
   `docs/fixed_point.md`).
2. C/N0 recovery at the u-blox: with the jammer on, PI against w = [1,0].
3. Dependence on the phase separation D between jammer and satellites,
   against the prediction of Section 5.
4. Starting values of the PI parameters: diagonal load and alpha (plan
   Section 10.2).

Not in T4: the jammer power sweep to the limit (T5), more than one jammer,
moving jammers, per-satellite phases (two-element simulator, plan Section
10.2).

---

## 2. Setup

```
bladeRF (bladeGPS) -> 40 dB -> SPL1 -+-> CMB1 -> Pluto RX1
                                     +-> CMB2 -> Pluto RX2
B205mini TX/RX (CW) -> 30 dB + 30 dB -> SPL2 -+-> leg a -> CMB1
                                              +-> leg b -> CMB2
Pluto TX1 -> DC block -> u-blox M8T, TX attenuation 50 dB in the Pluto (as T2)
```

- Unit: second Pluto, the CRPA unit. Settings as T2 and T3: Delta +3 MHz,
  fs 10 MSPS, bw 9 MHz, RX gain 60 dB manual on both, INT_LEN 10000 (1 ms),
  OUT_SHIFT 0, TX1 attenuation 50 dB.
- GPS: bladeRF x40, `./bladegps -e brdc3300.18n`, TX gain unchanged (default
  -5), so that the T1 reference stays comparable (decide, Section 9).
- Jammer: B205mini (serial `3297659`), CW from a constant baseband (tone on
  the B205mini LO, so tone and LO leakage are one line), at
  **L1 + 200 kHz = 1575.62 MHz**: inside the C/A main lobe, 200 kHz from the
  bladeRF carrier, and the offset used in the model (`results/t3_model.txt`).
  At the Pluto it appears at -2.8 MHz in baseband.
- Cabling variants: only the two jammer legs a and b change (crossed, or an
  adapter added in one leg). The GPS path and the RX cables stay untouched
  from P1 to the last run.

### 2.1 Level estimates

| Quantity | Estimate | From |
|---|---|---|
| Noise at RX gain 60 dB | -42.5 dBFS (15 LSB rms), about -101 dBm in 9 MHz at the RX port (NF assumed 3.5 dB) | T3-0 |
| GPS and carrier at the Pluto | about 3.5 dB below T2 (one combiner per leg); \|rho\| about 0.13 to 0.15 instead of 0.25 to 0.29 | T3 |
| Reference C/N0, w = [1,0], jammer off | about 3 dB below T2-A, i.e. about -6 dB against the T1 reference (mean about 39 dB-Hz) | T2-A |
| Jammer path loss | 60 dB + 3.5 dB (SPL2) + 3.5 dB (CMB) = 67 dB | parts |
| J/S at J/N = 0 dB | about 28 dB for a 42 dB-Hz signal at the element (69.5 dB-Hz bandwidth) | - |

Jammer ladder (J/N = jammer power over noise power in the 9 MHz band, per
element, measured in P2):

| Step | J/N | J/S (est.) | Level of x | CW peak | At the RX port (est.) | B205mini output needed (est.) |
|---|---|---|---|---|---|---|
| L0 | off | - | -42.5 dBFS | - | - | - |
| L1 | -10 dB | 18 dB | -42.1 | 5 LSB | -111 dBm | -44 dBm |
| L2 | 0 dB | 28 dB | -39.5 | 15 | -101 dBm | -34 dBm |
| L3 | 10 dB | 38 dB | -32.1 | 49 | -91 dBm | -24 dBm |
| L4 | 20 dB | 48 dB | -22.5 | 154 | -81 dBm | -14 dBm |
| L5 | 30 dB | 58 dB | -12.5 | 486 | -71 dBm | -4 dBm |

- L5 leaves 12 dB to ADC full scale (2047). No step above L5 in T4; higher
  J/N needs a lower RX gain and belongs to T5.
- Expected without the CRPA (w = [1,0]): a CW of J/S 28 dB raises the
  effective noise of a C/A receiver by roughly 10 dB (J / (N0 x 1.023 MHz),
  spectral separation factor taken as 1; the real value depends on the PRN
  code lines), so C/N0 should start to fall at L1 to L2 and tracking should be
  lost at about L3 to L4.
- PI needs the jammer well above the bladeRF carrier and satellites (common
  part about 8 dB below the noise here). L3 is 18 dB above it, L2 only 8 dB:
  at L2 and below the weights are a compromise and PI partly nulls the
  satellites. So the PI results that count are L3, L4 and L5; L2 is recorded
  to show the transition.
- If L5 cannot be reached with 60 dB (B205mini output too low), replace one
  30 dB attenuator by 20 dB (50 dB in total) after asking the user, and repeat
  P2. The attenuators are before SPL2, so D does not change.

### 2.2 Measured in P2 and P3 (V1, 2026-11-10)

Jammer alone, 30 + 30 dB, amplitude 0.5, 3 passive captures per step
(`results/t4_P2_*.txt`, `results/t4_P2_jammer.txt`). Noise in this run:
-42.53 / -42.84 dBFS.

| Step | B205mini gain | J/N (x1) | x1 / x2 dBFS | Peak | Line over the floor |
|---|---|---|---|---|---|
| L1 | 35 dB | -9.2 dB | -42.04 / -42.42 | 67 LSB | 36 dB |
| L2 | 45 dB | 0.6 dB | -39.20 / -39.87 | 74 | 46 dB |
| L3 | 55 dB | 10.8 dB | -31.40 / -32.34 | 109 | 56 dB |
| - | 60 dB | 15.8 dB | -26.62 / -27.61 | 147 | 61 dB |
| L4 | 65 dB | 20.9 dB | -21.63 / -22.65 | 220 | 66 dB |
| - | 70 dB | 25.9 dB | -16.62 / -17.66 | 353 | 71 dB |
| L5 | 75 dB | 30.5 dB | -12.03 / -13.08 | 566 | 75 dB |

- The ladder uses these gains as measured (steps 9.6 to 10.2 dB). The last
  5 dB of gain give 4.6 dB; where it compresses is not located. Below 35 dB
  the line follows the gain down to 0 dB (5 dB over the floor).
- `--max-gain 78` from here on.
- Jammer line at -2.8056 MHz in baseband (5.6 kHz below nominal). The second
  bladeRF line is at -2.8245 MHz: use `--cw-span 15e3` when both are on.
- After `off` and after `quit`: no line, noise level back. The B205mini need
  not be unplugged between runs.
- These levels hold for this cabling; a changed jammer leg changes the level
  in that channel and g_J.

| V1 | GPS path | Jammer | |
|---|---|---|---|
| Phase x2 against x1 | 165.74 deg (P1), 166.02 (P3) | 168.94 deg at L3 (P2), 168.95 (P3); 169.40 at L5 | **D = 2.93 deg** (std 0.17, 30 captures with both on, `results/t4_P3_*.txt`) |
| x2/x1 on the line | -0.76 dB (P1), -0.81 (P3) | -0.98 dB (-1.05 at L5) | 0.2 dB |

Section 5 with these values: Gs -24 dB, Gn +3.5 dB, C/N0 change about
-27 dB with PI. The separate measurements (P1, P2) and the joint one (P3)
agree within 0.3 deg.

**V3 (2026-11-10): V1 with the jammer leg to CMB1 (RX1) changed from a 25 cm
to a 50 cm cable** (as stated by the user), GPS path untouched. P3 with both
on at gain 55 dB, 30 captures (`results/t4_P3_V3_*.txt`):

| V3 | GPS path | Jammer | |
|---|---|---|---|
| Phase x2 against x1 | 167.72 deg (std 0.18) | -92.29 deg (std 0.03) | **D = 100.0 deg** (std 0.19) |
| x2/x1 on the line | -0.64 dB | -0.15 dB | 0.5 dB |

- Section 5 with these values: Gs +3.5 dB, Gn +3.1 dB, C/N0 change with PI
  about +0.4 dB against w = [1,0] with the jammer off.
- The longer leg takes 0.7 dB from the jammer in x1 (J/N at gain 55 dB: 10.1
  instead of 10.8 dB); x2 is unchanged. The gains of the ladder are kept.
- The GPS phase moved 1.7 deg and its x2/x1 0.17 dB against V1 although the
  GPS path was not touched (T3 saw 0.7 deg from re-mating connectors); the
  line-over-floor values of both sources are 0.6 to 1.4 dB lower, which is
  within what the position of the line between FFT bins can do. GPS alone
  was not measured again in V3.
- The receiver runs start in V3 (D in the 60 to 120 deg class). V1 (D 2.9
  deg) is kept as the "D near 0" case.

---

## 3. Safety

The rules of `docs/test-equipment.md`, Section 2 apply. T4 has three
transmitters.

- **Conducted only.** Every TX port is cabled through attenuators before
  anything is started: bladeRF through 40 dB, B205mini through 60 dB (never
  less than 50 dB), Pluto TX1 through the DC block with at least 50 dB TX
  attenuation. No open ports: the fourth splitter is not used, and the
  B205mini RX2 port and Pluto TX2 stay unconnected and unused (TX2 at
  89.75 dB).
- **Worst case of the jammer:** B205mini at full gain (about +20 dBm at most)
  through 60 dB + 7 dB gives -47 dBm at the Pluto RX ports: the ADC clips, and
  nothing is damaged. Pluto TX1 with a full-scale DAC at 50 dB attenuation is
  about -43 dBm into the u-blox, whatever the jammer does.
- **One go per run** from the user, covering the bladeRF, the B205mini and the
  Pluto for that run. Claude Code starts no transmitter without it.
- **Pluto:** unchanged from T2. The user starts `crpa_ctl run --on` over
  `ssh -t` and types CONDUCTED; `--tx-att 80 --min-tx-att 50`, then `tx 60`,
  `tx 50`.
- **Jammer:** `scripts/t4_jammer.py` (Section 4.1) is a dry run without
  `--on`. With `--on` it needs `--ext-att DB` (the operator's statement of the
  attenuators, refused below 50) and `--max-gain DB` (refuses any step above
  it; set from P2 to the gain of L5 plus 3 dB). It starts at its lowest step.
- **Stopping the jammer:** on quit, end of schedule, end of input, any UHD
  error and SIGINT/TERM/HUP, the script sets the gain to 0 dB, sends end of
  burst, closes the device and writes `JAMMER OFF` to its log. Claude Code
  keeps its PID in a file and kills by PID, never by pattern. After SIGKILL or
  a crash the state is unknown: unplug the B205mini from USB.
- **Residual output after stop:** P2 checks RX-only that no line is left at
  the Pluto after the script exits (the bladeRF left a carrier in the same
  situation). If one is left, the B205mini is unplugged between runs and for
  every jammer-off reference.
- **Order:** jammer on only while the Pluto runs or during an RX-only
  capture; jammer off before `quit`. With the jammer on and w = [1,0] the
  Pluto re-transmits the jammer: at L5 about 30 dB above the normal output,
  an estimated -54 dBm into the u-blox. That is intended in the fixed runs
  and stays conducted.
- **Stop and report** if: SAT_CNT is not 0 or PEAK exceeds 1800 in any block;
  FRAME_ERR is set; a safe state is not confirmed; the measured jammer level
  is more than 6 dB from the P2 table.

---

## 4. Tools

New or changed; each is tested as far as possible without RF before P1.

### 4.1 `scripts/t4_jammer.py` (new)

CW source on the B205mini through the UHD Python API (`python3-uhd`, system
Python; present on the host, UHD 4.6.0).

- Options: `--freq` (default 1575.62e6), `--rate` (default 1e6), `--ampl`
  (default 0.5), `--gain DB` or `--schedule "T:GAIN,T:GAIN,..."` (seconds from
  start; gain `off` mutes), `--on`, `--ext-att`, `--max-gain`, `--log`.
- Level steps use the analog TX gain, calibrated per step in P2, not the
  digital amplitude: the full DAC range is kept at every step.
- Stdin commands while running: `gain DB`, `off`, `note`, `quit`. Stdin may
  be a FIFO, as for `bladegps`.
- Log: every step with host time (UTC, 1 ms), settings, and the tune result
  read back. Log name `results/t4_<run>_jammer.txt`.
- Schedules count from t0, which is the stdin command `t0` (sent by Claude
  Code together with the u-blox cold start) or the script start with
  `--start-now`. Steps are a gain, `off` or `quit`.
- "off" is: end of burst sent, no streaming, gain at the device minimum.
- Offline tests: `python3 scripts/test_t4_jammer.py` (17 tests against a
  stand-in for the `uhd` module: schedule parsing, refusals, dry run, call
  order, commands, end of input, signals, send error, gain not taken).
- Nothing about the device is assumed: the script reads the TX gain range,
  the antenna names and the frequency range from the B205mini and stops if
  the request does not fit. What the TX front end emits after "off" and
  after exit is measured in P2.

### 4.2 `scripts/t3_phase.py` (extension)

- `--cw-offset HZ` (default 0): centre of the line search is
  -Delta + offset; `--cw-span HZ` (default 200e3). With `--cw-offset 200e3
  --cw-span 50e3` the script reads the jammer line, with `--cw-offset 0
  --cw-span 50e3` the bladeRF carrier, also when both are on.
- `--cap y`: labels for the capture mux in CAP_SEL (ch0/1 = y, ch2/3 = x1).
  The CW ratio is then the jammer line in x1 over the jammer line in y.
- `--passive`: writes nothing to the Pluto, for captures while a `crpa_ctl`
  dry run is active (the normal start writes fs, LO and gain, and a rate
  write sets FRAME_ERR). It stops unless the TX side is already safe and LO,
  fs and gain already match.
- Several offsets, `--cw-offset 0,200e3`, give one row per line from the same
  capture. New last columns: `cw_offset_hz`, `cw_snr2_db` (line over the
  floor in ch2/3).
- The selftest has a two-line case and a 40 dB null case. Log names stay
  `results/t3_...` unless `--log` is given; T4 uses
  `--log results/t4_<label>_<date>-<time>.txt`.

### 4.3 `scripts/ubx_cn0.py` (extension)

- New `scripts/ubx_log.py OUT.ubx`: runs `gpspipe -R --nobuffer` and writes,
  next to the raw log, an index `OUT.ubx.idx` with the host time of every
  chunk. The receiver time cannot be used: it is wrong after a cold start
  until the first fix.
- `--from SEC --to SEC` (and `--ref-from`, `--ref-to` for the reference log,
  which may be the same file): keep the frames received in that window, in
  seconds from `--t0 UNIX`, the T0 line of the jammer log. One log gives one
  C/N0 table per jammer step. Also new: a line with the number of GPS SVs
  tracked and used.
- The steps are cross-checked against the jumps of the MON-HW jamming
  indicator and AGC in the same log and of the x1 level in the `crpa_ctl`
  CSV. Every window starts 15 s after a step and ends 5 s before the next.
- Checked by replaying `results/t2_A.ubx` through the logger: raw file
  identical, windows add up to the whole log, T2-A value unchanged
  (-2.76 dB).

### 4.4 `sw/app/crpa_ctl` (no change planned)

### 4.5 P0 checks that need hardware (done)

Neither transmits.

1. B205mini connected (cabled as Section 2 or terminated):
   `scripts/t4_jammer.py` without `--on`. Expected: gain range, antenna
   `TX/RX` and frequency range printed, `dry run: nothing tuned`.
   **Done 2026-11-10** (`results/t4_p0_jammer_dry.txt`): B205mini found over
   USB 3, TX gain 0 to 89.75 dB in 0.25 dB steps, antenna `TX/RX`, 42 MHz to
   6008 MHz; nothing tuned or streamed.
2. Pluto after a reboot or `crpa_ctl off`, noise only. The user runs
   `ssh pluto /mnt/jffs2/crpa_ctl run --mode pi --cap-sel --duration 60 --out /tmp/t4_p0`
   (dry run); during it Claude Code runs
   `.venv/bin/python scripts/t3_phase.py --passive --cap y --count 5 --label p0 --log results/t4_p0_cap.txt`.
   Pass: 5 captures, the `crpa_ctl` log shows no path error, no FRAME_ERR
   and no more missed blocks than without the captures. If the path check of
   `crpa_ctl` or the driver objects, the null measurement N (Section 6) is
   changed to captures of x1, x2 before and after the dry run, with the null
   computed from the logged weights.
   **Done 2026-11-10** (`results/t4_p0_cap.txt`, `results/t4_p0.txt`; the
   run was started without `--load`, so load 0): 5 captures of y and x1
   during the dry run, nothing written by the host. `crpa_ctl`: no path
   error, STATUS 1 in every block (no FRAME_ERR), no saturation, PI weights
   live (|w2| mean 0.013), safe state confirmed. **Cost: each capture drops
   15 to 27 single blocks** (91 of about 3600 blocks in the 3.6 s of the five
   captures; 5 at startup, none in the other 74 s). A dropped block holds
   the weights for one more millisecond, which does not matter for a
   stationary CW, so run N stays as planned. Consequences: report the
   missed blocks of every N run; do not capture during the receiver runs F
   and P; for a moving jammer (later) the captures would disturb the loop.

---

## 5. Predictions to compare with

Notation: phase = arg(R21) = x2 against x1, as in T3. phi_G, g_G for the GPS
path (bladeRF carrier line), phi_J, g_J for the jammer (amplitude ratio
x2/x1). D = phi_J - phi_G.

With y = x1 + conj(w2) x2 and an ideal null on the jammer,
conj(w2) = -exp(-j phi_J) / g_J:

```
signal gain  Gs = |1 - (g_G / g_J) exp(-j D)|^2
noise gain   Gn = 1 + 1 / g_J^2          (equal noise on both elements)
C/N0 change against w = [1,0], jammer off:  10 log10(Gs / Gn)
```

For g_G = g_J = 1: 20 log10(2 |sin(D/2)|) - 3 dB, i.e. +3.0 dB at 180 deg,
+1.8 at 120, 0.0 at 90, -3.0 at 60, -5.3 at 45, -8.7 at 30 deg. The analysis
uses the measured g and phi of each cabling, not the equal-amplitude form.

Null depth: the model values are upper bounds. In hardware the limit is
expected from what differs between the two channels over the 1 ms block
(phase noise is common; quantization, DC and IQ image are not). No number is
predicted; T4 measures it.

---

## 6. Steps and runs

Who acts: U = user, C = Claude Code. "RX-only" means no Pluto transmission
(`t3_phase.py` puts the TX side in the safe state and reads it back).

### Preparation

| Step | Content | RF on | Who |
|---|---|---|---|
| P0 | Tools of Section 4 written and tested offline; `t4_jammer.py` dry run against the B205mini (no `--on`); `iio_readdev` during a `crpa_ctl` dry run with `--cap-sel`, noise only | none | C; U runs the ssh part |
| P1 | Cabling of Section 2, jammer legs straight (variant V1). B205mini connected, idle. GPS alone: `t3_phase.py --seq one --count 30`, then bladeRF unplugged: noise only, 10 captures | bladeRF | U cables, C measures after the go |
| P2 | Jammer alone (bladegps stopped), RX-only: gain from the lowest step upwards in 5 dB steps until L5, 3 captures each, `--cw-offset 200e3`. Table gain -> J/N, phi_J, g_J, peak, line frequency. Then stop the script and capture again: residual line or not | B205mini | C after the go |
| P3 | Both on, RX-only, at L3: both lines read in the same captures, 30 captures: D for V1. Compare with phi_J - phi_G from P1 and P2 | both | C after the go |

P1 expects a phase different from the 173 deg of T2 (new parts in both legs)
and |rho| near 0.13. P2 gives the calibration that all later runs use; J/N is
taken from the wideband level, (P_on - P_noise) / P_noise per element. If the
ladder is not within 2 dB of 10 dB steps, the gain values are adjusted, not
the analysis.

### Cabling variants

| Variant | Jammer legs | Aim |
|---|---|---|
| V1 | as first cabled | whatever D results |
| V2 | crossed (a to CMB2, b to CMB1) | a second D |
| V3 | as V1 or V2, with one SMA adapter or a short cable added in one leg (about 2.3 cm of coax is 65 deg at L1, T3-G) | a third D |

Aim: one D of 120 to 180 deg, one of 60 to 120 deg, one of 25 to 50 deg (the
sign does not matter). D cannot be chosen in advance: after V1 and V2 are
measured (P3 repeated for V2, RX-only), pick the change for V3 that fills the
missing class. If two variants fall in one class, keep both and say so.
The full set of runs is done for V1 first; V2 and V3 follow only after the V1
results are reviewed.

### Runs per variant

Each run: one go. Sequence as T2: U starts `crpa_ctl` and reaches `tx 50`;
C starts `bladegps`, the jammer script and `scripts/ubx_log.py`, cold-starts the
u-blox 30 s later and sends `t0` to the jammer script at the same moment
(t = 0), and reports when the schedule has ended; U quits
and fetches the CSV and log with `scp -O`.

| Run | Pluto | Jammer schedule (from the cold start, t = 0) | Gives |
|---|---|---|---|
| Vn-N | dry run, no `--on`: `crpa_ctl run --mode pi --load 24 --cap-sel --duration 150 --out /tmp/t4_VnN` | L3, L4, L5, 40 s each; C captures y and x1 with `t3_phase.py --cap y --cw-offset 200e3`, 10 captures per level | Null depth per level, RX-only; weights and R from the CSV |
| Vn-F | `--on`, `--mode fixed --w 1,0,0,0` | off to 180 s; then L1, L2, L3, L4, L5, 60 s each; off from 480 s to 570 s | Reference C/N0 of this cabling (60 to 175 s); C/N0 and tracking against J/S without the CRPA; re-acquisition after the jammer |
| Vn-P | `--on`, `--mode pi --load 24` | L5 on **before** `crpa_ctl` starts and to 180 s; then L4, L3, L2, 60 s each; off from 360 s to 420 s | Acquisition and TTFF from a cold start under the jammer with PI; C/N0 per level; with the jammer off, PI turns to the bladeRF carrier and the satellites (expected loss, recorded as the known limit) |

- `--load 24` is 0.1 x the noise power per sample (237 LSB^2 at -42.5 dBFS),
  the starting value of plan Section 5.4; alpha 0.
- Vn-N comes first in each variant: it needs no Pluto transmission and shows
  whether PI works before a receiver run is spent.
- Vn-F is independent of D (only RX1 matters). It is repeated per variant
  anyway, as the reference in the same cabling and on the same day.
- Run time about 10 min each. Three variants: 9 runs.

### Parameter runs (in V3, decided 2026-11-11; first planned for V1)

Done in V3 while it is cabled: in V1 D is 2.9 deg. The runs are named V3-L
and V3-A.

| Run | Pluto | Jammer | Gives |
|---|---|---|---|
| V1-L | dry run with `--cap-sel`, PI; U types `load 0`, `load 24`, `load 240`, `load 2400` about every 30 s | L3 constant, then repeated at L5 | Null depth against the load; choice of the default |
| V1-A | dry run with `--cap-sel`, PI, `--alpha 0.9` and `--int-len 1000` in two starts | L4 constant | Null depth against alpha and block length (model: no difference on a stationary CW) |

A receiver run with a changed load or alpha follows only if these show a
difference of more than 3 dB in null depth.

### State at the end of the session of 2026-11-11 and how the runs were done

Done: P1 to P3 in V1; P3 (twice), N, F and P in V3. V3-L done
(as executed: one dry run, the jammer alternating L3 / L5 every 20 s, the
loads typed about every 60 s, continuous captures; a capture takes about
0.87 s, so 230 captures last 200 s). V3-A done (three dry runs at L4 chained in one ssh command,
capture sets timed from the user's "started"). V1-N done (25 cm cable
back, P3 repeated: D 3.2 deg; one dry run, jammer L3, L4, L5 in one
schedule, continuous captures). Then V4 (P3 only, D 73 deg) and V5 (D 29.5 deg: P3, N, F,
P). **T4 measurements are complete; next is T5 (jammer power sweep), to be
planned.** Cabling at the end of the session: V5 (50 cm cable in the jammer
leg to CMB1 / RX1, 3 cm SMA adapter in the leg to CMB2 / RX2). The variants
as cabled differ from the table above: V2 (crossed legs) was not used; V3 is
the longer leg, V4 and V5 use the adapter.
Results: `results/t4.md`. u-blox on USB. Check the cabling with the user and
repeat P3 (1 min) if anything was unplugged or the Pluto was power-cycled
(done on 2026-11-11 before V3-P: after a power cycle the first capture set
runs without `--passive`, noise only, to write LO, fs and gain).

Host side of a run, as executed (the helper shell scripts were temporary and
are not in the repository):

- `bladegps` and `t4_jammer.py` each read stdin from a FIFO kept open by a
  `sleep infinity` writer; all PIDs go to files and are killed by PID.
  `echo q > fifo` stops `bladegps`, `echo quit > fifo` the jammer.
- Jammer: `python3 scripts/t4_jammer.py --on --ext-att 60 --max-gain 78
  --gain <start> --schedule "<...>" --log results/t4_<run>_jammer.txt`.
  V3-F schedule: `180:35,240:45,300:55,360:65,420:75,480:off,570:quit`,
  start `off`.
- u-blox: `python3 scripts/ubx_log.py results/t4_<run>.ubx`; 30 s after the
  start `echo t0 > fifo` and `UBXOPTS="-P 18" ubxtool -p COLDBOOT -w 20 -v 2`
  together. t0 (unix time) is the `T0` line of the jammer log.
- Run the host side as a background job (it exceeds 10 min) and stop
  `bladegps` and the logger when the jammer script has quit.
- Windows: 15 s after a step to 5 s before the next, `ubx_cn0.py --t0 T0
  --from A --to B --ref results/t1_ref_20261107_123927.ubx`. The reference
  of V3 is the window 60 to 175 s of V3-F: -5.12 dB against T1.
- N runs and P3: `t3_phase.py --passive ... --cw-offset 0,200e3 --cw-span
  15e3` (with `--cap y` during a `--cap-sel` dry run).
- The user's files arrive as `results/t4_<run>.log` and `.csv`: rename the
  log to `.txt` (`*.log` is ignored) and commit
  `awk 'NR==1 || (NR-2)%100==0'` of the CSV as `_every100.csv`.

V3-P order, as executed on 2026-11-11 (the jammer is on before `crpa_ctl`): the user's go; Claude Code
starts `bladegps` and the jammer with `--gain 75 --schedule
"180:65,240:55,300:45,360:off,420:quit"` and reports; the user starts
`ssh -t pluto /mnt/jffs2/crpa_ctl run --on --tx-att 80 --min-tx-att 50 --mode
pi --load 24 --out /tmp/t4_V3P`, CONDUCTED, `tx 60`, `tx 50`, and says "on";
then the cold start and `t0`. Expected with PI: 3D fix at every level and
C/N0 about +0.4 dB against the V3-F reference (Section 2.2), where V3-F lost
4.0 dB at L3, 9.9 dB at L4 and the fix at L5.

Open points from this session:

- Null depth criterion: decided 2026-11-11, "within 3 dB of the model
  value" (Section 7).
- V3-N ended at 178 s with a `data_sel` error (a `crpa_ctl off` during the
  run would do this); the first V3-F start was stopped by the user after
  about 100 s. Neither cause is confirmed with the user.
- The last 5 dB of jammer gain (70 to 75 dB) give 4.6 dB: not located.
- GPS path phase 165.7 deg in P1 and 167.7 deg in V3 without a change in
  that path; GPS alone was not measured again in V3.
- Second bladeRF line 181 kHz above its carrier, 19 kHz from the jammer:
  origin not looked at.
- D classes covered: 3 deg (V1, N only), 29.5 deg (V5), 100 deg (V3); 73 deg
  (V4) measured in P3 only. No D of 120 to 180 deg; not planned.
- V5-P: G04 was not used under the jammer although weaker SVs were; TTFF
  39.3 s. Single run; not looked into.
- The GPS path phase follows the jammer legs (165.9 deg in V1, 167.3 in V4,
  167.6 in V3, 169.1 in V5): coupling between the source paths through the
  combiners is the likely reason. Each variant uses its own measured values,
  so the predictions are not affected.
- V3-P: the u-blox log has a gap of 67 s after the cold start (5 s in V3-F):
  gpsd was slow to deliver data after the receiver reset. TTFF is taken from
  NAV-STATUS. If the first minute matters in a later run, log the serial
  port directly instead of through gpsd.
- V3-P has no fixed-weight reference of the same day; the V3-F window of
  2026-11-10 is used.
- V3-A: with INT_LEN 1000 `crpa_ctl` misses 0.1 to 0.8 % of the blocks
  without any capture, and a capture takes about 11 s (5 to 6 % missed while
  it runs). Not looked into; needed before a moving-jammer test with short
  blocks.
- `crpa_ctl` writes its CSV and log to `/tmp` (RAM) and does not check the
  writes: the files of V3-A2r are cut off. Delete the fetched files from
  `/tmp` after every run; a write check in `crpa_ctl` is a candidate change.
- A capture takes about 0.87 s at INT_LEN 10000; plan capture counts from
  that.

---

## 7. Records and evaluation

- Raw: `results/t4_<run>.ubx`, `results/t4_<run>.csv` (full CSV kept locally,
  every 100th block committed, as T2), `results/t4_<run>.txt` (crpa_ctl log),
  `results/t4_<run>_jammer.txt`, `results/t4_<label>_<date>-<time>.txt`
  (captures). Every log carries the settings of plan Section 12, the
  attenuators as stated by the user, the variant and the B205mini gain.
- Summary: `results/t4.md`, with
  - the P2 calibration table and the residual-line check;
  - per variant: phi_G, phi_J, g_G, g_J, D;
  - null depth per variant and level: line in x1 over line in y from Vn-N, and
    the weights against the ideal -exp(-j phi_J) / g_J. If the line in y is
    not above the floor, the value is a lower bound and is marked so;
  - C/N0 per window: mean over the PRNs used, against the Vn-F reference
    window and against the T1 reference, number of SVs, fix type, AGC and
    jamming indicator; TTFF of Vn-P;
  - measured C/N0 change with PI against the prediction of Section 5;
  - crpa_core: SAT_CNT, PEAK, MISSED, FRAME_ERR, |w2|, y level per window.

Pass criteria:

| Item | Criterion |
|---|---|
| Recorded | Null depth and C/N0 per level for at least V1, D measured per variant |
| C/N0 recovery | In V1-P at L3, L4 and L5: 3D fix held, and mean C/N0 within 2 dB of the Section 5 prediction for the measured D (receiver resolution 1 dB), where V1-F at the same level has lost the fix or at least 10 dB |
| Null depth | Within 3 dB of the model value (`docs/fixed_point.md`: 18 / 37 / 57 dB at L3 / L4 / L5). Decided 2026-11-11; it replaces "at least J/N + 10 dB", which is tighter than the model itself at L3. Deeper values are reported, not required |
| Integrity | SAT_CNT 0, no FRAME_ERR, no gap after startup, safe state confirmed in every run |
| D dependence | V2 and V3 within 2 dB of the prediction; a larger difference is a finding to explain, not a failure of T4 |

A null depth more than 3 dB under the model value, or a C/N0 more than 2 dB under the
prediction, is a finding: stop after that variant and report before going on
(candidates: load too high, DC or image terms, leakage between the legs,
which is checked by terminating one jammer leg).

Then update plan Sections 8.2, 10 and 11, the open items "T4 setup" and
"Diagonal loading and smoothing", and `docs/test-equipment.md` (B205mini TX
use, gain table, behavior after stop).

---

## 8. Order of work

1. Decisions of Section 9: done.
2. P0: tools, offline tests and the two hardware checks of Section 4.5: done
   (2026-11-10).
3. P1 to P3 in V1, RX-only.
4. V1-N, V1-F, V1-P; evaluate; report.
5. V1-L, V1-A.
6. V2 and V3: P3, then N, F, P each.
7. `results/t4.md`, plan update.

Steps 2 and 3 fit one session; step 4 onwards needs the u-blox and the user
at the terminal for each run.

---

## 9. Decisions (user)

Decided by the user on 2026-11-10:

| # | Question | Decision |
|---|---|---|
| 1 | Who runs the jammer | Claude Code, under the user's go before each run, as for `bladegps`; locks: `--on`, `--ext-att`, `--max-gain` |
| 2 | bladeGPS TX gain | Unchanged; about 3.5 dB lower C/N0 accepted, reference taken in the T4 cabling |
| 3 | Jammer levels changed inside a run (one cold start per run, one C/N0 window per level) | Yes: 9 runs instead of about 30. Cost: the windows are 40 to 55 s, and the receiver is not cold-started per level |
| 4 | Jammer attenuators | 30 + 30 dB first; 30 + 20 dB only if L5 is out of reach (ask first) |
| 5 | Jammer frequency | L1 + 200 kHz |

Decided by the user on 2026-11-11:

| # | Question | Decision |
|---|---|---|
| 6 | Null depth criterion | Within 3 dB of the model value, instead of at least J/N + 10 dB |
| 7 | Cabling for the parameter runs L and A | V3 (D 100 deg), before V1-N and the further D values |

---

## 10. Not in this plan

- J/N above 30 dB, lower RX gain, the J/S limit with PI: T5.
- Narrowband (modulated) jammers: after T4, same setup, another waveform in
  `t4_jammer.py`.
- Output level control (AGC) for the fixed-weight case under jamming; in PI
  the output stays near the noise level.
- LO leakage and image of the Pluto TX (plan Section 10.2), and the 180 deg
  ambiguity of the T3-G split.
