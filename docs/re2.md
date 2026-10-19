# Resident Evil 2

The approved target is Leon A on the owned USA Disc 1, SLUS-00421, pinned by the executable identity in [RE2-IDENTITY-001](research/re2.md#re2-identity-001-leon-a-disc-identity-and-candidate-room-layout). DuckStation savestates are the restore mechanism.

Match the existing tracker behavior: spatial floor plans revealed by entering rooms, room names, actual facing, floor browsing, zoom and pan, persistent exploration isolated by game/revision/scenario/playthrough, remaining items, separate unresolved checks, game-derived door access, and fresh item/door/story state after savestate changes. Exploration survives earlier savestates; acquired items and unlocked doors must rewind with the game.

RE2 follows the shared [collection-based completion policy](room-completion.md). An available collectible or source-established uncollected item keeps its explored room incomplete, including before activation and after departure. Clearance requires a resolved full list with nothing remaining. An inactive pointer or catalog candidate alone does not establish an item; unsupported conditions and conflicting identities remain unknown. The bounded source proof covers audited startup paths. [RE2-COLLECT-001](research/re2.md#re2-collect-001-source-established-items-remain-until-collected) records the initial implementation and its limits. [RE2-COLLECT-002](research/re2.md#re2-collect-002-conflicting-slots-preserve-unrelated-item-proofs) preserves proofs for unrelated items when another slot has conflicting definitions. [RE2-COLLECT-003](research/re2.md#re2-collect-003-scripted-activation-preserves-collection-identity) extends the proof through audited actor setup, automatic task scheduling and matching interaction resets. Seventeen relevant collectible identities now have source proofs. This count describes offline interpretation, not gameplay coverage.

Run the tracker while Leon A is playing:

```sh
python3 tools/track.py --profile profiles/re2_leon_a_slus00421.json --history-file .local/re2-leon-a.json --map
```

RE2 defaults to `.local/re2-leon-a.json`; RE1 keeps `.local/visit-history.json`. Use a separate history file for each playthrough. Add `--new-playthrough` to reset that history explicitly. The normal DuckStation GDB setup is the same as RE1. See the [startup guide](duckstation-startup.md).

The runner now reads the pinned RE2 revision, reveals native floor outlines on entry, reads player yaw, and uses the shared map controls and remaining-item overview. A source-specific interaction ID binds each door observation to its wall marker. Native acquisition and key flags are reread after loads and on every poll; exploration accumulates separately.

This is an initial implementation with candidate rules, not a completed gameplay audit. The catalog covers 125 Leon room sources and 20 native map areas offline. Runtime captures now cover nineteen room sources, including the controlled door cases in [RE2-DOOR-002](research/re2.md#re2-door-002-named-key-use-and-savestate-reversal) and [RE2-DOOR-001](research/re2.md#re2-door-001-event-driven-unlock-and-savestate-reversal). [RE2-LIVE-002](research/re2.md#re2-live-002-gun-shop-ammunition-and-savestate-reversal) records the two shop ammunition pickups. [RE2-LIVE-003](research/re2.md#re2-live-003-controlled-route-pickups-and-reentry) adds three ammunition pickups, position-assisted door transitions, reentry and earlier/later restores. These controlled interaction checks do not establish an uninterrupted route using ordinary navigation. A separate history-file round trip preserved the nine captured room and map-region visits while reconstructing item state from fresh captures.

Inactive descriptors can contain overwritten item fields; a missing descriptor establishes neither presence nor scenario absence. Event-awarded collectibles and items without a collection proof remain unresolved. Departed rooms refresh acquisition and unlock flags. Source-established items use fresh collection flags independently of activation. Unresolved identities and door activation remain Unknown; known unlocks still appear in door labels. One scripted reward now has captured activation, collection, departure, reentry and earlier/later restore checks in RE2-COLLECT-003. RE2-DOOR-001 verifies one event-driven door unlock, paired passage, reentry and earlier/later unlock reversal. RE2-DOOR-002 verifies one named-key pickup/use, passage, reentry and earlier/later restores. Carrying the key alone leaves its door locked. Other scripted rewards, other key locks, one-sided unlock operations, numeric door placement and the yaw conversion still need gameplay checks. Unsupported or mismatched room reads publish no new visits.

The catalog and floor plans contain numeric metadata and contours, not original game pixels or executable bytes. To regenerate them from the pinned owned disc, install `unicorn` in a development environment and run:

```sh
python3 tools/build_re2_metadata.py '/path/to/Resident Evil 2 (USA) (Disc 1).cue' data/rooms_slus00421.json data/floor_plans_slus00421.json
```

Runtime evidence and limitations belong in [RE2 research](research/re2.md). Source inspection, generated room counts and synthetic regressions do not confirm gameplay behavior.
