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

## 4. Interactive commands (`ssh -t`, default `--rt 40` build)

Run by the user in their own terminal: `ssh -t pluto /mnt/jffs2/crpa_ctl run --mode pi --monitor 5`, about 300 s, 301579 blocks. Dry run throughout. Log of the Ctrl-C run: `results/t6b_interactive.txt`.

| Command | Result |
|---|---|
| `help`, `level`, `status` | correct output |
| `rx 40` | x1 -48.7, x2 -52.0 dBFS: only 6-9 dB lower, since the receiver's own noise dominates at 40 dB. x2 is 3.5 dB below x1, the low-gain floor difference noted in plan Section 10.2 |
| `rx 60` | back to -42.6 / -42.9 dBFS |
| `tx 50` | refused in dry run |
| `w 0 0 1 0` | y estimate = x2, -42.9 dBFS |
| `w 1 0 1 0` | y estimate -39.7 dBFS; x1 + x2 of uncorrelated noise at -42.6 and -42.9 gives -39.74 |
| `shift 1`, `shift 0` | +6.1 dB, then back |
| `pi`, `load 22` | \|w2\| 0.01-0.03 again (load about 0.1 x noise power) |
| `rx abc`, `w 2 0 0 0`, `shift 16`, `foo` | each refused with its own message, run continues. Typed on one line, the whole line goes to `rx` and only its message appears |
| `note`, `quit` | NOTE line; safe state confirmed |
| Ctrl-C (second run) | `stopped by signal 2`, safe state confirmed |

Blocks lost in the 300 s run: 10. 5 at startup, 3 during `status` and 1 during each `rx`: these commands read or write AD9363 attributes over SPI in the same SCHED_FIFO thread as the loop. None during the 5 s monitor checks. Acceptable for operator commands; the CSV shows each gap. If it matters at T4, move the block loop to its own thread. Typed characters and summary lines interleave on the terminal (cosmetic).

## 5. Not yet tested

- `--on` (transmit): needs the conducted setup and the user's per-run go (T2).
