# RE2 Leon A validation

[Documentation index](../README.md) · [Testing index](../testing.md)

## RE2 Leon A checks

See [RE2](../re2.md) for the explicit profile/history command and current limits. Run `python3 -m pytest -q tests/test_re2_profile.py tests/test_re2_metadata.py tests/test_re2_tracking.py` for pinned identity, SCD bounds, shared contour extraction, source binding, native-map alternatives, lifecycle/scenario rejection, dormant versus unresolved items, acquisition/key flag reversal and atomic publication after coherence checks. These are synthetic regressions and offline catalog checks, not new gameplay observations. Browser regressions are `bun tests/check_map_browser.mjs <python>` for RE1 and `bun tests/check_re2_map_browser.mjs <python>` for all 133 RE2 outlines and source-specific door bindings. If Playwright is supplied by the bundled runtime, set `NODE_PATH` to its `node_modules` directory.

RE2-IDENTITY-001, RE2-SCD-001, RE2-MAP-001 and RE2-LIVE-001 in [research](../research.md) record exact identities, addresses, source leads and evidence. Current runtime coverage is the controlled opening street only. Before extending confidence, collect independent before/after pickups, key unlocks, room reentry, conditional floors and earlier/later savestate loads with achievements disabled and a separate agent history. Do not infer normal-save persistence from savestate tests.
