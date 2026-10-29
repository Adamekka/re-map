# RE2 known puzzle items

[Claim index](../../research.md) · [RE2 testing](../../testing/re2.md) · [Room completion rules](../../room-completion.md)

## RE2-PUZZLE-001: declared puzzle targets remain required before activation

Status: Candidate source and native-contract interpretation for Resident Evil 2 Dual Shock Ver., USA Disc 1, SLUS-00748, Leon A, Original/Normal. Native unactivated entry and ordinary departure support the reported correction in one starting context. They do not fully confirm the puzzle, callback activation, acquisition or quantity lifecycle. Other revisions are unaudited.

Executable `SLUS_007.48` SHA256 is `e576348f64d015ecff6e1ce875a8924ee252ba7f3f9478b0917cbbdeb97db441`. Main Hall source `PL0/RDT/ROOM2000.RDT` is 448820 bytes, SHA256 `7586728196fd83ec3992964746efd8d7f793fee383963e11c70951ff307fe000`. Native validation uses isolated official DuckStation `0.1-12083-g00e299795`, commit `00e2997958d62de79d352cd680ec0c1ad95d491c`, executable SHA256 `5c879677051cfb173002df22baee741c96fa8071c6fe1dd7e5454092bf128173`, GDB port 2347.

### Failure and the narrower conclusion

Before the Main Hall puzzle is activated, departed acquisition ID 93 was Unknown. The existing whole-source context proof still rejects unrelated movie/window effects, so its ordinary item-presence proof supplies no result. Extending a post-puzzle access callback would resolve none of the retained pre-puzzle outcomes. Those limitations are preserved in [RE2-DS-004](dualshock.md#follow-up-bounded-main-hall-control-movie-and-window-audit-2026-10-27).

The correction establishes positive knowledge of a real declared puzzle target. A guaranteed startup declaration and a guaranteed active player interaction must refer to the same collectible identity through a bounded native callback path. A saved puzzle predicate may block that path now. The known target still remains required until its fresh acquisition flag is set, as required by the room-completion rules.

This conclusion supplies neither current nor eventual access. It does not assert that the puzzle predicate becomes true, a scheduled event finishes, a movie/window returns, or another catalog item is absent. It selects no quantity or conflicting identity and grants no list completeness or clearance. A known remaining item can make the room Incomplete while other item checks stay unresolved.

### Shared source and native bounds

[`known_puzzle_items.py`](../../../src/games/re2/known_puzzle_items.py) requires both the exact-resource `VerifiedRoomEntryContract` and the revision's `ScriptItemDispatchConfig`. The [entry/resource contract](immutable-doors.md#native-entry-and-write-obligations) binds the executable, stage binary, door resources and native entry namespaces. It is an explicit revision capability, not a default for other profiles.

The compiler checks the complete source hash, native procedure tables, decoded packet spans and item metadata. It follows the two synchronous startup roots only through admitted effects. If the first root cannot complete that bounded prefix, the second root cannot establish a guarantee. Unknown later effects stop a path's prefix without gaining continuation permission. Alternative declarations must agree on acquisition ID and type; a catalog entry or an orphan procedure alone is insufficient.

Embedded model setup uses shared source/write partitions and the shared static-object packet predicate. Every prefix path must establish fresh single relocation and initialized fixed-object ownership before coordinate writes. These checks cover the actual model commands before the Main Hall callback, including offset 10190. They do not admit the later movie or window family. Retained source must fit below the native upper graphics arena, `0x80198000`, using the exact stage-derived source base `0x8011A65C` rather than a lower bound. Main Hall's section-two heap boundary is offset 192344, physical address `0x801495B4`.

An active callback must have the canonical ordinary kind-five descriptor, SAT `0x31`, a nonempty rectangle and event payload `FF 00 18 pp 00 00`. Its procedure-table entry must name the inspected source procedure. The bounded path is checked up to direct `Aot_on` of the declared pickup slot. Saved puzzle predicates remain symbolic. Callback writes cannot manufacture acquisition or alter enforced mode flags. The admitted STOP write is bit seven; the native scheduler and `Sce_Event` gate is bit six, so arbitrary control-word writes are rejected. The finite `09/0A` sleep macro uses a task-local counter. Camera changes require a real first matching 20-byte RVD record, not merely an in-range camera number. Other branches can stop at an unsupported message or effect without becoming a delivery/progress claim.

Native control has four total call frames, numbered zero through three, including the base frame. At most three nested `Gosub` calls are admitted; a fifth total frame is rejected in both the declaration and opposite-entry checks. The shared frame constant also serves the initializer-control proof.

Every potential item, door, generic interaction and reset binding of the target slot is checked for identity changes. Conflicting types for the acquisition ID also withhold knowledge. Explicit source flag writers and kind-six flag setters are compared by physical word/mask, including aliases and the native halfword index's eight-word wrap. A reader bank-width limit cannot hide such a writer. Main Hall's bank-ten/bit-71 setter is outside that reader bank's width but writes a different physical word.

Copy protection covers complete packets used by the startup proof, the complete positive callback body, the opposite-entry closure and its message resources, plus procedure tables and other identity/control fields. Protecting opcode bytes alone was rejected: Copy could otherwise change an `Aot_on` slot, camera operand or model setup mode while preserving the original opcode. The actual later copies into animation operands at 11512, 11534, 11600 and 11628 remain disjoint from the new proof.

### Main Hall declaration and puzzle relationship

RDT offsets below are source-file bytes. Native and live addresses are PS1 virtual addresses, little endian, not host-process pointers. Pointer/word masks are `0xFFFFFFFF`, halfword masks `0xFFFF` and byte masks `0xFF` unless a narrower mask is listed.

| Source relation | Exact evidence |
| --- | --- |
| Startup declaration | `16:0` creates slot nine at 9826 or 9852, both kind two, type 89, acquisition ID 93; amounts two/one remain alternatives |
| Player callback | `17:0` calls `17:2`, which creates slot ten at 10418 before its unsupported effect; the canonical active callback names `17:7` |
| Guarded delivery reference | `17:7` checks puzzle flag 4/72 and acquisition 8/93, then directly dispatches slot nine at 10838 |
| Puzzle event association | Frame root `17:1` calls `17:3`; the puzzle condition sets 4/72 and schedules `17:8` |
| Same-identity activation | Resets at 10944/10958 retain slot nine, type 89 and ID 93 while preserving the two quantity alternatives |

The declaration starts `4E 09 02 31`. SAT is `0x31`, not zero. Its parked rectangle is X/Z 15948/9485 with width/height one. The nonzero SAT alone does not establish ordinary physical reachability. The direct callback's association with that declared target is the relevant knowledge evidence.

| Fresh state | Word address, width and mask | Interpretation |
| --- | --- | --- |
| Entry mode 1/6 | `0x800CFBD8`, unsigned four bytes, `0x02000000` | Must be clear for the normal declaration/callback prefix |
| Puzzle activation 4/72 | `0x800D485C`, unsigned four bytes, `0x00800000` | May remain clear; knowledge does not require activation |
| Acquisition 8/93 | `0x800D48C4`, unsigned four bytes, `0x00000004` | Clear leaves the known item required; set gives Collected |
| Transition exclusion | `0x800CFB74`, unsigned four bytes, `0x02000000` | Prevents publishing the old source during the audited door transition |

### Historical mode guard and the opposite-entry proof

The initial proposal pruned startup paths using all fresh fixed settings. Review rejected a concrete counterexample: the declaration can be skipped with mode 1/1 set at entry, then a later source writer clears it, allowing a fresh zero to falsely authorize that historical declaration. Rejecting only writes before the target is insufficient.

The final proof rejects physical fixed-bit writers anywhere in the decoded source. It prunes only a literal leading mode-return guard; later scenario branches must agree on the target and callback. Main Hall therefore needs only the 1/6-clear entry predicate, not an inferred historical value for 1/1 or the puzzle flag.

For the inverted entry, 1/6 set, all ordinary roots have a smaller closed behavior: `16:0` immediately ends; `17:0` calls only `17:12`; frame `17:1` immediately ends. Procedure twelve creates two canonical kind-four nonchoice messages and two unlocked model-`0x0D` doors. Other callbacks, tasks, actors, mutators and unsupported effects reject this closure. No normal-mode movie/window path is entered in the inverted case.

Both message-seven language resources pass the shared nonchoice grammar. The four source witnesses are:

| Resource | Offset | Width | SHA256 |
| --- | --- | --- | --- |
| Japanese directory entry | 11806 | 2 | `a098cf43f0192eae10259edc74640c58207c39e9523cf2379843489771a09c91` |
| Japanese text | 12086 | 24 | `2c0f5a78f36641442aafd88459a134a7f86dd6e7bab9c94008d148ebd9887565` |
| English directory entry | 12126 | 2 | `b9b8cdc1be9a61a6aa5a9fba8945182e52b92a9357883c07e13a45b0598b5452` |
| English text | 12454 | 25 | `9194543e40cdb3aa2a29dce4ae4aadfed3047a4276c79b4030268b1a603204f7` |

The [shared message audit](scripted-items.md#message-lifetime-and-saved-word-preservation) establishes STATUS stores that OR only `0x00000040` at native `0x8002FEB0` and clear only that mask at `0x80030308`. Deferred close changes UI work and STOP, not entry-mode bit six. Choice/scheduling text paths remain excluded.

The direct unlocked-door callback `0x80051514..0x80051718` preserves STATUS and sets STOP at `0x800CFBDC` with mask `0xFF000000` for passage. Its pre-transition loader `0x80015064` ORs STATUS only with `0x00020000` at `0x800150FC`. The driver table at `0x8009A7B4`, used by `0x80013BC4`, enters setup `0x80013C1C` before animation driver `0x80013EB4`. Setup ORs SYSTEM with `0x02000000` at `0x80013CB8..0x80013CBC`, before auxiliary PC initialization at `0x80013E28` or interpreter `0x80014058`.

That system bit is the reader's explicit transition exclusion. The proof preserves the mode only until this boundary; a new source initialization establishes its own prefix. It supplies no invariant about STATUS throughout DO2 animation and no theorem about normal-mode movie/window lifetimes. Under the bound initialized engine contract, the skipped opposite entry cannot become an accepted clear-mode old-source publication without reinitialization.

### Integration and observed outcomes

Generation exports exactly two positive numeric records: source `01-00`, ID 93/type 89, and source `01-06`, ID 31/type 51. The latter uses creator 5428, callback 5388 and delivery reference 6942, with no additional entry condition. It is source-only evidence; no user-playthrough or new native lifecycle observation is asserted for `01-06`.

The loader requires the revision capability, explicit per-room records, unique/bounded fields, bound creator identity and valid fresh conditions. The reader reevaluates acquisition and conditions in the coherent polling transaction. Acquisition wins after delivery/use; earlier states restore the remaining item. Current live observations keep their independent precedence. The proof does not set `fixed_context_preserved`, choose a quantity or repair another item's identity/list coverage. No game-derived result is persisted in exploration history.

Root's native entry capture is `/tmp/re-map-loop-20261028/puzzle-native-mainhall-entry.ram`, 2097152 bytes, SHA256 `2157120471d11a320f71294e90e735a7aa125b286fcab2e981d62021b6d55ad3`. Loaded base is `0x8011A65C`; slot nine points to `0x8011CCC0`, creator 9826 plus two. Its 20-byte descriptor is `023100004c3e0d2501000100590002005d0001a0`. Mode 1/6, puzzle 4/72 and acquisition 8/93 are all clear. This observes the real pre-puzzle declaration, not callback activation or a pickup.

Entry reused an equivalent 12-byte door destination and nine pose fields, recorded in `puzzle-native-entry-setup.json`. It is a controlled equivalent entry, not an unmodified navigation claim. Root then used ordinary Main Hall door one to Waiting Room, with only the established nine pose fields recorded in `control-native-pose-writes.jsonl` after a control-only backup. The departed capture, `puzzle-native-departed.ram`, has SHA256 `56a5e5544a386999274ff9f537ac66d70896ee4f64f601d1b1ad2a38afbf5a3b`. Mode, activation and acquisition remain unchanged. Its key changes from Unknown/room Unknown to Uncollected/room Incomplete; quantity stays Unreconstructed and list completeness stays false. An inspection attempt did not establish callback activation and is excluded from that claim.

`puzzle-item-replay.json` compares 37 unique RAM captures: 28 Display and nine unchanged Retry results. Twenty-five departed Main Hall publications gain the known key. One is the previously excluded clipping-geometry control, so 24 gains count as accepted departed evidence. Three current Main Hall publications remain unchanged. Every other publication field, door, quantity and list-completeness result remains unchanged, and private visits-only history round trips reconstruct the same results. These replays add no pickup, award quantity or full-confirmation claim.

The artifact comparison preserves every pre-existing metadata field after removing only the new `known_puzzle_items` records and research ID; floor artifacts are byte-identical. Headless browser checks at desktop width 1280 and mobile width 390 show the Main Hall remaining item, Incomplete state and retained incomplete-list check without overflow or browser errors. Root updated the README image to match. These checks validate publication and layout, not the unobserved puzzle lifecycle.

### Reproduction, validation and contributions

Regenerate with the owned Leon Disc 1 CUE and `tools/build_re2_metadata.py --profile profiles/re2_leon_a_slus00748.json`. Inspect `known_puzzle_items` separately from `collection_item_ids`, quantity alternatives and fixed-context metadata. Reconstruct the two native captures above from fresh RAM and a separate visits-only history; require Uncollected after unactivated departure, preserve unresolved quantity/list state and compare all other published fields.

Run `python3 -m pytest -q tests/test_re2_known_puzzle_items.py tests/test_re2_profile.py tests/test_re2_tracking.py`. Regressions cover source/table binding, orphan or other-scenario declarations, target/callback aliases, native call limits, fixed-word writers, complete Copy packet protection, fresh model ownership, opposite-entry effect closure, both message languages, the transition boundary, mode mismatch/torn reads, and acquisition/activation reversal. The focused integrated run passes 604 tests; the final full suite passes 3613. Scoped Ruff formatting/lint and whitespace checks pass.

Private source/native evidence includes `known-puzzle-opposite-entry-audit.json/.asm`, `known-puzzle-source-results.json`, `native-message-flag-preservation.json`, `native-message-closure.asm` and `actor-domain-kind4.asm` under `/tmp/re-map-unresolved-20261028/`. These distinguish source interpretation, native instruction inspection, synthetic regressions and root's actual native captures. Copyrighted source/resources and raw RAM remain outside Git.

`/tmp/re-map-loop-20261028/puzzle-native-validation.json` records identical item flags, mode, activation and acquisition across entry, the inconclusive inspection attempt and ordinary departure. It records door slot one, creator 9560, as the native departure from `01-00` to `01-01`; no key was awarded.

The private emulator has both achievement integrations disabled, None/None memory cards, muted audio and black post-processing. No health, ammunition, story or key patch is enabled. Agent histories remain separate; the user's history stays released. This documentation task performs no emulator or history operation.

Contributions and review, 2026-10-28: the human user supplied the unresolved-room report and requested the repair loop. The `procedure_entries` agent, exact model `gpt-6.1-sol` verified by authoritative T3 runtime metadata, researched the bounded rule, authored the compiler and focused tests, inspected the native entry/transition instructions and authored this record. Root, the same exact model, authored generator/profile/reader integration, shared predicate reuse and call-frame correction, performed the native entry/departure, replay/history comparisons and full validation, and reviewed the combined change. The `door_diagnosis` agent, exact model `gpt-6.1-sol`, supplied the independently inspected message, camera and immediate-door write domains. The `metadata_diagnosis` agent, exact model `gpt-6.1-sol`, independently found the historical-mode counterexample, verified the narrower opposite-entry argument and reviewed caller/control closure, physical aliases, complete Copy/text protection, native message/door boundaries, source bounds and knowledge-versus-access separation. Its final review reported no remaining verified blocker. Configured external review providers were unavailable; they returned no reviews and provide no endorsement. Earlier research authorship and rejected movie/window and access experiments retain their separate scope.

## RE2-PUZZLE-002: source 00-12 needs incoming-resource and opposite-mode bounds

Status: Candidate source investigation and copied native-handler experiments for the same USA Dual Shock Ver., SLUS-00748, Leon A Original/Normal executable identified above. A stage-address-only extension is rejected. This increment changes no production rule, item/door outcome or clearance result and adds no gameplay observation.

### Reproduced gap and positive relation

Baseline `df90c60` reconstructs the existing unresolved checks from retained RAM and a read-only copy of the user's visits-only history. Seven bounded source diagnostics reproduce the checked-in catalogs exactly. Source `00-12` still reports acquisition ID 21, Bishop Plug, as Unknown after departure. Its other unresolved pickup remains separate.

Owned `PL0/RDT/ROOM1120.RDT` is 458232 bytes, SHA256 `832014cd87b9a81442ca91ddfe036e5846bb43b5135de3aae0378148df2ec5bf`. File offsets below refer to that source. Root `17:0` has a mode-return guard, declares slot eleven/type 59/ID 21 at 10656, initializes a static object at 10678 and calls `17:2`. That procedure declares active callback slot seven at 10804, naming `17:12`, before unsupported effect `0x54` at 10844. The callback references slot eleven through `Aot_on` at 13272. Camera thirteen has a real matching RVD record at 1560. These relations identify a candidate for the existing positive-knowledge rule; they do not establish all of its entry or mode requirements.

The existing verified stage-zero loader recipe places this source at PS1 virtual `0x8011A6A8`. Its retained-data boundary is offset 88916, ending at `0x801301FC`, below the graphics arena at `0x80198000`. Embedded model five uses an owned 1708-byte asset at source offset 24320. These resource facts do not replace the existing contract's stage-one address `0x8011A65C`. The incoming models are `01/0D`; the current room-entry contract audits `09/0D`, and the separate positive-declaration contract admits `02/0A`. A resource-selection receipt identifies an incoming model but does not prove that model's native entry effects.

Root `16:0` starts with doors and a conditional kind-four reset. Its mode-dependent return is in the second root, so the existing leading-first-root recognizer cannot simply be reused. Under the opposite entry setting, frame root `17:1` still calls `17:3`, which can schedule `17:13` at 11968. That path must preserve the enforced mode before current flags can justify a historical declaration.

### Bounded motion writes

All addresses in this subsection are PS1 virtual addresses. Data is little endian; word/pointer fields use four bytes and mask `0xFFFFFFFF`, and halfwords use two bytes and mask `0xFFFF`. Source packet offsets are distinct from these addresses.

Worker packet `2e0404` at 13306 selects fixed object four, record `0x800D0B04` with width 504. It does not select an inherited actor pointer. The following exact operations have a smaller write obligation than model or animation-resource ownership:

| Operation | Native code | Writes |
| --- | --- | --- |
| Work selection `0x2E` | `0x80055904` | Task work pointer at `+0x154`, six cleared words at `+0x158..0x16F`, task PC at `+0x1C` |
| Delta setter `0x2F` | `0x80055A84` | Source selectors one/seven write task halfwords `+0x15A/+0x166`; task PC advances four bytes |
| Motion `0x30` | `0x80055AB0` | Object coordinates `+0x38/+0x3C/+0x40` as words, rotations `+0x74/+0x76/+0x78` as halfwords; task PC advances one byte |
| Delta update `0x31` | `0x80055B2C` | Six task halfwords `+0x158..+0x162`, each adding its corresponding halfword at `+0x164..+0x16E` modulo 65536; task PC advances one byte |

The task pool begins at `0x800D7860`, stride `0x174`, fourteen records, ending at `0x800D8CB8` exclusive. Root reproduces 70 copied opcode-31 executions over all fourteen records and five seeds, including signed boundaries and wraparound. Another 490 copied executions use the source's Work/delta packets and two motion/delta-update iterations. Every complete two-MiB RAM comparison permits only the predicted task and object writes. This supports the local write domain without asserting that a scheduler, loop or game interaction actually executes that sequence.

Static inspection of scalar packet `340ce0ac` at 13350 selects member twelve and stores signed value -21280 to object four's Y field at `+0x3C`. Its full copied handler raises `UC_ERR_EXCEPTION`, so this increment claims static instruction evidence only for that setter. A reused Unicorn MIPS CPU also skipped a second handler entry; the accepted motion experiments use a fresh CPU for every invocation. Both failed harness variants remain private as diagnostics.

### Remaining entry and sound obligations

All explicit and kind-six flag writers avoid SYSTEM word `0x800CFB74`, mask `0x40`, and STATUS word `0x800CFBD8`, mask `0xC2000000`. Native bank-nine bit 128 aliases four-byte word `0x800D491C`, mask `0x80000000`, still disjoint from those mode words. All 53 Copy commands avoid the complete positive-prefix, callback and opposite-frame/worker packets checked in this investigation. These checks do not authorize other native effects or arbitrary alternate entries.

Worker sound packets at 13294/13322 call `0x80056428` and helper `0x8005BA28` for bank-two sounds `0A/0D`. They perform real VAB tone writes. The source's EDT/VAB offsets are 85108/85300, and section 22 is 36468. The corresponding four-byte EDT records are `00004400` and `00007300`. The existing immutable-door sound receipt requires section 22 zero, so it cannot be reused unchanged. Owned sound relocation/write bounds and incoming model `01` entry effects remain necessary, followed by the second-root guard and opposite-mode control argument. Unsupported effect `0x54` after the positive prefix remains unadmitted.

Private reproducible evidence:

- `/tmp/re-map-next-presence-df90c60-vugqupib/diagnose.py` pins production source/data to `df90c60` and reproduces the seven unchanged catalog outcomes.
- `opposite-mode-writes.py/json` in that directory records exact source packets, physical flag aliases, Copy destinations, native instruction spans and sound operands. The root reruns it independently. `stage-zero-compatibility.json` and its addendum retain the initial compatibility investigation and corrections.
- `/tmp/re-map-accuracy-20261030/native-object-motion.py/json` records the 560 accepted copied executions and complete-RAM comparisons. The separate reused-CPU and scalar-exception variants are not accepted executions. No DuckStation instance, game input/load, settings change, history write, live guest patch or screenshot occurs.

The focused known-puzzle, room-entry and startup-declaration suites pass 163 tests. Local links/anchors and whitespace checks pass. Direct review distinguishes the positive source relation, local copied-write evidence, incoming-resource and sound limits, and unchanged publication. External review providers remain disabled; no external endorsement is claimed.

Contributions, 2026-10-30: the human user requested continued autonomous RE2 improvements. The `startup_experience` agent, exact model `gpt-6.1-sol` from inherited authoritative T3 runtime metadata, diagnosed the seven sources and authored the static compatibility, packet, alias and Copy reports. Root, exact model `gpt-6.1-sol` from authoritative T3 runtime metadata, reproduced the retained publication and source diagnostics, independently inspected the native dispatch/handlers, ran the copied motion experiments, checked additional packet protection, reviewed the limits and authored this dated record. Earlier authorship, gameplay evidence and approved collection/identity policy remain unchanged.
