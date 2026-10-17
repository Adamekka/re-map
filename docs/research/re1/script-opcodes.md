# RE1 script opcodes research

[Documentation index](../../README.md) · [Claim index](../../research.md)

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

## RE1-SCD-021: item-interaction predicates compare transient byte variables

Status: Candidate; pinned native handler, writer and reset inspection, without an execution trace
Scope: RE1 Director's Cut NTSC-U SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`; SCD commands `10/11`
Environment: owned executable, Python 3.14.8 and Capstone 5.0.9; no emulator interaction
Authored: 2026-10-07; Codex root; model: GPT-6.1 Sol
Basis: primary dispatch/handler inspection, direct native writer references and resolved reset calls
Claim: opcode `10` compares packet byte 1 with u8 PS1 virtual `0x800C8672`; opcode `11` compares it with u8 `0x800C8673`. Both advance the script PC by two and return one for equality, zero otherwise. These are byte-variable indices 18 and 19 under RE1-VARS-001. They are item-interaction bytes, not persistent acquisition bits or searches of held inventory.

Evidence:

- Dispatch table PS1 virtual `0x80091108` maps `10` to `0x80045ADC` and `11` to `0x80045AA8`. The complete adjacent handlers through `0x80045B10` load the packet through PC word `0x800CF640`, advance it by two, load the corresponding unsigned byte and compare it with packet+1. Neither calls a helper nor writes tracked state apart from the PC.
- Inspected direct stores include ordinary acquisition at `0x8002CE1C` and the map callback at `0x800385E4`, both copying retained source+8 to `0x800C8673`. The item-return path at `0x8002D0A4`, item-use dispatch at `0x800343AC` and menu paths at `0x80056270`, `0x80056558`, `0x800565C4` and `0x80056634` write `0x800C8672`. These examples explain the interaction interpretation; they do not enumerate every indirect or overlay writer.
- Reset helper `0x8005BAA4..0x8005BACC` clears both bytes, word `0x800C8670`, and word `0x800C300C`. Direct calls occur at `0x8004422C` inside the room setup audited in RE1-EVENT-016 and at `0x8002A008`. The latter follows calls to recurring SCD runner `0x800489CC` and native event runner `0x80025CDC`. Thus a reset does not make either byte immutable during room execution. No zero seed was added to the interpreter.
- Held-inventory search is a separate routine, `0x8002CCB8..0x8002CD30`. It walks two-byte entries through pointer `0x800BA008`, bounded by count byte `0x800C8667`, and compares entry item types with its argument. Neither predicate calls it. Reading today's inventory would not reconstruct an earlier item-use event.

Reproduction: private `/tmp/tasks/re-map/post-acquisition-inspection/native_predicates.py` verifies the executable SHA256, resolves both table entries, scans direct calls to the reset helper and disassembles the named ranges. `native-predicates.json` has SHA256 `509a624a66a8a36140d093b5ea045a52a3ddf5f12f997ecefa027795174ff68c`; `native-predicates.txt` has SHA256 `8e6fe319a8799ec4fd49ddd60029eb467a22526693b8c3661b5a5db6aaf8220d`. Extracted instructions remain outside Git.
Limits: no natural item-use/acquisition predicate, instruction breakpoint or write watchpoint was observed. Reset stores alone do not prove a value at every later initialization/main/event boundary. Native scheduling, external player actions and unmodeled writers can invalidate an earlier shadow. No profile address or production semantic rule changed.
History:

- 2026-10-07; Codex root, GPT-6.1 Sol; inspected complete predicates and reset helper, checked direct writer excerpts and caller order, distinguished inventory search, and rejected an immutable zero assumption. Existing command-width and acquisition findings retain their original provenance.

## RE1-SCD-022: shared item-interaction comparisons retain bounded value lifetimes

Status: Candidate; implementation checked with synthetic tests and unchanged captured-RAM replay
Scope: RE1 Director's Cut NTSC-U SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`; SCD `10/11` across all generated source variants
Environment: Python 3.14.8, pytest 9.1.1, owned disc and existing captures; no new emulator session or gameplay
Authored: 2026-10-07; Codex root; model: GPT-6.1 Sol
Basis: RE1-SCD-021's pinned native contracts, RE1-VARS-001's physical shadows, synthetic regressions, metadata audit and paired comparisons
Claim: shared compilation interprets `10/11` as equality tests of byte-variable indices 18/19. Supported same-run writes can establish their values. Reconstruction never treats those interaction bytes as invariant across separate main/event runners or as current inventory or persistent acquisition facts.

Implementation:

- Both commands use the existing unsigned byte-test schema and physical-bit shadow. Missing writes and invalidated shadows retain both branch outcomes. Native returns stay conditional; neither command enters a constant/nonzero-return allowlist. Packet widths and indexed-event decoding are unchanged.
- At reentry joins, physical shadow bits belonging to bytes 18/19 become unknown. Native tick resets and player actions can replace them after initialization or another runner. A synchronous runner's complete procedure list still retains its supported writes for subsequent comparisons. Current-room initialization/history boundaries retain their existing conservative treatment.
- Existing quantity-copy and map-callback effects can invalidate earlier interaction writes. The map callback continues to forget byte 19; the private precision experiment in RE1-ANALYSIS-009 was not adopted. No zero seed, transient RAM read, inventory snapshot, new profile address, named-item exception or completion override was added.

Evidence:

- Two independent generations produce identical metadata. Exactly 132 commands in 72 source variants change from `uncertain-test` to `byte-test` with index 18/19, equality and the audited source operand. Full source identities, all other commands, proofs, coverage declarations, mutable fields, event-flow records and loader choices remain unchanged. The only other metadata changes are research references to RE1-SCD-021/022.
- The 52 new synthetic cases verify unsigned values including zero/128/255, byte-setter high-byte truncation, item and door selection, physical flag aliases, unresolved current-RAM matches, unknown quantity copies, map-callback invalidation, current/reentry lifetimes, separate main/event runners, same-run event procedure ordering, fresh acquisition reversal and truncated commands. An initial quantity-copy test used a known source quantity and correctly resolved it; the final uncertainty test explicitly makes that source quantity unresolved before copying it.
- All 1,479 tests pass in 63.84 seconds. The first sandboxed run passed 1,472 tests and blocked seven existing localhost socket tests with `PermissionError`; the complete rerun with socket access passed. Five changed Python files pass manually scoped Ruff lint/format checks and `git diff --check` passes. No project formatter/linter or Markdown check is configured.
- Against baseline `4aa56b4`, seven flag configurations, both epochs and 334 sources give 4,676 paired projections. Three unchanged donated captures preserve complete items at 267 current and 291 reentry, and doors at 263 current and 312 reentry. Four synthetic acquisition configurations likewise preserve their own baseline counts. No configuration gains a complete item result. Every previously complete item result and published item/quantity/acquisition value, door, disabled door, unresolved door slot, noncollectible slot and whole-source coverage remains identical.
- The unchanged twelve-step, eleven-capture replay preserves Main Hall clearance after departure and normal loading, Art Room's remaining Ribbon and available/taken Map reversal, the earlier Ribbon-state reversal and map reveal only for entered rooms 00-06/00-07. This replays recorded RAM rather than performing new gameplay.

Private evidence directory `/tmp/tasks/re-map/item-interaction-predicates/`: `differential.json`, SHA256 `77d084b588788a3b3e2414df5255f6496ee8c73386cc9d86d2b70a400dcd1574`; `audit.json`, SHA256 `0a33731a20a791fd56b0811204423905b57b8965445815541a00ead8aa83ec90`; `projection.json`, SHA256 `df16e98939d7141a14e76ce2483b73ad551a79ce17f2f109f2984d42016302bb`. `differential.py` loads both the preceding evaluator and preceding semantic programs from `4aa56b4`; it evaluates the named unchanged captures and explicit acquisition substitutions in private RAM copies. `audit.py` repeats RE1-REENTRY-004's recorded sequence. Regeneration and native operand evidence remain traceable through RE1-SCD-021 and the generation audit. Game files, raw instructions, RAM and savestates remain outside Git.
Limits: natural interaction-byte writes, item-use/acquisition predicates, later-area puzzles, actor/story progression and active-event normal-save/savestate reversal remain unvalidated. This supports shared script interpretation with no demonstrated whole-source coverage gain under the tested configurations. It does not establish full-playthrough reliability.
History:

- 2026-10-07; human user; directed continuation of the named shared item-interaction proposal. Codex root, GPT-6.1 Sol; implemented the compiler mapping and conservative reentry lifetime, verified source-only metadata differences, ran synthetic and paired comparisons and replayed unchanged captures. Independent self review checked conditional returns, bounds, shadow aliases, external value lifetimes and fresh acquisition reads before external review.
- 2026-10-07; Codex root, GPT-6.1 Sol; verified final manifest SHA256 `751b8c71a626b4aa9932b69a783a000a66791368c5cc91b51958b7ecc41fa47b` and private `generation-audit.json` SHA256 `2653219b252565f0a1a8b7c8279c53d0eeffe3439cad35f92a297f0cc75e598d`. Adding the implementation reference changes no semantic operand or runtime result.
- 2026-10-07; Gemini 3.8 Flash High via agy, conversation `2f032974-12c9-445c-99bf-9fc4fa6fd2aa`; reviewed the complete implementation diff, regenerated numeric metadata, compiler/scanner/proof interfaces, physical shadow interpreter, new regressions, existing helper/event/reentry contracts and pinned native findings. Returned "No findings." Process exit zero, final agent response DONE, terminal result SUCCESS and empty stderr; no tools or gameplay. The redacted packet was 344,199 bytes, SHA256 `70969d376d665145912cd74edb429179320477a6db1ba06087bf089b2c65e8e6`. Root completed the direct inspection and validation before consulting this advisory review.
- 2026-10-07; Gemini 3.1 Pro High review request; automatic approval review rejected uploading the redacted internal implementation/research snapshot without specific authorization for that payload and destination. The call did not start and no Pro payload was sent. The user was asked to authorize the upload; no approval had arrived before this record. No Pro review or endorsement is claimed. The parallel Flash upload was separately approved and completed.
- 2026-10-07; Claude Opus 5.5 High via agy; remained unavailable under RE1-EVENT-011's quota exhaustion reported on 2026-10-05, with reset in 110 hours, 53 minutes, 55 seconds. No retry before reset, substitution, review or endorsement.
