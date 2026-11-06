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
