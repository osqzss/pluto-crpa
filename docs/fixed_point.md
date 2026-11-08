# crpa_core Fixed-Point Design

Golden reference: `model/crpa_model.py`. RTL must match `combine()` and `covariance()` bit exactly (plan Section 12).

## Combiner

`y = conj(w1) * x1 + conj(w2) * x2`

```
yi_sum = w1i*x1i + w1q*x1q + w2i*x2i + w2q*x2q
yq_sum = w1i*x1q - w1q*x1i + w2i*x2q - w2q*x2i
```

| Stage | Format | Notes |
|---|---|---|
| Input `x` | S12, -2048..2047 | Low 12 bits of `adc_data_*`, sign-extended (`docs/interface.md`) |
| Weight `w` | Q1.15, S16 for each of re, im | **Unity is 0x7FFF**, see below |
| Product | 28 bits | S16 x S12. No truncation |
| Sum | 30 bits | Four products, magnitude at most 2^28 (reached at -32768 x -2048 on all four) |
| Shift | `OUT_SHIFT` s = 0..15 | Gain 2^s: right shift by `sh` = 15 - s |
| Rounding | Round half up, once | `(sum + 2^(sh-1)) >>> sh`; nothing is added when `sh` = 0 |
| Saturation | S12, -2048..2047 | Separately for I and Q. A sample with either saturated counts once in `sat` |
| Output | `y << 4` | Upper 12 bits of `dac_data_*`, low nibble zero |

**Unity weight.** Q1.15 has no +1.0, and 0x7FFF is exact in practice: for S12 input, `x * 32767 / 32768` differs from `x` by at most 1/16 LSB, so rounding returns `x` for all 4096 inputs (`test_unity_is_exact_for_every_input`). So `w = [0x7FFF, 0]` gives `y = x` bit exactly, with no extra format or scale bit. T2 can compare output and input directly.

**Round half up** has a mean bias of 2^-(sh+1) LSB at the rounding point. That is negligible at `sh` = 15, and it needs only one constant adder. Convergent rounding was not worth the extra logic.

**`OUT_SHIFT`** gives 6 dB steps. The finer output level comes from TX attenuation (0.25 dB steps). Whether a PL gain multiplier is needed is still open (plan Section 10.2).

## Covariance

| Value | Definition | Per sample | Accumulator |
|---|---|---|---|
| R11 | sum(x1i^2 + x1q^2) | 0..2^23 | 48-bit signed |
| R22 | sum(x2i^2 + x2q^2) | 0..2^23 | 48-bit signed |
| R21_re | sum(x2i*x1i + x2q*x1q) | magnitude at most 2^23 | 48-bit signed |
| R21_im | sum(x2q*x1i - x2i*x1q) | magnitude at most 2^23 | 48-bit signed |

- Taken from the input `x`, before the weights, so the result does not depend on the weights in use.
- No rounding. Results sign-extend to the 64-bit register pairs.
- **`INT_LEN` is 24 bits, 1..2^24 - 1.** At exactly 2^24 samples of full scale, R11 would reach +2^47 and overflow 48 bits.
- Vectors use consecutive blocks of `INT_LEN` samples from sample 0. The RTL runs the same way while CTRL.COV_EN is set (`docs/regmap.md`).
- Per block the RTL also reports SAT_CNT, the number of samples with output saturation in I or Q (the `sat` flag of `combine()`), and PEAK, max(|xi|, |xq|) per element, 0..2048 (|-2048| needs the full 12 bits unsigned). `blkstat.mem` holds both, and they are checked bit exactly.

## Weight computation (PS, floating point)

`w ~ [R22 + delta, -R21]`, with `delta` = load x `INT_LEN`, load in LSB^2 per sample.

Scale so that the larger of `|w1|`, `|w2|` is 1, then round to Q1.15 and clip at 0x7FFF. **The plan first normalized `|w1|` to 1, which does not work:** `|w2|/|w1|` exceeds 1 when the jammer is stronger on element 1, which Q1.15 cannot hold. The null depends only on the ratio, so this scaling costs nothing. It only moves the output level, which is why the PS has to manage `OUT_SHIFT` and TX attenuation.

`R_s[k] = alpha * R_s[k-1] + (1 - alpha) * R[k]` smooths R, not w, before this step.

## Test vectors

`model/gen_vectors.py` writes `model/vectors/<case>/` (not committed; regenerate). File formats are in the script header.

| Case | Purpose |
|---|---|
| `unity` | `y = x` on each element, then both |
| `corners` | Every input and weight extreme at shifts 0, 1, 14, 15; saturation |
| `random` | Random inputs and weight changes at random samples; mostly unsaturated, so rounding decides |
| `cw_loop` | Scenario with the PS loop; weight changes 137 samples after each block end |
| `core` | For `crpa_core_tb`: 6000 samples, six weight sets each with the full output (`out_<k>.mem`), since AXI writes are not sample exact |

## Simulated performance

`model/sim_pi.py`, full output in `results/t3_model.txt`. Bit-true path, weights from the previous block, C/N0 in 45 dB-Hz, satellite at -30 deg, jammer CW at 40 deg, noise 30 LSB rms unless noted. C/N0 comes from a correlation estimator. **Treat anything below about 33 dB-Hz as "not detected"**: with no usable signal it returns 29-33 dB-Hz on noise, and less under a strong CW, so those numbers in the log are not real C/N0 values.

**This is an ideal model.** It has no DC offset, IQ imbalance, frequency-dependent channel mismatch or AD9363 filtering, and only stationary CW. The null depths are upper bounds, and hardware will set the real limit (T4).

| J/N | C/N0 element 1 | C/N0 out | Null |
|---|---|---|---|
| none | 44.9 | 44.9 | - |
| 10 dB | not detected | 45.8 | 17.8 dB |
| 20 dB | not detected | 47.3 | 37.1 dB |
| 30 dB | not detected | 47.5 | 57.2 dB |
| 35 dB | not detected | 47.6 | 67.6 dB |
| 40 dB (ADC clips) | not detected | not detected | 32.8 dB |

Output C/N0 above the 45 dB-Hz input is array gain, and depends on the angles: the sweep tracks theory (signal gain over noise gain) to within about 1 dB, and a satellite within about 5 deg of this jammer is lost with it (28.7 dB-Hz predicted at 35 deg). That is inherent to a two-element null, not a design error.

What this says for the open parameters:

| Parameter | Finding | Starting value |
|---|---|---|
| Diagonal load | Up to 1 x noise power costs at most 1.2 dB C/N0 at J/N 10 dB; 10 x costs 8.8 dB there. Without a jammer, no load made any difference: unloaded weights already keep `|w2|` near 0.01 | 0.1 x noise power; revisit at T4, since real correlated DC or coupling may need more |
| Smoothing `alpha` | No benefit on a stationary CW | 0 |
| `INT_LEN` | 100, 1000 and 10000 samples perform alike at J/N 30 dB | 10000 (1 ms), as planned |
| RX gain | Reliable combining only needs noise of about 1-2 LSB rms (at 1 LSB: 46.6 dB-Hz out). The limit on J/N is ADC clipping, which ruins the result, so J/N max is about 20 log10(2048 / noise rms) minus margin: 35 dB at 30 LSB, 40 dB at 16 LSB, 58 dB at 2 LSB | As low as the AD9363 noise figure allows; set per scenario (T4, T5). The 16 LSB noise measured at 60 dB gain (no antenna) leaves about 40 dB |
| Channel mismatch | 3 dB and 77 deg, or 6 dB and 120 deg: same C/N0 within 0.1 dB. Calibration is not needed for power inversion | - |
