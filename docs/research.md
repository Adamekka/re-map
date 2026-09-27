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
Claim: the initial source survey suggested room identity as stage plus room plus camera and a 19-entry RDT offset table. It treated SCD Item_set 0x0D as the placement opcode and left acquisition bits and GlobalId mapping unknown. Later SLUS-00551 disc and executable work superseded those item-opcode and flag-mapping parts in RE1-STATIC-001 and RE1-FLAG-001.
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
- 2026-09-26; Codex with model GPT-6 Sol; marked the early 0x0D item and unknown-flag hypotheses superseded by RE1-STATIC-001 and RE1-FLAG-001, preserving the original survey provenance.

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
Limits: this was source inspection before extraction. The earlier interpretation of GlobalId as a runtime table index rather than a save-flag bit index is superseded by RE1-FLAG-001 for SLUS-00551. Item availability and complete room coverage remain unresolved.
History:
- 2026-09-25; opencode with model unknown; reviewed; file format assessment, no runtime test.
- 2026-09-25; opencode with model opencode/muse-spark-1.3-contributor-free; authored; summarized into this entry, still Candidate.
- 2026-09-26; Codex with model GPT-6 Sol; revised the GlobalId limit after verifying the pinned PS1 executable in RE1-FLAG-001; original source-inspection authorship remains.

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
Claim: the init script chunk holds a 0x18 pickup with id 131, type 0x2F Ink Ribbon, amount 3, gid 39 at real coordinates, a candidate match for the Art Room Ink Ribbon behind flag 0xC86E3 bit 0. A second 0x18 entry with id 2, type 0x4E, gid 145 has zero coordinates but maps to the Art Room Map flag at 0xC86ED bit 6 under RE1-FLAG-001; whether and when that row becomes a collectible is unresolved. Polarity 1 means present and 0 means taken fits the ink in inventory, 0x2F times 6, with flag 0xFE, and the map transition between bak and slot, but is still unproven. tools/track_offline.py reads extracted RAM through the Tracker and prints UNKNOWN for the untested Art Room item link and room completion.
Evidence: tools/scan_scd.py decodes 40 init operations before stopping on an unresolved byte, and the main chunk walks cleanly at 45 operations; the event chunk is unparsed. data/room_items_slus00551.json holds the row. Earlier offline runs with a candidate flag link printed Ink Ribbon taken; after removing that untested link, /tmp/ram_slot.bin prints Current room 00-07, Collected 0, State UNKNOWN.
Limits: RE1-FLAG-001 confirms the GlobalId-to-bit code path, but does not prove the Art Room rows are currently available in either saved scenario. Event chunk parsing is open. One room only.
History:
- 2026-09-25; opencode with model opencode/muse-spark-1.3-contributor-free; authored; disc parse plus save evidence, still Candidate.
- 2026-09-26; Codex with model GPT-6 Sol; superseded the byte-16 GlobalId 24 with 39 from RE1-RDT-002 and removed the untested Art Room flag link from the offline tracker; original runtime evidence and Candidate status remain.
- 2026-09-26; Codex with model GPT-6 Sol; superseded the zero-coordinate preload exclusion and missing-map-opcode conclusions after gid 145 and the direct flag code path in RE1-FLAG-001; item availability remains Candidate.
- 2026-09-26; Codex with model GPT-6 Sol; corrected the init walk status and linked the conditional runtime object evidence in RE1-SPAWN-001; the original row extraction and Candidate availability status remain.

## RE1-TABLE-001: partial init/main item scan across 335 RDTs

Status: Candidate
Scope: SLUS-00551 all stages, init and main chunks, metadata only
Environment: local build 2026-09-25 with tools/build_item_table.py, no gameplay
Authored: 2026-09-25; agent/tool: opencode; model: opencode/muse-spark-1.3-contributor-free
Basis: runtime observation of disc bytes
Claim: the original init/main scan recorded 647 opcode 0x18 entries from 335 RDTs, 535 with nonzero coordinates. RE1-SCD-003 later removed two unreachable tail rows, leaving 645 candidate entries in the current table. The historical type counts below describe the original scan: 0x44 Green Herb 107 times, 0x0B Clip 51 times, 0x2F Ink Ribbon 41 times, and 0x0C Shells 30 times. Zero coordinates alone do not prove an entry is a model preload: Vacant Room Shells gid 49 and Art Room Map gid 145 have zero coordinates yet map to named item flags under RE1-FLAG-001. Some chunks stop at unresolved bytes, and ROOM2000.RDT is a dummy file with zero offsets. Variable opcodes 0x33 and 0x17 are handled per scd1.xml. Event chunks stay unparsed. The partial table is committed at data/item_table_slus00551.json, paths plus integers only.
Evidence: per-room walk stats and item rows are in data/item_table_slus00551.json; ROOM1000.RDT remains clean at 115 init ops with 3 entries after the earlier 0x33 fix.
Limits: RE1-FLAG-001 confirms the opcode 0x18 GlobalId-to-bit calculation on this executable, while actual pickup availability and room membership remain untested for most entries. RE1-SCD-001 corrected two scanner opcode widths and changed 53 room scan statistics without changing any of the 647 item rows; RE1-EVENT-001 leaves event-created item coverage unresolved. The 647 rows are not a complete item count. ROOM1000.RDT holds Sword Key plus two 1x1 Serum shaped entries and no ink, so the save room file identity is unconfirmed and the profile demo pickup stays a 00170 side claim.
History:
- 2026-09-25; opencode with model opencode/muse-spark-1.3-contributor-free; authored; disc parse only, still Candidate.
- 2026-09-26; Codex with model GPT-6 Sol; regenerated the item table after RE1-RDT-002 and revised the mapping limit; 647 item entries remain.
- 2026-09-26; Codex with model GPT-6 Sol; revised the zero-coordinate and flag-mapping conclusions after the direct executable evidence and counterexamples in RE1-FLAG-001; entry counts and original extraction evidence are unchanged.
- 2026-09-26; Codex with model GPT-6 Sol; narrowed the table's completeness claim after RE1-SCD-001 and RE1-EVENT-001; the committed rows themselves were unchanged in an in-memory width comparison.
- 2026-09-26; Codex with model GPT-6 Sol; regenerated the table after correcting opcode 0x20/0x21 widths; only `stats` changed in 53 rooms, and the 647 item and all door rows stayed identical.
- 2026-09-26; Codex with model GPT-6 Sol; linked the historical 647-row count to RE1-SCD-003, which regenerated the table with 645 statically reachable candidate rows.

## RE1-DOORS-001: 782 door edges plus filename rule for runtime linkage

Status: Candidate
Scope: SLUS-00551 all stages, init and main chunks
Environment: local parse 2026-09-25 with extended tools/build_item_table.py, no gameplay
Authored: 2026-09-25; agent/tool: opencode; model: opencode/muse-spark-1.3-contributor-free
Basis: runtime observation of disc bytes
Claim: Door_set 0x0C byte 15 splits into next stage bits 7-5 and next room bits 4-0 per scd1.xml, giving 782 directed edges across the disc. The original filename inference used ROOM plus stage plus two digit room plus camera to link files to runtime Main and Sub: ROOM1070.RDT holds the Art Room ink matching runtime Sub 07 and its doors point at rooms 6 and 8, flanking 7. ROOM1000.RDT doors point at room 1, fitting Sub 00 Mansion Save Room next to Sub 01 West Stairway. STAGE1 doors target stages 0, 2, and 3, so the file folder number is not the runtime stage value and stays unresolved. RE1-VARIANT-001 rejects a direct camera-to-suffix rule for one captured Main Hall state.
Evidence: data/item_table_slus00551.json now 399936 bytes with doors arrays, per-room stats unchanged at 327 clean.
Limits: the file number tracks a candidate room number, but the trailing variant cannot be assumed to be 0. RE1-VARIANT-001 directly identifies loaded suffix-1 files in two runtime captures. The historical 782-edge count is a static parse, not a runtime variant selector. Folder to Main mapping remains open; event chunks remain unparsed.
History:
- 2026-09-25; opencode with model opencode/muse-spark-1.3-contributor-free; authored; disc parse only, still Candidate.
- 2026-09-26; Codex with model GPT-6 Sol; revised the filename-rule limit after matching two runtime RAM captures to suffix-1 RDT scripts in RE1-VARIANT-001.

## RE1-LINK-001: filename rule holds for 87 of 90 stage 0 doors

Status: Candidate
Scope: SLUS-00551 STAGE1 doors targeting stage 0
Environment: static check 2026-09-25 over data/item_table_slus00551.json
Authored: 2026-09-25; agent/tool: opencode; model: opencode/muse-spark-1.3-contributor-free
Basis: runtime observation of disc bytes
Claim: for STAGE1 doors with next stage 0, target file PSX/STAGE1/ROOM1 plus two digit hex room plus 0 exists in 87 of 90 cases. The 3 misses point at rooms 0x10 and 0x19, whose files are absent, likely special transitions such as stairs or elevators. Duplicate 0x18 rows identical in id, type, amount, gid, and box are character or mode variants of one pickup. tools/track_offline.py now resolves any Main 0 room through this rule, dedups variants, checks only observed flags, and reports UNKNOWN while coverage is open. Other Main values refuse instead of guessing.
Evidence: door invariant script output 87 resolving and 3 missing. Historical offline runs with a candidate Art Room flag link printed Items 1 Collected 1 State UNKNOWN; with that untested link removed, the same slot RAM prints Items 1 Collected 0 State UNKNOWN.
Limits: static consistency plus 2 runtime rooms is not confirmation. The suffix-0 resolution in `tools/track_offline.py` is contradicted for the captured Main Hall and Winding Passage states by RE1-VARIANT-001; its item list and count for those states must not be treated as current-room truth. The Art Room ink flag association remains untested; controlled item flags now cover the Winding Passage herb and Mansion Storeroom Chemical. Input injection was blocked in the original test environment because Pad1 bound only to an SDL gamepad.
History:
- 2026-09-25; opencode with model opencode/muse-spark-1.3-contributor-free; authored; static check plus offline runs, still Candidate.
- 2026-09-26; Codex with model GPT-6 Sol; updated the current offline output and flag-coverage limit after removing the untested Art Room link.
- 2026-09-26; Codex with model GPT-6 Sol; rejected universal suffix-0 runtime linkage after direct loaded-script comparisons in RE1-VARIANT-001; the historical 87/90 file-existence count remains a static observation.

## RE1-ROOM-001: room change Art Room to Main Hall observed live

Status: Candidate
Scope: SLUS-00551 Training Jill, DuckStation 0.1-11894 dev, GDB reads
Environment: live play by human user on 2026-09-25, agent read over GDB
Authored: 2026-09-25; human user walked, opencode with model opencode/muse-spark-1.3-contributor-free recorded
Basis: runtime observation, two rooms
Claim: Main 0x800C8660 plus Sub 0x800C8661 identify the room on SLUS-00551. Art Room reads 00 07 with prev 06. After the user walked through the door, Main Hall reads 00 06 with prev 07. Prev and Sub cross-link both ways. Item flags are stable across the transition: ink 0xC86E3 stays 0xFE, map bit 0xC86ED stays 0xBF, maps 0xC871C stays 0x08, health stays 0x96. The original filename inference selected `ROOM1060.RDT`; RE1-VARIANT-001 rejects that selection for this capture and identifies `ROOM1061.RDT` instead. Full RAM dumped to /tmp/ram_mainhall.bin, 2097152 bytes, kept out of git.
Evidence: GDB m reads before and after, /tmp/ram_mainhall.bin, and the historical `track_offline` output of three unknown items and State UNKNOWN. The three-item count came from the wrong RDT variant and is invalid for this capture.
Limits: two rooms only for this finding. Leave and re-enter was later shown in RE1-MILESTONE-001. The Art Room ink association remains Candidate; controlled pickup flags are in RE1-PICKUP-002 and RE1-PICKUP-003. RE1-VARIANT-002 establishes the selector for these tested Stage 0 rooms; other stages remain untested.
History:
- 2026-09-25; human user; walked; Art Room to Main Hall through gameplay.
- 2026-09-25; opencode with model opencode/muse-spark-1.3-contributor-free; recorded; GDB reads plus dump, still Candidate.
- 2026-09-26; Codex with model GPT-6 Sol; superseded the byte-16 Main Hall ink GlobalId 32 with 52 from RE1-RDT-002; room-transition evidence is unchanged.
- 2026-09-26; Codex with model GPT-6 Sol; rejected the original `ROOM1060.RDT` inference using the byte-for-byte loaded-script comparison in RE1-VARIANT-001; room-transition evidence is unchanged.

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
- 2026-09-26; Codex with model GPT-6 Sol; superseded the byte-16 Art Room ink GlobalId 24 with 39 from RE1-RDT-002; milestone runtime observations are unchanged.

## RE1-PICKUP-002: controlled green herb take confirms polarity and flag

Status: Confirmed for this revision
Scope: SLUS-00551 Training Jill, Winding Passage Main 00 Sub 09, DuckStation 0.1-11894 dev
Environment: before and after savestates on 2026-09-25, offline extracts, no emulator boot
Authored: 2026-09-25; human user played the single pickup, opencode with model opencode/muse-spark-1.3-contributor-free analyzed
Basis: runtime observation, controlled before and after with one item taken
Claim: taking the Winding Passage Green Herb clears exactly one bit: 0xC86EA bit 0 goes 1 to 0, 0xFF to 0xFE, while the other 13 known Item Collected bytes stay identical. Room bytes are unchanged, Main 00 Sub 09 cam 01, and inventory slot 5 gains 0x44 times 1. The loaded `ROOM1091.RDT` has the Herb row, 0x18 id 5 type 0x44 amount 1 gid 111 at real coordinates. The earlier linear scanner also reported gid 35 after the ordinary init procedure terminates; RE1-SCD-003 removes that unreachable ordinary-init row. The original `ROOM1090.RDT` file identity does not describe these captures. Bit polarity 1 means present and 0 means taken is confirmed for the Herb on this revision. Fixtures are committed at tests/fixtures/slus00551_green_herb_before.sav sha1 9adcac31dac8725219f5672bce9152fa487b5ee9 and slus00551_green_herb_after.sav sha1 1eaf8be8360025d25589255ef244584df84cef53, donated by the user as evidence.
Evidence: tools/extract_sav_ram.py both fixtures, targeted compare of 14 Item Collected bytes with a single-bit diff, track_offline prints INCOMPLETE before and UNKNOWN after.
Limits: save and normal load round trip on this bit untested, re-enter from another room untested for this flag, other flags still Candidate. A separate scripted entry to the gid 35 bytes has not been ruled out, and full room coverage is still open; the Herb pickup does not prove the room is cleared.
History:
- 2026-09-25; human user; played; stood before the herb, saved, took it, saved.
- 2026-09-25; opencode with model opencode/muse-spark-1.3-contributor-free; analyzed; single-bit diff plus inventory plus RDT row, promoting to Confirmed for this revision.
- 2026-09-26; Codex with model GPT-6 Sol; superseded the byte-16 RDT GlobalId 0 with 111 from RE1-RDT-002; the controlled pickup flag result is unchanged.
- 2026-09-26; Codex with model GPT-6 Sol; corrected the runtime file identity to `ROOM1091.RDT` and retracted the one-item list after the loaded-script comparison in RE1-VARIANT-001; controlled Herb evidence is unchanged.
- 2026-09-26; Codex with model GPT-6 Sol; narrowed the apparent second-row interpretation after the executable's opcode-0 termination and captured AOT state in RE1-SCD-002; controlled Herb evidence is unchanged.
- 2026-09-26; Codex with model GPT-6 Sol; noted the scanner correction in RE1-SCD-003 and the live debug view validation in RE1-PILOT-001; controlled pickup evidence is unchanged.

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
- 2026-09-26; Codex with model GPT-6 Sol; revised limits after the normal save/load observation in RE1-SAVE-001 and identified the RDT field-offset error by source and local byte inspection. The original pickup evidence and authorship remain unchanged.
- 2026-09-26; Codex with model GPT-6 Sol; superseded the byte-16 Chemical GlobalId 0 with 13 and revised the Broken Shotgun row to 48 from RE1-RDT-002; controlled pickup and normal-load observations are unchanged.

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
- 2026-09-26; Codex with model GPT-6 Sol; regenerated the side-by-side RDT identifiers after RE1-RDT-002; 15 room matches and 9 unmatched labels remain, with associations still unproven.

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

Status: Confirmed for this revision
Scope: Resident Evil Director's Cut USA, serial SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`; opcode `0x18` in the named RDT files; Training Jill herb and Chemical pickup scenarios tested, Chris variant static only
Environment: local disc read and controlled savestate evidence, 2026-09-26; DuckStation 0.1-11894-gc66b2694d for the pickup experiments in RE1-PICKUP-002 and RE1-PICKUP-003
Authored: 2026-09-26; Codex with model GPT-6 Sol
Basis: source inspection of an independently implemented RE1 RDT parser, direct disc-byte inspection, and comparison with two controlled pickup flags
Claim: opcode `0x18` is 26 bytes long and its one-byte GlobalId field is at byte 22 from the opcode start. The old parser read byte 16, which belongs to an eight-byte field preceding GlobalId. Corrected values are 39 for Art Room Ink Ribbon, 111 for Winding Passage Green Herb, 13 for Mansion Storeroom Chemical, 48 for its Broken Shotgun variant, and 52 for Main Hall Ink Ribbon. The table now reads byte 22 for all 647 item entries; 642 values changed. The parser correction alone did not prove save-flag mapping or room completion; RE1-FLAG-001 establishes the flag calculation for this executable.
Evidence: [biorand's `ItemAotSetOpcode.Read` at commit 5d0d523, lines 37-67](https://github.com/biorand/biohazard-utils/blob/5d0d523cc0e228b5c9eea269149853cda5f266bd/src/IntelOrca.Biohazard/Script/Opcodes/ItemAotSetOpcode.cs#L37-L67) reads opcode, ID, four 16-bit coordinates, type, amount, eight unknown bytes, two more unknown bytes, then GlobalId. Direct reads of the named disc gave byte 16 / byte 22 pairs: `ROOM1070.RDT` opcode `0x3481C` 24/39, `ROOM1090.RDT` `0x1CA5C` 0/111, `ROOM1180.RDT` `0x292` 0/13 and `0x2AE` 0/48. RE1-PICKUP-002 and RE1-PICKUP-003 independently observed the herb and Chemical flag changes in those rooms. A complete rebuild produced 335 rooms and 647 item entries; aside from GlobalId, all item and door fields stayed identical. Script-operation counts changed in eight rooms (12 init/main counts) because a prior opcode-size fix in `tools/scan_scd.py` had not been reflected in the committed table; all eight still walk cleanly.
Limits: RE1-FLAG-001 confirms the pinned PS1 executable reads opcode byte 22 for its item flag checks and pickups. Art Room, Main Hall, and Chris variant items have not had controlled pickup tests. Script event chunks and conditional availability remain unresolved, so room list completeness and completion remain Unknown.
History:
- 2026-09-26; Codex with model GPT-6 Sol; authored and tested; compared the pinned source layout, four disc opcode offsets, two controlled pickup fixtures, and full generated-table fields. This supersedes the byte-16 GlobalId readings in RE1-ROW-001, RE1-ROOM-001, RE1-MILESTONE-001, RE1-PICKUP-002, and RE1-PICKUP-003 without changing their original runtime observations.
- 2026-09-26; Claude Opus 4.6 (Thinking) via agy; reviewed the supplied code diff, test, and finding prose, without running an experiment; identified an ambiguous layout comment and missing table-to-tracker coherence test, both addressed. Suggested a short-opcode guard, rejected after checking that the bytecode walker only returns complete 26-byte opcode `0x18` records.
- 2026-09-26; Gemini 3.1 Pro (High) via agy; reviewed the same supplied material, without running an experiment; identified the untested Art Room mapping and missing scanner coverage, both addressed. Its short-opcode concern was rejected for the same walker invariant.
- 2026-09-26; Gemini 3.8 Flash (High) via agy; reviewed the same supplied material, without running an experiment; independently identified the untested Art Room mapping and ambiguous comment, both addressed. Its claims of omitted generated files and missing rows were rejected by the actual working-tree diff and data-file structure.
- 2026-09-26; Codex with model GPT-6 Sol; promoted only the byte-22 field interpretation to Confirmed for this revision after independently verifying the opcode dispatcher, flag test, and pickup clear path in the named PS1 executable (RE1-FLAG-001). Conditional item availability remains unconfirmed.

## RE1-FLAG-001: opcode 0x18 GlobalId selects an item flag bit

Status: Confirmed for this revision
Scope: Resident Evil Director's Cut USA, serial SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`; opcode 0x18 item flag calculation; Training Jill Winding Passage Green Herb and Mansion Storeroom Chemical runtime pickups
Environment: DuckStation 0.1-11894-gc66b2694d controlled savestates and normal Chemical-after load; macOS arm64, 2026-09-26; static PS-X EXE disassembly with Homebrew LLVM `llvm-objdump` 23.1.2
Authored: 2026-09-26; Codex with model GPT-6 Sol; read-only subagents `/root/ps1_flag_code` and `/root/flag_crosscheck`, models GPT-6 Sol, contributed focused investigations
Basis: direct disassembly of the pinned PS1 executable, independent disc/RDT and flag-note cross-checks, two controlled pickup pairs, and one normal Chemical-after in-game save/load
Claim: the opcode 0x18 item handler reads the one-byte GlobalId at opcode offset 22. For GlobalId `g`, it tests a 32-bit word at PS1 virtual address `0x800C86DC + 4 * (g // 32)` with mask `0x80000000 >> (g % 32)`; the pickup path clears that same bit. In little-endian PS1 RAM byte reads, the equivalent offset is `0xC86DC + 4 * (g // 32) + 3 - ((g % 32) // 8)` with byte mask `0x80 >> (g % 8)`. This predicts herb gid 111 at RAM offset `0xC86EA` bit 0 and Chemical gid 13 at `0xC86DE` bit 2, exactly the bits changed in their controlled pickups. The formula identifies the item's flag bit; a set bit alone does not establish that an item is currently available or that its room is incomplete.
Evidence: `python3 tools/extract_psx_file.py <pinned CUE> SLUS_005.51 /tmp/re-map-slus00551.exe` reproduces the SHA256 above. The PS-X EXE header loads `0x9E800` text bytes at `0x80010000`; a temporary ELF wrapper outside Git has a byte-identical `.text` section for `llvm-objdump -d` inspection. Original file offset is `0x800 + (virtual address - 0x80010000)`. The dispatcher at `0x80025FF4–0x80026010` indexes the opcode table; entry `0x18` at `0x80091168` (file `0x81968`) points to handler `0x80045F28`. That handler reads `lbu $5, 0x16($5)` at `0x80045F7C` and calls test helper `0x800489A8` with base `0x800C86DC`. It stores the opcode-plus-two pointer in the item object at `0x80046020–0x80046024`. The pickup path at `0x8002CDF4–0x8002CE04` reads `lbu $5, 0x14($2)` from that pointer, again original opcode byte 22, and calls clear helper `0x8004897C` with the same base. The helpers shift `g` by 5 for a four-byte word index and shift `0x80000000` by `g & 31` for the bit. The herb fixture changes only `0xC86EA` `0xFF→0xFE`, and the Chemical fixture changes only `0xC86DE` `0xFF→0xFB`, within the 32-byte flag range. RE1-SAVE-001 shows the Chemical-after bit persists through one normal in-game save/load.
Cross-check: inverse-mapping the 25 bits in 24 user-provided item flag labels gives 25 GlobalIds present in `data/item_table_slus00551.json`. Of 14 room-labeled rows with nonempty placed-item lists, 11 have a matching opcode row in the same listed room. The three others do not contradict the formula: Vacant Room Shells gid 49 and Art Room Map gid 145 occur at zero coordinates in their room RDTs, while Bathroom Clips gid 97 occurs in other stage variants. This is static consistency, not 25 runtime pickup tests, and it invalidates the old assumption that every zero-coordinate opcode 0x18 row is a mere preload.
Limits: only the herb and Chemical pickup flags were tested by controlled PS1 runtime comparisons; only Chemical-after has a normal in-game save/load check. The code path does not prove when conditional items spawn, whether zero-coordinate rows are collectible in the current scenario, whether event chunks add items, or whether any room's relevant item list is complete. Do not promote derived per-item availability or room completion from this finding. Do not generalize the address or formula to another executable revision without testing.
History:
- 2026-09-26; human user; played; supplied the controlled herb and Chemical before/after savestates and performed the Chemical-after normal save/load in RE1-PICKUP-002, RE1-PICKUP-003, and RE1-SAVE-001.
- 2026-09-26; Codex subagent `/root/ps1_flag_code` with model GPT-6 Sol; inspected the pinned executable and identified the dispatcher, handler, flag helpers, and pickup path by read-only disassembly; no runtime experiment or repository edit.
- 2026-09-26; Codex subagent `/root/flag_crosscheck` with model GPT-6 Sol; independently derived the bit formula and tested the static RA/RDT concordance and two fixture pairs; no new gameplay or repository edit.
- 2026-09-26; Codex with model GPT-6 Sol; independently verified executable SHA256, byte-identical ELF text, instruction sequences, opcode table entry, address conversion, and both controlled 32-byte flag-window diffs; authored this finding and limited confirmation to this revision's opcode 0x18 calculation.

## RE1-SPAWN-001: room scripts conditionally create item objects

Status: Confirmed for this revision
Scope: Resident Evil Director's Cut USA SLUS-00551, executable identity in RE1-FLAG-001; controlled Training Jill Mansion Storeroom and existing Art Room states only
Environment: DuckStation 0.1-11894-gc66b2694d for controlled Chemical fixtures; offline PS1 RAM and pinned RDT/executable inspection, 2026-09-26
Authored: 2026-09-26; Codex with model GPT-6 Sol; read-only subagents `/root/script_conditions`, `/root/runtime_availability`, and `/root/item_cases` with models GPT-6 Sol contributed separate script, code, and case inspections
Basis: direct executable disassembly, RDT script bytes, and saved PS1 RAM object records; Art Room pickup interpretation remains an inference from uncontrolled states
Claim: an opcode 0x18 row creates its runtime item object only when room script control flow reaches it. In `ROOM1180.RDT`, IF at file `0x28C` tests `04 05 2E 01` at `0x28E`, then chooses Chemical gid 13 at `0x292`; ELSE at `0x2AC` chooses Broken Shotgun gid 48 at `0x2AE`, using the same object ID and rectangle. The opcode 0x04 handler maps flag group 5 to PS1 virtual base `0x800C3000`; index `0x2E` is RAM byte `0xC3006` bit 1, and expected value 1 tests for a clear bit. It is clear in both controlled Chemical fixtures (`0xC3006=0x04`). Their object ID 1 record at PS1 virtual `0x800B816C` points to `0x80121E94`, exactly Chemical opcode `0x292` plus two in the loaded RDT, and its state byte changes `0x04→0x00` on pickup. Its acquisition flag changes `0xC86DE: 0xFF→0xFB`. The alternate branch and the broader meaning of group-5 bit 46 were not tested in gameplay.
Art Room cross-check: `ROOM1070.RDT` has zero-coordinate Map gid 145 rows at `0x347A4` and `0x347DE` in alternate branches. The branch selection tests player byte `0xC8669` against 3 and tests the Map item bit with `04 07 91 00`. Existing Art Room RAM has player value 1 and object ID 2 pointer `0x801563E0`, matching the second Map opcode `0x347DE` plus two in the loaded RDT. Object state byte is `0x0F` with flag `0xC86ED=0xFF` in the earlier backup, then `0x00` with flag `0xBF` in the later slot. Thus a zero-coordinate opcode row did execute and produce an object record; the backup/slot comparison is not a controlled Map pickup test, and the accompanying generic interaction opcode's role is unresolved.
Evidence: `ROOM1180.RDT` SHA256 `7a3b57eb01a2b3ac445090128555feb21ba39a38680d3381265e8fa54401be40`; `ROOM1070.RDT` SHA256 `1f3c51bb02986c8bfc9c4804b4f319a411f12361dab6ec55c2f49b39ea5d44b1`, both extracted from the named disc. The opcode 0x04 dispatcher entry points to handler `0x80044D54`, which selects flag bases and tests the indexed bit; opcode 0x01/0x02 handlers at `0x80044C6C`/`0x80044CC4` implement IF/ELSE jumps. The opcode 0x18 handler at `0x80045F48–0x80045FD4` indexes 12-byte object records by ID and initializes state from the acquisition bit; `0x80046020–0x80046024` stores the opcode-plus-two pointer. For the Chemical fixtures, `/tmp/ram_chem_before.bin` SHA256 `bb9110536a02122d7c6a14d489b2e94e7d8224d8ccf297d617694c4eb6e804f2` and `/tmp/ram_chem_after.bin` SHA256 `0d5e7dc6e450a99b9f8a354cc9ffd30e97dd3129427600e384681903330935df` reproduce the object and flag changes. Art Room `/tmp/ram_bak.bin` SHA256 `6725226807810c7667a9705233d65b7847dd8a43bceef401e6be610bb9405146` and `/tmp/ram_slot.bin` SHA256 `6451194fac736aa6cc7b3db1684e08e07a5037863cada5dbdc07bd6daedd9515` contain RDT bytes at loaded RAM base `0x80121C00`, matching both object pointers. [Reevengi's pinned SCD field layout](https://github.com/pmandin/reevengi/blob/8130d5fd029a7548135bdbbff19b0b8e338bd42d/src/g_re1/scd1.xml#L99-L150) was a naming lead; the PS1 executable and RAM provide the behavior evidence.
Limits: only the named Chemical branch was tested in a controlled pickup pair. Object state values for other item types and the zero-coordinate Map interaction are not yet validated as universal availability rules. `ROOM1020.RDT` and alternate Bathroom RDTs contain further group-5 gated items, but no corresponding controlled runtime scenario was tested. A set acquisition bit or static RDT row alone cannot establish that the room script executes that item in the current game state.
History:
- 2026-09-26; human user; supplied controlled Chemical pickup fixtures and earlier Art Room savestates.
- 2026-09-26; Codex subagents `/root/script_conditions`, `/root/runtime_availability`, and `/root/item_cases`, models GPT-6 Sol; reviewed separate script, executable, and anomalous-item evidence without repository edits or new gameplay.
- 2026-09-26; Codex with model GPT-6 Sol; independently checked IF/ELSE and flag-test instructions, RDT offsets, fixture flag values, runtime object pointers and state bytes, and loaded RDT byte equality; authored this finding with the alternate branch and Map interaction limits.

## RE1-SCD-001: two scanner opcode widths disagree with the executable

Status: Confirmed for this revision
Scope: SLUS-00551 executable identity in RE1-FLAG-001; opcode 0x20 and 0x21 lengths in RDT script scanning
Environment: static executable disassembly and in-memory disc table rebuild, 2026-09-26
Authored: 2026-09-26; Codex with model GPT-6 Sol; subagent `/root/script_conditions` with model GPT-6 Sol first identified the mismatch
Basis: direct PS1 instruction sequence and regenerated table comparison, without code changes
Claim: opcode 0x20 and 0x21 handlers advance the script pointer by 14 bytes. The scanner previously assigned 16 and 18 bytes; it now uses 14 for both. Regenerating with only these two widths corrected changed scan status or operation counts in 53 of 335 rooms. Several previously stopped chunks became clean, while four previously clean Stage 7 init chunks now stop on unresolved bytes; one Stage 7 main chunk stays clean with one fewer decoded operation. All 647 item rows and all door rows stayed identical; this does not make the table complete because other opcode and event parsing gaps remain.
Evidence: opcode dispatch table entries `0x80091188` and `0x8009118C` point to handlers `0x80046C2C` and `0x80046CD4`. Their script pointer increments are `addiu $3, $3, 0xE` at `0x80046CAC` and `addiu $2, $3, 0xE` at `0x80046CE4`; both store the advanced pointer at `0x800CF640`. A temporary in-memory correction and a subsequent run of `tools/build_item_table.py` on the pinned CUE produced byte-identical JSON. Structural comparison with the previous committed table found 53 changed `stats` fields and zero changed `items` or `doors` fields. `ROOM7170/7171` init changes `clean/33→unknown 0xD0`, `ROOM71C0/71C1` init changes `clean/34` or `clean/33→unknown 0x28`, and `ROOM7041` main changes `clean/38→clean/37`. The regression test places an opcode 0x18 item immediately after each corrected opcode and verifies the item's address and byte-22 field.
Limits: the four formerly clean Stage 7 chunks cannot be treated as fully decoded; opcode 0x28 is variable and 0xD0 remains unresolved at the new boundaries. The lower operation count in ROOM7041 is a changed segmentation result, not a lost item or door row. Only these two opcode widths were corrected and verified for the pinned executable; other revisions need their own validation. Other unknown or variable opcodes still stop scans, and event sections remain outside the table. This finding corrects a parser defect but does not establish that room item coverage is complete.
History:
- 2026-09-26; Codex subagent `/root/script_conditions` with model GPT-6 Sol; found the mismatch while tracing event scripts, verified an in-memory rebuild, and reported no changed item rows.
- 2026-09-26; Codex with model GPT-6 Sol; independently verified both dispatch entries and pointer increments and repeated the in-memory rebuild comparison across all 335 rooms.
- 2026-09-26; Codex with model GPT-6 Sol; corrected the two widths, regenerated the table, and added an adjacent-item alignment regression test; the fixture and full table comparisons keep item/door rows unchanged.
- 2026-09-26; Claude Opus 4.6 (Thinking) and Gemini 3.8 Flash (High) via agy; reviewed the supplied uncommitted diff without running experiments; both identified the four clean-to-stopped Stage 7 scans and ROOM7041 count reduction, which Codex verified against old and regenerated JSON and recorded above.
- 2026-09-26; Gemini 3.1 Pro (High) via agy; reviewed the same supplied diff without running experiments; its proposed test TypeError and file-size contradiction did not reproduce in the passing test and direct file measurements. No executable behavior was verified by this review.

## RE1-EVENT-001: event scripts remain outside the committed item scan

Status: Candidate
Scope: SLUS-00551 RDT event sections, especially `ROOM1070.RDT`; completeness of the RE1 item list
Environment: static disc inspection with experimental event decoder, 2026-09-26; no event-trigger gameplay test
Authored: 2026-09-26; Codex subagent `/root/script_conditions` with model GPT-6 Sol
Basis: RDT bytes and exploratory event decoding, with PC format documentation used only as a lead
Claim: the committed item table scans RDT init and main script sections, not event sections. The Art Room event section at file `0x34A58–0x34AA0` begins with relative 32-bit offsets `0x0C, 0x30, 0` and contains two indexed event scripts. The event decoder encountered embedded SCD commands, so event paths may add item behavior outside the current table. An exploratory sweep found no opcode 0x18 item creation in event blocks that decoded cleanly, but it cannot establish absence of event-created items across the disc.
Evidence: `ROOM1070.RDT` hash is recorded in RE1-SPAWN-001. Of 335 RDTs, 257 have event sections longer than four bytes by the committed header offsets. A temporary event sweep indexed 2,192 scripts, observed 4,545 direct embedded SCD calls and 2,592 embedded SCD blocks, and decoded 2,441 blocks cleanly with the corrected opcode 0x20/0x21 lengths. The remaining 151 blocks stopped on unknown or variable commands, and two RDTs did not fit the assumed offset table. Four apparent event item rows from the old 0x20 width disappear with the executable's 14-byte width and are rejected as misaligned operands. This sweep was exploratory and its negative result was not independently replayed.
Limits: event branching/calls were not followed, some event opcodes are unresolved, and the decoder is not committed. Do not infer full item coverage or room clearing from this negative sweep. RE1-EVENT-002 narrows the indexed event paths for one Winding Passage file only. [The PC event disassembler](https://github.com/ecruells/resident-evil-pc-decomp/blob/f7b2dee05e3ce420a95de9cb8300b6ec7b0dc8f5/tools/evt_disasm.py) is a format lead, not PS1 runtime confirmation.
History:
- 2026-09-26; Codex subagent `/root/script_conditions` with model GPT-6 Sol; performed the read-only Art Room event inspection and exploratory whole-disc sweep, noting parse gaps and rejecting false positives after the opcode width correction.
- 2026-09-26; Codex with model GPT-6 Sol; independently checked the 257 nontrivial section count and Art Room event offset bytes, then recorded the sweep as a Candidate with its unresolved paths.

## RE1-EVENT-002: Winding Passage indexed events show no second item command

Status: Candidate
Scope: Resident Evil Director's Cut USA SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`; Jill Winding Passage `ROOM1091.RDT` SHA256 `aafa97fb8a08d628a9cc34fc4b74fd4cf15783596c98b95733d7643e1ecfcf09`
Environment: pinned disc RDT and executable, donated before/after Herb RAM captures, 2026-09-26; no new gameplay event trigger
Authored: 2026-09-26; Codex with model GPT-6 Sol; read-only subagents `/root/winding_event` and `/root/winding_static` with model GPT-6 Sol independently traced the event paths
Basis: RDT and RAM byte comparisons, PS1 executable disassembly, and an exploratory event walk using [the PC event disassembler at commit `f7b2dee`](https://github.com/ecruells/resident-evil-pc-decomp/blob/f7b2dee05e3ce420a95de9cb8300b6ec7b0dc8f5/tools/evt_disasm.py) as a format lead
Claim: this room's indexed event scripts contain no decoded `0x18` item creation command. The event offset table has ten entries; the PC-informed walk reaches the terminator of each script and locates four embedded SCD blocks and ten direct SCD commands. All 27 embedded SCD opcodes decode cleanly with the local PS1 scanner, and none is `0x18`. The only raw event-section byte `0x18`, at file `0x1CBE2`, lies inside a `0x20` command's operand, not at an opcode boundary. One embedded `0x13` command at `0x1CC40` changes an existing object record for id 3, which ordinary init created as a door at `0x1CA28`; it does not create another item. The ordinary init/main scan still has only the Green Herb item row at `0x1CA5C` (RE1-SCD-003).
Evidence: the RDT header places the event section at file `0x1CAD4–0x1CF18`. Its table at `0x1CAD4–0x1CB00` ends with a zero dword and names scripts starting at `0x1CB00`, `0x1CC30`, `0x1CC48`, `0x1CC84`, `0x1CCF8`, `0x1CD38`, `0x1CDE0`, `0x1CE90`, `0x1CEC8`, and `0x1CEF8`. In both controlled RAM captures, the 1,048-byte event body after the table matches the disc at loaded base PS1 VA `0x80121C00`; the ten table dwords are relocated to pointers and the zero sentinel remains zero. The executable loader at `0x80044B74–0x80044BDC` performs that relocation. Event opcodes `0x06` and `0x07` dispatch through `0x80026190` and `0x800261A0` to `0x80027184` and `0x800271E0`, which run a length-prefixed SCD block or one command through the `0x80091108` SCD dispatch table. Embedded blocks start at file `0x1CB00`, `0x1CBB4`, `0x1CBD4`, and `0x1CC1C`; direct commands start at `0x1CB30`, `0x1CB52`, `0x1CB6A`, `0x1CB70`, `0x1CB84`, `0x1CB8A`, `0x1CB9A`, `0x1CBA0`, `0x1CBA8`, and `0x1CC3E`. The `0x20` command starts at `0x1CBDA` and has the executable-confirmed 14-byte width (RE1-SCD-001), covering the apparent `0x18`. The PS1 `0x13` handler at `0x80045C38–0x80045C84` writes two bytes to AOT id 3; both Herb captures have id 3 active as the init door, while id 5 is the sole active item object and changes `04→00` on pickup (RE1-AOT-001). A second independent read-only walk reproduced the 27-opcode count and empty `0x18` list.
PS1 interpreter cross-check: in the pinned executable, the control dispatch table at PS1 VA `0x800101A0` routes `F8` to `0x80025E10` and `F9` to `0x80025E58`; these handlers create and decrement the delay counter, then advance past the four-byte `F8 F9 nn nn` sequence. State dispatch at `0x80026078` reaches the room-used state-0, state-1, and state-2 handlers. The consumed widths match the exploratory walk for state-0 `04/05/06/07`, state-1 `81/84/87`, and state-2 `07`, including the embedded SCD dispatch at `0x80027184/0x800271E0`. The ordinary SCD runner at `0x800489CC` is called for room init at `0x800445FC`, room main at `0x80029FF8`, and event opcode `06` at `0x800271A4`. A repeat walk reached ten `FF` terminators; no `FC/FD` or `FA/FB` instruction appeared at a walked boundary. The room's event bytes contain only one raw `0x18` byte, at `0x1CBE2` inside the `0x20` operand. This checks the room-used event path against the named PS1 executable rather than relying only on the PC format lead.
Limits: the checked instruction widths cover the event opcodes encountered in these ten indexed scripts, not the entire event interpreter or a runtime trigger of every event. Native or later story-dependent item creation outside these paths remains possible. The negative scan does not prove complete collectible coverage. The tracker must keep room completion `UNKNOWN` after the Herb is taken. RE1-REENTRY-001 records one user-operated leave/return; normal in-game Herb save/load remains untested.
History:
- 2026-09-26; human user; provided the controlled before/after Herb savestates used for the RAM comparison.
- 2026-09-26; Codex subagent `/root/winding_static` with model GPT-6 Sol; independently walked all ten indexed scripts and their embedded SCD, checked object records, and identified the unresolved PC-derived outer event semantics without editing files.
- 2026-09-26; Codex subagent `/root/winding_event` with model GPT-6 Sol; traced the PS1 event table relocation, `0x06/0x07` dispatch, embedded commands, and `0x13` object update without editing files.
- 2026-09-26; Codex with model GPT-6 Sol; replayed the ten-script and 27-opcode counts, compared the disc event body with both RAM captures, verified the executable loader and dispatch instructions, and authored this bounded finding.
- 2026-09-27; Codex subagent `/root/event_dispatch` with model GPT-6 Sol; traced the room-used event opcode widths and delay control in the pinned PS1 executable without triggering events in gameplay.
- 2026-09-27; Codex subagent `/root/winding_coverage` with model GPT-6 Sol; independently checked the ordinary SCD runner's call sites and the absence of another indexed item opcode without triggering events in gameplay.
- 2026-09-27; Codex with model GPT-6 Sol; checked the executable and RDT hashes, the runner call sites, ten static event terminators, and the single raw `0x18` operand; revised the limits without changing tracker behavior.

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

## RE1-VARIANT-001: two runtime rooms load suffix-1 RDT files

Status: Confirmed for this revision
Scope: Resident Evil Director's Cut USA SLUS-00551, Training Jill Main/Sub 00-06 and 00-09 captures; executable identity in RE1-FLAG-001
Environment: DuckStation 0.1-11894 dev RAM captures from 2026-09-25, compared with RDTs extracted from the named disc on 2026-09-26
Authored: 2026-09-26; Codex with model GPT-6 Sol; subagent `/root/object_ram_crosscheck` with model GPT-6 Sol independently checked Main Hall item records
Basis: byte-for-byte runtime RAM versus disc script comparison, static RDT item rows, and saved runtime object records
Claim: Main/Sub 00-06 in `/tmp/ram_mainhall.bin` loads `ROOM1061.RDT`, and Main/Sub 00-09 in `/tmp/ram_herb_before.bin` loads `ROOM1091.RDT`. The trailing filename digit is not universally 0. The hardcoded suffix-0 rule in `tools/track_offline.py` selects the wrong item list for both captures. The loaded Main Hall variant has Ink gid 52 and zero-coordinate rows gid 14 and 9, whereas `ROOM1060.RDT` also has a placed gid 26 pickup absent from `ROOM1061.RDT`. The loaded Herb variant contains the controlled Herb gid 111 and a scanner row gid 35 after the ordinary init procedure terminates (RE1-SCD-002); `ROOM1090.RDT` has only the Herb row. The current-room item list and any derived completion result cannot rely on the suffix-0 rule.
Evidence: script sections use RDT header offsets 6 through 8 and load at PS1 RAM base `0x121C00`. Main Hall RAM SHA256 `8432db90eb1b15076d53ba1fc8b59627194030858b6b4b644e8d94b29f586a75` matches `ROOM1061.RDT` init+main across 1116/1116 bytes, versus 174/712 bytes matching `ROOM1060.RDT`. Herb-before RAM SHA256 `d819fbd41abea6537bf9ce9f4967b479ea1f6278024b9f4e018290343c0bc8d4` matches `ROOM1091.RDT` across 252/252 bytes, versus 193/200 for `ROOM1090.RDT`. Extracted suffix-1 RDT SHA256 values are `4bb6e58451df65a2ac13f7bf13ce2c914e82753e551c460255af89a1cc858738` and `aafa97fb8a08d628a9cc34fc4b74fd4cf15783596c98b95733d7643e1ecfcf09`. In Main Hall, AOT id 5 at PS1 VA `0x800B819C` points to `0x80151810`, the loaded `ROOM1061.RDT` Ink opcode at file `0x2FC0E` plus two. The capture's camera byte is 2, so the suffix is not simply the current camera number.
Limits: these comparisons identify the loaded file in two saved states; RE1-VARIANT-002 separately traces the Stage 0 file selector in the executable. Static rows are not proof that their pickup objects are currently available. RE1-SCD-002 excludes the gid 35 row from the ordinary init path in the captured Herb room; RE1-AVAIL-001 finds the Main Hall rows skipped in its captured state. Other scripted entry points and future state changes remain unresolved. RDT and RAM artifacts remain outside Git. RE1-ROOM-001 and RE1-PICKUP-002 preserve the original room and pickup observations while retracting their suffix-0 item-list inferences.
History:
- 2026-09-25; human user; played; produced the Main Hall and controlled Herb states used in the captures.
- 2026-09-26; Codex subagent `/root/object_ram_crosscheck` with model GPT-6 Sol; independently matched the Main Hall script bytes and Ink object pointer, and compared Main Hall item rows without new gameplay.
- 2026-09-26; Codex with model GPT-6 Sol; independently compared both RDT script spans against RAM, verified hashes and item rows, and authored this limited file-identity correction.
- 2026-09-26; Codex with model GPT-6 Sol; linked the direct file-identity evidence to the executable selector in RE1-VARIANT-002 without changing these capture results.
- 2026-09-26; Codex with model GPT-6 Sol; corrected the interpretation of loaded-variant item rows after the script-path checks in RE1-SCD-002 and RE1-AVAIL-001; file identity evidence is unchanged.

## RE1-VARIANT-002: Stage 0 RDT loader uses a per-room selector and flag bit

Status: Confirmed for this revision
Scope: Resident Evil Director's Cut USA SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`; Stage 0 rooms 06, 07, 09, and 18 in Training Jill captures
Environment: pinned PS-X executable and disc catalog inspected on 2026-09-26; DuckStation 0.1-11894 dev RAM captures from 2026-09-25
Authored: 2026-09-26; Codex with model GPT-6 Sol; subagent `/root/variant_exec` with model GPT-6 Sol found the selector and `/root/variant_ram` with model GPT-6 Sol independently checked the captures
Basis: direct MIPS disassembly, executable table bytes, disc file order, and runtime RAM script matches; external RDT naming research is a lead for character semantics
Claim: the Stage 0 room loader at PS1 VA `0x8004484C–0x800449A8` reads the room byte at `0x800C8661`, a little-endian base file ID at `0x80090BC8 + 2*room`, and a selector byte at `0x80090F48 + room`. If the selector is 0, it loads `base + 1 + ((word at 0x800C3000 >> 23) & 1)`; if the selector is 1, it loads `base + 1`. These are file IDs passed to the loader at `0x8002AD70`, not RDT filename characters. For the four captured rooms, those IDs map to the exact loaded RDT files found in RE1-VARIANT-001 and RE1-SPAWN-001. The simple rule "choose suffix 1 whenever that file exists" is false even in Stage 0: room `0x12` has both `ROOM1120.RDT` and `ROOM1121.RDT`, but its selector byte is 1, so this loader takes `base + 1` regardless of bit 23.
Evidence: the executable's room 06/07/09/18 base IDs are 454/457/462/498 and selector bytes are 0/1/0/1. Representative Jill RAM captures for each of these four rooms read `0x800C3000` bit 23 as 1; the computed IDs are 456/458/464/499. In this disc's ISO file listing, entry index is file ID + 3 for these assets: those IDs name `ROOM1061.RDT`, `ROOM1070.RDT`, `ROOM1091.RDT`, and `ROOM1180.RDT`. Each file's init and main scripts match its room RAM byte for byte. The pinned executable's room 12 base ID is 483 and selector byte 1; `ROOM1120.RDT` and `ROOM1121.RDT` both exist and have different SHA256 hashes `4d41e3b21316f608c6d531b73ac1f4fe10e12a9c09e953b959e672d9599f659b` and `1e4614f25676a6ea5be63d4a3419f34bc20aac52b54b281c8827edf283e8d14c`. [Reevengi-tools' RDT naming description](https://github.com/pmandin/reevengi-tools/wiki/.RDT-(Resident-Evil)), wiki commit `6010520d6adb1ede369c52d432432017c09d0ded`, calls suffix 0 Chris and suffix 1 Jill. All eight loaded Jill captures have character byte `0x800C8669=1` and bit 23 set. A separate non-gameplay Chris snapshot has character byte 0 and bit 23 clear, but no loaded room script.
Limits: the executable proves the Stage 0 file-ID computation; the relationship of bit 23 to character is supported by the naming source and these states but has not been tested by loading a Chris room with both variants. The non-gameplay Chris snapshot cannot serve as a room-file test. The writer and normal-save behavior of bit 23 were not traced. Other stage values enter different branches, including special handling for stages 5, 6, 12, and 13, so do not apply this Stage 0 formula to them without tracing and testing. Room 12's suffix-1 file may have another use; this observation only covers this loader path. Conditional item availability and full room coverage remain unresolved.
History:
- 2026-09-26; Codex with model GPT-6 Sol; consulted Patrice Mandin's reevengi-tools RDT naming reference as an external lead; it does not test this exact executable.
- 2026-09-26; Codex subagent `/root/variant_exec` with model GPT-6 Sol; traced the pinned executable's Stage 0 loader, table entries, bit test, and file-ID call without repository edits.
- 2026-09-26; Codex subagent `/root/variant_ram` with model GPT-6 Sol; matched eight loaded Jill captures to the corresponding disc scripts and excluded one non-gameplay Chris snapshot from file-selection evidence.
- 2026-09-26; Codex with model GPT-6 Sol; independently checked the disassembly, executable table bytes, disc catalog mapping, four saved bit values, and room 12 exception; authored this bounded rule.

## RE1-AOT-001: item object state is a handler index, not an availability bit

Status: Confirmed for this revision
Scope: Resident Evil Director's Cut USA SLUS-00551 executable identity in RE1-FLAG-001; controlled Training Jill Herb and Chemical pairs; uncontrolled Art Room and Main Hall captures
Environment: pinned executable disassembly and saved PS1 RAM reads, 2026-09-26
Authored: 2026-09-26; Codex with model GPT-6 Sol; subagent `/root/object_state_code` with model GPT-6 Sol traced the executable handlers
Basis: executable disassembly and runtime object records; only Herb and Chemical have controlled pickup pairs
Claim: opcode 0x18 indexes 12-byte AOT records at PS1 VA `0x800B8160 + 12*(id & 0x7F)`. Record byte 0 selects an interaction handler rather than directly expressing current collectibility. When the acquisition bit is set, the opcode initializes an ordinary item type below `0x4E` to handler `0x04`, a Map type `0x4E..0x53` to `0x0F`, and types at least `0x54` to `0x0D`; a cleared acquisition bit instead gives state 0. The controlled Herb id 5 and Chemical id 1 records both change `0x04` to 0 when taken, while their acquisition bits clear. A current script-row pointer plus the handler state can show that an object was instantiated, but a nonzero state alone does not prove the player can collect it now. A stale pointer alone is insufficient because room reset clears state byte 0 without clearing the saved pointer bytes.
Evidence: opcode 0x18 handler at `0x80045F48–0x80045FD4` writes the state, with dispatch table at `0x80090404`; reset at `0x80044C20–0x80044C50` clears state byte 0 for the first 24 records. In `/tmp/ram_herb_before.bin` versus `/tmp/ram_herb_after.bin`, id 5 at RAM `0xB819C` changes state `04→00` with pointer `0x8013E65E`, matching the loaded `ROOM1091.RDT` Herb row. In `/tmp/ram_chem_before.bin` versus `/tmp/ram_chem_after.bin`, id 1 at `0xB816C` changes `04→00` with pointer `0x80121E94`, matching `ROOM1180.RDT` Chemical. Main Hall id 6 at `0xB81A8` has state 0 and pointer `0x80156472`, matching none of the loaded `ROOM1061.RDT` id 6 opcode-plus-two addresses `0x8015185C`, `0x801518A8`, or `0x801518FE`, even though their gid 14 and gid 9 acquisition bits are set. This demonstrates that a set acquisition bit does not imply a matching active item object in that captured room state. RE1-AVAIL-001 later traced failed IF checks for these rows; their future availability remains unresolved.
Map limit: Art Room id 2 changes state `0x0F→0` across the uncontrolled backup-to-slot interval. Its record byte 1 is 0, while the ordinary interaction scans at `0x80038910–0x800389B4` and `0x80038AB4–0x80038B54` require matching mode bits and geometry. The state-15 handler at `0x80038578–0x800385E8` clears the acquisition bit and calls `0x80033D48` to set a Map-owned bit. For type `0x4E`, this predicts `0xC871C` bit 3, observed changing 0 to 1 between the Art captures. The Art event bytes at `ROOM1070.RDT` file `0x34A88` include a command targeting id 2 and handler 15, but its runtime trigger has not been observed; treat the event-path interpretation as Candidate.
Limits: no universal item availability or room-clear rule follows from these captures. An AOT slot may be overwritten by later script commands. RE1-AVAIL-001 reconstructs why the Main Hall rows were skipped in this capture; later event behavior remains open. The Map comparison is not a controlled pickup test. RE1-SCD-002 excludes the Herb-room gid 35 row from ordinary init execution but cannot rule out every separate entry path. The tracker must keep room completion Unknown until relevant conditions and item coverage are validated.
History:
- 2026-09-26; human user; supplied the controlled Herb and Chemical fixtures and earlier Art Room states.
- 2026-09-26; Codex subagent `/root/object_state_code` with model GPT-6 Sol; traced opcode 0x18, reset, interaction dispatch, and Map handlers in the pinned executable without new gameplay.
- 2026-09-26; Codex subagent `/root/object_ram_crosscheck` with model GPT-6 Sol; independently compared controlled and Main Hall records against the loaded RDT rows without new gameplay.
- 2026-09-26; Codex with model GPT-6 Sol; verified the script-span matches and object bytes in the saved RAM, and recorded the limits on availability inference.

## RE1-AOT-002: interaction scans use a dynamic item-object bound

Status: Confirmed for this revision
Scope: Resident Evil Director's Cut USA SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`; controlled Jill Herb and Chemical captures, plus Art Room and Main Hall captures
Environment: pinned executable disassembly, generated item table, and saved PS1 RAM, 2026-09-27
Authored: 2026-09-27; Codex with model GPT-6 Sol; subagent `/root/aot_interaction_scope` with model GPT-6 Sol traced the interaction loops
Basis: executable reset, initializer, and interaction code checked against saved object records
Claim: room reset clears the state byte in 24 twelve-byte AOT records starting at PS1 VA `0x800B8160`. A 32-bit little-endian pointer at PS1 VA `0x800B7ED8` tracks the highest initialized record. The two inspected player-interaction loops scan twelve-byte records from the base through that pointer, dispatching eligible records by their state byte. In the controlled Winding Passage after-Herb capture, this bound reaches id 5, ids 0–4 are doors, and id 5 has state 0; no other normal item handler is active within that bound. This describes the captured state, not a complete room item list.
Evidence: reset code at `0x80044C20–0x80044C50` loops 24 times, clears record byte 0, and resets the bound to `0x800B8160`; item initializer `0x8004602C–0x80046044` raises the bound. The interaction loops at `0x80038910–0x800389D0` and `0x80038AB4–0x80038B78` advance by 12 bytes, compare against the bound, and dispatch through the state table at `0x80090404`. Controlled RAM reads at offset `0xB7ED8` give inclusive bounds `0x800B819C` for both Herb states and `0x800B8190` for both Chemical states; the Art Room captures give `0x800B822C`. The Herb-before capture has one active normal item handler, id 5 state 4 with pointer `0x8013E65E`; the after capture has id 5 state 0 and no other state-4, state-13, or state-15 record through the bound. Across the current generated table's 645 opcode-`0x18` rows, every `id & 0x7F` is at most 23.
Limits: the 24-record reset and current table IDs do not enforce a universal maximum on the opcode's seven-bit ID field. Interaction eligibility also depends on record mode bits and geometry; an active handler alone is not proof that the item is collectible at that moment. Map and other special handlers can follow event-driven paths. A later script may replace an AOT slot or instantiate another item, and a native item grant might bypass these loops. One endpoint without an active item cannot prove full collectible coverage. The tracker must keep Winding Passage completion `UNKNOWN` after the Herb under the current evidence.
History:
- 2026-09-27; Codex subagent `/root/aot_interaction_scope` with model GPT-6 Sol; traced reset, high-water updates, interaction loops, handler classes, and mode/geometry filters without a gameplay experiment.
- 2026-09-27; Codex subagent `/root/clear_rule_audit` with model GPT-6 Sol; assessed whether these observations justify Cleared, without reproducing gameplay; concluded that the coverage condition remains unmet.
- 2026-09-27; Codex with model GPT-6 Sol; independently checked reset and loop disassembly, counted current table IDs, and compared high-water and handler bytes across saved RAM captures.

## RE1-SCD-002: an apparent Winding Passage item follows script termination

Status: Confirmed for this revision
Scope: SLUS-00551 executable identity in RE1-FLAG-001; loaded `ROOM1091.RDT` init procedure and Training Jill Herb captures
Environment: pinned executable disassembly, disc RDT bytes, and saved PS1 RAM, 2026-09-26
Authored: 2026-09-26; Codex with model GPT-6 Sol; subagent `/root/herb_gid35` with model GPT-6 Sol traced the procedure and counted similar scanner rows
Basis: executable script-runner control flow, RDT procedure boundaries, saved AOT record, and whole-disc read-only scanner comparison
Claim: opcode `0x00` ends the current script procedure in this executable. The then-current linear scanner treated it as a two-byte no-op and reported an opcode `0x18` item row with gid 35 at `ROOM1091.RDT` file `0x1CAA6`. Ordinary init execution reaches `00 FF` at `0x1CA94` without a preceding branch, then stops. The room's next length-prefixed procedure at `0x1CACA` has zero length. Thus the gid 35 row is not reached by ordinary room initialization and did not create an item object in the controlled Herb captures. This corrects the apparent second-item inference in RE1-PICKUP-002 without changing its Herb flag result.
Evidence: opcode-0 dispatch-table entry at PS1 VA `0x80091108` points to `0x80044C5C`, which clears script-depth byte `0x800CF63A` and returns zero. The runner at `0x800489E0–0x80048AD0` dispatches handlers, continues a procedure only on a nonzero return, and advances to the next length prefix after the zero return with no pending IF exit. `ROOM1091.RDT` init begins at `0x1C9D8` with length `0xF0` and ends at `0x1CACA`; the terminator is at `0x1CA94`, before the scanner row. In `/tmp/ram_herb_before.bin`, AOT id 0 at PS1 VA `0x800B8160` points to `0x8013E5DC`, the earlier Door_set opcode `0x1C9DA` plus two, rather than gid 35 opcode-plus-two `0x8013E6A8`. Herb id 5 points to its own opcode and changes state on pickup. A fresh read-only sweep using `tools/scan_scd.py::walk` on the length-prefixed init/main sections parsed by `tools/build_item_table.py` found 13 item rows after the first opcode 0 across 335 RDTs and 668 valid chunks: one here, eight across `ROOM10E0/10E1/60E0/60E1`, one in `ROOM40A0`, and three across `ROOM8130/D130/D131`.
Further path check: the pinned executable contains the item initializer `0x80045F28` as a literal pointer only in SCD dispatch-table slot `0x80091168`; no direct `jal` or `j` to it appears in the disassembly. Ordinary init, main, and embedded event blocks use that dispatch table, while event opcode `07` dispatches one SCD command through it. The ten indexed event pointers in `ROOM1091.RDT` all lead into the event section, not the gid 35 tail; RE1-EVENT-002 finds no additional item opcode in those scripts. Neither controlled Herb RAM dump contains gid 35's opcode address `0x8013E6A6` or opcode-plus-two object pointer `0x8013E6A8` anywhere in its 2 MiB RAM. Both contain the Herb object pointer `0x8013E65E` once, at AOT id 5. Generic AOT commands `0x0D`, `0x12`, and `0x13` can set object fields without running the item's acquisition-bit test; the indexed events use `0x13` only on the id-3 door.
Limits: this excludes gid 35 from the ordinary init and inspected indexed event paths, and it was absent in the two controlled RAM states. A computed pointer, other native code, or a later story path could still enter trailing bytes or alter objects; searching for literal pointers cannot rule those out. The other 12 historical rows follow a first opcode 0 inside conditional control flow, and an earlier branch may skip that terminator. The count is not a list of 13 proven false items. Simply stopping every scan at the first opcode 0 would be wrong; a parser correction must model procedure boundaries and branches. No scanner or item-table code changed in this finding, and full room completion remains Unknown.
History:
- 2026-09-26; human user; supplied the controlled Herb savestates used for the AOT comparison.
- 2026-09-26; Codex subagent `/root/herb_gid35` with model GPT-6 Sol; traced opcode-0 termination, procedure boundaries, AOT id 0, and the initial whole-disc count without repository edits.
- 2026-09-26; Codex with model GPT-6 Sol; independently verified the handler and runner disassembly, RDT lengths, AOT pointer, and 13-row read-only sweep; authored this limited correction.
- 2026-09-27; Codex subagent `/root/native_item_paths` with model GPT-6 Sol; traced the item handler's literal dispatch pointer, ordinary and event call sites, generic AOT handlers, and both controlled RAM pointer searches without a gameplay trigger.
- 2026-09-27; Codex with model GPT-6 Sol; independently checked the sole literal handler pointer in the pinned executable and the absence of gid 35 pointers there; retained the computed-path and future-state limits.

## RE1-SCD-003: branch-aware scan of ordinary room procedures

Status: Confirmed for this revision
Scope: SLUS-00551 executable identity in RE1-FLAG-001; init and main procedures in the 335 RDTs on the pinned disc
Environment: pinned executable disassembly and disc RDTs, 2026-09-26
Authored: 2026-09-26; Codex with model GPT-6 Sol; subagents `/root/scd_control` and `/root/scanner_scope` with model GPT-6 Sol independently traced control flow and table effects
Basis: executable handler inspection, full-disc table rebuild, and focused scanner regression tests
Claim: the ordinary init/main runner treats each nonzero procedure length as including its two-byte prefix and stops at a zero-length sentinel. Opcode `0x00` ends a procedure; IF `0x01` can resume at opcode position plus two plus its skip byte, while ELSE `0x02` jumps from its own position by its skip byte. Scanning both IF outcomes removes two rows from the previous 647-row candidate table: gid 35 at `ROOM1091.RDT` `0x1CAA6` and gid 120 at `ROOM40A0.RDT` `0x392A6`. Both lie after an unconditional terminator with no branch path around it. The regenerated table has 645 item rows; no door rows changed. Rows after a terminator that an IF can skip, including `ROOM10E0.RDT` `0x22B74` and `0x22B98`, remain.
Evidence: opcode-0 handler PS1 VA `0x80044C5C` clears script depth and returns zero; runner `0x800489CC–0x80048AD0` advances by the prefix's length; IF, ELSE, and ENDIF handlers at `0x80044C6C`, `0x80044CC4`, and `0x80044D10` supply the branch behavior. The generated `data/item_table_slus00551.json` was rebuilt from the pinned disc and compared by item and door records with its preceding version. Focused synthetic tests cover termination, branch-skipped termination, ELSE jumps, and malformed targets; the full Python suite passes. Every item and door delta was inspected, with exactly the two removals above.
Limits: this establishes static ordinary-procedure reachability, not current item availability or full room coverage. A separate script entry into trailing bytes is not ruled out. Of 670 init/main chunks, 548 scan cleanly, 120 are partial because opcode sizing or branch targets remain unresolved, and two have bad ranges. Partial chunks retain the previous linear candidates; their apparent absence is not proof. Event scripts and conditional predicates remain unmodeled, so room completion stays Unknown.
History:
- 2026-09-26; Codex subagent `/root/scd_control` with model GPT-6 Sol; traced procedure, IF, ELSE, ENDIF, and opcode-0 handlers and identified the boundary correction without editing the repository.
- 2026-09-26; Codex subagent `/root/scanner_scope` with model GPT-6 Sol; independently audited the two candidate removals, surviving branch-skipped rows, and malformed branch targets without editing the repository.
- 2026-09-26; Codex with model GPT-6 Sol; implemented and tested the conservative scanner, regenerated the full-disc candidate table, and reviewed all row changes.
- 2026-09-26; Claude Opus 4.6 (Thinking); reviewed the supplied code diff for procedure bounds, branch targets, and fallback behavior; did not inspect the disc or reproduce gameplay. Its concrete malformed-length and degenerate-ELSE cases were addressed and tested.
- 2026-09-26; Gemini 3.1 Pro (High); reviewed the supplied code diff for test artifacts and event scanning; did not inspect the disc or reproduce gameplay. Its event-scan regression was addressed.
- 2026-09-26; Gemini 3.8 Flash (High); reviewed the supplied code diff for control flow, event scanning, and unresolved statuses; did not inspect the disc or reproduce gameplay. Its malformed-length and event-scan findings were addressed and tested.

## RE1-PILOT-001: live debug view tracks the Winding Passage Herb

Status: Confirmed for the tested SLUS-00551 Jill states
Scope: Resident Evil Director's Cut USA SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`; Winding Passage Main/Sub 00-09, loaded `ROOM1091.RDT`, Green Herb gid 111
Environment: isolated portable DuckStation 0.1-11894-gc66b2694d on macOS arm64, GDB port 2345, 2026-09-26; donated before and after Herb savestates copied outside Git
Authored: 2026-09-26; Codex with model GPT-6 Sol; subagents `/root/live_profile` and `/root/herb_availability` with model GPT-6 Sol independently checked profile and item evidence
Basis: controlled savestate fixtures, pinned executable and RDT research in RE1-FLAG-001/RE1-VARIANT-002/RE1-AOT-001/RE1-SCD-003, and live GDB reads from both isolated emulator boots
Claim: the live tracker can identify the tested Winding Passage variant and display the Herb as currently available and room state `INCOMPLETE` when its acquisition flag at PS1 VA `0x800C86EA` has mask `0x01` set and AOT id 5 at `0x800B819C` has handler `0x04` plus pointer `0x8013E65E`. The before-pickup boot reported room `00-09`, Items 1, Collected 0, `INCOMPLETE`. The after-pickup boot reported the same room, Items 1, Collected 1, Herb taken, and `UNKNOWN`. The list stays incomplete in both states. A flag set with an inactive or mismatched object, a different character/variant, a changed room during polling, or a failed memory read cannot produce `INCOMPLETE` under this pilot rule. The tracker rereads game-derived state each poll; external visit history is labeled as this tracker session only.
Evidence: `python3 tools/track.py --once` returned the stated outputs after launching the isolated DuckStation with `-nogui -statefile` on the before and after files. Those copies match committed fixtures `tests/fixtures/slus00551_green_herb_before.sav` SHA256 `837ee1d0a752538a4cf7e74b20d3991f0d403015ba19407b2e6f7972e9b67112` and `tests/fixtures/slus00551_green_herb_after.sav` SHA256 `f7fda842f192b453b89c3282abfda72609bd65bbf86df48fd10b3a6f5c7403c9`. A separate GDB experiment confirmed reads still work after issuing `c` to resume emulation, and continuous polling returned the before-state view while running. Five 32-byte runtime windows at PS1 VAs `0x8004484C`, `0x80045F28`, `0x8004897C`, `0x800489A8`, and `0x80091168` match the pinned executable in seven saved RAM captures; their concatenated SHA256 is `23311956abca97ba2522be37f6d45457f4ebbda529ede887a9d0a6d6a2a56958`. The live tracker checks those windows before interpreting room or item bytes. Fixture-backed tests cover both states, reloading the earlier state, a mismatched runtime window, inactive or mismatched item object, character and variant mismatches, read failure, a room transition during one poll, and simulated leave/return to an unmapped room.
Limits: the runtime-window hash identifies the tested executable code regions, not the entire running executable. Availability classification is deliberately limited to this one controlled Herb object; it is not a general AOT rule. The after-pickup state remains `UNKNOWN` because separate entry paths, later story behavior, and full room item coverage are unresolved; RE1-EVENT-002 narrows the indexed event-script concern for this room without closing it. RE1-REENTRY-001 records one later user-operated leave/return check; a normal in-game save/load of this Herb flag remains untested. Chemical-after normal save/load is separately confirmed in RE1-SAVE-001. The two-read room guard cannot detect a room changing away and back between reads. No save-linked visit-history persistence or map UI is implemented.
History:
- 2026-09-25; human user; produced the controlled before/after Herb savestates.
- 2026-09-26; Codex subagent `/root/live_profile` with model GPT-6 Sol; checked confirmed room addresses, Stage 0 variant selection, runtime signature options, and live-loop limits without repository edits.
- 2026-09-26; Codex subagent `/root/herb_availability` with model GPT-6 Sol; checked the exact Herb RDT row, flag, AOT record, and fixture transitions without repository edits.
- 2026-09-26; Codex with model GPT-6 Sol; implemented the limited live profile and debug rule, verified both isolated emulator boots over GDB plus a final before-state live read after review fixes, and recorded the scope and unknowns.
- 2026-09-26; Claude Opus 4.6 (Thinking); reviewed the supplied diff for profile parsing, polling, resource cleanup, and tests without reproducing gameplay. The numeric parsing, configuration diagnostics, reset handling, and test gaps were checked and addressed; its socket-leak finding was based on an older diff and was already fixed.
- 2026-09-26; Gemini 3.1 Pro (High); reviewed the supplied diff for live polling, object matching, and cleanup without reproducing gameplay. Reset handling and pointer-mismatch coverage were addressed; socket cleanup was already present in the final code.
- 2026-09-26; Gemini 3.8 Flash (High); reviewed the supplied diff for CLI execution, profile parsing, transition display, and tests without reproducing gameplay. Transition retry and test gaps were addressed; its missing-entrypoint and socket-leak findings did not apply to the final code.

## RE1-REENTRY-001: the taken Herb flag remains cleared after a reported room return

Status: Candidate
Scope: Resident Evil Director's Cut USA SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`; Jill, Winding Passage Main/Sub 00-09, Green Herb gid 111
Environment: isolated portable DuckStation 0.1-11894-gc66b2694d on macOS arm64, GDB port 2345, 2026-09-27; scratch copy of the user-donated after-Herb savestate from RE1-PILOT-001
Authored: 2026-09-27; Codex with model GPT-6 Sol
Basis: human-operated room exit and return reported by the user, plus live GDB endpoint reads and live tracker output
Claim: after the user reported leaving Winding Passage through a door and returning without loading a savestate, the Herb acquisition byte at PS1 VA `0x800C86EA` was still `0xFE`, with bit 0 clear. The tracker reported room 00-09, Items 1, Collected 1, Herb taken, and completion `UNKNOWN`. This supports persistence across the reported room transition for this one tested playthrough; it does not establish full item coverage or room clearing.
Evidence: before departure, GDB read room bytes at `0x800C8660` as `00 09 01 08`, position x=`22062` at `0x800C5158` and z=`2579` at `0x800C5160`, HP=`102` at `0x800C51AC`, and Herb flag `0xFE`. The user then reported `returned` after the requested door exit and return in the isolated game. After that report, `python3 tools/track.py --once` printed room `00-09`, Items 1, Collected 1, `UNKNOWN`, and Green Herb taken. A separate paused GDB read returned room bytes `00 09 01 08`, x=`24400`, z=`3759`, HP=`102`, Herb flag `0xFE`, and AOT id 5 state `0x00` with pointer `0x8013E65E` at `0x800B819C`. The changed position is consistent with gameplay after the baseline capture. The GDB client resumed emulation after the reads.
Follow-up live comparison: GDB read 32 acquisition-flag bytes from PS1 VA `0x800C86DC`, the first 24 twelve-byte AOT records from `0x800B8160`, and the 1,048-byte loaded event body from `0x80121C00`. Each region matched the corresponding bytes of `/tmp/ram_herb_after.bin` exactly, with SHA256 values `8dc351ad69b1a0bbf1c1b84a599274084481b86ac07796bb69827130d278fe53`, `cd5aa936084c8f42df9b6e1aeedb2c32d273c2d9fcc57a43bb8ac9b5cdd479a2`, and `d12fe0f0940f9b51bdd130df602600c9170c732c2cc37560982e389ae1b7f541`, respectively. Room bytes were stable at `00 09 01 08` across the read. No new active item appeared in those first 24 object records at this endpoint.
Limits: the agent did not capture the intermediate room ID while the user played, and the exact door route was not recorded. The room's previous-room byte was already `08` before departure, so its final value does not independently prove a new transition. This is one human-reported leave/return with instrumented endpoints, not an independently observed transition or a repeatability test. No normal in-game Herb save/load was performed. Room completion remains `UNKNOWN`.
History:
- 2026-09-27; human user; performed the requested room exit and return without a savestate and reported `returned`.
- 2026-09-27; Codex with model GPT-6 Sol; read the pre-departure and post-return GDB endpoints, ran the live tracker after the report, and recorded the limits of the evidence.
- 2026-09-27; Codex with model GPT-6 Sol; compared the post-return acquisition flags, first 24 AOT records, and loaded event body against the controlled after-Herb RAM capture over live GDB.

## RE1-AVAIL-001: three Main Hall item rows are skipped in the captured state

Status: Candidate
Scope: SLUS-00551 executable identity in RE1-FLAG-001; loaded `ROOM1061.RDT`, Training Jill Main Hall Main/Sub 00-06 capture only
Environment: pinned executable disassembly, RDT script bytes, and `/tmp/ram_mainhall.bin`, 2026-09-26
Authored: 2026-09-26; Codex with model GPT-6 Sol; subagent `/root/mainhall_rows` with model GPT-6 Sol traced the three IF blocks
Basis: direct script predicates and executable handlers evaluated against one saved RAM state, without a controlled flag toggle
Claim: in the captured Main Hall state, three opcode `0x18` rows using AOT id 6 are skipped by their enclosing IF blocks. Gid 14 at file `0x2FC5A` requires group 7 bit 13 clear, but the captured word at PS1 VA `0x800C86DC` is `0xBEFFFFFF` with mask `0x00040000` set. Gid 9 at `0x2FCA6` requires group 1 bit 5 clear, but word `0x800C8694` is `0xBC000000` with mask `0x04000000` set. A second gid 9 row at `0x2FCFC` requires group 1 bit 3 clear, but the same word has mask `0x10000000` set. The interpreter therefore skips all three rows in this captured state, even though their acquisition bits are set. This explains the lack of a matching id-6 item object without treating a set acquisition bit as proof of current availability.
Evidence: the three IF commands at file `0x2FC48`, `0x2FC90`, and `0x2FCEE` jump past their respective item rows when their `0x04` tests fail. Opcode-0x04 handler `0x80044D54` maps group 1 to `0x800C8694` and group 7 to `0x800C86DC`; opcode-0x01 handler `0x80044C6C` computes the IF exit. Main Hall RAM SHA256 is in RE1-VARIANT-001. Its AOT id 6 at PS1 VA `0x800B81A8` has state 0 and pointer `0x80156472`, matching none of the three item opcodes; room reset may leave stale pointer bytes (RE1-AOT-001). The RDT init/main scripts match `ROOM1061.RDT` byte for byte in this capture.
Limits: a single saved state and source-derived path calculation have not been checked by toggling each predicate in gameplay. The predicates' story meaning and when the items may become available remain unknown. Later event scripts may create or replace AOT id 6. This finding does not prove room clearance or justify filtering the item rows from the static table.
History:
- 2026-09-25; human user; played; produced the Main Hall state later used for this comparison.
- 2026-09-26; Codex subagent `/root/mainhall_rows` with model GPT-6 Sol; traced three script IF blocks and evaluated their predicates against saved RAM without new gameplay.
- 2026-09-26; Codex with model GPT-6 Sol; independently checked the five referenced flag masks and saved word values, then authored this Candidate availability conclusion.

## RE1-PILOT-002: live debug view names the conditional Chemical

Status: Confirmed for the tested SLUS-00551 Jill Chemical states
Scope: Resident Evil Director's Cut USA SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`; Mansion Storeroom Main/Sub 00-18, `ROOM1180.RDT`, Chemical gid 13
Environment: isolated portable DuckStation 0.1-11894-gc66b2694d on macOS arm64, GDB port 2345, 2026-09-27; controlled before and after Chemical savestates
Authored: 2026-09-27; Codex with model GPT-6 Sol
Basis: controlled savestate pair, prior script/flag/object findings RE1-SPAWN-001, RE1-FLAG-001 and RE1-AOT-001, fixture-backed polling tests, and live GDB reads from both isolated emulator boots
Claim: for the tested Jill room variant, the live tracker names the Chemical only when group-5 branch byte at PS1 VA `0x800C3006` has mask `0x02` clear. With the acquisition bit at `0x800C86DE` mask `0x04` set and AOT id 1 at `0x800B816C` holding handler `0x04` and opcode-plus-two pointer `0x80121E94`, the before-pickup boot displayed Chemical available, Items 1, Collected 0, and `INCOMPLETE`. The after-pickup boot displayed Chemical taken, Items 1, Collected 1, and `UNKNOWN`. The item list is explicitly incomplete in both states. When the branch bit is set, the tracker leaves item identity and completion unknown because the same room script can select Broken Shotgun instead.
Evidence: isolated `./DuckStation -nogui -statefile /private/tmp/re-map-duckstation-eyr2yxx9/chemical_before.sav` followed by `python3 tools/track.py --once` returned the before view above. Repeating with `chemical_after.sav` returned the after view. The copied savestates correspond to committed `tests/fixtures/slus00551_chemical_before.sav` SHA256 `5eeef607419e49ab3b36be49363c601d63523410a68755dabef0a15dcf178f2b` and `tests/fixtures/slus00551_chemical_after.sav` SHA256 `b5de7d17f76a6f2812c3761008f118d0d35e165d655dd24d737fb104e344085b`. Fixture tests additionally flip the branch bit in both states, suppressing the Chemical name and counts; test an inactive object, a failed branch read, and confirm the existing Herb pilot and room-transition behavior. The full Python suite passed, 36 tests, with one pre-existing fake-GDB-server thread warning. RE1-SAVE-001 separately records Chemical-after normal save/load persistence.
Limits: only the Chemical branch has a controlled pickup pair and live boot check; the Broken Shotgun branch was not played or classified. Flipping a bit in a fixture tests the tracker's conservative response, not the game's alternate spawn. The active object check is specific to this row and does not prove general availability. Full relevant item coverage and future story changes remain unresolved, so the room cannot be marked cleared. The runtime signature checks five code windows rather than the whole executable. No map UI or save-linked visit persistence is implemented.
History:
- 2026-09-26; human user; played and supplied the controlled before and after Chemical savestates and performed the normal Chemical-after save/load described in RE1-SAVE-001.
- 2026-09-27; Codex with model GPT-6 Sol; added the profile branch predicate and named live pilot, ran fixture-backed tests and both isolated live boots, and recorded the boundaries of the result.
- 2026-09-27; Claude Opus 4.6 (Thinking); reviewed the supplied code diff for branch checks and test isolation without running gameplay. Its confounded read-failure test finding was addressed.
- 2026-09-27; Gemini 3.1 Pro (High); reviewed the supplied code diff for profile parsing and debug wording without running gameplay. Its silent legacy-key and misleading branch-message findings were addressed.
- 2026-09-27; Gemini 3.8 Flash (High); reviewed the supplied code diff for profile parsing, scenario selection, and tests without running gameplay. Its decimal-versus-hex room ID and confounded test findings were addressed.

## RE1-COVER-001: tested Chemical branch reaches one normal item row

Status: Confirmed for the tested SLUS-00551 Jill captures and loaded script paths
Scope: Resident Evil Director's Cut USA SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`; Mansion Storeroom Main/Sub 00-18, `ROOM1180.RDT`, controlled Chemical before/after states
Environment: DuckStation 0.1-11894-gc66b2694d savestate RAM captures; read-only RDT and RAM inspection on 2026-09-27
Authored: 2026-09-27; Codex with model GPT-6 Sol; subagents `/root/chemical_scripts` and `/root/chemical_runtime` with model GPT-6 Sol independently checked script paths and runtime objects
Basis: exact loaded-script comparison, branch-aware opcode walk, and bounded AOT records in both controlled captures
Claim: both captures load `ROOM1180.RDT` init `0x270..0x320`, main `0x320..0x350`, and event `0x350..0x354` byte for byte. Init scans cleanly and has two mutually exclusive opcode-`0x18` rows: Chemical gid 13 at `0x292` and Broken Shotgun gid 48 at `0x2AE`, both AOT id 1. The tested group-5 branch bit at PS1 VA `0x800C3006` mask `0x02` is clear, so the Chemical row executes and the ELSE skips Broken Shotgun. Init also has three generic opcode-`0x0D` AOT rows for ids 2–4; their handlers are 2, 8, and 16 in both captures, and their collectible roles are not fully classified. Main scans cleanly, has no opcode-`0x18` row, and its four opcode-`0x13` updates target AOT id 2. Those updates change its mode byte while leaving handler 2 intact; id 2's first two bytes are `02 00` before and `02 81` after the controlled pickup. The event section is a zero dword, with no indexed event entry. The dynamic interaction bound at PS1 VA `0x800B7ED8` is `0x800B8190`, inclusive through AOT id 4. In these captures, id 1 is the sole active ordinary item handler before pickup; its state changes `0x04→0x00` afterward while pointer `0x80121E94` remains, matching the Chemical opcode plus two. No other state-4, state-13, or state-15 handler appears within that bound in either capture.
Evidence: extracted `ROOM1180.RDT` SHA256 `7a3b57eb01a2b3ac445090128555feb21ba39a38680d3381265e8fa54401be40`. RAM captures `/tmp/ram_chem_before.bin` SHA256 `bb9110536a02122d7c6a14d489b2e94e7d8224d8ccf297d617694c4eb6e804f2` and `/tmp/ram_chem_after.bin` SHA256 `0d5e7dc6e450a99b9f8a354cc9ffd30e97dd3129427600e384681903330935df` match all three RDT sections at loaded RAM base `0x80121C00`. `tools/scan_scd.py` reports init `clean/10` and main `clean/14`, with item rows at `0x292` and `0x2AE` only. The before/after AOT id-0..4 handler bytes are `01 04 02 08 10` and `01 00 02 08 10`; their opcode pointers map to init offsets `0x272`, `0x292`, `0x2C8`, `0x2DA`, and `0x2EC`, each plus two. Acquisition byte at `0x800C86DE` changes `0xFF→0xFB`. RE1-SPAWN-001 verifies the condition handler; RE1-AOT-002 verifies the interaction bound.
Direct id-2 path check: opcode-`0x0D` handler `0x80045E00..0x80045EA4` copies the generic object fields without testing an acquisition bit, and opcode-`0x13` handler `0x80045C38..0x80045C84` rewrites its handler/mode bytes. The main script leaves handler 2 in place and selects mode `0x00` before or `0x81` after Chemical pickup, matching AOT id-2 bytes `02 00` and `02 81`. Mode `0x81` passes the inspected interaction-mode check at `0x80038AC4..0x80038ADC`. Dispatch-table entry `0x8009040C` points to handler `0x80037AF0`, which reads the record's message/control halfwords and calls `0x80035278`. That callee writes text/control state and has no call to the item pickup routine or inventory write. This establishes that the direct id-2 handler does not itself grant a normal item; it does not test the player's interaction or downstream state changes.
Direct id-3/id-4 path check: dispatch-table entries for handlers 8 and 16 point to `0x80037EF8` and `0x800385FC`. Handler 8 gates on input and game state, sets control byte `0x800C8457`, and calls `0x80051E38` to open another interaction; its direct path has no acquisition-flag clear or inventory addition. Its in-game purpose and indirect effects were not observed. Handler 16 calls `0x8002CCB8` with item type `0x2F`, which searches inventory slots for an Ink Ribbon; the user previously saved at this room's typewriter, consistent with this interaction. These direct handlers do not instantiate a normal item row, but the absence of a controlled activation limits the conclusion.
Branch-writer scan: the pinned executable's opcode-`0x05` handler at `0x80044E54..0x80044FA0` writes group/index flags, including the group-5 bit used here. A read-only walk of all 335 disc RDT files found 208 decoded opcode-`0x04` tests of group 5 index `0x2E`, but no decoded opcode-`0x05` write to that group/index in ordinary init/main sections. Of 668 valid sections, 548 decoded cleanly and 120 were partial. This is a bounded negative result, not evidence that the bit never changes: the partial sections, indexed events, and native code were not exhaustively checked for writers.
Limits: this covers ordinary opcode-`0x18` paths in the loaded RDT and active handlers in two captured endpoints. Opcode `0x0D` instantiates generic AOT objects without testing an acquisition flag; downstream behavior of those objects has not been played, and native grants are not ruled out. The meaning and future transitions of the branch bit, later story behavior, and alternate room variants remain untested. Absence of another ordinary item handler at these endpoints does not prove the complete relevant item list. The tracker must retain `UNKNOWN` after Chemical pickup; this finding does not authorize a `Cleared` rule.
History:
- 2026-09-26; human user; played and supplied the controlled Chemical before/after savestates.
- 2026-09-27; Codex subagent `/root/chemical_scripts` with model GPT-6 Sol; inspected the mutually exclusive init branches, main updates, and empty event table without editing files or triggering gameplay.
- 2026-09-27; Codex subagent `/root/chemical_runtime` with model GPT-6 Sol; compared all loaded script sections and bounded AOT states against both captures without editing files or triggering gameplay.
- 2026-09-27; Codex with model GPT-6 Sol; independently reproduced RDT hashes, script-byte equality, branch opcode rows, AOT states and pointers, and retained the completion limit.
- 2026-09-27; Codex subagent `/root/chemical_scripts` with model GPT-6 Sol; traced the id-2 mode change and direct handler path, corrected an earlier handler-versus-mode interpretation, and did not trigger gameplay.
- 2026-09-27; Codex with model GPT-6 Sol; checked the id-2 before/after record bytes, dispatch-table pointer, and message/control handler disassembly.
- 2026-09-27; Codex subagent `/root/chemical_runtime` with model GPT-6 Sol; traced id-3/id-4 direct handler paths and checked them against the controlled AOT records without triggering gameplay.
- 2026-09-27; Codex with model GPT-6 Sol; verified the handler-8/16 dispatch pointers, direct instruction paths, and inventory-search call in the pinned executable.
- 2026-09-27; Codex with model GPT-6 Sol; traced the opcode-`0x05` writer and ran a read-only full-disc ordinary-script scan for writes to the Chemical branch bit, retaining the partial-script and event limits.

## Suggested next experiments

1. Enable `Debug/EnableGDBServer` with port 2345, connect with a small Python GDB client, and read 16 bytes at `0x80000000` while the game idles. Record whether the game keeps running.
2. Move between two known RE1 rooms and poll a small candidate window at 10 Hz. Save the log with game revision and DuckStation version.
3. Take `.sav` files before and after one pickup, decompress with the header logic above, and diff for stable changed bytes.
4. Only if GDB polling fails, prototype Mach `vm_read` against the DuckStation PID for the same addresses and compare maintainability.
