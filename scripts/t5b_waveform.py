#!/usr/bin/env python3
"""T5b: jammer waveform files for t4_jammer.py --waveform (docs/t5b_plan.md, 4.1).

Writes OUT.sc16 (interleaved int16 I/Q, little endian), OUT.json (sidecar with
all parameters and measured values) and OUT.png (PSD, needs matplotlib; skip
with --no-png). Files go to tmp/t5b/ by default (git-ignored).

Kinds:
  cw      a tone at --offset from the centre (0 = on the centre)
  noise   band-limited complex Gaussian noise; --bw is the 99 % power bandwidth
          (brick-wall of width bw / 0.99, applied over the whole file)
  pn      random BPSK at --chip-rate; integer samples per chip; filtered to the
          main lobe +/- chip rate unless --no-filter
  chirp   linear sawtooth from -span/2 to +span/2 in --period, integer samples
          per period; the phase is continuous at the wrap
Options for every kind:
  --pulse-period S --duty D  gate the waveform: on for the first D x period of
                             every period; the level is the level during the pulse
  --offset HZ                shift the whole waveform (for cw: the tone)

Every filter acts on the whole file in the frequency domain, and the file length
is a whole number of all periods (chirp, pulse, chip, and the offset tone), so
the file loops without a seam. --length is rounded up to that.

Level: --rms-dbfs, dBFS against 32768 (a constant baseband of 0.5 in fc32 is
-6.02 dBFS). Defaults -15 for noise, -6.02 otherwise (the T4/T5 CW drive,
docs/t5b_plan.md, 2.5).
The file is refused if any I or Q sample would exceed 32767 in magnitude.

Usage: .venv/bin/python scripts/t5b_waveform.py noise --bw 1e6 --rate 4e6 --out tmp/t5b/N1
"""
import argparse
import datetime
import hashlib
import json
import math
import os
import sys
from fractions import Fraction

import numpy as np

FULL = 32768.0
LIMIT = 32767
KINDS = ("cw", "noise", "pn", "chirp")
VERSION = 1
CW_DBFS = 20 * math.log10(0.5)     # the t4_jammer.py CW: constant 0.5 in fc32


def as_int(x, what):
    """x as an int if it is within 1e-6 of one, else ValueError."""
    r = round(x)
    if r < 1 or abs(x - r) > 1e-6 * max(1.0, abs(x)):
        raise ValueError("%s is %.9g, not a whole number of samples" % (what, x))
    return int(r)


def lcm(a, b):
    return a * b // math.gcd(a, b)


def offset_period(offset, rate, max_samples):
    """Samples after which exp(j 2 pi offset n / rate) repeats. ValueError if that
    is more than max_samples or the phase error at the wrap over max_samples is
    above 1e-6 cycles."""
    if offset == 0:
        return 1
    fr = Fraction(offset / rate).limit_denominator(int(max_samples))
    if fr == 0 or abs(float(fr) - offset / rate) * max_samples > 1e-6:
        raise ValueError("offset %.6g Hz does not make whole cycles within --length; choose an offset "
                         "with a period that divides the file" % offset)
    return fr.denominator


def brickwall(x, rate, lo, hi):
    """Keep the bins with lo <= f <= hi (Hz) of the whole-file FFT."""
    f = np.fft.fftfreq(len(x), 1.0 / rate)
    X = np.fft.fft(x)
    X[(f < lo) | (f > hi)] = 0
    return np.fft.ifft(X)


def generate(kind, rate, length, seed=1, bw=None, chip_rate=1.023e6, pn_filter=True, span=None,
             period=None, offset=0.0, pulse_period=None, duty=None):
    """Return (complex baseband at unit rms during the pulse, params dict)."""
    if kind not in KINDS:
        raise ValueError("unknown kind '%s'" % kind)
    p = {"kind": kind, "rate": rate, "offset": offset, "seed": seed}
    per = offset_period(offset, rate, max(1.0, round(length * rate)))
    if kind == "noise":
        if not bw or bw <= 0 or bw / 0.99 >= rate:
            raise ValueError("noise needs 0 < bw / 0.99 < rate")
        p["bw"] = bw
    elif kind == "pn":
        spc = as_int(rate / chip_rate, "rate / chip rate")
        per = lcm(per, spc)
        if pn_filter and 2 * chip_rate >= rate:
            raise ValueError("the main-lobe filter needs rate > 2 x chip rate")
        p.update(chip_rate=chip_rate, samples_per_chip=spc, pn_filter=pn_filter)
    elif kind == "chirp":
        if not span or not period:
            raise ValueError("chirp needs --span and --period")
        if span >= rate:
            raise ValueError("chirp span must be below the rate")
        per = lcm(per, as_int(rate * period, "chirp period x rate"))
        p.update(span=span, period=period)
    if pulse_period is not None:
        if duty is None or not 0 < duty < 1:
            raise ValueError("pulsed needs 0 < duty < 1")
        pp = as_int(rate * pulse_period, "pulse period x rate")
        as_int(rate * pulse_period * duty, "pulse on time x rate")
        per = lcm(per, pp)
        p.update(pulse_period=pulse_period, duty=duty)
    n = int(math.ceil(round(length * rate, 6) / per)) * per
    if offset:
        offset_period(offset, rate, n)      # phase error over the final length
    p.update(n=n, length=n / rate, loop_period_samples=per)
    rng = np.random.default_rng(seed)
    t = np.arange(n) / rate
    if kind == "cw":
        x = np.ones(n, complex)
    elif kind == "noise":
        x = rng.standard_normal(n) + 1j * rng.standard_normal(n)
        x = brickwall(x, rate, -bw / 0.99 / 2, bw / 0.99 / 2)
    elif kind == "pn":
        chips = rng.integers(0, 2, n // spc) * 2 - 1
        x = np.repeat(chips, spc).astype(complex)
        if pn_filter:
            x = brickwall(x, rate, -chip_rate, chip_rate)
    else:
        m = as_int(rate * period, "chirp period x rate")
        tp = np.arange(m) / rate
        ph = 2 * np.pi * (-span / 2 * tp + span / (2 * period) * tp ** 2)
        x = np.tile(np.exp(1j * ph), n // m)
    if offset:
        x = x * np.exp(2j * np.pi * offset * t)
    on = np.ones(n, bool)
    if pulse_period is not None:
        pp = as_int(rate * pulse_period, "pulse period x rate")
        k = as_int(rate * pulse_period * duty, "pulse on time x rate")
        on = (np.arange(n) % pp) < k
        x = x * on
    x = x / np.sqrt((abs(x[on]) ** 2).mean())
    return x, p, on


def occupied(x, rate, frac=0.99):
    """(99 % bandwidth, power centroid) from the whole-file periodogram, in Hz."""
    f = np.fft.fftshift(np.fft.fftfreq(len(x), 1.0 / rate))
    pw = np.fft.fftshift(abs(np.fft.fft(x)) ** 2)
    c = np.cumsum(pw) / pw.sum()
    lo = f[np.searchsorted(c, (1 - frac) / 2)]
    hi = f[np.searchsorted(c, 1 - (1 - frac) / 2)]
    return float(hi - lo), float((f * pw).sum() / pw.sum())


def quantize(x, rms_dbfs):
    """Scale to rms_dbfs (during the pulse) and round to int16. ValueError on clipping."""
    a = FULL * 10 ** (rms_dbfs / 20)
    y = x * a
    peak = max(abs(y.real).max(), abs(y.imag).max())
    if np.round(peak) > LIMIT:
        raise ValueError("clipping: the largest I/Q sample would be %.0f (limit %d) at %.2f dBFS rms; "
                         "lower --rms-dbfs" % (peak, LIMIT, rms_dbfs))
    q = np.empty(2 * len(y), "<i2")
    q[0::2] = np.round(y.real)
    q[1::2] = np.round(y.imag)
    return q


def stats(q, on, rate):
    z = q[0::2].astype(float) + 1j * q[1::2].astype(float)
    pw = abs(z) ** 2
    bw99, cen = occupied(z, rate)
    return {
        "rms_dbfs": 10 * np.log10(pw.mean() / FULL ** 2),
        "rms_dbfs_on": 10 * np.log10(pw[on].mean() / FULL ** 2),
        "peak_abs_iq": int(abs(q.astype(int)).max()),
        "peak_dbfs": 10 * np.log10(pw.max() / FULL ** 2),
        "crest_db": 10 * np.log10(pw.max() / pw[on].mean()),
        "bw99_hz": bw99,
        "centroid_hz": cen,
        "duty_measured": float(on.mean()),
    }


def psd(z, rate, seg=4096):
    """Averaged Hann periodogram, dB relative to full scale per bin; (f, dB)."""
    nseg = max(1, len(z) // seg)
    seg = min(seg, len(z))
    w = np.hanning(seg)
    X = np.fft.fft(z[:nseg * seg].reshape(nseg, seg) * w, axis=1)
    p = (abs(X) ** 2).mean(axis=0) / (FULL ** 2 * (w ** 2).sum())
    f = np.fft.fftshift(np.fft.fftfreq(seg, 1.0 / rate))
    return f, 10 * np.log10(np.fft.fftshift(p) + 1e-30)


def write_png(path, q, rate, title):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    z = q[0::2].astype(float) + 1j * q[1::2].astype(float)
    f, db = psd(z, rate)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(f / 1e6, db, lw=0.8)
    ax.set_xlabel("Frequency from the centre (MHz)")
    ax.set_ylabel("dB full scale per bin (Hann, 4096)")
    ax.set_title(title)
    ax.grid(True, alpha=0.4)
    fig.tight_layout()
    fig.savefig(path, dpi=100)
    plt.close(fig)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("kind", choices=KINDS)
    ap.add_argument("--rate", type=float, required=True, help="sample rate in Hz")
    ap.add_argument("--length", type=float, default=1.0, help="seconds, rounded up to whole periods")
    ap.add_argument("--out", required=True, help="path without extension")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--bw", type=float, help="noise: 99 %% bandwidth in Hz")
    ap.add_argument("--chip-rate", type=float, default=1.023e6)
    ap.add_argument("--no-filter", action="store_true", help="pn: rectangular chips")
    ap.add_argument("--span", type=float, help="chirp: span in Hz")
    ap.add_argument("--period", type=float, help="chirp: sweep period in s")
    ap.add_argument("--offset", type=float, default=0.0, help="Hz from the centre")
    ap.add_argument("--pulse-period", type=float)
    ap.add_argument("--duty", type=float)
    ap.add_argument("--rms-dbfs", type=float, help="rms level during the pulse")
    ap.add_argument("--no-png", action="store_true")
    a = ap.parse_args(argv)
    rms = a.rms_dbfs if a.rms_dbfs is not None else (-15.0 if a.kind == "noise" else CW_DBFS)
    try:
        x, p, on = generate(a.kind, a.rate, a.length, a.seed, a.bw, a.chip_rate, not a.no_filter,
                            a.span, a.period, a.offset, a.pulse_period, a.duty)
        q = quantize(x, rms)
    except ValueError as e:
        print("REFUSED: %s" % e, file=sys.stderr)
        return 2
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    data = q.tobytes()
    with open(a.out + ".sc16", "wb") as f:
        f.write(data)
    p.update(stats(q, on, a.rate))
    p.update(format="sc16 interleaved int16 I/Q, little endian", full_scale=FULL, rms_dbfs_target=rms,
             file=os.path.basename(a.out + ".sc16"), bytes=len(data),
             sha256=hashlib.sha256(data).hexdigest(), generator="t5b_waveform.py v%d" % VERSION,
             command=" ".join(sys.argv if argv is None else ["t5b_waveform.py"] + list(argv)),
             created=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    with open(a.out + ".json", "w") as f:
        json.dump(p, f, indent=1, sort_keys=True)
        f.write("\n")
    msg = ("%s: %d samples (%.3f s) at %.0f Hz, rms %.2f dBFS (%.2f in the pulse), crest %.1f dB, "
           "peak %d, bw99 %.0f Hz" % (a.out, p["n"], p["length"], a.rate, p["rms_dbfs"], p["rms_dbfs_on"],
                                      p["crest_db"], p["peak_abs_iq"], p["bw99_hz"]))
    if not a.no_png:
        write_png(a.out + ".png", q, a.rate, "%s: %s" % (os.path.basename(a.out), a.kind))
        msg += ", PSD in %s.png" % a.out
    print(msg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
