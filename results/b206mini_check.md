# B206mini compatibility check: results

Plan: `docs/b206mini_check.md`. Host UHD: 4.10.0.0-0-g2af4ddb9, built from
source (`~/Work/uhd`, branch `UHD-4.10` at tag v4.10.0.0, commit
`2af4ddb96219a99d2300804830e0971f79557b23`, `scripts/build_uhd.sh`, 105 of 105
unit tests passed), installed in `/usr/local` next to the Ubuntu UHD 4.6
packages. Tools and `python3 -c "import uhd"` both report 4.10.0.0 from
`/usr/local`.

## C1, enumeration (2026-11-21, no RF)

Log: `results/b206mini_C1_20261121-131942.txt`.

| Item | B206mini | B205mini (T4/T5, UHD 4.6) |
|---|---|---|
| Product / name | B206mini / `B206i` | B205mini / `B205i` |
| Serial (UHD) | `352F132` | `3297659` |
| USB ID | 2500:0023 (boot loader and after firmware load) | 2500:0022 |
| EEPROM product | 30523 (0x773b, B206mini in `B2XX_PRODUCT_ID`) | - |
| Revision | 2 | - |
| FW / FPGA | 8.0 / 7.0 | 8.0 / 7.0 |
| FPGA image | `/usr/local/share/uhd/images/usrp_b205mini_fpga.bin` | `/usr/share/uhd/images/usrp_b205mini_fpga.bin` (4.6 package) |
| USB link | USB 3 (5000 Mb/s after the firmware load; 480 in the FX3 boot loader) | USB 3 |
| Master clock (default) | 16 MHz, automatic | 16 MHz (rate top 16 MSPS) |
| TX gain | 0 to 89.75 dB, step 0.25 | same |
| TX antenna | `TX/RX` | same |
| TX frequency range (`get_tx_freq_range`) | 42 to 6008 MHz | same |
| TX rate range | 31.25 kHz to 16 MSPS | same |
| Sensors | `ref_locked`; FE temp, lo_locked | - |
| `uhd_usrp_probe` time, first open with FPGA load | 10.4 s | about 12 s (jammer first open) |

## C2, scripts (2026-11-21, no RF)

- `python3 scripts/test_t4_jammer.py`: 23 tests OK under UHD 4.10 (stand-in
  `uhd` module; checks that the script and its tests run in the new
  environment).
- Dry runs, `--args serial=352F132`, nothing tuned or streamed:
  CW (default path), N1 (8 MSPS), PN (8.184 MSPS), N10 (16 MSPS) with
  `--lo-offset=-6e6`: all exit 0, sidecars checked, rates inside the range.
  Logs `results/b206mini_C2_dry_{CW,N1,PN,N10}.txt`. Device lines identical to
  the B205mini dry runs of 2026-11-18 (`tmp/t5b_dry_*.txt`).
- `scripts/t4_jammer.py` default `--args` changed to `serial=352F132`;
  device-neutral texts ("unplug the USRP"). Dry run with the default:
  `results/b206mini_C2_dry_default.txt`, B206mini opened. Tests still 23 OK.
- `t3_phase.py --seq selftest`: PASS.

**C1 and C2 pass.** What a dry run cannot show (exact rate and LO set,
`lo_off` honoured, underflows, output level) is part of C3.

## C3, RF, Pluto RX-only (2026-11-21, 13:29 to 13:33)

Go from the user for the run; cabling confirmed by the user: B206mini
`TX/RX` through 30 + 20 dB to SPL2 (V3, as T5 G60 and T5b), `RX2`
unconnected. bladeRF unplugged. Pluto (CRPA unit) found in its boot state
(power-cycled): the first `t3_phase.py` run (not passive, no jammer) wrote TX
safe, RX LO L1 + 3 MHz, 10 MSPS, 9 MHz, gain 60 once; all later captures
`--passive`, 3 per step, `--cw-offset 0,200e3 --cw-span 50e3 --spurs 5`
(span widened from 15 kHz for an unknown line offset). TX safe (TX LO powered
down, 89.75 dB) at the start and end. Jammer `t4_jammer.py --on --ext-att 50`
through a FIFO, stopped by `quit` (temporary runner, as in T4/T5).
Safety input: maximum TX power 16.06 dBm at 70 MHz to 4 GHz (NI
specifications, given by the user), 3.9 dB below the B205mini assumption of
+20 dBm; the 40 dB floor of `--ext-att` stays (`docs/b206mini_check.md`,
Section 4).

Logs: `results/t3_b206mini_C3_*_20261121-13*.txt` (captures),
`results/b206mini_C3_{cw,N1,N10}_jammer_20261121-132917.txt` (jammer).

**Noise (init, B206mini not opened):** x1 / x2 -42.52 / -42.81 dBFS, L1 +/-
1 MHz -49.79 dBFS (T5b P1: -42.56 / -42.90, -49.83). J/N60 below uses this
noise: J/N60 = 10 log10(10^((P_x1 - N)/10) - 1).

**CW ladder** (L1 + 200 kHz, amplitude 0.5, 1 MSPS):

| Gain (dB) | x1 dBFS | J/N60 B206mini | J/N60 B205mini (T5, gain - 35 below 70) | Line over floor | Clipped (x1 / x2, of 3.1 M) |
|---|---|---|---|---|---|
| 35 | -39.63 | -0.3 | 0 | 45.0 dB | 0 / 0 |
| 45 | -32.49 | 9.6 | 10 | 54.7 | 0 / 0 |
| 55 | -22.70 | 19.8 | 20 | 64.8 | 0 / 0 |
| 65 | -12.70 | **29.8** | **30.0** | 74.0 | 0 / 0 |
| 70 | -7.63 | 34.9 | 35.0 | 77.4 | 0 / 0 |
| 72.5 | -5.53 | 37.0 | - | 78.4 | 0 / 0 |
| 75 | -3.15 | 39.4 | 39.5 | 79.4 | 0 / 0 |
| 77.5 | -0.80 | 41.7 | 41.9 | 79.9 | 0 / 0 |
| 78.5 | 0.18 | 42.7 | (78: clipped) | 79.1 | 332483 / 286544 |
| 79.5 | 0.92 | 43.4 | - | 78.1 | 800291 / 798854 |

- **Anchor met:** gain 65 gives J/N60 29.8 (30.0 +/- 1). Every step up to
  77.5 dB within 0.4 dB of the B205mini. **The T5 gain table carries over**
  (J/N60 = gain - 35 dB below 70 dB, 50 dB of attenuators).
- Compression as the B205mini: 2.1 / 2.4 / 2.3 dB per 2.5 dB from 70 to
  77.5 dB (B205mini 2.2 to 2.6). ADC clip onset between gain 77.5 and 78.5,
  J/N60 41.7 to 42.7 (B205mini: 78 dB, 42.2).
- **Line at the Pluto 5.18 to 5.33 kHz below nominal** (B205mini 5.6 kHz),
  inside the `--cw-span 15e3` of the T5 / T5b commands.
- Jammer phase x2/x1 -90.8 deg, ratio -0.10 dB (T5: -91.2 deg, -0.19 dB):
  the V3 jammer legs are as in T5.
- No line at L1 + 200 kHz with the jammer opened and off (1.0 dB over the
  floor) and after `quit` (2.2 dB).

**Waveform files** (centre L1, `--freq 1575420000`, no LO offset):

| File | Rate | Gain | x1 dBFS | J/N60 | Underflows | Clipped |
|---|---|---|---|---|---|---|
| N1 | 8 MSPS | 65 | -21.88 | 20.6 | 0 (60 s) | 0 / 0 |
| N1 | 8 MSPS | 75 | -12.34 | 30.2 | 0 (60 s) | 1 / 0 |
| N10 | 16 MSPS | 65 | -23.57 | 18.9 (in the 9 MHz passband) | 0 (60 s) | 0 / 0 |

- Rates set exactly (1, 8, 16 MSPS read back), RF within 0.5 Hz of the
  target; no underflow, sequence error or other event in any run.
- N1: J/N60 = gain - 44.5 dB, as the T5b estimate (9 dB lower drive than CW,
  about gain - 44); the first clipped sample at J/N60 30.2, against the
  predicted Gaussian onset near 31. x2/x1 in the band -0.10 dB, coherence
  1.000, phase -90.8 deg.
- **LO leakage at L1:** with N1 no line rises above the jammer spectrum at L1
  (3.0 dB, the statistical maximum of the bins); with N10 (spectrum density
  about 10 dB lower) a line 8.1 dB over the local floor, estimated
  **about -40 dBc** against the total N10 power. Below the -30 dBc limit of
  `docs/t5b_plan.md`, Section 2.5: no LO offset needed. `--lo-offset` was
  not exercised on hardware.
- After each `quit`: `JAMMER OFF` in the log, no line, noise back
  (-42.53 / -42.83 and -42.54 / -42.83 dBFS).

**C3 passes. The B206mini is compatible with the B205mini for T5b:** same
gain to J/N60 within 0.4 dB, same clip onset within one step, same line
offset within 0.4 kHz, no underflows at 16 MSPS, clean off-state.

State at the end: Pluto at L1 + 3 MHz, 10 MSPS, 9 MHz, gain 60 manual
(written once after the power cycle), TX LO powered down, TX attenuation
89.75 dB; B206mini idle (closed); bladeRF unplugged; jammer attenuators
30 + 20 dB.
