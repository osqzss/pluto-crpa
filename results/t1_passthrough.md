# T1 RX1 -> TX1 pass-through: C/N0 against the reference

Date: 2026-11-07. Unit: second Pluto, serial 1044734c96050011f2ff2100408f4f2ac3. Reference: `results/t1_reference.md`. Acceptable degradation, set by the user: 3-5 dB.

## Common settings
- Simulator: bladeRF x40, `./bladegps -e brdc3300.18n`, TX gain 17 dB -> 40 dB attenuator -> 2-way splitter -> RX1, RX2.
- Pluto: RX LO = TX LO = 1578419998 Hz, fs 10 MSPS, bandwidth 9 MHz, RX gain manual 60 dB on both channels, TX2 attenuation 89.75 dB.
- Receiver: u-blox M8T, read with PyGPSClient 1.8.0, binary log.

## Run A: 50 dB external, TX1 attenuation 0 dB
- Path: TX1 -> DC block -> 50 dB attenuator -> u-blox. External attenuator not stated in the run log; assumed from the setup at that time, to be confirmed by the user.
- Control log: `results/t1_20261107-141621.txt`. Receiver log: `results/pygpsdata-20261107141657.log`.
- 115 epochs at 1 s, 111 with a valid 3D fix, ending with 11 satellites and hAcc 2.06 m. TTFF 24.8 s, one sample. The log starts about 21 s after the receiver restart. Height 72.9 m at the end.

| PRN | Reference (dB-Hz) | Run A (dB-Hz) | Difference (dB) |
|---|---|---|---|
| G26 | 50.7 | 47.0 | -3.7 |
| G16 | 49.0 | 45.0 | -4.0 |
| G31 | 48.0 | 44.0 | -4.0 |
| G14 | 46.0 | 42.1 | -3.9 |
| G03 | 45.0 | 41.0 | -4.0 |
| G23 | 45.0 | 42.0 | -3.0 |
| G04 | 43.9 | 39.8 | -4.1 |
| G29 | 43.6 | 40.0 | -3.6 |
| G32 | 42.0 | 38.0 | -4.0 |
| G27 | 41.0 | 37.2 | -3.8 |
| G09 | 40.5 | 36.3 | -4.2 |

Mean difference -3.8 dB, range -3.0 to -4.2 dB. MON-HW: AGC 2184 (reference 3432), noise 101-102 (126-131), jamming indicator 137-149 (125-141).

TX-to-RX coupling, levels from `results/t1_20261107-135801.txt`:

| TX1 attenuation | ch0/1 (RX1) | ch2/3 (RX2) |
|---|---|---|
| 80 dB | -41.4 dBFS | -41.7 dBFS |
| 0 dB | -40.1 dBFS | -41.8 dBFS |

RX1 rises 1.3 dB at 0 dB attenuation and RX2 does not move. If this is feedback through the path, the loop gain is about -6 dB. One pair of readings; source of the coupling not located.
