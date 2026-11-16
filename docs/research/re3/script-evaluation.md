# RE3 tracking and room-script evaluation

[Claim index](../../research.md) · [RE3 guide](../../re3.md)

## RE3-EVAL-001: evaluate RE3 room scripts with fresh flags for a runnable tracker

Status: Candidate for Resident Evil 3: Nemesis, USA, SLUS-00923, Hard; executable `SLUS_009.23` SHA256 `2e143418e358b2c99995cdc1a88c387163fb751912c723b755614f38e236bd29`. Executable disassembly, owned-source compilation and retained-RAM replay. No new emulator session was run for this claim.

The human asked for RE3 tracking with no unresolved rooms, items or doors. This claim adds the runnable profile `profiles/re3_jill_hard_slus00923.json`. It reuses the shared interpreter from [RE2-EVAL-001](../re2/script-evaluation.md#re2-eval-001-evaluate-room-scripts-with-fresh-flags-to-resolve-departed-items-and-doors), the guarded current-room reader from [RE3-LIVE-001](live-reader.md#re3-live-001-bounded-hard-current-room-and-pose-observations), and the [floor plans](floor-plans.md).

### Engine facts used

- RE3 rooms have one procedure directory, RDT section 16. Room load (`0x80052A94`, called at `0x80049790`) starts procedure 0 on task 1. The main loop (`0x80023B90` → `0x80052B18`) restarts procedure 1 on task 0 every frame unless bank 2's `0x02000000` stop bit is set. Entry runs `main:0` then `main:1`; procedure 1 also repeats as a trigger.
- Before scripts run, `0x80052294` sets variables 0-3 at `0x800D1F46` to -1 and clears bank 4 bits 32-63 (`0x800D1FC4`) and bank 44 (`0x800CCBAC`, 16 bytes). Variables 24 and 25 are the room's stage and room.
- The flag bank table at `0x8009E3F8` has 50 entries; banks 48 (`0x800D25AC`) and 49 (`0x800D1F30`) hold random item placement and other state. Flags are MSB-first words.
- Opcode widths come from each handler's script-pointer advance (handler table `0x8009E0F8`). `Ck` is `0x4C`, `Set` `0x4D`, `Cmp` `0x4E` (handler `0x800547F0`, operator table `0x80010B78`, same seven operators as RE2). `Save`, `Copy`, `Calc`, `Calc2` and `Member_copy` are `0x1E`, `0x1F`, `0x20`, `0x21` and `0x42`. `Work_copy` (`0x1D`, handler `0x800538E0`) patches later operands exactly as in RE2.
- Arrival-dependent predicates: actor member comparison `0x43` and the player-control check `0x27`. Game-state predicates: inventory searches `0x36` and `0x6B`, table test `0x35` and system-flag test `0x6C`. These were classified from their handlers and from every predicate that follows an `If` in the 169 owned sources.
- Variable 30 is a random value rerolled at room load and every frame (`0x800523C4`). Rooms with random item placement roll it once on first entry and store the result in bank 47/48 flags, so placement is determined after the first visit to either room of a pair.

### Tracker

`tools/track.py --profile profiles/re3_jill_hard_slus00923.json --disc <owned CUE> --map` loads the 169 owned room sources from the disc at startup. Each poll admits ordinary Hard gameplay through the guarded reader, reads the flag and interaction blocks, rechecks the room, then evaluates every visited room. The current room's live registry decides items and doors present now; acquisition flags (bank 7 before stage 2, then bank 8) and key flags (bank 9, `key_id & 0x3F`) are read fresh. Split rooms select their map part by world position bounds.

### Evidence

All 169 sources compile and evaluate without Unsupported control flow. Every `Work_copy` target is a predicate operand, a non-item Reset's data, a loop count or an unmodeled command. Six retained gameplay captures of room `00-0d` publish the current room, its door and a position inside the outline. With every room treated as visited and those early-game flags, unresolved items come only from random placements not yet rolled; a visited room has rolled.

### Limits

No native room loads were compared for RE3, and the retained captures cover one room. Native code outside scripts is not modeled. Stage 6 and 7 rooms may belong to Mercenaries. Unit-count item types and prompt-answer banks are not yet identified, so quantities show as recorded and prompt answers count as game state.

Contribution, 2026-11-16: requested by the human. Claude `claude-opus-5-5` wrote the RE3 opcode set, engine analysis, tracker integration, tests and this record. A `claude-opus-5-5` subagent derived the opcode width table and the floor plans. No external review has been performed yet.
