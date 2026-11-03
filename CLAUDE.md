# pluto-crpa

Two-element CRPA (Controlled Reception Pattern Antenna) anti-jamming prototype on PlutoSDR (AD9363 + Zynq XC7Z010).

**Read `docs/pluto-crpa-plan.md` before starting any work.** It is the specification for this project and contains:
- Section 10: current status and open items
- Section 11: the ordered task list (start with the first unfinished task)
- Section 12: work rules (mandatory)

## Repository

- `fw/` - plutosdr-fw fork, branch `crpa` (based on upstream master). `fw/hdl` is the ADI hdl fork, branch `crpa`.
- `ip/crpa_core/` - custom IP (Verilog). Linked into `fw/hdl/library/crpa_core` by `scripts/setup.sh`; edit only here.
- `model/` - Python bit-true reference model
- `sw/app/` - PS application (C), `sw/dts/` - device tree fragments
- `docs/` - plan, environment record, register map
- `results/` - utilization/timing reports and measurement logs

## Environment

- Ubuntu 24.04.4, Vivado 2025.1
- `export VIVADO_SETTINGS=/tools/Xilinx/2025.1/Vivado/settings64.sh`

## Commands

- Setup link (once per clone): `./scripts/setup.sh`
- HDL build + reports (30-60 min, ask the user first): `./scripts/build_hdl.sh 2>&1 | tee results/build_hdl.log`
- Record environment: `./scripts/record_env.sh >> docs/environment.md`

## Key rules (full list in plan Section 12)

- All code, scripts, comments and commit messages in ASCII English.
- Never modify `fw/hdl/library/`; ADI-side changes only in project files on the `crpa` branch.
- Submodule commit order: `fw/hdl` -> `fw` -> parent. No force-push without confirmation.
- Confirm ADI IP behavior from source (or ILA) before implementing; do not guess.
- Update Sections 10 and 11 of the plan at the end of each session.
