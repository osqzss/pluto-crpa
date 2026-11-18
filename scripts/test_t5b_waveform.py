#!/usr/bin/env python3
"""Tests of scripts/t5b_waveform.py (docs/t5b_plan.md, 4.1). No hardware.

Run: .venv/bin/python scripts/test_t5b_waveform.py
"""
import hashlib
import json
import os
import sys
import tempfile
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import t5b_waveform as tw  # noqa: E402

RATE = 4e6


def load(base):
    q = np.fromfile(base + ".sc16", dtype="<i2")
    with open(base + ".json") as f:
        side = json.load(f)
    return q[0::2].astype(float) + 1j * q[1::2].astype(float), side, q


class Files(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def make(self, *argv):
        base = os.path.join(self.tmp.name, "w")
        rc = tw.main(list(argv) + ["--out", base, "--no-png"])
        return rc, base

    def test_noise_bandwidth_and_sidecar(self):
        for bw in (0.1e6, 0.5e6, 1e6, 2e6):
            with self.subTest(bw=bw):
                rc, base = self.make("noise", "--bw", str(bw), "--rate", str(RATE), "--length", "0.25")
                self.assertEqual(rc, 0)
                z, side, q = load(base)
                bw99, cen = tw.occupied(z, RATE)
                self.assertLess(abs(bw99 / bw - 1), 0.02, bw99)
                self.assertLess(abs(cen), bw * 0.02)
                self.assertAlmostEqual(side["rms_dbfs"], -15.0, delta=0.01)
                self.assertEqual(side["n"], len(z))
                self.assertEqual(side["bytes"], 4 * len(z))
                with open(base + ".sc16", "rb") as f:
                    self.assertEqual(side["sha256"], hashlib.sha256(f.read()).hexdigest())
                self.assertGreater(side["crest_db"], 8.0)      # Gaussian
                self.assertLess(side["peak_abs_iq"], 32767)

    def test_cw_constant_and_offset(self):
        rc, base = self.make("cw", "--offset", "200e3", "--rate", str(RATE), "--length", "0.01")
        self.assertEqual(rc, 0)
        z, side, _ = load(base)
        self.assertAlmostEqual(side["rms_dbfs"], -6.02, delta=0.01)
        self.assertLess(side["crest_db"], 0.05)
        f = np.fft.fftfreq(len(z), 1 / RATE)
        self.assertAlmostEqual(f[np.argmax(abs(np.fft.fft(z)))], 200e3, delta=1.0)
        # loops without a seam: the phase step across the wrap equals the step inside
        d_in = np.angle(z[1] / z[0])
        d_wrap = np.angle(z[0] / z[-1])
        self.assertAlmostEqual(d_in, d_wrap, delta=1e-3)

    def test_chirp_instantaneous_frequency(self):
        span, period = 2e6, 1e-3
        rc, base = self.make("chirp", "--span", str(span), "--period", str(period), "--rate", str(RATE),
                             "--length", "0.0105")
        self.assertEqual(rc, 0)
        z, side, _ = load(base)
        m = int(RATE * period)
        self.assertEqual(len(z) % m, 0)
        self.assertEqual(len(z), 11 * m)                       # rounded up to whole periods
        fi = np.angle(z[1:] * np.conj(z[:-1])) * RATE / (2 * np.pi)
        tp = (np.arange(len(fi)) % m) / RATE
        want = -span / 2 + span * tp / period
        inside = (np.arange(len(fi)) % m) != m - 1           # skip the wrap sample
        self.assertLess(abs(fi[inside] - want[inside]).max(), span / m + 2e3)
        self.assertLess(side["crest_db"], 0.1)
        bw99, _ = tw.occupied(z, RATE)
        self.assertLess(abs(bw99 / span - 1), 0.05)

    def test_fast_chirp(self):
        rc, base = self.make("chirp", "--span", "2e6", "--period", "10e-6", "--rate", str(RATE),
                             "--length", "0.01")
        self.assertEqual(rc, 0)
        z, _, _ = load(base)
        self.assertEqual(len(z) % 40, 0)

    def test_pn_chip_rate(self):
        rc, base = self.make("pn", "--no-filter", "--rate", "4.092e6", "--length", "0.01")
        self.assertEqual(rc, 0)
        z, side, _ = load(base)
        self.assertEqual(side["samples_per_chip"], 4)
        s = np.sign(z.real)
        edges = np.flatnonzero(s[1:] != s[:-1]) + 1
        self.assertTrue(np.all(edges % 4 == 0))              # transitions only at chip boundaries
        self.assertAlmostEqual(len(edges) / (len(z) / 4), 0.5, delta=0.03)
        self.assertTrue(np.all(abs(z.imag) == 0))
        # filtered: main lobe, nulls at +/- chip rate
        rc, base = self.make("pn", "--rate", "4.092e6", "--length", "0.05")
        z, side, _ = load(base)
        f = np.fft.fftfreq(len(z), 1 / 4.092e6)
        pw = abs(np.fft.fft(z)) ** 2
        self.assertLess(pw[abs(f) > 1.03e6].sum() / pw.sum(), 1e-6)
        self.assertAlmostEqual(side["rms_dbfs"], -6.02, delta=0.01)

    def test_pn_needs_integer_samples_per_chip(self):
        rc, _ = self.make("pn", "--rate", "4e6")
        self.assertEqual(rc, 2)

    def test_pulsed(self):
        rc, base = self.make("noise", "--bw", "1e6", "--rate", str(RATE), "--pulse-period", "1e-3",
                             "--duty", "0.1", "--length", "0.02")
        self.assertEqual(rc, 0)
        z, side, _ = load(base)
        pp = int(RATE * 1e-3)
        on = (np.arange(len(z)) % pp) < pp // 10
        self.assertEqual(len(z) % pp, 0)
        self.assertTrue(np.all(z[~on] == 0))
        self.assertAlmostEqual(side["duty_measured"], 0.1, places=6)
        self.assertAlmostEqual(side["rms_dbfs_on"], -15.0, delta=0.01)
        self.assertAlmostEqual(side["rms_dbfs"], -25.0, delta=0.05)

    def test_pulsed_cw(self):
        rc, base = self.make("cw", "--offset", "200e3", "--rate", str(RATE), "--pulse-period", "10e-3",
                             "--duty", "0.1", "--length", "0.05")
        self.assertEqual(rc, 0)
        z, side, _ = load(base)
        self.assertEqual(len(z), 5 * 40000)

    def test_clipping_refused(self):
        rc, base = self.make("noise", "--bw", "1e6", "--rate", str(RATE), "--rms-dbfs", "-3",
                             "--length", "0.1")
        self.assertEqual(rc, 2)
        self.assertFalse(os.path.exists(base + ".sc16"))

    def test_offset_must_loop(self):
        rc, _ = self.make("cw", "--offset", "123.456", "--rate", str(RATE), "--length", "0.001")
        self.assertEqual(rc, 2)
        rc, _ = self.make("cw", "--offset", "1000", "--rate", str(RATE), "--length", "0.0015")
        self.assertEqual(rc, 0)

    def test_bad_args(self):
        self.assertEqual(self.make("noise", "--rate", str(RATE))[0], 2)                  # no bw
        self.assertEqual(self.make("noise", "--bw", "5e6", "--rate", str(RATE))[0], 2)   # bw >= rate
        self.assertEqual(self.make("chirp", "--span", "2e6", "--period", "1.1e-7", "--rate", str(RATE))[0], 2)
        self.assertEqual(self.make("cw", "--rate", str(RATE), "--pulse-period", "1e-3", "--duty", "1.5")[0], 2)


class Quantize(unittest.TestCase):
    def test_level_exact(self):
        x = np.exp(2j * np.pi * 0.01 * np.arange(1000))
        q = tw.quantize(x, -6.0206)
        z = q[0::2] + 1j * q[1::2].astype(float)
        self.assertAlmostEqual(abs(z).max(), 16384, delta=1)


if __name__ == "__main__":
    unittest.main()
