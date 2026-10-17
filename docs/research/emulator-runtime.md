# Emulator access and agent test setup

[Documentation index](../README.md) · [Claim index](../research.md)

## Local baseline 2026-09-22

Status: Candidate
Scope: macOS arm64 host only, no game revision yet
Environment: DuckStation 0.1-11752-g5fd366809 at /Applications/DuckStation.app, Python 3.14.7, settings.ini shows Debug/EnableGDBServer=false and GDBServerPort=2345
Authored: 2026-09-22; agent/tool: opencode; model: opencode/muse-spark-1.3-contributor-free
Basis: runtime observation of installed app and config, no game running
Claim: host has DuckStation with GDB server present but disabled, so the first live test is enabling that flag and reading 16 bytes at 0x80000000.
Evidence: Info.plist CFBundleShortVersionString 0.1-11752-g5fd366809, settings.ini Debug section, savestates folder contains non-RE1 serials such as SLUS-00551 and SLUS-00707.
Limits: no RE1 disc pinned, no room or item address, no live read yet.
History:
- 2026-09-22; opencode with model opencode/muse-spark-1.3-contributor-free; authored; local inspection only.

## RE1-CHEAT-001: third-party anchors, no room or pickup flag

Status: Candidate
Scope: SLUS-00551 primary, SLUS-00170 fallback, all unconfirmed at runtime
Environment: source inspection 2026-09-25, no local run
Authored: 2026-09-25; agent/tool: opencode; model: opencode/muse-spark-1.3-contributor-free
Basis: source inspection of cheat DBs and code lists
Claim: health anchor 0x800C51AC appears for both SLUS-00551 and SLUS-00170 as 16-bit. Ammo anchors differ by revision, 0x800418F8 on 00551 versus 0x8003F574 on 00170. Inventory and chest ranges around 0x800C8724 to 0x800C878E are useful anchors for item experiments. No room, stage, or acquired-flag address was found in any accessible source. Location Modifiers on GameHacking and RetroAchievements logic are blocked with 403 and remain the top manual follow-up.
Evidence:
- https://www.psxdatacenter.com/games/U/R/SLUS-00551.html health and ammo codes for 00551
- https://raw.githubusercontent.com/duckstation/chtdb/master/cheats/SLUS-00551.cht thin patch file with Quick Turn, invincibility, rocket hits
- https://raw.githubusercontent.com/duckstation/chtdb/master/cheats/SLUS-00170.cht full health, timer, ammo, maps, doors, chest ranges
- https://raw.githubusercontent.com/duckstation/chtdb/master/cheats/SLUS-00747.cht mirrors 00170 anchors, 00551 file does not repeat them
Limits: GameShark 80 means 16-bit LE write, 30 means 8-bit, D0 and E0 are conditionals not state, 50 is slide modifier, 90 and A6 and A7 are patches not state cells. Never generalize 00170 to 00551 without a runtime test.
History:
- 2026-09-25; opencode with model unknown; reviewed; fetched cheat files, recorded blocked pages.
- 2026-09-25; opencode with model opencode/muse-spark-1.3-contributor-free; authored; summarized into this entry, still Candidate.

## RE1-AUTO-001: automated boot and GDB without manual play is feasible

Status: Candidate
Scope: DuckStation macOS 0.1-11894 dev binary flags plus local 0.1-11752 install, no RE1 boot yet
Environment: source and CLI inspection 2026-09-25, no game running
Authored: 2026-09-25; agent/tool: opencode; model: opencode/muse-spark-1.3-contributor-free
Basis: source inspection and --help output
Claim: DuckStation can relaunch per room with -nogui -statefile path, no disc path needed. GDB on 127.0.0.1 port 2345 pauses on connect, resumes on c, pauses on 0x03 interrupt, reads with m packets up to 8192 bytes. Safe loop is connect, c to run, 0x03 to pause, burst m reads, c to resume. No TAS, movie, Lua, or scripted input channel was found. Movement needs OS-level key or pad injection, or prepared savestates per room.
Evidence: qthost.cpp ParseCommandLineParametersAndInitializeConfig, -batch, -nogui, -statefile, -state index, -resume, src/core/gdb_server.cpp ClientSocket OnConnected PauseSystem, PollUntil per frame, local settings.ini Debug section.
Limits: m while running is unverified for safety, -nogui display needs on macOS unverified, no virtual pad test, no RE1 boot or GDB read yet.
History:
- 2026-09-25; opencode with model unknown; reviewed; CLI and source inspection, no runtime test.
- 2026-09-25; opencode with model opencode/muse-spark-1.3-contributor-free; authored; summarized into this entry, still Candidate.

## RE1-CHEAT-002: GameHacking Director's Cut set has no room codes

Status: Candidate
Scope: SLUS-00551 Director's Cut NTSC-U, 56-code libretro set
Environment: file inspection 2026-09-25, no codes activated
Authored: 2026-09-25; GameHacking contributors as code authors; provided by human user as file; filed by opencode with model opencode/muse-spark-1.3-contributor-free
Basis: source inspection of third-party cheat file
Claim: the set filed at docs/leads/gamehacking_slus00551_ntscu.cht holds player position modifiers at 0x800A4BE4 through 0x800A4BF8, health at 0x300C51AC, ammo at 0x8003F574, enemy health at 0x800C532C, and chest and inventory codes around 0xC8724 and 0xC877C. It holds no Main or Sub location codes and no item flag codes, so the Location Modifiers category seen in search excerpts belongs to a different game page. Anchor cross-checks pass: health, enemy, and chest ranges match the RA notes and the runtime reads, and the ammo address equals the SLUS-00170 anchor, hinting shared layout without proving it.
Evidence: docs/leads/gamehacking_slus00551_ntscu.cht 6083 bytes, 56 codes, donated file from the user Downloads folder.
Limits: codes never activated, position modifiers unused by the tracker, cross-revision equality untested at runtime.
History:
- 2026-09-25; human user; provided; downloaded the libretro file.
- 2026-09-25; opencode with model opencode/muse-spark-1.3-contributor-free; filed; parsed all 56 codes, still Candidate.

## RE1-EMU-007: asynchronous GDB stops must not complete memory reads

Status: Confirmed for the tested DuckStation revision's stop notification and reply alignment; original UI trigger inferred
Scope: Resident Evil Director's Cut USA SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`, Jill in rooms `00-09` and `00-15`; no new game addresses or item rules
Environment: macOS arm64, DuckStation `0.1-11894-gc66b2694d`, GDB TCP port 2345, 2026-09-29
Authored: 2026-09-29; Codex with model GPT-6.1 Sol
Basis: tracker logs, controlled socket reproduction, pinned DuckStation source inspection, and live pause/resume reads
Claim: an asynchronous `Sxx` or `Txx` stop notification is separate from the outstanding memory response. Treating it as memory data produces a short reply and leaves the actual response queued for the next address. The client must acknowledge complete stop packets and continue waiting for the same memory request. Unframed socket drains can also split or discard replies. Checksum, framing, or timeout failures close the connection so later requests cannot consume stale responses.
Evidence:
- The ignored local `logs/tracker.log` records room `00-15` at 22:31:25.270, then a signature read at PS1 VA `0x8004484C` failing with `short reply: 1 of 32` at 22:31:25.372. The next signature poll repeats the first window's hash for the second address and shifts the other hashes one address later, producing a false wrong-game result and a waiting map. Similar short replies recur at 22:31:34, 22:31:52, and 22:32:17. The log stores hashes rather than executable bytes.
- A controlled socket sent a framed `S05` before a 32-byte memory response. The previous client returned the short-reply failure, then consumed the earlier address's response on its next request. Regression tests in `tests/test_gdb.py` cover `S05`, extended `T02`, multiple notifications, continue, running and already-paused interrupts, pending stop-query replies, one-byte TCP fragmentation, damaged checksums, short and non-hex replies, timeout closure, and an aligned GDB error reply. The full suite passed 57 tests.
- DuckStation source at commit `c66b2694d`, [`src/core/gdb_server.cpp` lines 1314-1337](https://github.com/stenzek/duckstation/blob/c66b2694d/src/core/gdb_server.cpp#L1314), sends a framed stop notification from `OnSystemPaused` after a resume. The [GDB stop-reply specification](https://sourceware.org/gdb/current/onlinedocs/gdb.html/Stop-Reply-Packets.html) identifies `S` and `T` signal replies separately from memory data. These external sources support packet interpretation, not game-state validation.
- With the corrected client connected to the real emulator, send interrupt byte `0x03` without first consuming its notification, verify the profile's five 32-byte signature windows, read the room, resume, and verify all windows again. Repeat five times. Every cycle logged a real `S02` notification and matched the pinned concatenated signature SHA256 `23311956abca97ba2522be37f6d45457f4ebbda529ede887a9d0a6d6a2a56958` both paused and resumed, with room `00-09`. Local metadata log `/tmp/tasks/re-map/gdb-live-check.log` SHA256 `1f25d8f64d9e58a3cf2be0c7e420de1e61c9ea7ec6ab08a37a25309a7969749d` remains outside Git. The experiment did not write RAM or load game saves.
- Review identified that requiring a fresh interrupt notification would time out when DuckStation was already paused. Source at the same commit, `gdb_server.cpp` lines 1235-1242 and 1314-1322, only sends the notification after a resume; lines 416-425 and 1340-1347 answer an explicit `?` stop query. The client now sends that query after the interrupt. Three live cycles each interrupted the running game, checked the signature, interrupted again while paused, checked the signature, resumed, and checked again. Every check matched in room `00-09`; each second interrupt took under 1 ms. Local metadata log `/tmp/tasks/re-map/gdb-interrupt-check.log` SHA256 `de1798cbd5ed6af838efbc50030b1aa858121fcb426913142c78bbd081cd3d7e` remains outside Git.
Limits: the original log did not capture raw stop packets, so its precise UI pause trigger remains inferred from the reproduced failure and matching server behavior. The live interrupt experiment directly captured `S02`; `T` handling was tested with synthetic packets. Normal save/load, savestate transitions, other DuckStation versions, and extended GDB protocol features were not retested. A genuinely damaged connection requires a tracker restart; automatic reconnection is not implemented. This finding does not expand item coverage or establish room completion.
History:
- 2026-09-29; human user; reproduced tracker failures after file logging was enabled and approved the packet-handling correction.
- 2026-09-29; Codex with model GPT-6.1 Sol; authored and implemented; inspected the logged hash shifts and pinned server source, reproduced the old failure, ran regression tests, and performed five live pause/resume cycles.
- 2026-09-29; external reviewers Gemini 3.1 Pro (High) and Gemini 3.8 Flash (High) through agy; reviewed the supplied client diff and tests before the stop-query correction, without running experiments. Both flagged the already-paused interrupt regression. Claude Opus 4.6 (Thinking) timed out after five minutes without returning review content.
- 2026-09-29; Codex with model GPT-6.1 Sol; verified review candidates against the pinned source and code, corrected the interrupt regression, added two regression tests, and performed three live running/already-paused cycles. Restarted the logged map and observed valid room `00-09` output.

## RE1-EMU-008: native write-watch stops and single-step framing

Status: Candidate; pinned source contract and one live CPU-write probe
Scope: DuckStation `0.1-11894-gc66b2694d`, commit `c66b2694da65cece8886ed3d4a069098831f8358`; Resident Evil Director's Cut USA SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`
Environment: isolated portable DuckStation on macOS, native GDB localhost port 2345; Python 3.14.8
Authored: 2026-10-05; Codex root; model: GPT-6.1 Sol
Basis: primary emulator source inspection, a live CPU write/step/remove probe, fragmented-packet regressions
Claim: this DuckStation server exposes client-owned CPU write callbacks through GDB `Z2`/`z2`. The observed stop is readable after the writing instruction finishes. Single stepping advances one instruction and produces a separate stop reply. This establishes the transport needed for RE1-EVENT-011, not complete event execution history.

Evidence:

- [Pinned GDB server](https://github.com/stenzek/duckstation/blob/c66b2694da65cece8886ed3d4a069098831f8358/src/core/gdb_server.cpp#L879) accepts write-watch lengths 1..256. `AddBreakpoint` at lines 1139..1190 creates debugger callbacks without patching guest instructions. `OnBreakpointHit` at lines 1371..1403 emits `T05watch:<actual access address>;` and suppresses a duplicate paused notification. [Disconnect cleanup](https://github.com/stenzek/duckstation/blob/c66b2694da65cece8886ed3d4a069098831f8358/src/core/gdb_server.cpp#L1266) removes that client's callbacks. When the last client leaves, it resumes if the first client attached while the emulator was running.
- [CPU interpreter](https://github.com/stenzek/duckstation/blob/c66b2694da65cece8886ed3d4a069098831f8358/src/core/cpu_core.cpp#L1605) checks a byte store before executing it. The interpreter completes the instruction before exiting to network processing at lines 2660..2673. `MemoryBreakpointCheck` at lines 2594..2600 checks the access's starting address; a wider store starting before a watched byte can bypass it. Emulator savestate restoration is not a CPU write.
- GDB register index 37, command `p25`, reads the next native PC; index 4 reads A0. Replies contain four little-endian bytes. [Single-step command](https://github.com/stenzek/duckstation/blob/c66b2694da65cece8886ed3d4a069098831f8358/src/core/gdb_server.cpp#L842) acknowledges `s` and calls `System::SingleStepCPU`. [The system operation](https://github.com/stenzek/duckstation/blob/c66b2694da65cece8886ed3d4a069098831f8358/src/core/system.cpp#L2419) schedules one instruction. The interpreter then pauses with `S05`. Continue acknowledges without a data reply. Existing RE1-EMU-007 explains asynchronous stop handling during reads.
- The live probe verified the game signature and initializer hash, installed a one-byte write watch on PS1 virtual `0x800CF688`, resumed, and caught the game's regular selected-event-record pointer store. This address is the little-endian u32 field from RE1-EVENT-005; watching its first byte was sufficient for this store. The server reported signal 5 and address `0x800CF688`; `p25` returned `0x80025D2C`. Reading the pointer already returned `0x800CF68C`. One step advanced PC to `0x80025D30`. Removing the watch and resuming produced `NoStop` in the subsequent bounded wait. No guest RAM writes, injected activity or patched instructions were used.
- `tests/test_gdb.py` checks fragmented replies, ACK-only idle waits, stops interleaved with register/memory replies, rejected watch commands, malformed watch/register replies and nested write stops during stepping. Protocol bytes in these tests are synthetic.

Reproduction artifacts remain outside Git in `/tmp/tasks/re-map/event-breakpoints/`. `probe.py` records the live sequence; `probe.json` SHA256 is `34fb1d3b5b34c503bc95796cc27f990efb87fb2752cab01e25751ad5f13c0993`. Downloaded source files are pinned to the commit above.

Limits: the live probe watches the selected-record pointer, not an activity transition. It validates this transport/stop phase and one sequential step, not the full RE1 initializer, natural event activation, return-delay stepping, cleanup after an actual broken connection, or other emulator versions. Exact-width byte watches do not cover every overlapping access or savestate load. Other clients must be stopped during these experiments.
History:

- 2026-10-05; Codex root, GPT-6.1 Sol; inspected the pinned server/interpreter/system code, ran the isolated probe and implemented bounded stop/register/watch/step operations. Runtime evidence remains limited to the sequence above.

## RE1-CHEAT-003: temporary health lock for isolated map validation

Status: Confirmed observed health write in this setup and the named Laboratory combat observations; poison and instant-death protection remain untested
Scope: SLUS-00551 executable identity in RE1-SAVE-005; Chris, private Guardhouse checkpoint `m-guardhouse-return.sav` and Laboratory checkpoints in RE1-MAP-015
Environment: isolated DuckStation 0.1-11894-gc66b2694d, commit `c66b2694da65cece8886ed3d4a069098831f8358`; RetroAchievements disabled and not logged in; native cheat editor, ordinary controls and read-only GDB
Authored: 2026-10-08; Codex root; model: GPT-6.1 Sol
Basis: user-authorized test patch, earlier health leads RE1-CHEAT-001/RE1-MAP-012, native enablement and captured RAM comparison
Claim: the custom GameShark code `800C51AC 008C`, activated at frame end, holds the little-endian u16 at PS1 virtual `0x800C51AC`, RAM offset `0xC51AC`, at 140 during the recorded Guardhouse route. This is a test patch, not a new production profile field or proof of general invincibility.

The first unpatched attempt entered Room 001 `03-01` and then died before reaching B1. `n-room001-settled.bin`, SHA256 `711dfe0c4bc4d5180d8ab7a697825c6f29d3ba3d31d8291e796dd4bc2568329c`, contains the health word 65529; the native Capcom/title sequence followed. This attempt adds no new floor-plan coverage. The subsequent attempt restored the same checkpoint and used a direct route through Passage and Room 002, with the health patch enabled. The patch and changed route are the changed conditions for this retry.

The bundled Invincibility patch `A7038CCA 10402400` was tried first. Its effect was not established, and it was disabled before the custom health lock was enabled. The native editor and emulator log then reported only `Validation health lock` enabled. Private custom file `n2-validation-cheats.cht`, 203 bytes, SHA256 `23a323e04c53d54f1880a986afb2430fc96b381a331dea678894dc31730b3bf9`, records the exact code, description and activation.

At 15:16:17 UTC, `n2-floor-1` reads health 53. After enabling the custom lock, `n2-health-lock-active` at 15:20:46 reads 140. The bytes at PS1 RAM offsets `0xC86B4..0xC8723` are identical in those two captures. Entry still publishes the same three available Blue Herbs and unresolved coverage. All eight captures in RE1-MAP-014 preserve the profile's full 32-byte acquisition bank at PS1 virtual `0x800C86DC`, and all captures after activation read health 140. Each capture still passes the pinned executable identity checks.

In the initial Guardhouse run, no infinite-ammunition patch was enabled, no weapon was fired, and no combat or poison damage was deliberately tested. A frame-end health write does not establish protection from instant-death scripts. The isolated emulator was closed afterward, its global settings restored byte-for-byte from the pre-test backup, and its new cheat/per-game settings archived with private evidence so the patch is no longer enabled by default. The user's normal emulator settings were untouched.
History:

- 2026-10-08; human user; authorized temporary infinite-health and infinite-ammunition patches to avoid repeated test deaths.
- 2026-10-08; Codex root, GPT-6.1 Sol; recorded the failed route, configured and observed the scoped health lock, compared captured flags, kept achievements disabled, and restored the temporary setup. No broader health-address validation state was promoted.
- 2026-10-08; Codex root, GPT-6.1 Sol; reused only this health lock for RE1-MAP-015. Native zombie and Chimera grabs/strikes occurred, and Chris survived repeated Chimera attacks while movement and firing were interrupted. All thirteen successful-route captures read 140 and preserve their route's acquisition bank. A zombie was killed through ordinary aim/fire input. No ammunition patch was enabled; the alternate Chris inventory showed three Colt Python rounds. This establishes the recorded survival and health values, without establishing immunity to stagger, poison or instant death. Closed the emulator and restored its original settings and absent cheat/per-game files afterward.

## RE1-CHEAT-004: bundled Invincibility patch does not match the pinned executable

Status: Rejected for this revision and the named validation setup
Scope: RE1 Director's Cut NTSC-U SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`, Jill Original, Tea Room `05-04`
Environment: RE1-MAP-017's isolated DuckStation 0.1-11894-gc66b2694d, session `x`, RetroAchievements disabled, RE1-CHEAT-003 health lock still active
Authored: 2026-10-09; Codex root; model: GPT-6.1 Sol
Basis: bundled code inspection, native cheat-list enable/disable, captured RAM and native hunter stagger; pinned emulator source inspection explains the failed comparison
Claim: enabling the bundled SLUS-00551 Invincibility code did not change its target instruction or remove the hunter stagger that blocked this route. It is not a usable validation patch for this pinned executable.

The app's `Contents/Resources/cheats.zip` entry `SLUS-00551.cht` supplies an EndFrame Gameshark code `A7038CCA 10402400`. Archive SHA256 is `4d1fa520de5d656aa3c08c8bd1106991e0e1774fb2141fdc8ec49ff3119f6c42`; the complete entry's SHA256 is `98b94a2370a0c7abcb731a7d1144f8f0b6d91670708844822fb69bcee6d17419`. No game or cheat archive is added to Git.

Reproduction: after the native Tea Room shortcut refuses passage and repeated hunter attacks block movement, select the bundled Invincibility entry through the isolated emulator's Cheats dialog. Verify its enabled checkbox and per-game configuration, resume the native encounter, then capture RAM. Hunters still interrupt Jill. Disable the entry through the same dialog and verify the per-game configuration contains only the health lock before resetting and normally loading session `y`. The isolated setup was restored after testing as recorded in RE1-MAP-017.

| Capture | Patch state | PS1 RAM word at offset `0x38CC8`, width 4, little endian | RAM SHA256 |
| --- | --- | --- | --- |
| `x-tea-blocked` | Not enabled | `0xA422AB00` | `f17fb605231479b8e4fda340de03898fd532f26a03c191c116a05d4b22e8243f` |
| `x-invincibility-attempt` | Enabled | `0xA422AB00` | `f7bc0e9c8f7348059c44bd632732c1883f96eaa91a6bad23701164c3f3db8b95` |

DuckStation's pinned `ExtConstantWriteIfMatchWithRestore16` execution checks a 16-bit value against the upper half of the code's value and writes its lower half only on a match. See [cheats.cpp, lines 2447–2458](https://github.com/stenzek/duckstation/blob/c66b2694da65cece8886ed3d4a069098831f8358/src/core/cheats.cpp#L2447-L2458) and [the A7 instruction enum](https://github.com/stenzek/duckstation/blob/c66b2694da65cece8886ed3d4a069098831f8358/src/core/cheats_private.h#L92). This code expects `0x1040` at PS1 RAM offset `0x38CCA`, width 2, little endian, before writing `0x2400`. Both captures contain `0xA422` there. The nonmatching value explains the lack of instruction replacement; the native stagger independently shows that the attempted setup did not solve this gameplay blocker.

Limits: the failed code is not evidence for an alternative invincibility address or for other executable revisions. No replacement immunity or ammunition patch was introduced. The working health lock continued to hold captured health at 140 but did not prevent grabs, stagger or poison poses.
History:

- 2026-10-09; Codex root, GPT-6.1 Sol; tested and disabled the bundled patch, compared its unchanged target word and checked the pinned conditional-write implementation. Rejected this setup and obtained B1 validation through the eastern Mansion route instead.

## RE1-EMU-009: gameplay endurance and reconnect recovery

Status: Confirmed for the tested isolated setup; one gameplay state, one kill/relaunch cycle
Scope: Resident Evil Director's Cut USA SLUS-00551 on isolated DuckStation 0.1-11894-gc66b2694d, GDB port 2345, achievements disabled; Art Room `00-07` Training Jill gameplay from a `-statefile` load; tracker at the RE1-LIFECYCLE-002 gated commit
Environment: the RE1-LIFECYCLE-002 scratch emulator copy and owned CUE; Python 3.14.8; no game files, captures, or disc bytes added to Git
Authored: 2026-10-10; agent/tool: opencode; model: opencode/muse-spark-1.3-contributor-free
Basis: an eight-minute continuous live tracker run in settled gameplay, a mid-run emulator kill, and a relaunch with the same checkpoint
Claim: the gated tracker holds a stable `Display` verdict in settled gameplay with no status flapping, survives an emulator kill through `ReadFailure` into its reconnect loop without crashing or publishing stale state, and resumes `Display` with retained visit history after relaunch.
Evidence:
- Continuous `tools/track.py` logged `Poll display` 15 times over about seven minutes in Art Room `00-07` (Map and Ink Ribbon available, `INCOMPLETE`), with no other poll status. After `SIGTERM` to the emulator, the log shows 2 `Poll read-failure` lines then repeated `GDB reconnect failed: connect failed` lines at the one-second cadence; the tracker stayed up and the map would have shown waiting throughout.
- Relaunching the same `-statefile` checkpoint logged `GDB reconnected and resumed` followed by further `Poll display` lines, 20 in total, with the same room, items, and `Visited: yes` history retained. Tracker, emulator, and GDB logs stay outside Git.
Limits: one settled gameplay state and one kill/relaunch cycle only. `SIGTERM` shutdown of a statefile-loaded instance again took over a minute before the process exited; a stuck shutdown would need `SIGKILL` like the RE1-LIFECYCLE-002 setup note. No save, menu, transition, or multi-room traversal was exercised in this run. Chris, other revisions, and other emulator versions remain untested.
History:
- 2026-10-10; opencode with model opencode/muse-spark-1.3-contributor-free; ran the endurance, kill, and relaunch sequence in the isolated copy, then stopped both processes. No production code changed.
