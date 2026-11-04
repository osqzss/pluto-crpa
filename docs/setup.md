# pluto-crpa: Development Environment Setup

This document describes how to set up the development environment for pluto-crpa from scratch, including the fixes found during the initial setup (2026-11-03). It is intended for humans; Claude Code works from `CLAUDE.md` and `docs/pluto-crpa-plan.md`.

Place this file at `docs/setup.md`.

Placeholders: `<user>` = GitHub account name (e.g. `osqzss`).

---

## 1. Host

| Item | Value |
|---|---|
| OS | Ubuntu 24.04.4 LTS (not officially supported by Vivado 2025.1, but works with the fixes below) |
| Vivado | 2025.1 (Vivado ML Standard, Zynq-7000 devices only) at `/tools/Xilinx/2025.1/` |
| Firmware base | plutosdr-fw upstream master (its hdl requires Vivado 2025.1) |

Why master and not a release tag: the hdl pinned by the latest plutosdr-fw release tag requires Vivado 2023.2, which does not support Ubuntu 24.04. plutosdr-fw master pins an hdl that requires Vivado 2025.1. Do not bypass the version check with `ADI_IGNORE_VERSION_CHECK=1`.

Officially supported Ubuntu versions for Vivado 2025.1 are 22.04.4 / 22.04.5 and 24.04.1. Later 24.04 point releases work in practice. A downgrade is not needed; if problems appear, use an Ubuntu 22.04 container for builds instead of reinstalling the host.

### 1.1 Dependencies

`libtinfo5` and `libncurses5` are not in the Ubuntu 24.04 repositories. Take them from the jammy (22.04) pool. The version in the pool changes over time, so list it first.

```bash
sudo apt update
sudo apt install -y build-essential git wget unzip locales \
  libx11-6 libxext6 libxrender1 libxtst6 libxi6 fontconfig \
  libncurses-dev libtinfo6 gcc-multilib
sudo locale-gen en_US.UTF-8

URL=http://archive.ubuntu.com/ubuntu/pool/universe/n/ncurses/
wget -qO- "$URL" | grep -oE 'lib(tinfo5|ncurses5)_6\.3-2ubuntu[^"]*_amd64\.deb' | sort -u
# As of 2026-11-03: 6.3-2ubuntu0.3 (6.3-2ubuntu0.1 has been removed from the pool)
wget "${URL}libtinfo5_6.3-2ubuntu0.3_amd64.deb" "${URL}libncurses5_6.3-2ubuntu0.3_amd64.deb"
sudo apt install ./libtinfo5_6.3-2ubuntu0.3_amd64.deb ./libncurses5_6.3-2ubuntu0.3_amd64.deb

ls -l /lib/x86_64-linux-gnu/libtinfo.so.5 /lib/x86_64-linux-gnu/libncurses.so.5
```

If `apt install ./xxx.deb` reports `Unsupported file ... given on commandline`, the file does not exist (failed download or wrong directory). Check with `ls -l` and `file`.

Fallback if the packages cannot be installed:

```bash
sudo ln -s /lib/x86_64-linux-gnu/libtinfo.so.6   /lib/x86_64-linux-gnu/libtinfo.so.5
sudo ln -s /lib/x86_64-linux-gnu/libncurses.so.6 /lib/x86_64-linux-gnu/libncurses.so.5
```

### 1.2 Vivado 2025.1

1. Download **AMD Unified Installer for FPGAs & Adaptive SoCs 2025.1: Linux Self Extracting Web Installer** from the AMD download page (AMD account and export compliance form required).
2. Prepare the install directory (default path since 2025.1 is `/tools/Xilinx`):
   ```bash
   sudo mkdir -p /tools/Xilinx
   sudo chown $USER:$USER /tools/Xilinx
   ```
3. Run the installer:
   ```bash
   chmod +x FPGAs_AdaptiveSoCs_Unified_*2025.1*_Lin64.bin
   ./FPGAs_AdaptiveSoCs_Unified_*2025.1*_Lin64.bin
   ```
   | Screen | Choice |
   |---|---|
   | Product | **Vitis** (includes Vivado; needed for the full firmware build / FSBL) or **Vivado** (HDL only) |
   | Edition | Vivado ML Standard (free, supports XC7Z010) |
   | Devices | SoCs -> **Zynq-7000 only** |
   | Path | `/tools/Xilinx` |
   | Cable drivers | Unchecked (install in step 4) |

   - A warning about an unsupported OS may appear; continue.
   - Java exceptions such as `IllegalArgumentException: Width (0) and height (0) cannot be <= 0` on the console are GUI repaint errors and harmless as long as the progress bar moves.
   - If the GUI hangs, use batch mode:
     ```bash
     ./FPGAs_AdaptiveSoCs_Unified_*2025.1*_Lin64.bin --keep --noexec --target ~/xinstall
     cd ~/xinstall
     ./xsetup -b AuthTokenGen
     ./xsetup -b ConfigGen      # edit ~/.Xilinx/install_config.txt: Zynq-7000 only, Destination=/tools/Xilinx
     ./xsetup -b Install -a XilinxEULA,3rdPartyEULA -c ~/.Xilinx/install_config.txt
     ```
4. JTAG cable drivers:
   ```bash
   cd /tools/Xilinx/2025.1/Vivado/data/xicom/cable_drivers/lin64/install_script/install_drivers
   sudo ./install_drivers
   ```
   If the path differs: `find /tools/Xilinx/2025.1 -name install_drivers -type f`.
5. Verify:
   ```bash
   source /tools/Xilinx/2025.1/Vivado/settings64.sh
   vivado -version
   ```
6. Environment variable used by the scripts (add to `~/.bashrc`; do not source `settings64.sh` itself in `.bashrc`):
   ```bash
   export VIVADO_SETTINGS=/tools/Xilinx/2025.1/Vivado/settings64.sh
   ```

Optional: choose "Ubuntu on Xorg" at the login screen to avoid Wayland-related GUI quirks.

### 1.3 Git

Pushes go over SSH, while fetch/clone and `.gitmodules` URLs stay HTTPS (so clones work without SSH keys). Run once per machine:

```bash
ssh -T git@github.com            # "Hi <user>! ..." means the key is registered
git config --global url."git@github.com:".pushInsteadOf "https://github.com/"
git config --global --get-regexp pushinsteadof
```

If no key exists: `ssh-keygen -t ed25519 -C "<email>"`, then register `~/.ssh/id_ed25519.pub` in GitHub (Settings -> SSH and GPG keys).

---

## 2. GitHub

1. Fork `analogdevicesinc/plutosdr-fw` and `analogdevicesinc/hdl`. Forking the main branch only is fine; the hdl commit pinned by plutosdr-fw enters the fork when the `crpa` branch is pushed (Section 4).
2. Create an empty repository `<user>/pluto-crpa`. Preferably do not add a README, .gitignore or license on GitHub (see Section 7 if you did).

---

## 3. Directory Structure

```bash
mkdir -p ~/Work/pluto-crpa && cd ~/Work/pluto-crpa
git init -b main

mkdir -p docs \
         ip/crpa_core/rtl ip/crpa_core/tb \
         model \
         sw/app sw/dts \
         scripts \
         tools \
         results

touch docs/environment.md docs/regmap.md

cat > .gitignore << 'EOF'
tools/
*.jou
*.log
*.str
.Xil/
__pycache__/
*.vcd
*.wdb
EOF

# keep empty directories in git
for d in ip/crpa_core/rtl ip/crpa_core/tb model sw/app sw/dts results; do
  touch "$d/.gitkeep"
done
```

Copy `README.md` to the root, and `pluto-crpa-plan.md` and this file to `docs/`. `CLAUDE.md` is added later (Section 8).

---

## 4. Submodules (plutosdr-fw and hdl)

```bash
cd ~/Work/pluto-crpa

# Add the plutosdr-fw fork as fw/ and create the crpa branch from upstream/master
git submodule add https://github.com/<user>/plutosdr-fw.git fw
cd fw
git remote add upstream https://github.com/analogdevicesinc/plutosdr-fw.git
git fetch upstream --tags
git checkout -b crpa upstream/master

# (1) Fetch hdl from upstream first (original .gitmodules URL = ADI);
#     a main-only fork may not contain the commit pinned by fw
git submodule update --init hdl

# (2) Create the crpa branch in hdl and push it to the fork;
#     this push brings the required history into the fork
cd hdl
git remote rename origin upstream          # current origin is ADI
git remote add origin https://github.com/<user>/hdl.git
git checkout -b crpa                       # branch from the commit pinned by fw
git push -u origin crpa
cd ..

# (3) Point .gitmodules to the hdl fork and push the fw crpa branch
git submodule set-url hdl https://github.com/<user>/hdl.git
git add .gitmodules hdl
git commit -m "Point hdl submodule to fork (crpa branch)"
git push -u origin crpa

# (4) Fetch the remaining submodules (linux, buildroot, u-boot, br2-external; several GB)
#     Only needed for the full firmware build; can be postponed
git submodule update --init --recursive
cd ..
```

Verification:

```bash
grep -n "required_vivado_version" fw/hdl/scripts/adi_env.tcl   # must be "2025.1"
git -C fw/hdl log -1 --format=%H                               # must match the line below
git -C fw ls-tree upstream/master hdl                          # hdl commit pinned by upstream master
git -C fw/hdl remote -v                                        # origin=fork, upstream=ADI
git -C fw submodule status                                     # all lines start with a space
```

State at the time of writing (plutosdr-fw master):

```
 46fb2fa54870cbddd0e5a6a26548c410723b0815 br2-external
 2e2994de5213abfa63ab5cf5f9291bf62b53d094 buildroot
 4840c81f2af172b036cb3ccb3f9f2dc45ed9c1d3 hdl
 bf1d49f17fa9e15bc40be2615ef67cdf023f660a linux
 b234cb3ae435f30c7d85ab589193fc9b93c7586d u-boot
```

Known harmless error in step (4):

```
fatal: No url found for submodule path 'u-boot/lib/mbedtls/external/mbedtls/framework' in .gitmodules
fatal: Failed to recurse into submodule path 'u-boot'
```

u-boot vendors mbedtls but keeps a stale nested gitlink without a URL. It is not used by the u-boot build and occurs after all other submodules are done. Ignore it; use `git -C fw submodule status` (without `--recursive`) for checks.

The submodule contents are never pushed by the parent repository: the parent records only the fw commit hash, and linux/buildroot/u-boot are read-only clones of ADI repositories.

Note: the `crpa` branches were first created from a release tag (v0.39 line). Because that hdl required Vivado 2023.2, fw `crpa` was reset to `upstream/master` and hdl `crpa` was recreated at the newly pinned commit and force-pushed.

---

## 5. Scripts

All scripts are ASCII English and use `set -euo pipefail`.

### 5.1 scripts/setup.sh (link the custom IP into the hdl library)

```bash
cat > scripts/setup.sh << 'EOF'
#!/usr/bin/env bash
# One-time setup: make the custom IP visible to the ADI hdl library.
# Usage: ./scripts/setup.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LIB="$ROOT/fw/hdl/library"

if [ ! -d "$LIB" ]; then
  echo "error: $LIB not found. Run 'git submodule update --init' in fw/ first." >&2
  exit 1
fi

ln -sfn "$ROOT/ip/crpa_core" "$LIB/crpa_core"

# Exclude the link from the hdl repository (do not commit it)
EXCL="$(git -C "$ROOT/fw/hdl" rev-parse --git-path info/exclude)"
case "$EXCL" in /*) ;; *) EXCL="$ROOT/fw/hdl/$EXCL" ;; esac
mkdir -p "$(dirname "$EXCL")"
grep -qx "library/crpa_core" "$EXCL" 2>/dev/null || echo "library/crpa_core" >> "$EXCL"

echo "linked: $LIB/crpa_core -> $ROOT/ip/crpa_core"
EOF
chmod +x scripts/setup.sh
./scripts/setup.sh

ls -l fw/hdl/library/crpa_core          # -> .../ip/crpa_core
git -C fw/hdl status --short            # library/crpa_core is not listed
```

The submodule `.git` is a file pointing into the parent `.git/modules/`, so the exclude path is obtained with `git rev-parse --git-path` and converted to an absolute path if needed. An empty `library/crpa_core` does not break the Pluto build, since `make` in `projects/pluto` builds only the libraries the project depends on.

### 5.2 scripts/record_env.sh (environment snapshot)

```bash
cat > scripts/record_env.sh << 'EOF'
#!/usr/bin/env bash
# Print development environment and repository state as Markdown.
# Usage: ./scripts/record_env.sh >> docs/environment.md
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FW="$ROOT/fw"; HDL="$FW/hdl"

VIV="(VIVADO_SETTINGS not set)"
if [ -n "${VIVADO_SETTINGS:-}" ]; then
  VIV="$(bash -c "source '$VIVADO_SETTINGS' >/dev/null 2>&1; vivado -version | head -1")"
fi

cat << MD

## Snapshot: $(date +%F)

### Host
| Item | Value |
|---|---|
| OS | $(lsb_release -ds) |
| Kernel | $(uname -r) |
| Vivado | $VIV |

### plutosdr-fw (fw/)
| Item | Value |
|---|---|
| Base (upstream) | master @ \`$(git -C "$FW" merge-base HEAD upstream/master)\` |
| Working branch | \`$(git -C "$FW" rev-parse --abbrev-ref HEAD)\` @ \`$(git -C "$FW" rev-parse HEAD)\` |

### ADI hdl (fw/hdl/)
| Item | Value |
|---|---|
| Base (pinned by upstream master) | \`$(git -C "$FW" ls-tree upstream/master hdl | awk '{print $3}')\` |
| Working branch | \`$(git -C "$HDL" rev-parse --abbrev-ref HEAD)\` @ \`$(git -C "$HDL" rev-parse HEAD)\` |
| required_vivado_version | $(grep -m1 -oP 'required_vivado_version "\K[^"]+' "$HDL/scripts/adi_env.tcl") |

### Other submodules (pinned by fw)
\`\`\`
$(git -C "$FW" submodule status)
\`\`\`
MD
EOF
chmod +x scripts/record_env.sh
```

Header to write by hand at the top of `docs/environment.md`:

```markdown
# Development Environment

## Decisions
- Based on plutosdr-fw master (Vivado 2025.1) instead of the release tag,
  whose hdl requires Vivado 2023.2 (2026-11-03)

## Host-specific notes
- Ubuntu 24.04.4 is not officially supported by Vivado 2025.1;
  installed libtinfo5 / libncurses5 6.3-2ubuntu0.3 from jammy
- Vivado: /tools/Xilinx/2025.1, Zynq-7000 devices only
- JTAG cable drivers: installed / not installed
```

Then append a snapshot, and repeat after upstream updates, Vivado changes or host migration:

```bash
./scripts/record_env.sh >> docs/environment.md
```

### 5.3 scripts/report_util.tcl and scripts/build_hdl.sh (HDL build + reports)

```bash
cat > scripts/report_util.tcl << 'EOF'
# usage: vivado -mode batch -source report_util.tcl -tclargs <xpr> <outdir>
set xpr    [lindex $argv 0]
set outdir [lindex $argv 1]
file mkdir $outdir
open_project $xpr
open_run impl_1
report_utilization                              -file $outdir/util_placed.rpt
report_utilization -hierarchical -hierarchical_depth 4 -file $outdir/util_hier.rpt
report_timing_summary -max_paths 10             -file $outdir/timing_summary.rpt
close_project
EOF

cat > scripts/build_hdl.sh << 'EOF'
#!/usr/bin/env bash
# Build the Pluto HDL project and save utilization/timing reports.
# Usage: VIVADO_SETTINGS=/path/to/settings64.sh ./scripts/build_hdl.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
: "${VIVADO_SETTINGS:?set VIVADO_SETTINGS to .../Vivado/settings64.sh}"

# Vivado/Vitis settings scripts reference unset variables; relax nounset while sourcing
set +u
source "$VIVADO_SETTINGS"
set -u

PROJ="$ROOT/fw/hdl/projects/pluto"
make -C "$PROJ"

STAMP="$(date +%Y%m%d-%H%M)_$(git -C "$ROOT/fw/hdl" rev-parse --short HEAD)"
OUT="$ROOT/results/hdl/$STAMP"
vivado -mode batch -nojournal -nolog \
  -source "$ROOT/scripts/report_util.tcl" -tclargs "$PROJ/pluto.xpr" "$OUT"
echo "reports: $OUT"
EOF
chmod +x scripts/build_hdl.sh
```

Without `set +u` around `source`, the script stops with `/tools/Xilinx/2025.1/Vitis/.settings64-Vitis.sh: line 13: PYTHONPATH: unbound variable`.

---

## 6. Default Design Build (T0)

```bash
cd ~/Work/pluto-crpa
./scripts/build_hdl.sh 2>&1 | tee results/build_hdl.log
```

- Takes 30-60 minutes. Reports go to `results/hdl/<date>-<time>_<hdl commit>/`.
- `results/build_hdl.log` is git-ignored; the `.rpt` files are committed.
- On errors, check the end of `results/build_hdl.log` and the first `ERROR` line in `fw/hdl/projects/pluto/*.log`.

Result on 2026-11-03 (`results/hdl/20261103-1639_4840c81f2/`): LUT 72%, FF 63%, DSP48 72/80 (90%), RAMB36 2/60; all timing constraints met (worst WNS 0.946 ns on clk_fpga_0). Details and decisions are in `docs/pluto-crpa-plan.md` Section 6.5.

---

## 7. Parent Repository Commit and Push

```bash
cd ~/Work/pluto-crpa
git -C fw/hdl status -sb        # "## crpa...origin/crpa", nothing ahead
git -C fw status -sb            # same

git status                      # review
git add -A
git commit -m "Initial project structure, scripts and T0 reports"
git remote add origin https://github.com/<user>/pluto-crpa.git
git push -u origin main
```

If the push is rejected with `Updates were rejected because the remote contains work that you do not have locally`, the GitHub repository was created with an initial commit (README / .gitignore / license):

```bash
git fetch origin
git show --stat origin/main
```

- Keep its content (e.g. a license):
  ```bash
  git pull --allow-unrelated-histories --no-rebase origin main
  # on conflicts keep the local versions:
  git checkout --ours README.md .gitignore
  git add README.md .gitignore
  git commit -m "Merge initial GitHub commit"
  git push -u origin main
  ```
- Discard it (only auto-generated files):
  ```bash
  git push -u --force-with-lease origin main
  ```

---

## 8. Claude Code

1. Place `CLAUDE.md` in the repository root and `pluto-crpa-plan.md` in `docs/`, then commit:
   ```bash
   git add CLAUDE.md docs/pluto-crpa-plan.md
   git commit -m "Add CLAUDE.md and English development plan"
   git push
   ```
2. Install and check Claude Code:
   ```bash
   curl -fsSL https://claude.ai/install.sh | bash
   claude --version
   ```
3. Start it in the repository root (not inside `fw/` or `fw/hdl/`, where the root `CLAUDE.md` would not be loaded):
   ```bash
   cd ~/Work/pluto-crpa
   export VIVADO_SETTINGS=/tools/Xilinx/2025.1/Vivado/settings64.sh
   claude
   ```
4. First prompt (plan mode recommended):
   ```
   Read CLAUDE.md and docs/pluto-crpa-plan.md. Then start Task 1 (FIR removal baseline):
   read fw/hdl/projects/pluto/system_bd.tcl and report how rx_fir_decimator and
   tx_fir_interpolator are connected, and propose the rewiring. Do not edit any files yet.
   ```
5. Resume later with: `Continue with the next unfinished task in docs/pluto-crpa-plan.md`.

---

## 9. Full Firmware Build

Builds the complete Pluto firmware (FPGA bitstream, FSBL, u-boot, Linux, Buildroot root filesystem) from `fw/`. Needed for hardware tests. The unmodified upstream master was built successfully this way on 2026-11-04 (Ubuntu 24.04.4, Vivado 2025.1).

### 9.1 Prerequisites

Packages listed in `fw/README.md`, with `libncurses5-dev` replaced by `libncurses-dev` (not available on Ubuntu 24.04), plus packages the u-boot build needs but the README does not list (`bison: not found` was the first failure without them):

```bash
# from fw/README.md
sudo apt install -y git build-essential fakeroot libncurses-dev libssl-dev ccache \
  dfu-util u-boot-tools device-tree-compiler mtools \
  bc python3 cpio zip unzip rsync file wget

# additionally required (u-boot kconfig, mkimage, pylibfdt)
sudo apt install -y bison flex libgnutls28-dev uuid-dev python3-dev python3-setuptools swig
```

The Arm GNU cross toolchain (`arm-none-linux-gnueabihf`) is downloaded and set up automatically during the build; Vivado/Vitis's own GCC is not used.

### 9.2 Build

```bash
cd ~/Work/pluto-crpa/fw
git submodule status            # all five lines start with a space (Section 4)
export VIVADO_SETTINGS=/tools/Xilinx/2025.1/Vivado/settings64.sh
make 2>&1 | tee ../results/fw_build.log
```

- The first build takes several hours and needs tens of GB of disk space.
- If the build stops (e.g. a missing package), install what is missing and run `make` again in `fw/`. Completed parts (toolchain, Buildroot packages) are reused.
- `results/fw_build.log` is git-ignored (`*.log`).
- `fw/build/` is ignored by the fw repository; build outputs are never committed to the parent.

### 9.2.1 Untracked build products in nested submodules

The build writes `fw/br2-external/board/adi/pluto/VERSIONS` (build date and submodule commits; it becomes `/opt/VERSIONS` on the Pluto). It is not tracked by br2-external, so after a build `git status` shows:

```
$ git -C fw status --short
 ? br2-external
$ git status --short
 ? fw
```

linux, u-boot and buildroot stay clean (their own `.gitignore` files cover the build products). Ignore untracked files in br2-external through fw's `.gitmodules` (committed on the fw `crpa` branch, so other clones get the same setting):

```bash
cd ~/Work/pluto-crpa/fw
git -C br2-external status --short       # expect only: ?? board/adi/pluto/VERSIONS
git config -f .gitmodules submodule.br2-external.ignore untracked
git add .gitmodules
git commit -m "Ignore untracked build products in br2-external"
git push                                 # -> <user>/plutosdr-fw, branch crpa

cd ..
git add fw
git commit -m "Update fw: ignore untracked files in br2-external"
git push

git -C fw status --short                 # no output
git status --short                       # no output
```

- `ignore = untracked` hides only untracked files; modified tracked files in br2-external are still reported.
- If linux, u-boot or buildroot start showing ` ?` after later builds, add `submodule.<name>.ignore untracked` the same way.
- Do **not** set `ignore` for `hdl` (in fw) or for `fw` (in the parent). hdl is under active development, and a parent showing `fw (modified content)` is the reminder that the hdl pointer in fw has not been committed yet.
- Adding the file to the parent `.gitignore` would have no effect: a repository's `.gitignore` does not apply inside its submodules.

### 9.3 Outputs (`fw/build/`)

| File | Use |
|---|---|
| `plutosdr-fw-<ver>.zip` | Release-style archive: `pluto.frm`, `boot.frm`, `pluto.dfu`, `boot.dfu`, `uboot-env.dfu`, ... |
| `pluto.frm` | Main firmware (FIT image) for USB mass storage update |
| `pluto.dfu` | Main firmware for DFU mode |
| `boot.frm` / `boot.dfu` | FSBL + u-boot |
| `system_top.bit`, `system_top.xsa` | FPGA bitstream and hardware description |
| `rootfs.cpio.gz`, `zImage`, `zynq-pluto-sdr-revc.dtb` | Root filesystem, kernel, device tree (Rev C) |

### 9.4 Flashing (USB mass storage)

Before flashing, keep the latest official release zip from the plutosdr-fw release page at hand for rollback, and note the current version:

```bash
ssh root@192.168.2.1 'cat /opt/VERSIONS'     # password: analog
```

Procedure (ADI wiki "Firmware Updates", Mass Storage Update):

1. Connect the Pluto by USB. It mounts as a drive named `PlutoSDR`.
2. Copy the firmware to the root of the drive:
   - **Main firmware only (lowest risk, try first):**
     ```bash
     cp ~/Work/pluto-crpa/fw/build/pluto.frm /media/$USER/PlutoSDR/
     sync
     ```
   - **Rev C, per the wiki: the entire unzipped release archive** (this also contains `boot.frm`, i.e. FSBL + u-boot):
     ```bash
     mkdir -p /tmp/pluto-fw && cd /tmp/pluto-fw
     unzip -o ~/Work/pluto-crpa/fw/build/plutosdr-fw-*.zip
     cp * /media/$USER/PlutoSDR/
     sync
     ```
     Use this if copying `pluto.frm` alone does not update the device (`/opt/VERSIONS` unchanged).
3. Eject the drive; do not unplug. On Linux, eject the base device, not the partition:
   ```bash
   lsblk                    # e.g. sdb with partition sdb1
   sudo eject /dev/sdb
   ```
4. LED1 blinks rapidly while programming (about 4 minutes). **Do not unplug or remove power until the rapid blinking stops.** The device then reappears as a mass storage drive.

### 9.5 Verification

```bash
ssh root@192.168.2.1 'cat /opt/VERSIONS; uname -a'   # build date and fw/hdl/linux commits
iio_info -s                                         # Pluto listed (package libiio-utils)
iio_attr -u ip:192.168.2.1 -d                       # ad9361-phy, cf-ad9361-lpc, cf-ad9361-dds-core-lpc, ...
```

`info.html` on the Pluto drive also shows the installed firmware version; compare before and after flashing.

The most direct check that our own build is running: the `VERSIONS` file generated by the build is installed as `/opt/VERSIONS`, so the two must match.

```bash
cat ~/Work/pluto-crpa/fw/br2-external/board/adi/pluto/VERSIONS   # what this build will report
ssh root@192.168.2.1 'cat /opt/VERSIONS'                          # what the Pluto reports
diff <(cat ~/Work/pluto-crpa/fw/br2-external/board/adi/pluto/VERSIONS) \
     <(ssh root@192.168.2.1 'cat /opt/VERSIONS') && echo "match: own build is running"
```

If the Pluto still reports the previous version after flashing `pluto.frm` alone, use the full unzipped archive (Section 9.4, Rev C).

### 9.6 Recovery (DFU)

- Enter DFU mode by holding the button (toothpick/paperclip) while plugging in USB, or with `device_reboot sf` on the Linux console (SSH works). The device also enters DFU automatically if the main firmware fails to boot.
- In DFU mode the DONE LED is off and LED1 is on (USB PID 0xB674).
- Flash the official release:
  ```bash
  sudo dfu-util -a firmware.dfu -D pluto.dfu
  ```
- If problems persist, rewrite in this order: firmware (`pluto.dfu`), `boot.dfu`, `uboot-env.dfu`.
- DFU is provided by u-boot. Flashing only `pluto.frm` leaves u-boot untouched, so DFU recovery remains available; flashing `boot.frm` from our own build replaces u-boot.

### 9.7 Sysroot for the PS application

- The PS application must be built against the firmware actually flashed to the Pluto, i.e. this build, not a release sysroot.
- The cross toolchain is in `fw/buildroot/output/host/bin/` (prefix `arm-none-linux-gnueabihf-`), as seen in the build log `PATH`. The sysroot is expected in `fw/buildroot/output/staging/`. **To be confirmed** before the first PS application build.
- Cross-compilation example (confirm the paths first):
  ```bash
  FWB=~/Work/pluto-crpa/fw/buildroot/output
  $FWB/host/bin/arm-none-linux-gnueabihf-gcc --sysroot=$FWB/staging \
    -o sw/app/crpa_ctl sw/app/crpa_ctl.c -liio
  ```

---

## 10. Cloning on Another Machine

```bash
git clone --recursive https://github.com/<user>/pluto-crpa.git
cd pluto-crpa
./scripts/setup.sh
```

Set up the host first (Section 1: dependencies, Vivado, `VIVADO_SETTINGS`, `pushInsteadOf`; Section 9.1 for the firmware build packages). The u-boot mbedtls `fatal` messages during `--recursive` (Section 4) are expected.
