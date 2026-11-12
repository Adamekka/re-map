# RE2 reset-created item candidates

## RE2-RESET-001: enumerate reset possibilities without granting presence

Status: Candidate for Resident Evil 2 Dual Shock Ver., USA, Disc 1 Leon A Original/Normal, SLUS-00748. Executable `SLUS_007.48` SHA256 `e576348f64d015ecff6e1ce875a8924ee252ba7f3f9478b0917cbbdeb97db441`. This contribution uses owned source bytes, synthetic reader controls and offline copied-save RAM. It supplies no gameplay, native restore or memory-card persistence confirmation. No emulator or DuckStation version was tested in this task. The supplied save extraction reports version 94 serialization using DuckStation source commit `1bc5405c417d8f8f61cc5eac624aac9f4b0677eb`.

The raw catalog enumerates dedicated item constructors. Its narrow reset variant companion binds changed types only to an ordinary item creator with the same slot and acquisition ID. That companion remains a positive identity input for [known puzzle items](known-puzzle-items.md#re2-puzzle-003-stable-acquisition-survives-reset-only-item-alternatives). It is not a complete possibility catalog.

The new revision opt-in requires a separate `reset_item_candidates` array, real reset offsets, slot/type/amount/GID/SAT, and tagged origins. Descriptor origins contain a real constructor offset and constructor-owned ordinary/four-point geometry. An explicit `unregistered_null_alias` origin has no offset. Every matching source descriptor and the NULL alternative remain possible until independent registration/entry authority can narrow them. Empty Aot_on slots alias physical zero; an apparently orphaned procedure alone proves no absence. Reset packets are decoded once for room interpretation and supply both the narrow legacy view and the general companion. Loader and reader use the same normalization. This changes no scenario, positive-presence, absence or full-list proof consumer.

Source-directed writes use the existing shared native partition and Copy witnesses. Intersections with descriptor identity, item/callback payloads or script control leave an explicit source failure. Such candidates remain possible but cannot gain current availability from that catalog. This bounded footprint check is not an arbitrary VM-lifetime claim. Ordinary initialized normal-engine trust remains the approved policy; no renderer, DMA or whole-VM theorem was added.

All constructor/reset locations here are byte offsets in the named RDT source, not PS1 RAM offsets or host addresses. Reset is ten bytes: one-byte opcode, slot, kind and SAT followed by three little-endian unsigned 16-bit type/amount/GID operands. The serialized candidate GID domain is 0..255 and registry slots are 0..31. Profile loading additionally enforces the actual stage-selected acquisition bank's capacity and pickup/award isolation. SAT geometry uses mask `0x80`. Descriptor payloads start at constructor offsets +14 for ordinary and +22 for four-point geometry; the corresponding current descriptor pointer starts two bytes into the constructor. No new fixed RAM address is introduced.

A current observation must match descriptor origin, payload geometry, type and freshly read GID. GID can change while type stays equal. Omitting the GID match makes the same physical descriptor publish two acquisition identities as Available. One shared typed observation now carries that identity through availability, scripted dispatch and fresh scenario contradictions. Missing/inactive descriptors, unknown live identities, coherent publication and fresh acquisition precedence keep their existing semantics.

### Complete owned-source consequences

Fresh EXE/resource/source binding covers 69 resources, 125 sources and 54 auxiliary inputs. It retains binding digest `727c49593f3d756594049140e357d8c4c6f47aefdb215d7fd6d0a0a79ed670a8`. The 280 dedicated item creators comprise 276 ordinary `4E` and four four-point `69` records. Other registry creators comprise 310 ordinary/11 four-point doors and 595 ordinary/30 four-point generic descriptors. There are 34 kind2 Reset packets in 20 sources and one existing event award. All 324 unique Copy packets were rebound to the actual owned bytes and the frozen protected-span census, with no protected intersections. This does not discharge other unsupported source/control paths.

Exactly two room/acquisition identities become visible, increasing the raw identity union from 218 to 220. No existing type/quantity union changes, and demonstrated clearance gain is zero.

| Source / acquisition | Actual source records | Result and unresolved boundary |
| --- | --- | --- |
| `03-01/129` | Reset offsets 9770 and 9784, slot 11, type/amount 27/100 and 20/30 | One generic Unknown row. No descriptor creator exists for this slot, so only the explicit NULL alias is cataloged. No current availability or absence follows from the orphan-path lead. Early-bank acquisition still reverses Taken to Unknown. |
| `05-10/46` | Reset 4120, slot 6, type/amount 24/6; real same-slot origins 4790/GID14 and 4974/GID45 | One Unknown row, recognizable from an independent current descriptor. Local conditions require both `1:0==1` and `1:1==1`; preserved whole-source context remains unproved, so neither current flags nor Leon selection establish absence. |
| `00-11/55` | Existing creator 8270 and reset type alternatives 57/61 | Existing known reward remains required before activation, generic when identity is unresolved, with no new clearance. |
| `01-02` event award | Existing award at 8944, collection bank 8 bit 5 | No new acquisition ID or presence rule. Its sufficient condition remains `1:1==0 AND 4:7==0`; mismatching conditions mean Unknown and fresh acquisition wins. |

All existing room fields, doors, floor plans and `candidate_list_complete` flags remain unchanged. Incomplete source lists remain `00-11`, `03-01`, `05-10`. Existing unresolved historical identity still matters after collection. The source-write catalog records ten unsupported sources: `00-02`, `00-16`, `00-19`, `00-1c`, `01-08`, `02-05`, `02-0c`, `02-0d`, `04-02`, `06-03`. The two camera cases are `00-19` and `06-03`; the other eight fail protected source mutation bounds. This increment does not widen any of those proofs. Other revision profiles remain opted out.

### Reproduction and evidence limits

Run the [reset candidate regressions](../../testing/re2.md#reset-candidate-enumeration), with `RE_MAP_RE2_OWNED_CUE` set explicitly. Sixteen synthetic corners vary fresh acquisition, actor guard `6:24`, event flag `4:7` and key banks across all 125 sources. Existing rows, room completion, list flags, doors, pose and exploration compare equal. Only the two added rows differ. Separate controls exercise same-type GID replacement, ordinary/four-point non-item origins, NULL aliases, malformed metadata/source packets, Copy intersections, fresh acquisition clear/set/clear, missing/inactive geometry, fresh Tracker reconstruction and hidden unvisited rooms. These controls are synthetic, not observations of a campaign route.

Against this feature's `83bd4c7` base, parent-supplied read-only RAM from three personal Leon A savestates supplies two observed current sources, `03-08` and `03-0a`. Current-only and two-observed-source scopes are unchanged. The separately simulated 125-source visit scope changes Unknown item rows from 67 to 69, retaining 37 Unknown rooms, 69 Cleared and 19 Incomplete. Every existing item, completion/list flag, door/access state, pose and visit equals baseline in each forward/reverse replay publication and fresh reconstruction. The two added checks account for both extra Unknown rows. These simulated visits are not real history or campaign reachability. `03-08` remains Unknown with four Taken items because identity 185 is ambiguous; that independent issue is outside this increment. The combined parent results below use the subsequently integrated positive-entry feature as their baseline.

New private evidence is durable under `~/.cache/re-map/evidence/2026-11-12-reset-candidates/`: `fresh-input-verification.json`, `all-source-consequences.json`, `before-gid-guard.txt`, `after-gid-guard.txt`, `retained-replay.json`, `retained-replay-comparison.json`, the two full generated room/floor outputs, command scripts and an evidence hash manifest. The frozen research input directory is `~/.cache/re-map/evidence/2026-11-12-reset-completeness-research/`; its handoff, prototype, comparisons and boundary controls were read and hash-verified, then actual source packets were rebound. Lost pre-November-7 temporary RAM/history paths were not reused as fresh evidence. Private bytes remain outside Git.

No UI renderer or layout changed. The RE2 README scene has no committed reproducible publication fixture, and its old retained input was lost. The existing README image remains unchanged; no fresh render or visual validation is claimed. Committed RE1 render fixtures do not reproduce that RE2 scene.

Contributions:

- 2026-11-12; research author `/root/review_partial_positive_entry`, `gpt-6.1-sol`, `xhigh`, native session `01a1cf6f-c5ce-73d2-a762-7f4079bf6417`; frozen read-only reset catalog/consumer research and synthetic boundary controls. Attribution is preserved from its verified executing-model metadata. This is prior research, not a production implementation or independent review of this increment.
- 2026-11-12; implementation agent, `gpt-6.1-sol`, `xhigh`, native session `01a1cfa2-4b74-7e32-90b5-20ecedc543e0`; authored the revision-gated companion, shared normalization, fresh GID guard and regressions; rebound actual owned inputs and ran copied-RAM comparisons. Model identity comes from this session's matching `session_meta` and latest `turn_context`. The parent supplied the copied-save inputs and baseline. Local review checks source binding, scalar/span/origin validation, proof separation, current identity, reversals, other profiles and full corpus consequences. Independent/external review is handled centrally by the parent and is not claimed here.

### Parent review corrections, 2026-11-12

Independent reviewer `audit_leon_a_coverage` identifies two P2 defects, each Low
difficulty. First, native Sleep `09` advances PC by one and executes its embedded
`0A` byte. The candidate compiler protected only the outer opcode, allowing Copy
to rewrite that helper while retaining observable candidates. Root protects the
helper byte separately and retains numeric duration writes. The owned census
finds zero Copy intersections with the helper or duration across 324 Copy packets
and 3,513 Sleep macros. This is a reproduced safety-contract defect, not a
reported mutation in the owned sources.

Second, the loader's acquisition bounds and pickup/award alias check covered
ordinary item records while omitting new Reset-only IDs. A modified late-stage
candidate could load with ID 129 and later hit the reader's pinned-bank assertion;
an early candidate could alias the existing event award at bank 8 bit 5. Root
applies the shared acquisition validation to the mandatory complete normalized
view. Both malformed inputs now fail during profile loading, before polling.
No new candidate is fed into a positive or clearance proof.

Three new regression cases fail on the reviewed implementation. All five controls
pass after correction, including the permitted duration-only Copy and the
already-protected `0B/0C` helper. The combined focused parent run passes 445
tests. The independent reviewer separately runs 840 focused tests and regenerates
all 125 source companions. Its complete review and root's corrections are
retained under `2026-11-12-reset-candidate-final-review/` and
`2026-11-12-reset-candidate-integration/` in the same private evidence root.
Root and the reviewer verify exact executing model `gpt-6.1-sol`, effort `xhigh`.
Neither review nor these synthetic regressions confirm gameplay.

### Combined parent verification

Root integrates the corrected candidate implementation onto positive-entry commit
`f43ff17`. All 7,421 tests pass with the explicit owned CUE. Two complete parent
generations are byte-identical to the integrated room catalog, SHA256
`90dc09af8a5a29a20f821ad50befa581932951330319811fe324a059ba100ceb`.
Both floor outputs remain byte-identical to the baseline artifact. Every prior
catalog field, including all positive-entry additions, is preserved; only the
Reset companions and explicit catalog opt-in are added. Scoped Ruff, formatting,
534 local documentation links and whitespace checks pass.

An independent root comparison checks every existing tracker field across all 15
saved-RAM publications. Only the two added Unknown rows and their room totals
change in the simulated full-source scope. Its Unknown item rows go from 65 to
67, with 35 Unknown rooms unchanged. The actual current-only and two-observed-
source scopes are completely equal. No clearance, door, pose or exploration
change is inferred.

Configured Claude Opus 5.5 is disabled. Gemini 3.8 Flash cannot open its provider
session; neither supplies an external review endorsement. Root verifies the
reported defects directly and performs the corrections and combined checks.
Exact code, generation and replay hashes are in the parent integration manifest.
These results remain offline validation, separate from gameplay and native
savestate restoration.
