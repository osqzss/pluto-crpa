#!/usr/bin/env python3
"""Tests of scripts/t1_passthrough.py without a Pluto and without RF.

iio_attr, iio_reg and iio_readdev are replaced by a stand-in with a small model of the
driver, which records every write together with the state after it. The stand-in
reflects the driver as read from source; it says nothing about the real hardware.

Run: python3 scripts/test_t1_passthrough.py
"""
import array
import json
import os
import pty
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import t1_passthrough as t1  # noqa: E402

SCRIPT = os.path.join(HERE, "t1_passthrough.py")
TARGET = t1.L1 + 3000000

FAKE = r'''#!/usr/bin/env python3
import array, json, os, sys
D = os.environ["FAKE_DIR"]
tool = os.path.basename(sys.argv[0])
args = sys.argv[1:]

def load(name, default):
    try:
        with open(os.path.join(D, name)) as f:
            return json.load(f)
    except FileNotFoundError:
        return default

def save(name, value):
    with open(os.path.join(D, name), "w") as f:
        json.dump(value, f)

def die(msg="fake failure"):
    print(msg, file=sys.stderr)
    sys.exit(1)

if os.path.exists(os.path.join(D, "dead")):
    die("Unable to create IIO context")
s = load("state", None)
log = load("log", [])

if tool == "iio_readdev":
    if os.path.exists(os.path.join(D, "fail_readdev")):
        die()
    log.append({"op": "capture", "state": s})
    save("log", log)
    a = array.array("h", [100, -100, 2047, 50] * 65536)
    sys.stdout.buffer.write(a.tobytes())
    sys.exit(0)

args = args[2:]    # -u uri
is_write = False
if tool == "iio_reg":
    addr = str(int(args[1], 0) & 0x7fffffff)
    key = "reg." + addr
    val = args[2] if len(args) > 2 else None
else:
    if args[0] == "-D":
        key, val = "dbg." + args[2], (args[3] if len(args) > 3 else None)
    elif args[0] == "-d":
        key, val = "dev." + args[2], (args[3] if len(args) > 3 else None)
    else:
        key = args[0] + "." + args[3] + "." + args[4]
        val = args[5] if len(args) > 5 else None

if val is None:
    if key not in s:
        die("no attribute " + key)
    print(s[key])
    sys.exit(0)

log_key = key + "=" + val
n = load("nwrites", 0) + 1
save("nwrites", n)
fail_n = load("fail_nth", 0)
if n == fail_n:
    log.append({"op": "failed", "key": log_key})
    save("log", log)
    die()
for m in load("fail_match", []):
    if m in log_key:
        log.append({"op": "failed", "key": log_key})
        save("log", log)
        die()

SEL = [str(0x4418 + c * 0x40) for c in range(4)]
if key == "dbg.loopback":
    if val == "2":
        for c, a in enumerate(SEL):
            if s["reg." + a] != "0x8":
                s["scratch.%d" % c] = s["reg." + a]
            s["reg." + a] = "0x8"
    elif val == "0":
        for c, a in enumerate(SEL):
            if s["reg." + a] == "0x8":
                s["reg." + a] = s.get("scratch.%d" % c, "0x0")
    s[key] = val
elif key.startswith("reg."):
    if key != "reg.%d" % 0x4044:
        s[key] = "0x%x" % int(val, 0)
elif key == "-o.altvoltage1.frequency":
    # TX quad calibration above the 100 MHz threshold: LO on for its duration
    if abs(int(val) - load("last_cal", 2450000000)) > 100000000:
        save("last_cal", int(val))
        log.append({"op": "cal", "tx_lo": int(val), "state": s})
    s[key] = val
elif key.endswith("rf_bandwidth"):
    log.append({"op": "cal", "tx_lo": int(s["-o.altvoltage1.frequency"]), "state": s})
    s[key] = val
elif key.endswith("hardwaregain"):
    s[key] = "%.6f dB" % float(val)
elif key == "-i.voltage0.sampling_frequency":
    s[key] = s["-o.voltage0.sampling_frequency"] = str(int(val) - 1 if int(val) % 2 == 0 else int(val))
else:
    s[key] = val
log.append({"op": "write", "key": log_key, "state": s})
save("state", s)
save("log", log)
'''


def initial_state():
    s = {"reg.%d" % 0x0044: "0x0", "reg.%d" % 0x4048: "0x0", "reg.%d" % 0x404c: "0x1",
         "reg.%d" % 0x005c: "0x1", "dev.ensm_mode": "fdd", "dbg.loopback": "0",
         "-o.altvoltage0.frequency": "2400000000", "-o.altvoltage1.frequency": "2450000000",
         "-o.altvoltage0.frequency_available": "[325000000 1 3800000000]",
         "-o.altvoltage1.powerdown": "0",
         "-i.voltage0.sampling_frequency": "30719999", "-o.voltage0.sampling_frequency": "30719999",
         "-i.voltage0.rf_bandwidth": "18000000", "-o.voltage0.rf_bandwidth": "18000000",
         "-i.voltage0.hardwaregain_available": "[-3 1 71]"}
    for c in range(4):
        s["reg.%d" % (0x4418 + c * 0x40)] = "0x0"
    for ch in ("voltage0", "voltage1"):
        s["-i.%s.gain_control_mode" % ch] = "slow_attack"
        s["-i.%s.hardwaregain" % ch] = "30.000000 dB"
        s["-i.%s.rssi" % ch] = "80.00 dB"
        s["-o.%s.hardwaregain" % ch] = "-10.000000 dB"
    return s


def sel_of(s):
    return [int(s["reg.%d" % (0x4418 + c * 0x40)], 0) for c in range(4)]


class Base(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="t1test")
        self.addCleanup(shutil.rmtree, self.d)
        self.bin = os.path.join(self.d, "bin")
        os.mkdir(self.bin)
        for tool in ("iio_attr", "iio_reg", "iio_readdev"):
            path = os.path.join(self.bin, tool)
            with open(path, "w") as f:
                f.write(FAKE.replace("#!/usr/bin/env python3", "#!" + sys.executable, 1))
            os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)
        self.put("state", initial_state())
        self.env = dict(os.environ, FAKE_DIR=self.d, PATH=self.bin + os.pathsep + os.environ["PATH"])
        self.out = os.path.join(self.d, "out")
        self.logfile = os.path.join(self.d, "run.log")

    def put(self, name, value):
        with open(os.path.join(self.d, name), "w") as f:
            json.dump(value, f)

    def get(self, name, default=None):
        try:
            with open(os.path.join(self.d, name)) as f:
                return json.load(f)
        except FileNotFoundError:
            return default

    def state(self):
        return self.get("state")

    def set_attr(self, key, value):
        s = self.state()
        s[key] = value
        self.put("state", s)

    def writes(self):
        return [e for e in self.get("log", []) if e["op"] in ("write", "failed")]

    def output(self):
        with open(self.out) as f:
            return f.read()

    def assert_safe(self):
        s = self.state()
        self.assertEqual(sel_of(s), [0, 0, 0, 0])
        self.assertEqual(s["dbg.loopback"], "0")
        self.assertEqual(s["-o.altvoltage1.powerdown"], "1")
        self.assertEqual(int(s["-o.altvoltage1.frequency"]), t1.TX_PARK)
        self.assertEqual(s["-o.voltage0.hardwaregain"], "-89.750000 dB")
        self.assertEqual(s["-o.voltage1.hardwaregain"], "-89.750000 dB")

    def assert_rf_never_on(self):
        """The LO was never powered up by the tool."""
        for w in self.writes():
            self.assertNotIn("altvoltage1.powerdown=0", w["key"])

    def run_plain(self, *extra, timeout=60):
        with open(self.out, "w") as o:
            p = subprocess.run([sys.executable, SCRIPT, "--log", self.logfile, *extra],
                               stdin=subprocess.DEVNULL, stdout=o, stderr=subprocess.STDOUT,
                               env=self.env, timeout=timeout)
        return p.returncode

    def start_on(self, *extra, confirm=True, script=SCRIPT, log=True):
        """Start --on on a pseudo terminal; wait until the path is on when confirm is set."""
        self.master, slave = pty.openpty()
        self.addCleanup(self.close_master)
        o = open(self.out, "w")
        self.addCleanup(o.close)
        args = list(extra) or ["--tx-att", "60"]
        logargs = ["--log", self.logfile] if log else []
        self.proc = subprocess.Popen(
            [sys.executable, script, "--on", "--poll", "0.2", *logargs, *args],
            stdin=slave, stdout=o, stderr=subprocess.STDOUT, env=self.env, start_new_session=True)
        os.close(slave)
        self.addCleanup(self.kill_proc)
        self.wait_output("Type CONDUCTED")
        if confirm:
            self.send("CONDUCTED")
            self.wait_output("ON: RX1")

    def close_master(self):
        if self.master is not None:
            os.close(self.master)
            self.master = None

    def kill_proc(self):
        if self.proc.poll() is None:
            self.proc.kill()
            self.proc.wait()

    def send(self, line):
        os.write(self.master, line.encode() + b"\n")

    def wait_output(self, text, timeout=60):
        end = time.time() + timeout
        while time.time() < end:
            if text in self.output():
                return
            if self.proc.poll() is not None and text not in self.output():
                self.fail("process ended without %r:\n%s" % (text, self.output()))
            time.sleep(0.02)
        self.fail("no %r:\n%s" % (text, self.output()))


class Settings(unittest.TestCase):
    def ok(self, **kw):
        a = dict(delta=3000000, fs=10000000, bw=9000000, tx_att=30)
        a.update(kw)
        return t1.check_settings(**a)

    def test_defaults_pass(self):
        self.assertEqual(self.ok(), [])

    def test_negative_delta_passes(self):
        self.assertEqual(self.ok(delta=-3000000), [])

    def test_rejected(self):
        for kw in (dict(delta=0), dict(delta=1000000), dict(delta=-1500000),
                   dict(fs=2000000, bw=2000000), dict(fs=40000000),
                   dict(bw=11000000),              # more than fs
                   dict(bw=100000), dict(bw=25000000, fs=30000000),
                   dict(bw=7000000),               # edge 4.023 MHz outside bw/2
                   dict(delta=4500000),            # edge outside bw/2 and fs/2
                   dict(tx_att=-1), dict(tx_att=90), dict(tx_att=10.1)):
            self.assertTrue(self.ok(**kw), kw)


class Dry(Base):
    def test_dry_run_keeps_tx_away_from_l1(self):
        self.assertEqual(self.run_plain(), 0, self.output())
        self.assert_safe()
        self.assert_rf_never_on()
        for w in self.writes():
            if "altvoltage1.frequency" in w["key"]:
                self.assertTrue(w["key"].endswith("=%d" % t1.TX_PARK), w)
        for e in self.get("log"):
            if e["op"] == "cal":
                self.assertEqual(e["tx_lo"], t1.TX_PARK)
                self.assertEqual(e["state"]["-o.altvoltage1.powerdown"], "1")
                self.assertEqual(e["state"]["-o.voltage0.hardwaregain"], "-89.750000 dB")
        self.assertIn("dBFS", self.output())

    def test_dry_run_applies_rx_settings(self):
        self.assertEqual(self.run_plain("--rx-gain", "40", "--delta", "-3000000"), 0, self.output())
        s = self.state()
        self.assertEqual(int(s["-o.altvoltage0.frequency"]), t1.L1 - 3000000)
        for ch in ("voltage0", "voltage1"):
            self.assertEqual(s["-i.%s.gain_control_mode" % ch], "manual")
            self.assertEqual(s["-i.%s.hardwaregain" % ch], "40.000000 dB")

    def test_second_run_writes_no_bandwidth(self):
        self.assertEqual(self.run_plain(), 0, self.output())
        self.put("log", [])
        self.assertEqual(self.run_plain(), 0, self.output())
        self.assertEqual([e for e in self.get("log") if e["op"] == "cal"], [])

    def test_failure_at_every_write_ends_safe(self):
        self.assertEqual(self.run_plain(), 0, self.output())
        total = self.get("nwrites")
        for k in range(1, total + 1):
            self.put("state", initial_state())
            self.put("nwrites", 0)
            self.put("log", [])
            self.put("last_cal", 2450000000)
            self.put("fail_nth", k)
            self.run_plain()
            self.assert_safe()
            self.assert_rf_never_on()

    def test_capture_failure_ends_safe(self):
        self.put("fail_readdev", 1)
        self.assertEqual(self.run_plain(), 1)
        self.assert_safe()


class Check(Base):
    def test_check_writes_nothing(self):
        self.assertEqual(self.run_plain("--check"), 0, self.output())
        self.assertEqual(self.writes(), [])
        self.assertIn("CHECK passed", self.output())
        self.assertIn("dBFS", self.output())

    def test_check_refuses_like_the_others(self):
        self.set_attr("reg.%d" % 0x0044, "0x4")
        self.assertEqual(self.run_plain("--check"), 1)
        self.assertEqual(self.writes(), [])


class Refusals(Base):
    def assert_refused(self, *args, rc=1):
        self.assertEqual(self.run_plain(*args), rc, self.output())
        self.assertEqual(self.writes(), [], "must not write")

    def test_bad_settings_refused_without_any_write(self):
        self.assert_refused("--delta", "100000")
        self.assertIn("REFUSED", self.output())

    def test_on_without_tx_att(self):
        self.assert_refused("--on", rc=2)

    def test_tx_att_without_on(self):
        self.assert_refused("--tx-att", "30", rc=2)

    def test_on_and_off(self):
        self.assert_refused("--on", "--off", "--tx-att", "30", rc=2)

    def test_not_2r2t_adc(self):
        self.set_attr("reg.%d" % 0x0044, "0x4")
        self.assert_refused()
        self.assertIn("2R2T", self.output())

    def test_not_2r2t_dac(self):
        self.set_attr("reg.%d" % 0x4048, "0x20")
        self.assert_refused()
        self.assertIn("2R2T", self.output())

    def test_wrong_rate_register(self):
        self.set_attr("reg.%d" % 0x404c, "0x3")
        self.assert_refused()

    def test_adc_status_low(self):
        self.set_attr("reg.%d" % 0x005c, "0x0")
        self.assert_refused()

    def test_not_fdd(self):
        self.set_attr("dev.ensm_mode", "alert")
        self.assert_refused()

    def test_path_already_on(self):
        self.set_attr("dbg.loopback", "2")
        self.assert_refused()

    def test_tx_dma_active(self):
        self.set_attr("reg.%d" % 0x4418, "0x2")
        self.assert_refused()

    def test_rx_gain_out_of_range(self):
        self.assert_refused("--rx-gain", "90")

    def test_link_dead(self):
        self.put("dead", 1)
        self.assertEqual(self.run_plain(), 1)
        self.assertIn("cannot check", self.output())

    def test_on_needs_terminal(self):
        self.assert_refused("--on", "--tx-att", "30")
        self.assertIn("interactive", self.output())

    def test_wrong_confirmation(self):
        for answer in ("yes", "conducted", ""):
            self.start_on(confirm=False)
            self.send(answer)
            self.assertEqual(self.proc.wait(30), 1)
            self.assertEqual(self.writes(), [], "must not write")
            self.close_master()

    def test_ctrl_c_at_prompt(self):
        self.start_on(confirm=False)
        self.proc.send_signal(signal.SIGINT)
        self.assertEqual(self.proc.wait(30), 128 + signal.SIGINT)
        self.assertEqual(self.writes(), [])

    def test_eof_at_prompt(self):
        self.start_on(confirm=False)
        self.close_master()
        self.assertEqual(self.proc.wait(30), 1)
        self.assertEqual(self.writes(), [])


class On(Base):
    def test_lo_comes_up_last(self):
        self.start_on("--tx-att", "42.5")
        self.send("quit")
        self.assertEqual(self.proc.wait(60), 0, self.output())
        ups = [w for w in self.writes() if w["key"].endswith("altvoltage1.powerdown=0")]
        self.assertEqual(len(ups), 1)
        s = ups[0]["state"]
        self.assertEqual(sel_of(s), t1.PATH_SEL)
        self.assertEqual(s["dbg.loopback"], "2")
        self.assertEqual(int(s["-o.altvoltage1.frequency"]), TARGET)
        self.assertEqual(int(s["-o.altvoltage0.frequency"]), TARGET)
        self.assertEqual(s["-o.voltage0.hardwaregain"], "-42.500000 dB")
        self.assertEqual(s["-o.voltage1.hardwaregain"], "-89.750000 dB")
        self.assert_safe()

    def test_calibration_near_l1_is_before_the_path(self):
        self.start_on()
        self.send("quit")
        self.proc.wait(60)
        cals = [e for e in self.get("log") if e["op"] == "cal" and e["tx_lo"] == TARGET]
        self.assertEqual(len(cals), 1)
        s = cals[0]["state"]
        self.assertEqual(sel_of(s), [0, 0, 0, 0])
        self.assertEqual(s["-o.altvoltage1.powerdown"], "1")
        self.assertEqual(s["-o.voltage0.hardwaregain"], "-89.750000 dB")

    def test_commands(self):
        self.start_on()
        for cmd, expect in (("rx 44", "RX gain 44 dB"), ("tx 33.25", "TX1 attenuation 33.25"),
                            ("level", "dBFS"), ("status", "RSSI"), ("note prn12 cn0 41", "NOTE prn12")):
            self.send(cmd)
            self.wait_output(expect)
        s = self.state()
        self.assertEqual(s["-i.voltage0.hardwaregain"], "44.000000 dB")
        self.assertEqual(s["-i.voltage1.hardwaregain"], "44.000000 dB")
        self.assertEqual(s["-o.voltage0.hardwaregain"], "-33.250000 dB")
        self.send("quit")
        self.assertEqual(self.proc.wait(60), 0, self.output())
        self.assert_safe()
        with open(self.logfile) as f:
            log = f.read()
        for text in ("delta 3000000", "RX gain 44 dB", "TX1 attenuation 33.25",
                     "NOTE prn12 cn0 41", "Safe state"):
            self.assertIn(text, log)

    def test_bad_commands_do_not_stop_or_change(self):
        self.start_on("--tx-att", "60")
        before = self.state()
        for cmd in ("rx abc", "rx 99", "tx -1", "tx 90", "tx 1.1", "tx", "rx", "bogus"):
            self.send(cmd)
        self.send("note after")
        self.wait_output("NOTE after")
        self.assertIsNone(self.proc.poll())
        self.assertEqual(self.state(), before)
        self.send("q")
        self.assertEqual(self.proc.wait(60), 0)

    def test_signals_end_safe(self):
        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP, signal.SIGQUIT):
            self.put("state", initial_state())
            self.put("last_cal", 2450000000)
            with open(self.out, "w"):
                pass
            self.start_on()
            self.proc.send_signal(sig)
            self.assertEqual(self.proc.wait(60), 128 + sig, self.output())
            self.assert_safe()
            self.close_master()

    def test_second_signal_during_cleanup_is_ignored(self):
        self.start_on()
        self.proc.send_signal(signal.SIGINT)
        for _ in range(5):
            time.sleep(0.01)
            if self.proc.poll() is None:
                self.proc.send_signal(signal.SIGINT)
        self.proc.wait(60)
        self.assert_safe()

    def test_end_of_input_ends_safe(self):
        self.start_on()
        self.close_master()
        self.proc.wait(60)
        self.assert_safe()

    def test_failure_at_every_setup_write_ends_safe(self):
        self.start_on()
        self.send("quit")
        self.proc.wait(60)
        writes = self.writes()
        up = [i for i, w in enumerate(writes) if w["key"].endswith("altvoltage1.powerdown=0")][0]
        stopped = 0
        for k in range(1, up + 2):
            self.put("state", initial_state())
            self.put("nwrites", 0)
            self.put("log", [])
            self.put("last_cal", 2450000000)
            self.put("fail_nth", k)
            with open(self.out, "w"):
                pass
            self.close_master()
            self.start_on(confirm=False)
            self.send("CONDUCTED")
            # A failed write in the first safe state is retried and succeeds, and the tool
            # goes on to transmit, correctly. Any other failure must stop it.
            while self.proc.poll() is None and "ON: RX1" not in self.output():
                time.sleep(0.02)
            if self.proc.poll() is None:
                self.send("quit")
            self.assertIn(self.proc.wait(60), (0, 1), "write %d\n%s" % (k, self.output()))
            self.assert_safe()
            stopped += self.proc.returncode == 1
        self.assertGreater(stopped, 5)

    def test_data_sel_changed_by_someone_else(self):
        self.start_on()
        self.set_attr("reg.%d" % 0x4418, "0x2")
        self.assertEqual(self.proc.wait(60), 1)
        self.assertIn("data_sel changed", self.output())
        self.assert_safe()

    def test_lo_moved_by_someone_else(self):
        self.start_on()
        self.set_attr("-o.altvoltage1.frequency", "1575420000")
        self.assertEqual(self.proc.wait(60), 1)
        self.assertIn("TX LO moved", self.output())
        self.assert_safe()

    def test_adc_status_lost(self):
        self.start_on()
        self.set_attr("reg.%d" % 0x005c, "0x0")
        self.assertEqual(self.proc.wait(60), 1)
        self.assert_safe()

    def test_link_lost(self):
        self.start_on()
        self.put("dead", 1)
        self.assertEqual(self.proc.wait(120), 3)
        self.assertIn("SAFE STATE NOT CONFIRMED", self.output())
        self.assertIn("power-cycle", self.output())

    def test_one_cleanup_step_failing_does_not_skip_the_others(self):
        self.start_on()
        self.put("fail_match", ["altvoltage1.powerdown=1"])
        self.send("quit")
        self.assertEqual(self.proc.wait(60), 3)
        s = self.state()
        self.assertEqual(sel_of(s), [0, 0, 0, 0])
        self.assertEqual(s["-o.voltage0.hardwaregain"], "-89.750000 dB")
        self.assertEqual(int(s["-o.altvoltage1.frequency"]), t1.TX_PARK)
        self.assertIn("SAFE STATE NOT CONFIRMED", self.output())

    def test_transient_cleanup_failure_is_retried(self):
        self.start_on()
        self.put("fail_nth", self.get("nwrites") + 1)   # the first cleanup write
        self.send("quit")
        self.assertEqual(self.proc.wait(60), 0, self.output())
        self.assert_safe()

    def test_default_log_goes_to_results(self):
        tree = os.path.join(self.d, "tree", "scripts")
        os.makedirs(tree)
        script = os.path.join(tree, "t1_passthrough.py")
        shutil.copy(SCRIPT, script)
        self.start_on("--tx-att", "60", script=script, log=False)
        self.send("quit")
        self.assertEqual(self.proc.wait(60), 0, self.output())
        names = os.listdir(os.path.join(self.d, "tree", "results"))
        self.assertEqual(len(names), 1)
        self.assertRegex(names[0], r"^t1_\d{8}-\d{6}\.txt$")


class Off(Base):
    def test_off_from_running_state(self):
        s = self.state()
        s["dbg.loopback"] = "2"
        s["-o.altvoltage1.frequency"] = str(TARGET)
        s["-o.voltage0.hardwaregain"] = "-20.000000 dB"
        for c, v in enumerate(("0x8", "0x8", "0x3", "0x3")):
            s["reg.%d" % (0x4418 + c * 0x40)] = v
        self.put("state", s)
        self.assertEqual(self.run_plain("--off"), 0, self.output())
        self.assert_safe()

    def test_off_works_when_not_2r2t(self):
        self.set_attr("reg.%d" % 0x0044, "0x4")
        self.assertEqual(self.run_plain("--off"), 0, self.output())
        self.assert_safe()

    def test_off_link_dead(self):
        self.put("dead", 1)
        self.assertEqual(self.run_plain("--off"), 3)
        self.assertIn("power-cycle", self.output())


class Levels(Base):
    def test_level_values(self):
        os.environ["FAKE_DIR"] = self.d
        old = os.environ["PATH"]
        os.environ["PATH"] = self.env["PATH"]
        try:
            text = t1.Pluto("ip:fake").levels()
        finally:
            os.environ["PATH"] = old
            del os.environ["FAKE_DIR"]
        # ch0/1 is constant, so the mean removal leaves nothing; ch2/3 clips on I.
        self.assertIn("clipped 0/", text.split("|")[0])
        self.assertIn("peak 2047 clipped 65536/131072", text.split("|")[1])


if __name__ == "__main__":
    unittest.main()
