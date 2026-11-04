#!/usr/bin/env python3
"""Digital loopback check of the FPGA data path on a Pluto, over libiio.

Path: DMA -> tx_upack -> axi_ad9361 -> AD9361 data port loop (debugfs loopback=1)
-> axi_ad9361 -> cpack -> DMA.

Each TX stream carries its own full-period 12-bit sequence, so a stuck bit, a
swapped stream or a sample offset between streams cannot pass. A control run
with loopback=0 must not match. Does not test the AD9361 analog or RF paths.
Runs with the AD9361 internal FIR off: enabling it needs a valid filter loaded,
which sets the driver's tx_fir_int and rx_fir_dec.

TX_LO is powered down and TX attenuation is at maximum for the whole test.
Previous settings are restored on exit and printed.

Usage: scripts/loopback_test.py [uri]   (default ip:192.168.2.1)
Needs iio_attr, iio_readdev, iio_writedev. Python standard library only.
"""
import os
import struct
import subprocess
import sys
import tempfile
import time

URI = sys.argv[1] if len(sys.argv) > 1 else "ip:192.168.2.1"
N = 4096
RX_DEV = "cf-ad9361-lpc"
TX_DEV = "cf-ad9361-dds-core-lpc"
PHY = ("-c", "ad9361-phy")
# Odd multipliers give a full period modulo 4096.
SEQ = [(1, 0), (1597, 5), (2741, 11), (3301, 17)]
FULL_RATE_RATES = [30720000, 10000000, 3000000, 2100000, 2084000]
REFUSED_NO_FIR = [2083333, 2000000]


def attr(*args):
    p = subprocess.run(["iio_attr", "-u", URI] + list(args),
                       capture_output=True, text=True, timeout=20)
    return p.returncode, (p.stdout + p.stderr).strip()


def get(*args):
    return attr(*args)[1]


def s12(v):
    v &= 0xfff
    return v - 4096 if v >= 2048 else v


def stream(idx):
    m, c = SEQ[idx]
    return [s12(n * m + c) for n in range(N)]


def num_channels():
    out = get("-c", RX_DEV)
    return sum(1 for ch in ("voltage0", "voltage1", "voltage2", "voltage3")
               if "'%s' (input" % ch in out)


def write_tx(path, streams):
    with open(path, "wb") as f:
        for n in range(N):
            for s in streams:
                # The DAC uses the upper 12 of 16 bits.
                f.write(struct.pack("<h", s[n] << 4))


def start_tx(path, chans):
    f = open(path, "rb")
    p = subprocess.Popen(["iio_writedev", "-u", URI, "-c", "-b", str(N), "-s", str(N), TX_DEV]
                         + ["voltage%d" % c for c in chans],
                         stdin=f, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    time.sleep(2)
    return p, f


def stop_tx(p, f):
    p.terminate()
    try:
        p.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        p.kill()
        p.communicate()
    f.close()


def capture(chans):
    want = N * 2
    p = subprocess.run(["iio_readdev", "-u", URI, "-b", str(want), "-s", str(want), RX_DEV]
                       + ["voltage%d" % c for c in chans],
                       capture_output=True, timeout=30)
    frame = 2 * len(chans)
    frames = len(p.stdout) // frame
    vals = struct.unpack("<%dh" % (frames * len(chans)), p.stdout[:frames * frame])
    return [list(vals[i::len(chans)]) for i in range(len(chans))]


def check(tx_chans, rx_chans, tmp):
    """Return (ok, text). RX channel c must carry TX channel c at a common offset."""
    path = os.path.join(tmp, "tx.bin")
    write_tx(path, [stream(c) for c in tx_chans])
    p, f = start_tx(path, tx_chans)
    rx = capture(rx_chans)
    alive = p.poll() is None
    stop_tx(p, f)
    ok = alive and bool(rx) and len(rx[0]) == N * 2
    parts = []
    offsets = set()
    for pos, c in enumerate(rx_chans):
        ref = stream(c)
        index = {v: i for i, v in enumerate(ref)}
        if not rx[pos]:
            ok = False
            parts.append("ch%d:empty" % c)
            continue
        k = index[rx[pos][0]]
        offsets.add(k)
        bad = sum(1 for j, v in enumerate(rx[pos]) if v != ref[(k + j) % N])
        ok = ok and bad == 0
        parts.append("ch%d:bad=%d" % (c, bad))
    ok = ok and len(offsets) == 1
    n = len(rx[0]) if rx else 0
    return ok, "n=%d offsets=%s tx_running=%s %s" % (n, sorted(offsets), alive, " ".join(parts))


def main():
    nch = num_channels()
    if nch not in (2, 4):
        print("unexpected channel count:", nch)
        return 2
    all_ch = list(range(nch))
    print("uri:", URI, "| channels:", nch, "|", get("-C", "fw_version"))
    print(get("-C", "hw_model"))
    tx_gains = ["voltage0"] + (["voltage1"] if nch == 4 else [])
    saved = {
        "lo": get("-o", *PHY, "altvoltage1", "powerdown"),
        "gain": {c: get("-o", *PHY, c, "hardwaregain").split()[0] for c in tx_gains},
        "fs": get("-i", *PHY, "voltage0", "sampling_frequency"),
        "fir": get("-c", "ad9361-phy", "out", "voltage_filter_fir_en"),
        "lb": get("-D", "ad9361-phy", "loopback"),
    }
    print("saved:", saved)
    tmp = tempfile.mkdtemp()
    fails = 0

    def result(label, ok, text):
        nonlocal fails
        fails += 0 if ok else 1
        print("  %-26s %s  %s" % (label, "PASS" if ok else "FAIL", text))

    def loop(on):
        attr("-D", "ad9361-phy", "loopback", "1" if on else "0")

    def set_rate(fs):
        rc, out = attr("-i", *PHY, "voltage0", "sampling_frequency", str(fs))
        return rc, out

    def rate_cases(rates, tag):
        nonlocal fails
        for fs in rates:
            rc, out = set_rate(fs)
            print("\nfs=%d %s: rc=%d phy=%s" % (fs, tag, rc, get("-i", *PHY, "voltage0", "sampling_frequency")))
            print("  " + get("-d", "ad9361-phy", "rx_path_rates"))
            if rc:
                fails += 1
                print("  FAIL rate refused:", out[:100])
                continue
            loop(True)
            ok, text = check(all_ch, all_ch, tmp)
            result("loop=1", ok, text)
            loop(False)
            ok, text = check(all_ch, all_ch, tmp)
            # The control passes only if the data does not match.
            result("loop=0 control", not ok, text)

    try:
        attr("-o", *PHY, "altvoltage1", "powerdown", "1")
        for c in tx_gains:
            attr("-o", *PHY, c, "hardwaregain", "-89.75")
        print("safety: TX_LO powerdown", get("-o", *PHY, "altvoltage1", "powerdown"),
              "| TX gain", [get("-o", *PHY, c, "hardwaregain") for c in tx_gains])
        if saved["lo"] == "" or get("-o", *PHY, "altvoltage1", "powerdown") != "1":
            print("safety setting not confirmed, stopping")
            return 2

        rate_cases(FULL_RATE_RATES, "(FIR off)")
        for fs in REFUSED_NO_FIR:
            rc, _ = set_rate(fs)
            print("refused without FIR? fs=%d rc=%d" % (fs, rc))

        if nch == 4:
            print("\nchannel enables at 10 MSPS")
            set_rate(10000000)
            loop(True)
            for label, tx_ch, rx_ch in (("TX all, RX ch0/1", all_ch, [0, 1]),
                                        ("TX all, RX ch2/3", all_ch, [2, 3]),
                                        ("TX ch0/1, RX ch0/1", [0, 1], [0, 1]),
                                        ("TX ch2/3, RX ch2/3", [2, 3], [2, 3])):
                ok, text = check(tx_ch, rx_ch, tmp)
                result(label, ok, text)
            loop(False)

    finally:
        print("\nrestore rc:",
              attr("-D", "ad9361-phy", "loopback", saved["lb"] or "0")[0],
              attr("-i", *PHY, "voltage0", "sampling_frequency", "3000000")[0],
              attr("-c", "ad9361-phy", "out", "voltage_filter_fir_en", saved["fir"] or "0")[0],
              attr("-i", *PHY, "voltage0", "sampling_frequency", saved["fs"])[0],
              [attr("-o", *PHY, c, "hardwaregain", saved["gain"][c])[0] for c in tx_gains],
              attr("-o", *PHY, "altvoltage1", "powerdown", saved["lo"])[0])
        print("after: fs", get("-i", *PHY, "voltage0", "sampling_frequency"),
              "gain", [get("-o", *PHY, c, "hardwaregain") for c in tx_gains],
              "lo_pd", get("-o", *PHY, "altvoltage1", "powerdown"),
              "fir", get("-c", "ad9361-phy", "out", "voltage_filter_fir_en"),
              "loop", get("-D", "ad9361-phy", "loopback"))
    print("\nFAILS:", fails)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
