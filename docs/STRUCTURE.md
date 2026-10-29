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
| `netcroc/app_names.py` | Friendly application labels, byte-preserving groups and unresolved identity handling. |
| `netcroc/desktop.py` | Local desktop preferences, monitor geometry and custom window controls. |
| `netcroc/tray_mode.py` | Optional edge/static overlays and best-effort tunnel/exit observations. |
| `netcroc/shell.py` | Direct sidebar navigation, Home overview and network tool links. |
| `netcroc/about.py` | About panel and the non-blocking release summary shown in the sidebar. |
| `netcroc/updates.py` | GitHub release-list check and version ordering; never downloads or installs. |
| `netcroc/prerequisites.py` | Read-only inspection of optional WireGuard and the verified routing core. |
| `netcroc/setup_ui.py` | Setup and repair dialog; installation stays user initiated. |
| `netcroc/tool_ui.py` | Shared primary-action bar and More menu used by the tool tabs. |
| `netcroc/dashboard.py` | Traffic, history, DNS, Wi-Fi, research and VPN tabs; shared monitoring loop. |
| `netcroc/isp.py` | Bounded HTTPS ISP lookup and recognized provider mapping; manual fallback. |
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

## Knowledge graph

A [graphify](https://pypi.org/project/graphifyy/) knowledge graph indexes `src/`, `tests/`, `tools/` and the Markdown in `docs/` and `README.md` for navigation and refactor impact analysis. Extraction is local AST plus Markdown headings: no source is sent to an LLM and no API key is used. A healthy build is roughly 1,072 nodes, 2,676 edges and 50 named communities.

```powershell
python -m graphify update .          # incremental re-extract after code changes
python -m graphify affected "History" --depth 2   # what a change would break
python -m graphify god-nodes --top 15             # architectural hubs
python -m graphify query "how does DNS rollback work" --context call
```

`affected` is the useful one before a refactor: it lists the production call sites and the exact test cases that reach a symbol, so you know which tests to run. Ambiguous labels are refused rather than guessed — `Traffic`, `Session`, `ProfileStore` and `crypt()` each exist in more than one module, so pass the node id (for example `src_netcroc_traffic_traffic`) or a file path.

Outputs live in `graphify-out/`: `graph.html` (interactive), `graph.json` (queryable), `GRAPH_REPORT.md` (audit). Generated artifacts are gitignored; the hand-curated community names in `.graphify_labels.json` are tracked so they survive a clean checkout and are reused without any LLM call. `.graphifyignore` keeps `assets/`, `releases/`, `test-artifacts/` and credential files out of the corpus.

Post-commit, post-checkout, post-merge and post-rewrite hooks rebuild the graph in the background (`graphify hook status`, `graphify hook uninstall`). Two verified limits: `from netcroc import vpn` and `from . import dns` resolve to `__init__.py` rather than the target module, so the graph under-reports coupling for package-level imports — 12 test-to-module edges at the time of writing — and `graph.html` loads its vis-network renderer from a CDN, so it needs internet access to draw.

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
