# crpa_core Register Map

IP version 1.0 (`VERSION` = 0x00010000). Source: `ip/crpa_core/rtl/crpa_core.v`. AXI-Lite, 32-bit registers, 64 KB address window, base address set in the block design (Task 5). Fixed-point formats: `docs/fixed_point.md`. Interface: `docs/interface.md`.

All registers are on `s_axi_aclk`. Control values reach the datapath on `l_clk` through `up_xfer_cntrl`, which sends every 64 `s_axi_aclk` cycles: under about 1.5 us. Status from the datapath (W_BUSY, FRAME_ERR, RES_DROP) comes back through `up_xfer_status`, which sends every 64 `l_clk` cycles, so a change can take up to about 2 x 64 `l_clk` cycles to show: about 7 us at 10 MSPS (`l_clk` 20 MHz), about 30 us at 2.084 MSPS. Block results use their own handshake and arrive within a few cycles of each clock. A register read back shows the up-domain value, not whether it has reached the datapath yet. Only W_BUSY tracks arrival, and only for weight updates.

## Summary

| Offset | Name | Access | Reset | Description |
|---|---|---|---|---|
| 0x00 | VERSION | RO | 0x00010000 | IP version, {major[31:16], minor[15:8], patch[7:0]} |
| 0x04 | ID | RO | `ID` parameter | Instance number |
| 0x08 | SCRATCH | RW | 0 | Bus test |
| 0x0C | CTRL | RW | 0 | Control bits, below |
| 0x10 | STATUS | RW | 0 | Status and flags, below |
| 0x14 | INT_LEN | RW | 10000 | Integration length N, [23:0], 1..2^24 - 1. A write of 0 is stored as 1 |
| 0x18 | W1 | RW | 0x00007FFF | Weight 1, {q[31:16], i[15:0]}, Q1.15. Staged; applied by UPDATE |
| 0x1C | W2 | RW | 0 | Weight 2, same format |
| 0x20 | OUT_SHIFT | RW | 0 | [3:0] s = 0..15, output gain 2^s. Staged; applied by UPDATE |
| 0x24 | UPDATE | WO | - | Any write commits W1, W2 and OUT_SHIFT together. Reads 0 |
| 0x28 | MISSED | RW | 0 | Blocks dropped because DONE was still set. Any write clears it |
| 0x40 | R11_LO | RO | 0 | R11[31:0] |
| 0x44 | R11_HI | RO | 0 | R11[47:32], sign-extended to 32 bits |
| 0x48 | R22_LO | RO | 0 | R22[31:0] |
| 0x4C | R22_HI | RO | 0 | R22[47:32], sign-extended |
| 0x50 | R21RE_LO | RO | 0 | Re(R21)[31:0] |
| 0x54 | R21RE_HI | RO | 0 | Re(R21)[47:32], sign-extended |
| 0x58 | R21IM_LO | RO | 0 | Im(R21)[31:0] |
| 0x5C | R21IM_HI | RO | 0 | Im(R21)[47:32], sign-extended |
| 0x60 | SAT_CNT | RO | 0 | [23:0] samples in the block with output saturation (I or Q) |
| 0x64 | PEAK | RO | 0 | [27:16] peak2, [11:0] peak1: max over the block of max(\|xi\|, \|xq\|) per element, 0..2048 |
| 0x68 | SEQ | RO | 0 | [15:0] block number since COV_EN was set (wraps at 2^16) |

Offsets not listed read 0 and ignore writes.

## CTRL (0x0C)

| Bit | Name | Reset | Description |
|---|---|---|---|
| 0 | SOFT_RST | 0 | 1 holds the datapath pipeline, block counter, accumulators and sticky flags in reset. The weights in use are kept. Pulse it after a sample rate change (`docs/interface.md`, Section 8, item 8) |
| 1 | COV_EN | 0 | 1: consecutive blocks of INT_LEN samples run back to back. Setting it starts block 0 at the next sample. 0 stops and resets the block count and SEQ |
| 2 | DAC_SEL | 0 | DAC mux. 0: `dma_dac_data_*` from upack pass through (normal Pluto). 1: TX ch0/1 = y << 4, TX ch2/3 = 0. Takes effect only with TX `data_sel = 2` (set by the PS) |
| 3 | CAP_SEL | 0 | Capture mux to cpack. 0: raw ADC data. 1: ch0/1 = y, ch2/3 = x1 of the same sample, each S12 sign-extended to 16 bits |

The reset value 0 leaves the Pluto working as before: DMA to the DAC, and raw ADC data to the capture DMA.

## STATUS (0x10)

| Bit | Name | Access | Description |
|---|---|---|---|
| 0 | DONE | R/W1C | A block result is held in 0x40-0x68. While DONE is set the result registers do not change, and further blocks are dropped and counted in MISSED. Write 1 to clear. Also drives the `irq` output (level, high while set) |
| 1 | W_BUSY | RO | An UPDATE has not yet been applied in the datapath |
| 2 | FRAME_ERR | RO, sticky | `adc_valid` was seen high in two consecutive `l_clk` cycles (the frame hazard of `docs/interface.md`, Section 3). Set by every sample rate change on hardware, and after boot; clear at a fixed rate (`results/t5_hw_check.md`). Clear it after a rate change (PS sequence, step 4) |
| 3 | RES_DROP | RO, sticky | A block ended while the previous result was still crossing to the AXI side, so it was lost before reaching DONE. Expected only for very short INT_LEN |

Writing 1 to bit 2 or bit 3 clears both FRAME_ERR and RES_DROP. The clear takes effect in the datapath, so the bits read 0 only after the status delay above (about 7 us at 10 MSPS). Bit 0 and bits 2-3 can be cleared in the same write.

## Weights and output shift

- W1, W2 and OUT_SHIFT are staged. A write to UPDATE copies all three to the committed set, and the datapath applies that set from one sample on. All three change on the same sample.
- W_BUSY is set from the UPDATE write until the set is applied. Wait for W_BUSY = 0 before relying on the new output. A second UPDATE before the first is applied replaces it. Only the newest set is applied.
- Unity is W1 = 0x00007FFF, W2 = 0, OUT_SHIFT = 0, which gives y = x1 bit exactly. This is also the reset state, and the state after an `axi_ad9361` reset. After such a reset the committed set is applied again once `l_clk` runs.
- Combining: y = conj(w1) x1 + conj(w2) x2, rounded half up once, then saturated to S12 (`docs/fixed_point.md`).

## Covariance blocks

- R11 = sum(x1i^2 + x1q^2), R22 = sum(x2i^2 + x2q^2), R21 = sum(x2 conj(x1)). These are computed from the inputs, before the weights. The results are 48-bit signed, each read as a LO/HI pair. Read HI then LO, or the other way round: both are stable while DONE is set.
- INT_LEN is read at the start of each block, so a change takes effect from the next block.
- At 10 MSPS a block of 10000 samples is 1 ms. A block that ends while DONE is still set is lost and counted in MISSED, and SEQ shows the gap.

## PS sequence

1. At startup: check 2R2T (`docs/interface.md`, Section 8, item 10). Write INT_LEN, then W1, W2, OUT_SHIFT and UPDATE. Wait for W_BUSY = 0.
2. Write CTRL = COV_EN | DAC_SEL (and CAP_SEL if the combined capture is wanted). Set TX `data_sel = 2` on all four TX channels through the driver.
3. Loop: wait for DONE (poll, or `irq`). Read 0x40-0x68. Write STATUS = 1. Compute the new weights. Write W1, W2, OUT_SHIFT and UPDATE.
4. After a sample rate change: CTRL.SOFT_RST 1, then 0. Write STATUS = 0xD. Discard the first block.
