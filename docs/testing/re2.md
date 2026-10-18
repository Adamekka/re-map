# RE2 Leon A validation

[Documentation index](../README.md) · [Testing index](../testing.md)

## RE2 Leon A checks

See [RE2](../re2.md) for the explicit profile/history command and current limits. Run `python3 -m pytest -q tests/test_re2_profile.py tests/test_re2_metadata.py tests/test_re2_tracking.py` for pinned identity, SCD bounds, shared contour extraction, source binding, native-map alternatives, lifecycle/scenario rejection, dormant versus unresolved items, acquisition/key flag reversal and atomic publication after coherence checks. These are synthetic regressions and offline catalog checks, not new gameplay observations. Browser regressions are `bun tests/check_map_browser.mjs <python>` for RE1 and `bun tests/check_re2_map_browser.mjs <python>` for all 133 RE2 outlines and source-specific door bindings. If Playwright is supplied by the bundled runtime, set `NODE_PATH` to its `node_modules` directory.

RE2-IDENTITY-001, RE2-SCD-001, RE2-MAP-001 and RE2-LIVE-001 in [research](../research.md) record exact identities, addresses, source leads and evidence. [RE2-LIVE-002](../research/re2.md#re2-live-002-gun-shop-ammunition-and-savestate-reversal) adds two observed shop ammunition pickups and actual earlier/later DuckStation loads. The first pickup followed ordinary navigation; the second used a recorded coordinate edit within the loaded shop. Neither establishes the full opening route to the RPD.

Continue with the shop's back exit and reentry, shotgun activation/collection, the remaining route to the RPD, key unlocks, unlock reversal and conditional floors. Use achievements-disabled agent settings and separate exploration history. Do not infer normal-save persistence from savestate tests.
