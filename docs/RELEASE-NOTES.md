# NetCroc cross-platform beta

Runnable desktop packages for Windows x64, Linux x64 (glibc 2.35+), macOS Apple Silicon and macOS Intel. Each asset is built on its native platform and must pass automated tests, bundled-source verification and read-only frozen GUI/helper checks before publication.

- Portable connection checks, adapter rates, history, CSV export, startup and single-instance handling.
- Native macOS/Linux Wi-Fi and DNS backends; explicit password reveal and network-changing actions.
- OS-keyring-backed profile encryption on macOS/Linux; no plaintext-key fallback.
- POSIX WireGuard controls through native authorization, and verified native sing-box downloads for local SOCKS5 / supervised privileged routing.
- Optional TShark metadata attribution with documented incomplete-socket/capture limits.
- Windows ETW, DPAPI, DNS watchdog and tunnel service support retained.

**Beta limits:** macOS packages are ad-hoc signed and signature-verified, but have no Developer ID signature or Apple notarization. Ubuntu-style NetworkManager desktops are the Linux networking target; other network managers need separate support. Optional WireGuard/TShark/system tools are not bundled. Physical Linux/macOS DNS/Wi-Fi/provider behaviour, sleep/resume and per-app capture still need hardware validation; hosted tests do not establish full feature parity. Whole-PC POSIX SSH/VLESS now uses native authorization and a separate supervised worker while the GUI keeps normal-user keyring access. A real Linux network-namespace lab validates TUN forwarding and crash cleanup without external network access. macOS TUN control has unit coverage and still needs live validation. A ready listener does not prove provider authentication. NetCroc operates no VPN servers and does not provide ISP package bypass.

Only runnable EXE/app/binary packages are uploaded. GitHub's automatic source links remain part of GitHub Releases.

Intel macOS pins cryptography 48.0.1 to its universal2 wheel. CI refuses source-only cryptography installs to avoid mixing host OpenSSL libraries into the frozen app. Other platforms retain their compatible provider dependency resolution.

## Beta 2 recovery improvements

- Native authorization for POSIX SSH/VLESS whole-PC routing; no root-launched GUI or second disconnect prompt.
- Parent identity, private control files, transaction tokens, adapter-readiness checks and independent process cleanup.
- Real isolated Linux SSH/VLESS TUN data, disconnect and parent-crash cleanup lab added to CI.
- Linux history displays connection names while UUIDs protect transitional/active profiles from deletion.
- Capture workers stop if metadata/socket inspection fails.
- Awake-time observation with detailed sampling-gap records and bounded keep-awake support. The earlier incomplete long test is not relabelled passed.
- macOS package signatures checked separately from notarization; no Developer ID credentials are included.
