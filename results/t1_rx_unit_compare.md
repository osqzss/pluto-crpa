# RX-only GPS check and Pluto unit comparison

Date: 2026-11-07. Status: **second Pluto passes the RX-only check on both channels; first Pluto has excess noise and bursts on RX2.** No Pluto transmission in any test (TX_LO powered down for all captures).

## Units
| Name | Serial | Firmware | Result |
|---|---|---|---|
| First unit | 1044734c960500110c000900418f4f7ca2 | v0.39-21-g27fb, `pluto.frm` only | RX2 faulty, cause not located |
| Second unit | 1044734c96050011f2ff2100408f4f2ac3 | v0.39-21-g27fb, `pluto.frm` only | Channels match |

Both report `Analog Devices PlutoSDR Rev.C (Z7010-AD9363A)`, `ad9361-phy,model: ad9363a`, four RX streams.

## Settings
- Pluto: RX LO 1578419998 Hz (L1 + 3 MHz), fs 10 MSPS, RF bandwidth 9 MHz, manual gain 60 dB on both channels unless stated, TX_LO powered down.
- Simulator: bladeRF x40, `./bladegps -e brdc3300.18n`, TX frequency 1575.42 MHz, 2.6 MSPS, TX bandwidth 2.5 MHz, TX gain 17 dB, static location mode, simulated start 2018/11/26 00:00:00.
- Path: bladeRF -> fixed attenuation -> 2-way splitter -> RX1, RX2. External attenuator: 40 dB (entered by the user), before the splitter loss.
- Terminated tests: 50 ohm loads on RX1 and RX2, splitter removed.

## First-unit findings
`scripts/gps_rx_check.py` (10 ms search) found GPS on ch0/1 at -Delta: G26 36.4, G31 14.5, G14 11.1, G23 7.6, G03 7.1 against about 4 on the mirrored side. On ch2/3 it showed about 8 for PRNs on both sides, including PRNs not simulated. That search uses only the first 10 ms, which contain the burst below, so it was not a valid negative.

Terminated, 60 dB gain, 1 ms blocks, steady level as the median:

| Capture | ch0/1 rms (LSB) | ch2/3 rms (LSB) | Excess (dB) | ch2/3 first ms rms | ch2/3 ms above 2x median |
|---|---|---|---|---|---|
| 0.1 s, 6 runs | 15.9-16.0 | 75.3-75.8 | 13.5 | 194-223 | 1-2 of 100, one run 15 |
| 1 s, run 1 | 15.9 | 75.7 | 13.5 | 222 | 180 of 1000 |
| 1 s, run 2 | 15.3 | 66.7 | 12.8 | 258 | 166 of 1000 |

Gain sweep, terminated (an earlier run in the same session, before the reboot):

| Gain (dB) | ch0/1 rms | ch2/3 rms | Excess (dB) | ch2/3 first ms rms |
|---|---|---|---|---|
| 71 | 40.3 | 196.0 | 13.7 | 716 |
| 60 | 15.3 | 60.9 | 12.0 | 210 |
| 50 | 7.4 | 20.3 | 8.8 | 70 |
| 40 | 6.6 | 7.6 | 1.2 | 21 |
| 30 | 5.8 | 6.4 | 0.8 | 8 |
| 20 | 5.7 | 5.8 | 0.1 | 6 |
| 10 | 5.9 | 5.8 | -0.1 | 6 |
| 0 | 5.9 | 6.1 | 0.2 | 6 |

- The excess and the bursts scale with gain, so they enter before the gain stages. They are not ADC or digital noise.
- The ch2/3 level changes without any setup change: 61-76 LSB terminated, 61-101 LSB on the splitter.
- voltage1 RSSI when idle moves between about 91 and 112 dB, and is steady near 91 dB during a capture. voltage0 stays near 113 dB. The excess is therefore also present when idle, and is stronger during a capture.
- ch0/1 shows no bursts when terminated. The first ms on ch0/1 rises to about 22 LSB through the splitter. How it gets there was not determined.
- Where the fault sits (chip, board or RX2 connection) was not determined. The user found the RX2 connector fine.

## Second-unit findings: terminated
| Capture | ch0/1 rms (LSB) | ch2/3 rms (LSB) | Excess (dB) | ch2/3 first ms rms | ch2/3 ms above 2x median |
|---|---|---|---|---|---|
| 0.1 s, 6 runs | 15.1-15.2 | 14.6-14.7 | -0.2 to -0.3 | 14.8-15.0 | 0 of 100 |
| 1 s, 2 runs | 15.2 | 14.7 | -0.3 | 14.7-14.8 | 0 of 1000 |

| Gain (dB) | ch0/1 rms | ch2/3 rms | Excess (dB) | ch2/3 first ms rms |
|---|---|---|---|---|
| 71 | 40.2 | 39.4 | -0.2 | 39.9 |
| 60 | 15.3 | 14.7 | -0.3 | 14.8 |
| 50 | 8.6 | 6.8 | -2.1 | 6.7 |
| 40 | 7.7 | 5.3 | -3.2 | 5.3 |
| 30 | 7.6 | 5.3 | -3.2 | 5.3 |
| 20 | 7.3 | 5.1 | -3.0 | 5.2 |
| 10 | 7.8 | 5.1 | -3.7 | 5.1 |
| 0 | 7.3 | 5.3 | -2.8 | 5.3 |

Idle RSSI: 113.50 / 113.50 dB on all 15 readings. The ch0/1 floor is about 3 dB above ch2/3 at low gain (about 7.5 against 5.3 LSB); it is well below the 15 LSB level at 60 dB. Not investigated.

## Second-unit findings: GPS on both channels
One contiguous 1 s capture through the splitter, mixed by +3 MHz, decimated to 2.5 MSPS, 4 ms coherent blocks, non-coherent sum of 250 blocks, Doppler 100 Hz steps, code drift compensated. No blocks discarded (0 of 1000 ms above 2x median on either channel). Ratio is the peak over the mean away from the peak. Highest PRN not simulated: 2.63 (ch0/1), 2.57 (ch2/3).

| PRN | Ratio ch0/1 | Ratio ch2/3 | SNR, ch2/3 - ch0/1 (dB) | Signal, ch2/3 - ch0/1 (dB) | Doppler (Hz) | Doppler - ephemeris (Hz) | Delay, ch2/3 - ch0/1 (ns) |
|---|---|---|---|---|---|---|---|
| G31 | 119.82 | 109.12 | -0.41 | -0.44 | -6900 | -5165 | +1.3 |
| G26 | 96.65 | 90.75 | -0.28 | -0.47 | -5200 | -5196 | -0.4 |
| G03 | 68.30 | 62.16 | -0.42 | -0.39 | -6400 | -5163 | -2.3 |
| G14 | 66.60 | 60.96 | -0.39 | -0.40 | -7900 | -5213 | -0.2 |
| G16 | 39.47 | 35.95 | -0.42 | -0.42 | -2900 | -5004 | +2.8 |
| G04 | 33.72 | 30.15 | -0.50 | -0.45 | -1400 | -5199 | -2.0 |
| G29 | 27.53 | 26.16 | -0.23 | -0.38 | -6300 | -5165 | +6.7 |
| G32 | 27.50 | 25.18 | -0.40 | -0.46 | -8700 | -5175 | -3.8 |
| G27 | 25.23 | 22.62 | -0.49 | -0.46 | -1400 | -5152 | -3.9 |
| G09 | 21.91 | 19.63 | -0.50 | -0.48 | -1600 | -5161 | +5.5 |
| G23 | 16.79 | 16.31 | -0.13 | -0.39 | -2000 | -5052 | -2.7 |

- All 11 simulated PRNs are found on both channels at -Delta, with the same Doppler on both. This confirms the I/Q order of Plan Section 4.1 for this unit. The mirrored side was not searched in this run.
- Doppler against ephemeris shows one common offset of about -5.2 kHz (-3.3 ppm), expected to be the bladeRF to Pluto clock difference. It was about -2.8 kHz on the first unit.
- The channels agree within 0.5 dB in SNR. ch2/3 is about 0.4 dB lower in signal. The delay difference averages about 0.1 ns over the 11 PRNs, spread within +/-7 ns. Inter-channel phase was not measured.
- ch0/1 and ch2/3 cannot be mapped to connectors from this run, because both inputs are on the splitter. See the next section.

## Second-unit findings: connector mapping
One splitter leg terminated in 50 ohm by the user, the other leg connected, `bladegps` running. Same settings and corrected search as above (one contiguous 1 s capture per case, Doppler -11 to +2 kHz).

| Terminated | Stream | Steady rms (LSB) | -3.000 MHz tone (dB over median) | Simulated PRNs found | Highest PRN not simulated |
|---|---|---|---|---|---|
| RX2 | ch0/1 | 17.6 | 21.6 | 11 of 11, ratios 18.6-125.6 | 2.77 |
| RX2 | ch2/3 | 14.8 | not in top bins | 0 of 11, all 1.29-1.36 | 1.39 |
| RX1 | ch0/1 | 15.2 | not in top bins | 0 of 11, all 1.29-1.38 | 1.38 |
| RX1 | ch2/3 | 16.7 | 20.8 | 11 of 11, ratios 16.7-121.0 | 2.74 |

Result: `i0/q0` (ch0/1) follows RX1 and `i1/q1` (ch2/3) follows RX2, confirmed in both directions. The common Doppler offset in these runs is about -4.5 kHz, against about -5.2 kHz earlier in the session.

## Analysis error corrected
The first version of the long search applied the code-drift compensation with the wrong sign, doubling the drift. On the second unit it gave ratios up to 18 instead of 120, and false delay differences of up to about 5.6 us on high-Doppler PRNs. The table above is from the corrected search on the same saved capture.

The first-unit long search used the wrong sign and its capture was not saved, so these results are not reliable and are not used as findings: its code-phase offsets of 3-7 samples (likely this error), its missing G32, and its ratios. The search scripts were temporary and are not in the repo.

## Other findings
- bladeRF: a carrier at 1575.42 MHz stays in the splitter path after `bladegps` exits, about 18 dB over the floor on first-unit ch0/1. It disappears when the bladeRF is unplugged from USB. Whether TX was left enabled or this is idle leakage was not determined. The same tone is seen while `bladegps` runs.
- Firmware environment: on the first unit `fw_printenv` shows `attr_name=compatible`, `compatible=ad9361`, `mode=2r2t`, and `attr_val` not defined. `adi_loadvals_pluto` (`fw/u-boot/include/configs/zynq_pluto_sdr.h:96`) needs `attr_name` and `attr_val`, and does not read `compatible`, so the setting has no effect: the device still reports `ad9363a` with an LO range of 325-3800 MHz. 2R2T comes from `mode`. The boot image on the devices was not replaced, so the running u-boot may differ from that source.
- After a reboot the first unit came up with LO 2400 MHz, 30.72 MSPS, gain 71 dB and TX_LO powered up at 2450 MHz. On the second unit only TX_LO was read before it was changed: also powered up at 2450 MHz.
