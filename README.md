# pluto-crpa

Two-element CRPA (Controlled Reception Pattern Antenna) anti-jamming prototype on PlutoSDR (AD9363 + Zynq-7010).

Signals from two antennas are weighted and combined in the Zynq PL, then re-transmitted at GPS L1 to a commercial off-the-shelf (COTS) GNSS receiver. Adaptive weights are computed on the Zynq PS using power inversion.

> **Status:** Early development. The default PlutoSDR design builds and has been characterized (T0). Next: FIR removal baseline (T0b). Interfaces and register maps may change.

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
| T0b | Remove the PL FIR decimator/interpolator to free DSP48 slices (72 -> 28 of 80) | Next |
| - | Bit-true Python model; `crpa_core` RTL and testbench; integration into the block design | Planned |
| T1 | PL pass-through RX1 -> TX1 with LO offset; COTS receiver gets a fix | Planned |
| T2 | Fixed weights ([1,0], [0,1], [1,1]); check combining gain | Planned |
| T3 | Inter-channel amplitude/phase measurement with a common signal | Planned |
| T4 | Conducted CW jammer; adaptive power inversion; null depth and C/N0 recovery | Planned |
| T5 | Jammer power sweep; J/S improvement | Planned |
| T6 | Over-the-air test in a shielded environment (authorized only) | Planned |

Default design resources (XC7Z010, T0): LUT 72%, FF 63%, DSP48 90%, BRAM 3%; all timing constraints met. See [docs/pluto-crpa-plan.md](docs/pluto-crpa-plan.md) for details.

## Hardware

- ADALM-PLUTO **Rev C/D** (second RX/TX channel on u.FL), 2R2T mode
- Two L1 antennas spaced about lambda/2 (approx. 9.5 cm), with bias tees / LNAs as needed
- DC block and attenuator between Pluto TX and the GNSS receiver

## Repository Layout

```
CLAUDE.md  Instructions for Claude Code
docs/      Development plan, setup guide, environment record, register map
fw/        plutosdr-fw fork (submodule, branch crpa); fw/hdl is the ADI hdl fork (branch crpa)
ip/        crpa_core IP (Verilog): rtl/, tb/
model/     Python bit-true reference model
sw/        PS application and device tree fragments
scripts/   Setup, build, report and environment scripts
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

Full firmware build: `cd fw && make` (see `fw/README.md`).

## Documentation

- [docs/pluto-crpa-plan.md](docs/pluto-crpa-plan.md): design specification, status, task list and work rules
- [docs/setup.md](docs/setup.md): development environment setup
- [docs/environment.md](docs/environment.md): recorded host, Vivado and commit versions

## Caution

Do not radiate jamming signals. All interference tests must be performed over cables or inside a shielded enclosure, in accordance with local radio regulations.

## License

TBD. Submodules (plutosdr-fw, ADI HDL, Linux, etc.) are under their own licenses.
