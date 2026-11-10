#!/usr/bin/env python3
"""Per-PRN C/N0 and MON-HW summary from a raw u-blox log (gpspipe -R).

Reads NAV-PVT, NAV-SAT and MON-HW (u-blox 8, protocol 18). For each GPS PRN,
C/N0 is averaged over the NAV-SAT epochs where the SV is flagged used in the
solution. Optional --skip drops the first seconds of the log (acquisition).
Optional --cut DB ends the log at the first epoch (after --skip) whose mean
C/N0 over the used SVs is more than DB below the median of those epoch means:
the signal path was switched off there (quit), and the fading epochs after it
would bias the averages. MON-HW is cut at the same point (1 Hz assumed).
Prints a Markdown table; with --ref, a second log is the reference column.

Windows by host time (T4, docs/t4_plan.md): --from SEC and --to SEC keep the
frames received in that window. They need the index LOG.ubx.idx written by
scripts/ubx_log.py. The seconds count from --t0 (unix time, e.g. the T0 line of
the jammer log); without --t0, from the start of the log. --ref-from and
--ref-to do the same for the reference log, which may be the same file.
--skip and --cut are not used together with a window.

Usage: scripts/ubx_cn0.py LOG.ubx [--ref REF.ubx] [--skip SEC] [--cut DB]
       scripts/ubx_cn0.py LOG.ubx --t0 UNIX --from 255 --to 295 \
           --ref LOG.ubx --ref-from 60 --ref-to 175
"""
import argparse
import bisect
import struct


def frames(data):
    """Yield (cls, id, payload) for every UBX frame with a valid checksum."""
    i = 0
    n = len(data)
    while i + 8 <= n:
        if data[i] != 0xB5 or data[i + 1] != 0x62:
            i += 1
            continue
        cls, mid, length = data[i + 2], data[i + 3], struct.unpack_from("<H", data, i + 4)[0]
        end = i + 6 + length
        if end + 2 > n:
            break
        ck_a = ck_b = 0
        for b in data[i + 2:end]:
            ck_a = (ck_a + b) & 0xFF
            ck_b = (ck_b + ck_a) & 0xFF
        if ck_a == data[end] and ck_b == data[end + 1]:
            yield cls, mid, bytes(data[i + 6:end]), i
            i = end + 2
        else:
            i += 1


def load_index(path):
    """Read LOG.ubx.idx: lists of chunk times and chunk byte offsets."""
    times, offsets = [], []
    with open(path + ".idx") as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            t, o = line.split()
            times.append(float(t))
            offsets.append(int(o))
    if not times:
        raise SystemExit("%s.idx has no entries" % path)
    return times, offsets


def parse(path, skip, window=None):
    """window: None or (t0, t_from, t_to); t0 None means the start of the log."""
    with open(path, "rb") as f:
        data = f.read()
    keep = None
    if window is not None:
        times, offsets = load_index(path)
        t0 = times[0] if window[0] is None else window[0]
        lo = -float("inf") if window[1] is None else t0 + window[1]
        hi = float("inf") if window[2] is None else t0 + window[2]

        def keep(pos):
            t = times[max(0, bisect.bisect_right(offsets, pos) - 1)]
            return lo <= t < hi
    pvt, sat, hw = [], [], []
    for cls, mid, p, pos in frames(data):
        if keep is not None and not keep(pos):
            continue
        if (cls, mid) == (0x01, 0x07) and len(p) >= 92:
            itow = struct.unpack_from("<I", p, 0)[0]
            pvt.append((itow, p[20], p[21] & 1, p[23], struct.unpack_from("<I", p, 40)[0]))
        elif (cls, mid) == (0x01, 0x35) and len(p) >= 8:
            itow, num = struct.unpack_from("<I", p, 0)[0], p[5]
            svs = {}
            for k in range(num):
                o = 8 + 12 * k
                if o + 12 > len(p):
                    break
                gnss, sv, cno = p[o], p[o + 1], p[o + 2]
                flags = struct.unpack_from("<I", p, o + 8)[0]
                if gnss == 0:
                    svs[sv] = (cno, bool(flags & 0x08))
            sat.append((itow, svs))
        elif (cls, mid) == (0x0A, 0x09) and len(p) >= 60:
            noise, agc = struct.unpack_from("<HH", p, 16)
            hw.append((noise, agc, p[45]))
    if skip and sat:
        t0 = sat[0][0]
        sat = [s for s in sat if (s[0] - t0) % (7 * 86400000) >= skip * 1000]
        if pvt:
            t0 = pvt[0][0]
            pvt = [s for s in pvt if (s[0] - t0) % (7 * 86400000) >= skip * 1000]
        hw = hw[int(skip):]     # MON-HW carries no time; 1 Hz assumed
    return pvt, sat, hw


def cut_at_drop(pvt, sat, hw, db):
    """Keep the log up to the last epoch whose mean used C/N0 is within db of the
    median epoch mean; drop the epochs after it (the fade after the signal path
    was switched off). Returns the lists and the seconds dropped at the end
    of the log, or None if nothing was dropped."""
    means = []
    for _, svs in sat:
        c = [cno for cno, used in svs.values() if used]
        means.append(sum(c) / len(c) if c else None)
    vals = sorted(m for m in means if m is not None)
    if not vals:
        return pvt, sat, hw, None
    med = vals[len(vals) // 2]
    last = max(i for i, m in enumerate(means) if m is not None and m >= med - db)
    if last == len(sat) - 1:
        return pvt, sat, hw, None
    # Times are measured back from the end of the log: after a cold start the
    # receiver time is wrong until the first fix, so the start is no reference.
    week = 7 * 86400000
    tl, tend = sat[last][0], sat[-1][0]
    drop = ((tend - tl) % week) // 1000
    sat = sat[:last + 1]
    pvt = [x for x in pvt if (tl - x[0]) % week < week // 2]
    hw = hw[:max(0, len(hw) - drop)]
    keep = drop
    return pvt, sat, hw, keep


def summary(pvt, sat):
    per = {}
    for _, svs in sat:
        for sv, (cno, used) in svs.items():
            if used:
                per.setdefault(sv, []).append(cno)
    return {sv: (sum(v) / len(v), min(v), max(v), len(v)) for sv, v in per.items()}


def rng(values):
    return "%d-%d" % (min(values), max(values)) if values else "-"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("log")
    ap.add_argument("--ref")
    ap.add_argument("--skip", type=float, default=0.0, help="seconds dropped at the start")
    ap.add_argument("--cut", type=float, help="end at the first epoch whose mean used C/N0 "
                    "is more than this many dB below the median (signal path switched off)")
    ap.add_argument("--t0", type=float, help="unix time of second 0 of the windows (default: log start)")
    ap.add_argument("--from", dest="t_from", type=float, help="window start, seconds from t0 (needs .idx)")
    ap.add_argument("--to", dest="t_to", type=float, help="window end, seconds from t0 (needs .idx)")
    ap.add_argument("--ref-from", type=float, help="window start in the reference log")
    ap.add_argument("--ref-to", type=float, help="window end in the reference log")
    args = ap.parse_args()

    window = ref_window = None
    if args.t_from is not None or args.t_to is not None:
        if args.skip or args.cut is not None:
            ap.error("--from/--to cannot be combined with --skip or --cut")
        window = (args.t0, args.t_from, args.t_to)
    if args.ref_from is not None or args.ref_to is not None:
        ref_window = (args.t0, args.ref_from, args.ref_to)
    pvt, sat, hw = parse(args.log, args.skip, window)
    cut = None
    if args.cut is not None:
        pvt, sat, hw, cut = cut_at_drop(pvt, sat, hw, args.cut)
    res = summary(pvt, sat)
    fixes = [x for x in pvt if x[1] == 3 and x[2]]
    if window is not None:
        print("Log: %s (window %s to %s s from %s)" % (
            args.log, "start" if args.t_from is None else "%g" % args.t_from,
            "end" if args.t_to is None else "%g" % args.t_to,
            "the log start" if args.t0 is None else "t0 %.3f" % args.t0))
    else:
        print("Log: %s (skip %g s%s)" % (args.log, args.skip,
              "" if args.cut is None else ", cut %g dB: %s" % (
                  args.cut, "last %d s dropped" % cut if cut is not None else "no drop found")))
    if ref_window is not None:
        print("Reference: %s (window %s to %s s)" % (
            args.ref, "start" if args.ref_from is None else "%g" % args.ref_from,
            "end" if args.ref_to is None else "%g" % args.ref_to))
    tracked = [sum(1 for cno, _ in svs.values() if cno > 0) for _, svs in sat]
    used = [sum(1 for _, u in svs.values() if u) for _, svs in sat]
    if sat:
        print("NAV-SAT epochs %d: GPS SVs with C/N0 > 0 %s, used %s" % (len(sat), rng(tracked), rng(used)))
    print("NAV-PVT epochs %d, valid 3D fix %d; last numSV %s, hAcc %s m"
          % (len(pvt), len(fixes), pvt[-1][3] if pvt else "-",
             "%.2f" % (pvt[-1][4] / 1000.0) if pvt else "-"))
    print("MON-HW: noise %s, AGC %s, jamming indicator %s (%d epochs)"
          % (rng([h[0] for h in hw]), rng([h[1] for h in hw]), rng([h[2] for h in hw]), len(hw)))
    print()

    ref = None
    if args.ref:
        ref = summary(*parse(args.ref, 0, ref_window)[:2])
        print("| PRN | Reference | This run | Difference | Min | Max | Epochs used |")
        print("|---|---|---|---|---|---|---|")
    else:
        print("| PRN | Mean C/N0 (dB-Hz) | Min | Max | Epochs used |")
        print("|---|---|---|---|---|")
    diffs = []
    order = sorted(ref or res, key=lambda s: -(ref or res)[s][0])
    for sv in order:
        if ref is not None:
            r = ref[sv][0]
            if sv in res:
                m, lo, hi, n = res[sv]
                diffs.append(m - r)
                print("| G%02d | %.1f | %.1f | %+.1f | %d | %d | %d |" % (sv, r, m, m - r, lo, hi, n))
            else:
                print("| G%02d | %.1f | - | - | - | - | 0 |" % (sv, r))
        else:
            m, lo, hi, n = res[sv]
            print("| G%02d | %.1f | %d | %d | %d |" % (sv, m, lo, hi, n))
    if ref is not None:
        extra = sorted(set(res) - set(ref))
        if extra:
            print("\nUsed here but not in the reference: %s" % ", ".join("G%02d" % s for s in extra))
        if diffs:
            print("\nMean difference %+.2f dB over %d PRNs, range %+.1f to %+.1f dB"
                  % (sum(diffs) / len(diffs), len(diffs), min(diffs), max(diffs)))
    else:
        vals = [v[0] for v in res.values()]
        if vals:
            print("\nMean of %d PRNs: %.1f dB-Hz" % (len(vals), sum(vals) / len(vals)))


if __name__ == "__main__":
    main()
