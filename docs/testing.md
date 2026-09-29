# Running the live tracker

Use DuckStation with the tested RE1 Director's Cut USA disc, SLUS-00551. Enable its GDB server on port 2345, then boot the game and load a playable room.

From the repository directory:

```sh
python3 tools/track.py --map
```

Open http://127.0.0.1:8765 and leave the terminal running. Stop with Ctrl+C.

The Mansion 1F floor plan reveals rooms only when the tracker observes entry. Collecting an in-game map does not reveal extra rooms. Red rooms have available items remaining, blue rooms are cleared, and the white outline marks the current room. Select an explored room to see its items and directional door locks. Visit history belongs to this tracker session and resets on restart. Other areas show the room ID. Some puzzle rooms need reentry after their conditions change; an incomplete item check stays visible until the tracker can verify it.

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
