#!/usr/bin/env python3
"""Performance sweeps of the bit-true path with the PS weight loop.

Weights always come from the block before the one they are applied to.
  null    jammer tone rejection, normalized by the noise gain of the weights
  C/N0    estimated from 1 ms correlations: peak over off-peak power. The CW jammer
          appears as extra off-peak power, as it would in a receiver
Input noise and quantization are as set in Scenario.

Usage: model/sim_pi.py
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import crpa_model as m  # noqa: E402
from scenario import CODE_RATE, Scenario, ca_code, generate, steer  # noqa: E402


def cn0(yi, yq, sc):
    n = int(sc.fs * 1e-3)
    blocks = len(yi) // n
    t = np.arange(n) / sc.fs
    chip = np.floor(np.arange(n) * CODE_RATE / sc.fs).astype(int) % 1023
    cc = np.conj(np.fft.fft(ca_code(sc.prn)[chip]))
    tot = np.zeros(n)
    for b in range(blocks):
        v = (yi + 1j * yq)[b * n:(b + 1) * n]
        lo = np.exp(-2j * np.pi * (-sc.delta + sc.doppler) * (t + b * 1e-3))
        tot += np.abs(np.fft.ifft(np.fft.fft(v * lo) * cc)) ** 2
    k = int(np.argmax(tot))
    mask = np.ones(n, bool)
    w = int(1.5 * sc.fs / CODE_RATE)
    mask[np.arange(k - w, k + w + 1) % n] = False
    snr = tot[k] / tot[mask].mean() - 1.0
    return 10 * np.log10(snr) + 30.0 if snr > 0 else float("nan")


def tone(yi, yq, f, fs):
    t = np.arange(len(yi)) / fs
    return abs(np.mean((yi + 1j * yq) * np.exp(-2j * np.pi * f * t))) ** 2


def run(sc, load, alpha=0.0, n_block=10000):
    """Adaptive run. Reports on the samples after the first blocks have settled."""
    g = generate(sc)
    x = (g["x1i"], g["x1q"], g["x2i"], g["x2q"])
    loop = m.PiLoop(load=load, alpha=alpha)
    blocks = sc.n // n_block
    yi, yq = [], []
    w = (m.UNITY, 0, 0, 0)
    sat = 0
    wall = []
    for b in range(blocks):
        s = slice(b * n_block, (b + 1) * n_block)
        part = tuple(v[s] for v in x)
        a, c, st = m.combine(*part, w)
        yi.append(a)
        yq.append(c)
        sat += int(np.count_nonzero(st))
        wall.append(w)
        w = loop.update(m.covariance(*part), n_block)
    skip = max(1, min(blocks // 4, 4))
    yi = np.concatenate(yi[skip:])
    yq = np.concatenate(yq[skip:])
    x = tuple(v[skip * n_block:blocks * n_block] for v in x)
    wlast = wall[-1]
    gain = sum(v * v for v in wlast) / 32768.0 ** 2
    res = {"w": wlast, "sat": sat, "clip": g["clipped"], "cn0_in": cn0(x[0], x[1], sc), "cn0_out": cn0(yi, yq, sc)}
    res["rms"] = float(np.sqrt(np.mean(yi ** 2 + yq ** 2)))
    if sc.jn_db is not None:
        f = -sc.delta + sc.jam_offset
        res["null"] = 10 * np.log10(tone(x[0], x[1], f, sc.fs) / (tone(yi, yq, f, sc.fs) / gain))
    else:
        res["null"] = float("nan")
    return res


def w_txt(w):
    c1 = complex(w[0], w[1]) / 32768
    c2 = complex(w[2], w[3]) / 32768
    return "|w1| %.3f |w2| %.3f" % (abs(c1), abs(c2))


BASE = dict(n=400000, cn0_dbhz=45.0, sat_deg=-30.0, jam_deg=40.0)
print("Common: fs 10 MSPS, delta 3 MHz, C/N0 in 45 dB-Hz, sat -30 deg, jammer 40 deg, offset +200 kHz")
print("        block 1 ms unless noted; C/N0 in = element 1 with no combining, same samples\n")

print("A. J/N sweep, noise 30 LSB rms, load = 1 x noise power")
print("  J/N   clip   sat  null   C/N0in C/N0out  y rms  weights")
for jn in (None, 0, 10, 20, 30, 35, 40):
    sc = Scenario(jn_db=jn, noise_rms=30.0, **BASE)
    r = run(sc, 30.0 ** 2)
    print("%5s %6d %5d %5.1f %7.1f %7.1f %6.1f  %s" % (jn, r["clip"], r["sat"], r["null"], r["cn0_in"], r["cn0_out"], r["rms"], w_txt(r["w"])))

print("\nB. Noise level vs. quantization, J/N 30 dB, load = 1 x noise power")
print("  noise  clip  null   C/N0in C/N0out")
for nr in (2.0, 5.0, 10.0, 16.0, 30.0, 45.0):
    sc = Scenario(jn_db=30.0, noise_rms=nr, **BASE)
    r = run(sc, nr ** 2)
    print("%6.1f %6d %5.1f %7.1f %7.1f" % (nr, r["clip"], r["null"], r["cn0_in"], r["cn0_out"]))

print("\nB2. Lower RX gain for more jammer headroom: noise rms vs. largest J/N, load = 1 x noise power")
print("  noise   J/N  clip  null   C/N0in C/N0out")
for nr, jn in ((16.0, 40), (16.0, 45), (5.0, 50), (5.0, 55), (2.0, 58), (2.0, 62), (1.0, 62)):
    sc = Scenario(jn_db=jn, noise_rms=nr, **BASE)
    r = run(sc, nr ** 2)
    print("%6.1f %5d %6d %5.1f %7.1f %7.1f" % (nr, jn, r["clip"], r["null"], r["cn0_in"], r["cn0_out"]))

print("\nC. Diagonal load (x noise power), noise 30 LSB rms")
print("  load  | no jammer: C/N0out  w        | J/N 10: null C/N0out | J/N 30: null C/N0out")
for load in (0.0, 0.1, 1.0, 10.0, 100.0, 1000.0):
    a = run(Scenario(jn_db=None, noise_rms=30.0, **BASE), load * 900.0)
    b = run(Scenario(jn_db=10.0, noise_rms=30.0, **BASE), load * 900.0)
    c = run(Scenario(jn_db=30.0, noise_rms=30.0, **BASE), load * 900.0)
    print("%6.1f  | %7.1f  %s | %5.1f %7.1f | %5.1f %7.1f" % (load, a["cn0_out"], w_txt(a["w"]), b["null"], b["cn0_out"], c["null"], c["cn0_out"]))

print("\nD. Block length and smoothing, J/N 30 dB, noise 30 LSB rms, load 1")
print("  N       alpha  null  C/N0out")
for nb, al in ((100, 0.0), (1000, 0.0), (10000, 0.0), (1000, 0.5), (1000, 0.9), (10000, 0.9)):
    r = run(Scenario(jn_db=30.0, noise_rms=30.0, **BASE), 900.0, al, nb)
    print("%7d %5.1f %5.1f %7.1f" % (nb, al, r["null"], r["cn0_out"]))

print("\nE. Satellite angle, jammer 40 deg, J/N 30 dB: measured vs. theory (signal gain / noise gain)")
print("  sat   C/N0out  theory")
for sa in (-90.0, -30.0, 0.0, 20.0, 30.0, 35.0, 38.0, 40.0):
    kw = dict(BASE)
    kw["sat_deg"] = sa
    r = run(Scenario(jn_db=30.0, noise_rms=30.0, **kw), 900.0)
    d = np.angle(steer(sa) / steer(40.0))
    th = 4 * np.sin(d / 2) ** 2 / 2
    print("%6.1f %7.1f %7.1f" % (sa, r["cn0_out"], 45.0 + 10 * np.log10(th) if th > 1e-9 else float("-inf")))

print("\nF. Channel 2 mismatch, J/N 30 dB, noise 30 LSB rms, load 1")
print("  gain dB phase deg  null  C/N0out")
for gdb, ph in ((0, 0), (1, 10), (3, 77), (-6, -120)):
    r = run(Scenario(jn_db=30.0, noise_rms=30.0, ch2_gain_db=gdb, ch2_phase_deg=ph, **BASE), 900.0)
    print("%7.1f %9.1f %5.1f %7.1f" % (gdb, ph, r["null"], r["cn0_out"]))
