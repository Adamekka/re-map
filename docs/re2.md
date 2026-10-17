# Resident Evil 2

The approved target is Leon A on the owned USA Disc 1, SLUS-00421, pinned by the executable identity in [RE2-IDENTITY-001](research.md#re2-identity-001-leon-a-disc-identity-and-candidate-room-layout). DuckStation savestates are the restore mechanism.

Match the existing tracker behavior: spatial floor plans revealed by entering rooms, room names, actual facing, floor browsing, zoom and pan, persistent exploration isolated by game/revision/scenario/playthrough, remaining items, separate unresolved checks, game-derived door access, and fresh item/door/story state after savestate changes. Exploration survives earlier savestates; acquired items and unlocked doors must rewind with the game.

Room completion follows the existing rules. An available uncollected collectible makes a room incomplete. Clearance requires a resolved full list with no available uncollected item. Unresolved conditions remain unknown. Missing scenario items and dormant future pickups do not block clearance once their conditions are established.

The first code increment supplies identity and raw room reading only. The player-facing runner still supports RE1. RE2 gameplay, maps and completion are not yet available. Runtime evidence and limitations belong in [research.md](research.md); source inspection and synthetic tests do not confirm gameplay behavior.
