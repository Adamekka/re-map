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

## Suggested next experiments

1. Enable `Debug/EnableGDBServer` with port 2345, connect with a small Python GDB client, and read 16 bytes at `0x80000000` while the game idles. Record whether the game keeps running.
2. Move between two known RE1 rooms and poll a small candidate window at 10 Hz. Save the log with game revision and DuckStation version.
3. Take `.sav` files before and after one pickup, decompress with the header logic above, and diff for stable changed bytes.
4. Only if GDB polling fails, prototype Mach `vm_read` against the DuckStation PID for the same addresses and compare maintainability.
