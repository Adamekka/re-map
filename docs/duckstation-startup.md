# Starting DuckStation from a terminal

This guide is for Muse or another agent with shell access and no computer-use tools. It uses the existing project setup and recorded commands. No new emulator research or startup test was performed for this guide.

DuckStation supplies the GDB server. The Python tracker connects to it; there is no separate `gdb` program to start. Launching the emulator from a shell does not require automating its UI. It still opens a native game window.

The tested combination is Resident Evil Director's Cut USA, **SLUS-00551**, and the isolated DuckStation **0.1-11894-gc66b2694d** used in the research notes. Other emulator builds and game revisions are not interchangeable validation environments.

The current delivery target is Jill using DuckStation savestates. Chris support and normal in-game memory-card save/load are outside the requirements.

The tracker is for the user's personal playthrough. Prioritize useful tracking and fix encountered problems using logs and savestates. A full campaign played by an agent is not required before the user starts playing.

## 1. Select the existing isolated copy

Use a prepared portable test copy, with its own settings, BIOS, memory cards and savestates. The installed app at `/Applications/DuckStation.app` is a reference location, not the test instance. Do not change the user's installed emulator settings or cards.

Earlier private setups and checkpoints were kept under `/private/tmp/re-map-*` and `/tmp/tasks/re-map/`. These temporary files may have disappeared. Find an existing test directory and identify its executable and effective `settings.ini`; do not assume the first matching file belongs to the emulator you will launch.

Set these variables to actual paths. The placeholder paths are intentionally not runnable:

```sh
cd /Users/adamekka/Coding/re-map

duckstation_bin='/absolute/path/to/isolated/DuckStation'
settings_file='/absolute/path/to/that/copy/settings.ini'
disc_file='/absolute/path/under/your/Games/directory/to/RE1.cue'
run_dir="$(mktemp -d /tmp/re-map-muse.XXXXXX)"

test -x "$duckstation_bin" || { echo 'Missing DuckStation executable'; exit 1; }
test -f "$settings_file" || { echo 'Missing isolated settings.ini'; exit 1; }
test -f "$disc_file" || { echo 'Missing owned disc CUE'; exit 1; }
```

Use the owned SLUS-00551 CUE under the user's Games directory, with its referenced BIN files present. A savestate is not a replacement for the disc and BIOS. On macOS, an app bundle's executable is normally at `DuckStation.app/Contents/MacOS/DuckStation`; a prepared standalone test directory may contain `DuckStation` directly.

If no prepared isolated copy remains, prepare one with a separate data directory before booting. Check that copy's `-help` output for its available launch options. Do not silently switch to the user's installed configuration. This guide does not prescribe an unverified portable-directory layout.

## 2. Enable GDB and disable achievements before boot

Edit only the selected isolated copy's configuration while that copy is closed. DuckStation may overwrite settings edited while it is running.

The required settings are:

```ini
[Debug]
EnableGDBServer = true
GDBServerPort = 2345

[Achievements]
Enabled = false
```

Merge these keys into the existing sections; do not append duplicate sections. Keep the isolated copy logged out of RetroAchievements and free of account credentials. Check its per-game configuration as well, so it cannot override the disabled setting. Verify this before loading any game, card or savestate.

Check whether another process already owns the GDB port:

```sh
lsof -nP -iTCP:2345 -sTCP:LISTEN
```

An empty result before launch is expected. If there is a listener, identify it first. Do not kill another emulator or attach to an unidentified instance. Stop your own tracker/capture client before using a different GDB client.

## 3. Launch the game directly

Run the executable itself, with quoted absolute paths:

```sh
"$duckstation_bin" -nogui -batch "$disc_file" \
  > "$run_dir/duckstation.log" 2>&1 &
duckstation_pid=$!
echo "DuckStation PID: $duckstation_pid"
echo "Log: $run_dir/duckstation.log"
```

`-nogui` skips the main launcher window; it does not mean there is no game render window. `-batch` runs the selected game without leaving the launcher open afterward. Do not wait for a browser tab or a computer-use connection before launching.

For an existing compatible DuckStation checkpoint, use this command **instead of** the preceding launch:

```sh
state_file='/absolute/path/to/a/compatible/SLUS-00551-checkpoint.sav'
test -f "$state_file" || { echo 'Missing checkpoint'; exit 1; }

"$duckstation_bin" -nogui -batch -statefile "$state_file" "$disc_file" \
  > "$run_dir/duckstation.log" 2>&1 &
duckstation_pid=$!
```

Keep the copy's BIOS and memory-card paths valid. Existing private checkpoints include `r-laboratory-b2.sav`, `u-powerroom-start.sav` and `y-basement-return.sav`; their existence and compatibility must be checked locally. Some contain the documented temporary health patch. Record enabled patches when using them for validation.

Loading a DuckStation checkpoint checks savestate restoration. It does not count as saving and loading through RE1's own menus.

## 4. Check the process and listener

```sh
ps -p "$duckstation_pid" -o pid=,command=
lsof -nP -a -p "$duckstation_pid" -iTCP:2345 -sTCP:LISTEN
tail -n 60 "$run_dir/duckstation.log"
```

Wait for boot to establish the listener. The listener must belong to the PID you launched. If the process exits or the listener never appears, inspect the log for the concrete failure: disc or BIOS paths, state compatibility, a port conflict, or settings loaded from the wrong directory. Also inspect the isolated data directory's emulator log if the redirected output is empty.

Avoid using a throwaway TCP connection as a readiness probe. DuckStation pauses on GDB attachment; a probe can change emulator state without reading anything.

## 5. Resume a paused boot or checkpoint

Attaching GDB pauses emulation. A checkpoint created while GDB was attached can also restore paused. This can look like a frozen boot or load.

With other GDB clients stopped, resume through the project's existing client:

```sh
PYTHONPATH=src python3 - <<'PY'
from emulator.duckstation_gdb import DuckStationGdb

gdb = DuckStationGdb(port=2345)
error = gdb.connect()
if error:
    raise SystemExit(error)
try:
    error = gdb.resume()
    if error:
        raise SystemExit(error)
    print('Resume sent to DuckStation')
finally:
    gdb.close()
PY
```

Use the framed client rather than ad hoc socket reads. Continue sends `c` and has no memory-data reply; later stop notifications are separate packets. For controlled RAM captures, use the client's interrupt/read/resume sequence and resume in cleanup.

GDB provides debugger operations, not controller input. Shell startup and loading a checkpoint work without computer use. Selecting New Game, operating doors and making a normal in-game save require a separate input method. OS keyboard injection still needs the native window focused and macOS permissions; a successful GDB connection does not supply those.

## 6. Attach the tracker after gameplay is ready

Once the character is controllable, first check the selected profile:

```sh
python3 tools/track.py --once --host 127.0.0.1 --port 2345 \
  --log-file "$run_dir/tracker-smoke.log" --history-file "$run_dir/visits.json"
```

Expect the pinned profile to be verified and a current room to be reported. A socket connection alone does not prove the correct game is running. Read any profile or source-rejection diagnostic before treating the room state as valid.

Then start the live map:

```sh
python3 tools/track.py --map --host 127.0.0.1 --port 2345 \
  --log-file "$run_dir/tracker.log" --history-file "$run_dir/visits.json"
```

The map is served at `http://127.0.0.1:8765/`. Muse can inspect the terminal and log without opening a browser. Keep the tracker terminal running and use Ctrl+C to stop it. Exploration resumes from the selected history file across restarts. Add `--new-playthrough` if the experiment requires fresh visits. Always use the isolated run's history file so agent tests do not alter the user's exploration.

The lifecycle gate now suppresses visits in the tested title and attract-mode states, as recorded in RE1-LIFECYCLE-002/003. Start a gameplay validation run after character control returns so its initial state is clear. Jill's gameplay menus, cutscenes and death/game-over phases remain unvalidated.

## Troubleshooting and cleanup

| Symptom | Next action |
| --- | --- |
| No GDB listener | Check process, effective isolated settings, boot errors and port ownership. |
| Window looks frozen after attach/load | Stop competing clients and send resume through `DuckStationGdb`. |
| Read timeout or damaged reply | Close the failed client, inspect the log and reconnect; do not reuse stale replies. |
| Keys do nothing | Check focus, actual controller bindings and OS input permissions. GDB is not controller input. |
| Tracker sees the wrong game | Check the CUE, checkpoint and runtime profile diagnostic. |
| Map page fails | Check the tracker process and its log, including a possible HTTP port conflict. |

Stop your own tracker or capture process before closing the emulator. For a shell-launched emulator, terminate only the recorded PID, after deciding whether any unsaved test progress needs preserving:

```sh
kill -TERM "$duckstation_pid"
```

Keep logs, RAM, discs, BIOS, cards and checkpoints outside Git. See [testing.md](testing.md) for the existing capture commands and validation routes, and research entries RE1-AUTO-001, RE1-EMU-007/008 and RE1-SAVE-005 for the recorded launch, debugger and load behavior.
