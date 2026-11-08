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
| TX to receiver | **Always insert a DC block** (the receiver supplies antenna bias). Set the receiver input level with TX attenuation: at least 50 dB in total with any external attenuator (`docs/test-equipment.md`, Section 2) |
| Calibration | 2-way in-phase splitter, variable attenuator, CW source, combiner for jammer injection |

---

## 4. RF Configuration (AD9363)

### 4.1 LO offset scheme
- An LO at L1 would leak into the TX output as a CW at the L1 center, and the RX DC correction would remove the C/A center component.
- Therefore set **RX LO = TX LO = 1575.42 MHz + Delta**. The signal appears at -Delta in baseband; combining and re-transmitting it with the same LO puts it back at L1. No digital NCO is needed.
- Values: Delta = +3 MHz, fs = 10 MSPS, bw 9 MHz (signal occupies -4 to -2 MHz). Confirmed by the T1 sweep and decided by the user on 2026-11-08 (`results/t1_sweep.md`).
- To evaluate: optimal Delta and fs, residual LO leakage within the receiver front-end bandwidth, IQ image (+Delta side).

### 4.2 Gain control
- **RX gain: manual mode, identical value on both channels.** Independent per-channel AGC would break the inter-channel amplitude ratio that the weights rely on.
- TX attenuation sets the receiver input level, together with any external attenuators. Prefer attenuation inside the Pluto: at 0 dB TX attenuation and 60 dB RX gain, TX-to-RX coupling raises RX1 by 1.3 dB (`results/t1_passthrough.md`).
- The combined output power varies strongly with nulling; normalize it (AGC) in the PL or PS.

### 4.3 Other
- FDD mode, identical LO frequency for RX and TX.
- Keep RX quadrature tracking and RF DC offset tracking enabled; evaluate their effect.
- Connect TX to the receiver by coax and check shielding to avoid TX-to-RX coupling.

---

## 5. Signal Processing Design

### 5.1 Data format
Details and evidence: `docs/interface.md`.
- axi_ad9361 2R2T outputs: `adc_data_i0/q0/i1/q1`, 12-bit two's complement, sign-extended and LSB-aligned in 16 bits, with `adc_valid_*`.
- DAC inputs: `dac_data_i0/q0/i1/q1`, 16 bit. The core uses `[15:4]` and truncates `[3:0]`.
- `l_clk` = 2 x fs for every fs (20 MHz at 10 MSPS, 61.44 MHz at 30.72 MSPS). Valid is high 1 cycle in 2, so there are always 2 `l_clk` cycles per sample.
- ADC and DAC sides run on the same `l_clk` (constrained as `rx_clk`, 61.44 MHz max), so no CDC is needed in the data path.

### 5.2 Combining
```
y[n] = conj(w1) * x1[n] + conj(w2) * x2[n]
```
- Weights w1, w2: complex, Q1.15 (16 bit).
- Complex multiply: 3-4 DSP48 per channel.
- Output: round half up once after the sum, saturate to 12 bits, then shift left by 4 for the DAC input. Output gain 2^s by `OUT_SHIFT`, s = 0..15. Hold the output between updates (`docs/interface.md`, Section 4).
- Unity weight is 0x7FFF, which passes S12 input bit exactly. Widths and rounding: `docs/fixed_point.md`.

### 5.3 Covariance estimation (PL)
- Integrate R11 = sum |x1|^2, R22 = sum |x2|^2, R21 = sum x2 * conj(x1) (complex).
- Integration length N set by a 24-bit register, 1..2^24 - 1 (e.g. 10,000 samples = 1 ms at 10 MSPS). Accumulators 48 bit signed; this limit is what rules out overflow.
- Latch results at the end of integration and set a ready flag for the PS; optional interrupt.
- `l_clk` is only 2 x fs, so a multiplier can be shared by at most 2 uses per sample. Sharing is not needed: about 16 DSP48 unshared, 52 free.

### 5.4 Weight computation (PS)
- Power inversion with constraint w1 = 1 (reference element):
  ```
  w = inv(R) * e1  ~  [R22, -R21]^T
  ```
  No matrix inversion is needed. Scale so that the larger of |w1|, |w2| is 1: |w2| can exceed |w1| when the jammer is stronger on element 1.
- Diagonal loading (R + delta*I). Starting value 0.1 x noise power per sample (`docs/fixed_point.md`).
- Update period ~1 ms; IIR smoothing on R as a parameter, starting at 0.
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
  - 0: existing upack/DMA (normal Pluto operation); default after reset
  - 1: crpa_core output
- No pass-through setting in this mux (decided 2026-11-05): the TX channel's `data_sel = 8` already provides RX1 -> TX1 (`docs/interface.md`, Section 4).
- The mux only takes effect with TX `data_sel = 2`, which the PS has to set (Section 7).
- Capture mux: raw RX data or combined data.
- Task 4 put both muxes inside `crpa_core` (CTRL.DAC_SEL, CTRL.CAP_SEL; `docs/regmap.md`): `upack -> crpa_core/dma_dac_data_* -> crpa_core/dac_data_* -> axi_ad9361`, and `crpa_core/cap_* -> cpack` in place of the direct ADC connection. Both default to the existing path after reset. Task 5 only rewires the block design.
- Task 5 (done, 2026-11-08), as in `fw/hdl/projects/pluto/system_bd.tcl`: `crpa_core` on `axi_ad9361/l_clk` and `rst`, `adc_valid` = `adc_valid_i0`; `cap_data_0..3` and `cap_valid` drive `cpack/fifo_wr_data_*` and `fifo_wr_en` (one `l_clk` register on this path); the `cpack` and `tx_upack` enables stay on `axi_ad9361`. AXI-Lite at **0x7C450000** (64 KB). `irq` on **ps-10**, which is GIC SPI 54 in the device tree (by the existing mapping: ps-11 = 55, ps-13 = 57). `LIB_DEPS += crpa_core` in the project `Makefile`.

### 6.3 Clock domains and CDC
- **Datapath** (weighting, combining, covariance) runs on `l_clk` (`rx_clk`).
- **AXI-Lite registers** run on `clk_fpga_0` (100 MHz).
- Weights cross clk_fpga_0 -> l_clk; covariance results cross l_clk -> clk_fpga_0.
- Follow the ADI pattern: `up_axi` for the AXI-Lite slave and `up_xfer_cntrl` / `up_xfer_status` (`library/common/`) for handshaked transfers. Transferring both weights in one `up_xfer_cntrl` word implements the double buffering of Section 6.4 naturally.
- Reuse the CDC constraint style of the ADI library XDC files.
- `clk_fpga_0` has the smallest slack in the default design (WNS 0.946 ns). Keep the AXI-side logic minimal and register the read-data mux output.

### 6.4 Register map
Final map: `docs/regmap.md` (IP version 1.0, Task 4). Changes from the draft:
- VERSION, ID, SCRATCH at 0x00-0x08; CTRL 0x0C, STATUS 0x10, INT_LEN 0x14, W1 0x18, W2 0x1C, OUT_SHIFT 0x20, UPDATE 0x24, MISSED 0x28; results 0x40-0x68.
- CTRL: SOFT_RST, COV_EN, DAC_SEL, CAP_SEL. No "integration start" bit: blocks run back to back while COV_EN is set, as the test vectors assume.
- Weight double buffering: W1, W2 and OUT_SHIFT are staged and committed together by a write to UPDATE; STATUS.W_BUSY until applied.
- Per block, besides R: SAT_CNT (output saturation), PEAK (input peak per element), SEQ (block number). MISSED counts blocks dropped while DONE was set. These replace the draft PEAK / OVF_CNT counters.

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
- Consequence: the FPGA x8 decimation/interpolation path is gone. Measured floor with the AD9361 internal FIR off: 2.084 MSPS (`results/t0b_hw_test.md`). Lower rates need a valid FIR loaded; 0.521 MSPS was accepted in 1R1T, but without a confirmed valid filter.
- **Known limitation (until Task 6):** `zynq-pluto-sdr.dtsi` still sets `adi,axi-decimation-core-available` and `adi,axi-interpolation-core-available`. The drivers therefore still offer and accept f/8 on the `cf-ad9361-lpc` and `cf-ad9361-dds-core-lpc` `sampling_frequency` attributes. With the FIRs removed, a write of f/8 has no effect on the hardware: the data stays at f while the attribute reports f/8, with no error. Do not write f/8 to these cores; set the rate through `ad9361-phy`. Both properties are removed in Task 6.
- Further reserves if needed: disable DC filter / IQ correction / DDS inside axi_ad9361 via parameters (check exact parameter names in `projects/pluto/system_bd.tcl` and `library/axi_ad9361/axi_ad9361_ip.tcl`), remove axi_tdd (FDD only).

**T0b result: FIRs removed.** Build: `results/hdl/20261104-1348_387ca1761/`, hdl `387ca1761`, Vivado 2025.1, xc7z010clg225-1, routed. All timing constraints met. Digital loopback passed in 1R1T and 2R2T: `results/t0b_hw_test.md`.

| Resource | T0 | T0b | Change | Available | T0b util. |
|---|---|---|---|---|---|
| LUT | 12,693 | 11,470 | -1,223 | 17,600 | 65% |
| FF | 22,208 | 18,985 | -3,223 | 35,200 | 54% |
| **DSP48** | **72** | **28** | **-44** | **80** | **35%** |
| RAMB36 | 2 | 2 | 0 | 60 | 3% |

| Clock | Freq. | T0 WNS | T0b WNS | T0 WHS | T0b WHS |
|---|---|---|---|---|---|
| clk_fpga_0 | 100 MHz | 0.946 ns | 1.180 ns | 0.010 ns | 0.015 ns |
| clk_fpga_1 | 200 MHz | 3.396 ns | 3.628 ns | 0.131 ns | 0.160 ns |
| rx_clk | 61.44 MHz | 3.679 ns | 7.297 ns | 0.017 ns | 0.024 ns |

**crpa_core alone (Task 4, out of context).** `scripts/ooc_crpa.tcl`, Vivado 2025.1, xc7z010clg225-1, routed, `l_clk` 61.44 MHz and `s_axi_aclk` 100 MHz: LUT 1,269, FF 2,233, DSP48 17, BRAM 0. WNS 5.595 ns (`l_clk`), 3.431 ns (`s_axi_aclk`); all 364 CDC endpoints safe (`results/hdl/20261108-1209_crpa_core_ooc/`). Added to T0b: about LUT 72%, FF 60%, DSP 45 of 80. Confirm with the full build in Task 5.

**Task 5 result: crpa_core in the block design.** Build: `results/hdl/20261108-1301_387ca1761-dirty/` (hdl `387ca1761` plus the uncommitted Task 5 change to `system_bd.tcl` and `Makefile`), Vivado 2025.1, xc7z010clg225-1, routed. All timing constraints met; no critical warnings. `crpa_core` in the full design: LUT 1,266, FF 2,233, DSP48 17, the same as out of context.

| Resource | T0b | Task 5 | Change | Available | Task 5 util. |
|---|---|---|---|---|---|
| LUT | 11,470 | 12,733 | +1,263 | 17,600 | 72% |
| FF | 18,985 | 21,219 | +2,234 | 35,200 | 60% |
| **DSP48** | **28** | **45** | **+17** | **80** | **56%** |
| RAMB36 | 2 | 2 | 0 | 60 | 3% |

| Clock | Freq. | T0b WNS | Task 5 WNS | T0b WHS | Task 5 WHS |
|---|---|---|---|---|---|
| clk_fpga_0 | 100 MHz | 1.180 ns | 0.922 ns | 0.015 ns | 0.027 ns |
| clk_fpga_1 | 200 MHz | 3.628 ns | 3.474 ns | 0.160 ns | 0.160 ns |
| rx_clk | 61.44 MHz | 7.297 ns | 4.390 ns | 0.024 ns | 0.008 ns |

- The worst setup paths of `clk_fpga_0` and `rx_clk` are both inside `axi_ad9361` (`up_axi` -> `up_timer`, and `up_xfer_cntrl` -> TDD control reset), not in `crpa_core`. The lower slack comes from placement density, not from the new logic.
- CDC on the routed design (`cdc_crpa.rpt`, `cdc_all.rpt` in the build directory): `crpa_core` has 364 endpoints, all covered by exceptions (6 ASYNC_REG synchronizers, 355 clock-enable and 3 mux-hold controlled), none unsafe or unknown, as out of context. Design-wide, 12 unsafe and 55 unknown endpoints between `rx_clk` and `clk_fpga_0` are outside `crpa_core`; there is no T0b CDC report to compare with.
- Packaging fix found by this build: `component.xml` held the ADI common files as `../../fw/hdl/library/...`, relative to `ip/crpa_core`. The project reaches the IP through the link `fw/hdl/library/crpa_core`, so Vivado resolved them to `fw/hdl/fw/hdl/library/...` and IP generation failed. `crpa_core_ip.tcl` now copies the five files into `ip/crpa_core/adi_common/` (git-ignored) at packaging time; the Makefile still depends on the originals.

---

## 7. PS Software

- User-space application on the standard Pluto Linux (plutosdr-fw).
- Register access: UIO (preferred; add a device tree node) or `/dev/mem`.
- AD9363 configuration via libiio (`ad9361-phy` attributes): 2R2T, LO, fs, bandwidth, manual gain, TX attenuation.
- Set TX `data_sel = 2` at startup and after any TX buffer close or DDS attribute write; the driver default is DDS (`docs/interface.md`, Section 5). Refuse to start unless the core is in 2R2T.
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
| T0b | Default design without FIR decimator/interpolator | Builds, timing met; Pluto works at fs >= approx. 2 MSPS. **Done** for the digital data path, 1R1T and 2R2T (`results/t0b_hw_test.md`); RF is covered by T1 |
| T1 | Pass-through RX1 -> TX1 via PL, with LO offset. Can run on the current firmware with debugfs `loopback` = 2, which sets TX `data_sel = 8` (`docs/interface.md`, Section 4). Also check connector mapping and I/Q order | COTS receiver gets a fix; C/N0 degradation acceptable |
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
|   |-- setup.md                  # development environment setup
|   |-- environment.md            # host, Vivado, fw/hdl commits (record_env.sh)
|   |-- interface.md              # axi_ad9361 data interface (CMOS, 2R2T)
|   |-- fixed_point.md            # crpa_core widths, rounding, saturation, simulated performance
|   `-- regmap.md                 # crpa_core register map
|-- fw/                           # plutosdr-fw fork, branch crpa (based on upstream master)
|   `-- hdl/                      # ADI hdl fork, branch crpa
|-- ip/crpa_core/                 # custom IP (Verilog): rtl/, tb/, IP packaging
|-- model/                        # Python bit-true model, test vector generation
|-- sw/app/                       # PS application (C)
|-- sw/dts/                       # device tree fragments
|-- scripts/                      # setup, build, simulation, hardware check and report scripts
|-- requirements.txt              # Python packages for .venv/ (the venv is git-ignored)
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
| `./scripts/loopback_test.py [uri]` | Digital loopback check of the FPGA data path over libiio; TX_LO down and maximum attenuation during the test (about 1 min) |
| `./scripts/sim_ad9361_if.sh [log]` | xsim characterization of the unmodified axi_ad9361 core, both rx frame alignments (about 40 s) |
| `.venv/bin/python model/test_model.py` | Checks of the bit-true model (under 1 s) |
| `.venv/bin/python model/gen_vectors.py` | Write RTL test vectors to `model/vectors/` (not committed) |
| `.venv/bin/python model/sim_pi.py > results/t3_model.txt` | Performance sweeps of the bit-true path with the PS loop (about 15 s) |
| `.venv/bin/python scripts/gps_rx_check.py` | RX-only GPS C/A search on both inputs, at both +delta and -delta; TX_LO down. |
| `./scripts/t1_passthrough.py` | T1 RX1 -> TX1 pass-through control, conducted use only. `--check` is read-only (under 1 s). Default is a dry run with the TX LO parked at 2400 MHz (about 2 s). `--on --tx-att DB` asks for a typed confirmation, then stays in the foreground with commands `rx`, `tx`, `level`, `status`, `note`, `quit`; logs to `results/t1_<date>-<time>.txt`. `--off` forces the safe state. `--min-tx-att DB` (required with `--on`, 50 minus the external TX1 attenuation) refuses a lower `--tx-att` or `tx`. Other settings: `--delta`, `--fs`, `--bw`, `--rx-gain`, `--log`, `--poll` |
| `python3 scripts/test_t1_passthrough.py` | Tests of `t1_passthrough.py` against stand-in iio tools, no Pluto and no RF (about 3 min) |
| `python3 scripts/ubx_cn0.py LOG.ubx [--ref REF.ubx] [--skip SEC]` | Per-PRN C/N0 (epochs where the SV is used) and MON-HW ranges from a raw u-blox log (`gpspipe -R`), optionally against a reference log; standard library only |
| `./scripts/sim_crpa.sh [dp\|core\|all] [log]` | xsim of `crpa_core` against the model vectors (regenerated first): `crpa_dp_tb` on every case with regular and irregular `adc_valid`, and `crpa_core_tb` (AXI, CDC, muxes, flags) at two `l_clk` rates (about 1 min). Last log: `results/t4_crpa_sim.txt` |
| `vivado -mode batch -source scripts/ooc_crpa.tcl -tclargs <dir>` | Out-of-context synthesis and implementation of `crpa_core`, with utilization, timing and CDC reports (about 1 min) |
| `make -C fw/hdl/library/crpa_core xilinx` | Package the IP (`component.xml`, about 30 s; needs `VIVADO_SETTINGS` sourced). Copies `up_axi.v`, `up_xfer_*.v` and their XDC files into `ip/crpa_core/adi_common/` first, so that the packaged paths work through the link. The project build does this through `LIB_DEPS` |
| `ssh pluto 'sh -s' < scripts/frame_err_test.sh` | Runs on the Pluto: clears `crpa_core` STATUS.FRAME_ERR and watches it at 30.72 and 10 MSPS, across two rate changes; leaves TX_LO powered down (about 30 s; ssh needs the password, so the user runs it) |
| `./scripts/if_check.py [uri]` | Check `docs/interface.md` on a running Pluto over libiio: registers, and `l_clk` at three rates; TX_LO down during the rate changes (about 30 s) |

Scripts that need numpy run in the repo venv, `.venv/bin/python`. Create it once with `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt` (needs the `python3-venv` package). numpy is pinned to 2.2.2, the version that produced `results/t3_model.txt`. `t1_passthrough.py` and its tests use only the standard library.

`build_hdl.sh` wraps `source "$VIVADO_SETTINGS"` in `set +u` / `set -u` because the Vivado settings scripts reference unset variables.

---

## 10. Status

### 10.1 Done
- [x] Host set up (Ubuntu 24.04.4, Vivado 2025.1)
- [x] Forks and `crpa` branches for plutosdr-fw and hdl (based on upstream master; hdl requires Vivado 2025.1)
- [x] `scripts/setup.sh`: custom IP link created and excluded from git
- [x] T0: default design built; utilization and timing recorded (Section 6.5)
- [x] Decision: remove FIR decimator/interpolator
- [x] Unmodified firmware built and flashed (`pluto.frm` only, Rev C); `/opt/VERSIONS` matches the build (fw 2414114, hdl 4840c8, linux bf1d49); libiio host 0.25, Pluto 0.26; IIO devices: ad9361-phy, xadc, one-bit-adc-dac, cf-ad9361-dds-core-lpc, cf-ad9361-lpc, iio-axi-tdd-0

- [x] T0b build: FIRs removed (hdl `387ca1761`), DSP 72 -> 28, timing met (Section 6.5)
- [x] T0b hardware: firmware flashed, `/opt/VERSIONS` matches; digital loopback bit-exact in 1R1T and 2R2T, 2.084-30.72 MSPS in 2R2T, with all four streams sample-aligned (`results/t0b_hw_test.md`). Current device setting: `mode=2r2t`, reported as AD9363A
- [x] Environment recorded in `docs/environment.md` (latest snapshot 2026-11-05: kernel 7.0.0-42, fw `27fb31b`, hdl `387ca1761`)
- [x] Task 2 from source and simulation: `l_clk` = 2 x fs, valid pattern, bit alignment, TX read cycle, latency, driver `data_sel` behavior (`docs/interface.md`; `results/t2_if_sim.txt`, all checks pass for both frame alignments). No ILA capture needed for Tasks 3-5
- [x] Task 3: bit-true model, PS weight loop, scenario generator and test vectors (`model/`, `docs/fixed_point.md`, `results/t3_model.txt`). Ideal-model results only; no hardware impairments
- [x] T1 tooling: `scripts/t1_passthrough.py` rewritten for `docs/t1_passthrough_plan.md`, 52 offline tests pass (`scripts/test_t1_passthrough.py`, count updated 2026-11-07). On the Pluto: `--check` and the dry run pass, final state read back as safe (`results/t1_dry_run.txt`). `--on` has not been run
- [x] Task 2 on hardware: `scripts/if_check.py` passes; `l_clk` = 2.000 x fs at 3, 10 and 30.72 MSPS, driver register values as documented (`results/t2_if_check.txt`)
- [x] Connector mapping and I/Q order at RF on the second Pluto: `i0/q0` = RX1 and `i1/q1` = RX2, by terminating each splitter leg in turn; signal at -Delta on both channels, as Section 4.1 assumes (`results/t1_rx_unit_compare.md`)
- [x] T1 reference: bladeRF -> 40 dB -> DC block -> u-blox without the Pluto, mean C/N0 45.1 dB-Hz over 11 PRNs, carrier left in (`results/t1_reference.md`). Acceptable degradation through the pass-through, set by the user: 3-5 dB per comparison with this table
- [x] T1 RX1 -> TX1 pass-through with RF on the second Pluto (`results/t1_passthrough.md`): 3D fix with 11 satellites. C/N0 against the reference: -2.9 dB mean with TX1 attenuation 50 dB and no external attenuator; -3.8 dB mean with 0 dB and 50 dB external. Both within the 3-5 dB limit. At 0 dB attenuation RX1 rises 1.3 dB, so keep TX attenuation inside the Pluto
- [x] T1 step 6, Delta and fs sweep (`results/t1_sweep.md`, 2026-11-08): 10 runs, fs 10-30.72 MSPS, bw 9 and 14 MHz, Delta +2 to +5 and -3 MHz, TX1 attenuation 50 dB. C/N0 -2.4 to -2.8 dB against the reference in every run, with no dependence on fs, bandwidth or Delta beyond the 1 dB resolution; A1 repeat within 0.1 dB. Delta +2 MHz raises the u-blox jamming indicator (about 156 vs. 102-109). Decided by the user (2026-11-08): Delta +3 MHz, fs 10 MSPS, bw 9 MHz
- [x] Task 4: `crpa_core` RTL (`ip/crpa_core/rtl/`), IP version 1.0. Bit exact against the model on all vector cases, including per-block saturation and peaks; core testbench passes at `l_clk` 61.44 and 20 MHz (`results/t4_crpa_sim.txt`). IP packages in ADI style. Out of context: 17 DSP48, timing met, CDC safe (Section 6.5). Register map `docs/regmap.md`. Design decisions confirmed by the user (2026-11-08): free-running blocks (no integration-start bit), muxes inside `crpa_core`, combined capture ch0/1 = y and ch2/3 = x1, result registers frozen while DONE is set, staged weights committed by UPDATE. Not yet in the block design or on hardware
- [x] Task 5: `crpa_core` in the pluto block design (hdl `crpa` branch; Section 6.2). Full build routed, timing met, DSP 45 of 80, LUT 72%, FF 60%; `crpa_core` CDC clean in the full design (Section 6.5, `results/hdl/20261108-1301_387ca1761-dirty/`). Registers at 0x7C450000, `irq` on ps-10 (GIC SPI 54), confirmed by the user (2026-11-08). Firmware not yet built or flashed with it
- [x] Task 5 on hardware (`results/t5_hw_check.md`, 2026-11-08): firmware fw `8f9cd60` / hdl `ad150ddd5` flashed on the CRPA unit, `fw_version` v0.39-22-g8f9c. With both muxes at reset, `loopback_test.py` (0 fails) and `if_check.py` (PASS) as in T0b. Registers at 0x7C450000 read the documented reset values; SCRATCH writes back. STATUS.FRAME_ERR is set by every sample rate change and stays clear at a fixed rate (20 s at 30.72 and 10 MSPS), which the PS sequence after a rate change already covers
- [x] RX-only GPS check and unit comparison (`results/t1_rx_unit_compare.md`, 2026-11-07). The first Pluto has 12-14 dB excess noise and bursts on RX2. The second Pluto (serial `1044734c96050011f2ff2100408f4f2ac3`, same firmware) has matched channels, and all 11 simulated PRNs at -Delta on both, within 0.5 dB in SNR. The user confirmed the second Pluto as the CRPA unit (2026-11-07)

### 10.2 Open items
- [ ] LO leakage and image levels not measured (effect on the receiver only, `results/t1_sweep.md`); a measurement with the B205mini on TX1 and a Pluto RX FFT is optional
- [ ] RX2 end to end: RX2 -> TX1 does not exist with `data_sel = 8`. RX2 is checked RX-only at T1 and through `crpa_core` at T2 (`docs/interface.md`, Section 4)
- [ ] First Pluto (serial `1044734c960500110c000900418f4f7ca2`) RX2 fault: location not found (chip, board or RX2 connection). It likely explains the 8 dB difference seen in the dry run on 2026-11-05, which was on this unit
- [ ] Second Pluto so far tested RX-only, in one session. Inter-channel phase not measured. About 3 dB higher ch0/1 floor at low gain not investigated (`results/t1_rx_unit_compare.md`)
- [ ] bladeRF carrier at L1 stays after `bladegps` exits, and is also present while it runs. Effect on the C/N0 reference and the T1 result not evaluated. Whether TX is left enabled not determined
- [ ] Output normalization: `OUT_SHIFT` in the PL and TX attenuation from the PS are the current design; decide at T2 whether a PL gain multiplier is needed
- [ ] Diagonal loading and smoothing: starting values from simulation (load 0.1 x noise power, alpha 0), to be confirmed at T4
- [ ] UIO vs. `/dev/mem`; interrupt vs. polling. The level `irq` (= STATUS.DONE) is connected to ps-10 (GIC SPI 54) since Task 5, so both are possible; decide in Task 6
- [ ] FRAME_ERR at rate changes (`results/t5_hw_check.md`): the number of affected samples, and whether ENSM changes also set it, are not known. The PS must soft-reset and clear STATUS after a rate change and treat FRAME_ERR at a fixed rate as an error (Task 6)
- [ ] Target receiver input level and external attenuation
- [ ] COTS GNSS receiver to use and how to read C/N0 (NMEA/UBX)
- [ ] Extent of RTL reuse for the future multi-element CRPA
- [ ] Procedure to extract the PS sysroot from our own firmware build

---

## 11. Tasks for Claude Code

Work through these in order. Mark progress in Section 10 when a task is finished.

### Task 1: FIR removal baseline (T0b)
Status: **done** (Section 6.5, `results/t0b_hw_test.md`). Device tree cleanup moved to Task 6.

1. Read `fw/hdl/projects/pluto/system_bd.tcl` and identify how `rx_fir_decimator`, `tx_fir_interpolator` and their control signals (decimation/interpolation enable, rate_gen) connect axi_ad9361, cpack and upack.
2. Report the planned rewiring to the user before editing.
3. On the hdl `crpa` branch, remove both FIR blocks and connect axi_ad9361 directly to cpack/upack. Leave any control outputs that lose their sink unconnected or tied off as appropriate; do not edit `library/`.
4. Check whether the device tree or Linux driver references the FIR blocks (e.g. GPIOs); report findings.
5. Build with `scripts/build_hdl.sh`; compare utilization and timing with T0 and record them in Section 6.5.

### Task 2: Verify the ADC/DAC interface
Status: **done**, from source, simulation and hardware (`docs/interface.md`, `results/t2_if_check.txt`). ILA capture not needed; the plan for one is in `docs/interface.md`, Section 7.

- From `library/axi_ad9361/` (CMOS interface, 2R2T), document in `docs/regmap.md` or a new `docs/interface.md`: port names, widths, valid pattern, bit alignment, `l_clk` vs. sample rate.
- Plan an ILA capture if the source is ambiguous.

### Task 3: Python bit-true model (`model/`)
Status: **done** (`docs/fixed_point.md`).

- Signal + noise + CW jammer generator for two elements.
- Fixed-point combiner and covariance integrator matching Section 5.
- PI weight computation (floating point, PS reference).
- Test vector export for the RTL testbench.

### T1 pass-through tooling and test (`docs/t1_passthrough_plan.md`)
Status: **done.** Steps 1-5 on 2026-11-07 (`results/t1_passthrough.md`), step 6 on 2026-11-08 (`results/t1_sweep.md`). Setup and rules are in that file. Use the second Pluto, the CRPA unit (`results/t1_rx_unit_compare.md`). After any reboot, check the state first: TX_LO comes up powered on at 2450 MHz. For noise floor or reference measurements, unplug the bladeRF from USB, because stopping `bladegps` does not remove its carrier at L1. Procedure:

1. Reference: bladeRF -> attenuators -> u-blox without the Pluto; note the C/N0. Done (`results/t1_reference.md`).
2. With the full setup cabled, run `.venv/bin/python scripts/gps_rx_check.py`. PRNs should appear on both inputs at -Delta, which also shows the I/Q order. Done on the second Pluto with a longer temporary search, not with this script.
3. Connector mapping: terminate one splitter leg in 50 ohm and repeat, then swap legs. With both legs connected a swap of the RX ports does not show. Done on the second Pluto: `i0/q0` = RX1, `i1/q1` = RX2.
4. Dry run: `./scripts/t1_passthrough.py`.
5. Transmit, no external attenuator: `./scripts/t1_passthrough.py --on --tx-att 80 --min-tx-att 50`, starting with high attenuation. Set `rx` by `level` so that the ADC does not clip, then lower `tx` in steps while watching C/N0 on the other PC. Record it with `note`.
6. Vary Delta and fs for LO leakage and image. Done (`results/t1_sweep.md`): one run per setting, simulator restarted and receiver cold-started each run, C/N0 and MON-HW from `scripts/ubx_cn0.py`. If the script ends with `SAFE STATE NOT CONFIRMED`, or is killed, or USB drops, power-cycle the Pluto.

### Task 4: crpa_core RTL (`ip/crpa_core/`)
Status: **done** (2026-11-08; Section 10.1, `docs/regmap.md`, `results/t4_crpa_sim.txt`). Next is Task 5. Requirements from `docs/interface.md`, Section 8; formats and vectors from `docs/fixed_point.md`.

- Datapath on `l_clk`: weight multiply, sum, round/saturate, covariance accumulators.
- AXI-Lite on `clk_fpga_0` using `up_axi`; CDC via `up_xfer_cntrl` / `up_xfer_status`.
- Testbench in `ip/crpa_core/tb/` comparing against model vectors.
- IP packaging in ADI library style (`Makefile`, `crpa_core_ip.tcl`).

### Task 5: Block design integration
Status: **done** (2026-11-08): build (Sections 6.2, 6.5) and hardware check with both muxes at reset (`results/t5_hw_check.md`). Next is Task 6.

- Add crpa_core to `projects/pluto/system_bd.tcl`, with DAC and capture muxes (Section 6.2; two-way DAC mux, no pass-through setting).
- Build, record utilization and timing.

### Task 6: PS application and device tree
- UIO node in `sw/dts/`, C application in `sw/app/` (Section 7).
- Remove `adi,axi-decimation-core-available` and `adi,axi-interpolation-core-available` from the device tree (Section 6.5). `fw/linux` has no fork yet (detached HEAD, `origin` = ADI upstream), so decide between a fork and a patch for this and the UIO node.

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
