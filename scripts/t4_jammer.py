#!/usr/bin/python3
"""T4: CW jammer on the USRP B205mini, conducted use only (docs/t4_plan.md).

Sends a constant baseband, so the CW is on the B205mini LO at --freq. The level is
set by the analog TX gain; the digital amplitude stays fixed.

Without --on this is a dry run: the device is opened, its TX gain range, antennas
and frequency range are read and checked against the request, and nothing is tuned
or streamed. With --on it transmits and needs:
  --ext-att DB    attenuators between the B205mini and the splitter, as cabled
                  (the operator's statement; refused below 50)
  --max-gain DB   highest TX gain this run may use; any higher step is refused

States: a gain in dB (streaming) or "off" (end of burst sent, no streaming, gain
at the minimum of the device).
  --gain G|off          state at the start (default off)
  --schedule "T:S,..."  states S (gain, off or quit) at T seconds after t0
  --start-now           t0 is the start of the script; otherwise the stdin
                        command "t0" sets it
Stdin commands, one per line: t0, gain DB, off, note TEXT, status, quit.
Stdin may be a FIFO. End of input is a quit.

On quit, end of input, a "quit" step, any error and SIGINT/TERM/HUP the script
ends the burst, sets the gain to the minimum, closes the device and logs
"JAMMER OFF". After SIGKILL or a crash the state is unknown: unplug the B205mini.

Uses the UHD Python API (python3-uhd), so it runs with the system Python.
Usage: scripts/t4_jammer.py --on --ext-att 60 --max-gain 60 --gain off \
           --schedule "180:30,240:40,300:off" --log results/t4_X_jammer.txt < fifo
"""
import argparse
import datetime
import os
import select
import signal
import sys
import threading
import time

L1 = 1575420000
MIN_EXT_ATT = 50.0
BUF = 10000          # samples per send call


def parse_state(text):
    """'off', 'quit' or a gain in dB. Returns the string or a float."""
    t = text.strip().lower()
    if t in ("off", "quit"):
        return t
    try:
        g = float(t)
    except ValueError:
        raise ValueError("'%s' is not a gain in dB, 'off' or 'quit'" % text)
    if g != g or g in (float("inf"), float("-inf")):
        raise ValueError("'%s' is not a finite gain" % text)
    return g


def parse_schedule(text):
    """'T:S,T:S,...' -> list of (seconds, state), times strictly increasing."""
    steps = []
    if not text:
        return steps
    for item in text.split(","):
        if item.count(":") != 1:
            raise ValueError("schedule item '%s' is not T:STATE" % item)
        t, s = item.split(":")
        try:
            sec = float(t)
        except ValueError:
            raise ValueError("schedule time '%s' is not a number" % t)
        if sec < 0 or (steps and sec <= steps[-1][0]):
            raise ValueError("schedule times must be >= 0 and increasing (at '%s')" % item)
        steps.append((sec, parse_state(s)))
    return steps


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--args", default="serial=3297659", help="UHD device address")
    ap.add_argument("--freq", type=float, default=L1 + 200e3, help="CW frequency in Hz")
    ap.add_argument("--rate", type=float, default=1e6)
    ap.add_argument("--ampl", type=float, default=0.5, help="digital amplitude, 0 < a <= 0.7")
    ap.add_argument("--ant", default="TX/RX")
    ap.add_argument("--gain", default="off", help="state at the start: gain in dB or off")
    ap.add_argument("--schedule", default="")
    ap.add_argument("--start-now", action="store_true")
    ap.add_argument("--on", action="store_true", help="transmit")
    ap.add_argument("--ext-att", type=float)
    ap.add_argument("--max-gain", type=float)
    ap.add_argument("--log", default=None)
    a = ap.parse_args()

    def refuse(msg):
        print("REFUSED: " + msg, file=sys.stderr)
        sys.exit(2)

    try:
        first = parse_state(a.gain)
        steps = parse_schedule(a.schedule)
    except ValueError as e:
        refuse(str(e))
    if first == "quit":
        refuse("--gain quit makes no sense")
    if not 0 < a.ampl <= 0.7:
        refuse("--ampl %g is outside 0 to 0.7" % a.ampl)
    if abs(a.freq - L1) > 2e6:
        refuse("--freq %.0f Hz is more than 2 MHz from L1" % a.freq)
    if a.on:
        if a.ext_att is None or a.max_gain is None:
            refuse("--on needs --ext-att and --max-gain")
        if a.ext_att < MIN_EXT_ATT:
            refuse("--ext-att %g dB is below %g dB" % (a.ext_att, MIN_EXT_ATT))
    elif a.ext_att is not None or a.max_gain is not None:
        refuse("--ext-att and --max-gain are only used with --on")
    gains = [s for s in [first] + [s for _, s in steps] if isinstance(s, float)]
    if a.on:
        for g in gains:
            if g > a.max_gain:
                refuse("gain %g dB is above --max-gain %g dB" % (g, a.max_gain))

    log_fp = open(a.log, "w") if a.log else None

    def out(msg):
        now = datetime.datetime.now(datetime.timezone.utc)
        line = "%s %.3f %s" % (now.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z", now.timestamp(), msg)
        print(line, flush=True)
        if log_fp:
            log_fp.write(line + "\n")
            log_fp.flush()

    stop = {"why": None}

    def on_signal(signum, _frame):
        if stop["why"] is None:
            stop["why"] = "signal %d" % signum

    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, on_signal)

    import numpy as np
    import uhd

    out("t4_jammer.py: " + " ".join(sys.argv[1:]))
    out("mode %s, device '%s'" % ("ON (transmit)" if a.on else "dry run", a.args))
    usrp = None
    rc = 0
    streaming = {"on": False}
    sender = {"thread": None, "run": False, "error": None, "sent": 0}
    gmin = None
    tx = None
    try:
        usrp = uhd.usrp.MultiUSRP(a.args)
        grange = usrp.get_tx_gain_range(0)
        gmin, gmax, gstep = grange.start(), grange.stop(), grange.step()
        ants = list(usrp.get_tx_antennas(0))
        frange = usrp.get_tx_freq_range(0)
        out("device: %s" % usrp.get_pp_string().strip().replace("\n", " | "))
        out("TX gain range %g to %g dB, step %g; antennas %s; freq %.0f to %.0f Hz" % (
            gmin, gmax, gstep, ",".join(ants), frange.start(), frange.stop()))
        if a.ant not in ants:
            raise RuntimeError("antenna '%s' is not one of %s" % (a.ant, ants))
        if not frange.start() <= a.freq <= frange.stop():
            raise RuntimeError("frequency %.0f Hz is outside the TX range" % a.freq)
        for g in gains:
            if not gmin <= g <= gmax:
                raise RuntimeError("gain %g dB is outside the device range" % g)
        usrp.set_tx_gain(gmin, 0)
        out("schedule: %s; start state %s; t0 %s" % (
            ", ".join("%g:%s" % (t, s) for t, s in steps) or "none", first,
            "at start" if a.start_now else "on the t0 command"))
        if not a.on:
            out("dry run: nothing tuned, nothing streamed")
            return 0

        usrp.set_tx_antenna(a.ant, 0)
        usrp.set_tx_rate(a.rate, 0)
        res = usrp.set_tx_freq(uhd.types.TuneRequest(a.freq), 0)
        rate = usrp.get_tx_rate(0)
        freq = usrp.get_tx_freq(0)
        out("tuned: target %.1f Hz, actual RF %.1f Hz, DSP %.3f Hz, reads %.1f Hz; rate %.1f; antenna %s" % (
            a.freq, res.actual_rf_freq, res.actual_dsp_freq, freq, rate, usrp.get_tx_antenna(0)))
        if abs(freq - a.freq) > 100 or abs(rate - a.rate) > 1:
            raise RuntimeError("frequency or rate not as requested")
        out("ext-att %g dB (as stated), max-gain %g dB, ampl %g" % (a.ext_att, a.max_gain, a.ampl))
        tx = usrp.get_tx_stream(uhd.usrp.StreamArgs("fc32", "sc16"))
        buf = np.full((1, BUF), a.ampl, dtype=np.complex64)

        def send_loop():
            md = uhd.types.TXMetadata()
            md.start_of_burst = True
            try:
                while sender["run"]:
                    n = tx.send(buf, md, 1.0)
                    md.start_of_burst = False
                    if n != BUF:
                        raise RuntimeError("send returned %d of %d samples" % (n, BUF))
                    sender["sent"] += n
            except Exception as e:  # reported by the main loop
                sender["error"] = "%s: %s" % (type(e).__name__, e)

        def burst_end():
            """Stop the sender and end the burst. Safe to call in any state."""
            if sender["thread"] is not None:
                sender["run"] = False
                sender["thread"].join(5.0)
                alive = sender["thread"].is_alive()
                sender["thread"] = None
                if alive:
                    raise RuntimeError("sender thread did not stop")
            if streaming["on"]:
                md = uhd.types.TXMetadata()
                md.end_of_burst = True
                tx.send(np.zeros((1, 1), dtype=np.complex64), md, 1.0)
                streaming["on"] = False

        def apply(state, why):
            if state == "off":
                burst_end()
                usrp.set_tx_gain(gmin, 0)
                out("STATE off (%s); gain reads %g dB" % (why, usrp.get_tx_gain(0)))
                return
            if state > a.max_gain or not gmin <= state <= gmax:
                out("REFUSED gain %g dB (max-gain %g, device %g to %g)" % (state, a.max_gain, gmin, gmax))
                return
            usrp.set_tx_gain(state, 0)
            got = usrp.get_tx_gain(0)
            if abs(got - state) > gstep / 2 + 1e-6:
                raise RuntimeError("gain reads %g dB, wanted %g" % (got, state))
            if not streaming["on"]:
                streaming["on"] = True
                sender["run"] = True
                sender["thread"] = threading.Thread(target=send_loop, daemon=True)
                sender["thread"].start()
            out("STATE gain %g dB (%s)" % (got, why))

        apply(first, "start")
        t0 = None
        if a.start_now:
            t0 = time.time()
            out("T0 (start)")
        pending = list(steps)
        line_buf = b""
        stdin_fd = sys.stdin.fileno()
        while stop["why"] is None:
            if sender["error"]:
                raise RuntimeError("sender: " + sender["error"])
            while t0 is not None and pending and time.time() - t0 >= pending[0][0]:
                t, s = pending.pop(0)
                if s == "quit":
                    stop["why"] = "schedule quit at %g s" % t
                    break
                apply(s, "schedule %g s" % t)
            if stop["why"]:
                break
            try:
                ready, _, _ = select.select([stdin_fd], [], [], 0.02)
            except InterruptedError:
                continue
            if not ready or stop["why"] is not None:
                continue
            chunk = os.read(stdin_fd, 4096)
            if not chunk:
                stop["why"] = stop["why"] or "end of input"
                break
            line_buf += chunk
            while b"\n" in line_buf and stop["why"] is None:
                raw, line_buf = line_buf.split(b"\n", 1)
                words = raw.decode("ascii", "replace").strip().split(None, 1)
                if not words:
                    continue
                cmd, rest = words[0].lower(), (words[1] if len(words) > 1 else "")
                if cmd in ("quit", "q"):
                    stop["why"] = "quit command"
                elif cmd == "t0":
                    if t0 is None:
                        t0 = time.time()
                        out("T0 (command)")
                    else:
                        out("t0 is already set; ignored")
                elif cmd == "off":
                    apply("off", "command")
                elif cmd == "gain":
                    try:
                        g = parse_state(rest)
                        if not isinstance(g, float):
                            raise ValueError("gain needs a number")
                    except ValueError as e:
                        out("REFUSED: %s" % e)
                    else:
                        apply(g, "command")
                elif cmd == "note":
                    out("NOTE " + rest)
                elif cmd == "status":
                    out("STATUS streaming %s, gain reads %g dB, samples sent %d, t %s" % (
                        streaming["on"], usrp.get_tx_gain(0), sender["sent"],
                        "%.1f s" % (time.time() - t0) if t0 is not None else "before t0"))
                else:
                    out("unknown command '%s'" % cmd)
        out("stopping: %s" % stop["why"])
    except Exception as e:
        out("ERROR: %s: %s" % (type(e).__name__, e))
        rc = 1
    finally:
        failed = []
        if tx is not None:
            try:
                burst_end()
            except Exception as e:
                failed.append("end of burst: %s" % e)
        if gmin is not None:
            try:
                usrp.set_tx_gain(gmin, 0)
                got = usrp.get_tx_gain(0)
                if abs(got - gmin) > 1e-6:
                    failed.append("gain reads %g dB" % got)
            except Exception as e:
                failed.append("gain: %s" % e)
        tx = None
        usrp = None
        if failed:
            out("JAMMER OFF NOT CONFIRMED: " + "; ".join(failed) + ". Unplug the B205mini.")
            rc = rc or 1
        elif a.on:
            out("JAMMER OFF: burst ended, gain at minimum, device closed")
        elif gmin is not None:
            out("device closed")
        if log_fp:
            log_fp.close()
    return rc


if __name__ == "__main__":
    sys.exit(main())
