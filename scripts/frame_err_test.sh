# FRAME_ERR (crpa_core STATUS bit 2) after sample rate changes. Runs on the Pluto:
#   ssh pluto 'sh -s' < scripts/frame_err_test.sh   (about 30 s; leaves TX_LO powered down)
# Only touches TX_LO powerdown, the sample rate and crpa_core STATUS (W1C clear).
P=/sys/bus/iio/devices/iio:device0
ST=0x7C450010
rd() { printf "%-34s fs=%s STATUS=%s\n" "$1" "$(cat $P/in_voltage_sampling_frequency)" "$(devmem $ST 32)"; }
clr() { devmem $ST 32 0x4; sleep 1; }

echo 1 > $P/out_altvoltage1_TX_LO_powerdown
rd "start"
clr; rd "cleared"
for i in 1 2 3 4 5; do sleep 2; rd "steady $i (10 s total)"; done

echo 10000000 > $P/in_voltage_sampling_frequency; sleep 1
rd "after change to 10 MSPS, no clear"
clr; rd "cleared at 10 MSPS"
for i in 1 2 3 4 5; do sleep 2; rd "steady $i (10 s total)"; done

echo 30720000 > $P/in_voltage_sampling_frequency; sleep 1
rd "after change to 30.72 MSPS, no clear"
clr; rd "cleared at 30.72 MSPS"
sleep 2; rd "steady"
echo "TX_LO powerdown: $(cat $P/out_altvoltage1_TX_LO_powerdown) (left powered down)"
