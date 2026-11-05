"""Two-element input generator: GPS C/A, thermal noise, CW jammer, S12 quantization.

Geometry: uniform spacing, angle from broadside. Element 2 sees a plane wave from angle
theta with phase pi * (spacing / (lambda / 2)) * sin(theta) relative to element 1.
Baseband: LO = L1 + delta, so the signal sits at -delta (plan Section 4.1).
"""
from dataclasses import dataclass

import numpy as np

CODE_RATE = 1023000.0
G2_TAPS = {1: (2, 6), 2: (3, 7), 3: (4, 8), 4: (5, 9), 5: (1, 9), 6: (2, 10), 7: (1, 8),
           8: (2, 9), 9: (3, 10), 10: (2, 3), 11: (3, 4), 12: (5, 6), 13: (6, 7), 14: (7, 8),
           15: (8, 9), 16: (9, 10), 17: (1, 4), 18: (2, 5), 19: (3, 6), 20: (4, 7), 21: (5, 8),
           22: (6, 9), 23: (1, 3), 24: (4, 6), 25: (5, 7), 26: (6, 8), 27: (7, 9), 28: (8, 10),
           29: (1, 6), 30: (2, 7), 31: (3, 8), 32: (4, 9)}


def ca_code(prn):
    """1023 chips of +1/-1."""
    g1 = [1] * 10
    g2 = [1] * 10
    s1, s2 = G2_TAPS[prn]
    out = []
    for _ in range(1023):
        out.append(g1[9] ^ g2[s1 - 1] ^ g2[s2 - 1])
        f1 = g1[2] ^ g1[9]
        f2 = g2[1] ^ g2[2] ^ g2[5] ^ g2[7] ^ g2[8] ^ g2[9]
        g1 = [f1] + g1[:9]
        g2 = [f2] + g2[:9]
    return 1.0 - 2.0 * np.array(out, dtype=float)


def steer(theta_deg, spacing_halfwave=1.0):
    """Element 2 phase factor relative to element 1."""
    return np.exp(1j * np.pi * spacing_halfwave * np.sin(np.radians(theta_deg)))


@dataclass
class Scenario:
    n: int = 200000
    fs: float = 10e6
    delta: float = 3e6
    noise_rms: float = 30.0        # complex rms per element, LSB
    prn: int = 1
    cn0_dbhz: float = 45.0         # None for no signal
    sat_deg: float = 0.0
    doppler: float = 1000.0
    code_phase: float = 123.4      # chips
    jn_db: float = None            # jammer to noise per element, over fs; None for no jammer
    jam_deg: float = 40.0
    jam_offset: float = 200e3      # relative to L1
    ch2_gain_db: float = 0.0       # channel 2 mismatch
    ch2_phase_deg: float = 0.0
    seed: int = 1


def generate(sc):
    """Returns dict with S12 integer arrays x1i, x1q, x2i, x2q, and the float components."""
    rng = np.random.default_rng(sc.seed)
    t = np.arange(sc.n) / sc.fs
    a = sc.noise_rms / np.sqrt(2.0)
    n1 = a * (rng.standard_normal(sc.n) + 1j * rng.standard_normal(sc.n))
    n2 = a * (rng.standard_normal(sc.n) + 1j * rng.standard_normal(sc.n))
    s1 = np.zeros(sc.n, dtype=complex)
    s2 = np.zeros(sc.n, dtype=complex)
    if sc.cn0_dbhz is not None:
        n0 = sc.noise_rms ** 2 / sc.fs
        amp = np.sqrt(n0 * 10 ** (sc.cn0_dbhz / 10.0))
        chip = np.floor(np.arange(sc.n) * CODE_RATE / sc.fs + sc.code_phase).astype(np.int64) % 1023
        s1 = amp * ca_code(sc.prn)[chip] * np.exp(2j * np.pi * (-sc.delta + sc.doppler) * t)
        s2 = s1 * steer(sc.sat_deg)
    j1 = np.zeros(sc.n, dtype=complex)
    j2 = np.zeros(sc.n, dtype=complex)
    if sc.jn_db is not None:
        amp = sc.noise_rms * 10 ** (sc.jn_db / 20.0)
        j1 = amp * np.exp(2j * np.pi * ((-sc.delta + sc.jam_offset) * t + rng.random()))
        j2 = j1 * steer(sc.jam_deg)
    mis = 10 ** (sc.ch2_gain_db / 20.0) * np.exp(1j * np.radians(sc.ch2_phase_deg))
    x1 = s1 + n1 + j1
    x2 = (s2 + n2 + j2) * mis
    r = {}
    clipped = 0
    for name, v in (("x1i", x1.real), ("x1q", x1.imag), ("x2i", x2.real), ("x2q", x2.imag)):
        q = np.rint(v).astype(np.int64)
        clipped += int(np.count_nonzero((q < -2048) | (q > 2047)))
        r[name] = np.clip(q, -2048, 2047)
    r["clipped"] = clipped
    return r
