# RE1 map validation

[Documentation index](../README.md) · [Testing index](../testing.md)

## Running the live tracker

For shell-only emulator setup, see [Starting DuckStation from a terminal](../duckstation-startup.md).

The current playthrough target is Jill using DuckStation savestates. Chris support and normal in-game memory-card save/load are outside the delivery requirements. Existing normal-save experiments below remain evidence, but are not completion gates.

This tracker is for personal use. A complete playthrough by an agent and exhaustive coverage are not required before using it. Play with the tracker, report mismatches, and use logs or savestates for targeted diagnosis and fixes. The validation limits below describe the available evidence.

Use DuckStation with the tested RE1 Director's Cut USA disc, SLUS-00551. Enable its GDB server on port 2345, then boot the game and load a playable room.

From the repository directory:

```sh
python3 tools/track.py --map
```

Open http://127.0.0.1:8765 and leave the terminal running. Stop with Ctrl+C.

The tracker automatically switches among eleven floor plans across the Mansion, Courtyard, Guardhouse and Laboratory. Rooms reveal only when the tracker observes entry. Collecting an in-game map does not reveal extra rooms. Red rooms have available items remaining, blue rooms are cleared, gray rooms need a further item check, and the white outline and cyan arrow mark the current room. The arrow follows Jill's facing direction and marks room identity rather than exact position within the room. Select an explored room to see its items and directional door locks. Wall symbols identify named key types independently of locked/open access. Sword, Armor, Shield and Helmet use distinct emblems; other named keys use a key silhouette with their exact label in the tooltip and door list. Locks with no established key identity have no emblem. Exploration resumes across tracker restarts and remains revealed after earlier savestate loads. Item and door states are rebuilt from the loaded game, not stored verdicts.

The Floor selector lists explored floors and the current floor. Selecting a floor keeps that view while gameplay continues. Current room returns to the player's outline and resumes automatic floor switching. Browsed rooms use the same fresh item and door results as the live floor. During an unreadable game state, controls are disabled and item/door verdicts are cleared until a coherent poll returns.

Remaining items groups confirmed available pickups by explored floor and room. Clicking an entry selects its room and keeps browsing that floor; Current room resumes following. Incomplete item checks lists rooms with incomplete item coverage, including red rooms with known remaining pickups. Several camera outlines for one logical room produce one entry. The overview includes observed outlines and the current room's details, including a current unoutlined or unmapped room. Earlier unoutlined visits have no stored map region and are outside the overview when no longer current. Interrupted tracking clears both lists until a fresh poll returns.

Run `bun tests/check_map_browser.mjs <python-executable>` with Playwright and Chromium installed for browser regressions. The check generates explicit test states through the production map publisher and exercises the real page in headless Chromium. It covers browsing across area changes, follow mode, the remaining-items overview, keyboard navigation, partial item coverage, fresh departed-room item/door states, acquisition reversal, interrupted tracking, new history, unoutlined rooms and camera aliases. It also checks the room marker, retained stair geometry, key emblems and initial/returned-Mansion wall matching. These are UI checks, not new gameplay validation.

Use `python3 tools/track.py --map --new-playthrough` to begin a fresh exploration history. Use `--history-file <path>` to keep a separate playthrough. The default `.local/visit-history.json` stays outside Git and contains only room/region visits and game/playthrough identity. Corrupt, mismatched or unwritable histories report an error instead of silently resetting. Only coherent gameplay polls save visits, and interrupted writes preserve the previous file.

Persistence checks run with `python3 -m pytest -q tests/test_visit_history.py`. They cover restart, camera-dependent outlines, unoutlined visits, reconstruction of a departed room, earlier item/door flag reversal, invalid history, atomic-write failure, concurrent writers and CLI gameplay gating. These use synthetic visits and existing donated captured states; they do not claim a new live emulator run.

Camera-dependent spaces reveal separately from their parent room. Their item/completion state still belongs to the underlying logical room, so several outlines can share one item list. The original map has no colored polygon for the Mansion elevator, heliport, Courtyard laboratory elevator and two Laboratory elevators. The tracker retains their room details and native floor selection without adding an invented outline. Door wall matching uses the catalog stage modulus, so initial and returned-Mansion doors share their floor geometry. RE1-MAP-018 covers the reported Helmet Key display failures. Seven boundary door markers have no encoded destination; they remain unassigned on the map while known exit access stays available in the door list.

Coverage status 2026-10-09: RE1-MAP-014/015/016/017 add Guardhouse B1, Laboratory B2/B1, Laboratory B4 and Mansion B1 entry checks, so all eleven floor plans now have scoped live entry coverage. The per-route "covers N of eleven" statements below record the state when each route was tested and are kept as history. None of these routes validates new pickups (except the Power Room Battery in RE1-MAP-016), story conditions beyond the recorded flags, unlocks, or normal-save persistence unless the entry says so.

Multi-area checks run with `python3 -m pytest -q tests/test_multi_area_maps.py tests/test_floor_plan.py tests/test_map_view.py`. They cover native floor/camera boundaries, every supported source room's binding, cross-floor reveal isolation, map acquisition, camera coherence, malformed catalog data, owned marker encodings and HTTP delivery. These are synthetic and captured-state regressions. RE1-MAP-004/005/006 record the source evidence and checks. RE1-MAP-007 adds a captured Storeroom-to-East-Stairway transition; its attempted floor test did not complete. RE1-MAP-008 completes a natural Main Hall 1F → 2F → 1F → 2F run, verifies entry-only outlines, retained visits, supported items and doors, and replays all nine new captures with exact live publication equality. RE1-MAP-009 adds native map-menu comparisons in both Main Halls, unchanged tracker publication while viewing those maps, and an exact seven-capture replay.

RE1-SAVE-005 and RE1-MAP-012/013 add normal public-card loads and nine rooms across Laboratory B3, Courtyard B1, Guardhouse 1F and Courtyard 1F. The natural Guardhouse → Courtyard → Guardhouse route checks area switching and retained visits. RE1-SOURCE-003 fixes a reproduced Guardhouse source rejection caused by native 32-bit event relocation; its regression command is `python3 -m pytest -q tests/test_room_cache.py tests/test_tracking_rules.py`. At that point scoped live checks covered six of eleven floor plans (see the coverage status note above for the current state). Mansion B1, Guardhouse B1 and Laboratory B1/B2/B4 were still untested in gameplay at that point. Native map-screen comparisons outside the Mansion remain untested, and these later-area entries do not validate new pickups or story conditions. Keep RetroAchievements disabled before loading any test game or checkpoint.

The tracker gates visit recording on the lifecycle byte at PS1 virtual `0x800C866C` (RE1-LIFECYCLE-002). Title, boot, and attract-mode demo states read `0x00` there, and polls in those states report non-gameplay without recording visits; tested Jill gameplay reads `0x07`. The tracker can stay running through title and demo playback, and `tools/track.py --once` exits 1 in those states. Only the `0x00` value suppresses visits, so untested gameplay phases stay fail-open. Jill's in-gameplay menus, cutscenes, door-transition transients, and death/game-over behavior remain unvalidated. Demo visits recorded by builds before this gate are excluded from reported gameplay coverage.

To compare against RE1's own map with the isolated test copy's keyboard bindings, press Enter for the status menu, move up twice from the first inventory slot to Map, confirm with K, then confirm the selected floor with K. The tracker should keep only its observed rooms, even when the native map displays rooms visited before tracking began. In the recorded Main Hall checks, it kept regions `06` and `07` on 1F and region `03` on 2F; items and doors also stayed unchanged. L and Enter return to gameplay.

Regenerate numeric plans from the pinned owned disc with `python3 tools/build_floor_plans.py <owned CUE> <output JSON>`. The generator verifies the executable identity and native file records. It exports coordinates and metadata, with no map texture or palette colors. Restart an existing tracker process to load code/catalog changes, then reopen its map at http://127.0.0.1:8765.

The shared RE1 engine reevaluates entered rooms from fresh acquisition, story and door flags. Supported script conditions can change an earlier room's items or doors without reentry, including after an earlier save or savestate is loaded. An unresolved item condition prevents clearance; unresolved door coverage has its own message and does not change item completion. Departed rooms use a fresh-entry reconstruction with bounded native resets and supported event starts. Unsupported native effects and unresolved room conditions can still require reentry. Tracking rules outside the captured Mansion cases are source-derived candidates, not full-game gameplay validation.

Recurring room-script updates also participate in this calculation. The engine accounts for possible earlier main/event writes rather than assuming an old effect disappears when its trigger flag changes. Event writes that agree on an item's current state do not block tracking. A completed scripted award uses the game's pickup bit; an uncollected dormant award still needs its event conditions resolved. Script-disabled doors retain their markers and show as unavailable.

Audited setup commands now continue through the shared rules instead of creating false failure branches. Supported variable setters affect later comparisons within the same script pass. Temporary values from another room do not establish a past room's state. A reached command with unsupported effects or an invalid event target prevents clearance. Supported quantity changes preserve item identity and acquisition state. An uncertain amount alone does not prevent clearance; a quantity-dependent availability condition still needs resolution.

Run `python3 -m pytest -q tests/test_dynamic_quantities.py` for quantity reads/writes, zero amounts, source bounds, event dispatches, quantity-dependent conditions and acquisition reversal. Current-room observations read exact amounts from RAM. Reconstructed amounts use supported script values where available, or the explicit `unreconstructed` quantity state in the map JSON. The map can still name the item and show remaining/collected. RE1-QUANTITY-001/002 document the pinned native contracts and offline checks. Natural quantity changes and their normal-save/load behavior remain unvalidated.

## Art Room map validation

RE1-EVENT-015 and RE1-PICKUP-004 record the tested Training Jill case on SLUS-00551. Use the isolated emulator/version above and keep Ink Ribbon untouched throughout:

1. Complete the opening and Barry's Lock Pick conversation through normal gameplay. Enter Art Room `00-07` from Main Hall `00-06`.
2. Push the movable wooden steps beside the statue. Save a private before savestate, then climb the steps. Do navigation before attaching the watchpoint recorder; native pause/frame-step actions can end it with an unexpected debugger-stop diagnostic.
3. Attach `--breakpoints` while the game runs. Interact with the map and choose No. Expect indexed entry 0 to start and stop while Map remains available and PS1 virtual `0x800C86ED` bit 6 remains set.
4. Interact again and choose Yes. Expect entry 0 and child entry 1, both linked to item slot 2. Accepting clears bit 6: the tested byte changed `0xFF -> 0xBF`. Dismiss the message, stop the recorder and save a private after savestate. The tracker should show Map taken, Ink Ribbon available and an incomplete room.
5. Keep only one GDB client connected. Leave to Main Hall and return normally. The Map bit must remain cleared; initialization may omit its taken descriptor. Ink Ribbon remains available and blocks clearance.
6. Use ordinary polling for before/after savestate loads. Before restores Map available and bit 6 set; after restores Map taken and bit 6 clear. Completion must be recomputed while the tracker's session visits remain recorded.

The completed runs captured five checked initializations and five stops, including decline without acquisition. Offline replay of full coherent RAM captures kept the Art Room incomplete through pickup, reentry and reversal. Acquiring the game's map added no tracker regions; only the observed Art Room and Main Hall visits were revealed.

RE1-SAVE-003 adds normal memory-card saving/loading and earlier-save reversal for this Map. To repeat it with an isolated empty card:

1. Leave the Map untouched, collect Main Hall Ink Ribbon and save through its typewriter to slot 1.
2. Restart the game, choose Load Game and load slot 1. After control returns, expect Map byte `0x800C86ED` equal to `0xFF`.
3. Prepare or play the collected Map state, save through the typewriter to slot 2, restart and load slot 2 through Load Game. Expect `0xBF`.
4. Restart and load the earlier slot 1 through Load Game. Expect `0xFF` again. Do not load an emulator savestate for any of these returns.
5. Keep Art Room Ink Ribbon untouched. A tracker that previously observed Art Room must refresh Map available/taken/available while preserving its session visits and keeping that room incomplete.

Savestates may prepare the two saving scenarios. The completed test matched all three loaded acquisition blocks to their private card payloads and replayed the captured RAM through one tracker/cache without synthetic substitutions. Main Hall completion remained unknown after its ribbon was taken; this does not establish clearance there. RE1-CLEAR-001 traces that verdict to slot 5's typewriter interaction and optional pickup-handler history. Its four-capture replay is a diagnosis of unchanged behavior, not a clearance regression or a new gameplay test.

RE1-CLEAR-002 replays those captures through shared live-interaction coverage. Main Hall now reports cleared while current after its ribbon is taken, including in all three normal-load captures, and incomplete when the captured uncollected ribbon state returns. The reader validates typewriter, item-box and document descriptors explicitly, preserves pending pickups and dormant-award uncertainty, and rechecks pending state before publication. After leaving Main Hall, unresolved event history still prevents an established clearance verdict there. These are recorded-RAM checks of the implementation, with no new gameplay run. Run `python3 -m pytest -q tests/test_room_items.py tests/test_tracking_rules.py` for its synthetic boundary and timing regressions.

RE1-CLEAR-003 adds a normal-load and walked Main Hall round trip with the ribbon already collected:

1. Load the tested slot-2 card save through the game's Load Game menu. After control returns in Main Hall, expect ribbon byte `0x800C86E1 = 0xF7`, mask `0x08` clear, and current completion `CLEARED` with complete item coverage.
2. Walk through the Art Room door without collecting anything. Capture after control returns. The ribbon flag and full acquisition block must remain unchanged. Art Room reports `INCOMPLETE`, and departed Main Hall should remain `CLEARED` under shared entry reconstruction (RE1-REENTRY-004). At tracker commit `e63f475`, before that fix, cached Main Hall incorrectly lost coverage and reported `UNKNOWN`.
3. Return through the same door. Current Main Hall reports `CLEARED` again. Keep the same profile/cache and tracker for the captured-state replay; reveal only the entered regions `06` and `07`.

The new run used ordinary controller input and no savestate return. The older Art Room return at the end of RE1-CLEAR-002's replay restores the Main Hall ribbon's uncollected state, so it alone does not test ordinary post-collection departure. The new three-capture sequence reproduced the coverage regression at the time; RE1-REENTRY-004 replays the same unchanged captures with Main Hall remaining `CLEARED`. RE1-EVENT-016/017 recorded bounded reset/start-condition leads before implementation.

RE1-REENTRY-004 replays these unchanged captures through shared entry reconstruction. Main Hall now remains `CLEARED` while the player is in Art Room. A twelve-step replay also preserves Art Room's available/taken Map reversal across the existing normal-save loads, keeps its Ink Ribbon available, and restores Main Hall to `INCOMPLETE` when the earlier ribbon-available capture returns. This is recorded-state validation of the implementation, with no new live gameplay run.

Run `python3 -m pytest -q tests/test_room_reentry.py` for synthetic reset bounds, physical aliases, event start/restart chains, separate dispatches, forced interactions, stale retained pointers, item/door story reversal, display-consumer effects, analysis limits and computation-cache invalidation. The cache belongs to the profile instance and retains one result per source only while every interpretation input matches. It never replaces fresh flag reads. RE1-REENTRY-002 records the pinned display command's source contract; its natural execution and broader room/story coverage remain unvalidated.

Fresh last-item pickup timing, other puzzles, other characters/revisions and normal save/load of active events remain unvalidated. Private artifact hashes and exact event/flag evidence are in the research entries.

## Guardhouse basement map validation

RE1-MAP-014 records the tested Chris ladder round trip on SLUS-00551:

1. Use the isolated emulator/version in RE1-SAVE-005 and verify RetroAchievements is disabled before loading. Restore the private Guardhouse return checkpoint, then attach a fresh tracker after gameplay resumes.
2. For this route, enable the temporary frame-end health lock `800C51AC 008C` described in RE1-CHEAT-003. It holds a 16-bit health word at 140; combat and instant-death protection are untested. Record whether the patch is enabled for any repeat.
3. Walk Entry `03-00` → Passage `03-05` → Room 002 `03-06` through ordinary doors. Expect Guardhouse 1F to reveal only regions `00,05,06`. Room 002 should show Shotgun shells ×7 and Map available, with incomplete completion.
4. Use Room 002's already exposed ladder through its interaction prompt. Expect Water Tank Entry `03-0d`, Guardhouse B1, to reveal alone and show cleared with two Green Herbs already collected. Move away from the ladder to check character control.
5. Climb back normally. Expect Guardhouse 1F to retain regions `00,05,06`, Room 002's available items and a visited destination on its B1 exit. Do not load a savestate during the round trip.
6. Disable the temporary patch after testing. Keep private saves, RAM and screenshots out of Git.

Eight captured publications replay exactly with pinned executable checks and unchanged acquisition flags. This is a map entry/return check using a health patch, not new pickup, story or normal-save persistence validation. Scoped live checks cover seven of eleven plans; Mansion B1 and Laboratory B1/B2/B4 still need entry checks. A Laboratory retry did not reach a valid checkpoint load and is excluded.

## Laboratory B2 and B1 map validation

RE1-MAP-015 records two Chris round trips on SLUS-00551, using the emulator and temporary health lock in RE1-CHEAT-003:

1. Verify RetroAchievements is disabled before loading. Load public card entry `BASLUS-005513` through Load Game, then attach a fresh tracker after character control returns.
2. Walk Save `04-0e` → Elevator Entry `04-0c` → O-Room `04-05` → Stairway `04-03`. Expect Laboratory B3 to reveal `0E,0C,05`, then Laboratory B2 to reveal only `03`. Stairway should show MODisk and one Green Herb taken, another Green Herb remaining, and incomplete completion.
3. Move on the stair landing, then descend normally to O-Room. Expect B3 to retain its three outlines and the Stairway exit to report its destination visited. Keep one tracker throughout this round trip.
4. For the separate B1 route, restore the private B2 checkpoint recorded in RE1-MAP-015 before attaching another fresh tracker. That checkpoint was saved while GDB-paused; resume it through GDB if the native load waits. Walk Stairway → Ladder Room `04-02` → Laboratory Entry `04-00` using the normal door and ladder prompt.
5. Expect B2 to reveal only `03,02`, then B1 to reveal only `00`. Ladder Room and Laboratory Entry should report cleared with zero items. At Entry's exit `04-01`, expect locked; normal interaction should produce the game's tightly locked message. This checks the lock state, not the required key's identity or an unlock.
6. Climb back normally and move away from the ladder. Expect B2 to retain both outlines and Ladder Room's B1 exit to report its destination visited. Do not restore a savestate during either round trip.
7. Close the isolated emulator and restore its temporary settings after testing. Keep RAM, saves, journals and screenshots out of Git.

All thirteen captured publications replay exactly with pinned executable checks and unchanged acquisition flags within each route. These checks add Laboratory B2/B1 and three rooms, bringing scoped live map entry coverage to nine of eleven plans. Mansion B1 and Laboratory B4 remain unvalidated. The tested B4 elevator refused operation; no power flag was established. Repeated Chimera attacks show that the health lock does not prevent stagger. New pickups, story changes, unlocks and normal-save persistence were not tested.

## Laboratory power and B4 elevator round trip

RE1-PICKUP-006, RE1-DOORS-008 and RE1-MAP-016 record this Jill route on SLUS-00551 with RE1-CHEAT-003's temporary health lock:

1. Keep RetroAchievements disabled before loading. Load public card entry `BASLUS-005514` through Load Game, then attach a fresh tracker after Jill is controllable. Walk Save `04-0e` → Elevator Entry `04-0c` → Power Maze 1 `04-0f` → Power Maze 2 `04-10` → Power Room `04-11`. Expect each outline to appear only on entry.
2. The recorded second session restores the private pre-pickup Power Room checkpoint before attaching a separate fresh tracker. Keep that tracker throughout the remaining route. Take the Battery through the native Yes prompt. Expect incomplete 0/1 → cleared 1/1, Battery available → taken, and acquisition byte RAM `0xC86E7` changing `0xEF → 0xEB` (mask `0x04`).
3. Connect elevator power in Power Room. Expect story byte RAM `0xC8706` changing `0xC0 → 0xC4`. Return through both mazes to Elevator Entry and check the elevator: expect blocked, matching the native no-power refusal.
4. Use Power Maze 1's panel to activate the blacked-out areas. Expect `0xC8706` changing `0xC4 → 0xC6`. Return to Elevator Entry and use its separate call switch. Let the native sequence enter Elevator `04-15`, then Main Lab Entry `04-14` and Main Lab `04-13`.
5. Expect B4 initially to reveal no outline for the unoutlined elevator, then only Entry `14`, then both `13,14` when Main Lab is entered. Main Lab has zero relevant collectibles in this observed state; its exit remains unavailable after the encounter until the native Barry interaction completes.
6. Defeat the native encounter through ordinary controls, interact with Barry, and walk the newly opened exit corridor. Follow the native elevator return to B3. Expect the earlier four B3 outlines, Battery taken, and the elevator open with destination visited and complete door coverage. No savestate should be restored during this pickup/power/return sequence.
7. Close the isolated emulator and private preview. Restore the temporary settings and remove the test-only cheat/per-game files after archiving them. Keep saves, game assets, RAM and private journals out of Git.

All 31 captured publications replay with the pinned executable checks and identical payload content after normalizing only door-array ordering; 15 also match without normalization. The final acquisition bank matches the post-Battery capture, and both power bits remain set. B4 completes scoped live entry checks for ten of eleven plans; Mansion B1 remains unvalidated. This is map-area coverage, not a whole-game readiness percentage. Battery reentry, normal in-game save persistence, earlier pickup/power reversals and other scenarios were not tested. The public card already supplied infinite Colt Python ammunition; no ammunition patch was added. The health lock does not prevent grabs or stagger.

## Mansion B1 and Elevator Stairway return

RE1-MAP-017 and RE1-DOORS-009 record this Jill Original route on SLUS-00551:

1. Disable RetroAchievements before loading public card entry 3, `BASLUS-005512`, through Load Game. Attach a fresh tracker after Jill is controllable. Use the RE1-CHEAT-003 temporary health lock only in the isolated validation copy.
2. Walk Courtyard B1 to the garden ladder and lift, then Mansion Store Room → Roofed Passage → Back Passage → East Stairway 1F/2F → Lesson Entry → Lesson Room. The successful session uses this eastern route; Tea Room's basement shortcut is locked from its other side.
3. Confirm the native rope descent. Expect room `06-0c` to select Mansion 1F region `1F`, with B1 still hidden. Walk the lower passage and confirm its ladder prompt. Expect `06-1a`, Mansion B1, with only region `1A` revealed.
4. Enter `06-1b` and `06-1c` normally. Expect B1 regions `1A,1B`, then `1A,1B,1C`. Passage 2 is incomplete with two available Green Herbs, quantity 1 each. Leave them untouched. Passage 1 reports its Shotgun shells taken; Kitchen reports zero registered collectibles in this save.
5. Interact with the Kitchen stairway exit. Let its native zombie event finish, clear the blocker through ordinary controls and cross the opened door. Expect `05-10`, basement region `1E`, and four visible B1 regions. Kitchen should publish target `05-10` under the stage-remap rule (RE1-DOORS-010); builds before that fix published `00-10` here (RE1-DOORS-009).
6. Ascend and descend the Elevator Stairway normally. Expect Mansion 1F region `10`, then Mansion B1 region `1E`. The return retains all four B1 outlines and Passage 2's two herbs. Cross back into Kitchen and move under player control. Stairway should publish `06-1c`; pre-fix builds published `01-1c` (RE1-DOORS-009).
7. Close the isolated emulator and private preview, restore its settings and remove archived temporary cheat/per-game files. Keep the RAM captures, cards, checkpoints and screenshots out of Git.

The private audit verifies 46 captured publications across three separate tracker sessions, using each RAM capture plus visit history explicitly observed in its live journal. All 46 complete payloads match exactly. Camera-only journal visits are supplied where sparse captures omit them; this is not RAM-only reconstruction of visit history. The successful session's 32-byte acquisition bank is unchanged. All eleven floor plans now have scoped live entry coverage, and B1's four outlined regions were entered. This does not establish whole-game readiness: broader item/door/save-load outcomes remain, and the remap correction has recorded-state replay validation only (RE1-DOORS-010), not a fresh traversal under the fixed build. No new pickup, shortcut unlock or normal-save persistence was tested in this route.
