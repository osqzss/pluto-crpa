#!/usr/bin/env python3
"""T1: RX1 -> TX1 pass-through in the PL on the current firmware (TX data_sel = 8).

Conducted or shielded use only: TX1 must go through a DC block and attenuation to the
GNSS receiver. Default is a dry run that exercises the path with TX_LO powered down
and maximum attenuation, and then restores it. Transmission needs --on and an
explicit --tx-gain; stop it with --off.

Usage: scripts/t1_passthrough.py            dry run, no RF output
       scripts/t1_passthrough.py --on --tx-gain DB [--rx-gain DB] [--delta HZ] [--fs HZ]
       scripts/t1_passthrough.py --off
Needs iio_attr and iio_reg. Python standard library only.
"""
import argparse
import subprocess
import time

L1 = 1575420000
ADC = "cf-ad9361-lpc"
CORE = 0x80000000  # DEBUGFS_DRA_PCORE_REG_MAGIC
TX_MIN = "-89.75"

ap = argparse.ArgumentParser()
ap.add_argument("--uri", default="ip:192.168.2.1")
ap.add_argument("--on", action="store_true")
ap.add_argument("--off", action="store_true")
ap.add_argument("--tx-gain", type=float)
ap.add_argument("--rx-gain", type=int, default=60)
ap.add_argument("--delta", type=int, default=3000000)
ap.add_argument("--fs", type=int, default=10000000)
ap.add_argument("--bw", type=int, default=9000000)
args = ap.parse_args()
if args.on and args.tx_gain is None:
    ap.error("--on needs an explicit --tx-gain")
if args.on and args.off:
    ap.error("--on and --off exclude each other")


def run(*cmd):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    if p.returncode:
        raise RuntimeError(" ".join(cmd) + ": " + (p.stdout + p.stderr).strip())
    return p.stdout.strip()


def phy(direction, chan, name, *val):
    return run("iio_attr", "-u", args.uri, direction, "-c", "ad9361-phy", chan, name, *val)


def loopback(*val):
    return run("iio_attr", "-u", args.uri, "-D", "ad9361-phy", "loopback", *val)


def reg(addr, *val):
    return run("iio_reg", "-u", args.uri, ADC, hex(CORE | addr), *[hex(v) for v in val])


def sel():
    return [int(reg(0x4418 + c * 0x40), 0) & 0xf for c in range(4)]


def tx_safe():
    """Mute TX: LO down, maximum attenuation."""
    phy("-o", "altvoltage1", "powerdown", "1")
    for ch in ("voltage0", "voltage1"):
        phy("-o", ch, "hardwaregain", TX_MIN)
    if phy("-o", "altvoltage1", "powerdown") != "1":
        raise SystemExit("TX_LO did not power down")


def path_on():
    loopback("2")
    reg(0x4044, 1)              # dac sync, for a repeatable latency
    time.sleep(0.2)
    for c in (2, 3):            # TX2 unused: zero, not whatever RX2 carries
        reg(0x4418 + c * 0x40, 3)


def path_off():
    loopback("0")
    for c in range(4):          # back to the driver default (DDS, scale 0)
        reg(0x4418 + c * 0x40, 0)


def report():
    print("RX LO", phy("-o", "altvoltage0", "frequency"), "| TX LO", phy("-o", "altvoltage1", "frequency"),
          "| fs", phy("-i", "voltage0", "sampling_frequency"),
          "| RX bw", phy("-i", "voltage0", "rf_bandwidth"), "| TX bw", phy("-o", "voltage0", "rf_bandwidth"))
    print("RX gain", phy("-i", "voltage0", "gain_control_mode"), phy("-i", "voltage0", "hardwaregain"),
          "/", phy("-i", "voltage1", "gain_control_mode"), phy("-i", "voltage1", "hardwaregain"),
          "| TX gain", phy("-o", "voltage0", "hardwaregain"), "/", phy("-o", "voltage1", "hardwaregain"),
          "| TX_LO powerdown", phy("-o", "altvoltage1", "powerdown"))
    print("loopback", loopback(), "| TX data_sel", sel(), "| reg 0x5c", reg(0x005c))


if args.off:
    tx_safe()
    path_off()
    print("OFF")
    report()
    raise SystemExit(0)

# Always mute first; nothing below may emit until TX_LO is powered up at the end.
tx_safe()
phy("-i", "voltage0", "sampling_frequency", str(args.fs))
phy("-i", "voltage0", "rf_bandwidth", str(args.bw))
phy("-o", "voltage0", "rf_bandwidth", str(args.bw))
phy("-o", "altvoltage0", "frequency", str(L1 + args.delta))
phy("-o", "altvoltage1", "frequency", str(L1 + args.delta))
for ch in ("voltage0", "voltage1"):
    phy("-i", ch, "gain_control_mode", "manual")
    phy("-i", ch, "hardwaregain", str(args.rx_gain))
path_on()
got = sel()
if got != [8, 8, 3, 3]:
    tx_safe()
    path_off()
    raise SystemExit("unexpected TX data_sel %s; path removed" % got)

if args.on:
    phy("-o", "voltage0", "hardwaregain", str(args.tx_gain))
    phy("-o", "altvoltage1", "powerdown", "0")
    print("ON: RX1 -> TX1 pass-through active. Stop with --off.")
    report()
else:
    print("DRY RUN: path set with TX muted")
    report()
    path_off()
    print("restored:")
    report()
