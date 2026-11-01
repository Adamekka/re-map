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
