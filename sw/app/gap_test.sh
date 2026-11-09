# Block-gap diagnosis, run on the Pluto: ssh pluto 'sh -s' < sw/app/gap_test.sh
# Dry runs only (no --on): TX LO stays powered down and parked, attenuation maximum.
B=/mnt/jffs2/crpa_ctl

gaps() {
  awk -F, 'NR > 2 { d = $2 - ps; if (d < 0) d += 65536; dt = $3 - pt;
      if (dt > mx) mx = dt;
      if (d != 1 && $1 > 1) { g++; lost += d - 1; printf "  gap at t %.3f: %d blocks\n", $3, d - 1 } }
    NR > 1 { ps = $2; pt = $3 }
    END { printf "  %s: gaps %d, blocks lost %d (after startup), max dt %.2f ms\n", FILENAME, g, lost, mx * 1000 }' "$1"
}

echo "== processes"; ps
echo "== RT throttling"; cat /proc/sys/kernel/sched_rt_runtime_us /proc/sys/kernel/sched_rt_period_us
echo "== interrupts over 1 s (changed lines)"
cat /proc/interrupts > /tmp/irq0; sleep 1; cat /proc/interrupts > /tmp/irq1
awk 'NR == FNR { a[$1] = $2; next } ($1 in a) && $2 != a[$1] { printf "  %s +%d %s %s %s %s\n", $1, $2 - a[$1], $3, $4, $5, $6 }' /tmp/irq0 /tmp/irq1
command -v chrt >/dev/null && echo "chrt available" || echo "no chrt"

echo "== A: normal priority, 5 s"
$B run --duration 5 --out /tmp/t6b_gapA > /tmp/t6b_gapA.out 2>&1; echo "rc=$?"
tail -1 /tmp/t6b_gapA.out
gaps /tmp/t6b_gapA.csv

echo "== B: --rt 40, 5 s"
$B run --duration 5 --rt 40 --out /tmp/t6b_gapB > /tmp/t6b_gapB.out 2>&1; echo "rc=$?"
grep -E "scheduling|WARNING|ERROR" /tmp/t6b_gapB.out; tail -1 /tmp/t6b_gapB.out
gaps /tmp/t6b_gapB.csv

echo "== C: --rt 40, PI mode, 10 s"
$B run --duration 10 --rt 40 --mode pi --out /tmp/t6b_gapC > /tmp/t6b_gapC.out 2>&1; echo "rc=$?"
tail -1 /tmp/t6b_gapC.out
gaps /tmp/t6b_gapC.csv

$B off
