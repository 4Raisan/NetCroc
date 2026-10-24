# NetCroc

Your quiet network companion.

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

Keep-alive may help some idle stalls; it does not guarantee higher bandwidth or lower game ping. Comparison results describe response times and failures, not download speed. Per-app capture requires administrator access. VPN support is not implemented.

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

Real administrator traffic capture, DNS mutation/rollback and Wi-Fi switching still require controlled live verification. Long-term history retention has been tested with simulated dates. No live Hutch speed increase is established by these checks.

See [structure and compatibility notes](docs/STRUCTURE.md), [network research](docs/NETWORK-RESEARCH.md), [VPN research](docs/VPN-RESEARCH.md) and [validation history](docs/STUDY-AND-TESTS.md).
