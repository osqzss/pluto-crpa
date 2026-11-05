
# Development Environment

## Decisions
- Based on plutosdr-fw master (Vivado 2025.1) instead of the release tag,
  whose hdl requires Vivado 2023.2 (2026-11-03)

## Host-specific notes
- Ubuntu 24.04.4 is not officially supported by Vivado 2025.1;
  installed libtinfo5 / libncurses5 6.3-2ubuntu0.3 from jammy
- Vivado: /tools/Xilinx/2025.1, Zynq-7000 devices only
- JTAG cable drivers: installed / not installed

## Snapshot: 2026-11-03

### Host
| Item | Value |
|---|---|
| OS | Ubuntu 24.04.4 LTS |
| Kernel | 6.17.0-20-generic |
| Vivado | vivado v2025.1 (64-bit) |

### plutosdr-fw (fw/)
| Item | Value |
|---|---|
| Base (upstream) | master @ `3b689562bfef2e9312a18cf3dba093c1fc00bc72` |
| Working branch | `crpa` @ `2414114880f3f5661a62981ea7cf7459d21aaca3` |

### ADI hdl (fw/hdl/)
| Item | Value |
|---|---|
| Base (pinned by upstream master) | `4840c81f2af172b036cb3ccb3f9f2dc45ed9c1d3` |
| Working branch | `crpa` @ `4840c81f2af172b036cb3ccb3f9f2dc45ed9c1d3` |
| required_vivado_version | 2025.1 |

### Other submodules (pinned by fw)
```
-46fb2fa54870cbddd0e5a6a26548c410723b0815 br2-external
-2e2994de5213abfa63ab5cf5f9291bf62b53d094 buildroot
 4840c81f2af172b036cb3ccb3f9f2dc45ed9c1d3 hdl (dev_prj_2018_r1-3136-g4840c81f2)
-bf1d49f17fa9e15bc40be2615ef67cdf023f660a linux
-b234cb3ae435f30c7d85ab589193fc9b93c7586d u-boot
```

## Snapshot: 2026-11-03

### Host
| Item | Value |
|---|---|
| OS | Ubuntu 24.04.4 LTS |
| Kernel | 6.17.0-20-generic |
| Vivado | vivado v2025.1 (64-bit) |

### plutosdr-fw (fw/)
| Item | Value |
|---|---|
| Base (upstream) | master @ `3b689562bfef2e9312a18cf3dba093c1fc00bc72` |
| Working branch | `crpa` @ `2414114880f3f5661a62981ea7cf7459d21aaca3` |

### ADI hdl (fw/hdl/)
| Item | Value |
|---|---|
| Base (pinned by upstream master) | `4840c81f2af172b036cb3ccb3f9f2dc45ed9c1d3` |
| Working branch | `crpa` @ `4840c81f2af172b036cb3ccb3f9f2dc45ed9c1d3` |
| required_vivado_version | 2025.1 |

### Other submodules (pinned by fw)
```
 46fb2fa54870cbddd0e5a6a26548c410723b0815 br2-external (2025.05-0.3.0-54-g46fb2fa)
 2e2994de5213abfa63ab5cf5f9291bf62b53d094 buildroot (2025.05-3633-g2e2994de52)
 4840c81f2af172b036cb3ccb3f9f2dc45ed9c1d3 hdl (dev_prj_2018_r1-3136-g4840c81f2)
 bf1d49f17fa9e15bc40be2615ef67cdf023f660a linux (v6.12-43124-gbf1d49f17fa9)
 b234cb3ae435f30c7d85ab589193fc9b93c7586d u-boot (b234cb3ae43)
```

## Snapshot: 2026-11-05

### Host
| Item | Value |
|---|---|
| OS | Ubuntu 24.04.4 LTS |
| Kernel | 7.0.0-42-generic |
| Vivado | vivado v2025.1 (64-bit) |

### plutosdr-fw (fw/)
| Item | Value |
|---|---|
| Base (upstream) | master @ `3b689562bfef2e9312a18cf3dba093c1fc00bc72` |
| Working branch | `crpa` @ `27fb31b8fb653b99ddf79f156880b910e4f894c4` |

### ADI hdl (fw/hdl/)
| Item | Value |
|---|---|
| Base (pinned by upstream master) | `4840c81f2af172b036cb3ccb3f9f2dc45ed9c1d3` |
| Working branch | `crpa` @ `387ca1761a26650a6a745c382dccacf0dfe93e3e` |
| required_vivado_version | 2025.1 |

### Other submodules (pinned by fw)
```
 46fb2fa54870cbddd0e5a6a26548c410723b0815 br2-external (2025.05-0.3.0-54-g46fb2fa)
 2e2994de5213abfa63ab5cf5f9291bf62b53d094 buildroot (2025.05-3633-g2e2994de52)
 387ca1761a26650a6a745c382dccacf0dfe93e3e hdl (dev_prj_2018_r1-3137-g387ca1761)
 bf1d49f17fa9e15bc40be2615ef67cdf023f660a linux (v6.12-43124-gbf1d49f17fa9)
 b234cb3ae435f30c7d85ab589193fc9b93c7586d u-boot (b234cb3ae43)
```
