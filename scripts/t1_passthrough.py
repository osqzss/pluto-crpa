#!/usr/bin/env python3
"""T1: RX1 -> TX1 pass-through in the PL on the current firmware (TX data_sel = 8).

Conducted or shielded use only: TX1 must go through a DC block to the GNSS receiver, with
at least 50 dB in total between external attenuators and the TX attenuation set here.

Usage: scripts/t1_passthrough.py --check [settings]              read-only checks
       scripts/t1_passthrough.py [settings]                      dry run
       scripts/t1_passthrough.py --on --tx-att DB --min-tx-att DB [settings]   transmit
       scripts/t1_passthrough.py --off                           force the safe state
Settings: --delta HZ --fs HZ --bw HZ --rx-gain DB. Needs iio_attr, iio_reg, iio_readdev.
--on needs --min-tx-att DB, a floor for --tx-att and the tx command: 50 minus the external
attenuation in the TX1 path, so 50 with none. The tool cannot see the external attenuator;
the operator states it through this value. The floor is not a limit on loop gain: it does
not depend on the rx command.

Dry run: checks the settings and the Pluto, sets up RX and the path with TX attenuation
at maximum and the TX LO powered down and parked at 2400 MHz, reads the levels, removes
the path. The TX LO is never tuned near L1.

--on: asks for a typed confirmation of the cabling, then stays in the foreground and
accepts commands (type "help"). Quit, Ctrl-C, SIGTERM, SIGHUP, end of input or any error
all lead to the safe state: TX attenuation maximum, path off, TX LO powered down, then
parked. Settings and commands go to a log in results/.

Limits that no option here removes:
- The cleanup needs the link to the Pluto. If USB drops, the host dies or the script gets
  SIGKILL, the path stays on until --off or a Pluto power cycle. After a power cycle the
  TX data_sel is back to DDS with scale 0.
- "Powered down" is not strictly silent. tx-lo-powerdown-managed-enable is set on Pluto,
  so a TX quad calibration powers the TX LO up for its duration and then restores it. The
  driver runs one on every bandwidth write and on a TX retune of more than 100 MHz. These
  are at TX attenuation maximum. The tool skips bandwidth writes that change nothing and
  does all of them with the LO parked; on --on the retune to L1 + delta happens before
  the path is connected.
- The powerdown readback is the driver's cached state, not a measurement.
"""
import argparse
import array
import math
import os
import select
import signal
import subprocess
import sys
import time

L1 = 1575420000
CA_HALF_BW = 1023000      # C/A main lobe half width
LO_GUARD = 500000         # minimum gap between the LO and the main lobe edge
TX_PARK = 2400000000
ADC = "cf-ad9361-lpc"
CORE = 0x80000000         # DEBUGFS_DRA_PCORE_REG_MAGIC
TX_MAX_ATT = 89.75
FS_MIN = 2084000          # measured floor without FIR, results/t0b_hw_test.md
FS_MAX = 30720000         # l_clk = 2 x fs, limited to 61.44 MHz
BW_MIN = 200000           # driver limit
BW_MAX = 20000000         # AD9363
FS_TOL = 10               # the driver reads back e.g. 2999999 for 3000000
BW_TOL = 1000
LO_TOL = 100
LO_MATCH_TOL = 10         # RX LO against TX LO
PATH_SEL = [8, 8, 3, 3]   # TX2 unused: zero, not whatever RX2 carries
LEVEL_SAMPLES = 65536
CALL_TIMEOUT = 20
SAFE_TIMEOUT = 10
CONFIRM = "CONDUCTED"


class Stop(BaseException):
    """A stop signal. Not an Exception, so that no error handler can swallow it."""

    def __init__(self, signum):
        super().__init__(signum)
        self.signum = signum


STOP_SIGNALS = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP, signal.SIGQUIT)


def set_signals(handler):
    for s in STOP_SIGNALS:
        signal.signal(s, handler)


def on_signal(signum, _frame):
    # One stop is enough: a repeated Ctrl-C must not interrupt the cleanup.
    set_signals(signal.SIG_IGN)
    raise Stop(signum)


class Log:
    """Console and optional log file. A closed stdout must not stop the cleanup."""

    def __init__(self):
        self.f = None

    def open(self, path):
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        self.f = open(path, "a", encoding="ascii", errors="replace")

    def say(self, msg):
        try:
            print(msg, flush=True)
        except OSError:
            pass
        if self.f:
            try:
                self.f.write(time.strftime("%Y-%m-%dT%H:%M:%S ") + msg + "\n")
                self.f.flush()
            except OSError:
                pass


LOG = Log()


def num(text):
    """First number of an attribute value such as '60.000000 dB'."""
    return float(text.split()[0])


def avail_range(text):
    """Parse '[min step max]'."""
    lo, step, hi = (float(v) for v in text.strip().strip("[]").split())
    return lo, step, hi


def check_tx_att(att, min_att=0.0):
    if not 0 <= att <= TX_MAX_ATT:
        return "TX attenuation %g dB is outside 0 to %g" % (att, TX_MAX_ATT)
    if abs(att * 4 - round(att * 4)) > 1e-9:
        return "TX attenuation %g dB is not a multiple of 0.25" % att
    if att < min_att:
        return "TX attenuation %g dB is below the minimum of %g dB" % (att, min_att)
    return None


def check_settings(delta, fs, bw, tx_att=None, min_tx_att=0.0):
    """Consistency of the settings, without the Pluto. Returns a list of problems."""
    out = []
    if abs(delta) < CA_HALF_BW + LO_GUARD:
        out.append("|delta| %d Hz puts the LO less than %d Hz from the C/A main lobe"
                   % (abs(delta), LO_GUARD))
    edge = abs(delta) + CA_HALF_BW
    if not FS_MIN <= fs <= FS_MAX:
        out.append("fs %d is outside %d to %d" % (fs, FS_MIN, FS_MAX))
    if not BW_MIN <= bw <= BW_MAX:
        out.append("bandwidth %d is outside %d to %d" % (bw, BW_MIN, BW_MAX))
    if bw > fs:
        out.append("bandwidth %d is more than fs %d" % (bw, fs))
    if edge * 2 > bw:
        out.append("signal edge at %d Hz is outside the bandwidth, +/-%d Hz" % (edge, bw // 2))
    if edge * 2 > fs:
        out.append("signal edge at %d Hz is outside fs/2 = %d Hz" % (edge, fs // 2))
    problem = check_tx_att(min_tx_att)
    if problem:
        out.append("--min-tx-att: " + problem)
    elif tx_att is not None:
        problem = check_tx_att(tx_att, min_tx_att)
        if problem:
            out.append(problem)
    return out


class Pluto:
    def __init__(self, uri):
        self.uri = uri
        self.timeout = CALL_TIMEOUT

    def run(self, *cmd):
        # A new session keeps Ctrl-C at the terminal away from a write in progress.
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=self.timeout,
                           start_new_session=True)
        if p.returncode:
            raise RuntimeError(" ".join(cmd) + ": " + (p.stdout + p.stderr).strip())
        return p.stdout.strip()

    def phy(self, direction, chan, name, *val):
        return self.run("iio_attr", "-u", self.uri, direction, "-c", "ad9361-phy", chan, name, *val)

    def dev_attr(self, name):
        return self.run("iio_attr", "-u", self.uri, "-d", "ad9361-phy", name)

    def loopback(self, *val):
        return self.run("iio_attr", "-u", self.uri, "-D", "ad9361-phy", "loopback", *val)

    def reg(self, addr, *val):
        return int(self.run("iio_reg", "-u", self.uri, ADC, hex(CORE | addr),
                            *[hex(v) for v in val]) or "0", 0)

    def sel(self):
        return [self.reg(0x4418 + c * 0x40) & 0xf for c in range(4)]

    def set_sel(self, chan, value):
        self.reg(0x4418 + chan * 0x40, value)

    def tx_att(self, chan, att):
        self.phy("-o", chan, "hardwaregain", "%.2f" % -att)

    def read_tx_att(self, chan):
        return -num(self.phy("-o", chan, "hardwaregain"))

    def lo(self, chan):
        return int(num(self.phy("-o", chan, "frequency")))

    def lo_down(self):
        return self.phy("-o", "altvoltage1", "powerdown") == "1"

    def adc_ok(self):
        return bool(self.reg(0x005c) & 1)

    def levels(self):
        """ADC level per stream pair, from one block of samples. Opening an RX buffer only
        changes adc_enable_* (docs/interface.md, Section 3); it does not touch the path."""
        p = subprocess.run(["iio_readdev", "-u", self.uri, "-b", str(LEVEL_SAMPLES),
                            "-s", str(LEVEL_SAMPLES), ADC,
                            "voltage0", "voltage1", "voltage2", "voltage3"],
                           capture_output=True, timeout=self.timeout, start_new_session=True)
        if p.returncode:
            raise RuntimeError("iio_readdev: " + p.stderr.decode("ascii", "replace").strip())
        a = array.array("h")
        a.frombytes(p.stdout[:len(p.stdout) // 2 * 2])
        if sys.byteorder != "little":
            a.byteswap()
        n = len(a) // 4
        if n < 1000:
            raise RuntimeError("iio_readdev returned only %d samples" % n)
        out = []
        for name, first in (("ch0/1", 0), ("ch2/3", 2)):
            i, q = a[first:n * 4:4], a[first + 1:n * 4:4]
            mi, mq = sum(i) / n, sum(q) / n
            power = sum((x - mi) ** 2 for x in i) / n + sum((x - mq) ** 2 for x in q) / n
            dbfs = 10 * math.log10(max(power, 1e-3) / 2048.0 ** 2)
            peak = max(max(abs(x) for x in i), max(abs(x) for x in q))
            clip = sum(1 for x in i if x >= 2047 or x <= -2048) + \
                sum(1 for x in q if x >= 2047 or x <= -2048)
            out.append("%s %.1f dBFS peak %d clipped %d/%d" % (name, dbfs, peak, clip, 2 * n))
        return "ADC " + " | ".join(out)


def precheck(p, rx_gain, delta):
    """Read-only checks before anything is written. Returns a list of problems."""
    out = []
    if p.reg(0x0044) & 0x4:
        out.append("ADC r1_mode is set: the Pluto is not in 2R2T")
    if p.reg(0x4048) & 0x20:
        out.append("DAC r1_mode is set: the Pluto is not in 2R2T")
    if p.reg(0x404c) != 1:
        out.append("DAC rate register is not 1, as expected in CMOS 2R2T")
    if not p.adc_ok():
        out.append("adc_status is low: RX frame not toggling or delay not locked")
    ensm = p.dev_attr("ensm_mode")
    if ensm != "fdd":
        out.append("ensm_mode is %s, not fdd" % ensm)
    if p.loopback() != "0":
        out.append("debugfs loopback is %s, not 0: a path may be active. Use --off first"
                   % p.loopback())
    sel = p.sel()
    if not all(s in (0, 3) for s in sel):
        out.append("TX data_sel is %s: another path or a TX buffer may be active. Use --off "
                   "first if it is safe to stop it" % sel)
    lo, step, hi = avail_range(p.phy("-i", "voltage0", "hardwaregain_available"))
    if not lo <= rx_gain <= hi:
        out.append("RX gain %d dB is outside %g to %g" % (rx_gain, lo, hi))
    lo, step, hi = avail_range(p.phy("-o", "altvoltage0", "frequency_available"))
    if not lo <= L1 + delta <= hi or not lo <= TX_PARK <= hi:
        out.append("LO %d or park %d is outside %g to %g" % (L1 + delta, TX_PARK, lo, hi))
    return out


def safe_state(p):
    """Bring TX to the safe state. Every step runs whatever happened to the others; failed
    steps get one more try unless nothing at all worked, which means the link is gone.
    Returns the steps not confirmed."""
    old = {s: signal.getsignal(s) for s in STOP_SIGNALS}
    set_signals(signal.SIG_IGN)
    p.timeout = SAFE_TIMEOUT

    def verify():
        problems = []
        if p.read_tx_att("voltage0") != TX_MAX_ATT or p.read_tx_att("voltage1") != TX_MAX_ATT:
            problems.append("TX attenuation")
        if p.loopback() != "0":
            problems.append("loopback")
        if p.sel() != [0, 0, 0, 0]:
            problems.append("data_sel")
        if not p.lo_down():
            problems.append("powerdown")
        if abs(p.lo("altvoltage1") - TX_PARK) > LO_TOL:
            problems.append("TX LO")
        if problems:
            raise RuntimeError("readback wrong: " + ", ".join(problems))

    steps = [("TX1 attenuation", lambda: p.tx_att("voltage0", TX_MAX_ATT)),
             ("TX2 attenuation", lambda: p.tx_att("voltage1", TX_MAX_ATT)),
             ("loopback off", lambda: p.loopback("0"))]
    steps += [("data_sel ch%d" % c, lambda c=c: p.set_sel(c, 0)) for c in range(4)]
    # Down first, so that the tone stops at once and stays off if the retune fails.
    steps += [("TX LO powerdown", lambda: p.phy("-o", "altvoltage1", "powerdown", "1")),
              ("TX LO park", lambda: p.phy("-o", "altvoltage1", "frequency", str(TX_PARK))),
              ("readback", verify)]
    failed = steps
    errors = {}
    for _ in range(2):
        retry = []
        for name, step in failed:
            try:
                step()
                errors.pop(name, None)
            except Exception as e:
                errors[name] = str(e)
                retry.append((name, step))
        if not retry or len(retry) == len(failed):
            failed = retry
            break
        failed = retry

    p.timeout = CALL_TIMEOUT
    for s, handler in old.items():
        signal.signal(s, handler)
    for name, _ in failed:
        LOG.say("SAFE STATE: %s failed: %s" % (name, errors.get(name, "")))
    return [name for name, _ in failed]


def report(p):
    LOG.say("RX LO %d | TX LO %d | fs %s | RX bw %s | TX bw %s" % (
        p.lo("altvoltage0"), p.lo("altvoltage1"), p.phy("-i", "voltage0", "sampling_frequency"),
        p.phy("-i", "voltage0", "rf_bandwidth"), p.phy("-o", "voltage0", "rf_bandwidth")))
    LOG.say("RX gain %s %s / %s %s | RSSI %s / %s" % (
        p.phy("-i", "voltage0", "gain_control_mode"), p.phy("-i", "voltage0", "hardwaregain"),
        p.phy("-i", "voltage1", "gain_control_mode"), p.phy("-i", "voltage1", "hardwaregain"),
        p.phy("-i", "voltage0", "rssi"), p.phy("-i", "voltage1", "rssi")))
    LOG.say("TX attenuation %.2f / %.2f dB | TX LO powerdown %s | loopback %s | data_sel %s" % (
        p.read_tx_att("voltage0"), p.read_tx_att("voltage1"),
        p.phy("-o", "altvoltage1", "powerdown"), p.loopback(), p.sel()))


def configure(p, args, tune_tx):
    """Everything but the path. The TX LO stays powered down; with tune_tx it moves to
    L1 + delta, which runs the TX quad calibration there, at maximum attenuation."""
    target = L1 + args.delta
    for direction, name, value, tol in (("-i", "sampling_frequency", args.fs, FS_TOL),
                                        ("-i", "rf_bandwidth", args.bw, BW_TOL),
                                        ("-o", "rf_bandwidth", args.bw, BW_TOL)):
        # Skip what would change nothing: each bandwidth write runs a TX quad calibration.
        if abs(num(p.phy(direction, "voltage0", name)) - value) > tol:
            p.phy(direction, "voltage0", name, str(value))
        got = num(p.phy(direction, "voltage0", name))
        if abs(got - value) > tol:
            raise RuntimeError("%s %s reads %g, wanted %d" % (direction, name, got, value))
    if abs(num(p.phy("-o", "voltage0", "sampling_frequency")) - args.fs) > FS_TOL:
        raise RuntimeError("TX sampling frequency differs from RX")
    p.phy("-o", "altvoltage0", "frequency", str(target))
    if abs(p.lo("altvoltage0") - target) > LO_TOL:
        raise RuntimeError("RX LO reads %d, wanted %d" % (p.lo("altvoltage0"), target))
    if tune_tx:
        p.phy("-o", "altvoltage1", "frequency", str(target))
        if abs(p.lo("altvoltage1") - p.lo("altvoltage0")) > LO_MATCH_TOL:
            raise RuntimeError("TX LO %d and RX LO %d differ" % (p.lo("altvoltage1"), p.lo("altvoltage0")))
    set_rx_gain(p, args.rx_gain, set_mode=True)
    if not p.lo_down():
        raise RuntimeError("TX LO came up during configuration")
    if p.read_tx_att("voltage0") != TX_MAX_ATT or p.read_tx_att("voltage1") != TX_MAX_ATT:
        raise RuntimeError("TX attenuation changed during configuration")
    time.sleep(0.2)
    if not p.adc_ok():
        raise RuntimeError("adc_status low after configuration")


def set_rx_gain(p, gain, set_mode=False):
    """Manual, same value on both channels (plan Section 4.2)."""
    for ch in ("voltage0", "voltage1"):
        if set_mode:
            p.phy("-i", ch, "gain_control_mode", "manual")
        p.phy("-i", ch, "hardwaregain", str(gain))
    for ch in ("voltage0", "voltage1"):
        got = num(p.phy("-i", ch, "hardwaregain"))
        mode = p.phy("-i", ch, "gain_control_mode")
        if got != gain or mode != "manual":
            raise RuntimeError("%s RX gain reads %g %s, wanted %d manual" % (ch, got, mode, gain))


def path_on(p):
    p.loopback("2")
    p.reg(0x4044, 1)            # dac sync, for a repeatable latency
    time.sleep(0.2)
    for c in (2, 3):
        p.set_sel(c, 3)
    got = p.sel()
    if got != PATH_SEL:
        raise RuntimeError("TX data_sel reads %s, wanted %s" % (got, PATH_SEL))


class Lines:
    """Line input from a file descriptor, usable with select and signals."""

    def __init__(self, fd):
        self.fd = fd
        self.buf = b""
        self.eof = False

    def get(self, timeout):
        """A line, or None on timeout. Sets eof at end of input."""
        if b"\n" not in self.buf and not self.eof:
            ready, _, _ = select.select([self.fd], [], [], timeout)
            if ready:
                try:
                    chunk = os.read(self.fd, 4096)
                except OSError:     # terminal hangup
                    chunk = b""
                if chunk:
                    self.buf += chunk
                else:
                    self.eof = True
        if b"\n" in self.buf:
            line, self.buf = self.buf.split(b"\n", 1)
            return line.decode("ascii", "replace").strip()
        return None


def confirm(args, lines):
    print("About to transmit, at TX attenuation %.2f dB (minimum allowed %.2f dB):\n"
          "  RX LO = TX LO = %d Hz (L1 + %d), fs %d, bandwidth %d, RX gain %d dB\n"
          "Required: TX1 -> DC block -> receiver, by cable, with external attenuation plus\n"
          "the minimum above at least 50 dB. RX1 and RX2 fed by cable through attenuators.\n"
          "TX2 and no port connected to an antenna.\n"
          "Type %s to confirm the setup is conducted and meets this: "
          % (args.tx_att, args.min_tx_att, L1 + args.delta, args.delta, args.fs, args.bw, args.rx_gain, CONFIRM),
          end="", flush=True)
    while not lines.eof:
        line = lines.get(None)
        if line is not None:
            return line == CONFIRM
    return False


HELP = """Commands:
  rx DB      RX gain on both channels (manual)
  tx DB      TX1 attenuation, up to 89.75 in 0.25 steps, not below --min-tx-att
  level      ADC level and clipping, from one block of samples
  status     all settings
  note TEXT  add a line to the log, e.g. the receiver C/N0
  quit       safe state and exit (also Ctrl-C)"""


def monitor(p, args):
    """Raise if the running path is no longer what was set up."""
    got = p.sel()
    if got != PATH_SEL:
        raise RuntimeError("TX data_sel changed to %s (a TX buffer or DDS write?)" % got)
    if p.lo_down():
        raise RuntimeError("TX LO is powered down")
    if abs(p.lo("altvoltage1") - (L1 + args.delta)) > LO_TOL:
        raise RuntimeError("TX LO moved to %d" % p.lo("altvoltage1"))
    if p.read_tx_att("voltage1") != TX_MAX_ATT:
        raise RuntimeError("TX2 attenuation changed")
    if not p.adc_ok():
        raise RuntimeError("adc_status went low")


def command(p, args, line, rx_range):
    """Run one command. Returns False to quit. Bad input only prints a message."""
    word, _, rest = line.partition(" ")
    rest = rest.strip()
    if word in ("q", "quit"):
        return False
    if word in ("h", "help", "?"):
        print(HELP, flush=True)
    elif word in ("s", "status"):
        report(p)
    elif word in ("l", "level"):
        LOG.say(p.levels())
    elif word == "note":
        LOG.say("NOTE " + rest)
    elif word == "rx":
        try:
            gain = int(rest)
        except ValueError:
            print("rx needs a whole number of dB", flush=True)
            return True
        if not rx_range[0] <= gain <= rx_range[2]:
            print("RX gain must be %g to %g" % (rx_range[0], rx_range[2]), flush=True)
            return True
        set_rx_gain(p, gain)
        LOG.say("RX gain %d dB on both channels" % gain)
    elif word == "tx":
        try:
            att = float(rest)
        except ValueError:
            print("tx needs a number of dB", flush=True)
            return True
        problem = check_tx_att(att, args.min_tx_att)
        if problem:
            print(problem, flush=True)
            return True
        p.tx_att("voltage0", att)
        if p.read_tx_att("voltage0") != att:
            raise RuntimeError("TX1 attenuation reads %g" % p.read_tx_att("voltage0"))
        LOG.say("TX1 attenuation %.2f dB" % att)
    elif word:
        print("unknown command; type help", flush=True)
    return True


def run_on(p, args, lines):
    configure(p, args, tune_tx=True)
    path_on(p)
    # The last two writes: nothing is emitted through the path until the LO comes up.
    p.tx_att("voltage0", args.tx_att)
    p.phy("-o", "altvoltage1", "powerdown", "0")
    monitor(p, args)
    LOG.say("ON: RX1 -> TX1 pass-through active")
    report(p)
    print(HELP, flush=True)
    rx_range = avail_range(p.phy("-i", "voltage0", "hardwaregain_available"))
    while True:
        line = lines.get(args.poll)
        if line is not None:
            if line:
                LOG.say("> " + line)
            if not command(p, args, line, rx_range):
                return
        elif lines.eof:
            LOG.say("end of input")
            return
        monitor(p, args)


def run_dry(p, args):
    configure(p, args, tune_tx=False)
    path_on(p)
    LOG.say("DRY RUN: path set with TX muted; TX LO stays parked")
    report(p)
    LOG.say(p.levels())


def main():
    ap = argparse.ArgumentParser(description="T1 RX1 -> TX1 pass-through. Conducted use only.")
    ap.add_argument("--uri", default="ip:192.168.2.1")
    ap.add_argument("--on", action="store_true", help="transmit, after a typed confirmation")
    ap.add_argument("--off", action="store_true", help="force the safe state")
    ap.add_argument("--check", action="store_true", help="read-only: checks, settings, levels")
    ap.add_argument("--tx-att", type=float, help="TX1 attenuation in dB; needed with --on")
    ap.add_argument("--min-tx-att", type=float,
                    help="needed with --on: refuse TX1 attenuation below this, in dB; "
                         "50 minus the external attenuation in the TX1 path")
    ap.add_argument("--rx-gain", type=int, default=60, help="manual, both channels (default 60)")
    ap.add_argument("--delta", type=int, default=3000000, help="LO = L1 + delta, Hz (default 3 MHz)")
    ap.add_argument("--fs", type=int, default=10000000, help="sample rate, Hz (default 10 MSPS)")
    ap.add_argument("--bw", type=int, default=9000000, help="RF bandwidth, Hz (default 9 MHz)")
    ap.add_argument("--log", help="log file (default with --on: results/t1_<date>-<time>.txt)")
    ap.add_argument("--poll", type=float, default=5.0, help="seconds between path checks")
    args = ap.parse_args()
    if args.on + args.off + args.check > 1:
        ap.error("--on, --off and --check exclude each other")
    if args.on and args.tx_att is None:
        ap.error("--on needs an explicit --tx-att")
    if args.on and args.min_tx_att is None:
        ap.error("--on needs an explicit --min-tx-att: 50 minus the external TX1 attenuation")
    if not args.on and args.tx_att is not None:
        ap.error("--tx-att is only used with --on")
    if not args.on and args.min_tx_att is not None:
        ap.error("--min-tx-att is only used with --on")
    if args.min_tx_att is None:
        args.min_tx_att = 0.0

    p = Pluto(args.uri)
    set_signals(on_signal)
    if args.log:
        LOG.open(args.log)

    if args.off:
        set_signals(signal.SIG_IGN)
        return finish(p, safe_state(p), 0)

    problems = check_settings(args.delta, args.fs, args.bw, args.tx_att, args.min_tx_att)
    try:
        problems = problems or precheck(p, args.rx_gain, args.delta)
    except Exception as e:
        problems = ["cannot check the Pluto: %s" % e]
    except Stop as s:
        return 128 + s.signum
    if problems:
        for problem in problems:
            LOG.say("REFUSED: " + problem)
        return 1

    if args.check:
        try:
            report(p)
            LOG.say(p.levels())
        except Stop as s:
            return 128 + s.signum
        except Exception as e:
            LOG.say("ERROR: %s" % e)
            return 1
        LOG.say("CHECK passed; nothing was written")
        return 0

    lines = Lines(sys.stdin.fileno()) if args.on else None
    if args.on:
        if not sys.stdin.isatty():
            LOG.say("REFUSED: --on needs an interactive terminal for the confirmation")
            return 1
        try:
            confirmed = confirm(args, lines)
        except Stop as s:
            return 128 + s.signum
        if not confirmed:
            LOG.say("REFUSED: setup not confirmed; nothing was changed")
            return 1
        if not args.log:
            root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            LOG.open(os.path.join(root, "results", "t1_%s.txt" % time.strftime("%Y%m%d-%H%M%S")))
        LOG.say("settings: delta %d fs %d bw %d rx_gain %d tx_att %.2f min_tx_att %.2f uri %s; "
                "confirmed conducted setup" % (args.delta, args.fs, args.bw, args.rx_gain,
                                               args.tx_att, args.min_tx_att, args.uri))

    rc = 0
    failed = []
    try:
        failed = safe_state(p)
        if failed:
            raise RuntimeError("could not reach the safe state before starting")
        if args.on:
            run_on(p, args, lines)
        else:
            run_dry(p, args)
    except Stop as s:
        LOG.say("stopped by signal %d" % s.signum)
        rc = 128 + s.signum
    except Exception as e:
        LOG.say("ERROR: %s" % e)
        rc = 1
    finally:
        set_signals(signal.SIG_IGN)
        failed = safe_state(p)
    return finish(p, failed, rc)


def finish(p, failed, rc):
    if failed:
        LOG.say("SAFE STATE NOT CONFIRMED: %s. TX may still be active: power-cycle the Pluto."
                % ", ".join(failed))
        return 3
    LOG.say("Safe state: TX attenuation %.2f dB, path off, TX LO powered down at %d Hz"
            % (TX_MAX_ATT, TX_PARK))
    return rc


if __name__ == "__main__":
    sys.exit(main())
