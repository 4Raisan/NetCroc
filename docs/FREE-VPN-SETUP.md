# Use your own free WireGuard account

NetCroc does not operate VPN servers. A free third-party account can supply a standard profile for its VPN tab. Provider availability, terms and limits can change.

On 26 October 2026, a user-created Proton VPN Free account was used to validate this path:

1. Create or sign into the free account in the browser. Enter credentials and verification codes there, not in a chat or repository.
2. Open Downloads → WireGuard configuration. Choose Windows and a free server. Give the device a recognizable name and create/download the profile. This creates an account access key; keep the downloaded file private.
3. Import the `.conf` in NetCroc's VPN tab. NetCroc encrypts its copy for the Windows account; the original downloaded file stays unchanged.
4. Save a baseline public IP, run NetCroc as administrator, and explicitly connect. Check handshake and public IP again. An IP lookup describes the observed exit, not necessarily physical server location.
5. Disconnect to return to the original network. Do not combine simultaneous system-routing tunnels.

The tested free Netherlands profile completed a real WireGuard handshake, changed the observed country from LK to NL, supplied working IPv6, and returned the VPN IPv4 address in a Cloudflare UDP/STUN check. Cleanup removed the service and temporary encrypted service file and restored the baseline IPv4/DNS. The ordinary connection had no working native IPv6, so this does not prove protection on every IPv6-capable access network. The separate BrowserLeaks DNS audit matched the browser IP to the VPN IP and found eight Netherlands DNS servers, with no baseline Dialog ISP resolver observed. No ISP DNS leak was observed in that bounded test; this is not exhaustive leak certification.

The user's profile and keys are not included in this repository. Only a private encrypted copy is stored in the app's local data directory. No subscription or VPS was purchased, and no ISP-package billing bypass was established.

Primary sources: [Proton WireGuard configuration guide](https://protonvpn.com/support/wireguard-configurations), [Proton Free](https://protonvpn.com/free-vpn), [Cloudflare public STUN service](https://developers.cloudflare.com/realtime/sfu/get-started/connection-patterns/), [IPinfo public API](https://support.ipinfo.io/hc/en-us/articles/30792479436562-What-Is-the-Difference-Between-Using-the-Authenticated-Free-Plan-and-the-Public-API-With-No-Account).
