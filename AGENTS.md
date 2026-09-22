# AGENTS.md

## Project goal

Build an exploration and room-clear tracker for the original PlayStation versions of Resident Evil 1, Resident Evil 2, and Resident Evil 3.

The target behavior is similar to the map in Resident Evil Remake:

- Unvisited room: unknown/unvisited state
- Visited room with collectible items remaining: incomplete state
- Visited room with all relevant collectible items taken: cleared state
- Current room should be visually distinguishable

The first target is **Resident Evil 1 on PS1 running in DuckStation**. Do not try to support all three games at once.

The preferred first implementation is an **external real-time tracker/overlay that reads emulator memory**. Do not modify the original game's map screen unless there is a strong technical reason to do so.

Once RE1 works reliably, design the code so RE2 and RE3 can be added as separate game profiles.

## Primary objective

Produce a working proof of concept that can:

1. Detect the current RE1 room.
2. Detect when the player enters a room for the first time.
3. Determine which collectible items belong to that room.
4. Determine which of those items have already been collected.
5. Mark the room as incomplete or cleared.
6. Update this state in real time while the game runs in DuckStation.
7. Persist only data that is not already reliably stored in the game's own state.

The first proof of concept does not need a polished graphical map. A debug UI like this is enough:

```text
Current room: 0x??
Visited: yes
Items: 3
Collected: 2
State: INCOMPLETE
```

Do not spend time polishing the UI until room identification and item-state detection are reliable.

## Definition of "cleared"

A room is cleared when all normal collectible items assigned to that room have been collected.

Do not require these unless game data proves otherwise:

- Killing enemies
- Unlocking every door
- Triggering every cutscene
- Reading every file/document
- Solving unrelated future events
- Collecting items that only appear later in the story

Story-dependent or conditional item spawns must be handled carefully. A room must not be marked incomplete because of an item that is not currently available.

If the game stores an "item acquired" bit or equivalent persistent flag, prefer that flag over heuristics.

## Scope order

Work in this order:

1. RE1 PS1, one exact game revision
2. RE1 map/tracker UI
3. RE1 support for additional revisions if practical
4. RE2 PS1
5. RE3 PS1
6. Optional DuckStation integration
7. Optional native modification of the in-game map

Do not begin RE2 or RE3 until RE1 has a repeatable solution.

## Game version handling

Never assume RAM addresses are universal.

Before adding memory addresses, identify and record:

- Game title
- Region
- Disc/revision
- Serial number
- Executable identity if available
- DuckStation version used during testing

Keep addresses and game-specific logic in a profile instead of scattering constants through the code.

Example:

```text
profiles/
    re1_ntsc_u.json
    re1_pal.json
    re2_ntsc_u_leon_disc1.json
```

## Architecture

Keep emulator access, game-specific memory interpretation, and UI separate.

A reasonable structure is:

```text
src/
    emulator/
        duckstation_memory.*
    games/
        game_profile.*
        re1/
            re1_profile.*
            room_state.*
            item_state.*
        re2/
        re3/
    tracker/
        exploration_state.*
    ui/
        debug_view.*
        map_view.*
```

RE1-specific addresses and logic must not leak into the generic tracker.

Use abstractions similar to:

```text
GameProfile
    detectGame()
    currentRoom()
    enumerateCurrentRoomItems()
    isItemCollected()
    isItemCurrentlyAvailable()

Tracker
    update()
    roomState()
```

Names and implementation details may differ.

## Preferred implementation strategy

Start outside DuckStation.

An external process is preferred for the first prototype because it allows faster iteration and avoids maintaining an emulator fork.

Investigate these approaches:

- Existing DuckStation debugging/memory facilities
- Emulator process-memory inspection
- A supported scripting/debug API if one exists
- A small DuckStation change that exposes required RAM through IPC
- Existing tooling such as EmuHook

Prefer documented and maintainable access over brittle process-memory scanning.

Do not commit to a DuckStation fork until the simplest external approach has been investigated.

## Reverse-engineering workflow

Treat reverse engineering as an experiment. Record evidence for every important address or flag.

### Finding the current room

Use controlled state comparisons:

1. Save state in room A.
2. Dump relevant RAM.
3. Move to adjacent room B.
4. Dump RAM again.
5. Compare changes.
6. Repeat between several known rooms.
7. Identify candidate room/stage identifiers.
8. Verify candidates by moving through many rooms.

Do not accept an address because it works in only two rooms.

The final room identity may require multiple values, such as:

```text
stage + room + scenario
```

### Finding item-collected flags

Use controlled before/after comparisons:

1. Save immediately before picking up one item.
2. Dump RAM or create a savestate.
3. Pick up only that item.
4. Dump again.
5. Compare.
6. Restore the earlier state.
7. Repeat with other items.
8. Determine whether the game uses a bitfield, byte array, script flag, object state, or another mechanism.

Prefer persistent game flags over scanning the active room object list.

Validate that candidate flags survive:

- Leaving and re-entering the room
- Saving and loading normally
- A DuckStation savestate reload
- Story progression where applicable

### Mapping items to rooms

Do not manually hardcode every item unless necessary.

First investigate whether room files or runtime room structures expose:

- Item ID
- Item position
- Item pickup flag/index
- Spawn condition
- Room identifier

For RE2 and RE3, investigate existing RDT reverse-engineering documentation before doing the work from scratch.

If static room data can be parsed, generate the room/item database from game data rather than maintaining it by hand.

## Research references

Investigate these before reinventing existing work:

- DuckStation source and debugger
  - https://github.com/stenzek/duckstation

- EmuHook
  - https://github.com/elModo7/EmuHook
  - Pay attention to the author's PSX Resident Evil 1 real-time map work.

- R3 Auto Map Gen
  - https://github.com/themitosan/R3-Auto-Map-Gen
  - It targets classic Resident Evil PC versions, but its room-mapping approach may still be useful.

- reevengi-tools and existing RDT format research
  - Search specifically for RE1, RE2, and RE3 RDT/event/item structures.

Treat third-party documentation as a lead, not ground truth. Verify important assumptions against the target game revision.

## Savestate analysis

DuckStation savestates may help with controlled comparisons, but do not assume their serialized bytes correspond directly to PS1 RAM.

If necessary:

1. Determine whether DuckStation compresses or transforms RAM in savestates.
2. Prefer emulator-exposed RAM when possible.
3. Build a small extraction tool only if savestate analysis materially helps the project.

Create scripts for repetitive diffing instead of comparing large dumps manually.

Useful tooling should support:

```text
dump A vs dump B
changed bytes
changed bits
stable changes across repeated experiments
candidate address filtering
```

## Data model

Represent room state explicitly.

For example:

```text
enum class RoomCompletion {
    Unvisited,
    Incomplete,
    Cleared,
    Unknown
};
```

`Unknown` matters. If the tracker cannot prove whether a room is cleared, it must not silently claim that it is cleared.

For each item, keep enough information to explain why the tracker thinks it exists and whether it has been collected.

Example:

```text
RoomItem {
    roomId
    itemId
    acquiredFlag
    spawnCondition
}
```

Avoid visual detection when memory/state data is available.

## Conditional items

Resident Evil games can change rooms based on character, scenario, story state, puzzle progress, and other flags.

The tracker must distinguish between:

- Item exists and is collectible now
- Item has already been collected
- Item does not exist in this scenario
- Item may appear later
- Item state is unknown

Do not mark a room incomplete for an item that the player cannot currently obtain.

When unsure, report `Unknown` during development rather than inventing a rule.

## UI

Start with a developer/debug UI.

Show:

- Detected game/profile
- Current room ID
- Current stage/area if applicable
- Visited state
- Items detected
- Item acquisition state
- Calculated room completion state
- Unresolved/unknown conditions

After the memory model is reliable, add a map.

The eventual map should make these states visually distinct:

```text
Unvisited
Visited, items remain
Cleared
Current room
Unknown
```

Do not copy Resident Evil Remake assets. Create original map visuals or derive simple geometry from legally accessible game data.

## Persistence

Prefer the game's own persistent flags whenever possible.

The tracker may need its own persistence for information that the original game does not store, such as whether the external tracker has ever observed a room.

External save data must include enough game identity to avoid mixing:

- RE1 and RE2
- Different regions
- Different scenarios
- Different save files when that distinction matters

Avoid storing a second copy of data that can be reconstructed from game RAM.

## Testing

Every discovered address or rule needs a reproducible test.

At minimum test:

- Fresh game
- Entering an unvisited room
- Leaving and returning
- Picking up one of several items
- Picking up the last item
- Saving/loading
- DuckStation savestate load
- Story-driven item changes
- Character/scenario differences where applicable

For a room with three items, verify:

```text
0/3 -> incomplete
1/3 -> incomplete
2/3 -> incomplete
3/3 -> cleared
```

Then leave and return and confirm the state remains cleared.

Maintain a small test log with:

```text
game revision
room
action
expected state
observed state
RAM addresses involved
notes
```

## Validation standard

Do not call a memory address "known" until it has been tested in multiple independent situations.

Label findings as one of:

- Candidate
- Confirmed for this revision
- Confirmed across listed revisions

Never generalize an address from one region/revision to another without testing.

## Agent behavior

Work autonomously where possible.

When blocked, first:

1. Inspect the repository and existing tooling.
2. Search existing documentation and source code.
3. Build a small experiment.
4. Use before/after memory comparisons.
5. Record the result.

Ask the user to perform manual gameplay steps only when the agent cannot obtain the required runtime state itself.

When requesting a user test, make it precise. Example:

```text
Load this savestate.
Stand in the dining room.
Do not pick up anything.
Create RAM dump A.
Pick up only the Ink Ribbon.
Create RAM dump B.
```

Avoid vague requests such as "test whether it works."

## Progress notes

Keep a `docs/research.md` file.

Record:

- Confirmed addresses
- Candidate addresses
- Meaning of each field
- Game revision
- How each claim was verified
- Failed hypotheses
- Useful external references

Example:

```text
## RE1 NTSC-U

Current room candidate
Address: 0xXXXXXXXX
Status: confirmed for tested revision

Evidence:
- Dining room -> value 0x04
- Main hall -> value 0x00
- East hallway -> value 0x07
- Stable across reloads
```

Do not rely on chat history as the only record of reverse-engineering findings.

## Code quality

Keep experimental code small and disposable until the memory model is understood.

Once an address or structure is confirmed:

- Give it a descriptive name
- Move it into the correct game profile
- Document the evidence
- Add a regression test if practical

Avoid:

- Giant hardcoded switch statements
- Magic numbers outside profile/data files
- Global mutable state
- UI code reading emulator memory directly
- Assuming successful reads are valid data

Memory reads can fail. Handle that explicitly.

## Performance

This tracker does not need per-frame heavy processing.

Polling at roughly 10 to 30 Hz should be enough for room/item tracking unless testing proves otherwise.

Do not continuously scan all PS1 RAM once stable addresses are known.

## Legal and repository hygiene

Do not commit or distribute:

- PS1 BIOS files
- Resident Evil disc images
- Copyrighted game assets
- User save files unless intentionally provided as test fixtures and safe to include

Keep generated RAM dumps and savestates out of version control unless explicitly approved.

Prefer hashes, offsets, metadata, parsers, and original code.

## First milestone

For one exact RE1 PS1 revision in DuckStation:

1. Reliably detect the current room.
2. Detect at least one pickup flag.
3. Associate that pickup with its room.
4. Display:
   - Current room
   - Item collected/not collected
   - Incomplete/cleared state
5. Document how the addresses were discovered.
6. Verify the result after leaving and re-entering the room.

Do not build the full map before this milestone works.

## Second milestone

Expand the RE1 implementation to:

- Multiple rooms
- Multiple items per room
- Conditional items
- Visited-room tracking
- A basic visual map
- Reliable save/load behavior

Only after this milestone should the project consider RE2.

## Success condition

The RE1 implementation is successful when a player can play normally in DuckStation and the tracker reliably answers:

```text
Have I already been in this room?
Is there still a collectible item available here?
Have I cleared this room?
```

without requiring manual bookkeeping and without modifying the original game files.
