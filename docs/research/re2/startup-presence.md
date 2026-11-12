# RE2 item presence through startup setup

[Claim index](../../research.md) · [RE2 testing](../../testing/re2.md)

## RE2-STARTUP-001: setup effects and equivalent creators preserve known items

Status: Confirmed current item bindings in the existing native clipping-entry captures for Resident Evil 2 Dual Shock Ver. USA Disc 1, SLUS-00748, Leon A, Original/Normal. The shared source-based presence inference remains Candidate outside those observations. The new source walker adds no native pickup observation or memory-card persistence claim.

Executable `SLUS_007.48` SHA256 is `e576348f64d015ecff6e1ce875a8924ee252ba7f3f9478b0917cbbdeb97db441`. Source `PL0/RDT/ROOM20E0.RDT` SHA256 is `94f38aa44a170d207c7625a41e24c595da82af57ad46f9fad7383600a0e92a0e`. Native evidence uses isolated DuckStation `0.1-12083-g00e299795`, full commit `00e2997958d62de79d352cd680ec0c1ad95d491c`, with emulator identity, setup writes and exact restore recorded in [RE2-CLIP-001](clipping.md#re2-clip-001-startup-clipping-preserves-the-fixed-item-context).

### Reported failure and two causes

The visited examination/interrogation source stayed gray after departure. Its full relevant item identities were resolved, but three unacquired items still had Unknown presence. Current native entry captures already showed the four relevant pickups Available or Collected. The departed item-presence lists were empty.

The first cause was inconsistent interpretation of setup. The fixed-context proof already validated native opcode 73 at offset 6012 and bounded SCA opcode 37 at 6096, 6188 and 6266. Both item-presence walkers nevertheless treated those setup commands as unsupported. Their startup-completion checks therefore withheld every item guarantee.

The second cause affected acquisition ID 56 independently. Its equivalent creators at 6534 and 6560 occupy opposite outcomes of an opaque comparison. Proving each creator separately and then ORing the results loses the guarantee that one of them executes. The walker now groups identical acquisition ID/type goals before intersecting branch outcomes. Different IDs, item types and awards keep separate goals. It does not select a camera outcome or assume a current counter value.

### Bounded shared correction

A revision opt-in selects the exact audited setup recipe. `ScenarioItemProof` exports a source-hash-bound continuation receipt only after the existing whole-source context proof succeeds. The receipt records validated instruction locations and the physical predicate bits they preserve. A broader query cannot inherit that receipt's guarantees.

SCA validation reuses the existing shared native record/write bounds. The complete declared collision asset must be disjoint from both complete script sections, including procedure directories. Clipping reuses its existing selector, startup placement, initializer-entry, allocation and write-mask guards. Decoded instruction spans must not overlap. Unproved commands retain the existing unsupported outcome.

This recipe protects only the explicit native system/status words already covered by the clipping audit. All addresses here are PS1 virtual and little endian: system flags `0x800CFB74` and status flags `0x800CFBD8`, each unsigned four bytes. Flag bank masks use `0x80000000 >> bit`. Source offsets above are RDT byte offsets, never host addresses. A predicate alias into task, source, model or heap work requires a separate proof and receives no continuation permission here. See RE2-CLIP-001 for the exact parameter stores and deferred model-copy limits.

The two startup walkers consume the same receipt. It grants continuation through its validated setup locations, not blanket permission for an opcode, source or revision. No new runtime cache, exploration field, guessed state value or clearance exception is introduced.

### Outcomes and reproduction

Owned-CUE generation changes only source `01-0e`'s conditional presence records, adding unconditional required presence for IDs 56, 60, 110 and 199. The two ID 56 creators remain in the catalog. Earlier fixed-scenario exclusions 61/171 and all selected identities remain unchanged. Every other room field and the floor artifact are identical, apart from the top-level audit/claim declaration.

In the retained user state, the three Unknown rows become Uncollected and the room changes from Unknown to Incomplete. The already collected Small Key remains Collected. Fresh acquisition flags continue to win, and synthetic earlier/later acquisition reversals rebuild all four rows without retaining a previous completion result.

Reproduce with the pinned owned CUE and `tools/build_re2_metadata.py`, using the profile's explicit `startup_effect_audit`. Compare the generated `01-0e` records before and after opt-in. Private `clip-presence-joint-diagnosis.py/json` records the two isolated causes; `startup-item-replay.py/json` compares 23 distinct native RAM captures against commit `fcf0c03`. Nineteen Display results preserve every other room, door, position and visit. Fourteen departed publications gain the three item-presence outcomes; four accepted current source captures keep their live item results. The remaining Display image is the previously excluded camera-only geometry preparation, `clip-active-entry.ram`; it changes four Unknown rows to Uncollected in the comparison, but is explicitly labeled an excluded control rather than native acceptance evidence. Four UI-transition Retry results remain unchanged. Each Display result also matches after a separate private history close/reopen and fresh poll.

The native evidence is reused rather than relabeled as a new gameplay experiment. The full equivalent entry and exact earlier/later savestate restoration remain those documented by RE2-CLIP-001. BIOS, RDT files, raw RAM and RE2 saves remain outside Git. The agent emulator is stopped, both achievement integrations are disabled in its private configuration, and the user's released history remains untouched.

### Validation and review

The applicable full Python suite passes 3471 tests. The parallel puzzle/compiler work is excluded from this increment's test run and commit. Thirty-three dedicated startup cases cover revision opt-in, missing capability, native bounds/placement, yield and entry rejection, complete script/table exclusions, instruction overlap, physical predicate aliases, source/query binding, collective startup/scheduled goals, nonmerging different identities and the actual generated artifact. Reader regressions cover fresh acquisition reversal and history-independent reconstruction. Scoped Ruff formatting/lint and whitespace checks pass.

Desktop/mobile rendering of the retained state verifies three Remaining rows, Collected Small Key, the Incomplete room color and no overflow or browser errors. The README screenshot is refreshed. No claim is made that unrelated door conditions or the other gray rooms are resolved.

Contributions, 2026-10-28: the human user supplied the unresolved map report and requested the fix loop. Codex `metadata_diagnosis`, exact model `gpt-6.1-sol`, diagnosed both walkers, authored the shared receipts/collective goal correction and adversarial regressions. Root, the same exact model verified by authoritative T3 runtime metadata, reviewed the receipt and branch semantics, authored generator/profile integration and acquisition regressions, compared all native captures and private history round trips, checked rendering and wrote this record. Prior native clipping experiments retain their original attribution in RE2-CLIP-001. Configured external review providers remain disabled; no external endorsement is claimed.

## RE2-STARTUP-008: a bound entry domain admits the positive item prefix

Status: Candidate for Resident Evil 2 Dual Shock Ver. USA Disc 1, SLUS-00748, Leon A, Original/Normal, under the user's approved normal initialized unmodified engine premise. This is offline source/native inspection and retained replay. It adds no native execution, gameplay, campaign or memory-card persistence confirmation. The retained inputs inherit the existing DuckStation `0.1-12083-g00e299795` provenance; this contribution did not launch an emulator.

Historical interrupted draft recovered on 2026-11-12. The following 2026-11-07 text preserves its original attribution and evidence claims. Its old `/tmp` artifacts and retained RAM/history are now unavailable. Recovery verification is recorded separately below and does not endorse those missing replay/render results as current evidence.

### Failure, binding and authority

At local base `a89253485190fae611d1e1493cebd733eaad9d2a`, the actual positive factory rejected source `PL0/RDT/ROOM2040.RDT`, SHA256 `4816336f9147fc6179d7f39dca7e5a33ee302555091312ced2e1c1bca40afd46`. The retained publication had five Unknown item rows. Target acquisition ID3 remained Unknown at the already established quantity15. Current saved story flags cannot decide which historical startup branch ran.

The new positive path consumes the actual `BoundStartupDeclarations` and `BoundEntryResources` returned by the owned binder. Their exact type-tagged complete binding digest is `727c49593f3d756594049140e357d8c4c6f47aefdb215d7fd6d0a0a79ed670a8`, covering 69 resources, 125 sources and 54 auxiliary DO2 scripts. Full executable SHA256 `e576348f64d015ecff6e1ce875a8924ee252ba7f3f9478b0917cbbdeb97db441` is mandatory before interpreting native code. All newly inspected native code belongs to that executable; no additional asset is implied or substituted.

The internal immutable capability recomputes entry, source-control, numeric-write and receiver facts on construction. It binds the complete corpus, native ingress, raw source, redecoded programs, room/profile JSON and every derived tuple. Matching field/derivation replacement, mutable aliases, subclasses and bool/int substitutions cannot replace the derivation. Existing positive paths retain their previous source-effect contract. The additional roles require this capability on the mandatory positive factory path. Neither branch consumes a Guard receipt or constructs strict-entry, whole-source, door, item-absence or list-pruning authority.

### Native entries and finite source control

The pinned installer inventory has eight direct calls. PS1 cached virtual addresses are `0x80013E28`, `0x800519A8`, `0x8005322C`, `0x800535E0`, `0x80053600`, `0x800536A4`, `0x8005388C` and `0x800538C4`. The native kind5 table word at `0x800A73D8`, u32LE, points to `0x80051980`. Manual dispatch at `0x8005149C` and scripted dispatch at `0x80055234` consume registered source payloads. Seven creator handlers publish source PC+2; opcode46 modifies an existing descriptor. The common registry reset, ordinary namespace restoration and bound auxiliary isolation remain required.

Fresh ordinary roots are `16:0`, `17:0` and refresh `17:1`. Every source birth and every kind5 creator/reset alternative contributes a possible fresh root. Gosub edges contribute their actual call depths, bounded by the existing four-frame formula. Both ordinary and four-point callbacks contribute conservatively. Source clone, return, alternate-entry classes, EventNext03 and shifted kind5 Aot_on remain unsupported by the additional capability. All 54 auxiliary sources exclude AOT creation, reset and dispatch. Their existing independent native ingress contract remains intact.

The shared structured-frame walker derives the fresh FF/FF Goto role without a current task-slot, inactive-receiver or allocation-count assumption. The native IF pointer is `task + 0xC0 + 32*callDepth + 4*(encodedIFLevel+1)`, u32LE. At fresh depth0, encoded FF sets it to task+`0x4C0`. Subsequent IF stores are finite source exits at that pointer, advancing four bytes per active IF. Goto resets the pointer, and counted-loop repeat edges must restore the same IF/frame state. Zero, one, `0x7FFF`, `0x8000` and `0xFFFF` counts retain the same skip/repeat possibilities; no termination or unbounded source-progress claim is needed.

For the target source, five actual escaped stores address receiver fields +`0x64`/+`0x68`, u32LE, after dividing by native task width `0x174`. The three fresh Goto procedures have no Gosub incoming edge. Their failure predicates consume their own freshly stored exit through immediate atomic CMP23. A Goto writer containing Gosub rejects because native Return reconstructs a canonical IF pointer and needs its own separate field role. The three ordinary Break sites read +`0x60`; all 126 Break sites across the complete 54-script auxiliary corpus avoid the written fields. Break's shared end-cell formula is `0x60 + 16*callDepth + 4*loopIndex`, u32LE. Other call, loop-start, count, saved-IF and IF-return readers remain disjoint. WHILE writes its own end cell before immediate atomic predicate consumption. A consuming receiver, positive-depth/noncanonical Goto, abandoned loop or accumulating frame state rejects the additional role.

This derives 21 admitted entries for the target source while protecting all 27 programs. The unentered attachment producer in `17:24` receives no native-effect permission. Its opcode2D flags82 still describe an unsafe attachment queue; an actual birth, callback or Gosub to that procedure restores its effect obligation. Excluding that obligation never excludes its source bytes or creator/control packets from write protection. ID0 remains Unknown, with no absence or removal inferred from the entry set.

### Numeric operands and the positive prefix

The only new Copy destinations are FOR's u16LE repeat count at +4..6, opcode36's signed XYZ halfwords at +6..12 when its fixed-position selector byte+4 is zero, and opcode54's two numeric SVECTORs at +8..14 and +14..20. Ranges are end-exclusive RDT byte offsets. Writes crossing a field boundary reject. Opcodes, selector/control bytes, loop ends, entries, callbacks, creators, immutable flags and source/resource write destinations stay protected, including in unentered programs. Existing shared source-write witnesses still check native model, collision, camera and resource footprints.

Original native handler `0x800538A4` publishes caller PC+4 at `0x800538C0` before calling the fresh installer at `0x800538C4`, then returns1 without dispatching its child or scheduler inline. Ordinary FF allocation chooses tasks2..9 and can replace busy9. It cannot replace startup0/1, so the synchronous startup prefix can continue without assuming free capacity or child completion. Later explicit births and kills admit only ordinary selectors2..9. Startup and auxiliary selectors reject.

DEFAULT15 is admitted only with its actual switch label/frame and pinned PC+2 native role. Operandless28 publishes PC+1 before updating fixed RNG state and counter29. Its two RNG branches write only their fixed seed words and that u16LE counter: PS1 virtual `0x800D8CB8` u32LE, `0x800CE318` u32LE and `0x800D4826` u16LE. The positive-only source role also admits coordinate members11/13, the owned Work's numeric X/Z u32 fields at +`0x38`/+`0x40`. These checks grant no pointer-selector permission, predicate value or broader native fallthrough whitelist.

Both historical bank4 bit85 paths reach item creator6732, slot4/type20/amount15/SAT0, and callback6776, slot6 targeting `17:8`, before the first constructor6836. Delivery7956 dispatches the registered target. Current bank4 bits85/86 and bank29 bit9 do not prune historical branches. Fresh acquisition remains bank8 ID3 at PS1 virtual `0x800D48BC`, u32LE mask `0x10000000`. The correction adds no quantity proof.

### Measured consequences and reproduction

The full 125-source comparison changes only positive factory/query results for `01-04` and `01-1b`. Existing default APIs, strict-entry/Guard results and both old positive query paths compare equal. Generated metadata adds exactly three generic records: puzzle ID3 and direct ID46 in `01-04`, plus direct ID2 in `01-1b`. Every other room field, list completeness, source identity, quantity and floor artifact remains equal. These additional direct records are disclosed separately from the target's retained-playthrough gain.

The historical 2026-11-07 draft reports a 58-visit replay changing only ID3 Unknown to Uncollected and its room verdict Unknown to Incomplete. ID0 stays Unknown. Its Unknown rows decrease five to four against that earlier baseline. Those temporary inputs were subsequently lost; this paragraph is historical evidence rather than a fresh integrated replay. It reports equal door state, pose, visits, list completeness and every other tracker field, plus acquisition clear/set/clear, fresh construction and a separate private history close/reopen. Existing real scenario-contradicting creators still reject atomically with SAT0 or enabled SAT. Mutable descriptor type/amount/ID changes are separate existing unresolved-input behavior, not new quantity or immutable-payload claims. The dated recovery below supplies the current baseline and verification scope.

Private numeric evidence is `/tmp/re-map-re2-positive-0104-20261107-t3-4264dd15/`. `baseline-failure.txt` records the unchanged factory regression; `catalog-diff.json`, `census-diff.json` and `replay-verification.json` record actual production consequences. The adapted `owned_inputs.py` and `baseline_owned_inputs.py` explicitly point to this worktree and its private base snapshot rather than main. The frozen handoffs remain read-only: `/tmp/re-map-re2-0104-native-entry-20261107-0erigw56/handoff.json`, SHA256 `ef9c55424620fdd2c38e4ec4eac8d2d05d3d215eee6be7eb97b63e2c9d59035d`, and `/tmp/re-map-re2-0104-candidate-20261107-2bn0v4nh/handoff.json`, SHA256 `8594930b26d7a64a767caee6699d38f7515a97c29d718d7609348e11e2549a7b`. Their source/native windows, operand witnesses and manifests supply Candidate inspection evidence, not production APIs or gameplay endorsement.

Reproduce metadata with `tools/build_re2_metadata.py <owned-cue> <rooms-output> <floor-output> --profile profiles/re2_leon_a_slus00748.json`. Set `RE_MAP_RE2_OWNED_CUE` explicitly for the full Python suite and `tests/test_re2_positive_entry_domain.py`. Private `replay.py` uses only retained RAM SHA256 `939264d8e98c07e0d7afcdef69efdf1e18ac4fa05052575d726022b5dfdd8b73` and copied history SHA256 `3d8b4240e2a63d4c873d805304a77060e81d548e01690029dade132f4fd04d97`. It never opens the current user history.

Contributions, 2026-11-07: the human user approved the normal initialized unmodified engine premise and the bounded positive-presence scope. Implementation sub-agent, exact executing model `gpt-6.1-sol` verified by T3 runtime metadata, verified the frozen artifacts, adapted private reproduction roots, authored the shared control/entry compiler and focused regressions, generated metadata and ran retained replay. Local final diff review belongs to this contribution; root will conduct independent/external integration reviews. No copied/native runtime, external review or campaign confirmation is claimed.

### Recovery verification, 2026-11-12

Status remains Candidate for the named revision. The prepared checkout started exactly at `83bd4c70fea4ea7064069ef9f61c29b576233116`, including persistent-registration absence205, door-policy approval and constructor-owned four-point geometry. Recovery selectively applied the frozen patch, SHA256 `dae0070cc53c21261fa99cffcf4c664002042eefe9ad23ed6bcd64bb6981b585`. The old stopped checkout was read only. The November 7 temporary evidence and 58-visit history are unavailable; their five-to-four Unknown result above is historical draft provenance, not a recovered result.

The positive entry capability is mandatory for its additional operand and control roles. Existing positive sources retain their all-program effect check. The added path derives fresh entries from actual births, every callback/reset alternative and Gosub depths, while preserving every program's source bytes. The shared structured walker retains the old strict/Guard behavior; shared native IF-frame constants and the Break end-cell formula avoid independent arithmetic in the two analyses. Unentered `17:24` remains protected against numeric Copy, and any actual source edge restores its unsafe attachment obligation. No room/procedure whitelist or additional strict, Guard, absence, door or whole-source capability was added.

No registration API/domain adaptation was needed. The private prefix result remains `_DeclaredPrefixFacts(items, registered_slots)`, and both public positive queries unwrap only `.items`. Registered slots still come from the mandatory shared startup traversal. Registration and scoped selection still require exact protected-program and entry-location equality. For `00-09`, the existing all-canonical prefix/Guard domains and registered slots are unchanged, and scoped absence still includes IDs146/205. The narrower `01-04` capability cannot enter the registration consumer because its source kinds fail that consumer's separate contract. The incidental `01-1b` capability has all seven canonical entries. Neither case justifies a cast, subset comparison or broader absence right.

Fresh owned binding checks cover the same complete 69 resources, 125 sources and 54 auxiliary inputs, with exact executable identity stated above. `retained-controls.json` records each input's SHA256 rather than inheriting a private pickle. The all-source baseline/current API census preserves every default query, strict-entry result, Guard result, prior positive query and prior registration output. The committed numeric baseline fixture pins those outputs to `83bd4c7`; its Guard comparison uses explicit Unaudited task control, while the independent `00-09` regression binds real task-control authority and preserves absence205. The new positive factory/query results are limited to `01-04` and `01-1b`.

The full catalog changes exactly three records: puzzle ID3 and direct ID46 in `01-04`, and direct ID2 in `01-1b`. All other room fields, item-list coverage, raw alternatives, quantities and floor bytes remain equal. The first complete generation equals the checked-in candidate. Its room SHA256 is `3ea696c50dbe297613ec49303a8fc613ea9c2487b9d2971d550c131269c51cd9`; unchanged floor SHA256 is `641c6362a66333d97d2bfcf6c72d7edb0dcfbfd390a145f7248cc0b06cee2e8b`.

All residual positive-factory failures are inventoried in `final-census.json`: 89 Source failures and Binding failures for `00-1d`/`03-0c`; 34 factories are accepted. Of those, 24 positive queries are accepted and ten retain NativeContract failure: `02-00`, `02-09`, `03-0f`, `05-00`, `05-05`, `05-06`, `05-09`, `05-0e`, `05-0f`, `05-14`. These are capabilities for positive declarations, not a campaign-completeness count. The 89 Source failures are:

- Stage00: `00-00`, `00-01`, `00-02`, `00-04`, `00-05`, `00-06`, `00-08`, `00-0a`, `00-0c`, `00-11`, `00-12`, `00-13`, `00-14`, `00-15`, `00-16`, `00-19`, `00-1b`, `00-1c`.
- Stage01: `01-01`, `01-02`, `01-05`, `01-06`, `01-08`, `01-0d`, `01-0e`, `01-0f`, `01-12`, `01-15`, `01-16`, `01-19`, `01-1a`.
- Stage02: `02-01`, `02-02`, `02-03`, `02-04`, `02-05`, `02-06`, `02-07`, `02-08`, `02-0a`, `02-0b`, `02-0c`, `02-0d`.
- Stage03: `03-00`, `03-01`, `03-02`, `03-03`, `03-04`, `03-05`, `03-07`, `03-08`, `03-09`, `03-0a`, `03-0b`, `03-0d`, `03-0e`, `03-10`.
- Stage04: `04-00`, `04-01`, `04-02`, `04-03`, `04-04`, `04-05`, `04-06`, `04-07`, `04-08`, `04-09`.
- Stage05: `05-01`, `05-02`, `05-03`, `05-04`, `05-07`, `05-08`, `05-0a`, `05-0b`, `05-0c`, `05-0d`, `05-10`, `05-11`, `05-12`, `05-13`, `05-15`, `05-16`, `05-17`.
- Stage06: `06-00`, `06-01`, `06-02`, `06-03`, `06-04`.

The parent subsequently supplied three read-only personal Leon A save copies and extracted version94 RAM. The parent's extraction uses DuckStation serializer commit `1bc5405c417d8f8f61cc5eac624aac9f4b0677eb`, four game-code witnesses and exact Bus-to-DMA serialization boundaries. This contribution reads only those supplied RAM/manifest/replay inputs and does not retest the serializer or load an emulator. `retained-replay.json` and `retained-replay-comparison.json` separate current-only, the two snapshot-observed sources, and a simulated 125-source visit scope. The first two scopes are exactly equal to the parent's baseline, including `03-08`'s four Taken items and Unknown verdict, and `03-0a`'s Cleared verdict. The simulated scope changes only ID3 in `01-04` and ID2 in `01-1b` from Unknown to Uncollected, both room verdicts to Incomplete, and the resolved reason in `01-1b`. Across all three saves and reverse order, Unknown item rows decrease 67 to65 and Unknown rooms37 to35. Every other tracker field is equal, including doors, unlock state, pose, visits, list completeness and ID0. These 125 visits are synthetic, not recovered history or campaign coverage. Direct ID46 is already Taken in these saved inputs, so its additional catalog record causes no replay change.

Fresh committed synthetic tests cover clear/set/clear acquisition, current/departed/reentered source states, visits-only close/reopen and complete earlier-memory replacement. An active descriptor paired with an acquired flag is deliberately excluded from the coherent synthetic collection state; the reader's existing torn-state rejection is retained. Independent pickup46 stays uncollected and keeps the lifecycle room Incomplete, while ID0 stays Unknown. Read-only saved-RAM controls separately reverse ID3 and an existing departed-door applicability bit, compare fresh reconstruction and require all other rooms/all doors to stay equal during the acquisition experiment. These controls change private in-memory copies only. They prove neither native save restoration nor memory-card persistence.

The 185 copied-original-handler cases were freshly rerun against the actual owned executable. They retain the complete FOR/NEXT count/frame cases, WHILE, Gosub/END/Return, root END, DO/WHILE and Break cases described in the recovery review. No handler bytes, PC repair, native stubs or memory-write hook are used. This is bounded CPU execution against synthetic inputs, separate from source inspection, saved-RAM interpretation and native gameplay. The fresh evidence directory is `/Users/adamekka/.cache/re-map/evidence/2026-11-12-positive-entry/`; the supplied immutable inputs remain in the parent's separate `2026-11-12-leon-a-save-replay` directory. No old `/tmp` path supplies current verification.

Contributions, 2026-11-12: implementation sub-agent `gpt-6.1-sol`, `xhigh`, verified from the executing Codex session's matching `session_meta` and latest `turn_context`, recovered the source/compiler/tests, preserved registration contracts, added corpus/lifecycle regressions and shared native arithmetic, ran the fresh source/copied-handler/saved-RAM controls, and authored this recovery record. The human user supplied the scope, trust approvals and task constraints. The parent supplied read-only save extraction and baseline replay; those are distinct from this contribution's implementation and comparisons. Local review covers authority construction/consumption, all protected source roles, native receiver/frame consumers, shared traversal equivalence, exact registration compatibility, generated consequences and fresh publication/reversal. Independent and external review remain with the parent; no endorsement or gameplay confirmation is claimed here.


The additional complete bound-task-control census also finishes for all125 sources. `baseline-census-complete.json`, `final-census-complete.json` and `census-comparison.json` retain every result, including all30 accepted scoped queries and all prior accepted registration outputs. Every default query, strict/Guard result, strict/scoped query and prior positive/registration output is equal; only the two disclosed positive sources change. This check is separate from the committed Unaudited-control snapshot and adds no task-frontier policy change.

The committed README scene fixture, SHA256 `cd580a030af6a11526fb2ef5c6e32d61f0ab662aba707fe5f07eb37eebd108a3`, replays without an emulator and reproduces publication SHA256 `0d55d2ed9a40441bd90cf22ca2dcdb138d4937160ee651a95f3a11567b64f3f2`. No rendered UI source changed. Screenshots were explicitly excluded from this task, so neither README image was regenerated; their existing bytes are retained. The lost RE2 screenshot/replay inputs were not invented or substituted.

`domain-inventory.json` further classifies every residual factory failure through the added compiler:46 source-control failures,22 protected-source-write failures,21 remaining source-effect failures, and the two Binding failures. It lists all125 results, including derived entries versus protected programs when available. Passing this unsealed domain analysis alone never grants positive facts or overrides the old positive path. No residual Unknown was replaced by guessed clearance.

Final local verification passes 7,370 Python tests with explicit owned CUE, including all72 feature cases. Both complete metadata generations match the checked-in candidate byte for byte and preserve every floor byte. Scoped Ruff E4/E7/E9/F/I with the established E402 exclusion, formatting for all seven changed Python files,431 local documentation links/anchors, and staged/unstaged whitespace checks pass. The read-only README fixture replay also passes. The first full-suite attempt used an incoherent synthetic acquired/enabled descriptor pair; the corrected fixture keeps the existing reader rejection and the final complete rerun passes. No production failure was masked. Local review has no residual finding within this increment. Parent independent/external review and combined integration verification remain outstanding.

### Parent integration verification, 2026-11-12

Root integrates the reviewed implementation onto `59c036f`. The fresh parent
suite passes all 7,370 tests with the explicit owned CUE. A complete parent
generation matches the integrated catalog byte for byte, SHA256
`3ea696c50dbe297613ec49303a8fc613ea9c2487b9d2971d550c131269c51cd9`,
and preserves the baseline floor artifact. Scoped Ruff, formatting, local links
and whitespace checks pass.

Root independently compares every tracker leaf across all 15 supplied real-RAM
publications. Exactly five fields change in each of the six simulated full-source
publications: the two expected item states, their room verdicts and `01-1b`'s
resolved reason. Every other tracker field is equal. The current-only and two
observed-source scopes are entirely equal. No historical visit file is invented.

Independent same-provider reviewer `review_partial_positive_entry` finds no
actionable issue in the final commit. It reruns 231 focused cases, the 185 copied
frame/loop/return controls and 15 base/final saved-RAM publications. Its 54
additional complete copied EventExec/installer cases cover startup callers 0/1,
selectors 2..9/FF and empty/full/one-free ordinary pools. Startup bytes remain
unchanged except caller PC+4; workers are not dispatched inline. Root separately
reviews capability construction, affected callers and registration compatibility.

Configured Claude Opus 5.5 is disabled. Gemini 3.8 Flash's review fails to open
its provider session, so neither supplies an external endorsement. Root evidence
is under `/Users/adamekka/.cache/re-map/evidence/2026-11-12-positive-entry-integration/`;
the independent review is in `2026-11-12-positive-entry-final-review/` alongside
it. Root and the independent reviewer verify exact executing model
`gpt-6.1-sol`, effort `xhigh`. These checks add no native gameplay or save-restore
confirmation and leave the full source-coverage gaps open.
