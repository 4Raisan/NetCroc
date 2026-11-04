# NetCroc 0.4.7

- VPN, SSH/TLS and VLESS pages show required-tool status and direct setup actions.
- WireGuard installation and provider-profile creation are separate, clearly labelled steps.
- Main window and setup/error popups center within the monitor work area.
- Sandbox Wi-Fi limitations appear on the Wi-Fi page instead of interrupting Home.
- Errors use plain-language explanations, next steps and expandable technical details.
- Windows uses a single versioned EXE; Linux/macOS packages include user-local installation scripts.
- README reorganized with a visible architecture diagram and concise source/setup guidance.
- Fixed previous CI failures caused by platform test isolation and missing-client guard ordering.

Windows and Linux local checks and native GitHub Actions checks are reported with the release. Headless/macOS CI is not physical hardware coverage: macOS network-changing operations remain experimental; ISP billing and provider connectivity require real-network checks. macOS packages are ad-hoc signed and not notarized by Apple.
