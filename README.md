# re-map

A companion map for Resident Evil in DuckStation, showing explored rooms, remaining items and doors.

![Explored floors, remaining items and doors](docs/images/map.jpg)

## Setup

You need Python 3, DuckStation, your own BIOS and Resident Evil Director's Cut USA, SLUS-00551. Currently supports Jill using DuckStation savestates.

With DuckStation closed, add or update these settings in its `settings.ini`:

```ini
[Debug]
EnableGDBServer = true
GDBServerPort = 2345
```

The GDB server is built into DuckStation. You do not need to install or start a separate debugger.

## Play

1. Open DuckStation and start Jill's game or load a compatible savestate.
2. From the project folder, run:

   ```sh
   python3 tools/track.py --map
   ```

3. Open [the tracker map](http://127.0.0.1:8765/) in your browser.

Keep the terminal running while you play. Press Ctrl+C there to stop the tracker.

Rooms appear as you enter them. Red means items remain; blue means cleared. The white outline marks your current room. Click a room to see its items and doors.

Use **Floor** to browse explored floors. Click **Current room** to return to your location and follow it again.

Explored rooms are saved automatically and stay revealed after restarts or earlier savestate loads. Items and doors update to match the loaded game.

For a new playthrough, run `python3 tools/track.py --map --new-playthrough`. Use `--history-file <path>` to keep another playthrough separate.

If something goes wrong, report what happened and include `logs/tracker.log` from the project folder.
