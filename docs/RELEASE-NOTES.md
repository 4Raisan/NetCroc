# NetCroc cross-platform beta

Runnable desktop packages for Windows x64, Linux x64 (glibc 2.35+), macOS Apple Silicon and macOS Intel. Each asset is built on its native platform and must pass automated tests, bundled-source verification and read-only frozen GUI/helper checks before publication.

- Portable connection checks, adapter rates, history, CSV export, startup and single-instance handling.
- Native macOS/Linux Wi-Fi and DNS backends; explicit password reveal and network-changing actions.
- OS-keyring-backed profile encryption on macOS/Linux; no plaintext-key fallback.
- POSIX WireGuard controls through native authorization, and verified native sing-box downloads for local SOCKS5 / optional root-session routing.
- Optional TShark metadata attribution with documented incomplete-socket/capture limits.
- Windows ETW, DPAPI, DNS watchdog and tunnel service support retained.

**Beta limits:** macOS packages are unsigned and not notarized. Ubuntu-style NetworkManager desktops are the Linux networking target; other network managers need separate support. Optional WireGuard/TShark/system tools are not bundled. Linux/macOS real network mutation, provider credentials, sleep/resume and per-app capture require hardware validation; hosted tests do not establish full feature parity. Whole-PC POSIX SSH/VLESS needs a root session and has not been certified with normal-user keyring profiles. A ready listener does not prove provider authentication. NetCroc operates no VPN servers and does not provide ISP package bypass.

Only runnable EXE/app/binary packages are uploaded. GitHub's automatic source links remain part of GitHub Releases.

Intel macOS pins cryptography 48.0.1 to its universal2 wheel. CI refuses source-only cryptography installs to avoid mixing host OpenSSL libraries into the frozen app. Other platforms retain their compatible provider dependency resolution.
