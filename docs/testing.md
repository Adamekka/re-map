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

Research entries RE1-ENGINE-001/002, RE1-SCD-007, RE1-VARS-001, RE1-SOURCE-002 and RE1-SELECT-001 describe the supported rules, evidence and remaining validation limits. Full map geometry remains limited to Mansion 1F even though the generated rule metadata covers other areas.

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
