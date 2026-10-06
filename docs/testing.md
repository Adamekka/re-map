# Running the live tracker

Use DuckStation with the tested RE1 Director's Cut USA disc, SLUS-00551. Enable its GDB server on port 2345, then boot the game and load a playable room.

From the repository directory:

```sh
python3 tools/track.py --map
```

Open http://127.0.0.1:8765 and leave the terminal running. Stop with Ctrl+C.

The Mansion 1F floor plan reveals rooms only when the tracker observes entry. Collecting an in-game map does not reveal extra rooms. Red rooms have available items remaining, blue rooms are cleared, and the white outline marks the current room. Select an explored room to see its items and directional door locks. Visit history belongs to this tracker session and resets on restart. Other areas show the room ID.

The shared RE1 engine reevaluates entered rooms from fresh acquisition, story and door flags. Supported script conditions can change an earlier room's items or doors without reentry, including after an earlier save or savestate is loaded. An unresolved item condition prevents clearance; unresolved door coverage has its own message and does not change item completion. Departed rooms use a fresh-entry reconstruction with bounded native resets and supported event starts. Unsupported native effects and unresolved room conditions can still require reentry. Tracking rules outside the captured Mansion cases are source-derived candidates, not full-game gameplay validation.

Recurring room-script updates also participate in this calculation. The engine accounts for possible earlier main/event writes rather than assuming an old effect disappears when its trigger flag changes. Event writes that agree on an item's current state do not block tracking. A completed scripted award uses the game's pickup bit; an uncollected dormant award still needs its event conditions resolved. Script-disabled doors retain their markers and show as unavailable.

Audited setup commands now continue through the shared rules instead of creating false failure branches. Supported variable setters affect later comparisons within the same script pass. Temporary values from another room do not establish a past room's state. A reached command with unsupported effects or an invalid event target prevents clearance. Supported quantity changes preserve item identity and acquisition state. An uncertain amount alone does not prevent clearance; a quantity-dependent availability condition still needs resolution.

Run `python3 -m pytest -q tests/test_dynamic_quantities.py` for quantity reads/writes, zero amounts, source bounds, event dispatches, quantity-dependent conditions and acquisition reversal. Current-room observations read exact amounts from RAM. Reconstructed amounts use supported script values where available, or the explicit `unreconstructed` quantity state in the map JSON. The map can still name the item and show remaining/collected. RE1-QUANTITY-001/002 document the pinned native contracts and offline checks. Natural quantity changes and their normal-save/load behavior remain unvalidated.

# Shared-engine regression checks

Run `python3 -m pytest -q` with pytest installed. The focused engine suite is `python3 -m pytest -q tests/test_tracking_rules.py tests/test_event_tracking.py tests/test_command_semantics.py tests/test_room_cache.py`.

These checks cover multiple pickups, last-item clearance, acquisition rewind, story-dependent alternatives, dormant items, source selection, door replacement, unresolved branches, malformed metadata and reads that change during polling. The Herb and Chemical cases compare rules with the donated before/after RAM fixtures. Other flag changes in this suite are explicitly synthetic and do not validate a natural story event or normal in-game save/load.

Decoder alignment and operand bounds have a focused suite, `python3 -m pytest -q tests/test_native_decoding.py tests/test_scan_scd.py tests/test_scan_scd_widths.py`. It checks pickups and doors after native setup commands, overlapping operand reads, procedure/event boundaries and rejection of nonadvancing or null dispatches. These are source-format regressions, not gameplay tests.

Indexed-event flow has a focused suite, `python3 -m pytest -q tests/test_event_contract.py tests/test_scan_events.py tests/test_cache_metadata.py`. It checks shared wait/counter/call/loop depth, overlapping counter reads, deferred-command return paths, native termination and actor/motion packet boundaries. Unknown nonadvancing states and reads beyond the supplied section still reject coverage. These tests use synthetic packets and do not reproduce natural puzzle or story events.

Research entries RE1-ENGINE-001/002, RE1-SCD-007 through RE1-SCD-015, RE1-EVENT-003/004, RE1-VARS-001, RE1-SOURCE-002 and RE1-SELECT-001 describe the supported rules, evidence and remaining validation limits. Full map geometry remains limited to Mansion 1F even though the generated rule metadata covers other areas.

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
