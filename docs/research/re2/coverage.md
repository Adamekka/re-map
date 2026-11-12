# RE2 Leon A coverage

[Claim index](../../research.md) · [RE2 support](../../re2.md)

## RE2-COVERAGE-001: complete source inventory exposes remaining tracking gaps

Status: Candidate source inventory and offline saved-state replay, 2026-11-12.
This records a baseline, not campaign completion or new gameplay confirmation.

The target is Resident Evil 2 Dual Shock Ver. USA Disc 1, SLUS-00748, Leon A,
Original/Normal. Executable `SLUS_007.48` SHA256 is
`e576348f64d015ecff6e1ce875a8924ee252ba7f3f9478b0917cbbdeb97db441`.
The baseline room catalog SHA256 is
`304daaa59e9521cdd20a5933e66456bf8396cc8d19a69f083795132364322fa0`;
floor plans are
`641c6362a66333d97d2bfcf6c72d7edb0dcfbfd390a145f7248cc0b06cee2e8b`.
These are the artifacts at commit `83bd4c7`, after the registration and
four-point validation corrections. Later changes need their own comparison.

### Source-wide baseline

All 125 owned RDT sources decode and match their catalog hashes. This establishes
source enumeration, not supported gameplay in every source. The audit evaluates
the catalog's explicit predicate contexts and 16 synthetic reader corners.
Contexts are not claimed reachable in the campaign.

| Scope | Baseline finding |
| --- | --- |
| Item declarations | 280 raw item creators, 218 source-scoped acquisition identities including files |
| Departed item presence | 109 selected ordinary identities lack a presence rule in at least one evaluated context |
| Item identity | 13 selected identities retain scenario/reset type ambiguity |
| Combined item gaps | 110 identities across 57 sources have a presence or identity gap |
| Broader room gaps | 58 sources have an unresolved item, award or candidate-list context |
| All represented acquisitions set | 15 sources can still be Unknown in an evaluated context |
| Incomplete candidate lists | `00-11`, `03-01`, `05-10` |
| Missing Reset candidates | `03-01/129` and `05-10/46` are not enumerated as candidates |
| Door declarations | 321 creators occupying 279 source-scoped AOT slots |
| Legacy departed access | Four creator records covering two slots have conditional Open proofs; 277 slots lack that proof |
| Fresh positive unlock | All 24 keyed creators support a freshly set unlock flag |
| Fresh negative lock | Seven keyed creators across six slots withhold negative locked inference |
| Map bindings | 89 raw door creators lack a shared map marker; two source files have no native outline |

These counts overlap. For example, an ambiguous acquisition can also lack
presence. Missing a departed Open proof does not mean a door is locked. Raw
creators can belong to another scenario or an unreachable script path.

Reset candidates require separate enumeration from positive item declarations.
The narrow existing Reset variant companion does not cover changing acquisition
IDs or unregistered descriptor aliases. Adding those possibilities cannot by
itself establish presence, absence or a complete list. Current observations must
match the fresh acquisition ID as well as descriptor origin and type; otherwise
a same-type Reset can make two different acquisitions appear Available.

The user's approved normal-engine premise now covers
[filtering and presence](scenario-selection.md#positive-presence-policy-extension-2026-11-07)
and [door tracking](immutable-doors.md#normal-engine-policy-extension-for-door-tracking).
It does not turn one capability into another. Source-bound creator, Reset,
scenario, explicit-write and unsafe-path checks remain required, alongside fresh
acquisition and lock flags.

### Access and map placement are separate

An independent reproduction checks native opening selection for all 321 raw
creators against owned `COMMON/DATA/MAPS.PIX`, executable map descriptors and
the committed floor plans. Every existing native marker reproduces exactly.
The 89 missing shared markers have explicit causes: projection beyond the
eight-map-unit placement bound, no native boundary opening, activation-floor
mismatch or missing native outline. Multiple causes can apply to one creator.

Of those 89 creators, 33 belong to the private trusted-door research's supported
access set. That research is a separate Candidate prototype, not an integrated
door result at this baseline. Resolving their access will not establish their
wall placement. The distance bound must not simply be enlarged to manufacture
markers. The two unoutlined sources are `00-1c` and `00-1d`; their campaign
applicability remains separate from their absence in the native map selectors.

### Retained real saves and visit scope

Three existing personal Leon A savestates were copied read-only for offline
replay. Original bytes and modification times remain unchanged. All use save
format version 94. That is a serialization version, not a verified DuckStation
application build. No emulator was launched or native save restoration tested.

Extraction uses the pinned version-94
[header](https://github.com/stenzek/duckstation/blob/1bc5405c417d8f8f61cc5eac624aac9f4b0677eb/src/core/save_state_version.h),
[Bus serialization](https://github.com/stenzek/duckstation/blob/1bc5405c417d8f8f61cc5eac624aac9f4b0677eb/src/core/bus.cpp#L420),
[component order](https://github.com/stenzek/duckstation/blob/1bc5405c417d8f8f61cc5eac624aac9f4b0677eb/src/core/system.cpp)
and [marker serialization](https://github.com/stenzek/duckstation/blob/1bc5405c417d8f8f61cc5eac624aac9f4b0677eb/src/util/state_wrapper.cpp).
The declared compressed payload decompresses successfully to its exact declared
length. Each unique two-MiB RAM window matches all four pinned game-code
witnesses and the Bus/post-RAM/DMA serialization boundaries. The production
reader accepts all three captures.

Only sources `03-08` and `03-0a` are actually observed as current in these saves.
No RE2 visit-history file was available. Current-only replay reveals one source;
an explicit union of the observed current sources reveals two. A separate
125-source visit scope is simulated solely for catalog diagnosis and must not
be described as the user's exploration or a campaign traversal.

In the two `03-08` captures, all four recorded acquisitions are Taken, but the
room remains Unknown with an incomplete identity verdict. ID 185 still admits
types 21 and 25 from creators 10558 and 10584. The raw choice is guarded by bank
1 bit 0, but a valid source-wide scenario proof is still missing. This is a
concrete remaining selection gap. The collected-state behavior follows
[RE2-COLLECT-021](../re2.md#re2-collect-021-collection-flags-remain-separate-from-item-identity);
this audit does not change that rule. The other observed source is Cleared.

The simulated 125-source scope has 67 Unknown item rows and 37 Unknown rooms
in each capture at this baseline. These are hypothetical visit-scope outcomes,
not 67 unresolved items in the user's recorded exploration. Forward/reverse
replay agrees with fresh tracker reconstruction for game-derived fields.
Accumulated region visits are compared separately from completion and access.
The older four-Unknown-row replay was a smaller historical explored-state
subset; its purged temporary inputs are not claimed to have been rerun here.

### Reproduction and evidence

Private evidence is retained outside Git under
`/Users/adamekka/.cache/re-map/evidence/`:

- `2026-11-12-leon-a-coverage/` contains the 125-source inventory, all predicate
  contexts, 16 synthetic reader corners, diagnostics and SHA256 manifest.
- `2026-11-12-map-gap-research/` contains `audit_map_gaps.py`, the complete
  creator-to-opening comparison and its SHA256 manifest.
- `2026-11-12-leon-a-save-replay/` contains original-copy hashes, extracted RAM
  hashes, pinned serializer sources, `extract_v94.py`, `replay.py`, the complete
  baseline report and SHA256 manifest. Saves, RAM and owned game assets are not
  committed or redistributed.

From the checkout, use `PYTHONPATH=src:tools` and the verification Python with
the repository's development requirements. Run `audit_map_gaps.py` to reproduce
the marker comparison. Run `extract_v94.py` with explicit `--cue`, `--profile`,
`--sav`, `--ram` and `--report` paths for each copied state. Then run `replay.py
--checkout <checkout> --output <report.json>` to reproduce all three explicit
visit scopes and reverse/fresh reconstruction checks. The private scripts bind
the recorded personal inputs; they are not production fallbacks or public game
fixtures. Their manifests identify all dependent inputs and hashes.

Contribution, 2026-11-12: the human requests complete Leon A room, door and item
coverage and supplies the normal-engine policy extensions. Codex
`audit_leon_a_coverage` authors the source inventory and synthetic controls.
`review_partial_positive_entry` investigates Reset candidates and the fresh-GID
migration guard. Root independently checks the inventory hashes, reproduces
all marker outcomes, extracts and verifies the real saves, runs the saved-state
reader/reconstruction checks and writes this record. All three executing
sessions verify exact model `gpt-6.1-sol`, effort `xhigh`. Source inspection,
copied native execution, synthetic controls, saved-RAM replay and gameplay
confirmation remain distinct. No external review endorsement is claimed.
