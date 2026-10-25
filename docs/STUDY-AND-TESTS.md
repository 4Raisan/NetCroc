# Recovery follow-up — 27 October 2026

The original 24-hour process/history observer finished but failed its coverage requirement (18.69 sampled hours, three observer gaps, zero history-read errors). Read-only inspection of Windows power events and minute coverage showed overlapping power transitions and history gaps. This is evidence of suspension/scheduling periods, not proof that every gap has one cause. The original failure report is preserved.

The revised observer distinguishes wall time, Windows awake uptime and observed samples; records timestamps/durations for gaps; refuses to overwrite prior evidence; supports an awake-time target with a bounded maximum wall duration; and can hold a nonpersistent thread-scoped awake request. An 18-second real Windows smoke passed with continuing history and no stalled samples. This does not complete a new 24-hour run.

Windows automated coverage expanded to 155 cases, with five POSIX-only skips. POSIX routing now separates the normal GUI/keyring from the privileged routing worker, with native OS authorization and parent-identity/transaction checks. The real Linux lab passed SSH and VLESS TUN byte forwarding, clean disconnects and parent-crash cleanup inside an isolated network namespace. No physical routes, DNS, Wi-Fi, ISP package or overseas provider was used by that lab. The lab is also enabled on the Ubuntu CI runner. Actual Linux/macOS physical-network tests and macOS notarization remain separate.

---

## REALITY, free provider and extended testing — 26 October 2026

The user authorized further administrator/provider tests, while excluding logo work and GitHub publishing, and deferred ISP-package billing checks because no package is currently available. **131 tests passed in 112.027 seconds.**

REALITY and REALITY+Vision now pass actual local native handshakes and byte forwarding. Invalid UUIDs, valid-but-incorrect X25519 public keys and incorrect short IDs fail forwarding. The first attempt revealed a missing server-name setting in the lab's REALITY server; adding the intended server name resolved it without weakening client certificate or key verification.

A **15-minute local soak completed 249 cases in 904.35 seconds**, including all four transports, REALITY, Vision, SSH/TLS, parallel channels and server-loss cleanup. It reported no errors or remaining child processes. Process handles were 201 at baseline and 206 after cleanup; resident memory was approximately 47.6 MB initially and 41.3 MB at the end. These observations cover this bounded run, not multi-day stability, sleep/resume or every possible resource leak.

The user created/signed into a Proton VPN Free account in the browser and explicitly approved generation/download of a Netherlands WireGuard profile. The original approved profile was recovered privately after a missed browser-download event, validated and imported into NetCroc's encrypted vault; no duplicate key was required. No account passwords, authentication codes or private keys are included in these documentation files or test reports. The original downloaded `.conf` remains a private credential file in the user's Downloads folder, outside this repository.

The real provider test completed a handshake, changed the public IPv4 and country from **LK to NL**, supplied working IPv6, and returned the VPN IPv4 in a Cloudflare STUN test. The ordinary access network had no working native IPv6; the test therefore does not certify leak protection on every IPv6-capable access network. System DNS worked while connected. Cleanup removed the tunnel service and encrypted runtime config, restored the original public IPv4 and left original physical-adapter DNS healthy. Public IPs are hashed in local test reports. Browser DNS resolver auditing is separate and must not be inferred from a healthy resolver or changed IP.

Baseline BrowserLeaks DNS testing observed four Dialog Axiata resolvers in Sri Lanka. The first DNS leak-test domain did not resolve on the access network, so BrowserLeaks was used instead. The subsequent approved elevated test completed the browser DNS audit: the browser IPv4 matched the native VPN IPv4, and BrowserLeaks found eight DNS servers, all in the Netherlands (CUSTOMERPANEL and WorldStream B.V.). No baseline Dialog resolver appeared. This bounded test observed no ISP DNS leak; it is not exhaustive leak certification. Disconnect again restored the baseline public IPv4 and physical-adapter DNS, with DNS health confirmed. Earlier cancelled administrator launches did not change routes.

The user supplied two saved Wi-Fi profile names. A live attempt reached the alternative SLT profile but did not obtain healthy DNS; a repeat did not establish a stable alternate connection. The OPPO hotspot was explicitly restored and a subsequent check confirmed stable association, working direct DNS queries and system hostname resolution. This is **partial**, not a passed two-network Internet test. Testing also corrected the `WLAN_CONNECTION_ATTRIBUTES` prefix order and filters transitional association/authentication states from the connected-profile display, while still protecting them from Forget. Two native-state regressions cover this behavior.

Windows 10 remains untested. The host is Windows 11 with 15.7 GB RAM and only 8.8 GB free on its sole filesystem. Hyper-V inventory found one VM but did not identify it as Windows 10; no guest was started or modified and no multi-GB OS download was attempted. No paid resource, subscription or VPS was purchased. All source/test changes remain local.

The old Fastlane process was subsequently quit through its own Quit control, and the rebuilt nine-tab NetCroc was opened. The saved Airtel/HTTP/one-second keep-alive selection was resumed; HTTP 200 responses and the encrypted provider profile were observed in the current UI. A low-overhead **24-hour process/history observer** started at 09:57:36 on 26 October 2026 (Asia/Colombo), due 09:57:36 on 27 October. Initial samples confirm process liveness and increasing aggregate minute-history coverage, with no history-read errors. Its status is **running**, not passed. It observes process resources and aggregate history progress without network probes or configuration changes; it does not certify GUI responsiveness, per-app ETW capture or sleep/resume. Quitting/replacing the monitored app ends the observation early. Local status: `test-artifacts/longrun-status.json`.

## Transport handshakes, full watchdog timeout and reconnection soak — 26 October 2026

The user authorized steps 1–3 only; no Git commit or push was made. Real native sing-box TLS forwarding and invalid-UUID rejection now pass for **WebSocket, gRPC and HTTPUpgrade**, in addition to TCP. These use local synthetic servers; REALITY and commercial-provider compatibility remain separate checks.

The actual independent DNS watchdog was exercised without shortening its timer. An elevated supervisor saved the adapter's original DNS, launched the independent watchdog, then launched a child that applied a reachable resolver and exited abruptly with code 23. The watchdog restored the original configuration after **90.63 seconds**. The supervisor verified the restored state and healthy DNS afterward; its finally block was a fallback, not the observed restoring mechanism. No restore callback was mocked. Local evidence: `test-artifacts/live-dns-timeout-check.json`.

The initial reconnection soak exposed intermittent Windows `WSAEWOULDBLOCK` during SSH/TLS login. TLS socket access now belongs to one I/O thread, with bounded buffers and a normal socket bridge for Paramiko. OpenSSL write retries retain the same immutable bytes. A new test transfers data across 24 channels with eight concurrent workers and verifies relay-thread cleanup. The local test server also serializes its TLS I/O to avoid the same fixture-side socket race.

The first corrected soak completed **78 cases in 182.92 seconds**, including TCP/WS/gRPC/HTTPUpgrade, SSH/TLS, parallel channels and server-loss cleanup, with no failures or remaining child processes. The confirmation run completed **72 cases in 181.43 seconds**, also without failures or child processes left behind. Both runs had 201 process handles at baseline and 206 after cleanup; these bounded observations do not establish absence of every leak. A full-suite rerun also exposed a Windows TCP reset when unsupported SOCKS requests were closed before their address/port had been consumed. The server now reads the complete request before sending its refusal. Twenty consecutive refusal regressions passed. The final expanded suite passed **127 tests in 54.998 seconds**. This is a bounded local reconnection check, not proof of multi-day stability, sleep/resume, repeated whole-PC route changes or all resource leaks.

The updated EXE matches source and passes nine-tab startup, independent packaged watchdog readiness/no-op shutdown and read-only DNS health. Older sections below are dated snapshots; pending items resolved in this section should not be read as still pending.

## VLESS implementation and live administrator checks — 26 October 2026

The user authorized administrator access and temporary connection interruption for this round. **123 tests passed in 31.334 seconds**, including native sing-box VLESS/TLS forwarding with a synthetic local server, invalid-UUID rejection, encrypted profile storage, strict URI parsing, schema checks for TCP/WebSocket/gRPC/HTTPUpgrade and REALITY, whole-PC configuration and the ninth GUI tab. VLESS uses the verified sing-box engine to connect to compatible Xray/3x-ui servers; an Xray server or executable is not bundled. CI now obtains the verified core before the suite so native tests are exercised rather than skipped. These new CI changes have not been published in this round.

Live Windows ETW testing found and fixed a TCP receive-address interpretation bug: this provider's TCP `saddr` identifies the local endpoint even for receives. The previous packet-style reversal discarded Internet downloads as local traffic. Updated native IPv4/IPv6 tests retain the different UDP ordering. After correction, a known 262,145-byte HTTP download and a server-echoed 69,000-byte synthetic upload produced 361,995 received and 70,714 sent bytes attributed to the test process, with zero decode errors or lost events. These are network-event counts, including TLS/HTTP overhead, the echoed upload response and receive-ahead; not an assertion that file bytes equal capture bytes. Historical per-app download totals that were missed cannot be reconstructed; adapter totals are independent. Evidence: `test-artifacts/live-traffic-fixed.json` (local, ignored).

Live administrator results:

| Check | Result | Limit |
|---|---|---|
| Real DNS apply and restore | Healthy before/after; exact original configuration restored | Current Wi-Fi adapter only |
| DNS rollback | Real apply/restore passed with a deliberately false post-apply health check | Injected health failure, not an actual resolver outage or watchdog timeout |
| Saved Wi-Fi connection | Current saved profile reconnected and DNS recovered | Did not switch to a different SSID or forget a real profile |
| WireGuard | Official signed client installed; synthetic local peer completed a real handshake and encrypted TCP echo; service/config removed | No overseas/provider exit; no default route or DNS change for this test |
| VLESS/TLS | Real native local-server byte forwarding and invalid-account rejection passed | Other transport/REALITY schemas checked, not all handshakes |
| Whole-PC VLESS | Live TUN, HTTPS and DNS succeeded; disconnect removed adapter and restored original DNS | Local exit, expected same public IP; one subsequent HTTPS attempt failed transiently and cleaned up correctly |
| Parent crash | Forced parent-process exit after TUN startup removed the adapter; DNS healthy/original afterward | Not every crash/power-loss condition |
| Updated EXE | Nine-tab startup, source matching, watchdog helper and read-only DNS health passed | Does not replace all live integrations |

Administrator helpers use synthetic secrets, bounded operations and cleanup; no Wi-Fi passwords or provider keys were written to reports. The official WireGuard 1.1.1 MSI was downloaded from the official distribution page and its valid WireGuard LLC Authenticode signature checked before installation. The optional verified routing core was also made available in the app's data folder. No real provider account/free VPS was created and no subscription or paid resource was purchased. No commits or pushes were made in this implementation round.

**Still requiring external resources/time:** foreign/provider connections and geolocation; a full DNS/IPv6/UDP leak test on a provider tunnel; ISP charging/package accounting; alternate-SSID switching with a supplied second network; actual watchdog-timeout recovery; every VLESS transport/REALITY handshake; a multi-day sleep/resume soak; and a separate Windows 10 machine. None is marked passed by local mocks or synthetic tests. Logo work remains paused.

## SSH/TLS implementation and safe retest — 26 October 2026

SSH/TLS is integrated as the eighth tab: encrypted profiles, account expiry, SSH key verification before authentication, TLS/SNI with CA validation or explicit certificate pinning, HTTP CONNECT proxy authentication, HTTP payloads before/after TLS, local SOCKS5, connection controls and byte-rate display. Optional whole-PC TCP mode uses a separately downloaded, hash-verified sing-box core, upstream route exclusion, tunneled DNS and rejection of other UDP/ICMP. A kill-on-close Windows job owns the child before configuration is sent. See [setup and limitations](SSH-TLS.md).

**113 tests passed in 34.764 seconds** in a clean Python 3.14 build environment. This includes all previous tests, 24 new SSH/routing tests and 3 new GUI tests. SSH tests use real loopback SSH/TLS servers and synthetic credentials: authentication, large bidirectional payloads, remote-domain forwarding, IPv4 forwarding and half-close, SNI, pre/post-TLS HTTP stages, certificate and host-key mismatch rejection before authentication, no-login identity inspection, cancellation, port conflicts, server-loss cleanup, encrypted DPAPI storage and unsupported UDP refusal. Proxy CONNECT formatting, routing launch/failure cleanup, download validation and non-admin blocking use mocks; a real harmless child process verified Windows job termination. The optional core's verified download and native `check` succeeded without starting a TUN adapter. GUI previews were inspected.

The updated local EXE passes source matching, eight-tab startup, independent watchdog readiness/no-op shutdown and read-only DNS health checks. Existing usage-period, Wi-Fi, DNS, WireGuard and accounting tests passed again. CI now includes the native routing configuration check. Remote results are available in GitHub Actions after publication; the local test results alone do not establish remote success.

**Still not verified live:** administrator ETW capture, real DNS apply/restore, actual Wi-Fi switching, real WireGuard/provider SSH connections, whole-PC TUN traffic/route recovery, public-IP and DNS/IPv6 leak tests, ISP package charging, Windows 10 and multi-day soak. These cannot be proven by mocks or localhost tests. The user's non-admin/connection-safe instruction was retained: no elevation, live route/DNS mutation or Wi-Fi switching was performed. No provider account or free VPS was created. No Git commit/push had been made at the time of this local validation snapshot.

## WireGuard local feature validation — 25 October 2026

86 source tests passed, including 17 new VPN backend/vault tests and 2 VPN GUI tests. Real Windows DPAPI user- and machine-scope encryption/decryption was exercised using synthetic secrets. Service installation, access-control handling, failure cleanup, existing-tunnel protection and non-admin blocking were tested with mocked Windows service operations. The VPN tab was rendered and inspected.

No provider profile or official WireGuard installation is present on this PC. No tunnel, route, DNS or Wi-Fi changes, installer or elevation prompt were used. An actual service connection/handshake, provider IP change and leak protection remain unverified. Optional public IP display is not a DNS/IPv6 leak test.

## NetCroc rename and structure cleanup — 25 October 2026

The active source is now `src/netcroc`, tests are in `tests`, maintainer scripts in `tools`, assets in `assets` and research in `docs`. The previous project folder is preserved as a recovery copy. No Git commits, pushes or releases were made by this cleanup.

67 tests passed, including existing-data folder compatibility and NetCroc startup-entry migration using mocks. Packaged NetCroc still requires controlled live administrator integration checks. Existing persistent data and the legacy instance lock deliberately retain compatibility identifiers.

## Startup repair — 25 October 2026

Fixed startup with the saved Show connection checks setting enabled: construct the footer before packing the log panel relative to it. Added a GUI regression covering startup with details enabled and repeated toggling. 66 source tests passed in 8.637 seconds.

## Keep-alive comparison and optional smart mode — 25 October 2026

65 source tests passed, including equal measurement counts with additional ON traffic, cancellation/refusal, robust summaries, optional/stale smart-mode sampling, and local GUI integration. Tests use a fake clock or localhost/mocked probes; no live Hutch throughput improvement has been established. Smart mode defaults off. This update does not change DNS or Wi-Fi configuration.

# NetCroc study and validation

## 25 October update: usage periods

Current history choices are **Last 30 days** (rolling now minus 30 days), **Last month** (previous calendar month), and **This month** (month-start through now). The 50-day choice was removed. Retention is 62 calendar days to cover two consecutive 31-day months. The current source suite passed **57 tests**, including twelve period/migration tests. Rolling data uses minute buckets; existing daily-only totals are preserved and never given invented time-of-day precision. Network filters, application/daily views, charts and CSV use the same selected window. Visible history refreshes every 30 seconds.

`releases/NetCroc.exe` contains this update; the running older `NetCroc.exe` was preserved. Updated source/executable verification is recorded in `test-artifacts/bundle-verification.json`. The older findings below remain the initial study/validation snapshot.

Date: 24 October 2026. Live tests used this Windows machine and its existing connection. Testing changed no DNS, Wi-Fi, router or startup settings. No UAC request was raised.

## HEAD URL study

Compared HTTPS roots and `/robots.txt`, three HEAD requests per candidate, with a one-second pause. All 30 requests returned HTTP 200; no response bodies were downloaded. Exact samples/final redirect URLs are in `endpoint-study.json`.

| Provider | Candidate selected for retesting | Median HEAD time | Root median |
|---|---|---:|---:|
| Dialog | `https://www.dialog.lk/robots.txt` | 1799.52 ms | 2345.69 ms |
| SLT | `https://www.slt.lk/robots.txt` | 242.33 ms | 321.53 ms |
| Mobitel | `https://www.mobitel.lk/robots.txt` | 622.58 ms | 684.26 ms |
| Airtel | `https://www.airtel.lk/robots.txt` | 814.52 ms | 901.64 ms |
| Hutch | `https://hutch.lk/robots.txt` | 874.65 ms | 992.37 ms |

These durations potentially include proxy discovery, DNS, TCP, TLS, redirects and server processing. They are **not ICMP RTTs**. They do not establish the best target on each provider's own access network, any speed improvement, or continuous one-request-per-second performance. The 1-second option waits after completion: a 1.8-second request takes about 2.8 seconds start-to-start. No checks overlap.

Selected candidates succeeded three times and had lower medians in this snapshot. A dedicated endpoint you control may be better for continual probing. URL Study permits retesting and explicitly copying a candidate; it never silently changes the running target. A one-second delay can generate up to 86,400 checks/day; data, battery and server costs are not zero.

Official provider sources: [Dialog](https://dialog.lk/support/contact-us), [SLT](https://www.slt.lk/support), [Mobitel](https://www.mobitel.lk/), [Airtel](https://www.airtel.lk/support/), [Hutch](https://hutch.lk/contact/). HEAD semantics: [RFC 9110](https://www.rfc-editor.org/rfc/rfc9110.html#section-9.3.2).

## DNS study

Three rounds across `example.com`, `www.microsoft.com` and `www.cloudflare.com`: nine IPv4 DNS queries per resolver, shuffled. A connected UDP socket verifies response ID/question/status and rejects failures/truncation. The test does not infer DNS quality from ping, support TCP-only/encrypted DNS, or eliminate cache effects.

| Resolver | Median successful lookup | Failed queries |
|---|---:|---:|
| Current router DNS | 14.29 ms | 0/9 |
| Cloudflare | 48.94 ms | 0/9 |
| Google | 90.79 ms | 0/9 |
| Quad9 | 238.63 ms | 2/9 |

`dns-study.json` contains the summary and current private resolver address. **Keep the existing DNS on this connection.** These results show no benefit from switching it. They establish neither a universally fastest resolver nor a throughput gain. [Google DNS performance documentation](https://developers.google.com/speed/public-dns/docs/performance)

## Validation

Automated coverage includes byte thresholds, elapsed-time speed calculations, counter resets, 50-day retention, date ranges, midnight allocation, persistent storage, per-network app queries and safe CSV export. ETW checks cover native structure layouts, IPv4/IPv6 TCP/UDP event directions, byte callbacks, visible errors and non-administrator handling. Wi-Fi checks cover protected/plaintext keys, open networks and connected-profile deletion protection. DNS checks cover query validation, reliability ranking, permissions, preflight, snapshots, simulated apply/restore, failure rollback and watchdog transaction isolation.

The final source suite passed **45 tests**. Watchdog tests also cover independent process startup, readiness confirmation and preventing a candidate DNS change if the watchdog fails. A subprocess regression verifies that the DNS health flag actually enters the read-only helper and returns a bounded status instead of launching the GUI. Frozen watchdog lifetime follows [PyInstaller's independent-process guidance](https://pyinstaller.org/en/latest/common-issues-and-pitfalls.html#using-sys-executable-to-spawn-subprocesses-that-outlive-the-application-process).

GUI integration tests exercise tables, history filters, invalid dates, permission handling, a real local HEAD server at the one-second-repeat setting and live adapter sampling. Native read-only checks verified adapter discovery, saved Wi-Fi reads and resolver queries. Passwords were not printed or saved in test artifacts. Synthetic previews in `test-artifacts/previews/` are not evidence of real administrator capture.

The final standalone `releases/NetCroc.exe` passed its six-tab GUI diagnostic, independent watchdog readiness/no-op exit test and read-only system DNS health check (exit 0). Every bundled application module and the entry point matched the current source. Evidence is in `test-artifacts/frozen-smoke.json`, `bundle-verification.json` and `source-validation.json`. These packaged checks did not apply DNS or switch Wi-Fi.

**Not verified live:** administrator-enabled ETW collection under real sustained traffic; real DNS mutation/rollback; Wi-Fi switching/forgetting; long-duration performance; Windows 10; actual multi-day sleep/resume; ISP billing agreement. No prior usage history was invented. These are required release checks once local administrator access and an expendable test connection are available.

An administrator-capable lab should compare known upload/download payloads from TCP and UDP apps, verify IPv4/IPv6 attribution and capture loss, exercise DNS success/failure/process termination with DHCP/static restoration, switch Wi-Fi profiles on a spare connection, and run a multi-day retention soak. Do not perform those disruptive checks on the only remote connection.
