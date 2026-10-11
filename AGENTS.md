# AGENTS.md

## Scope

- Build a tracker for the user's personal RE1 PS1 playthrough in DuckStation. Support Jill on one exact game revision.
- DuckStation savestates are the required restore mechanism. Chris and normal memory-card save/load are outside the current scope.
- The user has finished RE1 Remake and knows the broad progression. Deliver a useful tracker and fix problems encountered during play. Exhaustive coverage and a full campaign completed by an agent are not acceptance requirements.
- Add RE2 and RE3 later as separate game profiles, after RE1 has a repeatable solution.
- Prefer an external tracker reading emulator memory without changing the original game files. Investigate existing debugging facilities before maintaining a DuckStation fork.

## Map behavior

- Use RE2 Remake's map behavior where practical, with RE1 Remake's room-clear map as the minimum. Draw spatial floor plans, room outlines, corridors and door markers on walls. A graph of room nodes does not satisfy this requirement.
- Reveal rooms only after the player enters them. Startup and collecting an in-game map must not reveal unexplored rooms.
- Show room names directly on explored map outlines.
- Let the player browse explored floors without revealing unvisited rooms. Follow the current floor by default and provide a control to return to the current room.
- Keep visit history separate from completion. Visually distinguish the current room, incomplete, cleared and unresolved states. Being current or visited does not imply clearance.
- Track locked and unlocked doors from game state. Keep observed passage separate from unlock knowledge.
- Show specific remaining items when their identity is established. A reliable generic collectible indicator is acceptable when only presence is known.
- Provide a grouped overview of remaining items in explored rooms, with room navigation and separate incomplete item checks.
- Use original visuals or simple geometry derived from legally accessible game data. Do not copy Remake assets.

## Room completion

- Mark a visited room incomplete if at least one relevant collectible is currently available and uncollected.
- Mark it cleared only when the full relevant item list and conditions are resolved and no collectible is currently available and uncollected.
- Otherwise report `Unknown`. Resolve gaps affecting the user's playthrough; never replace uncertainty with guessed clearance.
- Distinguish available, collected, absent in this scenario, dormant and unresolved items. Items absent in Jill's scenario or unavailable until a later event do not block clearance.
- Enemy kills, every door unlock, files, cutscenes and unrelated future puzzles are not clearance requirements unless game data proves otherwise.
- Reevaluate completion when items or story conditions change. A cleared room can become incomplete again.

## Tracking design

- Separate emulator access, game interpretation, generic tracking and UI. Keep addresses and game-specific rules in revision profiles.
- Build shared interpretation for collectibles, doors and puzzle/story conditions across rooms. Use individual cases to validate it; avoid accumulating named-item exceptions.
- Prefer game acquisition flags over visual detection or transient object lists. Generate room/item metadata from owned game data when practical.
- Handle failed or incoherent memory reads explicitly. A successful read alone does not establish valid game state.
- After a game or savestate change, reread item, door and story state before displaying results. Earlier savestates must reverse acquisition and access state; do not carry cached completion forward.
- Persist exploration across tracker sessions. Visits accumulate throughout the playthrough, including after earlier savestate loads. Isolate histories by game, revision and playthrough identity; reread game-derived item and door states.
- Poll roughly 10 to 30 Hz unless evidence calls for another rate. Avoid continuous full-RAM scans once stable addresses are known.

## Research and validation

- Reproduce reported failures using logs and savestates, then verify fixes with focused regressions. Prepare equivalent test setups autonomously; ask for manual gameplay only when necessary, with precise steps.
- Before extending script interpretation, identify the tracking failure or correctness defect it addresses. Reconsider experiments that show no improvement; revisit rejected approaches only with new evidence or changed conditions and compare against the same baseline.
- Measure progress by resolved item/door outcomes, map coverage and gameplay observations. Keep offline source coverage separate from runtime coverage. Commit, test and opcode counts do not establish playthrough readiness.
- Validate relevant rules through controlled before/after observations, room reentry, story changes and earlier/later savestate loads. Savestate restoration alone does not prove memory-card persistence.
- Keep reproducible findings in `docs/research.md` with stable claim IDs referenced by related tests and profiles. Record game title, region, serial, disc/revision, executable identity when available and tested DuckStation version.
- For each address, record address space, value width, byte order and bit mask. Do not interchange PS1 RAM offsets, virtual addresses and host-process addresses or generalize across revisions without testing.
- Label findings Candidate, Confirmed for the named revision or listed revisions, Rejected, or Superseded. Confirmation requires reproducible runtime observations in multiple independent situations. Source inspection and model agreement do not confirm gameplay behavior.
- Record reproduction steps, expected/observed results, evidence references and tested/untested limits. Cite source inspection by URL, commit or version and relevant location. Preserve conflicting evidence and rejected hypotheses; link replacements for superseded findings.
- Preserve original research authorship and append dated contributions distinguishing writing, review, experiments and changed conclusions. Identify human contributions and external sources separately. Record exact verified model identifiers for authoring and returned reviews; ask if unavailable, never write `model unknown` or retroactively guess attribution.
- Record what each review checked. Failed or unavailable reviews are not endorsements, and a prose review is not runtime validation.

## Emulator testing

- Use a separate exploration history for agent tests so test visits do not reveal rooms in the user's playthrough.
- Verify RetroAchievements are disabled before loading any game or save in an agent test instance.
- Temporary infinite-health and infinite-ammunition patches are allowed for agent testing. Record enabled patches with the validation evidence.

## Repository hygiene

- Do not commit or distribute BIOS files, disc images, standalone copyrighted assets, credentials or unrelated user saves.
- Keep selected RE1 savestates and memory-card saves in Git as reproducibility fixtures, with provenance, checksums and emulator compatibility. Keep raw RAM dumps out of Git.

## Documentation

- Update the README screenshot whenever the UI changes.

## Commits

Automatically commit completed, verified work for the current request unless the user asks to leave it uncommitted. Inspect the final diff and run applicable checks first. If a required check fails or cannot run, report the blocker and leave the work uncommitted. Stage only the request's changes. This does not authorize pushing, publishing or rewriting history.
