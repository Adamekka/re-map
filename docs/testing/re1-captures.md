# RE1 event capture procedures

[Documentation index](../README.md) · [Testing index](../testing.md)

## Capturing live event observations

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
