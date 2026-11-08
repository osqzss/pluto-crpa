# pluto-crpa

Two-element CRPA (Controlled Reception Pattern Antenna) anti-jamming prototype on PlutoSDR (AD9363 + Zynq-7010).

Signals from two antennas are weighted and combined in the Zynq PL, then re-transmitted at GPS L1 to a commercial off-the-shelf (COTS) GNSS receiver. Adaptive weights are computed on the Zynq PS using power inversion.

> **Status:** Early development. The FIR decimator and interpolator are removed and verified on hardware by digital loopback (T0b), the axi_ad9361 data interface is documented, and the Python bit-true model is done. The first RF test (T1) passes: through the RX1 -> TX1 pass-through, a COTS receiver gets a 3D fix on a conducted GPS simulator signal, with C/N0 about 3 dB below the direct reference. C/N0 does not change with the LO offset (+2 to +5 and -3 MHz) or the sample rate (10-30.72 MSPS). The `crpa_core` RTL matches the bit-true model in simulation, and it is now in the Pluto block design and the firmware: with its muxes at reset, normal Pluto operation is unchanged on hardware, and its registers read back over AXI-Lite. Next: device tree and PS application, then fixed-weight tests (T2). Interfaces and register maps may change.

## Overview

![System overview](docs/img/overview.png)

- Target signal: GPS L1 C/A (1575.42 MHz)
- Algorithm: power inversion (closed form for 2 elements)
- Signal path stays in the PL for low, fixed latency
- RX and TX LOs offset from L1 by the same amount, so no digital NCO is needed and LO leakage falls outside the C/A main lobe

## Goals

1. Demonstrate interference (CW / narrowband jammer) suppression with a two-element array, measured as C/N0 recovery on a COTS GNSS receiver.
2. Establish a verified flow from a Python bit-true model to Verilog RTL on a small FPGA.
3. Prepare the algorithms, fixed-point design and test procedures for a future multi-element CRPA with a discrete RF front end and multi-channel ADC.

## Roadmap

| Stage | Description | Status |
|---|---|---|
| T0 | Build the default Pluto design; record utilization and timing | Done |
| T0b | Remove the PL FIR decimator/interpolator to free DSP48 slices (72 -> 28 of 80) | Done |
| - | Verify the axi_ad9361 data interface | Done |
| - | Bit-true Python model | Done |
| T1 | PL pass-through RX1 -> TX1 with LO offset; COTS receiver gets a fix | Done (fix, C/N0, LO offset and sample rate sweep) |
| - | `crpa_core` RTL and testbench | Done (simulation) |
| - | `crpa_core` integration into the block design | Done (build, timing met; register and default-path check on hardware) |
| - | Device tree (UIO) and PS application | Next |
| T2 | Fixed weights ([1,0], [0,1], [1,1]); check combining gain | Planned |
| T3 | Inter-channel amplitude/phase measurement with a common signal | Planned |
| T4 | Conducted CW jammer; adaptive power inversion; null depth and C/N0 recovery | Planned |
| T5 | Jammer power sweep; J/S improvement | Planned |
| T6 | Over-the-air test in a shielded environment (authorized only) | Planned |

Design resources with `crpa_core` (XC7Z010): LUT 72%, FF 60%, DSP48 56% (45 of 80), BRAM 3%; all timing constraints met. See [docs/pluto-crpa-plan.md](docs/pluto-crpa-plan.md) for details.

## Hardware

- ADALM-PLUTO **Rev C/D** (second RX/TX channel on u.FL), 2R2T mode
- Two L1 antennas spaced about lambda/2 (approx. 9.5 cm), with bias tees / LNAs as needed
- DC block between Pluto TX and the GNSS receiver, with at least 50 dB of Pluto TX attenuation plus any external attenuation

## Repository Layout

```
CLAUDE.md  Instructions for Claude Code
docs/      Development plan, setup guide, environment record, interface notes, register map
fw/        plutosdr-fw fork (submodule, branch crpa); fw/hdl is the ADI hdl fork (branch crpa)
ip/        crpa_core IP (Verilog): rtl/, tb/
model/     Python bit-true reference model
sw/        PS application and device tree fragments
scripts/   Setup, build, simulation, hardware check, report and environment scripts
results/   Utilization/timing reports and measurement logs
```

`fw/` and `fw/hdl/` are git submodules. The parent repository records a specific commit of each, not a branch; see [docs/setup.md](docs/setup.md).

## Getting Started

Requirements: Ubuntu 24.04 (or 22.04), AMD Vivado 2025.1. Full instructions, including host fixes for Ubuntu 24.04, are in [docs/setup.md](docs/setup.md).

```bash
git clone --recursive https://github.com/osqzss/pluto-crpa.git
cd pluto-crpa
./scripts/setup.sh

export VIVADO_SETTINGS=/tools/Xilinx/2025.1/Vivado/settings64.sh
./scripts/build_hdl.sh 2>&1 | tee results/build_hdl.log   # HDL build + reports in results/hdl/
```

Full firmware build: `cd fw && make` (see `fw/README.md` and [docs/setup.md](docs/setup.md), Section 9). After an HDL change, delete `fw/build/system_top.xsa` first: the fw Makefile only copies it when it is missing, so the old bitstream would be packaged. Flashing: [docs/test-equipment.md](docs/test-equipment.md), Section 7.1.

## Documentation

- [docs/pluto-crpa-plan.md](docs/pluto-crpa-plan.md): design specification, status, task list and work rules
- [docs/setup.md](docs/setup.md): development environment setup
- [docs/environment.md](docs/environment.md): recorded host, Vivado and commit versions
- [docs/interface.md](docs/interface.md): axi_ad9361 data interface (CMOS, 2R2T)
- [docs/fixed_point.md](docs/fixed_point.md): `crpa_core` fixed-point design and simulated performance
- [docs/regmap.md](docs/regmap.md): `crpa_core` register map
- [docs/test-equipment.md](docs/test-equipment.md): GNSS test equipment, host tools and test safety rules

## Caution

Do not radiate jamming signals. All interference tests must be performed over cables or inside a shielded enclosure, in accordance with local radio regulations.

## License

TBD. Submodules (plutosdr-fw, ADI HDL, Linux, etc.) are under their own licenses.
