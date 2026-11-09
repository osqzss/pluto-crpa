# Task 6b: crpa_ctl Dry Run on the CRPA Unit

Date: 2026-11-09. Unit: second Pluto (CRPA unit), Rev C, AD9363A, `mode=2r2t`. Firmware as in `results/t6a_dt_check.md` (linux `a26ff66`, hdl `ad150ddd5`).

Program: `sw/app/crpa_ctl` (uncommitted working tree at the time of the runs), built with `make` in `sw/app/` against the Buildroot toolchain and sysroot of our firmware build, copied to `/mnt/jffs2/` with `scp -O`. No run used `--on`: in every run the TX LO stayed powered down and parked at 2400 MHz, with TX attenuation 89.75 dB on both channels.

## 1. Host checks

- `make test`: C weights (`crpa_pi.c`) equal the model's `PiLoop` / `pi_weights` / `quantize_weights` Q1.15 output for all 4156 cases (edge cases, model scenario blocks, random R over 48 bits, sequences with loading and smoothing). numpy 2.2.2.
- Toolchain: `fw/buildroot/output/host/bin/arm-none-linux-gnueabihf-gcc` (Arm GNU 14.2.Rel1) is the Buildroot wrapper and passes the sysroot `fw/buildroot/output/staging` itself. libiio 0.26 headers and library in staging; the same version on the Pluto. Build has no warnings.

## 2. Dry-run test (`sw/app/dry_test.sh`)

First attempt: every `run` refused, because the unit was not in the safe state: `data_sel [0 0 2 2]`, TX LO powered up at 2450 MHz with 10 dB attenuation (left by earlier tools and the boot default). `crpa_ctl off` then reached the safe state. This is the intended behavior; after a reboot or other tools, run `crpa_ctl off` once on purpose.

Second attempt, all at fs 10 MSPS, bw 9 MHz, delta +3 MHz, RX gain 60 dB manual, INT_LEN 10000 (1 ms), normal scheduling:

| Run | Result |
|---|---|
| status | read-only report; crpa_core idle, STATUS 0x4 (FRAME_ERR from boot) |
| fixed [1,0], irq, 5 s | 4978 blocks; x1 -42.6, x2 -42.9 dBFS; y estimate = x1; no FRAME_ERR/RES_DROP |
| fixed [0,1], 3 s | y estimate = x2 (-42.9 dBFS) |
| PI, load 0, 5 s | \|w2\| 0.01-0.03 with noise only, as in the model (`docs/fixed_point.md`) |
| `--poll-status`, 3 s | same as irq |
| refusals | `--on` without a terminal, fs 1 MSPS, delta 1 MHz: refused, nothing changed |
| SIGTERM after 2 s | rc 143, safe state confirmed |
| off | safe state confirmed |

`/proc/interrupts`: 14687 crpa_core interrupts, equal to the blocks processed by the irq runs.

Noise floor -42.7 dBFS is about 15 LSB rms, consistent with the 16 LSB recorded earlier at 60 dB gain.

## 3. Dropped blocks and real-time priority (`sw/app/gap_test.sh`)

With normal scheduling about 0.5% of blocks were lost (MISSED 24-30 per 5 s run). The CSV timestamps (`results/t6b_fixed.csv`, `results/t6b_pi.csv`) show one stall per second of 5-8 ms (max time between processed blocks 7.8-8.6 ms, normally 1.00 ms), each dropping 1-7 blocks. It is not the 2 s monitor check. Processes on the Pluto include `/sbin/update.sh`, a shell loop with `sleep 1`, the likely source; in 1 s only the timer (110) and USB (2) interrupts fired.

| Run | Gaps after startup | Blocks lost | Max time between blocks |
|---|---|---|---|
| A: normal scheduling, fixed, 5 s | 5 (one per second) | 23 | 7.57 ms |
| B: `--rt 40`, fixed, 5 s | 0 | 0 | 1.25 ms |
| C: `--rt 40`, PI, 10 s | 0 | 0 | 1.23 ms |

SCHED_FIFO 40 is below the irq threads (50, including `irq/33-crpa_core`); RT throttling stays at the default 950000/1000000 us. `--rt 40` is now the default (`--rt 0` for normal scheduling). The 6-8 blocks lost at startup (set-up report between the start of the blocks and the loop) remain; the first block is discarded in any case.

## 4. Not yet tested

- `--on` (transmit): needs the conducted setup and the user's per-run go (T2).
- Interactive commands (`rx`, `tx`, `w`, `pi`, `load`, `shift`, `status`, `note`) need a terminal (`ssh -t`).
- The default `--rt 40` build: same code as run B/C, only the default changed; copy it again before T2.
