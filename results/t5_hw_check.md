# Task 5 Hardware Check: crpa_core in the Bitstream

Date: 2026-11-08. Unit: second Pluto (CRPA unit), serial `1044734c96050011f2ff2100408f4f2ac3`, Rev C, AD9363A, `mode=2r2t`.

Firmware: `fw/build/pluto.frm` from fw `8f9cd60` (hdl `ad150ddd5`), flashed by the user (`pluto.frm` only, `docs/test-equipment.md`, Section 7.1). Context `fw_version` = `v0.39-22-g8f9c`, as in the build's `VERSIONS`. The bitstream in `pluto.itb` is byte-identical to the routed build in `results/hdl/20261108-1301_387ca1761-dirty/`. IIO devices unchanged: ad9361-phy, xadc, one-bit-adc-dac, cf-ad9361-dds-core-lpc, cf-ad9361-lpc (4 channels), iio-axi-tdd-0.

RF state: no RF test. After boot: RX LO 2400 MHz, TX LO 2450 MHz powered on, fs 30.72 MSPS, RX gain slow_attack 71 dB, TX attenuation 10 dB, `data_sel` 0 (`t1_passthrough.py --check`). The loopback and interface checks power TX_LO down during their tests; the FRAME_ERR test leaves it powered down.

## 1. Default paths unchanged (both muxes at reset)

| Check | Result | Log |
|---|---|---|
| `scripts/loopback_test.py`, digital loopback 2R2T | `FAILS: 0`. Bit exact on all four streams at 30.72, 10, 3, 2.1 and 2.084 MSPS; all four channel-enable combinations at 10 MSPS; 2.083 and 2.0 MSPS refused without FIR, as in T0b | `t5_loopback.txt` |
| `scripts/if_check.py` | `RESULT PASS`. `l_clk` = 2.000 x fs at 30.72, 10 and 3 MSPS; register values as in `docs/interface.md` | `t5_if_check.txt` |

So the capture path through `crpa_core` (CAP_SEL = 0, one register) and the DAC path (DAC_SEL = 0, combinational) behave as in T0b (`t0b_hw_test.md`).

## 2. Register readback at 0x7C450000

`devmem` over ssh, run by the user.

| Offset | Register | Read | Expected |
|---|---|---|---|
| 0x00 | VERSION | 0x00010000 | 0x00010000 |
| 0x04 | ID | 0x00000000 | 0 |
| 0x08 | SCRATCH | 0x00000000 | 0 |
| 0x0C | CTRL | 0x00000000 | 0 |
| 0x10 | STATUS | **0x00000004** | 0 (see Section 3) |
| 0x14 | INT_LEN | 0x00002710 | 10000 |
| 0x18 | W1 | 0x00007FFF | 0x7FFF |
| 0x1C | W2 | 0x00000000 | 0 |
| 0x20 | OUT_SHIFT | 0x00000000 | 0 |
| 0x68 | SEQ | 0x00000000 | 0 |
| 0x08 | SCRATCH after writing 0xA5A5C3C3 | 0xA5A5C3C3 | 0xA5A5C3C3 |

## 3. FRAME_ERR after sample rate changes

STATUS bit 2 (FRAME_ERR, sticky) was set after boot and after the two scripts above, which change the rate several times. `scripts/frame_err_test.sh` (run by the user over ssh, TX_LO powered down) clears it and watches it:

| Step | fs | STATUS |
|---|---|---|
| start | 30.72 MSPS | 0x4 |
| cleared, then 5 reads over 10 s | 30.72 MSPS | 0x0 every read |
| after change to 10 MSPS, no clear | 10 MSPS | **0x4** |
| cleared, then 5 reads over 10 s | 10 MSPS | 0x0 every read |
| after change to 30.72 MSPS, no clear | 30.72 MSPS | **0x4** |
| cleared, then 1 read after 2 s | 30.72 MSPS | 0x0 |

Result: a sample rate change sets FRAME_ERR every time (2 of 2); at a fixed rate it stays clear (20 s in total, at both rates). This is the frame hazard of `docs/interface.md`, Section 3, now seen on the real chip, during a rate change only. `axi_ad9361/rst` also clears the flag, so either the rate change does not assert it, or the double valid comes after its release; this test does not tell which. No design change is needed: the PS sequence in `docs/regmap.md` already pulses SOFT_RST, clears STATUS and discards the first block after a rate change. The PS application (Task 6) must do this, and should treat FRAME_ERR at a fixed rate as an error.

Not covered: the number of affected samples per rate change, and whether ENSM state changes (other than FDD) also set it.

## 4. Not tested

- CAP_SEL = 1, DAC_SEL = 1, COV_EN, weights and the `irq` line on hardware: Task 6 and T2.
- The `irq` line to the PS (ps-10, GIC SPI 54): needs a device tree node (Task 6).
