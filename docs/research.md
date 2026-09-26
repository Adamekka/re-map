# Research: external PS1 RAM access from DuckStation on macOS

Scope: first target is RE1 PS1 in DuckStation on macOS. All findings below are
source inspection only against upstream DuckStation master at the pinned
commit. Nothing here is runtime confirmed on the target RE1 revision.

Pinned source: commit `2c9866ef9e6a3bd1803f0cd5dffd294c047d74b9`,
dated 2026-09-22T06:26:53Z per GitHub commits API on 2026-09-22.
Treat line numbers as approximate. File paths and symbol names are the stable
reference.

## Ranked options for 10-30 Hz external polling

### 1. Built-in GDB remote server over TCP loopback (most maintainable)

Use the documented GDB remote serial protocol packets `m` and `M` to read a
small set of known addresses at 10-30 Hz. This is the only external TCP API
found in the source. It is toggled by settings and needs no emulator fork.

Why first: documented protocol, small code, no pointer scans, works across
DuckStation updates as long as the GDB packet set stays stable. Poll only the
bytes needed. A full 2 MB dump per tick would not fit 10-30 Hz through the
`MAX_PACKET_SIZE` framing.

### 2. Savestate files plus a small diff tool (best for reverse engineering)

Use `.sav` savestates for controlled before/after comparisons. RAM is inside,
but it is compressed and framed, so this path is for finding candidates, not
for live polling.

Why second: reliable and repeatable for discovery. Not suitable as the live
tracker path because each sample needs a file write, header parse, and
decompress.

### 3. Host process memory reading, EmuHook style (fast but brittle)

Read the emulator process directly with OS memory APIs and a resolved base
address or pointer chain. EmuHook 0.6.8 proves this works for DuckStation PSX
on Windows and already has RE1 overlay demos. On macOS this needs new native
code with Mach VM APIs, and it breaks with ASLR, layout changes, SIP, and
code signing limits.

Why last on macOS: highest bandwidth, weakest maintainability. Keep as a
fallback if the GDB path cannot hit the needed rate or cannot see an address.

### Explicitly not recommended yet

- `Hacks/ExportSharedMemory` on macOS. The macOS backend creates an anonymous
Mach memory entry with no shared name, so there is no documented named object
for a second process to open. It still changes the internal mapping, but it is
not a macOS IPC path by itself.
- Screen scraping or UI automation of the Qt debugger. The debugger is
in-process only and gives no external API.

## RE1-EMU-001: GDB server exposes RAM reads and writes over TCP

Status: Candidate
Scope: DuckStation master, all platforms with Qt build, no game revision yet
Environment: source inspection on 2026-09-22, commit 2c9866ef9e6a3bd1803f0cd5dffd294c047d74b9, no local run
Authored: 2026-09-22; agent/tool: opencode with model opencode/muse-spark-1.3-contributor-free
Basis: source inspection
Claim: DuckStation has a TCP GDB server on 127.0.0.1 with configurable port,
default 2345, supporting `m` read, `M` write, registers, breakpoints, continue
and step, plus `qXfer:memory-map:read`. RAM appears at `0x00000000`,
`0x80000000`, and `0xA0000000` with length `0x00800000`, and scratchpad at
`0x1f800000` length `0x400`.
Evidence:
- `src/core/gdb_server.h`: `GDBServer::Initialize(u16 port)`, `HasAnyClients`, `PollUntil`, `Shutdown`.
- `src/core/gdb_server.cpp`: `MAX_PACKET_SIZE = 16384`, `MAX_MEMORY_READ_SIZE = MAX_PACKET_SIZE / 2`, `Cmd$m` uses `CPU::SafeReadMemoryBytes`, `Cmd$M` uses `CPU::SafeWriteMemoryBytes` plus `InvalidateMemoryWrite`, `MEMORY_MAP_XML` lists the RAM ranges above, `Initialize` parses `127.0.0.1` and creates a listen socket.
- `src/core/settings.h`: `u16 gdb_server_port = DEFAULT_GDB_SERVER_PORT`, `bool enable_gdb_server = false`, `DEFAULT_GDB_SERVER_PORT = 2345`.
- `src/core/settings.cpp`: loads `Debug/EnableGDBServer` and `Debug/GDBServerPort`, saves the same keys.
- `src/core/system.cpp`: starts the server when `g_settings.enable_gdb_server` is set, restarts it when the port or enable flag changes, calls `GDBServer::PollUntil` and `GDBServer::Shutdown`.
- `src/duckstation-qt/debuggingsettingswidget.cpp`: exposes `Enable GDB Server`, `GDB Server Port`, and `Export Shared Memory` as tweak options.
- URLs: https://github.com/stenzek/duckstation/blob/2c9866ef9e6a3bd1803f0cd5dffd294c047d74b9/src/core/gdb_server.cpp, https://github.com/stenzek/duckstation/blob/2c9866ef9e6a3bd1803f0cd5dffd294c047d74b9/src/core/gdb_server.h, https://github.com/stenzek/duckstation/blob/2c9866ef9e6a3bd1803f0cd5dffd294c047d74b9/src/core/settings.h, https://github.com/stenzek/duckstation/blob/2c9866ef9e6a3bd1803f0cd5dffd294c047d74b9/src/core/system.cpp
Limits: no local run. Untested whether reads pause emulation, what jitter looks like at 10-30 Hz, how the server behaves during pause, rewind, runahead, or save/load, and whether the macOS release build enables it by default. Full RAM length in the XML is 8 MB but normal PS1 RAM is 2 MB through `RAM_2MB_SIZE`; 8 MB mode is a setting.
History:
- 2026-09-22; opencode with model opencode/muse-spark-1.3-contributor-free; authored; source inspection only, no runtime test.

## RE1-EMU-002: shared memory export and exported RAM symbols

Status: Candidate
Scope: DuckStation master, OS dependent behavior, no game revision yet
Environment: source inspection on 2026-09-22, commit 2c9866ef9e6a3bd1803f0cd5dffd294c047d74b9, no local run
Authored: 2026-09-22; agent/tool: opencode with model opencode/muse-spark-1.3-contributor-free
Basis: source inspection
Claim: `Bus::AllocateMemory` takes `export_shared_memory`. When enabled, RAM,
BIOS, and handler tables live in shared memory and `Exports::RAM`,
`Exports::RAM_SIZE`, and `Exports::RAM_MASK` publish the RAM pointer. The
external name exists on Linux and Windows but not on macOS.
Evidence:
- `src/core/bus.h`: `RAM_2MB_SIZE = 0x200000`, `RAM_8MB_SIZE = 0x800000`, `AllocateMemory(bool export_shared_memory, Error* error)`, `ReallocateMemoryMap`, `CleanupMemoryMap`.
- `src/core/bus.cpp`: `Exports` namespace comment says `Exports for external debugger access`, sets `Exports::RAM` to `g_bus.unprotected_ram`, sets size and mask in `SetRAMSize`, clears them in `ReleaseMemoryMap`.
- `src/core/system.cpp`: reads `Hacks/ExportSharedMemory`, passes it to `Bus::AllocateMemory`, calls `Bus::ReallocateMemoryMap` when the setting changes.
- `src/common/memmap.h` and `src/common/memmap.cpp`: `GetFileMappingName`, `CreateSharedMemory`, `MapSharedMemory`. Linux builds `duckstation_<pid>` through `shm_open` or `memfd_create`. Windows uses `CreateFileMappingW` with `duckstation_<pid>`. macOS `GetFileMappingName` returns an empty string and `CreateSharedMemory` calls `mach_make_memory_entry_64` with an anonymous entry.
- URLs: https://github.com/stenzek/duckstation/blob/2c9866ef9e6a3bd1803f0cd5dffd294c047d74b9/src/core/bus.cpp, https://github.com/stenzek/duckstation/blob/2c9866ef9e6a3bd1803f0cd5dffd294c047d74b9/src/core/bus.h, https://github.com/stenzek/duckstation/blob/2c9866ef9e6a3bd1803f0cd5dffd294c047d74b9/src/common/memmap.cpp
Limits: did not verify any external process attaching on macOS. On macOS the empty shared name means this setting alone is not an IPC path. Did not verify SIP, code signing, or `task_for_pid` limits for reading the host process.
History:
- 2026-09-22; opencode with model opencode/muse-spark-1.3-contributor-free; authored; source inspection only, no runtime test.

## RE1-EMU-003: direct process memory reading and EmuHook precedent

Status: Candidate
Scope: DuckStation PSX on Windows for EmuHook, macOS path is unbuilt
Environment: source inspection plus EmuHook README version 0.6.8 on 2026-09-22, no local run
Authored: 2026-09-22; agent/tool: opencode with model opencode/muse-spark-1.3-contributor-free
Basis: source inspection and external project documentation
Claim: EmuHook supports DuckStation for PSX through process handle reads and per-emulator base resolution. Its README lists DuckStation as PSX supported and shows RE1 real-time map, health overlay, autosplitter, entity radar, inventory viewer, and IGT demos. The core method is Windows `OpenProcess` plus pointer handling in AutoHotkey v1, with 64-bit pointers needing AutoHotkeyU64. There is no macOS EmuHook path verified here.
Evidence:
- EmuHook README support table marks DuckStation as PSX supported.
- README notes DuckStation needs AutoHotkeyU64 because of 64-bit pointers.
- README demo section lists `[PC & PSX] Resident Evil 1 (1996) - Real Time Map, Health Overlay & AutoSplitter` and `[PC & PSX] Resident Evil 1 (1996) - Entity Radar, IGT, Inventory Viewer`.
- URLs: https://github.com/elModo7/EmuHook, https://raw.githubusercontent.com/elModo7/EmuHook/main/README.md
Limits: did not inspect EmuHook DuckStation pointer chains or offsets, did not run it, and did not verify which DuckStation version or RE1 revision the demos used. Treat as precedent that process memory reading can work, not as a stable address.
History:
- 2026-09-22; opencode with model opencode/muse-spark-1.3-contributor-free; authored; README inspection only, no runtime test.

## RE1-EMU-004: savestate format wraps RAM in a compressed framed file

Status: Candidate
Scope: DuckStation master savestate format, no game revision yet
Environment: source inspection on 2026-09-22, commit 2c9866ef9e6a3bd1803f0cd5dffd294c047d74b9, no local run
Authored: 2026-09-22; agent/tool: opencode with model opencode/muse-spark-1.3-contributor-free
Basis: source inspection
Claim: Savestates are not raw RAM dumps. A `SAVE_STATE_HEADER` frames title, serial, media path, screenshot, and state data. State bytes are compressed with None, Deflate, Zstandard, or XZ. Default compression is `ZstDefault`. Files use `.sav` names such as `{serial}_{slot}.sav` under the save states folder. `Bus::DoState` writes the active RAM size and raw RAM bytes into the state stream, so RAM is present after decompression and marker parsing.
Evidence:
- `src/core/save_state_version.h`: `SAVE_STATE_MAGIC = 0x43435544`, `SAVE_STATE_VERSION = 87`, `CompressionType` None, Deflate, Zstandard, XZ, header offsets for screenshot and state data.
- `src/core/settings.h`: `save_state_compression = DEFAULT_SAVE_STATE_COMPRESSION_MODE`, default `SaveStateCompressionMode::ZstDefault`.
- `src/core/settings.cpp`: compression name list includes Uncompressed, Deflate variants, Zstandard variants, and XZ variants.
- `src/core/system.cpp`: `SaveStateToBuffer`, `CompressAndWriteStateData`, `ReadAndDecompressStateData`, `DoState` with per-component markers including `Bus`, save names in `GetSaveStateFileName` area around `{serial}_{slot}.sav`.
- `src/core/bus.cpp`: `Bus::DoState` calls `sw.DoBytes(g_bus.ram, g_bus.ram_size)` after handling 2 MB versus 8 MB size.
- `src/util/state_wrapper.h` and `src/util/compress_helpers.h`: state reader/writer and Deflate, Zstandard, XZ helpers.
- URLs: https://github.com/stenzek/duckstation/blob/2c9866ef9e6a3bd1803f0cd5dffd294c047d74b9/src/core/save_state_version.h, https://github.com/stenzek/duckstation/blob/2c9866ef9e6a3bd1803f0cd5dffd294c047d74b9/src/core/system.cpp, https://github.com/stenzek/duckstation/blob/2c9866ef9e6a3bd1803f0cd5dffd294c047d74b9/src/core/bus.cpp, https://github.com/stenzek/duckstation/blob/2c9866ef9e6a3bd1803f0cd5dffd294c047d74b9/src/util/compress_helpers.h
Limits: no savestate captured or decompressed here. Did not verify the exact byte offset of RAM inside a real file, behavior across version 87 versus older states, or how rewind and runahead memory states differ from slot saves.
History:
- 2026-09-22; opencode with model opencode/muse-spark-1.3-contributor-free; authored; source inspection only, no runtime test.

## RE1-EMU-005: integrated debugger and memory views are in-process only

Status: Candidate
Scope: DuckStation Qt build, manual reverse engineering use
Environment: source inspection on 2026-09-22, commit 2c9866ef9e6a3bd1803f0cd5dffd294c047d74b9, no local run
Authored: 2026-09-22; agent/tool: opencode with model opencode/muse-spark-1.3-contributor-free
Basis: source inspection
Claim: The Qt debugger has RAM, scratchpad, EXP1, BIOS, VRAM, and SPU RAM views plus search, dump-to-view navigation, and live refresh. It is useful for finding room and item addresses by hand. It does not expose an external polling API by itself.
Evidence:
- `src/duckstation-qt/debuggerwindow.cpp` and `debuggerwindow.h`: memory region selection starting at `Bus::MemoryRegion::RAM`, `memoryView->forceRefresh`, dump address flow, `Bus::SearchMemory` for pattern search.
- `src/duckstation-qt/debuggerwindow.ui`: `Memory` dock with `memoryView`, region radio buttons for RAM, scratchpad, EXP1, BIOS, VRAM, SPURAM, plus `memorySearchString` and `memorySearch`.
- `src/duckstation-qt/memoryviewwidget.h`: `MemoryViewWidget` viewer and editor widget.
- `src/duckstation-qt/debuggermodels.*`: code, register, stack, and thread models behind the debugger window.
- README feature list advertises live memory scanning and editing plus integrated and remote debugging.
- URLs: https://github.com/stenzek/duckstation/blob/2c9866ef9e6a3bd1803f0cd5dffd294c047d74b9/src/duckstation-qt/debuggerwindow.cpp, https://github.com/stenzek/duckstation/blob/2c9866ef9e6a3bd1803f0cd5dffd294c047d74b9/src/duckstation-qt/memoryviewwidget.h
Limits: did not run the debugger UI on macOS. Did not verify dump-to-file, scripting hooks, or whether debugger refresh pauses the game loop.
History:
- 2026-09-22; opencode with model opencode/muse-spark-1.3-contributor-free; authored; source inspection only, no runtime test.

## RE1-EMU-006: no HTTP, pipe, or scripting API found

Status: Candidate
Scope: DuckStation master as inspected on 2026-09-22
Environment: source inspection on 2026-09-22, commit 2c9866ef9e6a3bd1803f0cd5dffd294c047d74b9, no local run
Authored: 2026-09-22; agent/tool: opencode with model opencode/muse-spark-1.3-contributor-free
Basis: source inspection, incomplete search
Claim: No HTTP server, named pipe API, Lua scripting API, or Python scripting API was found in the files inspected. The only external socket path found was the GDB TCP server. Internal memory users found were cheats through `CPU::SafeWriteMemory*`, RetroAchievements `ClientReadMemory` reading emulator RAM directly, and the Qt debugger reading `Bus` regions.
Evidence:
- `src/core/cheats.cpp`: cheat application through `CPU::SafeWriteMemoryByte`, HalfWord, and Word.
- `src/core/achievements.cpp`: `ClientReadMemory` callback wired into `rc_client_create`, plus `MEMORY_RAM_SIZE = Bus::RAM_2MB_SIZE` mapping logic nearby.
- CMake and Qt file-list checks inspected did not show Lua, Python, HTTP server, pipe, or WebSocket files.
- URLs: https://github.com/stenzek/duckstation/blob/2c9866ef9e6a3bd1803f0cd5dffd294c047d74b9/src/core/cheats.cpp, https://github.com/stenzek/duckstation/blob/2c9866ef9e6a3bd1803f0cd5dffd294c047d74b9/src/core/achievements.cpp
Limits: this negative result is weak. GitHub code search needed authentication during this check, so no exhaustive full tree search was completed. A small helper, fork-only patch, or new script API could exist outside the inspected files.
History:
- 2026-09-22; opencode with model opencode/muse-spark-1.3-contributor-free; authored; partial search only.

## What was not verified

- No DuckStation run on macOS here, so no measured GDB latency, polling rate, or pause behavior.
- No RE1 game revision, serial, region, executable identity, or DuckStation version for the actual target yet.
- No RAM address for current room or item flags. Those need the controlled savestate and GDB experiments in AGENTS.md.
- No test that `ExportSharedMemory` helps an external macOS process. Source points the other way because the macOS name is empty.
- No macOS process memory prototype, so no data on SIP, entitlements, ASLR, or pointer stability.
- No savestate captured, decompressed, or diffed.
- No EmuHook run and no macOS port of it.
- No exhaustive proof that scripting or HTTP support is absent.

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

## RE1-RDT-001: static room and item data is parseable, pickup flag mapping is not

Status: Candidate
Scope: RE1 PS1 retail file formats, no specific revision pinned
Environment: source inspection on 2026-09-22, no local run
Authored: 2026-09-22; agent/tool: opencode; model: opencode/muse-spark-1.3-contributor-free
Basis: source inspection of reevengi, biohazard-utils, OpenResident, plus EmuHook and R3-Auto-Map-Gen as pattern leads
Claim: room identity is stage plus room plus camera, files are psx/stageN/roomNxx0.rdt, header carries nItem with a 19 entry offset table, placements come from SCD Item_set 0x0D with id and type fields. Which bit means acquired and how GlobalId maps to save flags is unknown.
Evidence:
- https://github.com/pmandin/reevengi src/g_re1/rdt.h, rdt.c, game_re1_ps1.c, scd1.xml
- https://github.com/biorand/biohazard-utils src/IntelOrca.Biohazard/Room/Rdt1.cs, Script/Opcodes/ItemAotSetOpcode.cs
- https://github.com/XProger/OpenResident src/room.h, src/script.h
- https://github.com/elModo7/EmuHook README demo entries for RE1 real-time map with no published addresses, verified closed core
- https://github.com/themitosan/R3-Auto-Map-Gen node graph approach for PC Classic REbirth, no PS1 addresses
Limits: zero published PS1 RAM addresses with revision info found. No runtime confirmation. Tapatalk RDT thread unread, RetroAchievements pages blocked, EmuHook other_demos scripts not inspected.
History:
- 2026-09-22; opencode with model unknown; reviewed; source inspection of file formats, no runtime test.
- 2026-09-22; opencode with model opencode/muse-spark-1.3-contributor-free; authored; summarized review into this entry, still Candidate.

## RE1-DISC-001: local Director's Cut disc identity

Status: Candidate
Scope: Resident Evil Director's Cut USA, SLUS-00551, local .bin/.cue only
Environment: macOS local inspection 2026-09-25, DuckStation 0.1-11752-g5fd366809, no boot yet
Authored: 2026-09-25; agent/tool: opencode; model: opencode/muse-spark-1.3-contributor-free
Basis: runtime observation of local files
Claim: local image is MODE2/2352 single track, 707027664 bytes, sha1 d926cec7ac6a1665cc00039ab92dee6a6bebe824, serial SLUS_00551 found in binary, matching existing savestates SLUS-00551_1.sav 1631421 bytes and SLUS-00551_resume.sav 1629173 bytes with DUCC magic. This is the revision to pin for milestone 1, not SLUS-00170.
Evidence: .cue shows TRACK 01 MODE2/2352, bin strings contain SLUS_00551 and SLUS_005.51, savestate headers start with DUCCS.
Limits: no disc revision string, no SYSTEM.CNF BOOT line extracted yet, no executable hash yet, no live boot yet.
History:
- 2026-09-25; opencode with model opencode/muse-spark-1.3-contributor-free; authored; file inspection only.

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

## RE1-STATIC-001: RDT enumeration without booting is feasible

Status: Candidate
Scope: SLUS-00551 file formats, no boot
Environment: source inspection 2026-09-25, no extraction run yet
Authored: 2026-09-25; agent/tool: opencode; model: opencode/muse-spark-1.3-contributor-free
Basis: source inspection of biorand, reevengi, OpenResident
Claim: rooms and per-room pickup candidates can be listed from extracted RDTs using biorand Rdt1.cs plus ItemAotSet opcode 0x18 length 26 with Id, Type, Amount, GlobalId. Opcode 0x0D is generic AOT length 18 and must not be counted as collectible. Pickup-flag to save-flag mapping is not in any inspected source and needs runtime. Use RdtId colon ItemId keys from RtdItemId.cs.
Evidence:
- https://github.com/biorand/biohazard-utils src/IntelOrca.Biohazard/Room/Rdt1.cs, Script/Opcodes/ItemAotSetOpcode.cs, Script/OpcodeV1.cs, RdtId.cs
- https://github.com/pmandin/reevengi src/g_re1/game_re1_ps1.c, rdt.h, scd1.xml, reevengi -dumpscript path
- https://github.com/XProger/OpenResident src/room.h skip 21 TODO for item AOT
Limits: no extraction run, dumpsxiso and bchunk missing locally, isoinfo and 7z present. No save layout docs found. GlobalId is a runtime table index, not a save bit.
History:
- 2026-09-25; opencode with model unknown; reviewed; file format assessment, no runtime test.
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

## RE1-USERMAP-001: RetroAchievements code notes as the candidate feed

Status: Candidate
Scope: RE1 USA SLUS-00170 plus EU, FR, GER variants per the table, checked against local SLUS-00551 where noted
Environment: received 2026-09-25, source confirmed 2026-09-25, runtime cross-checks ongoing
Authored: RetroAchievements achievement developers as code notes; provided by human user on 2026-09-25; filed by opencode with model opencode/muse-spark-1.3-contributor-free
Basis: third-party documentation with runtime cross-checks
Claim: RAM offsets around 0x0c8660 Main Location, 0x0c8661 SubLocation, 0x0c8662 Camera, and 0x0c8663 Previous Location form the room identity. Offsets 0x0c86dc onward are Item Collected bitfields. Offsets 0x0c8710 onward are Map Visited bits. Full table is filed at docs/re1_ram_map_user_provided.md. Add 0x80000000 for GDB virtual addresses. Policy: RA notes are the primary candidate feed, not automatic truth. Achievement logic watches conditions sufficient for achievements, which can read transient state such as inventory rather than persistent collected flags, and coverage follows achievements rather than rooms. Promotion still needs runtime observation on the exact revision. Mutual corroboration so far: RA room bytes match live SLUS-00551 reads in RE1-RUNTIME-001 and RE1-ROOM-001, and the two Confirmed pickup bits in RE1-PICKUP-002 and RE1-PICKUP-003 sit exactly on RA labeled bits with matching polarity.
Evidence: local file docs/re1_ram_map_user_provided.md transcribed from user paste, user confirmation of RA origin, GDB and fixture runs cited in RE1-RUNTIME-001, RE1-ROOM-001, RE1-PICKUP-002, RE1-PICKUP-003.
Limits: RA pages return 403 to this project's fetcher, so new notes arrive through user pastes. Unchecked addresses stay Candidate no matter how plausible the label.
History:
- 2026-09-25; human user; provided; raw table paste, later confirmed as RetroAchievements code notes.
- 2026-09-25; opencode with model opencode/muse-spark-1.3-contributor-free; filed; saved verbatim to docs/re1_ram_map_user_provided.md, still Candidate.
Claim: RAM offsets around 0x0c8660 Main Location, 0x0c8661 SubLocation, 0x0c8662 Camera, and 0x0c8663 Previous Location form the room identity. Offsets 0x0c86dc onward are Item Collected bitfields. Offsets 0x0c8710 onward are Map Visited bits. Full table is filed at docs/re1_ram_map_user_provided.md. Add 0x80000000 for GDB virtual addresses.
Evidence: local file docs/re1_ram_map_user_provided.md transcribed from user paste. Health offset 0x0c51ac matches the independent cheat anchor 0x800C51AC from RE1-CHEAT-001, which raises confidence but does not confirm.
Limits: original source unknown, no revision string, no DuckStation version, no widths for every row, no proof these apply to SLUS-00551 Director's Cut. Requires live GDB reads on both revisions before any promotion.
History:
- 2026-09-25; human user; provided; raw table paste, source unknown.
- 2026-09-25; opencode with model opencode/muse-spark-1.3-contributor-free; filed; saved verbatim to docs/re1_ram_map_user_provided.md, still Candidate.

## RE1-RUNTIME-001: room bytes live on SLUS-00551, CLI extraction works

Status: Candidate
Scope: SLUS-00551 Director's Cut USA, DuckStation 0.1-11894 dev, GDB plus offline .sav parse
Environment: macOS arm64, 2026-09-25, three local states, no manual play
Authored: 2026-09-25; agent/tool: opencode; model: opencode/muse-spark-1.3-contributor-free
Basis: runtime observation, both live reads and save files
Claim: Main 0x800C8660, Sub 0x800C8661, Camera 0x800C8662, Prev 0x800C8663 from the user map return live values on SLUS-00551. Slot and resume states read Main 00 Sub 07 Cam 02 Prev 06, Health 0x96, Player 01 Jill, GameState 00 Ingame, region bytes US-0. The .bak state reads the same room with camera 06, so camera varies while Main plus Sub stays put. Offline extraction with tools/extract_sav_ram.py returns byte-identical room values to GDB. Switch to CLI only going forward: the app bundle ships just the cocoa Qt plugin, so no offscreen platform exists and any boot shows a window.
Evidence: GDB m reads on all three states, extractor ram base 6754 in decompressed 3835761 for all three files, slot versus resume 9855 bytes changed with room bytes stable, slot versus bak camera 02 versus 06 with Main and Sub stable.
Limits: one room observed, Art Room per the table. No room A versus B walk yet, no pickup flip observed, Ink flag reads 0xFF in all three states. Fresh disc boot read Main 00 Sub 00 Cam 00, consistent with title state but not a second gameplay room.
History:
- 2026-09-25; opencode with model opencode/muse-spark-1.3-contributor-free; authored; live GDB reads plus offline extraction, still Candidate.

## RE1-PICKUP-001: Art Room map bit differs between backup and slot saves

Status: Candidate
Scope: SLUS-00551 Training Jill, Art Room Main 00 Sub 07, three local states
Environment: offline RAM extracts 2026-09-25, no new gameplay
Authored: 2026-09-25; agent/tool: opencode; model: opencode/muse-spark-1.3-contributor-free
Basis: runtime observation of existing save files
Claim: offset 0xC86ED reads 0xFF in the .bak state and 0xBF in slot and resume, so bit 6 cleared between backup and slot. The user map labels 0x0c86ed Bit6 as Map on Art Room, the room the player stands in. Offset 0xC871C reads 0x00 in bak and 0x08 in slot and resume, and the map labels Bit3 as Mansion 1F map owned. Coherent story is taking the map item clears one bit and sets the other, but bit polarity is unproven and 205120 bytes differ between bak and slot, so this is a lead, not proof.
Evidence: /tmp/ram_slot.bin, /tmp/ram_resume.bin, /tmp/ram_bak.bin from tools/extract_sav_ram.py, 14 Item Collected bytes and 8 Map Visited bytes compared, only these two differ.
Limits: no controlled before and after pickup, no leave and re-enter test, no save and load round trip on this bit, polarity unknown.
History:
- 2026-09-25; opencode with model opencode/muse-spark-1.3-contributor-free; authored; save diff only, still Candidate.

## RE1-STATIC-002: 335 RDT files listed from SLUS-00551 without extraction

Status: Candidate
Scope: SLUS-00551 disc layout metadata only
Environment: local listing 2026-09-25 with tools/list_psx_files.py, no file contents read
Authored: 2026-09-25; agent/tool: opencode; model: opencode/muse-spark-1.3-contributor-free
Basis: runtime observation of local disc directory layout
Claim: the image holds 335 .RDT files under PSX/STAGE paths with LBA and size per file, for example PSX/STAGE1/ROOM1000.RDT lba 161395 size 339752. Room enumeration needs no gameplay. Next step is reading RDT headers for nItem counts as integers, still without committing any game bytes.
Evidence: full listing reproducible with python3 tools/list_psx_files.py cue path --filter RDT.
Limits: no header parsed yet, no item table built, naming of room versus camera digits unconfirmed.
History:
- 2026-09-25; opencode with model opencode/muse-spark-1.3-contributor-free; authored; listing only, still Candidate.

## RE1-ROW-001: first room to item row for Art Room with offline end to end run

Status: Candidate
Scope: SLUS-00551 Art Room Main 00 Sub 07, file PSX/STAGE1/ROOM1070.RDT
Environment: local parse and offline run 2026-09-25, no gameplay
Authored: 2026-09-25; agent/tool: opencode; model: opencode/muse-spark-1.3-contributor-free
Basis: runtime observation of disc bytes and save files
Claim: the init script chunk holds a 0x18 pickup with id 131, type 0x2F Ink Ribbon, amount 3, gid 39 at real coordinates, a candidate match for the Art Room Ink Ribbon behind flag 0xC86E3 bit 0. A second 0x18 entry with id 2, type 0x4E, zero coordinates is excluded as model preload, not a world pickup. The map pickup behind 0xC86ED bit 6 has no 0x18 entry and stays unresolved. Polarity 1 means present and 0 means taken fits the ink in inventory, 0x2F times 6, with flag 0xFE, and the map transition between bak and slot, but is still unproven. tools/track_offline.py reads extracted RAM through the Tracker and prints UNKNOWN for the untested Art Room item link and room completion.
Evidence: tools/scan_scd.py walk of init chunk is clean at 40 ops, main chunk clean at 45 ops, event chunk unparsed. data/room_items_slus00551.json holds the row. Earlier offline runs with a candidate flag link printed Ink Ribbon taken; after removing that untested link, /tmp/ram_slot.bin prints Current room 00-07, Collected 0, State UNKNOWN.
Limits: GlobalId 39 to flag 0xC86E3 bit 0 is association by label and coordinates, not by code path. Event chunk parsing is open. One room only.
History:
- 2026-09-25; opencode with model opencode/muse-spark-1.3-contributor-free; authored; disc parse plus save evidence, still Candidate.
- 2026-09-26; Codex with model unknown; superseded the byte-16 GlobalId 24 with 39 from RE1-RDT-002 and removed the untested Art Room flag link from the offline tracker; original runtime evidence and Candidate status remain.

## RE1-TABLE-001: full disc item table, 327 of 335 rooms walk clean

Status: Candidate
Scope: SLUS-00551 all stages, init and main chunks, metadata only
Environment: local build 2026-09-25 with tools/build_item_table.py, no gameplay
Authored: 2026-09-25; agent/tool: opencode; model: opencode/muse-spark-1.3-contributor-free
Basis: runtime observation of disc bytes
Claim: 335 RDTs yield 647 0x18 entries, 535 with nonzero coordinates. Type bytes match the chest item ID table, for example 0x44 Green Herb 107 times, 0x0B Clip 51 times, 0x2F Ink Ribbon 41 times, 0x0C Shells 30 times, which confirms the Type field split. Zero-coordinate entries read as model preloads, not pickups. Eight rooms in stages 3 and 4 stop at undocumented bytes above 0x50 such as 0xD0 and 0xE0, plus ROOM2000.RDT which is a dummy file with zero offsets. Variable opcodes 0x33 and 0x17 are handled per scd1.xml. Event chunks stay unparsed. Full table is committed at data/item_table_slus00551.json, paths plus integers only.
Evidence: data/item_table_slus00551.json 305076 bytes, per-room walk stats inside it, ROOM1000.RDT now clean at 115 ops with 3 entries after the 0x33 fix.
Limits: GlobalId to save flag mapping remains untested for most entries. ROOM1000.RDT holds Sword Key plus two 1x1 Serum shaped entries and no ink, so the save room file identity is unconfirmed and the profile demo pickup stays a 00170 side claim.
History:
- 2026-09-25; opencode with model opencode/muse-spark-1.3-contributor-free; authored; disc parse only, still Candidate.
- 2026-09-26; Codex with model unknown; regenerated the item table after RE1-RDT-002 and revised the mapping limit; 647 item entries remain.

## RE1-DOORS-001: 782 door edges plus filename rule for runtime linkage

Status: Candidate
Scope: SLUS-00551 all stages, init and main chunks
Environment: local parse 2026-09-25 with extended tools/build_item_table.py, no gameplay
Authored: 2026-09-25; agent/tool: opencode; model: opencode/muse-spark-1.3-contributor-free
Basis: runtime observation of disc bytes
Claim: Door_set 0x0C byte 15 splits into next stage bits 7-5 and next room bits 4-0 per scd1.xml, giving 782 directed edges across the disc. Filename rule ROOM plus stage plus two digit room plus camera links files to runtime Main and Sub: ROOM1070.RDT holds the Art Room ink matching runtime Sub 07 and its doors point at rooms 6 and 8, flanking 7. ROOM1000.RDT doors point at room 1, fitting Sub 00 Mansion Save Room next to Sub 01 West Stairway. STAGE1 doors target stages 0, 2, and 3, so the file folder number is not the runtime stage value and stays unresolved.
Evidence: data/item_table_slus00551.json now 399936 bytes with doors arrays, per-room stats unchanged at 327 clean.
Limits: filename rule rests on two rooms. No runtime walk through a door yet. Folder to Main mapping open. Event chunks still unparsed.
History:
- 2026-09-25; opencode with model opencode/muse-spark-1.3-contributor-free; authored; disc parse only, still Candidate.

## RE1-LINK-001: filename rule holds for 87 of 90 stage 0 doors

Status: Candidate
Scope: SLUS-00551 STAGE1 doors targeting stage 0
Environment: static check 2026-09-25 over data/item_table_slus00551.json
Authored: 2026-09-25; agent/tool: opencode; model: opencode/muse-spark-1.3-contributor-free
Basis: runtime observation of disc bytes
Claim: for STAGE1 doors with next stage 0, target file PSX/STAGE1/ROOM1 plus two digit hex room plus 0 exists in 87 of 90 cases. The 3 misses point at rooms 0x10 and 0x19, whose files are absent, likely special transitions such as stairs or elevators. Duplicate 0x18 rows identical in id, type, amount, gid, and box are character or mode variants of one pickup. tools/track_offline.py now resolves any Main 0 room through this rule, dedups variants, checks only observed flags, and reports UNKNOWN while coverage is open. Other Main values refuse instead of guessing.
Evidence: door invariant script output 87 resolving and 3 missing. Historical offline runs with a candidate Art Room flag link printed Items 1 Collected 1 State UNKNOWN; with that untested link removed, the same slot RAM prints Items 1 Collected 0 State UNKNOWN.
Limits: static consistency plus 2 runtime rooms is not confirmation. The Art Room ink flag association remains untested; controlled item flags now cover the Winding Passage herb and Mansion Storeroom Chemical. Input injection was blocked in the original test environment because Pad1 bound only to an SDL gamepad.
History:
- 2026-09-25; opencode with model opencode/muse-spark-1.3-contributor-free; authored; static check plus offline runs, still Candidate.
- 2026-09-26; Codex with model unknown; updated the current offline output and flag-coverage limit after removing the untested Art Room link.

## RE1-ROOM-001: room change Art Room to Main Hall observed live

Status: Candidate
Scope: SLUS-00551 Training Jill, DuckStation 0.1-11894 dev, GDB reads
Environment: live play by human user on 2026-09-25, agent read over GDB
Authored: 2026-09-25; human user walked, opencode with model opencode/muse-spark-1.3-contributor-free recorded
Basis: runtime observation, two rooms
Claim: Main 0x800C8660 plus Sub 0x800C8661 identify the room on SLUS-00551. Art Room reads 00 07 with prev 06. After the user walked through the door, Main Hall reads 00 06 with prev 07. Prev and Sub cross-link both ways. Item flags are stable across the transition: ink 0xC86E3 stays 0xFE, map bit 0xC86ED stays 0xBF, maps 0xC871C stays 0x08, health stays 0x96. Filename rule resolves 00-06 to ROOM1060.RDT, which holds 3 placed 0x18 pickups including ink x3 gid 52. Full RAM dumped to /tmp/ram_mainhall.bin, 2097152 bytes, kept out of git.
Evidence: GDB m reads before and after, /tmp/ram_mainhall.bin, track_offline run printing Current room 00-06 with 3 unknown items and State UNKNOWN.
Limits: two rooms only for this finding. Leave and re-enter was later shown in RE1-MILESTONE-001. The Art Room ink association remains Candidate; controlled pickup flags are in RE1-PICKUP-002 and RE1-PICKUP-003.
History:
- 2026-09-25; human user; walked; Art Room to Main Hall through gameplay.
- 2026-09-25; opencode with model opencode/muse-spark-1.3-contributor-free; recorded; GDB reads plus dump, still Candidate.
- 2026-09-26; Codex with model unknown; superseded the byte-16 Main Hall ink GlobalId 32 with 52 from RE1-RDT-002; room-transition evidence is unchanged.

## RE1-MILESTONE-001: first milestone complete on SLUS-00551 Art Room

Status: Candidate
Scope: SLUS-00551 Training Jill, Art Room and Main Hall 1F
Environment: live GDB plus offline extracts on 2026-09-25
Authored: 2026-09-25; human user walked both directions, opencode with model opencode/muse-spark-1.3-contributor-free recorded
Basis: runtime observation, three room reads across two transitions
Claim: all six milestone checks hold as Candidate. Current room reads Main plus Sub over GDB, Art Room 00 07 and Main Hall 00 06 with prev cross-linking both ways. Pickup flags read live: ink 0xC86E3 bit 0 and map 0xC86ED bit 6, polarity 1 present 0 taken fits every observation. The ROOM1070.RDT 0x18 row with id 131, type 0x2F, amount 3, and gid 39 at real coordinates is a candidate association for the Art Room ink; its collected state remains Unknown without a controlled pickup. tools/track.py and tools/track_offline.py print current room, visited, items, collected, state, and list completeness. Leave and re-enter verified: Art Room to Main Hall and back reads 00 07 again with camera 00, ink still 0xFE, map still 0xBF, health still 0x96.
Evidence: RE1-ROOM-001 reads, /tmp/ram_mainhall.bin, return-trip reads above, offline runs on three saves.
Limits: two rooms, one associated pickup, polarity unproven by a controlled take, no save and load round trip on these bytes yet, event chunks unparsed, 8 rooms walk truncated.
History:
- 2026-09-25; human user; walked; round trip Art Room to Main Hall and back.
- 2026-09-25; opencode with model opencode/muse-spark-1.3-contributor-free; recorded; milestone checks observed, still Candidate.
- 2026-09-26; Codex with model unknown; superseded the byte-16 Art Room ink GlobalId 24 with 39 from RE1-RDT-002; milestone runtime observations are unchanged.

## RE1-PICKUP-002: controlled green herb take confirms polarity and flag

Status: Confirmed for this revision
Scope: SLUS-00551 Training Jill, Winding Passage Main 00 Sub 09, DuckStation 0.1-11894 dev
Environment: before and after savestates on 2026-09-25, offline extracts, no emulator boot
Authored: 2026-09-25; human user played the single pickup, opencode with model opencode/muse-spark-1.3-contributor-free analyzed
Basis: runtime observation, controlled before and after with one item taken
Claim: taking the Winding Passage Green Herb clears exactly one bit: 0xC86EA bit 0 goes 1 to 0, 0xFF to 0xFE, while the other 13 known Item Collected bytes stay identical. Room bytes are unchanged, Main 00 Sub 09 cam 01, and inventory slot 5 gains 0x44 times 1. ROOM1090.RDT holds exactly one placed pickup, 0x18 id 5 type 0x44 amount 1 gid 111 at real coordinates. Bit polarity 1 means present and 0 means taken is confirmed for this revision. Fixtures are committed at tests/fixtures/slus00551_green_herb_before.sav sha1 9adcac31dac8725219f5672bce9152fa487b5ee9 and slus00551_green_herb_after.sav sha1 1eaf8be8360025d25589255ef244584df84cef53, donated by the user as evidence.
Evidence: tools/extract_sav_ram.py both fixtures, targeted compare of 14 Item Collected bytes with a single-bit diff, track_offline prints INCOMPLETE before and UNKNOWN after.
Limits: save and normal load round trip on this bit untested, re-enter from another room untested for this flag, other flags still Candidate.
History:
- 2026-09-25; human user; played; stood before the herb, saved, took it, saved.
- 2026-09-25; opencode with model opencode/muse-spark-1.3-contributor-free; analyzed; single-bit diff plus inventory plus RDT row, promoting to Confirmed for this revision.
- 2026-09-26; Codex with model unknown; superseded the byte-16 RDT GlobalId 0 with 111 from RE1-RDT-002; the controlled pickup flag result is unchanged.

## RE1-PICKUP-003: controlled chemical take confirms second flag

Status: Confirmed for this revision
Scope: SLUS-00551 Training Jill, room Main 00 Sub 18, DuckStation 0.1-11894 dev
Environment: before and after savestates on 2026-09-25, offline extracts
Authored: 2026-09-25; human user played the single pickup, opencode with model opencode/muse-spark-1.3-contributor-free analyzed
Basis: runtime observation, controlled before and after with one item taken
Claim: taking the Chemical clears exactly one bit: 0xC86DE bit 2 goes 1 to 0, 0xFF to 0xFB, while the other 13 known Item Collected bytes stay identical. Room bytes are unchanged, Main 00 Sub 18 cam 01, and inventory slot 6 gains 0x26 times 1. ROOM1180.RDT holds the pickup at 0x18 id 1 type 0x26 amount 1 gid 13 at real coordinates. The same id and spot also carry type 0x1C Broken Shotgun with gid 48, which reads as the Chris variant of one pickup spot, so the tracker groups rows by id and box. Third room linked through the filename rule. Fixtures are committed at tests/fixtures/slus00551_chemical_before.sav sha1 58eeb4f0f628a81d6d6bea2ab3def480ece4d0cf and slus00551_chemical_after.sav sha1 e5799cd941ed0ca4c7025f0c2df6e3edddf9b15d, donated by the user as evidence.
Evidence: targeted compare of 14 Item Collected bytes with a single-bit diff, track_offline prints INCOMPLETE before and taken with UNKNOWN after.
Limits: one normal in-game save and load after the pickup is covered by RE1-SAVE-001. Loading an earlier normal save to restore the untaken bit is untested. Character variant mapping is inferred from one spot only. The earlier gid 0 reading was an opcode field-offset error, corrected in RE1-RDT-002.
History:
- 2026-09-25; human user; played; stood in the safe room, saved, took the chemical, saved.
- 2026-09-25; opencode with model opencode/muse-spark-1.3-contributor-free; analyzed; single-bit diff plus inventory plus RDT row, promoting to Confirmed for this revision.
- 2026-09-26; Codex with model unknown; revised limits after the normal save/load observation in RE1-SAVE-001 and identified the RDT field-offset error by source and local byte inspection. The original pickup evidence and authorship remain unchanged.
- 2026-09-26; Codex with model unknown; superseded the byte-16 Chemical GlobalId 0 with 13 and revised the Broken Shotgun row to 48 from RE1-RDT-002; controlled pickup and normal-load observations are unchanged.

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

## RE1-JOIN-001: RA flags joined to RDT rooms, 15 of 24 placed

Status: Candidate
Scope: SLUS-00551 Mansion 1F RA item flags and RDT table
Environment: static join 2026-09-25 with tools/join_ra_rdt.py, no gameplay
Authored: 2026-09-25; agent/tool: opencode; model: opencode/muse-spark-1.3-contributor-free
Basis: source inspection of RA notes against disc bytes
Claim: 15 of 24 RA Item Collected flags resolve to a room through label prefix matching, each listed side by side with that room file's placed 0x18 entries and no forced association. Spot coherence is strong: L Passage Clips sits with clips in ROOM1080, Vacant Room Clips and Shells sit with clips in ROOM1020, Tea Room Clips sits with two clips rows in ROOM1040, Keeper Room Shells sits with shells in ROOM10E0, East Stairway herb sits with a herb in ROOM10B0, Wardrobe herbs and ink sit with two herbs and ink in ROOM1120, Dressing Room Clips sits with clips in ROOM1110. The 9 unmatched flags are roomless labels such as Star Crest, event items such as Acid Rounds from Barry, or the Keeper Bedroom Clips alias that likely means Keeper's Room. Table committed at data/room_flags_candidate.json. Uppercase hex in room digits broke the first join pass and is fixed.
Evidence: tools/join_ra_rdt.py output 15 matched and 9 unmatched, data/room_flags_candidate.json, per-room placed rows quoted above.
Limits: side by side is not association. The Winding Passage herb and Mansion Storeroom Chemical have controlled pickup observations; the Art Room ink link remains Candidate. Keeper Bedroom alias unproven.
History:
- 2026-09-25; opencode with model opencode/muse-spark-1.3-contributor-free; authored; static join only, still Candidate.
- 2026-09-26; Codex with model unknown; regenerated the side-by-side RDT identifiers after RE1-RDT-002; 15 room matches and 9 unmatched labels remain, with associations still unproven.

## RE1-VISIT-001: game visited bits decode into room lists

Status: Candidate
Scope: SLUS-00551 Map Visited bytes 0xC8710 through 0xC8717 per RA notes
Environment: offline decode 2026-09-25 with tools/map_visited.py, no gameplay
Authored: 2026-09-25; agent/tool: opencode; model: opencode/muse-spark-1.3-contributor-free
Basis: runtime observation of save files against RA labels
Claim: each visited byte decodes one room per bit. The slot save reads 6 visited rooms: Art Room Secret Room, Bar, Art Room, Main Hall, Dining Room, Tea Room. That matches real progress including Main Hall before the live walk, so set means visited. The tracker will read these as game-derived visited state, reread on every load, kept separate from its own observation history per the persistence rules. A line-join bug that bled Files rows into the 0x8717 group is fixed by stopping continuation at any new dash entry.
Evidence: tools/map_visited.py output on /tmp/ram_slot.bin, 6 VISITED lines.
Limits: set means visited is inferred from consistency, not from watching a bit flip on entry. Unvisited rooms in this save are untested.
History:
- 2026-09-25; opencode with model opencode/muse-spark-1.3-contributor-free; authored; save decode only, still Candidate.

## RE1-PLAYER-001: player position and facing next to health

Status: Candidate
Scope: SLUS-00551 Training Jill, live GDB plus input
Environment: windowed DuckStation 0.1-11894 dev on 2026-09-25, agent driven with keyboard and screenshots
Authored: 2026-09-25; agent/tool: opencode; model: opencode/muse-spark-1.3-contributor-free
Basis: runtime observation, walk versus turn separation
Claim: the player struct sits by health at 0xC51AC. X is 0xC5158, Z is 0xC5160, facing is 0xC5148, with mirror copies at 0xC5190, 0xC5194, and nearby. Walk-only movers versus turn-only movers separate cleanly across three paused dumps. Facing decreases on left turn. The GameHacking position codes at 0xA4BE4 do not move and are rejected for this revision. A door in room 09 at box 23400,800,2000,1700 does not open by pushing or by action, likely locked or keyed. Vision loop of move plus screencapture plus read works and ends blind driving.
Evidence: tools/split_walk_turn.py walk-only and turn-only lists, live reads during steering, screenshots jill.png through jill12.png in /tmp, kept out of git.
Limits: axis signs and facing units uncalibrated, door lock state unknown, no combat tested per the zombie warning so a pre-door savestate stays the rule.
History:
- 2026-09-25; opencode with model opencode/muse-spark-1.3-contributor-free; authored; live driving only, still Candidate.

## RE1-MAP-001: Mansion 1F topology from doors, mutually consistent

Status: Candidate
Scope: SLUS-00551 STAGE1 files with stage 0 door targets
Environment: static build 2026-09-25 with tools/door_map.py, no gameplay
Authored: 2026-09-25; agent/tool: opencode; model: opencode/muse-spark-1.3-contributor-free
Basis: source inspection of disc bytes against RA labels
Claim: 27 nodes and 54 edges form the Mansion 1F graph, committed as ASCII through tools/door_map.py and as data/mansion1f.dot. Edges run both directions everywhere checked, for example save room to stairway to vacant room and back, dining room to main hall to art room to L-passage to winding passage. Three independent sources agree: door bytes give the edges, filenames give the numbers, RA notes give the names. Room 0x10 Elevator Stairway is a target with no file, matching the earlier join misses, so it stays numeric rather than guessed.
Evidence: tools/door_map.py output, data/mansion1f.dot, bidirectional spot checks above.
Limits: topology only, no geometry or draw order. Camera variant files fold into base rooms by number. Other stages unmapped pending folder to Main linkage.
History:
- 2026-09-25; opencode with model opencode/muse-spark-1.3-contributor-free; authored; static build only, still Candidate.

## RE1-RDT-002: RE1 item opcode stores GlobalId at byte 22

Status: Candidate
Scope: Resident Evil Director's Cut USA, serial SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`; opcode `0x18` in the named RDT files; Training Jill herb and Chemical pickup scenarios tested, Chris variant static only
Environment: local disc read and controlled savestate evidence, 2026-09-26; DuckStation 0.1-11894-gc66b2694d for the pickup experiments in RE1-PICKUP-002 and RE1-PICKUP-003
Authored: 2026-09-26; Codex with model unknown
Basis: source inspection of an independently implemented RE1 RDT parser, direct disc-byte inspection, and comparison with two controlled pickup flags
Claim: opcode `0x18` is 26 bytes long and its one-byte GlobalId field is at byte 22 from the opcode start. The old parser read byte 16, which belongs to an eight-byte field preceding GlobalId. Corrected values are 39 for Art Room Ink Ribbon, 111 for Winding Passage Green Herb, 13 for Mansion Storeroom Chemical, 48 for its Broken Shotgun variant, and 52 for Main Hall Ink Ribbon. The table now reads byte 22 for all 647 item entries; 642 values changed. These identifiers are metadata, not automatic proof of save-flag mapping or room completion.
Evidence: [biorand's `ItemAotSetOpcode.Read` at commit 5d0d523, lines 37-67](https://github.com/biorand/biohazard-utils/blob/5d0d523cc0e228b5c9eea269149853cda5f266bd/src/IntelOrca.Biohazard/Script/Opcodes/ItemAotSetOpcode.cs#L37-L67) reads opcode, ID, four 16-bit coordinates, type, amount, eight unknown bytes, two more unknown bytes, then GlobalId. Direct reads of the named disc gave byte 16 / byte 22 pairs: `ROOM1070.RDT` opcode `0x3481C` 24/39, `ROOM1090.RDT` `0x1CA5C` 0/111, `ROOM1180.RDT` `0x292` 0/13 and `0x2AE` 0/48. RE1-PICKUP-002 and RE1-PICKUP-003 independently observed the herb and Chemical flag changes in those rooms. A complete rebuild produced 335 rooms and 647 item entries; aside from GlobalId, all item and door fields stayed identical. Script-operation counts changed in eight rooms (12 init/main counts) because a prior opcode-size fix in `tools/scan_scd.py` had not been reflected in the committed table; all eight still walk cleanly.
Limits: the external parser is a lead and the disc bytes alone do not show the PS1 executable using this field or a universal GlobalId-to-save-bit formula. Art Room, Main Hall, and Chris variant mappings have not had controlled pickup tests. Script event chunks and conditional availability remain unresolved, so room list completeness and completion remain Unknown.
History:
- 2026-09-26; Codex with model unknown; authored and tested; compared the pinned source layout, four disc opcode offsets, two controlled pickup fixtures, and full generated-table fields. This supersedes the byte-16 GlobalId readings in RE1-ROW-001, RE1-ROOM-001, RE1-MILESTONE-001, RE1-PICKUP-002, and RE1-PICKUP-003 without changing their original runtime observations.
- 2026-09-26; Claude Opus 4.6 (Thinking) via agy; reviewed the supplied code diff, test, and finding prose, without running an experiment; identified an ambiguous layout comment and missing table-to-tracker coherence test, both addressed. Suggested a short-opcode guard, rejected after checking that the bytecode walker only returns complete 26-byte opcode `0x18` records.
- 2026-09-26; Gemini 3.1 Pro (High) via agy; reviewed the same supplied material, without running an experiment; identified the untested Art Room mapping and missing scanner coverage, both addressed. Its short-opcode concern was rejected for the same walker invariant.
- 2026-09-26; Gemini 3.8 Flash (High) via agy; reviewed the same supplied material, without running an experiment; independently identified the untested Art Room mapping and ambiguous comment, both addressed. Its claims of omitted generated files and missing rows were rejected by the actual working-tree diff and data-file structure.

## RE1-SAVE-001: Chemical acquisition survives a normal in-game save and load

Status: Confirmed for this revision
Scope: Resident Evil Director's Cut USA, serial SLUS-00551, Training Jill, Chemical pickup in Mansion Storeroom Main 00 Sub 18
Environment: DuckStation 0.1-11894-gc66b2694d on macOS arm64, 2026-09-26; isolated portable copy with its own memory card and GDB server on port 2345. Disc executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`.
Authored: 2026-09-26; human user performed the in-game save and load; Codex with model unknown read GDB and recorded the result
Basis: runtime observation of a normal in-game save/load, live GDB reads, and inspection of the isolated memory card
Claim: after the Chemical was taken, saving at the room's typewriter, resetting, and loading through the game's Load Game menu preserved the collected state at PS1 virtual address `0x800C86DE` bit 2. The byte read `0xFB` after loading, matching the controlled after-pickup state, and inventory slot 6 still held item `0x26` (Chemical), quantity 1. The room read Main 00 Sub 18, camera 00, previous 1F. This confirms persistence through one normal in-game save/load for this flag on this revision; it does not establish full room item coverage or a cleared state.
Evidence: the controlled before-pickup fixture extracts to flag `0xFF`, inventory slot 6 `00 00`, room `00 18 01 0B`; the after-pickup fixture extracts to flag `0xFB`, inventory slot 6 `26 01`, room `00 18 01 0B` (RE1-PICKUP-003). The isolated DuckStation copy booted the after-pickup fixture. The human user saved at the typewriter, reset, loaded through Load Game, and reported control restored. A subsequent GDB read returned room `00 18 00 1F`, flag `0xFB`, and inventory bytes at `0x800C878E` `26 01`; the Ink Ribbon count changed from 6 in the fixture to 5 after the save. The new 131072-byte isolated memory card contained `BASLUS-005510` and had SHA256 `7323a3259f9d77e11a3ebae3f1985fff07f80a3aab8c0ff39bfb8ecaeeaa1c87`. The user's original `SLUS-00551_resume.sav` retained its prior modification time. The memory card and game files are outside Git.
Limits: the GDB read was taken after the user's report of a normal load, not during the game's save or load screens. The earlier normal-save case that should restore `0xFF` remains untested. The result confirms this flag's persistence, not that all RDT items use the same rule, that room completion can be inferred from one flag, or that another game revision shares this address.
History:
- 2026-09-26; human user; tested; saved to the isolated memory card, reset, loaded through the in-game menu, and reported completion.
- 2026-09-26; Codex with model unknown; tested and authored; compared the live GDB read with both controlled fixtures and inspected the isolated memory card, promoting only this normal-load behavior to Confirmed for this revision.

## Suggested next experiments

1. Enable `Debug/EnableGDBServer` with port 2345, connect with a small Python GDB client, and read 16 bytes at `0x80000000` while the game idles. Record whether the game keeps running.
2. Move between two known RE1 rooms and poll a small candidate window at 10 Hz. Save the log with game revision and DuckStation version.
3. Take `.sav` files before and after one pickup, decompress with the header logic above, and diff for stable changed bytes.
4. Only if GDB polling fails, prototype Mach `vm_read` against the DuckStation PID for the same addresses and compare maintainability.
