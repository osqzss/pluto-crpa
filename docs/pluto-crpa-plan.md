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
| Calibration | 2-way in-phase splitter, variable attenuator, CW source, combiner for jammer injection. At hand (user, 2026-11-10): four 2-way splitter/combiners and several 20 dB and 30 dB attenuators |

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
- **Device tree flags (resolved in Task 6a):** up to Task 5, `zynq-pluto-sdr.dtsi` still set `adi,axi-decimation-core-available` and `adi,axi-interpolation-core-available`, so the drivers offered f/8 and silently ignored it. Both are removed on the fw/linux `crpa` branch (`7a17700`). Since then `cf-ad9361-lpc` has no `in_voltage_sampling_frequency_available` attribute and passes `sampling_frequency` writes to the AD9361 clock; `cf-ad9361-dds-core-lpc` has no interpolation attributes (`results/t6a_dt_check.md`). Set the rate through `ad9361-phy` as before.
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
- Register access: UIO. Node `crpa-core@7c450000` in `zynq-pluto-sdr.dtsi` (fw/linux `crpa`): `generic-uio`, `reg = <0x7c450000 0x10000>`, `interrupts = <0 54 IRQ_TYPE_LEVEL_HIGH>`, `linux,uio-name = "crpa_core"`. It appears as `/dev/uioN` with `/sys/class/uio/uioN/name` = `crpa_core`; find it by name, not by number. Map 0 is the 64 KB register window (`docs/regmap.md`).
- Bootargs: `uio_pdrv_genirq` binds `generic-uio` only with `uio_pdrv_genirq.of_id=generic-uio`. u-boot sets bootargs with a fixed string in its boot commands, so the kernel appends it (`CONFIG_CMDLINE` with `CONFIG_CMDLINE_EXTEND=y` in `zynq_pluto_defconfig`). No u-boot environment change.
- Interrupt: blocking `read()` on `/dev/uioN` returns when `irq` (= STATUS.DONE, level) fires; the driver masks the IRQ at that point. Clear DONE first, then write 1 to `/dev/uioN` to unmask, or the level IRQ fires again at once. Polling STATUS is kept as a fallback (`--poll`).
- Application `sw/app/crpa_ctl` (C, Task 6b). Runs on the Pluto; crpa_core through UIO, the AD9363 through local libiio. Subcommands `status` (read-only), `off` (safe state), `run` (dry run without `--on`: path set, TX muted, TX LO parked and powered down). Decided by the user (2026-11-09): the application owns the RF side, with the T1 safety rules of `scripts/t1_passthrough.py` ported: `--on` needs a terminal (`ssh -t`) and the typed word CONDUCTED, `--min-tx-att` floor, and quit, end of input, errors and SIGINT/TERM/HUP/QUIT all end in the safe state. The cleanup runs on the Pluto, so an ssh or USB drop (SIGHUP) still reaches it; SIGKILL or a crash does not (then `crpa_ctl off` or a power cycle). It refuses to start unless `data_sel` is 0 or 3 on all channels, loopback is 0 and crpa_core is idle: after a reboot or other tools, run `crpa_ctl off` once on purpose.
- Safe state of `crpa_ctl`: TX attenuation 89.75 dB on both, loopback 0, crpa_core CTRL 0, `data_sel` 0 on all, TX LO powered down, then parked at 2400 MHz, and a readback of all of these.
- Weight modes: `--mode fixed --w A,B,C,D` (T2) and `--mode pi` with `--load` (LSB^2 per sample) and `--alpha`. Weight math in `sw/app/crpa_pi.c`, equal to the model's Q1.15 output (`make -C sw/app test`). Interactive commands while running: `rx`, `tx`, `w`, `pi`, `load`, `shift`, `level`, `status`, `note`, `quit`.
- Scheduling: SCHED_FIFO 40 and locked memory by default (`--rt`). With normal scheduling a 1 Hz task on the Pluto (likely `/sbin/update.sh`) stalls the loop for 5-8 ms once a second and drops 1-7 blocks (`results/t6b_dry_run.md`).
- AD9363 configuration via libiio (`ad9361-phy` attributes): 2R2T, LO, fs, bandwidth, manual gain, TX attenuation.
- Set TX `data_sel = 2` at startup and after any TX buffer close or DDS attribute write; the driver default is DDS (`docs/interface.md`, Section 5). Refuse to start unless the core is in 2R2T.
- Weight loop: wait for integration done (interrupt or polling) -> read R -> compute w -> write w.
- Logging: one CSV row per block (`--csv-every`) to `/tmp/crpa.csv`: R, SAT_CNT, peaks, MISSED, STATUS, the weights in force, levels of x1, x2 and an estimate of y from R and w (no saturation; approximate in the first block after a weight change), mode, discard flag. Events and summaries to `/tmp/crpa.log`. Retrieve with `scp -O`.
- Cross-compilation: **use the sysroot from the firmware actually flashed to the Pluto** (the Buildroot staging output of our own master-based build), not the release sysroot.
- Device tree and kernel config changes are commits on the fw/linux `crpa` branch (fork, not carried patches). `sw/dts/` holds `git format-patch` exports of those commits for review and documentation only.
- The application stays outside the firmware for now: copied to the Pluto (`/mnt/jffs2` survives a reboot; the root file system is in RAM). Buildroot packaging later, once stable.

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
| T2 | Fixed weights w = [1,0] / [0,1] / [1,1] | Each path received; combining gain as expected. **Done** (2026-11-09, `results/t2_A.md` to `t2_C2.md`): [1,0] and [0,1] within 0.2 dB of each other and of T1; the channels are 173 deg apart, so [1,-1] gives 1.8 dB array gain (level control T2-D) and [1,1] a 20 dB null |
| T3 | Same signal to both channels via in-phase splitter; measure inter-channel amplitude/phase | Phase difference recorded per retune. **Done** (2026-11-10, `results/t3.md`): 173 deg and -0.3 dB in the T2 cabling, unchanged by retunes, rate changes and power cycles (within about 1 deg over the day). With the legs swapped: 44 deg, so the fixture legs differ by 65 deg (or -115 deg) and the Pluto itself by 109 deg (or -71 deg) |
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
|   |-- regmap.md                 # crpa_core register map
|   |-- t3_plan.md                # T3 runs, method and safety
|   `-- t4_plan.md                # T4 levels, tools, runs, pass criteria and safety
|-- fw/                           # plutosdr-fw fork, branch crpa (based on upstream master)
|   |-- hdl/                      # ADI hdl fork, branch crpa
|   `-- linux/                    # ADI linux fork (osqzss/linux), branch crpa
|-- ip/crpa_core/                 # custom IP (Verilog): rtl/, tb/, IP packaging
|-- model/                        # Python bit-true model, test vector generation
|-- sw/app/                       # PS application (C)
|-- sw/dts/                       # format-patch exports of the fw/linux crpa commits
|-- scripts/                      # setup, build, simulation, hardware check and report scripts
|-- requirements.txt              # Python packages for .venv/ (the venv is git-ignored)
|-- tools/                        # sysroot etc. (git-ignored)
`-- results/                      # reports and measurement logs
```

### 9.2 Environment
- Host: Ubuntu 24.04.4 LTS, Vivado 2025.1 at `/tools/Xilinx/2025.1`.
- `VIVADO_SETTINGS=/tools/Xilinx/2025.1/Vivado/settings64.sh`
- Submodule remotes (fw/hdl and fw/linux): `origin` = own fork, `upstream` = analogdevicesinc. `.gitmodules` URLs stay HTTPS, with `branch = crpa` for both; pushes go over SSH via `pushInsteadOf`. buildroot, u-boot and br2-external stay unmodified ADI clones.

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
| `python3 scripts/ubx_cn0.py LOG.ubx [--ref REF.ubx] [--skip SEC] [--cut DB]` | Per-PRN C/N0 (epochs where the SV is used) and MON-HW ranges from a raw u-blox log (`gpspipe -R`), optionally against a reference log; standard library only. `--cut 10` drops the fade after the signal path is switched off (standard since T2-A; reproduces the T1 sweep values). T4: `--t0 UNIX --from SEC --to SEC` (and `--ref-from`, `--ref-to`) evaluate a window by host time; needs the `.idx` of `ubx_log.py` |
| `./scripts/sim_crpa.sh [dp\|core\|all] [log]` | xsim of `crpa_core` against the model vectors (regenerated first): `crpa_dp_tb` on every case with regular and irregular `adc_valid`, and `crpa_core_tb` (AXI, CDC, muxes, flags) at two `l_clk` rates (about 1 min). Last log: `results/t4_crpa_sim.txt` |
| `vivado -mode batch -source scripts/ooc_crpa.tcl -tclargs <dir>` | Out-of-context synthesis and implementation of `crpa_core`, with utilization, timing and CDC reports (about 1 min) |
| `make -C fw/hdl/library/crpa_core xilinx` | Package the IP (`component.xml`, about 30 s; needs `VIVADO_SETTINGS` sourced). Copies `up_axi.v`, `up_xfer_*.v` and their XDC files into `ip/crpa_core/adi_common/` first, so that the packaged paths work through the link. The project build does this through `LIB_DEPS` |
| `ssh pluto 'sh -s' < scripts/frame_err_test.sh` | Runs on the Pluto: clears `crpa_core` STATUS.FRAME_ERR and watches it at 30.72 and 10 MSPS, across two rate changes; leaves TX_LO powered down (about 30 s; ssh needs the password, so the user runs it) |
| `ssh pluto 'sh -s' < scripts/uio_check.sh` | Runs on the Pluto, read-only: `/opt/VERSIONS`, `/proc/cmdline`, `crpa_core` UIO map and IRQ, VERSION register, ADC/DAC `sampling_frequency` attributes (seconds; the user runs it) |
| `make -C sw/app` / `make -C sw/app test` | Cross-compile `crpa_ctl`; host test of the weight computation against the model (4156 cases, under 5 s) |
| `ssh pluto 'sh -s' < sw/app/dry_test.sh` | `crpa_ctl` dry runs (fixed, PI, polling), refusals, SIGTERM, `off`; no transmission (about 30 s) |
| `ssh pluto 'sh -s' < sw/app/gap_test.sh` | Processes, interrupts over 1 s, and block gaps with normal and real-time scheduling; dry runs only (about 25 s) |
| `.venv/bin/python scripts/t3_phase.py --seq SEQ --label X` | T3: inter-channel level ratio, \|rho\| and phase of R21 = x2 conj(x1) from raw captures over libiio, wideband and in the bins of the carrier near -Delta. RX-only: powers the TX LO down, sets maximum TX attenuation, reads both back at the end. Sequences `one`, `retune`, `rewrite`, `fs`, `delta`, `gain`; `--seq selftest` checks the analysis without a Pluto. Needs the capture mux at reset (after a reboot or `crpa_ctl off`). Logs to `results/t3_<label>_<date>-<time>.txt`. T4 additions: `--cw-offset HZ[,HZ]` and `--cw-span HZ` select the line(s), `--cap y` labels a CAP_SEL capture (y and x1), `--passive` writes nothing to the Pluto (captures during a `crpa_ctl` dry run) |
| `scripts/t4_jammer.py` | T4: CW jammer on the B205mini through the UHD Python API (system Python), conducted use only; Claude Code runs it under the user's go for the run. Dry run without `--on` (device opened and checked, nothing tuned or streamed). `--on` needs `--ext-att DB` (at least 50) and `--max-gain DB`. States: a TX gain or `off`; `--schedule "T:STATE,..."` from t0 (stdin command `t0`, or `--start-now`); stdin commands `t0`, `gain`, `off`, `note`, `status`, `quit`. Quit, end of input, errors and SIGINT/TERM/HUP end with the burst ended and the gain at minimum (`JAMMER OFF`). `--freq` (default L1 + 200 kHz), `--log` |
| `python3 scripts/test_t4_jammer.py` | Tests of `t4_jammer.py` against a stand-in `uhd` module, no B205mini and no RF (about 8 s) |
| `scripts/ubx_log.py OUT.ubx` | Raw u-blox log through `gpspipe -R --nobuffer` with an index `OUT.ubx.idx` of host times, for the `--from` / `--to` windows of `ubx_cn0.py`. Ends on SIGINT/TERM |
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
- [x] Task 6a, fw/linux fork and device tree (2026-11-09, `results/t6a_dt_check.md`): fw/linux is the fork `osqzss/linux`, branch `crpa` on ADI `bf1d49f` (linux `a26ff66`, fw `d8191eb`). FIR flags removed, `crpa_core` UIO node added, of_id appended through `CONFIG_CMDLINE_EXTEND`. On the CRPA unit: `/dev/uio0` named `crpa_core`, map 0x7c450000/0x10000, IRQ GIC 86 level, VERSION 0x00010000; f/8 no longer offered; IIO devices unchanged; `loopback_test.py` 0 fails, `if_check.py` PASS. Firmware flashed was built before the fw commit (`device-fw v0.39-22-g8f9c-dirty`); same content as `d8191eb`
- [x] Task 6b, PS application in dry run (2026-11-09, `results/t6b_dry_run.md`): `sw/app/crpa_ctl` built with our firmware's toolchain; weight math equal to the model in all 4156 test cases. On the CRPA unit without transmission: about 1000 blocks/s through the irq and through polling, fixed [1,0]/[0,1] give y = x1/x2, PI keeps \|w2\| at 0.01-0.03 on noise only, refusals and SIGTERM end in the safe state. Normal scheduling lost 0.5% of blocks to a 1 Hz system task; SCHED_FIFO 40 (now the default) lost none in 15 s. Interactive commands over `ssh -t` all as expected (300 s, PI and fixed, `w [1,1]` +3 dB, `shift` +6 dB); `status` and `rx` drop 1-3 blocks each (SPI in the loop thread). `--on` not yet run
- [x] T2-A (2026-11-09, `results/t2_A.md`): first `crpa_ctl --on` run. Fixed w = [1,0] through crpa_core, RX1 -> TX1, TX1 attenuation 50 dB, settings as T1 A1. C/N0 -2.76 dB against the reference (T1 A1 loopback -2.75 dB), 11 PRNs, 3D fix, AGC 2028, jamming indicator 108; 433483 blocks with no saturation, no frame error and no gap after startup. crpa_core adds no measurable loss
- [x] T2-B (2026-11-09, `results/t2_B.md`): w = [0,1], RX2 -> crpa_core -> TX1, the first RF check of RX2 through the PL. C/N0 -2.94 dB against the reference, 0.18 dB below T2-A on average (largest PRN 0.8 dB), 11 PRNs, 3D fix; no saturation, no frame error, no gap after startup. x2 is 0.4 dB below x1 in level (gain, not SNR). R21 shows the common signal (bladeRF carrier and GPS through the splitter) at 173 deg on RX2 relative to RX1, |rho| about 0.25
- [x] T2-C1 (`results/t2_C1.md`): w = [1,-1], coherent combining. C/N0 -0.96 dB against the reference, +1.80 dB over T2-A (+1.2 to +2.0 per PRN), 11 PRNs; y +3.7 dB over x1. T2-D control (`results/t2_D.md`): y = 2 x1 at TX1 attenuation 52.25 dB, the same TX1 output power, gives the T2-A C/N0 within 0.1 dB. So the 1.8 dB is array gain, and C/N0 does not depend on the TX1 level in this range. AGC differed (1638 vs. 1872) although total y power matched; not resolved
- [x] T2-C2 (`results/t2_C2.md`): w = [1,1], destructive. C/N0 -22.5 dB against the reference (about 19.8 dB below T2-A), 3 SVs tracked, no lasting fix; predicted about 21 dB from the measured amplitude ratio and phase. **T2 complete**: each path received ([1,0], [0,1]), 1.8 dB array gain in phase, a 20 dB null in antiphase
- [x] T3 (2026-11-10, `results/t3.md`, `docs/t3_plan.md`): inter-channel phase and amplitude from raw captures with `scripts/t3_phase.py`, RX-only, bladeRF through the splitter. T2 cabling: phase of x2 against x1 172.4 to 173.6 deg over the day, x2 0.3 dB lower; spread within a run 0.15 deg. No change on 30 retunes (2400 MHz and back: +0.35 deg when captured 0.5 s after), 30 LO rewrites or 10 rate changes. PL R21 from a `crpa_ctl` dry run agrees with the host within 0.15 deg and 0.015 dB. Three power cycles: 173.25 deg +/- 0.03 and -0.30 dB, flat for 30 min from boot (29 to 33 C). Delta +2 to -3 MHz: about 1 deg. RX gain 40 to 70 dB: carrier phase 174.4 to 172.6 deg. RX gain writes raise the RX1 level at 60 dB by up to 0.3 dB (phase +0.4 deg) until a power cycle. Legs swapped: 43.9 deg, so the phase is the sum of a fixture part of 64.7 deg (or -115.3 deg) and a Pluto part of 108.6 deg (or -71.4 deg); the antiphase seen in T2 belongs to that cabling, not to the unit. Cables put back: 172.5 deg, 0.7 deg from before the swap, amplitude unchanged (connector repeatability)
- [x] RX-only GPS check and unit comparison (`results/t1_rx_unit_compare.md`, 2026-11-07). The first Pluto has 12-14 dB excess noise and bursts on RX2. The second Pluto (serial `1044734c96050011f2ff2100408f4f2ac3`, same firmware) has matched channels, and all 11 simulated PRNs at -Delta on both, within 0.5 dB in SNR. The user confirmed the second Pluto as the CRPA unit (2026-11-07)

### 10.2 Open items
- [ ] LO leakage and image levels not measured (effect on the receiver only, `results/t1_sweep.md`); a measurement with the B205mini on TX1 and a Pluto RX FFT is optional
- [ ] RX2 end to end: RX2 -> TX1 does not exist with `data_sel = 8`. RX2 is checked RX-only at T1 and through `crpa_core` at T2 (`docs/interface.md`, Section 4)
- [ ] First Pluto (serial `1044734c960500110c000900418f4f7ca2`) RX2 fault: location not found (chip, board or RX2 connection). It likely explains the 8 dB difference seen in the dry run on 2026-11-05, which was on this unit
- [ ] Second Pluto: about 3 dB higher ch0/1 noise floor at low gain, seen again at T3 (wideband ratio -3.2 dB at 40-45 dB, `results/t3.md`); not investigated
- [ ] T3 leftovers (`results/t3.md`): 180 deg ambiguity of the Pluto / fixture split (needs a third measurement with a known change in one leg; only for calibration); RX1 level at 60 dB rises up to 0.3 dB with RX gain writes, mechanism not identified (set the gain once after boot for comparable runs); 0.7 deg rise within T3-H and 172.4 deg in the first boot not explained; correlated part without a source, |rho| 0.002 to 0.007
- [ ] bladeRF carrier after `bladegps` exits: on 2026-11-10 no carrier line was left after stopping with `q` (`results/t3.md`), unlike 2026-11-07. Not followed up
- [ ] bladeRF carrier at L1 stays after `bladegps` exits, and is also present while it runs. Effect on the C/N0 reference and the T1 result not evaluated. Whether TX is left enabled not determined
- [ ] Output normalization: `OUT_SHIFT` in the PL and TX attenuation from the PS are the current design; decide at T2 whether a PL gain multiplier is needed
- [ ] T4 setup: in the T1/T2 cabling the bladeRF carrier and the satellites reach RX1 and RX2 with the same relative phase, so power inversion would null the satellites with the jammer. Recommendation recorded in Section 11 (T4): separate CW source (B205mini) through a second splitter and one combiner per leg, phase separation set by cable length and measured per source with `scripts/t3_phase.py`; no two-element simulator for T4. Detailed plan written 2026-11-10: `docs/t4_plan.md` (jammer at L1 + 200 kHz, ladder J/N -10 to 30 dB, three cabling variants, per variant one RX-only null run, one fixed and one PI receiver run). Decided by the user the same day; tools written and tested offline (`scripts/t4_jammer.py`, `scripts/ubx_log.py`, extensions of `t3_phase.py` and `ubx_cn0.py`); hardware checks of P0 done (`docs/t4_plan.md`, Section 4.5); P1 to P3 done for V1, RX-only (jammer ladder calibrated; D only 2.9 deg in V1). Variant V3 (jammer leg to RX1 50 cm instead of 25 cm): D 100.0 deg; V3-N (null depth 18.9 / 38.1 / 57.1 dB at L3 to L5, equal to the model) and V3-F (fixed weights: fix lost at J/N 30 dB) done on 2026-11-10 (`results/t4.md`). V3-P done on 2026-11-11 after a P3 repeat (D 100.2 deg): with PI a 3D fix with 11 SVs at every jammer level, cold start under J/N 30 dB with TTFF 28.8 s, C/N0 +0.7 / +0.6 / +0.3 dB at L5 / L4 / L3 against the fixed-weight reference with the jammer off (prediction +0.4 dB), -0.9 dB with the jammer off. Still to do: the parameter runs, a V1 null run, further D values; open points listed in `docs/t4_plan.md`, Section 6
- [ ] Two-element GPS and jammer simulator (per-satellite and per-jammer phase on two coherent TX channels): not needed for T4; consider for T5 and later. Needs a 2-TX coherent generator (not the bladeRF x40; whether the first Pluto's TX side is usable is not checked) and a modified gps-sdr-sim
- [ ] Diagonal loading and smoothing: starting values from simulation (load 0.1 x noise power, alpha 0), to be confirmed at T4. V3-N with load 24 and alpha 0 reaches the model null depth (2026-11-10), and V3-P with the same values holds the receiver at the predicted C/N0 from J/N 10 to 30 dB and loses 0.9 dB with the jammer off (2026-11-11); the load and alpha runs (V1-L, V1-A in the T4 plan) are still to do
- [x] UIO vs. `/dev/mem`; interrupt vs. polling: decided 2026-11-09, UIO with the interrupt, polling as a fallback (Section 7). The UIO side is in place (Task 6a); the application is Task 6b
- [ ] FRAME_ERR at rate changes (`results/t5_hw_check.md`): the number of affected samples, and whether ENSM changes also set it, are not known. The PS must soft-reset and clear STATUS after a rate change and treat FRAME_ERR at a fixed rate as an error (Task 6)
- [ ] Target receiver input level and external attenuation
- [ ] COTS GNSS receiver to use and how to read C/N0 (NMEA/UBX)
- [ ] Extent of RTL reuse for the future multi-element CRPA
- [x] PS sysroot: the Buildroot toolchain wrapper in `fw/buildroot/output/host/bin/` uses `output/staging` itself; `make -C sw/app` (setup guide Section 9.7). Task 6b

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
Status: **6a done** (2026-11-09, `results/t6a_dt_check.md`). **6b in progress**: `crpa_ctl` written and tested in dry run (`results/t6b_dry_run.md`). Interactive commands done; the first `--on` run (T2-A) passed. **Task 6 done**; T2 continues: [1,0] and [0,1] done (T2-A, T2-B), [1,-1] (T2-C1), the level control T2-D and [1,1] (T2-C2) done: **T2 complete**. Next: T3 (inter-channel amplitude and phase per retune) and the T4 jammer setup (Section 10.2).

### T3: inter-channel amplitude and phase
Status: **done** (2026-11-10). Plan: `docs/t3_plan.md`, results: `results/t3.md`, tool: `scripts/t3_phase.py` (RX-only, libiio). Next: the T4 jammer setup (Section 10.2).

### T4: conducted CW jammer, setup recommendation
Status: **in progress**; P0 to P3 done, V3 complete (N, F, P; 2026-11-11). Detailed plan: `docs/t4_plan.md` (levels, tools, runs, pass criteria, safety for the second transmitter); the user's decisions are in its Section 9 (Claude Code runs the jammer under the per-run go; bladeGPS gain unchanged; levels stepped inside a run; 30 + 30 dB; L1 + 200 kHz). Hardware checks of its Section 4.5 (2026-11-10): the jammer dry run on the B205mini passes (TX gain 0 to 89.75 dB, antenna `TX/RX`); a raw capture during a `crpa_ctl` dry run works, with no path or frame error, but each capture drops 15 to 27 single blocks, so captures are used only in the RX-only null runs. P1 done (2026-11-10, V1, RX-only; `docs/t4_plan.md`, status): noise -42.5 / -42.8 dBFS, GPS path phi_G 166.5 deg, |rho| 0.174, no residual bladeRF carrier, idle B205mini silent. P2 and P3 done for V1 (`docs/t4_plan.md`, Section 2.2): gains 35 / 45 / 55 / 65 / 75 dB give J/N -9.2 / 0.6 / 10.8 / 20.9 / 30.5 dB through 30 + 30 dB, no residual line after the jammer stops; D is 2.9 deg in V1, so PI would null the satellites with the jammer (about -27 dB predicted). With the jammer leg to RX1 changed from 25 cm to 50 cm (variant V3) D is 100.0 deg, predicted C/N0 change with PI +0.4 dB. V3-N done (`results/t4.md`): null depth 18.9 / 38.1 / 57.1 dB at J/N 10.1 / 20.0 / 29.6 dB, equal to the model values, weights as PI predicts, no saturation or frame error. V3-F done: w = [1,0], reference -5.1 dB against T1, C/N0 loss 0.4 / 0.9 / 4.0 / 9.9 dB at L1 to L4, fix lost at L5 (J/N 30 dB), full recovery after the jammer; no saturation or frame error. V3-P done (2026-11-11, `results/t4.md`; P3 repeated first, D 100.2 deg): PI with load 24, cold start under L5 with TTFF 28.8 s, 3D fix with 11 SVs at every level, C/N0 +0.7 / +0.6 / +0.3 / -0.2 dB at L5 to L2 against the V3-F reference (prediction +0.4 dB), -0.9 dB with the jammer off; output level constant at -38.9 dBFS from L3 to L5; no saturation or frame error. Decided 2026-11-11: null depth criterion "within 3 dB of the model value" (V3-N passes); parameter runs in V3. **Next: V3-L and V3-A (load, alpha, block length), then V1-N and further D values**; state of the session, the run procedure as executed and the open points are in `docs/t4_plan.md`, Section 6. The setup and its reasons follow.

No two-element GPS simulator is needed for T4. Power inversion only needs the jammer to reach the two channels with a different inter-channel phase than the satellites, and that can be cabled with the parts at hand (user, 2026-11-10: four 2-way splitter/combiners, which work in both directions, and several 20 dB and 30 dB attenuators besides the ones in use).

```
bladeRF (bladeGPS) -> 40 dB -> SPL1 -+-> CMB1 -> Pluto RX1
                                     +-> CMB2 -> Pluto RX2
B205mini (CW) -> attenuators -> SPL2 -+-> CMB1
                                      +-> CMB2   (other cable length, or legs crossed)
Pluto TX1 -> DC block -> u-blox M8T, TX attenuation 50 dB in the Pluto (as T2)
```

- **GPS path:** as T2 and T3, with one combiner added in each leg. All satellites and the bladeRF carrier keep one common inter-channel phase, as if from one direction.
- **Jammer path:** a separate source, the B205mini (UHD), as a CW inside the C/A main lobe but not on the bladeRF carrier at L1. A separate source keeps the full DAC range for the jammer; a jammer 40 to 60 dB above GPS in the same 12-bit DAC would leave GPS near 1 LSB.
- **Phase separation:** D = (jammer phase of x2 against x1) - (GPS phase of x2 against x1). Set it by the cable lengths of the two jammer legs, or by crossing them. T3-G: about 2.3 cm of coax is 65 deg at L1. Do not assume D: measure each source alone, RX-only, with `scripts/t3_phase.py` (GPS on and jammer off, then the reverse), and record it for every cabling.
- **Expected effect of D** (equal amplitudes, ideal null on the jammer): the satellite SNR against a single element is 20 log10(2 |sin(D/2)|) - 3 dB: +3 dB at 180 deg, 0 dB at 90 deg, -3 dB at 60 deg, -8.7 dB at 30 deg, and the satellites are nulled with the jammer at 0 deg. With one common satellite phase, C/N0 recovery depends on D alone, so run two or three separations (for example near 180, 90 and 30 to 45 deg) and report C/N0 against D.
- **Level budget:** each combiner takes about 3.5 dB from the GPS path, so C/N0 will be lower than in T2 by about that much. Take a new reference in the T4 cabling with the jammer off and fixed weights [1,0]; do not compare with the T2 numbers directly. (Alternative, to be decided: raise the bladeGPS TX gain.) At RX gain 60 dB the noise is at -42.5 dBFS, so the jammer can be about 30 dB above the noise in 9 MHz before the ADC margin gets small, i.e. J/S of roughly 55 dB for a 45 dB-Hz signal; more needs a lower RX gain. Estimates only; confirm RX-only before any Pluto transmission.
- **Jammer level procedure:** the B205mini output level is not calibrated here. Start with at least 60 dB of attenuators (30 + 30) and the lowest TX gain, read the jammer level at the Pluto with `t3_phase.py` (RX-only), and step up from below the noise.
- **Reference runs must use fixed weights, not PI:** with the jammer off, power inversion sees the bladeRF carrier and the satellites as the strongest common signal and would null them (`results/t2_B.md`). Jammer-off reference: w = [1,0]. Jammer-on comparison: w = [1,0] against `--mode pi`. The jammer must be clearly stronger than the bladeRF carrier for the null to go to the jammer.
- **Isolation:** every device is a 2-way splitter, so no port is left open. Leakage of the jammer into the other leg goes through two isolations (CMB and SPL1, typically about 20 dB each; not measured) and is small against the direct path. Check with one jammer leg terminated if the measured D looks wrong.
- **Safety:** the B205mini is a second transmitter. Conducted only, never radiated (Section 8.2); the rules of `docs/test-equipment.md`, Section 2 apply, with the user's go before each run. The T4 plan must add how the jammer is stopped on exit and on errors.
- **Limits of this setup:** all satellites behave alike, there is one jammer, and nothing moves. A two-element simulator (two coherent TX channels with a phase per satellite and per jammer) would give a realistic sky, a jammer direction sweep, a moving jammer and two jammers. It needs a 2-TX coherent generator, which the bladeRF x40 is not, and a modified gps-sdr-sim. Kept as a separate item for T5 and later (Section 10.2).

---

## 12. Rules for Claude Code

- HDL is **Verilog** (Verilog-2001, minimal SystemVerilog). Every module gets a testbench.
- **All scripts, source code, comments and commit messages are ASCII English.**
- Shell scripts use `set -euo pipefail`; wrap sourcing of external scripts such as Vivado `settings64.sh` in `set +u` / `set -u`.
- Never modify ADI library IP (`fw/hdl/library/`). ADI-side changes are limited to project files such as `fw/hdl/projects/pluto/` and are committed on the `crpa` branch.
- Edit the custom IP only in `ip/crpa_core/` (`fw/hdl/library/crpa_core` is a link).
- Commit order for submodules: `fw/hdl` and `fw/linux` -> `fw` -> parent. Push each to its fork before updating the reference above it.
- Kernel and device tree changes are commits on the fw/linux `crpa` branch; export them with `git format-patch` into `sw/dts/`. Do not change u-boot or its environment without asking the user.
- Never force-push (`git push -f`) without the user's confirmation.
- RTL changes must pass the bit-exact comparison with the Python model before commit.
- Build with `scripts/build_hdl.sh`; keep reports in `results/hdl/` and compare utilization and WNS with the previous build.
- After upstream updates or environment changes, append a snapshot with `scripts/record_env.sh`.
- Document fixed-point widths, rounding and saturation in code comments and in `docs/`.
- Always record hardware settings (LO, fs, gains, attenuation) in measurement logs.
- Do not implement from guesses about ADI IP ports or behavior; confirm in the source or with ILA first.
- Ask the user before long-running operations (`git submodule update --init --recursive`, full firmware build, HDL builds).
- Update Section 10 and Section 11 of this file at the end of each work session.
