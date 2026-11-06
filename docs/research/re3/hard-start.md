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

## RE3-INPUT-004: ordinary reentry attempt reaches a disabled collision record

Status: Candidate for one observed native collision-scan rejection in the named revision. These attempts established no ordinary floor change, room departure/reentry or positive campaign/Hard admission. RE3-INPUT-002/003 retain their existing confirmed selection/control scope.

The target remains Resident Evil 3: Nemesis, PlayStation, USA, SLUS-00923, `SLUS_009.23` SHA256 `2e143418e358b2c99995cdc1a88c387163fb751912c723b755614f38e236bd29`. Both experiments used DuckStation `0.1-12083-g00e299795`, binary SHA256 `5c879677051cfb173002df22baee741c96fa8071c6fe1dd7e5454092bf128173`, native-state version 87, and the owned CUE. The first loaded RE3-INPUT-002's private `hard-second-room.sav`, SHA256 `1f844114b3ff244699c64dd3dcc9ca8feafa8b805593ad6d1ffda46ac83a0892`; the second loaded the first experiment's retained post-event checkpoint.

### Native route attempt and event lifecycle

The first baseline was stage/room/camera `0 / 1 / 10`, position `[-5404, -1800, -12401]`, facing 2688, health 200 and actor floor 1. Native turns and Up walked around source-derived collision bounds but remained in room `0 / 1`. The west approach clamped at x = -6363. A northern/western detour toward the candidate exit clamped at z = -16372. Its live registry descriptor at `0x80121DF4` matched source offset 30444 and required floor 4. Native code at `0x80050800..0x80050820` compares that descriptor's floor byte with the signed actor floor; the observed values differed. Subsequent detour and action attempts did not establish a usable path.

The first Cross/Up action instead produced control word `0x01000000`. A retained task source pointer at `0x800DEFEC` became `0x80121B11`, source offset 29705 inside procedure 12, whose source interval `[29668, 29754)` has SHA256 `f6d98f7a48a41a6b99ff7310c9654a393582b1cb6bc246c849b2c847a1ee0f68`. With input released, a bounded three-second observation found primary routine 4, actor flags `0x5103` and changed pose; a further five-second observation found control 0, primary routine 1 and flags `0x0003`. This associates the sequence with procedure 12 through its directory, changed retained pointer and native behavior. That pointer is script data, not a sampled MIPS PC, and this was not an instruction-exact trace of the event.

The later Cross/Up retry retained floor 1. A copied-native probe of `0x8004B374` raised `UC_ERR_EXCEPTION` before returning. The first directory's `copied-climb-error-detail.json`, SHA256 `0389252fd0c24383e3209ec20c86f734aba99666fddc3ba8ed541bd1f2d91f84`, preserves its original code/helpers and audited partial stores; it proved neither a rejection result nor a landing contract. The follow-up therefore used actual native execute callbacks.

### Actual scan rejection and separate source inference

The follow-up restored the post-event checkpoint at position `[-6363, -1800, -11415]`, facing 1952, floor 1 and control 0. A fresh Cross/Up action was intercepted with control `0xFFFF0000`, without a climb-entry callback. After releasing both inputs, Cross dismissed the interaction to control 0. Keeping Cross held and then adding Up separated that action edge from the subsequent collision scan. Raw held input was `0x1040`, logical held input `0x10D1`, including action mask `0x80`. The logs retain every toggle, hold, release, host-time interval and failed attempt.

The scan reached the exact source record at virtual `0x8012012C`, RDT offset 23076. Its owned bytes are `53e0eecb62e534da47fe510f0101f0f1`; live bytes are `53e0eecb62e534da0700510f0101f0f1`. Only its flags word differs, `0xFE47` versus `0x0007`; the latter was already present in the earlier experiment's captures.

| Actual native stop | Registers and outcome |
| --- | --- |
| `0x8004B00C` | `s0=0x80120136`, record plus 10; the scan reaches this record |
| `0x8004B020` | `v0=t4=0x11`; the preceding mask comparison passes |
| `0x8004B038` | `s2=7`, `t4=0x8000`, `v0=0`; the required flags bit is absent |
| Two native single steps | `0x8004B038` to delay slot `0x8004B03C`, then skip target `0x8004B2A0` |

These are live GDB general-register/PC reads, with unchanged target code at every stop. They are not registers decoded from a native checkpoint CPU payload. The scan stack was PS1 scratchpad `0x1F800364`; the requested mask is retained as actual GPR `t4`. The 2 MiB captures do not include scratchpad. This observed path skips the record before `0x8004B374`; that handler's entry arguments, side/landing checks and return were not observed.

Separately, source bytes `4c0309006e180000` at offsets 26420 through 26427, SHA256 `e388fbdbf2a4f6d6a6ed34fb7fc81daf21ea43869bc69843d0fa1bfd601e6d88`, encode numeric condition `3:9 == 0` and opcode `0x6E` for record 24 with operand zero. The pinned dispatch table sends `0x6E` to `0x800556E0`, which writes `(flags & 0x003F) | (operand & 0xFFC0)`. This predicts `0xFE47` becoming `0x0007`. Native CK code at `0x800546CC` and the bank-table word at `0x8009E404` resolve bank 3 to `0x800D1FA0`; the observed word was `0x00100000`, with bit-9 mask `0x00400000` clear. The earlier writer was not replayed or witnessed. This is source inference consistent with the live record, with no story or progression meaning assigned to `3:9`. It supplies no justification for forcing the bit or retrying another approach to this disabled record.

### Fields and source boundaries

Addresses here are PS1 virtual addresses. Main-RAM capture offsets subtract `0x80000000`; register values and scratchpad addresses are separate spaces. All multibyte fields below are little endian.

| Field | Address and width | Mask or interpretation |
| --- | --- | --- |
| Stage/room/camera | `0x800D1F76`, three i16 | Full `0xFFFF` each |
| Position; facing; health | `0x800CCBF8`, three i32; `0x800CCC32`, u16; `0x800CCC90`, u16 | Full `0xFFFFFFFF` / `0xFFFF` / `0xFFFF` |
| Actor floor | `0x800CCBCD`, i8 | Full `0xFF`, signed; observed 1 |
| Lifecycle | `0x800CC858`, u32 | Recorded `0x10000000` clear, world loop `0x08000000` set; title difficulty mask `0x100` remains insufficient identity |
| Control | `0x800CCBA0`, u32 | Full `0xFFFFFFFF`; movement-filter mask `0x01000000` from RE3-NATIVE-005 |
| Routines; actor flags | `0x800CCBC8`, four u8; `0x800CCC0A`, u16 | Full `0xFF` each / `0xFFFF`; inspected actor mask `0x8000` clear |
| Raw/logical held input | `0x800CC830` / `0x800CC83C`, u32 each | Full `0xFFFFFFFF`; observed raw `0x1040`, logical `0x10D1` |
| Source/allocation pointers; task source pointer | `0x800CC86C` / `0x800CC870`; `0x800DEFEC`, u32 each | Full `0xFFFFFFFF`; the task pointer is not a CPU register |
| Menu active/view/pause | `0x800E01E7` / `0x800E01D0` / `0x800D4434`, u8 each | Full `0xFF`; zero in the retained captures |
| Candidate collision flags | `0x80120134`, u16 | Full `0xFFFF`; required scan mask `0x8000` absent |
| Numeric bank 3, bit 9 | `0x800D1FA0`, u32 | Mask `0x00400000`, clear in the observed `0x00100000` word |

Both source audits checked all 169 native table rows. Each experiment's four bounded direct RAM captures had one matching header/camera/zone source, `CD_DATA/STAGE1/R101.ARD`, RDT SHA256 `5bccb836c34e1b62121928f6dba0b34b93fa5645e4f3789659686d9d6a7921e2`. Source and allocation pointers were `0x8011A708`. The 165280-byte source-file window `[0x8011A708, 0x80142CA8)` fits main RAM; it is not proof of allocation extent or byte-identical mutable source contents. The follow-up scan transiently observed lifecycle `0x2C001000`, then settled to `0x28001000`; no new meaning or admission rule is assigned to the differing bit.

The actor-floor byte is also the numeric `phase_i8` input in [RE3-MAP-009/011](map-semantics.md#re3-map-009-bind-the-loaded-source-before-evaluating-group-0-shapes). This observed comparison does not map its native floor tags to tracker floor labels or the separately browsed map layer.

| Pinned EXE interval, end exclusive | SHA256 |
| --- | --- |
| Floor comparison `[0x80050800, 0x80050820)` | `a44fc60fc2dbb81ebca74b92b4d9981ff65b4cd9846aedb421190366dcad0d14` |
| Actual scan `[0x8004B00C, 0x8004B070)` | `9572f8aa4f916b23f6a4569e944b27eea4142c46b8e0afcfe938dc9c325b2aa4` |
| `0x6E` handler `[0x800556E0, 0x80055728)` | `2e368009599db3cfb26ae1123a4bd9d4ff8c43db474974002dfd559e2911d440` |
| CK handler `[0x800546CC, 0x8005472C)` | `eaee5c31b20d9f51bce9efe54c627be99ca2f123d46dc507468f3159308cfe78` |

### Reproduction, evidence and limits

The first directory is `/var/folders/9d/q5n746z953bcs654g_1sqcy80000gn/T/re-map-re3-reentry-20261106-1vhrhnnq/`; the follow-up is `/var/folders/9d/q5n746z953bcs654g_1sqcy80000gn/T/re-map-re3-climb-guard-20261106-fkvqlcw7/`. Each retains preparation/launch/controller scripts, pre-load settings, owned-media identity, input logs, bounded RAM, source audit, verification and cleanup. The first `verify.py` preserves a rejected checkpoint-equality assertion; `verify-v2.py` is its corrected verifier. The follow-up `verify.py` checks the actual branch, five distinct native PCs, four captures and all 38 prior manifest file hashes. Its manifest has 26 files, excluding private application/resources. Counts describe the evidence, not gameplay coverage.

| Private evidence | SHA256 |
| --- | --- |
| First `verification.json` | `54bc5cb2a706d57129c02a85d6e0c7c591c1b7e2c4fab3cd9a1fb2c76d77cfe8` |
| First `artifact-manifest.json` | `47c0453150e0992169690970cba147a0807b846794aa0e55fee03c8babf40a11` |
| Retained `post-event-native.sav` | `3e3d067475daab53a7589fff3649521e6f9331746331998de09407dcb2c38290` |
| Follow-up `verification.json` | `4ba006e028ec44842e48035ada19e6edda48a16a83b4135f114b26de353ff975` |
| Follow-up `native-guard-records.json` | `8b36421f57993297ca96292dfeddb916c349c66400573feae4791bf30e0c5ef0` |
| Follow-up `artifact-manifest.json` | `af235e115a07900e10eb39e2acccafcf82dd41b3db15ab88543f8309ff227bdf` |

To reproduce the guard, use a fresh private instance and the hash-verified post-event checkpoint, repeat isolation checks before every load, pause between bounded native controller inputs, and retain actual delivery before accepting a requested toggle. Follow the logged interaction dismissal, retain Cross held and add Up. The private `find-record` procedure locates source record `0x8012012C` at scan PC `0x8004B00C`; observe the two mask tests, remove callbacks and single-step the branch/delay slot. Recheck every stopped code window against the pinned executable. These temporary scripts require explicit fresh paths, process ownership and a free port; their old launch manifests do not authorize attaching to another instance. CUA timeout/reset and an earlier accessibility-snapshot failure are preserved, with no duplicate toggles accepted without native input readback.

Before each experiment's only game/checkpoint load, both `Achievements` and `Cheevos` had `Enabled=false` and `UseRAIntegration=false`, account keys and per-game overrides were absent, `ApplyGameSettings=false`, cards were `None`, and resources were private. Gameplay stayed black and muted. F11/F13 toggled native Cross/Up; F15/F16 turned Left/Right. Host execute callbacks and native stepping left guest code unchanged. No guest pose/room/phase/difficulty/control writes, PC repair, patches, substituted handlers, tracker/user-history writes or repository gameplay changes occurred.

Cleanup released every held input, removed every execute callback, closed each client and verified only its owned process: PID 29426/port 2383 and PID 76282/port 2384. Both waiting launch wrappers recorded exit 0; PIDs/listeners were absent, ports bindable and settings byte-identical to preboot. The first run's unchanged settings SHA256 is `aea1b87e84cd8d141a81e3672a10bc141c72687c434b144a84211e1c9e3ad795`; the second's is `f389ebc64bab94184197cd03fc25cb816657a74c7eb91cc5185d3a8557cdcd37`. Both CUA sessions completed. Raw assets, RAM and saves remain private.

The retained checkpoint has released native controller buttons and matching selected fields, but differs from the preceding direct capture at 14830 RAM bytes, including tertiary routine 3 versus 1. Its later load likewise does not establish exact full-RAM restoration. There was one selected source throughout; no ordinary floor change, departure/reentry, item/door outcome, memory-card persistence or sufficient positive admission was established. Host intervals are not frame-exact. The observed skip covers one record/mask/path; an already active route needs a separate source premise. The failed Unicorn probe and unobserved earlier writer cannot fill that gap.

### Contribution and review

- 2026-11-06 UTC; independent native investigator and documentation author, exact model `gpt-6.1-sol`, effort `xhigh`, verified from matching session metadata and latest turn context; performed both bounded native-input experiments, captured actual GDB register/step observations, authored private verifiers/manifests and this Candidate claim, preserved failed probes, checked source inference, widths, hashes and cleanup. This contribution is separate from the original human/media and root authorship in RE3-INPUT-001/002. Documentation checks add no runtime validation.
- 2026-11-06 UTC; independent internal reviewer, exact verified model `gpt-6.1-sol`, effort `xhigh`; found no issues in the record and evidence. Checked all 19 documented fingerprints, 64 manifest entries, GDB register/PC and delay-slot sequence, input readbacks, pinned code/condition formulas, source-audit limits, settings, callback removal, process exit and field widths. No emulator operation, proof rerun, new tests, edits or user-history access occurred.
- 2026-11-06 UTC; Codex root, exact runtime model `gpt-6.1-sol`; independently rehashed the 64 artifacts, checked all five PC/register stops and the source/live flags, linked the existing numeric map-input alias and retained Candidate/no-reentry limits. No new emulator observation or restore is implied by this integration.
- 2026-11-06 UTC; external snapshot reviewer, `gemini-3.8-flash`, high reasoning through Antigravity; returned no findings on the claim, verification/cleanup reports, GDB record data, source inference and pinned native disassembly excerpts. Review covered address/bit arithmetic, actual versus inferred execution, requested versus observed inputs, failed-probe and checkpoint limits, provenance and cleanup claims. It inspected only the supplied snapshot, used no tools and supplied no new runtime validation. Claude Opus 5.5 remained disabled and supplied no review.

## RE3-INPUT-005: ordinary input reverses a floor change within one loaded source

Status: Candidate bounded native floor-cycle and caller observation. One isolated session observed floor 1/Y=-1800 → floor 2/Y=-3600 → floor 1/Y=-1800. No ordinary room departure/reentry or sufficient campaign/Hard admission rule was established. [RE3-INPUT-004](#re3-input-004-ordinary-reentry-attempt-reaches-a-disabled-collision-record) retains the earlier failed route and disabled-record evidence unchanged.

The revision is Resident Evil 3: Nemesis, PS1, NTSC-U, SLUS-00923. The owned CUE SHA256 is `ffb65655915a792780922cbf5a925235d223017cbf317c1551e9748d37451b2f`; image SHA256 is `d6c828dc92d50b28fd58329dbe607d4d22eeaeb1d9a46be54ac81b130fc2c7a6`. `SLUS_009.23` SHA256 is `2e143418e358b2c99995cdc1a88c387163fb751912c723b755614f38e236bd29`. DuckStation is `0.1-12083-g00e299795`, binary SHA256 `5c879677051cfb173002df22baee741c96fa8071c6fe1dd7e5454092bf128173`.

### Source premise and observed floor update

The retained live registry corrected the partial door census. Native ordinary creator `0x61` at `0x80055B5C` consumes 32 bytes; four-point creator `0x62` at `0x80055BBC` consumes 40, with SAT mask `0x80` selecting its geometry/payload layout. The 32-slot u32 registry at `0x800CC890` contained two kind-1 descriptors, both canonical ordinary commands in procedure 18. Neither activated on floor 1. The second door's native unlock/item checks remained unsatisfied, so this session attempted no door. Raw `0x61/62` bytes inside canonical item packets were excluded from the census. This does not close all script/callback routes or validate four-point doors at runtime.

The new premise was active collision record 6 at source offset 22788, PS1 virtual `0x8012000C`, separate from disabled record 24. Its 16 bytes have SHA256 `7faf0969724637958faafa17d3b645348fdf95b0a485e249f5778e1f642c3add`. Source inspection gives kind 10, flags `0xFE7A`, X bounds [-15094,-12584], Z bounds [-25805,-24185] and floor bytes [1,2]. The source-derived height model predicts -1800 at the southern edge and -3600 at the northern edge. `source-route.json` preserves the pre-session derivation and native code-window hashes. The selected record and type-10 dispatch were not dynamically stopped; their association with the observed route remains source inference.

Native Left/Right/Up input staged the player below that rectangle. The bounded captures show the following released-input states; health remained 200.

| Capture | XYZ i32 | Floor i8 | RAM SHA256 |
| --- | --- | ---: | --- |
| `ramp-lower-before` | [-14039,-1800,-23601] | 1 | `97e05bf48f67984d80cc509187807fc849c0217ec1b724219b22f1a7a107a3dc` |
| `ramp-upper-after` | [-14096,-3600,-25812] | 2 | `0f6e571e598af1b74c0aff6f71c9a81f2aeeb7d474617009b7914284162021c9` |
| `ramp-lower-returned` | [-14145,-1800,-23745] | 1 | `68b0506065ad0fd3ab1dd9aca9674395edb2d2b91739cfd8f97125591bb09f77` |

During ascent, actual GDB register reads retained 59 player entries to original `0x8004B7E8`, with A0=`0x800CCBC4` and RA=`0x80033C7C`. The last entry had A2=-3600, pose [-14096,-3574,-25812] and floor 1. After executing the original function, the actual return at `0x80033C7C` had Y=-3600 and floor 2. Source instructions store height at actor+`0x122`, floor at +9, and Y at +`0x38`; these instructions were not individually stepped. The entry/return brackets and changed live fields witness that update. The descent retained intermediate Y=-3164/-2527 and the stable lower endpoint, without another traced function return. All registers here came from the live GDB `g` response, not decoded checkpoint CPU state.

### Stationary caller evidence and field contract

After descent, with input released, original dispatcher entry `0x80038C7C` had A0=`0x800CCBC4`, RA=`0x80023F14`, SP=`0x1F8003FC`. Normal-handler entry `0x80039020` then had RA=`0x80038D34`, SP=`0x1F8003CC`. A bounded four-byte read at scratchpad `SP+0x2C`, address `0x1F8003F8`, returned `14 3F 02 80`, saved outer return `0x80023F14`; that original return was also observed. Scratchpad lies outside the direct 2 MiB RAM images. This is additional caller evidence only. It does not prove a sufficient admission gate, read coherence or writer ownership across future polls.

All addresses are PS1 virtual addresses and multibyte data is little endian. RE3-INPUT-004's selector/source/control/input field contract applies. XYZ at `0x800CCBF8` is three i32, floor at `0x800CCBCD` is i8 and height at `0x800CCCE6` is i16, each using its full-width mask. Actor flags at `0x800CCBC4` are u32; the Y-write guard reads mask `0x400`, observed clear. This differs from the actor u16 flags at `0x800CCC0A`. Facing at `0x800CCC32` is u16, with phase mask `0x0FFF`; raw values above 4095 are retained. GPRs and the scratchpad return word are u32 with full `0xFFFFFFFF` masks.

All four bounded RAM captures, including the loaded baseline, independently matched `CD_DATA/STAGE1/R101.ARD` after checking all 169 native source-table rows. RDT SHA256 was `5bccb836c34e1b62121928f6dba0b34b93fa5645e4f3789659686d9d6a7921e2`; source/allocation pointers stayed `0x8011A708`. The 165280-byte source-file window fits RAM but does not establish allocation extent. Lifecycle was `0x28001000`, control/menu/pause were zero at the settled captures; these values do not supply a positive campaign/Hard classifier.

| Pinned EXE interval, end exclusive | SHA256 |
| --- | --- |
| Floor writer `[0x8004B7E8,0x8004B874)` | `2706e1ae33bad6671c1251de186091bad57754eda60b1e1a2dbae0c7e72a0302` |
| Regular caller `[0x80023ED0,0x80023F28)` | `ef61ed40e753707b99d7999dac37a934e3f6df4f2f3777589ae30df59be063cc` |
| Dispatcher `[0x80038C7C,0x80038D34)` | `1c227b39126626edb098b9bb9ae6a53cf194c1d2b053159bb96b84d6e49cc7d2` |

### Reproduction, isolation and evidence

Private evidence is under `/var/folders/9d/q5n746z953bcs654g_1sqcy80000gn/T/re-map-re3-active-ramp-20261106-qqermggo/`. `verify.py` reproduces the source audit from owned media, verifies field changes/code bytes/caller words and checks all 64 earlier manifest entries unchanged. The new manifest lists 32 files, excluding private application/resources. Its source premise intentionally retains its original pre-session status.

Load the retained `post-event-native.sav` hash from RE3-INPUT-004 into a freshly isolated, ownership-checked instance. Repeat the settings checks before every load. Follow `input-timing.json` and native readbacks to stage below the verified rectangle, walk north to the upper endpoint, release, turn and walk south to the lower endpoint. F13/F15/F16 toggle native Up/Left/Right. Each execution interval was at most five seconds. The ascent trace uses host execute callbacks at original entry/return; remove callbacks before continuing. Temporary scripts require fresh private paths, PID and port rather than reuse of the old launch manifest.

Host durations were not frame-exact. The logs preserve delayed/missed toggles, an ineffective Right request before descent, and an Up-release CUA timeout/reset. Native input/pose readbacks governed recovery. A private preparation syntax error and initial wrong controller path failed before guest access. `failed-observations.json` preserves these limits; the earlier failed Unicorn probe remains a failure. The retained native checkpoint is not an exact restore of the latest direct RAM image.

Before the only game/checkpoint load, both `Achievements` and `Cheevos` had `Enabled=false`/`UseRAIntegration=false`, account keys and overrides were absent, `ApplyGameSettings=false`, cards were `None`, and resources were private. Gameplay stayed black and muted. No guest writes, patches, forced flags/pose/control/room changes, screenshots or user/tracker-history writes occurred. Cleanup released every input, removed all callbacks, closed both clients, stopped only owned PID 5997 and verified port 2385 listener absent and bindable, exit 0. Settings stayed byte-identical, SHA256 `d62498ba99a91b05a074240042a1746fb6e154ef63ba56cc9f2648e9607a5775`; CUA completed.

| Private evidence | SHA256 |
| --- | --- |
| `source-route.json` | `a9e7f1b96b2736f2bcfd0142ae666d5d9326285bb5cd014f90c8cb1ab74dbc1b` |
| `native-floor-update.json` | `b1352e3844d475f272f8ac38c2df8c3dae51b2a13377a3929c0e7e02653e69c2` |
| `native-dispatch-caller.json` | `9ae06376f6bd453543329819b193169a2c6afa42aa3472915afe5ee9edf5dffc` |
| `verification.json` | `45b5fbd9c7c8c1be3091846155a3af8a41a8a3ec5277dfa7603e2a5a29e50e85` |
| `artifact-manifest.json` | `51f29a42349a04c8b9eec6a48b127d0120eb1a9ef58452692cc0d62340cc59eb` |

This observation adds an ordinary reversible floor change within one loaded source. It establishes no item/door outcome, story meaning for numeric 3:9, room departure/reentry, memory-card persistence, map-layer ownership or general admission rule. Raw assets, RAM and saves remain private; hashes cannot replace missing temporary evidence.

### Contribution and review

- 2026-11-06 UTC; independent source/native investigator and documentation author, exact model `gpt-6.1-sol`, effort `xhigh`, reverified against matching session metadata and latest turn context; derived the new route premise, performed this isolated native-input cycle and stationary caller trace, authored the private verifier/manifest and appended this Candidate record. Original human/media, root and prior research authorship remains unchanged. No external review or new runtime validation is implied by documentation checks.
- 2026-11-06 UTC; Codex root, exact runtime model `gpt-6.1-sol`; independently checked all 96 current/prior manifest entries, four captures' pose/floor/height/health fields, retained live GPR/code consistency and the bounded scratchpad caller. A fresh offline audit reproduced the four source results against all 169 native rows, retaining unresolved admission. Root also checked unchanged private settings, process absence, port availability and the byte-identical earlier document prefix. Its first private verifier used the wrong health offset; the corrected `0x800CCC90` check passed without changing captures. Reproduction is `/var/folders/9d/q5n746z953bcs654g_1sqcy80000gn/T/re-map-re3-ramp-integration-20261106-opec7yge/verify.py`, with `verification.json` SHA256 `8afc3c1a00e82c8111a98c095445c59f301ff7d87208eb309d1f9016ebc47361`. This integration adds no native execution, savestate restoration or sufficient admission proof.
- 2026-11-06 UTC; external snapshot reviewer, `gemini-3.8-flash`, high reasoning through Antigravity; returned no findings on the new claim, source-route and verification records, selected native floor telemetry, complete caller record, pinned code bytes, failed observations and verifier. Review checked arithmetic/addresses/widths, observed versus inferred execution, chronology, input/checkpoint limits, source/lifecycle separation, provenance and cleanup. It used no tools and supplied no new runtime evidence. Claude Opus 5.5 remained disabled and supplied no review.

## RE3-INPUT-006: ordinary departure and reentry retain fresh source agreement

Status: Candidate for the named revision and one observed ordinary round trip. One isolated native-input session completed R101 → R100 → R101, with independently matched settled sources and released controls. This supplies the ordinary departure/reentry observation missing from RE3-INPUT-004/005. A sufficient campaign/Hard admission rule remains unresolved.

The target is Resident Evil 3: Nemesis, PS1, NTSC-U, SLUS-00923, using the owned media identity in [RE3-INPUT-005](#re3-input-005-ordinary-input-reverses-a-floor-change-within-one-loaded-source). `SLUS_009.23` SHA256 is `2e143418e358b2c99995cdc1a88c387163fb751912c723b755614f38e236bd29`. DuckStation is `0.1-12083-g00e299795`, binary SHA256 `5c879677051cfb173002df22baee741c96fa8071c6fe1dd7e5454092bf128173`. The session loaded the retained post-event native checkpoint once, then used ordinary controller input for both room transitions. It did not restore checkpoints between the rooms.

### New route and original native handlers

The known ramp-6 setup reproduced floor 2/Y=-3600. The next premise used live/source collision record 10 at RDT offset 22852, virtual `0x8012004C`. Its 16 bytes have SHA256 `87cc517165a8167a87dfb483b58a98d12eb72c2a22a94ec9979573b4c2074562`: flags u16 `0xFE6A`, kind low-nibble 10, attribute u16 `0x058A`, signed floor-bound bytes [2,4] and height i16 -9000. Source bounds X[-29579,-26634]/Z[-26045,-22265] and the native mode-9 height path predicted floor 2→3→4. Native movement then observed that progression. The disabled record-24 route was not retried, and the other door's missing `0x73` guard was not tested or forced.

| Actual GDB stop | Retained arguments and result |
| --- | --- |
| `0x8004E230` | A0=`0x8012004C`, A2=9, RA=`0x8004DA28`; original height dispatch directly selects the live second-ramp record |
| `0x8004B7E8` then `0x80033C7C` | Player A0=`0x800CCBC4`, A2=-7200, entry floor 3/Y=-7197; original return floor 4/Y=-7200 |
| Outbound `0x80050D28` | A0 payload=`0x80121E00`, s0 descriptor=`0x80121DF4`, RA=`0x80050B10` |
| Return `0x80050D28` | A0 payload=`0x8011B346`, s0 descriptor=`0x8011B33A`, RA=`0x80050B10` |

These are actual live GPR/PC reads with matching pinned executable bytes, not registers decoded from a checkpoint. The outbound descriptor matched procedure 18's ordinary creator at source offset 30442. SAT `0x21` uses a 620-unit forward probe, required floor 4 and zero native lock fields. The approach reached the predicted X=-18808 wall clamp with body radii 450/450. The original action handler then accepted the selected descriptor. Both actions retained raw input `0x40` and logical input `0x10C0`, including action mask `0x80`.

The source proposal incorrectly named its final increasing-Z leg "north". Following that label at phase 1056 produced the preserved stop [-18633,-7200,-20831]. Record 21's southern bound plus radius 450 equals that Z, but its collision handler was not sampled. The correction checked the actual X against the static east-side lane, turned toward south/phase 3072 and first verified increasing Z with stable floor 4. Input refinements stayed within the inspected corridor. The original proposal, wrong-heading capture and corrected check remain separate artifacts; no guest state was changed to bypass the stop.

### Settled source and caller observations

Before return input, a new full capture independently matched R100's header, relocated cameras and camera zones against all 169 native source-table rows. Its live slot-0 descriptor `0x8011B33A` matched canonical procedure 3, source command 3120, SAT `0x21`, floor 0 and zero lock fields. Fresh transient guards qualified, then an ordinary turn/action reached the return handler above. Source-only return metadata was not used as proof of a live descriptor.

| Settled capture | Selectors; XYZ; floor | RAM SHA256 |
| --- | --- | --- |
| Before departure | 0/1/6; [-18808,-7200,-11690]; 4 | `fed2db23b8a7048ca66c36eb36882d4ba18929fd7b257a2f3c3b8535602e9151` |
| Before return | 0/0/0; [-20400,0,-20790]; 0 | `17508fc8652a699eef400b0c2700a70e440940de9cf51112654b33feec1b476d` |
| After ordinary reentry | 0/1/6; [-18808,-7200,-11475]; 4 | `8c9d9bb4aacc8a684f3cb660bde1a74189373f886bad531ba15ae9f4368acf34` |

Each settled capture had health 200, control 0, phase 0, lifecycle `0x28001000` and all five input words zero. R101 RDT SHA256 is `5bccb836c34e1b62121928f6dba0b34b93fa5645e4f3789659686d9d6a7921e2`; R100 is `e47f25b5a6e82d73f79bf356c111a8add6a7e24555a4deb83ed8725e3979ed50`. Both used source/allocation pointer `0x8011A708`, so pointer equality alone would miss the source change. Source-file windows of 165280/109208 bytes fit RAM; allocation extent remains unproved.

Stationary regular-update traces in the settled old and new rooms both retained dispatcher `0x80038C7C`, A0=`0x800CCBC4`, outer RA=`0x80023F14`, SP=`0x1F8003FC`. Normal entry `0x80039020` retained immediate RA=`0x80038D34`, SP=`0x1F8003CC`; scratchpad `0x1F8003F8` contained LE word `0x80023F14`. Both original regular returns were observed. This adds caller evidence across the room change, without closing admission, read coherence or writer ownership for future polls.

### Pending transitions and limits of the trace

Initial R100 source agreement occurred while phase 1 and lifecycle `0x29401000` still indicated a pending transition. Actual stops at loader wait `0x80024A94` and door-task yield `0x80015834` retained released input. Source loader code yields while lifecycle mask `0x00400000` remains set. The door-task chain eventually waits for helper `0x8002A6BC(0)` to return zero, clears that mask and terminates. Its final clear/termination instructions were not sampled.

R100 settled after callbacks were removed and the first debugger client was closed/replaced for targeted reads. Native execution may have occurred across that handoff. Its exact completion time, instruction and any effect of disconnecting were not observed. The pending and settled captures remain distinct. Door-task active/status changed 1→0 and frame threshold changed 1→2; the sampled frame counter was zero in both states and is reset by native code, so it supplies no monotonic progress proof.

On return, the requested five-second callback at phase-clear instruction `0x80023470` did not hit. The failed observation retained actual PC `0x800292F0`, phase 1 and door-script cursor `0x8019D183` with bytes `0A 1E 00`. Pinned opcode `0x0A` handler `0x80053094` decrements a u16 timer without reading controller buttons. A later bounded two-second no-input interval observed phase 0 and the inactive task. The timer word and final phase-clear instruction were not directly sampled; neither wait established a confirmation prompt or justified another action press. Unused diagnostic reads with an address-calculation error are identified and excluded in `failed-observations.json`.

Addresses are PS1 virtual addresses and multibyte data is little endian. RE3-INPUT-004/005 retain the shared pose/input/source field contract. Additional fields are transition phase `0x800C7960`:u8; lifecycle `0x800CC858`:u32 with pending mask `0x00400000`; door-script active `0x800DFB71`:u8 and pointer `0x800DFB8C`:u32; task-1 status `0x800DCC14`:u16 in the native `0x80`-byte task stride; frame threshold `0x800D442C`:u8 and counter `0x800D454C`:u32. Each field uses its full-width mask unless stated otherwise. Scratchpad return words and GPRs are u32, separate from the direct 2 MiB main-RAM images. Actor floor is i8; it is not a tracker map-layer label.

| Pinned EXE interval, end exclusive | SHA256 |
| --- | --- |
| Selected type-10 mode-9 path `[0x8004E230,0x8004E268)` | `3ee7402db315c0e7a45fef5f4f6982f9284ecab8fc9204ef8ca425f8455a612c` |
| Loader wait `[0x80024A64,0x80024AA8)` | `7b11498c65946d6982187e649092b2195df4267c068921d3fd00c94f44278ddb` |
| Door-task termination `[0x80016150,0x80016208)` | `f414884a566e44113b0f03bad7fa03d64d1030a7fd0a02267d8d2196aae57a93` |
| Timer handler `[0x80053094,0x800530F8)` | `0075ad5fe5540c11eccb4139a8c28a3a862f4d6cfab9fca82e85d43f756239ad` |

### Reproduction, isolation and evidence

Private evidence is `/var/folders/9d/q5n746z953bcs654g_1sqcy80000gn/T/re-map-re3-native-return-20261106-idnv2yl9/`. `verify.py` checks eight bounded direct captures plus the saved RAM payload against all 169 owned source rows, original code/GPR records, both live doors, failed observations, cleanup and 100 unchanged prior manifest entries. Its manifest contains 49 files, excluding application/resources. Reproduction requires fresh private paths/PID/port and pre-load isolation checks, the retained seed, native input readbacks and the corrected signed-coordinate route in `input-timing.json`; host durations are not frame-exact. No new load is needed to verify the retained evidence offline.

A native F2 save completed after reentry. Its version-87 decompressed 2 MiB RAM payload equals the final direct capture byte-for-byte, with native controller pressed mask zero. This confirms checkpoint creation/payload equality only. It was not loaded or replayed, and it supplies no restore or memory-card-persistence test.

Before the only game/checkpoint load, both `Achievements` and `Cheevos` had `Enabled=false`/`UseRAIntegration=false`; account keys/overrides were absent, `ApplyGameSettings=false`, cards were `None`, and resources were private. Gameplay remained black/muted. The private checkpoint includes its embedded thumbnail; no game images were exported or shared. No patches, guest-memory/PC/pose/phase/flag/inventory/control writes or user/tracker-history access occurred. Cleanup released all input, removed callbacks, closed both clients, stopped only owned PID 97146 and verified port 2386 listener absent and bindable, wrapper exit 0. Settings remained byte-identical, SHA256 `b63e53931f2391b1d9f2822d76bddce5cb12b0a1997fbcaaad839bb397059125`; CUA completed.

| Private evidence | SHA256 |
| --- | --- |
| `native-route-records.json` | `146e3254a63f4434513ef41401d1671d0dd8c07e1d4d08fd3eb647f8b5711e60` |
| `verification.json` | `8f7408b1780b440758b11518a7085ce503aebc09ec4b20528f0173ca526d8792` |
| `artifact-manifest.json` | `9e2b80884ec0b96084b0d92e12b0bc8034adfc7c77cc35be1b32026f56c70ac5` |
| `ordinary-return-native.sav` | `4fd26335f93945de165d55a4577c0e32ec1e285af5a4c4ac466924ea5b03f8cc` |
| `cleanup.json` | `7b1251bd88c988531c7d7a03d9c01c1596318e28e384877ceeea7741105a7e26` |

This is one ordinary round trip in the named revision. No general campaign/Hard classifier, allocation extent, tracker item/door/map rule, numeric story meaning or memory-card persistence is established. Prior failed routes and the failed Unicorn probe remain unchanged. Raw assets, RAM and saves remain private; hashes do not replace lost temporary evidence.

### Contribution and review

- 2026-11-06 UTC; independent source/native investigator and documentation author, exact model `gpt-6.1-sol`, effort `xhigh`, reverified against matching session metadata and latest turn context; derived the route/item census, performed this isolated experiment, recorded original native floor/door/caller/yield telemetry and the wrong-heading correction, verified checkpoint creation/cleanup, authored the private verifier/manifest and appended this Candidate claim. Original human/media, root and prior review authorship remains unchanged. No external review or new runtime validation is implied by documentation checks.
- 2026-11-06 UTC; independent retained-evidence auditor, exact verified model `gpt-6.1-sol`, effort `xhigh`; found no issues in the frozen evidence after checking 49 new and 100 prior artifacts, native windows, source/RDT/payload agreement, checkpoint creation equality, isolation and cleanup. Its 18 controller-log GPR/code checks include repeated normal-entry samples; the route record separately has 14 code-bearing GPR records and three targeted GPR reads without captured code. A fresh offline audit reproduced all nine input results across 169 native rows. The auditor ran no native session, altered no files and reviewed no draft documentation.
- 2026-11-06 UTC; Codex root, exact runtime model `gpt-6.1-sol`; independently verified all 149 manifest entries, eight captures' decoded fields, the 14 route and 18 controller code/GPR checks, both scratchpad caller words and the unique full-RAM checkpoint payload. A fresh source audit matched every saved result; root rechecked process/port/settings cleanup and the unchanged earlier document prefix. An initial integration assertion conflated the route-record and controller-log counts; the final verifier distinguishes those datasets. Root also clarified the private embedded-thumbnail wording. Reproduction is `/var/folders/9d/q5n746z953bcs654g_1sqcy80000gn/T/re-map-re3-return-integration-20261106-at7od62q/verify.py`, report SHA256 `e59aa8ca9a477949e255e5c10688aea57bead275633680cacb350b13b1cc5acb`. This adds retained-file interpretation only, with no new native execution or restoration.
- 2026-11-06 UTC; external snapshot reviewer, `gemini-3.8-flash`, high reasoning through Antigravity; returned no findings on the new claim, private verifier/results, original native windows, retained route records, failed observations, checkpoint creation and cleanup. Review checked arithmetic/field contracts, source and descriptor binding, chronology, observed versus inferred execution, handoff/callback gaps, input/checkpoint limits, attribution and isolation. Its route height trace excerpt retained the first/last samples and total count. The completed response had no pending child work or tool attempts. This advisory review adds no native evidence. Claude Opus 5.5 remained disabled and supplied no review.

## RE3-INPUT-007: original code clears the startup input filter

Status: Candidate bounded native writer and completed-update observation for Resident Evil 3: Nemesis, PS1, NTSC-U, SLUS-00923. Original code cleared control `0x01000000` to zero without game input, then a regular player update returned to `0x80023F14`. This observes one original filter clear; campaign/Hard admission and gameplay readiness remain unresolved. [RE3-NATIVE-005](native-contracts.md#re3-native-005-the-normal-player-handler-can-retain-filtered-movement-input) retains the filter's rejection evidence.

### Restore, writer and source binding

The owned media identity is retained in [RE3-INPUT-005](#re3-input-005-ordinary-input-reverses-a-floor-change-within-one-loaded-source). Executable SHA256 is `2e143418e358b2c99995cdc1a88c387163fb751912c723b755614f38e236bd29`; DuckStation is `0.1-12083-g00e299795`, binary SHA256 `5c879677051cfb173002df22baee741c96fa8071c6fe1dd7e5454092bf128173`, native-state version 87. The old `first-normal-entry.sav`, SHA256 `7b79768087beb2e8c825aa6632757dbae1fa6169f9fc1a84f22da96c8c2d556f`, was restored with native F1 under an acknowledged debugger pause. Its full 2 MiB RAM, GPR0..31, HI/LO, PC and 1024-byte scratchpad matched the seed before experimental resume. RAM SHA256 was `333f2948fe24e752abbe5211ee935ef604ce6a5e84819cf1d5ca6bf3dd3bf4e3`. This equality covers those payloads, not every serialized device field.

An earlier command-line bootstrap advanced before client connection and is excluded from that restore claim. Its retained capture has health zero despite plausible partial source witnesses. After the exact F1 restore, two no-input probes of two and five host seconds produced no watched write. A source-derived execute callback at `0x800101AC` then witnessed progress; after its removal, the next bounded resume stopped on the watched write. Host durations are not guest-frame counts.

At epoch 5, GDB reported next PC `0x80052C70`. The new native checkpoint independently serialized `current_instruction_pc=0x800547BC` and instruction `0xACC40000`, `sw a0,0(a2)`, in the `jr ra` delay slot at `0x800547B8`. Live A0=0, A2=`0x800CCBA0`, A3=0, V1=`0xFEFFFFFF` and RA=`0x80052C70` agree with the observed clear. Raw branch-state bytes `[1,1,0,0,1,0]` are retained without interpreting the serialized exception flag as a gameplay fault.

The witnessed source is `CD_DATA/STAGE1/R10D.ARD`, SHA256 `51dce7d31e20c2a53fb6bbed9efa1c20bc30d6b03424f694f56463ba61dc9577`, with 162992-byte RDT SHA256 `b49017b7a7bd28d71f1129001d2acffb6ce549928f700e9a927a5f19ad4cddb2`. Task S0=`0x800DEFD0` had advanced PC at `+0x1C` equal `0x8011DF0A`. Original packet `4D 02 07 00` at `0x8011DF06` matches source offset 14334 from base `0x8011A708`, inside initializer procedure 37's envelope, offset 14328, size 16. This establishes packet/envelope identity, not complete canonical script interpretation.

Addresses in this claim are PS1 virtual, with scratchpad distinct from main RAM; source offsets are file bytes. Multibyte values are little endian. Control at `0x800CCBA0` is u32, full mask `0xFFFFFFFF`, with movement-filter mask `0x01000000`. Dispatch words at scratchpad `0x1F800134` and pinned table `0x8009E22C` are u32 and both select `0x8005472C`. The routine consumes u8 bank/index/operation, advances task PC by four and reads bank-two pointer `0x8009E400`=`0x800CCBA0`. Word stride is `4*(index>>5)` and mask is `0x80000000>>(index&31)`; index 7, operation zero clears `0x01000000`.

### Completed callback and retained limits

After removing the write callback, actual stops observed dispatcher `0x80038C7C`, A0=`0x800CCBC4`, outer RA=`0x80023F14`, SP=`0x1F8003FC`; normal handler `0x80039020`, immediate RA=`0x80038D34`, SP=`0x1F8003CC`; then completed return `0x80023F14` at epoch 8. Scratchpad u32 `SP+0x2C`, address `0x1F8003F8`, retained outer return `0x80023F14`. The final native save records original return-delay stack restoration at `0x80038E4C`.

No logged resume occurs between final stop, full RAM capture and native save creation. The same acknowledged pause retains selectors i16 `[0,13,0]`, control zero and source/allocation u32 pointers both `0x8011A708`. The earlier field contracts apply, with full-width masks. Pointer equality supplies no allocation extent, source generation or ABA proof.

| Checkpoint creation | Full RAM SHA256 | Native save SHA256 |
| --- | --- | --- |
| Writer stop | `3bef94813d0b5d2c4f5c2de572e3ae9b762ed2fa7af16b97cae723b4419f84d5` | `929dfc6ca1453b9a716212cf17975604bb3b494f138051dcc96a249a06ac0600` |
| Completed regular return | `37de217be5b6f6ef4cb218b0e746720b23665e7b2b9f0d24275c1cc27d3d0f39` | `b842cb6eb265187ed5d2e165aff7ba453056e1a93407b5a4dd2cce80b1b9da83` |

Both new saves match live full RAM, GPR0..31/HI/LO and scratchpad at their pauses. They were created but never restored/replayed; only the old seed received a restore test. No memory-card persistence follows. All five captures uniquely match the partial header/camera/zone R10D witnesses across 169 native source-table rows. The critical captures retain 403 initializer-byte differences from owned source, so full mutable-source identity is unproved. All 35 prior baseline RAM hashes and selected fields remain unchanged. Two earlier filtered startup negatives already had saved outer caller `0x80023F14`; caller agreement alone therefore remains insufficient.

### Reproduction, isolation and provenance

Private evidence is `/tmp/re-map-re3-filter-clear-20261106-1h16wi74/`. Run its `audit.py` with a nonexistent fresh output directory and the retained owned dependencies. It never rewrites frozen inputs. The first offline audit failed because it compared native HI,LO using GDB's LO,HI order. Pinned `cpu_types.h`/`gdb_server.cpp` establish the correct orders; only the comparator changed. `audit-attempts.json` and empty `audit-1` preserve that failed attempt. No native rerun was used to correct it.

| Frozen evidence | SHA256 |
| --- | --- |
| `report.md` | `da6b8c81577b7eb8b8f9fe16d373a02bdb38d34a8f6a30e2bf2261074322cf6d` |
| `audit-2/verification.json` | `6458cb6ab2c6555036638f28006737f9360ac30c2d0934597fa592ca49675db6` |
| `artifact-manifest.json`, 35 files | `20b72dba7a4fb58ce34c1f8a67a3762f389b910db826c57a00485dfbe70a421c` |

Before both game/state loads, both Achievements/Cheevos namespaces had achievements and RA integration disabled, `ApplyGameSettings=false`, no accounts/overrides, cards `None`, private paths, black output and muted audio. Settings remained byte-identical, SHA256 `f2efd1a6fe3e9d0cfbe1511bece44b9a8da0cc6849ad81e77362d92e917d425f`. Only host F1/F2 were pressed; all retained input words and both new native pressed masks are zero. No experimental guest writes or game-code patches were applied, no tracker/history was accessed and no game images were shared. Callbacks were removed, the client closed, only owned PID 69897 stopped with exit zero, and port 2391 was absent/bindable; CUA completion was recorded.

Final capture/save equality precedes client closure at 16:35:24Z. Pinned GDB disconnect behavior may resume an instance that was running at first connection. No guest read was observed between closure and process shutdown completed at 16:36:01Z. The final guest-state claim therefore ends at epoch 8; teardown execution remains unobserved. Campaign/Hard provenance, positive control admission and lifecycle/source ownership throughout future reads remain unresolved. Raw assets, RAM and saves remain private; hashes cannot replace missing evidence.

### Contribution and review

- 2026-11-06 UTC; Codex root, exact verified model `gpt-6.1-sol`, effort `xhigh`; authored the frozen source inspection, isolated native experiment and original offline audit above. This attribution retains the private report's scope and earlier human/media authorship.
- 2026-11-06 UTC; independent retained-evidence reviewer and documentation author, exact model `gpt-6.1-sol`, effort `xhigh`, reverified from matching session metadata/latest turn context; found no supported issues in the bounded evidence, checked all 35 manifest artifacts and pinned serialization/callback code, and appended this record/index row. A fresh offline rerun at `/tmp/re-map-re3-input007-docs-20261106-siEV8h/offline/verification.json`, SHA256 `3846eacf484996dd0e9bb4ba82095ec23a5a62168d9346bb9108e6e91d7f660c`, reproduced 169 sources, five captures and 35 prior baselines. Earlier independent review is `/tmp/re-map-re3-clear-independent-20261106-CggZME/independent-review.json`, SHA256 `7c4a4f638814fd4c9836be1295a2fbdf7d31d703af6299a4d1998f624e9555ff`. This contribution performed no new native/CPU experiment; cleanup was reviewed from retained records, with no independent CUA-event re-observation. No external review is claimed.
- 2026-11-06 UTC; Codex root, exact runtime model `gpt-6.1-sol`, independently checked all 35 artifact hashes, writer/source arithmetic, checkpoint payload equality, the unchanged document prefix and new links. A fresh offline audit reproduced 169 sources, five captures and 35 unchanged baselines. Integration review is `/var/folders/9d/q5n746z953bcs654g_1sqcy80000gn/T/re-map-re3-input007-root-20261106-09t8abnr/integration-review.json`, SHA256 `c3aa28074a932938cdca9c94360f7a7c597fe0bf732b554a37ec0152fd5a04fc`. This check adds no native execution or restoration.
- 2026-11-06 UTC; external snapshot reviewer, `gemini-3.8-flash`, high reasoning through Antigravity; returned no findings on the appended claim, original verifier, native windows and retained reports. The snapshot abbreviated the 35-row baseline matrix explicitly. Review checked arithmetic, dispatch/delay slots, source binding, checkpoint serialization, chronology, failed observations, cleanup boundaries and provenance. It ran no tools or native experiments and had no pending child work. This advisory review adds no gameplay validation. Claude Opus 5.5 remained disabled and supplied no review.
