# RE2 script coverage

[Documentation index](../../README.md) · [Claim index](../../research.md)

## RE2-SCD-002: switch branches establish candidate-list coverage

Status: Candidate for the bounded source interpretation on USA Dual Shock Ver. Leon A, SLUS-00748, and Claire B, SLUS-00756. Owned-source inspection, copied native-handler execution and replays of earlier runtime captures support the change. No new gameplay or campaign coverage is claimed.

### Failure and revision identities

On 2026-10-27 the human reported an empty item list with "Item check incomplete" in source `00-00`. The production log identifies `re2_leon_a_slus00748`, successful coherent reads, no item rows and `UNKNOWN`. The source has switch statements, so the old decoder set `candidate_list_complete` false even though it found no pickup declarations or direct awards. This flag alone prevented clearance.

The exact executable identities and tested official DuckStation `0.1-12442-gdd4a0eb77` are recorded in [RE2-DS-001](dualshock.md#re2-ds-001-leon-a-dualshock-revision-port) and [RE2-DS-002](dualshock.md#re2-ds-002-claire-b-dualshock-revision-port). Leon's `PL0/RDT/ROOM1000.RDT` has SHA256 `19e4144c44d7c706250f393115a23b92256fff80b5a775d612e6d58afa86c817`. Its three decoded switches start at source-file byte offsets `0x131E`, `0x138E` and `0x13FA`.

### Native contract and implementation

All handler addresses below are PS1 virtual code addresses, not host addresses or RAM-dump offsets.

| Opcode | Leon handler | Claire handler |
| --- | --- | --- |
| Switch `0x13` | `0x80054020` | `0x80053FF8` |
| Case `0x14` | `0x800540F8` | `0x800540D0` |
| Default `0x15` | `0x80054110` | `0x800540E8` |
| End switch `0x16` | `0x80054128` | `0x80054100` |
| Break `0x1A` | `0x80054268` | `0x80054240` |

The owned executables supply these handlers through their opcode tables. Switch is four bytes. Its selector index at packet offset one is an unsigned byte, mask `0xFF`; its exit displacement at offset two is unsigned 16-bit little-endian, mask `0xFFFF`, relative to the following command. The native selector reads a signed 16-bit counter. Case is six bytes, with an unsigned 16-bit little-endian skip at offset two, relative to its following command, and a signed 16-bit comparison at offset four. Both halfword operands use full mask `0xFFFF`. Default and end-switch are two bytes. A mismatch follows the case chain; a match enters its body; default ends the search. Break uses the switch's stored exit.

The decoder follows every bounded case label and separately queues the closing marker and post-switch path. An early return or jump in one case cannot hide a later case's pickup or direct award. Empty cases, default bodies and nested switches are included. Switch targets must stay in the procedure, the chain must terminate at a matching end marker or default, and decoded switch procedures must have non-overlapping command boundaries. Orphan markers keep coverage unresolved. Invalid bounds/chains produce an explicit source diagnostic rather than a guessed empty list.

This establishes a candidate catalog, not mandatory item presence. Existing startup/presence interpreters still reject switch-dependent proofs. Cataloged items, unresolved awards, mismatched identities and unrecognized live interactions continue to prevent unsupported clearance.

### Reproduction and evidence

Private evidence is under `/tmp/re-map-re2-switch-20261027/`:

- `native-switch.py` and `native-switch.json` execute both owned native switch handlers over Leon's three opening-source switches with fourteen signed selector samples each. All 84 selections match their source-label destinations. These are copied-code experiments using Unicorn `2.1.4`, not gameplay observations or Claire room validation.
- `leon-rooms.json`, `claire-rooms.json` and `corpus-delta.json` reproduce metadata generation using the commands in the DualShock revision records. Each 125-source corpus gains fifty complete candidate lists. Item declarations, identities, quantities, direct awards and doors are unchanged. Existing proofs additionally resolve some previously gated item-presence entries. Both generated map documents are unchanged. Original-release catalogs are not regenerated or relabeled as validated.
- `replay.py` and `runtime-replay.json` compare baseline/current readers over five existing native captures from each revision, including their earlier/later savestate restorations. Leon's `00-00` and Claire's `00-04` change from Unknown to Cleared in all ten fresh reads. Item lists stay empty and doors, position and heading agree. Ten production history save/close/reopen cycles retain their private playthrough identities and visits, initially restore Unknown, then reconstruct clearance from fresh RAM.
- Those captures retain the setup and limitations in RE2-DS-001/002, including disabled achievements, hidden agent instances and Leon's recorded health/position assistance. This task starts no emulator and applies no guest-memory patches. Replaying an existing restore capture is not a new restore, reentry, pickup, memory-card persistence or campaign observation.
- `browser-result.json` checks a headless render of the corrected Leon opening capture: one explored outline, Cleared state, zero item rows, zero incomplete-check links and no page errors. The refreshed README image contains only tracker geometry and copy.
- `live-before.json`, `live-after.json` and `live-restart.json` verify the user's active tracker changes `00-00` from Unknown to Cleared after a graceful tracker restart with its original arguments. The same playthrough identity and accumulated visits survive. This reads the already running game; no game input, game/save loading or guest-memory write is performed.

`tests/test_re2_metadata.py` covers branches after returns, the post-switch path, defaults, nested/empty cases, malformed targets and overlapping/orphan markers. `tests/test_re2_tracking.py` checks both DualShock catalogs' opening-room clearance and reversal to Unknown for an unresolved live interaction, followed by fresh reconstruction. Use the focused command in [RE2 testing](../../testing/re2.md).

The full suite passes 2,581 tests. All 133 existing RE2 browser outlines, bindings and controls pass their regressions. Strict Ruff checks pass for the decoder and changed tests; the generator passes scoped E4/E7/E9/F checks excluding its existing E402 path setup. Formatting and whitespace checks pass. Final regeneration exactly reproduces both checked-in room catalogs and preserves both map documents byte for byte.

### Review and limits

The root review checks native displacement semantics, all branch discovery, input bounds/termination, separation of coverage from item presence, generated deltas, fresh-state reconstruction and rendered clearance. The renderer, controls and persistence schema retain their existing implementation. Native reentry and item/door lifecycles outside the retained captures remain untested for this change.

T3 reports the Claude and Antigravity providers disabled, so the configured Claude Opus and Gemini Flash reviews cannot run. No substitute or CLI fallback is used, and neither unavailable review is an endorsement. Default Ruff also reports pre-existing import ordering in the metadata generator; scoped checks exclude that unrelated finding. After these limitations were reported, the human directed committing this fix on 2026-10-27.

Contributions:

- 2026-10-27; human user; supplied the opening-room screenshot, asked why the item check was incomplete, then requested the fix.
- 2026-10-27; human user; authorized committing this fix after the unavailable external reviews and pre-existing generator lint were reported.
- 2026-10-27; Codex root, exact model `gpt-6.1-sol`, verified through T3's current-thread model selection; authored the decoder/tests and this record, inspected the owned handlers, ran the copied-code experiments, regenerated the two DualShock catalogs and replayed the existing native captures. Prior research authorship and gameplay claims remain unchanged.
