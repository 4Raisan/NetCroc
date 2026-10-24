# NetCroc: free VPN/VPS research and custom profile design

Client research date: 25 October 2026. Scope: primary-source research and two read-only public-IP checks from the PC. No VPN was installed, connected, disconnected or reconfigured; DNS and Wi-Fi settings were not changed. No cloud account/server was created. The current NetCroc application has not gained VPN support in this research turn.

## What was actually verified

Both `api.ipify.org` and `ipinfo.io/json` answered HTTPS requests from the PC and returned the same public IPv4. IPinfo identified country LK and network AS18001, Dialog Axiata PLC. The exact address is intentionally omitted from this report. This is the HTTP egress observed by those requests, which can be affected by existing proxy settings; it is not proof that every PC application has the same route.

No supplied VPN profile/server was available for a before/after tunnel test. Therefore tunnel connectivity, VPN throughput, selected-country correctness, leak protection, streaming access and package charging are **not verified**. NetCroc appearing in the running-process list is not a VPN: the current build contains no tunnel engine. A browser page fetched by the research web tool sees that tool's network, not necessarily the PC's; its displayed IP was not used as PC evidence.

Primary checker sources: [ipify API](https://www.ipify.org/), [IPinfo](https://ipinfo.io/), [BrowserLeaks IP](https://browserleaks.com/ip), [BrowserLeaks DNS](https://browserleaks.com/dns).

## The ISP classification issue

The relevant names are zero-rating bypass, app-specific package bypass and traffic misclassification. TCP/UDP are transports, VLESS is a proxy protocol, and TLS/SNI are connection-security/hostname mechanisms. None of those names establishes which allowance an ISP will charge.

The friend's screenshots show a TLS Tunnel client with a Zoom SNI field and a different VLESS/TCP/TLS profile. They do not establish the server identity, certificate validity, active routing, current expiry date or billing classification. Setting an unrelated hostname alone does not make an ordinary authenticated TLS connection valid for that hostname. A profile requiring disabled certificate validation should not be described as a secure configuration. [Xray TLS configuration example with certificate verification enabled](https://github.com/XTLS/Xray-examples/blob/main/VLESS-WSS-Nginx/client.jsonc)

No working Dialog, SLT/Mobitel, Airtel or Hutch package loophole was verified. The official Dialog Work & Learn Plus page explicitly excludes both Netflix and tunneling/VPN. This is evidence of intended package scope, not proof that every classifier is implemented perfectly. [Dialog package notes](https://dialog.lk/home-broadband/postpaid/addon/work--learn-plus?id=191&language=en)

An IP change can establish changed egress for the tested request. It cannot establish free data or a package allowance deduction. That requires the user's exact carrier/plan and its own before/after quota/billing records, accounting for reporting delays and other device/background traffic. PC byte totals are a separate measurement. No such billing experiment was performed.

## Free VPS candidates

| Provider | Offer verified in official material | Suitability for NetCroc |
|---|---|---|
| Oracle OCI Always Free | Eligible compute in the account's home region; published free outbound allowance up to 10 TB/month. Capacity may be unavailable and idle compute can be reclaimed. | Best candidate to investigate for an individually owned, longer-term server. Not a guaranteed free server, global country pool or measured fastest option. |
| AWS | New users receive $100 initial credit and can earn up to $200 total; Free plan up to six months. | Good temporary development lab. Not indefinite free VPN hosting. Instance, IPv4, disk and egress limits must be checked separately. |
| Google Cloud | Eligible e2-micro usage in three US regions, 30 GB-month standard disk and 1 GB/month eligible VM outbound transfer. | Useful tiny test VM; unattractive for streaming/tunneling traffic to Sri Lanka. Free VM time does not make a whole network deployment free. |
| Azure | Eligible new-user $200 credit for 30 days, plus time/quantity-limited free services. | Another temporary lab, not an assumption of permanent free global VPN hosting. |

Sources: [Oracle free offering](https://www.oracle.com/cloud/free/), [Oracle compute restrictions](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm), [AWS Free Tier](https://aws.amazon.com/free/free-tier-faqs/), [Google free compute](https://docs.cloud.google.com/free/docs/free-cloud-features#compute), [Azure free-account limits](https://learn.microsoft.com/en-us/azure/cost-management-billing/manage/avoid-charges-free-account).

Oracle's currently retrieved compute page lists 2 OCPUs/12 GB total for free A1 allocation; older tutorials may quote different amounts. Its AMD E2 micro page states up to 50 Mbps public internet bandwidth (about 6 MB/s, before overhead). A1 shape bandwidth scales with allocation; a shape's advertised maximum is not a measured sustained VPN rate. These are reasons to verify the account console rather than promise a fixed free speed. Free compute must be in the home region, not one free machine in every country. [Oracle limits and shape details](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)

Inference for Sri Lankan users: include nearby available India/Singapore regions in a real latency/throughput comparison. Geography is only a starting point; ISP routing, actual server location, shared capacity and protocol overhead determine results. No regional speed ranking was measured here.

## Free VPN services: different from a VPS

| Service | Free allowance / locations | Main limitation and NetCroc fit |
|---|---|---|
| Proton VPN | Unlimited data; official free-app list includes 10 countries, including Singapore and Japan. | App chooses a server; changes are randomized with cooldowns. Official WireGuard configuration downloads support free accounts, making user-owned profile import worth investigating. This does not establish arbitrary country entitlement or shared-account redistribution rights. |
| Windscribe | 10 GB/month with confirmed email, otherwise 2 GB. Support page says 11 countries; another official Windows page says 10. | Treat the current account's free location list as authoritative. Custom config generation is described with paid plans; free app access does not imply free embeddable profiles. |
| PrivadoVPN | 10 GB/month high-speed allowance, limited free locations. | Official pages show differing country lists; use the live free account list. Suitable for an occasional-use comparison, not unlimited throughput. |
| hide.me | Advertises unlimited free data; support page advertises eight free locations. | Do not confuse locations with countries. Third-party OpenVPN configuration downloads require a paid plan according to its support page. |
| Cloudflare WARP | Free client offering; replaces the visible source IP with a Cloudflare address representing the approximate location. | A connectivity/privacy candidate, not a selectable-country VPN network. Do not present it as a free country-unblocking menu. |
| VPN Gate | Free community/academic relays, no registration required; changing public relay availability. | Country, uptime and speed vary. The project retains connection logs for at least three months. Not my default privacy/stability choice for NetCroc. |

Sources: [Proton free server selection](https://protonvpn.com/support/change-server-free-plan), [Proton WireGuard downloads](https://protonvpn.com/support/wireguard-configurations), [Windscribe plans](https://windscribe.com/knowledge-base/articles/how-much-does-it-cost-to-use-windscribe), [Windscribe Windows](https://windscribe.com/features/windows), [Privado free plan](https://www.privadovpn.com/freevpn/), [Privado pricing](https://privadovpn.com/pricing/), [hide.me free plan](https://hide.me/en/pricing), [hide.me location/config restrictions](https://hide.me/en/help/how-to-change-hide-me-vpn-server-location/), [WARP IP behavior](https://developers.cloudflare.com/warp-client/known-issues-and-faq/), [VPN Gate overview](https://www.vpngate.net/en/about_overview.aspx), [VPN Gate logging](https://www.vpngate.net/en/about_abuse.aspx).

Recommendations are a shortlist by product fit, not measured speed awards: Proton for unlimited free use; Windscribe for a limited-data country-selection trial; Oracle for investigating one's own server; a user's exported Proton WireGuard profile for investigating integration without hosting a VPS. No reviewed offer establishes unrestricted, fast, free service across a large global network. A provider's public country count or server-port bandwidth does not establish the user's achievable speed or security strength.

## VPN/proxy platforms to consider

| Platform | Proposed role | Important boundary |
|---|---|---|
| WireGuard | Standard full-device VPN option, compatible user-owned `.conf` profiles. | Needs a real compatible server/provider and correct routing/DNS. Not a package-bypass feature. |
| Xray-core | Closest fit for VLESS-style custom profiles like the screenshot. | Supports configurable transports/security; no guaranteed ISP billing effect. Certificate validation must remain on for ordinary TLS. |
| sing-box | Candidate unified backend for multiple proxy protocols, DNS and routing. | Broad configuration support adds integration and licensing work. WireGuard uses its current endpoint configuration, not an assumed old outbound schema. |
| OpenVPN | Compatibility option for `.ovpn` profiles from providers and existing deployments. | Profile import and scripts need careful validation; speed should be benchmarked, not assumed equivalent to WireGuard. |
| Outline | Simpler self-hosted access-key model for small groups. | Requires hosting; not a universal importer for VLESS or proprietary TLS Tunnel exports. |

Primary projects: [WireGuard](https://www.wireguard.com/), [Xray-core](https://github.com/XTLS/Xray-core), [sing-box](https://github.com/SagerNet/sing-box), [sing-box WireGuard endpoint](https://sing-box.sagernet.org/configuration/endpoint/wireguard/), [OpenVPN community](https://openvpn.net/community/), [Outline](https://getoutline.org/). Free software licensing is separate from free server capacity or redistribution rights. Review the selected core's exact current license before distribution.

## Proposed custom setup in NetCroc

Yes: users can own separate named connection profiles. Recommended initial categories are Standard VPN (WireGuard/OpenVPN) and Custom proxy tunnel (VLESS/VMess/Trojan/Shadowsocks where supported by the chosen core). These are user labels and configurations, not different sources of free internet.

Support importing a profile or manually entering server address, port, protocol, relevant authentication, transport, TLS server name, and supported transport-specific settings. Store credentials with Windows protection; mask them in logs/exports. Ordinary TLS should verify certificates and server identity. A browser-like fingerprint alone is not authentication. Do not silently connect two whole-PC routing engines at once.

The VLESS screenshot can inform a VLESS configuration editor. A TLS Tunnel/NetMod proprietary export or payload feature is not automatically interchangeable with an Xray/sing-box profile; its format and semantics require separate inspection. No promise is made to import an unidentified encrypted profile format.

Each profile should have: Validate, Connect, Disconnect, Check IP, and a clear routing scope (whole PC or selected proxy-aware apps). The active tunnel's DNS policy should take precedence over the unrelated DNS optimiser. Preserve original routes/DNS and provide disconnect/crash recovery before adding automatic connect. A user-owned VPS belongs to that user's account; a publicly distributed free server fleet would require separately funded bandwidth, account eligibility, provider permission and operations. Do not bundle shared commercial VPN credentials or scraped public connection keys.

## Verification before displaying “VPN working”

1. Read the existing route and DNS configuration without changing it, then obtain a baseline public IPv4/IPv6 through two independent services.
2. After the user explicitly connects a supplied profile, run the same checks through that profile's intended route. For a local SOCKS/HTTP proxy, checking the default Python/browser route is insufficient unless it is deliberately routed through the proxy.
3. Compare observed egress with the configured server/provider, inspect protocol handshake status and check representative app traffic. An IPv4 change alone does not prove all apps or IPv6 use the tunnel.
4. Run browser IPv6, WebRTC and DNS tests under the intended browser settings. An expected third-party secure DNS resolver is not automatically a leak. GeoIP country is approximate and does not prove the server is physically in that country.
5. On a spare connection, test disconnect/reconnect and the chosen kill-switch policy. Do not risk the remote access connection for this test.
6. If investigating package charging, separately compare carrier quotas/billing with a small controlled transfer and no competing traffic, allowing for reporting lag. Do not infer billing from an IP-check badge or PC byte counter.

Use separate results: Engine connected; Egress matches; IPv6/DNS policy checked; Speed measured; Carrier charging checked. Mark unrun tests Unknown. IPinfo's VPN/hosting classification is a reputation dataset, not proof that encryption works, a verdict that a tunnel failed, or evidence of free carrier usage. [IPinfo explanation](https://support.ipinfo.io/hc/en-us/articles/30792494886162-Do-You-Provide-VPN-or-Proxy-Services)

## Practical recommendation

### Ranked next steps for NetCroc

VPN support, ranked by ease/cost first and flexibility second (not measured speed):

1. **User-owned Proton WireGuard profile import.** First because it can use the user's free provider account without operating a VPS. Country/server entitlements and compatibility still require checking.
2. **User-owned VPS running WireGuard.** Second because it gives more server/location control, but adds hosting eligibility, costs and maintenance. Oracle free resources are a candidate to investigate, not a promise of available capacity.
3. **Xray/VLESS profiles.** Third for standard VPN use because configuration/security is more complex; valuable when screenshot-style customization is required.

ISP-package experimentation, ranked by how few unverified assumptions it introduces:

1. **Import a trusted existing 3x-ui profile/subscription and verify it on the exact package.** Closest to the friend's reported setup; establish carrier charging separately from IP changes before making a claim.
2. **User-managed Xray/3x-ui VPS.** More control over account expiry and configuration, but more operations and no automatic billing-classification advantage.
3. **Advanced manual Xray/sing-box profile editor.** Flexible fallback for supported transports/settings, ranked last because it requires the most knowledge and gives the least out-of-box confidence. Proprietary client payload formats need separate compatibility work.

These are workflow recommendations, not a list of confirmed working ISP vulnerabilities. No VPN connection, ISP billing experiment or free VPS deployment was performed for these rankings. Ordinary TLS certificate validation should remain enabled. Upstream 3x-ui guidance against production use also remains relevant to any publicly operated service.

### Friend's repository identified: 3x-ui

The user supplied [MHSanaei/3x-ui](https://github.com/MHSanaei/3x-ui). Its official README identifies it as a web management panel for Xray-core, with client quotas/expiry, share links and subscriptions. This makes a self-managed VPS plus exported VLESS client profile a plausible explanation for the screenshots. It does not establish the friend's installed version, server, ISP package or working classification bypass. Weekly expiry could have been an account/provider policy, not a TCP requirement.

Proposed NetCroc integration: import a user's compatible connection link or subscription; leave server administration in the user's panel. No panel administrator password should be needed for a normal client connection. The upstream README advises personal use and against production deployment; that guidance matters before choosing it as a public NetCroc service backend. It is not itself free VPS hosting. [Official README](https://raw.githubusercontent.com/MHSanaei/3x-ui/master/README.md)

Research first, then add user-owned WireGuard profile support and route-aware IP checks; consider Xray for VLESS customization next. Add further engines only for a concrete profile requirement. Do not advertise “free worldwide VPS” or a verified ISP-package bypass. A specific friend/provider/GitHub profile still needs identifying before compatibility and connectivity can be tested.
