#!/usr/bin/env python3
"""T5: one row per jammer step of a receiver run (docs/t5_plan.md, Section 4.2).

Inputs of one run:
  --jammer   the t4_jammer.py log: T0 line and STATE lines (host unix time)
  --ubx      the u-blox log with its .idx (scripts/ubx_log.py)
  --csv      the crpa_ctl CSV (every row, every 10th or every 100th block)
  --t1       the T1 reference log (default results/t1_ref_20261107_123927.ubx)

Steps are the STATE lines of the jammer log. The window of a step runs from
--settle seconds after its start to --guard seconds before the next one, as in
T4. The first step starts at T0 (the cold start); its window starts at
--first-from seconds after T0 (default 60 s, the T4 reference window).

The reference of the run is the window of one step (--ref-step, default: the
first step whose state is off). C/N0 is given against it and against T1.

crpa_ctl has only a monotonic clock, so its CSV is placed on the host time
axis by fitting: the offset is the one at which the x1 level (p1_dbfs) is most
constant within the steps (least within-step variance). The offset found and
the remaining scatter are printed; --csv-offset S sets it by hand instead
(host time of CSV t_s = 0, in seconds from T0).

--cal "GAIN:JN60,..." gives J/N60 per jammer USRP gain (from P2), printed as a
column. Without it the column is the x1 level over the reference window.

Usage: scripts/t5_steps.py --jammer results/t5_G60F_jammer.txt \
           --ubx results/t5_G60F.ubx --csv results/t5_G60F.csv [--cal 55:20.9,...]
"""
import argparse
import csv
import math
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ubx_cn0  # noqa: E402

STATE = re.compile(r"^\S+ ([0-9.]+) STATE (?:gain ([0-9.]+) dB|(off))")
T0 = re.compile(r"^\S+ ([0-9.]+) T0\b")
STOP = re.compile(r"^\S+ ([0-9.]+) (?:stopping|JAMMER OFF)")


def read_jammer(path):
    """Return t0 (unix), [(unix time, gain or None for off)] and the stop time."""
    t0, states, stop = None, [], None
    with open(path) as f:
        for line in f:
            m = T0.match(line)
            if m:
                t0 = float(m.group(1))
                continue
            m = STATE.match(line)
            if m:
                states.append((float(m.group(1)), None if m.group(3) else float(m.group(2))))
                continue
            m = STOP.match(line)
            if m and stop is None:
                stop = float(m.group(1))
    if not states:
        raise SystemExit("%s: no STATE lines" % path)
    if t0 is None:
        t0 = states[0][0]       # no cold start (N runs): time counts from the first STATE line
    return t0, states, stop


def steps_from(t0, states, end):
    """Steps relative to t0: [(start, stop, gain)]. States before t0 are folded
    into the first step, which starts at 0."""
    rel = [(t - t0, g) for t, g in states]
    before = [x for x in rel if x[0] <= 0]
    after = [x for x in rel if x[0] > 0]
    seq = ([(0.0, before[-1][1])] if before else []) + after
    out = []
    for i, (s, g) in enumerate(seq):
        stop = seq[i + 1][0] if i + 1 < len(seq) else end
        out.append((s, stop, g))
    return out


def read_csv(path):
    cols = {k: [] for k in ("t_s", "sat", "peak1", "peak2", "missed", "status",
                            "w1i", "w1q", "w2i", "w2q", "p1_dbfs", "p2_dbfs", "py_dbfs")}
    with open(path) as f:
        for row in csv.DictReader(f):
            if row.get("flag") == "discard":
                continue
            try:
                vals = {k: float(row[k]) for k in cols}
            except (KeyError, ValueError):
                continue        # a cut-off last line
            for k, v in vals.items():
                cols[k].append(v)
    return {k: np.array(v) for k, v in cols.items()}


def fit_offset(t, p1, steps, lo, hi, res=0.1):
    """Offset o (host time of t = 0, from t0) minimizing the within-step variance
    of p1 over the steps. Returns o and the rms scatter about the step means."""
    # 10 Hz medians keep the search cheap whatever the CSV density
    bins = np.floor(t / 0.1).astype(int)
    keys, idx = np.unique(bins, return_index=True)
    tm = keys * 0.1 + 0.05
    pm = np.array([np.median(p1[a:b]) for a, b in zip(idx, list(idx[1:]) + [len(p1)])])
    edges = np.array([s for s, _, _ in steps[1:]])
    c1 = np.concatenate([[0.0], np.cumsum(pm)])
    c2 = np.concatenate([[0.0], np.cumsum(pm ** 2)])
    best = (math.inf, None)
    for o in np.arange(lo, hi, res):
        cut = np.searchsorted(tm + o, edges)
        b = np.concatenate([[0], cut, [len(pm)]])
        n = np.diff(b)
        s1 = c1[b[1:]] - c1[b[:-1]]
        s2 = c2[b[1:]] - c2[b[:-1]]
        ok = n > 0
        sse = float((s2[ok] - s1[ok] ** 2 / n[ok]).sum())
        if sse < best[0]:
            best = (sse, o)
    return best[1], math.sqrt(best[0] / len(pm))


def cn0(path, t0, a, b):
    pvt, sat, hw = ubx_cn0.parse(path, 0, (t0, a, b))
    return pvt, sat, hw, ubx_cn0.summary(pvt, sat)


def mean_diff(res, ref):
    d = [res[sv][0] - ref[sv][0] for sv in res if sv in ref]
    return (sum(d) / len(d), len(d)) if d else (float("nan"), 0)


def rng(v, fmt="%d"):
    return (fmt + " to " + fmt) % (min(v), max(v)) if v else "-"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--jammer", required=True)
    ap.add_argument("--ubx", required=True)
    ap.add_argument("--csv")
    ap.add_argument("--t1", default="results/t1_ref_20261107_123927.ubx")
    ap.add_argument("--settle", type=float, default=15.0)
    ap.add_argument("--guard", type=float, default=5.0)
    ap.add_argument("--first-from", type=float, default=60.0)
    ap.add_argument("--ref-step", type=int, help="index of the reference step (default: first off step)")
    ap.add_argument("--csv-offset", type=float, help="host time of CSV t_s = 0, seconds from T0")
    ap.add_argument("--cal", default="", help="GAIN:JN60,... from P2")
    a = ap.parse_args()

    t0, states, stop = read_jammer(a.jammer)
    end = (stop if stop is not None else max(t for t, _ in states) + 60.0) - t0
    steps = steps_from(t0, states, end)
    cal = {}
    for item in filter(None, a.cal.split(",")):
        g, j = item.split(":")
        cal[float(g)] = float(j)

    wins = []
    for i, (s, e, g) in enumerate(steps):
        lo = a.first_from if i == 0 else s + a.settle
        wins.append((lo, e - a.guard))
    ref_i = a.ref_step
    if ref_i is None:
        offs = [i for i, (_, _, g) in enumerate(steps) if g is None]
        ref_i = offs[0] if offs else 0
    ref = cn0(a.ubx, t0, *wins[ref_i])[3]
    t1 = ubx_cn0.summary(*ubx_cn0.parse(a.t1, 0)[:2])

    d = None
    if a.csv:
        d = read_csv(a.csv)
        if a.csv_offset is not None:
            off, scat = a.csv_offset, float("nan")
        else:
            span = d["t_s"][-1]
            off, scat = fit_offset(d["t_s"], d["p1_dbfs"], steps, -span, end)
        d["t"] = d["t_s"] + off
        print("CSV %s: %d rows, t_s = 0 at %+.1f s from T0%s" % (
            a.csv, len(d["t_s"]), off, "" if math.isnan(scat) else
            " (fitted, x1 scatter about the step means %.2f dB)" % scat))
    print("Jammer log %s: T0 %.3f, %d steps; reference step %d (window %.0f to %.0f s)" % (
        a.jammer, t0, len(steps), ref_i, *wins[ref_i]))
    print("u-blox log %s; T1 reference %s" % (a.ubx, a.t1))
    print()
    print("| Step | Jammer | J/N60 or x1 over ref. | Window (s) | C/N0 against ref. | Against T1 | PRNs | "
          "SVs used | 3D fix | AGC | Jamming ind. | x1 / y dBFS | Peak | Sat. blocks | Missed | \\|w2\\| | STATUS |")
    print("|" + "---|" * 17)
    xref = None
    if d is not None:
        lo, hi = wins[ref_i]
        sel = (d["t"] >= lo) & (d["t"] < hi)
        xref = float(10 * np.log10(np.mean(10 ** (d["p1_dbfs"][sel] / 10)))) if sel.any() else None
    for i, ((s, e, g), (lo, hi)) in enumerate(zip(steps, wins)):
        jam = "off" if g is None else "%g dB" % g
        if hi <= lo:
            print("| %d | %s | - | too short | - | - | - | - | - | - | - | - | - | - | - | - | - |" % (i, jam))
            continue
        pvt, sat, hw, res = cn0(a.ubx, t0, lo, hi)
        dr, nr = mean_diff(res, ref)
        dt, _ = mean_diff(res, t1)
        used = [sum(1 for _, u in svs.values() if u) for _, svs in sat]
        fixes = sum(1 for x in pvt if x[1] == 3 and x[2])
        lvl = py = pk = satb = miss = w2 = stat = "-"
        jn = ("%.1f" % cal[g]) if g is not None and g in cal else "-"
        if d is not None:
            m = (d["t"] >= lo) & (d["t"] < hi)
            if m.any():
                x1 = float(10 * np.log10(np.mean(10 ** (d["p1_dbfs"][m] / 10))))
                lvl = "%.2f / %.2f" % (x1, 10 * np.log10(np.mean(10 ** (d["py_dbfs"][m] / 10))))
                pk = "%d" % max(d["peak1"][m].max(), d["peak2"][m].max())
                satb = "%d" % int((d["sat"][m] > 0).sum())
                miss = "%d" % int(d["missed"][m].max() - d["missed"][m].min())
                w1 = np.hypot(d["w1i"][m], d["w1q"][m])
                w2 = "%.3f" % float(np.mean(np.hypot(d["w2i"][m], d["w2q"][m]) / np.maximum(w1, 1)))
                stat = ",".join("%d" % v for v in np.unique(d["status"][m]))
                if jn == "-" and xref is not None:
                    jn = "%+.1f dB" % (x1 - xref)
        print("| %d | %s | %s | %.0f to %.0f | %s | %s | %d | %s | %d of %d | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            i, jam, jn, lo, hi, "-" if nr == 0 else "%+.2f dB" % dr,
            "-" if not res else "%+.2f dB" % dt, len(res), rng(used),
            fixes, len(pvt), rng([h[1] for h in hw]), rng([h[2] for h in hw]), lvl, pk, satb, miss, w2, stat))


if __name__ == "__main__":
    main()
