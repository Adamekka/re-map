# Running the live tracker

Use DuckStation with the tested RE1 Director's Cut USA disc, SLUS-00551. Enable its GDB server on port 2345, then boot the game and load a playable room.

From the repository directory:

```sh
python3 tools/track.py --map
```

Open http://127.0.0.1:8765 and leave the terminal running. Stop with Ctrl+C.

The Mansion 1F floor plan reveals rooms only when the tracker observes entry. Collecting an in-game map does not reveal extra rooms. Red rooms have available items remaining, blue rooms are cleared, and the white outline marks the current room. Select an explored room to see its items and directional door locks. Visit history belongs to this tracker session and resets on restart. Other areas show the room ID.

The shared RE1 engine reevaluates entered rooms from fresh acquisition, story and door flags. Supported script conditions can change an earlier room's items or doors without reentry, including after an earlier save or savestate is loaded. An unresolved item condition prevents clearance; unresolved door coverage has its own message and does not change item completion. Event-driven changes and conditions that depend on another room's temporary state can still require reentry. Tracking rules outside the captured Mansion cases are source-derived candidates, not full-game gameplay validation.

Recurring room-script updates also participate in this calculation. The engine accounts for possible earlier main/event writes rather than assuming an old effect disappears when its trigger flag changes. Event writes that agree on an item's current state do not block tracking. A completed scripted award uses the game's pickup bit; an uncollected dormant award still needs its event conditions resolved. Script-disabled doors retain their markers and show as unavailable.

Audited setup commands now continue through the shared rules instead of creating false failure branches. Supported variable setters affect later comparisons within the same script pass. Temporary values from another room do not establish a past room's state. A reached command with unsupported effects or an invalid event target prevents clearance. Quantity reads preserve item coverage; commands that change a pickup's quantity still need live observation.

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

The suite covers shared script aliases, initialized frame pointers, guarded starts, transitive starts, callbacks, explicit read failures, source bounds, stops and snapshot reversal. Active records and reversal in these tests are synthetic. A limited live attract-mode experiment bound registered interactions, including a trigger linked to a Map slot in room `00-07`, but captured no active event. Natural start/stop, puzzle changes and normal save/load remain unvalidated. RE1-EVENT-005 through RE1-EVENT-008 record these limits. Event activity never grants acquisition or proves earlier execution.

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
