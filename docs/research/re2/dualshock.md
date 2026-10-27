# RE2 DualShock

[Documentation index](../../README.md) · [Claim index](../../research.md) · [RE2 guide](../../re2.md)

## RE2-DS-001: Leon A DualShock revision port

Status: Candidate for USA Dual Shock Ver. Disc 1, SLUS-00748. Static extraction and synthetic regressions establish the profile contract; native observations are recorded separately below. Original-release gameplay is not DualShock validation.

### Target and identity

The human requested the DualShock edition and supplied the expected hashes on 2026-10-27. The selected setup is Leon A, Original Game on Normal difficulty, Casual/Softcore achievements and DuckStation savestates. The later instruction limits this migration to Leon; Claire is deferred even though Disc 2 is available.

Game: Resident Evil 2 Dual Shock Ver. USA Disc 1, serial SLUS-00748. `SYSTEM.CNF` boots `SLUS_007.48`. The executable is 987136 bytes, SHA256 `e576348f64d015ecff6e1ce875a8924ee252ba7f3f9478b0917cbbdeb97db441`, loading `0xF0800` bytes at PS1 virtual `0x80010000`.

The supplied CUE's extracted executable produces RetroAchievements hash `33df147cc40901c4f96e4e9328cc9218`, exactly matching the human's screenshot for [set 11245](https://retroachievements.org/game/11245). Reproduce with MD5 of the executable name `SLUS_007.48` followed by its complete bytes. This follows the official [PlayStation identification method](https://docs.retroachievements.org/developer-docs/game-identification.html#sony); it is not a full-disc MD5 or an achievement-unlock test. The expected Disc 2 hash supplied by the human is `2e78f5817db6bb9dfb0208068d0801ce`; this migration does not validate it.

Runtime identity hashes four 32-byte windows, in order, at PS1 virtual `0x80054CD4`, `0x80054BE4`, `0x80054354` and `0x80077360`. The configured SHA256 is recorded in `profiles/re2_leon_a_slus00748.json`. Extract each window at executable offset `0x800 + address - 0x80010000`. These cover ordinary item creation, door creation, the script flag predicate and shared flag test. Failed/short reads and an identity mismatch remain explicit failures.

### Revision contracts

All addresses below are PS1 virtual addresses, little-endian. They are not host addresses or raw RAM offsets. Unsigned fields use their full width unless a mask is stated.

| Field | Address | Width and mask |
| --- | --- | --- |
| Stage, room, camera | `0x800D481C`, `0x800D481E`, `0x800D4820` | two bytes each, `0xFFFF` |
| Initial player/state block | `0x800CFB70` | 420 bytes |
| Save/state block | `0x800D46D4` | 1792 bytes |
| System flags | `0x800CFB74` | four bytes; gameplay `0x40000000`, demo `0x2000`, transition `0x02000000`, game over `0x04000000`, required mode `0x40` |
| Scenario/status flags | `0x800CFBD8` | four bytes; required `(value & 0xC2000000) == 0` |
| Player active | `0x800CFBF8` | four bytes; mask `1` |
| Position X/Y/Z | `0x800CFC30`, `0x800CFC34`, `0x800CFC38` | signed four-byte values, `0xFFFFFFFF` |
| Facing | `0x800CFC6E` | two bytes; angle mask `0x0FFF` |
| Floor | `0x800CFCFE` | one byte, `0xFF` |
| Loaded room pointer | `0x800CE324` | four bytes, `0xFFFFFFFF` |
| Interaction pointer table | `0x800CE558` | 32 four-byte pointers, `0xFFFFFFFF` each |
| Script counter origin and permitted limit | `0x800D47EC` to `0x800D4834`, exclusive | aligned signed two-byte counters, `0xFFFF` |
| Native script flag-bank pointer table | `0x800A78C8` | four bytes per pointer, `0xFFFFFFFF` |
| Early/late acquisition banks | `0x800D48BC`, `0x800D48DC` | 32/16 bytes, little-endian words; bit `0x80000000 >> (id % 32)` at word `id // 32` |
| Door unlock bank | `0x800D4A34` | eight bytes; same word/bit convention |
| Map table and selectors | `0x800AAA38`, `0x8006E7F0`, `0x8006EAE8` | native table plus bounded selector entry points |
| Effect allocation region | `0x800E8CF0` to `0x800EBB70`, exclusive | byte region used for bounded exclusion/write proofs |

The complete flag-bank addresses and conditional selector inputs are explicit in the revision profile. The generator checks each declared bank against the owned executable's pointer table. Relative to the original release, system flags and the interaction registry move by `0x7E90`, while status, pose and save fields move by `0x7ED4`. A single relocation delta is rejected. The wider initial block includes DualShock's inserted fields and retains pose/floor within one bounded read.

Source leads: Megan Grass's [Starter Kit at 447bc6cc5388bf943616f54d50e5c20781003b71](https://github.com/MeganGrass/Resident-Evil-2-Starter-Kit/tree/447bc6cc5388bf943616f54d50e5c20781003b71), `source/assembly/directive.s`, `source/bio2/data.h` and `source/bio2/bio2.h`. These provide labels and structure leads; the supplied executable independently supplies the table values and instructions. Disassembly includes ordinary and four-point creators, reset, flag check/write, counter write, item interaction, door interaction, effect allocator and both map selectors. Ordinary pickup handling at `0x80051884` retains the native system-mask `0x40`, item-type 30, amount-two override. The shared flag helper at `0x80077360` retains descending masks within little-endian words. Static agreement is not gameplay confirmation.

The disc contains 125 numbered campaign room sources and a separate 125-source `A`–`G` corpus. Only numbered sources are generated for this profile. The revision target explicitly permits excluding those additional filenames; unrelated unexpected files still fail generation. New or unsupported script behavior remains unresolved under the existing bounded interpreter. Fifty-seven complete numbered room files match the original catalog byte-for-byte; this does not transfer runtime coverage for any room.

Generate with:

```sh
python3 tools/build_re2_metadata.py \
  '/absolute/path/to/Resident Evil 2 - Dual Shock Ver. (Disc 1) (Leon).cue' \
  data/rooms_slus00748.json data/floor_plans_slus00748.json \
  --profile profiles/re2_leon_a_slus00748.json
```

Generation produces 125 campaign sources and 20 map areas. These are offline counts, not gameplay readiness. The original-release profiles, catalogs and history filenames remain unchanged. DualShock defaults to `.local/re2-leon-a-slus00748.json`; history identity also includes its profile and runtime signature. Item/door state is reread instead of migrated from original-release caches.

### Validation and limits

The isolated test app is official DuckStation `0.1-12442-gdd4a0eb77`, source commit `dd4a0eb779296a525f8b10b6d9a45911ad6d088f`, GDB port 2347. Both achievements integrations are explicitly disabled, per-game overrides are absent, the first boot uses None/None cards, audio is muted and the black-only shader has SHA256 `f48b078181657e930272201ee01c82f1e14903ae0ed5196f10061ab3e76a382b`. Private setup and evidence stay under `/tmp/re-map-dualshock/`. User settings, saves and histories are not altered.

Native validation on 2026-10-27:

- The startup menu was read from private savestate thumbnails through a temporary Swift 6/Vision OCR helper, following the Swift skill. No game screenshot was emitted. The configured black display was verified. Initial cardless menu attempts and attract playback are excluded as campaign gameplay. A second isolated boot uses a newly created blank test card and selects Original Game, then Normal. RetroAchievements remains disabled.
- The first controllable campaign state at source `00-00` has system flags `0x40020040`, active bit one and a matching source. The production reader publishes Display, one explored source and its floor outline. Completion remains Unknown because source coverage is incomplete. This is one entered source, not broad campaign or item/door validation. Raw RAM SHA256 `4536cd0cd2a8b5e5d041d9dd4a309602046a908e8e3aa58c17554f17520e6544` is private in `native-opening.ram`.
- Private earlier/later checkpoints in that source exercise native F1 restores. The earlier RAM hash is `833e9edb9feb16812f0465f46d6ec3d33378eab37f1d8fda0aabf15d44146577`; the later hash is `757d0c79d7bbe7e7d592942053f511bcde8885b59486852595a2ea04ab0be808`. Both native restores are compared against their complete 2 MiB reference RAM. This checks exact savestate restoration and fresh tracker reconstruction, not normal memory-card persistence or acquisition/unlock reversal.
- Between those states, the isolated setup set the signed 16-bit player health at `0x800CFD4E`, mask `0xFFFF`, to 32767 and attempted recorded position/facing writes using the pose addresses above and prior/collision candidates. `writes.jsonl` retains every address, previous bytes and written bytes. The attempted door interaction did not leave the source, so it is excluded as a successful passage or pickup observation. These setup writes do not establish the candidate collision-field semantics. No acquisition, door-unlock or story flags were changed, and no ammunition patch was used.

The actual production CLI also passes `--once` over GDB port 2347 with the new profile and a private history file, publishing source `00-00` as Unknown. The earlier/later RAM pairs are byte-identical. A visits-only history replay rebuilds each publication from the corresponding fresh RAM. The isolated emulator is then terminated. The user's tracker is started with the DualShock profile on the normal GDB port 2345 and HTTP port 8765; it waits for the user to launch their game, with no agent test visits in its history.

Limits: only the opening source has accepted native campaign publication. Pickups, puzzle rewards, locked doors, room reentry, later floors, other scenarios and Arrange/Easy settings still need DualShock observations. Their existing shared interpreter behavior and synthetic tests are retained without relabeling original-release gameplay as confirmation.

`tests/test_re2_profile.py` guards the executable identity, separate system/status relocation, acquisition/key banks, widened initial block and independent default history. Shared tracking regressions now also exercise DualShock metadata for zero-activation presence, collection and reversal. These are synthetic observations. The focused RE2/profile/position/history/runner suite passes 909 tests. Scoped Ruff formatting and E4/E7/E9/F checks pass, excluding the existing module-path setup pattern E402. Default Ruff additionally reports pre-existing I001 import ordering and SIM102 nested-condition findings outside the changed lines; those unrelated findings are left unchanged. This count does not establish native item/door outcomes or broad playthrough readiness.

Hardcore compatibility is outside the selected setup: DuckStation's pinned [`Settings::ApplySettingRestrictions`](https://github.com/stenzek/duckstation/blob/dd4a0eb779296a525f8b10b6d9a45911ad6d088f/src/core/settings.cpp#L1274) disables GDB when Hardcore is active. The user explicitly selected Casual/Softcore.

Independent review limitation: T3's provider capability result reports Claude and Antigravity disabled, so the configured Claude Opus and Gemini Flash perspectives are unavailable. No replacement provider or CLI fallback is used. An unavailable review supplies no endorsement. After these review and pre-existing lint limitations were reported, the human directed committing the migration on 2026-10-27. No external review is claimed.

Contributions:

- 2026-10-27; human user; supplied the desired edition, exact hash screenshot, Disc 1 and mode/achievement selections, then limited the immediate migration to Leon.
- 2026-10-27; human user; directed committing the migration after the unavailable external reviews and unchanged pre-existing lint findings were reported.
- 2026-10-27; Codex root, exact executing model `gpt-6.1-sol`; verified the disc hash, audited revision layouts and native code, generated metadata, added profile/history isolation and synthetic regressions, and authored this record. Original-release research authorship and validation remain unchanged.
