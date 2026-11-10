#!/usr/bin/python3
"""Tests of scripts/t4_jammer.py without a B205mini and without RF.

The uhd module is replaced by a stand-in that records every call. The stand-in
only has the calls the script uses; it says nothing about the real device.

Run: python3 scripts/test_t4_jammer.py
"""
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "t4_jammer.py")
sys.path.insert(0, HERE)
import t4_jammer as tj  # noqa: E402

FAKE = r'''
import json, os, time
D = os.environ["FAKE_DIR"]

def rec(op, **kw):
    kw["op"] = op
    with open(os.path.join(D, "calls"), "a") as f:
        f.write(json.dumps(kw) + "\n")

def flag(name):
    return os.path.exists(os.path.join(D, name))

class _Range:
    def __init__(self, a, b, c=0.0): self.a, self.b, self.c = a, b, c
    def start(self): return self.a
    def stop(self): return self.b
    def step(self): return self.c

class _Res:
    def __init__(self, f): self.actual_rf_freq, self.actual_dsp_freq = f, 0.0

class _Stream:
    def __init__(self): self.n = 0
    def send(self, buf, md, timeout=0.1):
        if md.end_of_burst:
            rec("eob")
            return buf.shape[1]
        if md.start_of_burst:
            rec("sob", ampl=float(abs(buf[0, 0])))
        self.n += 1
        if flag("fail_send") and self.n > 3:
            raise RuntimeError("fake send failure")
        time.sleep(0.01)
        return buf.shape[1]

class _Usrp:
    def __init__(self, args):
        if flag("no_device"):
            raise RuntimeError("LookupError: KeyError: No devices found for ----->")
        rec("open", args=args)
        self.gain, self.freq, self.rate, self.ant = 40.0, 0.0, 0.0, "TX/RX"
    def get_pp_string(self): return "Fake B205mini"
    def get_tx_gain_range(self, ch): return _Range(0.0, 89.75, 0.25)
    def get_tx_antennas(self, ch): return ["TX/RX"]
    def get_tx_freq_range(self, ch): return _Range(22e6, 6e9)
    def set_tx_gain(self, g, ch):
        rec("gain", gain=g)
        if not flag("stuck_gain"):
            self.gain = g
    def get_tx_gain(self, ch): return self.gain
    def set_tx_antenna(self, a, ch): self.ant = a; rec("ant", ant=a)
    def get_tx_antenna(self, ch): return self.ant
    def set_tx_rate(self, r, ch): self.rate = r; rec("rate", rate=r)
    def get_tx_rate(self, ch): return self.rate
    def set_tx_freq(self, req, ch): self.freq = req.f; rec("freq", freq=req.f); return _Res(req.f)
    def get_tx_freq(self, ch): return self.freq
    def get_tx_stream(self, sa): rec("stream"); return _Stream()

class _MD:
    def __init__(self): self.start_of_burst = False; self.end_of_burst = False

class _TR:
    def __init__(self, f): self.f = f

class usrp:
    MultiUSRP = _Usrp
    @staticmethod
    def StreamArgs(a, b): return (a, b)

class types:
    TXMetadata = _MD
    TuneRequest = _TR
'''

ON = ["--on", "--ext-att", "60", "--max-gain", "50"]


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = self.tmp.name
        os.mkdir(os.path.join(self.d, "uhd"))
        with open(os.path.join(self.d, "uhd", "__init__.py"), "w") as f:
            f.write(FAKE)
        self.env = dict(os.environ, FAKE_DIR=self.d, PYTHONPATH=self.d)

    def tearDown(self):
        self.tmp.cleanup()

    def flag(self, name):
        open(os.path.join(self.d, name), "w").close()

    def calls(self):
        try:
            with open(os.path.join(self.d, "calls")) as f:
                return [json.loads(x) for x in f]
        except FileNotFoundError:
            return []

    def run_j(self, args, stdin=b"", timeout=30):
        p = subprocess.run([sys.executable, SCRIPT, *args], input=stdin, capture_output=True,
                           env=self.env, timeout=timeout)
        return p.returncode, p.stdout.decode(), p.stderr.decode()

    def popen(self, args):
        return subprocess.Popen([sys.executable, SCRIPT, *args], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=self.env)

    @staticmethod
    def close(p):
        for f in (p.stdin, p.stdout, p.stderr):
            f.close()

    def assert_off(self, out):
        """The last gain write is the minimum, after the last end of burst or with no burst."""
        self.assertIn("JAMMER OFF: burst ended", out)
        c = self.calls()
        self.assertEqual(c[-1], {"op": "gain", "gain": 0.0})
        ops = [x["op"] for x in c]
        self.assertEqual(ops.count("sob"), ops.count("eob"))
        if "sob" in ops:
            last_sob = len(ops) - 1 - ops[::-1].index("sob")
            self.assertIn("eob", ops[last_sob:])


class Parsing(unittest.TestCase):
    def test_schedule(self):
        self.assertEqual(tj.parse_schedule("0:off,10:30,20.5:42.25,30:quit"),
                         [(0.0, "off"), (10.0, 30.0), (20.5, 42.25), (30.0, "quit")])
        self.assertEqual(tj.parse_schedule(""), [])

    def test_bad_schedules(self):
        for s in ("10", "10:30:1", "a:30", "10:x", "10:30,10:40", "10:30,5:40", "-1:30", "1:nan", "1:inf"):
            with self.assertRaises(ValueError, msg=s):
                tj.parse_schedule(s)


class Refusals(Base):
    def refused(self, args, text):
        rc, out, err = self.run_j(args)
        self.assertEqual(rc, 2, out + err)
        self.assertIn("REFUSED", err)
        self.assertIn(text, err)
        self.assertEqual(self.calls(), [])     # the device was never opened

    def test_on_needs_statements(self):
        self.refused(["--on"], "--ext-att and --max-gain")
        self.refused(["--on", "--ext-att", "60"], "--ext-att and --max-gain")
        self.refused(["--on", "--max-gain", "50"], "--ext-att and --max-gain")

    def test_ext_att_floor(self):
        self.refused(["--on", "--ext-att", "49.9", "--max-gain", "50"], "below 50")

    def test_gain_above_max(self):
        self.refused(ON + ["--gain", "50.25"], "above --max-gain")
        self.refused(ON + ["--schedule", "1:20,2:51"], "above --max-gain")

    def test_other(self):
        self.refused(["--ext-att", "60"], "only used with --on")
        self.refused(["--gain", "quit"], "makes no sense")
        self.refused(["--schedule", "5:30,1:20"], "increasing")
        self.refused(["--freq", "1.2e9"], "from L1")
        self.refused(["--ampl", "0.9"], "--ampl")


class DryRun(Base):
    def test_dry_run_does_not_tune_or_stream(self):
        rc, out, err = self.run_j(["--gain", "30", "--schedule", "1:40,2:off"])
        self.assertEqual(rc, 0, out + err)
        self.assertIn("dry run: nothing tuned", out)
        self.assertNotIn("JAMMER OFF", out)
        ops = [x["op"] for x in self.calls()]
        self.assertEqual(ops, ["open", "gain", "gain"])
        self.assertTrue(all(x["gain"] == 0.0 for x in self.calls() if x["op"] == "gain"))

    def test_gain_outside_device_range(self):
        rc, out, err = self.run_j(["--gain", "95"])
        self.assertEqual(rc, 1)
        self.assertIn("outside the device range", out)

    def test_no_device(self):
        self.flag("no_device")
        rc, out, err = self.run_j(ON + ["--gain", "30"])
        self.assertEqual(rc, 1)
        self.assertIn("ERROR", out)
        self.assertEqual(self.calls(), [])


class Transmit(Base):
    def test_schedule_runs_and_ends_off(self):
        p = self.popen(ON + ["--start-now", "--schedule", "0.3:20,0.6:30,0.9:off,1.2:40,1.5:quit"])
        rc = p.wait(timeout=10)                  # ends by the quit step, stdin still open
        out, err = p.stdout.read().decode(), p.stderr.read().decode()
        self.close(p)
        self.assertEqual(rc, 0, out + err)
        ops = [(x["op"], x.get("gain")) for x in self.calls()]
        self.assertEqual(ops, [
            ("open", None), ("gain", 0.0), ("ant", None), ("rate", None), ("freq", None), ("stream", None),
            ("gain", 0.0),                       # start state off
            ("gain", 20.0), ("sob", None), ("gain", 30.0),
            ("eob", None), ("gain", 0.0),        # off step
            ("gain", 40.0), ("sob", None),
            ("eob", None), ("gain", 0.0)])       # quit
        self.assertIn("schedule quit", out)
        self.assert_off(out)
        freq = [x for x in self.calls() if x["op"] == "freq"][0]["freq"]
        self.assertEqual(freq, 1575620000.0)
        self.assertEqual([x for x in self.calls() if x["op"] == "sob"][0]["ampl"], 0.5)

    def test_schedule_waits_for_t0(self):
        p = self.popen(ON + ["--gain", "10", "--schedule", "0.2:20,60:quit"])
        time.sleep(1.0)
        gains = [x["gain"] for x in self.calls() if x["op"] == "gain"]
        self.assertEqual(gains, [0.0, 10.0])      # no schedule step before t0
        p.stdin.write(b"t0\n")
        p.stdin.flush()
        time.sleep(0.8)
        gains = [x["gain"] for x in self.calls() if x["op"] == "gain"]
        self.assertEqual(gains, [0.0, 10.0, 20.0])
        out, err = p.communicate(b"quit\n", timeout=10)
        self.assertEqual(p.returncode, 0, err)
        self.assert_off(out.decode())

    def test_commands(self):
        rc, out, err = self.run_j(ON, stdin=b"gain 30\nnote hello\nstatus\ngain 50.5\ngain x\nbogus\noff\ngain 45\nquit\n")
        self.assertEqual(rc, 0, out + err)
        gains = [x["gain"] for x in self.calls() if x["op"] == "gain"]
        self.assertEqual(gains, [0.0, 0.0, 30.0, 0.0, 45.0, 0.0])    # 50.5 was never written
        self.assertIn("REFUSED gain 50.5", out)
        self.assertIn("NOTE hello", out)
        self.assertIn("STATUS streaming True", out)
        self.assertIn("unknown command 'bogus'", out)
        self.assert_off(out)

    def test_end_of_input_is_quit(self):
        rc, out, err = self.run_j(ON + ["--gain", "30"], stdin=b"")
        self.assertEqual(rc, 0, out + err)
        self.assertIn("end of input", out)
        self.assert_off(out)

    def test_signals_end_off(self):
        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            with self.subTest(sig=sig):
                try:
                    os.remove(os.path.join(self.d, "calls"))
                except FileNotFoundError:
                    pass
                p = self.popen(ON + ["--gain", "30"])
                time.sleep(1.0)
                p.send_signal(sig)
                out, err = p.communicate(timeout=10)
                self.assertEqual(p.returncode, 0, err)
                self.assertIn("signal %d" % sig, out.decode())
                self.assert_off(out.decode())

    def test_send_error_ends_off(self):
        self.flag("fail_send")
        p = self.popen(ON + ["--gain", "30"])
        rc = p.wait(timeout=10)                  # ends by itself, stdin still open
        out = p.stdout.read().decode()
        self.close(p)
        self.assertEqual(rc, 1)
        self.assertIn("ERROR: RuntimeError: sender", out)
        self.assert_off(out)

    def test_gain_not_taken_is_an_error(self):
        self.flag("stuck_gain")
        rc, out, err = self.run_j(ON + ["--gain", "30"], stdin=b"")
        self.assertEqual(rc, 1)
        self.assertIn("JAMMER OFF NOT CONFIRMED", out)
        self.assertIn("Unplug", out)

    def test_log_file(self):
        log = os.path.join(self.d, "j.txt")
        rc, out, err = self.run_j(ON + ["--gain", "30", "--log", log], stdin=b"quit\n")
        self.assertEqual(rc, 0, out + err)
        with open(log) as f:
            text = f.read()
        self.assertEqual(text, out)
        self.assertIn("ext-att 60 dB (as stated), max-gain 50 dB", text)


if __name__ == "__main__":
    unittest.main()
