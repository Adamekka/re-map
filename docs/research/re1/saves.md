# RE1 saves research

[Documentation index](../../README.md) · [Claim index](../../research.md)

## RE1-SAVE-001: Chemical acquisition survives a normal in-game save and load

Status: Confirmed for this revision
Scope: Resident Evil Director's Cut USA, serial SLUS-00551, Training Jill, Chemical pickup in Mansion Storeroom Main 00 Sub 18
Environment: DuckStation 0.1-11894-gc66b2694d on macOS arm64, 2026-09-26; isolated portable copy with its own memory card and GDB server on port 2345. Disc executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`.
Authored: 2026-09-26; human user performed the in-game save and load; Codex with model GPT-6 Sol read GDB and recorded the result
Basis: runtime observation of a normal in-game save/load, live GDB reads, and inspection of the isolated memory card
Claim: after the Chemical was taken, saving at the room's typewriter, resetting, and loading through the game's Load Game menu preserved the collected state at PS1 virtual address `0x800C86DE` bit 2. The byte read `0xFB` after loading, matching the controlled after-pickup state, and inventory slot 6 still held item `0x26` (Chemical), quantity 1. The room read Main 00 Sub 18, camera 00, previous 1F. This confirms persistence through one normal in-game save/load for this flag on this revision; it does not establish full room item coverage or a cleared state.
Evidence: the controlled before-pickup fixture extracts to flag `0xFF`, inventory slot 6 `00 00`, room `00 18 01 0B`; the after-pickup fixture extracts to flag `0xFB`, inventory slot 6 `26 01`, room `00 18 01 0B` (RE1-PICKUP-003). The isolated DuckStation copy booted the after-pickup fixture. The human user saved at the typewriter, reset, loaded through Load Game, and reported control restored. A subsequent GDB read returned room `00 18 00 1F`, flag `0xFB`, and inventory bytes at `0x800C878E` `26 01`; the Ink Ribbon count changed from 6 in the fixture to 5 after the save. The new 131072-byte isolated memory card contained `BASLUS-005510` and had SHA256 `7323a3259f9d77e11a3ebae3f1985fff07f80a3aab8c0ff39bfb8ecaeeaa1c87`. The user's original `SLUS-00551_resume.sav` retained its prior modification time. The memory card and game files are outside Git.
Limits: the GDB read was taken after the user's report of a normal load, not during the game's save or load screens. The earlier normal-save case that should restore `0xFF` remains untested. The result confirms this flag's persistence, not that all RDT items use the same rule, that room completion can be inferred from one flag, or that another game revision shares this address.
History:
- 2026-09-26; human user; tested; saved to the isolated memory card, reset, loaded through the in-game menu, and reported completion.
- 2026-09-26; Codex with model GPT-6 Sol; tested and authored; compared the live GDB read with both controlled fixtures and inspected the isolated memory card, promoting only this normal-load behavior to Confirmed for this revision.

## RE1-SAVE-002: the normal-save payload includes the Herb acquisition byte

Status: Confirmed for this revision
Scope: Resident Evil Director's Cut USA SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`; one Training Jill Chemical-after normal save whose prior game state already had the Winding Passage Herb taken
Environment: pinned PS1 executable disassembly, controlled Chemical-after RAM capture, and the isolated DuckStation 0.1-11894-gc66b2694d memory card from RE1-SAVE-001, 2026-09-27
Authored: 2026-09-27; Codex with model GPT-6 Sol; subagent `/root/save_flag_serialization` with model GPT-6 Sol traced the copy path
Basis: executable save/load byte-copy instructions and a byte comparison of the normal-save card against controlled PS1 RAM
Claim: this normal-save path copies the 32 acquisition-flag bytes at PS1 virtual addresses `0x800C86DC..0x800C86FB` into the save payload. The Chemical-after card contains the full block, including Chemical byte `0xFB` at `0x800C86DE` and Herb byte `0xFE` at `0x800C86EA`. The executable also has a reverse card-buffer-to-RAM copy covering both bytes. This supports the Herb flag's inclusion in normal saves; a dedicated normal in-game Herb load has not been observed.
Evidence: the save branch at PS1 VA `0x80018988–0x800189B0` passes source `0x800C8660` and length `0x13C` to byte-copy routine `0x80057A64`, placing the flag block at relative offsets `0x7C..0x9B`, Chemical at `0x7E`, and Herb at `0x8A`. The branch then calls `0x80019DE8`, whose write path reaches BIOS B0 at `0x80019F0C`. The reverse branch at `0x80018ADC–0x80018B08` copies `0x240` bytes from the card buffer to `0x800C8660`, followed by state adjustment at `0x80019638`. In the isolated memory card with SHA256 `7323a3259f9d77e11a3ebae3f1985fff07f80a3aab8c0ff39bfb8ecaeeaa1c87`, file offset `0x2200` maps to the saved room bytes at RAM offset `0xC8660`, and the unique 32-byte match for the Chemical-after flag block starts at card offset `0x227C`. Card offset `0x228A` holds Herb byte `0xFE`. Of the `0x13C` copied bytes, 297 match the earlier Chemical-after RAM fixture; the other 19 differ between that capture and the later save, including camera and Ink Ribbon count.
Limits: the user-operated normal load in RE1-SAVE-001 directly checked Chemical byte `0xFB`, not the Herb byte. The title-screen Load Game caller into the reverse-copy branch was not fully traced. The reverse-copy instructions make Herb restoration the expected behavior for this path, but no separate Herb normal-load or earlier-save reversal test confirms it. The card is an isolated scratch artifact outside Git. No other executable revision was checked, and serialization says nothing about item availability or room completion.
History:
- 2026-09-26; human user; saved the Chemical-after state to the isolated memory card and loaded it through the game's menu (RE1-SAVE-001).
- 2026-09-27; Codex subagent `/root/save_flag_serialization` with model GPT-6 Sol; traced the save and reverse-copy routines in the pinned executable without a new gameplay test.
- 2026-09-27; Codex with model GPT-6 Sol; matched the card's flag block and byte positions against the controlled Chemical-after RAM and independently checked the copy routine and call sites.

## RE1-SAVE-003: Art Room map acquisition survives normal saves and reverses with an earlier save

Status: Confirmed for this revision
Scope: Resident Evil Director's Cut USA SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`; Training Jill, Art Room `00-07` Map, saves made and loaded in Main Hall `00-06`
Environment: isolated DuckStation `0.1-11894-gc66b2694d` on macOS arm64; native GDB at localhost port 2345; a newly created private shared memory card; coherent paused 2 MiB RAM captures; existing tracker at commit `67dd263`
Authored: 2026-10-06; Codex root; model: GPT-6.1 Sol
Basis: normal controller input, in-game typewriter saves, emulator restart followed by the game's Load Game menu, read-only GDB captures, memory-card inspection and existing-tracker replay
Claim: the Map acquisition bit from RE1-PICKUP-004 persists through normal saving/loading. Loading the earlier uncollected save after the collected save restores the set bit. The corresponding observed map-owned byte also reverses. No guest RAM writes, injected calls or patched game code were used.

Evidence:

1. Prepared the untouched Map scenario with private `art-map-before.sav` from RE1-EVENT-015. Left Art Room normally, took the Main Hall Ink Ribbon and used its typewriter to save to empty card slot 1. The game displayed `Jill /01/M.Hall 1F`. After the save returned to gameplay, Map byte `0x800C86ED` was `0xFF`, its bit 6 set, and map-owned byte lead `0x800C871C` was `0x00`.
2. Restarted the game using DuckStation's Restart Game action. Selected Load Game at the title screen and loaded card slot 1. After Jill returned to gameplay, captured RAM with the exact profile verified. Map byte remained `0xFF` and the ownership lead remained `0x00`.
3. Prepared the already-collected Map scenario with private `art-map-after.sav` from RE1-PICKUP-004. Descended the steps and left Art Room normally, took Main Hall Ink Ribbon and saved through the typewriter to empty card slot 2. Map byte was `0xBF`, its bit 6 clear, and the ownership lead was `0x08`.
4. Restarted again, selected the game's Load Game and loaded card slot 2. After return to gameplay, coherent RAM retained Map byte `0xBF` and ownership lead `0x08`.
5. Restarted a third time and loaded card slot 1 through Load Game. Gameplay RAM restored Map byte `0xFF` and ownership lead `0x00`. All three loaded captures identify current room `00-06`; Art Room Ink Ribbon byte `0x800C86E3` remains `0xFF` throughout.
6. The 131072-byte card contains separate directory entries `BASLUS-005510` and `BASLUS-005511` in blocks 1 and 2. Their acquisition blocks begin at file offsets `0x227C` and `0x427C`; Map bytes at `0x228D` and `0x428D` are `0xFF` and `0xBF`. Each 32-byte acquisition block matches its post-save and post-load RAM captures exactly. Block 1 remained byte-identical when slot 2 was written. These are card file offsets, not PS1 addresses. They agree with the payload-copy evidence in RE1-SAVE-002.
7. Replayed actual coherent captures through one profile/cache and tracker. Primed Art Room with its prior before/after captures, then supplied this test's normal loads in order: before, after, earlier before. Cached Map changed `taken -> available -> taken -> available` from fresh acquisition bytes while current room was Main Hall. Art Room Ink Ribbon stayed available with complete item/door coverage, so the room stayed `INCOMPLETE`. Only entered regions `07` and `06` were visible; ownership reversal revealed no extra room. The replay uses captured RAM without synthetic flag substitutions.

Artifacts outside Git at `/tmp/tasks/re-map/map-save-load/`:

| Artifact | SHA256 | Purpose |
| --- | --- | --- |
| `before-save-complete.bin` | `dd5292a01b4ac94c2f79f7b7a3952039f932f3d33bed967a6dc520356ad23edd` | Untouched Map after slot 1 save |
| `before-normal-load.bin` | `787b760543e7e5b807745671cce30fdac853565604b71f0c8054e356175770cf` | First normal load of slot 1 |
| `after-save-complete.bin` | `07fd3aba0c0e6a05b8bd9f31a498a969a373531e59dcfd00d7557f84be818616` | Collected Map after slot 2 save |
| `after-normal-load.bin` | `01f1e60a354e5d555f26a810cff94498d0902b7519bd668a1f80502e10008d4e` | Normal load of slot 2 |
| `earlier-normal-load.bin` | `a32890f93e76be8149122a2c6b8063ffa792f34bad8774ede006dd954c768a78` | Earlier slot 1 loaded after slot 2 |
| `before-only-card.mcd` | `0d9a76d4f834e46464e681956cebc2dfee1a848af264b4431c5627932563b2ea` | Card snapshot with slot 1 only |
| `both-saves-card.mcd` | `28734147c3547009d6da5290098beca6cc7500aa952e11d2eb1acede17d77761` | Card snapshot with both normal saves |

Limits: savestates prepared the two saving scenarios; every return under test used restart and the game's Load Game, with no DuckStation savestate return. GDB captures began after gameplay returned, so this does not test tracker reconnect behavior during boot/load screens or normal saving/loading of active events. The map-owned byte remains an observed lead rather than a new production address. Main Hall completion is still `UNKNOWN` after its ribbon is collected, including in the replay; this test confirms no Main Hall clearance or last-item clearance. Other characters, modes, revisions, map pickups and Chemical earlier-save reversal remain untested. The original RE1-SAVE-001/002 evidence and authorship are unchanged.
History:

- 2026-10-06; Codex root, GPT-6.1 Sol; performed both typewriter saves and all three normal loads, verified exact runtime identity, compared coherent RAM and private card blocks, and ran the persistent-cache replay. Closed the owned emulator normally with resume-save disabled and restored its private settings byte-for-byte. All RAM, cards, savestates and scratch navigation/audit scripts remain outside Git.
- 2026-10-06; Codex root, GPT-6.1 Sol; reviewed the documentation against all seven listed artifact hashes, the five-step capture replay, card comparisons and settings restoration. Those checks and `git diff --check` passed. No production code changed; the repository has no configured Markdown formatter or linter.

## RE1-SAVE-004: public memory card provides candidate later-area checkpoints

Status: Candidate, native save loading and later-area gameplay remain untested
Scope: intended target is Resident Evil Director's Cut NTSC-U SLUS-00551; downloaded save directory identifiers match that serial, but runtime compatibility is not yet established
Environment: isolated official DuckStation `0.1-11894-gc66b2694d`, owned SLUS-00551 disc, private shared memory card, read-only GDB localhost:2345
Authored: 2026-10-07; Codex root; model: GPT-6.1 Sol
Basis: public author's download, archive and memory-card inspection, native achievements settings, isolated disc boot log
Claim: the downloaded card contains native directory entries labeled Courtyard, Guardhouse and Laboratory. These are candidate starting points for validating RE1-MAP-005 and RE1-MAP-006's remaining floor plans without repeating Mansion progression. Directory labels alone do not establish loaded room identities or correct tracker behavior.

Source: [Tehppyd's save page](https://tehppyddistrict.blogspot.com/2017/12/resident-evil-directors-cut-dual-shock.html), with its public USA archive at [Google Drive](https://drive.google.com/file/d/1-B5iFXICLz1Qcca4cf6BfNEApk4GtAQR/view). The author describes compatibility with US Director's Cut versions and claims no cheats were used. Those are source claims, not independently reproduced findings. GameFAQs downloads were blocked by its browser challenge; that route was abandoned without bypassing the challenge.

Private artifacts under `/tmp/tasks/re-map/online-saves/`:

| Artifact | Bytes | SHA256 |
| --- | --- | --- |
| `tehppyd-usa.zip` | 17657 | `11f0cd0447a7674d18e7753ed630db8b595efa0fa6358eedafa21df9eb8f481d` |
| `SCEVMC0.mcd` | 131072 | `8a9d5c774f45584ec84d19af6fc4bc5cc28e75fb6afefd6772c8becb6b2e2236` |
| `SCEVMC1.mcd` | 131072 | `21bc80edfdcbdae68d2341256930413306997a3c46765ae9e20b8009b125db7a` |

The archive's folder is `SLUS00747`, but every occupied PS1 directory entry is named `BASLUS-00551` followed by a slot digit. Only its two 131200-byte VMP files were extracted. Each raw card is the exact 131072-byte payload after the 128-byte VMP header. The `MC` header and XOR checksums of the first sixteen frames were checked; no save identifiers or save blocks were edited. DuckStation's pinned [memory-card reader](https://github.com/stenzek/duckstation/blob/c66b2694da65cece8886ed3d4a069098831f8358/src/core/memory_card_image.cpp#L92) checks the raw card size in `LoadFromFile` and the `MC` signature in `IsValid`. Container extraction does not prove that RE1 can load a particular save.

Occupied entries on `SCEVMC1.mcd`, decoded from the directory titles:

| Native slot | File identifier | Character/mode label | Location label |
| --- | --- | --- | --- |
| 1 | `BASLUS-005510` | Chris Advanced | Guardhouse |
| 2 | `BASLUS-005511` | Chris Advanced | Laboratory |
| 3 | `BASLUS-005512` | Jill Original | Courtyard |
| 4 | `BASLUS-005513` | Chris Original | Laboratory |
| 5 | `BASLUS-005514` | Jill Advanced | Laboratory |

Safety/setup observations: before booting any game or loading a save, the isolated copy's native Achievements settings showed `Enable Achievements` unchecked, Hardcore disabled and `Not Logged In`. Its configuration also held `Achievements.Enabled = false`. The durable requirement is recorded in AGENTS.md. This test did not change the user's installed emulator settings or use an achievement account.

A separate `working-card.mcd` copy was mounted in the isolated instance, and the owned disc booted successfully according to DuckStation's log. Native window observation then repeatedly timed out, including after a control-session reset and a successful GDB interrupt/read/resume. No native Load Game selection or later-area gameplay was completed. This produces no new runtime map coverage. The failure is in the test's native window access; it does not establish a tracker defect or save incompatibility.

After boot, the working card differed at only `0x1F80`, `0x1F81` and `0x1FFF`, within its administrative block, with values `00 -> 4D`, `00 -> 43` and `00 -> 0E`. All fifteen save blocks, bytes `8192..131071`, were unchanged. The working card SHA256 became `478262def290e9c37bd6bcb7e6a2e75f94f394783e826715c36bee4bddac8a8e`; both original raw cards remain preserved. The exact isolated process was terminated after native access failed, and temporary card and controller settings were restored from their pre-test backup. Achievements remain disabled.

Reproduction for the pending test: with achievements disabled, mount a fresh copy of `SCEVMC1.mcd` as the isolated shared card, boot the owned SLUS-00551 disc, and use the game's Load Game menu to select slot 3, Jill Original / Courtyard. Verify the native character is controllable, check pinned executable signatures, and capture the actual Main/Sub/camera before evaluating the map. Start a fresh tracker and verify only the entered region is visible, then cross an adjacent room or floor normally and return. Other slots provide separate Laboratory and Guardhouse candidates. Their Original/Advanced and Jill/Chris scopes must be recorded independently of the previously tested Training Jill route.

Limits: no online checkpoint has been loaded through the game's menu, no new area has been entered, and no pickup, door, story condition or normal-save persistence behavior is validated by this setup. Save provenance and source claims are separate from tracker validation. Saves, archive contents and private scripts remain outside Git; production code and profiles are unchanged.
History:

- 2026-10-07; Codex root, GPT-6.1 Sol; obtained the public archive, extracted raw card payloads without changing saves, inspected directory labels, verified achievements were disabled before boot, recorded native-control failure and restored temporary settings. Manually reviewed this documentation; no external implementation review applies to this research-only change.
- 2026-10-08; Codex root, GPT-6.1 Sol; completed normal in-game loads from four entries with controllable characters and pinned runtime signatures. RE1-SAVE-005 records the successful follow-up; this entry preserves the earlier failed setup and its limits.

## RE1-SAVE-005: four public card entries load through the native game menu

Status: Confirmed for this revision and the four named entries; save origin, mode labels and normal-save persistence retain their limits
Scope: Resident Evil Director's Cut NTSC-U SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`; public `SCEVMC1.mcd` from RE1-SAVE-004
Environment: isolated official DuckStation `0.1-11894-gc66b2694d`, owned disc, separate native game window, temporary shared memory card, ordinary input through computer use and read-only GDB localhost:2345
Authored: 2026-10-08; Codex root; model: GPT-6.1 Sol
Basis: native Load Game selection, controllable characters, executable signature checks, captured Main/Sub/camera and exact save-block comparison
Claim: the public card provides usable later-area checkpoints on the pinned owned disc. These native saves were loaded through RE1's Load Game menu, rather than using downloaded emulator savestates or editing guest RAM.

| Card identifier | Native character | Initial Main/Sub | Observed location | First capture |
| --- | --- | --- | --- | --- |
| `BASLUS-005511` | Chris | `04-0e` | Laboratory B3 Save | `i-floor-1` |
| `BASLUS-005513` | Chris | `04-0e` | Laboratory B3 Save | `i-floor-5` |
| `BASLUS-005512` | Jill | `02-0e` | Courtyard B1 Save | `j-floor-1` |
| `BASLUS-005510` | Chris | `03-03` | Guardhouse 1F Save | `l-floor-1` |

RE1-MAP-012/013 preserve capture hashes, UTC times and gameplay results. Initial raw little-endian u32 values at PS1 virtual `0x800C3000` were respectively `0x90000000`, `0x50000000`, `0x50800000`, `0x90000000`. These words also change during room loading and status screens. The Original/Advanced directory labels in RE1-SAVE-004 remain source labels; this test does not independently establish their mode-bit meaning. Jill's native status displayed Poison; Chris's Guardhouse status displayed Fine. The Guardhouse inventory included a bonus Colt Python with an infinite-ammunition display, so this checkpoint is not evidence for fresh-game inventory behavior or the source author's no-cheats claim.

The follow-up used a separate render window, paused startup and a persistent GDB resume after boot. An automatic updater prompt was dismissed through the native UI. This setup permitted access after RE1-SAVE-004's timeout, but several setup conditions changed together, so no single cause is confirmed. One earlier boot process disappeared without a crash report; its cause is unresolved. Temporary controller bindings used Shift for aim and P for status. The isolated app was closed normally after the completed run, with Save State For Resume unchecked, then render, startup, card and controller settings were restored. The user's installed emulator was untouched.

Before loading any checkpoint, the isolated native Achievements settings showed Enable Achievements unchecked, Hardcore disabled and Not Logged In. `Achievements.Enabled = false` remained set through all restarts and cleanup. No achievement account was used.

Both original raw cards retain their RE1-SAVE-004 hashes. The working `working-card-paused.mcd` SHA256 is `478262def290e9c37bd6bcb7e6a2e75f94f394783e826715c36bee4bddac8a8e`. Its only differences from `SCEVMC1.mcd` are administrative bytes `0x1F80`, `0x1F81`, `0x1FFF`; all fifteen save blocks at offsets `8192..131071` are byte-identical. A new private DuckStation checkpoint was saved after the natural Guardhouse return, `m-guardhouse-return.sav`, 1599582 bytes, SHA256 `d0290deabf10fa9efa7bae80be3b71288b1bf16c05be1306b31dd19f97423249`. The native Save As dialog treated the entered absolute path as a filename containing colons in its previous folder; that agent-created file was renamed into the private evidence directory after checking the destination did not exist. This new checkpoint has not yet been loaded.

Reproduction: keep achievements disabled, mount a fresh private copy of RE1-SAVE-004's card, boot the owned disc and use Load Game to select the listed entry. Wait for gameplay, verify executable signatures and capture the runtime Main/Sub/camera before interpreting the area. Use ordinary door controls for RE1-MAP-012/013's routes. Do not reuse the poisoned Jill route without first preparing a viable health state through normal gameplay.

Limits: entry `BASLUS-005514` remains untested. Successful loads do not establish save provenance, every scenario, a new normal-save write, persistence of a newly changed pickup flag, or the safety of every later route. Archive/card/savestate data stay private outside Git.
History:

- 2026-10-08; Codex root, GPT-6.1 Sol; selected and loaded the four entries, verified native character control and pinned signatures, compared unchanged save blocks, retained a new checkpoint and restored the temporary isolated settings. RE1-SAVE-004 retains its original source and failed-setup evidence.
