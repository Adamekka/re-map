# RE2 creator lifetime

[Documentation index](../../README.md) · [Claim index](../../research.md) · [Room completion](../../room-completion.md)

## RE2-LIFETIME-001: unreachable generic creators preserve pickup presence

Status: Candidate for Resident Evil 2 Dual Shock Ver. USA Disc 1, SLUS-00748, Leon A, Original/Normal. Owned-source analysis, synthetic state reconstruction and retained-capture replay support this correction. No native target pickup, departure/reentry or savestate lifecycle is observed in this increment.

### Failure and bounded correction

Baseline `afebef5` retains West Office source `01-02`'s fixed context and excludes acquisition IDs 116/249. It gives IDs 111/113/114 required presence but withholds ID 115's presence after departure. [RE2-DS-003](dualshock.md#other-reported-rooms-and-evidence-limits) identified the cause. Slot 12 has a generic interaction at source offset 7370 in the opposite fixed system-mode branch, and an ordinary pickup creator at offset 7394 in the selected branch. The lifetime check considers every decoded generic creator, including the proven unreachable one.

The existing shared whole-source walk now returns unreachable creator offsets only after preserving the fixed context. It still seeds every procedure independently and retains every creator in opaque loop procedures. Uncalled procedures, fresh mutable predicates, unsupported effects and failed source proofs cannot establish these exclusions. The API extension was coordinated with the Main Hall/East Office investigation and authored in commit `3f060fc359790a62d4a9ae6a9c44960c96af5b6c`; this checkout incorporates the same patch as `1f0db84`.

Collection presence accepts that explicit result, asserts its source membership and preserved fixed context, and removes only proven unreachable generic interactions from slot conflicts. Existing door, reset and conflicting-item lifetime checks remain conservative. This establishes lifetime eligibility, not presence by itself. The existing startup proof must still establish the selected pickup. [RE2-COLLECT-019](../re2.md#re2-collect-019-preserved-context-prunes-inactive-startup-branches) records that separate shared proof and its original-release validation limits.

Owned-CUE regeneration changes exactly one room field: `01-02` gains required conditional presence for ID 115. No room or ID appears in the production lifetime rule. All item declarations, quantities, identities, exclusions, awards, source coverage, doors, other rooms and map bytes remain unchanged. The catalog also adds this claim reference. Other revision catalogs and profiles are unchanged.

ID 115 now stays Uncollected when its fresh acquisition bit is clear, including after departure and in a fresh tracker retaining visits alone. Acquisition makes it Taken; an earlier synthetic state reverses it independently of other items. The room's conditional direct award retains its own sufficient condition and acquisition flag. A visit or collection of the physical pickups cannot make that award required. With all physical pickups collected and that award unresolved, completion stays Unknown. A synthetic fully acquired state can clear the complete list; this is not observed gameplay clearance.

### Identity, addresses and reproduction

The owned executable is `SLUS_007.48`, SHA256 `e576348f64d015ecff6e1ce875a8924ee252ba7f3f9478b0917cbbdeb97db441`. Owned `PL0/RDT/ROOM2020.RDT` is 167840 bytes, SHA256 `31a5b1206bfa71d28ae92a15bebb86f90d046e62474a5c7be1cc64d74cadc323`. Source offsets above are RDT file offsets, not RAM or host-process addresses. Retained DualShock captures were made with official DuckStation `0.1-12442-gdd4a0eb77`, source commit `dd4a0eb779296a525f8b10b6d9a45911ad6d088f`, as recorded in [RE2-DS-001](dualshock.md#re2-ds-001-leon-a-dualshock-revision-port). This increment starts no emulator and performs no connection, game/save load, settings/history change or guest write. No new health or ammunition aid is enabled; retained captures keep their original documented assistance limits.

All addresses below are PS1 virtual addresses. Words are unsigned four-byte little endian; masks select one bit. Synthetic bytearrays map virtual addresses with `0x1FFFFF`. They are neither native observations nor writes to a running guest.

| Input | Address | Mask and interpretation |
| --- | --- | --- |
| Fixed system mode, bank 0 bit 25 | `0x800CFB74` | `0x00000040`, required set |
| Fixed scenario, bank 1 bit 1 | `0x800CFBD8` | `0x40000000`, required clear |
| Target acquisition, bank 8 bit 115 | `0x800D48C8` | `0x00001000`, set means collected |
| Independent acquisitions, bank 8 bits 113/114 | `0x800D48C8` | `0x00004000` / `0x00002000`, remain set during target reversal |
| Direct-award presence, bank 4 bit 7 | `0x800D4854` | `0x01000000`, clear is a sufficient condition in this fixed scenario |
| Direct-award collection, bank 8 bit 5 | `0x800D48BC` | `0x04000000`, set means collected |

Reproduce offline with the owned Leon CUE and `tools/build_re2_metadata.py`, passing `--profile profiles/re2_leon_a_slus00748.json`. Compare the resulting room catalog to the baseline, and compare the complete floor-plan file byte for byte. Two generations agree on every room field; their only catalog-header difference is the claim reference added between runs. The second generated catalog is the checked-in artifact. All generated floor-plan bytes equal baseline.

Private evidence is under `/tmp/re-map-re2-west-office-20261027/`. `source-diagnostic.json` records the pre/post lifetime result and the existing context walk's unreachable offsets, including generic creator 7370. This diagnostic inspects the walk's local result without changing its control flow. `baseline-rooms.json`, `generated-rooms.json`, `metadata-delta.json`, `baseline-maps.json`, `generated-maps.json` and `repeated-maps.json` retain the generation comparison. Owned bytes and raw RAM remain outside Git.

### Regressions, replay and review

Run:

```sh
python3 -m pytest -q tests/test_re2_creator_lifetime.py \
  tests/test_re2_scenario_reachability.py tests/test_re2_metadata.py \
  tests/test_re2_profile.py tests/test_re2_tracking.py
```

All 973 focused tests pass. The dedicated lifetime tests cover fixed-false and reachable generic creators, mutable and compound predicates, uncalled procedures, opaque zero-count FOR bodies, fixed-bit writes, incomplete sources, generic item creators, retained door/reset conflicts and invalid proof inputs. Current/departed synthetic states repeatedly reverse target acquisition with independently collected items and an unresolved award. Every state is also reconstructed by a fresh tracker from visits alone. Separate award condition/collection changes preserve Unknown until all relevant state resolves, and reverse it again. These are synthetic interpretation checks, not actual earlier/later savestate loads.

`replay.py` compares 383 unique untouched RAM images across all four profiles against baseline metadata. Every complete Tracker and poll status/message agrees. Accepted publications comprise 266 original Leon, 88 original Claire, three DualShock Leon and three DualShock Claire images; the remaining 23 are unchanged Retry or NonGameplay results. No retained DualShock West Office gameplay image is present, so unchanged replay does not validate the new target outcome. It supplies regression evidence for prior accepted observations only. `capture-replay.json` records the paths, checksums, profile matches and results.

Scoped Ruff E4/E7/E9/F checks with the established E402 exclusion, formatting and whitespace checks pass. The coordinating task runs the aggregate full suite. Test counts and source proofs add no native room coverage or campaign-readiness claim. Normal memory-card persistence, native target collection/departure/reentry and real earlier/later restore reversal remain untested here.

Direct final review checks the shared walk's provenance and failure behavior, source/context assertions, generic-only exclusion scope, mandatory startup presence proof, generator binding, metadata delta, fresh acquisition/award independence, preserved visits, malformed inputs, runtime cost and evidence attribution. No additional verified defect remains in this increment. External Claude Opus and Gemini Flash reviews are unavailable because their T3 providers are disabled, as specified by the coordinating task. Neither review ran; no substitution or CLI fallback supplies an endorsement. UI/UX/accessibility rendering is outside this interpretation-only change, and the README screenshot is unchanged.

Contributions:

- 2026-10-27; coordinating task; supplied the exact West Office diagnosis, current revision, source/capture locations, offline-only constraint and ownership split.
- 2026-10-27; Main Hall/East Office implementation task, exact model `gpt-6.1-sol` verified in T3 thread metadata; authored the shared reachability API and its dedicated source regressions. This attribution covers that dependency, not a review or native validation of the lifetime caller.
- 2026-10-27; implementation sub-agent, exact executing model `gpt-6.1-sol`, verified in session `01a17f23-3458-7850-94c7-286be7dff6f2`'s latest `turn_context`; implemented the lifetime caller and generator wiring, added regressions, regenerated Leon metadata, replayed retained captures, performed direct final review and wrote this entry. No new native gameplay experiment was performed. Earlier research authorship and observations remain unchanged.
