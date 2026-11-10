#!/usr/bin/env python3
"""Raw u-blox log with host times: runs `gpspipe -R --nobuffer`, writes its output to OUT.ubx
and an index OUT.ubx.idx with one line per chunk read: "<unix time> <byte offset>".

The index lets scripts/ubx_cn0.py cut windows by host time (--from, --to), which
the log alone cannot give: after a cold start the receiver time is wrong until the
first fix. A frame gets the time of the chunk that holds its first byte, so the
times are good to the receiver's 1 s message cycle.

Ends on SIGINT or SIGTERM (gpspipe is stopped, both files are closed), or when
gpspipe exits. Standard library only.

Usage: scripts/ubx_log.py results/t4_X.ubx [--cmd "gpspipe -R --nobuffer"]
"""
import argparse
import os
import shlex
import signal
import subprocess
import sys
import time


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out")
    ap.add_argument("--cmd", default="gpspipe -R --nobuffer", help="command that writes the raw stream to stdout")
    args = ap.parse_args()
    if os.path.exists(args.out) or os.path.exists(args.out + ".idx"):
        sys.exit("refused: %s or its .idx exists" % args.out)

    stop = []
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.append(1))
    p = subprocess.Popen(shlex.split(args.cmd), stdout=subprocess.PIPE, stdin=subprocess.DEVNULL)
    fd = p.stdout.fileno()
    offset = 0
    with open(args.out, "wb") as raw, open(args.out + ".idx", "w") as idx:
        idx.write("# unix_time byte_offset; started %.3f: %s\n" % (time.time(), args.cmd))
        idx.flush()
        while not stop:
            try:
                chunk = os.read(fd, 65536)
            except InterruptedError:
                continue
            if not chunk:
                break
            idx.write("%.3f %d\n" % (time.time(), offset))
            raw.write(chunk)
            raw.flush()
            idx.flush()
            offset += len(chunk)
        idx.write("# ended %.3f, %d bytes\n" % (time.time(), offset))
    if p.poll() is None:
        p.terminate()
        try:
            p.wait(5)
        except subprocess.TimeoutExpired:
            p.kill()
    return 0


if __name__ == "__main__":
    sys.exit(main())
