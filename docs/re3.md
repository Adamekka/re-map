# Resident Evil 3

The first RE3 profile targets the supplied PlayStation release of Resident Evil 3: Nemesis, USA, SLUS-00923, in **Hard** mode. The user provided the owned disc under `~/Games` and selected Hard on 2026-11-05. The boot executable is `SLUS_009.23`; its exact fingerprint and runtime contracts belong in the research evidence.

RE3 support is under investigation. The [disc identity](research/re3/identity.md), [packaged room and map data](research/re3/room-format.md) and [isolated DuckStation observations](research/re3/runtime.md) have reproducible evidence. A [fresh Hard campaign test](research/re3/hard-start.md#re3-input-002-native-hard-selection-and-control-in-two-rooms) verified native selection, deliberate control in two rooms, their loaded-source bindings and earlier/later checkpoint restoration. A [native map comparison](research/re3/map-semantics.md#re3-map-004-native-room-remapping-and-position-projection) corroborates row selection and position projection in those two rooms. These sampled observations are confirmed for the named revision.

The [bounded Hard current-room reader](research/re3/live-reader.md) checks revision, mode, loading, source identity and pose through fresh guarded memory reads. Its Python API returns observations or explicit failures without updating exploration or completion. Item/door state, physical floor identity and room contours remain unresolved, so there is no runnable tracking profile yet.

The [fresh map-position API](research/re3/live-reader.md#re3-live-002-fresh-native-map-position-under-current-room-guards) derives native group/row, numeric layer, projected coordinates and heading during that same guarded read. It uses the owned map resource and fresh world state because the map screen's cached row can be stale during gameplay. Numeric native layers do not establish tracker floors or room-owned outlines.

Use a separate revision profile and playthrough history. The intended tracker follows the existing [map behavior and controls](map-controls.md) and [collection-based room completion](room-completion.md). Game-derived item and door facts require fresh reads after savestate restoration.
