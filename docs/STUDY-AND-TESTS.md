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
