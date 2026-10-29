# Tracker diagnostics

[Documentation index](../README.md) · [Testing index](../testing.md)

## Diagnosing failures

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

Browser state requests run one at a time so a delayed older reply cannot overwrite a newer pickup or room state. A request that stalls for two seconds, including while reading its response body, is cancelled. The map clears live verdicts, reports a connection interruption and retries automatically. The inspected room and chosen zoom/pan survive recovery on the same floor.

Run `bun tests/check_map_refresh_browser.mjs <python>` with Playwright available to check request ordering, stalled headers and bodies, late cancelled replies, automatic recovery and retained map inspection.
