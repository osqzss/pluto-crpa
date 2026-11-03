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
