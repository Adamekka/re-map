# Room completion

In RE1, known puzzle items keep an explored room incomplete until the game records their collection, even before the puzzle is solved. The same rule applies while the player is in the room and after departure. The user explicitly chose this behavior for all puzzle items on 2026-10-17 after reporting Armor Room's gray state.

The map answers whether the room's required items have been collected. Whether a pickup interaction is currently active is a separate fact. A dormant puzzle reward remains listed under Remaining items. Once the pickup flag confirms collection, that item stops blocking completion, even after it is used or removed from inventory.

Use fresh game state after every load. Restoring an earlier state where the item was not collected makes it remaining again. Never preserve a cleared verdict solely because a later save previously showed collection.

Only established items count. The current scenario and source rules must establish the item's identity and acquisition flag. Items established as absent do not block completion. Unresolved identity, conflicting scenario alternatives and unsupported source effects remain explicit gaps; being visited never makes a room cleared. A known remaining item makes the room incomplete even when other item checks are unresolved.

This policy does not reveal rooms the player has not entered. Doors, enemies, files and unrelated puzzle steps are separate from item collection.

Implementation evidence and validation limits are indexed under [RE1 research](research.md). The Sun Crest case validates the shared rule; it does not receive an item-specific exception.
