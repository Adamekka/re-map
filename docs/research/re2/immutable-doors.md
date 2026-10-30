# RE2 immutable door bindings

[Claim index](../../research.md) · [RE2 testing](../../testing/re2.md)

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
