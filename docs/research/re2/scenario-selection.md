# RE2 scenario selection

[Documentation index](../../README.md) · [Claim index](../../research.md) · [RE2 guide](../../re2.md)

## RE2-SCENARIO-001: scoped scenario facts resolve two explored room checks

Status: Candidate for Resident Evil 2 Dual Shock Ver. USA Disc 1, SLUS-00748, Leon A, Original Game, Normal. Owned-source inspection, copied native execution and retained RAM replay support this correction. No new gameplay, collection, reentry or native savestate restore is observed. This claim does not generalize to another revision or scenario.

The human reports that many explored rooms still have unresolved checks. The previous vibration correction resolves one 2F check but cannot establish all later native effects in the remaining sources. This investigation separates stable scenario selection from whole-source continuation and from positive item presence.

### Identity and native domain

The executable is `SLUS_007.48`, 987136 bytes, SHA256 `e576348f64d015ecff6e1ce875a8924ee252ba7f3f9478b0917cbbdeb97db441`. The installed DuckStation identifies itself as `0.1-12083-g00e299795`; the copied user saves have container version 87. No emulator is launched for this investigation. No health/ammunition patch is enabled, and no user history or tracker lock is acquired.

The compiler reuses the existing startup-declaration contract, which binds the executable, 69 native resources and 125 owned room sources. Hashes select the inspected native recipe; they do not establish write effects by themselves. The recipe covers initialized engine records and owned resource heaps. It is not a proof for arbitrary pointer corruption, patched guest code, unrelated DMA or normal memory-card loads.

All addresses below are PS1 virtual RAM, not host addresses or raw RAM offsets. Multibyte values are little endian.

| Field | Address | Width and mask | Requirement |
| --- | --- | --- | --- |
| STATUS / script bank 1 | `0x800CFBD8` | four bytes, mask `0xC0000000` | Bank bits 0 and 1 are both zero for this profile |
| SYSTEM | `0x800CFB74` | four bytes, reset mask `0x00001000` | Reset bit clear on initial read and coherence reread |
| Native free-work pointer | `0x800CE32C` | four-byte pointer, mask `0xFFFFFFFF` | Four-byte alignment, at or above loaded section 2 and at or below `0x80200000`; independently reread |
| Loaded source base | existing section-derived address | four-byte pointer | At or above `0x80100000`; section 2 at or above base + 100 |

The existing revision, scenario, mode, player, source-witness, acquisition and atomic coherence gates remain mandatory. Soft reset needs the additional SYSTEM guard: native reset clears STATUS before the player and acquisition fields, leaving an interval where old gameplay data otherwise passes. The ending overlay changes scenario but overwrites mandatory room-source witnesses. Both boundaries reject publication in copied controls.

A source census checks all 125 room files for physical aliases of the two protected STATUS bits, including wrapped kind-six writes and Copy targets. No legitimate source-directed writer reaches either bit. The native inspection finds 78 core literal STATUS stores preserving those bits. Fourteen common overlays are inspected. Fifty-six actor code images contain 112 literal STATUS stores; two dynamic selector cases require the initialized model-33 selector domain, 28 or 29. Injected selectors 0 and 1 deliberately violate that premise. This is a revision-specific native-domain argument, not a complete machine-code points-to theorem.

### Separate source and presence capabilities

`scenario_entry_scope` qualifies ordinary canonical procedure entries, call/IF/shared-loop storage, native constructor roles, counter/member destinations and explicit source writes. It rejects unsafe task replacement, unbounded Goto, unmodeled constructor states and attachment registration whose native queue can reach task storage. It checks every source Copy, including in procedures unrelated to the target. Copies can change only certified scalar values; they cannot redirect guards, creators, calls, resource selectors or callback control.

Camera commands `4B` and `61`, floor command `38`, model relocation and SCA updates have shared source read/write footprints. Camera swaps are analyzed as transpositions before first-match writes. Mutable record fields cannot alias SCD, model assets or later lookup dependencies. An out-of-range floor index is an explicitly bounded native no-op, not guessed continuation.

The item query starts each relevant procedure at its qualified canonical entry, explores both outcomes of unknown numeric predicates and prunes only the immutable scenario guards. Creators and reset alternatives remain part of the same identity query. The resulting scoped variant/exclusion facts do not set `fixed_context_preserved` and do not establish presence, task termination or whole-source continuation.

Positive presence still uses the existing finite startup-prefix intersection. It requires a declaration on every admitted prefix, bounded calls and synchronous setup, the existing object/cache/heap checks, and source selection. A per-procedure initializer-control receipt permits the finite Copy/music block in the Art Storeroom without inheriting unrelated procedures' capabilities. All source Copies and global call height remain checked; partial receipts cannot authorize the whole-source context proof.

The new native receipt admits model render flags `0x12` for this prefix. Copied synchronous setup comparisons for flags `0x10` and `0x12` have identical writes except the supplied flag field. The extra bit supplies no write destination. This is not deferred-render lifetime or GTE-tail validation.

Alternate item payload flag `1` retains the descriptor and enters player pickup animation before requesting the same mode-two item UI as flag `0`. Only the new audited positive path accepts flags `{0, 1}`. The shared packet predicate retains its old flag-zero default and rejects higher bits. This establishes a source-declared ordinary collectible, not physical reachability, animation completion or awarded quantity. The source amount remains subject to the existing quantity contract.

### Generated outcomes and retained limits

Only two sources gain interpretation facts; their raw creators and whole-source capability fields remain unchanged.

| Source | New fact | Result in both copied user saves |
| --- | --- | --- |
| `01-00`, 1F Main Hall | ID 152 selects type 20 at source offset 10168 | Generic Collected becomes the identified collected item; the complete item check clears |
| `00-0b`, 2F Art Storeroom | ID 98 excluded; IDs 95 and 99 have guaranteed direct declarations | Unknown becomes Incomplete with two named remaining pickups; collection remains required |

The Art source is `PL0/RDT/ROOM10B0.RDT`, SHA256 `7e628f4ac91a051f6c1974e95c5f400e7ecaf7a023989846537b3b15fe5b69dc`. ID 95 is type 62 at offset 6076. ID 99 is type 21 at offsets 6166 and 6230, with payload flags zero and one respectively. The Main Hall source is `PL0/RDT/ROOM2000.RDT`; its exact size/hash remain bound by the revision's existing source corpus.

Rooftop and East Office deliberately receive no new facts. Rooftop's source-directed Goto can underflow the native IF/loop stack and expose another worker's control storage. East Office can replace its own kind-five callback worker, then advance the new PC by two into opcode `FF`, whose table entry is not a valid aligned handler. Suppressing these entry barriers in diagnostic experiments can select plausible identities, but those experiments are rejected as production evidence. The side entrance corridor has an independent later reset for ID 205, so its opposite-mode startup declaration alone cannot prove absence. Other unproven departed presence and puzzle/reset identities remain Unknown.

### Reproduction and verification

Private evidence is `/tmp/re-map-unresolved-shared-20261101/`. Original owned executable/RDT bytes stay outside Git. `positive-owned-compiler.py/json` binds the real owned corpus and factory receipts before comparing legacy and new outcomes. `scenario-writer-census.py/json` records the source alias census. Native instruction ranges and their SHA256 values are recorded alongside each copied experiment.

- `native-scenario-boundaries.py/json`: 210 reset/title/ending controls, including the mid-reset rejection requirement.
- `native-actor-selector.py/json`: 720 initialized-selector cases and 720 injected negative controls.
- `native-art-entry-controls.py/json`: 784 complete member-command controls and ten constructor-preset selection controls.
- `native-art-render12.py/json`: 56 complete synchronous setup-head executions across all fourteen tasks and the two Art model packets. No deferred-render claim.
- `native-art-pickup-flag1.py/json`: 112 complete creators, 56 complete dispatches and 28 explicit player-state/substate menu bridges. All final 2 MiB RAM matches independently predicted stores. The menu bridge explicitly selects substate two; it does not prove animation progress or an inventory award.

Copied execution uses Unicorn `2.1.4` and Capstone `5.0.7`, with original instructions, complete RAM comparisons and the shared MIPS code-hook store decoder. No call stubs, code patches or memory-write hooks are used for the complete controls.

`compare-final.py` reconstructs exploration from a private history copy for 52 retained captures and the two new save copies. All 43 Display publications change only these two room records; eleven Retry captures remain atomic. Every other room, door, position and visit publication agrees. Both new save copies show Main Hall Cleared and Art Storeroom Incomplete. These are file replays, not emulator restores. Source coverage and gameplay-readiness claims do not increase.

Regression tests cover collection clear/set/clear, departed known presence, a new tracker after each change, excluded live creator contradictions, partial-receipt isolation, source aliases, constructor roles, shared frame bounds, reset/work coherence, malformed metadata and old-profile opt-out. All 4378 Python tests pass. The existing RE1 and RE2 browser checks pass, covering 118 and 133 outlines respectively. Repeated owned-disc generation matches both checked-in outputs; floor-plan bytes remain unchanged. Scoped Ruff lint/formatting, whitespace checks and all 655 local documentation file targets pass. The README screenshot is refreshed from the copied explored state, without emulator or real history access.

Final review checks the scenario/source-entry split, positive prefix intersection, Copy aliases, partial receipts, packet defaults, constructor/work bounds, generator opt-out, metadata validation and fresh runtime publication. Verified findings are fixed before completion:

| Finding | Category / priority | Impact and fix | Difficulty |
| --- | --- | --- | --- |
| 1 | Correctness, P2 | Model attachment registration can append into native task storage. The entry factory rejects packet `2D` attachment flags `0x40/0x80`; regressions retain ordinary model setup and reject repeated attachment registration. | Low |
| 2 | Correctness, P2 | Passing a scenario receipt with a failed entry receipt violates the positive compiler's paired-capability invariant. The generator now opts into the new prefix only when entry qualification succeeds; other sources use both explicit Unaudited alternatives. Full owned-disc generation verifies this path. | Low |
| 3 | Tests, P2 | The new Art reversal test used a neighboring item-type label, and the old unaudited direct-pickup test hit the new dependent guard first. Corrected the label to source type 90 and removed the dependent scoped contract in the negative fixture, retaining the intended audit diagnostic. | Low |

The independent native review finds no remaining production issue after these corrections. Gemini `gemini-3.8-flash`, high reasoning, returns "No findings" after reviewing both new scenario modules, the integration/producer diffs, positive-consumer excerpts, selected regressions and bounded native-evidence summary. Its prose review performs no runtime validation. Claude `claude-opus-5-5` is unavailable because the configured provider is disabled; no substitute or endorsement is recorded. Root's final review preserves the Candidate status and the seven remaining unresolved rooms.

Contributions, 2026-11-01: the human supplies the unresolved-room screenshots and playthrough evidence. Root, exact model `gpt-6.1-sol`, authors integration, runtime guards, profile validation, scoped initializer production, regressions, generation, replay and this entry. The `roof_checks` agent, the same verified model, authors scoped selection/write footprints, positive-prefix support and focused regressions. The `prefix_entry_audit` agent, the same verified model, authors the ordinary-entry factory and frame/write regressions. The `corridor_checks` agent, the same verified model, authors native-domain and copied-execution evidence and independently reviews the implementation. Authorship, review and copied execution are separate from gameplay confirmation.

## RE2-SCENARIO-002: side entrance exclusion needs two constructor roles

Status: Candidate source investigation for the same Resident Evil 2 Dual Shock Ver. USA Disc 1, SLUS-00748, Leon A, Original Game, Normal revision. The native entry extension remains unqualified. No item exclusion, presence rule, room verdict or production code changes. This follow-up uses owned-source inspection, real production proof factories and retained RAM replay; it adds no copied native execution or gameplay observation.

### Retained baseline and source candidate

The executable remains `SLUS_007.48`, 987136 bytes, SHA256 `e576348f64d015ecff6e1ce875a8924ee252ba7f3f9478b0917cbbdeb97db441`. Owned `PL0/RDT/ROOM1090.RDT`, source `00-09`, is 287656 bytes, SHA256 `785c0c49c56f49a11829c1a98718a867d851893e372d0179d9ce06a63898c4d0`. Both are freshly extracted from the supplied Leon CUE using the existing ISO helpers. The actual startup-declaration factory binds all 69 required native resources and all 125 owned source hashes before the source-entry query runs. These bindings identify the inspected resources; they do not establish their native write effects.

The retained `/tmp/re-map-used-keys-20261103/slot1.ram` has SHA256 `939264d8e98c07e0d7afcdef69efdf1e18ac4fa05052575d726022b5dfdd8b73`. A private reconstruction from its copied visits-only history returns Display with 58 visited sources and current source `00-17`. Side Entrance Corridor `00-09` has a complete three-item list, no collected items and an Unknown room verdict. IDs 13, 146 and 205 each remain Unknown. The complete publication exactly equals that directory's retained `slot1-corrected.json`, including every other room and door. This is saved-RAM interpretation, not an observed savestate restoration. The previously tested emulator identity remains the historical `0.1-12083-g00e299795`; this investigation tests no emulator build or producing-save compatibility.

ID 146's only decoded creator is source offset 9054 in `17:3`, slot four, type 38, quantity one. The IF at 9046 checks scenario bank 1 bit 1 set at 9050. The coherent retained Leon state has that scenario bit clear. This is a candidate for the existing scoped exclusion query, not sufficient evidence to publish absence before native entry qualification succeeds. No decoded slot-four reset supplies another identity. ID 205 has an independent item reset at 13172 in `17:35`, so pruning an opposite-mode startup creator cannot exclude it. ID 13's zero-activation declaration and callback retain their separate obligations; neither item receives knowledge from this investigation.

All source offsets here are RDT-file bytes. Native addresses below are PS1 virtual addresses, not host addresses or RAM-file offsets. Multibyte fields are little endian.

| Retained field | Address | Width and mask | Observed value |
| --- | --- | --- | --- |
| Scenario bank 1 bit 1 | `0x800CFBD8` | four bytes, `0x40000000` | Clear |
| ID 146 acquisition | `0x800D48CC` | four bytes, `0x00002000` | Clear |

### Actual factory rejection and independent constructor roles

The unmodified `scenario_entry_scope` factory returns `ScenarioSelectionFailure.EntryScope` at `16:0`, source offset 8472. That `Enemy_set`, opcode `44`, requests model `0x2A`, preset `0x0200`, slot zero. The current native-entry recipe admits only model `0x22` with presets `0010/4011/4402`. No fabricated receipt or bypass experiment is used. Since the factory produces no `VerifiedScenarioEntryScope`, the scoped item query is not invoked.

The model is the unsigned byte at packet `+3`, mask `0xFF`; the preset is the unsigned two-byte little-endian value at `+4`, mask `0xFFFF`. The native handler reads the slot at `+2` as a signed byte. All listed source slots are nonnegative and below 32.

The first rejection is not the complete required extension. The same source has two independent constructor roles:

| Model | Source procedures and examples | Presets requiring qualification |
| --- | --- | --- |
| `0x2A` | `16:0` at 8472; `17:3` at 8784 | `0200/8800` |
| `0x21` | `17:7` through `17:11`; `17:9` at 10018 and `17:10` at 10152 are on Leon scenario paths | `0000/0040/4000/4040/4002` |

The factory checks every canonical procedure. Qualifying only model `0x2A` cannot provide the complete source-entry receipt. The earlier scenario-word census in RE2-SCENARIO-001 does not replace these constructor, task and callback ownership obligations. The independently rejected whole-context opcode `85` at 9248 is left separate; no continuation rule for it is investigated or added in this follow-up.

### Native loading and callback obligations

The complete `Enemy_set` handler is `0x8005714C..0x80057714`, end exclusive, SHA256 `178350b14ecebc82eace0a9a28ccfab8b2c6cac8a27a2fbf72680a5a07a57825`, including its return delay slot. It stores the current source PC in global pointer word `0x800D5BE8`. The acquired-enemy branch skips construction and reaches the final 22-byte task-PC advance. A constructed actor consumes `0x248` bytes through the four-byte free-work pointer `0x800CE32C`, plus model, part, mesh, shadow and temporary-loading allocations. This handler inspection does not bound all stores made by its callees.

The model loader at `0x8001AAA8` calls cooperative yield `0x80031F94(1)` at `0x8001AB74`, before that final script-PC advance. Its inspected interval `0x8001AAA8..0x8001AD38`, end exclusive, has SHA256 `8ff483d90bc172e55e95fba1f970153e217b6ecd4226fd3a872903f58e5d5304`. The new-resource return path restores phase byte `0x800D8CC8` and main procedure-table pointer word `0x800D8CBC` at `0x800574F0/0x800574FC`. The byte and pointer masks are `0xFF` and `0xFFFFFFFF`. Those restorations do not establish task-frame or source ownership during suspension. The selected incoming models are `00/07/08`; the earlier [constructor suspension audit](startup-declarations.md#constructor-suspension-and-interpreter-ownership) for incoming `02/0A` cannot be transferred by target-room identity.

The native actor resource table is `0x8009ADF4`, with eight-byte records containing unsigned four-byte sector and width fields. Sectors are 2048-byte archive blocks, not RAM addresses. Owned `PL0/PLD/CDEMD0.EMS` is 11124736 bytes, SHA256 `8724200c1ed5e8d3235ceb85640893467eb9878c2a016529aa84b49a79916fca`.

| Code resource | Sector | Bytes | Load address | SHA256 |
| --- | ---: | ---: | --- | --- |
| Model `21`, index 68 | 1310 | 19080 | `0x8010D000` | `182339ba7995cb36537297ac8a9e3f6100546f8636afff7e62943beefae469db` |
| Model `21`, index 69 | 1320 | 19080 | `0x80100000` | `321388df639be19753065422407d77a86eda8909615e9a8ad3e53fb253aef778` |
| Model `2A`, index 104 | 2194 | 20240 | `0x8010D000` | `2b8bcf2ac5da9579dc7f45efa654a0429db68d0a5243f6b196fc683f9e825606` |
| Model `2A`, index 105 | 2204 | 20240 | `0x80100000` | `710cedb28f9e778466c3ca50e9bd69911de5356d744dcecbdd7c444bc61da193` |

Model `2A`'s motion resource 106 is 66592 bytes, SHA256 `d7c9e0d7032d1cecb565928c321d7ed0354f62ea90e14038cf2720e04b2937d3`. Model resource 107 is 138372 bytes, SHA256 `f9d7aeec3c551008c82444298e1c448534aef2f97ac6656fce212969ff265ad3`; its TMD declares 32 objects. These sizes and code locations do not supply a complete heap or deferred-update lifetime bound.

In code pool zero, model `2A` initialization at `0x80101318` installs callback address `0x80104460` into global four-byte pointer `0x800CE3A8`, mask `0xFFFFFFFF`. That callback dispatches through table `0x80104F04` using unsigned actor byte `+5`, mask `0xFF`. Main update `0x80101194` also dispatches actor byte `+4` through table `0x80104E38` and may call the four-byte pointer at actor `+0x220`. The inspection identifies mandatory caller, selector, argument, actor/part and code-pool lifetime obligations. It does not prove that these callbacks are unsafe, or that preserving literal STATUS masks makes them safe for source-entry qualification.

Both dispatch tables and actor `+0x220` contain four-byte little-endian pointers with mask `0xFFFFFFFF`; actor byte `+4` uses mask `0xFF`.

A sound shared extension still needs initialized allocation bounds for skip/new/reuse/shared-resource paths, exact incoming auxiliary isolation during the yield, and bounded constructor/update/callback effects for both models and all requested presets. Protected scenario words, source packets and native call/IF/loop/task storage must remain within the existing capability contract. No harmful native counterexample is demonstrated; the required contract remains unproved. Expanding the preset whitelist alone is rejected. Resolved item outcomes are zero, and room clearance is not inferred.

### Evidence and reproduction limits

The initial replay and source diagnostic are private under `/var/folders/9d/q5n746z953bcs654g_1sqcy80000gn/T/re-map-side-entrance-20261106-jz0s4sm7/`. The constructor follow-up is under `/var/folders/9d/q5n746z953bcs654g_1sqcy80000gn/T/re-map-side-constructor-20261106-83ttc6_o/`. Owned bytes, RAM and copied history remain outside Git.

| Follow-up evidence | Bytes | SHA256 |
| --- | ---: | --- |
| `constructor-audit.json` | 7569 | `da8f52b812d59f0ca8692a15ed826e1e4248660e87a79d340a3fa0fdfc1cd215` |
| `factory-recheck.py` | 3952 | `01562c2bbe1557b99f6de6aec976f0d819359a46bbae76bc27e60425ccafaf9e` |
| `factory-result.json` | 1376 | `1d5280ad9737baa6e2a3db9be748f2e839f2cacd4927cd3e0c5f1023ccc5c6e2` |
| `replay-result.json` | 271 | `7ac06176fb2db176473f022f568722439fbe1a6b389ac3c19a10eb88853e034c` |
| `unchanged-publication.json` | 82214 | `3b0ab193ae6528dcc7e5b142a5ed1ff1b5b958dfe051322cae02522b538c1d1d` |

Copy the factory/resource scripts into a fresh private directory before reproducing, preserving their original reports. `factory-recheck.py` binds the real resources/corpus and records the actual rejection. `resource-audit.py` extracts the code windows and model-`2A` code resources; the additional model-`21` and model-data manifests identify their archive slices. The replay reads only the pinned RAM and copied visits, then compares the full publication with the retained corrected JSON. It never opens production history for writing. The artifact manifest records the remaining evidence hashes and inspection corrections. Linear disassembly includes tables/data and is not a reachability proof; an earlier incomplete handler window is superseded by `enemy-set-complete.asm` with the return delay slot.

No copied native execution, callback probe, emulator action, gameplay input, savestate load, health/ammunition patch, history modification or external-model review occurs in this investigation. Historical source and review authorship above remains unchanged.

Contribution, 2026-11-06 UTC: the human's unresolved-tracking request supplies the task priority; retained playthrough RAM/history keep their original human provenance. The `review_re3_detail_tables` investigation agent, exact model `gpt-6.1-sol`, reasoning effort `xhigh`, verified from its matching `session_meta` ID and latest `turn_context`, authors the source/resource inspection, real-factory diagnostics, replay comparison and this record. This is investigation and documentation authorship, not an independent review or runtime confirmation.

## RE2-SCENARIO-003: rooftop control spill needs a lifetime proof

Status: Candidate source/control investigation for the same pinned Leon A Original/Normal revision and executable. The ordinary-entry factory remains unqualified and the retained Rooftop result remains Unknown. This follow-up narrows the [unsigned Goto spill](dualshock.md#follow-up-unsigned-goto-depth-audit-2026-10-28) from a task-local objection to its actual receiving-side consumers. It supplies no item identity, presence, absence or clearance fact.

Owned `PL0/RDT/ROOM1080.RDT`, source `00-08`, has SHA256 `0f2975b8ae167c2b5ab6f4a605496d2a8ffeab0f5170c407e2d61a75da876fe6`. The retained RAM hash and private 58-visit baseline are the same as RE2-SCENARIO-002. Acquisition ID 213 remains generic Taken with an incomplete identity list. Its three decoded creator alternatives are at file offsets 6934, 6976 and 7010. A private diagnostic that suppresses entry guards can select a plausible identity, but it remains rejected evidence and is not rerun here.

All native addresses below are PS1 virtual, all source offsets are RDT-file bytes, and multibyte words are little endian. The native task stride is `0x174`. Source Goto at 7706 sets the encoded IF depth to unsigned byte `0xFF`. At root call depth, its next IF uses `task + 0x4C0`, which equals the record three task slots later plus `0x64`. It stores source pointer `source_base + 7534` there. The target is a four-byte control word, mask `0xFFFFFFFF`, not private storage belonging to the writer.

Under explicitly legal frame inputs, native Break at `0x80054268..0x800542B4`, end exclusive, reads `task + 0x60 + 16 * callDepth + 4 * loopDepth`. Call depth zero and loop depth one consume `+0x64` directly as the next PC, decrement loop depth to zero and restore the byte IF depth from `task + 0x0D`. WHILE overwrites its own end pointer before reading it; ENDFOR, ENDWHILE and EDWHILE use loop-start words. The writer's false-IF scheduler block can also consume the freshly written pointer before its ordinary handoff. That block is bounded evidence, not a complete scheduler execution.

Offset 7534 is a decoded `0x51` command inside `17:3`, but not its canonical entry. An injected Break continuation reaches it with inherited control state. Its next switch then uses loop slot one instead of canonical slot zero. A decoded boundary or a pointer remaining inside the source therefore does not establish safe continuation. Allowing arbitrary inherited continuations can propagate further Goto/IF stores beyond the fourteen-record pool; this is a proof counterexample domain, not demonstrated gameplay reachability.

The complete native ordinary reset at `0x80052F3C..0x800530C0` clears activity and control depths for task slots 0–9 while leaving auxiliary slots 10–13 untouched. It does not clear the root `+0x64` word. With that reset, the source's ordered startup births and the fixed Leon scenario guards place worker `17:3` in ordinary task two or three, targeting task five or six. Only `17:1` and `17:3` contain Break commands. These facts suggest a narrower source-bound lifetime argument, but do not prove its mandatory premise. Every later effect and callback must preserve allocation/control ownership, the writer's location and the legal receiving-frame domain. Current factory roles for `4C`, `6B` and `74` also remain unqualified for this source.

New evidence is `/tmp/re-map-rooftop-consumers-20261106-qdehyt7n/investigation.json`, 12569 bytes, SHA256 `f0bc8e21036df21e0782e305b66c2c3422ea5ff938a4e3d3588e7f89d7610b47`. It records 27 complete copied native calls and one bounded scheduler block, using original instructions, decoded-store checks and full 2 MiB RAM comparisons. Earlier 114 controls under `/var/folders/9d/q5n746z953bcs654g_1sqcy80000gn/T/re-map-rooftop-entry-20261106-ecav_2f7/` are referenced without rerunning them. Preserve both reports when reproducing into a fresh private directory. No emulator, gameplay input, savestate restore, user-history write, production relaxation or external-model review occurs in this follow-up.

Contribution, 2026-11-06 UTC: the `investigate_gdb_recovery` agent, exact verified model `gpt-6.1-sol`, reasoning effort `xhigh`, authors the source investigation and copied-native experiments. Codex root, exact runtime model `gpt-6.1-sol`, checks the report hash, control formulas, bounded/complete-call distinction and unchanged production policy, and authors this dated record. Original research and human playthrough provenance remain unchanged. These contributions are not gameplay confirmation or independent model endorsement.

## RE2-SCENARIO-004: fresh root replacement resolves one collected identity

Status: Candidate for Resident Evil 2 Dual Shock Ver. USA Disc 1, SLUS-00748, Leon A, Original Game, Normal, using the pinned executable in RE2-SCENARIO-001. A source-bound native-entry extension resolves a specific explored-room identity check. Source inspection, copied native execution and retained-file replay support it; no new gameplay, collection or native save restoration is observed.

Owned `PL0/RDT/ROOM2140.RDT`, source `01-14`, is 88224 bytes, SHA256 `f1b4592412c007fc3531f00bf25510dc04dd6e53eead536b3f2e6c987836b9f0`. ID 68 has creators at file offsets 1006 and 1032, with types 22/21 and quantities 8/7. The fixed Leon scenario, bank 1 bit 1 clear, selects offset 1032. The previous real entry factory rejects `EventNext` at 1420, then render update `74` at 1562. Without an entry receipt, the collected item remains generic and the list check incomplete.

### Mandatory source-entry rules

The [entry factory](../../../src/games/re2/scenario_entry_scope.py) admits canonical `03 00 18 target` only from main `17:` procedures, when the target is a bounded canonical procedure and the source procedure cannot be a synchronous callee. It computes the source-wide callee closure and rejects every replacement source in that set. This also rejects a positive-depth replacement chain at its first such caller. The old procedure terminates at replacement; its target independently passes the existing fresh control-frame and root-inclusive call-height checks. This recipe grants no initializer or auxiliary-table borrowing right. Other replacement, cancellation and Goto barriers remain in force. Source/write/callback/resource binding remains mandatory.

Native `EventNext`, `0x80053878..0x800538A4`, calls initializer `0x800530EC..0x80053138`. It resets root IF/loop bytes but preserves the byte call depth. Positive-depth controls retain stale deeper frames, so a canonical target alone is insufficient. It reads the current procedure-table pointer at PS1 virtual `0x800D8CBC`, u32 LE, mask `0xFFFFFFFF`. Ordinary startup `0x800535D4..0x80053608` switches that pointer to the main table before dispatch, while auxiliary execution can temporarily borrow another table; this extension therefore retains an explicit main-procedure scope. In this source, synchronous calls reach only `17:2/17:4`; both replacements are in `17:3`, targeting entries 1688/1766 in `17:5/17:6`. The sole kind-five callback declares `17:3` at slot seven with `FF 00 18 03 00 00`. Its descriptor can be created inside Gosub, but later native allocation creates a fresh root worker. No source `Aot_on` directly dispatches that callback slot. The scoped item query itself gains no `03` interpretation; ID 68's creators are in `17:0`.

Render update `74` reuses the existing initialized-renderer ownership contract for `53`, only after a conservative source recipe qualifies. A same-record `53` initializer must precede ordinary Sleep and the bounded FOR whose body is exactly `74`, yield, NOP and ENDFOR. The full existing control walk proves that every path to `74` passes that initializer; lexical adjacency alone is insufficient. The position-union graph conservatively retains all state-specific edges. Bypassing branches, mutations and unsupported control reject. Record selectors must be below four, blend modes below four and RGB masks at most seven. Every `53` in a source containing `74` must satisfy those domains too, including independent workers that can run during Sleep.

Native `53`, `0x80057EF0..0x80057FD8`, initializes one of four 76-byte records beginning at PS1 virtual `0x800DFC1C` through `0x8002C1A0`, then calls `0x8002C2B0`. Native `74`, `0x80057FD8..0x80058028`, calls the same helper, `0x8002C2B0..0x8002C324`, with a signed i16 coefficient from packet `+2`. It changes the coefficient/color/default rectangle without replacing the record's ordering index, blend/control fields or dynamic ordering-table pointers. The ordering index is native constant seven at `0x80057F14`, not packet byte `+3`; that source byte is the RGB mask. The source uses record two, initializer 1546 and update 1562. Multibyte fields and pointer words are little endian, with full i16/u32 masks `0xFFFF/0xFFFFFFFF`; packet selectors are u8, mask `0xFF`.

The proof reuses the already required initialized renderer buffer domain 0/1 and engine-owned ordering-table pointers. It does not derive pointer constants from one capture or claim arbitrary-pointer/DMA safety. Complete copied `53 -> 74 -> 0x8002C378` and GPU-link sequences pass for both buffers, including a subsequent inactive tick. The earlier 256-byte-selector immediate-store controls establish physical bounds only; they are not 256 valid renderer states. The old Rooftop report's label of `74` as audio is superseded by this render-effect/fade role; its artifact and separate control-spill evidence remain unchanged.

### Delivered outcome and reversal

The actual mandatory factory binds all 69 native resources and 125 owned sources, returns a `VerifiedScenarioEntryScope`, and the actual scoped query selects only ID 68 offset 1032. No receipt or guard is substituted. Two complete owned-disc generations are byte-identical. The sole catalog difference is this scoped variant in `01-14`; no absences are added, whole-source preservation remains false, other sources and floor-plan bytes are unchanged.

The retained RAM/history hashes are the same as RE2-SCENARIO-002. Replay retains 58 visits and current `00-17`. The old collected generic item becomes seven collected Shotgun shells, and the room's item-list check becomes complete. The independently uncollected SMG remains required, so room completion stays Incomplete. Every other tracker field, room, door, position and visit agrees with the baseline.

Five synthetic acquisition controls on private RAM bytearrays cover taken/clear, all collected, unresolved presence after collecting the weapon, and return to the original uncollected weapon state, with a new tracker each time. Clearing ID 68's bit produces the named item with Unknown presence, not guessed availability or absence. It still has quantity seven. The list remains complete; a separate remaining weapon prevents clearance, and unresolved ammo presence alone keeps the room Unknown. Contradictory live creators reject atomically for both active and zero-SAT bindings. These controls prove fresh interpretation, not new collection or save restoration.

| Acquisition field | PS1 virtual address | Width, byte order and mask |
| --- | --- | --- |
| ID 68 | `0x800D48C4` | u32 LE, `0x08000000` |
| ID 62 | `0x800D48C0` | u32 LE, `0x00000002` |

### Evidence and reproduction

Private source/native evidence is `/tmp/re-map-re2-storeroom-20261106-k4z0ueul/`. `factory-before.json` preserves the rejection; `factory-after.json` and `verification-after.json` preserve the real qualified result. `audit.py`, `source-premise.py`, `native-seams.py`, `native-kind5.py` and `native-render.py` retain explicit inputs and experiment limits. There are twelve complete entry controls, eight initialized render calls and the separate 256 immediate-store controls. Root's ten bounded original-dispatch compositions are under `/tmp/re-map-re2-event-next-caller-20261106-N57dJM/`; they execute the original scratchpad handler table and caller to the next dispatch with exact PC, seven predicted stores, full RAM and scratchpad comparison. Those ten blocks are not full scheduler calls.

Parent generation/replay evidence is `/tmp/re-map-re2-storeroom-integration-20261106-n1R4Gf/`. `replay.py` loads the generated and explicitly supplied baseline catalogs through separate private profiles. `rooms-before.json` comes from commit `d2dfd0d`, SHA256 `11a9fd2c7d5c6a70aa65289e7a8faedee9bdf688f67af32affa524bfeed846dc`; reproduction therefore does not depend on the current checkout still holding the old catalog. Only one retained user capture remains available; older replay manifests and RAM paths are absent and are not counted. RAM and copied history hashes remain unchanged. Original game bytes, raw RAM, copied history and private checkpoints stay outside Git.

| Evidence | Bytes | SHA256 |
| --- | ---: | --- |
| `verification-after.json`, source proof | 3834 | `055f41087136885cb5a675789c4d7c174d60a508f8dde792f9bd1126574ee6a4` |
| `native-render.json` | 28365 | `b316e7f933d405d03fc996c2999e465271f14e2c5ab98d11e5a2c79d168bfcf6` |
| `replay.py`, parent | 5920 | `8bf81de802ee3a4e405a353016816f152617648945e150db3ec066f719c137f6` |
| `verification.json`, parent | 7274 | `08a87e92fb9b533dc5391b6c8b5a635e2b57e94fe489c2444680926215f92654` |
| `rooms.json`, generated | 507072 | `413ccd7f773fe481778662665622a72ba62a112b49890a7801448db6bbe5738a` |
| `after-publication.json` | 82168 | `602fa65ab08e88c3368f00ec92c31949c11a864111f8ad7dfb0d6eef558b7d6e` |

Copy the source verifier or replay script into a fresh private directory before reproducing. Reuse its explicit pinned CUE/profile/RAM/history paths and retain original reports. The generator command is `python3 tools/build_re2_metadata.py CUE ROOM_OUTPUT FLOOR_OUTPUT --profile profiles/re2_leon_a_slus00748.json`. Parent replay expects both repeated generated outputs in its own directory, then requires arguments `BASELINE_CATALOG PROFILE RAM COPIED_HISTORY`, resolving all profile data paths explicitly. It operates no emulator or production history. All 2,788 RE2 tests pass; scoped lint, formatting and whitespace checks pass. No UI code, map geometry or game files change.

Contribution, 2026-11-06 UTC: the human supplies the unresolved-tracking priority and original playthrough provenance. The `investigate_gdb_recovery` agent, exact verified model `gpt-6.1-sol`, effort `xhigh`, authors the source investigation, complete copied-native controls, mandatory entry/recipe guards and their regressions. Codex root, exact runtime model `gpt-6.1-sol`, authors the independent bounded dispatcher experiment, generated catalog, private before/after replay, three fresh-state/contradiction regressions and this record. Root corrects neighboring acquisition IDs in one new synthetic test before final verification. No new emulator observation or user-history write occurs in this increment.

Independent review, 2026-11-06 UTC: reviewer `gpt-6.1-sol`, effort `xhigh`, verified from matching session metadata and latest turn context, checks native packet/frame/renderer semantics, source/callback/write ownership, dominance, catalog scope, replay/reversal, evidence hashes and provenance. It finds no code/runtime defect. Its P3 documentation finding, Low difficulty, corrects the initializer wording to one selected record among four; root fixes it directly. Root also removes a redundant callee-graph traversal because the union of every procedure's call targets is already closed, retains direct/transitive/chain regressions, and verifies the explicit baseline reproduction path. The reviewer runs no new native execution or emulator and makes no edits.

External review, 2026-11-06 UTC: `gemini-3.8-flash`, high reasoning through Antigravity, returns no findings on the supplied final factory, source contracts, control limits, source/runtime regressions, catalog delta, parent replay evidence, bounded dispatcher report and RE2-SCENARIO-004. It checks native order/frame/domain assumptions, source/resource/callback protection, dominance, prior behavior, fresh state and atomicity, errors/invariants, reuse and evidence limits. It uses no tools and performs no tests, native execution or gameplay validation. Claude Opus 5.5 remains disabled in the provider inventory and supplies no review.

## RE2-SCENARIO-005: normal engine trust removes one B-only item check

Status: Candidate for the same Resident Evil 2 Dual Shock Ver. USA Disc 1, SLUS-00748, Leon A, Original Game, Normal revision. Owned-source generation and fresh retained-RAM replay remove one opposite-scenario check. No new gameplay or native savestate restore is observed.

### Human decision and separate capabilities

On 2026-11-06, the human reported Claire B items appearing unresolved during Leon A and chose to trust normal execution of the unmodified game engine for scenario filtering. Every item creator/reset, fixed scenario guard, explicit source write and unsafe script path still requires checking. This replaces exhaustive native rendering/callback memory-safety proofs as a prerequisite for scenario filtering. It does not waive a concrete script-control hazard or establish positive item presence.

`scenario_guard_scope` shares source binding, write-footprint and control analysis with the existing strict factory but returns a distinct `VerifiedScenarioGuardScope`. Only the scenario identity/exclusion query consumes the new type. Positive item-declaration compilation still requires `VerifiedScenarioEntryScope`; passing the guard type is an invariant violation. The generator computes both explicitly. Existing positive-presence, whole-source continuation and door proofs retain their previous inputs and rules.

The first extension admits ordinary `64/65` effect operations under that trust boundary. `64` still requires its two source Work-reference selectors to be zero, selecting the static matrix. Source Copies cannot alter resource/control selectors, fixed scenario guards or creator packets. Numeric comparison operands may change; the query retains both outcomes. The exact executable and 69 native resources/125 room sources remain bound as in RE2-SCENARIO-001. This is an explicit engine assumption, not a newly completed proof of the deferred lifetimes in [RE2-EFFECT-001](effect-lifetimes.md#re2-effect-001-immediate-effect-execution-does-not-establish-a-room-lifetime).

A separate source-control rule permits a sealed Goto cycle. Its encoded IF/loop depths must be `FF/FF`, its padding zero and its target the same procedure's canonical entry. The procedure must contain no IF/ELSE/ENDIF, Gosub, replacement or END/return. The control walk requires empty IF/loop frames at the jump and retains normal structured-loop capacity checks, including caller frames. Native Goto writes its own IF-pointer field; this sealed body never dereferences that poisoned pointer. Predicate failure at signed IF depth `FF` suspends before the scheduler's pointer load. This also applies at bounded positive call depth without returning to the caller. The Rooftop Goto/IF consumer and the East Office kind-five shifted-PC path remain rejected.

### Source and retained outcome

Executable SHA256 remains `e576348f64d015ecff6e1ce875a8924ee252ba7f3f9478b0917cbbdeb97db441`. Owned `PL0/RDT/ROOM2130.RDT`, source `01-13`, is 139448 bytes, SHA256 `78227d7aac8266feccc018668ad6b25893e60fc30012fbd464977d00fc254ba1`. Both creators of acquisition ID 24, file offsets 3778/3804, require bank 1 bit 1 set at 3766. The selected profile requires it clear. The source has fourteen `64`, nine `65` packets and the sealed `17:6` cycle returning from offset 6368 to entry 6250. The strict entry factory still rejects this source; the new guard factory and actual item query produce only absence ID 24.

All native addresses below are PS1 virtual, not file offsets. Multibyte values are little endian.

| Field | Width and mask |
| --- | --- |
| Scenario word `0x800CFBD8` | u32, B-scenario mask `0x40000000`, required clear |
| ID 24 acquisition at `0x800D48BC` | u32, mask `0x00000080` |
| Independent ID 253 acquisition at `0x800D48D8` | u32, mask `0x00000004` |

The same private RAM/history hashes from RE2-SCENARIO-002 reconstruct 58 visits and current `00-17`. ID 24's unresolved row disappears; independent ID 253 remains Taken, so `01-13` changes Unknown to Cleared. Unknown item rows decrease from 12 to 11. Every other tracker field, room, door, position and visit agrees. Clearing ID 253's acquisition in synthetic controls restores Unknown, even when ID 24 is acquired. Fresh trackers reconstruct the same results; exploration remains unchanged. Current-room contradictory ID 24 bindings reject atomically, including zero-SAT descriptors.

Both complete owned-disc generations are byte-identical. Only this source's scoped absence and the research-ID list change; raw creators, positive-presence fields, other sources and floor-plan bytes remain identical. Three other source-local B-only checks, `01-0b` IDs 82/48 and `00-09` ID 146, remain unresolved in this increment. The source analysis also rejects two earlier tentative B-only classifications because their common-path creators survive. No item-name or room-name whitelist is used.

### Reproduction and provenance

Private integration evidence is `/var/folders/9d/q5n746z953bcs654g_1sqcy80000gn/T/re-map-re2-scenario-filter-20261106-rjmfsvcq/`. Reproduce generation with the existing `tools/build_re2_metadata.py CUE ROOM_OUTPUT FLOOR_OUTPUT --profile profiles/re2_leon_a_slus00748.json`, using fresh output paths. `replay.py` reads its explicit private before/after profiles/catalogs and the pinned RAM/copied visits; it acquires no user-history lock. Its report extractor was corrected to find the target among all explored floors rather than only the current-floor publication. This affected report construction, not the passing tracker comparisons or production code.

| Evidence | SHA256 |
| --- | --- |
| Independent real-factory `verification.json`, under `re-map-re2-normal-guard-factory-20261106-cixdbjdz` in the same temporary root | `5735935f1c6be06e6df6d51d0ee7186e8196ffa546ebe7ba5549f3d36bd8d2a0` |
| Generated `rooms.json` | `a188885ac0d6e90b142ce322aef4ecda49531b697e9ebacece9c245fbfca3824` |
| `replay-verification.json` | `fa06e088aaff2b6ac50af6b51b79fd8e1c7fb192894b9e2009e297cf964d9930` |

Raw owned media, RAM and copied history remain private. Historical DuckStation identity remains `0.1-12083-g00e299795`; this increment operates no emulator and adds no runtime compatibility or gameplay coverage.

Verification passes all 6,612 Python tests, including 31 new guard, type-isolation, binding, control-frame and runtime regressions. Scoped Ruff lint/formatting and whitespace checks pass. Repeated full generation matches the installed catalog exactly; both generated floor-plan files match the unchanged repository file. No UI implementation changes.

Contribution, 2026-11-06 UTC: the human supplies the item report and explicit engine-trust decision. `investigate_gdb_recovery`, exact verified model `gpt-6.1-sol`, effort `xhigh`, authors the shared guard factory, sealed-cycle checks, focused regressions and independent real-factory report. Codex root, the same exact runtime model, authors distinct receipt types, generator integration, generated metadata, fresh replay, reversal/contradiction tests and this record. `review_re3_detail_tables`, the same verified model/effort, independently checks datatype separation and authors guard-binding/audit and positive-compiler-isolation regressions. These source/file checks are separate from gameplay confirmation.

Independent review, 2026-11-06 UTC: `review_re3_detail_tables`, exact verified model `gpt-6.1-sol`, effort `xhigh`, checks production receipt isolation, creator/reset coverage, source writes, sealed-Goto frame/consumer semantics, generator/catalog scope, the other regressions, hashes, field masks and links. Fresh real-factory binding and retained replay reproduce the sole ID 24 change. It finds no production defect. Its P3 documentation finding, Low difficulty, narrows "guards" to "fixed scenario guards" because numeric comparison operands may change; root corrects the text and states the conservative two-outcome rule. The reviewer authored the selection tests, distinguished from its independent production/integration review. It performs no native execution or full-suite rerun.

External review, 2026-11-06 UTC: `gemini-3.8-flash`, high reasoning through Antigravity, returns no findings on the full guard factory/query, receipt types, producer and regression diffs, positive/runtime consumer excerpts, actual sealed source packets, native Goto/IF-consumer/Break windows, catalog delta, replay and documentation. It checks the approved trust boundary, source/control safety, type isolation, freshness, reversals, atomicity, maintenance and evidence limits. The completed response has no tool attempts or pending child work and adds no execution evidence. Claude Opus 5.5 remains disabled and supplies no review.

## RE2-SCENARIO-006: bounded source roles remove the side entrance B-only check

Status: Candidate for Resident Evil 2 Dual Shock Ver. USA Disc 1, SLUS-00748, Leon A, Original Game, Normal, on the same pinned revision as RE2-SCENARIO-005. Actual owned-source factories, repeated generation and retained-RAM replay resolve one further Unknown item row. This is offline validation. No emulator, game input or savestate restore occurs in this increment. Generation runs its existing bounded copied-native map selectors; the new guard roles receive no native execution experiment.

### Source roles and retained control checks

The human's normal-engine trust decision in RE2-SCENARIO-005 remains the premise. Only `TrustedNormalEngine` gains source roles. Strict `scenario_entry_scope`, positive item compilers, whole-source continuation and door proofs keep their existing rules. A trusted guard receipt still fails the positive compiler's type invariant.

- `Enemy_set 44` permits normal constructors with byte 1 zero, signed enemy slot 0 through 31 and model selector `10..4F` hexadecimal. Source Copies cannot retarget those selectors. Loading, AI and native allocation lifetimes rely on the explicit engine premise; no new exhaustive native safety theorem is claimed.
- Member operations `34/35/3D` share the additional scalar selector set `0/1/5/7/12`. Their Work offsets and widths are `+0 u16`, `+2 u16`, `+7 u8`, `+10E u16`, `+3C u32`, respectively. Existing Work table and counter bounds remain mandatory. This grants no pointer member permission. All actual member-copy counters in the target source select counter 16, PS1 virtual `0x800D480C`, u16 little endian, full mask `0xFFFF`.
- Operand-free `Camera_back 2A`, native `0x8005481C`, sets STATUS mask `0x00100000` and clears `0x00000100`. Both avoid the fixed scenario/mode mask `0xC2000000` at PS1 virtual `0x800CFBD8`, u32 little endian.
- Predicate `85`, native `0x8005922C..0x800592F8` end exclusive, reads positions through the player/partner/enemy pointer table at PS1 virtual `0x800CFE14`, u32 little endian pointers. Both source indices must be below 34. Normal SCA helper `0x80050858` remains within engine trust. The control graph retains both Boolean outcomes; failure pops its owned IF frame and retains occupied loop cells. The scoped item query itself gains no predicate truth or continuation rule.
- A mixed-kind `Aot_on 47` may use an immediately preceding same-slot door-kind Reset. Door Reset returns one without yielding or calling SCD. Full control predecessors and canonical-entry dominance must establish that Reset on every path. Source-write protection prevents mutation of the descriptor. Other kind-five dispatches retain shifted-PC rejection.

For owned `PL0/RDT/ROOM1090.RDT`, source `00-09`, size 287656, SHA256 `785c0c49c56f49a11829c1a98718a867d851893e372d0179d9ce06a63898c4d0`, the uninterrupted Reset/dispatch offsets are `11324→11334`, `11362→11372`, `11378→11388`. The fourth dispatch at 11530 uses an item-only slot. There is no Goto. EventNext roots `17:23/17:24` have no synchronous incoming calls and target canonical `17:25`; the existing four-frame call limit includes root chain `0→3→16→6`.

The actual source-write factory returns heap floor 34012, zero Copies, eight bounded embedded-object declarations and the bounded SCA/camera/floor writes. A fresh physical census checks all 41 source flag writers against STATUS `0x800CFBD8` mask `0xC2000000` and SYSTEM `0x800CFB74` mask `0x00000040`, both u32 little endian. None overlaps. The actual factory binds all 69 native resources and 125 source files, then returns a `VerifiedScenarioGuardScope`; the strict factory still returns `EntryScope`. No receipt is fabricated or substituted.

ID 146 has one creator, `17:3` offset 9054. IF 9046 and CK 9050 require bank 1 bit 1 set, STATUS mask `0x40000000`; Leon A fixes it clear. The only source item Reset concerns independent ID 205. The real scoped query returns exactly absence `(146,)`, with no identity variants. IDs 13 and 205 remain independent and are not excluded.

### Every generated difference and retained outcome

Both complete generations are byte-identical. Against base `9c73f8d9eda42033168a63f05db4597f3eddeafd`, catalog SHA256 `a188885ac0d6e90b142ce322aef4ecda49531b697e9ebacece9c245fbfca3824`, the complete differences are the research-ID addition, `00-09` absence ID 146, and one further scenario-only identity variant in `00-0d`. Raw item/door packets, positive-presence fields, whole-source preservation, all other sources and floor-plan bytes are identical. No room/item exception or hand-edited generated output is used.

The extra variant follows from the shared normal constructor role. Owned `PL0/RDT/ROOM10D0.RDT`, 24656 bytes, SHA256 `fd3f061362f4adf48d51b9ef198600ee8d63ab76fff5c81563d48ac967159b85`, has ID 206 type 21 creator at 2134 under B-only CK 2078. Its remaining creator at 2242 and item Reset at 2346 both use type 22. The real query selects only creator offset 2242; it adds no absence or presence proof. The private factory report preserves every source command for inspection. This additional catalog consequence is explicitly reported for the parent's integration review; it changes no field in the retained 58-visit replay.

Fresh production before/after trackers read only private copies of the pinned RAM and visits. Unknown item rows decrease from 11 to 10. Only `00-09` changes, from three Unknown item rows to the two independent rows for IDs 13/205. Its complete list and Unknown completion remain. All other tracker fields, rooms, doors, position and visits compare equal. A fresh reconstruction gives the same publication. Synthetic current/departed controls toggle and rewind each independent acquisition, preserve exploration, and reject a live excluded creator atomically even with zero activation bits. The `01-0b` guard remains `EntryScope`; its IDs 82/48 and Goto/shifted-PC hazards remain outside this correction.

### Reproduction and evidence

Private outputs are `/var/folders/9d/q5n746z953bcs654g_1sqcy80000gn/T/re-map-re2-0009-implementation-20261106-w53e5_pj/`. `factories.py` imports this prepared worktree, reads the owned CUE and calls the real resource/corpus, write, strict/trusted scope and item-query factories. `replay.py` uses the explicit private before/after profiles, catalogs and copied inputs. Run them with `/var/folders/9d/q5n746z953bcs654g_1sqcy80000gn/T/re-map-improvement-_b504zzf/clean-venv/bin/python`. Reproduce each full generation using `tools/build_re2_metadata.py CUE ROOM_OUTPUT FLOOR_OUTPUT --profile profiles/re2_leon_a_slus00748.json`, with fresh output paths. The executable freshly read from the CUE equals the supplied `SLUS_007.48`, 987136 bytes, SHA256 `e576348f64d015ecff6e1ce875a8924ee252ba7f3f9478b0917cbbdeb97db441`.

Before replaying, copy the scripts and their explicitly named catalogs, profiles and copied inputs into a fresh private directory. Their output directory is the script's parent; do not overwrite frozen reports. Use the corrected root `factories.py` identified below for the physical census. The original script/report preserve the initial incorrect address assertion.

| Evidence | SHA256 |
| --- | --- |
| Initial `factory-verification.json`, with the SYSTEM-address assertion corrected below | `26d40e70c4194723362f74edfecbbb16ff83122e5e63efdc2f3f6283c25bf0b0` |
| Corrected root `factory-verification.json` | `ff56f42e33041590140488f77e85fc65bfe444d06c7d4396bc4d45fb6f16d0fa` |
| Complete `catalog-delta.json` | `039b71cce4542e58291ca0f22c1c3c91407da373627c0c2c0f02eef1305ffa5b` |
| Generated `rooms.json` and `rooms-repeat.json` | `22e27c54ede31ed54d9be9ccaaa0bafc89475fe6489881bbf9afc77addeb953a` |
| Unchanged generated floor plans | `641c6362a66333d97d2bfcf6c72d7edb0dcfbfd390a145f7248cc0b06cee2e8b` |
| Production `replay-verification.json` | `960746dead6034e43b0c3293c3720ec01d45161ce2c9af6e9455dec10eb2782b` |
| Private copied `slot1.ram` | `939264d8e98c07e0d7afcdef69efdf1e18ac4fa05052575d726022b5dfdd8b73` |
| Private copied visits `history.json` | `3d8b4240e2a63d4c873d805304a77060e81d548e01690029dade132f4fd04d97` |

The frozen prerequisite packet remains `/var/folders/9d/q5n746z953bcs654g_1sqcy80000gn/T/re-map-re2-0009-guard-recipe-20261106-y7018p1q/`: `review.md` SHA256 `fc1f14a0e1de0ab4aadec374c70c2d51d726bc13cfecd1afa1e79638afdfe107`, `source-review.json` SHA256 `97e7c1861ad80ccf4969c6bdf71e23146987d6b0fc045702c885888a71329b4f`. It supplies source-only inspection, not the actual implementation/factory result recorded here. Neither frozen report is overwritten. Copyrighted source bytes, RAM and copied history stay outside Git.

Historical DuckStation identity remains `0.1-12083-g00e299795`; this work tests no emulator build or save compatibility and adds no gameplay coverage. All results depend on the exact revision, bound inputs and human-selected normal-engine premise. Runtime memory-card persistence, broader campaign readiness, native heap/render/callback safety and positive item/door availability remain separate.

Verification passes 285 focused guard/query/current-state tests and all 6,686 Python tests on final code, 74 more than the base. Scoped Ruff `E4,E7,E9,F,I`, ignoring `E402`, formatting, whitespace and research file-link checks pass. Installed metadata equals both generated catalogs, and floor plans equal the unchanged repository bytes. No UI implementation is changed.

Contribution, 2026-11-06 UTC: the human supplies the explicit trust decision and target. The prerequisite source recipe is authored by `review_re3_rows`, exact verified model `gpt-6.1-sol`, effort `xhigh`, with no native execution. The implementation sub-agent, exact runtime model `gpt-6.1-sol`, reasoning effort `xhigh`, authors the shared source roles, control checks, adversarial/type-isolation/current-state regressions, actual factory runs, generation/diff inspection, copied-input replay and this appended record. Original research and human playthrough authorship are preserved. Local self-review checks changed policy/control paths, strict-policy isolation, source-write protection, all generated differences and replay equality. This is not independent or external review. At handoff, the work was left uncommitted for the parent's integration reviews recorded below.

Independent integration review, 2026-11-06 UTC: `review_re3_detail_tables`, exact verified model `gpt-6.1-sol`, effort `xhigh`, finds no production defect after checking native operand/field tables, predicate/IF semantics, Reset/dispatch ordering and dominance, explicit writers, strict isolation, all catalog changes and fresh replay. Its 166 focused tests pass. The P3 documentation/evidence finding, Low difficulty, identifies an incorrect SYSTEM address in the initial private census assertion and draft. Root corrects the address to `0x800CFB74` and reproduces the real 69-resource/125-source factories plus all 41 physical writers using corrected `factories.py` under `/var/folders/9d/q5n746z953bcs654g_1sqcy80000gn/T/re-map-re2-0009-root-20261106-rin08w5s/`. Use that script for the corrected census reproduction. The original frozen report remains intact; its writer rows, guard result and item selection are unchanged.

An additional independent read-only source audit by `investigate_gdb_recovery`, the same exact model/effort, finds no issue in the ID 206 consequence after checking every creator/reset and entry/write path, real baseline/new factories, all source packets and unchanged non-scenario fields. Its report is `/var/folders/9d/q5n746z953bcs654g_1sqcy80000gn/T/re-map-re2-206-independent-audit-20261106-9vt33dl2/review.json`, SHA256 `4a71918c6fe6af3036d16ff91df14d7673a7b518d71d84268c8daed1a146baed`. Neither independent reviewer operates an emulator or supplies gameplay confirmation. This source audit is separate from the external review below.

Primary integration review, 2026-11-06 UTC: Codex root, exact runtime model `gpt-6.1-sol`, inspects the shared factory/control changes, typed consumer boundary, regressions, both catalog consequences and fresh corrected real-factory results. All 18 frozen evidence files and tested implementation hashes match; repeated catalogs/floors, the old research prefix and 422 local file links agree. Root corrects the SYSTEM assertion/address, reproduction output instructions and recipe attribution without changing production code. Its retained-file report is `/var/folders/9d/q5n746z953bcs654g_1sqcy80000gn/T/re-map-re2-0009-root-20261106-rin08w5s/integration-review.json`, SHA256 `a50cd88cdb82da46e38b6062b7fbdfed573991bc46e3566f5af3fe07484a8327`. The recorded 6,686-test full-suite result belongs to the implementation worktree; independent review reruns 166 focused cases. No additional native execution or gameplay validation is claimed.

External review, 2026-11-06 UTC: `gemini-3.8-flash`, high reasoning through Antigravity, returns no findings on the final shared factory, receipt/query and writer implementations, new adversarial tests and regression diffs, positive type invariant, all generated differences, corrected real-factory/census reports, retained replay, ID 206 audit, documentation and original Reset/predicate/interpreter windows. The snapshot explicitly omits unchanged context/camera/floor helper bodies and the existing partition receipts. Review checks normal-engine trust, source/control bounds and dominance, type isolation, both metadata consequences, freshness, test meaning, errors, maintenance and evidence limits. It has no tool attempts or pending child work and adds no execution evidence. Claude Opus 5.5 remains disabled and supplies no review.
