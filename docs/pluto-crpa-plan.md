# PlutoSDR Two-Element CRPA: Development Plan

This document is the working specification for developing a two-element CRPA (Controlled Reception Pattern Antenna) on PlutoSDR (AD9363 + Zynq XC7Z010) with Claude Code. It lives at `docs/pluto-crpa-plan.md` and is referenced from `CLAUDE.md`. Keep it up to date: update Section 10 (Status) and Section 11 (Tasks) at the end of each work session.

---

## 1. Objective and Scope

### Objective
- Apply complex weights (amplitude and phase) to the signals from two antennas, combine them, and re-transmit the result at GPS L1 from the PlutoSDR TX port.
- Feed the combined signal to a COTS GNSS receiver and evaluate interference (jammer) suppression.
- Establish the algorithm, fixed-point design and test procedure for a future multi-element CRPA (discrete RF front end + multi-channel ADC).

### Initial scope
- Signal: GPS L1 C/A (1575.42 MHz, main lobe +/-1.023 MHz).
- Algorithm: power inversion (PI), closed-form solution for two elements.
- Interference: single CW and narrowband interference.
- Test setup: conducted (cabled) or shielded environment only.

### Out of scope (future)
- Wideband signals (Galileo E1, BeiDou B1C).
- Beam steering toward satellites (MVDR etc.), which requires inter-channel calibration and the array manifold.
- More than two elements.
- Spoofing detection based on direction of arrival.

---

## 2. System Architecture

```
ANT1 -[BiasT/LNA/L1 SAW]- RX1 --+                         +-- TX1 -[DC block/ATT]- COTS GNSS receiver
                                +-- AD9363 -- axi_ad9361 --+
ANT2 -[BiasT/LNA/L1 SAW]- RX2 --+          (PL)    |       +-- TX2 (unused)
                                                   |
                         +-------------------------+-------------------------+
                         | crpa_core (PL, Verilog)                           |
                         |  - complex weight multiply x2 -> sum -> scaling   |
                         |  - covariance integration R11, R22, R21           |
                         |  - AXI-Lite registers                             |
                         +-------------------------+-------------------------+
                                                   | AXI-Lite
                                  PS (Linux): weight update loop, logging
```

- **The signal path stays entirely in the PL**: ADC outputs -> crpa_core -> DAC inputs.
- **The existing DMA paths are kept for debugging**: raw RX1/RX2 or combined data can be captured via libiio; the path is selected by a register.
- **Weights are computed on the PS**: the PS reads the covariance integrated in the PL over AXI-Lite and writes back new weights (update period ~1 ms).

---

## 3. Hardware Assumptions

| Item | Description |
|---|---|
| SDR | ADALM-PLUTO **Rev C/D** (RX2/TX2 on u.FL), 2R2T mode enabled |
| FPGA | XC7Z010-1: 17,600 LUT / 35,200 FF / 80 DSP48E1 / 60 RAMB36 |
| Antenna spacing | lambda/2 = approx. 9.5 cm (L1 wavelength approx. 19.03 cm) |
| Antenna power | Pluto provides no bias voltage; use external bias tees for active antennas |
| RF front end | External LNA and L1 SAW filter as needed (avoid saturation from strong out-of-band signals) |
| TX to receiver | **Always insert a DC block** (the receiver supplies antenna bias). Add fixed attenuation to set a proper receiver input level |
| Calibration | 2-way in-phase splitter, variable attenuator, CW source, combiner for jammer injection |

---

## 4. RF Configuration (AD9363)

### 4.1 LO offset scheme
- An LO at L1 would leak into the TX output as a CW at the L1 center, and the RX DC correction would remove the C/A center component.
- Therefore set **RX LO = TX LO = 1575.42 MHz + Delta**. The signal appears at -Delta in baseband; combining and re-transmitting it with the same LO puts it back at L1. No digital NCO is needed.
- Initial values: Delta = +3 MHz, fs = 10 MSPS (signal occupies -4 to -2 MHz).
- To evaluate: optimal Delta and fs, residual LO leakage within the receiver front-end bandwidth, IQ image (+Delta side).

### 4.2 Gain control
- **RX gain: manual mode, identical value on both channels.** Independent per-channel AGC would break the inter-channel amplitude ratio that the weights rely on.
- TX attenuation together with external attenuators sets the receiver input level.
- The combined output power varies strongly with nulling; normalize it (AGC) in the PL or PS.

### 4.3 Other
- FDD mode, identical LO frequency for RX and TX.
- Keep RX quadrature tracking and RF DC offset tracking enabled; evaluate their effect.
- Connect TX to the receiver by coax and check shielding to avoid TX-to-RX coupling.

---

## 5. Signal Processing Design

### 5.1 Data format (to be verified from the hdl source)
- axi_ad9361 2R2T outputs: `adc_data_i0/q0/i1/q1` (16 bit; 12-bit ADC value, sign-extended or MSB-aligned) with `adc_valid_*`.
- DAC inputs: `dac_data_i0/q0` (16 bit, upper 12 bits significant) with `dac_valid_*`.
- ADC and DAC sides run on the same `l_clk` (constrained as `rx_clk`, 61.44 MHz max), so no CDC is needed in the data path.
- **Verify before implementing**: ratio of `l_clk` to sample rate in CMOS 2R2T mode, valid pattern, bit alignment. Use the hdl source first, ILA second.

### 5.2 Combining
```
y[n] = conj(w1) * x1[n] + conj(w2) * x2[n]
```
- Weights w1, w2: complex, Q1.15 (16 bit).
- Complex multiply: 3-4 DSP48 per channel.
- Output: round and saturate back to 16 bit; output scale (shift or gain) set by register.

### 5.3 Covariance estimation (PL)
- Integrate R11 = sum |x1|^2, R22 = sum |x2|^2, R21 = sum x2 * conj(x1) (complex).
- Integration length N set by register (e.g. 10,000 samples = 1 ms at 10 MSPS). Accumulators ~48 bit.
- Latch results at the end of integration and set a ready flag for the PS; optional interrupt.
- Since `l_clk` is much faster than fs, multipliers may be time-shared.

### 5.4 Weight computation (PS)
- Power inversion with constraint w1 = 1 (reference element):
  ```
  w = inv(R) * e1  ~  [R22, -R21]^T
  ```
  No matrix inversion is needed. Normalize so that |w1| is equivalent to 1.
- Diagonal loading (R + delta*I) to avoid nulling on noise alone when J/N is low.
- Update period ~1 ms; IIR smoothing as a parameter.
- Future options: LMS in the PL (fast-varying jammers), MVDR (after calibration).

### 5.5 Fixed-point verification
- A Python (numpy) bit-true model is the golden reference.
- RTL simulation must match the model bit-exactly.

---

## 6. HDL Implementation

### 6.1 Base
- Use `fw/hdl/projects/pluto`, i.e. the ADI hdl that is a submodule of plutosdr-fw. Do not use a separately cloned hdl; it may not match the Linux drivers and device tree.
- **Base: plutosdr-fw upstream master (Vivado 2025.1)**; hdl at the commit pinned by that master (`4840c81f2...`). The latest release tag requires Vivado 2023.2, which does not support Ubuntu 24.04.
- Do not use `ADI_IGNORE_VERSION_CHECK=1`.
- **Do not modify ADI library IP** (`fw/hdl/library/*`). The custom IP lives in `ip/crpa_core/` and is linked into `fw/hdl/library/crpa_core` by `scripts/setup.sh` (the link is excluded from git).
- Changes to ADI project files (e.g. `projects/pluto/system_bd.tcl`) are committed on the `crpa` branch of the hdl fork.

### 6.2 Integration in the block design
- Tap the axi_ad9361 ADC outputs into crpa_core in parallel with the existing cpack path.
- DAC input mux:
  - 0: existing upack/DMA (normal Pluto operation)
  - 1: crpa_core output
  - 2: RX1 pass-through (test)
- Capture mux: raw RX data or combined data.

### 6.3 Clock domains and CDC
- **Datapath** (weighting, combining, covariance) runs on `l_clk` (`rx_clk`).
- **AXI-Lite registers** run on `clk_fpga_0` (100 MHz).
- Weights cross clk_fpga_0 -> l_clk; covariance results cross l_clk -> clk_fpga_0.
- Follow the ADI pattern: `up_axi` for the AXI-Lite slave and `up_xfer_cntrl` / `up_xfer_status` (`library/common/`) for handshaked transfers. Transferring both weights in one `up_xfer_cntrl` word implements the double buffering of Section 6.4 naturally.
- Reuse the CDC constraint style of the ADI library XDC files.
- `clk_fpga_0` has the smallest slack in the default design (WNS 0.946 ns). Keep the AXI-side logic minimal and register the read-data mux output.

### 6.4 Register map (draft; final version in `docs/regmap.md`)
| Offset | Name | Description |
|---|---|---|
| 0x00 | VERSION | IP version |
| 0x04 | CTRL | enable, path select, integration start, soft reset |
| 0x08 | STATUS | integration done, overflow |
| 0x0C | INT_LEN | integration length N |
| 0x10 | W1 | {w1_q, w1_i} (Q1.15) |
| 0x14 | W2 | {w2_q, w2_i} |
| 0x18 | OUT_SCALE | output shift or gain |
| 0x20- | R11, R22, R21_re, R21_im | integration results (64 bit each, two words) |
| 0x40- | PEAK / OVF_CNT | saturation counters |

- Weight writes are double-buffered and applied together by an "update" bit, so both weights change on the same sample.

### 6.5 Resources (T0 result: default design)

Build: `results/hdl/20261103-1639_4840c81f2/`, Vivado 2025.1, xc7z010clg225-1, routed.

| Resource | Used | Available | Util. |
|---|---|---|---|
| LUT | 12,693 | 17,600 | 72% |
| FF | 22,208 | 35,200 | 63% |
| **DSP48** | **72** | **80** | **90%** |
| RAMB36 | 2 | 60 | 3% |

| Block | DSP | LUT | FF |
|---|---|---|---|
| axi_ad9361 | 28 | 8,458 | 14,871 |
| rx_fir_decimator (2 ch) | 22 | 617 | 1,291 |
| tx_fir_interpolator (2 ch) | 22 | 594 | 1,915 |
| axi_tdd_0 | 0 | 462 | 902 |
| DMA x2, interconnect, SPI, IIC, cpack/upack | 0 | approx. 2,560 | approx. 3,200 |

Timing: all constraints met.

| Clock | Freq. | WNS | WHS |
|---|---|---|---|
| clk_fpga_0 | 100 MHz | 0.946 ns | 0.010 ns |
| clk_fpga_1 | 200 MHz | 3.396 ns | 0.131 ns |
| rx_clk | 61.44 MHz | 3.679 ns | 0.017 ns |

**Decisions:**
- Only 8 DSP48 remain; the CRPA needs about 10-20. **Remove rx_fir_decimator and tx_fir_interpolator** (DSP 72 -> 28, LUT approx. -1,200, FF approx. -3,200). They are only needed below approx. 2 MSPS; this project uses fs = 10 MSPS.
- Consequence: sample rates below approx. 2 MSPS will no longer work.
- Further reserves if needed: disable DC filter / IQ correction / DDS inside axi_ad9361 via parameters (check exact parameter names in `projects/pluto/system_bd.tcl` and `library/axi_ad9361/axi_ad9361_ip.tcl`), remove axi_tdd (FDD only).

---

## 7. PS Software

- User-space application on the standard Pluto Linux (plutosdr-fw).
- Register access: UIO (preferred; add a device tree node) or `/dev/mem`.
- AD9363 configuration via libiio (`ad9361-phy` attributes): 2R2T, LO, fs, bandwidth, manual gain, TX attenuation.
- Weight loop: wait for integration done (interrupt or polling) -> read R -> compute w -> write w.
- Logging: R, w, output power, saturation counters to CSV (retrieved over USB).
- Cross-compilation: **use the sysroot from the firmware actually flashed to the Pluto** (the Buildroot staging output of our own master-based build), not the release sysroot.
- Device tree changes for UIO: fragments in `sw/dts/`, applied in the plutosdr-fw / linux forks.

---

## 8. Verification Plan

### 8.1 Simulation
1. Python model: synthetic C/A signal + thermal noise + CW jammer with given arrival angles on two elements -> power inversion -> null depth.
2. RTL testbench: feed vectors generated by the Python model; outputs and covariance must match bit-exactly.
3. Simulator: Vivado xsim (Verilator / Icarus optional).

### 8.2 Hardware tests (in order)
| Stage | Content | Pass criteria |
|---|---|---|
| T0 | Reproduce default build, utilization and timing | **Done** (Section 6.5) |
| T0b | Default design without FIR decimator/interpolator | Builds, timing met; Pluto works at fs >= approx. 2 MSPS |
| T1 | Pass-through RX1 -> TX1 via PL, with LO offset | COTS receiver gets a fix; C/N0 degradation acceptable |
| T2 | Fixed weights w = [1,0] / [0,1] / [1,1] | Each path received; combining gain as expected |
| T3 | Same signal to both channels via in-phase splitter; measure inter-channel amplitude/phase | Phase difference recorded per retune |
| T4 | Conducted CW jammer into one channel (or both with phase offset); PI enabled | Null depth, C/N0 recovery |
| T5 | Jammer power sweep | J/S improvement vs. no suppression |
| T6 | Over-the-air test in a shielded environment (authorized only) | - |

- **Regulatory**: never radiate jamming signals. Tests are conducted or shielded only.

### 8.3 Metrics
- Null depth (dB)
- Receiver C/N0 (jammer on/off, CRPA on/off)
- J/S tolerance improvement
- Signal path latency (fixed; confirm it is absorbed in the receiver clock bias)
- Weight convergence time

---

## 9. Repository and Environment

### 9.1 Layout
```
pluto-crpa/                       # parent repository (main)
|-- CLAUDE.md
|-- README.md
|-- docs/
|   |-- pluto-crpa-plan.md        # this file
|   |-- environment.md            # host, Vivado, fw/hdl commits (record_env.sh)
|   `-- regmap.md                 # crpa_core register map
|-- fw/                           # plutosdr-fw fork, branch crpa (based on upstream master)
|   `-- hdl/                      # ADI hdl fork, branch crpa
|-- ip/crpa_core/                 # custom IP (Verilog): rtl/, tb/, IP packaging
|-- model/                        # Python bit-true model, test vector generation
|-- sw/app/                       # PS application (C)
|-- sw/dts/                       # device tree fragments
|-- scripts/                      # setup.sh, build_hdl.sh, report_util.tcl, record_env.sh
|-- tools/                        # sysroot etc. (git-ignored)
`-- results/                      # reports and measurement logs
```

### 9.2 Environment
- Host: Ubuntu 24.04.4 LTS, Vivado 2025.1 at `/tools/Xilinx/2025.1`.
- `VIVADO_SETTINGS=/tools/Xilinx/2025.1/Vivado/settings64.sh`
- Submodule remotes: `origin` = own fork, `upstream` = analogdevicesinc. `.gitmodules` URLs stay HTTPS; pushes go over SSH via `pushInsteadOf`.

### 9.3 Scripts
| Command | Purpose |
|---|---|
| `./scripts/setup.sh` | Link `ip/crpa_core` into `fw/hdl/library/crpa_core` (excluded from git) |
| `./scripts/build_hdl.sh 2>&1 \| tee results/build_hdl.log` | Build `fw/hdl/projects/pluto` and write `util_placed.rpt`, `util_hier.rpt`, `timing_summary.rpt` to `results/hdl/<date>-<time>_<hdl commit>/` (30-60 min) |
| `./scripts/record_env.sh >> docs/environment.md` | Append a snapshot of host, Vivado and commit hashes |

`build_hdl.sh` wraps `source "$VIVADO_SETTINGS"` in `set +u` / `set -u` because the Vivado settings scripts reference unset variables.

---

## 10. Status

### 10.1 Done
- [x] Host set up (Ubuntu 24.04.4, Vivado 2025.1)
- [x] Forks and `crpa` branches for plutosdr-fw and hdl (based on upstream master; hdl requires Vivado 2025.1)
- [x] `scripts/setup.sh`: custom IP link created and excluded from git
- [x] T0: default design built; utilization and timing recorded (Section 6.5)
- [x] Decision: remove FIR decimator/interpolator

### 10.2 Open items
- [ ] Record environment in `docs/environment.md` (`scripts/record_env.sh`)
- [ ] 2R2T (CMOS) `l_clk` ratio, valid pattern, bit alignment
- [ ] LO offset Delta and fs (LO leakage and IQ image)
- [ ] Output normalization in PL or PS
- [ ] Diagonal loading delta and smoothing constant
- [ ] UIO vs. `/dev/mem`; interrupt vs. polling
- [ ] Target receiver input level and external attenuation
- [ ] COTS GNSS receiver to use and how to read C/N0 (NMEA/UBX)
- [ ] Extent of RTL reuse for the future multi-element CRPA
- [ ] Procedure to extract the PS sysroot from our own firmware build

---

## 11. Tasks for Claude Code

Work through these in order. Mark progress in Section 10 when a task is finished.

### Task 1: FIR removal baseline (T0b)
1. Read `fw/hdl/projects/pluto/system_bd.tcl` and identify how `rx_fir_decimator`, `tx_fir_interpolator` and their control signals (decimation/interpolation enable, rate_gen) connect axi_ad9361, cpack and upack.
2. Report the planned rewiring to the user before editing.
3. On the hdl `crpa` branch, remove both FIR blocks and connect axi_ad9361 directly to cpack/upack. Leave any control outputs that lose their sink unconnected or tied off as appropriate; do not edit `library/`.
4. Check whether the device tree or Linux driver references the FIR blocks (e.g. GPIOs); report findings.
5. Build with `scripts/build_hdl.sh`; compare utilization and timing with T0 and record them in Section 6.5.

### Task 2: Verify the ADC/DAC interface
- From `library/axi_ad9361/` (CMOS interface, 2R2T), document in `docs/regmap.md` or a new `docs/interface.md`: port names, widths, valid pattern, bit alignment, `l_clk` vs. sample rate.
- Plan an ILA capture if the source is ambiguous.

### Task 3: Python bit-true model (`model/`)
- Signal + noise + CW jammer generator for two elements.
- Fixed-point combiner and covariance integrator matching Section 5.
- PI weight computation (floating point, PS reference).
- Test vector export for the RTL testbench.

### Task 4: crpa_core RTL (`ip/crpa_core/`)
- Datapath on `l_clk`: weight multiply, sum, round/saturate, covariance accumulators.
- AXI-Lite on `clk_fpga_0` using `up_axi`; CDC via `up_xfer_cntrl` / `up_xfer_status`.
- Testbench in `ip/crpa_core/tb/` comparing against model vectors.
- IP packaging in ADI library style (`Makefile`, `crpa_core_ip.tcl`).

### Task 5: Block design integration
- Add crpa_core to `projects/pluto/system_bd.tcl`, with DAC and capture muxes (Section 6.2).
- Build, record utilization and timing.

### Task 6: PS application and device tree
- UIO node in `sw/dts/`, C application in `sw/app/` (Section 7).

---

## 12. Rules for Claude Code

- HDL is **Verilog** (Verilog-2001, minimal SystemVerilog). Every module gets a testbench.
- **All scripts, source code, comments and commit messages are ASCII English.**
- Shell scripts use `set -euo pipefail`; wrap sourcing of external scripts such as Vivado `settings64.sh` in `set +u` / `set -u`.
- Never modify ADI library IP (`fw/hdl/library/`). ADI-side changes are limited to project files such as `fw/hdl/projects/pluto/` and are committed on the `crpa` branch.
- Edit the custom IP only in `ip/crpa_core/` (`fw/hdl/library/crpa_core` is a link).
- Commit order for submodules: `fw/hdl` -> `fw` -> parent. Push each to its fork before updating the reference above it.
- Never force-push (`git push -f`) without the user's confirmation.
- RTL changes must pass the bit-exact comparison with the Python model before commit.
- Build with `scripts/build_hdl.sh`; keep reports in `results/hdl/` and compare utilization and WNS with the previous build.
- After upstream updates or environment changes, append a snapshot with `scripts/record_env.sh`.
- Document fixed-point widths, rounding and saturation in code comments and in `docs/`.
- Always record hardware settings (LO, fs, gains, attenuation) in measurement logs.
- Do not implement from guesses about ADI IP ports or behavior; confirm in the source or with ILA first.
- Ask the user before long-running operations (`git submodule update --init --recursive`, full firmware build, HDL builds).
- Update Section 10 and Section 11 of this file at the end of each work session.
