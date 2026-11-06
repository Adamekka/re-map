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
