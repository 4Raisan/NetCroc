<p align="center">
  <img src="assets/netcroc-banner.svg" alt="NetCroc — Your quiet network companion." width="760">
</p>

[Logo SVG](assets/netcroc.svg) · [Logo PNG](assets/netcroc.png) · [Banner SVG](assets/netcroc-banner.svg) · [Banner PNG](assets/netcroc-banner.png)

# NetCroc

**Your quiet network companion.**

[![Desktop CI](https://github.com/4Raisan/NetCroc/actions/workflows/windows-ci.yml/badge.svg)](https://github.com/4Raisan/NetCroc/actions/workflows/windows-ci.yml)

A desktop app for Windows, macOS and Linux for checking connections, watching download/upload speeds, tracking usage, managing saved Wi-Fi and connecting through your own VPN or tunnel profiles.

## What you can do

| Area | Features |
|---|---|
| Connection checks | HTTP HEAD or ICMP, ISP presets and custom targets, 1/5/10/15/30-second intervals, optional smart intervals and a six-minute OFF/ON comparison. |
| Live traffic | Adapter and per-app download/upload speeds, a live graph and usage bars. Speeds use **bytes per second**: KB/s below 2 MB/s, MB/s from 2 MB/s, and GB/s from 1,024 MB/s. Units use 1,024-based conversion. |
| Usage history | **Last 30 days**, **This month** and **Last month**, app/network breakdowns and CSV export. Keeps 62 days of recorded data. |
| DNS | Benchmark resolvers, explicitly apply a selection, restore the original settings and recover through an independent rollback watchdog. |
| Saved Wi-Fi | View saved networks and passwords when Windows permits, connect, forget and review per-network usage. |
| VPN and tunnels | WireGuard, SSH/TLS and VLESS profiles, encrypted credential storage, connection controls and public-IP checks. |
| Desktop controls | System tray, saved preferences and optional Windows sign-in startup. |

Keep-alive is optional and does not guarantee faster downloads or lower game ping. DNS response times are not bandwidth measurements. NetCroc does not provide ISP package bypass, shared VPN accounts or built-in VPN servers.

## Get started

**Download:** use the runnable packages on the [GitHub Releases page](https://github.com/4Raisan/NetCroc/releases). Cross-platform packages are initially marked **beta** while live network-changing operations receive further hardware testing.

| Platform | Package | Requirements |
|---|---|---|
| Windows x64 | `NetCroc-windows-x64.exe` | Windows 10/11; Python bundled. |
| macOS Apple Silicon | `NetCroc-macos-arm64.zip` | Extract and open `NetCroc.app`; unsigned/unnotarized beta. |
| macOS Intel | `NetCroc-macos-x64.zip` | Extract and open `NetCroc.app`; unsigned/unnotarized beta. |
| Linux x64 | `NetCroc-linux-x64.tar.gz` | Extract and run `./NetCroc`; desktop Linux with glibc 2.35+ (Ubuntu 22.04+). |

macOS may require an explicit Open approval in Privacy & Security for this unsigned beta. Signing/notarization is not supplied by these builds. Linux needs a graphical desktop; the bundled binary does not include optional system networking tools.

**From source:** install Python 3.12–3.14 with Tcl/Tk, then run from the project root:

```powershell
# Windows
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r src/requirements.txt
.\.venv\Scripts\python.exe src/app.py
```

```bash
# macOS / Linux
python3 -m venv .venv
.venv/bin/python -m pip install -r src/requirements.txt
.venv/bin/python src/app.py
```

On Ubuntu, install `python3-venv python3-tk` first. Native profile encryption uses macOS Keychain or a Linux Secret Service keyring; a locked/missing keyring produces an error rather than a plaintext fallback. The app should run as the normal desktop user.

Quit any earlier Fastlane/NetCroc instance from its tray first. Windows retains the compatibility lock; macOS/Linux use an OS file lock to prevent two history recorders. Tray availability depends on the desktop; without a tray, keep the window open.

### Administrator access

Ordinary connection checks, adapter traffic, history, profile import and DNS benchmarking run without elevation. Windows per-app capture, DNS changes, WireGuard service controls and whole-PC routing require administrator access.

On macOS/Linux, DNS and WireGuard operations request native OS authorization (`osascript` / `pkexec`). No administrator passwords are entered into NetCroc. The elevated DNS watchdog starts before settings change. Whole-PC SSH/VLESS routing currently needs a root-launched session; local SOCKS5 does not. A normal user's encrypted profiles remain tied to their keyring, so use local SOCKS5 or WireGuard's operation-level authorization rather than assuming a root account can unlock them.

### Platform features and optional tools

| Feature | Windows | macOS | Linux |
|---|---|---|---|
| HTTP/ICMP, adapter speeds, history/CSV | Native | Native | Native |
| Per-app byte attribution | ETW, administrator | Optional TShark + capture/socket permissions | Optional TShark + capture/socket permissions |
| Saved Wi-Fi | WLAN API | `networksetup`; reveal password through Keychain | NetworkManager `nmcli`; reveal with OS permission |
| DNS settings / recovery | Windows adapter settings | `networksetup`, native authorization | NetworkManager, `pkexec` authorization |
| WireGuard | Official Windows client | `wg-quick`, `wg`, `wireguard-go` | `wg-quick`, `wg`; DNS may need `resolvconf` |
| SSH/TLS local SOCKS5 | Included | Included | Included |
| VLESS local SOCKS5 | Verified optional sing-box | Verified native sing-box | Verified native sing-box |
| Whole-PC SSH/VLESS | Administrator | Root session; additional live validation pending | Root session; additional live validation pending |
| Sign-in startup | Registry entry | LaunchAgent | XDG autostart entry |

TShark attribution captures metadata on one default interface, excludes local destinations and omits unresolved/ambiguous sockets. Short-lived connections, shared UDP sockets and capture loss can make per-app totals incomplete; adapter totals remain independent. Wi-Fi passwords on macOS/Linux are revealed only after an explicit click, never during startup.

Run network-changing tests while you can recover locally. Importing a profile never connects it. No macOS/Linux live DNS/Wi-Fi/VPN mutation is certified by hosted CI.

## Usage periods

| Selection | Time range |
|---|---|
| Last 30 days | The current moment back exactly 30 days. |
| This month | The first day of this month at midnight through now. |
| Last month | The complete previous calendar month. |

Recording happens while NetCroc is running. Missing time cannot be reconstructed, and the app's counters are not an ISP billing statement. Older daily records are preserved without inventing their time of day. See [validation notes](docs/STUDY-AND-TESTS.md) for the measurement limits.

## VPN and tunnel setup

| Mode | Prerequisite | Setup |
|---|---|---|
| WireGuard | Official Windows client or POSIX WireGuard tools, and your own `.conf` | [Free-account setup and tested behaviour](docs/FREE-VPN-SETUP.md) |
| SSH / SSH over TLS | Your own server account; optional verified routing core for whole-PC TCP | [SSH/TLS guide](docs/SSH-TLS.md) |
| VLESS / REALITY | Compatible provider/server account and the optional verified sing-box core | [VLESS guide](docs/VLESS.md) |

VLESS supports TCP, WebSocket, gRPC and HTTPUpgrade, plus REALITY and Vision. It uses sing-box; NetCroc does not install an Xray server or 3x-ui panel. Local SOCKS5 affects only apps configured to use it. Whole-PC routing needs elevation. SSH whole-PC mode carries TCP and tunneled DNS; other UDP/ICMP is blocked.

WireGuard profiles are encrypted for your OS account (Windows DPAPI or an AES-GCM key in the OS keyring). On Windows, connecting creates a named service and machine-encrypted runtime configuration accessible to Administrators and Local System. POSIX wg-quick uses a root-owned mode-0600 plaintext runtime file inside a mode-0700 folder in `/run/netcroc` or `/var/run/netcroc`; it is removed on a successful disconnect and retained if needed for recovery. Script hooks and unsupported profile extensions are rejected. Original imported files remain untouched and can contain private credentials: keep them out of Git.

**Closing NetCroc stops SSH/VLESS sessions, but leaves an active WireGuard tunnel running.** Use Disconnect in the VPN tab to remove the tunnel and its runtime configuration. Windows WireGuard services use manual startup. NetCroc does not add a persistent kill switch.

Save a baseline IP before connecting and check it afterward. A changed IP alone does not establish DNS/IPv6 leak protection or different ISP charging. Automatic server provisioning and a built-in Singapore VPN are not implemented.

## Project structure

The root stays small: **six maintained folders**, two generated local folders and this README/configuration.

```text
NetCroc/
├── src/                 Application entry point, dependencies and Python package
│   ├── app.py
│   ├── requirements.txt
│   └── netcroc/         UI, monitoring, storage and Windows/POSIX backends
├── tests/               Automated tests; synthetic credentials and local fixtures
├── tools/               Build/check scripts and opt-in live test utilities
├── docs/                Setup guides, research and dated validation notes
├── assets/              Current icon/diagram and local logo concept galleries
├── .github/workflows/   Windows CI
├── releases/            Local EXE/launcher; ignored by Git
├── test-artifacts/      Local test reports/downloads; ignored by Git
├── .gitignore
└── README.md
```

`netcroc/platforms.py` contains OS helpers; `posix_network.py` contains macOS/Linux networking backends. Start reading the code at `src/app.py`, then `src/netcroc/ui.py` and `dashboard.py`. The [structure guide](docs/STRUCTURE.md) maps the remaining modules and explains the tools. Logo explorations are drafts, not the installed app icon.

## Develop and verify

Use the virtual environment created above:

```powershell
.\.venv\Scripts\python.exe tools/release.py --check
# Optional verified core download; enables native VLESS loopback tests.
# This checks configuration without changing routes or DNS.
.\.venv\Scripts\python.exe tools/check_ssh_routing.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
```

Build and verify a native runnable package on its target operating system (PyInstaller is not a cross-compiler):

```powershell
# Windows
.\.venv\Scripts\python.exe -m pip install PyInstaller==6.22.3
.\.venv\Scripts\python.exe tools/package_release.py
```

```bash
# macOS / Linux
.venv/bin/python -m pip install PyInstaller==6.22.3
.venv/bin/python tools/package_release.py
```

Verified runnable packages are written to `test-artifacts/packages/`. Each build checks bundled Python source and launches read-only GUI/DNS helper diagnostics before packaging. The Windows-only `tools/release.py --build` remains available for the local EXE workflow.

[Desktop CI](https://github.com/4Raisan/NetCroc/actions/workflows/windows-ci.yml) tests Windows Python 3.12/3.13/3.14, Ubuntu x64, macOS Apple Silicon and macOS Intel. Platform-specific API tests run on their native OS; portable backends have separate mocked-command and child-crash tests. Linux GUI checks use Xvfb.

A separate native build matrix creates four runnable packages. Publishing is an explicit manual dispatch and runs only after all tests and package verification pass. Only the publish job has repository write permission. No live DNS/Wi-Fi changes or provider credentials run in CI, and no source archives are uploaded as release assets (GitHub supplies its own automatic source links).

### Verification status

The 26 October 2026 validation recorded **131 passing local tests** and successful GitHub CI for the published implementation. Controlled live tests covered administrator traffic capture, DNS apply/restore, failure rollback and the real 90-second crash watchdog. A Proton Free WireGuard profile changed the observed exit from Sri Lanka to the Netherlands; native IPv6/UDP checks and a separate browser DNS test also succeeded. These are bounded observations, not universal provider or leak certification.

Still incomplete: reliable switching between two internet-connected Wi-Fi networks, Windows 10 compatibility, sleep/resume recovery, longer stability testing, ISP charging checks and leak testing on a native IPv6 access network. The 24-hour observation completed on 27 October but failed its coverage threshold: about 18.7 hours were sampled, with three sampling gaps and no database-read errors. Sleep/suspension gaps remain unknown time, not zero usage.

See [test evidence and limits](docs/STUDY-AND-TESTS.md), [network research](docs/NETWORK-RESEARCH.md) and [VPN research](docs/VPN-RESEARCH.md).

## Local data and compatibility

Windows installs use `%LOCALAPPDATA%\NetCroc`; macOS uses `~/Library/Application Support/NetCroc`; Linux uses `$XDG_DATA_HOME/netcroc` (default `~/.local/share/netcroc`). On Windows, if `%LOCALAPPDATA%\ConnectionTrayPreview` exists, NetCroc continues using it to preserve settings, history and pending DNS recovery. Wi-Fi passwords are not stored in the usage database.

The legacy instance-lock identifier also remains intentional. Saving the sign-in preference replaces the old startup entry with `NetCroc`; until then, an old entry may still point to the previous executable. Reorganizing documentation does not migrate local data or change startup/network settings.
