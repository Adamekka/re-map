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

Collection-policy update, 2026-10-18: [RE2-COLLECT-001](#re2-collect-001-source-established-items-remain-until-collected) supersedes the availability-based treatment of dormant candidates. The original source observations below remain historical evidence; an inactive descriptor alone no longer establishes absence from the required item list.

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

The native player projection uses region Bpos plus `(worldX + 28000) / 450` in X and minus `(worldZ + 28000) / 450` in Y, truncating toward zero. Candidate door markers project each source trigger center and bind only to a unique nearest wall within eight map units; equal-distance corner ambiguity and more distant triggers remain unplaced. The marker's room/offset identity matches its live descriptor rather than a room pair. These placements are not yet independently checked in gameplay and do not establish access by themselves. Player yaw is a 16-bit little-endian value at PS1 virtual `0x800C7D9A`, masked to twelve bits; candidate clockwise heading is `(90 + yaw * 360 / 4096) % 360`. The native arrow quantizes the same masked angle with a half-step bias. This conversion was initially a source-derived candidate. [RE2-PLAYER-001](#re2-player-001-native-movement-confirms-continuous-heading) later supplies scoped native movement and restore confirmation; projected player and door placement remain unverified.

Opening capture replay renders only `re2-00:00` with heading 270 degrees and one observed exit; the README screenshot uses that publication. The browser shows the RE2 title, one selectable explored area, a labeled spatial outline and an incomplete check. It does not show unexplored shapes. Source-derived room names, later areas, conditional floors, wall placement, item appearance and key transitions still need gameplay observations. Tests enumerate generated selector alternatives, preserve contour area at diagonal contacts and exercise the shared map UI.

Contributions:
- 2026-10-17; Codex root, `gpt-6.1-sol`; traced the native table, projection and selector dependencies, generated numeric geometry, reused the shared map controls, added suit emblems and source-specific door binding, and captured the README's opening map. Static/native-emulation results are kept separate from gameplay coverage.
- 2026-10-19; `gpt-6.1-sol`; updated the former heading-validation limit after the native observations in RE2-PLAYER-001. That claim confirms only the stated continuous facing conversion; the remaining map/projection claims retain their existing status.

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

The later controlled route observations are recorded in RE2-LIVE-003 below. The limits in this entry describe the earlier shop-only pass.

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

## RE2-LIVE-003: controlled route, pickups and reentry

Status: Confirmed for the listed ammunition acquisitions, open-door transitions and savestate reversals on SLUS-00421. The observations cover selected interactions through the RPD entrance. They do not establish an uninterrupted route using ordinary navigation, every item condition or campaign-wide readiness. Key-unlock reversal remains untested.

Game, region, disc and executable identity are pinned in RE2-IDENTITY-001. The isolated emulator was official DuckStation `0.1-12083-g00e299795 (dev)` on 2026-10-18. Both achievement settings were false before each boot, both memory-card slots were `None`, and the copy had no credentials or per-game overrides. The user's normal history was never opened.

### Setup and pickup observations

The human provided an agent-instance checkpoint in room `00-02` after leaving the shop. Its inherited health and infinite-magazine setup are documented in RE2-LIVE-002. No acquisition, key, story or enemy-state flags were written for this pass. Further position/facing writes used the same fields documented there and were recorded in `position-edits.jsonl`. No enemy-freeze or invulnerability patch was enabled.

The first additional ammunition pickup followed ordinary controller navigation from that checkpoint. Later pickups and door interactions used position edits within the loaded room, followed by controller input through the native computer-use tool. Each pickup changed a separate reserve-ammunition stack by 15. The observed branch containing ID 154 was rewound before continuing the later route; the three gains did not accumulate in one uninterrupted inventory sequence.

All three flags below are unsigned 32-bit little-endian words in bank 8, at PS1 virtual addresses. The native acquisition interpretation is shared with RE2-SCD-001.

| Room | Acquisition ID | Word address | Mask | Observed word change | Reader result after collection |
| --- | --- | --- | --- | --- | --- |
| `00-02` | 154 | `0x800CC9F8` | `0x00000020` | `0x00000000` to `0x00000020` | Collected 1; Unknown because list coverage is incomplete |
| `00-18` | 161 | `0x800CC9FC` | `0x40000000` | `0x00000000` to `0x40000000` | Collected 1; Unknown because list coverage is incomplete |
| `00-1a` | 195 | `0x800CCA00` | `0x10000000` | `0x00000000` to `0x10000000` | Incomplete to Cleared under the current candidate completion policy |

Before each pickup, the reader reported one available 15-round item and collected count 0. Loading the earlier `00-02` checkpoint reset ID 154, restored that pickup to Available and returned the room to Incomplete. The item prompt captured as `bus-pickup-prompt` temporarily failed the loaded-source layout check. Replaying it after an accepted capture returned Retry without changing visits, items, doors or map state.

### Transitions and reentry

Controller-driven transitions reached `00-02 -> 00-18 -> 00-19 -> 00-1a -> 00-1b -> 00-03 -> 01-00`. Each selected source descriptor was reported Open before the successful interaction, and the reader accepted the destination's revision and relocated source proofs afterward. Position edits prepared these interactions; this does not validate the walking path between them or the projected door-marker position.

After the initial entrance sequence finished, `01-00 -> 00-03 -> 01-00` also succeeded. The reader returned from native map selection `re2-02:00` to `re2-00:03` and back. The native trigger-floor byte at PS1 virtual `0x800C7E2A`, unsigned 8-bit with mask `0xFF`, was 1 inside and 3 outside. These observations do not confirm conditional multi-floor selections or visual heading alignment. Bank 31 remained all zero throughout, so no actual key unlock or unlock rewind is claimed.

### Actual loads and exploration persistence

The same in-memory tracker handled actual earlier and later DuckStation loads. `route-rewind-outside` returned to `00-02`, cleared IDs 161 and 195, and changed the departed `00-1a` from Cleared to Unknown with collected count 0. The later `entrance-ready.sav` restore returned to `01-00`, restored both flags and the departed room's collected count 1 and Cleared result. Its full RAM was byte-identical to `entrance-ready.ram`.

An additional replay used one fresh tracker and the unchanged pinned profile across the opening, shop and accepted route captures, then the earlier and later loads. It retained exactly nine room IDs and nine native map-region visits. The production `VisitHistory` writer saved these visits to the private `captured-route-history.json` with the RE2 revision, Leon A scenario and a new agent playthrough identity. Closing and reopening that file preserved its identity and visits, initialized completion to Unknown, then reconstructed the reversed and restored acquisition results from the actual load captures. This is a real file round trip using runtime-derived visits and captured memory; it is not a live runner restart or a normal memory-card save test.

### Private evidence and reproduction

Evidence remains under `/tmp/re-map-re2-route-20261018/`. These are local temporary references, not portable public fixtures. Raw RAM, savestates, executable bytes and original game assets remain outside Git. `capture-audit.json` lists every replayed capture and its hash; `audit_captures.py` runs the unmodified production reader and history writer/reader without replacing signatures or source proofs.

| Capture | SHA256 |
| --- | --- |
| `user-outside.ram` | `dd0608342c984754f76b8c1241364f2294d44a05aa183f4dea0c7857422ed37b` |
| `alley-ammo-taken.ram` | `a38cdcf961b0597e55d3a969a862e0ef75b49b92c47cdde51813a128e8afefbf` |
| `alley-rewind.ram` | `99d47c8984da972dfcefc1d1dfecf64f2d58417dc0d06e9e546e12e78e8b50d9` |
| `street18-entry.ram` | `7c9de05146105afde6942fd78df27e9d5394089ea4685ccfbc3563d6a073ee4a` |
| `street18-ammo-taken.ram` | `598cecb96a65cb31ddb7e594f051ce0f4311fc3d969876febc5b15a1a1968d55` |
| `bus-entry.ram` | `f6c0455e43d957368bd67a03ff9e05f32f0c4ca50249e73c83a80198d362bf0d` |
| `bus-ammo-taken-controlled.ram` | `76830f7263dbdf14272f1272cd07ab9c766bbfd7c1567e922da78b5dfa34b46f` |
| `courtyard-accepted.ram` | `3f746ff99afa4e20f8490ced7b7a971ffa18b6e546bc9467354d5213de11cbad` |
| `entrance-ready.ram` and `route-restore-later.ram` | `2a486cc56163659f199f045b40d43b1529d88734f45e58c0c4b8aff18ec2c75f` |
| `courtyard-return.ram` | `9f6258b551a6a0d5468fbc40d5dea4160d8c9bc06ebe3697b4e64b6b73e51059` |
| `entrance-reentry.ram` | `91294a1d81af1dbbd9191d4550937f3c0a94a75b1da5db1f770652dbc4c86594` |
| `route-rewind-outside.ram` | `b8e102b633e6605df841d67c5936af1de188b0b7c914a16645f86a98e4dee737` |

The human-provided `user-outside-172650.sav` has SHA256 `995bb0ff5df6eb6b254d87ea9c6af5386105a50bfd50cdab018da50465965bfa`. The later `entrance-ready.sav` has SHA256 `156a026d3bce5b039b48f0f5f3a14f78a551e8b3be10ce5afcb4c0e1d0ce0c73`. The intermediate `bus-ammo.sav` has SHA256 `dabf821457d8d90462d8f817133b69adc95f695bc41aa2a3fa4707a54ccce0ee`.

Reproduce with the pinned disc and isolated settings. Load the human checkpoint, capture before and after collecting ID 154, then load the earlier state again. For later position-assisted interactions, use the recorded coordinates and writes in `position-edits.jsonl`, allow player initialization to finish, and pause between actions. A fresh native-control connection, a 700 ms unbound-input interval after unpausing and the existing repeated-Cross macro produced the successful final interactions. These are test-control observations, not a confirmed explanation of every missed input. Load the earlier and later checkpoints while paused, capture full RAM, then run the private audit. Do not substitute metadata proofs or synthetic bytes for these snapshots.

To avoid exposing gameplay, the isolated copy used a temporary display shader whose `main` calls `SetOutput(float4(0.0, 0.0, 0.0, 1.0))`. The format follows DuckStation's pinned [GLSL example](https://github.com/stenzek/duckstation/blob/00e299795/data/resources/shaders/simple-brightness.glsl); its [post-processing configuration](https://github.com/stenzek/duckstation/blob/00e299795/src/util/postprocessing.cpp#L278-L346) enabled one stage in `PostProcessing`. A private screenshot's central half had zero minimum and maximum channel values. No game screenshots were emitted to chat after the human requested spoiler-free testing. The test emulator was stopped, its original controls restored and the human-provided checkpoint returned to the test slot afterward.

### Excluded attempts and limits

`bus-reentry-controlled`, `courtyard-entry-controlled` and `courtyard-reentry-accepted` did not reach the destinations their provisional filenames suggested. They are excluded as successful transitions. Earlier coordinate, grab-animation and missed-input attempts also establish no passage or collection. Two diagnostic breakpoint attempts did not observe the expected input/door call and supplied no new gameplay contract. They do not justify changing access interpretation. The later accepted captures and explicit current-room checks supply the successful evidence above.

No production code changed. The current pass does not resolve shotgun activation, scenario-dependent absence, every door condition, key unlocks, conditional floors, visual map alignment or normal-save persistence. It does not validate a complete campaign.

Contributions:

- 2026-10-18; human user; supplied the isolated checkpoint after the shop and clarified that test preparation must not spoil the game or require playing ahead.
- 2026-10-18; Codex root, exact model `gpt-6.1-sol`, verified from the matching session's latest turn metadata; performed the additional controller interactions, position setups, captures, loads and reentry; created the temporary black display; replayed the production reader and performed the private history-file round trip; authored this entry and updated the coverage guides. Direct checks verified all three flag masks, inventory deltas, accepted source identities, unchanged state on the captured item prompt, restored counts and completion, nine retained visits and byte-identical later RAM. The focused Python suite passed 36 tests. Those synthetic regressions do not extend the listed runtime coverage.

## RE2-COLLECT-001: source-established items remain until collected

Status: Candidate for SLUS-00421. Pinned native inspection, generated presence proofs, synthetic regressions and replay of unchanged runtime captures. No new gameplay or puzzle interaction was performed.

Update, 2026-10-18: [RE2-COLLECT-002](#re2-collect-002-conflicting-slots-preserve-unrelated-item-proofs) supersedes the whole-room rejection for conflicting item slots. The original implementation and counts below remain historical; unsupported execution still prevents proof.

Game: Resident Evil 2 USA Disc 1, Leon A, SLUS-00421, executable `SLUS_004.21`, SHA256 `1cd618bc4390db4bd60735b0db1e91534f6134ede56fae454eb580be2aa686ef`. The replay uses RE2-LIVE-002/003 captures from DuckStation `0.1-12083-g00e299795 (dev)`, with their recorded health, ammunition and position setups. This contribution did not start or modify an emulator, game, save or user exploration history.

### Failure and native contract

The former reader excluded inactive candidates from the required count and could publish Cleared without proving their absence. It also forgot an established uncollected item after departure, even when a source proof could reconstruct that identity. The approved behavior is the shared [collection policy](../room-completion.md): an established item remains required until its acquisition flag records collection, independently of activation. Unproven identities and optional creators remain unresolved.

The pinned executable's command table is at PS1 virtual `0x8009F94C`, 32-bit little-endian handler pointers with full mask `0xFFFFFFFF`. All code locations in this entry are also PS1 virtual addresses; instruction words are 32-bit little-endian. Its item factories retain the acquisition behavior in RE2-SCD-001. Native `Aot_reset`, `0x800517D4..0x80051844`, overwrites the descriptor's handler and three little-endian 16-bit payload words, full mask `0xFFFF`, including item type, amount and acquisition ID for an item source. Therefore an inactive pointer does not authorize the initializer's original identity by itself.

Native startup at `0x8004FE60..0x8004FEA8` schedules procedure 0 from both section 16 and section 17 before dispatch. `Gosub`, `0x80050A44..0x80050AA8`, uses the current global main-procedure table, including from the init task. `Evt_end` and `Return`, `0x80050098..0x800500F8` and `0x80050AAC..0x80050B00`, restore the caller's pointer when nested. The audited object and enemy setup handlers, `0x800518E0..0x80051B88` and `0x800537CC..0x80053D90`, advance the script pointer by 38 and 22 bytes and return continuation. Flag writes at `0x80050C50..0x80050D0C` change flag storage rather than declaring collectible identity. These are source contracts from the pinned executable, not newly observed gameplay outcomes. Executable offsets are `0x800 + virtual_address - 0x80010000`.

### Bounded presence proof

The generator derives mandatory item identities from the two startup roots. It intersects the identities on every supported branch outcome, follows bounded main-table calls and preserves collection identity through a zeroed inactive reset. It handles padding, flag writes and the audited object/enemy setup commands as fall-through operations. It does not use current flag values to choose a branch, so a merely conditional creator cannot become a required item. Acquisition flags are read afresh by the runtime reader.

Unsupported commands, incomplete candidate coverage, missing calls, recursive/cyclic paths, more than four nested calls or a 4,096-step bound discard the room's presence proof. Generic/door slot replacement, differing item identities sharing a slot, ambiguous identities sharing an acquisition ID and nonzero resets also prevent proof. An item initializer with a handler other than inactive or ordinary item is unsupported. This deliberately leaves complex scripted rewards and scenario-dependent absence unresolved.

Each generated room now requires an explicit `collection_item_ids` list; startup rejects missing or malformed lists and IDs without an unambiguous catalog identity. The current output proves five IDs in three sources, `00-0e`, `00-1a` and `02-0c`. One is a file excluded by the existing file policy, leaving four relevant collectible identities. These are offline proof counts, not new room or campaign coverage. Owned-disc regeneration produces room metadata SHA256 `cd79508675758a0a1bf610d03fb47e119e2e2ab1b3bd34087267b46667fb7a85`; map metadata remains byte-identical.

The same fresh identity/flag rule applies to current and departed rooms. Source-established inactive or missing interactions report `uncollected`, count as remaining and appear in the shared Remaining items overview. A known remaining item forces Incomplete even if other checks are unresolved. Unproven inactive candidates report Unknown and cannot permit clearance. Conflicting item types remain Unknown even with an acquired flag. No item state, presence evidence or completion verdict is added to persistent visit history.

### Reproduction and limits

Run the focused command in [RE2 testing](../testing/re2.md). Synthetic cases exercise conditional returns, branch identity/quantity joining, uncalled procedures, main-table calls, unsupported effects, slot replacement, recursion, metadata rejection, overwritten inactive records, missing registries, current/departed consistency, cache loss and fresh collection reversal. The shared browser already handles `uncollected` as remaining; no renderer, controls or screenshot content changed.

Private `/tmp/re-map-re2-completion/replay.py` compares the previous and new production readers over 19 unchanged RE2-LIVE-002/003 RAM captures. Nine room/region visits, current rooms, headings, door observations and acquired counts agree throughout. The captured pickup prompt still returns Retry without changing publication. At `route-rewind-outside`, the departed `00-1a` changes from Unknown to Incomplete with its source-proven ID 195 uncollected; `route-restore-later` restores Taken/Cleared. A separate production history save/close/reopen starts with only visits and reconstructs both results from the same unchanged captures.

The former post-ammunition shop clearance becomes Unknown because the inactive candidate's startup source remains unsupported. Its item identity is not promoted by an old pointer or the new policy. The replay records exact capture hashes and before/after completion differences in private `replay.json`. These temporary captures are not portable fixtures, new savestate loads, native reward activation or a running-tracker restart. Existing gameplay confirmation remains limited to RE2-LIVE-002/003. Later scripts, optional/scenario absence, direct event awards and general door reconstruction remain unresolved.

Contributions:

- 2026-10-18; human user; explicitly approved RE2 collection-based completion after choosing to continue toward RE1 parity, with spoiler-free agent testing.
- 2026-10-18; Codex root, exact model `gpt-6.1-sol`, verified from the matching session's latest turn metadata; inspected pinned native handlers, implemented bounded source proofs and fresh current/departed collection semantics, regenerated numeric metadata, added regressions, compared unchanged captures and performed the private history-file round trip; authored this entry.
- 2026-10-18; `gpt-6.1-sol`; final validation passed all 1,686 Python tests, the 57-case focused RE2 suite, both browser suites, scoped Ruff lint/format checks, 216 changed-document local links/anchors, byte-identical owned-disc regeneration and `git diff --check`. The browser suites retain all 118 RE1 and 133 RE2 outlines and the existing remaining-item controls. These checks establish implementation regressions, not additional gameplay confirmation.
- 2026-10-18; returned identifiers `Claude Opus 4.6 (Thinking)`, conversation `eb8063d5-2814-42d3-9780-cdadaecf5e0f`, and `Gemini 3.8 Flash (High)`, conversation `c9d89733-888c-4863-a969-25fa0cb2faee`; reviewed the complete supplied diff, decoder/proof, profile validation, live reader, generic completion records, regressions and stated source contracts/limits. Neither returned an actionable finding. Both processes exited zero, completed an agent response, returned terminal SUCCESS and a nonblank response, had empty stderr and attempted no tools. This uses the previously human-approved Opus version in place of unavailable Opus 5.5. Prompt SHA256 `8f074bd1263b9c88197b187971dad025c1d48723f8a870a558d771f0691b0a32`; private evidence is under `/tmp/re-map-re2-completion/review/`. Subsequent edits add claim references, address-mask wording and validation provenance; runtime interpretation and generated presence proofs are unchanged. These advisory reviews did not run tests or validate gameplay.

## RE2-COLLECT-002: conflicting slots preserve unrelated item proofs

Status: Candidate for SLUS-00421. Generated metadata, synthetic source/runtime regressions and unchanged-capture replay. No new gameplay, pickup, save load or runtime coverage.

Game: Resident Evil 2 USA Disc 1, Leon A, SLUS-00421, executable `SLUS_004.21`, SHA256 `1cd618bc4390db4bd60735b0db1e91534f6134ede56fae454eb580be2aa686ef`. Native command and acquisition contracts are unchanged from RE2-COLLECT-001 and RE2-SCD-001. The reused RE2-LIVE-002/003 captures came from DuckStation `0.1-12083-g00e299795 (dev)` with their recorded agent patches. This pass did not start an emulator or change user saves/history.

At baseline `d3f60a4`, differing item identities in one slot discarded the entire room's presence proof. In source `01-03`, conditional IDs 34/36 share slot 1, but ID 35 is declared independently on every supported startup path. In `01-14`, slot 5's conflicting types for ID 68 similarly erased the mandatory IDs 62/64/65 in unrelated slots. The lost proofs made the departed rooms Unknown even when those independent items remained uncollected.

The shared decoder now identifies conflicting slots and excludes their item creators from the required set. It still traverses every supported path, so this does not skip an unsupported instruction or turn a conditional/uncalled item into a mandatory one. The final acquisition-ID/type consistency check still rejects conflicting identities across different slots. All existing bounds, call/branch handling, generic/door replacement rejection, reset restrictions and runtime coherence remain unchanged. Conflicting slots contribute no mandatory presence proof; existing live observations can still establish a currently active item. Their inactive/departed identity needs further source/history evidence.

Owned-disc regeneration changes only `collection_item_ids` in `01-03`, from empty to `[35,153]`, and `01-14`, from empty to `[62,64,65]`, plus the new research reference. ID 153 is an excluded file. Four additional relevant collectible identities retain proof, increasing the offline total from four to eight across five sources. All previous proofs survive. Room metadata SHA256 is `b7eeba65eabe14bd3755cbf7b88d2a4f4110eca0dde3b44827f5658c38414252`; the floor-plan metadata is byte-identical. These counts are not a gameplay-readiness measure.

Reproduce with the owned-disc generation command and focused suite in [RE2 testing](../testing/re2.md). New synthetic cases exercise both declaration orders, conflicting IDs versus types, branch alternatives, uncalled conflicting definitions, cross-slot acquisition aliases and unsupported control flow. Current/departed runtime cases keep two proven items `uncollected` alongside an ambiguous item, collect them, then reverse the flags. The room changes Incomplete → Unknown → Incomplete; setting the ambiguous item's acquisition bit does not establish its type or permit clearance. Fresh trackers reconstruct the remaining items from metadata and flags without retained observations.

Private `/tmp/re-map-re2-independent-items/audit.py` compares the baseline and new catalogs through the unchanged production reader. All 19 existing captured publications match exactly, including visits, items, heading and doors, because neither affected room was visited in those captures. A separate projection explicitly adds synthetic visits to `01-03`/`01-14` and changes only copied acquisition words at PS1 virtual `0x800CC9EC` and `0x800CC9F0`, unsigned 32-bit little-endian, masks `0x10000002` and `0xC8000000`. These are private bytearray edits, not guest-memory writes. Known remaining items now produce Incomplete; after their synthetic collection both rooms remain Unknown; reversal restores Incomplete. The previously captured incoherent prompt still leaves publication unchanged. `audit.json` preserves capture hashes and distinguishes the synthetic projections from the unchanged runtime evidence.

The startup proof remains limited to supported simple scripts. Generic slot replacement, nonzero resets, unsupported effects, optional/scenario absence and direct awards remain unresolved. No renderer or screenshot content changed, and no game content was displayed or reported to the human.

Contributions:

- 2026-10-18; human user; explicitly approved independent RE2 item checks after reviewing the scoped behavior, with spoiler-free testing.
- 2026-10-18; Codex root, exact model `gpt-6.1-sol`, verified from the matching session's current turn metadata; identified the whole-room rejection, implemented slot-local exclusion, regenerated metadata, added regressions and audited unchanged captures plus separately labeled synthetic projections; authored this entry.
- 2026-10-18; `gpt-6.1-sol`; validation passed all 1,696 Python tests, the 67-case focused RE2 suite, both browser suites, scoped Ruff lint/format checks, byte-identical owned-disc regeneration, 219 changed-document local links/anchors and `git diff --check`. All previous presence proofs survive, and the 19 unchanged captured publications remain identical. These checks do not add gameplay coverage.
- 2026-10-18; returned identifiers `Claude Opus 4.6 (Thinking)`, conversation `cc9eab0a-1987-48c1-8aff-5b5063ce0f10`, and `Gemini 3.8 Flash (High)`, conversation `72b6c8e6-fb2b-4aac-aaba-6ac95478f845`; reviewed the full supplied diff, complete collection proof, metadata and runtime regressions, unchanged reader/validation/completion contracts and stated source limits. Both returned No findings, exited zero, completed an agent response and terminal SUCCESS, had empty stderr and attempted no tools. The Opus version remains the previously human-approved alternative to unavailable Opus 5.5. Prompt SHA256 `0c7d3d83582d688530fa31220efae0b145a15c8b9a14c002912838fcf3ae61ce`; private evidence is under `/tmp/re-map-re2-independent-items/review/`. Only documentation wording and validation provenance changed after the supplied snapshot. These advisory reviews did not run tests or validate gameplay.


## RE2-COLLECT-003: scripted activation preserves collection identity

Status: Candidate for the shared source rules on SLUS-00421, with the single runtime reward sequence below observed on the named revision. Other generated proofs remain offline results.

Game: Resident Evil 2 USA Disc 1, Leon A, SLUS-00421, executable `SLUS_004.21`, SHA256 `1cd618bc4390db4bd60735b0db1e91534f6134ede56fae454eb580be2aa686ef`. Agent tests use DuckStation `0.1-12083-g00e299795 (dev)`. This entry extends RE2-COLLECT-001/002; their earlier whole-room reset and generic-slot restrictions describe historical implementations.

### Failure and native contracts

At baseline `26fd305`, the captured shop's disabled ID 15 remained Unknown. Its mandatory declaration follows unrelated resets, actor setup and automatic event scheduling, which the bounded proof rejected. The item must remain required before activation and after departure. Its initial quantity is five, but its activation reset supplies four; the initial amount cannot describe every state.

All addresses here are PS1 virtual addresses. Instruction words and command-table pointers are 32-bit little-endian, full mask `0xFFFFFFFF`; byte operands use `0xFF` and payload words use `0xFFFF`. Executable offsets are `0x800 + virtual_address - 0x80010000`. The pinned dispatch table remains at `0x8009F94C`.

Native `Evt_exec`, `0x80050140..0x80050174`, advances four bytes and schedules the procedure in byte 3. In ordinary script mode, automatic task IDs at least ten select tasks 2 through 9 at `0x8004FAA0..0x8004FBA8`. The dispatcher finishes each non-yielding startup task before running those tasks. The proof accepts only automatic scheduling to an existing main procedure; it never adds the child's declarations to the mandatory set. Explicit task replacement remains unsupported.

The audited handlers for scalar calculation `0x26`, actor-work selection `0x2E`, actor position `0x32`, member assignment from a scalar `0x35`, member copy `0x3D`, camera replacement `0x4B` and actor-part assignment `0x6E` advance by their packet widths and return continuation. Their pinned handler starts are respectively `0x80050E28`, `0x80051F84`, `0x80052220`, `0x800522D0`, `0x800524B8`, `0x800511CC` and `0x80052050`. Native branch helpers at `0x80050ED0`, `0x80052330` and `0x800525D0` operate on scalar or actor fields. These are source-inspection contracts, not separate gameplay confirmations. Private `native.txt` records the inspected instructions.

`Aot_reset` changes only the descriptor registered in its named slot. The source proof now examines resets throughout the room, including later events. A zeroed inactive reset preserves collection identity. An ordinary-item reset preserves it only when type and acquisition ID match; quantity may differ. Other resets and non-item creators exclude that slot's proof without excluding unrelated items. A reset that introduces an item absent from the creator catalog makes full-list coverage unresolved. Unknown instructions, optional creators, unsupported control flow and existing traversal bounds still prevent proof.

Each creator now includes a required, validated `amounts` list containing its initial amount and matching reset alternatives. A live active descriptor supplies the current amount. Without it, multiple alternatives produce the existing explicit unreconstructed quantity state. No quantity or collection observation is added to persistent visit history.

### Generated results and regressions

Owned-disc regeneration adds mandatory proofs in `00-01`, `00-06`, `01-08`, `01-09`, `01-10` and `01-15`. All earlier proofs survive. The total is 24 acquisition IDs, including 17 relevant collectibles, across eleven sources. These counts describe source interpretation, not campaign readiness. Unmatched item resets make `03-01` and `05-10` explicitly incomplete in source coverage. Room metadata SHA256 is `fbeb843f93a01e7407f11d3168ed30270314bf38de247dc39b7ef035b817b29b`; native floor plans remain byte-identical.

Synthetic regressions cover unrelated resets, matching activation with a changed amount, later identity mutation, unmatched item resets, asynchronous declarations and slot replacement, explicit/missing tasks, audited actor setup, required quantity metadata, and fresh acquisition reversal. The real generated `00-01` proof is exercised through disabled, available, taken and restored states. These tests do not constitute gameplay evidence.

### Runtime evidence and reproduction

Private evidence is under `/tmp/re-map-re2-scripted-pickup/`. Before boot, both achievement integrations were verified disabled, memory cards were None and the isolated emulator enabled the existing black display shader. A private screenshot's central half had zero minimum and maximum channel values. No game image was emitted. The test started from the previously captured `ammo-both.sav`, SHA256 `89e6315c5c8138784c9a27b138e90c78d4520107d1467b2f6b79d8f7baa7e570`.

The agent used recorded position/yaw and collision-coordinate writes to reach interactions, with the checkpoint's earlier assisted health/ammunition state retained. This pass did not write acquisition, key, story, enemy or inventory flags. Actual controller input activated the reward and confirmed collection. ID 15 uses acquisition bank 8 at `0x800CC9E8`, unsigned 32-bit little-endian, mask `0x00010000`. The word changed from `0xC0000000` to `0xC0010000`, and inventory gained type 7 with amount four. The initialized descriptor remained inactive before activation; during the item prompt it became kind 2 with payload type 7, amount four and ID 15 while the acquisition bit was still unset. The temporary prompt relocated a source section, so the production reader correctly returned Retry without changing publication.

The production reader replay of `before-activation`, SHA256 `907971f16e2798b805ac329f46b291e659392bc6e2282b14a8565592aa807911`, reports uncollected/Incomplete. `interaction-one`, `bf338ce042ff1d10819a2b3e4c77a8df46fa20148e011b7c88d047f0817b66d9`, preserves the activation-without-collection observation and returns Retry. `pickup-confirmed`, `a8c723bbdd99813b7610999d02e895ec2b92afca629143505b41929dfe67c1e8`, reports taken/Cleared. A native door transition to `00-02` in `departed-after-collection`, `ab80175fce964ff382f27f441802fac1462db67665d33f7138d6457e34210647`, retains that result for the departed room. An actual earlier savestate load in `rewind-before-activation`, `d5e8ef3230dba0ec4086f607da8af021da147e0cfae278e143ea11ceea068af0`, restores uncollected/Incomplete while preserving both visits. A later load in `restore-collected` reproduced `pickup-confirmed` byte for byte. The agent then left through the same door and returned using native input from the neighboring source. After the transition, `reentry-collected-stable`, SHA256 `4086bb304f16cd3782aab1d14a6c6be40cb3b074f2409a7e6cb4f8b0fa1f37dc`, reports taken/Cleared. Its immediately preceding transition capture correctly returned Retry. The later checkpoint `after-collection.sav` has SHA256 `0c0454888cb50cdbc72c5052801b9836a14b42c2deb651d0b74786ccbb0c1971`.

`audit.py` compares the old catalog and new catalog through the production reader over 19 unchanged RE2-LIVE-002/003 captures. Current rooms, headings, visits and door observations agree. The old unresolved shop reward becomes source-established and uncollected; the first two ammunition collections do not clear that room. The new quantity alternatives suppress the stale initial amount when no live descriptor supplies it. `audit.json` records the hashes, publications and separately captured new runtime states. Raw RAM and checkpoints remain outside Git.

Provisional filenames `reentry-after-collection` and `return-door-check` did not reach the return destination. Likewise, `activation-cancelled`, `activation-prompt-second` and `repeat-activation` did not establish activation or cancellation; enemy contact displaced the player. These attempts are excluded from successful interaction evidence. For the accepted return, the agent placed the player at X = -25813, Z = 21350, yaw = 3072, walked forward for 700 ms, used repeated Cross and allowed the room transition to finish. Position writes and widths are recorded in `position-edits.jsonl`; their address interpretation remains the candidate setup from RE2-LIVE-003. Runtime observations remain limited to the recorded setup. Other scripted rewards, scenario absence, direct event deliveries, key unlock reversal, heading alignment, normal saves and a complete campaign remain unvalidated. The final earlier-state load reproduced `rewind-before-activation` byte for byte. After testing, the isolated emulator was stopped and its original settings and selected slot restored byte for byte, as recorded in private `cleanup.json`. No renderer or README screenshot content changed.

Contributions:

- 2026-10-18; human user; explicitly approved this scripted pickup increment and required spoiler-free agent testing.
- 2026-10-18; Codex root, exact model `gpt-6.1-sol`, verified from the matching session's latest turn metadata; inspected pinned native handlers, implemented shared reset/scheduling rules and quantity alternatives, regenerated metadata, added regressions, performed hidden controller interactions and actual savestate loads, and compared captures with the production reader; authored this entry. Source inspection and synthetic checks are distinguished above from the named runtime observations.

- 2026-10-18; `gpt-6.1-sol`; validation passed all 1,718 Python tests, the 89-case focused RE2 suite, both browser suites, scoped Ruff lint/format checks, 222 changed-document local links/anchors, byte-identical owned-disc regeneration and `git diff --check`. The metadata audit confirmed that only collection proof sets, coverage flags, quantity alternatives and the research reference changed. These implementation checks do not extend the named runtime coverage.

- 2026-10-18; returned identifiers `Claude Opus 4.6 (Thinking)`, conversation `baaba46a-877a-4c0c-bbc8-3aa764908bcb`, and `Gemini 3.8 Flash (High)`, conversation `9a6dd03c-9817-442e-92eb-85fa5062b282`; reviewed the supplied source/test/profile/documentation diff, full decoder/reader/profile/completion contracts and tests, exact generated-data change summary and pinned native contracts. Both returned No findings, exited zero, completed an agent response and terminal SUCCESS with a nonblank response, had empty stderr and attempted no tools. Opus uses the previously human-approved alternative to unavailable Opus 5.5. Prompt SHA256 `1e4602778750b4104e5f15bedf2027d80758e1ead02edfc3de5c0b3c312fc188`; private evidence is in `/tmp/re-map-re2-scripted-pickup/review/`. Subsequent changes only correct documentation wording and append the later restore/reentry, cleanup and validation provenance. These advisory reviews did not run tests or validate gameplay.


## RE2-DOOR-001: event-driven unlock and savestate reversal

Status: Confirmed for the recorded event-driven bank 31 bit 17 unlock, listed passages, reentry and DuckStation restores on SLUS-00421. Named-key use and unlocking a one-sided lock by operating its door handler remain Candidate. This is one controlled door case, not general door coverage.

Game: Resident Evil 2 USA Disc 1, Leon A, SLUS-00421, executable `SLUS_004.21`, SHA256 `1cd618bc4390db4bd60735b0db1e91534f6134ede56fae454eb580be2aa686ef`. Emulator: DuckStation `0.1-12083-g00e299795 (dev)`. Production baseline: `8fad72d`. No tracker behavior, generated catalog, renderer or README screenshot changed. The existing interpretation matched this case.

### Native contract and accepted observations

The accepted case is the event-driven opening of `01-00` door slot 3, paired with `01-0a` slot 0. In `PL0/RDT/ROOM2000.RDT`, main procedure 6 resets the live interactions in slots 1 and 3 to ordinary doors after the native access interaction succeeds. The reset commands are at file offsets 10768 and 10778. The command at 10788 sets bank 31 bit 17; it follows a check of story bank 4 bit 70. In `ROOM20A0.RDT`, the ordinary Leon A initializer at 2178 declares the counterpart with lock ID `0x91` and type `0xFE`. The current-room source pointer selects that declaration rather than its alternate definition at 2090.

All addresses below are PS1 virtual addresses, not host addresses. Bank 31 starts at `0x800CCB60`, width eight bytes. The observed word at that address is unsigned 32-bit little-endian; bit 17 uses mask `0x00004000`. Its bytes changed from `00 00 00 00` to `00 40 00 00`. The other bank bytes remained zero. Bank 4 bit 70 is at `0x800CC988`, unsigned 32-bit little-endian, mask `0x02000000`. The access interaction set that prerequisite and the key-bank bit through game code. The agent never wrote acquisition, key, story, door-descriptor or inventory state directly.

The existing native flag contract from RE2-SCD-001 predicts that `0x91 & 0x3F` selects bit 17. The current counterpart descriptor consequently becomes Open/Unlocked. Its initializer retains `0xFE`; the flag supplies the unlock knowledge. Native inspection of the pinned door handler at `0x8004DFC0..0x8004E1C0` and SCD flag predicate at `0x80050BF0..0x80050C4C` agrees with the existing contract. Code words and pointers are unsigned 32-bit little-endian with mask `0xFFFFFFFF`; descriptor byte fields use mask `0xFF`. These source inspections do not establish other locks' gameplay behavior.

Ten accepted case captures are listed below. Private evidence is under `/tmp/re-map-re2-door-unlock-20261018/`; filenames alone do not establish success.

| Capture | Observed result | RAM SHA256 |
| --- | --- | --- |
| `access-locked-ready` | `01-00` current, key bit clear, slot 3 is an event; tracker withholds access. | `4516ab0a026f0448257d5f248862474f6edacfcb7586d207d9931f81de66e421` |
| `after-access-unlock` | Native access interaction set bit 17 and restored the door descriptor; current door reports Open. | `08bf093c6aaed812425d33f7b1c1219debe60f7e20a1b6d8bae77a8684c052e6` |
| `opposite-side-unlocked` | Actual `01-00 → 01-0a` passage; counterpart reports Open/Unlocked. | `05e86f76b72fdb36c53f5f2619f52941962e795d87567ab036a4ee2ffbb3c03b` |
| `rewind-access-locked` | Actual earlier load clears bit 17 and restores the event descriptor; visited counterpart loses its unlock label. | `4516ab0a026f0448257d5f248862474f6edacfcb7586d207d9931f81de66e421` |
| `passage-blocked-before-unlock` | Native interaction at the same first-side door does not leave `01-00`; bit 17 stays clear. | `56a36c56d5f813c0833e4336fb251ef267a60ac7fc8b4b31e59acef83c9cdd02` |
| `restore-opposite-unlocked` | Actual later load restores bit 17, counterpart Open/Unlocked and the original RAM bytes. | `05e86f76b72fdb36c53f5f2619f52941962e795d87567ab036a4ee2ffbb3c03b` |
| `return-door-transition-check` | Accepted native `01-0a → 01-00` return after the later load; current door is Open. | `759f65d3a5820b2e4ea47b1b8083f6da792c9bee3517c3dda7c1f720ae15d2f5` |
| `reentry-unlocked` | Native `01-00 → 01-0a` reentry; counterpart remains Open/Unlocked. | `7c947acf37701fbff6c20fbc9b1be0be005789e4573a5b2c2298ba7a1211c51d` |
| `repeat-access-locked` | Another actual earlier load reproduces the first pre-unlock RAM bytes. | `4516ab0a026f0448257d5f248862474f6edacfcb7586d207d9931f81de66e421` |
| `repeat-access-unlocked-final` | A second native access interaction sets bit 17 again and restores the current door to Open. | `7dc19c5e54722e64f50fe8c2a676a70d5a59bf88fabe7c82d0268532719972c2` |

While `01-0a` is departed, a set bit produces `Unlocked; access unconfirmed` with state Unchecked. It does not assert that the departed door is active. Rewinding to the clear bit restores `Door conditions unresolved`. The current first-side event also remains Unchecked before activation. Observed denied passage does not turn this deliberately incomplete generic event interpretation into a source-proven Blocked state.

`audit.py` replays these ten captures and three accepted setup captures through the unchanged production reader. It asserts the flag word, current room, exact door binding, both fresh unlock-label transitions and retained visits. The accepted setup captures are `before-route`, `before-unlock` and `control-return-check`; `01-02` was visited during setup. Together the pass contains three sources. Two are new relative to RE2-LIVE-003, bringing accepted runtime source coverage across the recorded passes to eleven. This does not establish complete item or door coverage in those rooms.

A separate production history-file save/close/reopen retains the three room/map visits and playthrough identity. Restored history initially has no current room or door observations. Polling the earlier capture reconstructs unresolved access; polling the later capture reconstructs Open/Unlocked. This is an offline history-file round trip over real captures, not an observation of restarting the full live tracker. The actual emulator loads are the independently captured operations above. Neither establishes normal memory-card persistence.

### Setup, reproduction and excluded attempts

Before boot, both achievement integrations were disabled, memory cards were None, per-game overrides were absent and the isolated copy enabled the existing black display shader. A private screenshot's central half had zero minimum and maximum channel values. No gameplay image was emitted. The starting `entrance-ready.sav` is the RE2-LIVE-003 checkpoint, SHA256 `156a026d3bce5b039b48f0f5f3a14f78a551e8b3be10ce5afcb4c0e1d0ce0c73`. It retains that pass's assisted health/ammunition state. No additional health or ammunition patch was written in this pass.

This is position-assisted validation. `position-edits.jsonl` records each X/Z/yaw write and the associated position fields from RE2-LIVE-003. Additional placement writes set Y at `0x800C7D60`, signed 32-bit little-endian, and adjust the observed signed 16-bit fields at `0x800C7D6A` and `0x800C7D70` by the same height delta to retain their body offsets. The controlled floor index at `0x800C7E2A` is unsigned eight-bit, mask `0xFF`. Y = 0/floor = 0 comes from `ROOM2010.RDT`'s return-door packet at 3018; Y = -1800/floor = 1 comes from `ROOM20A0.RDT`'s return packet at 2178 and the captured native hall entry. `placement-provenance.json` corrects the private floor command's fixed source annotation for the floor-one write. These are test setup values, not a confirmed formula for deriving floor from Y or evidence of a natural stair transition.

Prepare the access interaction through native gameplay from the checkpoint. The accepted pre-unlock placement after collision resolution is X = -14935, Y = -1800, Z = 2099, yaw = 2048, floor = 1 in `01-00`, with the natively acquired access item present. `access-locked-ready.sav` has SHA256 `83c9c444859fb42a43ed033a05cba1a5131d7c78da78f6c1fd93343b7c5dc8b3`. Resume explicitly through GDB, then use native repeated Cross, the isolated O macro. Continue native dialogue until the key-bank change is observed. The repeated run needed additional dialogue input; elapsed time alone does not prove completion.

For outbound passage, place X = -1349, Z = -24314, yaw = 1024 on the already established Y = -1800/floor = 1 and use native Cross. For the accepted return, restore the later checkpoint and use its observed entry position X = -15486, Y = 0, Z = -15268, floor = 0, facing yaw = 2048, with immediate repeated Cross. The accepted return and subsequent reentry form a continuous pair after that restore. `opposite-side-unlocked.sav` has SHA256 `1c026c81848e5773961f8de5734562260c9dd9111f8444951e42c0dc1343005c`. `access-unlocked.sav`, an earlier post-activation checkpoint in the first room, has SHA256 `dfd5be7bb5db71424ce99ad5800bcc897237011298ef40900c60286e2149a77c`.

Early provisional terminal/item-use captures targeted a different interaction and retained a mismatched height/floor. They establish neither access-item use nor an unlock. Inventory diagnostics established the configured Circle/L status and Triangle/I cancel controls; held-button macros were temporary diagnostics. Six inventory captures whose source layout was temporarily replaced correctly returned Retry; a replay verifies unchanged publication for each. The provisional `returned-after-unlock` stayed in `01-0a` after enemy contact and is excluded as a successful return. The intermediate `repeat-access-unlocked` still had a clear bit and is excluded as a completed unlock; only the final capture above supplies that result. No failed attempt is treated as passage, enemy death, collection or unlock evidence.

After testing, the isolated emulator was stopped and its original settings and selected test slot restored byte for byte. Private `cleanup.json` records both restored hashes. Raw RAM, savestates, extracted game data and diagnostic helpers remain outside Git. Remaining gaps include native named-key use, operating one-sided unlock handlers, other event conditions, conditional floors, heading/marker alignment and normal saves. No full campaign or uninterrupted ordinary-navigation route is claimed.

Contributions:

- 2026-10-18; human user; approved the named RE2 door-unlock and savestate-rewind increment with hidden agent gameplay and fixes only for confirmed tracker mismatches.
- 2026-10-18; Codex root, exact model `gpt-6.1-sol`, verified from the matching session's current-turn metadata; inspected pinned source contracts, prepared the position-assisted isolated setup, performed native access/door interactions and earlier/later loads, excluded failed attempts, replayed the unchanged production reader and checked the separate history-file round trip; authored this entry. No production mismatch was found in this case.

- 2026-10-18; `gpt-6.1-sol`; validation passed the 89-case focused RE2 suite, scoped Ruff lint/format checks, 225 changed-document local links/anchors and `git diff --check`. The private audit passed all thirteen required accepted captures, six Retry captures with unchanged publication, byte-identical earlier/later restore comparisons and the separate three-visit history-file round trip. Every logged direct guest write was checked against the listed position/floor fields. These checks do not extend the stated gameplay scope.

- 2026-10-18; returned identifier `Gemini 3.8 Flash (High)`, conversation `5b873c6b-c984-4576-bf7f-10a917031048`; reviewed the complete documentation/reference diff, unchanged reader/history/completion context, pinned event and door metadata, numeric capture extraction and private audit. It returned No findings, exited zero, completed an agent response and terminal SUCCESS with a nonblank response, had empty stderr and attempted no tools. The attempted `Claude Opus 4.6 (Thinking)` perspective, conversation `e8e53fae-c6f2-4277-8bcb-4f58427f2c21`, failed with `RESOURCE_EXHAUSTED`/HTTP 429 before reviewing any input; the service reported an individual quota reset in 133h36m38s. It supplied no review and was not retried. Its failure is not an endorsement. Prompt SHA256 `282e8b660b543573a23b9dbd0f1e82e278e9b4e4b52f96210fd0b37dd6941cf9`; private evidence is under `/tmp/re-map-re2-door-unlock-20261018/review/`. Only this provenance was appended after the reviewed snapshot. The prose review did not perform runtime validation.

## RE2-DOOR-002: named-key use and savestate reversal

Status: Confirmed for the controlled SLUS-00421 cases below. Other key locks, one-sided unlock operations and full room/campaign coverage remain unverified. No tracker behavior change was needed.

Game: Resident Evil 2 USA Disc 1, Leon A, SLUS-00421, executable `SLUS_004.21`, SHA256 `1cd618bc4390db4bd60735b0db1e91534f6134ede56fae454eb580be2aa686ef`. Test emulator: official DuckStation `0.1-12083-g00e299795 (dev)`. Revision, source-binding and flag contracts are in [RE2-IDENTITY-001](#re2-identity-001-leon-a-disc-identity-and-candidate-room-layout) and [RE2-SCD-001](#re2-scd-001-bounded-leon-room-metadata-and-acquisition-contracts). This extends [RE2-DOOR-001](#re2-door-001-event-driven-unlock-and-savestate-reversal) with native named-key use rather than an event-written unlock.

### Pinned source contracts

The owned `ROOM2000.RDT` declares item type 89, acquisition ID 93, in slot 9 at offsets 9826/9852. Main procedure 8 resets that slot to Item with the same identity and scenario-specific quantity, then invokes it through `Aot_on` at 11414. The observed Leon A quantity was two. Its prerequisite, item type 71/acquisition ID 104, was natively collected in `ROOM1150.RDT` and used through the native status menu in `01-00`. No inventory, acquisition, key, story or enemy-state fields were written directly.

The tested named-key door is `01-04:6430`, `ROOM2040.RDT` slot 2, target `01-03`, lock ID `0x85`, key type 89. Its counterpart is `01-03:1726`, `ROOM2030.RDT` slot 0, target `01-04`, with lock ID zero. The counterpart is an ordinary Open door; this case does not prove that both sides share a named-key descriptor.

In the pinned executable, `0x8004E0D4..0x8004E140` calls the inventory lookup at `0x80064EAC`, prepares the key-use message/callback when a matching inventory slot exists, then calls the shared flag setter for `lock_id & 0x3F`. The observed unlock bit changes before the message callback finishes reducing the key's use count. That intermediate state is recorded separately from completed use and passage.

All addresses below are PS1 virtual, little-endian. They are not host-process addresses. The whole key bank is freshly read at `0x800CCB60`, width eight bytes; the whole early acquisition bank is at `0x800CC9E8`, width 32 bytes.

| Value | Width and mask | Observation |
| --- | --- | --- |
| Acquisition ID 104 at `0x800CC9F4` | unsigned 32-bit, mask `0x00800000` | clear before native prerequisite pickup, set after pickup and later use |
| Acquisition ID 93 at `0x800CC9F0` | unsigned 32-bit, mask `0x00000004` | clear before the reward sequence, set after native key pickup |
| Unlock bit 5 at `0x800CCB60` | unsigned 32-bit, mask `0x04000000` | clear without the key and while carrying it; set after native door use |
| Inventory slot 3 type at `0x800CCB74` | unsigned eight-bit, mask `0xFF` | prerequisite type 71, then empty after use, then key type 89 after pickup |
| Slot 3 quantity at `0x800CCB75` | unsigned eight-bit, mask `0xFF` | key quantity two after pickup and at unlock-message start; one after acknowledgment |

The relevant unlock word was `0x00004010` while carrying the key and `0x04004010` after using it. Other unlock bits already set by native preparation remained present. The earlier pre-acquisition checkpoint has word `0x00004000`; it predates part of that preparation. Acquisition ID 93's word changed from zero to `0x00000004`. Earlier/later loads reverse and restore these game-derived values.

### Captured outcomes

Expected behavior: an acquired key is Taken, carrying it does not establish an unlock, native use opens the bound door and removes its key label, departed activation remains unconfirmed, and restored item/door flags replace current knowledge while visits accumulate. The unchanged production reader met those expectations.

| Capture | Observed outcome | RAM SHA256 |
| --- | --- | --- |
| `denied-without-key` | Native interaction stays in 01-04; target bit clear, no key in inventory; door Locked. | `c596bda4a1315ed0535eca26689f54de9b84d50f217c237b098a87bc5b343421` |
| `before-key-activation` | Prerequisite carried in 01-00; key acquisition ID 93 still clear. | `cda371e06c23b0a993adb9a60321e45c2e4a2667ed3601f0d476ffb9ec503b40` |
| `key-collected` | Native sequence collected the key; acquisition set, inventory quantity two, tracker Taken. | `0ffd6a8283e6e7644f9b79b9314872151583fbe4ffaf8882804ae50e6c4f846f` |
| `carrying-key-door-locked` | Returned to 01-04 carrying the key; bound door still Locked with its key label. | `ab341ed07fb922864f3fa7ed44a0929ea42559e760422eaee7b9fe1d33a1f647` |
| `key-present-locked-ready` | Saved pre-use state at the same door; key quantity two, unlock bit clear. | `a20af248af9d7c7832a009145443919b7d6e5b309cd4e14d50b36b1d3d205ff2` |
| `native-key-unlock` | One native interaction sets bit 5; current door Open/Unlocked, key label empty; quantity still two. | `0e39894d6e4f353eeefdee50f8fe1b54ff390b3e8ffee0f1d02b3f02503bbb22` |
| `key-use-complete` | Message acknowledged; same source and Open/Unlocked door, key quantity reduced to one. | `ca6041b7af853dd2722896e2fbe445d5d11a978d10f4004021125e9283d1a926` |
| `key-door-outbound` | Native 01-04 to 01-03 passage; counterpart Open, departed named door Unchecked/Unlocked; access unconfirmed. | `8fa95c78524ce3f102201b3ce387f6a578aafb2401d74b29d64dfd3d0784aea6` |
| `key-door-return-settled` | Native return to 01-04 after transition settles; current named door Open/Unlocked. | `48a159815effbea0380e5b881de5b4e1dc4ade67b560a59e4f612c07543f7227` |
| `key-door-reentry` | Native reentry to 01-03; unlock retained and no further key use consumed. | `58e9d79c5fd6c0ddacf33f140a3b96d3b2d8fa5afac5e2daaad4de98e96cfce1` |
| `rewind-key-present-locked` | Actual earlier load restores quantity two and Locked/key label; RAM identical to pre-use capture. | `a20af248af9d7c7832a009145443919b7d6e5b309cd4e14d50b36b1d3d205ff2` |
| `rewind-without-key` | Actual pre-acquisition load removes key possession and acquisition, restores Locked; visits retained. | `39d4f2c72bead74ae264a4e6cbf2b993bc6e29be8bf7798a0c3c9350b3eb7d68` |
| `restore-key-used-unlocked` | Actual later load restores quantity one and Open/Unlocked; RAM identical to completed-use capture. | `ca6041b7af853dd2722896e2fbe445d5d11a978d10f4004021125e9283d1a926` |
| `repeat-key-present-locked` | Another actual earlier load reproduces the pre-use RAM bytes. | `a20af248af9d7c7832a009145443919b7d6e5b309cd4e14d50b36b1d3d205ff2` |
| `repeat-native-key-use` | A second native use sets bit 5 again and reduces the key quantity to one. | `4ea24d14970cc5c943e66905c7be5c8a9340019ec6a61a4510c43e5cf2a2dc20` |

`audit.py` replays 25 required accepted captures through the production reader with the pinned revision and original source proofs intact. It compares every publication with the capture's original map state, checks acquisition/inventory/door transitions, and verifies that a departed named door remains Unchecked even when its fresh unlock label is known. Its key symbol disappears only on fresh unlock proof and returns on rewind. No new browser rendering or marker-placement claim is made.

The pass contains nine accepted room sources: `01-00`, `01-01`, `01-04`, `01-05`, `01-07`, `00-0c`, `00-14`, `00-15` and `01-03`. Eight are new relative to the eleven-source union recorded by RE2-LIVE-003 and RE2-DOOR-001. The recorded union is now nineteen. These are accepted runtime source reads, not complete item/door validation in those rooms or a campaign percentage. `coverage.json` derives the union from the previous audited capture lists and this pass's accepted list.

A separate production history-file save/close/reopen preserves the nine room visits, nine map-region visits and agent playthrough identity. The restored tracker initially has no current room or door observations. Polling the pre-use, pre-acquisition and completed-use captures reconstructs the corresponding Locked/Open result and acquisition state without losing visits. This is a file round trip over real captures, not a live runner restart. The actual emulator loads are independently recorded above. Normal memory-card persistence is not tested.

### Setup, reproduction and excluded attempts

Private evidence remains under `/tmp/re-map-re2-key-door-20261019/`. Raw RAM, savestates, owned source/executable data and diagnostic helpers remain outside Git. Before boot, both achievement integrations were false, cards were None, per-game overrides were absent and the existing black display shader was enabled. A private screenshot's central half had zero minimum and maximum channel values. No gameplay image was emitted. Agent visits used only the private history file.

Start from RE2-DOOR-001's `access-unlocked.sav`, SHA256 `dfd5be7bb5db71424ce99ad5800bcc897237011298ef40900c60286e2149a77c`. It retains RE2-LIVE-003's health/infinite-magazine assistance. This pass wrote no additional health/ammunition patch. Position/facing writes use the fields already recorded in RE2-LIVE-002/003 and RE2-DOOR-001. Controlled Y/floor placements use source door-entry packets: `ROOM2010.RDT` offset 3018 establishes hall Y = 0/floor = 0, and `ROOM1140.RDT` offset 2518 establishes `00-0c` Y = -3600/floor = 2. `ROOM2070.RDT` offset 3926 supplies that source's lower entry at Y = 0/floor = 0. `position-edits.jsonl` records all direct writes; `placement-provenance.json` distinguishes accepted setup from the first rejected floor attempt. This does not validate natural stair movement or a general Y-to-floor formula.

Prepare the prerequisite through the position-assisted native route `01-00 -> 01-01 -> 01-04 -> 01-05 -> 01-07 -> 00-0c -> 00-14 -> 00-15`, then return through the same sources. The accepted prerequisite interaction faces yaw 3072 from X = -20000, Y = 0, Z = -18025. Native file/pickup dialogue must finish before accepting the acquisition. The final collected capture has SHA256 `def20c550611405f2bd411d121ff4796dda8f1e64cee1c45f4aeca464547ded6`.

For native use in `01-00`, the accepted position is X = -13735, Y = 0, Z = -9806, yaw = 3072, floor = 0. Circle/L opens status; select inventory slot 3. In the pinned menu dispatch at `0x8006663C..0x8006670C`, action 1 calls inspection, 2 combination and 3 use/equip. Select action 3 and confirm with Cross/K. Earlier diagnostics assumed action 1 was Use; those inspection/combination attempts did not consume the prerequisite and are excluded as use evidence. Allow the native reward and pickup sequence to finish; only a set acquisition bit plus actual inventory quantity establishes the key pickup. The provisional `key-active-before-pickup` was already collected, so only `key-collected` names that accepted outcome.

For the named door, prepare X = -13326, Y = 0, Z = -8550, yaw = 0, floor = 0 in `01-04`. One native Cross begins key use and sets the bit. A later Cross acknowledges the message and reduces quantity; another enters `01-03`. Its observed entry is X = -26443, Y = 0, Z = -21844. Face yaw 2048 there and use Cross for return, then wait until the transition flag clears before accepting the current room. Reentry uses the original first-side preparation. The key-present pre-use savestate is `key-present-locked.sav`, SHA256 `e530308cd0b06eb0a9353790b9f7c3bfe9fc02f62d00c256c8c88a4dab827818`; the completed-use state is `key-used-unlocked.sav`, SHA256 `361435efcb9330a8fb1e4a712ec08b966eab81fe5c6e2448a4a5079f31b581e7`. The earlier pre-acquisition `without-key.sav` has SHA256 `58da4730c17b363f0d254031f20381c51f4a93434078368160af8b4a19bfe729`. Restore through the isolated selected slot using native F1, without changing guest-derived fields.

Enemy contact interrupted early route placements. Provisional `setup-room-0c` was still `01-07`, and `before-native-prerequisite` was still `00-14`; neither establishes the intended entry. The first upper-floor patch therefore ran in the wrong source and was reversed before accepted native entry. Unconfirmed return attempts during a native Start pause were retried after clearing that pause. Early pickup labels `after-prerequisite` and `prerequisite-collected` did not establish acquisition. Four transient captures, `pending-prerequisite-message`, `prerequisite-collected`, `after-key-activation` and `key-door-return`, returned Retry and left the tracker unchanged. The last was an unfinished return transition; only `key-door-return-settled` supplies the accepted outcome. No failed attempt is counted as collection, passage, unlock or new source coverage.

After testing, the isolated emulator was stopped and its original settings and selected slot restored byte for byte. `cleanup.json` records both restored hashes. Other named-key locks, one-sided unlock operations, other event rewards, natural conditional floors, heading/marker alignment, uninterrupted ordinary navigation and normal saves remain outside this confirmation.

Contributions:

- 2026-10-19; human user; approved the named RE2 key-based door-unlocking increment with hidden agent gameplay and fixes for confirmed tracking mismatches.
- 2026-10-19; Codex root, exact model `gpt-6.1-sol`, verified from the matching session's current-turn metadata; inspected the pinned source and native inventory/door branches, performed position-assisted native preparation, pickup/use, passage, reentry and actual earlier/later loads, excluded failed attempts, audited unchanged production publications and the separate history-file round trip; authored this entry. No production mismatch was found.

- 2026-10-19; `gpt-6.1-sol`; the 89-case focused RE2 suite, scoped Ruff lint/format checks, 231 local document links/anchors, profile claim reference and `git diff --check` passed. The private audit passed 25 required accepted captures, four Retry captures with unchanged publication, three byte-identical restore comparisons, fresh acquisition/access reconstruction after the nine-room/nine-region history-file round trip, and the position/floor-only guest-write check. These checks do not extend the stated gameplay scope.

- 2026-10-19; returned identifier `Gemini 3.8 Flash (High)`, conversation `bfaa0fb0-a30a-493b-ab80-99f766fc9161`; reviewed the complete documentation/reference diff, unchanged production reader/history/tracker contracts, relevant synthetic tests, numeric source/capture metadata, private audit, source-coverage union and cleanup/placement evidence. It returned No findings, exited zero, completed an agent response and terminal SUCCESS with a nonblank response, had empty stderr and attempted no tools. `Claude Opus 4.6 (Thinking)` remained unavailable because the preceding RE2-DOOR-001 call exhausted its individual quota, reporting a reset in 133h36m38s on 2026-10-18. That known quota failure was not retried and supplied no perspective on this snapshot. It is not an endorsement. Prompt SHA256 `01f21498f47207e43165f742eb9f92741934dc40839149db00eb214f00cb966b`; private review evidence is under `/tmp/re-map-re2-key-door-20261019/review/`. Only this provenance was appended after the reviewed snapshot. The prose review did not perform runtime validation.

## RE2-DOOR-003: one-sided unlock and savestate reversal

Status: Confirmed for the listed one-sided lock, paired passages, reentry and DuckStation restores on SLUS-00421. Other locks and full room/campaign coverage remain unverified. No tracker behavior change was needed.

Game: Resident Evil 2 USA Disc 1, Leon A, SLUS-00421, executable `SLUS_004.21`, SHA256 `1cd618bc4390db4bd60735b0db1e91534f6134ede56fae454eb580be2aa686ef`. Test emulator: DuckStation `0.1-12083-g00e299795 (dev)`; the bundle version was reread for this pass. Revision/source identity and flag contracts are in [RE2-IDENTITY-001](#re2-identity-001-leon-a-disc-identity-and-candidate-room-layout) and [RE2-SCD-001](#re2-scd-001-bounded-leon-room-metadata-and-acquisition-contracts). This extends the separate event and named-key cases in [RE2-DOOR-001](#re2-door-001-event-driven-unlock-and-savestate-reversal) and [RE2-DOOR-002](#re2-door-002-named-key-use-and-savestate-reversal).

### Pinned pair and native writer

RDT offsets below are file offsets. Runtime addresses are PS1 virtual and little-endian, never host-process addresses. Runtime source binding checks the owned source identity and relocated section pointers on every accepted capture.

| Side | Source and binding | Target | Lock fields | Clear-bit current verdict |
| --- | --- | --- | --- | --- |
| Allowed | `ROOM1090.RDT`, slot 2, `00-09:8432` | `00-16` | ID `0x90`, type `0xFE` | Unlock from this side / Unlockable |
| Denied | `ROOM1160.RDT`, slot 1, `00-16:2554` | `00-09` | ID `0x90`, type `0xFF` | Locked |

The lock fields are unsigned eight-bit values with full mask `0xFF`. Both select bank 31 bit `0x90 & 0x3F = 16`. Bank 31 begins at `0x800CCB60`, width eight bytes. This bit occupies its first unsigned 32-bit word with mask `0x00008000`. A set bit establishes fresh unlock knowledge for either side, independently of whether a departed door is currently active.

The pinned native door branch at `0x8004E07C..0x8004E0B0` handles type `0xFE` without the named-item inventory lookup. It joins the shared flag-set call at `0x8004E134..0x8004E144`, which calls `0x80072ADC`. Neither of the two decoded room sources contains a direct SCD bank 31 flag-write command. Source inspection alone would not confirm that gameplay reaches the branch.

A temporary host debugger write watch at PS1 `0x800CCB60`, width four bytes, captured the actual native write after a controller Cross interaction. The word bytes changed from `10 40 40 00` to `10 C0 40 00`, unsigned values `0x00404010` to `0x0040C010`. The only changed bit in that word was bit 16. The stop address was `0x800CCB60`, signal 5. GDB register samples were `a0 = 0x800CCB60`, `a1 = 0x10`, `s0 = 0xFE`, and `ra = pc = 0x8004E144`. These are unsigned 32-bit samples with full mask `0xFFFFFFFF`; code addresses and pointers in them are PS1 virtual. The registers bind the observed store to the one-sided door branch. `native-unlock-write.json` retains the complete numeric record. The watch was removed before coherent post-operation captures. A later native unlock repeated the result with no watch installed.

The tested emulator's [register definition](https://github.com/stenzek/duckstation/blob/00e299795/src/core/gdb_server.cpp#L39-L73) identifies PC as register 37; its [watch installation](https://github.com/stenzek/duckstation/blob/00e299795/src/core/gdb_server.cpp#L1067-L1109) uses debugger callbacks. These source checks support trace interpretation, not game validation.

The whole inventory at `0x800CCB68`, an opaque 44-byte block with full `0xFF` mask per byte, was unchanged across the native unlock, completed message, passage/reentry and repeat. The early acquisition bank at `0x800CC9E8`, width 32 bytes, was also unchanged across those checks. This is byte equality, not a new interpretation of every inventory field. The tested unlock consumed no inventory item.

### Captured outcomes and restoration

Expected behavior: Locked on the denied side, Unlockable on the allowed side, then Open/Unlocked after native operation. A departed side retains only fresh unlock knowledge and stays Unchecked. Earlier/later restores must replace access verdicts while exploration persists. The unchanged reader met these expectations.

| Capture | Observed outcome | RAM SHA256 |
| --- | --- | --- |
| `primary-denied-ready` | 00-16 current; bit 16 clear and bound door Locked, before native interaction. | `1e38c355928078d7cce40f24c417f6d83ae3eabd0cefe20cfffb45cc5b241fb0` |
| `primary-denied-message` | Native interaction produces blocked-door handling and stays in 00-16; bit remains clear and door Locked. | `7300b100eae1c832295e96fe703474fed1c7efea2472f01ada2af1a5768b73f3` |
| `primary-allowed-ready` | 00-09 current; bit clear, live descriptor type FE, bound door Unlockable. | `dca8f56a6b43381710f1a1659f19261f7185f55c8460c87209f4a0da49e3e05e` |
| `primary-native-unlock` | Watched native write sets bit 16; current door Open/Unlocked and departed counterpart Unchecked with fresh unlock knowledge. | `b76635372ed2524f4b6d56325b5447d02826363534b3eaedc888ed8d130ea410` |
| `primary-unlock-complete` | Message acknowledged in 00-09; unlock retained, inventory/acquisition unchanged. | `c745e924daf309379c2f3962a44a3f882ee08c491b111283473bc51775b00812` |
| `primary-outbound` | Native 00-09 to 00-16 passage; formerly denied counterpart now Open/Unlocked. | `ec5a55a26b70487e256c142f3345ed6a5937fad9a292fef8688e57c9eea929f3` |
| `primary-return` | Native 00-16 to 00-09 return; current allowed-side door Open/Unlocked. | `419f30a92293536e7084845c0867c1ee3398449b7403271c9fe0f1ffb6d157e0` |
| `primary-reentry` | Native 00-09 to 00-16 reentry; counterpart remains Open/Unlocked. | `1829424861b8e26f630816465ff674a94427c8a36d297e60fe3d6b336efd325e` |
| `rewind-primary-allowed` | Actual earlier allowed-side load restores Unlockable and original RAM bytes; visits retained. | `dca8f56a6b43381710f1a1659f19261f7185f55c8460c87209f4a0da49e3e05e` |
| `rewind-primary-denied` | Actual earlier denied-side load restores Locked and original RAM bytes; visits retained. | `1e38c355928078d7cce40f24c417f6d83ae3eabd0cefe20cfffb45cc5b241fb0` |
| `restore-primary-unlocked` | Actual later load restores Open/Unlocked and completed-use RAM bytes; visits retained. | `c745e924daf309379c2f3962a44a3f882ee08c491b111283473bc51775b00812` |
| `repeat-primary-allowed` | Another actual earlier load reproduces the allowed-side baseline RAM bytes. | `dca8f56a6b43381710f1a1659f19261f7185f55c8460c87209f4a0da49e3e05e` |
| `repeat-primary-unlock` | Native unlock repeated without a debugger watch; bit set, Open/Unlocked, inventory/acquisition unchanged. | `ecbde0cc0f88faa41b47a4d8b5d1b66191a9f173c0b3787d2de6d8c3aa261eff` |

The denied preparation's word was `0x00004000`; the allowed preparation's was `0x00404010`. They start from independent previously captured agent checkpoints and differ in other native progression flags. Each restore is compared with its own original baseline. They are not a single uninterrupted navigation sequence between preparations. The continuous outbound/return/reentry sequence begins after the allowed-side native unlock.

`audit.py` requires 28 accepted captures and compares every replayed publication with the original capture's map state. For the two current sources it checks exact source-offset binding, SCE ID 1, lock ID `0x90` and type FE/FF. It verifies current-side verdicts, departed-side uncertainty, retained visits, the native-writer register record, unchanged inventory/acquisition and four byte-identical restore comparisons. None of these checks assert that a source-only departed door is currently passable.

The pass has fifteen accepted sources: `01-00`, `01-0a`, `01-0b`, `00-16`, `01-04`, `01-05`, `01-07`, `00-0c`, `00-14`, `00-13`, `00-12`, `00-10`, `00-0f`, `00-0a` and `00-09`. Eight are new relative to RE2-DOOR-002's nineteen-source union, bringing the recorded union to twenty-seven. `coverage.json` derives the union from the prior accepted lists. Source acceptance is not complete item/door validation, native outline coverage or a campaign percentage.

A separate production history-file save/close/reopen retains those fifteen source visits, sixteen map-region visits and the agent playthrough identity. Restored history initially has no current room, no door observations and only Unknown item records. Fresh polls of the two earlier captures and the later capture reconstruct Unlockable, Locked and Open respectively, with the same visits. This is a file round trip over real captures, not a live runner restart. The emulator loads are independently recorded above. Memory-card persistence is not tested.

### Preparation, reproduction and rejected attempts

Private evidence is under `/tmp/re-map-re2-one-sided-20261019/`. These temporary local references are not portable public fixtures. Raw RAM, savestates, owned game data and diagnostic helpers remain outside Git. Before boot, both achievement integrations were false, cards were None, no per-game overrides were present and the existing black display shader was enabled. A private screenshot's central half had zero minimum and maximum channel values. No gameplay image was emitted. The agent history file was isolated from the user's playthrough.

The denied preparation starts from RE2-DOOR-001's `access-unlocked.sav`, SHA256 `dfd5be7bb5db71424ce99ad5800bcc897237011298ef40900c60286e2149a77c`. Native passages reach `01-0a`, `01-0b` and `00-16`. The accepted `01-0b` approach to `00-16` is X = -649, Y = 0, Z = -24332, yaw = 520, from `ROOM1160.RDT`'s return entry at file offset 2522 with reversed facing. In `00-16`, the controlled denied-side placement is X = -26159, Y = -7200, Z = -25126, yaw = 2048, floor = 4. Its height/floor and entry position come from `ROOM1090.RDT` offset 8432. One native Cross produces the denied interaction without changing bit 16.

The allowed preparation loads RE2-DOOR-002's `key-present-locked.sav`, SHA256 `e530308cd0b06eb0a9353790b9f7c3bfe9fc02f62d00c256c8c88a4dab827818`. Position-assisted native passages reach `01-05 -> 01-07 -> 00-0c -> 00-14 -> 00-13 -> 00-12 -> 00-10 -> 00-0f -> 00-0a -> 00-09`. A separate native named-key use on this route sets bit 9 and reduces that key's quantity. It is preparation, not the confirmed one-sided operation. The target bit 16 stays clear throughout. `allowed-route-approaches.json` records source entry packets used to prepare the route; actual successful interactions and failed attempts are distinguished in the captures and notes.

The accepted allowed-side stance is X = -13894, Y = 0, Z = -25290, yaw = 96, floor = 0 in `00-09`, from `ROOM1160.RDT` offset 2554 with reversed facing. Save while paused, then use native Cross/K. The watch records the first flag change. Remove it, resume and let the unlock handling finish before taking a coherent capture. A later Cross acknowledges the message, and a further Cross enters `00-16`. Its native entry is X = -26159, Y = -7200, Z = -25126, floor = 4. Face yaw 2048 there for the native return; face yaw 96 at the original first-side stance for reentry. Wait until each transition settles before accepting a capture. These are position-assisted interaction tests, not visual marker/facing alignment or uninterrupted ordinary navigation.

The agent checkpoints are `primary-allowed-locked.sav`, SHA256 `ace1efb3c8ec9b0ab3b8aabaa61bf980a1ec3425ed447e89d385323677f9a31a`; `primary-denied-locked.sav`, SHA256 `5543b1a8769a33f0eb8d6119e1d486dd23c1568bc9c2c06a63c470368a948ee4`; and `primary-allowed-unlocked.sav`, SHA256 `d53939aa01ef1e52d9bfc25c6503dac35740ec77626291b8c5cd8160bedd304d`. Restore through the isolated selected slot with native F1. The repeat restores the allowed-side baseline and performs native use/message acknowledgment without installing a watch.

Setup retains the earlier agent checkpoints' high-health and 255-round infinite-magazine assistance from RE2-LIVE-002/003. No new health/ammunition patch, enemy-state edit or acquisition/key/story/inventory write was made. Direct writes are limited to the position/facing, body-height and floor fields already recorded in RE2-DOOR-001/002. The additional upper-floor placement in `00-0c` uses Y = -3600/floor = 2 from `ROOM1140.RDT` offset 2518. `position-edits.jsonl` records every direct write, and `placement-provenance.json` identifies the source packets and rejected setup. This does not establish natural stair movement or a general Y-to-floor formula.

The initial candidate `01-02:7066` was interrupted by its native sequence, which exited through separate slot 20 with bit 15 still clear. It did not establish operation of that one-sided lock and is excluded as unlock evidence. `rejected-candidate.json` retains the five corresponding capture labels. A fresh private tracker starts the confirmed case. The provisional `denied-side-entry` was still `01-0b`, not `00-16`; its following upper-floor placement was reversed before accepted entry. Mandatory source checks were then added to the private placement commands. Later capture-client restarts seeded only listed accepted observations through the unchanged reader, without opening user history.

Enemy contact interrupted several `00-10` approach attempts and changed position/facing. Those attempts establish neither passage nor enemy kills. Native input diagnostics confirmed the configured controls; their unpaused samples were never tracker publications. The accepted exit followed stable native control at a distant entry and then a placement at X = 445, Y = -7200, Z = -22634, yaw = 0, floor = 4. Only the accepted `west-0f` capture proves the subsequent passage. These observations do not confirm the renderer's yaw conversion.

After testing, the isolated emulator was stopped and its original settings and selected test slot restored byte for byte. `cleanup.json` records both restored hashes. Other one-sided and named-key locks, other event conditions, natural conditional floors, visual heading/marker alignment and an uninterrupted ordinary-navigation route remain outside this confirmation. No normal-save or full-campaign claim is made.

Contributions:

- 2026-10-19; human user; approved the named one-sided door-unlocking increment with hidden agent gameplay and fixes for confirmed tracker mismatches.
- 2026-10-19; Codex root, exact model `gpt-6.1-sol`, verified from the matching session's current-turn metadata; inspected the pinned pair and native branch, rejected the first setup, prepared independent allowed/denied checkpoints, observed the native write through GDB, performed controller-driven unlock/passages/reentry and actual earlier/later loads, repeated without a watch, audited unchanged production publications and the separate history-file round trip; authored this entry. No production mismatch was found.
- 2026-10-19; `gpt-6.1-sol`; the 89-case focused RE2 suite, scoped Ruff lint/format checks, 238 local document links/anchors, profile claim reference and `git diff --check` passed. The private audit passed 28 required accepted captures, four byte-identical restore comparisons, native-writer register checks, unchanged inventory/acquisition, fifteen-source/sixteen-region history-file persistence and the position/floor-only guest-write check. These checks do not extend the stated gameplay scope.
- 2026-10-19; returned identifier `Gemini 3.8 Flash (High)`, conversation `a8d46881-95f9-4290-8bfa-5920efc24976`; reviewed the complete documentation/reference diff, unchanged production reader/history/tracker contracts, existing synthetic tests, private audit, numeric captures and target descriptors, agent settings, preparation/exclusion notes, source-coverage union and cleanup evidence. It returned No findings, exited zero, completed an agent response and terminal SUCCESS with a nonblank response, had empty stderr and attempted no tools. `Claude Opus 4.6 (Thinking)` remained unavailable because the preceding RE2-DOOR-001 call exhausted its individual quota, reporting a reset in 133h36m38s on 2026-10-18. That known quota failure was not retried and supplied no perspective on this snapshot. It is not an endorsement. Prompt SHA256 `335dcea787deaf32116d6d7063d43479f62819b8d7e6950325d7997d667a168e`; private review evidence is under `/tmp/re-map-re2-one-sided-20261019/review/`. Only this provenance was appended after the reviewed snapshot. The prose review did not perform runtime validation.


## RE2-PLAYER-001: native movement confirms continuous heading

Status: Confirmed for the continuous facing conversion relative to the pinned map axes, eight native forward-movement pairs in two rooms, and the listed DuckStation restores on SLUS-00421. Player-position projection, door placement and conditional floors remain unverified. No production behavior or UI change was needed.

Game: Resident Evil 2 USA Disc 1, Leon A, SLUS-00421, executable `SLUS_004.21`, SHA256 `1cd618bc4390db4bd60735b0db1e91534f6134ede56fae454eb580be2aa686ef`. Test emulator: DuckStation `0.1-12083-g00e299795 (dev)`; the bundle version was reread. The runtime signature remains `712628cd70ecee75e834248085df57ac0b22862fa8e7e486e06cc9833cae5d5a`. Source identity and pinned projection axes are in [RE2-IDENTITY-001](#re2-identity-001-leon-a-disc-identity-and-candidate-room-layout) and [RE2-MAP-001](#re2-map-001-native-leon-floor-selectors-and-numeric-contours). This changes the latter claim's former unverified continuous-heading limit, not its other candidate map findings.

### Measured direction and rendered arrow

All addresses here are PS1 virtual, little-endian. Facing at `0x800C7D9A` is an unsigned 16-bit value, width two bytes; the angle mask is `0x0FFF`. World X/Y/Z at `0x800C7D5C/0x800C7D60/0x800C7D64` are signed 32-bit fields, width four bytes each and full mask `0xFFFFFFFF`. These fields were read, never written in this pass. Stage and room at `0x800CC948/0x800CC94A` are unsigned 16-bit fields, width two bytes and full mask `0xFFFF`.

The pinned projection increases map X with world X and decreases map Y with world Z. Consequently, native forward displacement supplies an independent clockwise-from-north reference through `atan2(deltaX, deltaZ)`. Each accepted pair keeps its source, height, yaw, health and sampled player-action block unchanged while moving more than 500 world units. Collision-limited samples and the enemy-interrupted setup are excluded below. Expected behavior was agreement with the continuous conversion already recorded in RE2-MAP-001. The unchanged reader met that expectation.

| Before → after | Raw yaw | Delta X, Z | Published heading | Movement heading | Difference |
| --- | --- | --- | --- | --- | --- |
| `hall-facing-2` → `hall-walk-2` | 4208 | 1578, -287 | 99.843750° | 100.308042° | 0.464292° |
| `hall-facing-3b` → `hall-walk-3` | 5328 | -494, -1411 | 198.281250° | 199.295472° | 1.014222° |
| `hall-facing-4` → `hall-walk-4` | 6288 | -554, 119 | 282.656250° | 282.123006° | 0.533244° |
| `hall-facing-5` → `hall-walk-5` | 7248 | 65, 556 | 7.031250° | 6.667980° | 0.363270° |
| `shop2-facing-0` → `shop2-walk-0` | 779 | 204, -528 | 158.466797° | 158.875281° | 0.408484° |
| `shop2-facing-1` → `shop2-walk-1` | 1739 | -505, -260 | 242.841797° | 242.758258° | 0.083538° |
| `shop2-facing-2` → `shop2-walk-2` | 2699 | -352, 536 | 327.216797° | 326.706437° | 0.510360° |
| `shop2-facing-3` → `shop2-walk-3` | 3739 | 479, 289 | 58.623047° | 58.895727° | 0.272680° |

The first four pairs use source `01-00`; the other four use `00-01`. The raw values above one revolution confirm masking the yaw independently of its upper bits. Native Right turns increase the stored yaw and wrap the published heading through north; a separate native Left turn in `00-01` changes yaw 3739 to 2699 and heading 58.623046875° to 327.216796875°, with the same position and health. The measurements confirm the sign and offset with an observed maximum difference of 1.014222°, rounded to six decimal places. They do not establish zero-error movement physics or a universal two-degree guarantee.

[The numeric regression references](../../tests/fixtures/re2/heading-movements.json) retain these eight pairs, raw yaw, displacement, the captured published heading and both evidence hashes. The synthetic reader regression checks those published values against the independently measured movement vector with a two-degree bound. A separate fresh-yaw regression alternates the captured earlier/later angles without losing visits. The bound accommodates the observed difference; it is not a new production tolerance or an inferred heading value.

The browser regression replays the eight captured headings through the unchanged page with explicitly synthetic visits. It transforms the SVG path's actual first point, the arrow tip, into screen coordinates and compares its direction with the measured movement. This covers the glyph orientation and SVG rotation, including pose-only updates. All 133 outline and exact-door-binding browser checks also pass. It is an automated rendering replay, not another native gameplay observation. No native-camera or in-game map screenshot comparison was performed. The marker still identifies only the current room.

### Publications, restoration and evidence

Private evidence is under `/tmp/re-map-re2-facing-20261019/`. `audit.py` requires exactly 31 listed accepted publications and compares every replayed production map state with its originally recorded publication. Full paused captures use `.ram`; bounded paused production reads use `.reads.json`, recording every consumed address, width and returned bytes plus pose/health samples. The latter replay requires an exact recorded range and agreeing overlapping data, with no fallback bytes. The eight-pair reference hashes identify RAM bytes for `hall-facing-2`/`hall-walk-2`, and exact UTF-8 read-transcript bytes for the other pairs. Those private bytes and new savestates stay outside Git. Only numeric test references are committed.

Actual native F1 loads reproduce both original RAM images byte for byte:

| Baseline / loaded capture | Yaw / published heading | RAM SHA256 |
| --- | --- | --- |
| `hall-earlier` / `hall-rewind` | 4208 / 99.84375° | `725ea23cb5355f7b42b996765650ded6e4bf8387d1a1aba8733ab6d1eeee97bb` |
| `hall-later` / `hall-restore` | 7248 / 7.03125° | `6294df89d2f5166563abf5853e6c29f0f9fd6082997c7d5c39f3d6fb8437b390` |

Both loads retain the two agent source visits and replace the heading from fresh state. A separate production history-file save/close/reopen starts with no current room or heading, retains the same two visits/playthrough identity, and reconstructs earlier, later and second-room headings from fresh captures. This is an offline file round trip, not a live runner restart or memory-card persistence.

The audit also checks byte equality throughout each primary checkpoint sequence for inventory at `0x800CCB68`, width 44 bytes; early acquisition at `0x800CC9E8`, width 32 bytes; and bank 31 at `0x800CCB60`, width eight bytes. These are opaque blocks with full `0xFF` mask per byte here. Health samples at `0x800C7E7A` are signed 16-bit, width two bytes and full mask `0xFFFF`; the player-action sample at `0x800C7D24` is an opaque eight-byte block, full mask `0xFF` per byte. The eight accepted movement pairs retain health 28447 in `01-00` and 32377 in `00-01`, and action bytes `01 00 00 40 01 00 01 00`. This does not add a general interpretation of every sampled action or inventory field.

No new room source was accepted beyond the prior twenty-seven-source union. Publication, outline and test counts do not measure complete room item/door readiness or campaign progress.

### Reproduction, exclusions and cleanup

Before boot, both achievement integrations were false, cards were None, audio was muted, no per-game overrides were present and the black display shader's hash matched the earlier passes. A suppressed private screenshot's central half had zero minimum and maximum channel values. No game image was emitted. The private tracker and history file were separate from the user's exploration history. Earlier checkpoints retain the previously recorded high-health and infinite-magazine assistance from RE2-LIVE-002/003. No new patch or guest-memory write was made, including position, facing, health, ammunition, enemy, inventory, acquisition, key or story fields.

The first preparation loads RE2-LIVE-002's `ammo-both.sav`, SHA256 `89e6315c5c8138784c9a27b138e90c78d4520107d1467b2f6b79d8f7baa7e570`. Its preliminary yaw-3088 forward pair moved X/Z by 9/556 with unchanged health, agreeing within 0.4789°. A subsequent turn suffered enemy contact: health fell 32377 → 32317 and position changed. `shop-facing-1`, RAM SHA256 `de43e2818309dd675762144bcd5271faf504c9722672395e8da8140f1bfa4a05`, is excluded as turn/direction evidence. The preliminary pair is retained separately and is not one of the primary eight references. `shop-heading-earlier.sav`, SHA256 `187b7d926ded8c672baabf3d09244441f86d395fa92d736c8e11f79b747ca4d5`, is an unused preliminary checkpoint, not restore evidence.

For the primary `01-00` sequence, load RE2-DOOR-001's `access-unlocked.sav`, SHA256 `dfd5be7bb5db71424ce99ad5800bcc897237011298ef40900c60286e2149a77c`, through the isolated slot with native F1. Initial X/Y/Z are -14935/-1800/2099 and yaw 2048. Initial forward attempts at yaw 2048 and 3088 are collision-limited, with X/Z changes -1/0 and 9/0, and are excluded as directional evidence. Native Right turns and a 700 ms forward hold reach the accepted yaw-4208 start/end pair. Save the paused earlier state with native F2. Continue with native Right turns, a 700 ms forward hold at yaw 5328 and 240 ms holds at yaw 6288 and 7248. The first turn attempted after a private capture-client reconnect produced no yaw change and supplies no turn evidence; the repeated turn after explicit resume succeeded. Later client reads replay only the listed accepted publications, including the excluded-as-direction collision samples, through the unchanged reader.

Save the later state with native F2. `hall-heading-earlier.sav` has SHA256 `8b87722743255f85c608cd5ec1c0b9f0345fba23cf5405e54562715c8b26d77d`; `hall-heading-later.sav` has SHA256 `2e706d057fbf51d46c52daa242752f4a32744195e92d61db27ee564e133383d7`. Restore each through the isolated selected slot using native F1, then capture while paused. The audit checks the full RAM equalities above, not only matching angle samples.

For the independent `00-01` sequence, load RE2-LIVE-002's `shop-ready.sav`, SHA256 `e91351c6e55f6db2c87c4d0cca0a38c32197238097c0d57c69054cd696093528`. Its X/Y/Z are -16222/0/-12512 and yaw is 779. Perform four forward holds of 240 ms, separated by native Right turns of 440 ms; capture a paused source/pose before and after each. Raw yaw, rather than an assumed exact timed angle, identifies each measurement. A final Left hold of 440 ms supplies the opposite-turn check. No pickup, new passage or floor change is required for either primary sequence.

After testing, the isolated emulator was stopped and original settings and selected slot restored byte for byte. `cleanup.json` records settings SHA256 `792443989dc8f5f8ee3dabcc2a20dd71a3e61cc0a44de8a84266d51e6e889069` and slot SHA256 `995bb0ff5df6eb6b254d87ea9c6af5386105a50bfd50cdab018da50465965bfa`. Other player states, native visual alignment, player-position projection, door-marker placement, conditional floors and an uninterrupted ordinary-navigation route remain outside this confirmation. No full-campaign or normal-save claim is made.

Contributions:

- 2026-10-19; human user; approved the named facing-direction validation increment with hidden native turning/walking in two previously captured rooms, savestate reversal and fixes for confirmed heading errors.
- 2026-10-19; Codex root, exact model `gpt-6.1-sol`, verified from the matching session's current-turn metadata; prepared isolated native tests, excluded interrupted/collision-limited attempts, measured the eight primary movements, observed the opposite turn, performed actual earlier/later loads, audited full/bounded read replay and separate history-file reconstruction, added numeric reader/browser regressions and authored this entry. No production mismatch was found.
- 2026-10-19; `gpt-6.1-sol`; the 98-case focused RE2 suite, scoped Ruff lint/format checks, 245 local document links/anchors, profile claim reference and `git diff --check` passed. The RE2 browser check passed all 133 outlines, exact door bindings and eight measured headings. The private audit passed 31 accepted publication replays, eight movement pairs, committed-reference/hash equality, two byte-identical restores, unchanged inventory/acquisition/unlock blocks and separate history-file reconstruction. Cleanup hashes were verified. These checks do not extend the stated gameplay scope.
- 2026-10-19; returned identifier `Gemini 3.8 Flash (High)`, conversation `c7cb86e1-75c1-4347-9409-0c945890036f`; reviewed the complete tracked diff/new numeric fixture, reader/history/tracker contracts, affected tests, unchanged SVG/pose refresh, private capture/audit code and numeric setup, publication and cleanup evidence. It identified inconsistent rounding of the maximum difference in the prose/table. Root verified the audit value and corrected the prose to the same six-decimal rounding. The process exited zero, completed an agent response and terminal SUCCESS with a nonblank response, had empty stderr and attempted no tools. `Claude Opus 4.6 (Thinking)` remained unavailable because the preceding RE2-DOOR-001 call exhausted its individual quota, reporting a reset in 133h36m38s on 2026-10-18. That known quota failure was not retried and supplied no perspective on this snapshot. It is not an endorsement. Prompt SHA256 `0fba8560e12c481303e7aa9b904e381fa2c38b4af6bb301adf9f49614c225c6b`; private review evidence is under `/tmp/re-map-re2-facing-20261019/review/`. After the snapshot, root also strengthened the new synthetic reversal test to retain an earlier visited room, then reran all 98 focused cases and scoped Ruff checks successfully. Only that test strengthening, the verified prose correction and this provenance were added after the reviewed snapshot. The prose review did not perform runtime validation.
