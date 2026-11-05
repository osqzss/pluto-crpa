"""Bit-true reference model of crpa_core, and the PS weight computation.

This file is the golden reference: RTL must match combine() and covariance() bit
exactly. Formats are recorded in docs/fixed_point.md.

Fixed-point summary (S<n> = n-bit two's complement):
  input x    S12, -2048..2047. Sign-extended to 16 bits on the adc_data_* ports.
  weight w   Q1.15, S16 for each of re and im. Unity is 0x7FFF (see UNITY).
  product    S16 x S12, 28 bits.
  sum        four products, range +/-2^28, carried in 30 bits. No rounding before here.
  shift      OUT_SHIFT s = 0..15 is a gain of 2^s: sum >> (15 - s).
  rounding   round half up, once, after the sum: add 2^(sh-1), then arithmetic shift.
  output y   saturate to S12 (-2048..2047), then << 4 for dac_data_*.
  R11, R22   sum of xi^2 + xq^2. Each term is unsigned, at most 2^23.
  R21        sum of x2 * conj(x1). Each of re, im has magnitude at most 2^23.
  accumulator 48-bit signed. INT_LEN is 24 bits, at most 2^24 - 1, so |R| < 2^47: no overflow.
"""
import numpy as np

X_MIN, X_MAX = -2048, 2047
W_MIN, W_MAX = -32768, 32767
UNITY = 0x7FFF  # with S12 input this passes x unchanged: |x| / 32768 < 1/16 LSB
SHIFT_MAX = 15
INT_LEN_MAX = (1 << 24) - 1  # 2^24 samples of full scale would reach +2^47: overflow


def _as_x(x):
    x = np.asarray(x, dtype=np.int64)
    if x.size and (x.min() < X_MIN or x.max() > X_MAX):
        raise ValueError("input outside S12")
    return x


def combine(x1i, x1q, x2i, x2q, w, shift=0):
    """y = conj(w1) * x1 + conj(w2) * x2, for one weight set.

    w = (w1i, w1q, w2i, w2q), integers in Q1.15. Returns (yi, yq, sat), where yi and yq
    are S12 and sat flags samples in which either component saturated.
    """
    x1i, x1q, x2i, x2q = _as_x(x1i), _as_x(x1q), _as_x(x2i), _as_x(x2q)
    w1i, w1q, w2i, w2q = (int(v) for v in w)
    for v in (w1i, w1q, w2i, w2q):
        if not W_MIN <= v <= W_MAX:
            raise ValueError("weight outside Q1.15")
    if not 0 <= shift <= SHIFT_MAX:
        raise ValueError("shift outside 0..15")
    si = w1i * x1i + w1q * x1q + w2i * x2i + w2q * x2q
    sq = w1i * x1q - w1q * x1i + w2i * x2q - w2q * x2i
    sh = 15 - shift
    rnd = (1 << (sh - 1)) if sh > 0 else 0
    ri = (si + rnd) >> sh
    rq = (sq + rnd) >> sh
    yi = np.clip(ri, X_MIN, X_MAX)
    yq = np.clip(rq, X_MIN, X_MAX)
    return yi, yq, (yi != ri) | (yq != rq)


def covariance(x1i, x1q, x2i, x2q):
    """One integration block over the given samples: (R11, R22, R21_re, R21_im), as ints."""
    x1i, x1q, x2i, x2q = _as_x(x1i), _as_x(x1q), _as_x(x2i), _as_x(x2q)
    if x1i.size > INT_LEN_MAX:
        raise ValueError("block longer than INT_LEN_MAX")
    r11 = np.sum(x1i * x1i + x1q * x1q)
    r22 = np.sum(x2i * x2i + x2q * x2q)
    r21re = np.sum(x2i * x1i + x2q * x1q)
    r21im = np.sum(x2q * x1i - x2i * x1q)
    return int(r11), int(r22), int(r21re), int(r21im)


def to_dac(y):
    """S12 to the 16-bit dac_data_* format."""
    return np.asarray(y, dtype=np.int64) << 4


def quantize_weights(w1, w2):
    """Complex floats, largest component magnitude scaled to 1 already, to Q1.15."""
    out = []
    for v in (w1.real, w1.imag, w2.real, w2.imag):
        out.append(int(np.clip(np.rint(v * 32768.0), W_MIN, W_MAX)))
    return tuple(out)


def pi_weights(r11, r22, r21re, r21im, delta=0.0):
    """Power inversion with diagonal loading (PS reference, floating point).

    w ~ inv(R + delta I) e1 ~ [R22 + delta, -R21]. delta is in the units of R, that is,
    LSB^2 per sample times the block length. The null does not depend on overall gain,
    so w is scaled so that the larger of |w1|, |w2| becomes 1. |w2| can exceed |w1| when
    the jammer is stronger on element 1, so scaling by |w1| alone could overflow Q1.15.
    Returns complex (w1, w2). w1 is real and positive. Returns unity on an all-zero R.
    """
    w1 = complex(r22 + delta)
    w2 = -complex(r21re, r21im)
    m = max(abs(w1), abs(w2))
    if m == 0.0:
        return 1.0 + 0j, 0j
    return w1 / m, w2 / m


class PiLoop:
    """Weight loop of the PS application: smooth R over blocks, then compute w.

    R_s[k] = alpha * R_s[k-1] + (1 - alpha) * R[k]; alpha = 0 is no smoothing.
    load is the diagonal load in LSB^2 per sample.
    """

    def __init__(self, load=0.0, alpha=0.0):
        self.load = load
        self.alpha = alpha
        self.r = None

    def update(self, r, n):
        r = np.asarray(r, dtype=float)
        self.r = r if self.r is None else self.alpha * self.r + (1.0 - self.alpha) * r
        w1, w2 = pi_weights(*self.r, delta=self.load * n)
        return quantize_weights(w1, w2)
