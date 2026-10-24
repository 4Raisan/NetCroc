# SSH / TLS setup

Implemented 26 October 2026. These connections use your own server/provider account; NetCroc does not supply free servers or create accounts.

1. Open SSH / TLS, then New. Enter the issued server, port, username and password. Account expiry is optional; record the actual issued expiry, not a general marketing claim.
2. Enable TLS when the provider runs SSH inside TLS/STUNNEL. Enter the provider's SNI if needed. TLS 1.2 or newer is required; obsolete SSL protocols are not supported.
3. Use Probe verified server. Compare its SSH fingerprint with a trusted provider source before accepting it. For a self-signed certificate, import its trusted CA, or use Inspect identity to inspect without authenticating, independently verify both fingerprints, and explicitly pin them. Certificate/key mismatches stop login.
4. If your server requires an HTTP proxy or HTTP handshake, enter it in Payload and proxy. Empty payloads disable those stages. Order: proxy CONNECT, pre-TLS HTTP handshake, TLS/SNI, post-TLS HTTP handshake, SSH. Custom HTTP stages must return a 2xx or 101 response and finish their headers. This is not support for every proprietary TLS Tunnel export or arbitrary binary handshake.
5. Save. Profiles are encrypted with Windows DPAPI for the current account. Saving/importing never connects. JSON import accepts only documented fields from `DEFAULTS` in `src/netcroc/ssh_tunnel.py`; encrypted third-party exports are unsupported. JSON input files themselves remain plaintext: keep them private.
6. Default Local SOCKS5 listens only on 127.0.0.1, port 1080 (or a chosen/free port). Configure the intended app to use SOCKS5 with remote hostname resolution. Other apps keep their normal connection. Other local processes can access this loopback proxy; do not share an untrusted Windows login session.
7. Optional Whole-PC TCP: download the verified routing core from the tab, check its configuration, restart NetCroc as administrator when on a safe test connection, and explicitly connect. Disconnect other VPNs first. This mode may interrupt remote access. Closing NetCroc stops its SSH session and routing child.

## What whole-PC mode does

The optional engine is official sing-box 1.14.4 for Windows x64. The download is checked against its pinned release archive SHA-256, preserves its LICENSE, and checks the extracted executable before use. It is downloaded separately, not bundled into the NetCroc EXE. Configuration is piped through stdin instead of saved as a credential file. A Windows kill-on-close job owns the routing child before it receives configuration; closing/crashing the parent kills that child. It checks for a live adapter before reporting routing ready. Parent death behavior was exercised on a harmless child process, not a live TUN adapter.

IPv4/IPv6 TCP routes go to the SSH SOCKS proxy; the actual established upstream IP is excluded to avoid a routing loop. DNS uses HTTPS over that proxy. Other UDP/ICMP is rejected because ordinary SSH forwarding is TCP only. Games, QUIC and calls may fall back to TCP or fail. This is not a complete UDP VPN or a tested kill switch: disconnect returns normal connectivity, and process-crash route/DNS cleanup still needs administrator lab validation. Conflicting third-party routing and local-network reachability also require lab testing.

Do not run multiple system-routing VPNs together. The routing preflight refuses a visible WireGuard/NetCrocSSH adapter; arbitrary third-party VPN names cannot be detected reliably. Use the VPN tab's baseline/public-IP comparison to check an actual whole-PC connection; an IP change alone does not prove DNS/IPv6 leak protection. In Local SOCKS5 mode, an ordinary browser/IP check is meaningful only if that browser is explicitly configured to use the proxy.

## ISP packages

A configured SNI is a TLS server-name value. It does not establish authorization, free data, package eligibility or how the ISP bills encrypted traffic. No provider account, ISP-package billing bypass or real charging test was performed. Use only servers and packages you are permitted to use. No free VPS service is bundled or promised.

## Research sources

- [FastSSH guide](https://blog.fastssh.com/vpn-protocol/ssh/how-to-create-a-free-ssh-account/): provider account creation and SSH/STUNNEL distinction.
- [FastSSH STUNNEL servers](https://www.fastssh.com/page/ssh-ssl-stunnel-servers): availability and expiry vary. The index and individual creator page can show different validity periods; use the issued account details.
- [stunnel HOWTO](https://www.stunnel.org/howto.html): TLS wrapping of an existing TCP service.
- [Paramiko transport documentation](https://docs.paramiko.org/en/stable/api/transport.html): SSH transport, authentication and forwarding.
- [sing-box TUN documentation](https://sing-box.sagernet.org/configuration/inbound/tun/): route exclusions and Windows strict routing.
- [Official routing release](https://github.com/SagerNet/sing-box/releases/tag/v1.14.4): pinned engine and license.

The native `sing-box check` test creates no adapter. Full administrator routing, real provider authentication, public IP/leak checks, and ISP accounting remain integration tests requiring an authorized account and safe test network.
