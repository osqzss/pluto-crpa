#!/usr/bin/env python3
"""RX-only GPS L1 C/A check on a Pluto in 2R2T, over libiio. Never enables TX.

Powers TX_LO down, tunes RX LO to L1 + delta, captures both channels with identical
manual gain, and searches every PRN at both +delta and -delta baseband offsets.
A signal found at -delta means the I/Q order at RF is as plan Section 4.1 assumes;
which stream shows the signal identifies the RX connector.

Settings are left applied, with TX_LO down, and printed.

Usage: scripts/gps_rx_check.py [--gain dB] [--delta Hz] [--fs Hz] [--uri URI]
Needs iio_attr, iio_readdev, numpy.
"""
import argparse
import subprocess

import numpy as np

L1 = 1575420000
CODE_RATE = 1023000.0
G2_TAPS = {1: (2, 6), 2: (3, 7), 3: (4, 8), 4: (5, 9), 5: (1, 9), 6: (2, 10), 7: (1, 8),
           8: (2, 9), 9: (3, 10), 10: (2, 3), 11: (3, 4), 12: (5, 6), 13: (6, 7), 14: (7, 8),
           15: (8, 9), 16: (9, 10), 17: (1, 4), 18: (2, 5), 19: (3, 6), 20: (4, 7), 21: (5, 8),
           22: (6, 9), 23: (1, 3), 24: (4, 6), 25: (5, 7), 26: (6, 8), 27: (7, 9), 28: (8, 10),
           29: (1, 6), 30: (2, 7), 31: (3, 8), 32: (4, 9)}

ap = argparse.ArgumentParser()
ap.add_argument("--uri", default="ip:192.168.2.1")
ap.add_argument("--gain", type=int, default=60)
ap.add_argument("--delta", type=int, default=3000000)
ap.add_argument("--fs", type=int, default=10000000)
ap.add_argument("--bw", type=int, default=9000000)
args = ap.parse_args()


def attr(*a):
    p = subprocess.run(["iio_attr", "-u", args.uri, *a], capture_output=True, text=True, timeout=20)
    if p.returncode:
        raise RuntimeError(" ".join(a) + ": " + (p.stdout + p.stderr).strip())
    return p.stdout.strip()


def phy(direction, chan, name, *val):
    return attr(direction, "-c", "ad9361-phy", chan, name, *val)


def ca_code(prn):
    g1 = [1] * 10
    g2 = [1] * 10
    s1, s2 = G2_TAPS[prn]
    out = []
    for _ in range(1023):
        out.append(g1[9] ^ g2[s1 - 1] ^ g2[s2 - 1])
        f1 = g1[2] ^ g1[9]
        f2 = g2[1] ^ g2[2] ^ g2[5] ^ g2[7] ^ g2[8] ^ g2[9]
        g1 = [f1] + g1[:9]
        g2 = [f2] + g2[:9]
    return 1 - 2 * np.array(out, dtype=float)


def search(x, fs, center):
    """Non-coherent 1 ms search, 10 blocks, Doppler +/-10 kHz in 500 Hz steps."""
    n = int(round(fs * 1e-3))
    blocks = min(10, len(x) // n)
    t = np.arange(n) / fs
    dopplers = np.arange(-10000, 10001, 500)
    idx = (np.floor(np.arange(n) * CODE_RATE / fs).astype(int)) % 1023
    results = []
    data = x[:blocks * n].reshape(blocks, n)
    # Precompute FFTs per Doppler by mixing
    spectra = {}
    for d in dopplers:
        lo = np.exp(-2j * np.pi * (center + d) * t)
        spectra[d] = np.fft.fft(data * lo, axis=1)
    for prn in sorted(G2_TAPS):
        cc = np.conj(np.fft.fft(ca_code(prn)[idx]))
        best = (0.0, 0, 0, 0.0)
        for d in dopplers:
            corr = np.abs(np.fft.ifft(spectra[d] * cc, axis=1)) ** 2
            s = corr.sum(axis=0)
            k = int(np.argmax(s))
            # peak over mean excluding +/- 1.5 chips around the peak
            mask = np.ones(n, bool)
            w = int(1.5 * fs / CODE_RATE)
            mask[np.arange(k - w, k + w + 1) % n] = False
            ratio = s[k] / s[mask].mean()
            if ratio > best[0]:
                best = (ratio, int(d), k, s[mask].std() / s[mask].mean())
        results.append((prn,) + best)
    return results


phy("-o", "altvoltage1", "powerdown", "1")
if phy("-o", "altvoltage1", "powerdown") != "1":
    raise SystemExit("TX_LO did not power down")
phy("-i", "voltage0", "sampling_frequency", str(args.fs))
phy("-i", "voltage0", "rf_bandwidth", str(args.bw))
phy("-o", "altvoltage0", "frequency", str(L1 + args.delta))
for ch in ("voltage0", "voltage1"):
    phy("-i", ch, "gain_control_mode", "manual")
    phy("-i", ch, "hardwaregain", str(args.gain))
fs = float(phy("-i", "voltage0", "sampling_frequency"))
print("RX LO", phy("-o", "altvoltage0", "frequency"), "| fs", fs, "| rf_bw", phy("-i", "voltage0", "rf_bandwidth"),
      "| gain", phy("-i", "voltage0", "hardwaregain"), "/", phy("-i", "voltage1", "hardwaregain"),
      "| TX_LO powerdown", phy("-o", "altvoltage1", "powerdown"))

N = int(fs * 0.02)
raw = subprocess.run(["iio_readdev", "-u", args.uri, "-b", str(N), "-s", str(N), "cf-ad9361-lpc",
                      "voltage0", "voltage1", "voltage2", "voltage3"],
                     capture_output=True, timeout=60).stdout
v = np.frombuffer(raw, dtype="<i2").astype(float).reshape(-1, 4)
rx = {"ch0/1": v[:, 0] + 1j * v[:, 1], "ch2/3": v[:, 2] + 1j * v[:, 3]}
print("samples", len(v))
for name, x in rx.items():
    x = x - x.mean()
    peak = max(np.abs(x.real).max(), np.abs(x.imag).max())
    print("%s: rms %.1f LSB (%.1f dBFS), peak %d, rssi %s" % (
        name, np.sqrt((abs(x) ** 2).mean()), 10 * np.log10((abs(x) ** 2).mean() / 2048 ** 2),
        peak, phy("-i", "voltage0" if name == "ch0/1" else "voltage1", "rssi")))
    P = np.abs(np.fft.fftshift(np.fft.fft(x[: len(x) // 200 * 200].reshape(200, -1), axis=1))) ** 2
    P = P.mean(axis=0)
    f = np.fft.fftshift(np.fft.fftfreq(P.size, 1 / fs))
    db = 10 * np.log10(P / np.median(P))
    top = np.argsort(db)[-5:][::-1]
    print("   strongest bins (MHz, dB over median):",
          ", ".join("%.3f:%.1f" % (f[k] / 1e6, db[k]) for k in top))
    bands = [(-4, -2), (2, 4), (-1, 1)]
    print("   band power dB rel. median:", ", ".join(
        "%+d..%+d MHz %.1f" % (a, b, 10 * np.log10(P[(f > a * 1e6) & (f < b * 1e6)].mean() / np.median(P)))
        for a, b in bands))
    for sign, label in ((-1, "-delta (expected)"), (1, "+delta (mirrored)")):
        res = sorted(search(x, fs, sign * args.delta), key=lambda r: -r[1])[:5]
        print("   %s: best PRN ratio/Doppler/codephase: %s" % (label, ", ".join(
            "G%02d %.1f %+dHz %d" % (r[0], r[1], r[2], r[3]) for r in res)))
