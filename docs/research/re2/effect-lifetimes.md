# RE2 effect resource lifetimes

[Claim index](../../research.md) · [Room completion](../../room-completion.md) · [Startup declarations](startup-declarations.md)

## RE2-EFFECT-001: immediate effect execution does not establish a room lifetime

2026-11-06. Status: Candidate for Resident Evil 2 Dual Shock Ver., USA Disc 1, SLUS-00748, Leon A, Original/Normal. Copied original instructions establish bounded effect creation, clearing and resource-binding components under explicit premises. They do not establish a complete source lifetime or authorize another item exclusion. No production code, generated catalog or tracker outcome changes.

### Tracking failure and exact inputs

The retained 58-visit replay still reports acquisition ID 24 in source `01-13` as Unknown. Both source creators, offsets 3778 and 3804, require bank 1 bit 1 set; the selected fixed context requires it clear. The independent ID 253 is Taken. A qualified exclusion could resolve the room, but the real `scenario_entry_scope` factory rejects opcode `0x64` at offset 3908 in `17:3`. Skipping that guard is not an exclusion proof. Source control, incoming door work, resource initialization and deferred effect writes remain separate obligations.

Owned executable `SLUS_007.48` is 987136 bytes, SHA256 `e576348f64d015ecff6e1ce875a8924ee252ba7f3f9478b0917cbbdeb97db441`. Owned `PL0/RDT/ROOM2130.RDT` is 139448 bytes, SHA256 `78227d7aac8266feccc018668ad6b25893e60fc30012fbd464977d00fc254ba1`. Source offsets below are zero-based file bytes. Addresses are PS1 virtual addresses. Numeric memory is little endian; bytes use mask `0xFF`, halfwords `0xFFFF` and words/pointers `0xFFFFFFFF`, unless stated otherwise. These are owned-source and isolated CPU checks, with no new DuckStation session or tested gameplay observation.

The replay uses the previously retained RAM SHA256 `939264d8e98c07e0d7afcdef69efdf1e18ac4fa05052575d726022b5dfdd8b73` and copied visits SHA256 `3d8b4240e2a63d4c873d805304a77060e81d548e01690029dade132f4fd04d97`. It reconstructs results with the production reader, without importing old item, door or completion verdicts. The initial matrix was made at `082dd974eb77dab3a40798ed9928bd3b124fe43f`; later RE3 documentation commits do not change that implementation.

### Immediate native operations

The actual source has fourteen `0x64` packets and nine `0x65` packets. Every `0x64` requests resource 22 with matrix selectors zero/zero. The resolver therefore uses fixed matrix `0x8009DB44`, independently of the selected actor Work pointer. Subtype selection uses packet byte 3 masked with 7, including raw `0x10` selecting group zero. Resource, directory and animation bounds still require their own initialized bindings.

| Copied original component, end exclusive | Scope of retained execution |
| --- | --- |
| `0x64` handler `[0x80056644,0x800566F0)`, resolver `[0x80056A38,0x80056B8C)`, allocator `[0x8001C8C4,0x8001CBE8)` | 168 complete calls, fourteen actual packets with owned/minimum/maximum i16 coordinates and a full pool or one free record at index 0/47/95 |
| `0x65` handler `[0x800568E8,0x80056930)`, clear helper `[0x8001CFBC,0x8001CFFC)` | 36 complete calls, nine actual packets with none/all/edge/alternating matching records |
| Resource binder `[0x8001BCA0,0x8001BD38)` | One complete call with explicitly supplied relocated source and empty previous-local cache |
| Parent reset/binding `[0x8001BBA4,0x8001BC88)` | 67 bounded slices, stopping before texture upload and retaining the parent's stack frame |
| Texture fixup tail `[0x8001BE4C,0x8001BEBC)` with original pure helpers `[0x8008F7EC,0x8008F840)` | One separate bounded block with supplied predecessor rectangle coordinates; not a complete upload or a continuation of the prior slices |

The fixed effect pool is `[0x800D8CF0,0x800DBB70)`, 96 records of `0x7C` bytes. Clear matches the record's ID byte at `+0x1D` and zeros its bytes `+0/+1` and halfword `+0x18`. Creation controls independently predict the entire allocated record, task-PC advance of 16 and continuation result 1; clearing advances by two. Complete calls restore SP and saved registers. Every case compares the full 2 MiB image with independently predicted non-stack semantics and checks decoded native store bounds. Synthetic pool patterns and coordinate extrema are controls, not claims that every combination occurs during gameplay.

The controls execute original instructions without stubs, patches, PC repair or memory-write hooks. Their initial table pointers, source relocation, cache domain and resource ownership are explicit supplied premises. Immediate return and disjoint stores in these executions cannot grant a deferred renderer or loader permission.

### Resource binding and fixup limits

At source base `0x8011A65C`, section 18 is offset 12680 and section 19 is 13208. The eight-byte ID list contains resource 22 followed by `0xFF` entries. Its data begins at offset 12688, with low/high counts 12/8 and directory offset 12824. Groups zero and two each contain one element with two 24-byte frames. The first frame selects callback 1; the second selects callback 0. The inspected callback step reaches the second frame, whose selector zero stops further advancement. This source/resource inspection does not establish all future callback inputs or ownership.

The pre-upload parent clears the 96 effect flags, removes prior room-local table entries and binds the current data/directory pointers through tables `0x800D4CD8`/`0x800D4E18`. The cache is eight bytes at `0x800EAE50`. Controls cover empty, low-eight, high-eight and every singleton previous ID in `0..63`; they do not prove all prior game histories have that domain. The owned 125-source census has local IDs in `8..48`. Separately owned `COMMON/DATA/CORE00.ESP`, native file index `0x90`, is 8572 bytes, SHA256 `f07072b12c91792ba08b0415661dbf2b1e351cfdbc355c6ec913e02d427716b3`; its eight global IDs are disjoint from local resource 22. This global resource is not among the existing 69 bound startup resources. A future production binder must consume its exact identity rather than infer global initialization from those 69 witnesses.

The separate texture-tail control uses the actual source rectangles with supplied row offset zero and CLUT Y=480. It writes resource `+4` as u16 30738, resource `+6` as u8 15 and eight high-table bytes. Directory counts, source commands and frame records remain unchanged. It executes the original `GetClut`/`GetTPage` arithmetic, but no GPU, MMIO, BIOS, upload or prior rectangle parser. An initial expected-buffer calculation used OR instead of addition for a CLUT offset; correcting the expectation made the full-RAM check pass without changing original code or inputs.

### Remaining room-lifetime obligations

The native room loader publishes and overwrites the incoming source before the local effect reset/binding call. Therefore a correct argument needs an initialized loader interval excluding old effect/SCD reuse during that overwrite. It must then bind the resource after fixups and keep its future reads, callback targets and writes within their actual owners. Existing synchronous `0x54` support does not supply these `0x64` or deferred permissions.

The distinct effect renderer at `0x80077924` uses the current primitive cursor, selected frame pool, ordering table and camera/clip pointers. Its before/after-update render branches need their own bounds. A mirror helper can read additional axis-selected values. The current source has no new mirror-enable producer, but an initialized incoming mirror state and its preservation require a mandatory native contract. A packet census alone does not prove that state.

Source `17:6` has an independent Goto/frame-storage obligation. Bounded original dispatcher sequences establish its exact no-IF consumer path and fresh-root resets under supplied task premises. They do not waive the rejected Rooftop Goto/IF case, whose foreign storage has an actual control consumer. An early private comparison against `ROOM2090.RDT` was the wrong source and is Rejected; `ROOM2130.RDT` has no member-write `0x35/0x3D` barrier at the claimed location.

The canonical incoming route uses Door1D. Its copied setup/model-bind controls and bounded CPU write estimates are separate from an exclusive resource lifetime. Fixed background capture destination `[0x80198000,0x801BD800)` physically overlaps its source, active work and header. Ordinary mode 2 and loader waits provide conditional protection, but the dynamic dispatcher can restore mode zero before the render-mode check. An initialized phase-2 owner needs at most two normal dispatcher calls to finish. `SYSTEM & 0x10000` can skip those calls, so counting loader yields does not prove cleanup. Neither ordinary door admission, its vibration reset nor DoorInit establishes `SYSTEM & 0x200` clear. Inherited pending dynamic state therefore needs a constructed inactive-owner premise and preservation across the incoming source/door interval. Neither source heap bounds nor absence of a new `0x6F` packet establishes it. No harmful execution has been demonstrated, and no general buffer-disjointness claim is made.

The complete argument still needs incoming auxiliary control/resource ownership, source-heap reservation, actual texture completion or cancellation semantics, renderer/queue/platform contracts and fixed-context preservation. No production factory is weakened to accommodate these component results. ID 24 remains Unknown; no absence, clearance, door result or new runtime coverage follows from this claim.

### Reproduction and retained evidence

Private immediate controls are in `/var/folders/9d/q5n746z953bcs654g_1sqcy80000gn/T/re-map-re2-item24-effects-20261106-fh31yb44/`. Binding/fixup controls are in `/var/folders/9d/q5n746z953bcs654g_1sqcy80000gn/T/re-map-re2-item24-binding-20261106-nusx3j46/`. `verify-clear.py`, `verify-spawn.py`, binding `verify.py` and `verify-fixups.py` require the pinned owned inputs and Unicorn 2.1.4. Copy each script into a fresh output directory before execution because it writes derived JSON beside itself. Retained scripts name their exact input paths and assert input hashes. Inspect those dependencies before replay; missing owned data is a failed reproduction prerequisite.

| Frozen private report | SHA256 |
| --- | --- |
| `effects/clear-verification.json` | `8c602e06de789967268449ba08506d49c44463011ad8bab60fb8ef8318b9e11a` |
| `effects/spawn-verification.json` | `0a909113b1c52b6a3709db797458b41512ba668719fac1ce78e086b72d493ff3` |
| `binding/verification.json` | `7e59147bb7cd788ef7580d6c7befc9894d640ff3eef2db9404bb15b28d9172eb` |
| `binding/fixups-verification.json` | `dae8c77ae5cf90540f18e4c65e24a43a28a0de9f99d0901b6bd2a7a42cb8b0a4` |
| `binding/incoming-effect-id-census.json` | `59e4a83ceb456a3cbefac0dca9029dae6b162e3dfc89e687950ecf522d3f0835` |
| `/tmp/re-map-re2-item24-control-20261106-e75q7uwm/investigation-control-complete.json` | `17fc10d5d39180ba2e701edcc6d3fe331633567aa2bf88d95192f44d3e37bc14` |
| `doorwork/investigation-final.json` | `35ed25d76523d6f4b782fbc43120c2eaa931395f94023614ff6aece003b427a4` |
| `/tmp/re-map-re2-effect-resource-obligations-20261106-5dbzjlrv/door1d-dynamic-owner-admission-followup-20261106.json` | `f363991742a3e6f06b18b4fa437b26b4932287c5f92b82d67700910dffca9ab4` |

The `doorwork` root is `/var/folders/9d/q5n746z953bcs654g_1sqcy80000gn/T/re-map-re2-item24-doorwork-20261106-lftuv5i5/`. Additional resource/renderer/driver source inspection is retained under `/tmp/re-map-re2-effect-resource-obligations-20261106-5dbzjlrv/`; the component reports retain their native intervals and hashes. The publication and real-factory matrix are under `/tmp/re-map-re2-outcome-matrix-20261106-j7oqf7t9/`. Hashes identify retained temporary evidence; they cannot recover lost files. Owned assets, raw RAM and saves remain private.

### Contribution and review

- 2026-11-06 UTC; Codex root, exact runtime model `gpt-6.1-sol`, effort `xhigh`; surveyed the retained production outcomes and real factories, authored and checked immediate create/clear, reset/binder, fixup and global/local-ID controls, and wrote this claim. These experiments use copied CPU instructions and explicit component premises, with no emulator, guest-memory or user-history write.
- 2026-11-06 UTC; independent source/native investigator, exact verified model `gpt-6.1-sol`, effort `xhigh`; investigated source Goto/task storage, incoming Door1D mirror/control ownership and copied setup/model-binding components. Its reports preserve initialized-state and exclusive-lifetime gaps; they supply no production permission.
- 2026-11-06 UTC; independent retained-evidence auditor and resource-lifetime investigator, exact verified model `gpt-6.1-sol`, effort `xhigh`; checked the immediate control reports, native/source packet hashes and full-RAM semantic expectations without rerunning them. It separately traced deferred resource, renderer, loader, GPU-queue and fixed-capture obligations. No issues in those immediate components were found; this is not a whole-source, draft-documentation or gameplay endorsement.
- 2026-11-06 UTC; Codex root, exact runtime model `gpt-6.1-sol`; rechecked all eight quoted report hashes, 44 original executable windows, actual source packet sites, report case counts and unchanged production implementation. Its retained-file audit is `/var/folders/9d/q5n746z953bcs654g_1sqcy80000gn/T/re-map-re2-effects-doc-check-20261106-kokpd6qf/verification.json`, SHA256 `288b0b9b5871342378a095cc7e6e6db4efad3582f796e2c8d84e35106179f15b`. It corrected the draft's CORE00 directory from `ESP` to the census's `DATA`. This audit adds no CPU execution or gameplay evidence.
- 2026-11-06 UTC; independent draft and retained-evidence reviewer, exact verified model `gpt-6.1-sol`, effort `xhigh`; returned no findings after checking identities, all eight report hashes and 44 code windows, immediate/bounded case counts, fixup widths, supplied premises, reproduction instructions, attribution, the dynamic-owner caveat and the index row. It read scripts/reports without rerunning CPU experiments or gameplay. Deferred ownership, whole lifetimes and platform behavior remain unvalidated.
- 2026-11-06 UTC; external snapshot reviewer, `gemini-3.8-flash`, high reasoning through Antigravity; returned no findings on the complete new claim and four component verifiers, shared store-audit implementation, labeled report excerpts, actual factory failure and retained publication. The supplied reports explicitly abbreviated case lists and some supporting fields. Review checked documentation consistency, counts/fields, premise and lifetime boundaries, verifier expectations, reproduction and attribution. The completed response had no pending child work or tool attempts; it supplies no independent execution or omitted-case audit. Claude Opus 5.5 remained disabled and supplied no review.
