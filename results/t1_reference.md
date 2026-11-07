# T1 C/N0 reference: simulator to u-blox, no Pluto

Date: 2026-11-07. Status: **reference recorded.** Acceptable degradation through the pass-through, set by the user: 3-5 dB.

Raw log: `results/t1_ref_20261107_123927.ubx`, from `gpspipe -R` through gpsd.

## Settings
- Path: bladeRF x40 -> 40 dB attenuator -> DC block -> u-blox M8T. Attenuation and DC block as entered by the user. No Pluto and no splitter in the path.
- Simulator: `./bladegps -e brdc3300.18n`, TX 1575.42 MHz, 2.6 MSPS, TX bandwidth 2.5 MHz, TX gain 17 dB, static location 40.785092, -73.968285, 100.0 m, simulated start 2018/11/26 00:00:00.
- Receiver: NEO-M8T, FWVER=SPG 3.01, protocol 18.00. `ubxtool -p COLDBOOT` was issued at the start of the log.
- The bladeRF carrier at L1 is left in, by the user's decision. The pass-through test sees the same carrier.

## Result
137 epochs, 156 s of GPS time. 127 epochs have a valid 3D fix, ending with 11 satellites and hAcc 2.76 m.

| PRN | Mean C/N0 (dB-Hz) | Min | Max | Epochs used |
|---|---|---|---|---|
| G26 | 50.7 | 50 | 51 | 124 |
| G16 | 49.0 | 48 | 49 | 127 |
| G31 | 48.0 | 48 | 48 | 127 |
| G14 | 46.0 | 46 | 46 | 127 |
| G03 | 45.0 | 45 | 45 | 127 |
| G23 | 45.0 | 45 | 45 | 127 |
| G04 | 43.9 | 43 | 44 | 123 |
| G29 | 43.6 | 43 | 44 | 124 |
| G32 | 42.0 | 42 | 42 | 124 |
| G27 | 41.0 | 41 | 41 | 123 |
| G09 | 40.5 | 40 | 41 | 127 |

Mean of these 11 PRNs: 45.1 dB-Hz. G01 and G02 appear at about 30 dB-Hz for 1-2 epochs and are never used; treated as false acquisitions and left out.

MON-HW (134 messages): AGC 3432, noise 126-131, jamming indicator 125-141, antenna status OK, power on.

## Limits
- Cold start: inferred, not confirmed by a message. `msss` falls during the log (108 s near the start, 156 s at the end, over a 156 s span), with a 22 s gap in the epochs, 10 epochs without a fix, and TTFF about 31 s. The order of these events was not decoded.
- About 2 minutes after the fix. TTFF is a single sample and is not a reference.
- Height reaches at most 76.7 m against 100 m simulated, so at least 23 m low. Cause not determined. Use C/N0, not position, for the comparison until this is understood.
- The log ends at 12:42:03 JST; the receiver re-enumerated on USB around then.
