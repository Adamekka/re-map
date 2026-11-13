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

### Positive-presence policy extension, 2026-11-07

The human explicitly approves using the same normal-engine trust premise for RE2 item-presence checks as for scenario filtering. Creator/reset checks, scenario guards, explicit source-write checks and fresh acquisition reads remain required. This is a changed policy premise for subsequent positive proofs, not evidence that every remaining Unknown item exists or that an older unproved native-safety component has been confirmed.

Positive authority must be derived separately from source-bound positive conditions. A `VerifiedScenarioGuardScope` remains insufficient as a positive argument, and existing strict entry, whole-source and door contracts keep their distinct meanings. The new policy allows normal execution of the owned unmodified initialized engine to supply its native execution premise; it does not authorize guessed script outcomes, skipped explicit writes, ignored target aliases, fabricated state or cached acquisition after restore.

Contribution, 2026-11-07 UTC: the human selects "Use normal-engine trust for presence too" after the remaining eight checks are separated from the completed B-only filtering corrections. Codex root, verified `gpt-6.1-sol`, effort `xhigh`, records that decision. Implementation and measured item outcomes require their own subsequent evidence. The earlier source/native investigations and their original authorship and limits remain unchanged.

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

## RE2-SCENARIO-007: joint source task control removes two office B-only checks

Status: Candidate for the same Resident Evil 2 Dual Shock Ver. USA Disc 1, SLUS-00748, Leon A, Original Game, Normal revision. This extends the human's explicit normal-unmodified-engine premise from RE2-SCENARIO-005. Owned-source factories, repeated generation and retained-file replay exclude IDs 48/82 in source `01-0b`. No new gameplay, emulator session, input, savestate load or copied-native experiment establishes this extension. The generator still performs its existing bounded native map-selector work. Historical DuckStation identity `0.1-12083-g00e299795` is unchanged and is not retested here.

### Separate ingress and source control rights

The shared binding pass reads the pinned `SLUS_007.48`, SHA256 `e576348f64d015ecff6e1ce875a8924ee252ba7f3f9478b0917cbbdeb97db441`, 69 native resources and 125 exact room sources. It decodes those 125 sources and all 54 used DO2 auxiliary tables once, 179 decodes total. Immutable compiled tuples bind each auxiliary's owned resource, native descriptor, synthetic RDT bytes and decoded programs. A separate corpus receipt binds route-writer witnesses. Retaining one receipt while replacing bytes, programs, derived permissions or corpus members asserts at construction, including `dataclasses.replace`. The source receipt similarly binds its exact dispatch/Goto sets, task owners, frontier count and ingress. These are programmer invariants; unsupported external inputs return explicit failure enums.

`VerifiedOrdinaryTaskIngress` is a distinct normal native lifecycle right. It does not promote raw incoming models or change legacy `VerifiedEntrySelection.stages={0}`. The mandatory source-corpus pass checks every pending door payload and cross-kind Reset alternative, source Copy destinations and Reset writes through creator records. Protected routing bytes must remain disjoint from these writers. The pinned final native setter reloads the pending payload after auxiliary completion, stores room from payload byte 9 and stage from byte 8 modulo 9; model byte 12 selects the auxiliary beforehand. The incoming model set must be wholly covered by the verified native lookup/resource domain. Actual `01-0b` models are 4, 5 and 19. Model 71's cross-kind route is outside this coverage and obtains no ingress. No stage-one positive-entry or door right is invented.

Normal new-game setup calls global reset `0x8002C610` at `0x8002B264`; reset explicitly clears Message busy at `0x8002C68C`. Every later normal door passes the busy80 check `0x80025970..0x80025988` before its suspended RoomChange continuation, while auxiliary isolation prevents constructor-yield Message births. These are mandatory clean-ingress checks, not a sampled busy0 assumption. The normal driver must pass its SYSTEM10000 clear wait before the next ordinary SCD/AOT pass. Normal Door and ItemUI paths are disjoint at `0x800259AC..0x800259B8`. Before `Event_init`, `Room_load` clears the earlier ItemUI request via the STATUS mask at `0x80049E84..0x80049E8C` and clears player routine/substates at `0x8004A330`, using the player base established at `0x80049E48`. The retained `DF348` Door phase does not imply a Pending ItemUI request. The postload path `0x80025C7C..0x80025C94` preserves newly set STOP bits.

Native `Room_load` calls common `Event_init` at PS1 virtual `0x8004A334→0x80053528` regardless of model. The initializer calls `0x80052F3C` at `0x800535B8` to reset ordinary slots 0 through 9, clears auxiliary phase at `0x800535D0`, installs header16 task0 and header17 task1 through `0x80053138`, then schedules at `0x80053608`. Later `0x800536A4` seeds main procedure1. Aux slots10 through13 survive the ordinary reset. Their normal `0x80013C1C` reset and constructor resume contracts therefore remain mandatory and separate. Enemy constructor `0x800574F0..0x800574FC` and analogous object resume `0x80057B84` restore main source/phase immediately after the cooperative primitive returns. Normal native heap/render/AI behavior uses the human's engine premise, not a new exhaustive safety theorem.

All 54 auxiliary tables undergo the same source/control/write checks. Phase1 task selectors below14 are explicit, including unsafe0 through9; selectors14 and above allocate only10 through13. The actual `0E` selector is admitted by this rule. All 51 FF/FF Gotos have source-derived task10 roots. The shared stride/frame formula maps their escaped IF stores to aux13 `+A4` numeric LOOP-count cells at depth2, or `+84` only while receiver13 remains inactive at depth1. Poll shape must store a fresh IF target before the immediate predicate read without a yield; its true-arm yield must return through Goto/fresh IF before another read. Copies may affect only the proved Work-index or numeric member operands. Model16's bounded loops derive Work indices1 through9 and require main-side preservation of counter5, PS1 virtual `0x800D47F6`, u16 little endian. There is no blanket auxiliary Goto/IF permission.

The shared ordinary compiler closes complete source-selected task/input frontiers. It retains both historical startup alternatives, all six SCD Messages and the external kind4 Reset at offset12200. Persistent roots9/7 occupy slots2/3 on the normal branch; the alternate branch installs9 and ends. Every external callback is manual SAT31, FF/main18 canonical entry. Manual scanning admits at most one match per ordinary pass. Source automatic births, independent STOP clears, logical-input/history aliases, Message-phase/snapshot writers, source Copies and unsupported startup controls fail explicitly. Persistent roots may not hide descriptor mutation, births or Message/dispatch effects. Relied-upon native handlers close their complete nonyielding call graphs, including earlier workers and delay slots; a handler's return1 alone supplies no timing right. Positioned request36 and persistent sound51 use their checked native switches/callees. SDK passes are not counted as ordinary SCD/AOT passes.

STOP at PS1 virtual `0x800CFBDC` is u32 little endian; bank2 bits6/7 use masks `0x02000000/0x01000000`. Native STOP6 is sampled once before the ascending ordinary-slot pass. Source Message `2B` advances PC even when busy and ORs its mask without retrying; fresh Message phase0 cannot complete its first update, and Message update follows manual AOT. All admitted Message masks preserve6/7. Native STOP6 also gates scripted kind5 dispatch at `0x80051980..0x800519BC`; skipping the task birth still advances opcode47. The first mapping after STOP7 release suppresses fresh Action80. Both inherited STOP6/7 values are retained rather than sampled. The finite graph derives the helper lifetimes, receiver namespace and nonfinal/nonalias internal allocation; final slot9 or caller replacement fails. This covers the actual single naked02 gap without granting general shifted `Aot_on` streams.

Item UI is separate from Message. Flag0 source47 snapshots STOP and requests Pending UI, without an immediate STOP6/7 write. Pending can persist through arbitrarily many ordinary passes because Message/fade gates may defer admission; DF348 skips the apparent post-SCD clamp. Active UI suspends ordinary task0 even while literal STOP is cleared. Its postreturn clamp and later phase5 require an intervening filtered mapper before ordinary work resumes. Flag1 manual items first enter player routine6 and its checked animation closure; the later request captures STOP then, not at the original AOT. The model keeps delayed admission and both timing orders. It assumes neither current Message-idle nor fade-ready RAM. The selected source-record owner survives Pending UI and delayed animation. Acceptance may clear that record's kind and every registry alias; cancellation preserves them. A Reset of the selected payload during either unresolved lifetime fails explicitly because its resource/control contract is not established. Records used only by manual scanning, with no Reset or scripted47 consumer, share the explicit unobserved-owner state.

Registered AOT records remain distinct from empty slots. Every Reset requires a registered record, mutates its source-owned descriptor and updates all aliases; creator reexecution reads that mutated record. Rectangular `4E` and four-point `69` constructors may clear the registered kind when acquisition is already set. The compiler retains both histories without reading acquisition RAM. Inactive records observable by Reset or scripted47 are retained explicitly; manual-only inactive choices are covered by the no-match branch. Scripted kind0 dispatch is not a no-op: native `0x800514EC..0x80051514` copies low halfwords from `0x800EADE0/0x800EAE30` to counters0/1 at `0x800D47EC/0x800D47EE`, u16 little endian, then returns0; opcode47 ignores that result and advances two bytes. These numeric predicates remain unknown, counter5 stays protected, and no UI fence is added to kind0.

Actual `PL0/RDT/ROOM20B0.RDT` is 191432 bytes, SHA256 `c6b1fe6135f346ffb71500328ffef35a62c6f3d755138ce2a8513411274fc7f6`. The final compiler visits 1,812,546 frontiers, below its explicit 3,000,000 failure limit. The final immutable-binding owned-source run takes 167.35 seconds; this work runs during offline metadata generation, never during tracker polling. It derives roots2/3/4/10 as the relevant ordinary receiver namespace; those roots have no structured loop, call, Break, Goto, return or replacement consumer of the escaped loop-end cells. Sequential Sleep uses `+A0`. Root9's single fresh IF/predicate path closes its own escaped-pointer read. Root7's decoded-boundary Goto passes the existing balanced structural walker. The trusted factory returns a guard scope and the fixed-scenario query returns exactly absence `(48,82)`, with no identity variant. Strict entry remains `EntryScope`. Positive compilers, whole-source continuation, doors, raw creators and the separate context type retain their existing behavior.

### Rejected models and adversarial checks

The earlier no-kind4 claim is rejected. Other rejected intermediate models include raw stage-one tuple promotion, FF-only auxiliary allocation, all-aux-no-IF, unclosed return1 atomicity, skipped persistent descriptor effects, busy-Message retries, ItemUI-as-Message, unconditional post-SCD Pending promotion, immediate Active completion without a filtered mapper, flag1-as-flag0 timing, startup loop/predicate linearization, Reset into an empty registry, original-byte descriptor rereads after Reset and acquired kind0 described as a no-op. Their frozen reports and failed probes are preserved. Earlier provisional catalog/factory outputs in the implementation directory are not final evidence. Raising the frontier cap did not authorize truncation; reaching either analysis limit withholds the receipt.

Regressions use decodable source variants for an extra release-gap02, helperSleep30/final-slot allocation, autonomous/automatic births, Message masks, independent STOP clear, input/phase/snapshot aliases, persistent mutation, changed startup assignments/alternatives, source/control Copies, missing registration, Reset/reexecution, rectangular/four-point acquisition clearing, receiver loop/call, frame overflow and malformed/shifted auxiliary streams. Native tests follow nested calls, external/indirect transfers and delay slots. Retained-proof substitutions assert on both constructor and consumer paths. Existing strict-positive/type checks and Rooftop unsafe IF/Goto rejection remain. No production sample data or optional validation helper grants a right.

### Complete catalog and retained replay result

Both final full catalogs are byte-identical, SHA256 `6c2e4618f2f00beb988af4dd9446f7862d2604a3641a990dd7fcc1c0e36d6b83`, and equal the published repository bytes. Against parent `cb71d4241a6d267e333f8af257215a9cd031ae34`, the complete JSON differences are research ID007 and `01-0b` absence IDs48/82. There are no new scenario identity variants or other metadata consequences. All floor-plan bytes retain SHA256 `641c6362a66333d97d2bfcf6c72d7edb0dcfbfd390a145f7248cc0b06cee2e8b`. Raw item/door data and positive-presence fields are identical.

Fresh production replay uses only `/tmp/re-map-used-keys-20261103/slot1.ram` and `history.json`, with their original human provenance and hashes below. It retains 58 visits/current `00-17`. Unknown item rows decrease10→8; only `01-0b` changes, from seven rows to five. Its complete independent list consists of acquired IDs74/78/81/84/217, so it becomes Cleared only after the two B-only rows are removed. Its unresolved door fields are unchanged and remain separate from item completion. Every other tracker field, room, visit, door and position compares equal. A fresh tracker reproduces the publication. Synthetic acquisition rewind restores required Uncollected rows and the independent Unknown row; original RAM restores the exact original tracker. Current/departed tests also preserve Unknown when only that independent item is unresolved and reject either live excluded creator atomically with SAT0 or31. This is not a native savestate or collection observation.

### Reproduction, evidence and attribution

Final implementation evidence is `/tmp/re-map-re2-office-implementation-20261106-dedac3e2/`. Copy verifiers into a new private output directory before rerunning; never overwrite frozen reports. Use `/var/folders/9d/q5n746z953bcs654g_1sqcy80000gn/T/re-map-improvement-_b504zzf/clean-venv/bin/python handoff-factories.py` for the single shared 69/125/54 resource/decode binding, 171 retained-proof substitution rejections and actual source/query result. `final-replay.py` explicitly resolves production profile paths and reads only the two pinned retained inputs. Generate twice with `python tools/build_re2_metadata.py CUE ROOM_OUTPUT FLOOR_OUTPUT --profile profiles/re2_leon_a_slus00748.json`, using the supplied owned Leon CUE and distinct fresh output paths. No raw source, RAM, saves or media is added to Git.

| Final artifact | SHA256 |
| --- | --- |
| `factory-verification-handoff.json` | `df2c4c77169fa5b2fa35000c4f9701934301c1b0992cc9f27ecd049998adb4d5` |
| `catalog-delta-final.json` | `8bffb0256894e73c3a7c0959475ba30d4507b35a8b2a86e4c4486cd0b1948a73` |
| `replay-verification-final.json` | `986121b132b791162167b29b29f50ac2517c4e10b59f7093057f5df1db886670` |
| `handoff-factories.py` | `56e00c34c0a37651208fa5fbe4291ce9439c0e76dd17d635decf04784242de4d` |
| `final-replay.py` | `12da40a072ef5dae90d874986498632d138e75cc0f5c9f9630727073e0be1ad8` |
| Retained `slot1.ram` | `939264d8e98c07e0d7afcdef69efdf1e18ac4fa05052575d726022b5dfdd8b73` |
| Retained `history.json` | `3d8b4240e2a63d4c873d805304a77060e81d548e01690029dade132f4fd04d97` |

Frozen prerequisite directories remain private and unchanged. Under `/var/folders/9d/q5n746z953bcs654g_1sqcy80000gn/T/`, `re-map-re2-office-lease-followup-20261106-511c3bor/` contains `investigation.json` SHA256 `ffd9090f38970fda01a094228cdedbdf3c71ece38ea8c7cc30ec6a10270c83a3`, `conclusion.json` `b78adbb025e93fe6b72ad33d58db8d4b64ffb9240f0a4e272908ee1c149c971c` and `implementation-design.json` `6f0fb8cf2d792561630e1e56665fa2d2df7335f4989b866435996cdc22f65548`. `re-map-re2-office-task-births-20261106-kn_x44pb/source-analysis.json` is `04e1e40546ace1a949a02b62fb6b4e2075dbc00195eef560663ac609623194a8`; `re-map-re2-office-inbound-root-20261106-twltw23w/verification.json` is `0524eb1f80b8375b8e7d5b875e0984fed01f5315221b7b8259646b28c448543b`.

`/tmp/re-map-re2-office-aux-independent-20261106-H8SgUU/` retains census SHA256 `6bb823f07b66b5048661a081dbc1d39f973120cc06bc73e2771377fc987d008f`, closure `99855ec04e75c93e9fda6f8c3e380c89ed00281e48b2af7d26a4a67c9f86991a` and review-and-scope `54c5a06107bd77b8678b236049d1fd4a3b18c8eceb5fb36b9f422361b049e09e`, with their verifiers. Its closure is conditional on bound normal-resource/reset ingress, not route coverage. Earlier bounded input controls remain `re-map-re2-stop-action-20261106-dvhktamc/verification.json` under the long temp prefix, SHA256 `0b67c17bd24613ed5e020c4b6da653c4293fc07ca31e2b06436f6f084318d908`, and independent `/tmp/re-map-re2-stop-action-review-20261106-hxi4odqu/verification.json` `1f1604023f0e9931d1c90edc387010eb51434172f43c6259c3fe272148bc8a83`. They are bounded native blocks, not full gameplay frames. The ordinary SYSTEM10000 suspension report remains `/tmp/re-map-re2-effect-resource-obligations-20261106-5dbzjlrv/door1d-system10000-suspension-followup-20261106.json`, SHA256 `f2c0ea8e077668679bd90a54d8afadae75cd921ad49e631f9568a1000f8dd1d6`.

Parent-supplied preliminary components under the long temp prefix are `re-map-re2-ingress-review-20261107-16fbiy0h/review.json` SHA256 `09d70c393ac23d88f867632139671d9ee29a42a235345a300f2ddec00066681c`, `re-map-re2-reset-reentry-review-20261107-8qgwzxi8/source-proof.json` `3b0aa6bb2f90121d9d686f6f3bdb0ab6ee761546fe33c818bd283d1ad900f26f`, `re-map-re2-item-ui-control-20261107-5t5v982b/proof.json` `4832ad87fb1cb5d930f467fecce69f655deb069c59d725bf22b12c14587a3fc1` and `re-map-re2-item-disable-control-20261107-ndju3xr6/proof.json` `f62aafc576bb7a1e021f8b44688453f0e94120778df2c5a96cdb88f9aa556e35`. They identify the corrected native scheduling and source-record behavior and retain original rejected models. The binding-only report `re-map-re2-ingress-binding-review-20261107-fp5opmep/verification.json`, SHA256 `acd9534b0f2665954428c1e9e24d6f63098cbcf8ebfff9deed399aa41de9f55f`, checks resource/receipt binding only; it does not endorse scheduling or this final implementation.

The original implementation check passed 424 focused tests and 6,757 full tests. After the parent corrections below, all 6,760 Python tests pass in 141.28 seconds, together with 359 focused source/ingress/guard/query regressions. Scoped Ruff `E4,E7,E9,F,I` with the existing tool import-layout `E402` exemption, formatting, whitespace and 517 local documentation links pass. The original research prefix is byte-identical. The final native clean-ingress checks reproduce the same factory/frontier/query and both catalogs. Legacy binder wrappers retain their real positive-entry/reproduction consumers and return only their original contract; the generator uses the separate combined binding result. No compatibility wrapper transfers the new ingress into the old context. Main's subsequent RE3-only commits are outside this checkout and are left for the parent's fresh integration checks.

Contribution, 2026-11-07 UTC: the human supplies task priority, ongoing parallel-work authorization and the explicit normal-engine premise. This implementation sub-agent, exact runtime model `gpt-6.1-sol`, reasoning effort `xhigh`, authors the separate ingress/resource binding, shared finite source control, corrections/regressions, real factory checks, generation comparison, retained replay and this appended record. Parent-supplied native/source components identify their verified authors in the frozen reports; they are advisory inputs, not a final review of these changes. Original historical authorship and human playthrough provenance are preserved. The local final review checks receipt immutability, source/control/native premises, strict type isolation, all generated differences and replay equality. At the original handoff, parent external final review and integration were pending. No external endorsement, runtime confirmation, new route/positive/door right or broader campaign readiness is claimed.

Parent review and corrections, 2026-11-07 UTC: Codex root, exact runtime model `gpt-6.1-sol`, effort `xhigh`, reviews the complete implementation and reproduces two missing native paths. Scripted kind5 must honor STOP6 while still advancing opcode47. Accepted ItemUI must clear its selected source record and every registry alias, while cancellation preserves them. The corrected model retains selected-record ownership across Pending UI and delayed animation, rejects unproved selected-payload Reset, and retains both acceptance/cancellation outcomes. The new source variants fail on the earlier implementation and reject appropriately after correction. `review_re3_detail_tables`, the same exact verified model/effort, independently rechecks both corrections and their counterexamples; its frozen `fix-recheck.json` SHA256 is `69b806540efd1890313674baf46db30d81f39a68ce691e6c1815618d9a2b3f20`. This is a source/control review, not an independent gameplay or publication observation.

The parent factory and retained replay are preserved separately in `/tmp/re-map-re2-office-root-ui-expanded-20261107/`. `factory-verification-handoff.json` has SHA256 `05e124ca39505fb7a7a289bd3847d97335a4e3caa517a2f0dfbfc9e08beac7b3` and `replay-verification-final.json` has SHA256 `986121b132b791162167b29b29f50ac2517c4e10b59f7093057f5df1db886670`. The factory binds the same 69/125/54 inputs and visits 1,812,546 complete frontiers. Its exact selected-owner model exceeds the earlier 1,500,000 budget, so the explicit offline budget is 3,000,000. No path is dropped at the limit; exhaustion still withholds the receipt. The replay again produces only the office change, 10 to 8 Unknown rows, fresh reconstruction equality and acquisition rewind/recovery. These reports supersede the earlier factory counts without modifying their frozen evidence.

The corrected parent model also regenerates both complete catalogs byte-for-byte, preserving the published room SHA256 `6c2e4618f2f00beb988af4dd9446f7862d2604a3641a990dd7fcc1c0e36d6b83` and floor SHA256 `641c6362a66333d97d2bfcf6c72d7edb0dcfbfd390a145f7248cc0b06cee2e8b`. `catalog-verification.json` in that parent directory has SHA256 `84d6a135d7e39a2e07f80a380f389064c3e4d64a462f417ffa727fe634555e1d`; its exact JSON delta remains only claim ID007 and office absences48/82. The original implementation reports remain historical evidence, while the parent reports bind the corrected source and final results.

Immutable auxiliary correction, 2026-11-07 UTC: independent investigator `investigate_gdb_recovery`, exact verified model `gpt-6.1-sol`, effort `xhigh`, reproduces one P2 compiled-binding defect, Low difficulty, using genuine receipts for 69 resources, 125 sources and 54 auxiliary scripts. A value-equal mutable data replacement passed the earlier derivation comparison. Later mutation could introduce an auxiliary Message while decoded JSON retained NOP, or rename model 16 counter operands from 5 to 8. The latter lost required counter-5 preservation despite unchanged owned resources. Both controls expose the same missing immutable-type invariant. Numeric value aliases produced no additional changed outcomes.

Codex root, the same exact runtime model/effort, adds mandatory exact descriptor/data bytes, JSON string and model types, plus immutable corpus range shapes. Five regressions cover both mutable buffer forms and the model alias. The six-file focused set passes 364 tests; the corrected child full suite passes 6765 in 134.57 seconds. The independent post-fix real factory retains byte-identical identities, models, routes, atomic operations, counter 5, legacy stages and all 125 `covers` results. All 216 data/descriptor buffer substitutions and both boolean model aliases reject before corpus construction; all 54 unchanged script replacements still work. The earlier harmful counterexamples stop at constructor checks. Positive/door rights and normal generated outcomes remain unchanged.

Frozen original type audit: `/tmp/re-map-re2-receipt-type-audit-20261107-NCWoIq/`, `review.json` SHA256 `904a496ea9fef73727b6d45ec8ec58fc4ade95714042bd7cb8ec8036301369a4`; counter reproduction `a62884fbae2e3e146f57255d036d303421c3c499b26918c95ffb6837e9b224dd`; opcode control `c2ea8536b542508722bfe1a63e48246de0861c89d665cc92baa89dd1f6c276c4`. Its 119-file artifact manifest SHA256 is `e38b28462fa2da0fb5d90a8635fe9b1c5d694eafcff98b133eae7588b6a0aa94`. Separate fixed recheck: `/tmp/re-map-re2-receipt-fixed-check-20261107-QtJBRC/fixed-check.json`, SHA256 `4e3319c050dea3b76c920935237807e928a5394cc4d4c607e2de693f048bf942`. Original evidence remains unchanged. No emulator/history operation or new gameplay confirmation occurs.

Four initial Gemini final-review scopes failed without a response after 15 minutes. They supply no endorsement. A fresh corrected-source compiler request to `gemini-3.8-flash`, high reasoning through Antigravity, also fails to open a provider session. The other narrowed packets remain unsubmitted while that provider is unavailable. Claude Opus 5.5 is disabled. No external final review completes; the completed RE3 evidence review is a separate scope.

Final verification with the corrected types, 2026-11-07 UTC: `/tmp/re-map-re2-office-root-immutable-final-20261107/` visits the same 1,812,546 frontiers in 167.35 seconds and excludes exactly IDs 48/82. Its factory report SHA256 is `65b09ffd6f5f31746a89400d68aa2377fe3543b263d90ee442b81a097f360b1b`. Both complete generations match the repository catalog and the previously verified floor-plan bytes. Fresh retained replay is field-for-field identical to the preceding 10-to-8 result. `final-verification.json` SHA256 is `4b34f4cac78b7557ac1b5061098ca7b0dcdd2870cb674e96b05e60724f86c327`. Earlier reports remain frozen historical evidence; this pass binds the corrected final source.

Rendered-state check, 2026-11-07 UTC: six headless desktop/mobile renders use the untouched retained README publication and the exact fresh before/after publications above. The selected office changes from "Item check incomplete" to "Cleared" with five acquired rows; no browser error, horizontal overflow or publication mutation occurs. The existing desktop README PNG reproduces byte-for-byte, SHA256 `82ee90937821a2593dc2a989f5598ff66970d98a017cb2286c50066d9e6685b3`, so it remains unchanged. `/tmp/re-map-re2-office-render-20261107/report.json` has SHA256 `2f497e60e9060ba4bad021a90d9c660d57a170c22dcb6bc92677d57c02579e36`. The first private harness incorrectly expected the backend spelling "Unknown" in the UI; using the existing product label corrects that harness assertion without changing application code. No emulator, gameplay view or live history was opened.

Final bounded consumer review, 2026-11-07 UTC: `investigate_gdb_recovery`, verified `gpt-6.1-sol`, effort `xhigh`, independently checks typed guard/source-control binding, the strict positive compiler assertion, generator arguments, separate whole-source/door callers, failed-proof empty metadata, loader validation and Retry before publication. The actual catalog differs only by claim007 and absence48/82. Retained publication comparison checks 58 source rooms, the office clearance/rewind and equality outside that target, including incomplete door knowledge. The report returns no findings within those caller/consumer boundaries. `/tmp/re-map-re2-integration-review-20261107-cj6ndn12/review.json` has SHA256 `e2bf4447679f756f8c816e5bb2393fa174d2cc4e1a781359f606555851f0eb13`. This review does not endorse the complete native/scheduler proof or add gameplay validation. The parent full implementation review and corrected verification above remain separate evidence.

Parent integration, 2026-11-07 UTC: Codex root applies the verified child commit `e3ae5dafdb1ba02c8ade335df6617b5547228877` to main after RE3 collectible commit `171f6e124bc79899600ee7e0efb71c0a998c33c7`. All implementation/test/catalog bytes match the child; the research index retains every RE3 entry and adds only the scenario007 row. The combined suite passes 7107 tests in 133.68 seconds. Fresh production replay from this integrated checkout reproduces the identical report SHA256 `986121b132b791162167b29b29f50ac2517c4e10b59f7093057f5df1db886670`, including 10-to-8 Unknown rows, equality outside the office, fresh reconstruction and synthetic acquisition rewind/recovery. Scoped documentation validation checks 534 local links. `/tmp/re-map-integrated-re2-re3-20261107/final-verification.json`, SHA256 `d910c21911a77461a25dbb65de5063997ba40efc96bcaf6519337c81c6ac4177`, binds the integrated code/catalog and logs. This adds no native gameplay or broader positive/door authority.

## RE2-SCENARIO-008: persistent registration refines Reset origins

Status: Candidate under the human's explicitly approved ordinary initialized, unmodified engine premise for scenario filtering and positive presence. Revision is Resident Evil 2 Dual Shock Ver., USA Disc 1 Leon, SLUS-00748, Original Game, Normal, Leon A. Executable `SLUS_007.48` is 987136 bytes, SHA256 `e576348f64d015ecff6e1ce875a8924ee252ba7f3f9478b0917cbbdeb97db441`. This correction adds source interpretation and offline validation. It adds no gameplay or copied native execution. Full metadata generation retains the existing bounded native map-selector executions. Historical DuckStation identity remains `0.1-12083-g00e299795`; no emulator version or save compatibility is retested.

### Registration and consumer boundary

Reset is a real write through the registry's existing pointer, including NULL. Every empty slot aliases the same physical zero-page descriptor. Scripted `47` has no NULL check, so a different empty slot can consume a descriptor created there by Reset. Manual scanning skips NULL before reading SAT, geometry or kind. The rejected origin-only prototype therefore cannot establish absence by itself.

A separate compiler-owned `VerifiedPersistentRegistration` consumes an actual `VerifiedNormalEnginePositivePrefix`. Its mandatory factory calls `prefix.matches(data, room, profile, prefix.context.declaration_contract)` and uses the same synchronous startup traversal as positive items. Every ordinary and four-point creator adds a registration token before any acquisition-dependent kind clearing. The intersection retains only slots registered on every successful or terminal startup-prefix outcome. Unsupported or yielding operations stop that path's guarantees. Neither current nor historical acquisition flags suppress a possible consumer.

The capability requires guaranteed registration for every scripted `47` slot in every canonical source procedure. All source creator/Reset kinds must belong to the inspected initial set 0, 1, 2, 4, 5. Other kinds, including kind13's explicit cross-slot reads, withhold this role. Exact source identity, immutable guards, explicit source writes, native initializer control, ordinary ingress and auxiliary isolation remain mandatory. The positive prefix's sealed recipe digest is `727c49593f3d756594049140e357d8c4c6f47aefdb215d7fd6d0a0a79ed670a8`, covering the actual 69 resources, 125 sources and 54 used DO2 tables. GuardScope alone supplies no initialization right.

The compiler alone constructs the companion capability. Its registration set, dispatch tuple, kind set and prefix are immutable and checked by identity on consumption. Direct, equal-value mutable and coordinated dataclass replacements cannot manufacture it. Changed source, programs, profile, ingress or declaration bindings fail. The scoped query also requires the prefix's complete canonical entry set. The generator normalizes current derived fields to their serialized JSON form and mints a fresh prefix immediately before the query. It does not reuse the prefix created before positive/declaration fields changed.

With this capability, the existing scoped query gathers every ordinary/four-point registration origin for each Reset slot, regardless of kind or item identity. Their procedures join the same fixed-context all-canonical-entry walk. A reached kind2 Reset remains an item candidate whenever any same-slot ordinary origin remains possible. Ordinary item creators remain candidates independently. Unsupported origin control prevents exclusion. Default Unaudited calls retain Reset as an independent possible origin. Strict entry, positive item, whole-source, quantity and door contracts receive no new rights.

### Inspected native role and lifetime

These are source-inspection findings from the frozen prerequisite packet, under the approved engine premise. All addresses below are PS1 cached virtual addresses. Source offsets are bytes within the owned RDT, never host pointers. Multibyte values are little endian.

| Field or native interval | Width, mask and role |
| --- | --- |
| Registry `0x800CE558..0x800CE5D8`, end exclusive | 32 u32 pointer words, stride 4, mask `0xFFFFFFFF`. Selected-item word `0x800CE5D8` is separate. Current-interaction word `0x800EAD94` is also u32, distinct from task Work. |
| Clear `0x800530C0..0x800530EC` | Clears registry words and count `0x800D4230`, u32 full mask. Common initializer `0x80053528` calls ordinary reset through `0x800535B8` before installing header16/task0, header17/task1 and scheduling. |
| Creators `2C/67/3B/68/4E/69` | Original handlers at `0x80054AF4`, `0x80054B60`, `0x80054BE4`, `0x80054C50`, `0x80054CD4`, `0x80055008` publish source packet +2 into the selected registry word. Item publications at `0x80054D44/0x80055084` precede acquired-kind clears at `0x80054D94/0x800550D4`. Alternate-mode publication `0x80054E94` likewise precedes clear `0x80054F78`. |
| Reset `0x80055154..0x800551C8` | Slot operand is signed i8; admitted slots are 0..31. Kind/SAT are u8, mask `0xFF`. Three u16 payload writes, mask `0xFFFF`, start at descriptor +`0xC` or +`0x14` according to preserved geometry bit `0x80`. No registry word is published. Task PC advances ten bytes and returns one. |
| Manual `0x80051038..0x800514EC`; scripted `0x800551C8..0x80055260` | Manual `0x8005113C` branches on NULL before descriptor reads. Scripted dispatch dereferences its pointer without that check; STOP6 may suppress dispatch while PC advances two bytes. |
| Kinds 0/1/2/4/5 | Inspected complete applicable native consumer classes preserve registry words. Kind5 may create actual source procedures, already covered by canonical-entry/source checks. Kind13 at `0x80052044..0x80052620` reads other registry slots and is excluded from this role. |
| Item UI acceptance `0x80072298/0x80072B40` | Stores zero to selected descriptor KIND, u8 mask `0xFF`; registry pointer and aliases remain. Cancellation retains KIND. Existing `source_task_control._ui_completion_frontiers` already models both correctly and is unchanged. |

Ordinary source roots are reset before registry reuse. `Room_load` clears the old ItemUI request at `0x80049E84..0x80049E8C` and player routine/substates at `0x8004A330` before `Event_init` at `0x8004A334`. Exact source/normal ingress excludes an early or outside dispatch before the proved prefix boundary. All 54 auxiliary tables retain their creator/Reset/dispatch isolation. A new load, restore or reconnect must bind current source and reread game state; no historical registration Boolean or sampled pointer cache carries this authority across that boundary. Initialized graphics, audio and actor ownership use the approved engine premise. This is not an arbitrary heap, renderer, DMA or full-VM safety theorem.

### Actual source consequence and preserved rejected evidence

Owned `PL0/RDT/ROOM1090.RDT`, source `00-09`, is 287656 bytes, SHA256 `785c0c49c56f49a11829c1a98718a867d851893e372d0179d9ce06a63898c4d0`. The shared prefix guarantees slots 0, 1, 2, 3, 8. All four scripted `47` operands are 1, 2, 2, 3. Slot5 creators at 8826 and 8936 in `17:3` require the opposite fixed scenario. The independently possible `17:4` to `17:35` birth remains possible under mutable story predicates. Reset at 13172, bytes `4605023114001e00cd00`, therefore stays reached, but it cannot create a same-slot registration. No Copy command exists in this source. These are validation facts, not production constants or named-item exceptions.

The actual 125-source census contains twenty sources with kind2 Reset. Only `00-09`, `00-0d`, `01-0c` qualify for this initial registration role among them. The only scenario-query delta is adding ID205 to `00-09`'s absent IDs, alongside the existing ID146 exclusion. All 125 legacy positive compiler outputs equal the required base, as do all 32 qualifying normal-engine positive-prefix outputs.

Frozen evidence directory `/tmp/re-map-re2-null-consumers-20261107-88l16anc/` is verified before use and left unchanged:

| Artifact | SHA256 |
| --- | --- |
| `report.json` | `791440fc346d47e5aa4bec27afcb0b29bf4535579ff71ea6c233b73776747e11` |
| `artifact-manifest.json` | `c4ae8c4734284f3d903ac16af66a5e1872dc8181d65f132d11e5dc2ed92b39b6` |
| `factory-all125.json` | `ed3103a529d97e91eed29ca63d93ba7e736cb08e36117f807f2ec986364c11b0` |
| `replay.json` | `8334f4ae893a46a3453a05212f6c5ed8730f2214251e8facac3516d82aeaa82a` |

Its `registration_factory.py`, `candidate_query.py`, `query_all.py` and `finalize_evidence.py` are private experiments using copied source, tracing or monkeypatches. They mint no production authority. Production has one shared interpreter and no such instrumentation. The NULL-Reset-is-no-op and accepted-item-removes-pointer hypotheses are rejected. Earlier inaccurate kind4/kind5 diagnostic labels remain preserved with the corrected native-table bounds in `native-closure-final.json`.

Root's corrected local Reset component remains `/tmp/re-map-re2-reset-footprint-root-20261107/report-no-write-hook.json`, SHA256 `d18829387645bd4f7292fd4b17177ebbaa94ced2afbad8c40e6e505218e1ac89`, with `correction.json`, SHA256 `6aa429bde723e6269d2ad2d0c0d55a5c103087984527c806b5d4f17d1e67fac8`. It reports 56 synthetic instruction-hook cases; this implementation does not rerun them. Failed earlier memory-write-hook Unicorn traces stay excluded. Synthetic geometry `0x80` is a local branch-footprint case, not valid source ownership or global reachability evidence.

### Reproduction, resulting publication and limits

New private evidence is `/tmp/re-map-re2-registration-20261107-x2pp83ih/`. `implementation-evidence.json`, SHA256 `dc6ac70c961bc03ac9e11fbd18798e2c4ebd753f09c2dfad2989bd6c78cc410f`, binds the numeric results and logs. `owned_inputs.py` copies the prior verified loader with its root explicitly changed to this worktree. `binding.json` records the real owned binder's 69/125/54 counts and sealed recipe. `verify_corpus.py` compares all source queries and both positive APIs against the required base's verbatim private baseline compiler. That baseline copy and the targeted `debug_generator.py` instrumentation are experiments only. `verify_catalog.py` compares all catalog fields, both complete generations and the unchanged floor-plan bytes.

Reproduce with the supplied clean-venv Python and explicit owned `RE_MAP_RE2_OWNED_CUE`. Run `python -m pytest -q`, including `tests/test_re2_persistent_registration.py`, `tests/test_re2_positive_prefix.py`, `tests/test_re2_source_task_control.py` and `tests/test_re2_scoped_scenarios.py`. Generate twice using `tools/build_re2_metadata.py <owned-cue> <private-room-output> <private-floor-output> --profile profiles/re2_leon_a_slus00748.json`. The final catalog SHA256 is `304daaa59e9521cdd20a5933e66456bf8396cc8d19a69f083795132364322fa0`; both floor outputs equal repository SHA256 `641c6362a66333d97d2bfcf6c72d7edb0dcfbfd390a145f7248cc0b06cee2e8b`. Only the one absent-ID addition changes the complete catalog.

`replay.py` verifies retained RAM SHA256 `939264d8e98c07e0d7afcdef69efdf1e18ac4fa05052575d726022b5dfdd8b73` and copied history SHA256 `3d8b4240e2a63d4c873d805304a77060e81d548e01690029dade132f4fd04d97`, then uses a separate temporary visits-only history. In the same 58-visit replay, Unknown item rows decrease five to four. `00-09` loses only ID205; its independently uncollected ID13 and Incomplete verdict remain. Only that room's item tuple, total and resolved reason change. Every other dataclass field, remaining quantity, full-list status, door, visit, pose and floor plan agrees. Fresh history reconstruction and repoll agree; acquisition clear/set/clear for the earlier positive additions remains reversible, and Retry/unsupported-mode publication remains atomic. Synthetic current-source tests also reverse both excluded acquisition flags and reject active or inactive contradictory ID205 descriptors atomically.

All 7,286 Python tests pass with explicit owned input, including forty new feature cases. Existing accepted/cancelled ItemUI alias and ordinary/four-point acquired-record regressions pass without changing their implementation. New cases cover the different-empty-slot NULL dispatch, conditional/unsupported prefixes, all creator classes and origins, inactive registration, unsupported kinds, canonical entry replacement, input mutation, compiler-owned/equal-value/coordinated substitutions and fresh derived-field rebinding. Scoped Ruff `E4,E7,E9,F,I` with the existing `E402` exclusion and formatting pass for all seven changed Python files. Modified-document links and the final whitespace check pass.

`render.mjs` renders the actual retained publication on desktop and mobile, checks navigation, Incomplete selection, exact publication equality, no horizontal overflow and no page errors. The existing browser suite passes all 133 RE2 outlines and its door, heading and floor controls. The original README scene reproduces byte for byte, SHA256 `82ee90937821a2593dc2a989f5598ff66970d98a017cb2286c50066d9e6685b3`; no UI implementation or screenshot changes are needed.

Contribution, 2026-11-07: the human supplies the explicit engine premise, bounded target and retained-copy authorization. The frozen NULL-consumer research is authored by `review_re3_detail_tables`, verified exact model `gpt-6.1-sol`, effort `xhigh`; root supplies the separately corrected local Reset component. This implementation sub-agent, verified exact executing model `gpt-6.1-sol`, effort `xhigh`, authors the shared traversal facts, companion/query/generator changes, regressions, owned factory comparisons, repeat generation, replay/render evidence and this appended claim. Model identity is checked from this session's matching `session_meta` and latest `turn_context`. Self-review checks the changed authority/control paths, explicit writers, type isolation, all catalog consequences, freshness, actual renders and final diff. It is not independent review. Root handles independent/external integration review. No external endorsement, native gameplay validation, additional runtime coverage, memory-card persistence or campaign readiness is claimed.

Integration review and recovery, 2026-11-12: root integrates the reviewed implementation from child `35f463d828880bbe3dc2db2a04f145f9fc6c8164` after the RE3 documentation changes. All seven implementation/test Python files remain byte-identical to that child. Before the interruption, independent reviewers, both verified `gpt-6.1-sol`, effort `xhigh`, report no findings in their separate authority/shared-prefix and query/generator/runtime-consumer scopes. Review A passes 233 focused tests. Review B passes 139 focused tests, four additional origin-query controls and an independent retained replay covering the sole ID205 removal, ID13 acquisition reversals and short-read atomicity. Those reviews add no native observations. Their original temporary artifacts and retained RAM/history copies are absent after recovery; their replay and rendering results remain historical.

Fresh recovery checks use the explicit owned CUE and a new Python 3.12.14 environment with the pinned development requirements. All 7,286 tests pass. A complete metadata generation exactly reproduces catalog SHA256 `304daaa59e9521cdd20a5933e66456bf8396cc8d19a69f083795132364322fa0` and unchanged floors. The complete catalog comparison again changes only absence205. A new independent source audit compares all 125 legacy positive API outputs and all 32 qualifying trusted-prefix outputs with the exact `a892534` compiler; all agree. Every one of the thirteen registration-qualified sources also qualifies a direct Guard. The 29 direct scoped queries differ only at `00-09`; the other 96 direct Guards are unsupported, and this bounded comparison claims no replacement for their generator companion proofs. The complete generation separately runs the existing generator paths.

Current recovery evidence is `/Users/adamekka/.cache/re-map/evidence/2026-11-12-registration-integration/`. The source comparison and complete coverage inventory are `/Users/adamekka/.cache/re-map/evidence/2026-11-12-leon-a-coverage/`, manifest SHA256 `5c2d7c61fd088783ad64e0eaddda79ceebe9e3e6aefd911fd6702cd5897514f5`. Scoped Ruff, formatting, local documentation links and whitespace checks pass. A fresh Gemini 3.8 Flash high-reasoning request fails to open its Antigravity session; Claude Opus 5.5 remains disabled. Neither supplies an external endorsement. No current-user replay, new emulator session or fresh README render is claimed by this recovery.

## RE2-SCENARIO-009: normal engine identity filtering resolves one acquired identity

Status: Candidate. The human approved normal initialized, unmodified engine execution separately for filtering, presence and doors. This claim uses the filtering premise. It covers Resident Evil 2 Dual Shock Ver., USA, Disc 1 Leon, SLUS-00748, Original Game, Normal, Leon A. Owned `SLUS_007.48` has SHA256 `e576348f64d015ecff6e1ce875a8924ee252ba7f3f9478b0917cbbdeb97db441`. The required integrated base is `55d0c8eab798e55fa5c82fe42d9480617c591d81`, verified clean before editing. No emulator runs, game input, original saves, original exploration history or screenshots are used. Historical DuckStation `0.1-12083-g00e299795` and the retained version-94 extraction provenance are inherited evidence, not a newly tested emulator or restore contract.

### Separate authority and mandatory consumption

`normal_engine_identity_filtering` constructs a distinct, compiler-owned `NormalEngineIdentityFiltering`. Its exact profile opt-in is `slus00748-trusted-normal-identity-filtering-v1`. It binds the actual executable, all 69 resources, 125 source files, 54 auxiliary scripts, ordinary ingress, declarations, source bytes and decoded operands. The typed native/resource binding remains `727c49593f3d756594049140e357d8c4c6f47aefdb215d7fd6d0a0a79ed670a8`. Direct construction, a subtype, raw matching JSON, a trace, a positive receipt or a door receipt supplies no filtering authority.

The receipt consumes the shared unsealed source-entry analysis and full auxiliary Break census. `SourceEntryPolicy.Existing`, strict entry, Guard, default positive, trusted positive and persistent-registration behavior retain their prior domains. Filtering alone opts into scalar lighting Copy ranges and the additional reviewed native selectors below. It does not borrow the door opcode set or the door policy's post-Goto ban. Native frame arithmetic still has one implementation in `native_control`; the neutral semantic profile digest and startup registration traversal are also shared without transferring authority.

The generic scoped query explicitly accepts the new type. It checks the exact source/profile/context binding, recomputes `SourceWritePolicy.IdentityFiltering` and compares the complete protected write facts with the receipt. Every ordinary creator, item Reset and same-slot registration origin contributes to fixed-guard selection. Every source writer remains protected, including unentered procedures. All four historical flags and their physical aliases remain protected. Unsupported target control retains its raw alternatives.

Generation normalizes and rebinds the current room immediately before this separate query, before raw Reset records receive candidate enrichment. `identity_filtering_items` records only facts not already supplied by the existing compilers. The complete 125-source filtering catalog has its own mandatory loader pin. Existing source, variant, acquisition-bank and event-award checks still apply to the complete candidate list. Runtime filtering joins all four fresh historical flags to the normal read/coherence transaction and retains raw alternatives when applicability fails. It does not change whole-source presence conditions. A current excluded creator, including a disabled descriptor, causes atomic Retry.

### Reviewed source and native roles

The concrete defect is in owned `PL0/RDT/ROOM4080.RDT`, source `03-08`, SHA256 `d557b3c7c47c7a9c6a707e3b72c110835aac414da2892c00799f259cac7052cd`. Slot9 has exactly two ordinary creators, at source byte offsets 10558 and 10584. Their type fields are u16LE 21 and 25; their amount operands are u16LE 7 and 6. Both use acquisition ID185, a u16LE source field. No Reset or competing registration origin targets that slot. IF10550 tests fixed flag1:0 clear at10554 and selects10558. These numbers describe the validation case; production contains no room, item or creator exception.

All source offsets below are RDT byte offsets. All native addresses are PS1 cached virtual addresses, not host addresses. Multibyte fields are little endian. Full u8/u16/u32 fields use masks `0xFF`/`0xFFFF`/`0xFFFFFFFF` unless a narrower mask is listed.

| Role | Inspected bounds and effects |
| --- | --- |
| Historical flags | STATUS at `0x800CFBD8`, u32LE, uses bits1:0/1:1/1:6 with masks `0x80000000`, `0x40000000`, `0x02000000`, expected clear. System at `0x800CFB74`, u32LE, uses0:25 mask `0x40`, expected set. Bank30 at `0x800CFB70`, bit57 physically aliases system0:25. All 32 explicit22 writers and five kind6 creator/Reset writers avoid every alias. |
| Acquisition185 | Stage3 uses bank8 at `0x800D48BC`. ID185 reads u32LE `0x800D48D0`, mask `0x40`. The corresponding PS1 RAM offset is `0xD48D0`; it is a different address from the historical mode word. |
| Lighting Copy | Copies12392/12422 write only u16LE values12398/12428 inside6B packets12396/12426. The neutral footprint retains all sixteen 40-byte light records at1420..2060, end exclusive, below heap boundary45728 and disjoint from protected source. 6A admits only its scalar+4..6 interval;6B only+2..4. Selectors, opcodes, frame targets, callbacks, creators and the entire retained light asset remain protected. |
| Lighting native | `0x80058A8C..0x80058AD8` writes a u16LE at lighting base + camera*40 +34+2*light. Source light selectors must be below3. Normal current-camera ownership is the explicitly approved engine premise. |
| Camera29 | Handler `0x8005478C` masks its source selector with`0x7F` before helper `0x80054884` stores the current camera u16LE at`0x800D4820`. Filtering independently bounds that masked selector below the room camera count. This source selects1,3,4,5,7,13, all below16. Local review added this explicit bound so a source cannot redirect a later lighting write outside the protected table. |
| Source Goto and frames | Gotos11242/12374/12456 target canonical entries11210/12346/12382, with exact `17 FF FF 00` selectors. No positive-depth caller or Gosub-return role is admitted. Escaped IF stores use root-relative `0x4C0`; the shared native formula maps this to receiver task+3, field `0x64`, a u32LE scratch store. Its immediate CMP consumes its own fresh store without yielding. The source has no Break reads. All 54 auxiliary scripts and 447 reachable programs close under the existing neutral frame walk; their 126 Break reads use field `0x60`, disjoint from`0x64`. Unentered source packets stay protected. |
| Object2D | Full native handler `0x80055260..0x8005550C` and source partition checks bound the object/model slot. Filtering admits the additional attachment flags`0x82` while requiring the fixed reference selector byte7=0. Ordinary attachment queue, model, matrix and collision ownership use the approved initialized-engine premise. No arbitrary queue, render, heap or DMA safety theorem is claimed. |
| Actor44 | Full handler `0x8005714C..0x80057714` uses a signed slot. Filtering adds only reserved`FF` to the prior0..31 domain, with models still in`0x10..0x4F`; this source selects model `0x41`. Door-only additional models and reserved`FE` do not transfer. |
| Scalar member14 | The integrated audit found a further necessary role at12182. Native member table `0x80011228`, entry14, selects`0x80055D44`, whose delay-slot store writes only Work+`0x74`, u16LE. The new role is independently admitted as an owned numeric rotation field. |
| Effect4C | Packets13366/13432 require literal category/index0/0. Handler `0x80056884..0x800568E8` calls `0x80056A38..0x80056BD8`; table `0x80011470` maps category0 to fixed position`0x8009DB44`. Updater`0x8001CEFC..0x8001CFBC` scans96 records at `0x800D8CF0`, stride`0x7C`, and clears u8+0/+1 and u16+`0x18` only in matches. Source effect bytes are comparison filters, not unchecked array indices. |
| Predicates86/87 | `0x800592F8..0x80059318` reads u16LE`0x800CFE10` and advances PC by1. Filtering explicitly retains both predicate outcomes. `0x80059318..0x80059348` writes u32LE`0x800CFBFC`=1, u16LE`0x800CFE10`=0 and u8`0x800CFE12`=0, plus PC+1. These fixed stores are disjoint from the historical words. |
| Scripted47 | Slot10's only origin is unconditional kind12 creator10258, before any scheduling or unproved atomic effect. The neutral startup traversal now also accepts an explicit pinned-atomic opcode set for this filtering caller; door traversal retains its existing boundary policy. Every explicit dispatch requires guaranteed registration and all source origins/Resets must retain kind12. Table`0x800A73F4` selects leaf `0x80052004`; it ORs STATUS with`0x8000` and writes fixed UI/stop-snapshot fields without replacing SCD. NULL and kind5 scripted dispatch remain unsupported. |
| Native input callback | Source kind5 creator13614 has canonical `FF 00 18 12 00 00` payload for17:18. Manual input checks registration before reading kind, and has no SCD caller whose PC could receive the scripted47 increment. The full binder and native kind5 entry`0x80051980..0x800519C0`, installer`0x80053138..0x80053240` and fresh root`0x800530EC` bind this separate native-input birth. Allocation may replace the final worker; it supplies a fresh root and no scripted47 post-callback PC advance. The source-directed47 contract above cannot use this callback as a non-replacing dispatch. |

The new native windows and tables are hashed against the actual pinned executable. Source and synthetic mutation controls cover each added native role, creator/GID, callback, Goto, Copy/control/selector interval, all 37 flag writers against all five logical/physical flag aliases, mutable/type substitutions and loader metadata substitutions. These checks validate the bounded compiler under its premise. They are not gameplay confirmation.

### Complete consequences, reproduction and residuals

The complete source census yields five nonempty filtering queries: existing variant206 in00-0d, absence157 in00-0f, absence36 in01-03, existing variant207 in01-0c, and new variant185 in03-08. Only the last adds generated facts. Both raw185 alternatives remain in metadata. Selection grants identity only; the existing quantity reader reconstructs its selected source amount. No presence, acquisition, activation, quantity receipt or door permission is added.

The supplied retained-RAM replay uses three read-only extracted images, all fifteen publications, reverse order and fresh trackers. Only03-08 and03-0a are actually observed current sources. Fourteen publications contain the affected explored room and change only its identity detail, resolved-list status, completion and reason. Four rows remain Taken. Every other room, door/access state, pose, current source, visit and read count agrees with the exact integrated baseline. The125-visit diagnostic changes69Cleared/21Incomplete/35Unknown to70/21/34. Those125 visits are simulated, not restored user history. There is no claim to recover the lost58-visit replay or execute native save restoration.

When acquisition is clear and there is no valid separate presence/current observation, the same room remains Unknown. Synthetic tests cover acquisition clear/set/clear, current/departed/reentry, earlier complete memory images, fresh reconstruction, every historical flag and mode mismatch, excluded live creators and failed/short/incoherent reads without partial publication or unvisited-room reveal. Stage3 remains outside both positive-presence APIs' stage0/1 entry contract. The known3/46/2 additions, absence205, both newly enumerated Reset candidates, complete candidate-bank/award checks, fresh GID matching and embedded09 Sleep protection retain their prior checks.

The complete door compiler still emits114 facts covering124 creators,11 excluded creators and165 unsupported slots. Only necessary profile hashes change. The whole semantic profile now hashes to `561e1a35af80fabb58887271476861ab9322f2e5c1525c3b52806bc2520b699c`; no policy field is excluded and no old-pin fallback exists. The regenerated door catalog pin is `d8b589016b1c2da8eb6f463c7732a4050131581074aee85efd245e97d978cc09`. The original selector-only identity catalog pin was `cdda0e06bc128799e1f5eba9e2b9d5e1c7caf01d8001dcf72b7e1e21e85e2dcf`; the parent correction below supersedes that pin.

Full owned metadata generation uses `/Users/adamekka/.cache/re-map/verification-venv/bin/python tools/build_re2_metadata.py <owned-cue> <private-rooms> <private-floors> --profile profiles/re2_leon_a_slus00748.json`. Repeated generation compares complete files, not selected rows. Catalog output is `16605417db51a48f3393636c682e8be0ab44006d64e81a79fec44a37baa361a4`; floors remain byte-identical at `641c6362a66333d97d2bfcf6c72d7edb0dcfbfd390a145f7248cc0b06cee2e8b`. The new feature leaves UI layout unchanged. No README rendering or screenshot validation is claimed.

All 7,766 Python tests pass with the explicit owned CUE. The focused authority, query, loader, source-control, reset and fresh-reader set passes 1,191 tests. Scoped Ruff `E4,E7,E9,F,I` with `E402` excluded, formatting, local documentation links and whitespace checks pass. Every legacy strict/Guard/task-Guard scope/query, default positive, qualifying trusted-positive query and registration result agrees across all125 sources. Failed prototype diagnostics and their corrections remain in private `failed-diagnostics.json`; they are not validation evidence.

Private evidence is `/Users/adamekka/.cache/re-map/evidence/2026-11-12-leon-a-identity-filtering/`. Its handoff manifest records exact request files, baseline/final source and output hashes, external dependency hashes, commands, all catalog consequences, failed diagnostics and verification limits. The prerequisite `2026-11-12-leon-a-identity185-followup` packet imported721b619/f9c508f snapshots; those conclusions were rechecked on integrated55d0c8e rather than treated as authority. Its counterfactual reader edit is retained only as historical investigation. The implemented consequence comes from the real factory, query and full generator.

Residuals remain explicit. Sources03-0e,04-00 and04-09 do not gain this capability. Their DO/switch, non-lighting Copy and noncanonical/calling Goto gaps are not suppressed. The complete filtering census retains each source's rejection and the existing unsupported native/source domains. This increment resolves one acquired identity and supplies no campaign coverage or readiness claim.

Contribution, 2026-11-12: the human supplies the separate normal-engine approvals, bounded objective, private-copy authorization and review boundary. The prerequisite investigation and this implementation have separately verified executing model `gpt-6.1-sol`, effort `xhigh`. This implementation sub-agent authors the distinct capability, neutral sharing, generator/loader/reader changes, focused controls, full-corpus comparisons, repeat generation, offline replay and this appended claim. Exact model identity comes from this session's matching `session_meta` and `turn_context`, recorded in private `author-verification.json`. Local self-review checks binding, all new native/source roles, Copy/frame/flag/dispatch protection, freshness, legacy output preservation and the complete diff. Independent/external review and integration remain the parent's work. No review endorsement or new native execution is claimed.

Parent corrections, 2026-11-12: independent reviewer `review_trusted_door_reader`, verified `gpt-6.1-sol`, effort `xhigh`, checks the complete reader path, 128 descriptor/acquisition combinations, atomic faults, schema rejection and all fifteen copied-RAM comparisons. The review reproduces an unsafe catalog omission: the selector pin does not bind the selected raw item's type. Root independently changes only creator10558 from type21 to file104 and reproduces false Cleared with acquisition185 clear. The corrected mandatory pin binds all125 raw source identities, item and competing door descriptors, Reset variants/candidates/descriptor origins/source failures, list completeness and filtering selectors before loader normalization. Selected/competing type drift and Reset type drift reject. The audited digest is now `11fd9074594ed0e455417a05d93d610bb6c59ef49a81208be3fa9f764b4b4a9f`; generated room and floor bytes remain unchanged.

Independent reviewer `review_partial_positive_entry`, separately verified `gpt-6.1-sol`, effort `xhigh`, checks258 core regressions,5,883 prior control walks,125 prior source-role results and the bounded legacy API census. Its complete task-frontier rerun is stopped and supplies no result. The review finds that actual source00-0e successfully compiles a filtering receipt but its unchanged query rejects an unaccessed model enum in partition command7506. Root adds explicit class/name/typed-value Enum encoding to the one shared digest implementation. The actual owned public factory/query regression now returns the expected empty result; enum classes, strings, integers and booleans remain distinct. The full native/resource digest remains727c as pinned above. These corrections add no filtering consequence or presence/door rights. Both independent review reports and root baseline-failing regression logs remain in the durable evidence directories.

Parent final verification, 2026-11-12: the corrected feature passes all7,772 Python tests with the explicit owned CUE,291 focused identity/receipt/reader regressions, scoped Ruff and formatting for all16 changed Python files,345 local documentation links and whitespace checks. All fifteen fresh copied-RAM publications and their read plans exactly match the reviewed implementation result. The five original root regressions fail before the corrections and pass afterward; the additional Reset type-drift case also rejects. Configured Claude Opus 5.5 is disabled, and the fresh Gemini 3.8 Flash high review fails to open its provider session. Neither supplies an external endorsement. Parent code changes and checks are frozen in `root-final-manifest.json`; combining this feature with the separate staircase/UI change requires fresh generation, replay and README publication, recorded separately after integration.

Combined staircase integration, 2026-11-12: both complete owned metadata generations agree with each other and the integrated checkout byte-for-byte. Room SHA256 remains `16605417db51a48f3393636c682e8be0ab44006d64e81a79fec44a37baa361a4`; [RE2-MAP-008](../re2.md#re2-map-008-native-staircase-doorway-contours) supplies floor SHA256 `aa7280b8ee4e82db93ee375ddd7c384c298235a972e4dadfb87b1275bb4a6996`. All145 frozen production/profile/data files and actual imported modules remain unchanged during generation/replay. Fresh replay preserves every field from the reviewed identity result across all fifteen publications. All125 raw source door lists and all170 legacy shared marker records remain identical to the original geometry baseline.

The integrated checks pass1,220 focused Python tests, all four shared map/keyboard/interruption/refresh browser suites, the ten-contour/four-layout browser check and the four-layout README render. The original whole-room hash in the new staircase test initially fails because identity metadata changed; the corrected test pins every raw door descriptor, preserving its actual geometry requirement without coupling it to independent item policies. Root regenerates the explicit README publication twice from the same three verified copied RAM inputs and only their two observed sources, then replaces the screenshot with the exact desktop render. Only03-08's resolved identity/completion changes. Final scoped Ruff, formatting,492 local documentation links and whitespace checks pass. Individual feature full suites and the integrated focused checks remain distinct. Exact commands, hashes, failed initial check and final outputs are under `/Users/adamekka/.cache/re-map/evidence/2026-11-12-leon-a-identity-staircase-integration/`. No new gameplay, native restoration, user-history access or external endorsement is added.

## RE2-SCENARIO-010: bounded native frames refine an acquired identity

Status: Candidate under the human-approved initialized, unmodified normal-engine
premise. Target remains RE2 Dual Shock Ver., USA Leon Disc 1, SLUS-00748,
Original/Normal Leon A, executable SHA256
`e576348f64d015ecff6e1ce875a8924ee252ba7f3f9478b0917cbbdeb97db441`.
This increment uses owned source/native inspection and offline saved-RAM replay.
No new emulator, collection, native restoration or memory-card observation occurs.

The retained exploration has an acquired but unidentified GID213 in `00-08`.
The prior filtering factory rejects its interior FF/FF control flow. Admitting
that flow alone still leaves an initialized-render-record update and an ordinary
door callback unclosed. The coherent correction derives all three contracts
inside the independent filtering compiler; no Door, Guard, positive-entry or
registration receipt transfers its authority.

The shared unsealed native task/frame analysis now has mandatory ordinary or
auxiliary phase and frame-role arguments. The explicit native identity role
reuses actual producer/task/depth, foreign-store, canonical-return, Break/WHILE
and auxiliary checks. It keeps both canonical predicate86 continuations and the
IF pop. Only its own immediate CK21 or bounded CMP23 can consume an escaped IF
cell. Retained-level Goto, foreign Member_cmp, SET/yield/call-separated stores,
early Return, EventNext and sound compaction gain no identity permission. The
original four control roles and both original source-entry policies retain their
frozen outputs. Shared native windows and installer census are recomputed by
each policy compiler, not supplied by a matching receipt mirror.

For the new identity source policy, every relevant53 initializer retains record
selector below4, blend below4 and RGB mask at most7;74 selects a record below4
and consumes a signed16LE coefficient. The complete helper at PS1 virtual
`0x8002C2B0..0x8002C324` writes within fixed76-byte records based at `0x800DFC1C`.
It reads a data byte at record+`0x13`, not a per-record pointer. The native buffer
selector at `0x800CE5E0` has the explicitly approved initialized0/1 ownership
premise. No all-four-record bootstrap or arbitrary renderer/GPU/DMA theorem is
claimed, and no record is initialized to an invented value. Actual `00-08`
additionally has a separately checked same-record53 predecessor at7244 before
74 at7252 on every shared-graph path from entry7200. That local dominance is
not inferred from lexical adjacency or required to prove the helper's fixed
immediate write bounds under the approved ownership premise.

A new callback role requires guaranteed registration and every slot alternative
to be an immutable physical3B/68 door record, correct installed geometry and
payload bounds, a covered door resource and clear lock high bit. Reset, Copy,
mixed kinds, unregistered/NULL, locked kind1 and kind2 paths remain rejected.
Under protected STATUS1:0=0, the complete kind1 callback
`0x80051514..0x80051718` has two helper-free feasible paths. Busy word
`0x800CFDDC` remains unknown. Its non-stack writes are only pending phase
`0x800DF348` u8, pending payload `0x800CE550` u32LE and second STATUS word
`0x800CFBDC` u32LE OR `0xFF000000`. These do not touch fixed first STATUS word
`0x800CFBD8`, source bytes or task/frame storage. Aot_on advances the same task
PC after return. The later world transition sets SYS mask `0x02000000` before
its owned auxiliary/loader lifecycle. Existing transition/reset rejection,
room/RDT/source binding and fresh flag/coherence checks remain mandatory.
Multibyte data and pointer words are little endian; byte/halfword/word masks
are `0xFF`, `0xFFFF`, `0xFFFFFFFF`. Source offsets are RDT byte offsets, never
host addresses or PS1 virtual addresses.

All125 actual public factory/query results reproduce the bounded projection.
Support becomes30 sources; all19 prior supported queries remain equal, without
a legacy fallback. The new raw variant is GID213 creator6934, type20, amount15.
The additional raw absence `01-13`/GID24 duplicates an existing scoped absence
and is deduplicated by the generator. Complete metadata adds only the `00-08`
identity record. Every other item, presence, door and floor field remains equal.

The policy audit is `slus00748-trusted-normal-identity-filtering-v2`. Full semantic
profile SHA256 is `c9afde348a1f7651e33e961443b7fa3c24e208a377587b05edd816c59df11e58`;
the mandatory complete raw identity catalog is
`70387e94440aef491be72b765f1d55cc87977dd653d5981b70bdcab2dc122407`.
The independent door catalog changes its complete-profile binding only, to
`aab4d3a03b2573d33c60e29410b94ec31725b7d9afaa5c2fb5eadcca566c1a00`.
No semantic profile field is omitted and no old pin is accepted. Complete
69-resource/125-source/54-auxiliary binding remains
`727c49593f3d756594049140e357d8c4c6f47aefdb215d7fd6d0a0a79ed670a8`.

Two complete generations agree byte-for-byte. Fifteen fresh copied-RAM
publications and six publications restored from the private68-source/71-region
history copy preserve every outside-target field. Only `00-08` gains its
specific acquired identity, quantity and list completeness, becoming Cleared.
The retained actual scope has47 Cleared,15 Incomplete and6 Unknown rooms;
all4 Unknown item rows remain. Doors, pose, visits, regions, read requests and
requested bytes stay equal. Earlier synthetic acquisition-clear images restore
Unknown when no independent presence is established; a fresh matching current
descriptor supplies its own Available state. Current excluded creators, even
with zero activation bits, cause atomic Retry. Failed/short/incoherent flags
cannot publish stale clearance. No visited room is added.

The source-only projection, kind1 component and independent renderer inspection
remain frozen in `2026-11-12-gid213-joint-corpus-projection/`,
`2026-11-12-kind1-dispatch-closure-research/` and
`2026-11-12-render-record-bootstrap-audit/` under the private evidence root.
Root's actual compiler/generation/replay checks are in
`~/.cache/re-map/evidence/2026-11-12-native-identity-implementation/`.
Its baseline-failing regression, complete generation comparison, independently
rebuilt current item inventory, publication comparison and rejected test-harness
assumptions remain retained. The README fixture reproduces byte-identically;
UI implementation and image bytes do not change.

Contribution, 2026-11-13: root, verified `gpt-6.1-sol`, effort `xhigh`, authors
the independent native identity implementation, shared extraction, regressions,
complete regeneration, retained replay and this record. The preceding November
12 source/kind1/renderer investigations retain their separate authorship and
unsealed limits. The human supplied the normal-engine trust decisions.
An independent core reviewer, separately verified `gpt-6.1-sol`, effort `xhigh`,
checks six stable core files, actual phase/role extraction equivalence, foreign
field/return/callback/Copy boundaries and unchanged old domains. Its57 owned
identity tests and63 source-only shared helper tests pass;5 owned helper cases
are skipped and18 deselected in that separate selection. It reports no findings
within that core scope. Generated catalogs and reader replay remain root's
separate verification, with no new gameplay or external endorsement implied.

Parent final verification, 2026-11-13: all 8,462 Python tests pass with the
explicit owned CUE. The separate consumer reviewer, verified `gpt-6.1-sol`,
effort `xhigh`, reports no findings after 384 focused tests, 14 raw catalog
mutations, 8 applicability reversals, all 19 prior public query comparisons,
the complete 125-source metadata comparison and all 21 replay/history
publications. Its 342 reviewed source files remain byte-identical. This review
does not include native restoration, gameplay or rendered UX/AX.

The configured external snapshot review returns "No findings." T3 reports
model `gemini-3.8-flash`, with requested `thinking_level=high`, through
Antigravity; it supplies no separate executed-model attestation. The review
checks only the supplied source/contracts/tests, with no tools or runtime
validation. Configured Claude Opus 5.5 remains disabled and supplies no review.
These perspectives do not confirm the Candidate gameplay claim. Root's final
source/artifact manifest records the actual reviewed inputs, completed review
responses, checks and retained limitations.
