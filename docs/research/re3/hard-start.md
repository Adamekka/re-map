# RE3 Hard startup and control

[RE3 scope](../../re3.md) · [Original runtime baseline](runtime.md) · [Native lifecycle candidates](native-contracts.md)

## RE3-INPUT-001: targeted paused-menu input remains insufficient to verify Hard

Status: Candidate historical input procedure. This interrupted experiment did not verify Hard selection, campaign control or room reentry. Its evidence remains available without inheriting an unsupported success claim.

This is the historical attempt. [RE3-INPUT-002](#re3-input-002-native-hard-selection-and-control-in-two-rooms) supplies later positive selection/control evidence. Ordinary reentry remains unverified.

The target is Resident Evil 3: Nemesis, PlayStation, USA, SLUS-00923. The separately extracted `SLUS_009.23` SHA256 is `2e143418e358b2c99995cdc1a88c387163fb751912c723b755614f38e236bd29`. The private DuckStation is `0.1-12083-g00e299795`, executable SHA256 `5c879677051cfb173002df22baee741c96fa8071c6fe1dd7e5454092bf128173`. No interpretation is generalized to another revision.

### Changed method and isolation

The previous attempt could not verify menu selection and had allowed plausible no-input player states. This attempt used a new private portable application under `/tmp/re-map-re3-hard-20261105-fauot2qm/`, a separately checked port 2354 and pause-on-start. It paused the guest with its own F5 hotkey while analyzing native checkpoint thumbnails through private OCR, then resumed for deliberate inputs. This changed the earlier slow-menu procedure; it did not force guest state.

The private setup copied the application and owned BIOS only. It created fresh settings, memory-card paths, checkpoints and resource directories. Both card slots were `None`. Achievements were disabled in both `Achievements` and `Cheevos`, account keys were absent, per-game overrides were absent and `ApplyGameSettings=false`. Audio was muted. The original `private-black` shader loaded in the private instance; no gameplay image is published. Native logs and private window checks retain the presentation evidence. No tracker or user exploration history was opened.

The private controller used `DigitalController`. Cross/Circle were F6/F7. Six built-in macros held Cross, Start, Up, Down, Left and Right on F11 through F16, with toggle enabled, frequency zero and pressure 1.0. These are host controller bindings; no guest-memory patch, forced pose/room/difficulty, health/ammunition aid or game-file change was used. F2 created native private checkpoints, and F5 paused/resumed the identified application. The exact input calls remain in the failed run's activity and private files; they do not establish that a requested controller action reached a particular campaign state.

### Accepted observations and limits

The first retained RAM sample has all four disc-derived code windows equal to RE3-RUNTIME-001. Its candidate player fields remain zero. Later native checkpoint OCR produced memory-card-choice text and then `LOAD GAME` title-menu text. No accepted frame or state observation shows Hard selected, a campaign started, controlled translation/turning or ordinary room departure/reentry. Private filenames such as `cardless-choice` and `menu-2` describe capture attempts, not verified transitions.

OCR remained unreliable: several checkpoint images produced no text, and preprocessing variants did not establish a readable Hard choice. Repeating those same button attempts without a new state witness would add no accepted gameplay evidence. A next experiment should use the new native source/lifecycle audit to check each captured state, verify an actual difficulty selection and controlled input, and keep title/demo rejection separate from room-source matching. Neither the presence nor absence of the recorded-input bit alone admits gameplay.

The delegated run stopped when the workspace reported exhausted credits. It had made no repository changes or commits, and its private game process remained open. The parent recovered the evidence, matched PID 93709's complete command to `game-pid.json`, independently checked its `127.0.0.1:2354` listener, and sent SIGTERM to that PID only. Subsequent process and port checks confirmed it exited and port 2354 was free. `cleanup-parent.json` records this cleanup. No installed or user emulator process was stopped.

### Evidence and reproduction boundary

The private directory contains `prepare.py`, `control.py`, `identity.json`, `game-pid.json`, `bios-pid.json`, launch logs, preboot settings, the account/override audit, checkpoints, private thumbnail/OCR files and cleanup evidence. `control.py` asserts exact process and listener ownership before GDB access. Its `audit` command checks disabled achievements in both sections, absent account keys/overrides, muted audio, black postprocessing and private card settings. These temporary scripts refer to that experiment's original checkout and directory. A new run requires explicit path updates and fresh process/port checks.

| Private evidence | Bytes | SHA256 |
| --- | ---: | --- |
| `prepare.py` | 3468 | `73b3ec9cd33861fbe415e5b01d3c9e7d300547f29938ecf85c3a620ee21113e2` |
| `control.py` | 5034 | `d40d85dae31437259995854281c9fad4ab3691ad4795f58e0b5abe7836442f56` |
| `settings-preboot.ini` | 1365 | `19b8b188a40cca757cbcf73d5a015e14236d87d47cb5b676ef2c8718aa377379` |
| `settings-macros-preboot.ini` | 2123 | `019d722f6af577838b5ccc3f84da7400fa877c6b1e0e90152256c5b93b3c8465` |
| `boot-10sec.ram` | 2097152 | `90bd063fef1158ebcc83d1fc5cda0f5c8aae5bf5ce3a96fe87d67ed3fd243da3` |
| `startup.sav` | 18703 | `3f70e88d3b1ff05ec0a5f8dcc2f30b63ec58dffceedcd6749c75a11ca40588c0` |
| `cardless-choice.sav` | 998399 | `c0aad34e8b37a9df16f42985bb905a39ab3a515d5067aa2dd1974e8f5dfb97ed` |
| `menu-2.sav` | 1175842 | `80b513356ddd861d4a0153c86643dbe0c08ea9e35748bb4ec7023d15d4fec703` |
| `cleanup-parent.json` | 242 | `d89a8a3ef381c7f3b12296e510720248cde0ee371fc363cefb26d7fb33189464` |

Raw RAM, saves, disc/BIOS/executable bytes and image thumbnails remain private and are not committed. Temporary evidence may disappear; these hashes do not replace it. Native checkpoint operations do not prove memory-card persistence or a valid Hard campaign.

### Contributions and review

- 2026-11-05; human user; supplied owned media, authorized parallel research and selected Hard.
- 2026-11-05; implementation delegate, `gpt-6.1-sol` verified from returned run metadata; prepared the private instance, checked identity/isolation, performed native hotkey/menu attempts and retained private evidence. The run failed for exhausted workspace credits before final cleanup or documentation.
- 2026-11-05; Codex root, exact runtime model `gpt-6.1-sol`; recovered the failed run, verified process/listener ownership and cleanup, checked effective settings and evidence hashes, distinguished attempted input from accepted observations, and wrote/reviewed this record. No new emulator boot, game input or gameplay claim was made during recovery. Configured external reviewers remained unavailable; no endorsement is claimed.

## RE3-INPUT-002: native Hard selection and control in two rooms

Status: Confirmed for the named revision and the two sampled rooms. A fresh native boot reached a visibly identified Hard choice, followed by deliberate turning and translation in two rooms. This confirms those observations; a general tracker admission rule remains unresolved.

The title, serial, executable fingerprint and DuckStation version are the same as RE3-INPUT-001. The new experiment used `/var/folders/9d/q5n746z953bcs654g_1sqcy80000gn/T/re-map-re3-pulse-20261105-ggozkn3a/`, a private portable application, fresh resource paths, port 2355 and no initial checkpoint. Before boot, both achievements sections were disabled, account keys and game overrides were absent, `ApplyGameSettings=false`, cards were `None`, audio was muted and the original black shader was enabled. The effective settings remained byte-identical through cleanup. No tracker history was opened. No game-file edits, forced guest state, health/ammunition patches or other guest-memory writes were used.

### Native input and checkpoint procedure

The earlier Up/Down procedure targeted the wrong title navigation. Owned `TITLE.BIN` code at `0x80195634` reads Right/Left to cycle its three title choices. The default cursor in this fresh boot was 1, visibly `LOAD GAME`. Left selected cursor 0, visibly `NEW GAME`. Cross opened the two-entry difficulty choice, whose cursor 0 visibly read `HARD MODE`. Cross confirmed it. These labels came from newly written native checkpoint thumbnails and private OCR, with matching source-prefix and cursor-state observations. No game image is published.

The source-bound title cursor is a u8 at PS1 virtual `0x8019750C`, full mask `0xFF`, within the work structure based at `0x80197508`. The native title navigation reads a u16 LE edge word at `0x800CC834`, using Right mask `0x2000` and Left mask `0x8000`. These game input words differ from the native checkpoint controller's active-low PS1 button bits. The cursor is interpreted only while the first 128 owned overlay bytes match at `0x80194000` and the observed title/difficulty callback is active.

The private controller retained the six explicit toggle macros described in RE3-INPUT-001. A persistent GDB client held the guest paused between bounded execution intervals, so tool/model delays could not advance the title's idle timer into recorded playback. Each requested interval was at most five seconds, followed by interruption. This used native controller input and debugger observation without changing guest fields.

The exploratory proof run also established why checking native-save completion matters. A save hotkey issued while GDB held the guest paused could queue its callback. Copying the existing slot immediately could therefore retain an older image. Accepted saves here require a newer filesystem modification time, a complete version-87 native state, successful Zstd decompression and a unique 2 MiB RAM location matching all four executable windows. The guest runs briefly to flush the save callback before copying. A checkpoint can precede the following live observation by several frames; the table below reports checkpoint fields, not substituted later values.

This method agrees with the pinned DuckStation [GDB connection/pause implementation](https://github.com/stenzek/duckstation/blob/00e2997958d62de79d352cd680ec0c1ad95d491c/src/core/gdb_server.cpp), [native-state header](https://github.com/stenzek/duckstation/blob/00e2997958d62de79d352cd680ec0c1ad95d491c/src/core/save_state_version.h) and [save callback/write path](https://github.com/stenzek/duckstation/blob/00e2997958d62de79d352cd680ec0c1ad95d491c/src/core/system.cpp). The separate first proof run is retained under `/var/folders/9d/q5n746z953bcs654g_1sqcy80000gn/T/re-map-re3-hard-proof-20261105-swlm29xg/`; it verifies controller delivery and the stale-save hazard, not a Hard campaign. Its process was stopped before the fresh boot.

### Controlled observations and source witnesses

All addresses below are PS1 virtual addresses, with corresponding 2 MiB capture offsets obtained by subtracting `0x80000000`. Position is three signed i32 LE values at `0x800CCBF8`, `0x800CCBFC` and `0x800CCC00`, each using the full `0xFFFFFFFF` width. Facing is the raw u16 LE at `0x800CCC32`, full `0xFFFF`; these observations do not establish a map-facing conversion. Stage/room/camera and loaded-source contracts remain defined in [RE3-NATIVE-001](native-contracts.md#re3-native-001-native-selectors-agree-with-owned-room-sources).

| Native checkpoint | Stage / room / camera | Position x / y / z | Raw facing | Observation |
| --- | --- | --- | ---: | --- |
| `hard-control-baseline` | 0 / 13 / 0 | 13209 / 0 / -14515 | 2048 | Settled first-room baseline, no held input |
| `hard-left-turn` | 0 / 13 / 0 | 13209 / 0 / -14515 | 1008 | Left changed facing without translation |
| `hard-forward` | 0 / 13 / 0 | 12025 / 0 / -14515 | 2048 | Right returned facing to 2048; Up then translated |
| `hard-second-room` | 0 / 1 / 10 | -5404 / -1800 / -12401 | 2688 | Settled second-room baseline after a native scripted transition |
| `hard-second-moved` | 0 / 1 / 10 | -4869 / -1800 / -11095 | 3328 | Right and Up changed facing and position independently of the first room |
| `hard-restored-first` | 0 / 13 / 0 | 13209 / 0 / -14515 | 2048 | Earlier checkpoint restored the exact baseline room, position and facing |
| `hard-restored-second` | 0 / 1 / 10 | -4842 / -1800 / -11028 | 3328 | Later restore returned the second room and settled after released movement |

The first room matches `CD_DATA/STAGE1/R10D.ARD`, native file index 413, RDT SHA256 `b49017b7a7bd28d71f1129001d2acffb6ce549928f700e9a927a5f19ad4cddb2`. The second matches `CD_DATA/STAGE1/R101.ARD`, index 378, RDT SHA256 `5bccb836c34e1b62121928f6dba0b34b93fa5645e4f3789659686d9d6a7921e2`. Each accepted control/restore capture has one matching header/camera/zone source, matching selectors/allocation base, an in-range camera and no audit rejection evidence. The recorded-input bit is clear. This supplies runtime corroboration for the sampled source bindings; all 169 sources have not received gameplay validation.

The second-room source reused the first room's loaded base `0x8011A708`. That pointer's numeric value therefore does not identify the room. The retained transition and restore captures have the corresponding selectors and relocated source witnesses. The audit still reports `campaign_admission` and `hard_identity` as `unresolved`; the positive campaign conclusion comes from the observed native menu and deliberate controls, not a newly implemented classifier.

### Reproduction, limits and cleanup

1. Prepare a separate portable instance with the identity and isolation checks above. Check the intended port is free and retain its exact process command. Boot the owned CUE normally with fresh private state.
2. Use a persistent GDB connection to pause between bounded native inputs. Reach the title with Start; select `NEW GAME` with Left from the observed default, confirm with Cross, retain a fresh `HARD MODE` checkpoint and confirm. Recheck the visible label and source-bound title cursor instead of assuming a menu position from a filename.
3. Allow native startup and scripted sequences to finish. Retain settled baselines, then apply Left/Right and Up separately. Verify actual input words, changed facing/position and the corresponding fresh source audit. Script-driven movement is recorded separately from these controls.
4. Before every checkpoint load, recheck both achievements sections, absent accounts/overrides and private resource settings. Copy only a checksum-verified private checkpoint into the private native slot, invoke native Load Selected State and verify the load log plus fresh fields. Do this in both earlier/later directions.
5. Rerun the source audit against every accepted capture. Stop the verified private process after closing its GDB client; verify both process exit and a free listener port.

The private `controller.jsonl` retains execution durations and live observations. `load-audit.jsonl` records the pre-load settings checks. The retained `re-map-re3-pulse-control.py`, `re-map-re3-pulse-load.py`, `re-map-re3-pulse-ocr.py`, `re-map-re3-pulse-probe.py` and `re-map-re3-pulse-verify.py` refer to this exact temporary instance. A future run must update paths and verify its own process/port ownership. The verifier independently checks turn/translation differences, baseline reversal, restored state equality, difficulty-bit observations and source agreement. The audit checked 16 captures and all 169 native source-table rows; two audit executions produced identical JSON.

| Private evidence | Bytes | SHA256 |
| --- | ---: | --- |
| `settings-preboot.ini` | 2124 | `e0e45dd007b303d6dfd29176147eadf179af844112b863a927b74bc670e8b348` |
| `controller.jsonl` | 62263 | `b187097613d9385aa57cf36dd3cf89d11623938fd3ddddd1d5bf5e1fbafb37d6` |
| `load-audit.jsonl` | 1684 | `199f2839eb485375a9857b13350e85b585dfb5874140a7f8544d4ceffd404be5` |
| `final-source-audit.json` | 19437 | `98cb3779ba9f5f1cc903e447bfc7cdb3c717982e96606ebe9b1e13537e37814e` |
| `verification.json` | 13622 | `682351dc4a4f61c0de4135f30b274a705ac968c434c81bad60c04dcb36fb2ba4` |
| `choice-screen.sav` | 1259824 | `befa976c0d99a1a6c689a13d11ba57aa55ae15a9b340f30be2ef86884e6524e8` |
| `hard-control-baseline.sav` | 2066188 | `dcc5bb76ec869daf08d2254ac23894e996a02c4a9a53ac43994c6c52d83c9177` |
| `hard-second-room.sav` | 1936251 | `1f844114b3ff244699c64dd3dcc9ca8feafa8b805593ad6d1ffda46ac83a0892` |
| `hard-restored-first.sav` | 2067818 | `1c17f43119843753940ecceb2092ac1eb6ecbb3c64bf0f71834b4d393b4726fa` |
| `hard-restored-second.sav` | 1935749 | `9f1d1a1e932ac58772333a9e3c968f8b898ead6b7a64ce5925dedc78d77230e8` |
| `cleanup.json` | 342 | `b7f11980a1eeac7bee8d42d2faa6b487ec294b1ad82e69dca191dd98f7f22108` |

Ordinary room departure/reentry remains unverified. The observed first-to-second-room transition included native scripted movement. Later exit-interaction attempts remain attempts, with a separate `hard-interaction-attempt` sample. A general lifecycle gate must still distinguish title, recorded playback, loading, scripted sequences, native menus and player control. In particular, the recorded-input bit stayed clear during startup and scripted movement. Acquisition, door, story, room completion, spatial map binding and allocation extent remain unresolved. These checkpoint tests do not establish memory-card persistence.

Cleanup matched private PID 21125's exact command and listener ownership, closed the persistent controller, sent SIGTERM to that PID only, and confirmed exit plus free port 2355. All disc/BIOS/code bytes, RAM, native saves and images remain private. Only documentation is committed.

### Contributions and review

- 2026-11-05; human user; supplied owned media, authorized continued investigation and selected Hard.
- 2026-11-05; Codex root, exact runtime model `gpt-6.1-sol`; performed both root input experiments, checked native menu instructions and fresh checkpoint completion, observed Hard and Easy selections, verified controlled movement in two rooms and earlier/later restoration, reproduced all source audits, stopped both private instances, and authored/reviewed this contribution. Local review checked input provenance, checkpoint/live timing, address spaces and masks, source reuse, state reversal and unverified limits. Configured external reviewers remained unavailable, and delegated workspace credits were exhausted. No external endorsement is claimed.

## RE3-INPUT-003: the title difficulty choice writes lifecycle bit 0x100

Status: Confirmed for the named revision's title confirmation path. Using the bit as a general runtime difficulty/campaign classifier remains Candidate; an Easy campaign was not played.

The relevant PS1 virtual address is `0x800CC858`, u32 LE, with mask `0x00000100`. In the source-bound `TITLE.BIN` loaded at `0x80194000`, confirmation with cursor 0 clears that bit at `0x80195DB0..0x80195DC0`; cursor 1 sets it at `0x80195DC4..0x80195DD4`. The owned instruction interval `[0x80195DB0, 0x80195DD8)` has SHA256 `580a54d9658873b344addb64908f7c1abc30f332d35b89c489c6a9f163006210`. The overlay identity and load-base witnesses are recorded in [RE3-NATIVE-002](native-contracts.md#re3-native-002-recorded-input-rejects-plausible-player-states).

The fresh cursor-0 thumbnail reads `HARD MODE`. Its confirmed startup and both controlled rooms have the bit clear. For an independent opposite-choice observation, restore the verified preconfirmation checkpoint, select Right once, and retain a fresh cursor-1 thumbnail reading `EASY MODE`. Before confirmation the word is `0x20000000`; native Cross confirmation changes it to `0x20000100`. Restoring the later Hard checkpoint changes it back to `0x28001000`, and the following fresh native save is byte-identical to `hard-restored-second.sav`.

| Private comparison evidence | Bytes | SHA256 |
| --- | ---: | --- |
| `easy-choice-screen.sav` | 1260542 | `5af15bf237f9d7bf47f532271646df35a9224fbd217a5347bf5f016cb4b84115` |
| `easy-confirmed.sav` | 1245422 | `3b52bc1dcbdea1e454d93018ec7e2a6e20cd6fa5a1797408a41aa202bbd5a29d` |

The raw `0x800D1F30` lead from RE3-NATIVE-003 remained zero through both title confirmations and the controlled Hard samples. It still supplies no difficulty discriminator. A clear `0x100` bit also occurs before a campaign exists, so it cannot positively admit gameplay. The authorship, isolation, native inputs, review and cleanup are the same contribution as RE3-INPUT-002; no additional author or reviewer is implied.
