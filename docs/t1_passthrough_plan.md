Task: T1 pass-through test tooling that I (the user) will run by hand

Context
- See docs/pluto-crpa-plan.md (Sections 4, 8.2, 9.3, 12) and docs/interface.md.
- T1 = RX -> TX pass-through on the current firmware via debugfs loopback=2
  (TX data_sel = 8), with the LO offset scheme (RX LO = TX LO = L1 + Delta).
- I will run the tests myself and tune levels interactively. Your job is to
  write the tools, test them as far as possible without transmitting, and
  document how to use them. Do not transmit anything yourself.

Test setup (conducted only, never radiate)
-  GPS simulator SDR (bladeRF, gps-sdr-sim)
    -> fixed attenuator (40 dB; changed from 30 dB by the user, 2026-11-07) -> 2-way in-phase splitter
    -> RX1 and RX2 of the CRPA Pluto
-  CRPA Pluto TX1 -> DC block -> u-blox M8T (USB), with TX attenuation 50 dB in the
    Pluto (changed from a 50 dB external attenuator by the user, 2026-11-07,
    `results/t1_passthrough.md`). External plus TX attenuation at least 50 dB.
-  Pluto is connected to this host.
-  The other devices are connected another PC controlled by the user.

Before writing code, check and report:
- With data_sel = 8, which RX channel appears on which TX channel
   (confirm in fw/hdl/library/axi_ad9361 source and docs/interface.md).
   If RX2 -> TX1 is not possible on the current firmware, say so and
   propose how to test the RX2 path (e.g. u-blox moved to TX2).

Requirements
- Pluto control
   - Reuse scripts/t1_passthrough.py; extend it only if needed.
   - Settings on the command line: Delta, fs, RF bandwidth, RX gain
     (manual, same on both channels), TX attenuation.

Safety
- Dry run by default. Transmission (Pluto) only with an
  explicit --on flag, and only after an interactive prompt where I
  confirm the setup is conducted (cabled) with at least 50 dB of external plus
  TX attenuation. --on needs --min-tx-att, 50 minus the external attenuation.
- On exit, Ctrl-C or any error: disable pass-through, set TX LO away 
  and TX attenuation to maximum.
- Refuse to run if the Pluto is not in 2R2T or the settings look
  inconsistent.

Rules
- Follow Section 12 of the plan (ASCII English, set -euo pipefail for
  shell scripts, etc.).
- Test everything that does not need RF.
- Update Sections 9.3, 10 and 11 of the plan at the end.
