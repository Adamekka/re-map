# Resident Evil 2

The approved target is Leon A on the owned USA Disc 1, SLUS-00421, pinned by the executable identity in [RE2-IDENTITY-001](research/re2.md#re2-identity-001-leon-a-disc-identity-and-candidate-room-layout). DuckStation savestates are the restore mechanism.

Match the existing tracker behavior: spatial floor plans revealed by entering rooms, room names, actual facing, floor browsing, zoom and pan, persistent exploration isolated by game/revision/scenario/playthrough, remaining items, separate unresolved checks, game-derived door access, and fresh item/door/story state after savestate changes. Exploration survives earlier savestates; acquired items and unlocked doors must rewind with the game.

The current RE2 candidate implementation uses availability-based completion. An available uncollected collectible makes a room incomplete. Clearance requires a resolved full list with no available uncollected item. Unresolved conditions remain unknown. Missing scenario items and dormant future pickups do not block clearance once their conditions are established. The newer [RE1 puzzle-item collection policy](room-completion.md) has not been validated for this RE2 profile.

Run the tracker while Leon A is playing:

```sh
python3 tools/track.py --profile profiles/re2_leon_a_slus00421.json --history-file .local/re2-leon-a.json --map
```

RE2 defaults to `.local/re2-leon-a.json`; RE1 keeps `.local/visit-history.json`. Use a separate history file for each playthrough. Add `--new-playthrough` to reset that history explicitly. The normal DuckStation GDB setup is the same as RE1. See the [startup guide](duckstation-startup.md).

The runner now reads the pinned RE2 revision, reveals native floor outlines on entry, reads player yaw, and uses the shared map controls and remaining-item overview. A source-specific interaction ID binds each door observation to its wall marker. Native acquisition and key flags are reread after loads and on every poll; exploration accumulates separately.

This is an initial implementation with candidate rules, not a completed gameplay audit. The catalog covers 125 Leon room sources and 20 native map areas offline. Runtime coverage is limited to the opening street. Inactive descriptors establish dormant items; a missing descriptor does not establish scenario absence. Event-awarded collectibles and inactive items whose conditions are not yet understood remain unresolved. Departed rooms refresh acquisition and unlock flags. Unresolved availability and door activation remain Unknown; known unlocks still appear in door labels. Numeric door placement and the yaw conversion still need gameplay checks beyond the opening. Unsupported or mismatched room reads publish no new visits.

The catalog and floor plans contain numeric metadata and contours, not original game pixels or executable bytes. To regenerate them from the pinned owned disc, install `unicorn` in a development environment and run:

```sh
python3 tools/build_re2_metadata.py '/path/to/Resident Evil 2 (USA) (Disc 1).cue' data/rooms_slus00421.json data/floor_plans_slus00421.json
```

Runtime evidence and limitations belong in [RE2 research](research/re2.md). Source inspection, generated room counts and synthetic regressions do not confirm gameplay behavior.
