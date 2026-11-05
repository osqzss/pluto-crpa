#!/usr/bin/env python3
"""Checks of the bit-true model. Run: python3 model/test_model.py"""
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import crpa_model as m  # noqa: E402
from scenario import Scenario, ca_code, generate, steer  # noqa: E402

U = m.UNITY


def ref_sample(x1i, x1q, x2i, x2q, w, shift):
    """Independent one-sample version with Python integers: complex product written out
    from y = conj(w1) x1 + conj(w2) x2, rounding by floor(v + 1/2)."""
    w1i, w1q, w2i, w2q = w
    si = (w1i * x1i - (-w1q) * x1q) + (w2i * x2i - (-w2q) * x2q)
    sq = (w1i * x1q + (-w1q) * x1i) + (w2i * x2q + (-w2q) * x2i)
    den = 1 << (15 - shift)
    ri = (2 * si + den) // (2 * den)
    rq = (2 * sq + den) // (2 * den)
    return max(-2048, min(2047, ri)), max(-2048, min(2047, rq))


class Combiner(unittest.TestCase):
    def test_unity_is_exact_for_every_input(self):
        x = np.arange(-2048, 2048)
        z = np.zeros_like(x)
        yi, yq, sat = m.combine(x, x[::-1], z, z, (U, 0, 0, 0))
        self.assertTrue((yi == x).all() and (yq == x[::-1]).all() and not sat.any())
        yi, yq, sat = m.combine(z, z, x, x[::-1], (0, 0, U, 0))
        self.assertTrue((yi == x).all() and (yq == x[::-1]).all() and not sat.any())

    def test_conjugate_convention(self):
        # w = j: conj(w) * x = -j * x, so (i, q) -> (q, -i)
        yi, yq, _ = m.combine([1000], [200], [0], [0], (0, U, 0, 0))
        self.assertEqual((int(yi[0]), int(yq[0])), (200, -1000))

    def test_matches_independent_reference(self):
        rng = np.random.default_rng(1)
        for _ in range(3000):
            x = [int(v) for v in rng.integers(-2048, 2048, 4)]
            w = tuple(int(v) for v in rng.integers(-32768, 32768, 4))
            s = int(rng.integers(0, 16))
            yi, yq, _ = m.combine([x[0]], [x[1]], [x[2]], [x[3]], w, s)
            self.assertEqual((int(yi[0]), int(yq[0])), ref_sample(*x, w, s))

    def test_extreme_sum_fits_30_bits(self):
        v = [-2048]
        w = (-32768, -32768, -32768, -32768)
        # si = 4 * 2^26 = 2^28, the largest magnitude; 30-bit signed holds it
        yi, _, sat = m.combine(v, v, v, v, w, 15)
        self.assertEqual(int(yi[0]), 2047)
        self.assertTrue(sat[0])
        self.assertLess(4 * 32768 * 2048, 1 << 29)

    def test_saturation_flag(self):
        _, _, sat = m.combine([2047], [0], [2047], [0], (U, 0, U, 0), 0)
        self.assertTrue(sat[0])
        _, _, sat = m.combine([1000], [0], [1000], [0], (U, 0, U, 0), 0)
        self.assertFalse(sat[0])

    def test_rejects_out_of_range(self):
        with self.assertRaises(ValueError):
            m.combine([2048], [0], [0], [0], (U, 0, 0, 0))
        with self.assertRaises(ValueError):
            m.combine([0], [0], [0], [0], (32768, 0, 0, 0))


class Covariance(unittest.TestCase):
    def test_against_complex_float(self):
        rng = np.random.default_rng(2)
        x = rng.integers(-2048, 2048, (4, 5000))
        r11, r22, re, im = m.covariance(*x)
        x1, x2 = x[0] + 1j * x[1], x[2] + 1j * x[3]
        self.assertEqual(r11, round(float(np.sum(np.abs(x1) ** 2))))
        self.assertEqual(r22, round(float(np.sum(np.abs(x2) ** 2))))
        c = np.sum(x2 * np.conj(x1))
        self.assertEqual((re, im), (round(c.real), round(c.imag)))

    def test_worst_case_fits_48_bits(self):
        self.assertLess(m.INT_LEN_MAX * 2 * 2048 ** 2, 1 << 47)


class Weights(unittest.TestCase):
    def test_nulls_a_pure_jammer_exactly_in_float(self):
        for a, b in ((1.0, steer(40)), (3.0, 0.5 * steer(-70)), (0.2, 2.0 * steer(10))):
            r21 = b * np.conj(a)
            w1, w2 = m.pi_weights(abs(a) ** 2, abs(b) ** 2, r21.real, r21.imag)
            self.assertLess(abs(np.conj(w1) * a + np.conj(w2) * b), 1e-12)
            self.assertAlmostEqual(max(abs(w1), abs(w2)), 1.0)

    def test_noise_only_is_near_unity_on_element_1(self):
        w1, w2 = m.pi_weights(1000.0, 1000.0, 3.0, -2.0)
        self.assertGreater(abs(w1), 0.99)
        self.assertLess(abs(w2), 0.01)

    def test_zero_covariance(self):
        self.assertEqual(m.pi_weights(0, 0, 0, 0), (1 + 0j, 0j))

    def test_quantize_clips_plus_one(self):
        self.assertEqual(m.quantize_weights(1 + 0j, -1 + 0j), (32767, 0, -32768, 0))

    def test_loading_reduces_weight_on_weak_jammer(self):
        r = (1000.0, 1000.0, 100.0, 0.0)
        _, w2_a = m.pi_weights(*r)
        _, w2_b = m.pi_weights(*r, delta=9000.0)
        self.assertLess(abs(w2_b), abs(w2_a))


def tone_power(xi, xq, f, fs):
    t = np.arange(len(xi)) / fs
    return abs(np.mean((xi + 1j * xq) * np.exp(-2j * np.pi * f * t))) ** 2


class EndToEnd(unittest.TestCase):
    def run_loop(self, sc, load=None):
        g = generate(sc)
        x = (g["x1i"], g["x1q"], g["x2i"], g["x2q"])
        w = m.PiLoop(load=sc.noise_rms ** 2 if load is None else load).update(m.covariance(*x), sc.n)
        yi, yq, sat = m.combine(*x, w)
        f = -sc.delta + sc.jam_offset
        wg = sum(v * v for v in w) / 32768.0 ** 2
        null = tone_power(x[0], x[1], f, sc.fs) / (tone_power(yi, yq, f, sc.fs) / wg)
        return 10 * np.log10(null), w, sat, g

    def test_null_depth_on_cw(self):
        null, _, sat, g = self.run_loop(Scenario(n=100000, jn_db=30.0, cn0_dbhz=None))
        self.assertEqual(g["clipped"], 0)
        self.assertFalse(sat.any())
        self.assertGreater(null, 45.0)

    def test_independent_of_channel_mismatch(self):
        sc = Scenario(n=100000, jn_db=30.0, cn0_dbhz=None, ch2_gain_db=3.0, ch2_phase_deg=77.0)
        null, _, _, _ = self.run_loop(sc)
        self.assertGreater(null, 45.0)

    def test_gps_found_after_nulling_not_before(self):
        sc = Scenario(n=100000, jn_db=30.0, cn0_dbhz=50.0, sat_deg=-30.0, jam_deg=40.0)
        _, w, _, g = self.run_loop(sc)
        x = (g["x1i"], g["x1q"], g["x2i"], g["x2q"])
        yi, yq, _ = m.combine(*x, w)
        fc = -sc.delta + sc.doppler
        n = int(sc.fs * 1e-3)
        chip = np.floor(np.arange(n) * 1023000.0 / sc.fs).astype(int) % 1023
        cc = np.conj(np.fft.fft(ca_code(sc.prn)[chip]))
        t = np.arange(n) / sc.fs

        def metric(i, q):
            v = (i + 1j * q)[:10 * n].reshape(10, n) * np.exp(-2j * np.pi * fc * t)
            s = (np.abs(np.fft.ifft(np.fft.fft(v, axis=1) * cc, axis=1)) ** 2).sum(axis=0)
            return s.max() / np.median(s)

        self.assertGreater(metric(yi, yq), metric(x[0], x[1]))
        self.assertGreater(metric(yi, yq), 4.0)

    def test_signal_gain_follows_theory(self):
        # strong jammer: |w1| = |w2| = 1, so signal gain |1 - exp(j d)|^2, noise gain 2.
        wj = steer(40.0)
        w2 = -wj
        for sat in (-30.0, 0.0, 20.0):
            d = np.angle(steer(sat) / wj)
            g = abs(1.0 + np.conj(w2) * steer(sat)) ** 2
            self.assertAlmostEqual(g, 4 * np.sin(d / 2) ** 2)


if __name__ == "__main__":
    unittest.main(verbosity=1)
