# Project structure

NetCroc keeps the application, tests, development tools and documentation separate. The current layout is intentionally shallow; there is no need for another nested framework or a file per small helper.

## Top-level folders

| Folder | Purpose |
|---|---|
| `src/` | Runnable Python application and pinned dependencies. |
| `tests/` | Automated unit, GUI and native loopback tests. |
| `tools/` | Build helpers, verification utilities and explicit live-test runners. |
| `docs/` | User setup guides, research and dated test history. |
| `assets/` | Current icon/diagram plus local design explorations. |
| `.github/workflows/` | Native Windows/macOS/Linux tests and package CI. |
| `releases/` | Generated local EXE and launcher; ignored by Git. |
| `test-artifacts/` | Generated local evidence, routing-core downloads and build inputs; ignored by Git. |

`.git/`, `.venv/` and `__pycache__/` are repository/runtime internals rather than application features. Virtual environments and Python caches are ignored by Git.

## Read the source in this order

| File under `src/` | Responsibility |
|---|---|
| `app.py` | Entry point, startup error reporting and independent DNS helper modes. |
| `netcroc/ui.py` | Main window, tray, preferences and application lifetime. |
| `netcroc/dashboard.py` | Traffic, history, DNS, Wi-Fi, research and VPN tabs; shared monitoring loop. |
| `netcroc/core.py` | Connection-check settings, presets and shared local-data helpers. |
| `netcroc/traffic.py` | Adapter rates and Windows ETW per-app byte capture. |
| `netcroc/history.py` | SQLite recording, rolling/calendar periods, retention and exports. |
| `netcroc/dns.py` | Resolver benchmarking, Windows settings and rollback watchdog. |
| `netcroc/wifi.py` | Native saved-profile access, current connection and network management. |
| `netcroc/research.py` | Bounded HTTP/ICMP comparisons and study helpers. |
| `netcroc/platforms.py` | Native paths, startup, OS keyring encryption, instance lock, authorization and child-crash guard. |
| `netcroc/tun_service.py` | Privileged POSIX routing worker, private control transactions and parent-crash cleanup. |
| `netcroc/posix_network.py` | macOS/Linux Wi-Fi, DNS, WireGuard and optional metadata capture. |
| `netcroc/vpn.py` | WireGuard parsing, DPAPI storage and Windows tunnel services. |
| `netcroc/ssh_tunnel.py` | SSH/TLS transport, profile storage and local SOCKS server. |
| `netcroc/ssh_routing.py` | Verified optional core, whole-PC routing and child-process cleanup. |
| `netcroc/ssh_ui.py` | SSH profile editor and session controls. |
| `netcroc/vless.py` | VLESS parsing/storage, native configuration, sessions and proxy IP checks. |
| `netcroc/vless_ui.py` | VLESS account editor and explicit connection controls. |

The UI calls the backends; the monitoring loop writes history. GUI diagnostics do not initiate live capture or change network settings. Dependencies stay in `src/requirements.txt` so source setup, build and CI share the same versions.

## Tools: ordinary checks versus live tests

| Group | Files in `tools/` |
|---|---|
| Build | `package_release.py`, `release.py`, `refresh_bundle.py` |
| Read-only/source/package checks | `verify_bundle.py`, `smoke_frozen.py`, `preview_gui.py` |
| Optional verified core download/config check | `check_ssh_routing.py` |
| Local transport stress tests | `soak_connections.py` |
| Read-only process/history observation | `longrun_observer.py` |
| Explicit live network tests | `live_admin_checks.py`, `live_dns_rollback_check.py`, `live_dns_timeout_check.py`, `live_tunnel_check.py`, `live_wireguard_check.py`, `live_wifi_switch_check.py`, `live_provider_check.py`, `live_posix_routing_check.py` |

The `live_*` scripts are opt-in lab tools, not startup code. Only the explicitly isolated Linux routing lab runs in CI; it refuses the host network namespace. Depending on the script they need elevation, change DNS/routes, create temporary services or switch Wi-Fi. Review their arguments and recovery behaviour before running them at the PC. Standard tests use synthetic credentials; provider checks require a private local profile or an existing encrypted profile ID.

## Assets and design drafts

`assets/netcroc.ico` is the build icon. `netcroc.png` and `architecture.svg` are existing artwork. The logo concept directories and `netcroc-cloud-logo-v*` files are design drafts; none has been selected as a replacement icon. Keep the current gallery paths stable while reviewing concepts. They are separate from runtime data and private VPN profiles.

The tracked project can be checked with `git ls-files`; local logo experiments may appear as untracked files. `tools/release.py --check` checks local assets too, so its file count can differ from a clean checkout.

## Documentation

- [Main README](../README.md): features, setup, usage periods and development commands.
- [Free VPN setup](FREE-VPN-SETUP.md), [SSH/TLS](SSH-TLS.md) and [VLESS](VLESS.md): account and connection guides.
- [Network research](NETWORK-RESEARCH.md) and [VPN research](VPN-RESEARCH.md): rationale and provider limitations.
- [Study and tests](STUDY-AND-TESTS.md): dated validation snapshots; later sections can supersede older pending items.
- `research-data/`: bounded study results.
- [Legacy Fastlane notes](LEGACY-FASTLANE.md): historical documentation, not current setup instructions.

## Deliberate compatibility identifiers

`ConnectionTrayPreview` remains for existing local data, legacy startup cleanup and shared instance locks. Keeping it prevents lost history, abandoned DNS recovery state and two usage writers during migration. Fresh installations use the NetCroc data folder. Startup entries change only when the user saves the startup preference.

The optional bundle-refresh utility recognizes the older package name when examining compatible earlier builds, then writes the current `netcroc` package and verifies module fingerprints.

Executables, test evidence and private VPN configuration files are excluded from Git. Publishing a downloadable GitHub Release remains separate from pushing source and running CI.
