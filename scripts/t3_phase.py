#!/usr/bin/env python3
"""T3: inter-channel amplitude and phase of RX2 against RX1, RX-only, over libiio.

Captures raw x1 (ch0/1) and x2 (ch2/3) and reports, per capture:
  wideband  R11, R22, R21 = sum x2 conj(x1), as crpa_core integrates them:
            level of each channel, x2/x1 ratio, |rho| and the phase of R21
  CW        the same ratio and phase in the FFT bins of the strongest line near
            -delta (the bladeRF carrier at L1), with its SNR

Never enables TX. At the start the TX LO is powered down and both TX attenuations
are set to maximum; both are read back at the start and at the end. The TX LO
frequency is not written. Note (docs/interface.md, Section 5): a bandwidth write
or a sample rate change runs a TX quad calibration, which powers the TX LO up for
a moment at its parked frequency, at maximum attenuation. Bandwidth is therefore
only written when it differs; the fs sequence cannot avoid it.

The capture mux of crpa_core must be at reset (raw ADC data): run after a reboot
or after `crpa_ctl off`. It cannot be read over libiio.

Sequences (--seq):
  one       --count captures at the given settings (default sequence)
  retune    --count times: RX LO to --away, back to L1 + delta, capture
  rewrite   --count times: write the same RX LO frequency again, capture
  fs        --count times: fs to --fs-alt, back to --fs, capture
  delta     one capture group per value of --deltas
  gain      one capture group per value of --gains (same on both channels)
  selftest  check the analysis on synthetic data; no Pluto needed

T4 additions (docs/t4_plan.md):
  --cw-offset HZ[,HZ]  centre of the line search is -delta + offset; with two or
                       more values every capture gives one row per offset
  --cw-span HZ         half width of the line search (default 200e3)
  --cap y              the capture mux is in CAP_SEL (ch0/1 = y, ch2/3 = x1): the
                       columns named x1 hold y and those named x2 hold x1, so
                       cw_ratio is the line in x1 over the line in y
  --passive            write nothing to the Pluto: for captures while a crpa_ctl
                       dry run is active. The TX state must already be safe and
                       LO, fs and gain must already match; only --seq one

Usage: .venv/bin/python scripts/t3_phase.py --seq retune --count 30 --label B
Log: results/t3_<label>_<date>-<time>.txt (or --log). Needs iio_attr, iio_readdev, numpy.
"""
import argparse
import datetime
import subprocess
import sys
import time

import numpy as np

L1 = 1575420000
TX_MAX_ATT = -89.75
SEG = 65536          # FFT length of the CW analysis

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--uri", default="ip:192.168.2.1")
ap.add_argument("--seq", default="one",
                choices=["one", "retune", "rewrite", "fs", "delta", "gain", "selftest"])
ap.add_argument("--label", default="", help="run label, written to every row and the log name")
ap.add_argument("--count", type=int, default=10)
ap.add_argument("--per", type=int, default=1, help="captures per step in the stepped sequences")
ap.add_argument("--interval", type=float, default=0.0, help="seconds between captures (seq one)")
ap.add_argument("--delta", type=int, default=3000000)
ap.add_argument("--fs", type=int, default=10000000)
ap.add_argument("--bw", type=int, default=9000000)
ap.add_argument("--gain", type=int, default=60)
ap.add_argument("--samples", type=int, default=1 << 20, help="samples per capture")
ap.add_argument("--settle", type=float, default=0.5, help="seconds after a setting change")
ap.add_argument("--away", type=int, default=2400000000, help="RX LO of the away step (seq retune)")
ap.add_argument("--fs-alt", type=int, default=30720000)
ap.add_argument("--deltas", default="2e6,3e6,4e6,5e6,-3e6")
ap.add_argument("--gains", default="40,45,50,55,60,65,70")
ap.add_argument("--cw-offset", default="0", help="line search centre(s) relative to -delta, Hz")
ap.add_argument("--cw-span", type=float, default=200e3, help="half width of the line search, Hz")
ap.add_argument("--cap", default="raw", choices=["raw", "y"], help="capture mux state (labels only)")
ap.add_argument("--passive", action="store_true", help="no writes to the Pluto")
ap.add_argument("--note", default="", help="free text for the log header (cabling, source)")
ap.add_argument("--log", default=None)
args = ap.parse_args()
try:
    OFFSETS = [float(v) for v in args.cw_offset.split(",")]
except ValueError:
    ap.error("--cw-offset needs numbers")
if args.passive and args.seq != "one":
    ap.error("--passive only works with --seq one")

log_file = None


def out(line):
    print(line, flush=True)
    if log_file:
        log_file.write(line + "\n")
        log_file.flush()


def attr(*a):
    p = subprocess.run(["iio_attr", "-u", args.uri, *a], capture_output=True, text=True, timeout=30)
    if p.returncode:
        raise RuntimeError(" ".join(a) + ": " + (p.stdout + p.stderr).strip())
    return p.stdout.strip()


def phy(direction, chan, name, *val):
    return attr(direction, "-c", "ad9361-phy", chan, name, *val)


def num(text):
    """First number of an attribute value such as '60.000000 dB'."""
    return float(text.split()[0])


def analyze(x1, x2, fs, delta, offsets=(0.0,), span=200e3):
    """Return one dict of wideband and CW results per line offset. x1, x2: complex
    arrays, LSB. The line is searched within span of -delta + offset."""
    x1 = x1 - x1.mean()
    x2 = x2 - x2.mean()
    r11 = float((abs(x1) ** 2).mean())
    r22 = float((abs(x2) ** 2).mean())
    r21 = complex((x2 * np.conj(x1)).mean())
    res = {
        "p1": 10 * np.log10(r11 / 2048.0 ** 2),
        "p2": 10 * np.log10(r22 / 2048.0 ** 2),
        "ratio": 10 * np.log10(r22 / r11),
        "rho": abs(r21) / np.sqrt(r11 * r22),
        "phase": float(np.degrees(np.angle(r21))),
        "peak": int(max(abs(x1.real).max(), abs(x1.imag).max(), abs(x2.real).max(), abs(x2.imag).max())),
    }
    nseg = len(x1) // SEG
    if nseg < 1:
        res.update(f_cw=float("nan"), cw_snr=float("nan"), cw_snr2=float("nan"), cw_ratio=float("nan"),
                   cw_phase=float("nan"))
        return [dict(res, off=o) for o in offsets]
    win = np.hanning(SEG)
    X1 = np.fft.fft(x1[:nseg * SEG].reshape(nseg, SEG) * win, axis=1)
    X2 = np.fft.fft(x2[:nseg * SEG].reshape(nseg, SEG) * win, axis=1)
    f = np.fft.fftfreq(SEG, 1.0 / fs)
    p1 = (abs(X1) ** 2).mean(axis=0)
    p2 = (abs(X2) ** 2).mean(axis=0)
    results = []
    for off in offsets:
        near = np.flatnonzero(abs(f + delta - off) <= span)
        k = int(near[np.argmax(p1[near] + p2[near])])
        bins = np.arange(k - 1, k + 2) % SEG      # Hann main lobe
        s11 = p1[bins].sum()
        s22 = p2[bins].sum()
        s21 = (X2[:, bins] * np.conj(X1[:, bins])).mean(axis=0).sum()
        results.append(dict(
            res, off=off, f_cw=float(f[k]),
            cw_snr=10 * np.log10(p1[k] / np.median(p1[near])),
            cw_snr2=10 * np.log10(p2[k] / np.median(p2[near])),
            cw_ratio=10 * np.log10(s22 / s11), cw_phase=float(np.degrees(np.angle(s21)))))
    return results


def selftest():
    rng = np.random.default_rng(1)
    fs, delta, n = 10e6, 3e6, 1 << 20
    t = np.arange(n) / fs
    fails = 0
    for amp_db, ph, cw in ((-0.4, 173.0, 12.0), (1.0, -45.0, 12.0), (0.0, 10.0, 20.0)):
        g = 10 ** (amp_db / 20) * np.exp(1j * np.radians(ph))
        s = cw * np.exp(2j * np.pi * (-delta + 12345.0) * t)
        x1 = s + 15 * (rng.standard_normal(n) + 1j * rng.standard_normal(n)) + (3 - 2j)
        x2 = g * s + 15 * (rng.standard_normal(n) + 1j * rng.standard_normal(n)) + (1 + 1j)
        r = analyze(x1, x2, fs, delta)[0]
        dphi = (r["phase"] - ph + 180) % 360 - 180
        dcw = (r["cw_phase"] - ph + 180) % 360 - 180
        ok = (abs(dphi) < 1.0 and abs(dcw) < 0.3 and abs(r["cw_ratio"] - amp_db) < 0.05
              and abs(r["f_cw"] - (-delta + 12345.0)) < fs / SEG)
        fails += not ok
        print("%s set %.1f dB %.1f deg: wide %.2f deg rho %.3f | cw %.3f dB %.2f deg at %.0f Hz, %.1f dB" % (
            "ok  " if ok else "FAIL", amp_db, ph, r["phase"], r["rho"], r["cw_ratio"], r["cw_phase"],
            r["f_cw"], r["cw_snr"]))
    # no common signal: |rho| near 1/sqrt(n)
    x1 = 15 * (rng.standard_normal(n) + 1j * rng.standard_normal(n))
    x2 = 15 * (rng.standard_normal(n) + 1j * rng.standard_normal(n))
    r = analyze(x1, x2, fs, delta)[0]
    ok = r["rho"] < 0.005
    fails += not ok
    print("%s noise only: rho %.4f" % ("ok  " if ok else "FAIL", r["rho"]))
    # two lines with different inter-channel phase and ratio, read from one capture
    n1 = 15 * (rng.standard_normal(n) + 1j * rng.standard_normal(n))
    n2 = 15 * (rng.standard_normal(n) + 1j * rng.standard_normal(n))
    sa = 5.0 * np.exp(2j * np.pi * (-delta - 5000.0) * t)             # weak line, 173 deg, -0.3 dB
    sb = 150.0 * np.exp(2j * np.pi * (-delta + 200e3 + 2500.0) * t)   # strong line, 60 deg, +0.5 dB
    ga = 10 ** (-0.3 / 20) * np.exp(1j * np.radians(173.0))
    gb = 10 ** (0.5 / 20) * np.exp(1j * np.radians(60.0))
    ra, rb = analyze(n1 + sa + sb, n2 + ga * sa + gb * sb, fs, delta, offsets=(0.0, 200e3), span=50e3)
    for r, ph, db, name in ((ra, 173.0, -0.3, "weak line at offset 0"), (rb, 60.0, 0.5, "strong line at +200 kHz")):
        d = (r["cw_phase"] - ph + 180) % 360 - 180
        ok = abs(d) < 1.0 and abs(r["cw_ratio"] - db) < 0.1
        fails += not ok
        print("%s two lines, %s: cw %.3f dB %.2f deg at %.0f Hz, %.1f / %.1f dB" % (
            "ok  " if ok else "FAIL", name, r["cw_ratio"], r["cw_phase"], r["f_cw"], r["cw_snr"], r["cw_snr2"]))
    # a 40 dB null: line in ch2/3 (x1) over the line in ch0/1 (y), as with --cap y
    r = analyze(n1 + 0.01 * sb, n2 + sb, fs, delta, offsets=(200e3,), span=50e3)[0]
    ok = abs(r["cw_ratio"] - 40.0) < 0.5
    fails += not ok
    print("%s null of 40 dB: cw_ratio %.2f dB, line in y %.1f dB over the floor" % (
        "ok  " if ok else "FAIL", r["cw_ratio"], r["cw_snr"]))
    print("selftest:", "PASS" if not fails else "%d FAIL" % fails)
    return 1 if fails else 0


if args.seq == "selftest":
    sys.exit(selftest())


def tx_state():
    down = phy("-o", "altvoltage1", "powerdown")
    a1 = num(phy("-o", "voltage0", "hardwaregain"))
    a2 = num(phy("-o", "voltage1", "hardwaregain"))
    lo = phy("-o", "altvoltage1", "frequency")
    return down, a1, a2, lo


def tx_safe():
    """Power the TX LO down and set maximum attenuation; read back."""
    phy("-o", "altvoltage1", "powerdown", "1")
    for ch in ("voltage0", "voltage1"):
        phy("-o", ch, "hardwaregain", str(TX_MAX_ATT))
    down, a1, a2, lo = tx_state()
    if down != "1" or abs(a1 - TX_MAX_ATT) > 1e-6 or abs(a2 - TX_MAX_ATT) > 1e-6:
        raise SystemExit("TX not safe: powerdown %s, attenuation %g / %g dB" % (down, a1, a2))
    return "TX LO powerdown %s at %s Hz, TX attenuation %g / %g dB" % (down, lo, -a1, -a2)


def set_lo(freq):
    phy("-o", "altvoltage0", "frequency", str(freq))
    got = int(phy("-o", "altvoltage0", "frequency"))
    if abs(got - freq) > 10:
        raise SystemExit("RX LO reads %d, wanted %d" % (got, freq))


def set_fs(fs):
    phy("-i", "voltage0", "sampling_frequency", str(fs))
    got = num(phy("-i", "voltage0", "sampling_frequency"))
    if abs(got - fs) > 10:
        raise SystemExit("fs reads %.0f, wanted %d" % (got, fs))


def set_bw(bw):
    if abs(num(phy("-i", "voltage0", "rf_bandwidth")) - bw) > 1000:
        phy("-i", "voltage0", "rf_bandwidth", str(bw))
    got = num(phy("-i", "voltage0", "rf_bandwidth"))
    if abs(got - bw) > 1000:
        raise SystemExit("rf_bandwidth reads %.0f, wanted %d" % (got, bw))


def set_gain(gain):
    for ch in ("voltage0", "voltage1"):
        if phy("-i", ch, "gain_control_mode") != "manual":
            phy("-i", ch, "gain_control_mode", "manual")
        phy("-i", ch, "hardwaregain", str(gain))
    for ch in ("voltage0", "voltage1"):
        got = num(phy("-i", ch, "hardwaregain"))
        if got != gain or phy("-i", ch, "gain_control_mode") != "manual":
            raise SystemExit("%s RX gain reads %g, wanted %d manual" % (ch, got, gain))


def temperature():
    try:
        return "%.1f" % (num(phy("-i", "temp0", "input")) / 1000.0)
    except (RuntimeError, ValueError, IndexError):
        return "nan"


def capture():
    n = args.samples
    p = subprocess.run(["iio_readdev", "-u", args.uri, "-b", str(n), "-s", str(n), "cf-ad9361-lpc",
                        "voltage0", "voltage1", "voltage2", "voltage3"], capture_output=True, timeout=120)
    v = np.frombuffer(p.stdout[:len(p.stdout) // 8 * 8], dtype="<i2").astype(float).reshape(-1, 4)
    if len(v) != n:
        raise RuntimeError("capture returned %d of %d samples: %s" % (len(v), n, p.stderr.decode()[-200:]))
    return v[:, 0] + 1j * v[:, 1], v[:, 2] + 1j * v[:, 3]


COLS = ("row,label,step,t_s,rxlo_hz,fs_hz,gain_db,temp_c,p1_dbfs,p2_dbfs,ratio_db,rho,phase_deg,"
        "f_cw_hz,cw_snr_db,cw_ratio_db,cw_phase_deg,peak,cw_offset_hz,cw_snr2_db")
rows = []
t0 = time.time()


def measure(step, delta, fs, gain):
    x1, x2 = capture()
    t = time.time() - t0
    temp = temperature()
    for r in analyze(x1, x2, float(fs), float(delta), OFFSETS, args.cw_span):
        rows.append(r)
        out("%d,%s,%s,%.1f,%d,%d,%d,%s,%.2f,%.2f,%.3f,%.4f,%.2f,%.0f,%.1f,%.3f,%.2f,%d,%.0f,%.1f" % (
            len(rows) - 1, args.label, step, t, L1 + delta, fs, gain, temp,
            r["p1"], r["p2"], r["ratio"], r["rho"], r["phase"], r["f_cw"], r["cw_snr"], r["cw_ratio"],
            r["cw_phase"], r["peak"], r["off"], r["cw_snr2"]))


def circ(deg):
    """Circular mean and spread (max deviation from the mean) in degrees."""
    z = np.exp(1j * np.radians(np.asarray(deg)))
    m = np.degrees(np.angle(z.mean()))
    d = (np.asarray(deg) - m + 180) % 360 - 180
    return m, d.std(), abs(d).max()


def summary():
    if not rows:
        return
    wide = [r for r in rows if r["off"] == OFFSETS[0]]      # one per capture
    m, s, mx = circ([r["phase"] for r in wide])
    out("# wideband phase: mean %.2f deg, std %.2f, max deviation %.2f (%d captures)" % (m, s, mx, len(wide)))
    a = np.array([r["ratio"] for r in wide])
    out("# wideband x2/x1: mean %.3f dB, std %.3f, range %.3f to %.3f" % (a.mean(), a.std(), a.min(), a.max()))
    for off in OFFSETS:
        sel = [r for r in rows if r["off"] == off]
        tag = "" if len(OFFSETS) == 1 and off == 0 else " (offset %+.0f Hz)" % off
        m, s, mx = circ([r["cw_phase"] for r in sel])
        out("# CW phase%s: mean %.2f deg, std %.2f, max deviation %.2f (%d captures)" % (tag, m, s, mx, len(sel)))
        a = np.array([r["cw_ratio"] for r in sel])
        out("# CW x2/x1%s: mean %.3f dB, std %.3f, range %.3f to %.3f" % (tag, a.mean(), a.std(), a.min(), a.max()))
        if tag:
            b = np.array([r["cw_snr"] for r in sel])
            c = np.array([r["cw_snr2"] for r in sel])
            out("# CW line over the floor%s: ch0/1 %.1f dB, ch2/3 %.1f dB (means), at %.0f Hz" % (
                tag, b.mean(), c.mean(), np.median([r["f_cw"] for r in sel])))
    a = np.array([r["rho"] for r in wide])
    out("# |rho|: mean %.4f, range %.4f to %.4f; peak |x| %d LSB" % (
        a.mean(), a.min(), a.max(), max(r["peak"] for r in rows)))


stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
log_name = args.log or "results/t3_%s_%s.txt" % (args.label or args.seq, stamp)
log_file = open(log_name, "w")
rc = 0
try:
    out("# t3_phase.py %s, seq %s, label '%s'" % (stamp, args.seq, args.label))
    out("# command: " + " ".join(sys.argv))
    out("# note: " + args.note)
    if args.passive:
        down, a1, a2, lo = tx_state()
        if down != "1" or abs(a1 - TX_MAX_ATT) > 1e-6 or abs(a2 - TX_MAX_ATT) > 1e-6:
            raise RuntimeError("passive: TX is not in the safe state (powerdown %s, attenuation %g / %g dB); "
                               "nothing written" % (down, -a1, -a2))
        out("# start (passive, nothing written): TX LO powerdown %s at %s Hz, TX attenuation %g / %g dB" % (
            down, lo, -a1, -a2))
        got = (int(phy("-o", "altvoltage0", "frequency")), num(phy("-i", "voltage0", "sampling_frequency")),
               num(phy("-i", "voltage0", "hardwaregain")), num(phy("-i", "voltage1", "hardwaregain")))
        if (abs(got[0] - (L1 + args.delta)) > 10 or abs(got[1] - args.fs) > 10
                or got[2] != args.gain or got[3] != args.gain):
            raise RuntimeError("passive: the Pluto has LO %d, fs %.0f, gain %g / %g; expected %d, %d, %d" % (
                got[0], got[1], got[2], got[3], L1 + args.delta, args.fs, args.gain))
    else:
        out("# start: " + tx_safe())
        set_fs(args.fs)
        set_bw(args.bw)
        set_lo(L1 + args.delta)
        set_gain(args.gain)
        time.sleep(args.settle)
    out("# RX LO %s Hz (L1 %+d), fs %s, rf_bw %s, gain %s / %s, %d samples per capture" % (
        phy("-o", "altvoltage0", "frequency"), args.delta, phy("-i", "voltage0", "sampling_frequency"),
        phy("-i", "voltage0", "rf_bandwidth"), phy("-i", "voltage0", "hardwaregain"),
        phy("-i", "voltage1", "hardwaregain"), args.samples))
    out("# tracking: quadrature %s, rf_dc %s, bb_dc %s" % (
        phy("-i", "voltage0", "quadrature_tracking_en"), phy("-i", "voltage0", "rf_dc_offset_tracking_en"),
        phy("-i", "voltage0", "bb_dc_offset_tracking_en")))
    out("# phase = arg(sum x2 conj(x1)), ratio = x2/x1 power; cw_* in the 3 bins of the strongest line "
        "within %.0f Hz of -delta + cw_offset (%s)" % (args.cw_span, args.cw_offset))
    if args.cap == "y":
        out("# capture mux CAP_SEL: columns x1 = y (ch0/1), columns x2 = x1 (ch2/3); "
            "cw_ratio = line in x1 over line in y")
    out(COLS)
    if args.seq == "one":
        for i in range(args.count):
            measure("one", args.delta, args.fs, args.gain)
            time.sleep(args.interval)
    elif args.seq in ("retune", "rewrite"):
        for i in range(args.count):
            if args.seq == "retune":
                set_lo(args.away)
                time.sleep(args.settle)
            set_lo(L1 + args.delta)
            time.sleep(args.settle)
            for _ in range(args.per):
                measure("%s%d" % (args.seq, i), args.delta, args.fs, args.gain)
    elif args.seq == "fs":
        for i in range(args.count):
            set_fs(args.fs_alt)
            time.sleep(args.settle)
            set_fs(args.fs)
            set_bw(args.bw)
            time.sleep(args.settle)
            for _ in range(args.per):
                measure("fs%d" % i, args.delta, args.fs, args.gain)
    elif args.seq == "delta":
        for d in [int(float(v)) for v in args.deltas.split(",")]:
            set_lo(L1 + d)
            time.sleep(args.settle)
            for _ in range(args.per):
                measure("delta%+d" % d, d, args.fs, args.gain)
        set_lo(L1 + args.delta)
    elif args.seq == "gain":
        for g in [int(v) for v in args.gains.split(",")]:
            set_gain(g)
            time.sleep(args.settle)
            for _ in range(args.per):
                measure("gain%d" % g, args.delta, args.fs, g)
        set_gain(args.gain)
    summary()
except (RuntimeError, subprocess.TimeoutExpired) as e:
    out("# ERROR: %s" % e)
    rc = 1
except KeyboardInterrupt:
    out("# interrupted")
    summary()
    rc = 130
finally:
    try:
        down, a1, a2, lo = tx_state()
        safe = down == "1" and abs(a1 - TX_MAX_ATT) < 1e-6 and abs(a2 - TX_MAX_ATT) < 1e-6
        out("# end: TX LO powerdown %s at %s Hz, TX attenuation %g / %g dB%s" % (
            down, lo, -a1, -a2, "" if safe else "  ** TX STATE NOT SAFE **"))
        rc = rc or (0 if safe else 1)
    except (RuntimeError, subprocess.TimeoutExpired) as e:
        out("# end: TX state not read: %s" % e)
        rc = rc or 1
    out("# log: " + log_name)
    log_file.close()
sys.exit(rc)
