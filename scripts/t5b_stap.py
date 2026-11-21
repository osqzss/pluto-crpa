#!/usr/bin/env python3
"""T5b: inter-channel transfer and wideband null depth from raw captures, offline
(docs/t5b_plan.md, Section 4.5). No hardware.

Inputs are raw captures of t3_phase.py --save (int16 (n, 4): i0, q0, i1, q1 = x1, x2)
with a noise jammer and GPS off (--jam), and noise-only captures with the same
settings (--noise). fs and delta come from the JSON sidecar of the run.

1. H(f) = x2 / x1 of the jammer across --band: the cross-spectrum phase, fitted
   with a delay tau (from 32 sub-band sums, as t3_phase.py) and a constant, and
   |H|^2 = (S22 - N22) / (S11 - N11) with an amplitude slope in dB/MHz. The
   noise cross-spectrum N21 (correlated receiver noise) is subtracted from S21.
   Single-weight limits for a flat jammer of width B: delay alone
   (2 pi tau B)^2 / 12, amplitude slope s alone (s B / 8.686)^2 / 12, and both.
2. Null depth of a power-minimizing combiner with L taps per channel (L = 1 is one
   complex weight, as crpa_core), constraint: centre tap of x1 = 1, diagonal load
   --load LSB^2 per tap (crpa_ctl --load). Weights from capture i, evaluated on
   capture i + 1 (cyclic). Null depth = jammer in x1 over jammer in y in the band,
   each as power less the noise in the band (the noise of y from the noise-only
   captures through the same weights). When the residual is within the precision
   of the band power, the value is a lower bound, printed with '>'.
   Null depth is what one weight is judged by; with L > 1 taps the power
   minimization also uses the x1 taps to predict the band-limited jammer in x1
   (a temporal notch): it trades residual jammer for full-band noise, and
   notches a GPS signal in the band as well. So for every L also:
   - noise gain |w|^2 (dB), and
   - GPS loss (dB, C/A main lobe): C/N0 of a correlator after the combiner,
     against x1 alone with the jammer off, with x2/x1 of the GPS signal
     --gps PHASE,RATIO (flat; default the T5b P3 value 167.5 deg, -0.53 dB):
     loss = int(P_y S_g) / (|int(H_s S_g)|^2 int(P_n1 S_g)), H_s = W1 + W2 g_G,
     S_g the C/A sinc^2 main lobe (+/- 1.023 MHz around L1), P_y the output
     power spectrum of the test capture, P_n1 that of x1 in the noise capture.
     Negative: better than one element without a jammer.
3. The same with the fitted delay removed from x2, and with a real array's delay
   (--tau-array, default lambda/2 / c = 0.317 ns, endfire) put in its place.
   The GPS x2/x1 stays the --gps value in all three cases.

Output: one table per run on stdout; --csv appends one row per (case, L) (null
depth, noise gain, GPS loss) against bandwidth over several runs; --plot CSV PNG draws it
(needs matplotlib).

Usage:
  .venv/bin/python scripts/t5b_stap.py --jam 'tmp/t5b_cap/S-V3-N1_*_*.npy' \\
      --noise 'tmp/t5b_cap/S-V3-noise_*_*.npy' --band 0,1e6 --label S-V3-N1 \\
      --csv results/t5b_S.csv
  .venv/bin/python scripts/t5b_stap.py --selftest
"""
import argparse
import glob
import json
import os
import sys

import numpy as np

SEG = 65536
SUBBANDS = 32
C = 299792458.0
L1 = 1575420000
TAU_ARRAY = C / L1 / 2 / C       # lambda/2 at L1 over c: 0.317 ns
CA_CHIP = 1.023e6
GPS_DEFAULT = (167.5, -0.53)     # x2/x1 of the GPS carrier, T5b P3 (deg, dB)


def load(path):
    raw = np.load(path).astype(float)
    return raw[:, 0] + 1j * raw[:, 1], raw[:, 2] + 1j * raw[:, 3]


def sidecar(path):
    """The run sidecar: <label>_<date>-<time>.json next to <label>_<date>-<time>_<row>.npy."""
    base = os.path.basename(path).rsplit("_", 1)[0]
    with open(os.path.join(os.path.dirname(path), base + ".json")) as f:
        return json.load(f)


def band_bins(n, fs, delta, band):
    f = np.fft.fftfreq(n, 1.0 / fs)
    return f, abs(f + delta - band[0]) <= band[1] / 2


def spectra(caps, fs, delta, band):
    """Welch (Hann, SEG) auto and cross spectra over all captures, in the band.
    Returns f (Hz, baseband), s11, s22, s21 per bin."""
    win = np.hanning(SEG)
    acc = None
    m = 0
    for x1, x2 in caps:
        k = len(x1) // SEG
        X1 = np.fft.fft(x1[:k * SEG].reshape(k, SEG) * win, axis=1)
        X2 = np.fft.fft(x2[:k * SEG].reshape(k, SEG) * win, axis=1)
        a = np.array([(abs(X1) ** 2).sum(0), (abs(X2) ** 2).sum(0), (X2 * np.conj(X1)).sum(0)])
        acc = a if acc is None else acc + a
        m += k
    f, sel = band_bins(SEG, fs, delta, band)
    acc = acc / m
    return f[sel], acc[0][sel].real, acc[1][sel].real, acc[2][sel]


def fit_h(f, s11, s22, s21, n11, n22):
    """tau (s), phase at the band centre (deg), amplitude ratio (dB) and slope (dB/MHz),
    coherence, rms residual of the phase fit (deg)."""
    order = np.argsort(f)
    groups = np.array_split(order, SUBBANDS)
    g = np.array([s21[k].sum() for k in groups])
    fm = np.array([f[k].mean() for k in groups])
    tot = s21.sum()
    ph = np.unwrap(np.angle(g * np.conj(tot)))
    w = abs(g)
    fc = (w * fm).sum() / w.sum()
    slope = (w * (fm - fc) * ph).sum() / (w * (fm - fc) ** 2).sum()   # rad/Hz
    res = ph - (ph * w).sum() / w.sum() - slope * (fm - fc)
    a1 = np.array([max(s11[k].sum() - n11[k].sum(), 1e-30) for k in groups])
    a2 = np.array([max(s22[k].sum() - n22[k].sum(), 1e-30) for k in groups])
    adb = 10 * np.log10(a2 / a1)
    aslope = np.polyfit((fm - fc) / 1e6, adb, 1, w=w)[0]
    return {
        "tau": -slope / (2 * np.pi),
        "phase": float(np.degrees(np.angle(tot))),
        "amp_db": float(10 * np.log10(max(a2.sum(), 1e-30) / max(a1.sum(), 1e-30))),
        "amp_slope": float(aslope),
        "coh": float(abs(tot) / np.sqrt(s11.sum() * s22.sum())),
        "res_deg": float(np.degrees(np.sqrt((w * res ** 2).sum() / w.sum()))),
        "fc": float(fc),
    }


def corr(a, b, m):
    """mean(a[n] conj(b[n - m])), circular."""
    return (a * np.conj(np.roll(b, m))).mean()


def weights(x1, x2, taps, load):
    """Power-minimizing weights with the centre tap of x1 constrained to 1.
    Order: x1 taps then x2 taps, tap k = sample n - k for k in -(L-1)/2 .. (L-1)/2."""
    ks = np.arange(taps) - (taps - 1) // 2
    xs = (x1, x2)
    lags = {}
    for a in range(2):
        for b in range(2):
            for m in range(-(taps - 1), taps):
                lags[a, b, m] = corr(xs[a], xs[b], m)
    n = 2 * taps
    R = np.empty((n, n), complex)
    for i in range(n):
        for j in range(n):
            a, ki = divmod(i, taps)
            b, kj = divmod(j, taps)
            R[i, j] = lags[a, b, ks[kj] - ks[ki]]
    R += load * np.eye(n)
    e = np.zeros(n)
    e[(taps - 1) // 2] = 1.0
    v = np.linalg.solve(R, e)
    return v / np.vdot(e, v).conj(), ks


def combine(x1, x2, w, ks):
    taps = len(ks)
    y = np.zeros(len(x1), complex)
    for i, k in enumerate(ks):
        y += np.conj(w[i]) * np.roll(x1, k) + np.conj(w[taps + i]) * np.roll(x2, k)
    return y


def band_power(x, fs, delta, band):
    """Mean power in the band (LSB^2 per sample, whole-capture periodogram)."""
    f, sel = band_bins(len(x), fs, delta, band)
    return (abs(np.fft.fft(x)[sel]) ** 2).sum() / len(x) ** 2


def shift_delay(x, fs, tau):
    """Delay x by tau (s), circularly, in the frequency domain."""
    f = np.fft.fftfreq(len(x), 1.0 / fs)
    return np.fft.ifft(np.fft.fft(x) * np.exp(-2j * np.pi * f * tau))


def welch(x):
    """Welch power spectrum (Hann, SEG), per bin, fftfreq order."""
    k = len(x) // SEG
    X = np.fft.fft(x[:k * SEG].reshape(k, SEG) * np.hanning(SEG), axis=1)
    return (abs(X) ** 2).mean(0)


def gps_loss(y, n1, w, ks, fs, delta, g_gps):
    """GPS C/N0 loss (linear) after the combiner, against x1 alone without a jammer."""
    f = np.fft.fftfreq(SEG, 1.0 / fs)
    fr = f + delta                                   # relative to L1
    sg = np.where(abs(fr) <= CA_CHIP, np.sinc(fr / CA_CHIP) ** 2, 0.0)
    sg /= sg.sum()
    taps = len(ks)
    e = np.exp(-2j * np.pi * np.outer(f / fs, ks))   # (bins, taps): sample n - k
    hs = e @ np.conj(w[:taps]) + g_gps * (e @ np.conj(w[taps:]))
    return (welch(y) * sg).sum() / (abs((hs * sg).sum()) ** 2 * (welch(n1) * sg).sum())


def null_depth(jam, noise, fs, delta, band, taps, load, g_gps=None):
    """Over train/test pairs: null depth (dB), whether it is a lower bound, noise gain |w|^2 (dB),
    GPS loss (dB)."""
    if g_gps is None:
        g_gps = 10 ** (GPS_DEFAULT[1] / 20) * np.exp(1j * np.radians(GPS_DEFAULT[0]))
    out, ng, gl = [], [], []
    bound = False
    for i in range(len(jam)):
        tr = jam[i]
        te = jam[(i + 1) % len(jam)]
        nz = noise[i % len(noise)]
        w, ks = weights(tr[0], tr[1], taps, load)
        y = combine(te[0], te[1], w, ks)
        p_x1 = band_power(te[0], fs, delta, band) - band_power(nz[0], fs, delta, band)
        p_y = band_power(y, fs, delta, band)
        n_y = band_power(combine(nz[0], nz[1], w, ks), fs, delta, band)
        n_eff = len(te[0]) * band[1] / fs
        floor = 3.0 / np.sqrt(n_eff) * n_y              # 3 sigma of the band power estimate
        if p_y - n_y <= floor:
            bound = True
            out.append(p_x1 / floor)
        else:
            out.append(p_x1 / (p_y - n_y))
        ng.append(np.vdot(w, w).real)
        gl.append(gps_loss(y, nz[0], w, ks, fs, delta, g_gps))
    return (10 * np.log10(np.mean(out) if not bound else min(out)), bound,
            10 * np.log10(np.mean(ng)), 10 * np.log10(np.mean(gl)))


def nd_tau(tau, b, slope_db_mhz=0.0):
    """Single-weight null depth limit for a flat jammer of width b (Hz) with a delay tau (s)
    and an inter-channel amplitude slope (dB/MHz)."""
    x = (2 * np.pi * abs(tau) * b) ** 2 / 12 + (slope_db_mhz * b / 1e6 / (20 / np.log(10))) ** 2 / 12
    return -10 * np.log10(x) if x > 0 else float("inf")


def analyze(jam, noise, fs, delta, band, taps_list, load, tau_array, log=print, g_gps=None):
    """jam, noise: lists of (x1, x2). Returns rows (dict per case and L)."""
    f, s11, s22, s21 = spectra(jam, fs, delta, band)
    _, n11, n22, n21 = spectra(noise, fs, delta, band)
    h = fit_h(f, s11, s22, s21 - n21, n11, n22)
    log("# H(f) = x2/x1 in the band %+.0f Hz, %.0f Hz wide: tau %.3f ns, phase %.2f deg, amplitude %.3f dB, "
        "slope %.4f dB/MHz, coherence %.4f, phase residual %.3f deg rms" % (
            band[0], band[1], h["tau"] * 1e9, h["phase"], h["amp_db"], h["amp_slope"], h["coh"], h["res_deg"]))
    if h["coh"] < 0.9:
        log("# WARNING: coherence %.3f in the band: the jammer is not well above the noise, so tau and the "
            "null depths below are not meaningful" % h["coh"])
    log("# single-weight limit for this tau: %.1f dB; amplitude slope alone: %.1f dB; both: %.1f dB; "
        "for the array tau %.3f ns: %.1f dB" % (
            nd_tau(h["tau"], band[1]), nd_tau(0.0, band[1], h["amp_slope"]),
            nd_tau(h["tau"], band[1], h["amp_slope"]), tau_array * 1e9, nd_tau(tau_array, band[1])))
    cases = {
        "measured": (jam, noise),
        "delay_removed": ([(a, shift_delay(b, fs, -h["tau"])) for a, b in jam],
                          [(a, shift_delay(b, fs, -h["tau"])) for a, b in noise]),
        "array": ([(a, shift_delay(b, fs, tau_array - h["tau"])) for a, b in jam],
                  [(a, shift_delay(b, fs, tau_array - h["tau"])) for a, b in noise]),
    }
    rows = []
    log("case,taps,null_db,bound,noise_gain_db,gps_loss_db")
    for name, (j, nz) in cases.items():
        for taps in taps_list:
            nd, bound, ng, gl = null_depth(j, nz, fs, delta, band, taps, load, g_gps)
            rows.append(dict(h, case=name, taps=taps, null_db=nd, bound=bound, noise_gain=ng, gps_loss=gl))
            log("%s,%d,%s%.1f,%d,%.2f,%.2f" % (name, taps, ">" if bound else "", nd, bound, ng, gl))
    return rows


def selftest():
    rng = np.random.default_rng(7)
    fs, delta, n = 10e6, 3e6, 1 << 20
    band = (0.0, 2e6)
    F = np.fft.fftfreq(n, 1.0 / fs)
    sel = abs(F + delta) <= band[1] / 2
    tau, g = 1.2e-9, 0.9 * np.exp(1j * 1.3)
    fails = 0

    def noise():
        return rng.standard_normal(n) + 1j * rng.standard_normal(n)

    jam, nz = [], []
    for _ in range(3):
        J = np.fft.fft(noise()) * sel * 300.0                        # about 50 dB over the noise in the band
        x1 = np.fft.ifft(J) + noise()
        x2 = g * np.fft.ifft(J * np.exp(-2j * np.pi * F * tau)) + noise()
        jam.append((x1, x2))
        nz.append((noise(), noise()))
    rows = analyze(jam, nz, fs, delta, band, (1, 3), 0.1, TAU_ARRAY, log=lambda s: None)
    r = {(x["case"], x["taps"]): x for x in rows}
    h = rows[0]
    want = nd_tau(tau, band[1])
    checks = [
        ("tau fit %.3f ns (1.2)" % (h["tau"] * 1e9), abs(h["tau"] - tau) < 0.05e-9),
        ("amplitude %.3f dB (%.3f)" % (h["amp_db"], 20 * np.log10(0.9)), abs(h["amp_db"] - 20 * np.log10(0.9)) < 0.05),
        ("single weight %.1f dB (limit %.1f)" % (r["measured", 1]["null_db"], want),
         abs(r["measured", 1]["null_db"] - want) < 2.0),
        ("3 taps %.1f dB, > single + 10" % r["measured", 3]["null_db"],
         r["measured", 3]["null_db"] > r["measured", 1]["null_db"] + 10),
        ("delay removed, single %.1f dB, > limit + 10" % r["delay_removed", 1]["null_db"],
         r["delay_removed", 1]["null_db"] > want + 10),
        ("array delay, single %.1f dB (limit %.1f)" % (r["array", 1]["null_db"], nd_tau(TAU_ARRAY, band[1])),
         abs(r["array", 1]["null_db"] - nd_tau(TAU_ARRAY, band[1])) < 2.0 or r["array", 1]["bound"]),
    ]
    # GPS loss of one weight with the delay removed: residual jammer negligible, so
    # loss = (1 + 1/|g|^2) / |1 - g_G/g|^2 (signal through 1 - (g_G/g), noise of both channels)
    g_g = 10 ** (GPS_DEFAULT[1] / 20) * np.exp(1j * np.radians(GPS_DEFAULT[0]))
    want_gl = 10 * np.log10((1 + 1 / abs(g) ** 2) / abs(1 - g_g / g) ** 2)
    got_gl = r["delay_removed", 1]["gps_loss"]
    checks.append(("GPS loss, one weight, delay removed %.2f dB (%.2f)" % (got_gl, want_gl), abs(got_gl - want_gl) < 0.3))
    # amplitude slope alone: 0.5 dB/MHz over 2 MHz, no delay; the single-weight null follows nd_tau(0, B, s)
    slope = 0.5
    amp = 10 ** (slope * (F + delta) / 1e6 / 20)
    jam2 = []
    for _ in range(2):
        J = np.fft.fft(noise()) * sel * 300.0
        jam2.append((np.fft.ifft(J) + noise(), g * np.fft.ifft(J * amp) + noise()))
    f2, s11, s22, s21 = spectra(jam2, fs, delta, band)
    _, n11, n22, n21 = spectra(nz[:2], fs, delta, band)
    h2 = fit_h(f2, s11, s22, s21 - n21, n11, n22)
    nd2 = null_depth(jam2, nz[:2], fs, delta, band, 1, 0.1)[0]
    want2 = nd_tau(0.0, band[1], slope)
    checks += [
        ("amplitude slope fit %.3f dB/MHz (%.3f), tau %.3f ns (0)" % (h2["amp_slope"], slope, h2["tau"] * 1e9),
         abs(h2["amp_slope"] - slope) < 0.02 and abs(h2["tau"]) < 0.05e-9),
        ("single weight with the slope %.1f dB (limit %.1f)" % (nd2, want2), abs(nd2 - want2) < 2.0),
    ]
    for text, ok in checks:
        fails += not ok
        print("%s %s" % ("ok  " if ok else "FAIL", text))
    # weights of a known 2-tap problem: x2 = -x1 exactly gives w2 = 1 at the centre tap
    x = noise()
    w, _ = weights(x, -x, 1, 1e-9)
    ok = abs(w[0] - 1) < 1e-9 and abs(w[1] - 1) < 1e-6
    fails += not ok
    print("%s weights for x2 = -x1: %s" % ("ok  " if ok else "FAIL", np.round(w, 6)))
    print("selftest:", "PASS" if not fails else "%d FAIL" % fails)
    return 1 if fails else 0


def plot(csv_path, png):
    import csv
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    with open(csv_path) as f:
        rows = list(csv.DictReader(f))
    fig, ax = plt.subplots(figsize=(8, 5))
    for case in ("measured", "delay_removed", "array"):
        for taps in sorted({int(r["taps"]) for r in rows}):
            sel = sorted((float(r["band_hz"]), float(r["null_db"])) for r in rows
                         if r["case"] == case and int(r["taps"]) == taps)
            if sel:
                ax.plot([s[0] / 1e6 for s in sel], [s[1] for s in sel], "o-", label="%s, %d taps" % (case, taps))
    ax.set_xscale("log")
    ax.set_xlabel("Jammer bandwidth (MHz)")
    ax.set_ylabel("Null depth (dB)")
    ax.grid(True, which="both", alpha=0.4)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(png, dpi=100)
    plt.close(fig)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--jam", help="glob of jammer captures (.npy)")
    ap.add_argument("--noise", help="glob of noise-only captures (.npy)")
    ap.add_argument("--band", help="OFF,WIDTH in Hz relative to -delta")
    ap.add_argument("--taps", default="1,3,5,9")
    ap.add_argument("--load", type=float, default=24.0, help="diagonal load, LSB^2 (crpa_ctl --load)")
    ap.add_argument("--tau-array", type=float, default=TAU_ARRAY)
    ap.add_argument("--gps", default="%g,%g" % GPS_DEFAULT, help="x2/x1 of the GPS signal: PHASE_DEG,RATIO_DB")
    ap.add_argument("--label", default="")
    ap.add_argument("--csv", default=None, help="append rows to this CSV")
    ap.add_argument("--plot", nargs=2, metavar=("CSV", "PNG"))
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if a.plot:
        plot(*a.plot)
        return 0
    if not (a.jam and a.noise and a.band):
        ap.error("--jam, --noise and --band are needed")
    jf, nf = sorted(glob.glob(a.jam)), sorted(glob.glob(a.noise))
    if len(jf) < 2 or not nf:
        ap.error("need at least two jammer captures and one noise capture (%d, %d found)" % (len(jf), len(nf)))
    sj, sn = sidecar(jf[0]), sidecar(nf[0])
    for k in ("fs", "delta", "bw", "gain"):
        if sj[k] != sn[k]:
            ap.error("jammer and noise captures differ in %s (%s, %s)" % (k, sj[k], sn[k]))
    band = tuple(float(v) for v in a.band.split(","))
    taps = [int(v) for v in a.taps.split(",")]
    print("# t5b_stap.py %s: %d jammer captures (%s ...), %d noise captures; fs %s, delta %s, gain %s, load %g" % (
        a.label, len(jf), jf[0], len(nf), sj["fs"], sj["delta"], sj["gain"], a.load))
    gph, grat = (float(v) for v in a.gps.split(","))
    g_gps = 10 ** (grat / 20) * np.exp(1j * np.radians(gph))
    print("# GPS x2/x1 for the loss: %.2f deg, %.2f dB" % (gph, grat))
    rows = analyze([load(p) for p in jf], [load(p) for p in nf], float(sj["fs"]), float(sj["delta"]), band,
                   taps, a.load, a.tau_array, g_gps=g_gps)
    if a.csv:
        new = not os.path.exists(a.csv)
        with open(a.csv, "a") as f:
            if new:
                f.write("label,band_off_hz,band_hz,case,taps,null_db,bound,noise_gain_db,gps_loss_db,tau_ns,"
                        "phase_deg,amp_db,amp_slope_db_mhz,coherence,phase_res_deg,load,gps\n")
            for r in rows:
                f.write("%s,%.0f,%.0f,%s,%d,%.2f,%d,%.3f,%.3f,%.4f,%.2f,%.3f,%.4f,%.4f,%.3f,%g,%s\n" % (
                    a.label, band[0], band[1], r["case"], r["taps"], r["null_db"], r["bound"], r["noise_gain"],
                    r["gps_loss"], r["tau"] * 1e9, r["phase"], r["amp_db"], r["amp_slope"], r["coh"],
                    r["res_deg"], a.load, a.gps.replace(",", " ")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
