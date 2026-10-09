# Running the live tracker

Use DuckStation with the tested RE1 Director's Cut USA disc, SLUS-00551. Enable its GDB server on port 2345, then boot the game and load a playable room.

From the repository directory:

```sh
python3 tools/track.py --map
```

Open http://127.0.0.1:8765 and leave the terminal running. Stop with Ctrl+C.

The tracker automatically switches among eleven floor plans across the Mansion, Courtyard, Guardhouse and Laboratory. Rooms reveal only when the tracker observes entry. Collecting an in-game map does not reveal extra rooms. Red rooms have available items remaining, blue rooms are cleared, and the white outline marks the current room. Select an explored room to see its items and directional door locks. Visit history belongs to this tracker session and resets on restart.

Camera-dependent spaces reveal separately from their parent room. Their item/completion state still belongs to the underlying logical room, so several outlines can share one item list. The original map has no colored polygon for the Mansion elevator, heliport, Courtyard laboratory elevator and two Laboratory elevators. The tracker retains their room details and native floor selection without adding an invented outline. Seven boundary door markers have no encoded destination; they remain unassigned on the map while known exit access stays available in the door list.

Coverage status 2026-10-09: RE1-MAP-014/015/016/017 add Guardhouse B1, Laboratory B2/B1, Laboratory B4 and Mansion B1 entry checks, so all eleven floor plans now have scoped live entry coverage. The per-route "covers N of eleven" statements below record the state when each route was tested and are kept as history. None of these routes validates new pickups (except the Power Room Battery in RE1-MAP-016), story conditions beyond the recorded flags, unlocks, or normal-save persistence unless the entry says so.

Multi-area checks run with `python3 -m pytest -q tests/test_multi_area_maps.py tests/test_floor_plan.py tests/test_map_view.py`. They cover native floor/camera boundaries, every supported source room's binding, cross-floor reveal isolation, map acquisition, camera coherence, malformed catalog data, owned marker encodings and HTTP delivery. These are synthetic and captured-state regressions. RE1-MAP-004/005/006 record the source evidence and checks. RE1-MAP-007 adds a captured Storeroom-to-East-Stairway transition; its attempted floor test did not complete. RE1-MAP-008 completes a natural Main Hall 1F → 2F → 1F → 2F run, verifies entry-only outlines, retained visits, supported items and doors, and replays all nine new captures with exact live publication equality. RE1-MAP-009 adds native map-menu comparisons in both Main Halls, unchanged tracker publication while viewing those maps, and an exact seven-capture replay.

RE1-SAVE-005 and RE1-MAP-012/013 add normal public-card loads and nine rooms across Laboratory B3, Courtyard B1, Guardhouse 1F and Courtyard 1F. The natural Guardhouse → Courtyard → Guardhouse route checks area switching and retained visits. RE1-SOURCE-003 fixes a reproduced Guardhouse source rejection caused by native 32-bit event relocation; its regression command is `python3 -m pytest -q tests/test_room_cache.py tests/test_tracking_rules.py`. At that point scoped live checks covered six of eleven floor plans (see the coverage status note above for the current state). Mansion B1, Guardhouse B1 and Laboratory B1/B2/B4 were still untested in gameplay at that point. Native map-screen comparisons outside the Mansion remain untested, and these later-area entries do not validate new pickups or story conditions. Keep RetroAchievements disabled before loading any test game or checkpoint.

The tracker currently records attract-mode demo rooms as visits, reproduced in RE1-LIFECYCLE-001. Start it once gameplay is controllable and stop it before leaving the game idle at the title screen. A lifecycle detection fix is still required; demo visits are excluded from reported gameplay coverage.

To compare against RE1's own map with the isolated test copy's keyboard bindings, press Enter for the status menu, move up twice from the first inventory slot to Map, confirm with K, then confirm the selected floor with K. The tracker should keep only its observed rooms, even when the native map displays rooms visited before tracking began. In the recorded Main Hall checks, it kept regions `06` and `07` on 1F and region `03` on 2F; items and doors also stayed unchanged. L and Enter return to gameplay.

Regenerate numeric plans from the pinned owned disc with `python3 tools/build_floor_plans.py <owned CUE> <output JSON>`. The generator verifies the executable identity and native file records. It exports coordinates and metadata, with no map texture or palette colors. Restart an existing tracker process to load code/catalog changes, then reopen its map at http://127.0.0.1:8765.

The shared RE1 engine reevaluates entered rooms from fresh acquisition, story and door flags. Supported script conditions can change an earlier room's items or doors without reentry, including after an earlier save or savestate is loaded. An unresolved item condition prevents clearance; unresolved door coverage has its own message and does not change item completion. Departed rooms use a fresh-entry reconstruction with bounded native resets and supported event starts. Unsupported native effects and unresolved room conditions can still require reentry. Tracking rules outside the captured Mansion cases are source-derived candidates, not full-game gameplay validation.

Recurring room-script updates also participate in this calculation. The engine accounts for possible earlier main/event writes rather than assuming an old effect disappears when its trigger flag changes. Event writes that agree on an item's current state do not block tracking. A completed scripted award uses the game's pickup bit; an uncollected dormant award still needs its event conditions resolved. Script-disabled doors retain their markers and show as unavailable.

Audited setup commands now continue through the shared rules instead of creating false failure branches. Supported variable setters affect later comparisons within the same script pass. Temporary values from another room do not establish a past room's state. A reached command with unsupported effects or an invalid event target prevents clearance. Supported quantity changes preserve item identity and acquisition state. An uncertain amount alone does not prevent clearance; a quantity-dependent availability condition still needs resolution.

Run `python3 -m pytest -q tests/test_dynamic_quantities.py` for quantity reads/writes, zero amounts, source bounds, event dispatches, quantity-dependent conditions and acquisition reversal. Current-room observations read exact amounts from RAM. Reconstructed amounts use supported script values where available, or the explicit `unreconstructed` quantity state in the map JSON. The map can still name the item and show remaining/collected. RE1-QUANTITY-001/002 document the pinned native contracts and offline checks. Natural quantity changes and their normal-save/load behavior remain unvalidated.

# Shared-engine regression checks

Scripted-collectible checks run with `python3 -m pytest -q tests/test_scripted_collectibles.py`. Shared rules recognize supported direct awards and confirmation prompts that start bounded child events. Live and departed-room tracking both use fresh acquisition flags. A validated item already acquired is Taken even when its scripted access is unsupported. Uncollected items still require supported access across matching source aliases. Incomplete source coverage, failed execution bounds and conflicting identities still prevent clearance. The suite checks ordinary/map/separate acquisition flags, pending awards, stale pointers, failed/coherence-changing reads and earlier-state reversal. A flag change between the observer and later poll snapshot must retry without updating the tracker. RE1-COLLECT-001/002/003/004 record source coverage and remaining gameplay checks.

Scripted-door checks run with `python3 -m pytest -q tests/test_scripted_doors.py`. The same source-bound rule handles live registered event doors and fresh-entry reconstruction of departed rooms. A bounded script that delegates to the same door's ordinary callback uses fresh lock flags. A bounded script with no ordinary door call shows blocked passage. Confirmation prompts are a selectable route, not proof that the callback has already run or that a lock is open.

The suite checks accepted-dialog flow, retained geometry and target, lock reversal, message-only interactions, required metadata, disagreeing source aliases and loaded-state changes. Unsupported story/inventory guards, child starts, overlapping wrappers, different callback slots, changed player state on a player-dependent lock, pending forced awards and failed/incoherent reads cannot supply an access proof. These tests are synthetic. RE1-DIALOG-001 and RE1-DOORS-006 record the native contracts, generated-source comparison and unchanged-capture replay; the newly resolved routes have not been traversed naturally.

Script reachability checks run with `python3 -m pytest -q tests/test_script_reachability.py`. Departed-room reconstruction excludes a failed event only when its entry cannot be reached through the supported setup, recurring scripts, native child starts/restarts or registered/forced interactions. Unknown conditions include both possibilities. Malformed tables and source sections remain global failures. A reached decoding failure prevents item and door clearance even when no affected slot could be decoded. Current-room validation retains its historical coverage barrier; inactive events do not prove that an earlier script never ran. RE1-REENTRY-005 records the synthetic checks, unchanged-capture replay and remaining natural gameplay limits.

Run `python3 -m pytest -q` with pytest installed. The focused engine suite is `python3 -m pytest -q tests/test_tracking_rules.py tests/test_event_tracking.py tests/test_command_semantics.py tests/test_room_cache.py`.

These checks cover multiple pickups, last-item clearance, acquisition rewind, story-dependent alternatives, dormant items, source selection, door replacement, unresolved branches, malformed metadata and reads that change during polling. The Herb and Chemical cases compare rules with the donated before/after RAM fixtures. Other flag changes in this suite are explicitly synthetic and do not validate a natural story event or normal in-game save/load.

Decoder alignment and operand bounds have a focused suite, `python3 -m pytest -q tests/test_native_decoding.py tests/test_scan_scd.py tests/test_scan_scd_widths.py`. It checks pickups and doors after native setup commands, overlapping operand reads, procedure/event boundaries and rejection of nonadvancing or null dispatches. These are source-format regressions, not gameplay tests.

Indexed-event flow has a focused suite, `python3 -m pytest -q tests/test_event_contract.py tests/test_scan_events.py tests/test_cache_metadata.py`. It checks shared wait/counter/call/loop depth, overlapping counter reads, deferred-command return paths, native termination and actor/motion packet boundaries. Unknown nonadvancing states and reads beyond the supplied section still reject coverage. These tests use synthetic packets and do not reproduce natural puzzle or story events.

Research entries RE1-ENGINE-001/002, RE1-SCD-007 through RE1-SCD-015, RE1-EVENT-003/004, RE1-VARS-001, RE1-SOURCE-002 and RE1-SELECT-001 describe the supported rules, evidence and remaining validation limits. Multi-area geometry does not resolve the remaining item and door interpretation gaps or establish whole-game runtime reliability.

Remaining script-effect regressions run with `python3 -m pytest -q tests/test_remaining_effects.py`. They cover lighting continuation, movie control flags, particle header clearing, inventory-removal return branches, physical variable/flag aliases, parameter-dependent callbacks and deferred return paths. Supported forced map callbacks require a map descriptor. Other callback IDs still need native effect support; an unmodeled callback parameter cannot prove its pending bit. These tests are synthetic and do not validate natural inventory removal, document/movie events or save/load.

Forced-door regressions run with `python3 -m pytest -q tests/test_forced_doors.py`. Callback 1 preserves the door definition, including a disabled handler and its mode. Unlock state still comes from fresh game flags, so invoking a script callback or visiting both rooms does not imply an unlock. Conflicting event definitions and unsupported sources still need observation. The suite checks command return branches, temporary state aliases and locked/open/locked map refresh with synthetic flag changes over existing captures. It does not validate a natural unlock or door save/load.

Ordered event-condition regressions run with `python3 -m pytest -q tests/test_event_conditions.py`. Embedded full procedure lists retain command order, progress writes and repeated guard relations. Single/deferred changes and separate dispatches remain independent possibilities. Current progress flags do not prove that an earlier event ran. The suite covers waits, multi-procedure blocks, physical aliases, malformed inputs, analysis limits and fresh acquisition/story reversal using synthetic packets and substitutions. Natural event activation, puzzle progression and save/load still need gameplay validation; the existing-capture unresolved counts are unchanged.

Event-activation regressions run with `python3 -m pytest -q tests/test_event_activation.py`. The debug tracker reports active event slots, their matching source and indexed entry, registered event interactions, and potential item/door slots. The reader binds these observations to the current room's verified source and relocated event table. It ignores inactive script pointers and rereads event positions before publishing state. An unbound active event or event interaction prevents clearance.

The suite covers shared script aliases, initialized frame pointers, guarded starts, transitive starts, callbacks, explicit read failures, source bounds, stops and snapshot reversal. Active records and reversal in these tests are synthetic. A limited live attract-mode experiment bound registered interactions, including a trigger linked to a Map slot in room `00-07`, but captured no active event. RE1-EVENT-005 through RE1-EVENT-008 record that experiment's limits. RE1-EVENT-013 later captured natural opening starts/stops. RE1-EVENT-015 captures map acceptance and decline; other puzzle changes and normal save/load of active events remain unvalidated. Event activity never grants acquisition or proves earlier execution.

# Capturing live event observations

Use an isolated DuckStation copy with the exact SLUS-00551 profile and native GDB enabled. Stop any other tracker/GDB client before connecting this tool. It resumes the game on connection and briefly pauses on observed event, item, door or relevant flag changes.

From the repository directory, choose a new log path outside the repository:

```sh
python3 tools/capture_events.py \
  --profile profiles/re1_directors_cut_slus00551.json \
  --out /tmp/re-map-events.jsonl \
  --seconds 180 --hz 20
```

The output file must not exist. Stop early with Ctrl+C. The tool resumes before closing; connection/resume failures report a diagnostic. A broken connection ends the capture, so restart with a new output path after restoring GDB access.

Each JSONL record includes session identity, sequence, UTC time and elapsed time. Snapshots contain verified room/source aliases, all observed active slots, registered event interactions, current item/door states and flag values. Descriptor reads use hashes rather than game bytecode. Polling discards identical coherent captures. Gaps explain failed reads or unsupported state; recovery begins a new comparison baseline. Heartbeats give sample and capture counts every 30 seconds.

The requested polling rate is a limit, not a guarantee. Short events between polls can be missed. `became-active`, `became-inactive` and `position-changed` describe differences between observations, not completed execution or the cause of a reload. Item registry coverage is separate from room completion. This tool does not update tracker visit history or use event activity to grant acquisition.

Run `python3 -m pytest -q tests/test_event_capture.py` for synthetic lifecycle, coherence, flag, gap and pause-cleanup regressions. RE1-EVENT-009/010 record the implementation and live tests. Actual Herb-before/after/before savestate loads restored the recorded item state, but every event slot in those recordings remained inactive. RE1-EVENT-013 later captured natural opening events with the watchpoint mode below. RE1-EVENT-015 and RE1-PICKUP-004 add the Art Room Map interaction and reversal check. Other item/puzzle progression and normal save/load of active events still need validation.

## Capturing short events with watchpoints

For events that polling can miss, select the optional CPU write capture mode:

```sh
python3 tools/capture_events.py \
  --profile profiles/re1_directors_cut_slus00551.json \
  --out /tmp/re-map-event-writes.jsonl \
  --seconds 180 --breakpoints
```

Use the isolated DuckStation version documented in RE1-EMU-008 and leave it running before attaching. Its server can resume after a broken connection only when the first client attached while it was running. `--breakpoints` cannot be combined with `--hz`. The mode installs a one-byte write watchpoint on each of the eight event activity fields. It captures a baseline and each activity write, including repeated writes that leave the snapshot unchanged. Each snapshot records the triggering slot, accessed PS1 virtual address, native PC and step count.

RE1 writes activity before finishing its event record. The tool verifies the exact game's initializer code, then single-steps its remaining 13 instructions before reading the new script pointer. Other activity writes need no stepping. This temporarily pauses gameplay and can affect timing, so use this mode for experiments. `pause_seconds` measures the capture operation from receipt of a stop through the resume request; it excludes delivery latency. Cleanup removes the tool's watches, resumes and disconnects, including after a failed setup. A rejected debugger command or unexpected stop ends the run with a diagnostic.

Watchpoints observe CPU accesses starting at the watched byte. Wide writes starting earlier and emulator savestate restores can bypass them. Items, doors and flags are snapshots taken at activity writes, so unrelated changes do not trigger this mode. Use ordinary polling to observe those changes and save/load reversal. Neither mode establishes a complete execution history or grants acquisition from event activity.

Run `python3 -m pytest -q tests/test_gdb.py tests/test_event_breakpoints.py` for protocol framing, all-slot initialization, start/stop/restart observations, bounds and cleanup checks. The activity and CPU execution in these tests are synthetic. RE1-EVENT-011 records the pinned initializer contract and the live capture limits. RE1-EVENT-012 records real activity-clear writes across all eight slots, which produced source-unavailable gaps rather than active-event snapshots.

RE1-EVENT-013 records a natural gameplay check. Boot the owned disc in an isolated copy, select New Game, Training and Jill, and attach the recorder at character selection. Skip the movies with ordinary Start and let the Main Hall and Dining Room opening scripts run. The tested run captured 19 starts with 13 initializer steps each, eight stops and waits/restarts across slots 0/1/2/3/6/7. Every newly initialized slot bound to a room source and indexed entry. Slots 4/5 activation and item/puzzle interactions remain untested. Room transitions produced source-unavailable gaps, and three snapshots caught the already-running Main Hall event at its temporary parent pointer during a child start. RE1-EVENT-014 adds those source-bound positions to the shared scanner and resolves all three in a recorded-field replay. The original recording remains unchanged; complete event and availability interpretation are still unfinished.

For automated native input, DuckStation's built-in controller macros can hold a normal controller binding until the next key tap when toggle is enabled and frequency is zero. The experiment used temporary settings in its private portable copy and restored them afterward. This makes ordinary game input reproducible without changing guest memory. The measured initializer captures paused approximately 0.41..0.45 seconds each, so use this setup for validation rather than continuous player-facing tracking.

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
2. Walk through the Art Room door without collecting anything. Capture after control returns. The ribbon flag and full acquisition block must remain unchanged. At tracker commit `e63f475`, Art Room reports `INCOMPLETE`, while cached Main Hall incorrectly loses coverage and reports `UNKNOWN`.
3. Return through the same door. Current Main Hall reports `CLEARED` again. Keep the same profile/cache and tracker for the captured-state replay; reveal only the entered regions `06` and `07`.

The new run used ordinary controller input and no savestate return. The older Art Room return at the end of RE1-CLEAR-002's replay restores the Main Hall ribbon's uncollected state, so it alone does not test ordinary post-collection departure. The new three-capture sequence independently reproduces the coverage regression. RE1-EVENT-016/017 recorded bounded reset/start-condition leads before implementation.

RE1-REENTRY-004 replays these unchanged captures through shared entry reconstruction. Main Hall now remains `CLEARED` while the player is in Art Room. A twelve-step replay also preserves Art Room's available/taken Map reversal across the existing normal-save loads, keeps its Ink Ribbon available, and restores Main Hall to `INCOMPLETE` when the earlier ribbon-available capture returns. This is recorded-state validation of the implementation, with no new live gameplay run.

Run `python3 -m pytest -q tests/test_room_reentry.py` for synthetic reset bounds, physical aliases, event start/restart chains, separate dispatches, forced interactions, stale retained pointers, item/door story reversal, display-consumer effects, analysis limits and computation-cache invalidation. The cache belongs to the profile instance and retains one result per source only while every interpretation input matches. It never replaces fresh flag reads. RE1-REENTRY-002 records the pinned display command's source contract; its natural execution and broader room/story coverage remain unvalidated.

Fresh last-item pickup timing, other puzzles, other characters/revisions and normal save/load of active events remain unvalidated. Private artifact hashes and exact event/flag evidence are in the research entries.

## Shared native callbacks

Run `python3 -m pytest -q tests/test_native_callbacks.py` for forced movement callbacks 5/6 and parameter-driven flag callback 7. The tests cover source and parameter binding, disabled handlers, current/reentry epochs, init/main/indexed dispatch, pending consumers, command returns, physical aliases, bank/index bounds, fresh flag reversal and failed reads.

RE1-SCD-016/017 record the pinned native contracts. RE1-NATIVE-001 records the implementation, two identical disc regenerations, the unchanged twelve-step captured save/load replay and an offline projection of all 334 source variants. These synthetic/source checks do not confirm natural movement/flag interactions or later-area gameplay. The projection uses one flag configuration and must not be presented as a count of rooms validated in-game.

## Shared rendering commands

Run `python3 -m pytest -q tests/test_rendering_commands.py tests/test_native_decoding.py` for lighting command `40`, model recoloring `4D` and effect-record flags `4E`. Synthetic tests cover lighting destinations bounded before pointed room sections, signed/unsafe indices, the overlapping final operand read, SCD branch returns, ordered/single/deferred event dispatch, local flag aliases, fresh acquisition reversal and item/door preservation.

RE1-SCD-018/019/020 record the pinned native contracts; RE1-NATIVE-002 records two identical disc regenerations and the unchanged twelve-step captured save/load replay. The offline projection still resolves items in 258 and doors in 268 of 334 source variants under one existing flag snapshot. Five variants containing these commands still hit other reconstruction limits; recognition of the commands does not establish full room coverage. No new natural lighting/recoloring/effect event was played, so these findings remain Candidate.

## Script dependency filtering

Run `python3 -m pytest -q tests/test_script_dependencies.py tests/test_tracking_rules.py tests/test_room_reentry.py tests/test_native_callbacks.py tests/test_dynamic_quantities.py tests/test_event_conditions.py` for RE1-ANALYSIS-001. The shared interpreter retains simulated bits only when a predicate or quantity input anywhere in the room program reads them. Physical dependencies preserve flag/scalar aliases and reads in later procedures, events and ticks. Unsupported effects and genuinely relevant branches still prevent unsupported clearance; the analysis limits are unchanged.

The paired offline audit preserves all previously resolved payloads across 334 variants, both analysis epochs and three captured flag states. Reentry item coverage increases 258 -> 262 and door coverage 268 -> 272 in each snapshot; current door coverage increases 250 -> 252. The twelve-step captured save/load replay also passes, including earlier-state reversal and entry-only map reveal. These checks perform no new gameplay. Newly resolved source variants, broader story progression and whole-game save/load still require runtime validation.

## Shared interaction disabling

Run `python3 -m pytest -q tests/test_interaction_disabling.py tests/test_room_reentry.py tests/test_native_callbacks.py tests/test_dynamic_quantities.py tests/test_forced_doors.py` for RE1-AOT-003/004. Both short and extended handler-zero setters can disable an interaction without reading its retained source. Tests cover init/main/ordered/standalone commands, known-source preservation, nonzero setters, forced callbacks, quantity consumers, partial creators, dormant awards and fresh acquisition/story reversal. Unknown source data still cannot authorize enabling or a source-dependent operation.

The paired offline audit preserves previously resolved payloads across 334 variants, both epochs and three captured flag states. Reentry item coverage increases 262 -> 269 and door coverage 272 -> 281; current coverage is unchanged. The twelve-step captured save/load replay passes, including earlier-state reversal and entry-only map reveal. These checks add no natural disabling-event or whole-game gameplay validation.

## Shared branch merging

Run `python3 -m pytest -q tests/test_branch_merging.py tests/test_script_dependencies.py tests/test_room_reentry.py tests/test_native_callbacks.py tests/test_dynamic_quantities.py tests/test_event_conditions.py tests/test_interaction_disabling.py` for RE1-ANALYSIS-003/004. The runner combines interaction alternatives only at matching script positions, IF stacks, physical shadows and descriptor inputs to quantity/flag callbacks. Synthetic cases retain distinct guard histories, missing sources, conflicting item/door identities, callback parameters, quantity uncertainty and fresh acquisition reversal. Tests preserve a scalar guard that passes for both descriptor inputs. Descriptor, procedure and stack limits still prevent unsupported completion.

The paired audit preserves published results across 334 variants, both modes and three captured states. Current complete item projections increase 255 -> 259; reentry increases 269 -> 271. Door coverage remains 252/281. The existing twelve-step captured save/load replay passes with earlier-state reversal and reveal only on entry. These are offline checks; the newly resolved variants and whole-game behavior still need natural gameplay validation.

## Message interactions at known doors

Run `python3 -m pytest -q tests/test_message_doors.py tests/test_room_items.py tests/test_tracking_rules.py tests/test_room_reentry.py tests/test_live_items.py tests/test_map_view.py` for RE1-DOORS-003/004. A validated Door_set source retained by message handler 2 should keep its wall marker and show blocked access with "Passage is unavailable". It must remain blocked even when its ordinary unlock flag is set. Restoring handler 1 should restore normal open/locked interpretation, and reversing the handler or a cached rule's persistent flag should refresh the verdict. Revealing a door must not reveal its destination room.

The 39 new synthetic cases also cover pending forced awards, invalid/changing sources, mixed open/message alternatives, differing targets and incomplete script coverage. Handler-zero reset leftovers must not override an expected active door. The full suite passes 1,220 tests. The paired audit preserves previous payloads across 334 variants, both epochs and three captured flag states; door completeness increases 252 -> 256 current and 281 -> 287 reentry, with item completeness unchanged at 259/271. The unchanged twelve-step recorded save/load replay passes, including the earlier ribbon-available reversal and entry-only map reveal. No naturally activated message door or new door save/load experiment is included in these results.

## Shared acquisition flags

Run `python3 -m pytest -q tests/test_acquisition_state.py tests/test_native_callbacks.py tests/test_room_items.py tests/test_room_cache.py tests/test_tracking_rules.py` for RE1-FLAG-003. The pinned profile explicitly selects each supported pickup's flag and acquired polarity. Ordinary pickups/maps use their GlobalId flag; type `4D`, Radio, uses byte `0x800C870C`, mask one, set-to-acquired. Its initial active handler still follows the ordinary GlobalId bit. A later handler setter can change availability independently of ownership.

The tests cover both tracking epochs, same-pass activation writes and physical aliases, separate flags of both polarities, earlier-state reversal, observed/reconstructed caches, changing/failed reads and dormant forced awards. The unchanged twelve-step captured save/load replay and 2,004 paired source evaluations preserve prior item/door payloads. Complete item projections increase from 259/271 to 263/275 for current/reentry under the three captured flag configurations; door coverage remains 256/287. These are offline checks. A natural Radio pickup and its before/after normal saves still need validation before the separate flag can be called runtime-confirmed.

## Shared item-interaction predicates

Run `python3 -m pytest -q tests/test_item_interactions.py` for RE1-SCD-021/022. The 52 synthetic cases cover unsigned item-use/acquisition comparisons after supported script writes, byte-setter truncation, physical flag aliases, changed quantity inputs, map-callback invalidation and fresh acquisition reversal in both tracking epochs. Unknown interaction values remain unresolved even when current RAM matches the requested value. Values from initialization or a separate runner cannot exclude later player actions; synchronous event procedures retain their same-run writes. Truncated commands prevent clearance.

Two identical regenerations map 132 commands in 72 source variants to existing byte-comparison rules. The 4,676 paired projections preserve published item/door results against the preceding implementation, with no coverage gains. The unchanged twelve-step captured save/load replay passes, including earlier acquisition reversal and reveal only for entered rooms. These checks perform no new gameplay and do not validate natural item-use puzzles or full-playthrough tracking.

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
5. Interact with the Kitchen stairway exit. Let its native zombie event finish, clear the blocker through ordinary controls and cross the opened door. Expect `05-10`, basement region `1E`, and four visible B1 regions. Record the current defect: Kitchen publishes target `00-10` despite this native arrival.
6. Ascend and descend the Elevator Stairway normally. Expect Mansion 1F region `10`, then Mansion B1 region `1E`. The return retains all four B1 outlines and Passage 2's two herbs. Cross back into Kitchen and move under player control. Record the reverse defect: Stairway publishes `01-1c`, but the game enters `06-1c`.
7. Close the isolated emulator and private preview, restore its settings and remove archived temporary cheat/per-game files. Keep the RAM captures, cards, checkpoints and screenshots out of Git.

The private audit verifies 46 captured publications across three separate tracker sessions, using each RAM capture plus visit history explicitly observed in its live journal. All 46 complete payloads match exactly. Camera-only journal visits are supplied where sparse captures omit them; this is not RAM-only reconstruction of visit history. The successful session's 32-byte acquisition bank is unchanged. All eleven floor plans now have scoped live entry coverage, and B1's four outlined regions were entered. This does not establish whole-game readiness: wrong door destinations and broader item/door/save-load outcomes remain. No new pickup, shortcut unlock or normal-save persistence was tested in this route.

# Diagnosing failures

File logging is enabled automatically. The terminal shows the absolute path to `logs/tracker.log`. To watch it in another terminal:

```sh
tail -f logs/tracker.log
```

The log retains startup details, room and item changes, state snapshots, read addresses and errors, unexpected exception traces, failed map requests, and browser errors reported while the map server is reachable. Unchanged tracker state is logged every 30 seconds. Successful browser polling is omitted.

Small state reads include hex values. Larger reads, including executable signature windows, include SHA256 hashes instead of game code bytes. Logs rotate at 2 MiB, retaining three previous files. The `logs/` directory is excluded from Git.

To choose another path:

```sh
python3 tools/track.py --map --log-file /tmp/re-map-tracker.log
```

Reproduce the problem, then report what you did and when it happened so the corresponding entries can be inspected. If the tracker has exited, restart it before reproducing the problem.

Pausing DuckStation may produce a logged GDB stop notification; tracking continues after that notification. A timed-out or damaged debugger reply closes the connection to prevent later memory reads from using stale replies. The map keeps running and retries the GDB connection once per second. It clears completion colors and live item and door details until the game can be read again. Terminal-only tracking also reconnects after a dropped connection; it requires a connection at startup.
