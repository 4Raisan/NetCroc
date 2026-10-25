# NetCroc

Your quiet network companion.

[![Windows CI](https://github.com/4Raisan/NetCroc/actions/workflows/windows-ci.yml/badge.svg)](https://github.com/4Raisan/NetCroc/actions/workflows/windows-ci.yml)

A local Windows desktop app for connection checks, live traffic and usage history. The application now uses the NetCroc name. The source implementation is included. Standalone executables are built locally; no downloadable GitHub release has been published yet.

## Run

If you have a local build, open `releases/NetCroc.exe`, or run `python src/app.py` after installing `src/requirements.txt`. Python is bundled in the EXE.

Quit the earlier Fastlane app from its tray before opening NetCroc. Both share a compatibility lock, so an already-running copy will be brought forward instead of starting a second recorder.

## Features

- HTTP HEAD or ICMP checks with ISP presets, a custom target and 1/5/10/15/30-second intervals.
- Optional smart intervals, off by default, and a six-minute keep-alive OFF/ON comparison.
- Live adapter and per-application traffic in KB/s, MB/s and GB/s, with a traffic graph and usage bars.
- Usage for the last 30 days, this month and last month; 62-day retention and CSV export.
- DNS benchmarking, explicit administrator DNS apply/restore, and a rollback watchdog.
- Saved Wi-Fi profiles, password display when Windows permits, connect/forget controls and per-network history.
- Tray controls, saved preferences and optional sign-in startup.
- WireGuard profile import with encrypted storage, explicit connect/disconnect, service/handshake status and public IPv4 comparison.
  A user-created free account can supply the profile: [tested free VPN setup](docs/FREE-VPN-SETUP.md).
- SSH and SSH-over-TLS profiles with SNI, certificate/host-key verification, HTTP proxy and before/after-TLS payloads; local SOCKS5 or optional whole-PC TCP routing. See [SSH/TLS setup](docs/SSH-TLS.md).
- Custom VLESS profiles for compatible 3x-ui/Xray servers, with TLS/REALITY, TCP/WebSocket/gRPC/HTTPUpgrade, encrypted storage, local SOCKS5 or whole-PC routing and a proxy public-IP check. See [VLESS setup](docs/VLESS.md).

Keep-alive may help some idle stalls; it does not guarantee higher bandwidth or lower game ping. Comparison results describe response times and failures, not download speed. Per-app capture requires administrator access. WireGuard support requires the official Windows client and a user-supplied account/configuration. SSH whole-PC mode needs the optional routing core and administrator access; other UDP/ICMP is blocked. VLESS uses sing-box, not a bundled Xray executable. ISP billing bypass has not been established.

## Settings and history

New installations use `%LOCALAPPDATA%\NetCroc`. If `%LOCALAPPDATA%\ConnectionTrayPreview` exists, NetCroc continues using it to preserve settings, usage history and DNS recovery state. Nothing is moved or deleted automatically. Wi-Fi passwords are not stored in the usage database.

The compatibility instance lock also retains its old identifier. Saving the sign-in preference replaces the old startup entry with `NetCroc`; until you save it, an existing startup entry still points to the old executable. No startup/DNS/Wi-Fi settings are changed merely by reorganizing this project.

## Project layout

```text
NetCroc/
  src/
    app.py              # Entry point and helper modes
    requirements.txt
    netcroc/            # UI, monitoring, history, Wi-Fi, DNS and research
  tests/                # Automated tests
  tools/                # Build, bundle verification and preview utilities
  assets/               # Icon and architecture image
  docs/                 # Research, validation notes and structure guide
  releases/             # Local executable and launcher; Git-ignored
  test-artifacts/       # Local test evidence; Git-ignored
```

## Develop and verify

```powershell
python -m pip install -r src/requirements.txt
python -m unittest discover -s tests -p "test_*.py"
python tools/release.py --check
python tools/verify_bundle.py releases/NetCroc.exe
python tools/smoke_frozen.py releases/NetCroc.exe
```

A full standalone build requires PyInstaller 6.22.3:

```powershell
python -m pip install PyInstaller==6.22.3
python tools/release.py --build
```

`tools/refresh_bundle.py` is an optional maintainer shortcut requiring a previously verified compatible bundle at `test-artifacts/packaging-base.exe`. It refuses new dependencies and verifies bundled Python and native payloads. A clean checkout should use the full build command.

## Validation limits

Real administrator traffic capture, DNS mutation/rollback, Wi-Fi switching and a real provider VPN handshake still require controlled live verification. Long-term history retention has been tested with simulated dates. No live Hutch speed increase is established by these checks.

See [structure and compatibility notes](docs/STRUCTURE.md), [network research](docs/NETWORK-RESEARCH.md), [VPN research](docs/VPN-RESEARCH.md) and [validation history](docs/STUDY-AND-TESTS.md).

## Continuous integration

[Windows CI](https://github.com/4Raisan/NetCroc/actions/workflows/windows-ci.yml) runs on pushes to `main`, pull requests and manual dispatch. It checks pinned dependencies, source syntax, assets, README links and the Windows test suite on Python 3.12, 3.13 and 3.14. After the tests pass, a separate Windows job builds the standalone EXE, verifies its bundled code and checks the packaged UI and read-only DNS helper modes.

The workflow uses read-only repository permissions and actions pinned to commit hashes. It does not publish a release, apply DNS settings or switch Wi-Fi. CI mocks and temporary-runner checks do not replace controlled live administrator tests on users' PCs.

## WireGuard VPN

Open the **VPN** tab, install the [official WireGuard Windows client](https://www.wireguard.com/install/) and import your own `.conf` file. Provider links are available in the tab. Importing does not require elevation and does not alter routes or DNS. **Refresh status** reloads saved profiles.

Connecting or disconnecting requires NetCroc to run as administrator and an explicit confirmation. A VPN can interrupt remote access; do this at the PC. Connect creates a named WireGuard tunnel service; Disconnect removes that service and its encrypted runtime configuration. Closing NetCroc leaves a running tunnel active. NetCroc configures its service for manual startup so it does not automatically reconnect at reboot.

Imported profiles are encrypted with per-user Windows DPAPI. The original downloaded `.conf` remains untouched and contains credentials. At connect time, a separate machine-DPAPI service configuration is written under `%ProgramFiles%\NetCrocServiceData\WireGuard` with access restricted to Administrators and Local System. No plaintext service configuration is written. Script hooks and unsupported extensions are rejected. Only standard WireGuard client options are supported; DNS entries must be IP addresses.

Service status and handshake age are separate. **Save current IP as baseline** before connecting, then **Check public IP** afterward. These optional checks use ipify and keep the baseline only in memory. A changed public IPv4 is not proof of DNS/IPv6 leak protection, correct per-app routing or different ISP charging. NetCroc provides no additional automatic kill switch; behaviour depends on the WireGuard configuration/client.

Provider configurations:

| Provider | Account | Official guide |
|---|---|---|
| Proton VPN | Free or paid | [Generate WireGuard configuration](https://protonvpn.com/support/wireguard-configurations) |
| Mullvad | Paid | [Windows WireGuard guide](https://mullvad.net/en/help/wireguard-app-windows) |
| IVPN | Paid | [Windows WireGuard guide](https://www.ivpn.net/setup/windows-10-wireguard/) |
| Windscribe | Pro or Build-A-Plan | [Configuration access](https://windscribe.com/knowledge-base/articles/where-do-i-access-my-wireguard-configs) |

A provider account and usable server configuration are required. NetCroc does not supply shared keys, accounts or free VPN servers.
