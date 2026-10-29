# RE2 startup declarations

[Claim index](../../research.md) · [RE2 testing](../../testing/re2.md) · [Room completion](../../room-completion.md)

## RE2-STARTUP-002: a bounded startup prefix establishes a remaining pickup

2026-10-29. Status: Candidate for Resident Evil 2 Dual Shock Ver., USA Disc 1, SLUS-00748, Leon A, Original/Normal. The integrated compiler exports one positive declaration for source `00-02`, acquisition ID 154/type 20. Native pickup/reentry observations and saved-capture replays support the correction. The constructor and incoming-resource argument remains a bounded source/native audit; the captures do not observe an active constructor suspension or fully confirm the shared rule.

### Failure and the smaller proof

Visited source `00-02` has two declarations of the same slot-seven ammunition pickup, acquisition ID 154/type 20. Both have nonempty ordinary pickup rectangles. The departed presence check remains unresolved because the existing proof requires startup completion through more behavior than is needed to establish this declaration. Whole-source fixed-context preservation also fails. Extending a later actor or item lifetime is unnecessary for this positive conclusion.

The new proof is limited to the synchronous startup prefix. Root `16:0` must complete before any declaration in `17:0` can count. The second root can then establish the pickup through a bounded call path before a later unsupported effect. Alternative branches must establish the same acquisition ID and item type. The declaration is evaluated without pruning the native system-mode branch, so the two quantities remain alternatives. A catalog entry, an uncalled procedure or queuing a later task does not establish presence.

This is positive knowledge of a remaining item. It supplies no absence result, future access or event-progress guarantee, whole-source fixed-context receipt, quantity selection or item-list coverage. Acquisition and room conditions must still be read afresh; earlier savestates must reverse collection. Current live registry results retain their independent precedence. The separate [startup setup proof](startup-presence.md#re2-startup-001-setup-effects-and-equivalent-creators-preserve-known-items) and [known puzzle targets](known-puzzle-items.md#re2-puzzle-001-declared-puzzle-targets-remain-required-before-activation) retain their existing scopes.

### Exact revision and resources

Owned executable `SLUS_007.48` is 987136 bytes, SHA256 `e576348f64d015ecff6e1ce875a8924ee252ba7f3f9478b0917cbbdeb97db441`. Owned source `PL0/RDT/ROOM1020.RDT` is 184396 bytes, SHA256 `30fc267de1ad566dcb61403822731ec5eae099d934f244538d34c33ebe64dddf`. RDT offsets below are file bytes; addresses are PS1 virtual addresses, not host-process addresses. All numeric memory fields are little endian. Words/pointers use four bytes and mask `0xFFFFFFFF`, halfwords two bytes and `0xFFFF`, and bytes `0xFF`, unless a narrower mask is stated.

Stage-zero loading selects native recipe index eight at `0x800A2118`, file seven, destination `0x8011A000` through pointer word `0x80010810`. The owned `COMMON/BIN/STAGE1.BIN` is 1704 bytes, SHA256 `8e1c7fc3a99168a340dca2310ac0b7f41649bdea517ccd72678abef969c0e6ad`. Four-byte alignment gives exact RDT base `0x8011A6A8`. The proof must bind this resource and recipe rather than reuse the stage-one receipt's different source base.

The source's model-`0x1F` constructor presets are `0x0046`, `0x8046` and `0x8040`. Their loading audit uses exact owned `PL0/PLD/CDEMD0.EMS` entries:

| Resource | Sector | Bytes | SHA256 |
| --- | --- | --- | --- |
| Common code zero, loaded at `0x8010D000` | 0 | 53068 | `bd2c05f70cbf1088404cf583ff970f5f0d5d8b7ee05d32d027cd1c3def88bbdb` |
| Common code one, loaded at `0x80100000` | 26 | 53068 | `7115c0ad492f63c53ce1e3a0db99081c62b0a0ab3e7f7d51a71ffc99c5e2959c` |
| Motion entry 62 | 1060 | 133152 | `40d93d57aa2848212484ecb0f563119b234f6f448513678f13509602bf07d647` |
| Model entry 63, 17 parts | 1126 | 140804 | `2cbe3c4f82e00672eeca0ba02a36c8128932fad5745b2208c309ebe987ec8211` |

The synchronous first root declares two doors and embedded object zero, then reaches four actor constructors at 6248, 6270, 6292 and 6314 before End at 6336. The second root calls `17:4` at 6428 and `17:19` at 6430. The latter initializes object one at 7792, then declares ID 154/type 20 at either 7838 or 7864. Quantities 30/15 stay separate alternatives. Its End is at 7888; embedded TMD data begins at 7892. The last procedure's catalog extent continues into those assets, so a positive prefix must not pretend that the complete last-procedure extent is executed code or weaken another proof's full-source exclusions.

### Constructor suspension and interpreter ownership

Native `Event_init`, `0x80053528`, resets the ordinary task pool, queues `16:0` in task zero and `17:0` in task one, then scans the ordinary tasks. The call remains inside main-game `Room_change`, `0x80026B7C`, through `Room_load`, `0x80049E48`. Actor constructor `0x8001AAA8` calls cooperative yield `0x80031F94(1)` at `0x8001AB74`. Returning one from the SCD handler is therefore insufficient evidence that the constructor never suspends.

Suspension yields the current main-game coroutine. It does not recursively run that caller's ordinary frame/actor loop. Automatically queued SCD tasks use slots two through nine and cannot replace the executing second startup root. Auxiliary door interpretation is a distinct concurrent obligation and must be checked against the exact possible incoming resources.

| Native domain | Address, width or bound |
| --- | --- |
| Task pool | `0x800D7860`, stride `0x174`; ordinary slots `0..9`, auxiliary slots `10..13` |
| DOOR02/0A scheduled auxiliary tasks | Slots 11/12; slot 13 remains inactive |
| Inspected `Goto FFFF` write | `0x800D8BE8`, four bytes, inactive auxiliary task 13 `+0xA4`, with executing task ten at call depth two |
| Main-script phase restoration | `0x800574F0` stores zero to byte `0x800D8CC8` |
| Main procedure-table restoration | `0x800574FC` restores pointer word `0x800D8CBC` from loaded RDT `+0x4C` |
| Maximum constructor-prefix heap end | `0x8018A558` |
| Fixed model UV region | `0x8018EF3C..0x8018FFF0`, exclusive upper bound |
| Incoming door payload start | `0x801A1000` |

The `Goto FFFF` finding describes an exact native write to an inactive auxiliary record. It is not a harmful-corruption or ordinary-task mutation claim. The bounded constructor model has at most four 584-byte actors and seventeen 172-byte parts per actor. Exact model, primitive, mesh, shadow, temporary loading and UV bounds keep the startup work below the auxiliary payload. A whole future AI or actor lifetime is outside this argument.

The ordinary ingress creators are source `00-01` offset 6082, model `0x02`, and source `00-18` offset 7690, model `0x0A`. Their exact owned door resources are:

| Resource | File bytes | File SHA256 | Script bytes | Script SHA256 |
| --- | --- | --- | --- | --- |
| `COMMON/DOOR/DOOR02.DO2` | 58608 | `ec337184ffda73acdde7a5945e489e66240650628a2ca317e1c4877990c84dbd` | 540 | `b5f0bac206d77bdd69f6acb419af6113170941a3a109fcb57db9999533fa3d12` |
| `COMMON/DOOR/DOOR0A.DO2` | 77932 | `ae6d3950611c0636f4f2d068d49ce3ef8f844f695a2a75465f12062731431d89` | 600 | `e0dc44cf25b1a06d992d54471ad04281ef2d2c7a6fe3e17fb570625ca1aa6a5f` |

The door audit covers task/control records, Work selections, owned model/renderer work, sound and source/table restoration. A `0x0A` FOR-tail Unicorn attempt failed and is excluded from any complete execution claim. Static resource/native bounds and the successful native reentry below remain separate evidence. Target room identity alone cannot pin an incoming auxiliary asset. `startup_entry_selection.py` binds the exact executable, all 125 owned RDTs and 69 native resources. It checks native file indices, LBAs and resource sizes before decoding possible incoming routes. All 54 referenced DO2 resources exclude pending-AOT producers and unsupported routing writes; their calls fit four total native frames. The pinned non-card native startup paths and final pending-payload setter bound stage-zero ingress to models `0x02`/`0x0A` for this source. This complete corpus/resource receipt, rather than the two declared creators alone, authorizes the constructor's auxiliary-resource audit. Memory-card startup and arbitrary pointer corruption remain outside the contract.

### Native observations

The isolated emulator is official DuckStation `0.1-12083-g00e299795`, full commit `00e2997958d62de79d352cd680ec0c1ad95d491c`, executable SHA256 `5c879677051cfb173002df22baee741c96fa8071c6fe1dd7e5454092bf128173`. Both achievement integrations are disabled, memory-card slots are None/None, audio is muted and a black shader keeps agent gameplay out of view. Test history is private. The pickup test adds no health, ammunition, story, key or acquisition write. It retains the seed's equipped type-two quantity 99, unchanged; it does not establish that inherited seed as unmodified gameplay.

The initial equivalent entry reused the twelve-byte owned destination from source `00-01` door offset 6082 and nine established pose fields in a Waiting Room entry using incoming model `0x0D`. `alley2-native-entry-setup.json` records every write and the original item flags. It is a controlled equivalent destination, not evidence of ordinary model-`0x02` ingress.

The current capture `alley2-native-current-before.ram` has SHA256 `e0bf75b92f77dc552119603e4b932729ab0ab82a21fbdbedfd30d4d31bf8b55a`. Native slot seven binds creator 7864 at source base `0x8011A6A8` and reports Available, 15 rounds. The acquisition word at `0x800D48CC`, four bytes, has mask `0x00000020` clear. Inventory at `0x800D4A48` changes from bytes `14 2D 00 00` to `14 3C 00 00`, type 20 and quantity 45 to 60, after the ordinary pickup. The later checkpoint/reference SHA256 is `cc6d1bece52115c097e1d93850e91621033d091aee76e3d72ac130ace3f84bd4`; acquisition is then set and the item is Taken. Earlier/later native F2 checkpoints and F1 restores compare equal to their complete two-MiB reference RAM images. This does not test memory-card persistence.

Root subsequently used ordinary source `00-02` door one to `00-18`, then `00-18` door two at creator 7690 back into `00-02`, incoming model `0x0A`. `alley2-native-0a-current-before.ram` SHA256 is `028cd31b83bece056a07b76b1c508d3954664dc1e056445db2f0245764bffc4f`. The native item is Available, 15 rounds; acquisition 154 remains clear and inventory remains 45. Native counter fourteen at `0x800D480A`, signed two bytes, is ten. This reentry is separate from the equivalent `0x0D` entry and award.

All four enemy pointers remain the inactive sentinel `0x800D424C` in these observed entries because acquisition flags skip construction. They validate the real item binding, award, ordinary `0x0A` reentry and exact restore pair. They do not observe a suspended active constructor, exercise every constructor preset or confirm the auxiliary-interleaving proof at runtime.

Uncollected departure into `00-18` has SHA256 `c56a91d64f0bc634fb6d392c1f81c11fb99eae201d63eac1483a1996e38d162c`; the prior reader still reports the departed pickup Unknown. Collected departure SHA256 is `79561c2fd6a532288f21f83ad7fbbbe1db944de81c977bb8a55c69772e963184`; its prior reader already reports Taken and a cleared item list. The new outcome is Uncollected/Incomplete for the uncollected departed declaration, retaining Unreconstructed quantity and independent door uncertainty. Collected departure remains Taken/Cleared. The final ordinary `0x0A` departure was captured only during transition and returns Retry; no settled departure from that particular reentry is claimed. The private emulator was already stopped when final integration resumed, and no further gameplay was started.

### Reproduction, validation and contributions

Private source/native evidence is under `/tmp/re-map-unresolved-20261028/`: `next-00-02-positive-prefix-candidate.json`, `next-door-prefix-audit.json`, `door02-0a-resource-bounds.json`, `waiting-timing-constructor44.asm`, the owned RDT/executable and exact resource images. Native captures, setup, `alley2-native-validation.json` and private checkpoints are under `/tmp/re-map-loop-20261028/`. Read the validation JSON's separate ingress classifications and constructor-skipped limit before reusing a capture. Copyrighted resources, raw RAM and RE2 saves remain outside Git.

Regeneration uses `tools/build_re2_metadata.py` with the owned Leon CUE and profile. `startup_declaration_audit` parses the pinned manifest; `bind_startup_declaration_audit` requires `bind_entry_selection` to return its complete owned-corpus receipt. `startup_declarations` then binds source bytes, decoded programs, native flag addresses and write/allocation bounds. `source_presence` in declaration mode requires root `16:0` to finish and establishes equivalent positive targets before an unsupported later root-17 effect. Reentry into setup allocations, over-depth calls/IF frames, asynchronous-only targets, conflicting identities, stale receipts and uncovered incoming models withhold inference. Native binding failures are explicit modeled results, and a required generation failure stops generation.

The generator emits only `startup_item_declarations` as positive metadata. It adds exactly one nonempty record, source `00-02` with ID 154/type 20/slot seven and creator offsets `[7838, 7864]`. Removing that new field from each source and the new header manifest/research ID leaves the complete prior catalog JSON equal to baseline `e813bde`. Floor geometry remains byte-identical. A second generation from the owned CUE must reproduce the tracked catalog exactly. The runtime reader preserves fresh acquisition and current live-registry precedence; declaration knowledge supplies only the departed remaining state. The existing item-list completeness is unchanged.

Run `python3 -m pytest -q tests/test_re2_startup_declarations.py tests/test_re2_startup_entry_selection.py tests/test_re2_profile.py tests/test_re2_tracking.py`. The final focused suite passes 621 tests. The complete suite passes 3706 tests. Scoped Ruff format and E4/E7/E9/F/I checks and `git diff --check` pass. Profile regressions reject missing/extra fields, malformed identities/offsets and audit/catalog drift. Reader regressions reverse fresh acquisition with a new tracker and withhold torn read publications.

Private `declaration-item-replay.py` compares 48 distinct captures against `e813bde`: 33 Display and 15 Retry results. Twenty-nine Display publications change only the target item from Unknown to Uncollected and its room from Unknown to Incomplete. These comprise 27 retained/accepted departed captures, one controlled equivalent-entry departure and one separately excluded clipping-geometry control. Four current/acquired Display outcomes and all 15 Retry outcomes stay unchanged. Every other source, door, quantity, list-completeness value, pose and visit agrees. All 33 Display maps reproduce through fresh production visits-only history save/close/reopen; item or door verdicts are never persisted. These are replay checks of existing native observations, not 48 new gameplay cases.

Headless desktop `1280x1060` and mobile `390x844` checks select the corrected room through the grouped remaining-item list, show Remaining/Items remain, preserve its independent door warning, and find no overflow or page errors. The complete item list no longer appears under incomplete item checks. `docs/images/re2-map.png` is refreshed from this retained explored-map publication, without revealing test visits in the user's history.

Contributions, 2026-10-28: the human user reported unresolved gray rooms, requested the repair loop and then directed the agents to finish the last feature and stop. The `metadata_diagnosis` agent, exact model `gpt-6.1-sol`, researched and implements the bounded declaration receipt, constructor loading and auxiliary ownership/resource audit. The `door_diagnosis` agent, exact model `gpt-6.1-sol`, audits incoming-door selection and routing. Root, exact model `gpt-6.1-sol` verified by authoritative T3 runtime metadata, performs integration and the native equivalent entry, pickup, ordinary reentry and exact earlier/later restoration. The `procedure_entries` agent, exact model `gpt-6.1-sol`, authors this draft and checks its evidence, scope and links. Final integration/review contributions will be appended when complete. Configured external review providers are disabled; no returned external review or endorsement is claimed. Earlier research authorship remains unchanged.

Contributions, 2026-10-29: Root, exact model `gpt-6.1-sol`, completes profile/compiler/reader integration, regeneration, strict catalog comparison, 48-capture replay/history checks, desktop/mobile rendering and final verification. The `door_diagnosis` agent, exact model `gpt-6.1-sol`, completes the incoming selector and its mandatory manifest invariants. The `metadata_diagnosis` agent, exact model `gpt-6.1-sol`, completes declaration receipts and source/ownership regressions. The `final_declaration_review` agent, exact model `gpt-6.1-sol`, independently reviews native/resource/source binding, prefix ownership, positive-only semantics, profile validation, coherent acquisition reads and history compatibility. Its 620-test focused check and scoped lint pass with no blocking findings; it does not run an emulator or review rendered UI. Root subsequently adds one direct-config consistency regression, giving 621 focused tests. Configured external Claude/Gemini providers remain disabled/unavailable, so no external review is claimed. The repair loop stops after this feature at the human user's request; other unsupported item/door checks retain Unknown.
