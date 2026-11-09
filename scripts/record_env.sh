#!/usr/bin/env bash
# Print development environment and repository state as Markdown.
# Usage: ./scripts/record_env.sh >> docs/environment.md
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FW="$ROOT/fw"; HDL="$FW/hdl"; LNX="$FW/linux"

VIV="(VIVADO_SETTINGS not set)"
if [ -n "${VIVADO_SETTINGS:-}" ]; then
  VIV="$(bash -c "source '$VIVADO_SETTINGS' >/dev/null 2>&1; vivado -version | head -1")"
fi

# Test equipment. Absent devices must not abort the snapshot. These commands
# only read status; none of them transmits.
GPS_SDR_SIM_DIR="${GPS_SDR_SIM_DIR:-$HOME/Work/gps-sdr-sim}"
UBLOX_DEV="/dev/serial/by-id/usb-u-blox_AG_-_www.u-blox.com_u-blox_GNSS_receiver-if00"

try() { "$@" 2>/dev/null || true; }
or_na() { if [ -n "$1" ]; then printf '%s' "$1"; else printf 'not available'; fi; }

GPS_SDR_SIM_COMMIT="$(try git -C "$GPS_SDR_SIM_DIR" rev-parse HEAD)"
BLADERF_LIB="$(try bladeRF-cli --lib-version)"
BLADERF_CLI="$(try bladeRF-cli --version)"
BLADERF_VER="$(try timeout 30 bladeRF-cli -e version)"
BLADERF_FPGA="$(printf '%s\n' "$BLADERF_VER" | sed -n 's/^ *FPGA version: *//p')"
UHD_VER="$(try uhd_config_info --version)"
GPSD_VER="$(try gpsd -V)"
# ubxtool starts gpsd through socket activation if it is not already running.
# Skip it when the receiver is not connected.
UBLOX_VER=""
if [ -e "$UBLOX_DEV" ]; then
  UBLOX_VER="$(try timeout 30 ubxtool -p MON-VER -w 3)"
fi
UBLOX_FW="$(printf '%s\n' "$UBLOX_VER" | sed -n 's/^ *extension FWVER=//p' | head -1)"
UBLOX_PROT="$(printf '%s\n' "$UBLOX_VER" | sed -n 's/^ *extension PROTVER=//p' | head -1)"

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

### ADI linux (fw/linux/)
| Item | Value |
|---|---|
| Base (pinned by upstream master) | \`$(git -C "$FW" ls-tree upstream/master linux | awk '{print $3}')\` |
| Working branch | \`$(git -C "$LNX" rev-parse --abbrev-ref HEAD)\` @ \`$(git -C "$LNX" rev-parse HEAD)\` |

### Other submodules (pinned by fw)
\`\`\`
$(git -C "$FW" submodule status)
\`\`\`

### Test equipment
| Item | Value |
|---|---|
| gps-sdr-sim commit | \`$(or_na "$GPS_SDR_SIM_COMMIT")\` |
| libbladeRF | $(or_na "$BLADERF_LIB") |
| bladeRF-cli | $(or_na "$BLADERF_CLI") |
| bladeRF FPGA | $(or_na "$BLADERF_FPGA") |
| UHD | $(or_na "$UHD_VER") |
| gpsd | $(or_na "$GPSD_VER") |
| u-blox firmware | $(or_na "$UBLOX_FW") |
| u-blox protocol version | $(or_na "$UBLOX_PROT") |
MD
