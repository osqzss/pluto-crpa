# axi_ad9361 Data Interface (CMOS, 2R2T)

What `crpa_core` connects to. hdl `387ca1761`, Linux `bf1d49f17fa9`, Pluto project settings: `CMOS_OR_LVDS_N = 1`, `MODE_1R1T = 0`, `ADC_INIT_DELAY = 21`, `axi_ad9361/l_clk` tied to `axi_ad9361/clk`.

How far each fact has been checked:

- **Source**: read from the hdl or driver source.
- **Sim**: measured on the unmodified core with `scripts/sim_ad9361_if.sh` (`ip/crpa_core/tb/ad9361_if_tb.v`, log `results/t2_if_sim.txt`). All checks pass for both rx frame alignments. The AD9361 side of that testbench is a model written from the HDL and the driver settings, so it shows what the core does with such a port, not that the chip drives it that way.
- **Hardware**: T0b digital loopback (`results/t0b_hw_test.md`) and `scripts/if_check.py` (`results/t2_if_check.txt`, all checks pass).

## 1. Summary for crpa_core

| Item | Fact | Checked |
|---|---|---|
| Clock | `l_clk` = 2 x fs in 2R2T, for every fs. There are always exactly **2 l_clk cycles per sample**, even at low fs | Source, Sim (valid period), Hardware (2.000 at 3, 10 and 30.72 MSPS) |
| Valid | `adc_valid_*` and `dac_valid_*`: one cycle high, one cycle low. All four streams coincide | Sim |
| RX format | 12-bit two's complement, **sign-extended, LSB-aligned** in 16 bits: range -2048 to +2047 | Source, Sim, Hardware |
| TX format | 12-bit two's complement, **MSB-aligned**: the core uses `dac_data_*[15:4]` and **truncates** `[3:0]` | Source, Sim, Hardware |
| RX1/RX2 alignment | One `adc_valid` delivers I0, Q0, I1, Q1 of the same sample | Sim, Hardware |
| Data path | Not gated by `adc_enable_*`; independent of DMA and of libiio buffers | Source |
| TX select | `crpa_core` reaches the DAC only when the TX channels have `data_sel = 2`. **The driver default is DDS (0), so the PS must set it** (Section 5) | Source |

## 2. Ports

All on `l_clk`, in `library/axi_ad9361/axi_ad9361.v`. `rst` is the ADC core reset (`up_adc_common`), active high.

| Port | Dir (from axi_ad9361) | Width | Meaning |
|---|---|---|---|
| `l_clk` | out | 1 | `rx_clk_in` through IBUFG and BUFG (`ad_data_clk`). No MMCM. Constrained as `rx_clk`, 16.27 ns |
| `clk` | in | 1 | Tied to `l_clk` by the project |
| `rst` | out | 1 | Released when the driver writes RSTN (0x0040) |
| `adc_valid_i0/q0/i1/q1` | out | 1 | Sample strobe. The project uses `adc_valid_i0` |
| `adc_data_i0/q0/i1/q1` | out | 16 | Valid while the strobe is high |
| `adc_enable_i0/q0/i1/q1` | out | 1 | Channel enable for cpack. Follows the libiio scan mask |
| `dac_valid_i0/q0/i1/q1` | out | 1 | Sample request |
| `dac_data_i0/q0/i1/q1` | in | 16 | See Section 4 |
| `dac_enable_i0/q0/i1/q1` | out | 1 | High when the channel has `data_sel = 2` |
| `adc_dovf`, `dac_dunf` | in | 1 | Status only, for cpack overflow and upack underflow |
| `adc_r1_mode`, `dac_r1_mode` | out | 1 | 0 in 2R2T |

Streams: `i0/q0` = channel index 0/1 and `i1/q1` = channel index 2/3, on both RX and TX. Which SMA or u.FL connector each one is has not been checked (Section 7).

## 3. Receive path

**Rate.** `ad9361_validate_trx_clock_chain` in `drivers/iio/adc/ad9361.c` computes `data_clk = (rx2tx2 ? 4 : 2) / (lvds ? 1 : 2) * fs`, which is 2 x fs for CMOS 2R2T, limited to 61.44 MHz. So 10 MSPS gives `l_clk` = 20 MHz and 30.72 MSPS gives 61.44 MHz.

**Port.** The AD9361 sends I0, Q0, I1, Q1 as 12-bit DDR words. In pulse mode (`adi,rx-frame-pulse-mode-enable`) the frame is high for I0 Q0 and low for I1 Q1. `axi_ad9361_cmos_if` accepts two alignments of the frame to the clock:

| Alignment | `rx_frame_s` (rising, falling) | I0 captured on | I0 to `adc_valid_i0` |
|---|---|---|---|
| `FRAME_ALIGN = 0` | 11, 00 | falling edge | 14 l_clk |
| `FRAME_ALIGN = 1` | 01, 10 | rising edge | 15 l_clk |

The two alignments behave the same except for that 1 cycle of latency. Which one the chip uses does not matter to `crpa_core`.

**Bit format.** `ad_datafmt` with `DATA_WIDTH = 12` fills `[15:12]` with the sign only when `dfmt_enable` and `dfmt_se` are set; otherwise they are 0. Those bits reset to 0 and the driver sets them in `ad9361_post_setup`, together with unity IQ correction (`ADI_REG_CHAN_CNTRL_2` = 0x40000000 on I, 0x00004000 on Q). With those values the output equals the sign-extended input exactly (Sim). The IIO scan type agrees: S12 in 16 bits, shift 0 (`AIM_CHAN(.., 12, 'S')`).

**Hold between strobes.** With the DC filter off the data also holds through the non-valid cycle (Sim). Do not depend on this: `ad_dcfilter` stops holding once `dcfilt_enb` is set, as its output then follows a running offset. Load on the strobe only.

**Not gated.** `adc_enable_*` is only an output of the channel. Opening or closing a libiio RX buffer changes it (`cf_axi_adc_core.c`, update_scan_mode) but does not affect `adc_valid_*` or `adc_data_*`, so `crpa_core` must ignore it.

**Frame not toggling (hazard).** In 2R2T the delineation logic treats a frame stuck low as a valid sample on every cycle, and a frame stuck high as no valid at all (Sim: 100/100 and 0/100 cycles). Bit 0 of reg 0x005C (`adc_status`) drops in both cases. On the real chip, a sample rate change does produce it: `crpa_core` STATUS.FRAME_ERR was set by every rate change and stayed clear at a fixed rate (`results/t5_hw_check.md`, Section 3). Whether non-FDD ENSM states do too is not known; the Pluto stays in FDD in this project.

## 4. Transmit path

**Strobes.** `dac_rate_cnt` reloads from reg 0x404C. The driver writes 1 in CMOS 2R2T (`ad9361_conv.c`), giving a period of 2 `l_clk`.

**The read cycle is not the strobe cycle.** The core reads `dac_data_*` in the cycle after a `dac_valid_i0` pulse (read cycle minus strobe cycle = 1 modulo 2, Sim). From the source, the read comes from the internal strobe that reaches the `dac_valid_i0` port 3 cycles later, so a `crpa_core` must not treat the port strobe as "sample taken now". All four streams are read in the same cycle. This suits `util_upack2`, whose output changes in the cycle after `fifo_rd_en`.

**Rule for `crpa_core`:** update all four outputs together from one register, at most once per 2 cycles, and hold them between updates. Then each output sample is read exactly once whatever the strobe phase is.

**Bit format.** `dac_data_out_int <= dma_data[15:4]`: truncation, no rounding, no saturation. The low nibble never reaches the pins (Sim). A truncating `crpa_core` output would add a DC offset of -0.5 LSB, which is a small tone at the LO after upconversion, so **round in `crpa_core` to 12 bits, saturate, then shift left by 4**.

**Pins.** I0 Q0 with frame high, I1 Q1 with frame low (Sim).

**ADC/DAC strobe phase.** Same clock, same period, but the phase depends on history: before any sync the two strobes were in opposite cycles in simulation, and after a sync they coincide. `ADI_SYNC` (bit 0 of 0x4044) gates the rate counter with `adc_valid`. The driver issues it in `cf_axi_dds_start_sync`. With the hold rule above, either phase works and only the latency changes, by 1 `l_clk`. To get a repeatable latency, have the PS write the sync bit once after setting up.

**Internal loopback (`data_sel = 8`).** The TX channel has a built-in path from the raw ADC data (`DATA_SEL_LB`). The driver sets it with debugfs `loopback` = 2 (`iio_attr -D ad9361-phy loopback 2`; `ad9361_hdl_loopback`), and `loopback` = 0 restores the previous `data_sel`. With `data_sel = 8` on all TX channels, RX ch0/1 reach TX ch0/1 with no sample lost, and after a sync TX ch2/3 are all zero (Sim). It bypasses the RX format and IQ stages. So **an RX1 -> TX1 pass-through exists in the current firmware, without `crpa_core`**. This allows T1 before Task 5, so the DAC mux of plan Section 6.2 has no pass-through setting.

**RX2 with `data_sel = 8`.** Each TX channel only takes the ADC data of its own index (`axi_ad9361_tx.v`), so **RX2 -> TX1 does not exist**. RX2 -> TX2 depends on the strobe phase, because `axi_ad9361_cmos_if` drives `adc_data[47:24]` to zero in the non-valid cycle. After a sync TX ch2/3 read that zero. With the sync removed from a copy of the testbench, the strobes stay opposite and TX ch2/3 carry RX ch2/3 in 199 of 199 frames, with RX1 -> TX1 still correct (Sim, `results/t1_rx2_nosync_sim.txt`; its one FAIL per alignment is the after-sync phase check, expected without a sync). No way to get that phase on hardware has been confirmed, so do not rely on it. RX2 reaches TX1 through `crpa_core` with weights `[0,1]`.

## 5. Driver behavior the PS application must handle

| Situation | Effect on TX `data_sel` | Source |
|---|---|---|
| Boot | 0 (DDS), with `adi,axi-dds-default-scale = <0>`, so TX outputs zeros | `cf_axi_dds.c`, probe |
| libiio TX buffer opened | 2 for channels in the scan mask, 0 for the others | `cf_axi_dds_update_scan_mode` |
| libiio TX buffer closed | 0 for all | `dds_buffer_state_set` |
| DDS `raw` attribute written | 0 or 3 for all | `cf_axi_dds.c` |
| Sample rate written through the DDS device | Preserved | `cf_axi_dds.c`, write_raw |
| Sample rate written through `ad9361-phy` | Not changed: with this device tree (`adi,digital-interface-tune-fir-disable` set, `bb_clk_change_dig_tune_en` unset) the rate change runs no tune. `if_check.py` read it unchanged across three rates | `ad9361_set_trx_clock_chain` |
| Digital interface tune (boot, debugfs) | 9 during the tune, then restored. The tune also resets the ADC core, so `rst` pulses | `ad9361_dig_tune_tx`, `ad9361_dig_tune` |

So the application must write `data_sel = 2` at startup and again after any of the above. `crpa_core` cannot do it from the PL. Any host tool that opens and closes a TX buffer (`scripts/loopback_test.py`, for example) silently disconnects `crpa_core` from the DAC.

Other points:

- A powered-down TX LO is not strictly silent. `adi,tx-lo-powerdown-managed-enable` is set on Pluto, so `ad9361_tx_quad_calib` powers the TX LO up for the calibration and then restores it. It runs on every `rf_bandwidth` write and, in auto mode, on a TX retune of more than 100 MHz from the last calibrated frequency (`ad9361.c`, source only, not measured at the port). So any tool that writes bandwidth with the TX LO "down" (`scripts/gps_rx_check.py`, for example) can emit briefly at the current TX LO frequency. The `powerdown` attribute reads the driver's cached state, not the chip.
- With the DAC mux on `crpa_core` and no TX DMA running, upack keeps reading and underflows. This only sets a sticky status bit.
- Core registers through debugfs or `iio_reg` need the magic bit: `0x80000000 | offset` on `cf-ad9361-lpc`. Without it the access goes to AD9361 SPI registers (`axiadc_reg_access`).

| Register (byte offset from 0x79020000) | Use |
|---|---|
| 0x0044 bit 2 | ADC r1_mode |
| 0x0054 | `l_clk` cycles per 65536 `s_axi_aclk` cycles: `l_clk` = value x 100 MHz / 65536. Reads about 0.06% low in simulation; cause not traced |
| 0x005C bit 0 | `adc_status`: frame toggling and delay locked |
| 0x0400 + 0x40 x ch | ADC channel control: bit 9 IQCOR, bit 8 DCFILT, bit 6 SIGNEXT, bit 4 FORMAT, bit 0 ENABLE |
| 0x0414 + 0x40 x ch | ADC IQ correction coefficients |
| 0x4044 bit 0 | DAC sync |
| 0x4048 bit 5 | DAC r1_mode |
| 0x404C | DAC rate (1 in 2R2T) |
| 0x4418 + 0x40 x ch | DAC `data_sel`: 0 DDS, 2 DMA (and `crpa_core`), 3 zero, 8 ADC loopback, 9 PN |

## 6. Latency in the PL

In `l_clk` cycles, 20 MHz at fs = 10 MSPS (50 ns per cycle). Sim, except as noted.

| Segment | Cycles |
|---|---|
| I0 captured to `adc_valid_i0` | 14 or 15 |
| `crpa_core` | L, including up to 1 cycle of wait for the read cycle |
| `dac_data_*` read to Q1 on the pins | 11 |
| **Total, I0 in to Q1 out** | **25 or 26 + L** |
| Same with `data_sel = 8` (no `crpa_core`) | 14 or 15 |

At 10 MSPS, 25 cycles is 1.25 us. This excludes the AD9363 digital filters and analog paths, which have not been measured. Plan Section 8.3 still needs the end-to-end value.

## 7. What is still unverified

| Item | How to check | When |
|---|---|---|
| Which connector is `i0/q0` and which is `i1/q1`, on RX and TX | CW into one RX port; look at which stream carries it | T1, T2 |
| I/Q order at RF (spectrum not mirrored). T0b loopback cannot show it because TX and RX mirrors cancel | CW at LO + f must appear at +f in a capture | T1 |
| Frame behavior outside steady FDD. Rate change: two consecutive valids occur, seen by FRAME_ERR (`results/t5_hw_check.md`); handled by the soft reset after a rate change. Not known: ENSM changes, number of affected samples | STATUS.FRAME_ERR first; ILA below only if it turns out to matter | If needed |

**ILA plan.** The source is not ambiguous about the data path, so no ILA capture is needed for Tasks 3-5. If the output misbehaves in T1/T2 and `scripts/if_check.py` does not explain it, add an ILA on `l_clk` to `system_bd.tcl`:

- Probes: `adc_valid_i0`, `dac_valid_i0`, `adc_data_i0/q0/i1/q1`, `dac_data_i0/q0`, `axi_ad9361/rst`.
- Depth: 1024 samples, trigger on `adc_valid_i0` and its previous value both high, which never happens in normal 2R2T operation.
- Run during an `ensm_mode` change and a `sampling_frequency` write.
- This needs an HDL build, a flash and JTAG (30-60 min for the build); the JTAG setup on this host is not confirmed.

## 8. Requirements on crpa_core

1. Datapath on `l_clk`, with reset from `axi_ad9361/rst`.
2. Load all four inputs on `adc_valid_i0`. Ignore `adc_enable_*`.
3. Budget 2 cycles per sample. "`l_clk` much faster than fs" does not hold: time-sharing a multiplier allows at most 2 uses per sample. It is also unnecessary: about 16 DSP48 unshared (8 for two complex multiplies, 8 for R11, R22, R21), against 52 free.
4. Input is S12: |x|^2 needs 24 bits unsigned, and the 48-bit accumulators have plenty of margin.
5. Output: round to 12 bits, saturate, shift left by 4; hold between updates; update all four streams together.
6. Drive TX ch2/3 with zero, or have the PS set them to `data_sel = 3`.
7. Keep the DAC mux on DMA after reset, so that normal Pluto operation is unaffected.
8. Expect `l_clk` to change or stop during a rate change, since there is no MMCM. `up_xfer_*` must recover, and the PS should soft-reset `crpa_core` after a rate change.
9. Add a sticky status bit for two consecutive `adc_valid_i0` cycles, to catch the frame hazard of Section 3 cheaply. Without it, the failure would look like a wrong covariance.
10. 2R2T only. In 1R1T (from source, not simulated), `l_clk` = fs, valid is high on every cycle and ch2/3 read zero. The PS should refuse to start unless reg 0x0044 bit 2 is 0.
