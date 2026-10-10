# RE1 reproduction saves

These files preserve existing test checkpoints and the user's RE1 saves. The user approved keeping both DuckStation savestates and in-game saves in Git on 2026-10-10. Copies are byte-identical to their sources; duplicate files have one copy.

[manifest.json](manifest.json) lists every file's SHA256, size, source and related research finding. It also includes the four pickup savestates already kept in the parent fixture directory. Research IDs refer to [research.md](../../../docs/research.md). Archiving these files does not add new gameplay validation.

## Savestates

Use Resident Evil Director's Cut USA, SLUS-00551, with your own disc and BIOS.

| Directory | Checkpoints |
| --- | --- |
| `savestates/art-map/` | Jill before and after collecting the Art Room Map |
| `savestates/event-activation/` | Earlier opening and interaction tests |
| `savestates/mansion/` | Jill after the Terrace Bazooka grant |
| `savestates/later-areas/` | Guardhouse, Laboratory and Mansion basement validation |
| `savestates/user/` | User slot 1, slot 9 and resume saves |

The recorded agent-test build is DuckStation `0.1-11894-gc66b2694d`. Those savestates have format version 87. The creating build for the user checkpoints was not recorded; slot 1 has format version 83, while slot 9 and resume have version 87. Matching a format version does not prove compatibility. The manifest labels these limits per file.

Some later-area checkpoints contain Chris because earlier map experiments used him. The tracker delivery target remains Jill. Later-area tests used the temporary health lock described in RE1-CHEAT-003; individual patch notes are in the manifest. Repeat the recorded cheat setup when validating those patched routes.

Follow [the isolated DuckStation startup guide](../../../docs/duckstation-startup.md), keep RetroAchievements disabled, and pass the chosen checkpoint to `-statefile`. For example, from the repository root:

```sh
state_file="$PWD/tests/fixtures/re1/savestates/art-map/art-map-positioned-before.sav"
"$duckstation_bin" -nogui -batch -statefile "$state_file" "$disc_file"
```

The guide defines `duckstation_bin` and `disc_file`. Launching a checkpoint still requires a compatible emulator build.

## In-game saves

`memory-cards/art-map/` contains the earlier save, both before/after saves, and the later working-card snapshot from the Art Room experiment.

`memory-cards/online/` contains the public cards from [Tehppyd](https://tehppyddistrict.blogspot.com/2017/12/resident-evil-directors-cut-dual-shock.html) and the working copy used in later-area tests. RE1-SAVE-004 records their source and directory labels; RE1-SAVE-005 records the initial successful loads. The cards contain both Jill and Chris saves. Keep the source attribution with these files.

Copy a card into the isolated emulator's writable test directory, select that copy as its memory card, and load it through the game's Load Game menu. Use working copies so testing does not change the committed fixtures.

## Tracker history

Savestates and memory cards contain game state. They do not contain the external tracker's explored-room history. No matching history snapshot was retained for these older checkpoints.

Use `--history-file` with a separate test history. Add `--new-playthrough` when the test requires an empty explored map. For future bug reports, retain the matching history file and tracker log alongside the game checkpoint.
