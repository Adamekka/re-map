# RE3 paused-menu input attempt

[RE3 scope](../../re3.md) · [Original runtime baseline](runtime.md) · [Native lifecycle candidates](native-contracts.md)

## RE3-INPUT-001: targeted paused-menu input remains insufficient to verify Hard

Status: Candidate input procedure; **Hard selection, campaign control and room reentry remain unverified**. This records an interrupted experiment so a later run can use its evidence without inheriting an unsupported success claim.

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
