# Structure and compatibility

The current project lives in `NetCroc`, alongside the original `Hutch_Self-Ping` recovery copy. Its existing Git repository and history are preserved. The old source folder and running executable were not modified.

## Layout decisions

- `src/netcroc` is the renamed Python package; `src/app.py` remains the entry point.
- Tests moved out of the application source into `tests`.
- Release, bundle verification and preview scripts moved into `tools`.
- Icons and diagrams moved into `assets`.
- Research and validation notes moved into `docs`, with bounded study snapshots in `docs/research-data`.
- Build outputs and test artifacts stay local and ignored by Git.
- Historical Fastlane documentation is archived explicitly in `LEGACY-FASTLANE.md`; current instructions live in the root README.

## Deliberate legacy identifiers

`ConnectionTrayPreview` remains only for existing local data, old sign-in entry cleanup, and shared instance locks. Keeping these identifiers prevents losing history, losing pending DNS recovery state, or starting two usage writers during the transition. Fresh installations use the NetCroc data folder. Startup entry changes happen only when the user saves the startup preference.

The bundle refresh utility recognizes the old Python package name when importing a compatible earlier build. It writes the current `netcroc` package and validates all module fingerprints.

Source, tests, assets, tooling and documentation are tracked in Git. Executables and local test artifacts are excluded; publishing a downloadable release is a separate step.

## VPN module

`src/netcroc/vpn.py` validates standard WireGuard client profiles, stores them with user-scoped DPAPI, controls only NetCroc-named tunnel services, and reports service/handshake status. `tests/test_vpn.py` uses synthetic keys and mocked service operations. The official WireGuard Windows program is a separate prerequisite, not bundled in NetCroc.
