# ISP keep-alives, Z Pinger, and actual connection improvements

Historical pre-implementation analysis. See [STUDY-AND-TESTS.md](STUDY-AND-TESTS.md) and [README.md](README.md) for the implemented NetCroc dashboard and current validation status.

Research date: 24 October 2026. Scope: local source inspection and public primary sources. No network settings changed and no performance improvement measured.

## Existing project

`NetCroc` already implements the requested ISP/URL pinging idea. Its README calls it **NetCroc · Preview**. No duplicate `Fast-lane` folder was created.

Verified directly in `src/connection_tray/core.py` and `ui.py`:

- Preset websites: Dialog, Mobitel, Hutch and Airtel; custom HTTP(S) URL or host supported. Selecting an ISP only selects the destination.
- HTTP mode sends HEAD through Python urllib; ICMP mode invokes Windows `ping.exe` once per check.
- Available waits: 5, 10, 15 or 30 seconds. The worker waits **after** a probe completes, so start-to-start spacing also includes probe duration.
- HTTP uses a four-second socket timeout; ICMP sets a 1.5-second reply wait and a four-second subprocess limit. Redirects and successive network operations mean the HTTP timeout is not a guaranteed four-second total deadline.
- HTTP error responses count as reachable. Reported time measures the whole probe, including possible DNS, TCP, TLS, redirects and server processing; it is not a pure network RTT.
- It has tray controls, optional Windows sign-in startup, settings storage and an in-memory history. This is a Windows tool, not an Android radio controller.

## Z Pinger: confirmed claims versus reconstruction

Official app: **Z Pinger: Network Stabilizer**, **ZentixTeam**, package `com.zentix.zpinger`. The developer advertises background operation, configurable targets, HEAD requests, connection logs and 5/10/15/30-second intervals. These are developer statements, not independently verified implementation details. [Google Play](https://play.google.com/store/apps/details?hl=en-US&id=com.zentix.zpinger)

The mechanism can be reconstructed conceptually as:

```text
Start -> read target and interval -> run background service
      -> send HTTP HEAD -> record result/time -> wait -> repeat
Stop  -> cancel work and service
```

This is a behavioral reconstruction, **not completed APK reverse engineering**. No app binary was obtained or decompiled, no installed Android instance was examined, and no traffic was captured. Public searching did not establish an official source repository. Exact preset URLs, HTTP library, socket reuse, redirect policy, timer semantics, wake locks, service type, permissions and battery-saver behavior remain unverified. The listing alone cannot prove there is no additional mechanism.

HEAD asks for response headers without a response body. It still consumes request/response bytes and transport overhead, and HTTPS can require DNS/TCP/TLS setup. “Low data” is plausible relative to fetching pages; “zero data” is not. A website's Content-Length header does not measure bytes downloaded by HEAD. [HTTP specification, section 9.3.2](https://www.rfc-editor.org/rfc/rfc9110.html#section-9.3.2)

### Why periodic traffic sometimes helps

**Plausible inference:** periodic traffic can reduce the delay of the first request after inactivity by repeatedly activating a cellular radio. It may mask some idle-related stalls. The outcome depends on carrier timers, modem firmware, radio technology and Android power restrictions. It does not guarantee the radio stays continuously active. Android documents the battery/latency tradeoff; its illustrative 3G timings must not be treated as measured Hutch 4G/5G timings. [Android radio behavior](https://developer.android.com/develop/connectivity/network-ops/network-access-optimization)

Keeping the app's service running is separate from keeping a mobile radio active. Foreground services expose ongoing work to the user, but do not confer unrestricted networking in all power states. Doze restricts network access and has specific exemption rules. Consequently, “never killed” or “always works with screen off” requires device testing. [Foreground services](https://developer.android.com/develop/background-work/services/fgs), [Doze and App Standby](https://developer.android.com/training/monitoring-device-state/doze-standby)

**Important boundary:** sending HEAD to an ISP homepage does not refresh every game's NAT entry. NAT state belongs to particular flows/mappings; a game's supported heartbeat on its own socket can maintain its mapping. A separate HTTP connection is different traffic. The inference follows from the mapping and refresh model in [RFC 4787](https://www.rfc-editor.org/rfc/rfc4787.html#section-4.3).

Neither an ISP hostname nor more frequent probes inherently raises a subscription speed limit, adds tower capacity, repairs weak signal, or chooses a faster route for unrelated traffic. During an active game or download there is already traffic, so an idle-prevention explanation alone is weak evidence for improvements in that situation.

## Technique comparison

| Technique | What it does | When it can help | Limits/cost |
|---|---|---|---|
| Repeated ICMP echo | Measures reachability and echo RTT | Diagnostics; possibly keeps the access link active | No bandwidth upgrade; ICMP may be filtered or treated differently from app traffic. [RFC 792](https://www.rfc-editor.org/rfc/rfc792.txt) |
| Periodic HTTP HEAD, including Z Pinger's advertised method | Exercises DNS/HTTP and the access link | Idle-related first-request delay or some inactivity stalls | Extra traffic and battery; HTTP timing includes more than RTT; target may reject HEAD. Sources above. |
| Small HTTP GET | Fetches a resource to exercise the connection | Endpoint lacks HEAD support | Potentially more data, especially if a large page or redirects are fetched. HTTP specification above. |
| TCP connection probe | Tests whether a port accepts connections | Distinguishing web-port failures from ICMP blocking | No proof the app works after connection; no general acceleration. This is a diagnostic inference from the layers involved. |
| App-specific TCP/UDP heartbeat | Keeps that app's existing flow alive | Actual idle timeout/NAT expiry | Requires app/protocol support; unrelated website requests do not substitute for it. RFC 4787 above. |
| Faster/reliable DNS | Reduces name-resolution delays | Slow/failing resolver or uncached lookups | Does not generally change established-flow bandwidth; resolver choice can affect CDN selection, so compare actual sites. [Cloudflare explanation](https://www.cloudflare.com/learning/performance/more/speed-up-the-web/) |
| SQM using CAKE or fq_codel on the router | Controls queues and shares traffic | Lag spikes during uploads/downloads caused by bufferbloat | Often trades some peak throughput for responsiveness; CPU and variable cellular capacity complicate tuning. [OpenWrt SQM](https://openwrt.org/docs/guide-user/network/traffic-shaping/sqm) |
| VPN/WARP or another route | Tunnels traffic through another network | Worth an A/B test when routing is suspected | Can add overhead and latency; no universal gain. Cloudflare documents possible reduced throughput. [WARP FAQ](https://developers.cloudflare.com/warp-client/known-issues-and-faq/) |
| Ethernet, better Wi-Fi placement/channel | Addresses the local wireless bottleneck | Interference, weak coverage, retransmissions | Cannot fix upstream tower congestion. [Microsoft Wi-Fi troubleshooting](https://support.microsoft.com/en-us/windows/experience/connectivity-networking/fix-wi-fi-connection-issues-in-windows) |

For mobile data, also compare modem placement and available network modes using the same SIM and destination. This is a proposed experiment, not a verified recommendation to lock bands or change carrier settings. If the bottleneck is carrier congestion or poor coverage, there is no general ping command that removes it.

## Local tool versus Z Pinger

| Aspect | NetCroc: inspected source | Z Pinger: published description |
|---|---|---|
| Platform | Windows | Android |
| HTTP keep-alive idea | HEAD | HEAD advertised |
| ICMP | Implemented | Not established by the listing |
| Intervals | 5/10/15/30 seconds after each probe | 5/10/15/30 advertised; scheduling unverified |
| Targets | Four ISP sites and custom destination | Presets and custom URL advertised; presets unverified |
| Background lifecycle | Tray, worker thread, optional sign-in startup | Persistent service advertised; exact implementation unverified |
| Demonstrated speed gain | None measured here | No controlled benchmark verified here |

The existing project already covers the core published keep-alive behavior. Android-specific lifecycle work is a separate implementation concern. A PC sending through a phone hotspot or cellular router may generate modem traffic, but does not directly control the modem's radio state.

## How to establish whether this helps your connection

1. Define the symptom: slow first request after idle, disconnections, consistently low Mbps, or latency under load. They require different remedies.
2. Keep SIM, device, location, network mode, test server and approximate time consistent. Record signal metrics if available. Stop other keep-alive apps.
3. Compare OFF/ON/OFF/ON blocks and repeat across sessions. Start with a 30-second keep-alive interval; try 15/10/5 only if shorter spacing produces a repeatable benefit. This is a proposed test order, not a proven optimum.
4. For idle tests, use a real idle period such as 60–120 seconds before each application request. Do **not** run continuous measurement pings in the OFF condition: those pings themselves keep the link active and invalidate the baseline. Screen-on and screen-off tests should be separate.
5. Separately compare a sustained transfer/game and loaded-latency test. Log download/upload Mbps, application RTT median/p95, failures, and test duration. Report ICMP packet loss only when measured with ICMP; an HTTP timeout is not a packet-loss measurement.
6. Measure data and battery over equal, sufficiently long windows. Keep endpoint, protocol and connection reuse consistent. A 5-second nominal interval permits about 720 requests/hour versus 120 at 30 seconds, before probe time and scheduling delays; these counts are arithmetic, not measured data use.
7. Only call it an improvement when the same symptom improves repeatedly beyond baseline variation. Lower first-request latency supports an idle-latency benefit; higher sustained Mbps requires its own throughput evidence.

For a proper APK audit, obtain an authentic developer/Play-installed build, record version, certificate and SHA-256, inspect its manifest and decompiled worker/service code, then compare packet timings and Android power behavior against the listing. Capture metadata on a test device/network you control; HTTPS interception is unnecessary for verifying request cadence and destinations when other evidence is available. A capture app using Android's VPN API can change routing and must be accounted for in benchmarks. This work remains outstanding; the report must not be cited as a binary audit.

## Practical direction

Keep NetCroc as a connection-check/optional keep-alive tool. The useful next enhancement would be an opt-in measurement export and controlled comparison workflow, with separate HTTP duration and ICMP RTT labels. No app changes were made in this research task. For speed and responsiveness, diagnose the bottleneck first: idle stalls justify testing keep-alives; load-induced lag points toward SQM; local wireless problems point toward Ethernet/Wi-Fi fixes; suspected route problems justify a controlled tunnel comparison.
