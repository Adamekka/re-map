# Tracker diagnostics

[Documentation index](../README.md) · [Testing index](../testing.md)

## Diagnosing failures

File logging is enabled automatically. The terminal shows the absolute path to `logs/tracker.log`. To watch it in another terminal:

```sh
tail -f logs/tracker.log
```

The log retains startup details, room and item changes, state snapshots, read addresses and errors, unexpected exception traces, failed map requests, and browser errors reported while the map server is reachable. Unchanged tracker state is logged every 30 seconds. Successful browser polling is omitted.

Small state reads include hex values. Larger reads, including executable signature windows, include SHA256 hashes instead of game code bytes. Logs rotate at 2 MiB, retaining three previous files. The `logs/` directory is excluded from Git.

The log and its three backups must use separate paths from the selected profile, exploration history, writer lock, and the supplied RE3 CUE and its referenced tracks. History and lock paths must also be separate from the profile and disc. Startup checks symbolic and hard links before opening any output. With `--history-file` it checks that history and lock. Otherwise it checks all built-in history and lock paths. If startup reports a conflict, choose a different path for the affected output.

Startup reports an unreadable CUE or a directory in any log rotation slot in the terminal before opening the log.

To choose another path:

```sh
python3 tools/track.py --map --log-file /tmp/re-map-tracker.log
```

Reproduce the problem, then report what you did and when it happened so the corresponding entries can be inspected. If the tracker has exited, restart it before reproducing the problem.

Pausing DuckStation may produce a logged GDB stop notification; tracking continues after that notification. A timed-out or damaged debugger reply closes the connection to prevent later memory reads from using stale replies. The map keeps running and retries the GDB connection once per second. It clears completion colors and live item and door details until the game can be read again. Terminal-only tracking also reconnects after a dropped connection; it requires a connection at startup.

Browser state requests run one at a time so a delayed older reply cannot overwrite a newer pickup or room state. A request that stalls for two seconds, including while reading its response body, is cancelled. The map clears live verdicts, reports a connection interruption and retries automatically. The inspected room and chosen zoom/pan survive recovery on the same floor.

Run `bun tests/check_map_refresh_browser.mjs <python>` with Playwright available to check request ordering, stalled headers and bodies, late cancelled replies, automatic recovery and retained map inspection.

## Exploration history save failures

The tracker reserves the `.lock` suffix for its writer locks. If you previously saved exploration to a file with that suffix, stop all trackers, rename the history to a filename ending in `.json`, and use that path with `--history-file`.

If startup rejects a symbolic link at your history's lock path, stop all trackers, move the `.lock` link aside, and restart with your original history path. The tracker creates a new lock and resumes from the saved history.

If writing or replacing the history file fails, the previous saved history remains intact. Losing write access to the history directory can also prevent temporary-file cleanup. The tracker reports a history error with the leftover temporary file's path. Restore directory access before restarting the tracker. Leftover temporary files are never loaded as exploration history.

Run the history regressions with the [test environment](../testing.md#python-test-environment):

```sh
python3 -m pytest -q tests/test_visit_history.py tests/test_track_log_safety.py tests/test_logging.py
```

These tests use temporary history files and cover invalid history, writer exclusion, failed writes and replacement, cleanup failure, retry and restored exploration. Logging checks cover aliases, rotation destinations, profile and lock preservation, and startup errors. Missing and malformed profiles report the path and cause. Unexpected failures retain a traceback in the log.

## Offline snapshots

Inspect a retained RE1 savestate without starting DuckStation:

```sh
python3 tools/extract_sav_ram.py input.sav /tmp/re1-ram.bin
python3 tools/track_offline.py /tmp/re1-ram.bin
```

The extractor replaces the RAM image atomically and needs write access to its output directory.

The offline tracker uses the same revision, room-source, item and door checks as live tracking. It defaults to SLUS-00551 Jill. For RE2 and RE3, pass the exact profile matching the capture. RE3 also needs the owned disc CUE for its room sources.

```sh
python3 tools/track_offline.py /tmp/re2-ram.bin --profile profiles/re2_leon_a_slus00748.json
python3 tools/track_offline.py /tmp/re3-ram.bin --profile profiles/re3_jill_hard_slus00923.json \
  --disc "/path/to/Resident Evil 3 - Nemesis.cue"
```

The tool reads one extracted 2 MiB RAM image. It prints the current room and each known item's name and collection state using the same terminal view as live tracking. Exploration history stays untouched. Wrong revisions, non-gameplay states and incoherent snapshots return a diagnostic and a nonzero exit code.

Use the [test environment](../testing.md#python-test-environment) for regressions.

```sh
python3 -m pytest -q tests/test_track_offline.py tests/test_live_items.py tests/test_rdt_global_id.py
```
