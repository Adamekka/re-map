# RE2 DualShock

[Documentation index](../../README.md) · [Claim index](../../research.md) · [RE2 guide](../../re2.md)

## RE2-DS-001: Leon A DualShock revision port

Status: Candidate for USA Dual Shock Ver. Disc 1, SLUS-00748. Static extraction and synthetic regressions establish the profile contract; native observations are recorded separately below. Original-release gameplay is not DualShock validation.

Follow-up, 2026-10-27: the human subsequently authorized Claire B's DualShock port in [RE2-DS-002](#re2-ds-002-claire-b-dualshock-revision-port). The Leon observations below keep their original scope.

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

## RE2-DS-002: Claire B DualShock revision port

Status: Candidate for USA Dual Shock Ver. Disc 2, SLUS-00756. Native B-scenario startup, the first room publication, exact earlier/later restores and fresh history reconstruction are observed. Other room, item and door outcomes remain unvalidated on this revision.

### Scope and identity

On 2026-10-27, after the Leon migration, the human authorized porting Claire while they try Leon. This resumes the previously deferred Claire B scope. The selected setup remains Original/Normal with Casual/Softcore achievements and DuckStation savestates. Leon's running tracker, profile, exploration history and emulator are not replaced or used for agent tests.

Game: Resident Evil 2 Dual Shock Ver. USA Disc 2, serial SLUS-00756. `SYSTEM.CNF` boots `SLUS_007.56`, 987136 bytes, SHA256 `1664e7c634f8cfd03e421f10a6d7e8e8e9fa9bc7982f7c649cc86d28a983fbee`, loading `0xF0800` bytes at PS1 virtual `0x80010000`. MD5 of the executable name followed by the complete executable is `2e78f5817db6bb9dfb0208068d0801ce`, exactly the Disc 2 hash supplied by the human. This uses RE2-DS-001's cited identification method and does not validate every disc sector or an achievement unlock.

Runtime identity hashes four 32-byte code windows at `0x80054CAC`, `0x80054BBC`, `0x8005432C` and `0x80077318`, in that order. The concatenated hash is explicit in `profiles/re2_claire_b_slus00756.json`. They cover item creation, door creation, the script flag predicate and shared flag checking. The native capture matches this signature; full executable SHA256 separately binds the generated data.

### Audited revision layout

All addresses are PS1 virtual, little-endian. Integer masks apply to values after little-endian decoding. These are revision-specific addresses, not offsets to add indiscriminately to another profile.

| Field | Address | Width and mask |
| --- | --- | --- |
| Stage / room / camera | `0x800D47D4` / `0x800D47D6` / `0x800D47D8` | unsigned two bytes each, `0xFFFF` |
| Player/state block | `0x800CFB28` | 420 bytes |
| Save/state block | `0x800D468C` | 1792 bytes |
| System flags | `0x800CFB2C` | unsigned four bytes; gameplay `0x40000000`, demo `0x2000`, transition `0x02000000`, game over `0x04000000`, required mode mask/value `0x40` |
| Scenario/status flags | `0x800CFB90` | unsigned four bytes; `(value & 0xC2000000) == 0xC0000000` |
| Active player | `0x800CFBB0` | unsigned four bytes, active mask `1` |
| X / Y / Z | `0x800CFBE8` / `0x800CFBEC` / `0x800CFBF0` | signed four bytes each, `0xFFFFFFFF` |
| Facing | `0x800CFC26` | unsigned two bytes; angle mask `0x0FFF` |
| Floor | `0x800CFCB6` | unsigned one byte, `0xFF` |
| Loaded room pointer | `0x800CE2DC` | unsigned four bytes, `0xFFFFFFFF` |
| Interaction registry | `0x800CE510` | 32 unsigned four-byte pointers, `0xFFFFFFFF` each |
| Script counter range | `0x800D47A4` to `0x800D47EC`, exclusive | aligned signed two-byte values, `0xFFFF` |
| Native flag-bank table | `0x800A7884` | unsigned four-byte pointers, `0xFFFFFFFF` each |
| Early / late item banks | `0x800D4874` / `0x800D4894` | 32 / 16 bytes; word `id // 32`, mask `0x80000000 >> (id % 32)` |
| Door unlock bank | `0x800D49EC` | eight bytes; same native word/bit convention |
| Map table | `0x800AA9F4` | twenty eight-byte native descriptors |
| Area / region selectors | `0x8006E7A8` / `0x8006EAA0` | bounded native code entry points |
| Effect allocation pool | `0x800E8CA8` to `0x800EBB28`, exclusive | 96 slots, stride 124 bytes |

The script predicate independently locates the flag pointer table. Its configured banks are read from the supplied executable and checked by generation. The opcode dispatch table at `0x800A7484`, four-byte little-endian pointers, independently identifies ordinary/four-point creators, reset, flag write and counter write. Item creation reads the stage at `0x800D47D4`, selects item bank 8 before stage four and bank 34 afterward, and registers the original descriptor in the 32-slot registry. The shared flag helper retains descending masks within little-endian words. Ordinary item interaction at `0x8005185C` retains the system-mask `0x40`, type 30, amount-two override. These native-code findings retain Candidate status beyond the observed startup.

The map table is identified by all twenty descriptor tails and checked by executing both selectors over the requested B context and declared floor/story alternatives. The area selector explicitly reads floor `0x800CFCB6`. Conditional inputs are declared in the profile rather than borrowing Leon's scenario contexts. The effect allocator independently establishes its pool base, 124-byte stride and 96-slot bound. Relative to DualShock Leon, static tables move by `-0x44`, state fields by `-0x48`, and the selected code entries by either `-0x28` or `-0x48`. A single relocation delta is rejected.

Source labels and format leads retain the Starter Kit/biohazard-utils provenance in RE2-DS-001 and RE2-CLAIRE-001. The addresses above come from this owned executable's instructions/tables, not an assumed cross-disc address map. Private disassembly and lookup evidence are under `/tmp/re-map-dualshock-claire/`.

### Generated data and regressions

The supplied disc has 125 numbered `PL1/RDT` campaign files and a separate 125-source `A`–`G` corpus. All numbered files decode. The target reuses the existing explicit exclusion of the additional corpus; it does not extend script interpretation. Fifty-three whole campaign files match the original-release Claire catalog byte-for-byte. The original-release catalog includes decoded source `06-07` and unsupported source `06-05`; neither file is present on this disc. No empty replacement sources are invented.

Generate with:

```sh
python3 tools/build_re2_metadata.py \
  '/absolute/path/to/Resident Evil 2 - Dual Shock Ver. (Disc 2) (Claire).cue' \
  data/rooms_slus00756.json data/floor_plans_slus00756.json \
  --profile profiles/re2_claire_b_slus00756.json
```

A second complete generation matches both checked-in JSON documents byte-for-byte. They contain 125 sources and twenty map areas. These are offline extraction counts, not gameplay coverage. Original profiles and generated files remain unchanged. The new default history `.local/re2-claire-b-slus00756.json` is distinct from Leon and the original Claire release; history identity also binds revision signature and scenario. Production does not default to any test card or checkpoint.

Focused regressions pin Disc 2's executable/layout and B scenario, require distinct default history filenames, and run the existing zero-activation/collection/reversal cases against its generated metadata. B-scenario admission tests reject the other character/scenario combinations without changing visits or publication. No new game interpretation or UI behavior is introduced.

### Native validation and evidence

The isolated app uses official DuckStation `0.1-12442-gdd4a0eb77`, source commit `dd4a0eb779296a525f8b10b6d9a45911ad6d088f`, Interpreter mode, GDB port 2348. Before boot and both load preparations, both achievement integrations are disabled and no per-game overrides exist. Audio is muted and the black-only shader has RE2-DS-001's verified SHA256. A private copy of the native test card from ResidentEvilTim is loaded through Original data, selecting its sixth Claire B starter. Its source, unlocked-special-weapons limitation, original card SHA256 `69ad3a2e58cdc865d9d987ff2c635c500579152c30362e390fd9009d2b1cbb24` and block provenance remain as recorded in RE2-CLAIRE-001. The original fixture is unchanged. This verifies loading that one legacy fixture on DualShock; general save compatibility and ordinary memory-card persistence are not inferred.

Private savestate thumbnails are read by the existing Swift 6/Vision OCR helper, without emitting gameplay images. The native scenario-start sequence is advanced through controller input. There are no guest-memory writes, health/ammunition patches or position edits in this validation.

The accepted native source is `00-04`, with system flags `0x40000040`, status `0xC0000040`, active bit one and loaded RDT at `0x8011A728`. These values independently satisfy the new B-only gate and source binding. The production reader publishes Display, one visited source and one map outline, with Unknown completion because source coverage is incomplete. Native opening RAM SHA256 is `ac6493793d89b47bc8593dd43222cabcdd4273162fdb465da7eed4ece076b7e4`.

The first and later paused native F2 checkpoints are restored with native F1 after rechecking achievement isolation. Their complete 2 MiB RAM matches exactly:

| Checkpoint / restored capture | Native checkpoint SHA256 | Full RAM SHA256 |
| --- | --- | --- |
| `earlier-native-save` / `earlier-restored` | `44983282012152a113af3c8e851852832a47cb2b8b218866eba27e66cea44b3f` | `7157e1150f88d92579d51f2c78faf63b9e91992f6bf84cbbf6fc9883ef85abed` |
| `later-native-save` / `later-restored` | `ec8dfe3268308a7573f025bb1859f531d9971b1d8362404fef63ea1842dc3196` | `1d1fa9bceb66ca6eb0bf9eda4a5e86ceb34a44814288e3bd6d2af595bddbf79e` |

A five-capture visits-only history replay saves/closes/reopens the private history and reconstructs the same publication from each fresh RAM image. Exactly source `00-04` remains explored, and completion remains Unknown. This is not acquisition or unlock reversal. The actual CLI also passes `--once` against port 2348 using a private history. Both independent state captures, native restores, history replay, CLI logs and provenance are retained outside Git in `/tmp/re-map-dualshock-claire/`.

Only the private test emulator is terminated after validation. The agent does not replace or restart Leon's tracker, attach to its GDB port, or terminate the installed emulator. Agent visits are never written into a user playthrough history. No UI code or layout changes, so the README screenshot is retained.

Limits: one observed source. Native pickups, quantities, locked-door use, ordinary navigation, reentry, conditional floors, later rooms and campaign-wide clearance remain unvalidated on SLUS-00756. Original-release observations, byte-identical sources, synthetic tests and model advice do not promote those outcomes to Confirmed.

### Final verification and review

The focused profile/metadata/tracking/position/history/runner suite passes 924 tests in 8.36 seconds. Scoped Ruff formatting and E4/E7/E9/F checks pass, excluding the established module-path setup pattern E402. Local documentation links, JSON identity/schema loading, byte-identical regeneration and whitespace checks pass. The original Disc 1 and original-release profile/data files are unchanged.

Primary review finding 1; Configuration/DX, Low priority, Low difficulty: `profiles/re2_claire_b_slus00756.json`, `metadata_layout.selector_contexts`, copied original-release source `06-07`, absent from this disc. Removed that unused entry. Complete regeneration retains identical map/room outputs after the correction.

Primary review checks the complete registry/profile/test/documentation diff, generated metadata identity and deterministic output, B-only atomic admission, bounded field reads, distinct histories, source completeness, acquisition-versus-activation behavior, and native CLI/restore/history evidence. No verified defect remains in this port. There is no UI layout change; visual/UX/AX assessment is limited to the unchanged renderer contracts and serialized map publication, rather than a new browser screenshot.

The required external Opus review was requested through T3 as `claude-opus-5-5` with high effort and rejected before child creation with `provider_unavailable`: `Provider instance is disabled.` A subsequent capability check also reports Antigravity disabled, so the configured Gemini Flash perspective cannot run. No child review completed, no substitute model or CLI fallback was used, and no external endorsement is claimed. This is the same reported review limitation under which the human directed committing the preceding DualShock migration; the current change records that limitation separately from its direct verification and native evidence.

Contributions:

- 2026-10-27; human user; authorized the Claire port while preparing to try the Leon route. The existing Claire B and Original/Normal, Casual/Softcore scope is retained.
- 2026-10-27; Codex root, exact executing model `gpt-6.1-sol`; verified Disc 2's hash, audited its layout and code contracts, generated metadata, added profile/history/scenario regressions, performed hidden native admission/restores and CLI/history checks, reviewed the change and authored this record. External save authorship remains ResidentEvilTim's. Original-release authorship and validation are unchanged.

## RE2-DOOR-004: current slot selection and inactive door access

Status: Candidate for DualShock Leon A SLUS-00748. Retained publications and logs reproduce duplicate current creators; pinned code and synthetic tests establish the correction. No new gameplay observation confirms activation or passage. Original-release capture replay is recorded separately and does not confirm DualShock behavior.

The 2026-10-27 report concerns grey or incorrect doors during the user's playthrough. This pass incorporates the task-provided `current-variant.patch` and regression, then fixes the independently reproduced zero-activation defect. It changes only door interpretation and tests. Map geometry, symbols, interior geometry, generated metadata and user history are unchanged.

### Revision contract and defects

The requested revision is Resident Evil 2 Dual Shock Ver., USA Disc 1, Leon A, Original/Normal, SLUS-00748. Executable `SLUS_007.48` has SHA256 `e576348f64d015ecff6e1ce875a8924ee252ba7f3f9478b0917cbbdeb97db441`. [RE2-DS-001](#re2-ds-001-leon-a-dualshock-revision-port) records its full identity and prior DuckStation `0.1-12442-gdd4a0eb77` setup. This pass launches no emulator, loads no checkpoint and makes no guest-memory, settings or live-history writes. Retained captures keep their originating claims' emulator and assistance provenance.

1. A live interaction slot selects one source creator. The reader previously also published alternative door creators in that slot as Unchecked. The task-provided fix excludes these superseded current definitions after source, slot and geometry validation. An absent or untrusted current binding remains unresolved. Departed rooms retain their candidate uncertainty; the reader does not cache the previous variant choice.
2. A bound kind-one door with SAT zero previously reported Open or Locked from its lock payload. The reader now marks it inactive before interpreting access, retaining independently established unlock knowledge. A set key flag cannot activate the door. Reenabling SAT reconstructs the current lock result from fresh flags. Losing required four-point geometry remains unresolved rather than proving inactivity.

Addresses are PS1 virtual. The registry at `0x800CE558` contains 32 little-endian unsigned four-byte pointers, mask `0xFFFFFFFF`; the loaded-source pointer is at `0x800CE324`, with the same width and mask. Registry pointers address source offset plus two. Kind and SAT occupy descriptor offsets zero and one, unsigned bytes with masks `0xFF`; SAT bit `0x80` selects four-point geometry. Ordinary/four-point payloads begin at descriptor offsets 12/20. Target stage/room and lock ID/type are payload byte offsets 8/9 and 15/16. Byte order is immaterial for these byte fields. Fresh bank-31 unlock knowledge uses `0x800D4A34`, eight bytes, little-endian words and mask `0x80000000 >> (bit % 32)`, with bit index `lock_id & 0x3F` when lock ID bit `0x80` is set.

Owned executable inspection at `0x80054BE4..0x80054C4C` shows the door creator replacing its registry entry. The shared activation guard loads SAT at `0x80051160`, ANDs the caller mask at `0x80051168` and branches to the skip path `0x800514A4` when zero. The eight MIPS32 little-endian words at `0x80051160` have SHA256 `8e1b1b82dc8bc7efe4349d50fa81ec12f2f0470b5444275388cdbb5d26d35111`. This agrees with the original-release guard in [RE2-COLLECT-022](../re2.md#re2-collect-022-zero-activation-bytes-do-not-establish-availability). It is source inspection, not gameplay confirmation. Nonzero SAT masks and additional actor, floor, distance and scripted-dispatch conditions retain their existing limits.

### Reproduction and retained evidence

The supplied `/tmp/re-map-re2-door-positions-20261027/current-publication.json` contains only waiting/disconnected status, no current room and no rooms. It cannot validate a door. The same directory's `before-render.json` and `after-render.json`, plus retained tracker logs, show source `01-0a` publishing five current door candidates. Offsets 2178 and 2210 select slots zero and one, while superseded offsets 2090 and 2122 also appear grey. Selection now retains the three current doors, without changing the live Unlocked/Open results. The logs also reproduce alternative creators in other sources. These publication observations do not prove passage or source binding independently of the original reader.

Private offline evidence is under `/tmp/re-map-re2-door-state-20261027/`: `baseline/live_tracking.py`, `replay.py`, `capture-replay.json`, `log-door-observations.json` and `dualshock-activation-guard.asm`. Baseline is commit `2c1f8bf`; reader SHA256 is `4a8d231ef7ea2dc8930611114d134f415476bc874bfc2074256fa7b7968b2f0f`. Replay hashes and deduplicates retained full RAM, verifies each revision's runtime signature, and compares old/new results and tracker fields. No raw RAM or copyrighted source is added to Git.

| Revision | Unique captures / Display | Removed superseded door observations | Zero-SAT corrections |
| --- | --- | --- | --- |
| Leon A SLUS-00421 | 279 / 266 | 158 | 5 |
| Claire B SLUS-00592 | 94 / 88 | 42 | 0 |
| Leon A SLUS-00748 | 7 / 3 | 0 | 0 |
| Claire B SLUS-00756 | 3 / 3 | 0 | 0 |

All 383 result statuses/messages and all item, completion, pose, map and visit fields agree. Changes are limited to the selected door list, zero-SAT access and derived door coverage. The five zero-SAT corrections are door observations across three original-release captures, not five independent captures. They are retained in `/tmp/re-map-re2-third-variant-native-20261023/native/`: `alternate-connection-verified.ram`, SHA256 `6d2d60208db648629f6cd489541c83c31b7712dc680834726807bf49561bb4e5`; `alternate-transition-result.ram`, `e2728702220813974e92ce9ac82ae2b66aa6ed99adbc0a0010e5245f6421218d`; and `alternate-lower-entry.ram`, `72210889bbceaa714de05bf2a033f15523d021c59852d05d0cd9eef0cb84fab6`. Their selected descriptors have kind/SAT bytes `01 00`. No new denied interaction is observed. The six unique Display captures across the two DualShock profiles are unchanged opening states, not validation of the user's current rooms.

### Tests, review and limits

Run `python3 -m pytest -q tests/test_re2_profile.py tests/test_re2_metadata.py tests/test_re2_tracking.py tests/test_re2_position.py tests/test_visit_history.py tests/test_logging.py tests/test_re2_door_layout.py`. All 980 tests pass. New door regressions cover creator replacement and reversal across all four profiles, absent bindings, departed uncertainty with fresh unlock reversal, zero-SAT disabling/reenabling, fresh trackers, untrusted geometry, and atomic rejection when registry or SAT changes during a read. The zero-SAT tests failed against the preceding reader and pass with the fix. Scoped Ruff formatting and E4/E7/E9/F checks pass with the repository's established E402 exclusion.

Primary final review checked slot/source binding, mutable lock payloads, zero-SAT precedence, geometry rejection, fresh flag interpretation, departed uncertainty, coherent publication, scoped changes and retained-capture differences. No further verified defect remains within this increment. UI/UX/AX assessment is limited to the unchanged publication/renderer contract; no browser or live-emulator check is claimed. Required external Claude and Gemini review providers are disabled in T3, as reported by the coordinating task. Neither review ran; no replacement provider or CLI fallback was used, and there is no external endorsement.

Remaining limits include unresolved departed activation and scenario alternatives, nonzero activation-mask interpretation, direct script dispatch, and native validation of current DualShock doors. Earlier passage never becomes cached Open knowledge. No new room coverage, native unlock lifecycle, normal memory-card persistence or campaign readiness is claimed. The README screenshot is retained because no UI code or geometry changes.

Contributions:

- 2026-10-27; coordinating task; supplied the current-slot diagnosis, patch, regression and retained publication paths, and required offline-only work without emulator access.
- 2026-10-27; implementation sub-agent, exact executing model `gpt-6.1-sol`, verified in session `01a17f15-f420-7511-ba71-e950442b5d2a`'s latest `turn_context`; incorporated the supplied fix, reproduced and corrected zero-SAT access, added regressions, replayed retained captures, performed the primary review and wrote this record. No new native gameplay experiment was performed.
