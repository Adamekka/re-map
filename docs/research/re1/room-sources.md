# RE1 room sources research

[Documentation index](../../README.md) · [Claim index](../../research.md)

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
