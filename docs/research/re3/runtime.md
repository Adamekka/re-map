# RE3 isolated runtime baseline

[RE3 scope](../../re3.md) · [DuckStation startup](../../duckstation-startup.md)

This record establishes an isolated debugger baseline for the owned USA release of Resident Evil 3: Nemesis. The requested mode is Hard. **Hard selection and controllable campaign gameplay were not verified.** No runnable profile, room admission rule, item outcome or door outcome follows from this experiment.

## RE3-RUNTIME-001: Disc binding and isolated debugger access

Status: Candidate for a production runtime identity contract. The individual observations below were reproduced in the listed private sessions; they do not validate game-state interpretation.

### Identity

Independently extracted `SYSTEM.CNF` boots `cdrom:\SLUS_009.23;1`. The executable is 868352 bytes, SHA256 `2e143418e358b2c99995cdc1a88c387163fb751912c723b755614f38e236bd29`. Its PS-X header gives entry `0x80011B80`, load address `0x80010000` and text length 866304 bytes. These are executable virtual addresses and lengths, not host-process addresses. Serial is SLUS-00923, region NTSC-U, one supplied disc. No retail revision number beyond this exact executable identity was established.

The tested application is DuckStation `0.1-12083-g00e299795 (dev)`, source commit [`00e2997958d62de79d352cd680ec0c1ad95d491c`](https://github.com/stenzek/duckstation/tree/00e2997958d62de79d352cd680ec0c1ad95d491c). Executable SHA256 is `5c879677051cfb173002df22baee741c96fa8071c6fe1dd7e5454092bf128173`. The copied BIOS is the existing owned `psone-45a.bin`, SHA256 `aca9cbfa974b933646baad6556a867eca9b81ce65d8af343a7843f7775b9ffc8`. DuckStation identifies it as SCPH-101, v4.5 05-25-00 A, NTSC-U. No BIOS, executable, media, raw RAM, image or checkpoint is added to Git.

### Isolation and effective settings

All new resources and evidence are private under `/tmp/re-map-re3-runtime-20261105/`. The application was copied to `DuckStation.app` there. `portable.txt` and freshly written `settings.ini` sit beside its executable in `Contents/MacOS`. The pinned [`Core::SetDataRoot`](https://github.com/stenzek/duckstation/blob/00e2997958d62de79d352cd680ec0c1ad95d491c/src/core/core.cpp#L141) selects that directory when `portable.txt` exists. The resulting BIOS, card, checkpoint, shader, cache and game-settings directories are separate from the installed application. No tracker is launched and no user exploration history is opened or written.

Before every game/checkpoint boot and native checkpoint preparation, the private configuration was checked for these settings and for absent per-game overrides and account keys:

| Section | Effective values |
| --- | --- |
| `Main` | `SetupWizardIncomplete=false`, `PauseOnFocusLoss=false`, `PauseOnStart=false`, `SaveStateOnExit=false`, `ApplyGameSettings=false` |
| `Achievements` and `Cheevos`, each | `Enabled=false`, `ChallengeMode=false`, `UseRAIntegration=false`; no username, password or token keys |
| `Debug` | `EnableGDBServer=true`, `GDBServerPort=2353` |
| `CPU` / `GPU` | `ExecutionMode=Interpreter`, `Renderer=Metal` |
| `BIOS` | `PathNTSCU=psone-45a.bin`, `PatchFastBoot=true` |
| `MemoryCards` | `Card1Type=None`, `Card2Type=None`; any configured card paths are private |
| `Audio` | `OutputMuted=true`, `OutputVolume=0` |
| `Display` | `ShowOSDMessages=false`, `ShowFPS=false`, `ShowStatusIndicators=false` |
| `PostProcessing` | `Enabled=true`, `StageCount=1`; stage `private-black`, enabled |
| `AutoUpdater` | `CheckAtStartup=false` after the first BIOS-only launch opened an updater dialog |

The tested version reads achievement enablement from `Cheevos`, as shown in pinned [`Settings::Load`](https://github.com/stenzek/duckstation/blob/00e2997958d62de79d352cd680ec0c1ad95d491c/src/core/settings.cpp#L532). Checking only the older `Achievements` section would have been insufficient. Both sections were explicitly disabled before any game or checkpoint load. Private `gamesettings/` stayed empty, and no installed settings, cards, saves, credentials or histories were copied into the setup.

The original black shader always outputs opaque black to keep gameplay hidden. Its SHA256 is `b18291bd5172a924d55d7d8c8087ec3d52ec4641a7bf2b37918a6463e2123d64`. It loaded before RE3 boot. Private host-window captures sampled zero nonblack pixels in the central display region at BIOS and after RE3 boot. This sampling does not assert every window decoration is black. Audio was muted. No gameplay image is published.

`lsof` showed port 2353 free before each launch. The owned BIOS PIDs were 98612 and 8634; the first encountered the updater dialog and required termination by its recorded PID after SIGTERM did not exit. No game had loaded. RE3 ran as PID 22144, then PID 94965 for the private title-checkpoint boot. Each game listener was independently checked as TCP `127.0.0.1:2353` owned by its recorded PID. No connection was made to port 2345 or to an unidentified emulator. The application logs, launch arguments and `pid.json` identify the private executable and supplied CUE. Both game processes were stopped through their own app controls. `cleanup.json` records no remaining final PID and a free GDB port.

No guest-memory writes, health/ammunition aid, cheat activation or game-file changes were used. The shader and host key bindings affect presentation/input only. Native private checkpoints were created and restored, but are not committed. No ordinary memory-card save/load or persistence claim is made.

### Runtime code checks

The existing `DuckStationGdb` client interrupted the identified process, read RAM through framed requests, checked failures explicitly and resumed in cleanup. Initial research captures read the 2 MiB PS1 RAM range starting at virtual `0x80000000`, in 4096-byte requests. This was bounded discovery, not a proposed full-RAM polling loop.

Four 32-byte windows matched the owned executable in all six captured phases across both game processes:

| PS1 virtual address | Width, endian and mask | Window SHA256 |
| --- | --- | --- |
| `0x80011B80` | 32 opaque bytes; endian not applicable; `0xFF` per byte | `991d5c5970c6808e508b07718445e87db54dcd73482ea7c2e1bd59afdf32a978` |
| `0x80020000` | same | `74738eaf814214d606d79a3a61800ec32483d4da127c411e77fcbfbf14f354a1` |
| `0x80040000` | same | `558386f1922c49c09245a56e6677b21534c663a7a28a022281dea97e1bfe3f73` |
| `0x80060000` | same | `8ac6475c71ae7697b94cc5ae035e3f75fc863e8700a964f16772feef34a90afb` |

Concatenating those windows in table order gives SHA256 `fd92eec215e9e21702f7ce5c8e6edd1de0e5f91201165bc9cfdc3c8ffa70c728`. These checks bind sampled executable code to this disc; they do not compare every runtime executable byte, establish overlay identity or distinguish title/demo/campaign states. GDB register index 37 supplied the sampled PC as a four-byte little-endian register value with full mask `0xFFFFFFFF`; this is a register, not a RAM address.

## RE3-RUNTIME-002: Pose and lifecycle leads are insufficient for admission

Status: Candidate for field semantics. Rejected: treating plausible player mode, health, pose or inventory size alone as proof of controllable campaign gameplay.

External leads come from BrazilianHobbyist's Project RE: Visited RE3, pinned commit `0f95c6ded51ba07b9d405de51f712c9d5093976b`. The source describes its own SLUS-00923 research in [`05-settings-input-cheats.patch`, player-work comments and screen-relative movement](https://github.com/BrazilianHobbyist/Project-RE-Visited-RE3/blob/0f95c6ded51ba07b9d405de51f712c9d5093976b/patches/runtime/05-settings-input-cheats.patch#L547). It does not establish an exact executable fingerprint matching this disc. No external patch is applied and its runtime claims are not inherited as confirmation.

All addresses below are PS1 virtual addresses. Their RAM offsets are the virtual address minus `0x80000000`; none is a host pointer.

| Candidate field | Address | Width, endian and mask | What remains unverified |
| --- | --- | --- | --- |
| Player mode / routine | `0x800CCBC8` / `0x800CCBC9` | unsigned one byte each; endian not applicable; `0xFF` | Meaning of each value; title/demo/cutscene/death/control distinctions |
| World X / Y / Z | `0x800CCBF8` / `0x800CCBFC` / `0x800CCC00` | signed four bytes each, little-endian; `0xFFFFFFFF` | Controlled translation, axes, units, current actor binding and stale-pose handling |
| Facing | `0x800CCC32` | raw unsigned two bytes, little-endian; `0xFFFF`; proposed angle mask `0x0FFF` is a source lead | Controlled turns, orientation convention, scale and upper-bit meaning |
| Health | `0x800CCC90` | unsigned two bytes, little-endian; `0xFFFF` | Native damage/healing relation; no write performed |
| Inventory capacity | `0x800D225E` | unsigned one byte; endian not applicable; `0xFF` | Capacity semantics, scenario/difficulty and lifecycle relation |
| Proposed UI/status word | `0x800D4314` | unsigned four bytes, little-endian; full `0xFFFFFFFF`, proposed UI bits `0x00080808` | Native UI open/close behavior and other flag meanings |
| Later external inventory-open lead | `0x800C7961` | unsigned one byte; endian not applicable; `0xFF` | No controlled inventory cycle in this experiment |

The bundled `cheats.zip` entry `SLUS-00923.cht`, section `Infinite Health`, independently supplies the same health address. Archive SHA256 is `378974a3fdc3c1ba49d9bd500352a350ea1c2d40af1bbac6d6f6d80d84d3af96`. It is a lead, not proof of that field's semantics, and was never enabled. The later external [`10-smooth-motion-v2-controls.patch`](https://github.com/BrazilianHobbyist/Project-RE-Visited-RE3/blob/0f95c6ded51ba07b9d405de51f712c9d5093976b/patches/runtime/10-smooth-motion-v2-controls.patch#L1285) explicitly replaces UI gating by `0x00080808` because those bits can remain set after UI closes. That conflicting evidence is retained. This experiment does not validate either proposed UI gate.

Observed raw values:

| Private capture label | Mode / routine | X / Y / Z | Raw facing | Capacity | Health | Status word |
| --- | --- | --- | --- | --- | --- | --- |
| `initial-no-input` | 0 / 0 | 0 / 0 / 0 | 0 | 0 | 0 | `0x00000000` |
| `no-input-later` | 1 / 3 | 6672 / 0 / 18227 | 293 | 8 | 200 | `0x60000000` |
| `difficulty-selection` | 1 / 15 | 1685 / -1503 / -5653 | 1083 | 8 | 200 | `0x60000000` |
| `current-phase` | 0 / 0 | 0 / 0 / 0 | 0 | 0 | 0 | `0x60000000` |
| `after-cardless-choice` | 0 / 0 | 18669 / 0 / -24359 | 15776 | 8 | 200 | `0x00000000` |
| `post-menu-attempt` | 1 / 5 | -5337 / 0 / -12642 | 3597 | 8 | 200 | `0x60000000` |

`no-input-later` was captured on the first fresh disc boot before any guest controller input. Only host checkpoint/debugger actions had occurred. Its plausible active mode, pose, capacity and health therefore cannot prove a New Game campaign was started. The exact distinction between attract playback and other startup phases still needs a lifecycle field and controlled observation. `difficulty-selection` is an early private filename assigned before menu validation failed; it is **not** evidence of any difficulty selection. Likewise none of the later labels establishes player control. The nonzero raw facing 15776 while mode is zero also rules out accepting the raw halfword as an always-valid 0–4095 angle without lifecycle interpretation.

No stage, room, camera, difficulty or loaded-room pointer address was established. No RE1/RE2 address was substituted. Live item, door and story flags remain unidentified.

Later [RE3-NATIVE-001/002/003](native-contracts.md) derives candidate selectors and loaded-source witnesses from the executable and these retained captures, including explicit recorded-input and selector/source rejection evidence. It does not change this experiment's unverified Hard selection or campaign-control result.

## RE3-RUNTIME-003: Targeted input and bounded startup result

Status: Candidate. This establishes targeted host hotkeys and native cardless menu input, not a completed Hard start.

The private Swift 6 utility's `CGPreflightPostEventAccess()` and `AXIsProcessTrusted()` both returned false. Direct PID-targeted synthesized input did not create a checkpoint. Those attempted events are excluded from successful-input evidence; no global keys were sent and no permission setting was changed.

The available computer-use tool selected the exact private app path. F2 at BIOS produced the expected diagnostic that checkpoints require a disc with a valid serial. With RE3 inserted, F2 created native `SLUS-00923_1.sav`, whose header contains Resident Evil 3 - Nemesis and SLUS-00923. Native F1 and a separate `-statefile` launch restored only this experiment's private title checkpoint. This does not establish exact full-RAM restoration or memory-card persistence.

The initial controller binding used `DigitalController`, Cross on X, Circle on C, Start on Return and arrow directions. Printable Cross input did not yield a verified selection. In the second private game process, Cross was bound to F6 and Circle to F7. Those names/types are supported by the pinned [`DigitalController` bindings](https://github.com/stenzek/duckstation/blob/00e2997958d62de79d352cd680ec0c1ad95d491c/src/core/digital_controller.cpp#L182). Both configurations remained private. `ConfirmPowerOff=false` was added before the second boot solely to allow unambiguous cleanup of that test instance.

Private OCR then observed a native memory-card-not-inserted prompt and the subsequent choice to use or not use a memory card. Down followed by Cross selected the cardless path, followed by a title-menu capture. A later Up/Cross attempt did not produce a readable Hard selection. No emulator or guest patch was used to force difficulty, room, scenario or player control. No before/after campaign movement or room reentry is accepted from these attempts.

No images are included in this document or chat. Native checkpoint thumbnails remain private. Tesseract 5.5.4 could not open the temporary PNG by filename in this environment, producing a Leptonica file-open error; feeding the same encoded image through stdin worked. The first URL-based Vision request did not complete and was stopped. Passing image bytes to Vision completed, but did not supply a usable difficulty observation. These OCR failures are research limitations, not game-state facts.

## Reproduction, evidence and next interface

Private `prepare.py`, `start.py`, `capture.py`, `thumbnail.py`, `menu_ocr.py` and `native.swift` retain the exact preparation, launch, capture and text-only menu-reading steps. They require the owned BIOS/media and the private directory; they are not production APIs or defaults. `start.py` refuses an occupied port or enabled achievements/account settings/per-game overrides. `capture.py` verifies PID/listener ownership, uses the existing client, stops on failed reads and resumes before disconnecting.

Reproduce the accepted baseline by preparing the isolated portable copy, auditing settings before loading, booting BIOS to verify hidden presentation, stopping that PID, then booting the owned CUE on a verified-free port. Check the log's executable/title/serial, interrupt over GDB and compare the four windows with the exact extracted executable. Capture a no-controller-input startup sample before attempting New Game. Never treat that sample's player fields as a visit.

| Evidence | Private file and SHA256 |
| --- | --- |
| Earliest RAM | `initial-no-input.ram`, `170472ba409df40aca3fd12268fd921970a7fdc52dfe07f98b6747b2a6643420` |
| No-controller-input RAM with plausible player fields | `no-input-later.ram`, `c8d3067d106993a09d14f8da52d0e6a88bdd3932e4a823c1b94cfa03aa61dacb` |
| Later first-process zero-mode RAM | `current-phase.ram`, `0ab0c0caf4968ef3b2bbcaf23ca21dfe51589b4261efdd010338d8bf15c5fd67` |
| Second-process post-menu RAM | `post-menu-attempt.ram`, `0afebd6a98836d09d723a67ccb37b5d8b2399cb94defbd640191493438d6be04` |
| Native title checkpoint | `startup-menu.sav`, `a2167413c9601a199c63fd071b85b53c37f9c1129746d8db8f347c56d574e9a1` |
| Final effective settings | `DuckStation.app/Contents/MacOS/settings.ini`, `a55275c890ac8dee3930d1ce0b93e9a2865e7db4230fdff5143b12cde99c9ac1` |

`identity.json`, per-capture JSON, `capture-evidence.json`, `settings-preboot.ini`, `bios-launch.log`, `game-launch-first.log`, `game-launch.log`, `manifest.json` and `cleanup.json` retain the remaining provenance. Raw RAM and checkpoints are private temporary evidence and may disappear; their hashes are not a substitute for retained bytes. Private capture labels and hashes are not intended as user save locations.

The next implementation needs independently derived stage/room/camera fields and a loaded-room binding, a verified Hard/scenario field, and a lifecycle rule that excludes the observed no-input player state. Then obtain a readable Hard selection, demonstrate controlled turn/translation in a known room and observe an ordinary departure/reentry without writing room or pose fields. Only after that can the pose candidates support a map arrow or visits. Item/door/story banks require their own before/after evidence. Neither the code signature nor matching an external address table supplies these contracts.

Validation: all six private captures match the four disc-derived code windows. The final settings/account/override audit passed, the final owned process exited and port 2353 was free. The existing GDB transport regression suite passed all 39 tests in 2.05 seconds using `/var/folders/9d/q5n746z953bcs654g_1sqcy80000gn/T/re-map-improvement-_b504zzf/clean-venv/bin/python -m pytest tests/test_gdb.py -q`. This exercises the reused transport, not RE3 field semantics. No production source, profile, persistence format, UI, index or shared requirement changed.

## Contributions and review

- 2026-11-05; human user; supplied the owned media, authorized parallel RE3 research and selected Hard. No manual gameplay was requested or supplied for this experiment.
- 2026-11-05; Codex implementation agent, exact executing model `gpt-6.1-sol`; independently extracted the executable, prepared/ran/closed the isolated test instance, collected the GDB and targeted menu observations, preserved unsuccessful attempts and authored this document. Verified model attribution from `CODEX_THREAD_ID=01a1acad-c149-7681-a83a-52ea71c68fe4`, the matching rollout's `session_meta.payload.id` and latest `turn_context.payload.model`. No identity was inferred from a default model configuration.
- Direct verification checked disc-window equality, private PID/port ownership, disabled achievement settings in both sections, absence of account keys/per-game overrides, hidden display sampling, menu-evidence limits, address units/widths/masks and final cleanup. The parent owns integration and final review. No independent model review was performed or claimed; the parent's external review providers were unavailable.
