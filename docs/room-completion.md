# Room completion

In RE1 and RE2, known puzzle items keep an explored room incomplete until the game records their collection, even before the puzzle is solved. The same rule applies while the player is in the room and after departure. The user explicitly chose this behavior for all RE1 puzzle items on 2026-10-17 and approved extending collection-based completion to RE2 on 2026-10-18. Each profile must establish the item's identity and presence; this policy does not turn an unproven catalog candidate into a required item.

The map answers whether the room's required items have been collected. Whether a pickup interaction is currently active is a separate fact. A dormant puzzle reward remains listed under Remaining items. Once the pickup flag confirms collection, that item stops blocking completion, even after it is used or removed from inventory.

Use fresh game state after every load. Restoring an earlier state where the item was not collected makes it remaining again. Never preserve a cleared verdict solely because a later save previously showed collection.

Only established items count. The current scenario and source rules must establish the item's identity and acquisition flag. Items established as absent do not block completion. Unresolved identity, conflicting scenario alternatives and unsupported source effects remain explicit gaps; being visited never makes a room cleared. A known remaining item makes the room incomplete even when other item checks are unresolved.

This policy does not reveal rooms the player has not entered. Doors, enemies, files and unrelated puzzle steps are separate from item collection.

Implementation evidence and validation limits are indexed in [Research](research.md). RE1's Sun Crest case validates the shared rule without an item-specific exception. [RE2-COLLECT-001](research/re2.md#re2-collect-001-source-established-items-remain-until-collected) records RE2's bounded source proofs, unchanged-capture replay and remaining gameplay limits.
