# RE1 map controls, facing and door symbols

[Documentation index](../../README.md) · [Claim index](../../research.md)

## RE1-PLAYER-001: player position and facing next to health

Status: Superseded for the direct-facing interpretation by RE1-PLAYER-002; position observations remain Candidate
Scope: SLUS-00551 Training Jill, live GDB plus input
Environment: windowed DuckStation 0.1-11894 dev on 2026-09-25, agent driven with keyboard and screenshots
Authored: 2026-09-25; agent/tool: opencode; model: opencode/muse-spark-1.3-contributor-free
Basis: runtime observation, walk versus turn separation
Claim: the player struct sits by health at 0xC51AC. X is 0xC5158, Z is 0xC5160, facing is 0xC5148, with mirror copies at 0xC5190, 0xC5194, and nearby. Walk-only movers versus turn-only movers separate cleanly across three paused dumps. Facing decreases on left turn. The GameHacking position codes at 0xA4BE4 do not move and are rejected for this revision. A door in room 09 at box 23400,800,2000,1700 does not open by pushing or by action, likely locked or keyed. Vision loop of move plus screencapture plus read works and ends blind driving.
Evidence: tools/split_walk_turn.py walk-only and turn-only lists, live reads during steering, screenshots jill.png through jill12.png in /tmp, kept out of git.
Limits: axis signs and facing units uncalibrated, door lock state unknown, no combat tested per the zombie warning so a pre-door savestate stays the rule.
History:
- 2026-09-25; opencode with model opencode/muse-spark-1.3-contributor-free; authored; live driving only, still Candidate.

## RE1-MAP-018: door markers share the floor layout's stage identity

Status: Candidate; reproduced display defect from recorded tracker publications and checked in Chromium. No new gameplay or unlock experiment.

Game: Resident Evil Director's Cut USA, SLUS-00551, pinned executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`. No emulator was started for these UI checks.

The user's October 15 tracker log reports `00-0a → 00-19` and `01-0b → 01-0c` as `LOCKED`, labeled Helmet Key. Their wall markers were gray because the destination outlines list only `05-19` and `06-0c`, respectively. Raw room equality in the browser rejected both observations. Floor selection already normalizes stages modulo the catalog's explicit `stage_modulus`, five, as recorded in RE1-MAP-004. Wall matching now uses the same identity rule, while directional source selection and game-derived door verdicts retain their original runtime IDs.

Reproduce with `bun tests/check_map_browser.mjs <python>`: the Helmet Key test state reveals only Back Passage and Lesson Room Entry, supplies the recorded locked targets, and checks red wall markers on both floors. Synthetic locked/open/locked updates check that the marker refreshes without revealing either destination. Existing checks retain directional selection, floor browsing and interrupted-state clearing. Boundary markers without a destination remain unassigned. This fixes display association and does not change lock decoding, establish a natural unlock, or confirm other revisions.

Contributions:
- 2026-10-15; human user; reported gray Helmet Key doors at Lesson Room Entry and Back Passage.
- 2026-10-15; Codex root, `gpt-6.1-sol`; inspected log publications and catalog identities, implemented shared stage normalization for marker matching and added browser regressions. README screenshot uses the recorded explored state, with no emulator interaction or visit-history writes.

## RE1-MAP-019: retain native interior map geometry

Status: Candidate; numeric source extraction and browser checks, no new gameplay.

Game and executable identity are unchanged from RE1-MAP-018. Read the owner's pinned disc with `tools/build_floor_plans.py`; no emulator was started. The existing parser already includes CLUT index `14 + 6*region` in floor membership but discarded its distinction from the main floor shade when constructing outline unions. This loses the stair treads/rails visible in both Main Halls and East/West Stairways, along with other interior features.

Preserve contiguous horizontal runs of that shade as numeric center-line segments, owned by each outlined region. Square-ended strokes retain singleton runs. The generated catalog adds 388 segments across eleven plans and 118 outlines. Removing only the new `detail_segments` properties from the regenerated document reproduces the entire preceding catalog exactly. No palette colors or texture files are exported. Browser rendering uses original neutral strokes and reveals details only with their entered room. Current-room/completion styles must not override the detail stroke.

Reproduce extraction with `python3 tools/build_floor_plans.py <owned-cue> <output>`. Run `python3 -m pytest -q tests/test_floor_plan.py tests/test_multi_area_maps.py` for a synthetic floor whose stair shading disappears in an outline union, singleton geometry, and malformed/missing detail records. The browser check verifies interior geometry and its stroke on all 118 outlined rooms, alongside the existing glyph-within-outline checks. These source/UI checks do not establish additional runtime map coverage or stairs' gameplay accessibility.

Contributions:
- 2026-10-15; human user; reported missing stair indications.
- 2026-10-15; Codex root, `gpt-6.1-sol`; inspected native numeric shade runs, extended extraction and catalog validation, regenerated geometry from the owned disc and added extraction/browser regressions. No guest-memory, emulator, or exploration-history changes.

## RE1-PLAYER-002: live yaw and a directional room marker

Status: Confirmed for the named SLUS-00551 Jill captures in Chemical Storage and Winding Passage; floor-wide compass alignment remains Candidate outside those rooms and the static door comparisons.

Game: Resident Evil Director's Cut USA, SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`. Runtime: isolated official DuckStation `0.1-12083-g00e299795 (dev)`, Python 3.14.8, the committed Chemical-before and Herb-before savestates, ordinary keyboard turns/walking. Both `[Achievements] Enabled=false` and `[Cheevos] Enabled=false` were explicit before the successful validation loads, with no account or per-game overrides. No cheats or guest-memory writes. A first setup attempt reached the wizard and is not gameplay evidence.

The actual yaw is the little-endian u16 at PS1 virtual `0x800C5198`, RAM offset `0xC5198`. Rotation uses mask `0x0FFF`, 4,096 units per turn. The observed component at `0x800C5148` is not a direct angle: its signed 16-bit values follow a sine-shaped component and cannot distinguish all headings. This supersedes that part of RE1-PLAYER-001, preserving its original authorship and observations. For motion validation only, X at PS1 virtual `0x800C5158` and Z at `0x800C5160` were read as signed little-endian 32-bit values, with all bits retained. These position reads are not new production tracking fields.

Pinned executable inspection: the door transition at `0x8002A660..0x8002A668` copies its arrival angle into `0x800C5198`; turn code `0x8003EC18..0x8003EC70` increments/decrements that same halfword. `0x800376EC..0x80037718` passes actor field `+0x74` to the yaw matrix, and the trig routines at `0x8006CBDC` and `0x8006D0FC` mask inputs to twelve bits. Runtime forward motion follows `(cos(yaw), -sin(yaw))` in world X/Z. Floor-plan door comparisons put +X right and +Z up, so an SVG arrow drawn pointing up rotates by `(90 + (yaw & 0xFFF) * 360 / 4096) % 360` degrees. Source comparisons cover door vectors across the existing plans; geometry distortion and an ambiguous Guardhouse pair prevent treating them as universal runtime confirmation.

Observed sequence:

| Capture | Room | Yaw | X | Z | Result |
| --- | --- | ---: | ---: | ---: | --- |
| `chemical-start` | `00-18` | 1480 | 4171 | 3072 | Start from the donated fixture |
| `chemical-forward-a` | `00-18` | 1480 | 3373 | 3072 | Negative-X motion; wall constrains Z |
| `chemical-left` | `00-18` | 520 | 3373 | 3072 | Left turn decreases yaw |
| `chemical-forward-b` | `00-18` | 520 | 4294 | 3072 | Positive-X motion; Z remains constrained |
| `chemical-left-b` | `00-18` | 2792 | 4294 | 3072 | Left turn wraps through zero |
| `chemical-forward-c` | `00-18` | 2792 | 3808 | 4111 | Both-axis motion matches yaw within 0.46 degrees |
| `winding-start` | `00-09` | 1352 | 23850 | 4649 | Independent room and fixture |
| `winding-left-b` | `00-09` | 3624 | 23850 | 4649 | Left turn wraps; initial shorter input produced no change and is not counted as a successful turn |
| `winding-forward` | `00-09` | 3624 | 24543 | 5260 | Both-axis motion matches yaw within 0.09 degrees |
| `winding-restored` | `00-09` | 1352 | 23850 | 4649 | Restore the same earlier fixture; published heading reverses from 48.515625 to 208.828125 degrees |
| `winding-right` | `00-09` | 2312 | 23850 | 4649 | Right turn increases yaw |

Private numeric observations and capture/publish helpers are in `/tmp/re-map-arrow-test/`. `observations.jsonl` SHA256 is `3847f098452d09c27d3429f303a19f7db3349d9950c6c773b3875fc8d2d97460`; restored `published-state.json` SHA256 is `d6c4a0731621fa2a924f6d8ce0df85f6f0a7dc053f06725b83d851f50b4b32f5`. Each capture verifies the running executable signatures. The README screenshot uses that fresh restored publication with an isolated copy of the existing two-region visit history. The user's history stayed byte-identical, SHA256 `d66fe942858e3c3c1bd00a5c7e321ae418cff8b3cee140822456a2c2399dbb94`. The isolated emulator was closed afterward.

Production polls require the revision's facing address, read the latest heading once before the final room/lifecycle checks, and reject failed/short reads before publishing visits or heading. They do not require a stationary character. Heading is reread after loads and is not persisted in exploration history. The room-level arrow has a fixed screen size, follows the current floor, disappears on an interrupted read and rotates at the tracker's 10 Hz publication rate. Exact within-room X/Z placement is outside this marker's implementation. Heading-only browser updates retain the room click targets and viewport. The separate key-symbol legend was removed at the user's request; the door symbols remain.

Reproduce the source/fixture/UI checks with `python3 -m pytest -q tests/test_player_heading.py tests/test_map_view.py tests/test_multi_area_maps.py` and `bun tests/check_map_browser.mjs <python>`. Quarter turns, high-bit masking, required startup configuration, failed/short reads, earlier-state reversal, absent legends, browser rotation, stable room controls, all 118 outlines and zoom/pan behavior are covered. These checks do not validate other revisions, exact map coordinates, other characters or whole-game gameplay.

Contributions:
- 2026-10-15; human user; requested a classic arrow rotating with Jill's actual facing and removal of the key legend.
- 2026-10-15; Codex root, `gpt-6.1-sol`; traced native yaw, superseded the earlier direct-angle candidate, performed the two-room turn/walk/restore experiment, implemented required coherent heading publication and the arrow, added regressions and updated the README screenshot.
- 2026-10-15; Codex root, `gpt-6.1-sol`; final direct review checked stage-normalized wall matching, key metadata, reveal isolation, heading-read failure handling, final camera/room/lifecycle ordering, restore reversal, stable controls during rotation and fixed arrow sizing. The final Python suite passes 1,597 tests in 80.13 seconds; browser checks pass across all 118 outlines, and scoped Ruff lint/format plus whitespace checks pass. These checks do not extend the two-room runtime scope above.
- 2026-10-15; Gemini 3.8 Flash (High), configured identifier `gemini-3.8-flash-high`, via agy conversation `3ec74445-b0dd-4023-9ebb-ba91c10511ad`; reviewed the complete final code changes, canonical numeric detail additions, heading regressions, full map renderer, poll flow and extractor. Returned no supported findings. The process exited zero with agent response DONE, terminal SUCCESS, empty stderr and no tool attempts. This is advisory code review, not gameplay validation. Private evidence: `/tmp/re-map-arrow-final-review/`; prompt SHA256 `5f364c5b860e210c611f0969cf2dfd7877c0ab05bcc0baff1f6509a393e55ff4`.
- 2026-10-15; Codex root, `gpt-6.1-sol`; Claude Opus 5.5 (High), required by the review skill, could not be consulted because agy rejects that model name. A fresh `agy models` listing offers only Claude Opus 4.6 (Thinking) in that family; no model was substituted. Earlier Gemini Pro selection was also unavailable under the preceding skill version, which has since removed Pro. The first Flash snapshot was truncated; the compact retry ended ERROR after a provider failure and supplied no accepted review. Neither failed call is an endorsement. The final successful review above covers the finished implementation. Changes were initially left uncommitted because the required Opus review was unavailable.
- 2026-10-15; human user; subsequently instructed commit and push, authorizing completion despite the unavailable Opus review.

## RE1-MAP-020: name the unresolved room color in the map legend

Status: Candidate; display-only change with served-page and browser checks, no new gameplay.

Game: Resident Evil Director's Cut USA, SLUS-00551, pinned executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`. No emulator was started for these UI checks, so no DuckStation version applies.

Rooms with `UNKNOWN` completion previously fell back to the default room fill with no legend entry, so only the side panel's `Item check incomplete` text and the `Incomplete item checks` overview explained the gray state. The page now pins that fill to an explicit `.room.UNKNOWN` rule so a future default change cannot silently merge unresolved rooms with a decided state, and the legend names it `Check incomplete` beside the red `Items remain` and blue `Cleared` entries. Completion verdicts, visit history, and item/door interpretation are unchanged.

Reproduce with `python3 -m pytest -q tests/test_map_view.py` for the served-page chip and rule assertions, and `bun tests/check_map_browser.mjs <python>` with Playwright and Chromium installed for the legend-text and single `.room.UNKNOWN` node assertions. These checks do not validate room clearance, other revisions, or whole-game gameplay.

Contributions:
- 2026-10-16; human user; selected the unresolved-legend task over the stale door-defect docs and emulator validation options.
- 2026-10-16; opencode with model opencode/muse-spark-1.3-contributor-free; authored; added the explicit rule, legend chip, served-page and browser regressions, matching README and testing wording, and refreshed the README screenshot by rendering the recorded `/tmp/re-map-arrow-test/published-state.json` publication in headless Chromium. No emulator interaction and no exploration-history reads or writes. The full suite passes 1,597 tests and the browser checks pass.

## RE1-MAP-021: matching access survives different descriptions on opposite sides

Status: Candidate; reproduced from a recorded tracker publication and checked in Chromium. No new traversal or unlock experiment.

Game: Resident Evil Director's Cut USA, SLUS-00551, pinned executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`. The user's running tracker supplied its read-only `/state` publication while Jill was in `00-0c`. No emulator connection, guest-memory writes, save loads, history writes or agent gameplay were needed; no emulator version was newly verified.

The Keeper's Room marker `03-0E` combined `00-03 → 00-0e`, `OPEN`, `Unlocked`, Sword Key, with `00-0e → 00-03`, `OPEN`, `No lock`, no key label. The Trap Room marker `09-15` combined `00-09 → 00-15`, `OPEN`, `No lock`, with its reverse direction, `OPEN`, `Unlocked`. Neither endpoint was current or selected, so both directions participated. Requiring identical labels and key labels incorrectly turned both markers gray despite unanimous open access.

Wall colors now require agreement on access state alone. A single established nonempty key identity survives a reverse side with no key label; conflicting named keys produce no emblem. Tooltips retain the distinct access descriptions. Selecting a direction still uses that side's observations. Real access conflicts remain unresolved when neither direction disambiguates them, and unassigned boundary markers remain unassigned. This changes browser association only, not game-derived lock interpretation, passage history or room completion.

Reproduce with `bun tests/check_map_browser.mjs <python>` for both reported pairs, observation-order independence, real state conflicts, conflicting keys and keyboard direction selection. `bun tests/check_re2_map_browser.mjs <python>` retains all 133 RE2 outlines and exact source-ID wall bindings. Private `/tmp/re-map-gray-door-fix/replay.mjs` renders the same recorded publication with the old and new production pages: both reported markers change from `UNCHECKED` to `OPEN`, and the Keeper's Room recovers its Sword Key symbol. Publication SHA256 `92a3b4dc8605f64f15a58b6784eea0f03ab14ceda35c25e869d978766d67fc4c`; replay result SHA256 `753732edc728dc6bfe6524297701bf37ab781d51901d1070a278ef6714482a27`. The README screenshot uses that frozen publication rendered with the fixed page. These checks do not confirm a new gameplay outcome or establish within-room player positioning.

Contributions:
- 2026-10-17; human user; reported gray Trap Room and Keeper's Room doors with screenshots.
- 2026-10-17; Codex root, `gpt-6.1-sol`; inspected the running tracker's publication, reproduced the exact old/new rendering difference, separated color agreement from descriptive/key metadata, added browser regressions and refreshed the README screenshot.
- 2026-10-17; Claude Opus 4.6 (Thinking), via agy conversation `94e6ee98-209f-4cbf-87e3-bc368b48c196`; reviewed the complete rendering change, publisher, tracker records and both browser suites. Returned no findings. Gemini 3.8 Flash (High), conversation `302abfd8-f673-481f-be85-04d6d913e6b4`, reviewed the same snapshot and identified that key identity must use all doorway observations even when access chooses one direction. Codex root, `gpt-6.1-sol`, verified that case, corrected the key lookup and added both reverse-side retention and selected-side conflict regressions. Both processes exited zero with agent response DONE, terminal SUCCESS, empty stderr and no tool attempts. These advisory reviews are not gameplay validation. Private evidence is under `/tmp/re-map-gray-door-fix/`; prompt SHA256 `3a5b3d59268e077667ba41915d2bb413d38e972adb4a64dfe3a87d03f1f72cca`.

## RE1-MAP-022: remove a key symbol after fresh unlock proof

Status: Candidate; existing fixture replay, synthetic unlock/rewind changes and browser regressions. No new key use in gameplay.

Games: Resident Evil Director's Cut USA, SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`; Resident Evil 2 USA Disc 1, SLUS-00421 Leon A, executable SHA256 `1cd618bc4390db4bd60735b0db1e91534f6134ede56fae454eb580be2aa686ef`. No emulator was opened, controlled or newly version-verified for these checks.

The user changed the earlier symbol-retention policy: a used key should disappear from its unlocked door. This supersedes the after-unlock emblem behavior recorded in RE1-MAP-021 and RE1-PLAYER-002, without changing their historical access/color findings. RE1 retains its already decoded persistent unlock fact independently of passage state; both game interpreters omit the obsolete key requirement once fresh flags prove unlocking. A temporarily disabled RE1 door or inactive/unconfirmed RE2 door remains blocked or unresolved, while its already-used key stays absent. OPEN wall observations also omit the emblem. Earlier-state flags restore the requirement and symbol. Unlock formulas and access verdicts are unchanged.

Reproduce with the existing unlock-bit and live-poll regressions in `tests/test_door_state.py`, `tests/test_live_items.py` and `tests/test_re2_tracking.py`. They cover locked → unlocked → locked, temporarily blocked passage and departed RE2 doors with fresh unlock knowledge. Both browser suites check an open door without an emblem, retained locked-door identity and symbol restoration after rewind. These are synthetic and recorded-state checks; they do not add a naturally performed unlock or normal-save persistence result.

Contributions:
- 2026-10-17; human user; requested removal of a key symbol after use.
- 2026-10-17; Codex root, `gpt-6.1-sol`; preserved independent unlock knowledge, removed obsolete key requirements, updated browser/polling regressions and refreshed the README screenshot.
- 2026-10-17; Claude Opus 4.6 (Thinking), agy conversation `711df6c2-c916-4f8a-8892-900433b37fd0`, and Gemini 3.8 Flash (High), conversation `0d0d23c2-ea17-4b61-883d-83c164405e17`; reviewed both the used-key policy and Follow player control, including fresh flag callers, explicit unlock knowledge, shared rendering and browser/polling regressions. Both returned no findings, exited zero with agent response DONE and terminal SUCCESS, and had empty stderr and no tool attempts. Codex root, `gpt-6.1-sol`, directly checked those contracts and added explicit blocked/inactive-door assertions. The final complete Python suite passes 1,650 tests; both browser suites and scoped Ruff checks pass. These reviews and checks add no gameplay validation. Private evidence is in `/tmp/re-map-keys-follow-review/`, prompt SHA256 `d102f94c7384ae680c5e4b0eebd99ed58384e836e36717521911573967da516b`.

## RE1-MAP-023: follow player explicitly resumes room selection

Status: Candidate; shared browser checks, no new gameplay.

Scope: the same pinned RE1 and RE2 profiles named in RE1-MAP-022. No emulator was started or version-verified. The former Current room action already cleared manual selection and browsing, but its label did not explain automatic following. It is now named Follow player, with a highlighted pressed state when the readable map is following the player. Selecting a room or floor turns that state off. Activating the action clears the static selection, recenters the current floor and follows subsequent room/floor entries. A panned view can still be recentered while following. An interrupted read clears the pressed state and disables the control until a coherent publication returns.

The shared browser regression checks manual selection, resuming, consecutive room changes, floor browsing, recentering and interruption. This changes the control's presentation and makes its established behavior visible; it does not change exploration or item/door interpretation.

Contributions:
- 2026-10-17; human user; requested a button to leave a static room selection and continue following entered rooms.
- 2026-10-17; Codex root, `gpt-6.1-sol`; clarified the existing action, exposed following state, added browser assertions and refreshed the README screenshot.

## RE1-MAP-024: retain the native ladder shade

Status: Candidate; pinned numeric source extraction and production-page browser checks. No new gameplay or ladder traversal.

Game: Resident Evil Director's Cut USA, SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`. This experiment did not start an RE1 emulator or verify its version. RE1-MAP-014 retains the earlier runtime traversal evidence and its separate limits.

The user reported that Room 002 lacked its ladder. RE1-MAP-019 retained shade index `14 + 6*region` for stairs, while ladders use `15 + 6*region`. Both were already part of the floor union, so the ladder shade disappeared into the room fill. Extract horizontal runs of either detail shade with the existing numeric center-line representation and square-ended renderer.

`PSX/ITEM_M2/MAP0A.TIM`, LBA 11915, 29216 bytes, SHA256 `1832969a69837396c80aab2e22de029e9aa9705bd609c272d60c90f7414bb431`, contains twelve cells of index 51 in region `06`, Room 002. Their bounds are X89..91 and Y28..32 in TIM-local cells, X right and Y down. They encode two vertical rails and two connecting rungs. Eight numeric segments preserve these cells. The same shared extraction restores twelve cells each in the Lesson Room and Falls, adding four and eight segments respectively. All other room geometry, labels, door markers and bindings remain byte-equivalent after removing the new segments and research ID. No texture or palette colors are exported.

Reproduce with `python3 tools/build_floor_plans.py <owned-cue> <output-json>` and compare with the production catalog. Run `python3 -m pytest -q tests/test_floor_plan.py tests/test_multi_area_maps.py tests/test_map_view.py` and `bun tests/check_map_browser.mjs <python>`. The focused checks cover a synthetic ladder's rails, rungs and unchanged outline, the exact Room 002 coordinates, and browser stroke hits in both singleton rails and a rung with an empty gap between them. The browser also checks that Room 002 and its ladder stay hidden before entry and validates all 118 room outlines. These are source and UI checks, not new runtime confirmation of accessibility or story state.

Private evidence is under `/tmp/re-map-re1-room002-ladder-20261022/`. The README screenshot renders a read-only publication from the existing tracker with the corrected catalog, browsed to Guardhouse 1F and Room 002. Its current room remains on B1. No exploration history, game state or running tracker process was changed. The pre-existing `docs/images/map.jpg` worktree edit is preserved separately.

Contributions:
- 2026-10-22; human user; reported the missing Room 002 ladder and corrected the game name to RE1.
- 2026-10-22; Codex root, `gpt-6.1-sol`; verified the pinned executable and native map shade, corrected shared extraction, regenerated the production catalog, added focused regressions and refreshed the README screenshot. Original extraction authorship remains in RE1-MAP-002 and RE1-MAP-019.
- 2026-10-22; returned identifier `Gemini 3.8 Flash (High)`, agy conversation `5175da4e-5da2-4c8e-a759-4a5562e57cb0`; reviewed the complete scoped textual diff, extraction/generation modules, focused and browser tests, catalog loader and relevant renderer. Returned No findings, exited zero, completed agent response DONE and terminal SUCCESS, had empty stderr and attempted no tools. Duration 134.320535 seconds; prompt SHA256 `c2eb4b37cb12ec4712c0a7ceca45e31ea60230fa672da2f141e65c72378079c1`. This prose review is not gameplay validation. The earlier `Claude Opus 4.6 (Thinking)` quota exhaustion recorded in RE2-DOOR-001 remains active and was not retried; it supplies no review of this fix. Committing remains pending the required review or a scope-specific human exception.
- 2026-10-22; human user; explicitly approved committing this Room 002 ladder fix using the completed Gemini review alone while Claude remains unavailable. This exception applies only to this fix.
