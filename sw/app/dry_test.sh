# crpa_ctl dry-run test, run on the Pluto: ssh pluto 'sh -s' < sw/app/dry_test.sh
# No transmission: every run is without --on, so the TX LO stays powered down
# and parked at 2400 MHz, TX attenuation at maximum. Ends with "crpa_ctl off".
# Expects /mnt/jffs2/crpa_ctl (scp sw/app/crpa_ctl pluto:/mnt/jffs2/).
B=/mnt/jffs2/crpa_ctl

csv_stats() {
  # rows, discarded rows, max missed, seq gaps, non-zero status bits other than DONE,
  # mean p1/p2/py, last weights
  awk -F, 'NR > 1 {
      n++; if ($22 == "discard") d++;
      if ($11 > mm) mm = $11;
      if (n > 1 && $2 != (ps + 1) % 65536) gaps++; ps = $2;
      if (and($12 + 0, 14)) bad++;
      if ($22 != "discard") { s1 += $18; s2 += $19; sy += $20; k++ }
      w = $13 " " $14 " " $15 " " $16
    } END {
      printf "rows %d discard %d missed_max %d seq_gaps %d flag_rows %d | mean p1 %.1f p2 %.1f py %.1f dBFS | last w %s\n",
        n, d, mm, gaps, bad, s1 / k, s2 / k, sy / k, w
    }' "$1"
}

echo "== status (read-only)"
$B status; echo "rc=$?"

echo "== 1: dry run, fixed unity weights, irq, 5 s"
$B run --duration 5 --out /tmp/t6b_fixed; echo "rc=$?"
csv_stats /tmp/t6b_fixed.csv

echo "== 2: dry run, fixed w = [0, 1] (x2 only), 3 s"
$B run --duration 3 --w 0,0,1,0 --out /tmp/t6b_w01; echo "rc=$?"
csv_stats /tmp/t6b_w01.csv

echo "== 3: dry run, power inversion, load 0, 5 s"
$B run --duration 5 --mode pi --out /tmp/t6b_pi; echo "rc=$?"
csv_stats /tmp/t6b_pi.csv
echo "first rows:"; head -4 /tmp/t6b_pi.csv

echo "== 4: dry run, polling STATUS instead of the irq, 3 s"
$B run --duration 3 --poll-status --out /tmp/t6b_poll; echo "rc=$?"
csv_stats /tmp/t6b_poll.csv

echo "== 5: refusals (must not change anything)"
$B run --on --tx-att 50 --min-tx-att 50 --duration 1 </dev/null; echo "rc=$? (expect 1: no terminal)"
$B run --fs 1000000 --duration 1; echo "rc=$? (expect 1: fs too low)"
$B run --delta 1000000 --duration 1; echo "rc=$? (expect 1: delta too small)"

echo "== 6: SIGTERM during a run"
$B run --out /tmp/t6b_term > /tmp/t6b_term.out 2>&1 &
P=$!; sleep 2; kill -TERM $P; wait $P; echo "rc=$? (expect 143)"
tail -2 /tmp/t6b_term.out

echo "== off"
$B off; echo "rc=$?"
echo "== interrupts"
grep crpa /proc/interrupts
