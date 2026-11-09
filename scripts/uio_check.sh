# crpa_core UIO and device tree check, run on the Pluto (Task 6a):
#   ssh pluto 'sh -s' < scripts/uio_check.sh
# Read-only: prints VERSIONS, cmdline, UIO maps and IRQ, reads VERSION (0x00)
# with devmem, and lists the ADC/DAC sampling_frequency attributes.
echo "== /opt/VERSIONS"; cat /opt/VERSIONS
echo "== /proc/cmdline"; cat /proc/cmdline
echo "== /sys/class/uio"
for u in /sys/class/uio/uio*; do
  [ -e "$u" ] || { echo "no uio devices"; continue; }
  echo "$u name=$(cat $u/name) version=$(cat $u/version)"
  for m in $u/maps/map*; do
    echo "  $(basename $m) name=$(cat $m/name 2>/dev/null) addr=$(cat $m/addr) size=$(cat $m/size)"
  done
done
ls -l /dev/uio* 2>&1
echo "== device tree node"
d=$(find -L /proc/device-tree -maxdepth 3 -name 'crpa-core@7c450000' | head -1); echo "node: $d"
[ -n "$d" ] && echo "compatible: $(cat $d/compatible)"
echo "== driver binding"
ls -l /sys/bus/platform/devices/7c450000.crpa-core/driver 2>&1
echo "== /proc/interrupts (crpa)"; grep -i crpa /proc/interrupts || echo "no crpa irq line"
echo "== VERSION @ 0x7C450000 (expect 0x00010000)"; devmem 0x7C450000 32
echo "== sampling_frequency attributes"
for dev in /sys/bus/iio/devices/iio:device*; do
  n=$(cat $dev/name)
  case "$n" in
    cf-ad9361-lpc|cf-ad9361-dds-core-lpc)
      echo "-- $n"
      ls $dev | grep -i "sampling_frequency\|interpolation\|decimation"
      for f in $dev/*sampling_frequency*; do
        printf '%s: ' "$(basename $f)"; cat $f 2>&1
      done;;
  esac
done
echo "== iio devices"; for dev in /sys/bus/iio/devices/iio:device*; do echo "$(basename $dev) $(cat $dev/name)"; done
echo "== dmesg uio/crpa"; dmesg | grep -i "uio\|crpa" | tail -10
