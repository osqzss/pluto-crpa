# T0b hardware test

Date: 2026-11-04. Status: **passed** for the digital data path in 1R1T and 2R2T. RF not tested (T1).

## Device and firmware
- Pluto Rev C (Z7010-AD9363A), `pluto.frm` only flashed.
- `fw_version`: v0.39-21-g27fb (fw `27fb31b`, which pins hdl `387ca1761`). Kernel: 6.12.77-gbf1d49f17fa9.
- IIO devices: ad9361-phy, xadc, one-bit-adc-dac, cf-ad9361-dds-core-lpc, cf-ad9361-lpc, iio-axi-tdd-0.
- Mode for the Results table below: 1R1T (only `voltage0`/`voltage1` on `cf-ad9361-lpc`). See the 2R2T section for the 2R2T run.

## Settings
- TX_LO powered down and TX attenuation -89.75 dB for the whole test; no RF connections. RX LO and RX gain not changed.
- Rates set through `ad9361-phy`. All settings were read back as restored afterwards: fs 30.72 MSPS, TX gain -10 dB, TX_LO on, loopback 0, FIR off.

## Method
- Data path: DMA -> tx_upack -> axi_ad9361 -> AD9361 data port loop (debugfs `loopback` = 1, "AD9361 internal TX->RX") -> axi_ad9361 -> cpack -> DMA.
- TX: cyclic 4096-sample buffer. I is a counter over all 12-bit codes, Q is `(n * 1597 + 5) mod 4096`, both in the upper 12 of 16 bits.
- RX: 8192 samples (two periods), compared exactly (S12) at the cyclic offset found from the first sample.
- Control: same TX with `loopback` = 0 must not match.

## Results
Mismatches are out of 8192 samples.

| fs (MSPS) | AD9361 FIR | RF rate (MSPS) | ADC (MHz) | Bad I | Bad Q | Control bad I/Q |
|---|---|---|---|---|---|---|
| 10 | off | 10 | 80.0 | 0 | 0 | 8189/8192 |
| 3 | off | 3 | 36.0 | 0 | 0 | 8189/8191 |
| 2.1 | off | 2.1 | 25.2 | 0 | 0 | 8190/8188 |
| 2.084 | off | 2.084 | 25.008 | 0 | 0 | 8189/8189 |
| 2 | on | 8 | 64.0 | 0 | 0 | not run |
| 1 | on | 4 | 32.0 | 0 | 0 | not run |
| 0.6 | on | 2.4 | 28.8 | 0 | 0 | not run |
| 0.53 | on | 2.12 | 25.44 | 0 | 0 | not run |
| 0.521 | on | 2.084 | 25.008 | 0 | 0 | not run |

Rates refused with EINVAL:
- FIR off: 2083333, 2000000, 1000000. Lowest rate that worked: 2084000.
- FIR on: 520000, 500000. Lowest rate that worked: 521000.

## Notes
- **FIR-on rows (1R1T) are not a clean measurement.** The test's `filter_fir_config` write was rejected (EINVAL, cause not found). Enabling the FIR needs `tx_fir_int` and `rx_fir_dec` to be 1, 2 or 4; `ad9361_parse_fir` sets them before loading the coefficients, so the rejected load most likely set them. The enable worked and gave decimation by 4 (RF rate = 4 x fs), but no valid filter was confirmed. The rows show which rates were accepted in that state, not supported operation or filter quality. Without any load (after a reboot) the enable was refused, as seen in 2R2T.
- The data port loop does not exercise the AD9361 analog or RF paths.

## 2R2T
Tested with `scripts/loopback_test.py`; raw output in `results/t0b_loopback_2r2t.txt`. Same method and TX safety settings, with four distinct streams, FIR off. All settings read back as restored.

Device settings: `mode=2r2t`, `attr_name=compatible`, `attr_val=ad9361`, `compatible=ad9361` (`hw_model` reports Z7010-AD9361). The previous values were `mode=1r1t` with the other three undefined.

| fs (MSPS) | Loop on: bad samples, all 4 streams | Common offset | Control (loop off) |
|---|---|---|---|
| 30.72 | 0 | yes | no match, as required |
| 10 | 0 | yes | no match, as required |
| 3 | 0 | yes | no match, as required |
| 2.1 | 0 | yes | no match, as required |
| 2.084 | 0 | yes | no match, as required |

Channel enables at 10 MSPS, all 0 bad samples: TX all with RX ch0/1; TX all with RX ch2/3; TX ch0/1 with RX ch0/1; TX ch2/3 with RX ch2/3.

Rates refused with FIR off: 2083333, 2000000.

An earlier run of the script also tried the FIR on: the enable was refused (rc=1) and 2, 1 and 0.521 MSPS were refused. The likely cause, from the driver source, is that no filter had been loaded since boot; the kernel log was not checked. That section was removed from the script.

### Rerun with the AD9363 identity
The `attr_name`, `attr_val` and `compatible` variables were then removed by the user, keeping `mode=2r2t`. `hw_model` reports Z7010-AD9363A and the LO range is back to 325 MHz to 3.8 GHz. Rerunning the same test gave the same outcome: 14 of 14 checks passed, with 0 bad samples, a common offset on all streams at every rate, and all settings restored. Raw output: `results/t0b_loopback_2r2t_ad9363.txt`. This is the Pluto's current configuration; its saved environment is `results/pluto_env_after_2r2t.txt`.

## Not tested
- RF reception and transmission (covered by T1).
- AD9361 internal FIR with a valid filter.

## Identity check
`/opt/VERSIONS` on the device matches `fw/br2-external/board/adi/pluto/VERSIONS` line by line (compared by the user, 2026-11-04): device-fw v0.39-21-g27fb, hdl dev_prj_2018_r1-3137-g387ca, br2-external 2025.05-0.3.0-54-g46fb, linux v6.12-43124-gbf1d49, u-boot b234c, buildroot 2026.02-3.

U-Boot environment at that check (before the 2R2T change): `mode=1r1t`; `attr_name`, `attr_val` and `compatible` not defined.
