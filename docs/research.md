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
- 2026-10-06; Codex root, GPT-6.1 Sol; added controlled acceptance, decline, room reentry and savestate reversal evidence in RE1-PICKUP-004. The original uncontrolled comparison and its authorship remain as recorded.

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
Limits: topology only, no geometry or draw order. Camera variant files fold into base rooms by number. Other stages were unmapped in this finding; RE1-STAGE-001 later adds a source-derived candidate folder link without gameplay validation.
History:
- 2026-09-25; opencode with model opencode/muse-spark-1.3-contributor-free; authored; static build only, still Candidate.
- 2026-09-27; Codex with model GPT-6 Sol; linked the later candidate folder-selection finding RE1-STAGE-001 without changing this Mansion 1F topology claim.

## RE1-STAGE-001: room-file folder selector for base and alternate areas

Status: Candidate for unplayed areas; executable rule checked for the named revision
Scope: Resident Evil Director's Cut USA SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`; runtime Main 0–6, room-file folders STAGE1–E
Environment: pinned PS-X executable disassembly and generated SLUS-00551 RDT table, 2026-09-27; only runtime Main 0 has loaded-room file matches in RE1-VARIANT-002
Authored: 2026-09-27; Codex with model GPT-6 Sol; subagent `/root/topology_audit` with model GPT-6 Sol found the selector and catalog correspondence
Basis: executable disassembly and static disc-file/door metadata; no new gameplay outside Main 0
Claim: the room-file selector at PS1 VA `0x80043FB4..0x80044134` reads runtime Main byte `0x800C8660`. It normally returns that value, 0–6. When word `0x800C3004` has mask `0x00020000` set, it compares Sub byte `0x800C8661` against nine whitelist slots for that Main copied from PS1 VA `0x80010670`; a match returns Main+7. Caller `0x80044870` uses the returned index for its room-file ID and variant tables at `0x80090BC8` and `0x80090F48`. The seven whitelist sets exactly match the Sub IDs present in the sparse STAGE8–E folders, paired with base STAGE1–7. The mask is the same byte `0x800C3006` bit `0x02` that selects the alternate Storeroom item row in RE1-BRANCH-001. This establishes an executable-level reason that folder number alone cannot identify a runtime room; the branch flag can select an alternate file while Main/Sub remain the same.
Evidence: the PS-X executable header loads at `0x80010000`, so whitelist VA `0x80010670` is file offset `0xE70`. Its seven nine-byte rows contain 8, 5, 2, 3, 4, 9, and 7 non-`0xFF` room IDs; each row equals the collapsed Sub set in its paired STAGE8–E folder in `data/item_table_slus00551.json`. Instructions `0x800440A4..0x80044130` test the flag, index the nine-byte rows, compare Sub, and return Main or Main+7. The loader call and table indexing are at `0x80044870..0x8004489C`. Independently recounting the generated table yields 335 RDT files but 160 base `(Main,Sub)` candidates after suffix variants collapse; all sparse-folder Sub IDs overlay base-room IDs. Treating door target-stage zero as same Main and nonzero 1–7 as target Main 0–6 gives 343 distinct directed links from base folders. The 96 distinct sparse-folder links add no new logical edge. Eight base links target seven `(Main,Sub)` IDs without a corresponding RDT file, so those targets remain unresolved.
Limits: gameplay has matched loaded RDT files to runtime Main 0 only. The selector's executable rule does not validate room traversal, door availability, labels, geometry, or completion for Main 1–6. Door target-stage normalization and the 160-room graph are static candidate interpretations; script decoding is incomplete in some RDTs. The alternate branch has no natural gameplay capture in this environment, and file suffix selection has separate rules in RE1-VARIANT-002. Do not promote a full-game live map solely from these counts.
History:
- 2026-09-27; Codex subagent `/root/topology_audit` with model GPT-6 Sol; traced the selector and compared all seven whitelist rows with sparse room folders, without editing files or testing gameplay.
- 2026-09-27; Codex with model GPT-6 Sol; independently checked the executable hash, selector and caller disassembly, whitelist bytes at file offset `0xE70`, seven exact folder-set matches, and base/alternate node and edge counts.

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

Status: Superseded in part by RE1-SCD-004: the gid-35 row is object payload, not a command after termination; the recorded runtime absence remains evidence
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
- 2026-09-29; Codex subagent `/root/remake_doors`, model GPT-6.1 Sol; revised the decoding basis in RE1-SCD-004: correcting opcode `0x1F` to 28 bytes places `0x1CA94` and `0x1CAA6` inside a 22-byte opcode `0x1B`, with the real procedure terminator at `0x1CAC6`. The gid-35 absence is unchanged, but the earlier termination explanation was wrong.

## RE1-SCD-003: branch-aware scan of ordinary room procedures

Status: Superseded in part by RE1-SCD-004: procedure control flow is retained; the gid-120 exclusion and historical opcode-0 interpretations were incorrect
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
- 2026-09-29; Codex subagent `/root/remake_doors`, model GPT-6.1 Sol; corrected opcode `0x1F` width and regenerated metadata in RE1-SCD-004. Gid 120 in `ROOM40A0` is reachable and restored; the earlier apparent terminator was misaligned object payload. Gid 35 in `ROOM1091` remains excluded because it is entity payload.

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

## RE1-BRANCH-001: normal load can set the Storeroom item branch bit

Status: Confirmed for the named SLUS-00551 executable's normal-load code; alternate gameplay untested
Scope: Resident Evil Director's Cut USA SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`; group-5 index `0x2E` at PS1 VA `0x800C3006` mask `0x02`, tested Jill Chemical states
Environment: pinned PS1 executable disassembly, 19 full 2 MiB RAM files with 14 unique hashes, committed Chemical savestates, and isolated normal Chemical-after memory card, 2026-09-27
Authored: 2026-09-27; Codex with model GPT-6 Sol; subagents `/root/chemical_scripts` and `/root/chemical_runtime` with model GPT-6 Sol independently traced the code and classified RAM states
Basis: executable load/setup branches, exact RDT byte scan, runtime-signature-matched RAM reads, and one normal-save payload
Claim: the normal in-game load path copies save payload into PS1 RAM starting at `0x800C8660`, then calls `0x80019638` at `0x80018B08`. That routine reads saved byte `0x800C8693`. If it is 2, instructions `0x80019688..0x800196A0` OR `0x00020000` into word `0x800C3004`; if it is 3, `0x800196AC..0x800196CC` OR that bit and `0x00010000`. The `0x00020000` word mask is byte `0x800C3006` mask `0x02`, which chooses the alternate Broken Shotgun row in `ROOM1180.RDT` (RE1-SPAWN-001). A value of 1 instead follows a separate branch that ORs `0x00040000`; it does not set the Broken Shotgun selection bit. A setup/reset routine at `0x800294B0` masks the same word with `0x20080000` at `0x80029560..0x80029570`, clearing the selection bit when that routine runs. Another setup path at `0x80029878..0x800298E4` reads the selection bit to assign byte `0x800C8693` as 2 or 3; this path does not set the bit. These code paths show a concrete load-time writer, so the branch bit is not immutable and cannot be identified solely from the player's character byte.
Evidence: `SLUS_005.51` SHA256 above; the reverse-copy and call instructions are at `0x80018AE0..0x80018B0C`. All 19 available full RAM files match the profile's five-window runtime SHA256 `23311956abca97ba2522be37f6d45457f4ebbda529ede887a9d0a6d6a2a56958`; 14 unique hashes remain after aliases. Every one has the selection bit clear. The two controlled Chemical RAM images have character byte `0x800C8669=1`, saved byte `0x800C8693=1`, word `0x800C3004=0x20040000`, and Chemical flag `0x800C86DE` `0xFF→0xFB`. The isolated normal Chemical-after card SHA256 `7323a3259f9d77e11a3ebae3f1985fff07f80a3aab8c0ff39bfb8ecaeeaa1c87` contains the saved byte value 1 at file offset `0x2233`, matching the saved RAM block mapping in RE1-SAVE-002. A byte-exact scan of all 335 disc RDTs, 125,328,072 bytes, found zero `05 05 2E 00`, `05 05 2E 01`, or `05 05 2E 02` sequences for direct opcode-`0x05` set/clear/toggle commands; RE1-COVER-001 separately records the narrower decoded-script scan.
Limits: no available natural RAM capture has saved byte 2 or 3 or the selection bit set. The only character-byte-0 image has no matching loaded room RDT and cannot validate Chris gameplay; its provenance is unknown. The user-supplied Chemical fixtures are real gameplay captures, whereas tests that flip the selection bit are synthetic. The exact menu or story meaning of saved values 2 and 3, the callers of the setup/reset routine, other possible native/indirect writers, and a played Broken Shotgun branch remain unverified. The normal-load adjustment only sets the selection bit for values 2 and 3; it does not clear it for values 0 or 1. Loading an earlier value-0/1 save after a value-2/3 session may depend on a separate reset path, which has not been traced or tested. The code proves what it would write for values 2 and 3, not that such a save has been loaded in this environment. Room completion stays `UNKNOWN` after Chemical pickup.
History:
- 2026-09-26; human user; supplied the controlled Chemical savestates and performed the isolated Chemical-after normal save/load in RE1-SAVE-001.
- 2026-09-27; Codex subagent `/root/chemical_runtime` with model GPT-6 Sol; inventoried 19 full RAM files, distinguished 14 unique matching captures, and excluded the character-byte-0 image from gameplay-branch evidence.
- 2026-09-27; Codex subagent `/root/chemical_scripts` with model GPT-6 Sol; found and traced the load-time setter and setup/reset masks in the pinned executable without editing files or triggering gameplay.
- 2026-09-27; Codex with model GPT-6 Sol; independently checked the executable branch instructions, saved-byte and flag values in RAM, isolated card byte and hash, and byte-exact full-disc absence of direct opcode-`0x05` writes.

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

## RE1-DOORS-002: active Door_set records expose directional lock state

Status: Candidate for gameplay lock interpretation and persistence; executable paths and offline fixture decoding reproduced
Scope: Resident Evil Director's Cut USA SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`; controlled Jill Herb and Chemical RAM captures, no new gameplay
Environment: DuckStation `0.1-11894-gc66b2694d` fixtures; macOS arm64, Homebrew LLVM executable disassembly and disc metadata inspection, 2026-09-29
Authored: 2026-09-29; Codex subagent `/root/remake_doors`, model GPT-6.1 Sol
Basis: pinned executable inspection, active AOT records in four existing RAM fixtures, and static RDT door metadata
Claim: Door_set opcode `0x0C` creates handler-1 AOT records with an opcode-plus-two pointer. Original opcode byte 14 packs a separate player-state gate in bit `0x40`, a persistent lock selector in bit `0x80`, and a six-bit unlock index. With the lock selector set, a set indexed bit means unlocked. Original byte 24 selects a normal required item or a special unlock path. An item held in inventory does not itself make the persistent unlock bit set, and a reciprocal door can have different behavior.

Evidence:
- SCD dispatch entry PS1 VA `0x80091138` points to `0x80045EA8`. This initializer raises the bound at `0x800B7ED8`, writes handler 1 at `0x800B8160 + 12*id`, copies original byte 25 as mode, and stores opcode-plus-two at record offset 8. State dispatch entry `0x80090408` points to door interaction handler `0x8003789C`. These records use the same bounds and pointer cautions as RE1-AOT-001/002.
- At `0x80037904..0x80037924`, the interaction reads original byte 14, bypasses ordinary locks when bit `0x80` is clear, and otherwise tests `g = byte14 & 63` at base PS1 VA `0x800C86B4` through helper `0x800489A8`. The 32-bit little-endian word is `base + 4*(g//32)` with mask `0x80000000 >> (g%32)`. For byte reads, the RAM offset is `0xC86B4 + 4*(g//32) + 3 - ((g%32)//8)` with mask `0x80 >> (g%8)`. A nonzero result takes the door path. The successful unlock path at `0x80037A44..0x80037A58` sets the same bit through `0x80048954` and returns before traversal. The flag range is inside the normal game-state save copy in RE1-SAVE-002; no door save/load experiment was performed.
- The preceding gate at `0x800378D0..0x800378F8` blocks byte-14 bit-`0x40` doors when PS1 byte `0x800C5125 & 3` equals 3, even if the ordinary lock bit is set. Original byte 24 equal to `0xFE` bypasses inventory, queues message `0xD4` and event category 2/index `0x21`, then sets the bit. Value `0xFF` follows the missing-key path without setting it. Reciprocal static rows `00-03→00-04` and `00-04→00-03` share lock selector `0x92`, respectively types `0xFE` and `0xFF`, and use RAM byte `0xC86B5` mask `0x20`. The `00-0A↔00-0B` pair similarly shares selector `0x94`, byte `0xC86B5` mask `0x08`.
- Type `0x33` has a prior special path when `0x800C5125 & 3` equals 1. It tests base `0x800C8700`, index 124, equivalent RAM byte `0xC870C` mask `0x08`, and unlocks without the ordinary inventory search if set. Otherwise it follows a missing-key path. Both before fixture types have `0xC5125=1` and `0xC870C=8`. Other ordinary types call `0x8002CCB8`, which searches the count at `0x800C8667` and the array pointer at `0x800BA008`; that check happens after the unset unlock-bit test. Type 0 with a lock selector appears in puzzle/script doors and must not produce a key label "Nothing".
- Both Herb fixtures in room `00-09` have five active mode-`0x81` doors. Id 1 points to `0x8013E5F6`, matching loaded `ROOM1091.RDT` offset `0x1C9F4` plus base `0x80121C00` plus two. Its target is `00-14`, selector `0xC4`, type `0x34`, and RAM `0xC86B7` mask `0x08` is clear, so the decoder reports Locked. Ids 0, 2, 3, and 4 target `00-08`, `00-13`, `00-15`, and `00-0A` and bypass the ordinary lock; the separate `0x40` gate does not block the captured state. Both Chemical fixtures have one active door, id 0 to `00-0B`, pointer `0x80121E74`, matching `ROOM1180.RDT` offset `0x272` plus the loaded base plus two, with no ordinary lock. These are decoded fixture results, not observations of each door opening.
- Fixture SHA256s are Herb-before `d819fbd41abea6537bf9ce9f4967b479ea1f6278024b9f4e018290343c0bc8d4`, Herb-after `0130861a3a27d2810ccbd0d1e2e7bbc42c64abdac130e1d43dd71ed646784704`, Chemical-before `bb9110536a02122d7c6a14d489b2e94e7d8224d8ccf297d617694c4eb6e804f2`, and Chemical-after `0d5e7dc6e450a99b9f8a354cc9ffd30e97dd3129427600e384681903330935df`. Local metadata experiment `/tmp/tasks/re-map/doors/metadata.py` expands all 782 existing door rows in 335 disc RDTs without changing any original ID, offset, or target. Its `metadata.json` SHA256 is `61b30c29b29c223ab1f664f73f45105de10f720eaa1940088a0bdfbf02152256`; offline `fixtures.py` reproduces the AOT matches and emits `fixtures.json` SHA256 `85ff6ef7ab9651520d74c20d8455ec4b19de3296e69b0008de836a07808f327d`. All artifacts remain outside Git.
- [Reevengi's field layout](https://github.com/pmandin/reevengi/blob/8130d5fd029a7548135bdbbff19b0b8e338bd42d/src/g_re1/scd1.xml#L167-L186) and the [Biohazard-utils reader](https://github.com/biorand/biohazard-utils/blob/5d0d523cc0e228b5c9eea269149853cda5f266bd/src/IntelOrca.Biohazard/Script/Opcodes/DoorAotSeOpcode.cs#L44-L78) are field-naming leads. [Biorand item metadata](https://github.com/biorand/classic/blob/6d0568609cdd537a503e501d67d3cd88d3d21605/IntelOrca.Biohazard.BioRand/RE1/Re1ItemIds.cs#L55-L64) names type `0x34` Armor Key; the name is external metadata, not a runtime string observation. Its [other-side unlock patch](https://github.com/biorand/classic/blob/6d0568609cdd537a503e501d67d3cd88d3d21605/IntelOrca.Biohazard.BioRand/RE1/Re1DoorHelper.cs#L155-L177) uses type 254 consistently with the inspected PS1 path, but targets the PC game.

Limits: no controlled door unlock pair, normal save/load door check, savestate reversal door check, or alternate character/revision was played. Active AOT mode, geometry, and the transient global interaction gate at `0x800C3000` also affect whether an interaction can run. Story scripts can replace AOT records and special puzzle behavior needs separate interpretation. The existing table omits event-section doors and has partial script scans. Static destination decoding also needs the existing stage/story adjustments outside Mansion 1F. Never infer an unlocked door merely because both rooms were visited.
History:
- 2026-09-29; Codex subagent `/root/remake_doors`, model GPT-6.1 Sol; inspected and implemented; checked the pinned executable paths, regenerated door metadata outside Git, matched four existing RAM fixtures, and added a pure decoder with fixture and synthetic flag-reversal tests. No game control or memory writes.
- 2026-10-02; Codex root, GPT-6.1 Sol; rechecked callback 1 and its helper chain for RE1-SCD-015. The earlier description of `0x80051E38` as event scheduling is superseded by the direct audio audit there. Original authorship and gameplay limits remain unchanged.


## RE1-MAP-002: numeric Mansion 1F floor plan from indexed room regions

Status: Candidate for live map behavior; pinned disc encoding and executable calculations checked statically
Scope: Resident Evil Director's Cut USA SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`; `PSX/ITEM_M2/MAP01.TIM`, runtime Main 0
Environment: owned MODE2/2352 disc, pinned PS-X executable and generated RDT metadata, 2026-09-29; no emulator connection or gameplay in this experiment
Authored: 2026-09-29; Codex subagent `/root/remake_geometry`; model GPT-6.1 Sol
Basis: direct disc-byte decoding, pinned executable disassembly, exact contour area checks, and comparison with all Mansion same-floor RDT door targets
Claim: the classic game's Mansion 1F map encodes 32 independently indexed architectural regions and 56 region-owned half-door markers. Palette floor index is `16 + 6*region`, with the neighboring group entries carrying floor detail and door marks. Tracing room-mask cell edges yields 32 connected outer polygons and no holes for this particular map. Pairing each half marker with its unique different-room counterpart exactly 1.5 pixels away yields 28 physical doors. All 54 directed same-floor Mansion RDT links in the committed table correspond to those physical pairs. Two additional reverse directions, `10→04` and `19→0A`, have no source RDT file in STAGE1. The generated artifact stores only numeric outlines, labels, door segments, IDs and evidence metadata, with no texture pixels, palette colors or original image.

Evidence:

- `PSX/ITEM_M2/MAP01.TIM` is at LBA 11780, 29216 bytes, SHA256 `0385b147fe2a698e7ece61e82a8cfa704bfc4903b1afc884afed5955602da20f`. Its little-endian TIM header has magic 16, flags 9, one 256-color CLUT of 524 bytes, then a 28684-byte image block. Image dimensions are 128 16-bit words by 112 rows, so 256 indexed pixels by 112 rows. The extracted floor bounds are X `[1,158)`, Y `[1,93)`.
- The pinned executable's map file-ID table at PS1 VA `0x8008EB80` begins `0x00DC`. Internal file record 220 at `0x80091F68 + 12*220` contains `(LBA=11780, size=29216, 4096)`, identifying MAP01. Routine `0x80032B2C..0x80032CA0` loads the map and advances its CLUT cursor by `0xC` bytes per region, or six 16-bit entries, while evaluating the region's visit flag. At `0x80032E84..0x80032E98`, it multiplies the selected region by six, adds `0x10`, and uses that as the palette entry for the flashing current-region color.
- Numeric regions give a coherent architectural layout: Main Hall `06` spans X60..100, Y58..93; Art Room `07` is east of it; Winding Passage `09` is north of L Passage `08`; the Mansion Storeroom `18` is east of East Stairway `0B`. Every region is one connected floor component. Collinear edge collapse preserves the exact encoded area. The tool rejects ambiguous contours and unpaired half markers instead of inventing geometry.
- `data/mansion1f_floor_plan.json` contains the numeric result. `python3 tools/build_floor_plan.py <owned CUE> <output JSON>` verifies both map and executable identities, then reproduces the committed JSON byte for byte. `tests/test_floor_plan.py` covers a hole, floor-area preservation, labels on real floor cells, owned door pairs and wall orientation, malformed files, unpaired markers, marker-without-floor failure, and the 54-link RDT comparison. Eight tests passed, plus Ruff lint and format checks.
- [Mortician's TIM parser](https://github.com/mortician/lib_bio/blob/ee30311756f213f60e0d885d9c2eef668ccb53e9/lib_bio/lib_tim.py#L113-L123), commit `ee30311756f213f60e0d885d9c2eef668ccb53e9`, provided an independent format lead for indexed TIM widths; the dimensions and blocks above were checked against the owned file.

Region selection limits:

- The map region normally retains runtime Sub, but the pinned selector first copies Sub into map-state byte `0x800B7F87` at `0x80033730..0x8003374C` and applies exceptions afterward. At `0x80033798..0x800337F8`, Sub07 with camera3..6 selects region1D, while Sub0F with camera3..4 selects region1E. These are embedded secret spaces in the Art Room and Bar. Revealing them merely because the parent logical room was visited would violate entry-only disclosure.
- Sub10 with camera0 selects map selector2, region1E at `0x800337FC..0x80033838`, rather than this Mansion 1F plan. Region1F's runtime identity has not been traced. The 32 drawn regions therefore are not 32 independent RDT room files.
- No map-screen gameplay was performed. Current-region flashing, the camera exceptions, visit-bit interpretation, door-lock states, door availability, transitions and earlier-save reversal were not newly validated. No game-world-to-map coordinate transform was established, so player or item coordinates cannot be plotted by simply scaling RDT positions into these polygons. This finding does not establish item coverage or room completion.

Rejected geometry shortcut: RDT camera records with `to=9` are per-camera boundary quadrilaterals, not a global architectural plan. Their large overlapping room-local regions and collision rectangles do not establish a coherent Mansion floor plan. [Reevengi's boundary layout](https://github.com/pmandin/reevengi/blob/8130d5fd029a7548135bdbbff19b0b8e338bd42d/src/g_re1/rdt_rvd.h#L26-L43) and [collision implementation](https://github.com/pmandin/reevengi/blob/8130d5fd029a7548135bdbbff19b0b8e338bd42d/src/g_re1/rdt_sca.c#L36-L51), commit `8130d5fd029a7548135bdbbff19b0b8e338bd42d`, were inspected as leads; obstacle-box union was not used as a room outline.

History:
- 2026-09-29; Codex subagent `/root/remake_geometry`, model GPT-6.1 Sol; extracted local map metadata, traced the executable palette and selector routines, implemented the extraction tool, and ran eight focused tests without connecting to the emulator.


## RE1-COVER-002: bounded registered room pickups and deferred awards

Status: Candidate for general room availability and completeness; controlled Herb/Chemical record classification reproduced
Scope: Resident Evil Director's Cut USA SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`; normal inventory pickups and map pickups in the loaded room, excluding documents and end-of-game inventory rewards
Environment: read-only inspection of the pinned PS1 executable and local disc RDT files; four existing 2 MiB controlled RAM captures; Python 3.14.7 and Capstone 5.0.9; no new emulator interaction by this author
Authored: 2026-09-29; Codex subagent `/root/remake_items` with model GPT-6.1 Sol
Basis: pinned executable disassembly, loaded descriptor comparisons, controlled before/after captures, and synthetic failure tests
Claim: the currently registered AOT table exposes the descriptor used by the normal pickup and map award paths. This permits named current-room items and current completion without inferring availability from every static item row. The reader must retain a pending award after its handler is disabled, reject active unsupported descriptors, and exclude stale inactive pointers from earlier rooms. General availability remains a source-derived rule, with the runtime checks below covering the controlled Herb and Chemical pairs.

Evidence:

- AOT records start at PS1 VA `0x800B8160`. The inclusive high-water pointer is a little-endian u32 at `0x800B7ED8`. Each 12-byte record is `<BBHHHI`: handler, mode, parameter, model, GlobalId, and source pointer. Opcode `0x18` at `0x80045F28..0x80046048` masks its slot ID to seven bits, sets handler 4 for inventory items, 15 for maps, or 13 for documents when the acquisition flag remains set, then stores `opcode address + 2` as its pointer. It also masks the source parameter at byte 24 to bit 0 before copying it into the record. Generic opcode `0x0D` at `0x80045E00..0x80045EA4` copies the handler and fields from its 18-byte source. Its slot ID is not masked.
- The reset at `0x80044C20..0x80044C50` clears only byte 0 of 24 records. Other bytes can retain a previous room's descriptor, as RE1-AOT-001 observed. The item initializer technically accepts 128 slot indices. The runtime reader therefore uses the profile's explicit 24-record bound for this revision and reports an error if the live high-water pointer exceeds it, rather than scanning adjacent state.
- The loaded RDT pointer is a u32 at `0x800CAB10`. Header offsets `0x60`, `0x64`, `0x68`, and `0x6C` hold relocated init, main, event start, and event end pointers. The reader requires ordered pointers inside configured PS1 RAM and validates each active source against this loaded script span, its creation opcode, and its slot ID. It returns active opcode-`0x0C` doors separately. Generic handler-1 sources have no implemented door decoder and cause an explicit error.
- Ordinary handler 4 at `0x80037B80..0x80037BB0` puts the selected record in u32 `0x800B7DCC`. Its immediate path sets word `0x800C3000` mask `0x00000800`. Script opcode `0x24` at `0x800470B8..0x80047120` dispatches a specified handler with a specified registered AOT record. Opcode `0x2D` at `0x80047AE0..0x80047B14` invokes that dispatch and updates masks `0x00000400` and `0x00000800`. The reader treats either bit as a pending item interaction and validates the selected pointer against the bounded registry.
- The normal take-item dispatcher at `0x80034340..0x80034390` calls `0x8002CD30` for ordinary items. That routine reads the same selected descriptor, disables its handler, clears its GlobalId through `0x8004897C`, and obtains item type and quantity at source-pointer offsets 8 and 9. The acquisition index is at source-pointer offset 20, or opcode byte 22. It stacks compatible ammunition or writes the selected inventory, then increments byte `0x800C8667` at `0x8002D000..0x8002D00C`. A full-text direct-call scan found only the call at `0x8003437C` to `0x8002CD30` and no literal pointer to that routine.
- A scan resolving direct LUI/base-relative references to inventory pointer `0x800BA008` and held-count byte `0x800C8667` found the normal award above. Other direct held-count stores were new-game initialization at `0x8002C95C`, inventory compaction at `0x8002CB30`, recount at `0x8002CBEC`, attract/save-state restoration at `0x8002ABA8`, and the put-back decrement at `0x8002D0E0`. The surrounding instructions were inspected to classify these stores. This scan is stronger evidence than the single caller alone, but it does not prove absence of every indirect or bulk memory write.
- Item type `0x4D`, Radio, branches around the normal award at `0x80034368..0x80034388` and sets scenario-bank index 127 instead. It does not establish ordinary acquisition-flag semantics. The implementation reports an explicit unsupported Radio acquisition error until that separate flag is configured. Active type 0 or types `0x54..0xFF` on an inventory/map/pending path are errors, not silently omitted items.
- Map handler 15 at `0x80038578..0x800385E8` disables its registered object, clears its acquisition GlobalId, and records map ownership through `0x80033D48` using item type minus `0x4E`. Handler 13 opens the document screen. Documents do not block normal room completion. Handler 8 at `0x80037EF8` sets item-box state byte `0x800C8457`; its deferred path at `0x80038BA4..0x80038D00` opens storage through word `0x800C3000` bit `0x00001000`. Its `0x80051E38` call plays a sound. This resolves the direct item-box uncertainty retained in RE1-COVER-001. Item-box transfers move existing stored inventory and are not collectible room awards. Typewriter handler 16 searches for Ink Ribbons rather than granting an item.
- Zero rectangles and mode 0 are real registered puzzle/event items. `ROOM1070.RDT`, SHA256 `1f3c51bb02986c8bfc9c4804b4f319a411f12361dab6ec55c2f49b39ea5d44b1`, contains Mansion 1F map type `0x4E`, GlobalId 145, AOT 2 with zero geometry. Indexed event 1 invokes `24 02 0F 00` at file `0x34A8A`, using the same map handler. `ROOM1130.RDT`, SHA256 `d01ba9bbef4fcfa5d2e76624aa6328b50fc59426c51be9020ba503618216f7a3`, registers Small Key type `0x3D`, GlobalId 3, AOT 1. Its indexed event 4 invokes `24 01 04 00` in the embedded script starting at file `0x1CDAE`. Other Bathroom variants use different item identities, so the loaded descriptor controls the displayed name.
- `ROOM1000.RDT`, SHA256 `bc013eaceb14dde97a71ce63b2d268d42043b7fd116ccdd127e76c8091907628`, registers two mode-0 Magnum Round descriptors as AOTs 6 and 7. Its registered event 57 dispatches `24 06 04 00` and `24 07 04 00`; each award predicate tests a flag recording the corresponding already-received award. The observed code provides no additional future-story predicate for these two awards. Main Hall's distinct `ROOM1061.RDT` initializers are genuinely skipped by story/acquisition predicates in the capture described by RE1-AVAIL-001. Their stale inactive slot is excluded by the current loaded-source check.
- The controlled Herb source remains `0x8013E65E`, AOT 5, type `0x44`, GlobalId 111. Before pickup its handler is 4 and its acquisition flag is set. After pickup its handler is 0 and its flag is clear. The Chemical source remains `0x80121E94`, AOT 1, type `0x26`, GlobalId 13, with the same 4-to-0 handler and set-to-clear flag transition. The observer reports one available item before and one taken item after in both pairs, with five active Herb-room doors and one active Chemical-room door. Their normal acquisition and save/load evidence remains in RE1-FLAG-001 and RE1-SAVE-001.

Artifacts: controlled RAM SHA256 values are Herb-before `d819fbd41abea6537bf9ce9f4967b479ea1f6278024b9f4e018290343c0bc8d4`, Herb-after `0130861a3a27d2810ccbd0d1e2e7bbc42c64abdac130e1d43dd71ed646784704`, Chemical-before `bb9110536a02122d7c6a14d489b2e94e7d8224d8ccf297d617694c4eb6e804f2`, and Chemical-after `0d5e7dc6e450a99b9f8a354cc9ffd30e97dd3129427600e384681903330935df`. Dumps and disc data remain outside Git. The regression tests use the existing explicitly supplied pickup fixtures and synthetic pointer/handler/pending changes. At this contribution, all 23 observer tests pass and Ruff passes its two implementation/test files.

External lead: [resident-evil-pc-decomp RoomEvents.cpp](https://github.com/ecruells/resident-evil-pc-decomp/blob/15004914527567a2b9cecf34997abe8c252bcbf9/src/game/RoomEvents.cpp) and [PlayerAnimations.cpp](https://github.com/ecruells/resident-evil-pc-decomp/blob/15004914527567a2b9cecf34997abe8c252bcbf9/src/game/PlayerAnimations.cpp) at commit `15004914527567a2b9cecf34997abe8c252bcbf9` helped locate the award and item-box functions. The PS1 instructions above, not the port's implementation, support the claims.

Limits: the current registry is a live observation, not a permanent static item list for an unvisited room. Registered interactions and acquisition flags must be reread after script changes and loads. Dormant handler 0 and put-back handler 3 do not establish a currently available pickup. A validated ordinary item with a clear flag is taken; one with a set flag and active handler 4/15 or the selected pending pickup is available under this rule. Untested story, character, difficulty, and room variants remain outside the controlled runtime proof. The Bathroom, map, and generic-AOT paths above were inspected but not played by this author. Event decoder output alone does not prove all event entry points or conditions. General availability needs additional live comparisons as play progresses. Radio and malformed/unsupported active descriptors remain explicit failures. The inventory-store audit covers the main executable's directly resolved paths; native overlays and bulk state restore need separate scope checks before claiming complete inventory-write coverage. End-of-game rewards are not normal world pickups. The observer's coherence checks reject changed acquisition flags, registration bytes, script ranges, or pending item state during a read; they do not freeze the emulator or make memory access atomic.

History:
- 2026-09-29; Codex subagent `/root/remake_items` with model GPT-6.1 Sol; authored and implemented; traced the pinned normal/map/file/storage handlers, compared four existing pickup captures, audited direct held-count stores, and added 23 passing observer tests. No gameplay, save/load, or new GDB reads were performed by this author.
- 2026-09-29; Codex root with model GPT-6.1 Sol; independently identified the Radio branch and reviewed the active unsupported-type and generic descriptor-width failures. Runtime integration and external review are separate contributions.


## RE1-SCD-004: object initializer is 28 bytes in SLUS-00551

Status: Candidate; pinned executable decoding and static reachability reproduced, no new gameplay execution check
Scope: Resident Evil Director's Cut USA SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`; init/main sections of all 335 disc RDTs, including byte-matched Jill Herb and Chemical fixtures
Environment: macOS arm64, LLVM disassembly of an ELF wrapper whose text is byte-identical to the PS-X executable; owned disc and existing RAM captures, 2026-09-29; no GDB or game control
Authored: 2026-09-29; Codex subagent `/root/remake_doors`; model: GPT-6.1 Sol
Basis: pinned executable source inspection, full-disc old/new scanner comparison, fixture section matching, and synthetic branch regression
Claim: opcode `0x1F` advances the script pointer by `0x1C` (28) bytes. The previous scanner width 30 can skip a real following command and decode its payload as opcode `0x00`, incorrectly ending a procedure. Correcting this width preserves the branch rules from RE1-SCD-003 and restores additional reachable commands.
Evidence: dispatch-table slot PS1 VA `0x80091184` points to handler `0x800467A0`. That handler repeatedly reads the current script pointer at `0x800CF640`; the final pointer in `$5` is still the original opcode address. Instruction `0x80046AB8` reads its byte-8 halfword, `0x80046ABC` adds `0x1C`, and `0x80046ADC` stores the advanced pointer back. A full rebuild produces 335 rooms, 652 candidate item rows and 782 door rows, with generated JSON SHA256 `cfacd9d9df5efc6c67175bf1f9462644d3188a2ff25b11a8f3cb27f3993b6a47`. Compared with the 30-byte scan, 170 rooms change statistics; 91 sections change partial to clean and eight change clean to partial. All 43 Mansion RDT variants now have clean init/main scans. The whole disc has 631 clean sections, 37 partial sections, and two bad ranges. No door records change, no item records are removed, and seven candidate item records are added: gid 120 at `ROOM40A0` `0x392A6`, and gids 163/229/164 at `ROOM50A0` and `ROOM50A1` `0x28E36/0x28E50/0x28E6A`. Metadata-only comparison is `/tmp/tasks/re-map/item-cache/deltas_1f28.json`, SHA256 `4a9ae96957f76010fee38333640a446c295cc1625f53bf213273422e84653e7a`.
Correction to earlier findings: in `ROOM1091`, opcode `0x1F` at `0x1CA76` is followed by a 22-byte opcode `0x1B` at `0x1CA92`. The former apparent terminator at `0x1CA94` and item at `0x1CAA6` are inside its payload. The actual terminator is `0x1CAC6`; gid 35 remains excluded, with a different reason. In `ROOM40A0`, the corrected first object command ends at an ELSE at `0x39236`, and subsequent correctly aligned commands reach gid 120. The old apparent terminator at `0x3925A` is payload. This supersedes those specific explanations in RE1-SCD-002 and RE1-SCD-003 while preserving their original provenance and runtime observations.
Fixture check: both existing Chemical RAM captures match `ROOM1180` init `0x270..0x320` byte for byte at loaded base `0x80121C00`; its last object opcode at `0x2FE` now leads to the real terminator at `0x31A`. The two RAM hashes are recorded in RE1-PILOT-002. The regression test constructs an object initializer followed by an entity initializer whose zero payload previously looked like termination, then verifies that both IF item paths and their exact addresses are retained. No game bytes were added to Git.
Limits: source inspection and fixture alignment do not prove a played object-initialization path or current item availability. The eight newly partial init scans are `ROOM20F0/20F1/70F0/70F1` with overlapping branch targets, `ROOM3010/3011` with unresolved opcode `0xC4`, and `ROOM5130/5131` with unresolved opcode `0x28`. Their previous clean status was not reliable evidence. Other opcode widths, indexed events, native callbacks, and story-dependent item availability remain separate questions. This finding does not promote any room to complete item coverage.
History:
- 2026-09-29; Codex subagent `/root/remake_doors`, model GPT-6.1 Sol; inspected the pinned handler, compared old/new walks across all disc RDTs, matched existing Chemical RAM sections, corrected the one scanner width, regenerated the candidate table, and added the branch alignment regression. No gameplay, memory write, or new save capture.


## RE1-CACHE-001: source dependencies bound prior-room manifest reuse

Status: Candidate; conservative static eligibility and metadata generation, no new save/load or story gameplay validation
Scope: the named SLUS-00551 executable in RE1-SCD-004; all 43 Mansion RDT variants on the owned disc
Environment: pinned PS1 executable disassembly, owned disc, profile configuration and Python regression tests, 2026-09-29; no GDB or game control
Authored: 2026-09-29; Codex subagent `/root/remake_doors`; model: GPT-6.1 Sol
Basis: direct opcode-`0x04`/`0x06` handler inspection, conservative scan of both init/main branch outcomes, source signatures, and synthetic rewind cases
Claim: cached availability can be retained only with matching game identity, source RDT, character, variant, and every source predicate's masked value. Acquisition state must be reread from the game separately. Opcode `0x18` also implicitly checks its GlobalId acquisition bit: source GlobalIds absent from a runtime observation must guard reuse, because an already-taken item can leave no active descriptor after entering the room and become available again after an earlier load. Metadata therefore records both explicit predicate dependencies and all reachable `item_global_ids`, rather than caching a completed room color.
Evidence: opcode-`0x04` handler at `0x80044D54` selects one of ten bank bases through table `0x800106B0` and numbers bits from each little-endian word's MSB. The source bases for groups 0 through 9 are `0x800C8700`, `0x800C8694`, `0x800C86B4`, `0x800C86BC`, `0x800C3008`, `0x800C3000`, `0x800CAB00`, `0x800C86DC`, `0x800C8710`, and `0x800B8348`. Group 9 specifically uses `lui 0x800C` at `0x80044E04` followed by signed `addiu 0x8348` at `0x80044E08`, yielding `0x800B8348`; treating that immediate as unsigned would produce the wrong bank. Opcode `0x06` at `0x80044FA4` compares the runtime byte at `0x800C8660 + operand`, so camera and interaction fields cannot be fingerprinted from the active room to infer a prior room. The reusable `tools/build_cache_metadata.py` requires CUE, output, and profile paths; its addresses come from required profile configuration and it verifies the disc executable hash before writing. It retains init/main signatures for all 43 variants even when cache reuse is rejected. Generated `data/room_manifest_slus00551.json` SHA256 is `d2176d42361be12106d9f5637efc4fee943214a668f18576c55687292529bc7a`.
Eligibility: five files pass the initial conservative scan: `ROOM1010/1011`, `ROOM10A0`, `ROOM10B0`, and `ROOM1180`. The Storeroom dependencies include the branch mask at `0x800C3006` bit 1 and the explicit acquisition-controlled main checks at `0x800C86DE` bit 2 and `0x800C86E1` bit 7. Every row also includes character and variant context masks. Nonempty indexed event sections, unresolved boundaries, unaudited commands or generic callbacks, active-room-only comparisons, and main writes to potential item AOTs explicitly reject reuse. Generic normal-item handlers 4/15 are rejected until their acquisition descriptor semantics are audited; they do not silently receive an empty source-item list.
Tests: synthetic cases verify both IF paths, four word/bit boundary positions, masked context extraction, required configuration failure, indexed events, room-local comparisons, native commands, unknown flag groups, malformed branches, generic item callbacks, and an item with an implicit acquisition check but no explicit predicate. The full worktree Python suite passes 91 tests. Metadata generation reproduced 43 rows and five eligible candidates.
Limits: the whitelist is a source-derived candidate safety gate, not gameplay confirmation of every native callee or absence of every possible item grant. Object/entity construction is admitted because the inspected direct handlers construct scene records without direct AOT mutation; indirect behavior and future stories remain untested. The Winding Passage event audit in RE1-EVENT-002 is bounded and is not automatically promoted into a cache exception. This metadata does not establish source completeness for the other 38 variants or justify carrying an availability observation across a changed dependency. Runtime source identity, coherent reads, actual manifest capture, cache mutation, and game-load reversal behavior need their own implementation checks.
History:
- 2026-09-29; Codex subagent `/root/remake_doors`, model GPT-6.1 Sol; inspected all ten flag-bank selectors and comparison handlers, generated Mansion dependencies from owned RDTs, implemented metadata generation and regressions, and retained explicit rejection reasons. No game control or memory writes.


## RE1-COVER-003: bounded native overlay inventory audit

Status: Candidate; source inspection with a bounded address-reference scan, no new gameplay proof
Scope: Director's Cut USA SLUS-00551 and the executable identity in RE1-COVER-002; all twelve owned-disc PSX/PROG2 executable overlays
Environment: local disc extraction and little-endian MIPS32 disassembly, Capstone 5.0.9; existing Herb-before RAM capture only
Authored: 2026-09-29; Codex subagent `/root/remake_geometry`; model: GPT-6.1 Sol
Basis: pinned executable and overlay inspection, resolved resident callback table, and read-only comparison with controlled RAM
Claim: the inspected stage overlays contain no directly resolved normal inventory award bypassing the registered pickup descriptor. The ending overlay does construct next-cycle reward inventory outside AOT. This is excluded from normal collectible room completion and prevents generalizing the claim to all inventory writes.
Evidence:

- The main overlay loaders are at PS1 VA `0x8003642C` and `0x80036578`. They load the 0x800-byte PS-X header, copy its entry/load metadata into the task, and then load and schedule its body. The original-release loader addresses in third-party leads differ and were rejected for this revision.
- The resident callback initializer at `0x80036278..0x800362D4` copies 0xB4 words from `0x8008F764` to `0x801FE900`. The complete 0x2D0-byte copy matches the existing Herb-before RAM capture, whose SHA256 is in RE1-COVER-002. Root independently repeated this byte comparison and inspected the copy loop on 2026-09-30. Callback `0x801FEB38` resolves to flag setter `0x80048954`; `0x801FEBAC` resolves to inventory reset `0x8002C7A8`. Stage-native registrations are real and were included in the audit.
- Across STAGE1 through STAGE7, the linear register-constant scan found no direct jump/call or literal pointer to pickup acceptance `0x80034340` or ordinary award `0x8002CD30`, and no resolved references to inventory pointer `0x800BA008`, count byte `0x800C8667`, selected AOT `0x800B7DCC`, or reset callback `0x801FEBAC`. Surrounding candidate instructions and callback resolutions were inspected by the author.
- ENDING.EXE SHA256 `15fe81f2f40e2587cdd58ea472c9f455e6547ff4d30fd8966682a0054d7aeae4` resets inventory through callback `0x801FEBAC` at `0x800E1804..0x800E1810`. Its branches append inventory at `0x800E18B8/0x800E18DC`, `0x800E199C/0x800E19C0`, and `0x800E1A1C/0x800E1A40`, increment the held count, set unlock bits, and enter next-cycle saving. These awards have no room pickup AOT and are not presently obtainable world items.

Artifacts: numeric overlay manifest `/tmp/tasks/re-map/geometry/overlays/manifest.json`, SHA256 `f7aae05e4bc0dcb4c38be1bdf2fcf68fb14c8ef96db6ffa22e24bf6cc557f052`, records each owned file's LBA, size, load address, entry and hash. Audit methods and checked instructions are recorded in `/tmp/tasks/re-map/geometry/current_item_coverage_audit.md`. Executable overlay bytes remain outside Git.
Source leads: [pinned PSX engine analysis](https://github.com/ecruells/resident-evil-pc-decomp/blob/15004914527567a2b9cecf34997abe8c252bcbf9/docs/PSX_ENGINE_ANALYSIS.md), [DC stage overlays](https://github.com/ecruells/resident-evil-pc-decomp/blob/15004914527567a2b9cecf34997abe8c252bcbf9/docs/PSX_DC_STAGE_OVERLAYS.md), and [DC ending overlay](https://github.com/ecruells/resident-evil-pc-decomp/blob/15004914527567a2b9cecf34997abe8c252bcbf9/docs/PSX_DC_ENDING_OVERLAY.md), commit `15004914527567a2b9cecf34997abe8c252bcbf9`. Their descriptions are leads; the owned pinned instructions support this finding.
Limits: linear constant propagation is not an exhaustive control-flow or alias proof. Computed pointers, bulk restoration, indirect callback aliases and writes through larger structures can escape the scan. The negative result supports RE1-COVER-002 but does not independently confirm universal availability or every story/character variant. No gameplay, GDB read, save or load was performed by the author for this audit.
History:
- 2026-09-29; Codex subagent `/root/remake_geometry`, model GPT-6.1 Sol; authored; extracted and hashed twelve overlays, traced the resident callback copy, scanned stage references, and inspected next-cycle reward writes.
- 2026-09-30; Codex root, model GPT-6.1 Sol; reviewed and integrated; repeated the complete callback-table comparison against the pinned executable and controlled RAM, inspected the initializer instructions, and preserved the audit's bounded negative-result limits. This contribution did not reproduce every overlay scan.


## RE1-LIVE-002: floor-plan, item and door integration checks

Status: Confirmed for the listed controlled Herb/Chemical snapshots and live Winding Passage display; general room availability remains Candidate under RE1-COVER-002
Scope: SLUS-00551 executable identity in RE1-COVER-002, Jill controlled Winding Passage 00-09 and Storeroom 00-18 states; Mansion 1F numeric geometry in RE1-MAP-002
Environment: macOS arm64; official DuckStation 0.1-11894-gc66b2694d in an isolated portable copy, no memory cards attached; GDB localhost:2345; tracker localhost:8765; Python 3.14.7 regression runner
Authored: 2026-09-30; Codex root; model: GPT-6.1 Sol
Basis: offline controlled-state reproduction, synthetic failure/reversal regressions, live read-only GDB polling, and browser inspection
Claim: the integrated poll binds the loaded Mansion script hash to the room ID before publishing a visit, reads currently registered items and directional locks, and renders entered room geometry and item details. Runtime read failures interrupt live details and the map reconnects after emulator restart.
Evidence:

- All four existing controlled savestates were extracted and passed through the production poll. Herb and Chemical before states each report one remaining item and INCOMPLETE; after states report one taken item and CLEARED; replacing the capture with the before state restores INCOMPLETE. Exact RAM hashes remain in RE1-COVER-002. These checks reuse supplied states and are not new normal-save or gameplay experiments.
- Synthetic regressions reject a changed room ID while the old RDT is loaded, altered script content with unchanged header, out-of-RAM room pointers, changed room ID during a poll, wrong executable signature and failed item reads without recording a visit. Cached acquisition flags are reread, not cached colors. An empty earlier observation with a rewound absent item flag loses completion coverage; a changed Storeroom story branch also invalidates reuse.
- The Winding Passage source contains five active doors. The live locked Armor Key door is displayed from unlock byte `0x800C86B7` mask `0x08` clear, alongside four open doors. Synthetic set/clear replacements exercise the decoder's lock-to-open-to-lock behavior. An actual key use or normal save/load of a door unlock was not performed.
- An isolated live Herb-before boot showed just the entered Winding Passage contour, five wall door markers and Green Herb Remaining. Closing the isolated emulator produced an interrupted-connection message and cleared item/door details. Restarting it with the Herb-after savestate, without restarting the map server, produced the same entered contour with All available items collected and Green Herb Collected. The tracker log recorded GDB reconnected and resumed. This tests reconnection and fresh reads, not normal in-game saving.
- Geometry and candidate item generators reproduce their committed numeric metadata byte for byte. No map texture, palette, disc, executable, BIOS or additional savestate was added to Git. Existing visit history remains scoped to the tracker session.

Artifacts: `tests/test_live_items.py`, `tests/test_room_cache.py`, fixture hashes in RE1-COVER-002, rotating ignored `logs/tracker.log`, and temporary validation logs under `/tmp/tasks/re-map/`. Browser screenshots are delivery artifacts outside Git.
Limits: live display was checked in Winding Passage. Storeroom current completion uses the controlled snapshot pair; normal-save evidence stays scoped to RE1-SAVE-001. The floor map covers Mansion 1F only, camera-selected secret region rules remain source-derived, and unvisited regions stay hidden. Source-derived general AOT semantics, native coverage, door special paths and conditional prior-room cache policies retain their respective Candidate limits. A normal room transition and actual key unlock were not newly reproduced for this contribution.
History:
- 2026-09-30; Codex root, model GPT-6.1 Sol; implemented and tested; integrated the runtime registry, source identity, acquisition refresh, directional locks, original numeric floor-plan renderer, and explicit reconnect behavior. Tests using replaced bytes are labeled synthetic and do not promote gameplay validation.
- 2026-09-30; Gemini 3.1 Pro (High) through agy; reviewed the supplied integration source and tests without gameplay. Its terminal-only reconnect finding was verified and corrected; startup-offline map and dropped-connection map/CLI regressions were added. Its generic-0x0D descriptor boundary findings were checked against award handlers `0x8002CD30` and `0x80038578`: those later handlers read source-pointer offsets 8/9/20 without checking the creator opcode. The bounded 26-byte award read is intentional, although the creator itself is 18 bytes. The matching regression is synthetic; no active generic inventory/map initializer was found in the 43 Mansion sources inspected by `/root/remake_items`.
- 2026-09-30; Claude Opus 4.6 (Thinking) and Gemini 3.8 Flash (High) through agy; integration reviews unavailable. The headless runners attempted commands despite the supplied-context-only request and command permission was denied; no usable findings returned. These attempts are not endorsements. Earlier component reviews from Gemini 3.1 Pro (High) and Gemini 3.8 Flash (High) checked door/geometry source excerpts only; root directly checked every candidate against the pinned scope and data.
- 2026-09-30; Codex root, model GPT-6.1 Sol; reviewed; rejected stale details on room clicks during connection failure, added required runtime camera/room address validation, and bounded loaded-source pointer reads before hashing.
- 2026-09-30; Codex root, model GPT-6.1 Sol; tested; live controlled boots now show two entered regions, with the prior Herb room cleared and the current Chemical room incomplete. Clicking the prior room during a disconnected interval kept item and door details cleared. Screenshot `logs/validated-floor-plan.jpg` is an ignored local delivery artifact. This observed-state sequence uses supplied savestates and does not imply a walked door transition.
- 2026-09-30; Codex root, model GPT-6.1 Sol; checked tooling; no repository formatter/linter is configured. Manual Ruff lint and formatting checks pass the new/edited implementation and test scope. Strict lint also reports existing `PYI034`/`UP037` at the GDB client's unchanged context-manager annotation; old scanner-wide formatting differences remain outside the functional change. These are residual style diagnostics, not runtime validation evidence.
- 2026-09-30; Codex root, GPT-6.1 Sol; final integrated suite passed 205 tests in 9.48 seconds. Node syntax check and manual Python formatting passed; the repository has no configured formatter/linter. Scoped Ruff checks passed with the already documented pre-existing PYI034/UP037 annotations outside the changed lines treated as residual diagnostics. Controlled emulator boots observed Chemical-before followed by Herb-after without restarting the tracker: only two observed room outlines appeared, past Chemical stayed red/Remaining, Herb was blue/Collected, and the Armor Key door stayed locked. Screenshot `logs/validated-floor-plan.jpg` is ignored local evidence. An interrupted connection clears current-room markers, item/door details and completion colors until fresh reads. These boots do not reproduce a walked transition or a real door unlock.
- 2026-09-30; Codex root, GPT-6.1 Sol; final regression gate passed 206 tests in 9.63 seconds after requiring a source-bound ordinary map region. An unbound Sub1F cannot reveal the unresolved physical region1F. Independent pieces were committed separately; no game images, BIOS, new savestates, RAM dumps or screenshot entered the commits. The isolated validation game was stopped and tracker-session history reset before handoff.


## RE1-SCD-005: pinned variable command widths and operand-free block end

Status: Candidate; pinned source inspection and synthetic alignment tests
Scope: Resident Evil Director's Cut USA SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`
Environment: Python 3.14.7, Capstone 5.0.9, read-only executable and extracted Mansion RDT files; no new GDB or gameplay
Authored: 2026-09-30; Codex subagent `/root/remake_items`; model: GPT-6.1 Sol
Basis: primary PS1 instruction inspection; the PC decompilation was a navigation lead
Claim: three variable-width commands need revision-specific widths to keep following event commands aligned. Opcode `0x17` consumes 10 bytes for sound-source low bytes 0–3 and 6 bytes in its default case. Opcode `0x28` uses subcommand byte 3 and widths `{0:6,1:8,2:6,3:6,5:6,6:4,8:4,9:6,10:6}`. Opcode `0x33` uses subcommand byte 1 and widths `{0:2,1:4,3:4,4:2,5:4,6:2,7:2,8:4,9:4,10:4}`. Unsupported property subcommands have no proven advance and reject complete scanning. The `0x00` block-end handler reads no operands, so a single final zero is a legal terminator; nominal padding is not a required operand.
Evidence: opcode `0x17` handler `0x800458F4..0x80045A5C`, enemy-property handler `0x80047124..0x80047320`, player-property handler `0x80047324..0x800475F8`, and block end `0x80044C5C..0x80044C68` in the pinned executable. `tests/test_scan_scd_widths.py` verifies that a following pickup remains aligned for each implemented subtype and that unsupported subtypes fail explicitly. The branch walker still rejects a target overlapping a previously decoded padded zero, so two real `ROOM1051.RDT` embedded blocks remain conservative decode failures even after accepting a final single zero.
Limits: source inspection and synthetic tests do not confirm gameplay or additional revisions. Regeneration can change parsed rows outside Mansion, and those deltas require inspection rather than attribution to new game items.
History:
- 2026-09-30; Codex subagent `/root/remake_items`, GPT-6.1 Sol; inspected the pinned handlers, corrected the scanner widths, and added 28 passing alignment/unsupported-subcommand tests. No runtime experiment was performed.
- 2026-09-30; Codex root, GPT-6.1 Sol; independently inspected the pinned variable handlers, integrated the decoder and regenerated all 335 room records. Final output has 652 raw item candidates and SHA256 `c096fde64662cc8e8fdeeb8e30d810cd75c6e4c03a08710d9171c84adedf7617`. Relative to the earlier opcode-1F correction, the later width changes alter scanner diagnostics in 37 records and do not alter item or door payloads. The source handler has a six-byte default for opcode17, but unsupported source modes deliberately reject scan coverage. This is parser evidence, not confirmation of additional pickups.
- 2026-10-01; Codex root, GPT-6.1 Sol; superseded the padded-zero overlap limitation with RE1-SCD-006. Opcode `0x00` has a one-byte instruction extent at every reachable position, including when another branch targets the next zero. The variable-width claims above are unchanged.


## RE1-SCD-006: operand-free script ends allow adjacent Dining Room branch targets

Status: Candidate; pinned source inspection, owned-disc decoding and synthetic regression tests
Scope: Resident Evil Director's Cut USA SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`; Dining Room source `PSX/STAGE1/ROOM1051.RDT`, SHA256 `5806bca194b92319f58bdc642060924a6d837054d8bffcbbe34d4d5af81a80e4`
Environment: Python 3.14.7 and Capstone 5.0.9; read-only local executable and disc extraction; no new DuckStation, GDB or gameplay experiment
Authored: 2026-10-01; Codex root; model: GPT-6.1 Sol
Basis: primary PS1 instruction inspection, before/after scanner results and synthetic tests
Claim: opcode `0x00` ends its procedure without reading operands. Its instruction occupies one byte even when nominal padding follows. A branch landing on that next byte can therefore execute a separate `0x00`; treating padding as an operand incorrectly rejects these valid paths. The length-prefixed procedure list still requires its separate two-byte zero-length sentinel.

Evidence:

- The pinned handler at PS1 virtual address `0x80044C5C..0x80044C68` loads the global base, clears the IF depth byte at `0x800CF63A`, returns, and sets the result to zero. It does not read source operands. This extends RE1-SCD-005's acceptance of a single final zero to all reachable end instructions.
- `ROOM1051.RDT` embedded blocks at file offsets `0x286AC` and `0x286D2` each contain a length-16 procedure. Their IF false path targets procedure-code offset 13, immediately after another end instruction at offset 12. Previously both were rejected as `overlapping branch target at +13`. The corrected walker emits separate single-byte ends at `0x286BC/0x286BD` and `0x286E2/0x286E3`; both blocks and the full indexed event section now decode cleanly.
- Reproduction: run `tools/build_item_table.py` and `tools/build_cache_metadata.py` against the owned SLUS-00551 disc, using the committed profile. Compare the output with the previous generated files. All 335 room item/door payloads remain identical. The item table remains 652 candidates with SHA256 `c096fde64662cc8e8fdeeb8e30d810cd75c6e4c03a08710d9171c84adedf7617`. Only three diagnostic fields in the ROOM1051 manifest record change: event status and the two cache-rejection reasons. The regenerated manifest SHA256 is `f662c41c414e25b79dd5075af24066c461febc4f30888cc124ad6d0c58f7801d`.
- Synthetic regressions in `tests/test_scan_scd.py` cover distinct adjacent end instructions and rejection of a missing two-byte procedure sentinel. `tests/test_scan_events.py` covers both camera/flag variants of the Dining Room branch structure and a single-command end followed by the VM terminator. Existing true payload-overlap, malformed-bound, unsupported-opcode and cache/load safeguards remain in the full suite.
- The explicitly partial linear candidate scan retains nominal two-byte end/padding packets to preserve its historical raw candidates. Those packets do not establish instruction reachability or complete coverage; the branch and event decoders use the one-byte extent.

Limits: no new gameplay or save/load validation was performed. Clean decoding does not resolve ROOM1051's picked/used-item and camera conditions or its event-driven door updates. Both cache-completeness fields remain false; item-cache eligibility remains 31/43 sources and door-cache eligibility 30/43. No additional game revision is covered. Extracted game bytes and external review outputs remain outside Git.
History:

- 2026-10-01; Codex root, GPT-6.1 Sol; inspected the pinned handler, reproduced both failures, corrected the instruction extent, audited regeneration, and reviewed the final code and metadata diff. All 211 tests passed in 9.51 seconds. Scoped Ruff lint passed for the three changed Python files, and Ruff formatting checks passed for the two changed test files. No project formatter or linter is configured; the legacy opcode table was not reformatted.
- 2026-10-01; external review attempts via agy: Claude Opus 4.6 Thinking was unavailable due quota exhaustion; Gemini 3.1 Pro High timed out after five minutes without a usable review; Gemini 3.8 Flash High failed with an internal service error. None returned review findings or endorsements. The local inspection and regression results above are separate evidence.


## RE1-SOURCE-001: room initialization and quantity transfer mutate source bytes

Status: Candidate; explicit stores in the pinned executable and exact Mansion source targets
Scope: the SLUS-00551 executable identity in RE1-SCD-005; source binding for loaded init/main scripts
Environment: read-only executable and 43 extracted Mansion RDT variants
Authored: 2026-09-30; Codex subagent `/root/remake_items`; model: GPT-6.1 Sol
Basis: primary PS1 instruction inspection and static target enumeration
Claim: loaded init/main scripts are not entirely immutable. Opcode `0x18` masks its source u16 at command byte 24 to bit 0. Opcode `0x4C` modes 1/2 can write the quantity at the selected AOT's source pointer plus 9, equivalent to initializer byte 11. Exact source matching must validate and normalize these proven fields before comparing the original source SHA256; every other byte remains exact.
Evidence:

- `0x80045FE8..0x80045FF4` reads the item parameter, masks it with 1, and stores it back into the source packet. Actual nontrivial original parameters occur in `ROOM1000.RDT` command `0x10C76` (`0x8700→0`), `ROOM1050.RDT` commands `0x2805C` (`0x8401→1`), `0x280A0` (`0x8600→0`), `0x280BC` (`0x8400→0`), and `ROOM1051.RDT` commands `0x2808C` (`0x8600→0`), `0x280A8` (`0x8400→0`), `0x28242` (`0x8401→1`). Every item initializer has a declared parameter field, including original values already equal to 0/1.
- Transfer handler `0x80048634..0x80048770`: mode 0 reads source quantity into a byte at `0x800C8660 + field`; mode 1 writes that state byte to source+9 at `0x800486C0`; mode 2 writes inventory quantity into both the state byte and source+9 at `0x80048754..0x80048758`. The actual Mansion transfers are `ROOM1160.RDT` init `0x1FE5E` raw `4C 01 01 0C` and event `0x2033A` raw `4C 02 01 0C`, both targeting AOT 1.
- Opcode `0x12` at `0x80045BC4..0x80045C34` and `0x13` at `0x80045C38..0x80045C84` write AOT record fields only and preserve its source pointer. They do not rewrite their source packets.
- Metadata `mutable_fields` uses an explicit section, offset relative to that section, width, kind (`item-parameter-mask` or `item-quantity`), and original integer. Parameter matching permits only original or original&1, then restores original bytes for hashing. Quantity matching permits the proven runtime byte and restores its original byte for hashing. Tests identify exact fields and include already-masked parameters. Production matcher rejection of third parameter values or adjacent corruption is separate integration work.

Limits: this author did not run a live mutation experiment. Dynamic quantity in `ROOM1160.RDT` still rejects prior-room item caching. No item initializer was found in indexed events among the scanned Mansion paths; immutable matching currently binds init/main, not event-body bytes. Unsupported event paths remain rejected in RE1-CACHE-002, so this is not proof for arbitrary source packets or all game stages.
History:
- 2026-09-30; Codex subagent `/root/remake_items`, GPT-6.1 Sol; traced source stores, enumerated concrete Mansion targets, and generated exact mutable-field metadata. Root integration and runtime matching tests are separate contributions.
- 2026-09-30; Codex root, GPT-6.1 Sol; independently verified stores at `0x80045FF4`, `0x800486C0`, and `0x80048758`. Added mandatory mutable-field construction checks, per-source normalization and identity hashing. Regression tests accept only original or original&1 parameter values, accept the audited quantity byte, and reject a third parameter value, adjacent opcode corruption, overlapping fields and out-of-range declarations. No new live source-mutation experiment was performed.
- 2026-10-01; Codex root, GPT-6.1 Sol; RE1-SOURCE-002 extends exact source identity to indexed-event bytes and their loader relocation. The original item-mutation claims and attribution above are unchanged.


## RE1-CACHE-002: indexed event analysis permits guarded Mansion item-cache reuse

Status: Candidate; source-derived cache eligibility with synthetic regression tests
Scope: SLUS-00551 executable identity in RE1-SCD-005; 43 first-Mansion source files, with both available variants where present
Environment: read-only local disc extraction; no new emulator access; Python 3.14.7 and Capstone 5.0.9
Authored: 2026-09-30; Codex subagent `/root/remake_items`; model: GPT-6.1 Sol
Basis: primary PS1 interpreter inspection, all indexed entries and bounded control-flow exploration, source predicate analysis
Claim: merely containing an indexed event does not require invalidating a room's observed item list after departure. Cache reuse can be authorized when every decoded source path is covered, relevant item-manifest guards are reconstructable or captured as context, and existing acquisition/absent-item rewind safeguards remain intact. Door definition reuse has a separate conservative policy; item-cache completeness alone does not establish stable doors.

Evidence:

- Event initialization `0x80025C1C..0x80025C54` starts each indexed entry in state 0 with depth `0xFF`. The scanner follows all indexed entries, validates their table/ranges, and models states 0–3 through the switch at `0x80026078` and state handlers `0x800262D0`, `0x80026B14`, `0x80026A94`. Payload bytes are consumed by their state-specific widths, rather than searched for apparent item opcodes.
- `FA/FB` loops are inspected at `0x80025EAC..0x80025F70`; repeat and exit paths are both covered. `FC` at `0x80025F74..0x80025FCC` stores source+2 as a deferred SCD pointer and transfers to source+byte1. `FD` at `0x80025FD0..0x80026064` dispatches that saved SCD and either repeats or exits. A linear event walker omitted these deferred commands. The 0x34-byte native event record contains four return/call/counter slots; deeper analysis rejects coverage. Unknown state/opcodes, invalid event indices, malformed packets, and paths leaving the section reject coverage explicitly.
- State-0 opcode `06` calls the length-prefixed SCD runner at `0x80027184..0x800271DC`; opcode `07` dispatches a single source+2 command at `0x800271E0..0x80027238`. The runner at `0x800489CC..0x80048AEC` reads its final two-byte sentinel independently of the VM's advance width. Some odd wrappers leave one sentinel byte in the following VM no-op. Single-command dispatch likewise reads the command's actual operands independently of wrapper width; real short `0x12` wrappers still cause the handler to read ten bytes. Both reads remain bounded by the source section. Synthetic tests exercise these engine-shaped cases.
- Item-relevant source writers include normal `0x18` initializers and `0x0C/0x0D/0x12/0x13` writes to their AOT slots. IF/ELSE predicates guarding such writes become dependencies. Event creation guards also become dependencies when indexed scripts contain item-manifest writes. Global flag bit masks follow the pinned opcode-04 handler; mandatory character/variant context stays configured by the profile. Room-local or non-bit comparisons guarding item changes reject reuse rather than reading another room's camera, selected item, menu, or puzzle bytes as the cached room's context. Camera/entity predicates with no item-manifest effect do not create an item-cache blocker.
- Award `0x24/0x2D` targeting pickup handlers 4/15 must reference an item initializer. Generic `0x0D` pickup/exchange handlers 3/4/15 are rejected by this source cache audit until their descriptor role is classified. Quantity transfer into an item AOT is rejected for cached items. Documents (`type >=0x54`) are excluded from normal source item/acquisition lists. Unobserved normal GlobalIds remain in the source manifest for the existing absent-item rewind guard.
- Door metadata is independent: unknown source flow rejects both kinds of cache. Any decoded door-slot update or forced interaction outside init rejects cached raw-door reuse. Global init predicates guarding door definitions contribute to the same captured context; unresolved local/non-bit init door predicates reject door reuse. Live current-room doors remain direct observations.
- With manual cache audits disabled, 31/43 sources are item-cache candidates: `1000,1001,1010,1011,1020,1030,1031,1040,1041,1070,1080,1081,1090,1091,10A0,10B0,1110,1120,1121,1130,1140,1150,1151,1170,1171,1180,11A0,11B0,11B1,11C0,11C1`, each meaning `PSX/STAGE1/ROOMxxxx.RDT`. Thirty sources are independently door-cache candidates. `ROOM1091.RDT` decodes 27 embedded commands, with no new item initializer, agreeing with the prior Herb audit; its hash override is no longer needed to obtain this result.
- The 12 rejected item sources are `1050/1051` (picked/used-item and camera guards; 1051 also overlapping padded-zero targets), `1060` (state-1 opcode07 at `0x304E2` and local field16), `1061` (camera/local fields16/7 guarding event creation), `10C0/10C1` (paths leave event end at `0x32C48/0x32C44`), `10D0` (puzzle fields19/16/18), `10E0/10E1` (menu field5), `10F0` (event path leaves `0x31F1C`, picked/used-item and menu guards), `10F1` (picked/used-item guards), and `1160` (picked/used-item guards plus live quantity transfers). Exact offsets and mask dependencies are emitted in generated diagnostic metadata; the machine report stays outside Git.
- Generic descriptor audit: the 43 source files' init/main plus decoded event commands contain no `0x0D` initializer with handler4 or15. Counts by generic handler are `{0:29,2:89,7:39,8:3,9:46,10:2,14:2,16:5}`. The normal award routine `0x8002CD30` and map handler `0x80038578` read source+8/type, +9/quantity, and +20/GlobalId without checking the creator opcode. Thus a 26-byte engine-shaped read from an 18-byte generic initializer is intentional handler behavior when bounded by loaded source, but generic pickup tests remain synthetic and are not Mansion gameplay confirmation.

References: [PC RoomEvents.cpp](https://github.com/ecruells/resident-evil-pc-decomp/blob/15004914527567a2b9cecf34997abe8c252bcbf9/src/game/RoomEvents.cpp) and [CmdFunctions.cpp](https://github.com/ecruells/resident-evil-pc-decomp/blob/15004914527567a2b9cecf34997abe8c252bcbf9/src/game/CmdFunctions.cpp), commit `15004914527567a2b9cecf34997abe8c252bcbf9`, supplied navigation leads. Claims above are checked against the pinned PS1 instructions, not inferred from the port.

Limits: eligibility is source inspection, not runtime confirmation of every room/scenario. Already-observed manifests still downgrade if relevant captured context changes, an absent acquisition bit rewinds, or an observed item was unavailable; source rejection also requires reentry. This extension removes blanket event rejection, not uncertainty about those real conditions. It does not persist manifests across tracker restarts, reconstruct unvisited rooms, make GDB reads atomic, or infer future spawn identity. Native callback coverage remains separately scoped in RE1-COVER-003. Opcode/event decoding failures are explicit unresolved coverage and cannot be labeled Cleared. Independent external review and root matcher/poll integration are separate work.
History:
- 2026-09-30; Codex subagent `/root/remake_items`, GPT-6.1 Sol; authored scanner, relevant dependency metadata, independent door-cache policy, and mutable-field metadata; 105 scoped observer/scanner/cache tests passed, and Ruff passed changed Python files. No GDB, emulator control, or gameplay was performed.
- 2026-09-30; Codex root, GPT-6.1 Sol; integrated independent door policy and removed the unnecessary Herb hash override. Added conservative rejection of unguarded item-slot mutations outside init, based on the subagent audit. The only eligible main/event item writers are ROOM11B0/1 and have captured group5 bits24/8 and group7 bits34/35. Final manifest regenerates byte-for-byte from the owned disc, SHA256 `9429de41ddb49407d75b7d0ffc0a1f23d1462bfe75f10700e05fa83566ed45fd`; eligibility remains 31/43 item sources and 30/43 door sources. This count describes static audit coverage, not runtime validation of 43 rooms.
- 2026-09-30; Gemini 3.8 Flash High via agy; reviewed the supplied cache/event/source-binding integration. Its fresh-tracker cached-door KeyError finding was reproduced and corrected with a regression test. Its GlobalId assertion candidate was rejected because the mandatory observer validates the index before returning items. Direct pinned opcode12/13 stores use the complete slot byte without an item-initializer mask; state-0 event08 reinitializes the current event at `0x80027150..0x80027180` and has no sequential continuation. Quantity-transfer stores write selected AOT source+9 regardless of creator opcode, so the source normalization covers every possible matching initializer pointer. Those review suggestions did not change these verified rules. Claude Opus 4.6 Thinking and Gemini 3.1 Pro High final cache reviews timed out after five minutes without a usable review; they are not endorsements. The earlier usable Gemini Pro integration review and its verified reconnect correction remain recorded above.
- 2026-10-01; Codex root, GPT-6.1 Sol; RE1-SCD-006 resolves ROOM1051's two padded-zero event-decoding failures. The regenerated manifest now reports its indexed events as clean, but retains its unresolved item predicates and door updates as cache blockers. Eligibility counts and all item/door payloads remain unchanged; the new manifest hash is recorded in RE1-SCD-006. This is source-derived scanner validation, not a new runtime cache experiment.
- 2026-10-01; Codex root, GPT-6.1 Sol; RE1-CACHE-003 supersedes the range-only predicate relevance calculation above. Nested checks are now bounded by their own branch lifetime, with transitive dependencies and procedure-ending paths retained. The regenerated source eligibility counts remain unchanged; this correction does not establish new gameplay coverage.
- 2026-10-01; Codex root, GPT-6.1 Sol; RE1-ENGINE-001 adds shared reconstruction when an observed manifest's supported global conditions change. Stable observations still use this cache audit, with additional rejection of temporary-bank context. Reentry remains necessary where conditions or asynchronous effects cannot be reconstructed.
- 2026-10-02; Codex root, GPT-6.1 Sol; RE1-EVENT-003 revises the common wait/counter depth, embedded read-window and deferred-return contracts above. It establishes the native state-0 default as termination, while retaining failures for other nonadvancing states and out-of-section paths. The original source audit and attribution remain recorded here; current regenerated coverage is reported by the newer finding.


## RE1-CACHE-003: nested predicate lifetimes and transitive source guards

Status: Candidate; pinned interpreter inspection, owned-source audit and synthetic regression tests
Scope: Resident Evil Director's Cut USA SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`; the 43 Mansion sources in the generated manifest
Environment: Python 3.14.7 and Capstone 5.0.9; local read-only executable and RDT extraction; no new DuckStation, GDB or gameplay experiment
Authored: 2026-10-01; Codex root; model: GPT-6.1 Sol
Basis: primary PS1 instruction inspection, synthetic source experiments and before/after generated metadata
Claim: a predicate within a nested IF does not directly guard a later sibling after that IF's two arms reconverge. Item and door dependency analysis must retain the active enclosing conditions and transitively include conditions that decide whether another relevant test runs. A branch that can end the procedure, or an ELSE test at depth zero, cannot be given that narrow reconvergence limit.

Evidence:

- Pinned IF handler `0x80044C6C..0x80044CC0` pushes source+2+operand1 as its failure target and raises IF depth. ELSE `0x80044CC4..0x80044D0C` pops one frame and jumps by its own operand. ENDIF `0x80044D10..0x80044D50` pops one frame and advances two bytes. The runner at `0x80048A6C..0x80048AB0` handles a zero predicate result by popping and jumping to the active target; with depth zero it proceeds to the next length-prefixed procedure. Thus tests in a nested ELSE use the parent's frame, while a depth-zero ELSE failure prevents later commands in that procedure from running. RE1-SCD-006 records opcode00's procedure-ending behavior.
- Before the fix, a synthetic outer global-flag IF containing a closed camera IF followed by an item update decoded cleanly, but its cache audit rejected the unrelated camera field. The new tests exercise this in both main and embedded event procedures, and with a later door initializer. Separate cases retain genuine nested flags, camera-dependent items in either arm, a nested ELSE's parent target, and a parent ELSE item update.
- Conditions are audited transitively because a nested flag may choose an ELSE path whose camera test can exit the parent before an item update. Dropping that flag would lose a real dependency even though its own branch ends before the update. A three-level fixture verifies that only the closed innermost camera branch is removed, while both active flag dependencies remain.
- A reachable opcode00 in an IF region prevents applying a narrow lifetime. A dedicated fixture verifies that true ends the whole procedure while false reaches a later item update. A depth-zero ELSE test remains conservatively relevant to later source writes; fixtures verify unresolved camera tests block item and door initializers both inside the ELSE and after it. This conservative lifetime alone does not satisfy the existing requirement for a captured guard on a non-init item mutation.
- Regeneration changes only dependency masks and diagnostic reasons in `ROOM1050`, `ROOM1051`, `ROOM10D0`, `ROOM10F0`, and `ROOM10F1`. The source hashes for those exact owned files remain recorded in their manifest rows. All source signatures, decoder statuses, item/AOT acquisition IDs, mutable fields and cache-eligibility booleans are unchanged. All 31 item-eligible rows are byte-identical. Item eligibility remains 31/43 and door eligibility 30/43.
- ROOM1050's shared mask at `0x800C300F` narrows from `0xC0` to `0x40`. ROOM1051's masks at `0x800C300F` and `0x800C86AB` narrow from `0x30` to `0x10` and from `0xE0` to `0x40`. ROOM10F0/10F1's masks at `0x800C86AB` narrow from `0xF8` to `0xE8` and from `0x03` to `0x01`. Isolating door roots in an analysis-only in-memory copy verifies that the removed shared bits in door-eligible ROOM1050/10F1 are not door dependencies. The modified copies never enter production or Git.
- Dining Room's spurious main-camera blockers are removed. Its genuine opcode10 condition remains at `0x28374` in ROOM1050 and `0x284DC` in ROOM1051. ROOM1051 also retains its event-driven door updates; the conservative procedure-end audit adds event-camera diagnostics at `0x286B2/0x286D8`, without changing its already-false door eligibility.
- Reproduction: run `tools/build_cache_metadata.py` against the owned SLUS-00551 CUE with the committed profile. Compare all 43 rows with the parent commit, allowing only the five listed rows' dependency/reason fields and the new research reference. The regenerated manifest SHA256 is `1d5e29575d66500ca315de6cdd7d20b5eb5baadefdfaa7cc08f02b9f50b9a2b9`. The unaffected item table remains SHA256 `c096fde64662cc8e8fdeeb8e30d810cd75c6e4c03a08710d9171c84adedf7617`. The comparison report is `/tmp/tasks/re-map/nested-conditions/regeneration-audit.json`, outside Git.

Limits: this is a source-derived cache dependency correction, not confirmation of new pickups, cleared rooms or runtime door behavior. Flattened event operations do not retain enough procedure context to narrow every procedure-ending predicate; such cases keep conservative later-source dependencies. This analysis does not establish arbitrary nonstructured IF-stack behavior, solve the remaining picked/used-item comparisons, repair other event decoder gaps, or extend the map to other floors. No additional revision or new save/load experiment is covered.
History:

- 2026-10-01; Codex root, GPT-6.1 Sol; reproduced unrelated camera/flag scope failures before the implementation change, inspected the pinned stack handlers and runner, added the guard analysis and fifteen regression cases, audited all regenerated rows, and reviewed the final diff. All 226 tests passed in 9.40 seconds; scoped Ruff lint and formatting checks passed for both changed Python files. The project has no configured formatter or linter.
- 2026-10-01; Gemini 3.8 Flash High via agy; reviewed the supplied initial branch-analysis diff and synthetic cases. Its depth-zero ELSE finding was verified against the pinned runner and corrected with item/door regressions for later initializers. Its requested own-ELSE-arm coverage was added. Root also verified that retaining a parent's combined two-arm extent is necessary when a nested ELSE test selects a parent ELSE item update, and added that regression. This review did not run gameplay or reproduce the source extraction.
- 2026-10-01; Claude Opus 4.6 Thinking via agy was unavailable due quota exhaustion. Gemini 3.1 Pro High timed out after five minutes without a usable review. Neither returned findings or an endorsement. Final corrections and checks were performed by Codex root, GPT-6.1 Sol.


## RE1-LOAD-001: room loader executes init synchronously before returning

Status: Candidate; lifecycle source inspection only
Scope: SLUS-00551 executable identity in RE1-SCD-005; potential snapshot readiness checks
Environment: read-only pinned executable and all 43 Mansion init sections
Authored: 2026-09-30; Codex subagent `/root/remake_items`; model: GPT-6.1 Sol
Basis: primary instruction inspection and unconditional source initializer audit
Claim: room loader `0x80044138` resets AOTs at `0x80044198`, loads/relocates the RDT at `0x800444AC`, executes init through `0x800489CC` at `0x800445FC`, runs one event tick at `0x80044610`, and returns at `0x80044844`. The item initializer raises the inclusive AOT bound even when its acquisition flag disables the handler. Source/header/AOT consistency alone does not make a read atomic or prove init has finished.
Evidence: every scanned Mansion source has an unconditional door AOT0 as its first init command, init+2. This excludes a fully reset registry if the descriptor matches the current source, but it cannot prove later items initialized. The SCD pointer at PS1 VA `0x800CF640` is advanced to the final zero-length procedure sentinel by `0x80048AB4..0x80048AD0`. A combined door/source witness and this pointer could distinguish partial init, but door replacement and later event use require a separate audit.
Limits: no ready gate was implemented or runtime-tested. A guaranteed high-water slot alone may be registered before lower-slot items and is not a complete readiness proof. No invented timer or artificial state flag is authorized by this finding.
History:
- 2026-09-30; Codex subagent `/root/remake_items`, GPT-6.1 Sol; inspected the loader and initializer; reported the bounded lifecycle candidate without changing production readiness behavior.

## RE1-ENGINE-001: shared reconstruction of entered rooms from scripts and fresh flags

Status: Candidate; pinned source inspection, synthetic regressions and comparison with donated RAM captures
Scope: Resident Evil Director's Cut USA SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`; 334 bounded RDT sources for 159 logical Main/Sub pairs
Environment: Python 3.14.7, pytest 9.1.1 and Capstone 5.0.9; owned-disc extraction and existing Herb/Chemical captures from DuckStation `0.1-11894-gc66b2694d`; no new emulator session
Authored: 2026-10-01; Codex root; model: GPT-6.1 Sol
Basis: primary executable inspection, generated semantic rules, synthetic branch experiments and existing controlled RAM comparisons
Claim: one RE1 engine can refresh entered rooms from their source-defined interactions and fresh acquisition/story flags. It keeps trusted live descriptors only while their audited global conditions and source selection remain valid. When those conditions change, it reconstructs supported item and door initializers rather than requiring an item-specific rule or carrying the old completion state forward.

Evidence:

- The compiler retains semantic operands and command boundaries from bounded initialization procedures. It models IF/ELSE/ENDIF, global flag tests and local shadow writes, Main/Sub/character byte comparisons, item and door creators, and AOT handler changes. RE1-CACHE-003 identifies the pinned stack handlers and runner; RE1-FLAG-001 identifies acquisition-bit numbering. No raw script bytes enter the generated program.
- The ten required flag banks remain profile data. Groups 0, 1, 2, 3, 7 and 8 lie in the saved RAM block inspected in RE1-SAVE-002. Only separately audited group-5 bits 8 and 46 are supported outside that block. Character is the byte at PS1 VA `0x800C8669`. Room-local banks 4, 6 and 9, other group-5 bits, and unresolved byte comparisons cannot establish an earlier room's condition from the current room's temporary state. Coincident equal cache bytes do not authorize that reuse.
- Shadow flag writes use physical address and mask because native bank ranges overlap. They never write game RAM. A synthetic cross-bank alias test verifies this invariant. An audit of all 334 initialization programs found no existing write/read alias pair crossing different banks, so this is a preventive interpreter correction, not a reproduced game defect.
- An unresolved predicate explores both native failure and continuation. The engine publishes each slot only when all resulting paths agree. Per-procedure limits of 4096 analysis states and 16 IF frames bound work; exceeding either rejects completeness. These are analyzer budgets, not claims about native stack capacities.
- Any decoded main/event AOT mutation, quantity transfer, or forced handler-1/4/15 dispatch blocks reconstruction for its affected slot. The engine does not replay asynchronous events. Unclassified generic pickup creators or awards without a descriptor reject coverage. A live current-room descriptor can resolve a slot whose initializer condition is unresolved, but absence of that descriptor cannot prove clearance. Expected available items missing from a partially populated live registry also prevent clearance.
- `tests/test_tracking_rules.py` compares reconstructed types, GlobalIds and acquisition states with the donated Herb and Chemical before/after captures. It exercises six GlobalIds across word/byte boundaries, multiple-item clearance, earlier acquisition restoration, absent future items, supported story alternatives, source changes, door replacement, unsupported predicates, failed reads and malformed metadata. The story flag substitutions and earlier-load simulations are synthetic. In the Storeroom test, toggling `0x800C3006 & 0x02` selects Chemical versus Broken Shotgun inside `ROOM1180.RDT`; it does not select a different Storeroom file.
- Polling rechecks the rule bytes, masked source context, acquisition/door flags, loaded-source pointer/header, AOT bound/registry and finally Main/Sub before publication. Regressions change a save-related flag, room, registry or source pointer late in a poll and require Retry without publishing. This reduces mixed snapshots but does not make separate GDB reads atomic.
- Door coverage has its own explicit state and reason in the tracker/map. An unresolved door does not turn an item-cleared room into an item-incomplete room. Source inference refreshes entered rooms only; map reveal still follows observed entry, and collecting a game map does not reveal additional rooms.
- The generation audit reports 334 sources, 159 logical rooms and 298 clean bytecode-coverage candidates. The older conservative cache audit reports 255 candidates, subject to the engine's additional global-context checks. These counts measure static coverage, not confirmed cleared rooms. `ROOM2000.RDT` remains excluded with bad init/main/event ranges. All 43 original Mansion rows retain their source signatures, item IDs, decoder statuses and cache-eligibility booleans. Audit artifact `/tmp/tasks/re-map/shared-engine/generation-audit.json` stays outside Git.

Limits: this is bounded initialization reconstruction, not a complete RE1 VM. Unmodeled commands contribute uncertain return paths; native callback side effects and asynchronous changes do not receive invented rules. Clean bytecode decoding alone does not confirm every condition, native callback, pickup or door. No new natural story event, normal save/load, walked transition or other character/revision was tested. The map still has Mansion 1F geometry only. Visit history still belongs to the tracker session; the engine rereads game-derived state without persisting another copy.
History:

- 2026-10-01; Codex root, GPT-6.1 Sol; generated the semantic rules, implemented shared evaluation and integration, compared donated captures, and inspected the final source/data changes. Validation results are appended below after the final checks.
- 2026-10-01; Gemini 3.8 Flash High via agy; reviewed supplied source and tests without gameplay. Root verified and corrected late poll publication checks, missing door uncertainty, omitted changed door handlers and delayed builder slot validation. Targeted regressions cover each correction and the analyzer budgets.
- 2026-10-01; Gemini 3.1 Pro High via agy; reviewed the same supplied source and tests without gameplay. Root added unresolved-opcode divergence and present/absent live-slot reconciliation cases. Its proposed FC/FD event continuation change was rejected after direct pinned instruction inspection: `0x80026044..0x80026064` decrements the event stack and advances the current event PC by one on the zero-return exit; it does not resume after the saved deferred SCD. Existing repeat/exit scanner tests cover that native behavior.
- 2026-10-01; Claude Opus 4.6 Thinking via agy; final review unavailable because its eligibility request returned service error 503. It supplied no usable review or endorsement. Root verified the returned Gemini candidates and performed the final review.
- 2026-10-01; Codex root, GPT-6.1 Sol; final suite passed 259 tests in 11.99 seconds. Scoped Ruff lint and formatting checks passed for all 13 changed Python files, and `git diff --check` passed. The project has no configured formatter or linter; these Ruff runs were explicit manual checks. No new runtime/save files or raw game sources enter the feature commit.


## RE1-SOURCE-002: indexed-event relocation belongs in loaded source identity

Status: Candidate; pinned relocation instructions and existing RAM comparisons
Scope: the SLUS-00551 executable identity in RE1-ENGINE-001; loaded init/main/indexed-event sections
Environment: read-only pinned executable, owned RDTs and donated Herb/Chemical RAM; no new GDB experiment
Authored: 2026-10-01; Codex root; model: GPT-6.1 Sol
Basis: primary executable inspection, exact source comparison and synthetic corruption tests
Claim: source binding must include the indexed-event section, normalizing only its proven pointer relocation and the audited item fields in RE1-SOURCE-001. Each original nonzero event-table u32 becomes `loaded_rdt_base + events_offset + original_relative_pointer`. Other event bytes remain exact except the separately declared item parameter/quantity mutations.

Evidence:

- Loader instructions `0x80044BA4..0x80044BD8` read each nonzero event-table entry, add the event-section base, store it back, and advance by four bytes until the zero sentinel. The matcher requires this exact relocated value, then restores the original integer for hashing. It does not accept an unrelocated nonzero pointer as initialized source identity.
- The existing Herb capture differs from its owned event source in 40 pointer bytes, all accounted for by these declared relocations. Its event payload matches after normalization. The Chemical source has an empty event table and matches exactly. These compare existing captures, not a newly observed loader execution.
- `tests/test_tracking_rules.py` and `tests/test_room_cache.py` reject a corrupted relocated pointer, an unrelated changed event byte, malformed section bounds, overlapping mutable fields and invalid pointer declarations. Exact init/main matching and rejection of unsupported item parameter values remain intact.

Limits: normalization authorizes source identity, not event execution or item completeness. Quantity-changing slots still require live observation. Unknown or malformed event flow remains unresolved. The evidence covers the named captures and source instructions, not every loaded room or revision.
History:

- 2026-10-01; Codex root, GPT-6.1 Sol; extended source metadata/matching to indexed events, inspected relocation stores and added exact corruption regressions. RE1-SOURCE-001 retains its original authorship and item-mutation evidence.


## RE1-SELECT-001: complete source choices for supported logical rooms

Status: Candidate for unplayed areas; pinned loader rule and owned-disc catalog audit
Scope: the SLUS-00551 executable identity in RE1-ENGINE-001; Main 0 through 6 and supported Sub IDs
Environment: read-only executable and owned-disc catalog; existing Mansion captures only
Authored: 2026-10-01; Codex root; model: GPT-6.1 Sol
Basis: primary loader instructions, catalog correspondence and synthetic selector tests
Claim: the tracker can generate and validate all four variant/alternate source choices for each supported logical room from the pinned loader tables. A story or mode change therefore selects the appropriate semantic program for an already-entered room without guessing its filename.

Evidence:

- RE1-STAGE-001 establishes the nine-entry-per-Main whitelist at PS1 VA `0x80010670` and the alternate flag, PS1 VA `0x800C3006` mask `0x02`. Only a matching Sub selects Main+7. The loader reads a u16 file ID at `0x80090BC8 + stage*64 + Sub*2` and a selector byte at `0x80090F48 + stage*32 + Sub`.
- Instructions `0x800448AC..0x800449A4` use the base file ID directly for selected stages 5, 6, 12 and 13; other stages use base+1. If the selector byte is zero, they also add word `0x800C3000` bit 23, equivalent to byte `0x800C3002` mask `0x80`. The ISO catalog correspondence is file ID+3 as inspected in RE1-VARIANT-002. All addresses are PS1 virtual addresses; table IDs and semantic room IDs are separate values.
- Generation checks all 636 choices for 159 supported logical rooms against the disc catalog, verifies the logical filename prefix and requires a generated source. Startup requires unique choices and all four cases for every supported room. The executable hash must match before metadata is written.
- The room `00-12` regression checks the fixed alternate source `ROOM8120.RDT`. Storeroom `00-18` is not in the alternate-file whitelist and retains `ROOM1180.RDT`; its internal item branch is separate. The original Mansion source hashes/IDs remain unchanged. Generated manifest SHA256 is `c181ef221d9fc2837141c1bf7bf68b6d998895ab3e917247612a204eab4d280a`.
- Reproduction: run `tools/build_cache_metadata.py` with the owned SLUS-00551 CUE, `data/room_manifest_slus00551.json` output and `profiles/re1_directors_cut_slus00551.json`. The compiler verifies executable identity and validates each semantic program before writing the source choices. No disc, executable or raw script bytes enter Git.

Limits: correspondence for every table choice is a source audit, not natural gameplay validation of other areas or character/scenario changes. `ROOM2000.RDT` has unusable script ranges and receives no supported choices. This does not provide geometry, room names or complete native-event coverage outside Mansion 1F. RE1-VARIANT-002 and RE1-STAGE-001 retain their original runtime limits.
History:

- 2026-10-01; Codex root, GPT-6.1 Sol; independently checked both fixed-base branches in the pinned loader, generated every supported choice, audited the original Mansion rows and added source-selection regressions. No gameplay was performed outside the existing captures.


## RE1-ENGINE-002: recurring scripts and possible event histories share item/door rules

Status: Candidate; pinned source inspection, synthetic regressions and existing donated-capture checks
Scope: Resident Evil Director's Cut USA SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`; generated programs for 334 bounded RDT sources
Environment: Python 3.14.8, pytest 9.1.1 and Capstone 5.0.9; owned executable/disc and existing Herb/Chemical captures from DuckStation `0.1-11894-gc66b2694d`; no new emulator or GDB experiment
Authored: 2026-10-02; Codex root; model: GPT-6.1 Sol
Basis: primary executable inspection, source-derived semantic programs, abstract interpretation, synthetic tests and comparisons with donated RAM
Claim: the shared engine can account for recurring main-script updates and possible indexed-event descriptor changes without blocking every affected slot. Fresh persistent flags select supported recurring updates. Earlier main/event writes remain possible until a current update overwrites them or all possible states agree. Completed inventory/map awards use the game's acquisition bit; event timing is not inferred from that bit.

Evidence:

- The pinned loader reads relocated header offsets `0x60/0x64/0x68` at PS1 VAs `0x80044B7C..0x80044BA0`, storing the main pointer at `0x800B9E9C`. The main loop loads that pointer and calls runner `0x800489CC` at `0x80029FF0..0x80029FFC`, then ticks indexed events at `0x8002A000..0x8002A004`. The compiler now retains bounded main procedures alongside init procedures; both pass the same mandatory command/branch schema. Startup checks main and event effects against their own source ranges and acquisition width.
- Opcode `0x12` at `0x80045BC4..0x80045C34` advances ten bytes and writes handler, mode and three u16 registry fields while preserving the source pointer. Opcode `0x13` at `0x80045C38..0x80045C84` advances four bytes and writes handler/mode only. Both return one. The item identity used by completed pickups remains in the source descriptor identified in RE1-COVER-002. A regression verifies the extended setter updates availability without replacing that source GlobalId with its copied registry operand.
- Opcode `0x24` at `0x800470B8..0x80047120` dispatches the selected AOT callback and returns one. Opcode `0x2D` calls it, updates pending interaction bits and returns zero at `0x80047AE0..0x80047B14`. That zero follows the native IF failure path. Normal callback 4 at `0x80037B80..0x80037BB0` selects/queues an item interaction; completed take clears the acquisition bit at `0x8002CDF4..0x8002CE04`. Map callback 15 clears it at `0x800385A8..0x800385B8`. The tracker reads the completion result and does not grant an item by replaying the command. Dormant uncollected descriptors with a scripted award remain unresolved because their event progress can affect current availability.
- Before current main rules run in the analyzer, each relevant slot receives an overapproximation of possible historical main/event writes. This prevents a false guard from erasing a retained earlier effect. Current setters can establish a common state across those histories. After main evaluation, possible event writes are applied again because the event tick follows main. Independent slots remain independent, and a 256-descriptor-per-slot budget rejects only an overflowing slot. Existing procedure/state budgets remain in force.
- Event writes are optional and may occur in any order or repeat. Their historical guards, event activation and timing are deliberately not reconstructed from current flags. The compiler retains all decoded item/door creators and handler setters as possible effects. It retains hard barriers for live quantity transfers and forced door callbacks. Unclassified creators and partial decoding still reject coverage.
- Item-state agreement compares interpreted identity, quantity and acquisition/availability rather than requiring identical handler/mode tuples. A mode-only event write therefore need not erase a known item. A cleared acquisition bit can resolve supported handler alternatives as Taken. Wrong map/inventory handler combinations remain unresolved, and source identity changes do not collapse into an invented item name.
- A validated `Door_set` source with live handler zero now remains a disabled door observation. Handler zero cannot dispatch its door interaction, so the map preserves its marker as Blocked with text `Passage is unavailable`. Live registry mode replaces the initializer's mode in both active and disabled observations. Reconstructed disabled doors have an explicit separate collection; no fake lock bit or hidden packet marker is introduced. Current-room validation checks expected active and disabled states separately, so a partial registry mismatch cannot establish complete door coverage. Door uncertainty still does not change item clearance.
- `tests/test_event_tracking.py` exercises recurring multi-item/door flag branches and reversal, fresh flags after init shadow writes, one-way retained updates, temporary-flag rejection, allowed group-5 bit isolation, optional event writes, conflicting creator order, independent-slot budgets, forced ordinary/map awards, opcode-2D failure, extended setters, undefined flag writers, failed reads, and disabled-door publication into the map. Its replacements are synthetic. Existing controlled Herb/Chemical cases still compare real donated captures, with their original provenance preserved.
- Regeneration adds 217 main procedures and 607 event effects across 156 sources; 55 sources contain scripted normal/map award slots. It replaces 779 blanket mutable-slot barriers with 74 remaining hard barriers. These are source/analysis counts, not 705 confirmed runtime cases. All source signatures/ranges, source choices, decoder statuses, item IDs, mutable-field declarations and old cache-eligibility fields remain unchanged. Manifest SHA256 is `9028af6e877f24d9f5d78e5393235be07ebaf1d79e61bf0cf5b89850ac51e49f`.
- A static projection under the existing Herb-before flag snapshot resolves previously blocked item slots in 40 source variants and door slots in eight variants. It evaluates the old and new rules for all 334 sources in 0.106 seconds on this host. This is an offline implementation probe, not a live polling-latency measurement or gameplay validation of those rooms. Reproduction uses the owned CUE with `tools/build_cache_metadata.py`, the committed profile and manifest output. Detailed generation/projection audit is `/tmp/tasks/re-map/event-tracking/generation-audit.json`, outside Git.

Limits: no new natural puzzle event, door unlock, normal save/load, story progression or alternate character was played. Main/event histories are deliberately wider than current control flow and can retain an unresolved candidate even when its current branch is unreachable. Native callbacks beyond the audited award behavior, event scheduling, temporary-room predicates, dynamic quantities and undecoded scripts remain unfinished detection work. Generic opcode-0x0D door descriptors still produce an explicit recoverable unsupported-source result; no such creator was found in the generated 334 programs. No other revision or new floor-plan geometry is covered. This extends RE1-ENGINE-001's initializer model without promoting its runtime coverage to Confirmed.
History:

- 2026-10-02; Codex root, GPT-6.1 Sol; inspected the native main caller, setters and award return paths; implemented recurring interpretation, conservative histories and explicit disabled doors; generated/audited metadata and added the synthetic/regression cases above.
- 2026-10-02; Gemini 3.8 Flash High via agy; reviewed supplied code and tests without gameplay. Root verified the active/disabled-door mismatch and corrected it, rejected unsupported flag writes as side effects rather than predicates, and added bit-isolation/extended-setter cases. Its standard IF/ELSE/ENDIF double-pop claim was checked against `0x80044CC4..0x80044D50`: both ELSE and ENDIF decrement depth unconditionally, so an extra ENDIF at empty depth wraps native depth to `0xFF`; the analyzer correctly rejects that unsupported stack path. Its key-label claim was rejected because `parse_door` assigns lock_type from byte 24, not byte 14. Strict source ranges retain the native section sentinels; zero-length sections are excluded, not silently bound. Generic doors remain an explicit unsupported case rather than a guessed decoder.
- 2026-10-02; Claude Opus 4.6 Thinking via agy; review unavailable with quota error 429. Gemini 3.1 Pro High via agy timed out after five minutes without a usable review. Neither supplied findings or an endorsement. Root performed the final inspection and verified the available review candidates directly.
- 2026-10-02; Codex root, GPT-6.1 Sol; final verification: all 279 tests passed in 13.31 seconds using `/tmp/re-map-check/bin/python -m pytest -q`. The nine changed Python files passed manually scoped Ruff lint and formatting checks; no project formatter or linter is configured. `git diff --check` passed, and the final manifest hash matched the generation audit above. These checks validate the implementation and existing capture regressions, not new gameplay behavior.
- 2026-10-02; Codex root, GPT-6.1 Sol; RE1-EVENT-004 narrows independent event writes inside the synchronous full-list dispatch boundary while retaining conservative histories between dispatches. RE1-SCD-015 separately removes forced-door descriptor barriers. These revisions preserve this entry's original source/synthetic provenance and do not confirm additional gameplay.

## RE1-SCD-007: native command results and effects govern shared reconstruction

Status: Candidate; pinned executable inspection and synthetic regression tests
Scope: Resident Evil Director's Cut USA SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`; init/main programs for 334 bounded source variants
Environment: Python 3.14.8, pytest 9.1.1 and Capstone 5.0.9; owned executable/disc and existing Herb/Chemical captures from DuckStation `0.1-11894-gc66b2694d`; no new emulator or GDB experiment
Authored: 2026-10-02; Codex root; model: GPT-6.1 Sol
Basis: primary executable inspection, source-derived semantic metadata, synthetic tests and an offline projection using existing capture flags
Claim: commands with an audited nonzero result can continue through the shared item/door interpreter. Native predicates retain their supported result or both unresolved outcomes. Reached unsupported effects reject reconstruction. Relevant variable/flag changes require explicit rules; visual/audio effects are not replayed.

Evidence:

- The native dispatch table is at PS1 VA `0x80091108`. The runner at `0x800489CC..0x80048AEC` calls the selected handler at `0x80048A40..0x80048A6C`. A nonzero result continues; zero leaves the current IF block or ends the procedure. Treating every previously unclassified setup command as a possible zero result therefore introduced impossible branches. All instruction addresses below are PS1 virtual addresses in the executable named above.
- The following 37 handlers return one for their decoded supported forms. Their native setup work is separate from the modeled item/door descriptors. Event activation by `14` remains represented by RE1-ENGINE-002's possible event effects. Local flag aliases listed below are explicitly forgotten rather than retained from an earlier shadow write.

| Opcode | Native handler entry |
| --- | --- |
| `0B` | `0x800452F4` |
| `0E` | `0x80045160` |
| `14` | `0x80045C88` |
| `15` | `0x800453A4` |
| `16` | `0x8004574C` |
| `17` | `0x800458F4` |
| `19` | `0x80045B10` |
| `1B` | `0x80046420` |
| `1F` | `0x800467A0` |
| `20` | `0x80046C2C` |
| `21` | `0x80046CD4` |
| `25` | `0x80046AF8` |
| `27` | `0x8004582C` |
| `28` | `0x80047124` |
| `2A` | `0x800475FC` |
| `2B` | `0x80047A10` |
| `2F` | `0x800456B4` |
| `30` | `0x80047B18` |
| `32` | `0x80047BE0` |
| `33` | `0x80047324` |
| `34` | `0x80047C60` |
| `35` | `0x80047D68` |
| `37` | `0x8004534C` |
| `39` | `0x80047F9C` |
| `3A` | `0x80047FF0` |
| `3B` | `0x80048054` |
| `3D` | `0x80047700` |
| `3E` | `0x80047834` |
| `41` | `0x80048334` |
| `42` | `0x80047884` |
| `43` | `0x8004587C` |
| `44` | `0x80045CE4` |
| `45` | `0x800483B0` |
| `47` | `0x80046DE4` |
| `49` | `0x800485D4` |
| `4A` | `0x8004541C` |
| `4B` | `0x8004555C` |

- Indirect writes matter even when the return is one. Message helper `0x80035278..0x8003538C` can mask the little-endian halfword at `0x800CAB00`, so opcode `0B` forgets bank 6 indices 16 through 31. Enemy setup `1B`, including helper `0x80025B18..0x80025C18`, changes the pointer at `0x800CAB14` and counter byte at `0x800C3022`; their bank 6 indices 160 through 191 and bank 4 indices 200 through 207 become unknown. Particle helpers `0x80021FD8..0x8002241C` can replace the u32 record header at `0x800C3024`, so `2A/3D/3E/42` forget bank 4 indices 224 through 255. These are local alias invalidations, not new persistent acquisition flags.
- Camera setters `09/0A`, at `0x80045180..0x800452F4`, set/clear u32 `0x800C3000` mask `0x00100000`. Camera control `23`, at `0x80047044..0x800470B8`, sets it for a nonzero operand and clears it for zero. This is native bank 5 index 11, not a byte-numbered index. The camera rebuild calls scene helpers through `0x80017B28..0x80017B9C`; the analyzer discards earlier shadows in local banks 4/6/9 because those helpers' local results are not reconstructed. Camera predicates remain unresolved.
- Player control `0F`, at `0x80045D38..0x80045E00`, clears the lowest two bits of u32 `0x800C3000`, then ORs its byte operand into that word. Higher bits with zero operands preserve their preceding state. Graphics copy/allocation calls through `0x80030378..0x800305E8` can change local pointers at `0x800CAB14..0x800CAB1F`; their bank 6 indices 160 through 255 become unknown. Tests check both low-bit replacement and a high operand bit.
- Quantity transfer `4C`, at `0x80048634..0x8004878C`, always returns one and advances four bytes. Mode 0 reads the AOT source quantity into a byte variable. Mode 1 writes that variable into the source quantity. Mode 2 reads the source's item type, searches inventory with `0x8002CCB8`, then copies the found quantity into both the byte variable and source. Thus byte 2 is an AOT slot in all three modes, not an inventory item ID. Modes 1/2 retain a live-quantity barrier; mode 0 does not mutate the descriptor. Modes 0/2 forget the destination variable because its live input is unavailable to past-room reconstruction. If mode 2 finds no inventory match, the native value is unchanged; unconditional forgetting is deliberately conservative. Other mode bytes follow a native no-op return path and compile to an explicit constant result.
- Read-only predicates `10/11/1A/1D/22/36/38/3C/3F` retain both outcomes. Their handlers are respectively `0x80045ADC`, `0x80045AA8`, `0x80045B54`, `0x80045A60`, `0x80046E90`, `0x80047DEC`, `0x80047F40`, `0x80048120` and `0x8004824C`. Past-room inventory, selected item, camera, actor, geometry and input state are not inferred from the current room. Supported variable comparisons are separately scoped in RE1-VARS-001.
- Unclassified side effects now stop reconstruction when reached instead of behaving like predicates. The 21 remaining init/main occurrences are inventory removal `2C`, light setup `46`, movie `1E`, unaudited callbacks `24/2D` and particle-pool clear `48`. An unreachable unsupported branch does not invalidate a supported path. This classification does not authorize a scanner-width correction or claim support for those commands. Native stubs `26/2E`, which leave the script pointer/result unchanged, are also excluded from the continuing set.
- Source audit failures are mandatory input to program coverage. Clean instruction decoding alone does not validate opcode `14`'s event index. Invalid event targets now prevent clearance even if a normal pickup follows. This corrects overclaimed source coverage for `ROOM6031`, `ROOM60B1` and `ROOMD0B1`. The `ROOM70C0` rejection instead follows its reached unsupported `46` command.
- `tests/test_command_semantics.py` checks multiple pickups and a door after setup, acquisition rewind, true predicate divergence, reached/unreachable unsupported effects, invalid event targets, scalar/physical flag aliases, local-effect invalidation, camera/player flags, all supported word comparisons, quantity modes/default, and mandatory metadata bounds. These byte packets and RAM replacements are synthetic. Existing capture regressions retain their original provenance.
- Regeneration covers the same 334 sources and all 636 loader choices. Against commit `4d2e50b`, every existing source signature, range, decoder status, item ID, mutable-source declaration and cache-eligibility field is unchanged. The 5,105 former uncertain commands become 3,123 constant results, 1,380 local invalidations, 60 additional flag writes, 64 variable-write commands, 42 camera changes, 16 player-control commands, six quantity transfers, 231 word predicates, 162 unresolved predicates and 21 unsupported effects. Manifest SHA256 is `d58fa42e9d1edc99774ac9b1fe0bce201dc69e8db7934f887fee1f0bf5dc0da9`.
- An offline projection under the existing Herb-before flag snapshot changes complete-item source coverage from 233 to 248 variants. Nineteen gain coverage and four reject earlier overclaims; unresolved item slots fall from 184 to 145, and unresolved door slots from 204 to 203. Both generated command sets run through the current evaluator with source stage digit minus one modulo seven and source room digits as the logical room ID. This comparison is not a replay of the previous engine or gameplay in every source. Both evaluations took 0.267 seconds on this host, not a live polling-latency measurement. The script and report are `/tmp/tasks/re-map/command-semantics/audit.py` and `generation-audit.json`, outside Git. Regenerate with `tools/build_cache_metadata.py`, the owned SLUS-00551 CUE and committed profile; compare all fields outside `tracking_program` and the complete source-choice list against `4d2e50b`.

Limits: no new natural story event, door unlock, normal save/load, savestate sequence, alternate character or other-area gameplay was performed. This audits native instruction paths and analyzer behavior; it does not promote commands or variable addresses to confirmed runtime coverage. Unresolved local conditions, dynamic quantities, unsupported effects and incomplete source decoding still prevent clearance. Room visit/reveal behavior and map geometry are unchanged. No other revision is covered.
History:

- 2026-10-02; Codex root, GPT-6.1 Sol; inspected the pinned dispatch table, handler returns and relevant direct/indirect writes; implemented shared semantics, regenerated source metadata and added regressions. Primary instruction excerpts remain outside Git at `/tmp/tasks/re-map/command-semantics/native-handlers.txt`; the executable hash and instruction locations above identify the reproducible evidence.
- 2026-10-02; Gemini 3.8 Flash High via agy; reviewed supplied source and tests without tools or gameplay. Root verified its mode-0 quantity barrier finding against `0x800486C4..0x800486F8` and removed that barrier. Root also added explicit native default-mode compilation, semantic mode validation and quantity/high-control-bit regressions. Its proposed mode-2 item-ID interpretation was rejected by descriptor lookup `0x80048704..0x80048718` and source quantity store `0x80048758`. Retaining initializer scalar shadows into recurring main evaluation would assert stale state; they remain discarded under RE1-VARS-001's history limit. Camera writes are unconditional set/clear and need no prior RAM value; later persistent flag predicates already contribute their own snapshot reads. Word-operator regressions were added during primary inspection before the review returned.
- 2026-10-02; Claude Opus 4.6 Thinking via agy; review unavailable with quota error 429. Gemini 3.1 Pro High via agy timed out after five minutes without usable output. Neither supplied findings or an endorsement. Root checked the available review candidates against the pinned executable and performed the final inspection.
- 2026-10-02; Codex root, GPT-6.1 Sol; all 335 tests passed in 13.48 seconds with `/tmp/re-map-check/bin/python -m pytest -q`. The seven changed Python files passed manually scoped Ruff lint and formatting checks; the project has no configured formatter or linter. `git diff --check` passed. These checks cover implementation and existing captures, not new gameplay validation.
- 2026-10-02; Codex root, GPT-6.1 Sol; RE1-SCD-008 subsequently corrects opcode `47`'s decoding advance and the malformed synthetic `3D` packet in this feature's local-effect test. It adds an assertion that the test's source coverage is complete before accepting its unknown flag result. Original native-effect evidence and author provenance remain unchanged.

- 2026-10-02; Codex root, GPT-6.1 Sol; RE1-SCD-009 through RE1-SCD-014 replace the remaining-effect classifications with audited lighting/movie/pool rules, conservative inventory returns and supported callback effects. The original 21-unsupported count remains the historical result of RE1-SCD-007. No additional gameplay confirmation is implied.


## RE1-VARS-001: byte and word commands share physical shadow bits

Status: Candidate; pinned address/operand inspection and synthetic alias tests
Scope: the SLUS-00551 executable identity in RE1-SCD-007; commands `06/07/08/1C/31/4C`
Environment: read-only pinned executable and synthetic tests; existing DuckStation captures retain RE1-SCD-007's environment and original attribution
Authored: 2026-10-02; Codex root; model: GPT-6.1 Sol
Basis: primary executable inspection and synthetic comparisons
Claim: native byte variables start at PS1 VA `0x800C8660` with one-byte indexing; word variables start at PS1 VA `0x800C8674` with two-byte indexing and little-endian u16 values. The interpreter can reconstruct supported same-pass writes and comparisons in a physical-bit shadow without writing emulator RAM or treating another room's local scalar values as persistent facts.

Evidence:

- Byte setter `08`, at `0x800450EC..0x80045120`, consumes four bytes, uses byte 1 as its index and stores only the low byte of the u16 at packet+2 into `0x800C8660 + index`. Word setter `31`, at `0x80045124..0x8004515C`, consumes four bytes and stores packet+2's u16 into `0x800C8674 + 2*index`. Both return one. The profile requires both bases explicitly and validates their full u8-index address ranges inside PS1 RAM; word alignment and character offset 9 are mandatory.
- Word predicate `07`, at `0x80045048..0x800450E8`, consumes six bytes, ignores packet byte 1, uses byte 2 as the index, byte 3 as the comparison and packet+4's little-endian u16 as the expected value. It loads the actual word with `lhu`. Comparison codes 0 through 5 are equality, greater-than, greater-or-equal, less-than, less-or-equal and inequality. Both operands are nonnegative halfwords, so high-bit values compare unsigned. Tests use `0xFFFF` and `0x8000`, nonzero padding and all six operators. Other comparison codes remain unresolved rather than copying an incidental native register result.
- Counter setup `1C`, at `0x80046B68..0x80046C28`, consumes six bytes and returns one. It writes byte index 8 from packet byte 1 and word index 2 from packet+2's u16. A nonzero signed counter also sets word index 1 to `0x7FFF` for negative or zero for positive. A zero counter preserves that earlier word. Packet+4 also controls bytes at PS1 VAs `0x800C845D..0x800C845F`, outside the modeled variable/flag banks; their results are not used to claim item or door state.
- Flag and variable shadows use the same physical address/mask keys. For example, word index 16 is PS1 VA `0x800C8694`, also the beginning of persistent flag bank 1. A later flag clear overrides a preceding word write through that alias. Each supported word value occupies 16 individual little-endian physical bits. Neither setter changes emulator memory.
- Byte predicates use the established logical Main/Sub and fresh character byte only for indices 0/1/9, with same-pass shadow changes applied afterward. Other byte predicates remain unresolved. Word predicates are resolved only for indices below 16 and only when all 16 bits were written in the current analysis pass. Higher indices overlap other saved structures and are not promoted to scalar predicates by this feature. No new whole variable-bank read is added to polling.
- At the init-to-recurring-main boundary, initializer flag and variable shadows are discarded. Current persistent flag tests use the fresh snapshot; scalar state is unknown until current main commands write it. Earlier main/event ticks can change a scalar after initialization, and historical descriptor reconstruction does not reconstruct those scalar histories. Carrying the initializer value forward would therefore permit false availability conclusions. Regressions verify both same-pass resolution and rejection of stale initializer/current-other-room values.
- Quantity copies `4C` modes 0/2 explicitly replace the destination byte shadow with unknown, so a preceding known character write cannot authorize a later comparison after a live quantity read. Native quantity and default-mode behavior is documented in RE1-SCD-007.

Limits: these addresses and effects are Candidate source findings for the pinned executable. There is no new controlled variable dump or natural puzzle test. Same-pass reconstruction does not establish persistent variable lifetimes, earlier event timing or higher-index scalar semantics. RE1-SCD-005 retains its original command-width provenance.
History:

- 2026-10-02; Codex root, GPT-6.1 Sol; inspected native byte/word loads/stores and counter direction writes, added required profile fields, physical-bit shadow effects, comparison and history regressions. The final implementation checks and external-review scope are recorded in RE1-SCD-007.
- 2026-10-02; Codex root, GPT-6.1 Sol; RE1-EVENT-004 extends same-pass byte comparisons to fully written scalar shadows, including block-local progress values. Unwritten bytes and higher-word limits remain unresolved. No new variable-bank memory read or runtime confirmation.

## RE1-SCD-008: complete native dispatch audit separates PC advance and read bounds

Status: Candidate; pinned instruction/dispatch inspection and synthetic decoder regressions
Scope: Resident Evil Director's Cut USA SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`; all 81 SCD dispatch entries `00..50`
Environment: Python 3.14.8, pytest 9.1.1 and Capstone 5.0.9; read-only owned executable/disc and existing Herb-before RAM from DuckStation `0.1-11894-gc66b2694d`; no new emulator/GDB experiment
Authored: 2026-10-02; Codex root; model: GPT-6.1 Sol
Basis: primary executable inspection, source regeneration, mandatory decoder bounds and synthetic tests
Claim: native command PC advances, operand-read extents and branch targets are separate constraints. The shared scanner must use the pinned advances, require every audited immediate operand read to fit its source window, and reject nonadvancing or null dispatch. This corrects three remaining fixed widths and the sound command's native default form without inventing item-specific rules.

Evidence:

- Dispatch entries are little-endian u32 pointers at PS1 VA `0x80091108 + 4*opcode`. The named executable hash was checked before inspection. Every entry's direct PC updates and operand loads was inspected; variable-form jump tables and fixed-count loops were checked separately. Instruction addresses below are PS1 virtual addresses. This audits source behavior, not runtime execution of all commands.
- Opcode `40`, at `0x8004828C..0x80048330`, writes `source+16` to the script PC at `0x8004829C..0x800482A0`. Its last `lh`, at `0x80048320`, reads `source+16..17`. Thus an 18-byte serialized-field guess consumed the next instruction, while a 16-byte PC span alone would miss a possible operand overread. Decoding now returns a 16-byte command only when all 18 readable bytes exist. A branch can legally target bytes also read by the preceding command; those bytes are not part of its PC interval.
- Opcode `46`, at `0x800483EC..0x80048520`, advances two header bytes, three 12-byte light records and three u16 values. The loops at `0x80048420..0x800484AC` and `0x800484C8..0x800484EC` have fixed count three. Total advance/read coverage is 44 bytes, replacing the old 46-byte format guess.
- Opcode `47`, at `0x80046DE4..0x80046E8C`, writes `source+14` at `0x80046DF4..0x80046DF8`; its last u16 load at `0x80046E70` ends at source+14. The old 16-byte width skipped the next opcode. Its existing continuation/effect classification in RE1-SCD-007 is unchanged.
- Sound `17`, at `0x800458F4..0x80045A5C`, first advances six bytes. Source selector is the low byte at packet+4. Selectors 0..3 additionally advance to source+10, including forms that do not use the coordinate words. Other selectors follow `0x80045950/0x8004596C` to the common return at `0x80045A50`, leaving PC at source+6 and returning one. The scanner now explicitly decodes that native default rather than rejecting it as an unspecified width.
- The enemy-property jump table at `0x80010770` retains advancing selectors `{0:6,1:8,2:6,3:6,5:6,6:4,8:4,9:6,10:6}`. Selectors 4/7 and values outside the table reach `0x8004731C` without a PC update. The player-property table at `0x800107A0` retains `{0:2,1:4,3:4,4:2,5:4,6:2,7:2,8:4,9:4,10:4}`. Selector 2 and out-of-range values return at `0x800475F4` without advancing. These remain explicit unsupported forms; no finite no-op width is invented.
- Fixed stubs `26`, at `0x80045824..0x80045828`, and `2E`, at `0x8004539C..0x800453A0`, leave PC and return register unchanged. Their prior nominal one-byte widths could expose a following pickup that the native loop never reaches. Entries `4F/50` are null pointers, not two-byte instructions. Both kinds now reject decoding, including single/deferred event dispatch. The graphics command `4D` does advance two bytes at `0x80048928..0x80048950`; a preliminary excerpt ending at `0x80048910` was incomplete and is not evidence of a nonadvancing handler.
- Terminal `00` reads no operands and clears native IF depth. The walker records its one-byte opcode and stops that path. ELSE `02` requires its byte-1 operand and jumps to source+byte1; its two-byte decoding extent is not a fixed sequential advance. Existing branch validation rejects an exit inside the command or outside the procedure. All other supported direct operand loads fit inside the audited advance. Skipped padding still must fit the procedure's PC interval.
- Procedure walking and semantic compilation use identical read windows. An explicit `operand_tail` contains the remaining bytes of the same source section, permitting `40` to read a following instruction, procedure header or sentinel. Instruction flow remains bounded by the current procedure body. A tail cannot supply missing instruction bytes. Direct/single/deferred event dispatch already supplies its bounded event-section window independently of wrapper advance, so it uses the same corrected decoder. No memory outside the provided section is used to close a missing read.
- Semantic compilation independently checks both section bounds, procedure lengths, clean decoder results and zero-length sentinels. A caller's complete-source claim cannot authorize a truncated procedure list. Failed embedded SCD blocks contribute no speculative linear candidates and stop their event-analysis path; other indexed entries remain independently inspectable. The existing diagnostic procedure walker can still retain explicitly partial candidates, which cannot establish complete source coverage.
- `tests/test_native_decoding.py` verifies multiple pickups and a door after `40/46/47`, a branch into the overlapping `40` read, missing final halfwords, a readable but non-executable tail, procedure sentinels, compiler/scanner agreement, native sound defaults and null/nonadvancing event rejection. Existing variable-width/alignment tests remain. The earlier local-effect test for `3D` used an invalid six-byte setup instead of twelve bytes; it now uses the complete packet and asserts source coverage before checking flag invalidation, preventing a malformed-source rejection from passing as a semantic test.

The complete dispatch audit follows. A zero entry is a native null pointer. For fixed advancing commands, the listed advance is also the required bounded PC span. Only `40` needs a larger immediate read window, 18 bytes. Variable selectors and terminal/branch handling are described above.

| Opcode | Native handler entry | Native PC advance |
| --- | --- | --- |
| `00` | `0x80044c5c` | Terminal; no advance |
| `01` | `0x80044c6c` | 2 |
| `02` | `0x80044cc4` | Source + byte 1 |
| `03` | `0x80044d10` | 2 |
| `04` | `0x80044d54` | 4 |
| `05` | `0x80044e54` | 4 |
| `06` | `0x80044fa4` | 4 |
| `07` | `0x80045048` | 6 |
| `08` | `0x800450ec` | 4 |
| `09` | `0x80045180` | 2 |
| `0A` | `0x80045248` | 2 |
| `0B` | `0x800452f4` | 4 |
| `0C` | `0x80045ea8` | 26 |
| `0D` | `0x80045e00` | 18 |
| `0E` | `0x80045160` | 2 |
| `0F` | `0x80045d38` | 8 |
| `10` | `0x80045adc` | 2 |
| `11` | `0x80045aa8` | 2 |
| `12` | `0x80045bc4` | 10 |
| `13` | `0x80045c38` | 4 |
| `14` | `0x80045c88` | 4 |
| `15` | `0x800453a4` | 2 |
| `16` | `0x8004574c` | 2 |
| `17` | `0x800458f4` | 10 for sources 0..3; otherwise 6 |
| `18` | `0x80045f28` | 26 |
| `19` | `0x80045b10` | 4 |
| `1A` | `0x80045b54` | 2 |
| `1B` | `0x80046420` | 22 |
| `1C` | `0x80046b68` | 6 |
| `1D` | `0x80045a60` | 2 |
| `1E` | `0x80046730` | 4 |
| `1F` | `0x800467a0` | 28 |
| `20` | `0x80046c2c` | 14 |
| `21` | `0x80046cd4` | 14 |
| `22` | `0x80046e90` | 4 |
| `23` | `0x80047044` | 2 |
| `24` | `0x800470b8` | 4 |
| `25` | `0x80046af8` | 4 |
| `26` | `0x80045824` | No advance |
| `27` | `0x8004582c` | 2 |
| `28` | `0x80047124` | 4/6/8 by selector; unsupported forms do not advance |
| `29` | `0x800466dc` | 2 |
| `2A` | `0x800475fc` | 12 |
| `2B` | `0x80047a10` | 4 |
| `2C` | `0x80047a78` | 2 |
| `2D` | `0x80047ae0` | 4 |
| `2E` | `0x8004539c` | No advance |
| `2F` | `0x800456b4` | 4 |
| `30` | `0x80047b18` | 12 |
| `31` | `0x80045124` | 4 |
| `32` | `0x80047be0` | 4 |
| `33` | `0x80047324` | 2/4 by selector; unsupported forms do not advance |
| `34` | `0x80047c60` | 8 |
| `35` | `0x80047d68` | 4 |
| `36` | `0x80047dec` | 4 |
| `37` | `0x8004534c` | 4 |
| `38` | `0x80047f40` | 4 |
| `39` | `0x80047f9c` | 2 |
| `3A` | `0x80047ff0` | 4 |
| `3B` | `0x80048054` | 6 |
| `3C` | `0x80048120` | 6 |
| `3D` | `0x80047700` | 12 |
| `3E` | `0x80047834` | 2 |
| `3F` | `0x8004824c` | 6 |
| `40` | `0x8004828c` | 16 |
| `41` | `0x80048334` | 4 |
| `42` | `0x80047884` | 4 |
| `43` | `0x8004587c` | 4 |
| `44` | `0x80045ce4` | 2 |
| `45` | `0x800483b0` | 2 |
| `46` | `0x800483ec` | 44 |
| `47` | `0x80046de4` | 14 |
| `48` | `0x800478d4` | 2 |
| `49` | `0x800485d4` | 2 |
| `4A` | `0x8004541c` | 2 |
| `4B` | `0x8004555c` | 2 |
| `4C` | `0x80048634` | 4 |
| `4D` | `0x8004878c` | 2 |
| `4E` | `0x80047950` | 4 |
| `4F` | `0x00000000` | Null dispatch |
| `50` | `0x00000000` | Null dispatch |

- Regeneration retains 335 item-table sources and 334 bounded tracking sources. All 652 initializer entries and 782 door entries in the static item table are unchanged; only decoding diagnostics/counts changed. All 636 loader choices, source hashes/ranges and event relocations are unchanged. Tracking programs change in 27 source variants. Full source coverage increases from 295 to 307 variants; static cache candidates increase from 255 to 257. These are decoder/source-audit counts, not confirmed playable-room coverage.
- Manifest SHA256 is `afa4be2230b75d3f0bb2a72b5996a1a0d63f9ae81280a6c1bfef4c134896d557`; item-table SHA256 is `00ef72741801b9f16722f600a9d56be2b8b42ef1a652cfb71c390be47fcfb3d0`. Reproduction uses `tools/build_cache_metadata.py` with the owned SLUS-00551 CUE and committed profile, plus `tools/build_item_table.py` with the same CUE. Compare generated rows and source choices against commit `ce8df1f`. The detailed audit is `/tmp/tasks/re-map/native-decoding/generation-audit.json`, outside Git.
- Under the same offline Herb-before flags used in RE1-SCD-007, complete item-source coverage changes from 248 to 250; unresolved item slots remain 145, and unresolved door slots fall from 203 to 198. Both command sets run through the current evaluator using source stage digit minus one modulo seven and source room digits. Both evaluations took 0.324 seconds. This is an offline comparison, not live polling latency, prior-engine replay or gameplay across those sources.

Limits: the audit covers this executable's decoder contract, not the effect semantics of every command or the indexed VM's entire instruction set. Unsupported effects still reject reconstruction. No natural story event, save/load, pickup, alternate character or new area was played. Existing captures and source identities retain their original provenance. No other revision, floor-plan geometry or room-reveal behavior is changed.
History:

- 2026-10-02; Codex root, GPT-6.1 Sol; inspected every native dispatch entry, corrected the three fixed advances, modeled the sound default and explicit read tails, rejected nonadvancing/null dispatch, regenerated metadata and added decoder/boundary regressions. Primary disassembly stays outside Git; the executable hash and handler locations above identify the reproducible source evidence.
- 2026-10-02; Gemini 3.1 Pro High via agy; reviewed the supplied decoder/compiler changes and tests without tools or gameplay. Root verified that the compiler trusted its caller's completeness claim and added independent parse/sentinel/section checks. The sole production caller already passed source-audit failures as False; direct-call regressions now enforce the compiler's own gate too. Its claimed failing 18-byte procedure test was rejected by the length-prefixed format and the passing test: 18 includes the two-byte header plus a 16-byte body, leaving the sentinel outside that body.
- 2026-10-02; Gemini 3.8 Flash High via agy; reviewed the same supplied context without gameplay. Root verified the compiler gate and removed speculative candidate recording/continuation after failed embedded blocks. Added malformed-input, sound-truncation, variable-selector and single/deferred-event regressions. Its proposed wider block-tail requirement was checked against the wrapper invariant: block length is at most wrapper width minus two, and the existing window extends another two bytes for the mandatory sentinel, supplying the two-byte `40` overread. A positive embedded-block test reproduces that bound. Existing source-0..3 sound and IF/ELSE tests already cover their alignment/control flow. Full owned-disc regeneration is source evidence and does not substitute for natural gameplay.
- 2026-10-02; Claude Opus 4.6 Thinking via agy; review unavailable with quota error 429. It supplied no findings or endorsement. Both Gemini reviews completed; root checked their candidates directly and performed the final review.
- 2026-10-02; Codex root, GPT-6.1 Sol; final verification passed all 378 tests in 13.92 seconds with `/tmp/re-map-check/bin/python -m pytest -q`. Seven changed Python files passed manually scoped Ruff lint and formatting checks; the scanner's formatting check covers its changed decoder region and preserves the pre-existing CLI formatting. The project has no configured formatter or linter. `git diff --check` passed. Review corrections regenerate the same manifest hash above, and a second offline projection retains the stated coverage counts. No new gameplay or restricted artifacts enter this change.
- 2026-10-02; Codex root, GPT-6.1 Sol; RE1-EVENT-003 supersedes the embedded-block window restriction above. The asserted relationship between procedure length and wrapper width was enforced by the scanner, but the native VM does not enforce it. The native block reader at `0x80027184..0x800271DC` reads the entire procedure list independently of the later wrapper jump. New short-wrapper and multi-procedure regressions use the full bounded event section. This corrects the earlier root response to Flash's wider-window suggestion without changing the original review attribution. Owned-disc regeneration retains the same command payloads under this wider contract.


## RE1-EVENT-003: indexed-event reads, returns and shared depth follow the native VM

Status: Candidate; pinned native instruction inspection, owned-disc regeneration and synthetic event-flow regressions
Scope: Resident Evil Director's Cut USA SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`; the indexed-event interpreter and all 334 bounded tracking source variants
Environment: Python 3.14.8, pytest 9.1.1 and Capstone 5.0.9; read-only owned executable/disc; offline comparison uses the existing Herb-before RAM from DuckStation `0.1-11894-gc66b2694d`; no new emulator or GDB experiment
Authored: 2026-10-02; Codex root; model: GPT-6.1 Sol
Basis: primary native dispatch/operand/control-flow inspection, mandatory source bounds, synthetic regressions and existing-capture projection
Claim: waits, counters, calls and loops share event-stack depth. Source reads and VM jumps require independent bounds. Deferred SCD returns select repeat or exit paths, and the state-0 default is a native event stop. These contracts can improve shared item/door source coverage while retaining explicit failures for nonadvancing states and out-of-section reads.

Evidence:

- The executable hash was checked before inspection. All addresses below are PS1 virtual addresses. Event initialization at `0x80025C1C..0x80025C54` sets state zero and depth `0xFF`. The active event record is `0x34` bytes. Repeat pointers use record+`0x0C + 4*depth`, deferred pointers use +`0x1C + 4*depth`, and u16 counters use +`0x2C + 2*depth`. Each array has four slots. The scanner retains which fields a frame actually initialized and rejects reads of stale fields or a fifth frame.
- The common opcode table at `0x800101A0` is selected before the state switch at `0x80026078`. Thus `F6..FF` keep their common meaning in actor and motion states too. Native handlers and scanner behavior are listed below. Wait duration and event scheduling are not reconstructed; the scanner follows possible command reachability.

| Opcode | Native handler range | Audited control flow |
| --- | --- | --- |
| `F6` | `0x80025D88..0x80025DB4` | Push depth, advance one, yield |
| `F7` | `0x80025DB8..0x80025E0C` | Wait while external conditions hold; otherwise pop depth and advance one |
| `F8` | `0x80025E10..0x80025E54` | Push depth, read u16 at source+2, advance one, yield |
| `F9` | `0x80025E58..0x80025EA8` | Decrement current counter; yield until zero, then pop and advance three |
| `FA` | `0x80025EAC..0x80025F00` | Push counter/repeat pointer; advance four |
| `FB` | `0x80025F04..0x80025F70` | Decrement counter; repeat or pop and advance one |
| `FC` | `0x80025F74..0x80025FCC` | Push source+2 as deferred SCD; jump to source+byte1 |
| `FD` | `0x80025FD0..0x80026064` | Dispatch saved SCD; repeat on nonzero, otherwise pop and advance one |
| `FE` | `0x8002625C..0x80026274` | Advance one and yield |
| `FF` | `0x80026068..0x80026074` | Disable event |

- `F8`'s four readable bytes are distinct from its one-byte advance. Byte 1 normally contains `F9`, but the native VM executes that byte regardless of its value. The old width-four decoder skipped it. The scanner now validates the complete counter read and visits byte 1. A u16 zero starting count wraps to `0xFFFF` after decrement and eventually exits. Collapsing repeated `F9` ticks preserves source reachability because those ticks do not change VM state or source PC. It does not estimate elapsed gameplay time.
- `F7` reads no stored frame field before popping, so it can discard any existing frame. `F9` can consume a counter initialized by `F8` or `FA`. `FB` needs an initialized repeat pointer and counter from `FA`; `FD` needs a deferred pointer and repeat pointer from `FC`. Missing fields are explicit unsupported flow, even though native memory could contain stale values. Reinitialization through state-0 `08` resets state/depth and transfers to the indexed target, preserving RE1-CACHE-002's lack of sequential continuation.
- `FC` has no native minimum displacement of three. A two-byte header is required, its target must remain inside the section, and an overlapping target can execute VM bytes also used by a deferred SCD. Offset-zero recursion exceeds the bounded stack; offsets one/two have synthetic examples with valid flow. Removing the invented minimum does not authorize an out-of-range target.
- SCD `00`, at `0x80044C5C..0x80044C68`, returns zero. `FD` therefore exits without adding a repeat path for it. The 37 continuing handlers in RE1-SCD-007 plus `01/02/03/05/08/09/0A/0C/0D/0F/12/13/18/1C/23/31/40/46/4C/4D` have inspected nonzero returns and cannot expose an `FD` exit path. Flag setter `05` returns one for supported modes and two in its native default at `0x80044F3C..0x80044FA0`; both repeat. Return contracts do not authorize ignoring command effects. Other commands retain both possible return paths. Unsupported operand forms are rejected by the shared SCD decoder before applying a return rule.
- State 0 accepts opcodes `00..09` through table `0x800101C8`. Its default at `0x80026214..0x80026218` clears the current event's active byte and leaves the tick. Bytes after that opcode cannot contribute effects from the same entry. Other indexed entries remain independently inspectable. State 1's default at `0x80026324/0x80026394` reaches `0x80026A8C` without changing PC; state 2's default at `0x80026B34` reaches `0x80026FF0` without advancing. These remain explicit failures. The old cache test's state-0 `0F` is now a proven stop; its unsupported-flow fixture instead enters state 1 before `0F`.
- State-0 embedded block `06`, at `0x80027184..0x800271DC`, calls runner `0x800489CC` with source+2 and only afterward advances the VM by byte 1. Single dispatch `07`, at `0x800271E0..0x80027238`, independently stores that VM jump and dispatches source+2. Neither requires a wrapper width of at least three or confines a procedure list to that width. Blocks now read the full bounded event section through their required zero-length sentinel, including an empty list. The VM advance remains independently bounded; a zero width is unsupported nonadvancing flow. Missing opcodes, lengths, sentinels and operand tails fail explicitly without publishing diagnostic raw candidates. RE1-SCD-008's two-byte `40` operand peek still applies.
- Fixed state widths and direct operand reads were checked against the entire native routines, including jump tables. Their existing widths remain unchanged. The table below records the audited contract. Packet extents require every advanced byte to fit the supplied section, even if the handler does not load padding.

| State | Native dispatch/handler | PC advances and transitions |
| --- | --- | --- |
| 0 | `0x800260B8..0x80026218`; helpers `0x80026FF8..0x80027238` | `00/01/02/03`: 1; `04`: 3; `05`: 4; `06/07`: byte 1; `08/09`: 2. `01` enters state 1, `02/03` enter state 2; `08` reinitializes rather than continuing |
| 1 | `0x800262D0..0x80026A90` | `00/80/82/86/8B`: 1; `81`: 2 or 10 depending on byte 1's low nibble; `83`: 7; `84/85/87/88`: 4; `89/8A`: 2. `80/8B` return to state 0 |
| 2 | table `0x800101F0`, handler `0x80026B14..0x80026FF4` | `00/01/02/03/04`: 1; `05/06/0A`: 4; `07/0B`: 8; `08`: 3; `09`: 2. `01` returns to state 0 |
| 3 | `0x80026A94..0x80026B10` | Advance 2. No source-only transition into this state is currently modeled |

- `tests/test_event_contract.py` covers timed waits and shared-depth exhaustion, stale frame rejection, overlapping counter/header/source bytes, zero/nonzero/unknown deferred returns, empty and multi-procedure blocks beyond wrapper width, mandatory section reads, every supported actor/motion packet boundary, independent entries after termination, and last-item acquisition rewind. These packets and flag replacements are synthetic. The existing `FC/FD` repeat-and-exit test formerly used an item setter with a constant nonzero return; it now uses a flag predicate whose two outcomes justify that test's branches.
- Against commit `baceff0`, regeneration retains all 334 bounded source variants, 636 loader choices, source signatures/ranges, event relocations, item/door operands and semantic command lists. Nine event sources change diagnostics: `ROOM4060/4061`, `5070/5071`, `6010`, `70C1`, `C070/C071`, `D010`, with their corresponding `PSX/STAGEx/` paths. Event sections decoding cleanly increase from 312 to 321. Full program source coverage increases from 307 to 312, item-cache candidates from 257 to 262, and five program payloads change only their completeness boolean. The static item table is unchanged.
- The manifest SHA256 is `aa4a59be0b59d4513de5b183804ef225b60183edfcbf3f90a77c1eaf7863546d`. Reproduce with `tools/build_cache_metadata.py`, the owned SLUS-00551 CUE and committed profile; compare all source fields and choices against `baceff0`. The detailed audit is `/tmp/tasks/re-map/indexed-event-audit/generation-audit.json`. Native instructions, extracted source bytes and review scratch files remain outside Git.
- An offline projection uses the same existing Herb-before flags for old/new metadata through the current evaluator. Complete item-source coverage changes from 250 to 254 variants; unresolved item slots fall from 145 to 141 and unresolved door slots from 198 to 186. Both evaluations took 0.414 seconds together. This is an existing-snapshot comparison, not full-game coverage or live polling latency. `/tmp/tasks/re-map/indexed-event-audit/projection.py` and `projection-audit.json` retain the reproduction and results.
- Thirteen event sections still fail: two nonadvancing state-1 paths, nine paths leaving the declared section, and two indexed pointers outside their section. The native VM does not enforce those section boundaries, but current source binding does; bytes beyond the verified source are not used to invent a terminator. Invalid event creation targets, unsupported effects, unresolved temporary predicates and dynamic quantities still prevent broader completion claims.

Limits: no new natural puzzle/story event, pickup, door unlock, save/load, savestate sequence, alternate character or other-area gameplay was performed. State-3 reachability, arbitrary callback side effects, event scheduling and stale native frame values are not established by these decoder checks. The wider block contract produces no additional owned-disc command payloads. All findings remain Candidate for this exact executable. The map still covers Mansion 1F, and reveal/visit behavior is unchanged.
History:

- 2026-10-02; Codex root, GPT-6.1 Sol; inspected every event-state packet width and direct read, common control handlers, source bounds and relevant SCD return paths. Corrected shared stack, wrapper/read and native-stop contracts; regenerated metadata and added synthetic regressions. All primary captures retain their original attribution.
- 2026-10-02; Gemini 3.8 Flash High via agy; reviewed the supplied production diff, complete scanner/compiler context, native contracts and synthetic tests without tools or gameplay. Root verified its missing state-0/state-1 packet and outstanding-frame termination cases, added regressions, and corrected the shared-frame test's name. A proposed missing deferred-byte success case was disproved by bounded target flow: when an FC header reaches section end, every displacement either recurses beyond supported depth or leaves the section; explicit regressions now cover the end case. Its suggestions to reject a native state-0 stop or all possible unknown-return exits contradicted the inspected stop instructions and the conservative possible-effect policy. Offset-zero FC already fails the shared-depth bound. No review is runtime confirmation.
- 2026-10-02; Claude Opus 4.6 Thinking via agy; review unavailable with individual quota error 429. Gemini 3.1 Pro High via agy timed out after five minutes with no usable review. Neither supplied findings or endorsement; no automatic retry was made. Root verified Flash's candidates directly against source and tests and performed the final inspection.
- 2026-10-02; Codex root, GPT-6.1 Sol; final verification passed all 480 tests in 14.32 seconds with `/tmp/re-map-check/bin/python -m pytest -q`. The project has no configured formatter or linter; all six changed Python files passed manually scoped Ruff lint and formatting checks. `git diff --check` passed. A separate owned-disc regeneration is byte-identical to the committed manifest candidate and retains the SHA256 above. Tests and review scratch files outside Git provide no new gameplay evidence.


## Suggested next experiments

1. Enable `Debug/EnableGDBServer` with port 2345, connect with a small Python GDB client, and read 16 bytes at `0x80000000` while the game idles. Record whether the game keeps running.
2. Move between two known RE1 rooms and poll a small candidate window at 10 Hz. Save the log with game revision and DuckStation version.
3. Take `.sav` files before and after one pickup, decompress with the header logic above, and diff for stable changed bytes.
4. Only if GDB polling fails, prototype Mach `vm_read` against the DuckStation PID for the same addresses and compare maintainability.

## Shared command-effect audit, RE1-SCD-009 through RE1-SCD-014

The six findings below share this provenance:

Status: Candidate; pinned native source inspection and synthetic regressions
Scope: Resident Evil Director's Cut USA SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`
Environment: Python 3.14.8, pytest 9.1.1, Capstone 5.0.9; the original owned executable/disc and existing donated captures from DuckStation `0.1-11894-gc66b2694d`; no new emulator or GDB experiment
Authored: 2026-10-02; Codex root; model: GPT-6.1 Sol
Basis: primary executable inspection, generated semantic programs, synthetic tests and existing capture regressions
Limits: these source contracts do not establish gameplay coverage, natural event scheduling, ordinary save/load behavior or another revision. Native CD/audio work, graphics and inventory mutations are not replayed into emulator memory. Temporary state, unaudited callbacks, quantity writes and incomplete sources can still prevent clearance.

### RE1-SCD-009: light setup continues without changing tracked state

Claim: opcode `46` advances 44 bytes and returns one. It modifies the loaded room's light data, without changing modeled descriptors, flag banks or scalar variables.
Evidence: `0x800483EC..0x80048520` writes three 20-byte light records at loaded-room offsets `0x0C..0x47`, plus color halfwords at offsets 6/8/10. Loader `0x80044860..0x80044874` places that room pointer at PS1 VA `0x800CAB10`; the command only reads the pointer. Helper `0x80068030..0x80068054` calls `0x8006C77C..0x8006C798`, which writes GTE control registers, not RAM. `tests/test_remaining_effects.py` checks multiple items and a door after lighting, and preservation of an earlier flag shadow that aliases the pointer's storage.
History:
- 2026-10-02; Codex root, GPT-6.1 Sol; inspected the command, loader and graphics helper, added the common continuation rule and synthetic regression. No gameplay reproduction.

### RE1-SCD-010: particle clear zeros only the overlapping header halfword

Claim: opcode `48` advances two bytes, clears both header bytes of all 64 particle records and returns one. Only record zero's header overlaps a script flag bank: PS1 VAs `0x800C3024/0x800C3025`, bank 4 indices 240..255. The upper halfword at `0x800C3026/0x800C3027` remains unchanged.
Evidence: `0x800478D4..0x8004794C` initializes the index at `0x800CF62E` to zero, writes byte offsets 0/1 at `0x800C3024 + 132*index`, and loops through index 63. The new `local-flag-clear` rule uses physical shadow bits, sharing state with variable writes and comparisons. Synthetic tests cover both bytes, preservation of the upper halfword, an overlapping word comparison, malformed metadata and deferred repetition.
History:
- 2026-10-02; Codex root, GPT-6.1 Sol; inspected the clear loop, added bounded flag clearing and verified synthetic cases. No live particle event was observed.

### RE1-SCD-011: movie setup establishes control-word bit 17

Claim: opcode `1E` advances four bytes, invokes the movie/audio helper, sets bit 17 of the little-endian u32 at PS1 VA `0x800C3000` and returns one. The script alias is bank 5 index 14. This final set occurs for modes 1/2 and the helper's default modes.
Evidence: `0x80046730..0x8004679C` calls `0x80014C58` and then ORs `0x00020000` into the control word. Helper `0x80014C58..0x80014D10` handles modes 1/2 and returns directly for others. Its setup chain `0x800152A4..0x800154A8`, volume path `0x800154C0..0x80015544` and CD wrapper `0x80015B5C..0x80015C24` change CD/audio buffers and work fields outside the modeled banks. Mode 2 can clear bit 17 internally before the caller sets it again. Synthetic tests cover modes 0/1/2/255, a preceding clear, an unrelated flag and the nonzero deferred result.
History:
- 2026-10-02; Codex root, GPT-6.1 Sol; inspected the native caller/helper chain and implemented its final flag effect. No movie or CD timing was tested in-game.

### RE1-SCD-012: inventory removal has two outcomes and can invalidate scalar aliases

Claim: opcode `2C` advances two bytes, searches for its item-type operand, returns zero if absent, or removes one matching inventory entry, compacts inventory and returns one. It does not reset the world pickup acquisition bit.
Evidence: `0x80047A78..0x80047ADC` calls inventory search `0x8002CCB8..0x8002CD2C` and conditional compaction `0x8002CA0C..0x8002CB78`. Compaction can write count byte `0x800C8667` and selection byte `0x800C8689`, byte-variable indices 7 and 41. It also changes inventory entries at the array selected by `0x800BA008` and inventory-menu work data outside the flag banks. The common interpreter retains both results and forgets count/selection shadows conservatively on either outcome. Synthetic tests cover IF divergence, unguarded procedure termination, both scalar aliases, acquisition reversal and preservation of independent pickups.
History:
- 2026-10-02; Codex root, GPT-6.1 Sol; inspected search/removal/compaction and implemented conservative return/effect handling. No past-room inventory is inferred from the player's current inventory, and no natural removal was played.

### RE1-SCD-013: forced document callbacks conditionally set pending bit 8

Claim: callback 13 sets control-word bit 8 at PS1 VA `0x800C3000`, bank 5 index 23, only when the u16 registry parameter at record offset 2 is zero. It leaves handler, mode, parameter and source pointer unchanged. With an unmodeled parameter, the interpreter preserves a prior true pending bit and otherwise records uncertainty.
Evidence: callback table at `0x80090404` selects `0x80038138..0x80038168` for handler 13. The routine stores the selected AOT pointer at `0x800B7DCC`, branches on its parameter and sets the control word only on the zero path. Synthetic tests cover both command returns, preservation of item/door state, a previously set bit and uncertainty after a prior clear. Callback 12 at `0x800380C0..0x80038134` performs the adjacent parameter toggle; it remains unsupported.
History:
- 2026-10-02; Codex root, GPT-6.1 Sol; rejected an initial unconditional-set/parameter-toggle interpretation after distinguishing callback 12 from callback 13; corrected the rule and added parameter-dependent uncertainty regressions. No callback was activated in-game.

### RE1-SCD-014: forced callback command returns and pending flags are independent

Claim: opcode `24` returns one after callback dispatch. Opcode `2D` dispatches through `24`, sets control-word bit 10, toggles bit 11 and returns zero. This zero can exit a deferred `FD` call and skips a native IF body; it cannot repeat that call.
Evidence: `0x800470B8..0x80047120` advances four bytes, selects the AOT slot and callback table index, then returns one. `0x80047AE0..0x80047B14` applies `(word | 0x400) ^ 0x800` at `0x800C3000` and returns zero. Inventory callback 4 at `0x80037B80..0x80037BB0` conditionally sets bit 11 based on its parameter. Map callback 15 at `0x80038578..0x800385F8` disables its handler, clears the selected acquisition bit and writes item type into byte-variable 19, `0x800C8673`. Helper `0x80033D48..0x80033D6C` sets bank 8's map ownership index, `124 + item_type - 0x4E`. The interpreter requires supported map descriptors before using their flag targets and discards preceding shadows only at those targets. Fresh acquisition flags remain authoritative; it does not grant a synthetic map. Other callback IDs remain explicitly unsupported. Tests exercise known zero/nonzero deferred returns, pending-bit ordering, parameter-dependent uncertainty, invalid map types and untouched ownership bits.
History:
- 2026-10-02; Codex root, GPT-6.1 Sol; rechecked return paths already recorded in RE1-ENGINE-002, extended the common pending/alias effects and the indexed scanner's zero-return contract. No callback was activated in gameplay.

### Shared command-effect generation and regression audit

- The same 334 bounded sources and 636 loader choices were regenerated from the owned CUE. Compared with `c31bb4f`, all source hashes/ranges, decoder status, cache eligibility, event effects, item/door identities, acquisition IDs, mutable-source declarations and program coverage flags are unchanged. Seventeen programs change only their init/main semantic command classification.
- All 21 previous unsupported init/main effects are classified: 12 light continuations, two movie flag writes, two uncertain inventory removals, one pool clear and four parameter-dependent callback-13 effects. This does not prove that every room is resolved; unsupported effects can still arise in a newly decoded source or an unaudited callback, and independent conditions remain unresolved.
- Manifest SHA256 is `6514c3c7e7b37ecdabd45e66565b76f2719d4f954b46caed21cddcb514f237bb`. Detailed generation and projection audits are `/tmp/tasks/re-map/remaining-effects/generation-audit.json` and `projection-audit.json`, outside Git. Reproduction uses `tools/build_cache_metadata.py` with the pinned profile and owned CUE, then compares with `c31bb4f`.
- Both generated command sets evaluated by the current engine under the existing Herb-before flags produce complete item-source coverage of 254 before and 255 after. Unresolved item slots change from 141 to 135, doors from 186 to 180. `ROOM70C0.RDT` is the one newly complete item-source variant. Other variants can resolve individual slots while retaining other uncertainty. The dual evaluation took about 0.34 seconds here, an offline probe rather than live polling latency or gameplay validation.
- `tests/test_remaining_effects.py` uses synthetic packets and flag substitutions. Existing Herb/Chemical capture regressions retain their original authorship and scope. The project has no configured formatter/linter; scoped Ruff formatting and linting are used for these Python changes.
- 2026-10-02; Gemini 3.1 Pro High via agy; reviewed the supplied source, diff, synthetic tests and native instruction excerpts without gameplay. Root verified its callback-4 precision finding against `0x80037B80..0x80037BB0`: a conditional OR preserves an already true bit. The common rule now preserves that fact, with opcode-24 preservation and opcode-2D toggle regressions. Its missing-test finding covered the same transition. Root rejected removing global `FF` handling: the dispatcher selects `F6..FF` at `0x80025D60..0x80025D84` before checking VM state at `0x80026078`; `FF` clears activity at `0x80026068..0x80026074`. Explicit actor/motion termination regressions retain that native contract from RE1-EVENT-003.
- 2026-10-02; Claude Opus 4.6 Thinking via agy; review timed out after five minutes with no usable output. Gemini 3.8 Flash High via agy produced no review because its headless session attempted a command that was auto-denied. Neither result supplies findings or an endorsement. No permissions were broadened, and the timed-out model was not retried.
- 2026-10-02; Codex root, GPT-6.1 Sol; final review checked every external candidate against the pinned instructions and actual rules. All 529 tests passed in 13.82 seconds. The six changed Python files passed scoped Ruff lint/format checks; no project formatter/linter is configured. Independent regeneration was byte-identical, the final offline projection retained the counts above, and `git diff --check` passed. These checks establish implementation/source consistency, not additional runtime confirmation.

## RE1-SCD-015: forced door callbacks preserve descriptors and use fresh unlock state

Status: Candidate; pinned native inspection and synthetic tracking regressions
Scope: Resident Evil Director's Cut USA SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`
Environment: Python 3.14.8, pytest 9.1.1, Capstone 5.0.9 on macOS; owned executable/disc and existing donated DuckStation `0.1-11894-gc66b2694d` captures; no new emulator or GDB experiment
Authored: 2026-10-02; Codex root; model: GPT-6.1 Sol
Basis: primary executable inspection, generated source metadata, synthetic commands/flags and existing capture regressions
Claim: forced callback 1 preserves the selected AOT's handler, mode, parameter, GlobalId and source bytes. It can set a door unlock bit and queue a transition or message, but those effects do not replace the door definition. The tracker reconstructs supported definitions and reads the actual lock state from fresh game flags. It never grants an unlock by replaying a callback.

Evidence:

- Callback table at PS1 VA `0x80090404` selects `0x8003789C..0x80037AEC` for handler 1. It first checks little-endian u32 `0x800C3000` mask `0x80`, then reads the AOT's source pointer at record offset 8. Source byte `+0x0C` is Door_set opcode byte 14; `+0x16` is opcode byte 24. The callback has no store to the selected descriptor or pointed-to source. Its directly called helpers are the message setup, inventory search, flag read/set and audio functions below. No helper in this inspected chain dispatches indexed scripts or stage overlays.
- The unset-lock path checks player state, the special type-`33` ability flag or current inventory before setting the selected bit at `0x80037A44..0x80037A58`. Native flag helper `0x80048954..0x80048978` ORs `0x80000000 >> (index & 31)` into a little-endian u32 at `0x800C86B4 + 4*(index//32)`, with `index = source[0x0C] & 63`. This is script bank 2, within eight bytes. Its read helper is `0x800489A8..0x800489C8`. The reconstruction preserves a previously true shadow or fresh persistent bit, and otherwise invalidates only the possible target when bit `0x80` selects a lock. An earlier false or unknown script shadow takes precedence over the fresh bit. Key type `FF` cannot set the lock bit, so its prior value remains unchanged. Reached callback-1 commands add all eight unlock bytes to the rule snapshot and recheck when bank 2 is persistent. Actual inventory and past interaction timing are unavailable, so the command does not establish an unlocked state. Ordinary acquisition flags remain untouched.
- Transition setup at `0x80037A9C..0x80037AD4` writes byte `0x800C845B=1`, zeros u16 `0x800CAB00`, stores the source pointer into u32 `0x800CAAFC`, and ORs mask `0x02000000` into `0x800C3000`, script bank 5 index 6. A prior true transition bit stays true; other prior shadows become unresolved because the callback can instead take a locked/message or early-return path. Descriptor fields are unchanged even for a forced callback on a disabled handler or mode.
- Message helper `0x80035278..0x8003538C` returns immediately when byte `0x800C8665 & 0x80` is already set. Otherwise it writes that byte as `0x80`, copies the old `0x800CAB00` halfword to `0x800CAB02`, and masks the former with the inverse of argument `0xFF`. The callback can also write key byte `0x800C8666`. These are byte-variable indices 5/6 and script bank 6's first u32, indices 0..31 under its MSB-first numbering. The interpreter forgets those conditional physical aliases, including overlapping scalar words. It preserves unrelated bits and never substitutes temporary RAM from another room.
- Inventory helper `0x8002CCB8..0x8002CD2C` searches the count at `0x800C8667` and the inventory array selected by `0x800BA008`, updating only search-work pointer `0x800BA0CC`. It neither consumes an item nor changes the door. Audio helper `0x80051E38..0x80051FD8` resolves category/index into sound-bank parameters and calls `0x80086364..0x80086748`. Its inspected chain is `0x800820E0..0x800821B0`, `0x800827CC..0x80082A44`, `0x80082A48..0x80082F24`, `0x80082F28..0x80083158`, `0x8008315C..0x8008361C`, `0x80083884..0x80083980` and `0x80089214..0x800892E8`. Writes target audio buffers/voice records or SPU state, outside the pinned tracking banks. The executable initializes pointer words at `0x800AD734/0x800ADD34` to SPU register base `0x1F801C00`. Setup `0x80084690..0x800846B4` clamps the voice count at `0x800B7F78` to at most 24, bounding the 48-byte voice records at `0x800B5200` below the AOT registry. No AOT/source or script-variable writes occur in this audio chain under that native initialization. The previous event-category interpretation in RE1-DOORS-002 is superseded; that routine plays audio.
- Opcode `24` dispatches the callback and returns one; `2D` uses the same dispatch, updates pending bits and returns zero as recorded by RE1-SCD-014. The callback's own zero return cannot change those command contracts. Runner `0x800489CC..0x80048AF0` takes a zero return at `0x80048A74..0x80048AB4`, pops an IF when present or advances to the next procedure when its depth is zero. Thus an unguarded `2D` intentionally skips the rest of its current procedure. Reached init/main dispatch requires every possible source descriptor to be a supported Door_set. Missing or other creator kinds reject reconstruction explicitly. Indexed event timing remains unmodeled; its descriptor writes already participate in the conservative possible-event closure, while callback 1 itself adds no descriptor effect.
- `tests/test_forced_doors.py` covers init/main/event dispatch for both commands, unchanged and disabled door definitions, branch returns, unlock-index boundaries 0/31/32/63, true/false target shadows and fresh RAM bits, other-side locks, required unlock reads and failures, independent locks, pending transition state, dialog backup/clear aliases, overlapping scalar words, unsupported sources and event source conflicts. A synthetic main callback over the existing Herb capture is then refreshed while the tracker is in the Chemical room. Replacing the unlock flag produces Locked, Open, Locked for the entered Herb room's supported door. Its unrelated slot-3 disable event remains unresolved, and item clearance stays independent. No emulator RAM is written by the tracker.

Generation and offline probe:

- Regeneration compares with `4c8e71b` using the same 334 source variants and 636 loader choices. Only `tracking_program.mutable_slots` changes in source rows. It removes 68 forced-door barriers across 57 variants, leaving six quantity-write barriers. Source signatures, decoder statuses, source/cache eligibility, source choices, item/door IDs, event effects, scalar commands and coverage flags are unchanged. There are no handler-1 forced dispatches in the generated init/main sections; their new semantic support is exercised synthetically.
- The manifest SHA256 is `0c3ad08459f3ff4db03d20311547addf890a341ecc47d3f427c4d0d82957d5a1`. Audit artifacts are `/tmp/tasks/re-map/forced-door-callback/native.txt`, `generation-audit.json` and `projection-audit.json`, outside Git. Reproduce metadata with `tools/build_cache_metadata.py`, the pinned profile and owned CUE, then compare against `4c8e71b`.
- Evaluating both metadata versions with the current engine under the existing Herb-before flags changes unresolved door slots from 180 to 135. Complete door-source variants change from 218 to 250. Item results are unchanged, with 255 complete item-source variants and 135 unresolved item slots. Twenty-three removed barriers still have other uncertainty. These are source/analysis counts under one offline flag snapshot, not confirmed gameplay rooms or unlocks.

Limits: no natural forced-door event, controlled door unlock, normal door save/load, door savestate reversal, story progression or alternate character/revision was played. Audio/transition work is inspected, not executed by the tracker. Incomplete sources, conflicting optional event writes, unsupported creators and quantity mutations remain unfinished detection work. Existing runtime findings retain their original validation states. Map geometry is still Mansion 1F.
History:
- 2026-10-02; Codex root, GPT-6.1 Sol; audited the callback/helper chain, extended the common callback semantics, removed the descriptor barrier, regenerated/audited metadata and added the synthetic regressions above. No gameplay reproduction.
- 2026-10-02; Gemini 3.8 Flash High via agy; reviewed the supplied source, diff, native contract and synthetic tests without gameplay. Root verified loss of a known true persistent unlock bit after a callback, preserved the fresh value only when no prior script shadow supersedes it, and added targeted RAM/shadow and failed-read tests. The native FF path also justified preserving that target, with two regressions. Its unguarded-2D continuation suggestion contradicted runner `0x80048A6C..0x80048AB4`; a regression now confirms native procedure termination. The proposed six-bit lock overflow is excluded by the mask and mandatory descriptor validation. Its stale-publication claim was checked against `tools/track.py`'s independent eight-byte door-state recheck; the added rule-snapshot reads support fresh-bit preservation rather than repairing that already-covered polling check.
- 2026-10-02; Claude Opus 4.6 Thinking and Gemini 3.1 Pro High via agy; each review timed out after five minutes with no usable output. Neither supplied findings or endorsement. No automatic retries were made; root verified Flash's candidates directly and performed the final review.
- 2026-10-02; Codex root, GPT-6.1 Sol; final checks passed all 574 tests in 14.30 seconds, scoped Ruff lint and format checks on all five changed Python files, and `git diff --check`. No project formatter/linter is configured. Independent metadata regeneration was byte-identical, and the final offline projection retained the counts above. These checks establish source/implementation consistency, not additional gameplay confirmation.

## RE1-EVENT-004: ordered event blocks retain their internal progress conditions

Status: Candidate; pinned native inspection, owned-disc generation and synthetic regressions
Scope: Resident Evil Director's Cut USA SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`; the shared item/door rules and 334 bounded source variants
Environment: Python 3.14.8, pytest 9.1.1 and Capstone 5.0.9 on macOS; owned executable/disc and existing Herb-before RAM captured with DuckStation `0.1-11894-gc66b2694d`; no new emulator or GDB experiment
Authored: 2026-10-02; Codex root; model: GPT-6.1 Sol
Basis: primary native call/return inspection, semantic source metadata, synthetic tests and existing-capture projection
Claim: an event's embedded full SCD procedure list preserves command order and flag/variable relations within that dispatch. Its possible final descriptor states can be calculated as a shared item/door transformation. Current flags alone do not establish whether that event ran or what its historical guards observed.

Evidence:

- All native addresses here are PS1 virtual addresses. Wrapper `06` at `0x80027184..0x800271DC` calls runner `0x800489CC` with source+2 at `0x800271A4`. After the runner returns, it loads the wrapper width and advances the event PC at `0x800271AC..0x800271C8`. Runner `0x800489CC..0x80048AF0` reads each u16 length, dispatches its commands through `0x80091108`, handles zero returns through the IF stack, advances to the next procedure and returns at the zero-length list sentinel. The complete procedure list is one synchronous dispatch boundary. It is not the entire indexed event, whose waits and repeats are documented by RE1-EVENT-003.
- Wrapper `07` at `0x800271E0..0x80027238` advances the event PC and invokes one SCD handler. Deferred `FD` also invokes one handler, as recorded in RE1-EVENT-003. These retain independent descriptor effects. The scanner now retains both full-list starts and standalone command offsets, so a command reachable in both forms cannot lose its standalone possibility.
- Generated blocks preserve every procedure, guard and semantic command within a full-list dispatch that changes a tracked item/door slot. Startup enforces their mandatory command, branch and procedure-order schema. Invalid event decoding or semantic blocks prevent completeness. The old command-list decoder API remains available to standalone decoder callers; metadata generation requires the richer scan result.
- The evaluator uses the same command semantics for initialization, recurring main procedures and historical blocks. Each block is optional; block order, repetition and activation are overapproximated. Historical flag inputs are unknown, including persistent flags. A same-block flag test splits paths with the corresponding physical-bit assumption. Repeated tests retain that relation until a setter, scalar alias or native forgetting effect changes it. Flag/variable writes remain shadows and never write emulator RAM.
- Block-local scalar bytes can now supply later comparisons when all eight shadow bits are known. Unwritten bytes remain unresolved, apart from the established room/character identity fields. Low scalar words retain RE1-VARS-001's existing bounds. Shadows continue through the next procedure of the same dispatch, then are discarded across dispatches. A flag set in a different event or before a wait does not authorize pruning a later event's alternatives.
- Each slot considers the block's final outcomes rather than every intermediate descriptor write as an independently completed event. Initial descriptors and optional nonexecution remain possible. Unsupported effects, missing callback descriptors and analysis limits retain independent writes for that block. The existing per-procedure and per-slot budgets still prevent clearance when analysis cannot establish a common result. Door uncertainty remains separate from item clearance.
- `tests/test_event_conditions.py` covers same-block progress writes, contradictory and toggled guards, ordered item/door restoration, multi-procedure shadows, separate dispatches and waits, physical aliases, scalar comparisons, native forgetting, zero-return termination, deferred/full-list command aliasing, unsupported effects, budgets, malformed sources/schema and acquisition/story snapshot reversal. The byte packets and RAM substitutions are synthetic. They do not confirm a natural puzzle, event activation or ordinary save/load.

Generation and offline probe:

- Two independent owned-disc generations are byte-identical. Compared with `3f43518`, all 334 source identities/ranges, 636 loader choices, cache dependencies and eligibility, init/main commands, source-coverage flags and slot barriers are unchanged. The 609 original descriptor effects equal the union of 413 independent effects and 196 effects inside 92 ordered blocks across 61 source variants. No original descriptor command is lost or changed. Source-complete programs remain 312; item-cache candidates remain 262.
- Manifest SHA256 is `4caf0d005e917477a30fc114ed2c714ad4a807bebfdf58614bf42d87b0a22a7f`. Reproduce with `tools/build_cache_metadata.py`, the pinned profile and owned CUE, then compare source fields and the event-command union against `3f43518`. Native inspection, generation and projection scratch are in `/tmp/tasks/re-map/event-conditions/`, outside Git. Extracted RDT hashes and the owned executable hash were checked before the audit.
- Both metadata versions evaluated under the existing Herb-before flags yield 255 complete item-source variants, 250 complete door-source variants, 135 unresolved item slots and 135 unresolved door slots. No previously complete source loses completeness in that probe. The paired evaluation took about 0.44 seconds. These are offline source-variant results, not gameplay room counts or live polling latency. This change preserves event-condition structure but does not resolve the remaining activation/history gaps in this capture.

Limits: no new natural event, pickup, unlock, room transition, ordinary save/load, emulator savestate reversal or alternate character/revision was tested. Current progress flags are not interpreted as proof of historical execution. Relations across separate dispatches, event scheduling, dormant awards, unsupported sources, quantity writes and undecoded paths remain unfinished detection work. The earlier conservative event model in RE1-ENGINE-002 is narrowed only inside the inspected full-list boundary; its provenance and runtime limits remain recorded. No map geometry or reveal behavior changes.
History:

- 2026-10-02; Codex root, GPT-6.1 Sol; inspected runner/dispatch boundaries, preserved semantic event blocks, implemented shared ordered outcomes and physical-bit guard relations, regenerated/audited metadata and added synthetic regressions. No gameplay reproduction.
- 2026-10-02; Gemini 3.8 Flash High via agy; reviewed the supplied scanner, compiler, interpreter, native boundary contract and initial synthetic tests without gameplay. Root verified its semantic-block completeness finding, which had also been corrected independently while review ran, and added explicit dirty-scan and clean-width/invalid-schema regressions. Root verified the suggested word, quantity-copy and callback test gaps and added ordered-block cases. Its empty-main claim was checked against the unconditional final event closure and its own budget check; initializer shadows do not feed historical blocks, and new empty-main regressions pass. A proposed minimum wrapper width of two contradicts the audited native independent jump and existing width-one regressions in RE1-EVENT-003. Ordering/overlap between separate blocks does not imply runtime ordering and shared source bytes are allowed; each individual procedure list and mandatory source range remain validated.
- 2026-10-02; Claude Opus 4.6 Thinking and Gemini 3.1 Pro High via agy; each timed out after five minutes with no usable review. Neither supplied findings or endorsement, and neither was automatically retried. All three received the same supplied context.
- 2026-10-02; Codex root, GPT-6.1 Sol; final inspection additionally applied mandatory source-section and acquisition-width checks to the new event-block fields at profile startup, with two corruption regressions. Final checks passed all 616 tests in 14.40 seconds and scoped Ruff lint/format checks on all seven changed Python files. No project formatter/linter is configured. `git diff --check` passed, final regeneration matched both earlier generations, and the manifest hash matched the audit. External review covered the supplied initial implementation; root verified its candidates and the final corrections directly. These checks establish implementation/source consistency, not natural event activation or additional gameplay confirmation.
- 2026-10-02; Codex root, GPT-6.1 Sol; corrected finding-ID collisions introduced by the native-flow and ordered-condition entries. The 2026-09-26 event findings retain RE1-EVENT-001/002 and their original provenance. The later native-flow audit is RE1-EVENT-003 and ordered conditions are RE1-EVENT-004. Updated references and the manifest research-ID list; all source rows, commands and runtime behavior are unchanged.

## RE1-EVENT-005: native event activity is separate from retained script pointers

Status: Candidate; pinned native inspection and extraction of existing captures
Scope: Resident Evil Director's Cut USA SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`; Jill Herb and Chemical capture pairs
Environment: Python 3.14.8 and Capstone 5.0.9 on macOS; existing savestates from DuckStation `0.1-11894-gc66b2694d`; no new emulator or GDB experiment
Authored: 2026-10-02; Codex root; model: GPT-6.1 Sol
Basis: primary native instruction inspection and offline RAM extraction
Claim: the event tick checks an activity byte independently of the retained script pointer. An inactive record's nonzero pointer cannot establish current activation, room ownership or completed execution.

Evidence:

- All native addresses below are PS1 virtual addresses. The tick at `0x80025CDC..0x800262CC` iterates eight records at `0x800CF68C`, with stride `0x34`, totaling 416 bytes. It writes each selected record pointer to `0x800CF688`, a little-endian u32, before testing activity. This pointer alone does not establish that its selected record runs. The tick tests record+2 as a u8 at `0x80025D34..0x80025D3C` and skips zero. The state dispatch reads record+0 as a u8 at `0x80026078`, despite initialization clearing a u16 there.
- Initializer `0x80025C1C..0x80025C54` writes activity 1 at +2, clears +0/+1, writes depth `0xFF` at +3 and loads a little-endian u32 script pointer at +8 from the indexed event table. The table pointer at `0x800B835C` is a little-endian u32; entry selection uses four-byte indexing. Record+4 receives the little-endian u32 at `0x800CAB14`; its gameplay meaning remains unmodeled here. Depth and frame contracts are separately recorded in RE1-EVENT-003. These fields use their full width, with no added bit mask.
- Global `FF` at `0x80026068..0x80026074` clears activity and then advances through the common yield path. The tick's next-opcode check at `0x80026278..0x8002629C` also clears activity when it sees `FF`. Neither path clears the retained script pointer. State-0 default termination likewise clears activity, as recorded in RE1-EVENT-003.
- Extracting all four donated fixtures with `tools/extract_sav_ram.py` produces zero active records and six inactive records with nonzero script pointers in every capture. Herb-before/after report room `00-09` and table pointer `0x8013E6D4`; Chemical-before/after report `00-18` and `0x80121F50`. Their state, activity, depth and script-pointer fields are identical across these pairs and rooms. This is direct evidence of retained inactive data, without identifying the historical events that left it.

| Existing fixture | Extracted RAM SHA256 |
| --- | --- |
| `slus00551_green_herb_before.sav` | `d819fbd41abea6537bf9ce9f4967b479ea1f6278024b9f4e018290343c0bc8d4` |
| `slus00551_green_herb_after.sav` | `0130861a3a27d2810ccbd0d1e2e7bbc42c64abdac130e1d43dd71ed646784704` |
| `slus00551_chemical_before.sav` | `bb9110536a02122d7c6a14d489b2e94e7d8224d8ccf297d617694c4eb6e804f2` |
| `slus00551_chemical_after.sav` | `0d5e7dc6e450a99b9f8a354cc9ffd30e97dd3129427600e384681903330935df` |

Reproduce by extracting each fixture and reading the fields above at RAM offset `0xCF68C + 0x34*slot`, for slots 0 through 7. Inspect the named native ranges in the hash-verified executable, whose text starts at PS1 virtual `0x80010000` and file offset `0x800`. The extraction script and JSON results are in `/tmp/tasks/re-map/event-activation-inspection/`, outside Git.

Limits: none of these captures contains an active event. Start, wait, completion, room ownership, slot replacement and save/load reversal need controlled runtime observations before profile reads can support availability conclusions. Zero active records cannot prove that a future event or collectible is absent. No profile or tracker behavior changed.
History:

- 2026-10-02; Codex root, GPT-6.1 Sol; inspected the initializer and tick, checked the executable hash and extracted the existing capture pairs. Recorded the state field as u8 after checking the dispatch load. No new gameplay or external model review.

## RE1-EVENT-006: script and interaction commands share the native event initializer

Status: Candidate; pinned native call and operand inspection
Scope: Resident Evil Director's Cut USA SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`
Environment: Python 3.14.8 and Capstone 5.0.9 on macOS; read-only owned executable; no new emulator or GDB experiment
Authored: 2026-10-02; Codex root; model: GPT-6.1 Sol
Basis: primary native dispatch-table, call and operand inspection
Claim: SCD event creation, indexed-event creation and interaction callback 9 pass slot/index operands to shared starter `0x80025C58`. Indexed-event reinitialization calls initializer `0x80025C1C` directly. Decoding their commands does not prove that their triggers ran.

Evidence:

- All addresses are PS1 virtual addresses. SCD table `0x80091108`, entry `14`, points to `0x80045C88`. Handler `0x80045C88..0x80045CE0` reads the little-endian u16 at packet+2, passes its low byte as requested slot and high byte as indexed entry to `0x80025C58`, advances four bytes total and returns 1. Packet+1 is skipped by this handler. The current tracking compiler treats this opcode as continuing without retaining its activation operands.
- State-0 indexed-event opcode `05` dispatches through table `0x800101C8`, entry 5, to `0x80026180`. Its helper at `0x800270E8..0x8002714C` passes packet+1 as slot and packet+2 as indexed entry to the same starter, then finishes a four-byte advance. Opcode `08`, table target `0x800261B0`, uses helper `0x80027150..0x80027180` to reinitialize the selected record directly with packet+1 as indexed entry. RE1-EVENT-003 already records its lack of sequential continuation.
- Interaction table `0x80090404`, entry 9 at `0x80090428`, points to `0x80037FA0`. Handler `0x80037FA0..0x80037FC8` reads u8 slot at registry-record+2 and u8 indexed entry at +4, calls the shared starter and returns zero. The current abstract descriptors do not retain these activation parameters, so callback identity alone cannot determine which event starts.
- A whole-executable aligned direct-call scan finds the three starter calls above and initializer calls from the starter and reinitialization helper. This scan does not exclude indirect callers. Reproduction and native call excerpts are in `/tmp/tasks/re-map/event-activation-inspection/start-callers.txt`, outside Git; inspect the listed ranges in the hash-verified executable to reproduce each operand mapping.

Limits: trigger eligibility, native slot allocation/replacement, actual event timing and natural item/door changes remain unvalidated. Shared source metadata must retain command ownership and guards, and live activation must be bound to the actual room source before it can narrow availability. RE1-EVENT-005's inactive pointers provide no execution proof. No implementation or broader completion claim accompanies this inspection.
History:

- 2026-10-02; Codex root, GPT-6.1 Sol; checked dispatch-table targets and native operands for shared event start/reinitialization. No gameplay or external model review.

## RE1-EVENT-007: shared source metadata binds transient event activity

Status: Candidate; pinned native contracts, generated-source audit and synthetic regressions
Scope: Resident Evil Director's Cut USA SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`; no other revision
Environment: Python 3.14.8, pytest 9.1.1 and Capstone 5.0.9 on macOS; native contracts from RE1-EVENT-003/005/006
Authored: 2026-10-05; Codex root; model: GPT-6.1 Sol
Basis: primary native inspection already recorded in the linked findings, semantic source generation, code inspection and synthetic RAM substitutions
Claim: the shared reader can associate current active event records and callback-9 registry entries with matching indexed scripts and their potential item/door changes. This association provides transient debug information. It does not establish acquisition, completed execution history or current availability by itself.

Evidence:

- The scanner retains every indexed entry's VM positions, state, shared frame depth and initialized loop/call pointer targets. Identical source bytes can have several owners. VM `05` starts and `08` reinitializations retain their target operands; reinitialization changes ownership. SCD `14` retains its slot/index operands and native return of one. Callback 9 and its registry parameter writers remain in the shared semantic metadata. Full dispatches retain guards around triggers, awards, door callbacks and quantity changes.
- The profile uses the PS1 virtual layout from RE1-EVENT-005, eight records at `0x800CF68C` with stride `0x34`, u8 state at +0, u8 activity at +2, signed depth at +3 and little-endian u32 PC at +8. Loop/call repeat pointers begin at +`0C`; deferred command pointers begin at +`1C`, both little-endian u32 arrays with four-byte strides. The little-endian u32 table pointer is at `0x800B835C`. The profile rejects malformed layouts, out-of-section points/frame targets and entries without an initial position.
- `src/games/re1/event_state.py` requires the actual relocated indexed table to match the current hash-verified source. Active PC/state/depth and initialized pointer targets must match a source position. All matching owners remain explicit. Inactive fields are ignored, including retained nonzero PCs. Callback 9 uses the low bytes of the current registry u16 parameter/model fields, bound through its retained creator pointer and slot. Possible VM/SCD starts expand item/door links transitively with bounded cycle handling. Links describe possible changes, regardless of whether a guard or later command ran.
- `tools/track.py` rereads event positions, initialized pointer storage, table data, loaded-room pointer, source/registry markers and existing flag/context reads before mutating tracker/cache state. Failed reads return a modeled failure. Changed snapshots retry without mutation. An unbound active event or registered event interaction rejects item and door coverage. No event history is persisted and no conservative historical availability alternative is removed by observing an active or stopped slot.
- `tests/test_event_activation.py` has 33 synthetic cases. They cover source aliases, VM starts/reinitialization, guarded SCD starts, native wrapper returns, active/stopped/restored state, initialized frame-pointer corruption, table relocation, standalone and guarded awards/quantity writes, transitive starts, cycles, current callback parameters, failed reads, mixed polls, false-clearance prevention and startup bounds. Live RAM activity in the donated Herb-after capture is substituted for the poll regressions. Those substitutions are not natural activation or save/load observations.
- Two independent owned-disc generations are byte-identical. The audit compares all 334 source rows against the previous committed manifest and preserves source hashes/ranges, 636 loader choices, dependency sets, 262 cache candidates, coverage booleans and all earlier descriptor effects. It adds 599 retained full dispatch blocks, totaling 691. Event metadata contains 2,192 entries, 85,555 owned positions, 8,919 dispatches, 1,007 VM starts/reinitializations, 2,806 creators, 1,981 parameter writers, 4,635 potential changes and 1,160 SCD starts. These counts describe static metadata, not confirmed gameplay cases. The manifest SHA256 is `44d78fddb3b3dfb18729d1078b83c2f5cf37db4730d1511ec97988f4f2c42f5d`.

Reproduce the static audit with `tools/build_cache_metadata.py <owned-cue> <output> profiles/re1_directors_cut_slus00551.json`, generate twice and compare the outputs. Run `python3 -m pytest -q tests/test_event_activation.py` for the synthetic contract. Generation outputs, audit JSON and external-review streams are outside Git at `/tmp/tasks/re-map/event-activation/`. The generated manifest retains semantic operands and hashes, not game bytecode.

Limits: natural active-event start, wait, stop, slot replacement, puzzle/story changes and save/load reversal were not captured. The limited registered-trigger observation is recorded separately in RE1-EVENT-008. Trigger eligibility and historical scheduling remain unresolved. Counter values and stale inactive pointers cannot establish execution. Active script identity does not prove a particular command ran. Existing room-completion rules remain conservative; this adds debug evidence without claiming full-game item/door coverage or changing map reveal/persistence behavior.
History:

- 2026-10-02; Codex root, GPT-6.1 Sol; began the user-approved shared activation implementation after RE1-EVENT-005/006. Preserved entry ownership, trigger operands and source-bound runtime interpretation.
- 2026-10-05; Codex root, GPT-6.1 Sol; resumed implementation, bound initialized frame pointers, added standalone/transitive item and door links, retained award/door/quantity guards, audited regeneration and startup bounds. Final full suite passed 649 tests in 28.70 seconds. Scoped Ruff lint/format checks and `git diff --check` passed; no project formatter/linter is configured.
- 2026-10-05; Claude Opus 5.5 High through agy; review unavailable. The request failed with individual quota exhaustion, reporting a reset in 112 hours, 17 minutes, 58 seconds. No review returned and no retry or model substitution was made.
- 2026-10-05; Gemini 3.1 Pro High through agy; review unavailable. It attempted a prohibited repository command, which was denied, and returned an empty response. No permissions were granted and no review was accepted.
- 2026-10-05; Gemini 3.8 Flash High through agy; the first supplied-snapshot review exceeded the output limit with repetitive reasoning and ended in ERROR. Its partial output is diagnostic only. One fresh retry with the complete scope and a concise-response instruction exited successfully, reached a completed response and returned "No findings." It reviewed the supplied implementation/schema/tests without tools or gameplay. Root inspected the final generation, corrections and startup corruption regressions directly; review does not confirm runtime behavior.

## RE1-EVENT-008: live demo registry entries bind to source event targets

Status: Candidate; limited live observation of registered triggers, no active-event capture
Scope: Resident Evil Director's Cut USA SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`; automatic attract/demo sequence
Environment: DuckStation `0.1-11894-gc66b2694d`, isolated portable copy with native GDB on localhost port 2345; Python 3.14.8 on macOS
Authored: 2026-10-05; Codex root; model: GPT-6.1 Sol
Basis: live GDB reads of the unmodified game and generated source metadata
Claim: callback-9 registry entries observed in the demo sequence can bind to the current room source and indexed target. A registered trigger does not prove that its event is currently active or has executed.

Evidence:

- Launched the isolated emulator with the owned disc and verified the runtime executable windows through the profile. Resumed through GDB. For 120 seconds, read current room, hash-bound source, the live AOT registry, relocated event table and event records. Repeated reads in room `00-07` matched `PSX/STAGE1/ROOM1070.RDT`. Registry slot 5 used callback 9, requested event slot 9 and indexed entry 0. The potential change links included item slot 2, whose source item ID is `0x4E`, labeled Map by the profile. Requested slot 9 is passed to the native allocator; it is not an observed allocated event slot.
- Later room `01-07` matched identical-source alternatives `PSX/STAGE2/ROOM2070.RDT` and `ROOM2071.RDT`. Registry slots 8 and 9 used callback 9, requested slot 9 and indexed entries 1 and 0. Both source aliases remained explicit; these events have no linked tracked item/door changes. Room transitions also produced explicit not-ready/source-disagreement results, and one interaction became unbound during a transition.
- No active record was observed in that loop. A separate 90-second loop read the 416-byte event pool at 20 ms intervals and also observed no active record. Neither experiment captured natural start/stop or savestate reversal. Menu key attempts did not establish a player-controlled test state. The isolated emulator was then closed without saving a resume state.
- Metadata-only observations are in `/tmp/tasks/re-map/event-activation/live-events.json`, SHA256 `30485c6891a099e909f52c9c9c54d3e4a49d164140781ac40e3e22f19e5ef30a`. `runtime_capture.py`, `live-capture.log`, `watch_event.py` and `watch-event.log` in that directory record the reads and negative capture result. These temporary artifacts remain outside Git.

Limits: this is one automatic demo sequence, not controlled normal gameplay or several independent trigger tests. The exploratory loop did not perform the final poller's complete coherence recheck, so transitions are diagnostic observations. No new item take, door unlock, natural puzzle progression, ordinary save/load, savestate reversal or alternate character/revision was validated. The linked Map slot is static potential-change metadata, not proof that the item was available or acquired in the observed frame.
History:

- 2026-10-05; Codex root, GPT-6.1 Sol; performed the isolated GDB observation and attempted the short-event capture. Recorded registered targets and preserved the unsuccessful activation capture as a limit. Corrected the initial experimental description of the linked item from Shotgun to Map after checking source item ID `0x4E`; the captured slot metadata was unchanged. No external reviewer reproduced this experiment.

## RE1-EVENT-009: reusable coherent event observation log

Status: Candidate; implementation and synthetic regression contract
Scope: Resident Evil Director's Cut USA SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`; no other revision
Environment: Python 3.14.8, pytest 9.1.1 on macOS; required profile layouts and native contracts from RE1-EVENT-005/007
Authored: 2026-10-05; Codex root; model: GPT-6.1 Sol
Basis: implementation inspection and synthetic substitutions over the donated Herb and Chemical fixtures
Claim: `tools/capture_events.py` can log source-bound event, registry, item, door and flag observations without updating tracker history. Its change labels compare observed snapshots and do not establish completed execution, trigger eligibility or a complete event history.

Evidence:

- The tool requires an explicit profile and a new output file outside the repository. Session metadata records profile/manifest hashes, executable identity, GDB endpoint, requested polling rate/duration and PS1 virtual address semantics. Snapshots include UTC/monotonic times, sequence numbers, pause duration, room/source aliases, event positions/owners, registered event targets, item states, door states and watched flag values. Descriptor reads contain SHA256 fingerprints, not game bytecode. Live registry coverage is labeled separately from room completion.
- The watch reads all eight event slots through the pinned layout, ignoring inactive fields and incidental counters. It reads current room/context, acquisition and door flags, the inclusive live registry and bounded descriptor fingerprints. Full script-flag banks remain in the paused snapshot. Capture triggers mask unrelated transient flag bits, retaining profile-persistent bits and source-declared flag tests/writes/dependencies. RE1-EVENT-010 records why the initial unfiltered trigger was rejected.
- On a watched change, the tool interrupts DuckStation, verifies the executable and actual relocated room source, reads the existing item/door/event interpretation, and rechecks all source/registry/event markers plus watched values before recording. Invalid or changing input produces an explicit gap. The next valid capture is a comparison baseline. A room/source change does not report prior-room slots as stopped. Active events with unresolved ownership remain explicit diagnostics.
- Capture cleanup attempts resume in a `finally` block even if interruption, reading or logging fails. A failed resume reports an explicit diagnostic. Transport loss stops with a diagnostic; this experiment tool does not reconnect. Normal duration and Ctrl+C termination append an end record when the output remains writable. Connecting resumes the emulator because native GDB attachment pauses it.
- `tests/test_event_capture.py` covers all eight synthetic active/stopped/restored slots, flags changing without event activity, in-place descriptor quantity changes, the last inclusive registry record, ignored retained records beyond the bound, unrelated transient flags, wrong game, unbound activity, failed/short/mixed reads, source changes, log fingerprinting, pause cleanup and comparison reset after a gap. These substitutions do not validate natural activation or normal save/load.

Reproduce with `python3 -m pytest -q tests/test_event_capture.py`. `docs/testing.md` gives the external capture command. The complete redacted external-review snapshot and response streams are outside Git at `/tmp/tasks/re-map/event-capture/`.

Limits: events can start and stop between polls. Polling frequency is requested, not guaranteed, and changed snapshots require pauses. No historical completion, acquisition inference, map reveal, tracker persistence or room availability rule changes accompany this tool. Natural activation, waits, slot replacement and puzzle/story effects remain unvalidated. Source/hash agreement and synthetic tests do not confirm runtime execution.
History:

- 2026-10-05; Codex root, GPT-6.1 Sol; implemented the user-approved reusable capture tool, corrected the inclusive registry watch bound, added read/coherence/cleanup regressions and filtered transient capture triggers after the live experiment. Full suite passed 680 tests in 32.69 seconds. After correcting the source-mutation test to alter the quantity byte, all 31 focused tests passed in 2.48 seconds. Scoped Ruff lint/format checks passed; no project formatter/linter is configured.
- 2026-10-05; Gemini 3.8 Flash High through agy; completed a supplied-snapshot code review of the new capture reader, CLI, tests and existing contracts without tools. Returned "No findings." This review did not reproduce gameplay.
- 2026-10-05; Claude Opus 5.5 High through agy; review unavailable due to individual quota exhaustion, reporting a reset in 111 hours, 35 minutes, 30 seconds. No response, retry or model substitution.

- 2026-10-05; Gemini 3.1 Pro High through agy; completed a supplied-snapshot review without tools. Identified duplicate recording when a torn running hint resolves to the previous coherent capture. Root reproduced that case in the CLI regression and now suppresses identical captures while preserving polling, heartbeats and resume cleanup. Its separate suggestion to omit camera/player/special inputs was not applied: camera is recorded context, and the existing door interpreter consumes player/special state. That review did not validate runtime addresses or gameplay.

- 2026-10-05; Codex root, GPT-6.1 Sol; verified the review correction directly. All 31 focused tests passed in 2.31 seconds; the final full suite passed 680 tests in 30.50 seconds. Scoped Ruff lint/format checks and `git diff --check` passed. Closed the isolated emulator after the recording ended; native shutdown required a second termination signal after the accessibility timeout. No active-event gameplay was obtained.

## RE1-EVENT-010: live capture records item-state savestate reversal

Status: Candidate; controlled emulator observations, no natural active-event capture
Scope: Resident Evil Director's Cut USA SLUS-00551, executable identity from RE1-EVENT-009; Jill in Winding Passage, room `00-09`
Environment: DuckStation `0.1-11894-gc66b2694d`, isolated portable copy, native GDB localhost port 2345; Python 3.14.8 on macOS; requested 20 Hz
Authored: 2026-10-05; Codex root; model: GPT-6.1 Sol
Basis: live GDB observations during actual emulator loads of the donated Herb-before/after savestates; no emulator RAM writes
Claim: the capture tool observes the Herb acquisition state restoring in both directions during savestate loading. Filtering unrelated transient flags prevents continuous idle capture pauses in this tested room. Neither observation proves natural indexed-event execution.

Evidence:

- Started the isolated emulator with `tests/fixtures/slus00551_green_herb_before.sav` and the owned CUE. The reusable CLI validated the runtime and captured room/source/registry/item/door/flag snapshots. Loading the after state through System, Load State, Load From File changed Green Herb from `available` to `taken`. A second actual file load of the before state restored `available`. The final log contains three coherent snapshots with no gaps and no active event slots. Snapshot times were approximately 0.106, 15.620 and 65.843 seconds. Capture pauses were 50.30, 45.16 and 52.58 ms. The relevant acquisition byte is PS1 RAM offset `0xC86EA`, bit 0, equivalent to PS1 virtual `0x800C86EA`. Original fixture provenance and pickup experiments remain RE1-PICKUP-002; this experiment observes loads, not a new pickup.
- The first watch compared every raw script flag byte. Unrelated `script-flags-4/5` changes caused 1,210 captures in 141.96 seconds, with 48.15 seconds spent interrupting/reading/resuming. A native UI observation showed 3 game FPS and 10% speed. Ctrl+C ended the recording cleanly. This broad capture trigger was rejected; it would interfere with experiments.
- After masking transient bits from capture triggers, a 120.03-second idle run produced one baseline snapshot, zero gaps and 2,238 watch samples. Its sole pause took 37.11 ms. A native UI observation showed 30 game FPS, 60 video FPS and 100% speed. Full flag bytes remain in recorded snapshots. The final 180.02-second reversal run recorded 3,358 samples, approximately 18.65 samples/second, and spent 148.04 ms total in its three capture pauses. These are measurements for this idle/load case, not a guarantee during active events.
- A first load experiment recorded before-to-after only. Its duration expired before the attempted return load, so it is not reversal evidence. The separate final run above captures both actual loads. CUA key attempts did not move Jill or take the Herb. Later native accessibility/screenshot requests timed out even though GDB recorded the return load. No successful manual gameplay was attributed to those attempts.
- Offline extraction of the seven existing user `.sav` states and the current slot-1 `.bak` found no active event record. The current Art Room slot/backup have already taken Map and Ink Ribbon and no registered event interaction. These private inputs were read explicitly and remain outside Git. They do not provide an active-event continuation test.

Artifacts outside Git at `/tmp/tasks/re-map/event-capture/`:

| Artifact | SHA256 | Purpose |
| --- | --- | --- |
| `live-trial-a.jsonl` | `08309b5bd571b6b1a635c2c72a89840f1b252b93f52f9baa4ba7b1222f9c92bc` | Rejected unfiltered trigger and interrupted termination |
| `live-trial-b.jsonl` | `5a2aedcc6ea0e9f7eebea74c289affd49f8110c7d426b5caea865e631b751f24` | Filtered idle observation and duration termination |
| `live-loads.jsonl` | `594d8be468f79118fb93f73c6a3a8e579e8089ba33216ae3a183af06e4cf3c9e` | Before-to-after load only |
| `live-reversal.jsonl` | `08c20d6118670bf1453bef3e447f7c03fd86c0fb2258d63035ce6e83b62d151b` | Before, after, before actual savestate loads |

`audit_logs.py` and `live-audit.json` in the same directory reproduce capture counts/timings/hashes. Emulator/CLI logs retain diagnostics. Game files, RAM extractions and savestates were not added to Git.

Limits: all live event slots remained inactive. Start/stop, waits, natural pickup, door unlock, puzzle/story effects, ordinary in-game save/load and another character/revision were not tested here. Normal save/load evidence for existing flags must be evaluated under its original research findings. Transient filtering does not make polling exhaustive; activity between samples can be missed. No room-completion or availability claim is promoted by this capture.
History:

- 2026-10-05; Codex root, GPT-6.1 Sol; launched the isolated emulator, ran the reusable CLI, performed actual native file-load reversal, inspected private inactive states, audited timings and preserved the failed broad trigger. External code reviewers did not run this experiment.

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

## RE1-EVENT-011: activity-write capture completes the pinned initializer

Status: Candidate; pinned native contract, synthetic regressions and inactive live observations
Scope: Resident Evil Director's Cut USA SLUS-00551, executable identity from RE1-EMU-008; all eight event records from RE1-EVENT-005/006
Environment: Python 3.14.8, pytest 9.1.1 and Capstone 5.0.9 on macOS; isolated DuckStation `0.1-11894-gc66b2694d`, native GDB localhost port 2345
Authored: 2026-10-05; Codex root; model: GPT-6.1 Sol
Basis: hash-checked owned executable inspection, shared capture implementation, synthetic activity/CPU tests and negative live recordings
Claim: the optional `--breakpoints` mode can watch every event activity byte and finish the source-derived initializer before binding a newly active record. It preserves activity-write observations in the existing coherent JSONL format. Natural indexed-event start/stop remains unvalidated by the inactive recordings below.

Evidence:

- The exact owned executable hash matches the profile. Its initializer is 60 bytes at PS1 virtual `0x80025C1C..0x80025C58`, SHA256 `617d66cbb61456b7eadb7e38a53eb71ab9cdefc1a278dca868363d5322ac6869`. It stores u8 activity at `0x80025C20` through A0+2 before initializing state/depth and pointer fields. It writes the little-endian u32 script PC at `0x80025C54`, the return delay slot after `jr ra` at `0x80025C50`. RE1-EVENT-005/006 retain the earlier initializer and event-pool provenance.
- With the post-store phase from RE1-EMU-008, register 37 should report `0x80025C24` at the activity hit. Thirteen single steps through `0x80025C54` finish this straight-line body. The tool checks the exact code hash and A0 record address, verifies each next PC before stepping, and refuses an unexpected path. This is a pinned source contract, not a live observation of all 13 steps. Other activity writes receive a coherent capture without stepping.
- The profile stores initializer addresses/hash. The optional mode installs width-one watches at `0x800CF68E + slot*0x34` for all eight records. KSEG0/KSEG1 hit addresses normalize to the same physical byte. Startup requires the pinned initializer configuration, runtime signature and code hash. A rejected command, unexpected stop or stepping failure ends the run explicitly; there is no implicit polling replacement.
- A paused baseline and each activity write use the existing source-bound room/registry/item/door/flag capture from RE1-EVENT-009. Repeated identical activity writes remain snapshots because they can represent a restart. Captured item/door states do not trigger this mode independently. A failed capture emits a gap; the next valid observation begins a baseline. Bounded stop waits allow duration/interruption and 30-second heartbeats. Cleanup tracks in-flight installs, removes watches in reverse order, resumes and disconnects. Pinned server disconnect cleanup is documented separately in RE1-EMU-008.
- `tests/test_event_breakpoints.py` models all eight initializer starts, stop/restart between polls, unchanged restarts, corrupt identity/code/registers/record addresses, a deviating PC, foreign stops, rejected/interrupting setup and transport failure. Each case verifies resumed state and applicable owned-watch removal. RAM activity and CPU steps are explicitly synthetic. The test-only initializer writes do not confirm a natural event or an in-game save/load.
- Starting the CLI from the actual donated Herb-before savestate, room `00-09`, completed a 45.025-second idle run with one baseline, zero hits and no gaps. A separate 180.039-second recording included native CUA arrows/confirm attempts. Repeated taps visibly moved Jill, but neither a pickup nor an indexed event was obtained. It also ended normally with one baseline and zero hits/gaps. Both runs installed/removed the eight watches and left the isolated game running. They prove inactive-mode setup/termination for this case, not active initializer completion.

Artifacts outside Git at `/tmp/tasks/re-map/event-breakpoints/`:

| Artifact | SHA256 | Purpose |
| --- | --- | --- |
| `live-idle.jsonl` | `739f6fabddaa86742b93f5a9e86ff21e0fb661b437a1f4b36a8d4698c57e1168` | Baseline, heartbeat and duration cleanup |
| `live-interaction.jsonl` | `20cededcb99b1b8a317fea6c09b6d8ea10adf8426ed2dee87eecfd761e0f6575` | Key attempts with no activity hit |

`plan.md`, the CLI/emulator logs and external review streams remain in the same scratch directory. Extracted native code, disc files, private emulator configuration and captured RAM are not committed.

Limits: no natural activity start/stop, waits, slot replacement, puzzle/story change, pickup, door unlock or normal save/load is established by these inactive runs. Wide overlapping stores and emulator restores bypass CPU watches. Capture pausing/stepping can alter timing, and the measured capture interval omits stop-delivery latency. Event activity still grants no acquisition, eligibility or execution history. This changes the observation tool only; the unfinished availability/history interpretation remains separate work.
History:

- 2026-10-05; Codex root, GPT-6.1 Sol; inspected initializer order, implemented the user-approved optional shared mode, ran synthetic regressions and the inactive live recordings. No runtime finding was promoted to confirmed.
- 2026-10-05; Gemini 3.8 Flash High through agy; completed the supplied-snapshot code/protocol/test review and returned "No findings." It used no tools and did not reproduce gameplay.
- 2026-10-05; Gemini 3.1 Pro High through agy; completed the supplied-snapshot review of the capture, protocol and cleanup paths. Root reproduced and corrected masking of a failed connection or interruption by a subsequent resume attempt. Disconnected captures now preserve the original failure, and cancellation during memory/interrupt exchanges closes the partial stream. New synthetic regressions cover both capture modes and these exchanges. Root also checked watch removal against the pinned server: valid removal returns `OK` even when an in-flight install never completed, and disconnect clears remaining owned callbacks.
- 2026-10-05; Claude Opus 5.5 High through agy; review unavailable due to individual quota exhaustion, reporting reset in 110 hours, 53 minutes, 55 seconds. No review returned; no retry or model substitution was made.
- 2026-10-05; Codex root, GPT-6.1 Sol; final review and regressions verified the diagnostic correction, including a failed coherent read after a write hit. The final suite passed all 722 tests in 35.33 seconds. Scoped Ruff format/lint and `git diff --check` passed. No project formatter/linter is configured; the scoped lint invocation excludes pre-existing `PYI034`/`UP037` warnings on the unchanged GDB context-manager return annotation, verified against HEAD. Closed the owned isolated emulator after capture cleanup; its process exited normally. No active initializer was validated.
- 2026-10-05; Codex root, GPT-6.1 Sol; later natural gameplay in RE1-EVENT-013 validates the 13-step path for 19 starts across six slots and two rooms. The earlier inactive evidence above remains unchanged. Slots 4/5 activation, acquisition and save/load are still outside this validation.

## RE1-EVENT-012: native transition clears hit every activity watch

Status: Candidate; two clear loops during one automatic/menu experiment
Scope: Resident Evil Director's Cut USA SLUS-00551, executable identity from RE1-EMU-008; the eight-record pool from RE1-EVENT-005/006
Environment: isolated DuckStation `0.1-11894-gc66b2694d`, native GDB localhost port 2345; Python 3.14.8 and Capstone 5.0.9 on macOS
Authored: 2026-10-05; Codex root; model: GPT-6.1 Sol
Basis: live CPU-write stops, hash-checked native inspection and reusable CLI output
Claim: all eight optional activity watches caught the game's byte-clearing loop twice. The corresponding room source was unavailable, so these hits produced explicit gaps rather than source-bound event snapshots. This validates activity-write delivery and continued resume after capture gaps, not an active initializer or completed event.

Evidence:

- After the two inactive recordings in RE1-EVENT-011 ended, restarted the isolated game through its native System menu. Started the optional recorder while the runtime signature and old room `00-07` source still matched. Native key attempts progressed through the opening/title/demo screens; no controlled player interaction or story event was established.
- The 180.021-second run recorded one baseline, 16 hits and 16 `source-unavailable` gaps. Each eight-hit group reports slots 0 through 7 and the exact addresses `0x800CF68E + slot*0x34`, with signal 5, zero steps and next native PC `0x800441C0`. The first group arrived around 82.914..83.143 seconds. The log preserves exact times for both groups. Every gap reports `room script ranges are outside PS1 RAM`. The recorder continued and ended normally, removing its watches and disconnecting.
- In the hash-checked executable, `0x800441B4..0x800441CC` loops eight times. The byte store at `0x800441BC` writes zero through a `0x800D0000 + slot*0x34` base and displacement `-0x972`, exactly the watched activity byte. `0x800441C0` increments the slot counter; the loop bounds it to eight and advances the offset by `0x34`. These native writes corroborate the all-slot offsets and post-store PC interpretation. They are record clears, not observed starts or proof that a previously active event stopped.
- The complete JSONL is `/tmp/tasks/re-map/event-breakpoints/live-attract.jsonl`, SHA256 `4e5f77d90f04c037b351f69bf3783b0a93eb79898607bf44477b43fc54f04d57`. The matching CLI/emulator logs remain outside Git. Reproduce by restarting the isolated game, attaching the optional CLI after identity verification, and observing title/demo transitions. The exact timing and room-source readiness can differ.

Limits: both clear loops belong to one automatic/menu experiment. No natural activation hit, full initializer stepping, wait, acquisition, door unlock, puzzle progression, ordinary save/load or another revision was captured. A zero write alone does not establish earlier activity. The observation adds runtime evidence for delivery and gaps only; RE1-EVENT-011's activation limits remain.
History:

- 2026-10-05; Codex root, GPT-6.1 Sol; ran the isolated recording, audited all 16 hit addresses/PCs, inspected the corresponding native zero-store loop and kept source-unavailable observations as gaps. External reviewers inspected code only and did not run this experiment.

## RE1-EVENT-013: natural opening events validate initializer stepping and stops

Status: Candidate; natural starts, restarts, waits and stops in two rooms of one fresh playthrough
Scope: Resident Evil Director's Cut USA SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`; Training Jill; Main Hall `00-06` and Dining Room `00-05`
Environment: isolated portable DuckStation `0.1-11894-gc66b2694d`, commit `c66b2694da65cece8886ed3d4a069098831f8358`; native GDB localhost port 2345; Python 3.14.8 and Capstone 5.0.9 on macOS; recorder at repository commit `66571a0`
Authored: 2026-10-05; Codex root; model: GPT-6.1 Sol
Basis: normal controller input in a fresh game, live write-watch stops, hash-checked initializer stepping, source-bound snapshots and an offline log audit
Claim: the optional recorder completed the pinned 13-instruction initializer for 19 natural starts across slots 0, 1, 2, 3, 6 and 7. Each newly initialized slot bound to its current room's indexed entry. Eight subsequent writes removed a previously observed active slot. These observations validate the tested capture path, without establishing complete execution history or item availability.

Evidence:

- Booted the owned disc in the isolated official emulator without a savestate, memory cards or exit resume writes. Brief native key taps had not reliably reached gameplay. Configured the private copy's documented controller macros with frequency zero and toggle enabled. A native key tap held Cross/Start or one direction through ordinary controller input; a second tap released it. [Pinned macro loading and toggle behavior](https://github.com/stenzek/duckstation/blob/c66b2694da65cece8886ed3d4a069098831f8358/src/util/input_manager.cpp#L2076) feeds controller bindings through `SetMacroButtonState` and `ApplyMacroButton` at lines 2176..2212. It does not write guest RAM. Native screenshots confirmed New Game, Training, Jill and the opening Main Hall/Dining Room sequence. No guest flags, RAM, function calls or instructions were injected.
- Started `tools/capture_events.py --profile profiles/re1_directors_cut_slus00551.json --out /tmp/tasks/re-map/natural-event-validation/fresh-jill-b.jsonl --breakpoints --seconds 900` at character selection. Used ordinary Start to skip the movies and let the opening scripts run. Interrupted the recorder after 154.247 seconds. It exited zero, wrote its final summary, removed its watches and disconnected. The emulator continued at 30 game FPS, 60 video FPS and 100% speed after cleanup, then exited normally when stopped. This is a UI observation after cleanup, not a performance guarantee while captures run.
- The run contains 27 coherent snapshots, 43 activity-write hits and 17 `source-unavailable` gaps. One gap is the initial baseline before room scripts were ready; the other 16 are two eight-slot room-transition clear loops. The coherent snapshots comprise 19 initializer writes and 8 observed stops. Main Hall has 11 snapshots and Dining Room has 16. Sequence numbers are contiguous through the final record. Every valid observation after a gap begins a fresh comparison baseline.
- Each start reports signal 5, its exact watched address `0x800CF68E + slot*0x34`, next native PC `0x80025C24` and 13 completed steps. The initializer hash is the pinned RE1-EVENT-011 value. The captured record has activity 1, state 0 and depth `0xFF`. Each triggering slot is `active` with a nonempty room-source/indexed-entry owner. Main Hall starts bind to `PSX/STAGE1/ROOM1061.RDT` entries 0, 1, 2 and 3. Dining Room starts bind to `PSX/STAGE1/ROOM1051.RDT` entries 0, 1, 2, 3, 4, 9 and 10. For example, sequence 11 initializes Main Hall slot 0 at script PC `0x80151C68`; sequence 32 initializes Dining Room slot 0 at `0x8014A224`.
- Repeated starts preserve observations even when the same slot/entry restarts while active. Main Hall slot 1 restarts entry 3 before its stop. Dining Room slot 2 changes from entry 2 to entry 3 after an observed stop. This confirms that the recorder preserves these starts and slot reuse in this sequence; it does not reconstruct intervening commands.
- Eight stop snapshots have zero steps, omit the watched slot from active positions and contain the corresponding `became-inactive` change. Five report next native PC `0x800261F8`, across Main Hall slots 1/2/3 and Dining Room slots 6/7. Three report `0x8002625C`, across Dining Room slot 2 twice and slot 0. The owned executable's byte-zero store at `0x800261F4` addresses the indexed activity field. The other reported PCs are retained as observations without inferring their exact terminating instruction or cause.
- Snapshots also observe supported `waiting` positions for slots 0/1/2/3/6/7. Three Main Hall snapshots, sequences 12..14, leave the already-running slot 0 `unbound` at script PCs `0x80151CA3`, `0x80151CA7` and `0x80151CAB`. Their newly started slots still bind. This is a remaining interpreter/binding limit during another event's initialization. No unsupported owner or completion state was invented to fill it.
- The 19 initializer captures paused approximately 411.81..446.48 ms each. All 27 coherent capture pauses total 8.839 seconds, excluding gap operations and stop delivery latency. Stepping materially interrupts gameplay, so this mode remains an experiment tool.
- An earlier 142.462-second fresh-boot attempt with brief key taps produced zero snapshots and 16 transition-clear hits, all source-unavailable. It did not establish player-controlled event activation. The later macro run supplies the natural evidence; the failed input attempt is preserved separately.

Artifacts outside Git at `/tmp/tasks/re-map/natural-event-validation/`:

| Artifact | SHA256 | Purpose |
| --- | --- | --- |
| `fresh-jill-a.jsonl` | `f565ee4120af8eb40f2270e8438bcb305c2a8afbf772021a392023e11cc47868` | Earlier tap-only attempt, no source-bound snapshots |
| `fresh-jill-b.jsonl` | `7415a88b892e182bdc62e610e1383a4dce23d80888e3c1c1991ed844eb8f5e38` | Natural opening starts, waits, restarts, stops and room transitions |
| `fresh-training-jill-dining.sav` | `6438e0a363fc291f98244921135c865cb350ab5fd6270fdcea52dcd4dbddea9e` | Private state saved through the emulator after capture cleanup for later experiments |

`audit.py` checks contiguous sequences, exact start addresses/PCs, initialized activity/state/depth, nonempty owner bindings and the eight inactive transitions. It writes `audit.json` with counts, owners, pause measurements, unresolved slots and artifact hashes. CLI/emulator logs and the pinned input source remain in the same directory. The private macro settings were restored after closing the emulator. No game files, new savestate, RAM, log or controller configuration entered Git.

Limits: one fresh Training Jill playthrough and two rooms; no natural activation for slots 4/5, Art Room Map interaction, pickup, door unlock, full puzzle progression, ordinary save/load, savestate reversal of an active event, another character or another revision. The capture binds potential item/door effects without proving they ran. Room transition gaps and three mid-dispatch unbound observations remain explicit. Wide overlapping stores and emulator restores still bypass CPU watches. These results narrow RE1-EVENT-011's activation limits but do not establish finished availability/history interpretation or promote room completion.
History:

- 2026-10-05; Codex root, GPT-6.1 Sol; chose the test setup under the user's autonomous-validation direction, drove normal native controller input, recorded and audited the natural opening, preserved a private continuation state, restored the isolated settings and closed the owned emulator. No external reviewer ran this gameplay experiment.
- 2026-10-05; Codex root, GPT-6.1 Sol; RE1-EVENT-014 identifies the three unbound parent positions as the native VM05 starter's temporary PC+1. A later offline replay resolves those recorded fields with the corrected metadata. The original log and its gameplay limits remain unchanged; this contribution did not run another game experiment.

## RE1-EVENT-014: VM05 exposes parent PC+1 during child initialization

Status: Candidate; exact native inspection, three recorded positions and offline replay
Scope: Resident Evil Director's Cut USA SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`; state-0 indexed-event opcode `05`; runtime cases from Training Jill in Main Hall `00-06`
Environment: Python 3.14.8, Capstone 5.0.9 and pytest 9.1.1 on macOS; original observations from isolated DuckStation `0.1-11894-gc66b2694d`, native GDB localhost port 2345; no new emulator run for this correction
Authored: 2026-10-05; Codex root; model: GPT-6.1 Sol
Basis: hash-checked native helper inspection, RE1-EVENT-013's natural recording, generated semantic metadata, synthetic regressions and replay of recorded event fields
Claim: the parent record temporarily retains VM05 packet address+1 while its child is initialized. This is a readable in-progress position belonging to the parent entry, with its existing state/depth/frame ownership. It is not another VM command entry into the operand bytes. The shared scanner must retain this position separately from sequential control flow.

Evidence:

- All native addresses are PS1 virtual. State-0 table dispatch reaches `0x80026180`, which calls helper `0x800270E8`. The helper loads the selected parent record from little-endian u32 `0x800CF688`. At `0x80027104` it loads the parent's script PC from record+8. Instructions `0x8002710C/0x80027110` add one and store it back before loading requested slot from packet+1 and indexed entry from packet+2. Call `0x8002711C` invokes the shared starter `0x80025C58`. After return, `0x80027124..0x80027138` reload the selected record and add three to its current PC. The full sequential command still advances four bytes. The child initializer and activity-store order remain RE1-EVENT-006/011.
- Main Hall entry 0 has three consecutive VM05 starts at source offsets `0x300A2`, `0x300A6` and `0x300AA`, requesting slot/index pairs 3/1, 2/2 and 1/3. RE1-EVENT-013 snapshots 12, 13 and 14 capture each corresponding child initialization after 13 steps. Parent slot 0 remains active with state 0 and depth `0xFF`, at script PCs `0x80151CA3`, `0x80151CA7` and `0x80151CAB`. Loaded RDT base is `0x80121C00`, so each captured parent PC is exactly its VM05 source offset+1. The prior generated positions contained the command starts and their four-byte successors, but omitted these intermediate values.
- The scanner now retains an `active` point at VM05+1 with the same entry/state/depth/frames after validating the full packet and target index. It does not enqueue or decode that operand address. Event starts, embedded commands and possible child effects are unchanged. The existing runtime reader still requires the exact relocated source table and matching initialized frame pointers. The point reports current ownership; it does not establish that a later item/door command ran.
- Six synthetic regressions exercise parent PC+1, +2 and +3 with and without a loop frame. PC+1 binds the parent and retains possible child item/door effects; +2/+3 remain unbound. Corrupting the initialized loop pointer rejects the intermediate owner. Before the correction, the two PC+1 cases failed as unbound and the four neighboring-operand cases passed. After the correction, all six pass. These byte packets and RAM substitutions are synthetic.
- Two independent owned-disc regenerations are byte-identical, SHA256 `431c83b18df30776560bb527f881f792714b45fd7192b5b743e42ee49f9d0b5a`. The audit against commit `b40db10` verifies 734 added intermediate points across 101 of 334 source variants. Each added point matches a retained VM05 start+1 and preserves its previous command-start state/depth/frames. All old points remain. The only other metadata change is this finding's research ID. Source hashes/ranges, 636 loader choices, cache/coverage flags, dependencies, item/door rules, event entries/starts/commands and possible effects are identical.
- Offline replay feeds all 27 original coherent snapshots' recorded activity/state/depth/PC/frame fields into the old and corrected readers. It reproduces every original event result with the old metadata. Only snapshots 12..14 change with the correction: parent slot 0 binds to `PSX/STAGE1/ROOM1061.RDT` entry 0, with potential door slot 2 and no linked item slot. Every other event and all other 24 snapshots remain identical. Relocated tables are reconstructed from verified source metadata, and unused record bytes are synthetic zeros. This replay checks interpretation of the recorded fields, not another complete live-memory capture or availability experiment.

Artifacts outside Git at `/tmp/tasks/re-map/event-position-inspection/`:

| Artifact | SHA256 | Purpose |
| --- | --- | --- |
| `start-native.txt` | `3fdb2a76fd1489b985418729b908d62ca01dac2cc918b443b5a63ce68596e0fb` | Hash-checked starter/initializer disassembly |
| `generation-audit.json` | `ed632a4db23048b30bc31e2f6c71b0efd56ede75c0378593ed60b376874bd581` | Exact metadata comparison against `b40db10` |
| `replay.json` | `b506af90fc8feb758e5d56a02c11d0a5c890c7c9fa63d4613bee101a0e51c877` | Recorded-field replay and the three corrected owners |

`audit_generation.py` reproduces the metadata comparison, and `replay.py` reproduces the old/new event interpretation using RE1-EVENT-013's original private JSONL. `manifest-a.json` and `manifest-b.json` hold the independent semantic generations. Run `python3 -m pytest -q tests/test_event_activation.py -k parent_start_position` for the six synthetic cases. No game bytecode, RAM, savestate or private log is added to Git.

Limits: runtime evidence comes from three starts in one parent entry during the earlier single playthrough. The other 731 generated intermediate positions have source-derived support only. No new gameplay, pickup, puzzle change, door unlock, normal save/load, active-event savestate reversal or other revision was tested. Other unsupported event positions and source-transition gaps remain explicit. Correcting ownership does not complete availability/history interpretation or establish clearance.
History:

- 2026-10-05; Codex root, GPT-6.1 Sol; traced the temporary parent pointer, reproduced the missing binding before the fix, corrected the shared scanner, regenerated twice and audited/replayed the recorded fields. The focused activation/scanner suite passed 62 tests in 1.36 seconds; the full suite passed 728 tests in 36.68 seconds. Scoped Ruff format/lint checks passed. No project formatter/linter is configured; Ruff was run explicitly on the three changed Python files.
- 2026-10-05; Gemini 3.8 Flash High through agy; completed a supplied-snapshot review of the complete scanner/metadata/test diff and runtime ownership contracts without tools. Returned "No findings." It did not reproduce gameplay.
- 2026-10-05; Gemini 3.1 Pro High through agy; completed the same supplied-snapshot review without tools. Claimed that added positions at offsets 67979, 68063, 150181, 222035 and 223387 invent loop frames or depth. Root compared all nine added source instances at those offsets against `b40db10`; every exact parent point already has the same entry/state/depth/phase/frames. The generation audit verifies this for all 734 added points. Rejected this finding; no implementation change followed. The comparison is preserved in private `review/frame-check.json`. This review did not reproduce gameplay.
- 2026-10-05; Claude Opus 5.5 High through agy; remained unavailable under the quota exhaustion already recorded in RE1-EVENT-011, which reported a reset in 110 hours, 53 minutes, 55 seconds. No new retry or model substitution was made, and no review was attributed to it.

## RE1-EVENT-015: Art Room map interaction binds its natural event starts

Status: Candidate; controlled map accept/decline paths in one Training Jill playthrough
Scope: Resident Evil Director's Cut USA SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`; Art Room `00-07`, source `PSX/STAGE1/ROOM1070.RDT`
Environment: isolated portable DuckStation `0.1-11894-gc66b2694d`, commit `c66b2694da65cece8886ed3d4a069098831f8358`; native GDB localhost port 2345; Python 3.14.8; repository commit `8b87205`
Authored: 2026-10-06; Codex root; model: GPT-6.1 Sol
Basis: normal gameplay input, live activity-write captures and a private log audit
Claim: the shared event reader binds the tested map interaction to indexed entry 0 and its accepted-map child to entry 1. Declining ends the parent without acquiring the map. These observations extend RE1-EVENT-013/014 beyond opening cutscenes without granting acquisition from event activity.

Evidence:

- Continued a fresh Training Jill game through the first zombie, Barry's return and Lock Pick conversation. Entered the Art Room from Main Hall, positioned the movable wooden steps beside the statue and climbed them through normal controller input. No guest memory writes, injected event calls or executable patches were used. Private controller macros and paused frame stepping helped navigation; the activity recordings ran during ordinary continuous gameplay.
- Before interaction, AOT 5 registered callback 9 requesting event slot 9, indexed entry 0, with potential item slot 2. The live allocator selected pool slot 0. Its initializer stopped at PS1 virtual `0x80025C24` and completed all 13 checked steps from RE1-EVENT-011. The reader bound it to `ROOM1070.RDT`, entry 0, with potential Map slot 2 and no unresolved reason.
- The first accepted interaction recorded parent slot 0 and child slot 1, entry 1. Both mapped to the same verified room source and potential item slot 2. Subsequent writes at next native PC `0x8002625C` stopped the parent, then the child. The acquisition bit remained set until the final snapshot, which reported Map taken. All five snapshots were source-bound, with no gaps or unbound parent during the child start.
- Restored the private positioned-before state. A second recording captured a decline: entry 0 started and stopped while Map remained available. A subsequent Yes choice started entry 0 and child entry 1, then stopped both with Map taken. This recording contains seven snapshots, six activity hits and no gaps. Across the two recordings, five natural starts completed 13 steps each and five stops completed without stepping. Initializer capture pauses measured 0.390..0.421 seconds, excluding stop-delivery latency.
- The log audit checked contiguous sequence numbers, single session identity, ending records, source ownership, trigger slots/PCs, item states and manifest provenance. Both recordings use manifest SHA256 `431c83b18df30776560bb527f881f792714b45fd7192b5b743e42ee49f9d0b5a` and profile SHA256 `ff65f07c2dfdbe87ee6e6d95c158395ff0e5921f78de62b92e9df37cdfe0fa4e`.

Artifacts outside Git at `/tmp/tasks/re-map/item-event-validation/`:

| Artifact | SHA256 | Purpose |
| --- | --- | --- |
| `art-map-events-e.jsonl` | `0e8eb83ad72a34b0733b0f6942649f08378342e90c1c3163effc3fc689b67de0` | First accept, two starts and two stops; 41.212 seconds |
| `map-decline-accept.jsonl` | `d5e03a4dc47a4affb58fed9c16b3595f40dd2d00c3c8d69e6a5978b9c17eee76` | Decline followed by accept; 117.612 seconds |

`audit.py`, `audit.json`, setup recordings, CLI/emulator logs, private states and RAM remain outside Git. An earlier setup recording, `art-map-events-d.jsonl`, ended with `Unexpected debugger stop with signal 5` after a native pause action. It recorded no event hit and is retained as failed setup evidence, not an activation result. Restarted capture with a new path and a running emulator. Earlier incorrect step placements and failed zombie retreats are also setup attempts, not successful pickup tests.

Limits: one room, one character/mode and two accepting runs from the same playthrough, separated by a savestate restore. Slots 4/5 activation, other puzzles, natural door unlocking, ordinary save/load and complete execution history remain unvalidated. Watchpoints can affect timing and miss wide writes or emulator restores. This test validates the observed source binding and capture path; it does not establish every story-dependent availability rule.
History:

- 2026-10-06; Codex root, GPT-6.1 Sol; performed normal gameplay, audited both event recordings and kept failed setup attempts separate. UTC records span the preceding UTC date. No production code or generated metadata changed.

## RE1-PICKUP-004: controlled Art Room map acquisition and reversal

Status: Confirmed for this revision; scoped to the Training Jill checks below and the normal-save checks in RE1-SAVE-003
Scope: Resident Evil Director's Cut USA SLUS-00551, executable and Training Jill environment from RE1-EVENT-015; Art Room `00-07` and Main Hall `00-06`
Environment: isolated DuckStation `0.1-11894-gc66b2694d`; coherent paused GDB RAM captures; existing shared tracker at commit `8b87205`
Authored: 2026-10-06; Codex root; model: GPT-6.1 Sol
Basis: controlled gameplay, live flag reads, private savestate restores and offline replay of complete coherent RAM captures
Claim: the Art Room Map descriptor uses GlobalId 145, with acquisition at PS1 virtual `0x800C86ED`, u8 bit 6 (`0x40`), clear when taken. Acceptance changes `0xFF` to `0xBF`; decline does not. Reentry and before/after savestate restores preserve or reverse the observed state correctly. RE1-SAVE-003 adds normal in-game save/load of both acquisition states and earlier-save reversal. This supplies controlled evidence for the earlier RE1-PICKUP-001 lead.

Evidence:

- The source-bound live descriptor identifies Map type `0x4E`, quantity 1, AOT 2 and GlobalId 145. The existing native flag calculation selects byte index 17 in the 32-byte block at PS1 virtual `0x800C86DC` and mask `0x40`. RE1-EVENT-015's first accept and later decline/accept recordings show exactly this byte transition. The room's Ink Ribbon, GlobalId 39, remains available with its acquisition byte `0x800C86E3` equal to `0xFF`.
- After accepting and dismissing the message, captured all 2 MiB of PS1 RAM while paused. The existing `poll_once` reported Map taken, Ink Ribbon available, complete item/door coverage and `INCOMPLETE`. Normal movement and door interaction then produced `00-07 -> 00-06 -> 00-07`. Separate coherent Main Hall and return captures retained the map bit at `0xBF`. On reentry, initialization omitted the already-taken Map descriptor; Ink Ribbon remained available and the room remained incomplete.
- Polling recorded the return state followed by loading the positioned-before savestate: `0xBF -> 0xFF`, Map absent from the registry -> Map available. A separate polling run recorded before -> after savestate restoration: `0xFF -> 0xBF`, Map available -> taken. Both logs ended on interruption without gaps or failures. Savestate restoration proves restoration behavior, not ordinary save-file persistence.
- Replayed five complete RAM captures in six steps through the existing shared tracker, retaining one profile/cache and tracker throughout: before, after, Main Hall, return, before again, after again. The second before step reused the same capture. Every Art Room verdict was incomplete with complete coverage and available Ink Ribbon. The tracker refreshed its cached Map state on both reversals. This is replay of real captured RAM, not substituted flag bytes or a new gameplay run.
- The same replay checked the map response: acquisition revealed only region `07`; entering Main Hall added `06`; later restores retained these session visits and added no other region. The game's map-owned byte at PS1 virtual `0x800C871C` also changed `0x00 -> 0x08` on acceptance and reversed with the states. That ownership interpretation remains a limited observation supporting RE1-PICKUP-001, not a new production address or a reveal trigger.

Artifacts outside Git at `/tmp/tasks/re-map/item-event-validation/`:

| Artifact | SHA256 | Purpose |
| --- | --- | --- |
| `map-rewind.jsonl` | `567edb5b1dba8f4685538f7d1fa377daf86049f3444a507dc21a4e655edaa778` | Reentry state -> positioned-before load |
| `map-load-after.jsonl` | `0b2691035d558795c7075d26334db1f1ce0954369f7fe4698f2a54391b5a1f4a` | Before -> after load |
| `art-map-positioned-before.sav` | `e5b06502d95a22d260f8bc4fdc9e4cb2c07eacb4137f36e3537b2712caee6141` | Steps positioned, Map and Ink untouched |
| `art-map-after.sav` | `193780b5fd8941bcb70066b5e5061c833696b1761cd763eb2f5eb3f2ad468bd2` | Accepted Map, Ink untouched |
| `map-restored-before.bin` | `db76ff09b829b04c257a3492367550b2e78ea36d83881ce651c8bdc435494543` | Coherent before RAM |
| `map-after.bin` | `90dd91cfc306d45d745f829944e2b2c8511682244e4e04bbba838e7665750332` | Coherent first-accept RAM |
| `map-main-hall.bin` | `ac1c99a481c0f6667d9fecfbc333e7bfa6e1aebef1aa52e2a5bcfca47a704610` | Coherent RAM after leaving |
| `map-return.bin` | `1e0c4b7151fa54e99554e5111b0ed5a860dec2645f0ef4521a3fc9b1aaecdcc7` | Coherent RAM after returning |
| `map-restored-after.bin` | `f3a9bfa7a7c3f50620e05661b74013a7c7633d94e59b1727c0560d9cd63b39ff` | Coherent after-load RAM |

Limits: Chris/other mode/revision, last-item clearance and other map pickups remain untested. The Map and Ink states do not prove that every availability condition in the game is implemented. Collected descriptors can disappear on reentry, so registry counts need not retain the prior taken Map row. The observed session visit history intentionally survives savestate loads; completion is recomputed from fresh game state. Normal-save checks are scoped separately in RE1-SAVE-003.
History:

- 2026-10-06; Codex root, GPT-6.1 Sol; collected the map twice, declined once, left/returned normally, restored both private states and audited the existing tracker against coherent captures. Closed the owned emulator normally and restored its private settings byte-for-byte. No game files, saves, RAM or captured bytecode were added to Git.
- 2026-10-06; Codex root, GPT-6.1 Sol; final documentation review checked recorded counts, addresses, artifact hashes, provenance and stated limits. The focused event activation/capture/watchpoint/tracker/map regressions passed 107 tests in 9.26 seconds. `git diff --check` passed; the repository has no configured Markdown formatter or linter.
- 2026-10-06; Codex root, GPT-6.1 Sol; tested both acquisition states through the game's Load Game menu and loaded the earlier save after the collected save, as recorded in RE1-SAVE-003. Promoted only this Training Jill Map rule from Candidate; other availability and event rules retain their own validation limits.

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

## RE1-CLEAR-001: Main Hall's typewriter slot blocks completion after ribbon acquisition

Status: Candidate; existing runtime-capture replay and pinned native/source inspection
Scope: Resident Evil Director's Cut USA SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`; Training Jill, Main Hall `00-06`, source `PSX/STAGE1/ROOM1061.RDT`
Environment: existing coherent 2 MiB RAM captures from RE1-SAVE-003 in DuckStation `0.1-11894-gc66b2694d`; Python 3.14.8 and Capstone 5.0.9 on macOS; no new gameplay or emulator changes
Authored: 2026-10-06; Codex root; model: GPT-6.1 Sol
Basis: captured runtime descriptors, replay through the unchanged tracker, traced rule interpretation and pinned executable/source inspection
Claim: item slot 5 alone causes the captured Main Hall completion uncertainty. The observer omits its live typewriter handler, while source reconstruction retains a possible ordinary-pickup handler on that slot. Slot 6's story awards resolve absent in these captures. This diagnoses the existing verdict; it does not yet establish a shared clearance rule or prove that an optional story event is unreachable.

Evidence:

- Replayed `after-table-position.bin`, `before-save-complete.bin`, `after-normal-load.bin` and `earlier-normal-load.bin` through `poll_once`, each with a fresh tracker and unmodified capture bytes. All four bind to the source above. The ribbon-available capture reports `INCOMPLETE` with complete item coverage; the other three report `UNKNOWN` with incomplete coverage and no live collectible rows. Their hashes are respectively `0d83cfe3b56bee607fb8ff417f3a0ee7c180c6668cdb53e5e919ee06efb3aee5`, `dd5292a01b4ac94c2f79f7b7a3952039f932f3d33bed967a6dc520356ad23edd`, `01f1e60a354e5d555f26a810cff94498d0902b7519bd668a1f80502e10008d4e` and `a32890f93e76be8149122a2c6b8063ffa792f34bad8774ede006dd954c768a78`. RE1-SAVE-003 documents their gameplay provenance and normal-load sequence.
- Traced the existing evaluator's descriptor interpretations without changing its code. Every capture has unresolved item slots exactly `(5,)`. Before pickup it considers the Ink Ribbon creator with handlers 4 and 16. The live available item represents slot 5, satisfying current-room validation. After pickup, fresh initialization reconstruction instead selects the generic typewriter creator and considers handlers 16 and 4. Handler 16 means no normal item; handler 4 on a generic creator remains unresolved. The live observer produces no row representing slot 5, so validation cannot discharge that uncertainty.
- Slot 5's record is at PS1 virtual `0x800B819C`, within the existing 12-byte AOT registry. Before pickup its handler byte is 4 and its source opcode address is `0x8015180E`, the item initializer. After saving, the handler is 16 and the same source remains. After each normal load under this probe, handler 16 points instead to the generic creator at `0x8015182A`. The changing creator pointer matters: a normal load can recreate an interaction rather than restore the exact pre-save descriptor. All three post-pickup captures have ribbon GlobalId 52 cleared at PS1 virtual `0x800C86E1`, byte `0xF7`, mask `0x08`; story bank 1 index 11 is true, versus false in the available capture.
- Source file offset 195598 creates Ink Ribbon in slot 5 under the bank-1/index-11 branch; offset 195626 is its generic handler-16 alternative. Recurring main commands at offsets 196550..196576 test that story bit and acquisition bank 7/index 52, then set the story bit and change slot 5 to handler 16. Indexed entry 25 has a standalone handler-4 setter at offset 202858. RE1-EVENT-004 deliberately treats that standalone effect as optional history; it is not an ordered block whose guard can simply be evaluated against current saved flags.
- Rechecked native setters at PS1 virtual `0x80045BC4..0x80045C34` and `0x80045C38..0x80045C84`. They preserve the registered source pointer, consistent with RE1-SOURCE-001 and RE1-ENGINE-002. The callback table's handler-16 entry selects `0x800385FC..0x800386B8`. It gates on input/control state, searches inventory for type `0x2F` through `0x8002CCB8`, stores the selected record at `0x800B7DCC`, writes its inventory-search result into record offset 2, and starts the save interaction through byte `0x800C8456`. Its direct path reads no collectible identity from the source pointer and does not grant an item or clear acquisition flags. The return delay instruction is a NOP. RE1-SAVE-003 already exercised the typewriter naturally; this inspection adds no new runtime test or claim about every deferred save path.
- Existing manifest programs contain 19 handler-16 creator/setter commands across 15 source variants. That count establishes reuse of this interaction mechanism, not runtime validation in those other rooms. A shared fix should use explicit, source-bound evidence from a coherently observed noncollectible interaction. It must retain pending-pickup handling, dormant-award uncertainty, source-completeness checks and initialization checks. Omission of a live item row alone is insufficient evidence. Historical alternatives must not be pruned merely because current story flags have different values.

Reproduction: bind the four captures to the pinned profile with `match_room_source`, read a fresh rule snapshot and acquisition block, then evaluate the selected program and call `poll_once`. Inspect the registered slot-5 record alongside each verdict. Private diagnostic scripts, `diagnosis.json`, `current-replay.json`, the native audit and the source-variant count are under `/tmp/tasks/re-map/main-hall-clearance/`. The native audit has SHA256 `249b00dce97f8a0e23dd3a2af1b7461834013b1a64d0ddebd6cb473e5fa64032`; executable bytes, RAM and extracted RDTs remain outside Git.

Limits: no tracker implementation changed. This does not validate Main Hall last-item clearance, a live pre-save poll at the moment of ribbon acquisition, absent-item evidence for all handlers, or retaining such evidence after leaving the room. Dormant story awards, generic pickup creators, pending interactions and transitions need explicit regression coverage before this diagnosis authorizes changed completion behavior. The optional event's activation/history remains unresolved; it must not be declared impossible from this replay. Other scenarios, characters and revisions remain untested.
History:

- 2026-10-06; Codex root, GPT-6.1 Sol; reproduced the four current-room verdicts, traced the sole unresolved item slot, compared captured creator pointers and flags, inspected the pinned typewriter/setter routines and counted shared source usage. Recorded a bounded shared-fix direction without editing production code or promoting room clearance.
- 2026-10-06; Codex root, GPT-6.1 Sol; checked the final notes against all four capture hashes/verdicts, registry/flag values, source command offsets, indexed owner, native-audit hash, source counts and finding references. Those checks and `git diff --check` passed. No Markdown formatter or linter is configured; no production code changed.
- 2026-10-06; Codex root, GPT-6.1 Sol; implemented the approved shared current-room evidence described in RE1-CLEAR-002. The original diagnosis and capture provenance remain unchanged; the newer replay resolves the captured current-room verdicts but does not resolve Main Hall's historical reconstruction after leaving.

## RE1-CLEAR-002: explicit live noncollectible evidence resolves current-room slot uncertainty

Status: Candidate; shared implementation, synthetic regressions and replay of existing runtime captures
Scope: Resident Evil Director's Cut USA SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`; current-room coverage for audited handlers 8, 13 and 16, with Training Jill Main Hall `00-06` as the captured validation case
Environment: Python 3.14.8 and pytest 9.1.1 on macOS; unchanged captures from DuckStation `0.1-11894-gc66b2694d`; no new emulator/gameplay run
Authored: 2026-10-06; Codex root; model: GPT-6.1 Sol
Basis: RE1-COVER-002/RE1-CLEAR-001 native contracts, explicit runtime evidence, synthetic tests and actual-capture replay
Claim: a validated live typewriter, item-box or document interaction can resolve an uncertain current item slot when that source has no forced-award path for the slot. A pending pickup overrides the handler classification. The evidence establishes the observed interaction's current function; it does not establish which historical event ran or prove that this handler persists in another room or loaded state.

Implementation and regression evidence:

- `observe_room_items` records unique, bounded noncollectible slot IDs only after the existing loaded-script span, creator opcode, slot identity and full descriptor-width checks. Pending-selected records instead use the pickup reader, including when the visible handler is a document interaction. Failed or changing reads return no slot evidence. Construction asserts that evidence belongs to a successful observation and cannot overlap collectible rows.
- `validate_current_room` uses that evidence alongside observed items to resolve current-slot uncertainty. Source-specific `award_slots` are excluded because a forced inventory/map callback ignores the live handler. The expected-available-pickup check and incomplete-source barrier remain mandatory. Other dormant or missing slots supply no evidence. Historical reconstruction and its cache eligibility rules are unchanged; no room/item exception or new profile address was added.
- Added final poll markers for the pending-item control word and, when pending, its selected AOT pointer. The control-word comparison masks only the configured pending-item bits. Ordinary save/storage/door pointer changes and unrelated control bits remain irrelevant. Synthetic late-start and late-target regressions reproduced stale publication before this recheck, then passed after the fix. A separate control-bit change still publishes normally. This extends the existing coherence checks; separate GDB reads are not an atomic snapshot.
- Synthetic regressions cover both full item and generic creators for each audited handler, both pending-item masks, stale/mismatched/truncated sources, dormant and unaudited handlers, registry changes, conflicting evidence, live pickup/absence reversals, missing expected pickups, incomplete source coverage, same-slot and other-slot dormant awards, and ineligible cached-room reconstruction. Existing fixture RAM and test source snippets are modified only inside tests. These cases do not reproduce new natural gameplay or validate other source variants.

Recorded-capture replay:

- Reused one profile/cache and tracker for ten steps from nine distinct, unchanged coherent captures. Started with Art Room before/after, then Main Hall ribbon available, post-save ribbon taken, all three normal-load captures from RE1-SAVE-003, ribbon available again, the second post-save capture, and the normal Art Room return from RE1-PICKUP-004. `poll_once` verified the runtime signature and bound each current source.
- Main Hall changed `INCOMPLETE -> CLEARED` after ribbon acquisition and remained `CLEARED` in each normal-load capture. Returning to the captured uncollected ribbon state restored `INCOMPLETE`; the following taken state restored `CLEARED`. Every current-room step had complete item coverage. Each cleared Main Hall observation carried noncollectible slot 5. This is real captured-RAM replay, not a live test of the new implementation at the instant of pickup or loading.
- Art Room stayed `INCOMPLETE` with available Ink Ribbon. Its cached Map state followed the fresh acquisition flag through the normal-save reversals. On normal reentry the taken Map descriptor was omitted, as already observed by RE1-PICKUP-004; the current room still had complete coverage and its remaining ribbon. The map revealed only entered regions `07` and `06` throughout.
- After the final Art Room return, Main Hall's historical reconstruction reported `UNKNOWN`. Its live evidence did not override the unresolved event history while it was no longer current. Resolving that away-room verdict remains separate detection work.

Reproduction: run `python3 -m pytest -q tests/test_room_items.py tests/test_tracking_rules.py` for the synthetic boundaries. Replay the private captures with `/tmp/tasks/re-map/main-hall-clearance/verify_live_coverage.py`; detailed results and hashes are in `live-coverage-replay.json` there. Capture provenance/hashes are in RE1-SAVE-003, RE1-PICKUP-004 and RE1-CLEAR-001. The new replay is stored separately from the original save/load audit. All RAM, cards, savestates, extracted game data and scratch files remain outside Git.

Limits: no new live gameplay or ordinary save/load was performed with this implementation. Natural pending-award timing, immediate last-item pickup/reentry, other characters, modes, revisions and all other typewriter/item-box/document variants remain unvalidated. Same-slot forced awards deliberately retain uncertainty unless the existing acquisition/rule model resolves them. No source/program metadata, map geometry, reveal policy or persistence behavior changed. This does not complete RE1 availability or historical event interpretation.
History:

- 2026-10-06; Codex root, GPT-6.1 Sol; implemented the approved shared evidence, retained forced-award barriers, reproduced/fixed final-poll pending-state gaps, added synthetic regressions and ran the ten-step captured-RAM replay. All 760 tests passed in 45.48 seconds. Scoped Ruff lint/format checks and `git diff --check` passed; the repository has no configured formatter/linter.
- 2026-10-06; Gemini 3.1 Pro High via agy; completed an independent review of the supplied implementation diff, current observer/validator, historical cache/rule interfaces, poll publication and synthetic tests. Returned no findings. It did not reproduce gameplay or run the tests. Claude Opus 5.5 High was unavailable under its previously recorded quota exhaustion, so it was not retried before that reset and supplied no review or endorsement.
- 2026-10-06; Gemini 3.8 Flash High via agy; the first review call encountered a provider internal error and ended with an interrupted-stream error. Its returned text was not accepted as a completed review. Retried this model once in a fresh session with the complete diff and affected interfaces/call sites/tests retained; the completed Pro review was preserved.
- 2026-10-06; Gemini 3.8 Flash High via agy; the fresh retry completed successfully and returned no findings. Reviewed the same implementation scope, including source/pending validation, forced-award exclusions, cached reconstruction and the complete new synthetic tests. It did not reproduce gameplay or run checks.
- 2026-10-06; Codex root, GPT-6.1 Sol; inspected the final diff, verified all nine replay capture hashes and the ten-step current/away-room verdict sequence, and confirmed the profile and room manifest are byte-identical to the prior commit. Final scoped Ruff lint/format and `git diff --check` passed. Both accepted Gemini calls reached a completed response, successful terminal result and process exit with empty stderr; no findings required edits. Reviews do not expand the runtime validation state. No Markdown formatter or linter is configured.
- 2026-10-06; Codex root, GPT-6.1 Sol; clarified the final replay step's scope in RE1-CLEAR-003. Its Art Room return capture predates Main Hall ribbon acquisition and restores that ribbon's available flag. It is not an ordinary departure from the preceding collected state. A new normal-load and walked round trip independently reproduced the away-room uncertainty with the ribbon still collected.

## RE1-CLEAR-003: normal Main Hall departure loses coverage with acquisition unchanged

Status: Confirmed for the listed normal-load and walked room transitions; the cause's general interpretation remains Candidate
Scope: Resident Evil Director's Cut USA SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`; Training Jill, Main Hall `00-06` and Art Room `00-07`; tracker commit `e63f475`
Environment: isolated official DuckStation `0.1-11894-gc66b2694d`; existing private RE1-SAVE-003 card copied for this experiment; GDB localhost:2345, Python 3.14.8; native controller macros and paused frame stepping
Authored: 2026-10-06; Codex root; model: GPT-6.1 Sol
Basis: new ordinary game load and controller-driven room transitions, coherent read-only RAM captures and replay through the unchanged shared tracker
Claim: Main Hall reports cleared after normal loading, unknown while the player is in Art Room, then cleared on normal reentry. Its acquired ribbon flag and full acquisition block remain unchanged. This establishes an away-room coverage regression rather than a pickup-state reversal.

Evidence:

1. Started the owned disc without an emulator savestate. Used the game's Load Game menu to load card slot 2, `Jill /01/M.Hall 1F`, from RE1-SAVE-003. After control returned, the current room was `00-06`. Ribbon GlobalId 52 at PS1 virtual `0x800C86E1`, mask `0x08`, was cleared in byte `0xF7`; Map GlobalId 145 remained taken in `0x800C86ED = 0xBF`. `poll_once` reported `CLEARED` with complete item coverage and explicit noncollectible slot 5.
2. Walked around the typewriter alcove, crossed the hall and used the Art Room door normally. After the door animation and room initialization finished, captured `00-07` with the same ribbon and Map bytes. Art Room had available Ink Ribbon, complete item/door coverage and `INCOMPLETE`. Replaying the two captures through one profile/cache and tracker changed Main Hall to `UNKNOWN` with incomplete item coverage.
3. Turned and used the return door normally. After control returned in `00-06`, current Main Hall was `CLEARED` again, with noncollectible slot 5. No item was collected, card save made, game reset or savestate loaded during this round trip. The 32 acquisition bytes at PS1 virtual `0x800C86DC` matched the original slot-2 card payload in all three captures. Only entered map regions `06`, then `06` and `07`, appeared.
4. The two current Main Hall captures have slot 5 registered as handler 16 with a generic opcode-`0x0D` source at PS1 virtual `0x8015182A`. While away, the evaluator's only unresolved item slot is 5. Its alternatives are the generic typewriter creator with handler 16, meaning absent, and the same creator with handler 4, meaning unresolved. Slot 6 resolves absent. The selected source is `PSX/STAGE1/ROOM1061.RDT`, SHA256 `4bb6e58451df65a2ac13f7bf13ce2c914e82753e551c460255af89a1cc858738`.
5. Current live evidence does not make that source's cache eligible. Its manifest has `cache_complete = false` and dependencies include transient room/control bits. `refresh_visited_room` therefore reconstructs from source rather than carrying forward the live typewriter classification. Unconditionally retaining the last cleared color would conceal changed story conditions and earlier loads; this experiment does not authorize that shortcut.
6. Rechecked RE1-CLEAR-002's older final `map-return.bin`, SHA256 `1e0c4b7151fa54e99554e5111b0ed5a860dec2645f0ef4521a3fc9b1aaecdcc7`. Its Main Hall ribbon byte is `0xFF`, mask `0x08` set, and story bank 1/index 11 is false. That replay step is an earlier uncollected state, not a natural departure from the preceding collected Main Hall capture. Its original verdict remains recorded, but it alone cannot establish the regression now reproduced above.

| Private capture | SHA256 | Current room/verdict | Main Hall verdict |
| --- | --- | --- | --- |
| `main-loaded.bin` | `a9f2a970b20cfd3a4151311d76424f5ced14d6ecd2c83d146a6e71186bfbcc33` | `00-06 / CLEARED` | `CLEARED` |
| `art-after-leaving.bin` | `b743e87bc4697c107e0e211bc05252e038c0a90ca9540fb8aaa35052e4310265` | `00-07 / INCOMPLETE` | `UNKNOWN` |
| `main-returned.bin` | `ad1be172396d4d6e8e5c7406a12765109ef20266a55d4d122650e2b82b5f9b33` | `00-06 / CLEARED` | `CLEARED` |

Reproduction: load the tested collected-ribbon card save through Load Game, capture Main Hall, walk to Art Room, capture, return and capture again. Run the unchanged `poll_once` over these captures in order with one profile/cache and tracker. `/tmp/tasks/re-map/away-room-validation/audit.py` checks the recorded sequence, source alternatives, fresh flags, card payload equality, map reveal and restored settings; `audit.json` retains the detailed results. The capture scripts interrupt before reading all 2 MiB. Navigation coordinates are experiment leads, not added profile addresses.

Hygiene: the copied input card SHA256 was `28734147c3547009d6da5290098beca6cc7500aa952e11d2eb1acede17d77761`. After the run its hash was `0477d308bdb7441d28ddb2b8ad0cc699d14fcf89f89494501d540d654e6d952f`; twelve bytes changed within the reserved frame at file offsets 8064..8191. Both save payloads and directory entries were byte-identical; the reserved changes' purpose was not investigated. The original card was untouched. Closed the owned emulator normally and restored its private settings byte-for-byte, SHA256 `1a469b241fc5d5804c65c596599629d5c490705e52bcf1d9e590b09dd7cc5872`. No tracker server or emulator was left running. RAM, cards, extracted code and scripts remain outside Git.

Limits: one collected-ribbon normal load and one walked round trip were tested. No fresh ribbon acquisition, before-pickup normal-save reversal, active story event, alternate character/mode/revision or other room's clearance was newly tested. The three captures establish the regression; they do not establish an implementation fix or prove optional past events impossible. RE1-CLEAR-001/002 and RE1-EVENT-004 retain their earlier provenance and limits.
History:

- 2026-10-06; Codex root, GPT-6.1 Sol; prepared the private card copy, loaded slot 2 normally, performed the two door transitions through native input, captured and audited the three unchanged RAM states, traced the away-room alternatives, and identified the older replay's acquisition rewind. No production code or generated metadata changed.

## RE1-EVENT-016: room setup clears only a bounded portion of local flag storage

Status: Candidate; pinned native inspection and compatible post-initialization captures, without an instruction/watchpoint execution test
Scope: Resident Evil Director's Cut USA SLUS-00551, executable SHA256 from RE1-CLEAR-003; native room setup and script flag-bank 4
Environment: Capstone 5.0.9, owned executable, and the three RE1-CLEAR-003 RAM captures; no emulator memory writes
Authored: 2026-10-06; Codex root; model: GPT-6.1 Sol
Basis: direct MIPS instruction inspection, resolved callers and runtime-value comparison
Claim: native routine `0x80044138` unconditionally stores zero to PS1 virtual words `0x800C300C` and `0x800C3008` at `0x800441A8` and `0x800441B0`. These eight bytes cover flag-bank 4 indices 0..63 under the existing MSB-first little-endian mapping. They provide a bounded candidate initial value for a new room-entry simulation. They do not make the full 32-byte bank persistent or prove that the first 64 bits remain zero after scripts execute.

Evidence:

- Inspected the complete routine through its return at `0x80044844`. It first masks the low four bits of words `0x800C3000` and `0x800C3004`, calls existing reset helpers, writes the two zero words, then clears the eight event activity fields and continues room loading through `0x8004484C`. These instructions do not clear the rest of bank 4; higher indices overlap other runtime structures and need their own semantics.
- Resolved direct calls at `0x8002A750` and `0x80052D4C`. The latter is on the inspected door-loading path. This is source evidence about the routine and callers, not a new runtime trace of either instruction.
- All three RE1-CLEAR-003 post-initialization captures have eight zero bytes at RAM offsets `0xC3008..0xC300F`. Bank-4/index-9 at PS1 virtual byte `0x800C300A`, mask `0x40`, and index 13 in that byte, mask `0x04`, are false. Such final values are compatible with the reset; they do not independently prove which instruction wrote them or exclude later writes.
- The current evaluator deliberately discards initializer local shadows before recurring-main interpretation because earlier ticks may change them, as recorded in RE1-VARS-001. A reset value belongs at a room-entry boundary followed by modeled writes and event starts. Supplying it as an immutable current-main value or reading equal local bytes from another room would be invalid.

Reproduction: inspect the named words/stores/callers in the pinned executable and compare only their bounded bytes in the three captured states. Complete native excerpts are private at `/tmp/tasks/re-map/away-room-validation/full-room-load-native.txt`, SHA256 `a8f86259d18e3489ec373296d4e7dda406ab24e0f925961eb83e98e740b997ad`. No new configured address, reset rule or profile metadata was added.

Limits: no execution breakpoint or write watchpoint verified reset timing relative to all room scripts. Other native helpers and script aliases can subsequently change local bits. Do not initialize the entire bank to zero, use this as proof of earlier event history, or broaden it to other revisions. A shared reconstruction must retain unsupported effects and analysis limits as unresolved states.
History:

- 2026-10-06; Codex root, GPT-6.1 Sol; located the stores with a bounded constant-reference scan, independently inspected the full routine and resolved caller instructions, compared the three capture values, and recorded the bounded reset candidate.

## RE1-EVENT-017: Main Hall pickup-handler activation depends on room-local progress

Status: Candidate; source interpretation under the existing native command contracts, not a completed event-reachability proof
Scope: SLUS-00551 and `PSX/STAGE1/ROOM1061.RDT`, SHA256 from RE1-CLEAR-003; indexed entry 25 and its decoded start sites
Environment: unchanged numeric room manifest, clean indexed-event scan of the owned RDT, existing interpreter contracts and RE1-CLEAR-003 captures
Authored: 2026-10-06; Codex root; model: GPT-6.1 Sol
Basis: branch-aware source inspection and fresh captured persistent flags
Claim: entry 25's handler-4 setter is not an unconditional room action. Its three decoded recurring-main start sites require local bank-4/index-9 to be true. Distinguishing a new room entry from possible past dispatches is necessary before those guards can narrow away-room reconstruction.

Evidence:

- Entry 25's standalone setter at file offset 202858 changes slot 5 to handler 4 and preserves its creator pointer. Its decoded starts at offsets 196280, 196352 and 196424 are all inside the bank-4/index-9 true branch beginning at 196258. They additionally use local indices 10/11/12 and 13. The existing `event_effects` closure deliberately keeps the setter independent of those start conditions.
- Decoded bank-4/index-9 setters are initializer offset 195812 and main offsets 196184 and 196226. The initializer setter is in the story-bank-1/index-5 false branch. The two main setters are in the opening branch that also requires this saved bit to be false. The clean indexed-event scan contains no direct flag-write to bank-4/index 9. This list describes decoded flag commands; it does not rule out every alias or native writer.
- Story-bank-1/index 5 at PS1 virtual `0x800C8697`, mask `0x04`, is true in all three new captures. The corresponding local index 9 is false. RE1-EVENT-016 supplies a candidate reset boundary, rather than borrowing the Art Room's local flag values as Main Hall history.
- The generic creator at offset 195626 has handler 16. Its bytes at the later award-reader's type/quantity/GlobalId offsets would instead read values 16, 129 and 3 if a pickup handler were hypothetically applied. GlobalId 3 is still uncollected in the tested saves. Therefore checking only the real ribbon's acquired GlobalId 52 cannot discharge this generic-handler uncertainty. This is a hypothetical source read, not evidence that the game ever awards that payload.

Assessment: the next shared detection candidate is reconstruction from a fresh room-entry boundary: apply audited resets, interpret initialization against fresh saved state, follow supported script/event start conditions, and retain subsequent local writes and possible scheduling. This differs from filtering arbitrary historical events with current flags. It requires a shared activation model and conservative handling of unsupported starts, aliases, native effects and bounded analysis. No named-item exception, cached-color override or implementation change was made.

Reproduction: inspect the source offsets against the clean scan, locate the three entry-25 starts in the retained branch structure, and compare the named bits in RE1-CLEAR-003. The private RDT and native excerpts remain outside Git. The existing evaluator still returns unresolved slot 5 in the ordinary away-room capture.

Limits: no event-25 execution or exhaustive native/alias reachability was newly tested. True current story bits alone cannot disprove historical dispatches. Reentry initialization, future scheduling, script/local flag relations and remaining-item identity must be modeled before this lead changes completion. Other sources, dormant awards, puzzles and characters retain their existing coverage limits.
History:

- 2026-10-06; Codex root, GPT-6.1 Sol; inspected the three retained start branches and decoded local-progress writers, checked the generic source's hypothetical award fields and GlobalId-3 bit, and separated the entry-reconstruction candidate from unsupported pruning of past history.

## RE1-REENTRY-004: shared fresh-entry reconstruction preserves tested departed-room clearance

Status: Confirmed for the listed unchanged-capture implementation replay; general source reconstruction remains Candidate
Scope: Resident Evil Director's Cut USA SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`; recorded Training Jill Main Hall `00-06` and Art Room `00-07`, plus synthetic shared item/door/event cases
Environment: original captures from isolated official DuckStation `0.1-11894-gc66b2694d`; Python 3.14.8, pytest 9.1.1, Capstone 5.0.9; no new emulator session or game-memory writes
Authored: 2026-10-06; Codex root; model: GPT-6.1 Sol
Basis: pinned native/source inspection, unchanged coherent RAM replay, synthetic regressions and numeric manifest generation
Claim: departed rooms use a separate fresh-entry epoch, initialized from current saved flags and the bounded bank-4 clear from RE1-EVENT-016. Supported initialization, recurring-main writes and reachable event dispatches determine possible interactions. This resolves RE1-CLEAR-003's Main Hall clearance regression in the recorded round trip without carrying forward its prior cleared verdict.

Implementation evidence:

- The profile clears only bank-4 indices 0..63 in the simulation, PS1 virtual bytes `0x800C3008..0x800C300F`. Current-room historical interpretation remains separate and does not treat that reset as immutable current state. Physical aliases, native forget effects and later writes can invalidate simulated values. This uses the source-derived reset contract; RE1-EVENT-016's lack of an instruction/watchpoint execution test remains unchanged.
- Main/event interpretation joins possible earlier ticks and separate dispatches to a bounded fixed point, follows reached SCD starts and native indexed start/restart chains, then applies a recurring-main pass and optional reachable event effects. Full SCD procedure lists retain their synchronous boundary; temporary writes inside one list do not become another runner's starting state. Stable fresh-entry invariants seed the final event interpretation. Unsupported effects, missing semantic payloads, invalid targets and analysis limits prevent clearance.
- Generic creators and extended setters retain their own known little-endian u16 registry parameters in the semantic descriptor. Short setters preserve those parameters. Callback-9 targets use the descriptor's model low byte, not every parameter ever written to that slot. Unreconstructed parameters remain an explicit failure. Source/schema validation binds each parameter writer to its semantic command and slot.
- RE1-REENTRY-003's handler-only registry reset retains prior pointers. A reached reentry setter without this entry's modeled creator therefore rejects reconstruction rather than claiming the slot absent.
- The compiler retains flag-only ordered blocks and standalone semantic event commands, including writes that can enable later starts. Slots changed to pickup or door handlers are tracked even without an item/door creator in that source. Generic payloads cannot silently disappear from completion coverage. No named pickup, puzzle or room exception was added.
- One computation result per source is retained within the profile instance. Program identity, room, layout, fresh rule snapshot, acquisition bytes and labels must all match before reuse. Any changed input recomputes the result. Failed reads still stop publication before interpretation. This cache is transient computation state, with no persisted completion or visit-history change.

Recorded-state validation:

1. Replayed twelve steps from eleven unchanged 2 MiB captures through one profile/cache and tracker. The sequence includes Art Room Map before/after, Main Hall ribbon available and taken, all three normal-load captures from RE1-SAVE-003, RE1-CLEAR-003's walked round trip, then earlier ribbon-available captures.
2. Main Hall remains `CLEARED -> CLEARED -> CLEARED` across `main-loaded.bin`, `art-after-leaving.bin` and `main-returned.bin`, with its acquired ribbon byte still `0xF7`. The later earlier-state captures restore its available ribbon and `INCOMPLETE` verdict. The three original capture hashes and ordinary gameplay provenance remain in RE1-CLEAR-003.
3. Art Room stays `INCOMPLETE` with available Ink Ribbon. Its Map follows available/taken/available across the original normal-save loads, and the taken descriptor can disappear on natural reentry as recorded in RE1-PICKUP-004. Only entered map regions `07` and `06` are revealed. No in-game map ownership or inferred event start grants a visit or acquisition.
4. Final capture replay's slowest local-memory poll was approximately 3.1 ms. An offline projection over all 334 source variants using one donated Herb-before flag configuration returned complete item interpretation for 248 variants and complete door interpretation for 262. It took approximately 4.74 seconds, with the slowest source about 263 ms. These are source variants under one supplied state, not validated gameplay rooms or live GDB latency. Dictionary reuse removed an observed expensive join; the per-profile cache avoids repeating unchanged analysis.

Generation audit: all 334 source identities and init/main/event hashes, source choices, excluded sources and non-program source fields remain identical. Ordered blocks increased from 691 to 2,586, and 6,289 standalone semantic commands are retained. The count of complete source programs remains 312; clean source coverage is not runtime confirmation. Regeneration was repeated byte-identically. Manifest SHA256 is `2ef6de824895419852c671066cc33359b5901a86a4af203d2a84817dd0b8cd65`; profile SHA256 is `c5533c05da0617604b8e94de8a1f2586d7fd2b51e86ba020b1e6c94603c37512`.

Reproduction: run `python3 -m pytest -q tests/test_room_reentry.py` and the shared engine suites. `/tmp/tasks/re-map/room-reentry/audit.py`, `audit.json`, `projection.json`, `generation-audit.json`, and native excerpts retain the private replay/projection evidence. Rebuild metadata with `tools/build_cache_metadata.py` and the pinned profile/owned disc, then compare it byte-for-byte. Captures, extracted code, disc files and cards remain outside Git.

Limits: no new live gameplay, fresh last-item pickup, natural puzzle/door unlock, display-command execution, active-event normal-save/load, alternate character/mode/revision or later-area traversal was tested. Fresh-entry reconstruction describes what the supported source can establish on entry from the current saved state; it does not prove arbitrary earlier event history. Unmodeled native effects, quantity mutations, unsupported callbacks and conflicting conditions still require detection work. A first analysis after changed inputs can be expensive in branching sources. The original visit-history and Mansion 1F geometry limits remain.
History:

- 2026-10-06; Codex root, GPT-6.1 Sol; implemented the approved shared epoch, retained-pointer and parameter checks, expanded numeric metadata, reproduced/fixed synchronous ordering and parameter-reuse failures, optimized the observed slow join and added input-keyed computation reuse. All 787 tests passed in 46.02 seconds. Scoped Ruff lint/format checks and `git diff --check` are the code checks; no formatter/linter is configured in this repository.
- 2026-10-06; Gemini 3.1 Pro High and Gemini 3.8 Flash High via agy; each completed an initial supplied-snapshot review with no findings. These reviews preceded the subsequent parameter-binding, retained-pointer, schema and cache changes. Neither ran tests or reproduced gameplay.
- 2026-10-06; Gemini 3.1 Pro High via agy, conversation `a67f580a-ea46-4d6b-8fe5-78bad49307a2`; reviewed the complete final implementation snapshot, compiler/schema contracts, cache invalidation and new regressions, and returned "No findings." Process exit 0, final agent response DONE, result SUCCESS and empty stderr. No tools, tests or gameplay.
- 2026-10-06; Gemini 3.8 Flash High via agy, conversation `6607fcaf-3b64-4b4f-af00-f8325505c068`; reviewed the same final implementation snapshot, entry bounds, retained pointers, display aliases, dispatch ordering and cache inputs, and reported no findings. Process exit 0, final agent response DONE, result SUCCESS and empty stderr. No tools, tests or gameplay. Primary inspection subsequently corrected the new implementation claim's duplicate ID to RE1-REENTRY-004, preserving the original RE1-REENTRY-001 Herb finding.
- 2026-10-06; Claude Opus 5.5 High via agy; remained unavailable under the quota exhaustion recorded in RE1-EVENT-011, which reported a reset in 110 hours, 53 minutes, 55 seconds on 2026-10-05. No retry before that reset, review, model substitution or endorsement.

## RE1-REENTRY-002: display request has a transient control and scalar-alias footprint

Status: Candidate; pinned native inspection and synthetic effect regressions, without a natural display execution trace
Scope: SLUS-00551 executable identity from RE1-REENTRY-004; SCD opcode `0x29`, deferred display consumer and scalar word aliases
Environment: Capstone 5.0.9 and the owned executable; no game-memory writes or new gameplay
Authored: 2026-10-06; Codex root; model: GPT-6.1 Sol
Basis: direct MIPS handler/consumer inspection and synthetic interpreter tests
Claim: opcode `0x29` advances two bytes and returns one. It sets `0x800C3000` bit 18, native bank-5/index-13, and queues its operand plus a buffer pointer for later display. The consumer can subsequently clear that bit and words `0x800C8680` and `0x800C8682`, scalar indices 6 and 7 under word base `0x800C8674`. Neither a permanent true display bit nor a preceding scalar shadow is a valid cross-tick invariant.

Evidence:

- Handler `0x800466DC..0x8004672C` ORs `0x00040000` into `0x800C3000`, advances the script pointer at `0x800CF640` by two, writes the pointer from `0x800CAB1C` into `0x800CF63C`, stores the packet's second byte at `0x800CF63B`, and returns 1 in the delay slot. Its direct stores do not change acquisition flags or AOT descriptors.
- Consumer `0x80031B38..0x80031B84` tests that bit, passes the queued operand/buffer to display routine `0x80036870`, clears both scalar halfwords and masks the pending bit afterward. The inspected display routine through `0x80036E3C` loads/presents the asset and handles display/input/audio work; it does not dispatch a room SCD procedure or award a world pickup in the inspected path. The tracker does not replay that visual work.
- Shared `display-request` rules conservatively forget the pending bit and both scalar words, covering pending and consumed requests without assuming their timing. The audited nonzero return also participates in deferred event scanning. Synthetic regressions show that prior writes to either scalar alias or a guard on the control bit cannot prove a later pickup's availability. Main Hall's potentially reachable entry 31 uses operand 5; the implementation applies the command contract rather than a named story exception.
- Private handler/consumer/display/input excerpts are `/tmp/tasks/re-map/room-reentry/display-native.txt`, SHA256 `ab43eea40e0e7658c1e93bd5f077faaf127c0727415bc831c0ee83dc040599fc`. The unchanged target executable hash is recorded above.

Limits: no opcode-29 execution breakpoint, asset-display timing, all operand/asset choices or normal-save/load during display was played. The source contract is specific to the pinned executable. Compatible room captures and synthetic agreement do not promote it to runtime confirmation or prove every library helper's arbitrary-input behavior.
History:

- 2026-10-06; Codex root, GPT-6.1 Sol; traced Main Hall's reached but formerly unsupported command, inspected its native producer and consumer, modeled the pending-bit/scalar-alias uncertainty and recorded the source-only scope.

## RE1-REENTRY-003: registry setup retains source pointers behind cleared handlers

Status: Candidate; pinned native inspection with synthetic stale-source rejection, without a new execution trace
Scope: SLUS-00551 executable identity from RE1-REENTRY-004; room setup's 24-record AOT reset
Environment: Capstone 5.0.9, owned executable and synthetic reentry regression
Authored: 2026-10-06; Codex root; model: GPT-6.1 Sol
Basis: direct MIPS routine/caller inspection and interpreter regression
Claim: `0x80044C20..0x80044C58`, called at `0x80044198` before the local flag clear, loops over 24 records and zeros only the handler byte at PS1 virtual `0x800B8160 + 12 * slot`. It does not clear a record's retained source pointer at offset 8. A handler setter in a fresh entry cannot establish an absent descriptor merely because that entry has no modeled creator for its slot.
Evidence: the loop's store at `0x80044C30` is byte-width, its record increment at `0x80044C40` is 12, and the bound at `0x80044C38` is 24. Its remaining store updates the registry cursor at `0x800B7ED8`. The new synthetic regression rejects a reached pickup-handler setter without an entry creator. Private excerpt `/tmp/tasks/re-map/room-reentry/registry-reset-native.txt` has SHA256 `44a760f500ab9d47e0aa9217149fb99555103dc181c5f260bb56903cfc89bc6b`.
Limits: no retained stale pointer was deliberately resurrected in gameplay, and no new instruction/watchpoint reset test was performed. Other reset helpers and revisions retain their existing coverage limits. The implementation rejects that unsupported source history rather than assigning a new pointer value.
History:

- 2026-10-06; Codex root, GPT-6.1 Sol; inspected the complete reset and its caller, recorded the retained-pointer distinction, and added the conservative shared reentry guard and regression.
- 2026-10-06; Codex root, GPT-6.1 Sol; RE1-AOT-003 distinguishes source-independent handler-zero setters from enabling a retained unknown source. Its pinned setter inspection and private experiment do not authorize reconstructing that pointer or executing a source-dependent callback.

## RE1-QUANTITY-001: shared quantity uncertainty no longer invalidates a known pickup

Status: Candidate; pinned source contracts and synthetic regressions, with unchanged-capture replay for existing cases
Scope: Resident Evil Director's Cut USA SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`; SCD quantity transfers and shared current/departed-room interpretation
Environment: Python 3.14.8, pytest 9.1.1, Capstone 5.0.9; the existing captures retain their original isolated DuckStation `0.1-11894-gc66b2694d` provenance; no new emulator session or game-memory writes
Authored: 2026-10-06; Codex root; model: GPT-6.1 Sol
Basis: direct pinned native inspection, semantic interpreter changes, synthetic regressions and unchanged captured-RAM replay
Claim: an audited source-quantity write does not alone invalidate an item's identity or acquisition state. The shared interpreter models quantity separately from handler, type and GlobalId. It joins conflicting amounts into an explicit unreconstructed quantity while retaining a matching item's availability/collection state. Conditions that depend on an unproven amount still block availability conclusions.

Implementation evidence:

- Mode 0 copies a modeled item quantity into the scalar shadow when known. Mode 1 copies a fully reconstructed byte shadow into the descriptor quantity without changing the scalar. Mode 2 conservatively forgets both amount and scalar because earlier inventory and its no-match path are not reconstructed. These effects preserve physical variable/flag aliases and do not write RAM.
- A source with a quantity writer cannot recover its amount just by rerunning its disc creator. The creator uses an unreconstructed quantity until a supported write establishes one. This also prevents a later mode-0 read from treating an old disc amount as current. The conservative marker covers all creators for the affected slot rather than selecting a historical pointer.
- Quantity writers participate in recurring-main and optional ordered/standalone event updates. Independent dispatches remain optional; complete embedded procedure lists retain their synchronous boundary. Amount-only alternatives join without joining different types, GlobalIds, handlers or availability states. Reached writes through missing, generic or door sources reject reconstruction because source+9 does not have an audited item-quantity meaning there.
- Runtime and tracker records require a byte/count or the explicit `ItemQuantityState.Unreconstructed` enum. No amount defaults to zero. The map JSON serializes the enum as `unreconstructed`; item label and remaining/collected text remain available. Current-room runtime observations continue reading exact source quantities and rechecking source bytes before publication.
- All 820 tests passed in 45.05 seconds. The 33 new cases cover same-pass copies, physical scalar reads, zero/maximum amounts, acquisition reversal under both room epochs, divergent quantities versus divergent identities, unresolved quantity guards, optional ordered/standalone event writes, invalid sources, repeated creators, metadata rejection and map JSON. These packets and state changes are synthetic, not gameplay proof. Scoped Ruff lint/format checks and `git diff --check` passed; no project formatter/linter is configured.
- The twelve-step unchanged-capture replay from RE1-REENTRY-004 still passes, including the three normal loads, natural walked Main Hall departure/return and earlier-state reversal. These captures contain no newly validated dynamic quantity interaction. An offline projection of all 334 source variants under the same donated Herb-before flag state increases complete item interpretations from 248 to 252 without a loss. The gains are `ROOM3080`, `ROOM30B0`, `ROOM30B1` and `ROOM30D0`; the two `ROOM1160`/`ROOM6160` quantity-changing variants retain other unresolved conditions. Door interpretation remains complete for 262 variants. These are offline source counts, not confirmed gameplay rooms.
- Regeneration preserves every source identity, script hash, source choice, exclusion and tracking program. All actual disc quantity writes were already retained in ordered event blocks; the new standalone quantity-effect support is exercised by synthetic packets. Only the manifest's research reference list changes. Manifest SHA256 is `990b8382e1fb2f62d219b851781155add23ff17bf873f887a3dd6e9d6d528d6c`. The profile remains unchanged.

Reproduction: run `python3 -m pytest -q tests/test_dynamic_quantities.py` and the full suite. Private `/tmp/tasks/re-map/dynamic-pickups/audit.py`, `audit.json`, `projection.json`, `generation-audit.json` and the two manifest snapshots retain the unchanged-capture/source comparison. Rebuild metadata from the pinned profile and owned disc with `tools/build_cache_metadata.py`. Captures, extracted instructions and game files remain outside Git.

Limits: no natural dynamic quantity pickup, inventory transfer, zero-quantity prompt, puzzle progression, later-area traversal or normal-save/load of a quantity change was played. Mode-2 exact amounts and the historical quantity of a mutable source remain unreconstructed. The native argument-byte contract is specific to this executable, and quantity-dependent conditions, stale sources, unsupported effects and event history retain their own coverage barriers. No new visit, persistence, map geometry or game-revision support is added.
History:

- 2026-10-06; Codex root, GPT-6.1 Sol; implemented the approved shared dynamic-pickup scope, kept quantity separate from acquisition, added synthetic regressions, audited regeneration and replayed the original captures. Existing source-mutation authorship in RE1-SOURCE-001 and native mode contracts in RE1-SCD-007 are preserved.
- 2026-10-06; Gemini 3.1 Pro High via agy, conversation `fe502c9e-b4de-4a85-b1dd-692af809b4b5`; reviewed the complete supplied implementation snapshot, quantity contracts, event/source interfaces and new tests, returning "No findings." Process exit 0, final agent response DONE, result SUCCESS and empty stderr. No tools, test execution or gameplay.
- 2026-10-06; Gemini 3.8 Flash High via agy, conversation `300cd0f1-e015-49b3-a500-6349fb8a6b7d`; the initial call exhausted its output-token limit after repetitive analysis and ended with result ERROR. Its partial response is diagnostic data, not a completed review or endorsement. A single fresh retry used a shorter brief with the supplied code/diff/test snapshot preserved exactly.
- 2026-10-06; Gemini 3.8 Flash High via agy, retry conversation `270d5c1d-7368-4e21-b727-2db8395355ce`; completed the same implementation-scope review and returned "No findings." Process exit 0, final agent response DONE, result SUCCESS and empty stderr. No tools, test execution or gameplay. The only subsequent source edit was a comment explaining the quantity enum's JSON string representation; interpretation and interfaces are unchanged.
- 2026-10-06; Claude Opus 5.5 High via agy; remained unavailable under the quota exhaustion recorded in RE1-EVENT-011, which reported a reset in 110 hours, 53 minutes, 55 seconds on 2026-10-05. No retry before reset, review, substitution or endorsement.


## RE1-ANALYSIS-001: whole-room shadow dependencies preserve published results and reduce branching

Status: Candidate; interpreter inspection, synthetic regressions and captured-RAM replay
Scope: Resident Evil: Director's Cut, NTSC-U, SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`; all 334 generated source variants
Environment: Python 3.14.8, pytest 9.1.1; prior RAM captures retain their original DuckStation environment and provenance
Authored: 2026-10-06; Codex root; model: GPT-6.1 Sol
Basis: interpreter dependency inspection, synthetic tests, comparison against commit `86c42fa`, and replay of previously captured game states
Claim: before deduplicating procedure states, simulated writes can discard physical bits that no command in the whole room program reads. Keeping every flag/scalar predicate dependency and mode-1 quantity input preserves later procedure, event and tick decisions while preventing irrelevant shadow writes from multiplying paths. Acquisition and door access still use fresh game state.

Evidence:

- The mandatory evaluator collects physical byte-address/bit-mask dependencies across initialization, recurring main, ordered event blocks and standalone/deferred event commands. Flag predicates retain their addressed bit, byte/word predicates retain all 8/16 bits, and quantity mode 1 retains its eight scalar input bits even without a predicate. Flag toggles and native conditional writes read their own destination only; any destination observable by a later decision is already retained. Slot descriptors, registry parameters, quantities, event starts, unsupported effects and snapshot reads are not filtered. The existing 4,096-state, 16-stack and 256-descriptor limits remain unchanged.
- `tests/test_script_dependencies.py` adds 34 synthetic cases across current/reentry epochs: thirteen independent unread flag/byte/word branches, flag/scalar aliases, dependencies in later procedures, optional ordered/single events enabling a later main tick, registry callback alternatives retaining scalar quantities, event-only quantity inputs and unsupported effects. The two earlier path-budget tests now read the branched bits so they continue to exercise genuinely retained state. Existing callback, alias, quantity, story/acquisition and load tests also pass.
- All **1,039 tests pass in 43.59 seconds**. The four changed Python files pass manually scoped Ruff lint/format checks; no repository formatter/linter is configured. `git diff --check` passes.
- A differential audit runs both the unmodified evaluator from `86c42fa` and the new evaluator on all 334 programs, both epochs, and three captured RAM states: Herb-before SHA256 `d819fbd41abea6537bf9ce9f4967b479ea1f6278024b9f4e018290343c0bc8d4`, Herb-after `0130861a3a27d2810ccbd0d1e2e7bbc42c64abdac130e1d43dd71ed646784704`, and Chemical-before `bb9110536a02122d7c6a14d489b2e94e7d8224d8ccf297d617694c4eb6e804f2`. All 2,004 old/new evaluations preserve every previously published item descriptor, amount, acquisition state, door and disabled door. Every previously complete item/door result remains complete with the same payload.
- In each reentry snapshot, complete item results increase **258 -> 262** and complete door results **268 -> 272**. Gains are `PSX/STAGE3/ROOM30F0.RDT`, `ROOM30F1.RDT`, `PSX/STAGEA/ROOMA0F0.RDT` and `ROOMA0F1.RDT`. In each current snapshot, items remain **255**, while doors increase **250 -> 252** through `ROOM30B0/ROOM30B1`. These are source variants analyzed against existing flags, not six newly played rooms.
- Reentry analysis of all 334 variants takes 5.07-5.15 seconds with the baseline and 1.09-1.13 seconds with filtering in the paired audit. Current analysis takes 0.25-0.27 seconds before and 0.26-0.28 seconds after. These offline totals do not measure live polling latency or guarantee a speedup for current-room analysis.
- The unchanged RE1-REENTRY-004 twelve-step, eleven-distinct-capture replay passes through one tracker/profile. Main Hall clearance survives departure, normal-load captures and the ordinary round trip; an earlier Ribbon state becomes incomplete again; Art Room remains incomplete with its Ribbon and correct Map reversal. The map reveals only entered rooms 06/07. No RAM values were substituted and no new gameplay was performed.
- Private artifacts are under `/tmp/tasks/re-map/dependency-filtering/`: `audit.py`, `audit.json`, `projection.json`, `differential.py`, `differential.json` and pytest logs. Differential script SHA256 `3bb902d9987b00990b92e024a727a0b34651cf3fc0652312c8203f99fbda18a8`; differential report `8d407e27c2e92d336ee535c72230225f4652a36b33a245e968af7b5c967de549`; replay report `f2d96bd2405b0493bfcea757f6db560f07c30a06035d388f7ae943a777987662`. The committed manifest and profile are unchanged; raw game data and captures remain outside Git.

Limits: this does not establish natural gameplay coverage in the newly resolved variants. ROOM3030 remains unresolved because of descriptor/condition ambiguity; the dependency-filtered run no longer reports incomplete script coverage there. Other conditional spawns, cross-slot event reconstruction, scenario differences and whole-game save/load remain unfinished. Dependencies are conservative for the current command set; future commands that read shadow state must add their physical read dependencies. RE1-ANALYSIS-002 records the rejected broader predicate experiment.
History:

- 2026-10-06; Codex root, GPT-6.1 Sol; inspected all shadow read sites, implemented shared dependency filtering, added synthetic regressions, compared all published old/new payloads across six projections and replayed the existing save/load sequence.
- 2026-10-06; Codex root, GPT-6.1 Sol; corrected the stale ROOM3030 budget limitation after tracing the committed evaluator. Its item slot 1 and door slot 0 remain unresolved, with no failed procedure execution in the donated Herb-before projection. RE1-NATIVE-002's earlier budget observation remains valid for its earlier interpreter.
- 2026-10-06; Gemini 3.1 Pro High via agy, conversation `511d3146-3c2b-422e-8995-b0f1ba519d93`; reviewed the complete supplied diff, full interpreter/schema/event contracts/compiler, new tests and existing callback/quantity/reentry/event regressions. Returned "No findings." Process exit 0, final agent response DONE, result SUCCESS and empty stderr; no tools, tests or gameplay. Review packet 188,352 bytes, SHA256 `d4c682cfb56968c191c3a797b17c8c7a5f345e2237712f7f8aaa21be8311ce7d`. Root independently inspected every shadow consumer and verified the paired payload/replay results.
- 2026-10-06; Gemini 3.8 Flash High via agy, conversation `c3842318-5abe-4bbe-8d00-a54ad05c6812`; completed the same supplied-snapshot review and returned "No findings." Process exit 0, final agent response DONE, result SUCCESS and empty stderr; no tools, tests or gameplay. Neither review reproduced the runtime experiments or promoted their validation state.
- 2026-10-06; Claude Opus 5.5 High via agy; remained unavailable under the RE1-EVENT-011 quota exhaustion, reported on 2026-10-05 with a reset in 110 hours, 53 minutes, 55 seconds. No retry before reset, review, substitution or endorsement.


## RE1-ANALYSIS-002: extending unknown-flag assumptions to current execution exceeded existing budgets

Status: Rejected; private offline experiment, not implemented
Scope: same pinned SLUS-00551 executable and generated source set as RE1-ANALYSIS-001; one donated Herb-before flag configuration
Environment: Python 3.14.8; no emulator interaction
Authored: 2026-10-06; Codex root; model: GPT-6.1 Sol
Basis: private interpreter substitution and source-variant comparison against `86c42fa`
Claim investigated: applying historical repeated-flag assumptions to current execution might resolve the remaining branching limits.
Evidence: removing the historical-only guard for unknown flag assumptions resolved no additional variant and lost eight complete item results and thirteen complete door results under the existing budgets. Items changed 258 -> 250, doors 268 -> 255. Combining that experiment with dependency filtering still lost four item and nine door results despite four gains each. The accepted change only filters dependencies; it preserves the original predicate semantics. Private `/tmp/tasks/re-map/branch-consistency-inspection/comparison.json`, SHA256 `f5dedc5946a78ea5fad2943dd085115c2b4372c2cf341848c44a1e3cce0871dd`, lists the standalone experiment's losses; `dependencies-and-consistency-projection.json` records the combined experiment's source results.
Limits: rejection concerns this bounded interpreter and snapshot, not the native consistency of repeated reads or all possible future analyses.
History:

- 2026-10-06; Codex root, GPT-6.1 Sol; performed private substitutions, observed coverage losses, rejected the extension and left production predicate behavior unchanged.


## RE1-ANALYSIS-003: merging interaction alternatives at matching branch states avoids two procedure limits

Status: Candidate; private offline experiment, not implemented
Scope: Resident Evil Director's Cut NTSC-U SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`; all 334 generated source variants at `d3c36b3`, reentry analysis only
Environment: Python 3.14.8; donated Herb-before RAM SHA256 `d819fbd41abea6537bf9ce9f4967b479ea1f6278024b9f4e018290343c0bc8d4`; no emulator interaction or RAM writes
Authored: 2026-10-06; Codex root; model: GPT-6.1 Sol
Basis: interpreter tracing and three private in-memory substitutions, without production edits
Claim investigated: forward control flow permits joining possible interaction descriptors when paths reach the same script PC, IF stack and physical shadow values. This can reduce duplicate execution while preserving distinct flag states and all descriptor alternatives.

Evidence:

- The updated gap audit finds 92 variants with unresolved item or door coverage. Its mutually exclusive diagnostic categories are 62 with condition/descriptor ambiguity and no failed procedure, 22 with incomplete source coverage, six with other source/context failures, and two exceeding the procedure budget. These counts describe one offline snapshot, not naturally validated rooms.
- Repeating RE1-AOT-003's full-registry-context experiment after shared disabling produces no complete item/door gains, losses or changes to previously published payloads. A separate partial registry experiment retains known handler/mode/extended parameters without claiming a source identity and still rejects source-dependent reads. It also produces no complete coverage gains or losses in this snapshot. These observations do not reject the native contracts or establish that such models are unnecessary in other states.
- The branch experiment processes pending states by ascending PC. At a matching PC, IF stack and exact physical shadow tuple, it unions descriptor alternatives separately for each slot, including a missing descriptor when a path lacks that slot. It leaves paths with different flag shadows separate. `RuleProcedure` already enforces forward branch targets. The existing 4,096-state, stack, descriptor and fixed-point limits are unchanged.
- Complete item projections increase **269 -> 271**. The gains are `ROOM3050.RDT` and `ROOM3051.RDT`; each exposes item slots 15..18 with GlobalIds 203..206 under this captured configuration. Peak states per procedure fall **4,097 -> 524**, and each variant's failed-procedure count falls one -> zero. Door slots 1/2 become interpretable, but slot 0 still has a message-handler ambiguity, so complete door coverage remains **281/334**.
- Across all 334 paired evaluations, every previously published item descriptor, quantity, acquisition state, door and disabled-door payload remains present and equal. No previously complete item or door result becomes incomplete. The report compares published results, not equality of every unresolved alternative or internal execution path.

Private artifacts remain under `/tmp/tasks/re-map/post-disable-inspection/`:

| Artifact | SHA256 | Purpose |
| --- | --- | --- |
| `gaps.json` | `7bd0db110768c74d00ee37ec5fc6554b1ccb8db354c1e13c46f04b6a7a74a18b` | Updated failure categories and traced commands |
| `context-comparison.json` | `f94a1fa759853e928b5e117dbae14f7690f06c80ff9b505f8b4d015bfd8141da` | Repeated full-context experiment |
| `registry-comparison.json` | `d41c99949dcd9738c480cb8148e0ddd69cddbc0fc25a102a242bcf15548830db` | Partial registry experiment |
| `merge_experiment.py` | `bdde18612aac971016ab01b0cf673f051a307b728b4e7515e1f20d3f4a7877f9` | Reproducible in-memory branch substitution and comparison |
| `merge-comparison.json` | `29f6e0d57529fca44e359e53a33e01dcb5b3ae90e4787405508ba5a1d6020c98` | Paired coverage and published-payload results |
| `merge-budget.json` | `88f6927bfed7e37432a98c11c166b05e52e26bb49d898ffc25214fa091c90b73` | Traced procedure counts and the two gained item lists |

Limits: no production implementation, regression suite, current-room experiment, other captured flag state, save/load replay or natural gameplay validation was performed for merging. Joining slots can discard correlations between them; implementation must verify that all consumers remain conservative and that distinct guard states remain separate. The private list-based scheduling is an experiment, not a polling-performance design. Remaining item/door ambiguity and incomplete source coverage are unchanged.
History:

- 2026-10-06; Codex root, GPT-6.1 Sol; reran the gap audit and full-context hypothesis, inspected unresolved descriptor meanings, compared a partial registry hypothesis, then measured the branch-state candidate across 334 variants and traced both prior budget failures. Recorded evidence before requesting implementation approval. Manually reviewed the documentation diff and passed `git diff --check`; no Markdown formatter/linter is configured.
- 2026-10-06; Codex root, GPT-6.1 Sol; implemented the approved shared runner change and recorded RE1-ANALYSIS-004's synthetic, paired-projection and captured-load checks. The initial experiment remains separate from implementation evidence; no natural gameplay validation is added.
- 2026-10-06; Codex root, GPT-6.1 Sol; found that merging distinct descriptor inputs before quantity/registry reads can discard a guard proof, despite matching earlier flag shadows. RE1-ANALYSIS-004 retains those inputs separately and adds the counterexample regressions. The original experiment's narrower measured results remain recorded.


## RE1-ANALYSIS-004: bounded branch merging preserves source and guard uncertainty

Status: Candidate; synthetic regressions, paired offline projections and previously captured RAM replay
Scope: RE1 Director's Cut NTSC-U SLUS-00551 identity from RE1-ANALYSIS-003; shared initialization/main/event runner in current and reentry analysis
Environment: Python 3.14.8 and pytest 9.1.1; capture environments/provenance remain RE1-REENTRY-004's, without a new DuckStation session
Authored: 2026-10-06; Codex root; model: GPT-6.1 Sol
Basis: approved interpreter change, direct invariant/consumer inspection, synthetic boundary tests and comparison against `620f44c`
Claim: pending states can join possible interaction descriptors at matching script PCs, IF stacks, demanded physical shadow tuples and source descriptor inputs to quantity/flag callbacks. The runner retains missing creators and conflicting identity, parameter, quantity and availability alternatives; differing guard inputs remain separate. This avoids some procedure-budget failures without inventing a source or granting acquisition/unlock.

Evidence:

- A heap processes validated forward PCs and uses a unique sequence number to avoid ordering unknown shadow values. Keyed pending buckets union descriptors separately per slot and include `None` when a predecessor lacks that slot. Inputs to quantity reads and door/flag/map callbacks stay in the join key, because those consumers can affect later scalar/flag guards. Enqueueing filters only RE1-ANALYSIS-001's already-unread shadow bits. A union exceeding the existing 256-descriptor limit fails reconstruction; the 4,096-state, 16-stack and 64-iteration limits remain unchanged. The common runner handles both epochs and every existing procedure entry point. No room-specific exceptions, profile/manifest changes or new memory addresses were added.
- `tests/test_branch_merging.py` adds 46 synthetic cases for independent registry branches in init/main/ordered events, distinct physical flag/scalar shadows, missing creators, source-dependent callbacks and quantity writes, alternative flag/event callback parameters, conflicting item/door identities, fresh acquisition reversal, unknown quantities, the descriptor boundary and malformed IF stacks. Four cases preserve a `>= 1` guard after reading either quantity 1/2 or registry flag parameters producing scalar 1/2. An unrestricted descriptor union loses that proof by turning the read into unknown. Separate relevant flag histories still reach the original procedure budget and remain unresolved. All tests use synthetic packets and explicitly supplied test RAM.
- The final full suite passes **1,181 tests in 44.37 seconds**; the final focused file passes **46 in 0.25 seconds**. Ruff formatting and lint checks pass on the modified Python files, and `git diff --check` passes. The repository has no configured formatter/linter; documentation is reviewed manually.
- The unchanged paired audit from RE1-AOT-004 compares both evaluators across all 334 sources, both epochs and Herb-before, Herb-after and Chemical-before captures, using their recorded hashes from RE1-ANALYSIS-001. All **2,004 comparisons** preserve previously published item descriptors, quantities, acquisition states, doors and disabled doors. Previously complete results remain complete and equal. In each snapshot, current item coverage increases **255 -> 259**, reentry item coverage **269 -> 271**. Complete current/reentry door coverage stays **252/281**.
- Current item gains are `ROOM3050/3051` and `ROOM5130/5131`; reentry gains are `ROOM3050/3051`. Under Herb-before, traced `ROOM3050/3051` peak states fall **4,097 -> 273** for current analysis and **4,097 -> 524** for reentry. Current `ROOM5130/5131` peaks fall **4,097 -> 2,932/2,942**. Each prior budget failure disappears. Their unresolved door slot 0 remains unresolved; item gains do not establish complete door access.
- RE1-REENTRY-004's unchanged twelve-step replay of eleven distinct coherent 2 MiB RAM captures passes through one profile/tracker. It covers the recorded Art Map pickup, Main Hall Ribbon states, three normal-load captures, ordinary departure/return and earlier-state reversal. Main Hall remains cleared after departure when its Ribbon is taken and becomes incomplete in the recorded uncollected state. Art Room keeps its remaining Ink Ribbon and Map acquisition reversal. Only entered rooms 06/07 are revealed. No bytes are substituted and no new gameplay occurs.

Private artifacts stay under `/tmp/tasks/re-map/branch-merging/`:

| Artifact | SHA256 | Purpose |
| --- | --- | --- |
| `differential.py` | `3bb902d9987b00990b92e024a727a0b34651cf3fc0652312c8203f99fbda18a8` | Unchanged paired-evaluator audit |
| `differential.json` | `9cb2a5f5a8c52fe55ac9e163762657755f841e39205faddefb48bb3f9dec0f14` | Six projections and preserved published results |
| `audit.json` | `b0fa14d6acb242cad3d1ed50094425d0c9e430f6cd8f550120276f3155698235` | Captured save/load/room replay and source projection |
| `budget.json` | `0e89c1129a35c8361f3b92f442d9a0c4feb967ee86803661d0514eed1ed07bc4` | Old/new procedure traces for the four gained variants |
| `pytest-final.log` | `5889e1e98f970fc9a65f1545ba8011202559633567fe623da7620c7eb24de7e3` | Final full-suite result |

Limits: merged slots can lose correlations between descriptors in different slots, so consumers must remain conservative. No claim of equivalence for every unresolved execution path is made. The source counts are disc variants under three captured flag configurations, not validated rooms or playthrough coverage. Newly resolved variants, broader story progression, alternate character/revision and whole-game behavior still need natural gameplay validation. Existing source/condition and door-handler gaps remain.
History:

- 2026-10-06; Codex root, GPT-6.1 Sol; implemented the approved shared join, inspected its forward-control-flow invariant and source/quantity/parameter consumers, ran the synthetic boundaries and full suite, compared all source projections and replayed the existing recorded load/room sequence. Raw game/capture data remains outside Git.
- 2026-10-06; Gemini 3.1 Pro (High), conversation `4716d2da-566d-48df-b85c-4ef211d5d30d`, and Gemini 3.8 Flash (High), conversation `be3054be-7e47-4048-88a4-d0b2a1757aab`; reviewed the initial 184,572-byte implementation/test snapshot and returned no findings. Both processes exited zero with completed responses, successful terminal results and empty stderr; neither used tools or ran tests/gameplay. These draft reviews were superseded after Codex root found the descriptor-input guard regression and corrected it.
- 2026-10-06; Gemini 3.1 Pro (High), conversation `cd770447-e720-4173-8d26-db30f9affe13`; reviewed the corrected implementation, 46 regression cases, caller/contracts and documentation in a 188,911-byte snapshot (SHA256 `f6e2e3f2144b506d0d6a30350d5cd036f3e0745459423c874f23383c2d38b122`) and returned no findings. Process exit zero, response DONE, terminal SUCCESS and empty stderr were checked; no tools, tests or gameplay were performed by the reviewer. Codex root verified the final diff and test/report evidence independently.
- 2026-10-06; Gemini 3.8 Flash (High), conversation `6110b773-1cd2-43a4-a1a3-fe265816388b`; the corrected snapshot's review encountered an unexpected stream EOF. The CLI retried internally and returned text, but its terminal result remained ERROR despite process exit zero and empty stderr. This failed call is diagnostic output, not a completed review; one fresh retry was dispatched with the identical snapshot.
- 2026-10-06; Gemini 3.8 Flash (High), fresh conversation `01c23e49-5d12-4fed-9c82-785e2c3a7180`; the retry encountered the same unexpected stream EOF and emitted an error step without a completed terminal result. Codex root stopped that failed process (exit one) rather than accepting diagnostic output or making another retry. The final Flash review remains unavailable; no endorsement is claimed.
- 2026-10-06; Claude Opus 5.5 (High); unavailable because of the quota exhaustion recorded on 2026-10-05, with a reported reset in 110 hours 53 minutes 55 seconds from that check. The model was not retried before its reset; no Claude review or endorsement is claimed.


## RE1-AOT-003: disabling a registry handler does not dereference its retained source

Status: Candidate; pinned native inspection and private offline experiment; implementation follow-up in RE1-AOT-004
Scope: Resident Evil: Director's Cut, NTSC-U, SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`; SCD setters `12/13`, visited-room reentry reconstruction
Environment: Python 3.14.8 and Capstone 5.0.9; donated Herb-before RAM SHA256 `d819fbd41abea6537bf9ce9f4967b479ea1f6278024b9f4e018290343c0bc8d4`; no new DuckStation session or RAM writes
Authored: 2026-10-06; Codex root; model: GPT-6.1 Sol
Basis: primary native setter inspection, tracing commit `851bc2c`, and an in-memory experimental evaluator
Claim investigated: a setter writing handler zero can establish a disabled interaction without interpreting the retained source pointer. RE1-REENTRY-003's stale-pointer rejection remains necessary when a setter enables an interaction or a later operation requires its source. Rejecting every setter merely because a creator is missing also rejects source-independent disabling.

Evidence:

- Extended setter `0x80045BC4..0x80045C34` advances the script PC by ten, computes `0x800B8160 + 12*slot`, writes the packet handler and mode to record bytes 0/1, and writes three u16 parameters to record offsets 2/4/6. Short setter `0x80045C38..0x80045C84` advances by four and writes only record bytes 0/1. Both return one. Neither reads, dereferences or replaces the record's retained source pointer at offset 8; neither calls another routine. The inspected command behavior is independent of the handler operand's value.
- The committed interpreter's reentry guard rejects a reached handler setter whenever a possible slot descriptor is missing, including a write of zero. Tracing all 334 source variants under the captured flag configuration finds 99 with unresolved item or door coverage. Of these, 22 have incomplete source coverage, 54 have descriptor/condition ambiguity without a failed procedure, two reach the procedure budget, and 21 have other failed source/context execution. These categories are diagnostic observations, not whole-game validation.
- A private experiment exempts only handler-zero setters from that reentry guard. It preserves existing rejection for enabling an unknown source and preserves source-dependent callback/quantity checks. No production code, profile or manifest was edited. Complete item projections change **262 -> 269**, doors **272 -> 281**, with no coverage losses or changes to previously published item/quantity/acquisition, door or disabled-door payloads.
- Item gains occur in `ROOM1130`, `ROOM20E0/20E1`, `ROOM6130`, `ROOM8130` and `ROOMD130/D131`. Door gains include those seven variants plus `ROOM61A0` and `ROOMD1A0`. These nine source variants are not nine naturally validated rooms. The experiment only uses one captured flag configuration and reentry analysis.
- A separate private experiment supplies the entire reconstructed reentry registry to final ordered event analysis. It produces no complete item/door gains or losses in the same snapshot. Retaining more context alone did not resolve the observed disabling failures.
- Private artifacts under `/tmp/tasks/re-map/next-shared-inspection/` include `gaps.py`, `gaps.json`, `context_experiment.py`, `context-comparison.json`, `disable_experiment.py`, `disable-comparison.json` and `setter-native.txt`. The native excerpt SHA256 is `16f95956a448c5ace95520380de53d3acfe952b233b31adc9ecd74e1c34b1d3c`. Raw executable and capture data remain outside Git.

Limits of the initial experiment: no production fix, regression suite, save/load replay or natural disabling event was validated at that point. A disabled handler does not grant acquisition, identify the retained source or prove that a later enabling/forced callback is safe. Current-room reconstruction, other flag configurations, other characters and other revisions were not changed or validated. No broader exemption for missing source pointers is supported.
History:

- 2026-10-06; Codex root, GPT-6.1 Sol; traced remaining failures, reinspected both native setters, compared two private shared-rule hypotheses and recorded the scoped disabling candidate before implementation approval. Manually reviewed the documentation diff and passed `git diff --check`; no Markdown formatter/linter is configured.
- 2026-10-06; Codex root, GPT-6.1 Sol; implemented the approved disabling scope and added RE1-AOT-004's regression, differential and captured-load evidence. The original experiment and its limits remain recorded; no natural runtime validation is added.


## RE1-AOT-004: shared disabling preserves stale-source rejection and fresh load results

Status: Candidate; synthetic tests, paired source projections and previously captured RAM replay
Scope: RE1 Director's Cut NTSC-U SLUS-00551 identity from RE1-AOT-003; shared handler-zero setters `12/13`, current and visited-room reconstruction
Environment: Python 3.14.8, pytest 9.1.1; existing captures retain the DuckStation environment and provenance documented in RE1-REENTRY-004
Authored: 2026-10-06; Codex root; model: GPT-6.1 Sol
Basis: RE1-AOT-003's native contract, scoped interpreter change, synthetic regressions and captured-state comparisons against `bf75fcd`
Claim: reentry reconstruction can execute a handler-zero setter without a creator for that slot. It keeps an unreconstructed source unreconstructed, preserves known sources and rejects subsequent enabling or source-dependent operations that lack an audited source. Disabling does not grant acquisition or an unlock.

Evidence:

- The missing-creator guard exempts only `aot-handler` commands whose handler operand is zero. Nonzero handlers still reject a path containing a missing source. There is no new pointer, descriptor, quantity or acquisition value. Existing callback/quantity source checks, current-room semantics, event interpretation, profile data, scanner widths and analysis limits are unchanged. The shared rule applies to both setter forms without room-specific exceptions.
- `tests/test_interaction_disabling.py` adds 96 synthetic cases. Both setter forms, modes 0/255, current/reentry epochs and init/main/ordered/standalone events preserve unrelated items and doors. Subsequent short/extended enabling, both forced-callback return forms and quantity writes cannot use a missing source; quantity reads remain unknown when a branch depends on them. Known item/door sources and callback parameters survive disabling; disable alone yields unavailable items or disabled doors without setting acquired flags. Dormant awards still require fresh acquisition. Partial creator branches need a new creator before enabling, and saved story reversal cannot reuse an earlier creator.
- All **1,135 tests pass in 44.90 seconds**. The two changed Python files pass manually scoped Ruff lint/format checks and `git diff --check`. No repository formatter/linter is configured.
- The unmodified evaluator from `bf75fcd` and the new evaluator are compared for every source, both epochs and three unchanged captured RAM states: Herb-before, Herb-after and Chemical-before, with hashes recorded in RE1-ANALYSIS-001. All **2,004 paired comparisons** preserve every previously published item descriptor, amount, acquisition state, door and disabled door. Previously complete results remain complete with the same payload. In each reentry snapshot, complete items increase **262 -> 269**, doors **272 -> 281**. The gains match RE1-AOT-003's seven item/nine door variant lists. Each current snapshot remains **255** complete item results and **252** complete door results, with no gains or losses.
- The unchanged twelve-step, eleven-distinct-capture RE1-REENTRY-004 replay passes through one tracker/profile. Main Hall stays cleared after normal-load captures and its ordinary departure/return; an earlier Ribbon-available state becomes incomplete again. Art Room retains its remaining Ribbon and correct available/taken Map reversal. Only entered rooms 06/07 appear. This replays previous observations without substituting RAM bytes or performing new gameplay.
- Private `/tmp/tasks/re-map/interaction-disabling/` holds `audit.py`, `audit.json`, `projection.json`, `differential.py`, `differential.json` and `pytest.log`. The differential report SHA256 is `f41f851d14093a1f1113985d3a5775dc2f442dfe4732918fc5b01817e20216aa`; replay report `cbe606650931cc4ce25288eabfeeb254ca5e315ab462ae63b3d1a738e5cb0bb5`. The unchanged differential script has SHA256 `3bb902d9987b00990b92e024a727a0b34651cf3fc0652312c8203f99fbda18a8`. Profile/manifest are unchanged and all raw game/capture data remains outside Git.

Limits: source projections are not naturally validated rooms. No newly resolved disabling event, broader story progression, whole-game playthrough, alternate character or other revision was tested in gameplay. The rule does not resolve an unknown retained pointer, authorize a nonzero setter or remove any other source/condition barrier.
History:

- 2026-10-06; Codex root, GPT-6.1 Sol; implemented the approved shared disabling rule, verified retained-source barriers and fresh acquisition reversal, ran the full suite, compared old/new payloads across six projections and replayed the existing load/room sequence.
- 2026-10-06; Gemini 3.1 Pro High via agy, conversation `3a946832-39d2-4915-b6e3-931d8f4ce729`; reviewed the complete supplied diff, full interpreter/schema/event contracts/compiler, native setter excerpt, all new tests and existing reentry/callback/door/quantity regressions. Returned "No findings." Process exit 0, final agent response DONE, result SUCCESS and empty stderr; no tools, tests or gameplay. Review packet 185,975 bytes, SHA256 `56cfe4e31e4440780e84df55fdbf53a21d86afe61f99f1f7b7cb8c011de5151f`. Root independently checked the source-free disable and retained-source barriers before review dispatch.
- 2026-10-06; Gemini 3.8 Flash High via agy, conversation `75402988-0875-4ecc-b440-2c7f2fdbe8c0`; completed the same supplied-snapshot review and returned "No findings." Process exit 0, final agent response DONE, result SUCCESS and empty stderr; no tools, tests or gameplay. Neither reviewer reproduced runtime observations or promoted these Candidate findings.
- 2026-10-06; Claude Opus 5.5 High via agy; remained unavailable under the RE1-EVENT-011 quota exhaustion, reported on 2026-10-05 with a reset in 110 hours, 53 minutes, 55 seconds. No retry before reset, review, substitution or endorsement.

## RE1-QUANTITY-002: transfer writes preserve item identity and collection is independent of amount

Status: Candidate; direct pinned native inspection without a natural quantity-change trace
Scope: executable identity from RE1-QUANTITY-001; opcode `0x4C`, ordinary interaction handler 4 and ordinary take-item routine
Environment: read-only owned executable and Capstone 5.0.9; no runtime mutation or new gameplay
Authored: 2026-10-06; Codex root; model: GPT-6.1 Sol
Basis: direct MIPS inspection, independently rechecking RE1-SOURCE-001 and RE1-SCD-007 contracts
Claim: opcode `0x4C` writes only source+9 for modes 1/2, and scalar `0x800C8660 + index` for modes 0/2. It does not change the registered handler, item type at source+8 or GlobalId at source+20. The normal acceptance routine disables the handler and clears the GlobalId before using quantity. A zero quantity does not, by itself, establish that the registered item has disappeared or that its acquisition flag is taken.
Evidence:

- `0x80048634..0x8004878C` selects mode from packet byte 1, AOT slot from byte 2 and scalar index from byte 3. Mode 1 stores the scalar byte at source+9 in the delay slot at `0x800486C0`. Mode 0 reads source+9 and stores the scalar at `0x800486F0`. Mode 2 searches inventory using source+8 through `0x8002CCB8`; a missing match skips its stores, otherwise `0x80048754/58` store inventory quantity into scalar/source. The handler returns one and advances four bytes. Undefined modes take the already-audited no-op path.
- Interaction handler 4 at `0x80037B80..0x80037BB4` records the selected AOT and sets the pending pickup bit when permitted by its AOT control field. It does not test the source quantity.
- The item creator still registers its source pointer after selecting a zero handler for an acquired item. Its acquisition result is stored at `0x80045FD4`, and `0x80046024` subsequently stores opcode+2 into the record's source pointer. A taken item's modeled creator can therefore still supply the quantity source; a setter without any creator retains the separate stale-pointer barrier from RE1-REENTRY-003.
- Normal take-item routine `0x8002CD30..0x8002D00C` zeros the selected AOT handler at `0x8002CD48`, clears its source GlobalId through `0x8004897C` at `0x8002CE00`, then loads source+9 at `0x8002CE20` for inventory stacking/allocation. There is no preceding source-quantity-zero branch in the inspected path. RE1-COVER-002 retains the original acquisition-dispatch evidence; this reinspection does not add a played acceptance case.
- Private native excerpts `/tmp/tasks/re-map/dynamic-pickups/quantity-native.txt` have SHA256 `88ee732b594a14a666824522d6b2f55187688ec250b29695d438cbf7ec1b94e4`. The unchanged target executable hash and exact instruction locations identify the source.

Limits: this is a source contract, not a breakpoint trace or a natural zero-quantity pickup/save test. It does not establish all earlier UI, inventory-capacity or puzzle conditions. Only item-created source pointers have the implemented quantity interpretation; a transfer through another creator can target a different source field and must remain unresolved.
History:

- 2026-10-06; Codex root, GPT-6.1 Sol; disassembled the complete transfer handler, ordinary interaction handler and acceptance routine, checked exact stores and ordering, and recorded the candidate contract separately from the implementation regressions.

## RE1-SCD-016: movement callbacks preserve descriptors but their request is consumed

Status: Candidate; direct native inspection and synthetic effect checks, without natural callback execution
Scope: Resident Evil Director's Cut USA SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`; interaction callbacks 5 and 6
Environment: owned executable/disc, Capstone 5.0.9 and Python 3.14.8 on macOS; no new emulator or GDB experiment
Authored: 2026-10-06; Codex root; model: GPT-6.1 Sol
Basis: pinned MIPS instruction inspection and synthetic shared-interpreter regressions
Claim: callbacks 5/6 read rectangle geometry through the AOT's source pointer and modify actor movement fields. They preserve the registered handler, parameters, source bytes and acquisition flags. Their pending movement and dialog bits cannot be treated as permanent values across ticks.
Evidence:

- Callback table at PS1 virtual `0x80090404` selects `0x80037BB4..0x80037CC8` and `0x80037CC8..0x80037DD8`. Both read the source pointer at registry offset 8 and actor pointer at `0x800CAB14`. Callback 5 compares actor X against rectangle X/half-width; callback 6 uses Z/depth. Depending on orientation they store direction at actor offset `0xC4`, clear actor byte `0x85`, update actor byte 3 and clear little-endian `0x800CAB00` mask `0x0040`. Both unconditionally OR `0x00400000` into `0x800C3004`, physical flag-bank-5/index-41. Neither calls another function or stores to an AOT/source/acquisition location under the native initialized actor layout.
- The subsequent player path at `0x8003E990..0x8003EA08` ORs `0x0040` into `0x800CAB00` at `0x8003E9EC` and clears `0x00400000` from `0x800C3004` at `0x8003E9F0`. The dialog alias is bank 6 index 25. The interpreter therefore forgets both physical bits, preserving other shadows. An initial implementation preserving a previously false dialog bit was rejected before commit after inspecting this consumer.
- An initially inspected `0x8002A7F4` consumer accesses `0x800C3000`, not the movement word at `0x800C3004`; it does not supply the movement-clear contract. This distinction was checked directly against its address construction.
- `tests/test_native_callbacks.py` checks both callbacks, missing sources, disabled modeled creators, independent items/doors, recurring main/indexed dispatch and the consumed bits. Source geometry must have a modeled creator; a missing retained pointer remains unresolved. The tool never changes emulator RAM.
- Native excerpts are private at `/tmp/tasks/re-map/native-callbacks/native.txt`, SHA256 `8dcbe8855283dc2c7769132607f5b7d6b1096dfc4d47abb574f8ec5c5b4f45eb`. They include both callback bodies, the consumer, registry setters and dispatch returns.

Limits: no natural callback activation, actor movement, consumer timing or normal save/load of that interaction was tested. Actor coordinates and orientation are not reconstructed. These rules cover forced SCD dispatch; they do not infer the history of every registered native interaction. Other actor callbacks and revisions retain their own limits.
History:

- 2026-10-06; Codex root, GPT-6.1 Sol; inspected the callback bodies and pending consumer, rejected the permanent-bit interpretation, and added shared conservative effects and regressions. RE1-NATIVE-001 records generation/replay checks separately.

## RE1-SCD-017: flag callback consumes three registry words

Status: Candidate; direct pinned native inspection and synthetic parameter/alias checks
Scope: same SLUS-00551 executable as RE1-SCD-016; interaction callback 7 and generic/extended registry writers
Environment: owned executable/disc and Capstone 5.0.9; no new live experiment
Authored: 2026-10-06; Codex root; model: GPT-6.1 Sol
Basis: direct native dispatch, store and flag-target inspection
Claim: callback 7 uses the little-endian u16 fields at registry offsets 2/4/6 as bank/index/operation. Operation zero clears one MSB-first bit; every nonzero value sets it. Banks 5/6 select a fixed word and use index modulo 32. Other banks select `base + 4 * (index // 32)` using the full u16 index.
Evidence:

- Body `0x80037DD8..0x80037EF8` checks bank `<10`, selects its address through the table at `0x800103EC`, reads index at offset 4 and operation at offset 6, and constructs `0x80000000 >> (index & 31)`. Stores at `0x80037ECC/0x80037EEC` implement set/clear. Bank bases agree with the existing profile. The bank-5/6 cases jump directly to `0x80037EA4` without adding a word offset. An undefined bank reaches that code without establishing the address register; the interpreter rejects it. Non-fixed-word indices above 255 exceed the modeled bank and also reject reconstruction rather than inventing an alias.
- Generic creator `0x80045E00..0x80045EA8` copies packet offsets 12/14/16 into registry offsets 2/4/6. Extended setter `0x80045BC4..0x80045C38` copies packet offsets 4/6/8 into the same fields. Short setter `0x80045C38..0x80045C88` changes only handler/mode. The semantic descriptor retains all three words per exact writer offset and slot. Previously generated metadata retained only the first two.
- Forced dispatch at `0x800470B8..0x80047124` returns one regardless of callback result. `0x80047AE0..0x80047B18` subsequently sets/toggles pending flags and returns zero, as originally recorded in RE1-SCD-014. Callback 7's own zero return does not become a predicate or repeat a deferred command.
- Synthetic tests cover every bank, bit/word boundaries, u16 operation and fixed-word index extremes, invalid addresses, short/extended setters, conflicting parameter alternatives, physical bank aliases, source-context bytes that cannot supply local history, command/pending ordering, acquisition reversal and failed target reads. Acquisition results remain fresh RAM values even when a simulated callback changes an acquisition-bank shadow. The native excerpt hash is in RE1-SCD-016.

Limits: no flag callback was activated naturally. The implementation does not replay collection, infer unsupported creator parameters, follow arbitrary native pointers or extend flag banks beyond their modeled bounds. Invalid native operands are explicit unsupported paths, not confirmed game behavior. Other callback IDs remain separately scoped.
History:

- 2026-10-06; Codex root, GPT-6.1 Sol; inspected all native branches and writer fields, retained the third u16 word, and implemented bounded source-dependent effects without changing acquisition provenance.

## RE1-NATIVE-001: shared forced callback support and source projection

Status: Candidate; implementation, synthetic/source checks and unchanged recorded-state replay
Scope: pinned SLUS-00551 identity from RE1-SCD-016; forced callbacks 5/6/7 across generated source variants
Environment: Python 3.14.8, pytest 9.1.1, Capstone 5.0.9 on macOS; existing DuckStation `0.1-11894-gc66b2694d` captures; no new gameplay
Authored: 2026-10-06; Codex root; model: GPT-6.1 Sol
Basis: RE1-SCD-016/017 native contracts, source regeneration, synthetic tests and captured-RAM replay
Claim: the shared compiler/interpreter now supports these forced callbacks without blanket source rejection. Parameters follow modeled creators/setters, branch alternatives join conservatively, unsupported source/operand paths remain unresolved and fresh acquisition flags remain authoritative.
Evidence:

- Two owned-disc generations are identical: manifest SHA256 `30ed335b05dfbefdbf6275c2eb52bc73044725da4c9b913003922ecd252c524b`. Relative to `d914405`, 20 command occurrences across 12 source variants become callback rules: callback 5 has four occurrences, 6 has twelve and 7 has four. All 1,981 registry-writer rows gain their third source u16. Reverting only those classifications and removing those words reproduces every previous source row exactly. Source signatures/ranges, loader choices, item/door identities, acquisition IDs, coverage flags, mutable fields and all other commands are unchanged; metadata gains these three research references.
- All 944 tests pass in 45.35 seconds, including 124 new callback cases. Scoped Ruff lint/format checks pass for the seven changed Python files; the repository has no configured formatter/linter. The final diff was inspected and `git diff --check` passed before commit.
- The original twelve-step RE1-REENTRY-004 captured-RAM replay passes. Main Hall remains cleared after departure and normal loads, the earlier ribbon-available capture restores incomplete, Art Room stays incomplete with its ribbon remaining, and only entered regions 06/07 appear. This adds no live save/load or callback execution observation.
- Under the same donated Herb-before flag configuration used in RE1-QUANTITY-001, offline item-source completeness rises from 252 to 258 of 334; door-source completeness rises from 262 to 268. Neither loses a previously complete variant. Both gain `ROOM2070/2071`, `ROOM6100/6101` and `ROOM7070/7071`. The full projection takes about 4.94 seconds here, with the slowest source about 283 ms. These counts describe source interpretation under one snapshot, not rooms tested in gameplay or continuous polling latency.
- Private reproduction artifacts are `/tmp/tasks/re-map/native-callbacks/audit.py`, `audit.json`, `projection.json`, `generation-audit.json`, both generated manifests and native excerpts. Regenerate with `tools/build_cache_metadata.py`, the owned CUE and pinned profile; run `tests/test_native_callbacks.py` for the synthetic contracts. Restricted code/captures/disc files remain outside Git.

Limits: whole-game runtime validation, other unresolved predicates/effects, source scanner gaps, ordinary activation of these callbacks, other characters/revisions and later-area floor plans remain unfinished. The map still has Mansion 1F geometry and entry-only reveal. Visit history remains session-scoped. No new game profile, persistence policy or map geometry is introduced.
History:

- 2026-10-06; Codex root, GPT-6.1 Sol; implemented the approved shared callback feature, audited unchanged source fields, checked fresh flag reversal and replayed the original captures. Existing native/source findings and human capture attribution remain as recorded.
- 2026-10-06; Gemini 3.8 Flash High via agy, initial conversation `40e9da17-a735-4301-9092-628acaa72199`; reported missing essential implementation/test context after the transport truncated the large generated diff. Its SUCCESS result is not a completed implementation review or endorsement. The initial Pro conversation `b9bfeff6-336f-4af0-b909-985df28d2150` was terminated after diagnosing that same packet defect, with no response. A single fresh call per model uses the complete authored source/test snapshot and an exact compact generated-data delta.
- 2026-10-06; Gemini 3.1 Pro High via agy, fresh conversation `64674351-9a4d-44f6-a863-ad58bf0affbb`; reviewed the supplied interpreter, source/schema interfaces, native contracts, complete new tests and exact metadata delta, returning "No findings." Process exit 0, final agent response DONE, result SUCCESS and empty stderr. No tools, tests or gameplay were run by the reviewer.
- 2026-10-06; Gemini 3.8 Flash High via agy, fresh conversation `cd96a4df-b3ff-4548-94ee-36b2c5b6528f`; exhausted its output-token limit after repetitive analysis and ended with result ERROR. The partial response is diagnostic data, not a completed review or endorsement. This was the single fresh recovery attempt; no further retry or substitution. No tool steps were attempted. Root's direct audit and Pro's completed perspective remain the review basis.
- 2026-10-06; Claude Opus 5.5 High via agy; remained unavailable under the quota exhaustion recorded in RE1-EVENT-011, which reported a reset in 110 hours, 53 minutes, 55 seconds on 2026-10-05. No retry before reset, review, substitution or endorsement.

## RE1-SCD-018: lighting writes require a bounded room-file destination

Status: Candidate; pinned native instructions and synthetic bounds tests
Scope: RE1 Director's Cut, NTSC-U, SLUS-00551, disc revision pinned by `SLUS_005.51` SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`; opcode `40`
Environment: read-only owned executable/disc inspection, Python 3.14.8 and Capstone 5.0.9; no new DuckStation gameplay
Authored: 2026-10-06; Codex root; model: GPT-6.1 Sol
Basis: primary native inspection, source-file bounds and synthetic tracking tests
Claim: native command `40` returns one and writes lighting fields inside the loaded RDT. Reconstruction treats it as a constant successful result only when every destination remains in the unreferenced prefix after the 19-entry offset table and before every nonzero pointed section. An unsafe index remains an unsupported effect.

Evidence:

- Dispatch entry `0x80091108 + 4*0x40` selects `0x8004828C`. The handler through `0x80048330` advances PC by 16, sign-extends packet byte 1, and loads the current room-file base from PS1 virtual `0x800CAB10`. Destination record offset is `0x94 + 44*index`. Seven sign-extended halfwords are stored as little-endian u32 values at record offsets `8, 12, 16, 20, 24, 28, 40`. The final word ends at record+44. The return delay slot at `0x80048330` sets one.
- The last source halfword is read at packet+16, independently of the 16-byte PC advance. RE1-SCD-008's required 18-byte read window and separate bounded operand tail remain unchanged. The semantic compiler neither truncates the read nor changes instruction flow.
- Native code does not bound its signed index. The compiler requires the first destination at or after file offset `0x94` and the last word's end no later than both the earliest nonzero RDT section offset and the supplied file's end. It does not assume only indices 0/1/2 exist or use a room-name exception. Negative/header targets and writes reaching another section reject reconstruction when reached.
- Owned `ROOM3030.RDT` uses indices 0/1/2 at file offsets `0x1278C/0x1279C/0x127AC`. Its earliest pointed section is `0x1F4`; all three destinations fit. These are static source observations, not executions of those event commands.
- `tests/test_rendering_commands.py` checks safe higher indices with a larger synthetic prefix, signed negative indices, positive indices reaching scripts, an exact last-word section boundary, SCD branch returns, independent event dispatch and preservation of flags/items/doors. Existing native-decoding tests retain the overlapping source read and truncated-tail cases.

Limits: this proves a source contract for the pinned executable and bounded destinations, not natural puzzle execution, lighting correctness, other revisions or whole-game item coverage. Rendering values and camera/actor predicates remain outside reconstructed availability. The instruction excerpt is private at `/tmp/tasks/re-map/rendering-commands/native.txt`, SHA256 `3505a3e6c55fca2c9d153eff05686ef33866c351cc6e92a0ea7a82a88c2b330c`; no executable bytes or room assets are committed.
History:

- 2026-10-06; Codex root, GPT-6.1 Sol; inspected the native writes and return, added the mandatory destination bound and synthetic regressions. RE1-NATIVE-002 records shared generation and replay checks separately.


## RE1-SCD-019: model recoloring preserves tracked descriptor and flag state

Status: Candidate; pinned native instruction/helper inspection and synthetic tests
Scope: same executable/revision as RE1-SCD-018; opcode `4D`
Environment: same read-only inspection/test environment as RE1-SCD-018; no new gameplay
Authored: 2026-10-06; Codex root; model: GPT-6.1 Sol
Basis: primary handler/helper inspection and synthetic tracking/event-return tests
Claim: command `4D` advances two bytes and returns one after recoloring model rendering data. It preserves the modeled collectible/door descriptors, variable bytes, saved flags and local flag aliases. Its second packet byte is not a state operand.

Evidence:

- Handler `0x8004878C..0x80048950` loads the model-data pointer at PS1 virtual `0x800C51BC` and calls `0x8005CD94` fourteen times at model-relative offsets `0, 0x7C, 0xF8, 0x45C, 0x5D0, 0x174, 0x1F0, 0x26C, 0x2E8, 0x364, 0x3E0, 0x4D8, 0x554, 0x64C`, with color arguments `0x30, 0x80820, 0x606060`. It reads no packet operand. PC advances two at `0x80048928..0x8004893C`, and the function returns one at `0x80048934/0x8004894C`.
- The complete helper `0x8005CD94..0x8005CEFC` sets model-part header bit `0x80`, preserves primitive words' upper byte while replacing their color bits, and writes scratchpad PS1 virtual `0x1F800000` and, on its copied-model path, `0x1F800018`. It reads `0x800C3000` bit 0 to select that second path. The copied-model addresses come from actor/model pointers, including the actor at `0x800CAB14`; it does not change these pointers or the selector bit. There are no further calls from this helper. These rendering destinations are separate from the modeled flags, variables and AOT/script descriptors.
- Static inspection finds eighteen commands across `ROOM30B0/30B1`, `ROOM30F0/30F1` and `ROOMA0F0/A0F1`, three per source. RE1-NATIVE-002 records their generation delta. Synthetic tests use nonzero packet padding, both tracking epochs, branch success, ordered/single event dispatch, descriptor preservation, flag preservation and acquisition reversal. An FD deferred call cannot take its exit branch after this nonzero return.

Limits: no live recoloring, model allocation or later-area gameplay was performed. This does not resolve model/actor predicates or certify arbitrary invalid native model pointers. RE1-SCD-018 identifies the pinned instruction excerpt and hash.
History:

- 2026-10-06; Codex root, GPT-6.1 Sol; inspected all fourteen calls, the complete helper and the caller's advance/return; added shared continuing-command semantics and regressions. Original RE1-SCD-008 width provenance is unchanged.


## RE1-SCD-020: effect-record flag writes do not change the aliased pool header

Status: Candidate; pinned native instruction inspection and synthetic tests
Scope: same executable/revision as RE1-SCD-018; opcode `4E`
Environment: same read-only inspection/test environment as RE1-SCD-018; no new gameplay
Authored: 2026-10-06; Codex root; model: GPT-6.1 Sol
Basis: primary native inspection and synthetic tracking/event-return tests
Claim: command `4E` returns one after modifying an existing effect pool's per-record flag halfwords. It reads each record's active header, preserves the header and writes no modeled flag or collectible/door descriptor. It therefore requires no pool-header invalidation, unlike effect creation/clearing commands in RE1-SCD-007/011.

Evidence:

- Handler `0x80047950..0x80047A0C` advances PC by four and reads byte 1 as operation and packet+2 as a little-endian u16 mask. It visits 64 records at PS1 virtual `0x800C3024 + 0x84*record`. For a nonzero header halfword, operation 0 ORs the mask, 1 ANDs its complement, and 2 XORs it into the flag halfword at record+14. Other operation bytes skip the store. All paths return one, including an inactive pool and default operations.
- Flag-store addresses run from `0x800C3032` through `0x800C50AE`, each two bytes. They lie outside every modeled flag-bank and scalar-variable range. The first record's header `0x800C3024/0x800C3025` overlaps bank 4; `4E` only reads it. It also preserves the player-state gate at `0x800C5125` used by door interpretation. The loop contains no calls or AOT/source writes.
- Owned `ROOM3030.RDT` uses mode 0 and 1, both with mask `0x8000`, at offsets `0x11538/0x11748`. Tests include modes 0/1/2/255 and mask `0xFFFF`, preserved local/persistent flag shadows, fresh acquisition reversal, SCD branch results and deferred-return reachability. Adding `4E` to the continuing set also makes its nonzero FD return explicit rather than exploring a nonexistent exit.

Limits: no controlled live effect-pool mutation was captured. Actor/effect-dependent availability remains unresolved where the corresponding predicates lack a supported state model. RE1-SCD-018 identifies the private native excerpt and hash.
History:

- 2026-10-06; Codex root, GPT-6.1 Sol; inspected the complete loop, every operation/default path and the exact write addresses; added shared continuing/nonzero semantics and synthetic regressions.


## RE1-NATIVE-002: shared rendering command support and unchanged projection limits

Status: Candidate; generated source comparison, synthetic tests and recorded-RAM replay
Scope: pinned SLUS-00551 identity from RE1-SCD-018; commands `40/4D/4E` across all generated source variants
Environment: owned disc/executable, Python 3.14.8, pytest 9.1.1 and Capstone 5.0.9; earlier captures retain their documented DuckStation environment and provenance
Authored: 2026-10-06; Codex root; model: GPT-6.1 Sol
Basis: RE1-SCD-018/019/020 contracts, source regeneration, synthetic tests and unchanged captured-RAM replay
Claim: shared interpretation recognizes the remaining 23 rendering-command occurrences in seven source variants while preserving conservative completion and save/load refresh. Under the existing single offline flag snapshot, complete item and door coverage does not increase.

Evidence:

- Two independent disc generations produce the same manifest, SHA256 `4dcb36457ad9040ee868b3df06537d67b3320f54bed7ab0c5043005ab8c07767`. Against commit `4e947a8`'s manifest SHA256 `30ed335b05dfbefdbf6275c2eb52bc73044725da4c9b913003922ecd252c524b`, the only row differences are 23 commands changing from `unsupported-effect` with no operands to `constant-test` with result one. The four new research references are the only other changes. Every signature, range, identity, source-choice row, mutable-field declaration, coverage flag and event-flow record is unchanged. There remain 334 sources and 636 loader choices.
- `ROOM3030` has three `40` and two `4E` changes; `ROOM30B0/30B1`, `ROOM30F0/30F1` and `ROOMA0F0/A0F1` each have three `4D` changes. The private source audit binds extraction to each committed full-source SHA256. No room-specific interpretation was added.
- All **1,005 tests pass in 45.66 seconds**, including 61 new rendering cases. The four changed Python files pass manually scoped Ruff lint/format checks; no repository formatter/linter is configured. `git diff --check` passes.
- The unchanged twelve-step, eleven-distinct-capture replay from RE1-REENTRY-004 passes through one tracker/profile. It preserves Main Hall clearance after departure, Art Room's remaining Ribbon and available/taken Map reversal, three normal-load captures, the later ordinary round trip, earlier Ribbon-state reversal and reveal only for entered rooms 06/07. This performs no new gameplay and substitutes no RAM values.
- The same donated Herb-before flag configuration projects all 334 source variants offline. Complete items remain **258**, complete doors remain **268**, with no gains or losses. ROOM30B0/30B1 already resolved before this change. Tracing current reentry analysis of ROOM3030 and ROOM30F0 reaches the existing 4,096-state procedure budget in recurring main scripts at file `0x112A8` and `0x35DE6`, respectively. The other main-script/condition limits are unfinished detection work, not reasons to guess clearance. The projection took 5.06 seconds total; this is not a live polling-latency measurement.
- Private artifacts are under `/tmp/tasks/re-map/rendering-commands/`: `source-audit.json`, `generation-audit.json`, `manifest-generated.json`, `manifest-repeated.json`, `audit.py`, `audit.json`, `projection.json`, `projection-delta.json`, `remaining-blockers.json` and `pytest.log`. The regeneration command remains `tools/build_cache_metadata.py` with the owned CUE and pinned profile; none of the raw game/capture data is committed.

Limits: natural execution of these commands, the five still-unresolved variants, broader puzzles/story events, other characters and other revisions remain unvalidated. This improves shared command interpretation without claiming new whole-room gameplay coverage. Map geometry and persistence policy are unchanged.
History:

- 2026-10-06; Codex root, GPT-6.1 Sol; inspected the primary native effects, added bounded/shared semantics and 61 synthetic cases, regenerated twice, compared every manifest field, reran the unmodified captured-state sequence and recorded the unchanged projection and remaining analysis limits.
- 2026-10-06; Gemini 3.1 Pro High via agy, conversation `0114f608-371e-4115-9200-c8f86a5c78bb`; reviewed the complete supplied diff, compiler/interpreter/scanner interfaces, native handler/helper excerpts, new tests and exact generation delta. Returned "No findings." Process exit 0, final agent response DONE, result SUCCESS and empty stderr; no tools, tests or gameplay. The self-contained review packet was 188,931 bytes, SHA256 `55c31ba02e86045177ee097d03fef24252849827f27609d31b80490fd1c5d0d5`.
- 2026-10-06; Gemini 3.8 Flash High via agy, conversation `76e30b86-0510-4877-886e-bd9939152289`; completed the same supplied-snapshot review and returned "No findings." Process exit 0, final agent response DONE, result SUCCESS and empty stderr; no tools, tests or gameplay. Root independently checked the native write boundaries, preserved flags and conservative projection before accepting the review result.
- 2026-10-06; Claude Opus 5.5 High via agy; remained unavailable under the quota exhaustion recorded in RE1-EVENT-011, which reported a reset in 110 hours, 53 minutes, 55 seconds on 2026-10-05. No retry before reset, review, substitution or endorsement.
