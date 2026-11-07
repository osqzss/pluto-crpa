# Test Equipment and Host Tools

This file tells Claude Code which GNSS test equipment and tools are installed
on the development host and may be used for pluto-crpa testing (T1 and later,
`docs/pluto-crpa-plan.md`, Section 8.2). It lives at `docs/test-equipment.md`
and is referenced from `CLAUDE.md`.

Items marked `<TBD>` are not yet recorded. Fill them in on first use (Section 8)
and commit the update. Values below were last checked on 2026-11-06.

---

## 1. Overview

| Item | Role | Interface | Tools |
|---|---|---|---|
| gps-sdr-sim | Generates GPS L1 C/A baseband IQ files | - | `~/Work/gps-sdr-sim/gps-sdr-sim` (not on PATH) |
| bladeRF x40 | GPS simulator TX (primary) | USB | libbladeRF, `bladeRF-cli` |
| USRP B205mini | GPS simulator TX (alternative), or RX capture for checks | USB 3 | UHD (`uhd_find_devices`, `uhd_usrp_probe`, `tx_samples_from_file`, ...) |
| u-blox M8T | COTS GNSS receiver under test (C/N0, fix, TTFF) | USB (CDC ACM) | gpsd, `gpspipe`, `ubxtool` |
| PlutoSDR Rev C | CRPA device under test | USB (network 192.168.2.1) | libiio, `scripts/*.py` |

All of the above are built or installed on the host and available to
Claude Code. Before first use in a session, check that they are present
(Section 8) rather than assuming paths or versions.

Test setup for T1 (conducted only):

```
bladeRF or B205mini TX -> fixed attenuator -> 2-way splitter -> Pluto RX1, RX2
Pluto TX1 -> DC block -> 50 dB attenuator -> u-blox M8T
Baseline: simulator TX -> attenuators -> u-blox M8T (Pluto not in path)
```

---

## 2. Safety Rules (highest priority)

- **Conducted or shielded tests only. Never radiate GPS signals.** Every TX
  output (bladeRF, B205mini, Pluto) must be cabled to its load through
  attenuators.
- **Claude Code must not start any transmission on its own.** Before starting
  the simulator TX or enabling Pluto TX, ask the user to confirm in the
  session that the setup is cabled and the attenuators are in place. One
  confirmation covers one test run, not the whole session.
- Scripts that can transmit are dry-run by default and transmit only with an
  explicit flag (e.g. `--on`).
- On normal exit, Ctrl-C or any error, scripts must stop all transmission:
  stop the bladeRF TX / kill the UHD TX process, disable Pluto pass-through,
  set Pluto TX attenuation to maximum and move TX_LO away from L1.
- Start with high attenuation and reduce it step by step. Do not exceed the
  maximum input level of the Pluto RX or the u-blox receiver.
- Record all hardware settings in every measurement log: simulator device,
  TX gain, sample rate, external attenuator values (as entered by the user),
  Pluto LO, Delta, fs, bandwidth, RX gain, TX attenuation.

---

## 3. gps-sdr-sim

- Binary: `/home/sdr/Work/gps-sdr-sim/gps-sdr-sim`, not on PATH (built from
  source, commit `28ca29a6719475195e3aabd5930c4ed02d67190f`).
- Needs a GPS broadcast ephemeris file (RINEX nav). Location:
  `/home/sdr/Work/gps-sdr-sim/brdc0010.22n` (2022-01-01).
  Do not download ephemeris files without asking the user.
- Check the options with `gps-sdr-sim` (no arguments prints usage) before
  writing commands. Main options: ephemeris file (`-e`), static location
  (`-l lat,lon,hgt`), duration (`-d`), sample rate (`-s`), I/Q bit width
  (`-b`), output file (`-o`).
- The simulated GPS time comes from the ephemeris file, not from the host
  clock. Always cold start the u-blox receiver before each run.
- Output files are large. Write them to a git-ignored directory
  (`sim/`, in `.gitignore`); never commit them.
- The sample rate and I/Q format must match what the TX tool expects
  (bladeRF: 16-bit I/Q; UHD `tx_samples_from_file --type short`). Confirm
  with the tool help before use.

---

## 4. bladeRF

- libbladeRF 2.6.1 and `bladeRF-cli` 1.10.0 built from source
  (`~/Work/bladeRF`, commit `35174c30b009cdb335800c411f3c14d45283f12b`),
  installed in `/usr/local`.
- Model: x40 (`bladerf1`, 40 KLE; bladeRF x40/x115 and bladeRF 2.0 micro use
  different gain commands). Serial: `ead3cd3312f2d66184bb4e9166124a0a`.
  Firmware: 2.6.0-git-09c82087. USB 3 (SuperSpeed).
- FPGA version: 0.16.0. libbladeRF loads it over USB when a tool opens the
  device, from `~/.config/Nuand/bladeRF/hostedx40.rbf`
  (SHA-256 `b21a50c87bccf915b8b1630354dbd07c87c17892c6011ec086bbf9e50dedc15a`).
- Probe: `bladeRF-cli -p`. Version and FPGA: `bladeRF-cli -e version`.
- Use non-interactive modes only: `bladeRF-cli -e "cmd; cmd"` or
  `bladeRF-cli -s script.txt`. Do not use interactive mode (`-i`).
- Check `bladeRF-cli -e "help set"` and `bladeRF-cli -e "help tx"` before
  writing scripts; do not guess command syntax.
- Typical sequence: set TX frequency (1575.42 MHz), sample rate, bandwidth
  and gain; `tx config file=<file> format=bin repeat=<n>`; `tx start`;
  `tx wait`.
- Select a specific device with `-d "*:serial=<serial>"` if more than one
  bladeRF is ever connected.
- A carrier at 1575.42 MHz stays on after `bladegps` exits and disappears when
  the bladeRF is unplugged from USB (2026-11-07,
  `results/t1_rx_unit_compare.md`). Do not treat a stopped `bladegps` as no RF
  at L1. Unplug the bladeRF for noise floor measurements.

---

## 5. USRP B205mini (UHD)

- UHD 4.6.0 from the Ubuntu packages (`uhd-host`
  4.6.0.0+ds1-5.1ubuntu0.24.04.1). FPGA images: `/usr/share/uhd/images`
  (the B205mini loads `usrp_b205mini_fpga.bin` at runtime).
- Serial: `3297659` (name `B205i`, FW 8.0, FPGA 7.0).
- Probe: `uhd_find_devices`, `uhd_usrp_probe`.
- TX from file: UHD example `tx_samples_from_file`
  (path `/usr/libexec/uhd/examples/tx_samples_from_file`), e.g.
  `--args "serial=<serial>" --file <file> --type short --rate <fs>
  --freq 1575.42e6 --gain <dB> --repeat`. Check `--help` first.
- Connect to a USB 3 port; USB 2 limits the sample rate.

---

## 6. u-blox M8T via gpsd

### 6.1 Access
- Device: `/dev/serial/by-id/usb-u-blox_AG_-_www.u-blox.com_u-blox_GNSS_receiver-if00`.
  Always use the by-id path; the Pluto
  also enumerates as `/dev/ttyACM*`, so ttyACM numbers are not stable.
- gpsd config (`/etc/default/gpsd`): `DEVICES` = the by-id path,
  `USBAUTO="false"` (so gpsd does not grab the Pluto serial port),
  `GPSD_OPTIONS="-n"`.
- Status: `systemctl status gpsd gpsd.socket`, `pgrep -a gpsd`. Port users:
  `sudo fuser -v /dev/serial/by-id/usb-u-blox_AG_-_www.u-blox.com_u-blox_GNSS_receiver-if00`.
  Note that `gpspipe` starts gpsd
  through socket activation.
- The user may stop gpsd to use a GUI client directly on the serial port.
  If the port is busy or gpsd is stopped, ask the user before restarting
  gpsd.

### 6.2 Receiver configuration (set and saved by the user)
- Protocol version: `18.00` (from `ubxtool -p MON-VER | grep PROT`). Set
  `export UBXOPTS="-P 18"`; ubxtool commands fail silently with a wrong
  value.
- Firmware (MON-VER): `EXT CORE 3.01 (107900)`, `FWVER=SPG 3.01`, HW
  `00080000`, GNSS `GPS;GLO;GAL;BDS`. gpsd 3.25 (Ubuntu package).
- Module label: `NEO-M8T-0-01`. It runs standard-precision (SPG) firmware,
  not timing (TIM) firmware. The user accepted this for CRPA development
  (2026-11-06).
- u-blox 8 generation: use CFG-MSG / CFG-PRT, not CFG-VALSET. No NAV-SIG,
  no MON-RF; use NAV-SAT and MON-HW.
- Timing mode (CFG-TMODE2, 0x06 0x3D) must be disabled. Check with
  `ubxtool -c 0x06,0x3d` before tests. On the current SPG 3.01 firmware the
  receiver answers ACK-NAK: the message is not supported, so there is no
  timing mode to disable.
- Enabled UBX messages (rate 1 on USB, saved with `ubxtool -p SAVE`):

| Message | Class/ID | Use |
|---|---|---|
| NAV-PVT | 0x01 0x07 | fix type, numSV, time, position |
| NAV-SAT | 0x01 0x35 | per-SV C/N0, tracking/used flags, elevation (main metric) |
| MON-HW | 0x0A 0x09 | AGC count, jamming indicator, noise level |
| NAV-STATUS | 0x01 0x03 | TTFF |
| NAV-CLOCK | 0x01 0x22 | clock bias and drift (pass-through latency appears as a bias step) |

- Check a rate with `ubxtool -p CFG-MSG,<class>,<id>` (no rate argument).
  Do not change or save the receiver configuration without asking the user.

### 6.3 Monitoring commands
- `gpspipe -w`: JSON. SKY gives per-SV `ss` (C/N0, dB-Hz) and `used`;
  TPV gives fix mode and time.
- `gpspipe -R > <run>.ubx`: raw log; decode later with
  `ubxtool -f <run>.ubx` or pyubx2. Keep raw logs under `results/`.
- `ubxtool -w <sec> -v 2`: decoded UBX stream including MON-HW and
  NAV-CLOCK, which are not in the gpsd JSON.
- Cold start: `ubxtool -p COLDBOOT -w 20 -v 2`. Do this before every run.

---

## 7. PlutoSDR (device under test)

- URI `ip:192.168.2.1`; ssh host `pluto` (`~/.ssh/config`).
- The simulator SDRs are bladeRF and B205mini, so there is no address
  conflict. If a second Pluto is ever connected, stop and ask the user.
- See `docs/pluto-crpa-plan.md` (Sections 4, 7, 9.3) and
  `docs/interface.md` for configuration and scripts.
- Units: second Pluto, serial `1044734c96050011f2ff2100408f4f2ac3`, is the CRPA
  unit, with matched RX channels. First Pluto, serial
  `1044734c960500110c000900418f4f7ca2`, has excess noise and bursts on RX2
  (`results/t1_rx_unit_compare.md`). Connect only one at a time: both use
  192.168.2.1.
- After a reboot, TX_LO is powered on at 2450 MHz and the RX settings are back at
  defaults (LO 2400 MHz, 30.72 MSPS, 71 dB). Check before each run.
- 2R2T needs only `fw_setenv mode 2r2t`. The chip variant uses `attr_name` and
  `attr_val`; a variable named `compatible` is not read by U-Boot, and the first
  Pluto still has that unused setting. Both units run as `ad9363a`.

---

## 8. First-Use Checklist for Claude Code

Run these, report the results to the user, and fill in the `<TBD>` items:

```
which gps-sdr-sim bladeRF-cli uhd_find_devices uhd_usrp_probe gpsd gpspipe ubxtool
bladeRF-cli -p
bladeRF-cli -e version
uhd_find_devices
uhd_usrp_probe --args "type=b200"      # takes a few seconds, loads FPGA image
systemctl status gpsd gpsd.socket --no-pager
ls -l /dev/serial/by-id/
groups                                   # must include dialout
ubxtool -p MON-VER
```

These commands only read status; none of them transmits.

Also extend `scripts/record_env.sh` to record: gps-sdr-sim commit,
libbladeRF and bladeRF FPGA versions, UHD version, gpsd version, u-blox
firmware and protocol version.
