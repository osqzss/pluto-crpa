#!/usr/bin/env python3
"""Write RTL test vectors to model/vectors/<case>/, for $readmemh.

  input.mem   one line per sample: {x1i, x1q, x2i, x2q}, 16 bits each (adc_data_* format)
  config.mem  one line per weight set: {start_sample[31:0], w1i, w1q, w2i, w2q, shift},
              16 bits each. A set applies from sample start_sample on.
  output.mem  one line per sample: {yi, yq}, 16 bits each (dac_data_* format)
  cov.mem     one line per integration block: {R11, R22, R21_re, R21_im}, 64 bits each.
              Blocks are consecutive INT_LEN samples from sample 0; samples after the
              last whole block belong to no block.
  meta.txt    samples, sets, blocks, int_len, sat (samples with saturation)

Usage: model/gen_vectors.py [output dir]
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import crpa_model as m  # noqa: E402
from scenario import Scenario, generate  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "vectors")


def h(v, bits):
    return "%0*x" % (bits // 4, int(v) & ((1 << bits) - 1))


def write_case(name, x, sets, int_len):
    """x = (x1i, x1q, x2i, x2q); sets = [(start, (w1i, w1q, w2i, w2q), shift), ...]."""
    x1i, x1q, x2i, x2q = x
    n = len(x1i)
    d = os.path.join(OUT, name)
    os.makedirs(d, exist_ok=True)
    yi = np.zeros(n, dtype=np.int64)
    yq = np.zeros(n, dtype=np.int64)
    sat = 0
    for k, (start, w, shift) in enumerate(sets):
        end = sets[k + 1][0] if k + 1 < len(sets) else n
        a, b, s = m.combine(x1i[start:end], x1q[start:end], x2i[start:end], x2q[start:end], w, shift)
        yi[start:end], yq[start:end] = a, b
        sat += int(np.count_nonzero(s))
    with open(os.path.join(d, "input.mem"), "w") as f:
        for k in range(n):
            f.write(h(x1i[k], 16) + h(x1q[k], 16) + h(x2i[k], 16) + h(x2q[k], 16) + "\n")
    with open(os.path.join(d, "output.mem"), "w") as f:
        di, dq = m.to_dac(yi), m.to_dac(yq)
        for k in range(n):
            f.write(h(di[k], 16) + h(dq[k], 16) + "\n")
    with open(os.path.join(d, "config.mem"), "w") as f:
        for start, w, shift in sets:
            f.write(h(start, 32) + "".join(h(v, 16) for v in w) + h(shift, 16) + "\n")
    blocks = n // int_len
    with open(os.path.join(d, "cov.mem"), "w") as f:
        for b in range(blocks):
            s = slice(b * int_len, (b + 1) * int_len)
            r = m.covariance(x1i[s], x1q[s], x2i[s], x2q[s])
            f.write("".join(h(v, 64) for v in r) + "\n")
    with open(os.path.join(d, "meta.txt"), "w") as f:
        f.write("samples %d\nsets %d\nblocks %d\nint_len %d\nsat %d\n" % (n, len(sets), blocks, int_len, sat))
    print("%-12s samples %6d sets %3d blocks %3d int_len %5d sat %5d" % (name, n, len(sets), blocks, int_len, sat))


U = m.UNITY
rng = np.random.default_rng(20261105)

# 1. Unity on each element, then both: y must equal x for the first two sets.
x = tuple(rng.integers(-2048, 2048, 2000) for _ in range(4))
write_case("unity", x, [(0, (U, 0, 0, 0), 0), (700, (0, 0, U, 0), 0), (1400, (U, 0, U, 0), 0)], 500)

# 2. All corners of input and weight, at the extreme shifts, including saturation.
vals_x = [-2048, -1, 0, 1, 2047]
grid = np.array(np.meshgrid(vals_x, vals_x, vals_x, vals_x, indexing="ij")).reshape(4, -1).astype(np.int64)
vals_w = [-32768, -1, 0, 1, 32767]
sets = []
pos = 0
parts = []
for shift in (0, 1, 14, 15):
    for w in rng.choice(vals_w, (40, 4)):
        sets.append((pos, tuple(int(v) for v in w), shift))
        parts.append(grid)
        pos += grid.shape[1]
cat = np.concatenate(parts, axis=1)
write_case("corners", (cat[0], cat[1], cat[2], cat[3]), sets, 625)

# 3. Random inputs, with a new weight set and shift at random samples. Most sets use
# small weights and shifts so that rounding, not saturation, decides the output.
x = tuple(rng.integers(-2048, 2048, 20000) for _ in range(4))
starts = [0] + sorted(int(v) for v in rng.choice(np.arange(1, 20000), 199, replace=False))
sets = []
for s in starts:
    if rng.random() < 0.8:
        sets.append((s, tuple(int(v) for v in rng.integers(-6000, 6000, 4)), int(rng.integers(0, 2))))
    else:
        sets.append((s, tuple(int(v) for v in rng.integers(-32768, 32768, 4)), int(rng.integers(0, 16))))
write_case("random", x, sets, 777)

# 4. Scenario: CW jammer, adaptive loop. Each weight set comes from the previous block
# and applies some samples after the block ends, as the PS is not instantaneous.
sc = Scenario(n=20000, jn_db=25.0, seed=7)
g = generate(sc)
x = (g["x1i"], g["x1q"], g["x2i"], g["x2q"])
N = 2000
loop = m.PiLoop(load=sc.noise_rms ** 2, alpha=0.5)
sets = [(0, (U, 0, 0, 0), 0)]
for b in range(sc.n // N - 1):
    s = slice(b * N, (b + 1) * N)
    w = loop.update(m.covariance(x[0][s], x[1][s], x[2][s], x[3][s]), N)
    sets.append(((b + 1) * N + 137, w, 0))
write_case("cw_loop", x, sets, N)
