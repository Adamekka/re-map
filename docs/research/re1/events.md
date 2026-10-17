# RE1 events research

[Documentation index](../../README.md) · [Claim index](../../research.md)

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

## RE1-DIALOG-001: dialog busy and choice values explain the scripted-door guard

Status: Candidate; pinned native instruction inspection, no natural confirmation experiment
Scope: RE1 Director's Cut, NTSC-U, SLUS-00551, `SLUS_005.51` SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`; the byte-variable layout in RE1-VARS-001 and event contracts in RE1-EVENT-003
Environment: read-only owned executable/RDT inspection, Python 3.14.8 and Capstone 5.0.9; no new DuckStation gameplay
Authored: 2026-10-07; Codex root; model: GPT-6.1 Sol
Basis: primary native message helper/consumer and source-bound indexed-script inspection
Claim: PS1 virtual byte `0x800C8665`, RAM offset `0xC8665`, width one byte, contains a message busy bit `0x80` and a selectable result in bit `0x01`. The five delegated scripts in RE1-DOORS-005 wait for this byte to fall below `0x80` and then test zero before calling the ordinary door callback. Zero describes a selectable confirmation result, not a story flag or a door unlock.

Evidence:

- SCD `0B` at `0x800452F4..0x80045348` calls message helper `0x80035278..0x8003538C` and returns one regardless of that helper's result. The helper returns early while the byte's `0x80` bit is already set. Otherwise it writes `0x80`, selects the text source, stores control fields and masks/saves the `0x800CAB00` halfword. It does not request a room transition.
- Message input at `0x80035B14..0x80035B44` toggles bit 0 with XOR one. Completion at `0x80035AE4..0x80035B08` clears bit `0x80` and restores the saved control halfword. The timed completion path at `0x80035D00..0x80035D58` also clears the busy bit. Result selection at `0x80035D80..0x80035DB8` explicitly uses bit 0. The two low-bit possibilities are therefore user choices under this native contract.
- The inspected delegated entries issue SCD `0B` with prompt control bit `0x80`, establish an FC deferred predicate `06 05 02 80`, yield and use FD to repeat it. Comparison type 2 means greater than or equal under RE1-SCD-007; the initialized FC/FD frame contract is RE1-EVENT-003. After the wait exits, a full SCD procedure tests `06 05 00 00` and invokes callback 1 on the same door slot. The wrapper's source length must contain its complete dispatched operands.
- The dialog consumer's token `0A` can invoke one of four valid callbacks from the table at `0x8008EE1C`: `0x80034340`, `0x80034394`, `0x800344E4`, `0x8003455C`. Their direct bodies handle acquisition, inventory consumption/removal and a no-op. They contain no ordinary door callback or passage-request write. This inspection does not make message effects a general no-op in the tracking engine.

Limits: source inspection does not reproduce prompt timing, normal accept/decline, scripted passage, character changes or save/load in the affected rooms. An earlier busy message can suppress a new prompt; the implemented rule describes the route available through a fresh normal interaction, not the event's current PC or proof of completed execution. Arbitrary message bytecode, malformed callback indices, other revisions and unrelated predicates remain outside this claim. RE1-DOORS-006 identifies private excerpts and hashes; no executable or message bytes are committed.
History:

- 2026-10-07; Codex root, GPT-6.1 Sol; inspected the complete message helper, busy-bit completion, choice toggle/selection, valid callback table and the five source-bound FC/FD confirmation routes. Kept the native claim Candidate pending natural gameplay validation.

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

## RE1-EVENT-018: out-of-section event tails reach the native state-0 disable

Status: Candidate; static disc-byte tail decode plus pinned-executable instruction checks, no gameplay
Scope: Resident Evil Director's Cut USA SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`; the nine `leaves section` event failures in `ROOM10C0/60C0`, `ROOM10C1/60C1`, `ROOM10F0/60F0`, `ROOM3060/3061`, and `ROOM7060`
Environment: owned MODE2/2352 disc read with `tools/extract_psx_file.py` to scratch paths outside Git, repo `scan_event_program` reproduction, Capstone 5.0.7 MIPS disassembly of `/private/tmp/re-map-slus00551.exe` (SHA256 matches the pinned revision); Python 3.14.8, no emulator boot, gameplay, or memory writes
Authored: 2026-10-09; agent/tool: opencode; model: opencode/muse-spark-1.3-contributor-free
Basis: direct RDT byte inspection, repo scanner reproduction, and primary instruction inspection
Claim: all nine out-of-section event tails have the same shape, and the first byte past each section end decodes to the native state-0 default, which disables the event. If these entries execute to the section end in-game, the next tick disables the event rather than running an unknown payload. This is a benign-tail hypothesis, not authorization to trust out-of-section bytes: production rules and coverage are unchanged.
Evidence:
- Replaying the committed `scan_event_program` over the nine extracted RDTs reproduces one `leaves section` failure each: entry 3 at `0x32c48`/`0x32c44` (`ROOM10C0/60C0`, `ROOM10C1/60C1`), entry 17 at `0x31f1c` (`ROOM10F0/60F0`), entry 7 at `0xa2e8` (`ROOM3060/3061`), entry 11 at `0x38024` (`ROOM7060`). In eight cases the last in-section opcode is state-1 `0x80`, which returns to state 0; in `ROOM7060` it is state-0 `0x00`, which advances. The first byte past the section end is `0x64` in all nine files. In state 0 the audited width tables contain no `0x64` entry and `0x64 >= 10`, so it takes the native state-0 default path.
- The state-0 default at PS1 VA `0x80026214..0x80026218` stores zero to event-record byte 2 (the active byte) in its delay slot and jumps to the shared epilogue: `j 0x800262b0` with `sb $zero, 2($a1)`. This matches the existing scanner comment that the state-0 default disables the event. Instruction file offsets in the pinned PS-X executable are `0x800 + (VA - 0x80010000)`; event offsets in the preceding bullet are RDT file offsets. The later recount below binds the private RDTs to their committed source hashes.
- The state-1 `0x07` case behind the `ROOM1060/6060` nonadvancing-path failures was checked in the same disassembly pass: the state-1 dispatch chain sends every value below `0x80` except `0x00` to the default jump at `0x80026324`, which reaches `jr $ra` at `0x80026a8c` with no PC store. The existing `unsupported` treatment stands; no decoder width was missed.
- Independent recount: each of the nine private RDTs matches its `source_sha256` in the committed room manifest. The scanner reproduces the named entry and section end, the final in-section state/opcode and the first trailing byte in every case. Private numeric report `/tmp/tasks/re-map/muse-followup-review/event-tail-evidence.json`, SHA256 `2c67ab7fe196dc11df6d3dac25b6a22252cf59a83c27c3c4e4b992f622c888b0`. The following hashes identify the inspected files; the RDTs remain outside Git.

| RDT filename | SHA256 |
| --- | --- |
| `ROOM10C0`, `ROOM60C0` | `a8f8312dabea201cf5fa11f29457958fb7c1bf59fc066888e732138d8e36a0ee` |
| `ROOM10C1`, `ROOM60C1` | `9ddf4896824b1acf20b26cb319c06cf5ebaa7fc5cd2922e9baf0061ed2f44c8d` |
| `ROOM10F0` | `3f95e915fa5745133f697510c7e462453b1b42c471f26699bbcdf80000ba987e` |
| `ROOM60F0` | `f426085395b2520b38a08f67198f37f573430823970010df7721936158450bc6` |
| `ROOM3060` | `9bc8ce7e6b6d50f8ada64b86c66fac0503e4e4cda4fbd713f5bac1c1354b142b` |
| `ROOM3061` | `768d326255482220279cdb4c28d192d65e9465d705d18fcffba559d835a6dfc9` |
| `ROOM7060` | `964e0d63797fc479e9ab9f9911ef1c3ef6c755dc84c4375f30f1642d8946aee6` |

Limits: the tail decode assumes the file bytes following each event section are the bytes the VM would read in RAM. Whole-section RAM/disc equality is established for tested rooms in RE1-COVER-001 and RE1-SOURCE-002, but no RAM capture of these nine rooms was inspected, so trailing-byte contiguity in RAM is unverified. None of the nine entries was observed activating in gameplay, so the benign tail does not prove these events are harmless in ordinary play and grants no coverage, clearance, or production rule change. Other revisions need their own checks. The audit script is scratch at `/tmp/re-map-review/tail_audit.py`, outside Git.
History:
- 2026-10-09; opencode with model opencode/muse-spark-1.3-contributor-free; extracted the nine RDTs read-only to scratch, reproduced all nine failures with the repo scanner, tail-decoded each exit path, and verified the state-0 disable and state-1 default instructions in the pinned executable. No production code changed.
- 2026-10-09; Codex root, GPT-6.1 Sol; independently matched the nine extracted files to manifest hashes, reproduced all nine scanner failures and tail states, and rechecked the state-0 disable and state-1 default instructions in the pinned executable. Added missing file hashes and distinguished PS1 virtual instruction addresses, executable file offsets and RDT file offsets. No live activation or RAM-tail check was performed; the finding remains Candidate.
- 2026-10-10; Codex root, gpt-6.1-sol; restored the unchanged preceding contribution to RE1-EVENT-018 after the new lifecycle entries had displaced it into RE1-LIFECYCLE-003 history. This corrects attribution only and adds no event evidence.
