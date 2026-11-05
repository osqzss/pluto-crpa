#!/usr/bin/env python3
"""Check the axi_ad9361 interface facts of docs/interface.md on a running Pluto.

Reads core registers over libiio and measures l_clk with the core's clock monitor at
a few sample rates. Needs no firmware change and no RF connection. TX_LO is powered
down during the rate changes. Previous settings are restored on exit and printed.

Usage: scripts/if_check.py [uri]   (default ip:192.168.2.1)
Needs iio_attr and iio_reg. Python standard library only.
"""
import subprocess
import sys
import time

URI = sys.argv[1] if len(sys.argv) > 1 else "ip:192.168.2.1"
ADC = "cf-ad9361-lpc"
PHY = "ad9361-phy"
CORE = 0x80000000  # DEBUGFS_DRA_PCORE_REG_MAGIC: core register, not AD9361 SPI
AXI_HZ = 100e6
RATES = [30720000, 10000000, 3000000]
errors = 0


def run(*cmd):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    if p.returncode != 0:
        raise RuntimeError("%s: %s" % (" ".join(cmd), (p.stdout + p.stderr).strip()))
    return p.stdout.strip()


def attr(*args):
    return run("iio_attr", "-u", URI, *args)


def reg(addr):
    return int(run("iio_reg", "-u", URI, ADC, hex(CORE | addr)), 0)


def spi(addr):
    return int(run("iio_reg", "-u", URI, PHY, hex(addr)), 0)


def check(ok, text):
    global errors
    errors += 0 if ok else 1
    print("%s  %s" % ("PASS" if ok else "FAIL", text))


def fs_attr(*value):
    return attr("-i", "-c", PHY, "voltage0", "sampling_frequency", *value)


def lo_pd(*value):
    return attr("-o", "-c", PHY, "altvoltage1", "powerdown", *value)


saved_fs = fs_attr()
saved_lo = lo_pd()
print("before: fs", saved_fs, "| TX_LO powerdown", saved_lo)
print("AD9361 parallel port conf 0x010-0x012:", [hex(spi(a)) for a in (0x010, 0x011, 0x012)])

check((reg(0x0044) >> 2) & 1 == 0, "adc r1_mode = 0 (2R2T)")
check((reg(0x4048) >> 5) & 1 == 0, "dac r1_mode = 0 (2R2T)")
check(reg(0x404c) & 0xffff == 1, "dac rate = 1 (one sample every 2 l_clk)")
check(reg(0x005c) & 1 == 1, "reg 0x005c bit 0: adc_status (rx frame toggling, delay locked)")
for ch in range(4):
    ctrl = reg(0x0400 + ch * 0x40)
    print("ch%d: adc CHAN_CNTRL 0x%08x, IQCOR coeffs 0x%08x, dac data_sel %d, dac iqcor_enb %d"
          % (ch, ctrl, reg(0x0414 + ch * 0x40), reg(0x4418 + ch * 0x40) & 0xf,
             (reg(0x4414 + ch * 0x40) >> 2) & 1))
    check(ctrl & 0x50 == 0x50, "ch%d sign extension on" % ch)
    check(ctrl & 0x100 == 0, "ch%d DC filter off" % ch)

try:
    lo_pd("1")
    if lo_pd() != "1":
        raise RuntimeError("TX_LO did not power down")
    for fs in RATES:
        fs_attr(str(fs))
        time.sleep(2)  # the monitor window is 65536 / 100 MHz; let it refresh
        got = int(fs_attr())
        lclk = reg(0x0054) * AXI_HZ / 65536
        ratio = lclk / got
        print("fs %d: l_clk %.3f MHz, ratio %.3f" % (got, lclk / 1e6, ratio))
        check(abs(ratio - 2) < 0.02, "l_clk = 2 x fs at fs = %d" % got)
        check(reg(0x005c) & 1 == 1, "adc_status set at fs = %d" % got)
        print("dac data_sel after rate change:", [reg(0x4418 + c * 0x40) & 0xf for c in range(4)])
finally:
    fs_attr("3000000")
    fs_attr(saved_fs)
    lo_pd(saved_lo)
    print("after: fs", fs_attr(), "| TX_LO powerdown", lo_pd())

print("RESULT", "PASS" if errors == 0 else "FAIL errors=%d" % errors)
sys.exit(1 if errors else 0)
