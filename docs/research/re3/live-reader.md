# RE3 live current-room reader

## RE3-LIVE-001: bounded Hard current-room and pose observations

Status: Candidate revision-bound reader for Resident Evil 3: Nemesis, PS1, NTSC-U, SLUS-00923. `games.re3.live_reader.read_current_room` returns a fresh current-room/pose observation or a modeled failure. It does not mutate a tracker, exploration history, items, doors, completion or map visibility. No RE3 profile is registered in the application yet.

The executable SHA256 is `2e143418e358b2c99995cdc1a88c387163fb751912c723b755614f38e236bd29`. Native validation uses DuckStation `0.1-12083-g00e299795`, binary SHA256 `5c879677051cfb173002df22baee741c96fa8071c6fe1dd7e5454092bf128173`, native-state version 87. The human supplied owned media and selected Hard. Easy is used only as an opposite-difficulty control.

### Required revision and source binding

Call `bind_source_catalog(executable_bytes, sources)` with the complete owned corpus as a tuple of `RoomSource` records. Missing or modified inputs return `RoomFormatFailure`; there are no fixture defaults or partial-catalog live fallback. Binding verifies the complete executable hash, native stage/file-table size and LBA, all 169 source identities, unique selectors/paths and conservative witness ambiguity. The normalized source-manifest digest is `2e044734044d39327bdfabcb40c81a6f51e4f97f9859f0609e36217ce5fadaba`.

`SourceCatalog` retains an immutable selector index and runtime signature. Its validated receipt binds every compiled witness field and the signature. Copying a catalog with changed sources, camera bytes, header words, camera count or revision signature raises an assertion for programmer error. Checking only the raw RDT hash would leave those derived fields replaceable.

Witness constructors also require exact immutable `bytes` for camera/zone data, a tuple of exact integer section words and exact integer native fields. Value equality alone accepts a mutable `bytearray` or `memoryview` equal to the original bytes. Changing its backing storage after an equality-only catalog check could otherwise change the expected source without changing the owned RDT. Bound and unbound witness constructors reject these programmer errors before a catalog can retain them. Parsing unsupported external source data still returns the existing modeled failures.

The diagnostic `compile_source_witness` and `bind_diagnostic_sources` APIs can inspect a partial corpus but cannot construct a live catalog. The existing offline `re3_native_contracts.audit_capture` uses these shared source formulas and still reports campaign/Hard admission as unresolved. It retains its original diagnostic output and rejection semantics.

Each poll verifies four 32-byte revision windows at PS1 virtual `0x80011B80`, `0x80020000`, `0x80040000` and `0x80060000`. It selects one source using signed native selectors, then checks prefix bytes 1..7, relocated header words 0..20, every camera record and the complete bounded camera-zone section. Native relocation includes opaque word 2 and adds the base to camera-mask words even when originally zero. Prefix byte 0 and header word 21 are mutable work fields. Mutable SCD bytes are not silently treated as immutable.

The conservative ambiguity key excludes opaque word 2, whose unrestricted value can wrap to relocated zero, and does not use a longer zone extent to distinguish a source from its shorter prefix. All 169 owned sources remain distinct. The full extracted RDT must fit at an aligned cached-main-RAM base; this is not an independent malloc-extent or arbitrary-pointer proof.

Source-parser failures report file-byte offsets. A `source-binding` range failure instead reports the rejected PS1 virtual base; a selector failure uses argument offset zero. The live reader presents their diagnostic text without interpreting one address space as another.

### Native state contract

All following addresses are cached PS1 virtual addresses; multibyte fields are little endian. Native ordinary-engine execution and the backend's coherent contiguous RAM reads are the supported domain. Corrupted saves, modified game code and arbitrary ABA behavior are outside that domain.

| Field | Width and supported value |
| --- | --- |
| Lifecycle `0x800CC858` | u32: world `0x08000000` set; recorded input `0x10000000`, pending load `0x00400000`, Easy `0x100`, alternate `0x80` and update bypass `0x600` clear |
| Saved difficulty `0x800D1F30` | u32 mask `1` clear; both difficulty bits set means Easy; a mixed pair means initialization/Retry |
| Native additional mode `0x800C79CC` | u32, full mask, zero; other initializer domains are unsupported |
| Ingress phase `0x800C7960` | u8, full mask, zero |
| Interface/pause `0x800E01E7` / `0x800D4434` | u8, full masks, zero; stale interface-view bytes are not gates |
| Control `0x800CCBA0` / `0x800CCBA4` | u32 masks `0x81000000` / `0x40000000` clear |
| Player owner `0x800CCD94` | u32, full mask, `0x800CCBC4` |
| Primary routine `0x800CCBC8` / actor update `0x800CCC0A` | u8 equals 1 / u16 mask `0x8000` clear |
| Stage/room/camera `0x800D1F76` / `0x800D1F78` / `0x800D1F7A` | i16 selectors resolve to the selected source; camera in range |
| Source/allocation `0x800CC86C` / `0x800CC870` | u32, full masks, equal and aligned; source witnesses must also match |
| Position `0x800CCBF8` / `0x800CCBFC` / `0x800CCC00` | Three i32 raw coordinates from one grouped pose read |
| Facing `0x800CCC32` / actor floor `0x800CCBCD` | u16 / i8 raw outputs; actor floor is not an established physical map layer |

Cold initialization loads before publishing world ownership at original `0x80024884`. Ordinary ingress publishes a new source base at `0x80049448` before loading finishes. Its pending-bit/phase completion path is distinct from source-byte agreement. Retained pending captures already have plausible player/source/Hard fields, so the phase and pending gates are required. The native roles and original windows are retained in the implementation handoff below, with earlier observations in [RE3-NATIVE-001..005](native-contracts.md) and [RE3-INPUT-002..008](hard-start.md).

Capacity 8, lifecycle bit `0x1000`, health ranges, current work pointer and a sampled caller are not readiness heuristics. The failed INPUT007 bootstrap remains memory-compatible despite health zero. Its capture provenance is unqualified; it is not a proven noncampaign counterexample, and no invented health range excludes it.

### Coherence and result behavior

The supplied memory reader must honor bounded contiguous reads. Initial order is selector/mode block `0x800D1F2C`, 80 bytes, **before** pose/world block `0x800CC830`, 1384 bytes; then phase/mode block `0x800C7960`, 112 bytes, interface and pause bytes. Read the selected source witnesses, repeat those witnesses in reverse order, then repeat the guard blocks in reverse order.

Compare all consumed source bytes and the lifecycle/mode/owner/selector/source/floor signature. Do not require XYZ or facing to remain stationary between the two sweeps. The initial contiguous pose block supplies those outputs. Reading selectors first prevents an old pose from being paired with a new room/source after a complete transition reuses the same source address. A regression reproduces that ordering hazard.

The current corpus uses 22 memory requests per accepted poll and at most 8026 payload bytes, including revision and repeated source witnesses. No request exceeds 4096 bytes. Source lookup is indexed; polling neither reads full RAM nor scans all 169 sources. No execute breakpoint or per-poll pause is imposed.

Every poll rereads mode, lifecycle, source and pose. It carries no Hard latch, source-address cache or historical caller capability over restoration or reconnect. Read/short-reply failures return `ReadFailure`; wrong revision returns `WrongGame`; unsupported mode/source returns `UnsupportedSettings`/`UnsupportedRoom`; inactive world, recorded input, interface, pause or filtered control returns `NonGameplay`; loading, transient ownership or inconsistent reads return `Retry`. Only the full contract returns `CurrentRoomObservation`.

### Private live validation

An isolated instance ran the reader while the guest was running, without per-poll interrupts or execute callbacks. The settled Hard checkpoint supplied a fixed position; native Right changed facing without translation. Final constructor-fixed source code and unchanged reader code were frozen separately from the earlier version.

| Target rate | Accepted Hard samples, stationary plus turning | Stationary / turning p95 poll time | Turning maximum |
| --- | --- | --- | --- |
| 10 Hz | 100 / 100 | 29.09 / 28.68 ms | 29.41 ms |
| 20 Hz | 200 / 200 | 24.43 / 23.52 ms | 24.51 ms |
| 30 Hz | 300 / 300 | 21.73 / 24.70 ms | 60.84 ms |

Each condition ran for five seconds per rate. All 600 Hard observations succeeded with zero Retry/read failures. One turning 30 Hz poll exceeded its 33.3 ms interval; these measurements establish best-effort cadence on this host, not a deadline guarantee. The earlier Hard seed progressed under no requested input and later left admitted gameplay; its intervals remain recorded and are not described as stationary validation. No cause or extra health/mode gate is inferred from that sequence.

Five native F1 restorations matched full 2 MiB RAM, GPR0..31, HI/LO, PC and 1024-byte scratchpad before experimental resume. They do not compare every serialized device field. Hard R10D to Easy R10D, and ordinary Hard R101 to Easy R10D and back, all reused base `0x8011A708`. The fresh reader immediately returned the proper Hard observation or Easy `UnsupportedSettings`; source identity was rebound rather than inferred from pointer equality. Easy rejected all 360 running samples at 10/20/30 Hz in the earlier snapshot. The fixed constructor was then exercised by fresh catalog binding and the later reversals.

The final five input words and native Pad pressed mask were zero. Native F2 created a new private checkpoint, SHA256 `fd38cb3e033053cf411d6830dad8adb29a4689862f1bfc22d5f85e859d6b9ec6`; it was not restored. This adds no memory-card persistence claim. No guest memory/code patches, items, visits, routes or history were written. Both clients closed, the owned PID 41778 exited with wrapper status zero, port 2393 was freed, and CUA completion was recorded once. Root independently observed that PID absent and the port bindable. Disabled achievements/integration in both namespaces, private paths, muted/black output, absent accounts/overrides, no cards and no patches were checked before loads and during cleanup.

Private evidence is `/var/folders/9d/q5n746z953bcs654g_1sqcy80000gn/T/re-map-re3-live-validation-20261106-fbu05ckf/`. Report SHA256 is `6c158cab9d6da5d455bfe7a8a22a689ccda34189421a5db52fdd178f21e69b13`, `verification.json` is `9c04a16e7ad74935a745029608096b7ca508b5ce31f088d7850c8cd0d8398634`, and the 269-file artifact manifest is `0b7c03b9c4009a77c03cfed13c183626dbcd1e19221c2de1186012b82d655616`. To recompute metrics without changing frozen files, copy the benchmark/restore JSON and `verify_results.py` into a fresh directory, preserving its `v2` layout, then run that copy. Root verified all 269 artifact hashes and reproduced the verifier result in a separate output directory. Root's integration record is `/var/folders/9d/q5n746z953bcs654g_1sqcy80000gn/T/re-map-re3-live-root-20261106-u_3_v29j/integration-review.json`, SHA256 `bf64f88f19fc588b37decaa5e0a90e9b9945bcc1345aec6cf39b4bfe57679b07`.

This validates bounded source/mode/pose observations in the tested situations. It does not establish full campaign readiness, item/door interpretation, physical room outlines, arbitrary ABA exclusion or an API that owns the user's pause/resume state.

### Reproduction and review

The read-only source/contract handoff is `/var/folders/9d/q5n746z953bcs654g_1sqcy80000gn/T/re-map-re3-admission-composition-20261106-nw5njgci/`. Its `contract.md` has SHA256 `35a2e8903b133212b53dc0444fad1c628cfcc1a04c128d9f7ad9662fa90fee5f`; manifest SHA256 is `bd6a9f778ff145638bf5e68e2c4e8657a1479e1d71f63c0870c6f03c73a0efa7`. The frozen handoff's live pose/order recommendation was corrected during independent review as described above; frozen files remain unchanged.

Current-code source integration is `/tmp/re-map-re3-source-witness-integration-20261106-62_i5n6f/verify.py`, with report SHA256 `96aa81fa17fafcb359b65855c74899c39a4f692726fe9b3c6f2a8db655f51a19`. It preserves original dependencies separately from the extraction's current code version. All 54 archived classifications remain byte-identical, SHA256 `e2c5d021e9b8889a3e1b0794c739e8b4dce337f306677dad47521a45ae5f5d5a`: 16 prior and three INPUT007 images are compatible; all 14 Easy images reject. These counts include duplicate/paused images and are not 54 independent gameplay situations or 169 runtime-tested rooms.

Root's initial real-catalog reader replay is `/var/folders/9d/q5n746z953bcs654g_1sqcy80000gn/T/re-map-re3-reader-replay-20261106-nojxmhks/verification.json`, SHA256 `4a9ed0eeeead81ddf23a58f9a6ffe68feb582f081979b4f88595f51f67384572`. It checks the actual reader against the same 54 captures and complete 169-source binding. This archived replay does not measure a running transport.

Synthetic regressions cover every request's failure/short reply, all revision windows, native rejection gates, source mutation, source reuse across a transition, moving pose, Hard/Easy reversal, witness chunking and constructor replacement. The constructor regressions failed before the immutable-receipt fix and pass afterward. No copyrighted assets, raw RAM or new saves are added to Git.

The final full Python suite passes 6803 tests; the focused reader/source/audit set passes 176. Scoped Ruff lint/formatting, whitespace and 331 local documentation links pass. No UI changed, so the README screenshots are unchanged.

- 2026-11-06 UTC; Codex root, exact verified model `gpt-6.1-sol`, effort `xhigh`, authored the live reader, regressions and this document. An investigator using the same verified model/effort authored the frozen native contract and shared source extraction. Original human/media and earlier research authorship remain unchanged.
- 2026-11-06 UTC; independent reviewer, exact verified model `gpt-6.1-sol`, effort `xhigh`, reproduced the archived matrix, identified the pose/order issue, reviewed all six implementation/test files and reproduced the constructor gap. Follow-up verified all five replacement variants reject and unchanged copies still work, with 176 focused tests passing and no remaining supported findings. This was source/test review, not live execution.
- 2026-11-06 UTC; private native validator, exact verified model `gpt-6.1-sol`, effort `xhigh`, prepared the isolated instance, proved the five restorations, measured both source-code versions and the six final Hard cadence conditions, recorded Easy reversals and completed cleanup. It operated no user history, performed no new route/ingress experiment and stopped after this bounded validation. Root independently checked the frozen files, code hashes, metrics and process/port cleanup without rerunning gameplay.
- 2026-11-06 UTC; external snapshot reviewer, `gemini-3.8-flash`, high reasoning through Antigravity, returned no findings on the final reader, shared source binder/audit, synthetic tests/fixture, revision interface, documentation, pinned native windows and selected live validation records. Review covered source/constructor invariants, coherence, lifecycle/failure handling, restore freshness, performance, test meaning, shared logic and evidence limits. The snapshot abbreviated unchanged format bounds, retained only final-version benchmark rows and selected controller sections, and omitted full raw artifacts and internal review conclusions. The completed response had no tool attempts or pending child work. This advisory review adds no runtime validation. Claude Opus 5.5 remained disabled and supplied no review.

Constructor correction, 2026-11-07 UTC: independent reviewer `review_re3_rows`, exact verified model `gpt-6.1-sol`, effort `xhigh`, reproduces a P2 immutable-witness defect, Low/Medium difficulty, for both cameras and zones. A value-equal mutable buffer passed the earlier seal; after changing that buffer and the corresponding loaded bytes, the copied catalog accepted a source that the original catalog rejected. Codex root, the same exact runtime model/effort, adds mandatory witness type checks and 14 regressions covering both buffer forms, unbound compilation, numeric aliases and section-word mutability. Existing relocation, bounds, ambiguity and failure formulas remain unchanged. All 198 focused source/current-reader/map-position checks pass. An isolated tracked export containing only this three-file correction passes all 6884 Python tests in 133.99 seconds, with the separate collectible API excluded. This source/type correction adds no native gameplay observation or broader admission claim.

External constructor-fix review, 2026-11-07 UTC: `gemini-3.8-flash`, high reasoning through Antigravity, returns No findings on the complete source-witness module, complete source tests, exact fix diff, unchanged consuming source sweep and isolated verification summary. The completed response has no pending child work or tool attempts. Review covers immutable/type invariants, correctness, modeled failures, compatibility, tests, maintenance and scope. Claude Opus 5.5 remains disabled and supplies no review. This review adds no runtime observation.

## RE3-LIVE-002: fresh native map position under current-room guards

Status: Candidate for the same Resident Evil 3: Nemesis, PS1, NTSC-U, SLUS-00923 executable and Hard domain as RE3-LIVE-001. This increment returns numeric native map position alongside the admitted room observation. Physical floors, selected geometry, room ownership, items, doors and tracker exploration remain unresolved. It registers no application profile.

### Shared source and projection

Compile explicit owned MAP and executable bytes with `games.re3.map_data.compile_map_position_layout`. Format or executable failures return `RoomFormatFailure`. The result is immutable, and its receipt binds every compiled row count, anchor, layer field, ordered remap and identity hash. Copies with modified derived data assert as programmer errors. Polling reuses the compiled data.

`resolve_native_map_position(layout, context)` accepts a required `MapPositionContext` containing source selectors, initial X/Z and facing, system flags, three remap/layer flag words and the previous identifier. The existing snapshot API `decode_native_map_position` now calls this shared evaluator and retains its JSON schema, failure offsets and projection behavior. Ordered remaps, early returns, raw-stage folding, signed wrapping, division toward zero, heading and numeric layer selection still have one implementation. See [RE3-MAP-003/004](map-semantics.md#re3-map-004-native-room-remapping-and-position-projection) for native semantics.

The live API `games.re3.live_reader.read_current_map_position(catalog, layout, read_memory)` additionally requires the exact executable SHA256 above and MAP_U SHA256 `7182beb90347fe4ea0c2a4db30dff93aaee88b8ef1b633398ffcef6f3d3d1268`, the owned resource documented in [RE3-ROOM-004](room-format.md#re3-room-004-native-map-resource-directories). Another valid diagnostic layout returns `UnsupportedSettings` before transport access. There is no fixture or alternate-resource fallback.

### Fresh context and one guarded read

Eight retained ordinary-gameplay captures have stale cached map bytes AA/AB/AC at PS1 virtual `0x800E026A..0x800E026C`, all zero. The fresh source-derived row in seven of those captures is one. Two earlier map-menu captures initialize the expected current row, but menu admission is `NonGameplay`. The live API therefore derives its map context from source selectors and world state, without reading those UI caches or assuming the browsed group belongs to the current source.

The shared current-room reader inserts a 72-byte contiguous read at PS1 virtual `0x800D1F7C` after initial selectors and before the initial pose block. It repeats that span in the reverse final sweep and compares these little-endian fields:

| Field | Address / width / compared mask |
| --- | --- |
| Previous identifier | `0x800D1F7C`, u16, `0xFFFF` |
| Position remap flag | `0x800D1FB8`, u32, `0x00800000` |
| Layer override flag | `0x800D1FBC`, u32, `0x00004000` |
| Story remap flag | `0x800D1FC0`, u32, `0x00000001` |

The existing source, lifecycle, difficulty, ownership, selector and raw actor-floor guards remain mandatory. A changed consumed map field returns `Retry`. Unrelated bits do not block the observation. The first contiguous pose block supplies both room and projected position; normal movement does not require stationary X/Z or facing. The result performs no later independent map-state read. The room-only API retains its original read spans and result type.

`CurrentMapObservation` contains a `CurrentRoomObservation` and `NativeMapPosition`. The latter keeps source stage/room, canonical native group/row, numeric record/layer, projected X/Y, heading, anchor and source hashes distinct. An unavailable projection row or layer returns `UnsupportedRoom`. All existing modeled read and admission failures propagate. Earlier saves and Easy/Hard changes are reread without cached admission or map state.

The numeric layer is not a physical floor identifier. Retained raw actor floors 1, 2 and 4 all resolve to native layer zero in one source, although its original shape rules select different geometry. This API supplies no geometry-selection or room-area ownership fact and must not collapse those observations into one tracker floor or reveal an aliased source.

### Verification and limits

The owned-source replay is `/tmp/re-map-current-position-20261107-final/verification.json`, SHA256 `4fc46a603f536075403ab31483f99542d3147f63a59f4f0c2275fc29636899a8`. Its adjacent `verify.py`, SHA256 `034194ffd4e2e41886b4fb639343966de4c1118afafe9a90f10d8fa42733d410`, rebuilds the complete 169-source catalog from owned media, checks pinned executable/MAP and retained-capture hashes, compares the old snapshot decoder from the fixed baseline commit `abf271ade52261f2bcdc7af1dce734584eb490df`, and checks current code hashes before and after execution. It requires a new output directory. Earlier verifier drafts remain unchanged.

All 245 generated source/remap contexts produce identical old/new diagnostic results. These are decoder inputs, not demonstrated reachable campaign states. All 54 earlier capture classifications remain unchanged. Ten further retained evaluations contain eight admitted current-room/map observations and two rejected map-menu controls. The combined 64 evaluations accept 27 observations, including repeated files and unqualified capture provenance from RE3-LIVE-001; they are not 27 new independent gameplay situations.

Accepted reads use 24 memory requests and at most 8170 payload bytes, 144 more than the room-only API. Requests remain bounded by 4096 bytes. [RE3-MAP-013](map-semantics.md#re3-map-013-native-current-row-draws-distinguish-two-r101-features) subsequently compares the API with original native drawing in two restored states of one source. These paused samples add no running-transport cadence measurement. RE3-LIVE-001's live timing measurements apply to its room-only API.

Synthetic tests exercise every request's failure and short reply, stale UI caches, each additional guard field, unrelated bits, initial moving pose, earlier restoration, Easy reversal, pinned resource rejection, missing projection rows, compiler reuse and copied-layout invariants. The focused three-file suite passes 213 tests; the complete RE3 test set passes 2090. The full Python suite passes 6870 tests with source/test hashes unchanged, retained in `/tmp/re-map-current-position-full-suite-final-20261107/`. Scoped Ruff lint, formatting, whitespace and 335 local documentation links pass. No UI changed, so README screenshots are unchanged.

- 2026-11-07; Codex root, exact verified model `gpt-6.1-sol`, effort `xhigh`, authored the shared typed evaluator, guarded map-position API, regressions, retained replay and this claim. A separate investigator using the same verified model/effort identified the stale UI caches, source aliases and geometry-selection limits in `/tmp/re-map-re3-map-ownership-20261107-crm26a4j/handoff.md`, SHA256 `25893bf49446e3181cd763fbe73aa5625ac84cdfd2ca4cb8580c476cb341860c`. Its observations were retained-file interpretation and original-source inspection, without new gameplay. Earlier authorship remains unchanged.
- 2026-11-07; independent reviewer, exact verified model `gpt-6.1-sol`, effort `xhigh`, checked source/configuration and constructor binding, native arithmetic, shared logic, read order/coherence, restoration, failures, tests and evidence limits. It reproduced 1996 identical old/new diagnostic cases: 54 archived captures, 1792 selector pairs and 150 remap/flag/previous/alternate/32-bit-boundary contexts. It passed 213 focused tests and found the private verifier's baseline incorrectly followed current HEAD. That reproducibility defect was corrected to the pinned commit before the final replay. No supported production finding remained. The review report is `/tmp/re-map-re3-live-map-review-20261107-lmfb84tf/final-review.json`, SHA256 `b1b8378c5ad027d4a05db433618a7d3da1fffcb8bb419511f04986272a9e132a`.
- 2026-11-07; external snapshot reviewer `gemini-3.8-flash`, high reasoning through Antigravity, checked the full changed source, new and existing tests, prior projection implementation, unchanged catalog/runtime/parser interfaces, the new claim and retained replay summary. Its test-clarity suggestion was applied: the fully masked previous identifier explicitly retains its initial value in the unchanged-field case. Root verified the suggestions against the admission contract; no supported production defect remained. The final delta also restores the original heading comments. Final focused checks and owned-source replay passed afterward. The returned review is `/tmp/re-map-current-position-external-20261107.json`, SHA256 `947c3f3dcb931a67af70ad36d538944d0a8523bcc0c9b4e55bd7e5bc32a14c0d`. This advisory review adds no runtime validation. Claude Opus 5.5 remained disabled and supplied no review.

## RE3-LIVE-003: original attract playback remains rejected after world publication

Status: Candidate. One new original-engine negative control for Resident Evil 3:
Nemesis, PlayStation, NTSC-U, SLUS-00923, supplied revision. Executable
`SLUS_009.23` SHA256 remains
`2e143418e358b2c99995cdc1a88c387163fb751912c723b755614f38e236bd29`.
The separate private instance uses DuckStation `0.1-12640-gbb4e9ac5e`, binary
SHA256 `ddceaaa426e67e328430fcb916320803fddc014374ea45a00778e58081f36dcb`.
It cold-boots the original disc without a seed, save or restoration. The agent
sends no controller input and uses no CUA. This does not select Hard or start
a campaign.

### Original publishers and recorded input

All game addresses below are cached PS1 virtual addresses. Multibyte fields
are little endian. Source offsets are relative to the complete owned packet;
capture offsets subtract `0x80000000` from a virtual address.

| Original instruction address | Field and width | Observed before/after |
| --- | --- | --- |
| `0x801967DC`, SW | Lifecycle `0x800CC858`, u32 | `0x20000000` to `0x30000000`; recorded mask `0x10000000` becomes set |
| `0x80024884`, SW | Same lifecycle u32 | `0x30000000` to `0x38000000`; world mask `0x08000000` becomes set while recorded phase remains zero |
| `0x800248B0`, SB | Recorded phase `0x800C79AE`, u8 | zero to one |
| `0x80038418`, SW | Recorded index `0x800C79B0`, u32 | zero to one |
| `0x8003841C`, SH | Raw input `0x800CC830`, low u16 | zero written over existing zero; no input-value transition |

Recorded phase is separate from ingress phase at `0x800C7960` and signed actor
floor at `0x800CCBCD`. The unchanged public reader returns `NonGameplay` at all
11 named coherent stops, including world-set/recorded-phase-zero and later
recorded-phase-one states. Native source auditing independently retains the
recorded-input rejection; campaign admission and Hard identity remain
`unresolved`. No new guard or readiness rule follows.

The fresh source pointer at `0x800C79A8`, u32, is `0x80192000`. All 3,620 bytes
match owned `CD_DATA/ETC/PDEMO00.DAT`, native file index 65, ISO LBA 9534, SHA256
`4846be41d32c20718ad10b0ea2b5e8f1f7bf44dd0e174a203d33e3b49ecb006f`.
Its length at source offset `0x71A`, u16, is 815. Before original LHU at
`0x80038410`, index zero selects u16 at source offset `0x71C`, virtual
`0x8019271C`. That bounded word is zero and equals V1 after the original
load-delay instruction. The later index store is observed separately. The
comparison uses the pre-LHU word, not the incremented index. V1 and raw input
were already zero, so this does not demonstrate a nonzero recorded-input
transition.

### Coherence, source scope and cleanup

Each named capture brackets a paused full 2 MiB read with identical consumed
fields, GPR0..31, HI/LO, PC, source/code witnesses and public-reader results.
Address-free stepping follows the original instructions without guest writes,
patches, stubs or PC repair. Each of the five store pairs equals its original
store prediction across the full 2 MiB RAM. This compares RAM, not all
serialized devices. The 11 stops contain eight distinct RAM payloads within
one episode; they are not 11 independent gameplay situations.

All 169 owned sources compile offline. After world loading the unchanged
header/camera/zone witnesses bind `CD_DATA/STAGE1/R103.ARD`, RDT SHA256
`d0bd104f6798ef8277d417b71b715cb0e31fcd309d0e0430318e021eb851ca4e`.
This does not establish full immutable script identity or the allocation
extent. Reused overlay addresses after
loading are not interpreted as TITLE code.

Both achievement namespaces, hardcore and integration are disabled before
loading; cards, accounts, cheats, patches and game overrides are absent.
Audio is muted and the private black shader is active. Exact private
binary/config/argv, portable-source branch, log location, shader and PID-owned
port corroborate isolation. This build does not print a literal DataRoot field;
that missing log receipt is preserved.

All owned execute callbacks are removed before the sole client closes with
exit zero. The still-owned wrapper processes the explicit completion request,
reaps its child with exit zero after 570.68 host seconds, and verifies port
2461 bindable before its 900-second watchdog. Native observations end at epoch
14, PC `0x80038420`. Execution after the last coherent capture, including
disconnect and teardown, remains unobserved.

On orderly exit DuckStation removes the empty Hotkeys section and adds four UI
geometry keys. The first strict post-exit settings check fails and remains in
evidence. The final offline comparison requires every original actual
configuration key/value unchanged and exactly those serialization differences.
Neither settings nor reviewed runtime checks are repaired or relaxed.

### Reproduction and contribution

Private evidence is
`~/.cache/re-map/evidence/2026-11-15-re3-attract-preflight/`.
`native-reproduction.json` gives the exact offline command with a new output
path. Run only `verify_native.py`; never rerun a completed launch/controller
or signal its historical PID. The verifier binds the named captures, reviewed
runtime files, explicit RE3/shared code and owned inputs, prohibits fixture
opens, and checks the port without changing another process.

`native-handoff.json` SHA256 is
`aa1e0a2172678d03f45df6201818b98e29532d07fef678976a95f1a03a9aac64`.
The two byte-identical final verification reports have SHA256
`ac8e34f25d692264f9bbd5fa246ed6e9a835515c1f523227bbb887271d4266cf`.
`native-final-manifest.json`, SHA256
`a5c3a81a97f08d18ca582280df989d9d106c1520a8ca92f3839bf2e4054f100a`,
binds 55 named evidence files and four private runtime resources. Root's fresh
offline run produces the identical report and verifies this explicit manifest.
It uses no emulator and opens no fixture content.

2026-11-15 UTC contributions: native investigator `gpt-6.1-sol`, effort
`xhigh`, session `01a1dfd0-5c8b-7372-804c-cd98fb34c563`, turn
`01a1e01a-ef86-7fd3-b6dd-b60e3c2d8f8c`, performs the episode, cleanup and
bounded offline verification. Codex root, the same verified model/effort,
reviews and corrects the private setup before launch, independently reproduces
the frozen native report, and writes this contribution. Earlier authorship
and human Hard selection remain separate. This adds no positive Hard/campaign
admission, exploration, physical-floor ownership, item/door completion or
production-profile readiness.

The completed external snapshot review requested `gemini-3.8-flash` at high
reasoning effort through Antigravity and returned no findings, with no tools
or pending child work. It checked the complete new verifier/controller/isolation
scripts, wrapper, native result report and cleanup/settings receipts, plus the
unchanged public reader transaction and debugger request/stepping methods.
Snapshot SHA256 is
`f2fa82307f58a1842a3e2a3900d966efcf46f146abaf27b4a4a6a95ed078c044`.
The returned model field names `gemini-3.8-flash`; the separate executed-model
field is unavailable. Claude Opus 5.5 remains disabled and supplies no review.
This advisory source/evidence review performs no native execution. Root review
and the rejected whole-file comparison assumption remain under
`~/.cache/re-map/evidence/2026-11-15-re3-attract-evidence-review/`.
