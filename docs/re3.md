# Resident Evil 3

The first RE3 profile targets the supplied PlayStation release of Resident Evil 3: Nemesis, USA, SLUS-00923, in **Hard** mode. The user provided the owned disc under `~/Games` and selected Hard on 2026-11-05. The boot executable is `SLUS_009.23`; its exact fingerprint and runtime contracts belong in the research evidence.

Run the tracker with your owned disc:

```sh
python3 tools/track.py --profile profiles/re3_jill_hard_slus00923.json --disc "$HOME/Games/DuckStation/Resident Evil 3 - Nemesis.cue" --map
```

The tracker reads every room's scripts from the disc and evaluates them with the game's current flags, so visited rooms show remaining items, door access and clearance without unresolved checks; random item placements resolve once you have entered the room. The default history is `.local/re3-jill-hard-slus00923.json`. [RE3-EVAL-001](research/re3/script-evaluation.md#re3-eval-001-evaluate-re3-room-scripts-with-fresh-flags-for-a-runnable-tracker) records the method and limits.

The research below led to it. The [disc identity](research/re3/identity.md), [packaged room and map data](research/re3/room-format.md) and [isolated DuckStation observations](research/re3/runtime.md) have reproducible evidence. A [fresh Hard campaign test](research/re3/hard-start.md#re3-input-002-native-hard-selection-and-control-in-two-rooms) verified native selection, deliberate control in two rooms, their loaded-source bindings and earlier/later checkpoint restoration. A [native map comparison](research/re3/map-semantics.md#re3-map-004-native-room-remapping-and-position-projection) corroborates row selection and position projection in those two rooms. These sampled observations are confirmed for the named revision.

The [bounded Hard current-room reader](research/re3/live-reader.md) checks revision, mode, loading, source identity and pose through fresh guarded memory reads. Its Python API returns observations or explicit failures without updating exploration or completion. Its observations now feed the tracker above.

The [fresh map-position API](research/re3/live-reader.md#re3-live-002-fresh-native-map-position-under-current-room-guards) derives native group/row, numeric layer, projected coordinates and heading during that same guarded read. It uses the owned map resource and fresh world state because the map screen's cached row can be stale during gameplay. Numeric native layers do not establish tracker floors or room-owned outlines.

A [native collectible test](research/re3/collectibles.md#re3-collect-001-one-native-pickup-survives-reentry-and-reverses-with-saves) observed one inventory pickup setting its acquisition bit, ordinary reentry preserving it, and exact earlier/later saves reversing and restoring it. The [source-bound collectible API](research/re3/collectibles.md#re3-collect-002-one-fresh-registered-collectible-condition) reads one current registered packet's raw acquisition condition under the same guarded room transaction. Complete item lists and stronger collection/presence rules remain unresolved.

Use a separate revision profile and playthrough history. The intended tracker follows the existing [map behavior and controls](map-controls.md) and [collection-based room completion](room-completion.md). Game-derived item and door facts require fresh reads after savestate restoration.
