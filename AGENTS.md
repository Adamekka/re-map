# AGENTS.md

## Project goal

Build an exploration and room-clear tracker for the original PlayStation versions of Resident Evil 1, Resident Evil 2, and Resident Evil 3.

The target behavior is similar to the map in Resident Evil Remake:

- Unvisited room: no visit recorded for the tracked playthrough
- Visited room with collectible items remaining: incomplete state
- Visited room with all relevant collectible items taken: cleared state
- Current room should be visually distinguishable

Keep visit history separate from completion knowledge. A visited room can have unknown item state, and being the current room does not imply that it is cleared.

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

A visited room is cleared when its relevant item list and conditions are fully understood and no normal collectible item is currently available and uncollected. An item that is confirmed absent in this scenario or unavailable until a later story event does not block clearing.

One confirmed available, uncollected item is enough to mark a visited room incomplete. If none is known to remain but item coverage or a relevant condition is unresolved, report `Unknown`. Detecting one collected item does not prove that the whole room is cleared.

Do not require these unless game data proves otherwise:

- Killing enemies
- Unlocking every door
- Triggering every cutscene
- Reading every file/document
- Solving unrelated future events
- Collecting items that only appear later in the story

Story-dependent or conditional item spawns must be handled carefully. A room must not be marked incomplete because of an item that is not currently available.

Reevaluate completion when game state changes. A cleared room can become incomplete when a new item becomes available or an earlier save or savestate is loaded.

If the game stores an "item acquired" bit or equivalent persistent flag, prefer that flag over heuristics.

## Scope order

Work in this order:

1. RE1 PS1, one exact game revision
2. RE1 map/tracker UI
3. RE1 support for additional revisions if practical
4. RE2 PS1
5. RE3 PS1
6. Optional integration inside DuckStation beyond the external memory access required for RE1
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

For each address, record its address space, such as PS1 RAM offset, PS1 virtual address, or host-process address, plus the value width, byte order, and any bit mask. Do not interchange these address spaces. Research leads with missing revision information may be recorded as candidates, but must not be treated as validated profile addresses.

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

## Tracking strategy

Build shared tracking systems for RE1 collectibles, doors, and puzzle/story availability conditions. Apply supported rules across rooms instead of implementing support as one item or puzzle at a time. Prefer extending common interpretation of game scripts and runtime state over adding named-item exceptions.

Use individual pickups, puzzles, and doors as validation cases for the shared system.

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
stage + room + character or scenario, if the tested revision requires it
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

Validate candidate flags against the expected game state after:

- Leaving and re-entering the room
- Saving and loading normally
- A DuckStation savestate reload
- Story progression where applicable

Test loads from both before and after a pickup. Loading an earlier save or savestate must restore the earlier acquisition state. A savestate restoring a value proves restore behavior, not that the value is a persistent acquisition flag; verify persistence through normal in-game saving/loading and room transitions too.

### Mapping items to rooms

Do not manually hardcode every item unless necessary.

First investigate whether room files or runtime room structures expose:

- Item ID
- Item position
- Item pickup flag/index
- Spawn condition
- Room identifier

Investigate existing RE1 room-format documentation before doing the work from scratch. Apply the same approach to RE2 and RE3 when they enter scope.

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

The player-facing map should match the useful behavior of RE2 Remake where practical, with RE1 Remake's room-clear map as the minimum:

- Draw spatial floor plans with room outlines, corridors, and door markers on walls. A graph of room nodes and connecting lines does not satisfy the map requirement.
- Track door access from game state, including locked and unlocked doors, and distinguish observed passage when useful.
- Show specific remaining items when their identity is established; otherwise a reliable remaining-item indication is acceptable.
- Resolve unknown room and door states as unfinished detection work. Do not accept pervasive unknown states as the finished product or replace them with guessed clearance.

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

Prefer showing the specific item when its identity is supported by game data. When only item presence is known, a generic remaining-item indicator is acceptable. Do not guess an item name from an unresolved spawn condition.

After the memory model is reliable, add a map.

The eventual map should make these states visually distinct:

```text
Unvisited
Visited, items remain
Cleared
Current room
Unknown
```

Reveal a room on the tracker map only after the player enters it. Do not reveal the whole area at startup or when an in-game map is collected.

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

After a game, save, or savestate change, reread game-derived state before presenting completion. Do not carry cached completion into the new state. Define and document whether external visit history follows the loaded save or records all tracker-observed visits in the playthrough before implementing persistence.

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

Label each finding with one of these validation states:

- Candidate
- Confirmed for this revision
- Confirmed across listed revisions
- Rejected, with the contradicting evidence
- Superseded, with a link to the replacement finding

Confirmation requires reproducible observations on the named game revision under the relevant checks above. Source inspection, model agreement, and model identity alone do not confirm runtime behavior. Record exactly which situations were tested and which remain untested; confirmation must not imply broader coverage.

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

Choose among test scenarios and prepare test setups autonomously when the agent can obtain equivalent validation from them. Do not ask the user to choose an emulator test setup that the agent can prepare itself.

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

### Automatic commits

Automatically commit completed, verified work for the current request without asking for separate commit approval, unless the user explicitly asks to leave it uncommitted. Inspect the final diff and run applicable checks before committing. If a required check fails or cannot run, report the blocker and leave the work uncommitted.

Stage only changes belonging to the request. Keep unrelated user changes, secrets, game files, RAM dumps, and savestates out of the commit. Split independent changes into separate commits and use concise Conventional Commit messages. Automatic commits do not authorize pushing, publishing, or rewriting existing commits.

Put the authoring model on its own line in every agent-authored commit body, for example `Model: GPT-6 Sol`. Use the model identity exposed by the runtime or explicitly confirmed by the user for the current session. Never write `Model: unknown`; if the model identity is unavailable, ask the user before committing or writing research attribution. Do not attribute another agent's contribution to the current model unless its identity is established.

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
- Research attribution and validation labels defined below

Example:

```text
## <finding ID>: <specific claim>

Status: Candidate
Scope: <game, region, serial, revision, executable identity, character/scenario>
Environment: <DuckStation version and relevant setup>
Authored: <YYYY-MM-DD>; <agent/tool>; model: <confirmed model name>
Basis: <runtime observation, source inspection, or inference; list all that apply>
Claim: <address and interpretation, or rule being investigated>
Evidence: <reproduction steps, observed results, source permalinks or local artifact references>
Limits: <untested situations, missing identity details, unresolved conditions>
History:
- <date>; <actor and confirmed model name>; <authored/reviewed/tested/revised>; <contribution and evidence>
```

This is a template, not a finding. Do not copy placeholders or illustrative values into profiles or mark them confirmed.

Do not rely on chat history as the only record of reverse-engineering findings.

### Research attribution

Give each independently verifiable claim a stable ID, such as `RE1-ROOM-001`. Reference that ID from related tests, profile documentation, and later findings so readers can trace a rule to its evidence.

For every new finding or substantive revision:

- Record the authoring agent/tool and exact model identifier when the runtime exposes it or the user explicitly confirms it for the current session. Record reasoning effort only when explicitly known. Never write `model unknown`; ask the user if the identity is unavailable. Do not infer a model from writing style, the app name, or a requested model selection alone.
- Keep original authorship and append dated contributions to the history. Distinguish writing, reviewing, running an experiment, and changing a conclusion. Record human contributions as human, and identify an external source separately from the model summarizing it.
- Attribute reviews to the models that actually returned them and state what each review checked. A model reviewing prose has not reproduced the experiment. Record failed or unavailable reviews as such, never as endorsements.
- Attach evidence to each claim. For source inspection, include the URL and commit or version plus the relevant location. For experiments, include steps, expected and observed results, environment, and artifact references or hashes where available. Keep restricted artifacts out of Git under the repository hygiene rules below.
- Preserve rejected hypotheses and conflicting observations with their attribution. Mark superseded claims explicitly and link their replacements rather than silently overwriting their history. Split entries when their claims have different authors, evidence, or validation states.

Model labels describe provenance, not a quality ranking. Later agents must judge findings by reproducibility, direct evidence, revision coverage, and unresolved limitations. A more capable model must still verify a claim before promoting its validation state.

For existing notes without verified attribution, preserve the recorded provenance and ask the user before adding a model label. Do not retroactively claim authorship or verification.

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
   - Incomplete, cleared, or unknown state under the completion rules above
   - Whether the room's full relevant item list has been established
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
