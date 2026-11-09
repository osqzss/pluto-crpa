# Task 6a Check: crpa_core UIO Node and FIR Flags Removed

Date: 2026-11-09. Unit: second Pluto (CRPA unit), Rev C, AD9363A, `mode=2r2t`.

Firmware: `fw/build/pluto.frm`, built 2026-11-09 11:57 from fw `8f9cd60` plus uncommitted changes (`.gitmodules`, `Makefile` `LINUX_URL`, linux pointer), linux `crpa` `a26ff66`, hdl `ad150ddd5` (bitstream unchanged from Task 5). Flashed by the user (`pluto.frm` only). Build log: `results/fw_build.log` (git-ignored).

fw/linux `crpa` commits (on ADI `bf1d49f`), exported to `sw/dts/`:

| Commit | Change |
|---|---|
| `7a17700` | `zynq-pluto-sdr.dtsi`: remove `adi,axi-decimation-core-available` and `adi,axi-interpolation-core-available` |
| `88d1c7e` | `zynq-pluto-sdr.dtsi`: add `crpa-core@7c450000`, `generic-uio`, `reg = <0x7c450000 0x10000>`, `interrupts = <0 54 IRQ_TYPE_LEVEL_HIGH>`, `linux,uio-name = "crpa_core"` |
| `a26ff66` | `zynq_pluto_defconfig`: `CONFIG_CMDLINE="uio_pdrv_genirq.of_id=generic-uio"`, `CONFIG_CMDLINE_EXTEND=y` |

Address and IRQ source: `system.hwh` of the Task 5 build (`crpa_core` `C_BASEADDR` 0x7C450000, `C_HIGHADDR` 0x7C45FFFF; `irq` -> `sys_concat_intc/In10` -> `IRQ_F2P[10]`). ps-n maps to SPI 44+n, as the existing DMA (ps-13 = SPI 57, ps-12 = SPI 56) and I2C (ps-15 = SPI 59) nodes show.

## 1. Build products

- `fw/br2-external/board/adi/pluto/VERSIONS`: `linux v6.12-43127-ga26ff66`, `device-fw v0.39-22-g8f9c-dirty`.
- All three dtbs in `fw/build/` (`zynq-pluto-sdr`, `-revb`, `-revc`) contain the node; none contains `*-core-available`.
- `vmlinux` contains `uio_pdrv_genirq.of_id=generic-uio`.
- `make savedefconfig` reproduces the committed defconfig exactly.

## 2. On the Pluto (ssh, check script)

| Check | Expected | Result |
|---|---|---|
| `/opt/VERSIONS` | linux `a26ff66` | `linux v6.12-43127-ga26ff66`, `device-fw v0.39-22-g8f9c-dirty` |
| `/proc/cmdline` | ends with of_id | `... uboot=U-Boot PlutoSDR v0.20-... uio_pdrv_genirq.of_id=generic-uio` |
| UIO device | name `crpa_core` | `/sys/class/uio/uio0`, name `crpa_core`, version `devicetree`, `/dev/uio0` (248,0) |
| map0 | 0x7c450000, 0x10000 | `addr=0x7c450000 size=0x00010000` |
| Driver | `uio_pdrv_genirq` | `7c450000.crpa-core/driver -> uio_pdrv_genirq` |
| IRQ | GIC 86 (SPI 54), level | `33: 0 GIC-0 86 Level crpa_core` |
| VERSION (0x00) | 0x00010000 | `devmem 0x7C450000 32` = `0x00010000` |
| `cf-ad9361-lpc` | no f/8 | only `in_voltage_sampling_frequency` (30720000); no `_available` attribute |
| `cf-ad9361-dds-core-lpc` | no interpolation attributes | only `out_voltage_sampling_frequency`, `out_altvoltage_sampling_frequency` (30720000) |
| IIO devices | unchanged | ad9361-phy, xadc, one-bit-adc-dac, cf-ad9361-dds-core-lpc, cf-ad9361-lpc, `adi-iio-fakedev` (label `iio-axi-tdd-0`, the same TDD device as in Task 5) |

Notes:
- The u-boot on the unit is the factory one (v0.20, 2020); only `pluto.frm` was flashed. Its bootargs are passed through and the of_id parameter is appended, as intended.
- The `/proc/device-tree` lookup in the check script returned nothing (`find` does not follow the `/proc/device-tree` symlink); the platform device `7c450000.crpa-core` and its binding confirm the node.
- The ADC driver no longer creates `in_voltage_sampling_frequency_available`; with the flag removed a write to `cf-ad9361-lpc` `sampling_frequency` goes to the AD9361 clock (`ad9361_conv.c`), like `ad9361-phy`. Our scripts set the rate only through `ad9361-phy`.

## 3. Regression tests (libiio, from the host)

- `scripts/loopback_test.py`: `FAILS: 0`, 2R2T, at 30.72, 10, 3, 2.1 and 2.084 MSPS plus the channel-enable cases; settings restored. Log: `results/t6a_loopback.txt`.
- `scripts/if_check.py`: `RESULT PASS` (sign extension, DC filter off, l_clk = 2 x fs at 30.72, 10 and 3 MSPS). Log: `results/t6a_if_check.txt`.

## 4. Result

PASS. crpa_core is available to user space as `/dev/uio0` with its interrupt, the f/8 rate is no longer offered, and the existing data path is unchanged.
