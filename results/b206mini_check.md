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

## C3, RF (pending)

Safety input: maximum TX power 16.06 dBm at 70 MHz to 4 GHz (NI
specifications, given by the user), 3.9 dB below the B205mini assumption of
+20 dBm; the 40 dB floor of `--ext-att` stays (`docs/b206mini_check.md`,
Section 4). Needs the user's go.
