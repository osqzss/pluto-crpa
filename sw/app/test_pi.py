#!/usr/bin/env python3
"""Check the C weight computation (crpa_pi.c, through pi_cli) against the
golden PS reference in model/crpa_model.py (PiLoop, pi_weights,
quantize_weights). Weights must be equal, element by element.

Usage: test_pi.py PI_CLI      (normally through "make test" in sw/app)
Cases: edge cases, covariance blocks from the model's own scenarios
(covariance() on generated samples), random R over the full 48-bit range,
and sequences with smoothing and loading.
"""
import os
import random
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "model"))
import numpy as np                 # noqa: E402
import crpa_model as m             # noqa: E402
from scenario import Scenario, generate   # noqa: E402

R_MAX = (1 << 47) - 1


def run_c(cli, seqs):
    """seqs: list of (load, alpha, [(n, r11, r22, r21re, r21im), ...])."""
    lines = []
    for load, alpha, blocks in seqs:
        lines.append("init %r %r" % (load, alpha))
        for b in blocks:
            lines.append("blk %d %d %d %d %d" % b)
    p = subprocess.run([cli], input="\n".join(lines) + "\n", capture_output=True, text=True,
                       check=True)
    out = [tuple(int(v) for v in ln.split()) for ln in p.stdout.splitlines()]
    return out


def run_py(seqs):
    out = []
    for load, alpha, blocks in seqs:
        loop = m.PiLoop(load=load, alpha=alpha)
        for n, *r in blocks:
            out.append(tuple(int(v) for v in loop.update(r, n)))
    return out


def scenario_blocks():
    """R from the model's covariance() on generated two-element samples."""
    blocks = []
    for jn, noise in ((None, 30.0), (0, 30.0), (20, 16.0), (30, 5.0), (40, 16.0), (55, 2.0)):
        sc = Scenario(jn_db=jn, noise_rms=noise, n=40000, cn0_dbhz=45.0, sat_deg=-30.0,
                      jam_deg=40.0)
        g = generate(sc)
        for k in range(4):
            s = slice(k * 10000, (k + 1) * 10000)
            blocks.append((10000,) + m.covariance(g["x1i"][s], g["x1q"][s], g["x2i"][s],
                                                  g["x2q"][s]))
    return blocks


def main():
    cli = sys.argv[1]
    rng = random.Random(20261109)
    seqs = []
    # edge cases
    edge = [(1, 0, 0, 0, 0), (10000, 0, 5, 0, 0), (10000, 5, 0, 0, 0),
            (10000, 100, 100, 100, 0), (10000, 100, 100, 0, -100), (10000, 1, 1, -1, -1),
            (10000, R_MAX, R_MAX, R_MAX, R_MAX), (10000, R_MAX, R_MAX, -R_MAX - 1, -R_MAX - 1),
            (m.INT_LEN_MAX, R_MAX, 1, 0, 0), (10000, 3, 4, 3, 4),
            (10000, 1 << 40, 1 << 40, -(1 << 40), 0), (10000, 7, 7, 0, 7)]
    for b in edge:
        seqs.append((0.0, 0.0, [b]))
        seqs.append((0.1, 0.0, [b]))
        seqs.append((900.0, 0.0, [b]))
    # model scenarios
    sb = scenario_blocks()
    for load in (0.0, 0.1 * 900, 900.0):
        seqs.append((load, 0.0, sb))
    seqs.append((90.0, 0.5, sb))
    seqs.append((90.0, 0.9, sb))
    # random, independent and in sequences
    for _ in range(3000):
        n = rng.choice((1, 100, 1000, 10000, 65536, m.INT_LEN_MAX))
        r11 = rng.randrange(0, R_MAX + 1)
        r22 = rng.randrange(0, R_MAX + 1)
        lim = rng.choice((1 << 10, 1 << 30, R_MAX))
        seqs.append((rng.choice((0.0, 0.1, 3.7, 900.0)), 0.0,
                     [(n, r11, r22, rng.randrange(-lim, lim + 1), rng.randrange(-lim, lim + 1))]))
    for _ in range(50):
        blocks = []
        for _ in range(20):
            r11 = rng.randrange(0, 1 << 40)
            blocks.append((10000, r11, rng.randrange(0, 1 << 40),
                           rng.randrange(-(1 << 39), 1 << 39), rng.randrange(-(1 << 39), 1 << 39)))
        seqs.append((rng.uniform(0, 1000), rng.choice((0.0, 0.25, 0.5, 0.99)), blocks))

    c = run_c(cli, seqs)
    p = run_py(seqs)
    if len(c) != len(p):
        print("FAIL: %d C results, %d Python results" % (len(c), len(p)))
        return 1
    bad = [(i, a, b) for i, (a, b) in enumerate(zip(c, p)) if a != b]
    for i, a, b in bad[:10]:
        print("MISMATCH %d: C %s model %s" % (i, a, b))
    print("%d weight sets compared, %d mismatches (numpy %s)" % (len(c), len(bad), np.__version__))
    print("PASS" if not bad else "FAIL")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
