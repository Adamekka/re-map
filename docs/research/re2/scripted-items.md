# RE2 script-dispatched items

[Claim index](../../research.md) · [RE2 testing](../../testing/re2.md)

## RE2-DISPATCH-001: a live callback can grant a parked pickup

Status: Confirmed native pickup behavior in the two named situations below for Resident Evil 2 Dual Shock Ver. USA Disc 1, SLUS-00748, Leon A, Original/Normal. The bounded shared source interpretation remains Candidate outside those runtime observations. Other revisions, departed presence and campaign readiness are not established.

Executable `SLUS_007.48` has SHA256 `e576348f64d015ecff6e1ce875a8924ee252ba7f3f9478b0917cbbdeb97db441`. The reported source is `PL0/RDT/ROOM2040.RDT`, SHA256 `4816336f9147fc6179d7f39dca7e5a33ee302555091312ced2e1c1bca40afd46`. Native tests use isolated DuckStation `0.1-12083-g00e299795`, full commit `00e2997958d62de79d352cd680ec0c1ad95d491c`. Its executable identity and isolation are recorded in [RE2-CLIP-001](clipping.md#re2-clip-001-startup-clipping-preserves-the-fixed-item-context).

### Reported failure and bounded correction

In both retained user corridor images, acquisition ID 3 is uncollected. Slot four actually binds the Handgun ammo creator at source offset 6732, type 20 and quantity 15. Its SAT is zero; its rectangle is parked at 32000/32000 with size 1/1. The normal activation dispatcher therefore skips it. Treating that as unresolved presence misses the separate script delivery path.

Live slot six binds the kind-five interaction at 6776, SAT `0x31`, with canonical payload `FF 00 18 08 00 00`. Procedure eight occupies 7926..7974. One interaction can set inspection flag 5/2 and display a message. A later interaction directly invokes `Aot_on` slot four while acquisition flag 8/3 is clear. This dispatch bypasses normal SAT and rectangle eligibility.

The shared compiler proves this restricted callback behavior across all initial values of its bounded saved flags, allowing repeated completed interactions. It permits only structured single-flag IF/ELSE/ENDIF, NOP, flag writes, the audited message form, one target `Aot_on` slot and termination. Calls, loops, source mutation, other dispatch targets, acquisition writers, malformed frames, unknown effects and exhausted bounds withhold the relation. Physical word/mask comparison handles flag-bank aliases. All callback flags must lie inside explicit audited saved ranges, including callbacks without messages: changing scheduler or STOP flags can prevent continuation.

At runtime, the relation additionally requires both exact live registry bindings, the complete unchanged callback descriptor, the native main-table pointer, its exact procedure entry, the complete callback bytecode and its bounded message resources. Every read participates in the existing coherence transaction. Invalid witnesses withhold this extra presence; failed or torn reads reject publication. A proven parked item is Uncollected, while a normal active item remains Available. Coexisting live observations both contribute to identity and quantity, so a conflicting direct-dispatch observation cannot be hidden by an available alternative.

This establishes current-room presence independently of the whole-source fixed-context proof. After departure, an unacquired item returns to Unknown without carrying cached presence. Acquisition still wins from fresh game flags. No application state or save flag is invented.

### Native addresses and semantics

All addresses below are PS1 virtual, little endian. RDT offsets above are file offsets, not RAM or host addresses.

| Field or handler | Address | Width and mask |
| --- | --- | --- |
| Registry | `0x800CE558` | 32 unsigned four-byte pointers, `0xFFFFFFFF` each |
| Main SCD table pointer | `0x800D8CBC` | unsigned four bytes, `0xFFFFFFFF`; must equal loaded RDT section 17 |
| Selected item descriptor | `0x800CE5D8` | unsigned four bytes, `0xFFFFFFFF` |
| `Aot_on` handler | `0x800551C8` | unsigned byte slot operand; task PC advances by two |
| Direct kind-two handler | `0x80051884` | descriptor kind/SAT bytes, `0xFF`; payload halfwords, `0xFFFF` |
| Kind-five handler | `0x80051980` | canonical six-byte event payload |
| Task allocation / procedure entry | `0x80053138` / `0x800530EC` | unsigned procedure byte; unsigned two-byte directory offset, `0xFFFF` |
| Inspection flag 5/2 | `0x800D4874` | unsigned four bytes, mask `0x20000000` |
| Acquisition flag 8/3 | `0x800D48BC` | unsigned four bytes, mask `0x10000000` |
| Inventory base | `0x800D4A3C` | four-byte entries; type, quantity and state are bytes |
| Observed inventory entry two | `0x800D4A44` | four bytes, `00 00 00 00` to `14 0F 00 00` |

Native `Aot_on` has no slot bound check, so the compiler requires a valid registry index. It uses SAT bit `0x80` only to select payload offset 12 or 20, then dispatches by kind. The complete kind-two handler does not test SAT enablement, rectangle, distance or acquisition. It binds the selected descriptor and starts the item UI. Sixteen complete copied executions cover SAT 0/31/80/B1, parked/ordinary geometry and status seeds. Eight complete kind-five allocation controls cover ordinary task slots 2..9, auxiliary slots 10..13 and full-occupancy fallback replacement, with procedure entry and frame resets checked.

The actual main table is `0x8011BFF4`; procedure eight's unsigned two-byte entry is at source offset 6568. The live item and callback descriptors are `0x8011C0AA` and `0x8011C0D6`. Fresh hashes cover their exact source witnesses rather than assuming camera-based room identification proves immutable script bytes.

Native confirmation at `0x8007227C` reads the selected descriptor, loads its quantity at `0x8007231C`, and calls inventory addition at `0x80072320`. Ordinary type 20 reaches setter `0x8006947C`, which writes the type and quantity bytes at `0x800D4A3C + 4 * slot`. Acquisition follows at `0x8007235C`. Thus the observed `14 0F 00 00` entry establishes an actual 15-round award, independently of the source operand.

### Message lifetime and saved-word preservation

Only packet form `2B 00 <id> 00 FF FF` is admitted. `FFFF` is a STOP mask, not evidence that a message lacks choices. The handler at `0x80054A8C` advances PC by six, calls `0x8002FE38` and ORs `0xFFFF0000` into STOP at `0x800CFBDC`. Initialization sets STATUS `0x800CFBD8` bit `0x40` and writes UI work at `0x800E873C` onward.

The compiler binds the directory pair and complete text in both RDT message sections 13/14. Its bounded grammar excludes choice and external name/audio lookup branches. Runtime rereads these hashes and the relocated section pointers. This prevents a changed text resource from invalidating the flag-preservation assumption while leaving callback code unchanged.

The opt-in preserved ranges are `0x800D4874 + 8` and `0x800D48BC + 32`, complete aligned words with mask `0xFFFFFFFF`. Four complete copied message starts and 23 complete parser/render/close calls per case, using saved ranges seeded 00/FF/55/AA, preserve both ranges. The primitive linker executes 476 times per case. Complete continue-prompt formatting, queued rendering and queue reset also preserve them. No controlled stubs are used.

Other writes include STATUS bit `0x40`, STOP's saved masks, input word `0x800CE30C`, initialized graphics/UI work and native stack. The nonchoice close path at `0x800307E0..0x800307FC` clears UI work bit `0x80` and restores STOP without calling or scheduling a script. System, status, STOP, choice and inventory words do not receive blanket preservation. Initialized frame/queue pointers remain an engine precondition.

The Japanese branch is inspected and freshly bound, but no completed copied Japanese execution is claimed. Broader wrapper, Japanese and long-prompt harness attempts encounter Unicorn branch-transition exceptions. They are excluded controls, not native engine failures or endorsements. The accepted English parser and prompt workers complete independently.

#### Follow-up: final message entry bounds, 2026-10-28

The shared nonchoice parser now accepts a directory's final message without inventing a successor entry. It binds the real two-byte directory entry and consumes at most 4096 text bytes, stopping at the first valid native `FE` terminator inside the enclosing section. Non-final entries retain the original four-byte directory pair and complete padded-text witness. Both language resources remain mandatory. This source-only extension adds no runtime confirmation beyond the observations above.

The 148 focused parser/dispatch tests pass. Regenerating all 125 owned sources leaves every existing metadata field and the floor artifact unchanged; the private 18-snapshot comparison recorded in `message-final-publication-replay.json` preserves all publications and Retry results. Codex `metadata_diagnosis`, exact model `gpt-6.1-sol`, authored the extraction and terminal-entry rule. Root, the same exact verified model, reviewed the bounds, reran the focused checks and verified the unchanged generated fields. No external review endorsement is available.

### Native reproduction and restore

Private evidence is under `/tmp/re-map-loop-20261028/` and `/tmp/re-map-unresolved-20261028/`. Both achievement integrations are disabled before tests; game overrides are absent, memory cards are None/None and no health/ammunition aid is used. The renderer remains black; no game screenshot is published. The user's released history is never reopened for writes.

1. Restore the retained corridor state. Its complete RAM matches SHA256 `9bcece90b4f15af78d1f4c0c36d790f710b9c29f76bda24d06e0a58cdfe15b73`. Inspection flag 5/2 is set and acquisition 8/3 is clear. Prepare only recorded player pose fields at callback center -15784/-12344, facing 2048, and press the native action key.
2. The native selected descriptor becomes slot four's `0x8011C0AA`. Confirming the pickup changes acquisition word `00 00 01 04` to `00 00 01 14` and inventory entry two to `14 0F 00 00`. The settled capture `dispatched-corridor-collected.ram` has SHA256 `1af78319cd44f392dbf53cb06e42999801a3a29a7c57a6056a72a0620fd530df`.
3. Save an actual F2 checkpoint and restore it with F1 while paused. Its independently extracted complete RAM equals the restored image, SHA256 `85699dd8dab89481c676c24c0c8a38c0b61e0cc2adb1f2ed24962b61b55dff62`. A first unpaused restore runs extra frames and is excluded from the exact-byte comparison. This verifies DuckStation savestates, not normal memory-card persistence.
4. For the independent first-use case, restore the private Waiting Room checkpoint and use its ordinary native door into the corridor. No destination, key, story or item flag is patched. The entry has inspection 5/2 clear and acquisition 8/3 clear, SHA256 `c9cc30a9fad5f5b3bbe666114b771ad7dc8fa7d5369c32323c5661c0e3b5dd7a`. The first interaction sets the inspection flag and shows its message. Subsequent action/confirmation grants another 15 rounds and sets acquisition. The settled image is `dispatched-first-settled.ram`, SHA256 `20a7e6c31155895264f50f04ca58ee6ecd79f1e54ff4863bec972124edcdc6a6`.

`direct-pickup-native.json` records the capture sequence. `pose-writes.jsonl` records setup writes. Native handler evidence includes `native-direct-item-dispatch.py/json`, `native-callback-entry.py/json`, `native-dispatched-inventory-xrefs.asm` and `native-message-flag-preservation.json` with `native-message-closure.asm`. Raw RAM, models, BIOS and game files remain outside Git.

### Tracker outcomes and review

Owned-CUE generation emits two shared relations, `00-09` and `01-04`. Every other catalog field and the floor artifact remain unchanged. The 17-visited-source, 18-snapshot comparison changes only the current corridor's unacquired ammo from Unknown to Uncollected, quantity 15. Settled collected/restored snapshots remain Taken, other visited-source outcomes agree, and UI-transition Retry results remain unchanged. See private `dispatch-reader-all-visited.json`.

The Knife remains unresolved. Its unreferenced procedure is not excluded by a guessed entry graph; the [RE2-DS-004 follow-up](dualshock.md#follow-up-unsigned-goto-depth-audit-2026-10-28) records the control-frame lifetime gap. The corridor is Incomplete while its ammo remains, and Unknown after collection if that independent gap remains. This increment grants no room clearance and changes no exploration history.

The full Python suite passes 3154 tests, including 134 dedicated dispatch cases. Tests cover flag aliases and scheduler writes, progress and bounds, source/table/text/descriptor drift, unaudited profiles, mandatory catalog contracts, current/departed reversal, conflicting live identities and atomic short/torn reads. Scoped Ruff formatting/lint and whitespace checks pass. A native-state headless render verifies desktop/mobile Remaining ammo, Collected herb, unresolved Knife, the Incomplete room color, no overflow and no browser errors; the README image is refreshed.

A live GDB poll of the restored unacquired state reproduces Unknown before the opt-in and Uncollected afterward. Its bounded request budget changes from 66 reads/3271 bytes to 82 reads/3643 bytes, including coherence rereads. No continuous RAM scan is added. Paused-emulator timings vary with concurrent rendering and are not a sustained polling-rate benchmark. Configured Claude Opus/Gemini Flash review providers are disabled; no substitute endorsement is claimed.

Contributions and review, 2026-10-28: the human user supplied the unresolved-room report and requested the repair loop. Codex root and the `metadata_diagnosis` and `door_diagnosis` agents execute as exact model `gpt-6.1-sol`, verified by authoritative T3 runtime metadata. The metadata agent authored the shared compiler, typed capability, generator/profile/reader integration and regressions. The door agent audited complete message consumers and preserved-word bounds. Root performed both native pickup situations and exact restore, identified the message/scheduler, table, descriptor and coexisting-observation proof gaps, reviewed the final code and authored this record. The separate procedure-entry agent's control investigation retains its dated attribution in RE2-DS-004. Source/copied-code checks and native gameplay observations are distinguished above.
