# Tracker diagnostics

[Documentation index](../README.md) · [Testing index](../testing.md)

## Diagnosing failures

File logging is enabled automatically. The terminal shows the absolute path to `logs/tracker.log`. To watch it in another terminal:

```sh
tail -f logs/tracker.log
```

The log retains startup details, room and item changes, state snapshots, read addresses and errors, unexpected exception traces, failed map requests, and browser errors reported while the map server is reachable. Unchanged tracker state is logged every 30 seconds. Successful browser polling is omitted.

Small state reads include hex values. Larger reads, including executable signature windows, include SHA256 hashes instead of game code bytes. Logs rotate at 2 MiB, retaining three previous files. The `logs/` directory is excluded from Git.

The log and its three backup paths must differ from the selected profile, exploration history and its writer lock, including symbolic and hard links. Startup rejects conflicts before opening any log output. An explicit `--history-file` protects that history; otherwise startup protects every built-in history path before loading the profile so profile errors can still be logged safely. Choose another `--log-file` when a conflict is reported.

To choose another path:

```sh
python3 tools/track.py --map --log-file /tmp/re-map-tracker.log
```

Reproduce the problem, then report what you did and when it happened so the corresponding entries can be inspected. If the tracker has exited, restart it before reproducing the problem.

Pausing DuckStation may produce a logged GDB stop notification; tracking continues after that notification. A timed-out or damaged debugger reply closes the connection to prevent later memory reads from using stale replies. The map keeps running and retries the GDB connection once per second. It clears completion colors and live item and door details until the game can be read again. Terminal-only tracking also reconnects after a dropped connection; it requires a connection at startup.

Browser state requests run one at a time so a delayed older reply cannot overwrite a newer pickup or room state. A request that stalls for two seconds, including while reading its response body, is cancelled. The map clears live verdicts, reports a connection interruption and retries automatically. The inspected room and chosen zoom/pan survive recovery on the same floor.

Run `bun tests/check_map_refresh_browser.mjs <python>` with Playwright available to check request ordering, stalled headers and bodies, late cancelled replies, automatic recovery and retained map inspection.

## Exploration history save failures

If writing or replacing the history file fails, the previous saved history remains intact. Losing write access to the history directory can also prevent temporary-file cleanup. The tracker reports a history error with the leftover temporary file's path. Restore directory access before restarting the tracker. Leftover temporary files are never loaded as exploration history.

Run the history regressions with the [test environment](../testing.md#python-test-environment):

```sh
python3 -m pytest -q tests/test_visit_history.py tests/test_track_log_safety.py tests/test_logging.py
```

These tests use temporary history files and cover invalid history, writer exclusion, failed writes and replacement, cleanup failure, retry and restored exploration. Logging checks cover aliases, rotation destinations, profile/lock preservation, new histories, default paths and malformed-profile tracebacks.

## Offline RE1 snapshots

Inspect a retained RE1 savestate without starting DuckStation:

```sh
python3 tools/extract_sav_ram.py input.sav /tmp/re1-ram.bin
python3 tools/track_offline.py /tmp/re1-ram.bin
```

The offline tracker uses the same revision, room-source, item and door checks as live tracking, defaulting to SLUS-00551 Jill. It prints the snapshot's current room and leaves exploration history untouched. The input must be an extracted 2 MiB RAM image. Wrong revisions, non-gameplay states and incoherent room snapshots return a diagnostic and a nonzero exit code.

Room and item metadata come from the profile; the old `--items` argument is no longer accepted. Use the [test environment](../testing.md#python-test-environment) for regressions:

```sh
python3 -m pytest -q tests/test_track_offline.py tests/test_live_items.py tests/test_rdt_global_id.py
```
