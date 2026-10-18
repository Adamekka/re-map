# RE2 Leon A research

[Documentation index](../README.md) · [Claim index](../research.md)

## RE2-IDENTITY-001: Leon A disc identity and candidate room layout

Status: Candidate for runtime room tracking; owned disc metadata checked statically.

Game: Resident Evil 2 USA, Leon Disc 1, SLUS-00421. The boot executable `SLUS_004.21` is 987136 bytes with SHA256 `1cd618bc4390db4bd60735b0db1e91534f6134ede56fae454eb580be2aa686ef`. The PS-X EXE loads `0xF0800` bytes at PS1 virtual `0x80010000`. The original disc has no explicit revision label in the inspected boot configuration; the executable hash pins this profile. Isolated test emulator: official DuckStation `0.1-12083-g00e299795 (dev)`.

The human selected Leon A and approved RE1-equivalent map, item completion, door access and savestate behavior on 2026-10-17. See [RE2 scope](../re2.md).

Candidate addresses are PS1 virtual, little-endian. Stage, room and camera are unsigned 16-bit values at `0x800CC948`, `0x800CC94A` and `0x800CC94C`, respectively, with full mask `0xFFFF`. The native map caller at `0x8006990C..0x80069948` loads stage and room from these locations. These raw reads do not establish gameplay, scenario, loaded source or snapshot coherence.

Runtime revision checking hashes four 32-byte code windows at `0x80051570`, `0x80051480`, `0x80050BF0` and `0x80072B30` in that order. Their concatenated SHA256 is `712628cd70ecee75e834248085df57ac0b22862fa8e7e486e06cc9833cae5d5a`. They cover the ordinary item creator, door creator, script flag predicate and shared flag test. For each window, original executable offset is `0x800 + address - 0x80010000`. Reproduce by extracting the executable with `tools/extract_psx_file.py`, checking its full hash, concatenating the named windows and hashing them. A mismatch is a wrong revision; failed or short memory reads are separate failures.

Source leads: Megan Grass's [RE2 Starter Kit](https://github.com/MeganGrass/Resident-Evil-2-Starter-Kit/tree/447bc6cc5388bf943616f54d50e5c20781003b71), particularly `source/bio2/data.h`, `source/assembly/directive.s` and room names in `source/overlay/room_jump/bio2/room_info.h`, describe the later SLUS-00748 release. They are not evidence that its addresses work on SLUS-00421. IntelOrca's [biohazard-utils](https://github.com/biorand/biohazard-utils/tree/5d0d523cc0e228b5c9eea269149853cda5f266bd), `Room/Rdt2.cs` and `Script/Bio2ConstantTable.cs`, provides RDT and SCD format leads. The current disc independently supplies 125 `PL0/RDT` files.

Evidence and limits: extracted executable, original map pixels and exploratory RAM remain private under `/tmp/re-map-re2-live/`. Both achievement settings were explicitly false before boot; there are no per-game overrides or account credentials. No guest-memory patches were enabled. An unpaused opening experiment reached death/title while inspecting memory and is rejected as gameplay-state evidence. Synthetic tests check halfword bounds, profile/scenario isolation, wrong-code signatures and failed/short reads. Item flags, lifecycle gating, map selection, actual facing and door locks still require controlled observations.

Contributions:

- 2026-10-17; author and static inspection: Codex root, exact model `gpt-6.1-sol`, verified from this session's current turn metadata. Implemented shared revision hashing and the initial RE2 identity/room reader. This entry does not claim runtime confirmation.

- 2026-10-17; synthetic validation: `gpt-6.1-sol` ran 27 passing tests across RE2 profile reads, existing RE1 profiles, lifecycle and logging. Scoped Ruff lint and format checks and `git diff --check` passed. A controlled paused opening RAM capture matched the configured signature and raw room `00-00`; this single situation does not meet the runtime-confirmation threshold.
- 2026-10-17; external snapshot reviews: CLI-returned identifiers `Claude Opus 4.6 (Thinking)` and `Gemini 3.8 Flash (High)` reviewed the shared identity extraction, new profile reader, configuration and synthetic tests. Both processes exited successfully with completed response events and nonblank successful results, and empty stderr. Gemini returned no findings. Direct inspection found no actionable defect among Opus's candidates. These prose reviews do not validate gameplay. The requested `Claude Opus 5.5 (High)` was unavailable due to invalid model selection; the human explicitly approved using Opus 4.6 instead.

## RE2-SCD-001: bounded Leon room metadata and acquisition contracts

Status: Candidate for SLUS-00421; static native inspection and synthetic regressions, not runtime pickup confirmation.

Game, region, disc, executable and emulator are pinned in RE2-IDENTITY-001. The [RE2 guide](../re2.md) describes the current scope. Format leads are the exact Starter Kit and biohazard-utils commits cited there; the installed disc independently supplies the actual offsets and operands. The Starter Kit targets a different revision and supplies names and format leads only.

The generator decodes the init and main procedure tables from RDT section indices 16 and 17. Each table contains little-endian 16-bit relative procedure offsets. A bounded worklist retains both conditional branches, including code after a conditional event return. Ordinary Item AOT `0x4E` is 22 bytes and its four-point form `0x69` is 30 bytes. Item type, amount and acquisition ID are unsigned little-endian 16-bit fields at raw offsets 14/16/18, or 22/24/26 for the four-point form. Door forms `0x3B` and `0x68` are 32 and 40 bytes. The PS1 Endif `0x08` consumes two bytes, including padding, unlike the PC format lead. Switches leave candidate-list coverage incomplete. Direct awards `0x76` remain unresolved event collectibles. Files, item types 104 and above in this pinned catalog, do not block clearance.

Native item creation at PS1 virtual `0x80051570..0x80051698` registers its AOT pointer before testing acquisition. An acquired item changes the descriptor SCE ID to zero. Its native four-point sibling sets the SAT high bit. Runtime pointers refer to the original opcode plus two bytes. The AOT registry has 32 little-endian 32-bit pointers at `0x800C66C8`; native clearing at `0x8004FA28..0x8004FA50` zeros the registry and its count. A live descriptor with SCE ID 2 establishes a candidate available item; matching SCE ID 0 plus an unset acquisition flag establishes inactivity. A missing pointer does not prove scenario absence.

Native flag testing at `0x80072B30` selects `word = id // 32`, then bit mask `0x80000000 >> (id % 32)` in a little-endian 32-bit word. Set means acquired. Item AOT creation uses bank 8 before stage 4 and bank 34 from stage 4 onward. Bank 8 begins at PS1 virtual `0x800CC9E8`, width 32 bytes; bank 34 at `0x800CCA08`, width 16 bytes. Key unlock bank 31 begins at `0x800CCB60`, width 8 bytes. These are PS1 virtual addresses, never host addresses or raw offsets.

Native-helper cross-check, 2026-10-17: bounded Unicorn execution of the pinned `0x80072B30` helper passed twelve literal byte/bit cases. Bytes `00 00 00 80` make ID 0 true, while `80 00 00 00` make ID 24 true and ID 0 false. Rejected hypothesis: mapping ID 0 to byte 0's high bit based only on endianness. Native `lw` plus a 32-bit descending mask establishes the word mapping. The private numeric evidence `native-flag-check.json` has SHA256 `c6cc4a5c538d45a7f7ca2f2947ad7548b336b5d845b38d5596ca8a92f81bc842`. This is native emulation, not a gameplay pickup observation.

Door access uses the live descriptor's target and lock fields. The native door handler `0x8004E054..0x8004E190` treats a clear `lock_id & 0x80` as open. Otherwise bank 31 bit `lock_id & 0x3F` establishes unlock knowledge. Lock type `0xFE` allows unlocking from this side; `0xFF` and unacquired named-key locks remain locked. Disabled live door descriptors stay blocked even when key bits are set. Departed-room activation and conditional targets remain unresolved. Fresh key bits still produce the label `Unlocked; access unconfirmed`; they do not turn a potentially inactive door into an open passage. Earlier savestates remove that unlock knowledge when the bit clears.

Offline output contains 125 room sources, 281 candidate Item AOT definitions and 321 candidate Door AOT definitions. Counts describe source extraction only. Every source retains its size, SHA256, 23 section offsets and camera-coordinate proofs. Camera proofs alone collide for three pairs of sources, so runtime binding also compares every relocated section pointer after subtracting the loaded RDT base. The combined catalog identities are unique. Rejected approach: relying on only the first three camera proofs would accept those wrong-source aliases.

Reproduce generation with the command in re2.md. `tests/test_re2_metadata.py` checks conditional-return reachability, malformed branches/widths, extraction counts and combined source identity uniqueness. `tests/test_re2_tracking.py` checks flag reversal, dormant versus missing items, source rejection, key locks, disabled doors and coherence. Synthetic acquisition/key reversals are not evidence of gameplay acquisition or normal-save persistence.

Contributions:
- 2026-10-17; Codex root, `gpt-6.1-sol`; authored decoder, source binding, shared contour extraction and live item/door interpretation. Inspected the pinned executable and compared the isolated opening source with owned room data. No runtime pickup or key-unlock confirmation is claimed.

## RE2-MAP-001: native Leon floor selectors and numeric contours

Status: Candidate for SLUS-00421; native selector execution and one opening-room publication, not campaign map confirmation.

Identity and primary source leads are in RE2-IDENTITY-001. The pinned executable's map descriptor table at PS1 virtual `0x800A2DF4` has 20 records of eight bytes: a little-endian 32-bit region-table pointer, one-byte count/page fields and a little-endian 16-bit file number. Each 16-byte region descriptor contains U/V/width/height bytes, four signed little-endian 16-bit positions and four flag bytes. The native draw code at `0x8006AB20..0x8006AB4C` uses Cpos X/Y directly as the sprite top-left. Rejected approach: Bpos minus height is not the sprite origin.

The generator executes the pinned area selector at `0x80069FC0` and region selector at `0x8006A2B8` in bounded Unicorn MIPS runs for every supported room, every floor byte and each identified selector context. Runtime selection uses the generated alternatives, not copied native code. Inputs beyond stage/room include the player floor byte at PS1 virtual `0x800C7E2A` with mask `0xFF`, common flag byte `0x800CC997` mask `0x02`, common byte `0x800CC98F` mask `0x10`, common byte `0x800CC992` mask `0x40`, previous-room halfword `0x800CC94E` mask `0xFFFF` compared with `0x0602`, and context byte `0x800CCE80` mask `0xFF` compared with 1. Each address is PS1 virtual, little-endian, width one byte except the named halfword. The profile lists the rooms that consume each context. Unreachable/debug source files without valid native regions remain explicitly unmapped.

The owned `MAPS.PIX` contains twenty 256-square 4bpp pages. Nonzero cells form numeric contours; shade 2 retains interior runs. UV coordinates wrap at 256, including a native rectangle crossing a texture-page edge. Contours preserve pixel-cell area, holes and disconnected corner contacts. Generated JSON contains no source pixels, palettes, textures or executable bytes. Extra native regions with no Leon room binding cannot be revealed by this profile. Map ownership flags never reveal a region; only entry adds exploration.

The native player projection uses region Bpos plus `(worldX + 28000) / 450` in X and minus `(worldZ + 28000) / 450` in Y, truncating toward zero. Candidate door markers project each source trigger center and bind only to a unique nearest wall within eight map units; equal-distance corner ambiguity and more distant triggers remain unplaced. The marker's room/offset identity matches its live descriptor rather than a room pair. These placements are not yet independently checked in gameplay and do not establish access by themselves. Player yaw is a 16-bit little-endian value at PS1 virtual `0x800C7D9A`, masked to twelve bits; candidate clockwise heading is `(90 + yaw * 360 / 4096) % 360`. The native arrow quantizes the same masked angle with a half-step bias. Controlled multi-direction walking to verify the continuous conversion remains outstanding.

Opening capture replay renders only `re2-00:00` with heading 270 degrees and one observed exit; the README screenshot uses that publication. The browser shows the RE2 title, one selectable explored area, a labeled spatial outline and an incomplete check. It does not show unexplored shapes. Source-derived room names, later areas, conditional floors, wall placement, item appearance and key transitions still need gameplay observations. Tests enumerate generated selector alternatives, preserve contour area at diagonal contacts and exercise the shared map UI.

Contributions:
- 2026-10-17; Codex root, `gpt-6.1-sol`; traced the native table, projection and selector dependencies, generated numeric geometry, reused the shared map controls, added suit emblems and source-specific door binding, and captured the README's opening map. Static/native-emulation results are kept separate from gameplay coverage.

## RE2-LIVE-001: coherent opening-room reads and explicit runtime limits

Status: Candidate for SLUS-00421. One controlled opening-room observation is available; multiple independent pickup, key-door and restore situations are not yet confirmed.

Game identity and tested DuckStation version are in RE2-IDENTITY-001. Achievements were disabled in both `[Achievements]` and `[Cheevos]` before boot. The agent used an isolated portable DuckStation copy, disabled memory cards and a separate in-memory tracker, not the user's exploration history. All original disc data, RAM and new RE2 checkpoints stay private outside Git.

The reader captures a 352-byte player block at PS1 virtual `0x800C7CE0` and a 1792-byte save block at `0x800CC800`, then bounded source proofs and the AOT registry. Relevant fields are reread before publication. Loaded RDT is an unsigned little-endian 32-bit pointer at `0x800C6494`, mask `0xFFFFFFFF`. System flags at `0x800C7CE4` are 32-bit little-endian, with gameplay mask `0x40000000`, demo `0x00002000`, transition `0x02000000` and game over `0x04000000`. Status flags at `0x800C7D04` use scenario mask `0xC2000000`, expected zero for Leon A; the subplayer bit is outside that mask. Active-player flags at `0x800C7D24` are 32-bit little-endian, admitted only with mask 1 set. Other animation/system bits need not remain fixed during a coherent read. These lifecycle masks are source-derived candidates; the opening supports the admission case but does not confirm every excluded phase.

A failed or short read is a read failure, identity mismatch is a wrong game, and mismatched room source or changed consumed state retries without mutating visits, items, doors or heading. The default loop requests 10 Hz and reads fixed bounded locations. Neither successful transport nor stage/room bytes alone establish gameplay. History stores only visits, isolated by profile, revision fingerprint, scenario and playthrough UUID. Fresh flags reconstruct acquired state after a restart or earlier savestate; unresolved availability stays Unknown. Cached clearance and door access are never persisted.

Controlled evidence `street-before` was paused before its full RAM capture, with stage/room/camera `0/0/0`, active bit 1, System flags `0x40020040`, scenario bits zero, and a matching runtime signature, relocated section table and camera proofs. Replay publishes the opening street, its native floor region, the native yaw and one open live descriptor. No pickup, door unlock, floor transition or normal memory-card persistence is established by that capture. The raw RAM SHA256 is c9665284ca828e618971721be518ed1197c4ea3d3e210b0fffa9017573b061a7 and the private savestate SHA256 is aa71f7aa7e76de8601e1524a7e604615ff6785ff891215a5cfd7d26390b62b6e. Restore the private checkpoint in the isolated emulator, pause before capturing, then run the production reader against the captured memory to reproduce the publication. The private capture and helper files are under `/tmp/re-map-re2-live/`; they are not portable public fixtures.

After that baseline, an agent-only high-health edit set the signed 16-bit little-endian life field at PS1 virtual `0x800C7E7A` to 32767. Earlier direct observation showed 200 before damage and 110 afterward. No ammunition patch was enabled. Later experiments also positioned the player and its previous/collision coordinates near the first exit. They did not establish a controlled room transition or pickup and are excluded from confirmation and the README screenshot. They do not justify extending native flag/door claims. Earlier unpaused or not-ready captures listed in RE2-IDENTITY-001 remain rejected.

Contributions:
- 2026-10-17; human user; approved implementing Leon A and later requested splitting the large documentation by feature/topic.
- 2026-10-17; Codex root, `gpt-6.1-sol`; authored the bounded reader, runner dispatch and synthetic regressions; performed the controlled opening capture and the explicitly excluded later experiments; wrote this evidence and its limits. Source agreement and synthetic tests are not runtime confirmation.

- 2026-10-17; Codex root, `gpt-6.1-sol`; final direct review verified revision/source binding, lifecycle and scenario gates, word-level flag polarity, snapshot publication, dormant versus missing items, source-specific wall matching, earlier-state reversal and separate history defaults. It added regressions for unknown history rooms and unbound door coverage. Metadata regeneration is byte-identical, SHA256 `7a04a85c799484e328a55aaa55a495b202eea434f29313d30a5111d28e1a2765` for room metadata and `40b5599e5558237c5986aba310bbc7bfebb376fce48a3700ee1b75e3070da93c` for plans. Browser regressions pass for all 118 RE1 outlines and all 133 RE2 outlines. The final full Python suite passed 1,633 tests; scoped Ruff lint/format and whitespace checks also pass. These checks do not extend gameplay coverage beyond the controlled opening.
- 2026-10-17; returned model identifier `Claude Opus 4.6 (Thinking)`, via agy conversation `a3533a2c-cd3d-4ca5-b343-cd6b852a0dbe`; reviewed the complete RE2 generator, catalog, profile, reader, runner, shared map changes and relevant interfaces/tests. Root accepted the separate default-history and required-metadata validation findings and verified the changes with regressions. Other candidates were checked against the actual RE1 multi-area catalog and the bounded key-bit mask; retracted or unsupported suggestions were not treated as defects. Process exit 0, final agent response DONE, terminal SUCCESS, empty stderr, no tool attempts. Prompt SHA256 `f6d5c57dc41b21faf221dc4f1b9d2db97d9b53784131263400a0bf8ed60b20a2`. The user explicitly approved this installed Opus version in place of unavailable Opus 5.5. Advisory review is not gameplay confirmation.
- 2026-10-17; returned model identifier `Gemini 3.8 Flash (High)`, via agy conversation `c6c87bac-47a8-491a-802b-05093847a17a`; reviewed the complete updated changes, generated data, contracts and tests. Root reproduced and fixed the missing unresolved-item overview entry, retained fresh departed-door unlock knowledge without guessing activation, and rejected the byte-order proposal after direct native inspection and twelve literal emulated cases. Process exit 0, final agent response DONE, terminal SUCCESS, empty stderr, no tool attempts. Retry prompt SHA256 `553ace897111457da3fc5754038d7ddc318580f3316290b2c07952aaa3c03ede`. The original Flash call ended ERROR after exceeding its output-token limit and supplied no accepted review. Its partial response is diagnostic only; one shorter-context retry completed. Private review evidence is under `/tmp/re-map-re2-final-review/`. These reviews checked code and supplied metadata, not new gameplay.

## RE2-LIVE-002: gun-shop ammunition and savestate reversal

Status: Confirmed for the two observed ammunition acquisition flags and the listed DuckStation restores on SLUS-00421. Other item IDs, shotgun availability, door unlocks and the route to the RPD remain Candidate or untested. This is partial validation of the approved opening-route work, not completion of that route.

Game, region, disc and executable identity are pinned in RE2-IDENTITY-001. Tests used the same isolated DuckStation `0.1-12083-g00e299795 (dev)` portable copy on 2026-10-18. Before boot, both `[Achievements] Enabled` and `[Cheevos] Enabled` were false, the copy had no account credentials or per-game overrides, and both memory-card slots were `None`. A private in-memory `Tracker` accumulated observations; the user's history file was never opened. These observations do not test history-file persistence or normal memory-card saves.

### Observed pickups

Ordinary controller navigation reached the shop, room `00-01`, from the opening street. The bounded production reader accepted its revision, relocated source proofs and native region `re2-00:01`. With Kendo alive, it listed two available handgun-ammo boxes, each containing 15 bullets, and a dormant shotgun candidate. Both item bits were initially clear.

The first observed pickup was the shop's acquisition ID 1. Leon reached it through ordinary navigation and collected it through the game's Yes prompt. The inventory gained 15 bullets and the box disappeared. The second observed pickup was acquisition ID 0. To prepare that interaction, the agent positioned Leon at PS1 world X/Z `-24120/-20314`, facing `2048`, within the already loaded shop, then used the same game prompt. Collision settled X to `-23710` in the resulting capture. The inventory count increased to 30 bullets and the second box disappeared. No acquisition, key or story flags were written by the agent.

Both flags use the first unsigned 32-bit little-endian word of bank 8 at PS1 virtual `0x800CC9E8`. ID 0 has mask `0x80000000`; ID 1 has mask `0x40000000`. Before either pickup, the word bytes were `00 00 00 00`. After ID 1 they were `00 00 00 40`; after both they were `00 00 00 C0`. The reader reported collected counts 0, 1 and 2, respectively. Completion remained Incomplete after the first pickup and became Cleared after both under the current RE2 availability policy. That clearance result does not establish that the dormant-shotgun policy is correct throughout this event.

### Actual earlier/later loads

The following states were restored through DuckStation's load-state hotkey, then paused before full RAM capture. The same tracker instance handled these restores.

| Restore | Expected and observed result |
| --- | --- |
| Earlier `shop-ready.sav` | Both bits clear; both ammunition pickups available; shop Incomplete with collected count 0. The restored RAM was byte-identical to the earlier `shop-ready` capture. |
| Later `ammo-both.sav` | Both bits set; both ammunition pickups taken; shop Cleared under the candidate availability policy, with collected count 2. The restored RAM was byte-identical to `ammo-both-taken`. |
| Original `street-before.sav` | Opening street current, both item bits clear, and the shop visit retained. The departed shop became Unknown with unresolved item availability. Its cached Cleared result did not survive the rewind. |

All observed bank 31 bytes remained zero. These loads therefore establish pickup reversal and retained in-memory exploration, not key-unlock reversal. The opening exit was observed as Open, and the shop back exit was reported Open, but no successful shop-back-exit transition or later reentry was captured.

### Private evidence and reproduction

Files are under `/tmp/re-map-re2-route-20261018/`. These temporary paths are local evidence references, not portable public fixtures. BIOS, disc files, executable bytes and RAM remain outside Git.

| Evidence | SHA256 |
| --- | --- |
| `shop-ready.ram` and `rewind-before-pickups.ram` | `4a2f15e046453d13d83d1b51b3489ce4a0aa10dba23031606eaa68e978e7e4ad` |
| `ammo-one-taken.ram` | `4211f21c788f3f5f08a7fda17aa4ebe5e353db3bd5c1ee5475933861df4431fc` |
| `ammo-both-taken.ram` and `restore-both-pickups.ram` | `d5e8ef3230dba0ec4086f607da8af021da147e0cfae278e143ea11ceea068af0` |
| `rewind-opening.ram` | `f30db8fa544f164c11e6f63fdc1ee3e7732078e28a0e5c0337f278b4fab0a034` |
| `shop-ready.sav` | `e91351c6e55f6db2c87c4d0cca0a38c32197238097c0d57c69054cd696093528` |
| `ammo-both.sav` | `89e6315c5c8138784c9a27b138e90c78d4520107d1467b2f6b79d8f7baa7e570` |

Reproduce with the pinned owned disc and isolated emulator settings above. Load `shop-ready.sav`, collect the box near world X/Z `-15922/-23234`, then collect the other box near `-24911/-20314`. Pause and capture after each completed prompt. Load the earlier and later checkpoints, capture again, and replay the captures in that order through `poll_re2` using one fresh tracker. A replay reader returns the requested slice at RAM offset `address & 0x1FFFFF` as `MemRead`; it must not replace the pinned runtime signature or source proofs. Load the original opening checkpoint last and verify that both visited room IDs remain while acquired state reverses. The JSON alongside each capture records its publication and numeric state.

Agent-only setup edits were enabled. Signed 16-bit little-endian health at PS1 virtual `0x800C7E7A`, full mask `0xFFFF`, was set to 32767 and later decreased through damage. The unsigned one-byte handgun magazine count at `0x800CCB69`, mask `0xFF`, was set to 255; the game's inventory displayed infinite ammunition. The observed pickups added a separate reserve-ammo stack. For coordinate setups, `position-edits.jsonl` records every write. X/Z at `0x800C7D5C/0x800C7D64` are signed 32-bit little-endian, full mask `0xFFFFFFFF`. Facing at `0x800C7D9A` is 16-bit little-endian with full write mask `0xFFFF`. Candidate previous/collision X/Z fields at `0x800C7D68/0x800C7D6C`, `0x800C7D6E/0x800C7D72` and `0x800C7E3C/0x800C7E3E` received signed 16-bit little-endian coordinates, full mask `0xFFFF`. Those setup writes do not confirm the fields' interpretation.

Controller macros were configured only in the test copy to hold aim, repeat fire and combine movement with running. Their configuration follows DuckStation's pinned [macro loader and toggle implementation](https://github.com/stenzek/duckstation/blob/00e299795/src/util/input_manager.cpp#L1908-L2042). Input was sent through the native computer-use tool. No original game files were changed.

### Rejected observations and remaining limits

The initial resumed opening attempt reached a death animation during setup; `baseline` and `street-walk` are excluded from validation. Later coordinate-assisted body and back-door attempts did not establish shotgun collection or a room transition and are also excluded from those claims. The scripted shop attack was observed, but the reader still listed the shotgun as dormant in the recorded captures. This does not resolve its activation contract or justify a completion-policy change. The remaining opening route, door-unlock before/after observations, reentry and conditional floors still need controlled evidence. No production code changed in this validation pass.

Contributions:

- 2026-10-18; human user; approved opening-route pickup, door-access and savestate-rewind validation and scoped fixes.
- 2026-10-18; Codex root, exact model `gpt-6.1-sol`, verified from the matching session's latest turn metadata; performed the controller-driven pickups, recorded setup edits and captures, restored the listed checkpoints, replayed the bounded production reader and authored this evidence. Direct checks compared flag bytes, collected counts, capture hashes and retained room visits. The existing focused RE2 Python suite passed 36 tests. Those synthetic tests do not extend the runtime claims above.
