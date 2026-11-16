# RE2 room-script evaluation

[Documentation index](../../README.md) · [Claim index](../../research.md) · [RE2 guide](../../re2.md)

## RE2-EVAL-001: evaluate room scripts with fresh flags to resolve departed items and doors

Status: Candidate for Resident Evil 2 Dual Shock Ver. USA Disc 1, SLUS-00748, Leon A, and Disc 2, SLUS-00756, Claire B, Original/Normal. Executable `SLUS_007.48` SHA256 `e576348f64d015ecff6e1ce875a8924ee252ba7f3f9478b0917cbbdeb97db441`; `SLUS_007.56` SHA256 `1664e7c634f8cfd03e421f10a6d7e8e8e9fa9bc7982f7c649cc86d28a983fbee`. Owned-source inspection, executable disassembly, saved-RAM replay, agreement with every existing proof and native room loads in 45 rooms from one savestate.

The human asked for RE2 tracking with no unresolved rooms, items or doors during play. The existing proofs establish departed presence and door access one bounded case at a time; on the user's actual Leon A history they left four Unknown rooms, three Unknown items and 80 departed doors marked "Door conditions unresolved". The approved [normal-engine premise](scenario-selection.md#positive-presence-policy-extension-2026-11-07) already trusts the unmodified engine to run room scripts normally. This claim applies that premise directly: interpret each room's own scripts with the flags and variables that are current now, and report what entering the room would create.

### Method

`tools/build_script_models.py` compiles every catalog source from the owned disc into a reduced program model (`data/script_models_slus00748.json`, `data/script_models_slus00756.json`). Each source must match the room catalog's SHA256. The model keeps control flow, flag and variable operations and interaction operands with their source offsets. Opcode widths come from the existing [decoder](../re2.md#re2-scd-001-bounded-leon-room-metadata-and-acquisition-contracts). Every jump target must land on a command boundary or the procedure is marked invalid.

`src/games/scd_state.py` is the game-neutral interpreter:

- The room loader runs the initializer and starts main procedure 0 (`0x800535C0` → `0x80053138`, tasks 0 and 1). The main loop (`0x800263B0` → `0x80053644`) restarts main procedure 1 on task 0 every frame. Entry therefore runs `init:0`, `main:0` and `main:1`; procedure 1 also repeats as a trigger.
- Before the scripts run, the loader (`0x80052E20`, called at `0x800535B0`) clears bank 5 bits 32-63 and bank 10, and sets variables 0-3 to -1. Variables 24 and 25 are the room's stage and room. Claire's executable has the same routine at `0x80052DF8`.
- `Cmp` compares signed 16-bit variables at `0x800D47EC` (Claire `0x800D47A4`) with ==, >, >=, <, <=, != and bit test (handler `0x80054474`, operator table `0x800111A0`). `Switch` scans its labels in order and stops at the first matching case or Default (`0x80054020`). `Save`, `Copy`, `Calc`, `Calc2`, `Member_copy` and `Sce_rnd` write variables.
- Variables 12-15 and 28-29 are written natively with no stable entry value and stay unreadable. Variable 26 (entry camera) and 27 (previous room) depend on how the player arrives. Bank 11 (`0x800E873C`) holds prompt answers and other interaction results.
- An unreadable condition forks both outcomes. Arrival and interaction conditions (actor members, facing, enemy position, trigger checks, variables 26-27, bank 11) give alternative outcomes that all exist in the room, such as different pickups on each floor of a two-level sewer room. Other unreadable conditions taint the values and interactions written under them; outcomes that differ through tainted writes stay Unknown.
- Paths in identical states merge at join points. Loops and backward jumps run at most twice and are assumed to exit, as normal waits do.
- Procedures started later, by event interactions or delayed tasks, are explored from every entry outcome. Flags and variables any room procedure writes, and the room's own acquisition flags, are unreadable there. A pickup they can create or hand over with `Aot_on` stays obtainable, including a parked zero-activation pickup ([RE2-DISPATCH-001](scripted-items.md#re2-dispatch-001-a-live-callback-can-grant-a-parked-pickup)) and a puzzle reward before the puzzle is solved.

The tracker only uses an evaluation for a row the existing proofs leave Unknown or unresolved. A pickup no creator runs for now or after any trigger is not listed. An evaluated door creator that the scripts replace with a message or event, or create with zero activation, is inactive. Alternative creators for one slot that do not run are omitted, and the map hides their markers. In the current room, a door slot that holds an event replacing the door is inactive and an empty slot has no door. Evaluations are cached per source and revalidated against every flag and variable they read, so savestate loads and story changes re-evaluate the affected rooms.

### Evidence

All 125 sources of each profile evaluate without Unsupported control flow. From a fresh-game flag state, both profiles resolve every item and door (`tests/test_re2_script_models.py`).

Three of the user's Leon A savestates, copied read-only and extracted earlier for [RE2-COVERAGE-001](coverage.md#re2-coverage-001-complete-source-inventory-exposes-remaining-tracking-gaps), replayed through the production reader:

| Scope | Before | After |
| --- | --- | --- |
| Actual history, 68 rooms | 49 Cleared, 15 Incomplete, 4 Unknown; 3 Unknown items; 80 of 181 doors unresolved | 52 Cleared, 16 Incomplete, 0 Unknown; 0 Unknown items; 0 of 156 doors unresolved |
| Simulated full catalog, 125 rooms | 73 Cleared, 22 Incomplete, 30 Unknown; 65 Unknown items; 142 of 309 doors unresolved | 80 Cleared, 45 Incomplete, 0 Unknown; 0 Unknown items; 0 of 274 doors unresolved |

The full-catalog scope is a diagnostic, not the user's exploration. The door count falls because alternative creators that do not run are no longer listed.

Agreement with existing proofs, over both distinct copied states and the full catalog: all 54 required (uncollected) items are present in the evaluation, all 20 scenario-absent items are absent, every door the proofs mark blocked is inactive and every keyed or open door is active, except 24 alternative creators for slots whose running creator the evaluation identifies. Two initial item disagreements exposed missing `Aot_on` hand-over handling, which the interpreter now models.

For the current room in the copied states, every predicted interaction matches the live registry except pickups already collected and slots changed by events the player triggered after entering.

### Native room loads

An isolated portable DuckStation copy, with achievements disabled and GDB enabled, loaded a copy of the user's Leon A resume savestate (room `03-08`). For each target room, a GDB write turned registry slot 0's door in the current room into a contact trigger (SAT `0x41`) around the player, with arrival bytes copied from a real door leading to the target and key fields cleared. After the room loaded (target stage/room, transition bit `0x02000000` clear, registry rebuilt inside the new source and stable for two polls), the registry was sampled every 0.5 s for 6 s. No health or ammunition patch was used.

45 rooms loaded, 44 of them from the user's history. Against the prediction from the pre-transition RAM, 296 slots matched exactly. 67 were pickups the save had already collected (native kind 0 with the acquisition flag set). Eight four-point creators differed only by the SAT geometry bit `0x80`, which the engine adds at load and the evaluator masks when testing activation. Several rooms created or changed slots during the first seconds after control returned; the settled samples matched the prediction. One room, `01-1a`, has only an early sample, with two predicted slots missing; it is unresolved. Every room was entered from the same flags, so each comparison covers one entry outcome. Changes later than 6 s after load were not observed. The emulator build cannot run without a visible window, so the remaining 80 rooms were not loaded natively.

### Limits

This is source interpretation under the normal-engine premise. Native code outside scripts that changes interactions or flags is not modeled. A condition the interpreter treats as arrival-dependent but which actually reflects persistent state would overstate presence. Items that only appear after a flag set in another room count as absent until that flag changes; the tracker re-evaluates them then. Entry inventory checks and poison checks stay unreadable. The original-release profiles are not configured.

Contribution, 2026-11-16: the human requested complete RE2 and RE3 tracking with no unresolved rooms, items or doors. Claude `claude-opus-5-5` designed and wrote the interpreter, compiler, executable analysis, integration, tests and this record. A Claude `claude-opus-5-5` subagent ran the native room loads; its private captures and scripts, with the audit and consistency scripts, are retained outside Git in `~/.cache/re-map/evidence/2026-11-16-re2-script-evaluation/`. No external review has been performed yet.
