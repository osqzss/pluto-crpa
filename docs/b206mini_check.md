# B206mini compatibility check (replaces the B205mini)

The USRP B205mini (serial `3297659`) used as the jammer in T4, T5 and T5b is
replaced by a B206mini. Ettus describes the two as the same design. This plan
confirms that before the B206mini is used in T5b P2, and decides which B205mini
numbers still apply. Safety rules: `docs/test-equipment.md`, Section 2, and
`docs/t5b_plan.md`, Section 3. Nothing in this plan transmits without the
user's go for that run.

## 1. Found on 2026-11-21 (connected, read-only)

| Item | Seen | Note |
|---|---|---|
| USB ID | `2500:0023`, "Cypress / WestBridge", serial `0000000004BE`, speed 480 | FX3 boot loader state (no firmware loaded yet). The speed must be checked again after UHD loads the firmware |
| `uhd_find_devices` (UHD 4.6.0) | "No UHD Devices Found" | |
| `libuhd.so.4.6` | no `B206` string, only `B200mini` and `B205mini` | |
| udev rules (`uhd-host` 4.6) | PIDs 0002, 0020, 0021, 0022 only | node `/dev/bus/usb/001/005` is `root:root 0664`, so non-root UHD cannot open it |

From the UHD source on GitHub (master, read 2026-11-21):

- `host/lib/usrp/b200/b200_iface.hpp`: `B206MINI_PRODUCT_ID = 0x0023` (B205mini
  0x0022), name "B206mini", FPGA image **`usrp_b205mini_fpga.bin`**, the
  same file as the B205mini.
- `b200_impl.hpp`: `B205_FPGA_COMPAT_NUM = 7 // applies to all B2xxminis`;
  `b200_impl.cpp`: `is_b2xx_mini()` includes B206MINI. Code paths are shared
  with the B205mini.
- `CHANGELOG`: first release with B206mini support is **UHD 4.9.0.0**
  ("Support for USRP B206mini-i").
- `host/utils/uhd-usrp.rules` (master) has the 0x0023 rule.

**Conclusion:** the hardware and FPGA image are shared with the B205mini, but
the host needs **UHD 4.9 or newer**. The Ubuntu 24.04 package (4.6.0) cannot
use it.

## 2. Decision for the user: UHD upgrade route

`scripts/t4_jammer.py` uses the UHD Python API from system Python
(`python3-uhd`), so the new UHD must provide Python bindings that system
Python (or `.venv`) can import.

| Option | Content | Effect |
|---|---|---|
| A (**decided**, 2026-11-21) | Build UHD at a release tag >= v4.9.0.0 from source with Python API, install in `/usr/local` next to the Ubuntu packages; `uhd_images_downloader` for images of the same version; install the udev rule from that tree | Exact version recorded (tag and commit) as for libbladeRF; same pattern as the bladeRF install |
| B | Ettus PPA (`ppa:ettusresearch/uhd`) if it has a >= 4.9 build for noble | Less work; the version follows the PPA; check that it ships `python3-uhd` |

Either way: also the udev rule for 0x0023 (`udevadm control --reload`,
re-plug), and the FPGA images must match the UHD version (`usrp_b205mini_fpga.bin`
from 4.9 may differ from the 4.6 image; the FPGA compat number is 7 in both
cases, to be confirmed on the device).

The B205mini results (T4, T5) were taken with UHD 4.6. A new UHD is a second
change next to the new unit; the checks of Section 4 cover both together.

### 2.1 Build and install (option A)

Facts checked on the host and in the source (2026-11-21):

- **UHD v4.10.0.0** (commit `2af4ddb96219a99d2300804830e0971f79557b23`),
  cloned to `~/Work/uhd` (`--depth 1`), local branch `UHD-4.10` at the tag
  so the version reads `4.10.0.0-0-g2af4ddb9` (a detached HEAD gives
  `4.10.0.HEAD-...`, a development version). Decided by the user on 2026-11-21
  after v4.11.0.0 (latest) failed: 4.11 needs gRPC and Protobuf for MPMD
  (not installed), and with `-DENABLE_MPMD=OFF` its Python module does not
  compile (upstream bug: `python/CMakeLists.txt` adds `lib/include` to the
  pyuhd include path only under `ENABLE_MPMD`, but `rfnoc_python.hpp`
  includes `uhdlib/features/fpga_load_notification_iface.hpp` always).
  4.10 has B206mini support (`b200_iface.hpp`), no gRPC, and the same B2xx
  image entries in `images/manifest.txt`; the 4.11 changelog has no B2xx,
  USB or TX streaming change.
- **The Ubuntu packages stay.** `gnuradio` and `libgnuradio-uhd3.10.9t64`
  depend on `libuhd4.6.0t64`, and `uhd-host` and `python3-uhd` depend on each
  other; removing them would remove GNU Radio. The two libraries have
  different sonames (`libuhd.so.4.6.0`, `libuhd.so.4.10.0`).
- `/usr/local` wins everywhere: `/usr/local/bin` is before `/usr/bin` in
  PATH, `/usr/local/lib/python3.12/dist-packages` is before
  `/usr/lib/python3/dist-packages` in `sys.path`, `/usr/local/lib` is in
  `ld.so.conf.d/libc.conf`.
- UHD's default Python path (`posix_prefix`) would be
  `/usr/local/lib/python3.12/site-packages`, which Ubuntu's Python does not
  read; `scripts/build_uhd.sh` sets `UHD_PYTHON_DIR` to `dist-packages`.
- Build dependencies present: cmake 3.28, g++ 13, Boost 1.83 (filesystem,
  program_options, serialization, test), libusb-1.0, python3-dev, numpy,
  mako, ruamel.yaml, requests, setuptools, pybind11. Doxygen absent (manual
  off). Build with default components (MPMD on, no gRPC in 4.10).
- Images: the 4.10 `libuhd` looks in `/usr/local/share/uhd/images`, not in
  the 4.6 package directory `/usr/share/uhd/images`. In `images/manifest.txt`
  of v4.10.0.0 (and v4.11.0.0), `b2xx_b206mini_fpga_default` points to the same archive as
  `b2xx_b205mini_fpga_default` (`b2xx_b205mini_fpga_default-gc37b318.zip`,
  same sha256): one FPGA image for both. `-t b2xx` (a regex) also takes
  `b2xx_common` (FX3 firmware).
- udev: the 4.10 tree installs `uhd-usrp.rules` (with 0x0023) to
  `/usr/local/lib/uhd/utils/`, not into udev; the packaged
  `/lib/udev/rules.d/60-uhd-host.rules` lacks 0x0023.

Steps (B206mini may stay connected; nothing here transmits):

```bash
# 1. Claude or user, no sudo (about 10-20 min, 12 cores):
cd ~/Work/pluto-crpa && ./scripts/build_uhd.sh

# 2. User:
cd ~/Work/uhd/host/build
sudo make install
sudo ldconfig
sudo cp /usr/local/lib/uhd/utils/uhd-usrp.rules /etc/udev/rules.d/60-uhd-usrp-local.rules
sudo udevadm control --reload-rules && sudo udevadm trigger
sudo /usr/local/bin/uhd_images_downloader -t b2xx     # into /usr/local/share/uhd/images
# then unplug and re-plug the B206mini

# 3. Claude, checks (no device access yet):
hash -r; which uhd_find_devices uhd_usrp_probe        # expect /usr/local/bin
uhd_config_info --version                             # expect 4.10.0.0
python3 -c "import uhd; print(uhd.__file__, uhd.get_version_string())"
ls -l /usr/local/share/uhd/images | grep b205mini
```

Rollback: `sudo xargs rm -v < ~/Work/uhd/host/build/install_manifest.txt`,
remove `/etc/udev/rules.d/60-uhd-usrp-local.rules` and
`/usr/local/share/uhd/images`, `sudo ldconfig`; the 4.6 packages are then in
use again unchanged.

Notes: `scripts/t4_jammer.py` runs on system Python and gets the 4.10 module;
`.venv` has no system site packages and no `uhd`, as before. GNU Radio keeps
using UHD 4.6 and cannot open the B206mini (not needed here).

## 3. Checks without RF (C1, C2)

**C1, enumeration** (after the upgrade; B206mini TX/RX through 30 + 20 dB as
cabled, or terminated; RX2 port unconnected):

1. `uhd_config_info --version`, `python3 -c "import uhd; print(uhd.get_version_string())"`:
   same version for tools and Python.
2. `uhd_find_devices`: product `B206mini`, serial (the UHD serial, not the
   FX3 boot loader serial), name.
3. `uhd_usrp_probe --args "serial=<serial>"`: FW and FPGA version (FPGA
   compat 7.x), image file loaded, master clock, TX gain range (B205mini 0 to
   89.75 dB), TX frequency range, TX antennas (`TX/RX`), sensors (`ref_locked`,
   temperature).
4. After the probe: `/sys/bus/usb/devices/.../speed` = 5000 (USB 3). At 480
   the 8 / 16 MSPS waveforms of T5b are at risk: move to a USB 3 port.
5. First-open time after power-up (B205mini about 12 s, later 2 s).

**C2, scripts** (offline and dry runs, no `--on`):

1. `python3 scripts/test_t4_jammer.py` (stand-in `uhd` module, 23 tests):
   checks that the scripts still import and run under the new Python setup.
2. `t4_jammer.py` default `--args serial=3297659` is the B205mini: change the
   default to the B206mini serial (code change, with the test updated).
3. Dry runs as in `docs/t5b_plan.md`, Section 4.7: CW, N1 (8 MSPS), PN
   (8.184 MSPS), N10 (16 MSPS), `--lo-offset=-6e6`. Expect TX rate range
   31.25 kHz to 16 MSPS at the default master clock, as the B205mini.
4. `scripts/t3_phase.py --seq selftest` (unchanged, no UHD; only to confirm the
   Python environment).

Pass: product B206mini found by serial, FPGA image `usrp_b205mini_fpga.bin`
loaded, USB 3, gain range, antennas and rate range as the B205mini, all tests
and dry runs pass. Otherwise stop and report.

## 4. RF check, RX-only (C3; needs the go)

A second unit has its own output power, gain curve, reference clock error,
LO leakage and spurs, even with the same design. The T5 table "B205mini gain
-> J/N60" and the safety worst case were measured or assumed for the old unit.

**Before C3 (safety): done 2026-11-21.** B206mini maximum TX power from the
NI specifications (given by the user,
https://www.ni.com/docs/en-US/bundle/usrp-b206mini-i-specs/page/specs.html;
the page content was not readable here, conditions not seen): **16.06 dBm,
70 MHz to 4 GHz** (9.16 dBm, 4 to 5.9 GHz). That is 3.9 dB below the
+20 dBm assumed for the B205mini, so every worst case of the T4 / T5 / T5b
safety texts drops by about 4 dB and the 40 dB floor of `--ext-att` stays:
at 40 dB and full gain, CW about -24 dBm and noise (12 dB crest) about
-19 dBm peak at the Pluto RX, about 21 dB below the AD9363 absolute maximum
of +2.5 dBm peak; at 30 + 20 dB about 10 dB lower again. No script change.

Setup: as T5b P1 / P2 (`docs/t5b_plan.md`, Sections 2.1 and 2.7): V3, jammer
attenuators 30 + 20 dB, Pluto at L1 + 3 MHz, 10 MSPS, 9 MHz, RX gain 60, TX
safe, bladegps stopped (bladeRF idle or unplugged), `t3_phase.py --passive`.

| Step | Content | Compare with (B205mini) |
|---|---|---|
| C3-0 | B206mini opened by `t4_jammer.py --on --gain off`, 3 captures; then after `quit` 3 captures | no line at L1 + 200 kHz or L1; noise -42.56 / -42.90 dBFS |
| C3-1 | CW (L1 + 200 kHz, ampl 0.5), gain 35, 45, 55, 65, 70, 72.5, 75, 77.5, then 1 dB steps to the first clipped step + 1, 3 captures each with `--cw-offset 200e3 --cw-span 15e3 --spurs 5` | J/N60 -9 / 1 / 10 / 30.0 / 35.0 / ... (T4 P2, T5 P2); clip onset at 78 dB, J/N60 42.2; step 2.2 to 2.6 dB per 2.5 dB above 70 |
| C3-2 | Same captures: line frequency at the Pluto | B205mini 5.6 kHz below nominal; must stay inside `--cw-span 15e3` |
| C3-3 | Same captures: sidebands near the line and the floor next to it | +/-4 kHz sidebands; floor up to +9.6 dB near the line at J/N60 52 |
| C3-4 | N1 file (8 MSPS) at gain 65 and 75, 60 s each: underflow count on every STATE line; LO leakage at L1 against the jammer power | 0 underflows; leakage under -30 dBc or an LO offset (T5b Section 2.5) |
| C3-5 | N10 file (16 MSPS) at gain 65, 60 s: underflows | 0 |
| C3-6 | `off`, `quit`, exit: `JAMMER OFF` in the log, no residual line | as B205mini |

C3-1 and C3-6 replace the CW part of T5b P2-a (its CW same-day check is the
gain 65 point). C3-4 is the first part of the N1 ladder of P2-a.

**Results and what follows:**

- CW gain 65 gives J/N60 30.0 +/- 1 dB and the curve is within 1 dB of the
  B205mini at every step up to 75 dB: the T5 gain table carries over; T5b P2
  ladders unchanged.
- Otherwise: the C3-1 table becomes the B206mini table ("B206mini gain ->
  J/N60") and the T5b P2 ladders shift by the measured offset. CW results of
  T5 stay valid (J/N60 is measured at the Pluto, not from the gain), but the
  "CW from T5" shortcut in T5b (F and P runs) then depends on the same-day CW
  N run matching T5 within 1 dB, as already planned.
- Stop rules as T5b P2: underflows, level more than 3 dB from the expected
  value at gain 65 (here: report and replace the table, after the user has seen
  it), `JAMMER OFF` not confirmed, TX not safe, any unexpected error.

Log: `results/b206mini_check.md` (C1 to C3 values, versions, command lines,
attenuators as stated), raw jammer and capture logs `results/t5b_C3_*`.

## 5. Records to update after the checks

- `docs/test-equipment.md`: Section 1 table and setup, Section 2 safety text,
  Section 5 (title, UHD version and install path, serial, FW/FPGA, image,
  first-open time, gain table or pointer to `results/b206mini_check.md`,
  off-state behaviour), Section 7 ("bladeRF and B206mini"), Section 8
  (`--args "type=b200"` still matches), the date of the last check.
- `scripts/t4_jammer.py`: default `--args`, docstring and the "unplug the
  B205mini" message (device name); `test_t4_jammer.py` if it checks the text.
- `scripts/record_env.sh` and `docs/environment.md`: UHD version and source.
- `docs/t5b_plan.md`: "B205mini" in the setup, safety and P2 text becomes
  B206mini where it refers to future runs; T4 / T5 records stay as they are
  (they were B205mini).
- `docs/pluto-crpa-plan.md`, Sections 10 and 11.

## 6. Order

1. User: UHD route (Section 2; decided: A, from source) and data sheet
   output power (Section 4; 16.06 dBm, given 2026-11-21).
2. Build (`scripts/build_uhd.sh`) and install (user runs the `sudo` steps,
   Section 2.1).
3. C1, C2 (Claude, no RF).
4. C3 (go from the user), report; then T5b P2-a continues with N1 from the
   C3-4 level.
