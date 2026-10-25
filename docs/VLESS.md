# VLESS profiles

Open the VLESS tab and download the optional verified core once. NetCroc uses sing-box to connect to compatible VLESS servers; it does not install or run an Xray server or 3x-ui panel.

Use New to enter your provider's server, UUID, SNI, TLS or REALITY settings, transport and routing mode. Alternatively, save one provider-issued `vless://` link in a private text file and use Import file. NetCroc VLESS JSON is also supported. UUIDs and link files are credentials: don't publish them. Imported profiles are encrypted for the current Windows account. Original input files remain unchanged and may contain plaintext credentials.

Supported transports are TCP, WebSocket, gRPC and HTTPUpgrade. TLS validates the certificate and server name; a trusted custom CA PEM can be imported for private servers. There is no skip-certificate-verification switch. REALITY accepts the provider public key, short ID, SNI and TLS fingerprint; Vision requires TCP. Unencrypted VLESS is allowed only with literal loopback test servers. Unsupported link parameters, duplicate parameters, subscriptions, VMess, Trojan, XHTTP, arbitrary Xray JSON and third-party encrypted exports are rejected rather than silently misinterpreted.

Local SOCKS5 binds only 127.0.0.1, default port 1081. Configure the desired app to use it with remote DNS. A local listener is not proof of successful upstream authentication: click Check public IP through proxy to make a certificate-verified HTTPS request to api.ipify.org through that specific proxy. In whole-PC mode, use the existing VPN tab's public-IP check. Compare with a baseline before connecting. Neither test alone establishes DNS/IPv6 leak protection or a foreign location.

Whole-PC mode requires administrator access, resolves the provider server before changing routes, excludes its resolved addresses, tunnels DNS over HTTPS, and sends TCP/UDP through VLESS. ICMP is rejected; actual UDP availability depends on the server. Other VPNs must be disconnected first. The routing process is assigned to a Windows kill-on-close job before receiving its configuration. Closing NetCroc stops VLESS. Disconnect restores ordinary connectivity; this is not a persistent kill switch.

The local lab validates real TLS-protected forwarding over TCP, WebSocket, gRPC and HTTPUpgrade with synthetic accounts and local servers, including invalid-UUID rejection. REALITY and REALITY+Vision also pass real local handshakes, with rejection of invalid UUIDs, public keys and short IDs. The lab's REALITY server must set its intended server name; schema acceptance alone did not reveal that fixture requirement. These tests do not establish compatibility with every commercial provider. No public/free VPS, provider account, foreign exit, or ISP billing bypass is bundled.

Primary protocol references: [VLESS outbound](https://sing-box.sagernet.org/configuration/outbound/vless/), [TLS/REALITY](https://sing-box.sagernet.org/configuration/shared/tls/), [V2Ray transports](https://sing-box.sagernet.org/configuration/shared/v2ray-transport/).

## macOS / Linux whole-PC routing

Run the GUI as your normal desktop user. A connect action requests native OS authorization and starts an independent privileged worker; the GUI retains access to its own OS keyring. The worker receives validated settings over a private control request and stdin, never command-line credentials. It monitors the GUI's PID, creation time and owner, and tears down routing when the GUI exits or crashes. Disconnect uses the existing private transaction and does not prompt again. Private recovery state is retained if cleanup cannot be confirmed.

Linux real TUN forwarding and crash cleanup pass inside an isolated network namespace with synthetic accounts and no external network. Physical macOS routing, provider authentication, DNS/IPv6 leak behaviour and sleep/resume recovery still need live tests. macOS can have pre-existing system utun interfaces; their mere presence is not treated as proof of an active conflicting VPN.
