#!/usr/bin/env python3
"""Per-PRN C/N0 and MON-HW summary from a raw u-blox log (gpspipe -R).

Reads NAV-PVT, NAV-SAT and MON-HW (u-blox 8, protocol 18). For each GPS PRN,
C/N0 is averaged over the NAV-SAT epochs where the SV is flagged used in the
solution. Optional --skip drops the first seconds of the log (acquisition).
Prints a Markdown table; with --ref, a second log is the reference column.

Usage: scripts/ubx_cn0.py LOG.ubx [--ref REF.ubx] [--skip SEC]
"""
import argparse
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
            yield cls, mid, bytes(data[i + 6:end])
            i = end + 2
        else:
            i += 1


def parse(path, skip):
    with open(path, "rb") as f:
        data = f.read()
    pvt, sat, hw = [], [], []
    for cls, mid, p in frames(data):
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
    args = ap.parse_args()

    pvt, sat, hw = parse(args.log, args.skip)
    res = summary(pvt, sat)
    fixes = [x for x in pvt if x[1] == 3 and x[2]]
    print("Log: %s (skip %g s)" % (args.log, args.skip))
    print("NAV-PVT epochs %d, valid 3D fix %d; last numSV %s, hAcc %s m"
          % (len(pvt), len(fixes), pvt[-1][3] if pvt else "-",
             "%.2f" % (pvt[-1][4] / 1000.0) if pvt else "-"))
    print("MON-HW: noise %s, AGC %s, jamming indicator %s (%d epochs)"
          % (rng([h[0] for h in hw]), rng([h[1] for h in hw]), rng([h[2] for h in hw]), len(hw)))
    print()

    ref = None
    if args.ref:
        ref = summary(*parse(args.ref, 0)[:2])
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
