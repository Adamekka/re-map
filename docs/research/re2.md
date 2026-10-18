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
