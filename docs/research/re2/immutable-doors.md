# RE2 immutable door bindings

[Claim index](../../research.md) · [RE2 testing](../../testing/re2.md)

## Normal-engine policy extension for door tracking

2026-11-12. The human explicitly selects "Use normal-engine trust for doors" after requesting coverage of all unresolved Leon A rooms, doors and items. This extends the ordinary initialized, unmodified engine premise already approved for [item filtering and presence](scenario-selection.md#positive-presence-policy-extension-2026-11-07) to door interpretation on the pinned SLUS-00748 Leon A Original/Normal profile.

Door rules must still check every relevant creator, Reset, retargeting path, scenario guard and explicit source write. Concrete unsafe script/control paths remain unsupported. Native initialization, resource ownership and ordinary engine execution use the approved premise; a general renderer, heap, DMA or whole-VM safety theorem is not required for each source. New door authority must bind the actual revision and source inputs explicitly. Existing item/guard capabilities alone grant no door rights.

Lock/unlock and applicability flags must be read afresh and checked coherently after departure, reentry, reconnect and earlier/later savestate changes. Passage remains separate from unlock knowledge. Key possession alone does not establish that a door was unlocked. Exploration still reveals only entered rooms, and door state remains separate from room clearance.

This is a policy decision, not a new door proof, runtime observation or confirmation of campaign coverage. The existing bounded claims below retain their original assumptions, authorship and limits. Subsequent implementation must record its own supported outcomes and remaining source gaps.

Contribution, 2026-11-12: the human supplies this explicit extension. Codex root, verified exact model `gpt-6.1-sol`, effort `xhigh`, records it. The current audit and future implementation are separate from the approval.

## RE2-DOOR-007: bounded native writes preserve departed open doors

Status: Confirmed open bindings in the two native Waiting Room entry situations below for Resident Evil 2 Dual Shock Ver. USA Disc 1, SLUS-00748, Leon A, Original/Normal. The shared lifetime interpretation remains Candidate outside those observations. Other revisions and general departed-door inference are untested.

Executable `SLUS_007.48` SHA256 is `e576348f64d015ecff6e1ce875a8924ee252ba7f3f9478b0917cbbdeb97db441`. Source `PL0/RDT/ROOM2010.RDT` SHA256 is `48360046aa7758cb7a0df5a1306b8ecd2902374218fe330c57ccd786f4f26f37`, size 196852 bytes. Native tests use isolated DuckStation `0.1-12083-g00e299795`, commit `00e2997958d62de79d352cd680ec0c1ad95d491c`, executable SHA256 `5c879677051cfb173002df22baee741c96fa8071c6fe1dd7e5454092bf128173`.

### Failure and correction

After departure, two enabled, unlocked Waiting Room doors became unresolved. Their byte-identical script alternatives occupy offsets 3018/4232 for slot zero and 3050/4264 for slot one. The [row grouping fix](dualshock.md#re2-door-006-alternate-door-creators-share-one-detail-row) removed duplicate rows but deliberately did not establish access.

A positive departed binding now requires all of the following: exact audited executable and auxiliary resources; a closed native procedure-entry namespace; preserved fixed scenario; bounded reachable source, actor, part, model, collision and interaction writes; fresh single startup allocations; guaranteed door creation in a deterministic initializer prefix; and identical enabled, unlocked creators for that slot. An unsupported effect yields no proof. A reachability result alone cannot establish activation.

The actual source produces two proofs, each requiring enemy flag bank 6, bit 24 to remain clear. The reader reevaluates this condition from fresh saved state and includes its word in the coherent read transaction. It never persists access or carries it across a savestate load. Current-room interpretation still requires its live binding, including missing/inactive results. This changes door access only. Items, clearance, visited rooms and positions keep their independent rules.

### Native entry and write obligations

All native addresses below are PS1 virtual, little endian. Source ranges are byte offsets in the RDT; they are not host pointers. Full-width pointer masks are `0xFFFFFFFF`, halfword masks `0xFFFF` and byte masks `0xFF`.

| Domain | Native binding and bound |
| --- | --- |
| AOT registry | `0x800CE558`, 32 four-byte pointers; selected item global `0x800CE5D8` is outside the registry |
| Fixed objects | `0x800D0324`, 32 records of `0x1F8` bytes |
| Room source | Native stage setup places it at or above `0x8011A000`; loader `0x8004A30C..0x8004A324` starts free work at relocated section 2, not at the full file end |
| Source heap boundary | Offset 15592. Script tables/code end at 4404, door creators before 4296; all lie below allocation work |
| Actor construction | Opcode 44 allocates a fresh `0x248`-byte actor; native part allocation uses fresh heap records of `0xAC` bytes |
| Actor member write | Opcode 34 selector 23 writes two bytes at actor+`0x1D4`. The actual type-22 state uses this as an animation semaphore; it is not a generic pointer-safe selector |
| Part writes | Opcode 6E selectors 0..6 write `(offset,width)` values `(0x70,2)`, `(0x72,1)`, `(0,2)`, `(2,2)`, `(0x68,2)`, `(0x6A,2)`, `(0x6C,2)` within proven owned parts |
| Fresh applicability | Bank 6 base `0x800D487C`, bit 24, unsigned four-byte word, mask `0x00000080`, expected zero |
| Embedded models | MD1 directory section 10, eight-byte entries. Mode-one relocation writes only bounded model/UV data and newly allocated primitive packets |
| Collision | Opcode 37 writes the bounded SCA flags halfword. The shared SCA formula serves item-context and door proofs |

The scalar actor interpreter exports 149 reached locations, four bounded Copy writes, two owned actor writes and 32 owned part writes for this source. Fourteen other 6E commands lie in unentered procedure 17:7. Their exclusion depends on the joint entry/write invariant, rather than an unqualified scan for calls. Copy targets are scalar 6E operands; control bytes, directory entries, constructors and ownership operands remain unchanged. The largest literal part index is 22; copied indexes range 0..21 within the owned 23-part model.

Decoded command spans must not overlap. Review reproduced an IF entering an item quantity halfword initially decoded as `END`; native Original-mode pickup changes quantity 1 to 2, making those same bytes `SLEEP` and exposing another instruction path. The shared partition validator now rejects that source before exporting a door proof. Invalid signed actor slots likewise return no write certificate rather than reaching an ownership assertion. Neither counterexample occurs in the actual Waiting Room source.

Native room initialization clears ordinary task frames and AOT slots before roots 16:0, 17:0 and frame procedure 17:1. The source's call/task closure contains procedures 2,3,4,5,6,8,9,10,11 and excludes 7. Native `Evt_exec` advances the caller PC before scheduling. This is distinct from the unsafe shifted `Aot_on` scenario investigated in [RE2-DS-004](dualshock.md#follow-up-unsigned-goto-depth-audit-2026-10-28).

The profile-owned entry manifest binds `STAGE2.BIN`, both pool-specific actor code resources for model `0x22` and preset `0x4402`, and door models `0x09`/`0x0D`. Each complete resource is hash checked against the audited recipe. Door scripts use a separate table while ordinary room execution is stopped; local auxiliary procedure seven is not room procedure seven. The type-22 native state, graphics callbacks and stage routine do not enter another room procedure. The binder checks the native lookup tables as well as full resource hashes. This is a bounded logical engine-work contract, not a proof that arbitrary corrupt pointers or GPU/DMA state cannot write RAM.

Dated extension, 2026-10-30: [RE2-PUZZLE-002](known-puzzle-items.md#bounded-source-correction-2026-10-30) adds stage zero's exact `STAGE1.BIN` recipe and audited incoming model `01`. Entry receipts now bind both stages explicitly and expose their distinct source addresses. Immutable-door callers select the base for the actual stage; their reachable-effect and sound-lifetime restrictions stay intact. The shared EDT/VAB parser replaces the duplicated layout/sample arithmetic, while this caller still requires null section 22. No additional immutable-door result follows from this extension. Root and the `mode_design`/`sound_bindings` agents, verified exact model `gpt-6.1-sol`, authored and checked this extension.

Dated extraction, 2026-10-30: [the shared lifetime validator](../../../src/games/re2/room_lifetime_proof.py) now returns a frozen receipt bound to the exact source and decoded program graph. It retains native entry/resource binding, partitions, actor write ownership, fixed flags, task/call/allocation facts and fresh applicability conditions. The door compiler independently applies its existing deterministic-prefix and identical-binding requirements. The shared receipt proves neither finite initializer continuation nor item or door presence.

The 51 moved validator statements are AST-identical apart from the failure-enum rename. All 125 owned-source door results and 52 retained publications match baseline; the replay retains 41 Display and 11 Retry outcomes and leaves user history unchanged. A full owned-CUE regeneration produces byte-identical room and floor artifacts, SHA256 `dc49bd6358ab9c25c262d19d3d79d0ef5b0fc43b0f9113166dcc93be27735bb1` and `ed0d180d7cec62245194b35d43e4c61aae3cd621031935d9b469b137de5369ec`. All 884 focused tests pass; an independent door-only run passes 73 tests, alongside scoped Ruff formatting/F and whitespace. Reproduction is `/tmp/re-map-lifetime-extraction-20261030/verify.py`; root's AST and regeneration evidence is under `/tmp/re-map-lifetime-extract-20261030/`. This adds no new gameplay or tracking fact. The `next_identity_evidence` agent authors the extraction, root independently checks the moved logic and regeneration and writes this contribution, and `gdb_latency` independently reviews binding/guard/failure/consumer behavior and runs the door suite. All use exact model `gpt-6.1-sol`, verified by authoritative T3 runtime metadata. External review providers remain disabled.

### Callbacks and sound are real writes

Kinds 4, 10 and 13 are admitted only in their audited forms. Non-scheduling does not mean no writes.

Kind 4 uses the shared [nonchoice message grammar](scripted-items.md#message-lifetime-and-saved-word-preservation) in both language sections. The final message entry has no next directory offset: its witness binds the actual two-byte directory entry and the text through its first valid `FE` terminator within the section. Existing non-final padded text witnesses retain their original bounds.

Kind 10 enters box mode, with bounded inventory and fixed object work. Inventory entry `0x80068B88` temporarily replaces RDT header+`0x2C` with menu lighting and saves the original at `0x800DCBCC`; close `0x80068EE4` restores it. Whole-header immutability would therefore be false. The proof admits this particular save/restore exception; the live reader rejects the temporary section mismatch.

Kind 13 selects a bounded ordinary item descriptor and declared model. Its camera helper `0x8002C7AC` searches 20-byte RVD records by byte two, rather than indexing by camera number. Its eight halfword stores remain inside the selected RVD record. Deferred item pickup may disable exactly the selected item descriptor's kind byte at creator+2. No competing door/reset binding is permitted for that target.

File pickups use the shared bounded file path, not a named-file exception. The 25 native file indexes 0..24 correspond to item types 104..128. The base-picture byte table at `0x800A9AD0` and inclusive page-limit halfword table at `0x800AA144` select 163 bounded picture rows at `0x800A94B4`. Each row is eight bytes; all payload widths are at most 55904 and fit the 5257216-byte image archive. The fixed worker `0x8006D444` loads graphics at `0x801A0000`, without a source procedure entry. File-list insertion is bounded to 24 bytes at `0x800D4B68`; pickup completion disables only the selected item descriptor and sets its acquisition flag. Source and assets must end below the earliest upper graphics destination, `0x80198000`. The entry receipt binds the exact source base, `0x8011A000 + align4(1626) = 0x8011A65C`, through the stage resource recipe and native file directory.

Sound handler `0x8005BA28` can write VAB tone flags. It is not a no-op. Bank-two EDT/VAB pointers are initialized from source sections 0/1 by `0x8005A338`. Sound compactor `0x8004A414` returns before relocation when section 22 is zero; the actual source has zero there, and the compiler preserves that header field. Nonzero section 22 remains unsupported. This closes the sound-address obligation from source/native semantics without consulting a cached departed observation. It does not generalize the legacy [RE2-SOURCE-001](../re2.md#re2-source-001-bounded-sound-relocation-preserves-room-identity) paired-relocation evidence.

For this source, EDT is 12296..12488 and VAB is 12488..15592. Its relevant tone writes are at 14793, 14825, 14857 and 14889, outside script/door bytes. The compiler bounds all declared EDT tones, extra tones and voices against the initialized bank. Fixed voice work occupies `0x800D4CA0 + 2*voice` and `0x800D4F18 + 32*voice`, with voice plus extras below 24. Bank-four UI sounds use the initialized global bank, outside room source.

### Reproduction and evidence

Private evidence remains in `/tmp/re-map-unresolved-20261028/` and `/tmp/re-map-loop-20261028/`; no RDT, native code resource, RAM dump, BIOS or RE2 save enters Git. Both achievement integrations are disabled, game overrides are absent, memory cards are None/None, and no health/ammunition patches are enabled. The user's history stays released. Agent histories use separate private files.

1. The earlier native Waiting entry and exact native save/restore documented in RE2-DS-005 have both door slots registered and Open with the actor inactive. Its exact restored RAM SHA256 is `9622bd0f612bc390bc5f0b23c5c5981dd202b0a3509c99ee79d7ba452a8d1dd1`.
2. To exercise active allocation independently, restore the retained source 01-0c state. Copy the authentic 12-byte Waiting destination from source 01-04 door zero into the private current door and prepare the nine recorded pose fields. No story, item, key or enemy flag is changed. This is a controlled equivalent transition setup, not unmodified progression through that source door. Use the native action and wait for the real loader/initializer.
3. Capture `waiting-live-domain-entry.ram`, SHA256 `7a41e1e76793f9666102f2048925c623089076e9241e6bb6f53f6e5b4f58e874`. Loaded base is `0x8011A65C`, heap floor `0x8011E344`, free work `0x801586A0`, active actor `0x8011F8C4`, part array `0x8014833C`, count 23. Enemy 6/24 remains clear. Slots zero and one bind creators 3018 and 3050, with kind/SAT prefix `01 31 00 00`; both report Open. Only source bytes 3922 and 3936 differ inside the 3000..4404 script/table range, each changing from zero to 21 within the certified Copy targets.

`actor-native-entry-setup.json` preserves every preparation write. Native execution did not stop at the attempted GDB initialization breakpoints; those timeout attempts are excluded from instruction-level evidence. The settled allocation and source comparisons are direct emulator observations.

Separate copied-function experiments are narrower than gameplay: 1280 native opcode-34 body cases and a separately checked wrapper tail; four complete owned model CPU setup chains through relocation/allocation, excluding the full GTE-bearing opcode; eight complete sound handler calls with no stubs; and the complete null-section sound compactor with eight stack stores only. See `native-actor-write-domain.json`, `native-model2d-write-domain.json`, `native-callback-sound-domain.json`, `native-sound-relocation-null.json`, `native-callback-preservation-report.json` and `native-type22-procedure-entry-audit.json`. Rejected Unicorn branch-transition attempts are not engine failures.

The private game viewport uses black post-processing. A savestate preview thumbnail bypasses that effect in this DuckStation version. The private test container was repacked with a one-pixel black preview while preserving its compressed game payload and decompressed payload SHA256 `abd2ff70e874e089b306de92b3348fbf98ded7058d5c0e5e2b4ad0305e6d50ba`. No game screenshot is published. Header layout and thumbnail storage were checked against the exact official [save-state header](https://github.com/stenzek/duckstation/blob/00e2997958d62de79d352cd680ec0c1ad95d491c/src/core/save_state_version.h) and [writer](https://github.com/stenzek/duckstation/blob/00e2997958d62de79d352cd680ec0c1ad95d491c/src/core/system.cpp).

### Validation and contributions

The generator and reader regressions require exact revision/resource binding, conservative entry closure, owned scalar writes, single startup allocation, nonoverlapping command spans, preserved source partitions, bounded callback messages/targets/sounds, guaranteed activation and identical creators. Reader tests reverse fresh applicability, reject torn reads, and preserve current missing/inactive bindings. The full owned-CUE regeneration adds only the manifest, claim ID and immutable-door records; every prior metadata field and the floor artifact remain identical.

The private comparison contains 17 unique native RAM captures. All 13 Display results preserve items, room completion, position and visits. Eleven departed Waiting Room publications change only four raw door observations to Open, displayed as two rows; two current Waiting Room captures retain their live observations. Four UI-transition Retry results remain unchanged. Every Display result survives a separate private exploration-history close/reopen and fresh poll. See `immutable-door-replay.json`. The current-binding regressions deliberately remove the generic fixture's excluded item alternatives so they exercise the intended door paths rather than an unrelated incoherent pickup rejection.

Desktop/mobile headless rendering of the real unacquired corridor snapshot shows selected Waiting Room collected ammo, two Open door rows and no unresolved note. The current corridor remains Incomplete. The existing door-grouping browser regression also passes, preserving four wall observations, conflicts, creator reversal and zoom. Both checks report no overflow or browser errors; the README screenshot is refreshed.

The final full Python suite passes 3433 tests. Scoped Ruff formatting/lint and whitespace checks pass. Earlier failed runs exposed the malformed-null validation order, an excluded item alternative in a door-only fixture and the old departed-Unchecked expectation; all are corrected before the final pass. The private emulator is stopped after validation. Neither the user's history nor its lock file has an open holder at handoff.

Contributions, 2026-10-28: the human user reported unresolved rooms and requested the repair loop. Root and the `metadata_diagnosis`, `door_diagnosis` and `procedure_entries` agents run exact model `gpt-6.1-sol`, verified by authoritative T3 runtime metadata. Metadata authored the scalar certificate and shared door compiler; door diagnosis authored shared write partitions and audited callback/sound effects; procedure entries audited native namespaces and authored the resource binder. Root performed the active native entry, authored generator/profile/reader integration and this record, and reviewed the combined change. The same-provider door agent independently reviews the combined native proof and integration. Configured Claude Opus/Gemini Flash providers remain disabled, so no external review endorsement is claimed. Source inspection, copied native execution, native gameplay observations and synthetic regressions remain distinct.

### Follow-up: Main Hall and corridor lifetime limits, 2026-10-28

Status: Candidate source/native inspection for the same SLUS-00748 executable above. This follow-up establishes limitations of extending the Waiting Room proof. It adds no confirmed gameplay situation or production capability.

Main Hall source `PL0/RDT/ROOM2000.RDT`, size 448820 bytes, has SHA256 `7586728196fd83ec3992964746efd8d7f793fee383963e11c70951ff307fe000`. Its initially unlocked door descriptors do not retain one role throughout ordinary source execution:

| Source location | Descriptor effect and source guard |
| --- | --- |
| `17:2`, offset 10546 | Reset slot 1 to kind 5, script callback procedure 9, while bank 4 bit 70 is clear |
| `17:2`, offset 10564 | Reset slot 3 to kind 5, script callback procedure 10, while bank 4 bit 70 and bank 31 bit 17 are both clear |
| `17:6`, offsets 10768/10778 | Restore slots 1/3 to kind 1 after the earlier interaction and wait, inside checks requiring bank 11 bit 31 clear and bank 4 bit 70 set |

Native opcode 46 at `0x80055154..0x800551C4` selects the descriptor through the AOT table. It stores the new kind byte at descriptor+0, the new SAT byte with the existing four-point bit retained at descriptor+1, and three little-endian halfwords from packet+4/+6/+8 into descriptor+`0x0C` or +`0x14`. These are actual descriptor writes, not merely scheduling metadata. The Main Hall reset packets begin `46 01 05 31` and `46 03 05 31`; their later restoration packets begin `46 01 01 31` and `46 03 01 31`. Thus guaranteed startup creation and an unlocked source operand do not establish departed Open access.

The current whole-source context check first withholds a Main Hall proof at opcode 54, offset 10438. Its handler `0x800566F0..0x800567B0` calls `0x80056A38` and `0x8001C224`; advancing the task PC and returning one does not establish those callees' write domains. Main Hall also uses kinds 9/14 and nonzero section 22, outside the Waiting Room callback/sound lifetime contract. These require separate native obligations rather than an opcode whitelist.

Corridor source `PL0/RDT/ROOM2040.RDT`, size 196792 bytes and SHA256 `4816336f9147fc6179d7f39dca7e5a33ee302555091312ced2e1c1bca40afd46`, has deterministic unlocked startup creators for slots 0/1 and a null section 22. Those favorable facts do not close its remaining domains. Its current context check first withholds a proof at opcode 54, offset 7326. Its constructor set includes model `0x1F` with presets `0xC007`/`0x0000` and model `0x22` with presets `0x4510`/`0x0512`, beyond the Waiting Room's audited `0x22`/`0x4402` entry contract. The full declared constructor set also includes the separate `0x22`/`0x0502` scenario branch; this list makes no fresh-state reachability exclusion.

Startup procedure `17:0` conditionally schedules `17:20` at 7256 and `17:21` at 7302. Both scheduled procedures combine backward Goto and self-modification. Their eight opcode-1D writes are two-byte stores into FOR counts at 8990/9174, opcode-36 operands at 9064/9248, and opcode-54 operands at 9114/9120/9298/9304. Valid instruction widths alone do not prove loop termination, native frame lifetime or the affected effect parameters. Procedure `17:23` also writes kind 1/SAT `31` and six zero payload bytes into door slot 1 at 9344, then dispatches that slot at 9354. This is a destination-payload mutation, not evidence that the door closes, but it prevents reuse of an unchanged-descriptor proof. The independent [Knife entry limitation](scripted-items.md#tracker-outcomes-and-review) remains unresolved.

Reproduction uses only the owned executable, source copies and decoded command offsets under `/tmp/re-map-unresolved-20261028/`. Rebinding the existing audited entry resources succeeds, while `immutable_open_doors` returns `FixedContext` for both sources. Unsupported effects must not be admitted merely to produce Open labels; the native write, entry and descriptor-lifetime obligations remain necessary. No production history or emulator was accessed, no new gameplay test was performed, and no absence or clearance claim follows.

Contribution, 2026-10-28: Codex `door_diagnosis`, exact model `gpt-6.1-sol`, authored this source/native inspection follow-up. It preserves the authorship and runtime confirmation limits of RE2-DOOR-007 above. No external review endorsement is claimed.

### Four-point source geometry correction, 2026-11-12

Status: Candidate source and copied-handler evidence on the pinned SLUS-00748
executable above. No new emulator observation or departed-door result follows.

The shared write-partition validator incorrectly required raw four-point door
`68` and camera-volume `67` packets to carry SAT bit `0x80`. Their native
constructors add that bit themselves. SAT is an unsigned byte at source packet
offset `+3`; the little-endian MIPS source stores are at PS1 virtual addresses
`0x80054CB8` and `0x80054BC8`, respectively. Source `05-10`, door offsets 3838 and
3882, contains valid `68` packets with raw SAT `0x31`.

The validator now accepts either raw bit value for those four-point constructors
and retains their full 40-byte door and 28-byte camera packets. Ordinary `3B` and
`2C` packets still reject bit `0x80`; their native constructors preserve the raw
byte, so accepting it would mismatch their shorter payloads. Reset `46` retains
its existing geometry restriction. Slot, camera, model, source-overlap and Copy
bounds remain required.

Four new raw-SAT regression cases fail before the fix. All 354 focused partition,
scenario-entry, scenario-selection and immutable-door tests pass afterward.
Independent original-handler execution covers 96 synthetic cases across all six
ordinary/four-point AOT constructors, four SAT values, early/late acquisition
banks and acquired/unacquired states. It uses unchanged executable bytes with no
stubs, patched instructions, PC repair or memory-write hooks.

A fresh comparison of all 125 owned sources changes only neutral partition and
source-write receipts for `05-08`, `05-0b`, `05-0c`, `05-10` and `05-11`. Strict
entry, scenario guards, positive item results, lifetime/immutable-door results
and candidate-list completeness remain equal. This corrects a shared validation
barrier; it does not turn a receipt into presence, Open access or clearance.

Private reproduction scripts, original code-window hashes, full comparison and
focused-test output are retained under
`/Users/adamekka/.cache/re-map/evidence/2026-11-12-fourpoint-integration/`.
The accompanying research inputs are in
`/Users/adamekka/.cache/re-map/evidence/2026-11-12-reset-completeness-research/`.
No user history, savestate or emulator was used.

Contribution, 2026-11-12: Codex `review_partial_positive_entry` identifies the
defect and authors the private source/native controls. Root implements the
correction and regressions, independently reruns those controls, compares all
sources and writes this contribution. Both executing sessions verify exact model
`gpt-6.1-sol`, effort `xhigh`. Earlier authorship and confirmation limits remain
unchanged. Root reviews the changed predicates, native controls, failure bounds
and affected callers. Configured Claude Opus 5.5 is disabled; Gemini 3.8 Flash's
review fails to open its provider session. Neither provides an endorsement.

## RE2-DOOR-009: opted-in normal-engine door access

Status: Candidate for Resident Evil 2 Dual Shock Ver. USA Disc 1, SLUS-00748,
Leon A, Original/Normal. This extends the policy recorded above. It adds source
analysis, synthetic reader controls and copied native component execution. It
adds no gameplay confirmation, native room entry or native savestate restore.
The executable remains `SLUS_007.48`, SHA256
`e576348f64d015ecff6e1ce875a8924ee252ba7f3f9478b0917cbbdeb97db441`.
No DuckStation instance runs for this contribution. The previously tested
DuckStation version and the narrower confirmation status of RE2-DOOR-007 remain
unchanged.

The defect is departed access remaining unresolved despite stable source-owned
door alternatives. The explicit `trusted_door_policy` in the
[pinned profile](../../../profiles/re2_leon_a_slus00748.json) now authorizes a
separate [door compiler](../../../src/games/re2/door_authority.py). Its
`DoorAuthority` and `DoorAccessFact` cannot be constructed or replaced through
the public dataclass API. Item and Guard receipts grant no door rights. The
compiler consumes the actual owned binder result for all 69 resources, 125 room
sources and 54 auxiliary scripts, checks native ingress, and binds the exact
executable, semantic profile, source and decoded programs. A separately pinned
[loader](../../../src/games/re2/door_access.py) validates the complete generated
catalog before giving the reader typed access facts. Unsupported sources retain
their independent legacy rules.

The shared source/frame/write traversal has a distinct door policy. New native
opcodes cannot inherit door permission when another policy's effect set grows.
Ordinary actor/resource/render ownership uses the approved engine premise.
Signed FE/FF actor slots are bounded reserved pointers; object slots stay below
32. Actor model selectors remain in the native domain, including `0x50`/`0x51`/`0x55`.
Explicit counter/member/part selectors, task targets, call/IF/loop/switch
frames, callback replacement, Copy domains and physical aliases of all four
historical scenario/mode flags still require checks. Unknown historical flags
are never replaced by their current values.

Every reached origin competes for its slot, including non-door origins. Every
Reset kind participates in the history check. Kind-changing histories stay
unresolved. Same-kind Reset preserves route/floor/lock only when geometry and
SAT semantics remain valid. Setting geometry80 on an ordinary origin is
unsupported because a later Reset or dispatch could use the longer layout.
Semantic alternatives may differ in proven-disjoint geometry or destination
pose, as in source `05-10`, without changing access identity. Scenario-excluded
creator offsets are kept separate from accepted offsets and never receive Open
through another creator's fact.

Native source inspection uses PS1 virtual addresses, little endian. The complete
Reset leaf at `0x80055154..0x800551C8` has SHA256
`3ac89bd618207ddc7c84953e22b53de29436d99cf95566b48ba2ad5cac9b3b05`.
It writes kind/SAT bytes and three pose halfwords at descriptor+12 for ordinary
geometry or +20 for four-point geometry. Target stage/room/floor and lock bytes
at payload+8/+9/+11/+15/+16 do not overlap those first six pose bytes. Ninety
unchanged-leaf executions compare the complete two-MiB synthetic RAM against
expected stores, including kind changes and high-SAT controls. This extends the
frozen research's 54 copied-component controls; neither is gameplay evidence.

Lighting `6A`, `0x800589D4..0x80058A8C`, writes a little-endian halfword at
camera-record+16+6*light+2*component. Lighting `6B`,
`0x80058A8C..0x80058AD8`, writes at +34+2*light. Light indices are 0..2 and
6A selectors 11..13 choose components 0..2. The compiler requires every full
40-byte camera-light record to fit retained source below the section-2 work
boundary and remain disjoint from scripts and other source dependencies. Copy
can change scalar values, never these selectors. Cut_chg at `0x8005478C` masks
its high mode bit before selecting a bounded camera. Sound compaction `6C`
remains unsupported.

The complete [generated catalog](../../../data/rooms_slus00748.json) accounts
for 279 slots and 321 raw ordinary/four-point creators. It contains 114 access
facts across 56 sources, covering 124 creators. Thirteen facts are keyed, 55 are
in later stages, 110 are enabled and four are inactive. Eleven other creators
are separately scenario-excluded. The remaining 165 slots and 186 creators
retain explicit unsupported outcomes. Two conditional legacy `01-01` slots
remain independently available. These are source counts, not campaign or map
coverage percentages. No coverage cap is applied.

All residual reason classes are retained below. Counts overlap when one slot
has multiple history defects. A source's first blocker does not endorse later
commands in that source.

| Residual reason | Slots |
| --- | ---: |
| Goto receiving-frame consumer | 45 |
| Copy changes an unclosed operand domain | 32 |
| Explicit source-write footprint unclosed | 20 |
| History-dependent kind Reset | 14 |
| Sound compaction write domain | 14 |
| Goto depth escape | 14 |
| Scripted NULL dispatch | 9 |
| Competing non-door origin | 7 |
| Source/control rewrite | 5 |
| Missing switch frame | 3 |
| Native ingress binding | 2 |
| Different access target or lock | 2 |
| Callback self-replacement | 1 |
| No guaranteed startup registration | 1 |
| No reached creator | 1 |

The fresh reader uses facts only after departure and correct applicability.
Current Missing stays unresolved, Inactive stays blocked, and contradictory
live data still retries. Key bank 31 is PS1 virtual `0x800D4A34`, eight bytes;
lock bit `lock_id & 0x3F` selects a little-endian u32 at base+4*(bit//32), mask
`0x80000000 >> (bit%32)`. Every consumed applicability/key word joins the read
transaction. Clear/set/clear flags and complete earlier synthetic RAM restores
reverse access without erasing visits. Passage and inventory key possession
supply no unlock or activation knowledge. Items, clearance, pose and unvisited
reveal retain their existing rules.

Fresh read-only replay uses the parent's three copied version-94 RAM inputs,
extracted with DuckStation serializer commit
`1bc5405c417d8f8f61cc5eac624aac9f4b0677eb`. The current-only and two actually
observed source scopes have identical complete tracker results. In the separate
simulated 125-source visit scope, 124 door observations change and 11 excluded
observations disappear. Every item, clearance, pose, history and other tracker
field remains equal; only door observations and derived door summaries change.
Reverse-order replay and fresh reconstruction agree. Against the isolated implementation base `83bd4c7`, the simulated scope has
67 Unknown item rows and 37 Unknown rooms. The combined integration below
includes the separately verified positive-entry changes. Neither scope is real
exploration or a completed campaign; the `03-08` identity gap is unchanged.

Access and marker coverage remain separate. The parent's unchanged marker
census accounts for all 321 creators; 89 lack a shared marker, including 33 with
an access fact. Overlapping reasons are 66 projections beyond eight map units,
19 without a native opening, nine floor mismatches and four unmapped outlines.
The sole missing keyed creator, `05-0c` offset 3922, remains unsupported here.
No projection bound, outline, marker or floor-plan geometry changes.

Reproduction and precise output hashes are recorded in
[door validation](../../testing/re2.md#trusted-normal-engine-door-validation-2026-11-12).
Fresh private evidence is under
`/Users/adamekka/.cache/re-map/evidence/2026-11-12-trusted-door-implementation/`.
Frozen research hashes are verified against
`2026-11-12-trusted-door-research/sha256-manifest.json`. Original interrupted
`/tmp` evidence is not claimed as freshly verified. No DuckStation instance, user history,
save mutation or screenshot is used. Native, synthetic, retained-RAM and source
analysis remain distinct evidence categories.

Contribution, 2026-11-12: the implementation sub-agent authors this compiler,
profile/generation/reader increment, regressions, local review and record.
Authoritative executing-session turn metadata verifies exact model
`gpt-6.1-sol`, effort `xhigh`. Frozen research retains its own authorship; the
human's normal-engine decision and root's supplied RAM extraction/marker census
are separate inputs. Local review checks authority boundaries, explicit unsafe
paths, all creator/Reset alternatives, fresh reversal/coherence, scope isolation,
metadata generation and retained replay. Independent/external review is handled
centrally by root and is not completed or endorsed by this contribution.

### Combined item/door integration, 2026-11-12

Root integrates this feature over `721b619`, preserving the separately committed
positive-entry domain and Reset-candidate fixes. One exact-type binding encoder
now serves the separate authorities; its actual 69-resource/125-source native
digest remains `727c49593f3d756594049140e357d8c4c6f47aefdb215d7fd6d0a0a79ed670a8`.
The shared structured walker has an explicit door role and immutable fixed-check
outcomes. Existing Strict/FreshPositive behavior and the positive domain's
startup-slot restrictions remain unchanged. Door-only effects and source-write
permissions grant no item, Guard or strict-entry right. Door catalogs compile
against raw Reset records before candidate-origin enrichment.

The source operation list now reuses `FLAG_WRITE_OPERATIONS`: clear `0`, set `1`
and toggle `7`. The isolated feature's duplicate list incorrectly admitted the
native no-op `2` and rejected toggle `7`. All owned writes use `0` or `1`, so the
correction changes no catalog fact. New controls admit non-fixed toggles and
reject physical aliases of fixed bits. Eleven integration regressions also
cover fixed-predicate pruning, policy isolation, embedded versus standalone
Sleep helpers, explicit startup slots and exact-type binding.

The actual combined compiler retains every accepted fact, creator and exclusion
from the isolated feature. Three residual records in `04-09` and `05-17` now
report `goto_depth_escape`: the shared walker encounters an active frame before
the wrapper's post-Goto receiver scan. All three remain unsupported. The table
above records the resulting 45 receiving-frame and 14 depth-escape slots;
the isolated output recorded 48 and 11 respectively. These diagnostic changes
grant no additional authority.

The full semantic profile, including both Reset and door opt-ins, hashes to
`56e298cb85f90912b2de29b130113465c6215a4c5346ddf11ee532e2121c9564`.
Actual compilation of all 125 sources produces catalog digest
`d56467299a229dd733508b8dc85c3fbbd398195305e7fdf5e90e6e25a1f31cde`.
The mandatory loader accepts this exact union rather than treating either old
profile or catalog as a compatibility fallback.

Root's fresh copied-RAM comparison checks 15 publications against `721b619`.
Every item, completion, pose and visit field agrees. Current-only and the two
actually observed sources have entirely equal tracker results. Each of six
simulated 125-source publications changes exactly 124 door observations and
removes exactly 11 excluded observations; only derived door summaries also
change. The combined simulated scope has 67 Unknown item rows and 35 Unknown
rooms. Forward/reverse order and fresh reconstruction agree. This is offline
reader evidence, not gameplay or native restoration.

Independent combined reader review checks Reset/door interactions, current
kind-two repurposing with changed GID, departure/reentry, complete synthetic RAM
reversal, fresh reconstruction, hidden targets, malformed catalogs and atomic
payload/acquisition failures. It passes 507 keyed-observation controls, all
eleven exclusions and 23 focused regressions. Synthetic all-source polling uses
60 memory requests with either policy; processing medians are 2.87 ms without
catalogs and 3.75 ms combined, excluding emulator/GDB latency. Evidence is under
`2026-11-12-trusted-door-reader-review/combined/` in the private evidence cache.

Contribution: root resolves the shared-policy/binding integration, fixes the
flag-operation defect, authors the integration regressions and writes this
record. `review_trusted_door_reader` independently reviews the combined reader.
Both executing sessions verify exact model `gpt-6.1-sol`, effort `xhigh`.
Claude Opus 5.5 remains disabled. A fresh Gemini 3.8 Flash review fails to open
its provider session; neither supplies an endorsement.

`review_partial_positive_entry` independently checks the final shared migration:
3,922 Strict/FreshPositive program walks, 375 existing source-policy queries
and all 125 default source-write results agree with `721b619`. Its 26 focused
regressions, 13 fixture controls, clean import orders and exact pins pass.
It independently verifies both Goto failure-order changes. The reviewer reports
no supported findings and verifies executing model `gpt-6.1-sol`, effort `xhigh`.
Its scope excludes full generations and saved-RAM replay, which root performs.
Root's full suite passes 7,492 tests; the final 1,351-test focused run, 558 local
documentation links, scoped lint/formatting and whitespace checks pass. Two
complete generations agree byte for byte and preserve every pre-existing item
field and every floor byte. Final private artifacts are under
`2026-11-12-trusted-door-integration/`; the independent shared-code review is in
`2026-11-12-trusted-door-integration-final-review/`.

## RE2-DOOR-010: unchanged neutral entries admit six additional doors

Status: Candidate for Resident Evil 2 Dual Shock Ver. USA Disc 1, SLUS-00748,
Leon A, Original/Normal. This is owned-source/native inspection and offline
reader validation, without new gameplay or native savestate restoration.
The executable remains SHA256
`e576348f64d015ecff6e1ce875a8924ee252ba7f3f9478b0917cbbdeb97db441`.
No DuckStation version is newly tested. The three read-only copied version94
RAM inputs retain the extraction provenance recorded in RE2-DOOR-009.

The exact clean implementation base is
`67614582e65d1c71a05f94eeb004e22bc0daeea0`. The unsealed November12
`door-goto-entry-research` proposal identified seven formerly Goto-blocked slots
already admitted by the unchanged `SourceEntryPolicy.Existing` analysis. This
increment seals that analysis separately for doors. It adds no broader stage-A
traversal, Member_cmp, atomic-token, retained-IF Goto, source/effect/Copy opcode
permission or geometry change.

| Source | Slot | Creator byte offset | Target stage/room/floor |
| --- | --- | --- | --- |
| `00-1b` | 0 | 2282 | `00-1a`, 0 |
| `00-1b` | 1 | 2314 | `00-03`, 3 |
| `01-04` | 0 | 6366 | `01-01`, 0 |
| `01-04` | 1 | 6398 | `01-05`, 0 |
| `02-08` | 0 | 2450 | `01-1b`, 0 |
| `02-08` | 1 | 2482 | `02-00`, 0 |

All six have enabled SAT low mask `0x31`, activation floor zero and no key lock.
The seventh slot, `01-04/2`, creator 6430, retains a competing non-door origin.
Across all 125 sources, facts increase 114→120, covered creators 124→130 and
unsupported slots 165→159. Eleven excluded creators remain excluded. The other
122 source results, every previous fact and every exclusion are unchanged.
The seventh slot's diagnostic becomes `competing_non_door_origin`; no unsupported
slot gains partial authority. Items and room clearance gain no authority.
Marker coverage stays 242/321, with 79 raw creators missing markers. Five added
facts already have markers; `02-08:2450` does not. Accepted-access creators
without markers increase 31→32. No marker or geometry is invented.

The mandatory public door factory derives a separate compiler-owned exact-type
binding from the complete 69-resource/125-source/54-auxiliary tuple, executable,
semantic profile and fresh raw source decode. The shared typed binding digest
remains `727c49593f3d756594049140e357d8c4c6f47aefdb215d7fd6d0a0a79ed670a8`.
Positive domains, Guard/filtering/registration receipts, raw JSON and matching
receipt mirrors cannot construct or replace the binding. The existing neutral
source and full auxiliary consumer analyses keep their inputs, outputs and
permissions. Failed neutral analysis remains explicit and retains the existing
door receiving-frame restriction. There is no retry through broader semantics.

All ordinary producers contribute their actual task/depth roots, including
unentered EventExec and every kind 5 creator/Reset alternative. Phase zero stays
within tasks 0..9; selectors 10 and above mean ordinary AUTO 2..9. Gosub preserves
task and adds depth. Both domains use the existing native-control arithmetic
and structured walker. Existing call/return, foreign-cell, yield, Break and
four-frame restrictions remain unchanged. The full auxiliary Copy/writer proof
is rerun, retaining 126 Break consumers at offset `0x60` and 51 escaped writers:
47 numeric task 13+`0xA4` cases and four task 13+`0x84` cases with no task 13 entry.
No sampled inactive flag replaces those obligations.

The whole-executable direct JAL census reproduces the eight installer callers
at PS1 virtual addresses `0x80013E28`, `0x800519A8`, `0x8005322C`, `0x800535E0`,
`0x80053600`, `0x800536A4`, `0x8005388C`, `0x800538C4`. Pinned native windows
bind installer/initialization, kind 5 dispatch, IF/ELSE/ENDIF, CMP,
Goto/Gosub/Return/Break and ordinary dispatch. The actual IF/CMP native graphs
close without a cooperative yield. These are normal-engine source contracts,
not a claim excluding arbitrary computed calls or corrupted execution.
Native task fields use u32LE IF targets and Break reads, full mask `0xFFFFFFFF`,
within task records of width `0x174`; the shared canonical/escaped IF bases remain
`0xC0`/`0x4C0` with depth stride `0x20`. Source creator/Copy locations are byte
offsets, never host or PS1 virtual addresses.

The explicit door policy moves to `slus00748-trusted-normal-door-access-v2` with
entry audit `slus00748-existing-neutral-door-entry-v1`. Including that field in
the complete semantic profile changes its pin from
`561e1a35af80fabb58887271476861ab9322f2e5c1525c3b52806bc2520b699c` to
`907c37e906f12eee11a67cbd2da25679d7b753dc23d90fff872a832f855cbf23`.
Both door and independent identity-filtering profile pins are refreshed. No
semantic field is omitted and no legacy pin is accepted. The corrected raw
source/item/competing-door/Reset identity catalog binding is unchanged.
The complete door catalog pin becomes
`a16d04fadbde5ea55d1e8be0b81d5f6fab53dcf4ff47526d04b957ae532423af`;
the mandatory reader continues to reject changed facts, gaps or exclusions.

Reproduction, checked artifact hashes, failed test-harness assumptions and
reader/publication consequences are recorded in
[door-entry validation](../../testing/re2.md#six-row-door-entry-validation).
Private durable evidence is under
`~/.cache/re-map/evidence/2026-11-12-door-entry-six-implementation/`.
The original unsealed research and its authorship remain untouched. Its
broader 34-row proposal remains separate and unimplemented.

Contribution, 2026-11-12: the implementation agent authors the bounded binding,
regressions, measurements, local review and this record. Matching executing
session/turn metadata verifies exact model `gpt-6.1-sol`, effort `xhigh`.
The human supplied the normal-engine trust decision; earlier research and the
parent's copied-RAM evidence are separate inputs. Local review checks exact
factory ownership, full source/native/auxiliary binding, unchanged grant domains,
all catalog consequences, fresh reader reversal and publication preservation.
Independent/external review and integration remain with the parent; this
contribution supplies no external endorsement or gameplay confirmation.

Parent review and verification, 2026-11-12: root and two independent reviewers, all separately verified executing model `gpt-6.1-sol`, effort `xhigh`, inspect the bounded feature. `review_door_entry_core` checks the actual owned69/125/54 binding, native installer phases, eight callers, task/frame arithmetic, all54 auxiliary writer/consumer obligations and unchanged Existing source/control roles. Its43 focused tests pass, including all125 catalogs and7,844 prior walks. `review_door_entry_consumers` checks generator/loader/profile pins, fourteen metadata rejection probes, six focused tests and a fresh fifteen-publication replay. Nine actual/current publications stay equal; six simulated publications change six door observations and two derived door summaries only. Raw descriptors, item/clearance state, pose, visits, read metrics and README bytes remain unchanged. Neither reviewer returns a verified actionable finding. Their durable reports are under `2026-11-12-door-entry-core-independent-review/` and `2026-11-12-door-entry-consumer-review/`.

Root adds a why comment for the delayed policy import that avoids a module-initialization cycle; the complete Python AST is unchanged. The final owned-CUE43-test run passes in14.87seconds, with scoped Ruff/formatting on all9 changed Python files, local documentation links and whitespace checks. The retained7,858 full-suite and1,392 focused implementation results, two identical complete generations and browser/README checks apply to the same executable semantics. Configured Claude Opus5.5 is disabled; the fresh Gemini3.8Flash high review fails to open its provider session. Neither supplies an external endorsement. Exact reviewed file hashes, AST check, external failure and integration evidence are retained in `2026-11-12-door-entry-six-integration/`. These checks add no native gameplay or restoration observation.

Main-checkout integration, 2026-11-12: all385 selected door-entry, trusted-door and profile tests pass in30.53seconds. Root compares every non-door field in all125 sources, preserves every prior fact and exclusion, and reproduces exactly the six new facts. Both complete generated room/floor pairs match main byte-for-byte. All fifteen fresh main publications and read plans equal the reviewed implementation result. Rebuilding the README fixture from the same three verified copied RAM inputs is byte-identical, as are the existing PNG and floor catalog. The private `root-main-comparison.json` and `root-main-focused.txt` record these final checks. Items, clearance, pose and visits remain outside this new authority.

## RE2-DOOR-011: bounded native FF/FF door frames

Status: Candidate for Resident Evil 2 Dual Shock Ver., USA Disc 1, SLUS-00748,
Leon A, Original/Normal. This contribution uses owned-source inspection,
unchanged copied native handlers and offline reader replay. No game emulator,
game input, native room entry, native savestate restoration or memory-card test
is performed. The earlier DuckStation observations retain their named limits.
The exact clean implementation base is `2c69c06e6f3a580fcc1012046675ba20bd07788d`.
Executable `SLUS_007.48` retains SHA256
`e576348f64d015ecff6e1ce875a8924ee252ba7f3f9478b0917cbbdeb97db441`;
the complete 69-resource/125-source/54-auxiliary binding retains
`727c49593f3d756594049140e357d8c4c6f47aefdb215d7fd6d0a0a79ed670a8`.

The unsealed stage-A proposal on `55d0c8e` is remeasured against this base before
use. Fifteen public factory/catalog regressions fail on the base. The new
explicit `NativeDoors` role in the one shared structured-control walk admits
28 further facts and one scenario exclusion. All prior facts and exclusions
survive. The total becomes 148 facts covering 158 creators, 12 excluded creators
and 131 unsupported slots. No item, clearance, effect, opcode, Copy, geometry or
registration permission is added.

| Source | Additional creator byte offsets |
| --- | --- |
| `00-04` | 2994 |
| `00-08` | 6446, 6478 |
| `00-0a` | 6602, 6634, 6666, 6698 |
| `00-11` | 8158, 8190 |
| `01-06` | 5334 |
| `01-0f` | 5938, 5970, 6002 |
| `01-12` | 1986, 2018 |
| `01-13` | 3714 |
| `02-07` | 4178, 4210, 4242 |
| `02-0b` | 2902, 2934, 2966, 3030 |
| `03-08` | 10174, 10206 |
| `05-04` | 8112 |
| `05-05` | 6578 |
| `05-15` | 11158 |

Source `04-05` additionally excludes creator 2996. Its remaining slot retains
both target ambiguity and a history-dependent kind Reset. The other diagnostic
changes expose callback self-replacement in `01-0b`/`03-0a` and unregistered
scripted dispatch in `05-0c`. They grant no facts. `02-04` retains its non-FF
IF-level Goto gap. Foreign Member_cmp, SET-before-check tokens, retained-level
Goto and switch/call reconvergence beyond this bounded contract remain outside
this increment. The full 131-slot residual and every old/new diagnostic are
retained with the validation evidence.

### Native cells and source ownership

The compiler seals the actual full owned tuple, semantic profile, fresh raw
decode, every program, NormalDoors source-write witness, producer, call/replacement
edge, task/depth, initialization, receiving field and auxiliary proof. An
unsupported field analysis grants no new receiving right; the previous narrow
door path retains its own checks. Positive, identity, Guard and registration
capabilities cannot construct or substitute this binding.

Ordinary roots remain `16:0/task0`, `17:0/task1` and refresh `17:1/task0`.
Every EventExec and kind-5 creator/Reset alternative contributes, including
unentered producers. Ordinary selectors >=10 mean AUTO tasks 2..9. Gosub adds
its actual depth; admitted EventNext preserves task/depth and still fails in a
positive-depth chain. Programs without a producer gain no native entry or store,
while all their source and Copy operands remain protected.

FF/FF Goto may abandon logical IF/loop frames and target any decoded command
boundary in its program. It computes the foreign IF pointer. Each foreign IF
failure consumes its own immediately preceding nonyielding CK/CMP store.
SET, a yield, a call, an actor predicate or an older store grants no such right.
The logical IF frame carries the actual store-cell provenance. END/Return
reconstruct the canonical pointer from the signed saved IF byte; they cannot
make a foreign target into a canonical value. The stale IF/call/return/predicate
counterexample remains rejected. Break restores the saved IF byte and leaves
the IF pointer unchanged. Copied native execution rejects the implementation's
initial contrary Break hypothesis; the failed run is retained.

All native locations below are PS1 virtual addresses. Fields are task-relative,
little endian; RDT targets are source byte offsets, never host addresses.
The single [native arithmetic implementation](../../../src/games/re2/native_control.py)
serves both the new receiving facts and the unchanged neutral disjointness test.

| Field | Task-relative byte offset | Width/mask |
| --- | --- | --- |
| Task records | base `0x800D7860`, stride `0x174` | 14 normal/auxiliary records |
| IF/loop level | `4+depth` / `8+depth` | u8, `0xFF`; signed when natively consumed |
| Saved loop IF | `0x0C+4*depth+loop` | u8, `0xFF` |
| Loop start/end | `0x20+16*depth+4*loop` / `0x60+16*depth+4*loop` | u32, `0xFFFFFFFF` |
| FOR count | `0xA0+8*depth+2*loop` | u16, `0xFFFF` |
| Canonical IF store | `0xC0+32*depth+4*level` | u32, `0xFFFFFFFF` |
| FF Goto next IF store | `0x4C0+32*depth` | u32, `0xFFFFFFFF` |
| Current IF pointer / return PC | `0x140` / `0x144+4*depth` | u32, `0xFFFFFFFF` |

Native pins cover the eight installer callers, phase/root installers, ordinary
failed-predicate dispatcher, IF/ELSE/ENDIF, CK, CMP and its seven-target switch,
FOR/WHILE/DO/NEXT/SWITCH, Goto/Gosub/END/Return and Break. The full auxiliary
Copy/writer/phase closure stays mandatory: 126 Break reads at `0x60`, 51 escaped
IF writes, 47 numeric task13+`0xA4` cases and four task13+`0x84` cases with no
task13 entry. Neither inactive flags nor zero counters are assumed. WHILE reads
that overlap an escaped writer require an uninterrupted bound predicate; retained
Break reads cannot overlap. FOR counts 0, 1, `7FFF`, `8000`, `FFFF` retain both
conservative continuations and establish no loop progress.

The policy is `slus00748-trusted-normal-door-access-v3`, with entry audit
`slus00748-bounded-ff-native-door-entry-v2`. The full semantic profile pin is
`c7d775403b9790c2e0f0704e214fdeea58a6024a968f1cdf65df7ea0ce1668f1`;
the exact catalog pin is
`41d4e5d42ff4bff81d17ec6ca8d7c57063bd66bd4d2d7bb3160f8ff80de435ea`.
The independent identity authority changes its complete-profile pin only. Its
raw source/item/competing-door/Reset catalog pin remains intact. Original four-role
walks, Existing neutral analyses and 750 Strict/Guard/default-positive/positive/
identity queries preserve their semantic outputs. No old pin alias is accepted.

### Reader and map consequences

All 15 fresh publications use only the three authorized read-only copied RAMs.
Current-only results agree exactly. In the observed-two-source scope, the two
`03-08` door observations improve only when that source is departed. In the
simulated 125-source scope, 26 observations improve with `03-08` current and
28 with `03-0a` current; creator `04-05:2996` disappears separately. Only derived
door summaries also change. Items, completion, pose, visits and read request/byte
counts remain equal through forward/reverse replay and fresh reconstruction.
That implementation replay uses only the two current-source observations,
`03-08`/`03-0a`. The parent integration below separately restores the existing
persisted exploration. Simulated visits and compiler counts establish no native
gameplay or campaign readiness.

Marker coverage stays 242/321 creators in the production shared-door layout,
with 79 missing. Twenty new access facts have markers and eight do not; accepted
creators without markers increase 32 to 40. The raw floor/geometry bytes remain
unchanged. The observed-source README fixture and rendered PNG also remain
byte-identical after rebuilding from the real copied-RAM reader.

[Reproduction and checks](../../testing/re2.md#bounded-native-door-frame-validation)
record complete generation, catalog, query, native and publication artifacts.
Durable private evidence is under
`~/.cache/re-map/evidence/2026-11-12-door-ff-frame-implementation/`.
The original unsealed research, authorship, rejected broader probes and initial
implementation/test failures remain preserved separately.

Contribution, 2026-11-12: the implementation agent, verified exact model
`gpt-6.1-sol`, effort `xhigh`, authors this increment, experiments, regressions,
local review and record. T3 executing-thread metadata is retained with the
artifacts. The human supplies the engine-trust decision; the earlier research
and copied-RAM captures retain their original authorship. Local review checks
factory sealing, shared frame/cell arithmetic, producer/auxiliary/Copy closure,
all catalog and legacy-domain consequences, fresh reader reversal and map
preservation. Independent/external review and integration remain with the parent.
No external endorsement or new runtime confirmation is claimed.

Parent integration and review, 2026-11-12: root combines this increment with
the already verified A0 pickup feature on `7f42f9fb4ad00972939ba464fbe004c7261475b0`.
The combined semantic profile is
`b99e92bdcae309071943317038fab9ef4d39088020c424bfac16736688a15e7f`,
and the complete door catalog is
`803d1a124481d117321dcb357eaa71ccc07c0c74d373b4d167fc9e03f4083b96`.
Two complete generations agree byte-for-byte. Every non-door metadata field,
including both pickup additions, and all floor bytes match that parent.
The frame, entry and neutral-domain ASTs equal the independently reviewed
implementation; the native helper additionally retains the separate A0 constant.

Root restores only the private copy of the existing 68-source, 71-region
exploration, then rereads the three copied RAM images in both orders. Across
six publications, 22 or 24 door observations change, depending on the current
source. Door observations become 95 Open, one Blocked and 85 Unchecked; rooms
with incomplete door coverage decrease from 44 or 45 to 35. All item, clearance,
pose, visit, region and read-plan fields remain equal. The four Unknown item
rows and seven Unknown rooms remain unresolved. No visit is added. These are
offline results for persisted exploration, not new gameplay observations.

Two independent reviewers, each verified as `gpt-6.1-sol`, effort `xhigh`,
report no findings in the bounded core and consumer scopes. The core reviewer
checks native frame arithmetic, producer/auxiliary closure, sealing and legacy
roles, and reruns 609 focused tests including 335 copied-native component cases.
The consumer reviewer checks all catalog consequences, five metadata mutations,
two contradictory exclusion controls, 43 focused tests and fresh replay,
including the private persisted exploration. Root reviews the final combined
diff and corrects the original two-source replay wording above. Configured
Claude Opus 5.5 is disabled; Gemini 3.8 Flash high fails to open its provider
session. Neither supplies an external endorsement.

The final combined checkout passes 8,394 Python tests with explicit owned CUE,
Ruff and formatting for all 14 changed Python files, documentation links and
whitespace checks. All 15 copied-RAM publications preserve non-door results;
the real README fixture reproduces byte-identically and its image is unchanged.
Root authors this integration contribution as verified `gpt-6.1-sol`, effort
`xhigh`. Exact comparisons, commands, review limits and hashes are retained in
`~/.cache/re-map/evidence/2026-11-12-ff-a0-integration/`.
