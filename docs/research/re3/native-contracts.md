# RE3 native room and lifecycle candidates

[RE3 scope](../../re3.md) · [Disc identity](identity.md) · [Room sources](room-format.md) · [Runtime baseline](runtime.md)

Target: Resident Evil 3: Nemesis, PlayStation, USA, SLUS-00923, executable `SLUS_009.23`, SHA256 `2e143418e358b2c99995cdc1a88c387163fb751912c723b755614f38e236bd29`. Hard remains the human-selected target. Claims 001 through 003, 005 and 006 are Candidate contracts. Claim 004 adds confirmed observations of specific menu/pause boundaries. The audit reads the owned executable/disc and retained RAM; it does not operate an emulator. Claims 001 through 005 use captures from DuckStation `0.1-12083-g00e299795`, as recorded in RE3-RUNTIME-001. Claim 006 records a separate native episode on `0.1-12640-gbb4e9ac5e`.

The immediate tracking failure is admission: plausible player fields already appear without controller input. A tracker needs fresh room/source agreement and an independently established campaign lifecycle before it can record visits. This audit supplies source witnesses and rejection evidence, while always reporting `campaign_admission` and `hard_identity` as `unresolved`.

## RE3-NATIVE-001: native selectors agree with owned room sources

Status: Candidate. Native table agreement and retained-source matching do not establish a campaign visit.

Every address in this table is a PS1 virtual address. Subtract `0x80000000` for its offset in a captured 2 MiB main-RAM image. None is a host-process address.

| Candidate field | PS1 virtual address | Width, byte order and mask | Interpretation used by the audit |
| --- | --- | --- | --- |
| Stage / room / camera | `0x800D1F76` / `0x800D1F78` / `0x800D1F7A` | Signed i16 LE each, full `0xFFFF` | Raw selectors; stage indexes native tables from zero |
| Loaded RDT base | `0x800CC86C` | u32 LE, `0xFFFFFFFF` | Candidate cached-main-RAM pointer |
| RDT allocation base | `0x800CC870` | u32 LE, `0xFFFFFFFF` | Must agree with loaded base; allocation extent remains unestablished |
| Stage-table roots | `0x8009DFD0 + 4*stage` | Seven u32 LE pointers, `0xFFFFFFFF` | Select per-stage u16 file-index table |
| Room file index | Stage-table pointer plus `2*room` | u16 LE, `0xFFFF` | Index in native file metadata |
| Native file metadata | `0x800946A4 + 8*index` | Two u32 LE words, each masked `0x00FFFFFF` | Source byte length and ISO LBA; high bytes are not interpreted |

The room loader at virtual `0x800493EC` reads signed stage/room selectors and the allocation base. At `0x80049448` it publishes that base as the loaded RDT pointer. Its selector sequence at `[0x8004960C, 0x80049638)` has SHA256 `15dedaade71b6c5d29d31cfa59a3576ed191ba179967cc9fba1eebc46bce9990`. The camera selector indexes 32-byte records, for example at `0x800229E4..0x80022A00`. These references are locations in the pinned owned executable, not claims generalized to other revisions.

Independent checks matched the native length/LBA pair to all 169 cataloged ARD files. Native stage zero corresponds to filename stage one. The seven root pointers are `0x8009DE30`, `0x8009DE80`, `0x8009DEBC`, `0x8009DEF0`, `0x8009DF24`, `0x8009DF48` and `0x8009DF94`. This supplies the previously missing candidate source-selector encoding without borrowing RE1/RE2 addresses.

Source matching requires a word-aligned cached-main-RAM base and the complete source extent inside the capture. It compares source prefix bytes 1 through 7, relocated header words 0 through 20, every camera record and the complete bounded camera-zone section. The camera selector must be inside the source camera count. Zero or multiple matches remain explicit rejection evidence, as do disagreement with the selected source or allocation base.

At `[0x8004963C, 0x800496A8)`, SHA256 `1cdf145a57861df885d1f1bc23909c52c489904fff9136413b1b0d289f9fef21`, native initialization adds the base to every nonzero header word before file byte `0x60`. This includes opaque slot 2. It then adds the base to each camera mask word even when the source value is zero. Source prefix byte 0 and header slot 21 become runtime work fields and are excluded from the witness. The shared section-bound implementation still excludes slot 2 from pointer ordering, as established by RE3-ROOM-002.

Initializer bytes change in retained captures. The audit reports their different-byte count and size; it does not silently mask them, demand immutable script operands or interpret command execution. Matching header/camera/zone witnesses is not a proof of every mutable room field or a complete allocation boundary.

## RE3-NATIVE-002: recorded input rejects plausible player states

Status: Candidate. Rejected hypothesis: a matching room source and plausible pose establish controllable campaign gameplay.

| Candidate field | PS1 virtual address | Width, byte order and mask | Audit use |
| --- | --- | --- | --- |
| Lifecycle word | `0x800CC858` | u32 LE, full `0xFFFFFFFF`; inspected bit `0x10000000` | Bit selects the recorded-input initialization path |
| Recorded-input phase | `0x800C79AE` | u8, endian n/a, `0xFF` | Raw diagnostic value only |
| Recorded-input index | `0x800C79B0` | u32 LE, `0xFFFFFFFF` | Raw diagnostic value only |

The native initializer tests `0x10000000` at `0x800246C4..0x800246D8` and calls `0x80024B34`. That function copies 0x708 bytes from the selected recorded-input source into game state, then supplies pose and other player fields from following source bytes. Its interval `[0x80024B34, 0x80024C50)` has SHA256 `4188cf1243611453395d8e30a74892eb00a8225de76431ee7b59ede318702234`.

The owned `CD_DATA/BIN/TITLE.BIN` overlay contains the complementary setup at candidate virtual `0x801967B8..0x801967DC`, clearing the phase/index and setting that lifecycle bit. Its candidate load base is `0x80194000`, matching the retained disassembly. The overlay is 14248 bytes, SHA256 `b7807319bc0a26339d925c3a260de22df6c2d4144b0dfa5346b9fa062e6924cd`. Its first 128 bytes match uniquely at `0x80194000` in both `current-phase` and `after-cardless-choice`; the full mutable image does not match. Rejected: the earlier note's `0x80190000` base, which displaced these code locations. No patch or overlay is installed by the audit. The main-executable path and retained counterexamples supply the rejection evidence; this is not a fully interpreted title/campaign state machine.

| Retained capture label | Stage / room / camera | Unique loaded source | Lifecycle word | Rejection evidence |
| --- | --- | --- | --- | --- |
| `initial-no-input` | 0 / 0 / 0 | None | `0x00000000` | No valid loaded base or unique source |
| `no-input-later` | 0 / 3 / 6 | `STAGE1/R103.ARD` | `0x38000000` | Recorded-input bit set |
| `difficulty-selection` | 0 / 32 / 11 | `STAGE1/R120.ARD` | `0x1C000000` | Recorded-input bit set |
| `current-phase` | 0 / 0 / 0 | `STAGE2/R20B.ARD` | `0x00000000` | Selectors disagree with loaded source |
| `after-cardless-choice` | 0 / 3 / 0 | None | `0x30000000` | Recorded-input bit set; no valid loaded base |
| `post-menu-attempt` | 0 / 32 / 12 | `STAGE1/R120.ARD` | `0x1C000000` | Recorded-input bit set |

These are the original private filenames, including the misleading `difficulty-selection` label already corrected in RE3-RUNTIME-002. None proves a selected difficulty or player control. The mismatched `current-phase` capture also demonstrates why reading selectors alone cannot identify a loaded room. A clear recorded-input bit supplies no positive admission rule: every output still reports campaign admission as unresolved.

## RE3-NATIVE-003: raw mode words cannot identify Hard

Status: Candidate field leads. These raw words have no confirmed difficulty interpretation.

This describes the original offline audit's limit. Later [RE3-INPUT-002/003](hard-start.md#re3-input-002-native-hard-selection-and-control-in-two-rooms) verify native Hard selection/control and a separate title-written difficulty bit. The two raw words below remain uninterpreted; audit outputs still refuse campaign or Hard admission.

| Candidate field label | PS1 virtual address | Width, byte order and mask | Limit |
| --- | --- | --- | --- |
| Saved status word | `0x800D1F2C` | u32 LE, `0xFFFFFFFF` | Raw diagnostics; no campaign/difficulty interpretation |
| New-game option word | `0x800D1F30` | u32 LE, full `0xFFFFFFFF`; exported low-bit view uses `0x00000001` | Raw option lead; neither bit value is mapped to Hard |

The owned `INIT_TBL.DAT` and `INIT_SUB.DAT` are each 2312 bytes. Their SHA256 hashes are `821da14c1716e00256d2556f43942f19c6e9176d43d5fba74a8aa1e24745996f` and `e8817cdcfb34436a6c822de406a82d28bd9b774efe6a7abe44f70a63d862bcbe`. They give initialization leads, not a verified runtime selector. All six retained captures have zero at the proposed option word. The saved status word is zero except `post-menu-attempt`, which has `0x140`. Treating these values as proof of Hard would repeat the original no-input admission error.

## RE3-NATIVE-004: native menus and Start pause preserve plausible player states

Status: Confirmed for the named revision's observed Circle/L2 interface entries and Start pause/reversal. The fields provide explicit rejection evidence. A general positive campaign/control gate remains unresolved.

The tracking failure under investigation is false admission while native gameplay updates are blocked. The [two-room Hard control experiment](hard-start.md#re3-input-002-native-hard-selection-and-control-in-two-rooms) supplied positive examples. A follow-up retained the same valid room, position, health, player routine and clear recorded-input/difficulty bits while native interfaces or Start pause blocked deliberate turning. Rejecting only recorded playback, invalid sources or nonzero saved-status words would miss some of these cases.

| Field | PS1 virtual address | Width, byte order and mask | Audit behavior |
| --- | --- | --- | --- |
| Native interface loop active | `0x800E01E7` | u8, endian n/a, full `0xFF` | Any nonzero value adds `native-menu-loop-active` |
| Native interface view | `0x800E01D0` | u8, endian n/a, full `0xFF` | Raw diagnostics only; retained after dismissal |
| Native world-update pause | `0x800D4434` | u8, endian n/a, full `0xFF` | Any nonzero value adds `native-world-update-paused` |

These are main-RAM virtual addresses, not host pointers. The source-bound native interface routine at `0x8006DFDC` uses a work structure based at `0x800E01C0`. It reads byte `+0x27` before entering and after each iteration of its interface loop, continuing while nonzero. The view byte at `+0x10` selects callbacks. Interval `[0x8006DFDC, 0x8006E0A4)` has SHA256 `9589883de539fa71a0821c54f58d11ab7aa90a7fb33544256ad5821a469a8ddd` in the pinned owned executable.

The native world loop reads `0x800D4434` at `0x800232A0` and skips its normal update body when nonzero. Interval `[0x800232A0, 0x800232B4)` has SHA256 `a1737f2f7e6bb6a18224305061e9480c339c53e06de60450eb388bece150d25e`. The Start edge mask `0x0800` sets this byte to 2 at `0x80029144..0x80029184`; another Start edge clears it at `0x800291E8..0x80029218`. The containing interval `[0x80029134, 0x8002921C)` has SHA256 `cfaf357b5e5f074887e34672dea40172fc82b606da363a7ecba5d3ed16ba245b`. Source also contains a value-1 controller-disconnection path; that situation was not exercised at runtime.

### Native observations

The follow-up used a new private portable instance under `/var/folders/9d/q5n746z953bcs654g_1sqcy80000gn/T/re-map-re3-lifecycle-20261105-1xr0gz_3/`, port 2356. Before its initial private checkpoint load, achievements were disabled in both sections, accounts/overrides were absent, `ApplyGameSettings=false`, cards were `None`, audio was muted and the black shader was enabled. Settings remained byte-identical through cleanup. The checksum-verified input was `hard-second-moved.sav` from RE3-INPUT-002. Its source hash and exact command are in the manifest. No user history, game-file edit, patch, forced guest state or guest-memory write was used.

Native toggle bindings were explicit: F11 Cross, F12 Start, F13 Triangle, F14 Circle, F15 L2 and F16 Right. The persistent GDB client paused between bounded execution intervals. New checkpoint completion and four-window RAM identity used the same checks as RE3-INPUT-002. One L2 capture attempt encountered an in-progress native write with the slot temporarily absent; it failed explicitly and was accepted only after the complete newer file appeared. The first launch attempt exited before a debugger connection, leaving an empty log. Its manifest/log are preserved; all accepted observations came from the later owned process held by a waiting launch wrapper.

Every row below has stage/room/camera `0 / 1 / 10`, position `-4842 / -1800 / -11028`, health 200 and the same unique `R101.ARD` source witness from RE3-INPUT-002. Position/facing addresses and widths are defined there. The player routine bytes at PS1 virtual `0x800CCBC8` and `0x800CCBC9`, u8 each with full `0xFF`, are `[1, 0]` in the blocked interface/pause checkpoints and `[1, 4]` in the two resumed-turn checkpoints. The recorded-input bit stays clear.

| Private checkpoint | Lifecycle word | Saved status word | Interface active / view | Pause | Raw facing | Observation |
| --- | --- | --- | --- | ---: | ---: | --- |
| `triangle-attempt` | `0x28001000` | `0x000` | 0 / 0 | 0 | 3328 | Initial control context; Triangle alone did not establish an interface |
| `circle-menu` | `0x29001000` | `0x300` | 1 / 2 | 0 | 3328 | Circle entered the native interface loop |
| `circle-menu-right` | `0x29001000` | `0x300` | 1 / 2 | 0 | 3328 | Right reached native input but did not turn the player |
| `circle-dismissed-control` | `0x28001000` | `0x000` | 0 / 13 | 0 | 3888 | Triangle dismissed the interface; Right then turned the player |
| `l2-menu-settled` | `0x29001000` | `0x300` | 1 / 5 | 0 | 3888 | Independent L2 entry; Right again left facing unchanged |
| `start-right-attempt` | `0x28001000` | `0x000` | 0 / 13 | 2 | 3888 | After interface dismissal, Start blocked turning despite clear menu/status fields |
| `start-dismissed-control` | `0x28001000` | `0x000` | 0 / 13 | 0 | 4448 | A second Start restored turning while Right remained held |

For the blocked Start sample, the native checkpoint controller independently retains pressed mask `0x0020`, Right. The live input word also reports Right. Thus missing controller delivery does not explain unchanged facing. The raw facing value can exceed 4095; this experiment does not establish a map-facing conversion.

Rejected: a matching room/source and plausible actor fields prove control. Rejected: a clear recorded-input bit plus zero saved-status word proves control, as Start pause retains both. Rejected: a nonzero interface view means the interface is active, as view 13 remains after dismissal. The audit uses the active byte and pause byte separately, preserves raw view values and source matches, and always leaves `campaign_admission` and `hard_identity` unresolved. It does not infer control from the absence of these rejection reasons.

### Reproduction and private evidence

Load the verified Hard checkpoint only after fresh isolation checks. Enter the native interface with Circle, deliver Right and check unchanged player facing, dismiss with Triangle, then deliver Right and observe changed facing. Repeat entry with L2. After dismissal, press Start, deliver Right, retain the complete native state and verify pause byte 2 with unchanged facing. Press Start again while Right remains held and check pause byte 0 plus changed facing. Capture full RAM through native states, audit each source independently, and retain requested inputs separately from observed outcomes.

The retained `prepare.py`, `re-map-re3-lifecycle-launch.py`, `re-map-re3-lifecycle-control.py`, `re-map-re3-lifecycle-ocr.py` and `re-map-re3-lifecycle-verify.py` describe this exact temporary instance. The verifier checks all eight captures, source identity, expected independent rejection reasons, facing differences and native code hashes. Two audit runs produce identical JSON. Temporary paths must be updated for a new instance; retained RAM/saves/images and owned code remain private.

| Private evidence | Bytes | SHA256 |
| --- | ---: | --- |
| `settings-preboot.ini` | 2130 | `851e05a6ba86f2a1c274df84dcb2f5f1743209d8edc6e43d3e1a028e9463d95f` |
| `controller.jsonl` | 16408 | `0f4a72b358c3bbe0dae515c2f20ed516b44f88451a9f7c8457e532414f1928df` |
| `final-source-audit.json` | 12490 | `53c889e32c375530be44176c439017e7da09dbebc61f0a223f6d85f95abed0cb` |
| `verification.json` | 9588 | `f1201ca4093b606613a3ca375cbbd2d2eaa8a27b5744f86247b01cc3f83cdb2f` |
| `circle-menu.sav` | 1777284 | `b57d98410c594152496bcad9b849ad46f78602c29c73bcb49e1d45938925f7f8` |
| `l2-menu-settled.sav` | 1653804 | `7a0321baec42aef6aca92f1081933b5f4d436c7f04d943e4e280d8b6f1510d15` |
| `start-right-attempt.sav` | 1861552 | `11c979a37a48f2234200e18a5ca01f8fedc439f7136482e8a9cbe722fb670b58` |
| `start-dismissed-control.sav` | 1934511 | `9f809e6d48c540e7ec1ee2cbdd17d152d50794d4b7287ce5b09b7e2349b471c5` |
| `cleanup.json` | 342 | `6c84564a82519d82d5a43e7c640314a56ef4cb4196fafe47113699ad4116fc12` |

Cleanup verified PID 84283's exact command and port ownership, closed the GDB client, stopped that process only, confirmed its launch wrapper exited successfully and verified port 2356 free. The initial failed PID was already absent. General startup/loading/cutscene admission, ordinary room reentry, allocation extent, acquisition/story/door interpretation and map projection remain unresolved. This experiment did not perform new memory-card operations or validate a runtime profile.

## RE3-NATIVE-005: the normal player handler can retain filtered movement input

Status: Candidate additional rejection for the named revision. A sufficient positive campaign-admission rule remains unresolved.

The diagnostic gap was a startup state with a unique loaded source, world-loop set, normal primary routine 1, clear recorded-input/menu/pause fields and clear examined actor-update masks. The original audit reported no rejection reasons. A later native checkpoint retained raw Right while logical movement Right was filtered to zero, showing that these earlier candidate gates do not establish movement control.

| Field | PS1 virtual address | Width, byte order and mask |
| --- | --- | --- |
| Native control word | `0x800CCBA0` | u32 LE, full `0xFFFFFFFF`; movement filter `0x01000000`; update gate `0x80000000` was clear |
| Raw held input | `0x800CC830` | u32 LE, full `0xFFFFFFFF`; observed Right `0x00002000` |
| Logical held input | `0x800CC83C` | u32 LE, full `0xFFFFFFFF`; Right `0x00000002`; filter retains `0x00003000` |
| Primary/secondary routine | `0x800CCBC8` / `0x800CCBC9` | u8 each, full `0xFF` |
| Actor flags | `0x800CCC0A` | u16 LE, full `0xFFFF`; inspected gate `0x8000` was clear |

At `[0x80038468, 0x80038490)`, SHA256 `831b9b342424f7ac98d1c8ad45c6828f49ff3206509e827b5be86550e1fd9ad9`, native code tests the control mask and replaces logical held input with `held & 0x3000`. This removes movement Right `0x2`; it does not disable every input. Normal handler `0x80039020` reads logical held/edge at `0x80039044`/`0x8003904C` before secondary dispatch. Source inspection alone does not establish when the filter is active.

### Native comparison and limits

The private DuckStation instance used the verified Hard confirmation and settled-control checkpoints from [RE3-INPUT-002](hard-start.md#re3-input-002-native-hard-selection-and-control-in-two-rooms). Before game/state loads, achievements were disabled in both settings namespaces, game overrides disabled, and private resources/cards isolated. Gameplay stayed hidden and muted. No guest-memory writes, patches, new progression or user-history access occurred.

A host-side execute breakpoint caught the first observed normal-handler entry. The completed native checkpoint retains MIPS register contents `PC=0x80039020`, `A0=0x800CCBC4`, `RA=0x80038D34`: A0 identifies the player object, RA the dispatcher return. Its PC and complete RAM match the live stopped capture; A0/RA are decoded from the native CPU payload, not separately retained live-register telemetry. These are register values, not RAM offsets. Target code remained unchanged. Restoring the checkpoint reproduced all 2 MiB before matched input trials.

| Observation | Control word | Raw held | Logical held | Facing u16 |
| --- | --- | --- | --- | ---: |
| First normal-handler entry | `0x01000000` | `0` | `0` | 1824 |
| Startup Right, 100 ms | `0x01000000` | `0` | `0` | 1824 |
| Startup Right, 600 ms plus about 20 ms to next handler | `0x01000000` | `0x2000` | `0` | 1824 |
| Settled no-input, 600 ms | `0` | `0` | `0` | 2048 |
| Settled Right, 100 ms | `0` | `0x2000` | `0x2` | 2208 |
| Settled Right, 600 ms | `0` | `0x2000` | `0x2` | 3408 |

Position stayed unchanged within each restored comparison. Settled Right selected secondary routine 4; release restored routine 0 and logical zero without changing final facing. The startup next-handler checkpoint again has the same PC/A0/RA, world-loop set, primary 1, both update masks clear, and recorded/menu/pause clear.

Fresh native version-87 checkpoints show controller pressed mask `0x20` alone during Right trials and zero after release. This serialized controller mask differs from the game's raw `0x2000` and logical `0x2`. The 100 ms startup observation is inconclusive by itself because raw input had not updated. The later raw-Right/filtered-logical witness supports this rejection. A failed input method and the rejected assumption that every startup raw-held value stayed zero remain preserved in `failed-input-attempt.json` and `verification-failures.json`.

CPU payload decoding follows pinned [CPU::DoState ordering](https://github.com/stenzek/duckstation/blob/00e2997958d62de79d352cd680ec0c1ad95d491c/src/core/cpu_core.cpp#L241) and the [34-register enum](https://github.com/stenzek/duckstation/blob/00e2997958d62de79d352cd680ec0c1ad95d491c/src/core/cpu_types.h#L28). The root independently decoded both key checkpoint register/controller fields and compared their RAM byte-for-byte with direct captures. An independent internal checker decoded all nine native states, checked eleven captures' critical code against the executable, verified both full-RAM restores and all 67 manifest files, and checked private settings/isolation.

Intervals are host-timed, including resume/interrupt overhead, not frame-exact. Only one previously observed room was sampled across startup and settled camera/lifecycle situations. Absence of this filter does not establish readiness. Deferred-update lead `0x800CC858 & 0x200` remains unconfirmed; reentry, item/door/story outcomes, card persistence and other revisions remain untested.

### Audit behavior and evidence

The audit adds three raw diagnostics: `native_control_word_u32`, `raw_held_input_u32`, `logical_held_input_u32`. Control mask `0x01000000` adds `native-logical-movement-input-filtered`, independently of recorded input, menus, pause or source agreement. Raw/logical disagreement alone adds no reason, and surviving non-movement bits `0x3000` do not cancel rejection. Both admission fields stay unresolved; no runtime profile, history or UI changes.

Parent integration reran the real CLI against all 169 owned sources and eleven direct captures: six startup captures gain the reason, five settled captures do not. Removing only the new diagnostics and reason reproduces every earlier audit field exactly. The normal-handler regression failed before the change with an empty reason list. Nine new synthetic cases cover exact masks, independent causes, surviving input, raw/logical mismatch, input preservation and earlier-state reversal.

Experiment evidence is under `/var/folders/9d/q5n746z953bcs654g_1sqcy80000gn/T/re-map-re3-first-handler-20261106-oaof6f__/`; parent evidence is under `/tmp/re-map-re3-input-filter-integration-20261106-SLTIyv/`. Parent verifiers require explicit inputs and fresh output paths. The original experiment verifier rewrites reports: copy/adapt it before rerunning. Its wrapper-exit-zero field is an agent-recorded observation, not independently derived exit telemetry. Independent checks establish PID 64490 absent and port 2360 free; the parent also verified it bindable. Breakpoints were removed, Right released, settings stayed byte-identical and CUA ended.

| Evidence | Bytes | SHA256 |
| --- | ---: | --- |
| Experiment `report.json` | 35393 | `b62734978a7c4e90ec1b7eb1d3572e660962d774d34c0b8a2826e60d203175c6` |
| Experiment `artifact-manifest.json` | 9926 | `2764d2d3a2abf55ac7b40e2dcfe6aca80bba8ac5f6036d359000d8bdf4fd9a1e` |
| Parent `verify.py` | 4952 | `38ac94de4a53e8e2e186255375f2456546e722c3072ed801ea51854cbe95ffd6` |
| Parent `verification.json` | 2687 | `1b1d507eec81b077382432907fcde672bd1b9ead719fe8cc0b2af992470d5ae2` |
| Parent `audit.json` | 18491 | `1bfc39981ed4f2745aea350d7cd73e7826ebfcb25c310ac14c4df0c12229160c` |
| Parent `verify-native-checkpoints.py` | 2398 | `41749ea88be50d83279200b3095f30a6f35dd4e8884351e27157bab0898038af` |
| Parent `native-checkpoints.json` | 666 | `34915b9f3ddef3f9489c8911d50bf4f4ac1c77039eef88ec997f7abc65193d60` |

## RE3-NATIVE-006: a restored seed reaches source-bound world and native exit

Status: Candidate lifecycle contract for the named revision. One bounded native episode supplies exact checkpoint/RAM comparisons and an observed original writer/consumer chain. It does not establish a general campaign-admission rule.

The gap was a completed post-Hard/pre-world seed without a completed source-bound checkpoint, plus an earlier exit-request interval whose writer was unobserved. On 2026-11-12 UTC, one stock restoration let the original engine initialize R10D, clear its movement-input filter and later execute the current-value outcome/exit path. No game buttons were delivered. This episode adds no deliberate turning or translation observation; the earlier [Hard controls](hard-start.md#re3-input-002-native-hard-selection-and-control-in-two-rooms) and [filter-clear evidence](hard-start.md#re3-input-007-original-code-clears-the-startup-input-filter) retain their own provenance.

The actual log identifies DuckStation `0.1-12640-gbb4e9ac5e`, source commit `bb4e9ac5e6b3872126dc76f1fe4f46169c96b082`, native state version 94. Installed and private binary SHA256 is `ddceaaa426e67e328430fcb916320803fddc014374ea45a00778e58081f36dcb`. PID 4556 first booted BIOS with private argv `-nofullscreen -bios`; its settings and port 2401 ownership were checked before loading the exact private seed. Both Achievements/Cheevos namespaces disabled Enabled, ChallengeMode and UseRAIntegration. Cards were `None`, game overrides disabled, credentials absent, gameplay hidden and audio muted. No patches, guest-memory/register writes or user-save/history access occurred. Private settings later gained only four UI window-geometry keys; every prelaunch setting remained intact.

### Checkpoint creation and exact restoration boundary

The stock seed was `hard-startup-current/state.sav` from the frozen fresh-admission episode. Save SHA256 `9fd59cebaa32a0c007663d4437a481d067f83fac2863be760515d3366e93cc56` and serialized RAM SHA256 `9d880e76f431a6bd946785c602b65f2f0b17fd6760ac94de3a2196229289ca0a` match the one restored full 2 MiB stopped capture exactly. Its source/allocation pointers and actor fields were zero. It was a post-Hard/pre-world seed, not an already source-bound R10D state.

| New private native checkpoint | Save SHA256 | Serialized/direct RAM SHA256 | Stopped observation |
| --- | --- | --- | --- |
| `checkpoints/first-source-bound-filtered/state.sav` | `28e059a0202e8fbed456d6c3abd6991dc36a026b727764fa3aaded25bf27ce23` | `64edcde7f57c8ee4b7e9050d02a4279105c2f1ba3a8c1aed0648fcebf8e327a3` | R10D; current/ceiling 200/200; control `0x01000000`; NonGameplay |
| `checkpoints/source-bound-unfiltered/state.sav` | `4ac6a3ef7c8b60d6f477c793864e336bee9209ab41cf08f53c61421407c4d543` | `b537be7a6424dacee13fb29dc47f0b59f6f438cbc1ac4a74700a6cfdfd8491f3` | R10D; current/ceiling 200/200; control zero; Display |

Both new files completed, identify serial `SLUS-00923` and version 94, and decode both declared zstd frames with matching screenshot dimensions and payload lengths. Full serialized RAM at payload offset 6755 equals the corresponding coherent direct capture. Neither new checkpoint was restored. These checks establish creation/completion and exact RAM equality, not complete serialized-device equality, future restoration behavior or memory-card persistence.

### Field meanings and original execution

All addresses here are PS1 cached KSEG0 virtual addresses. Subtract `0x80000000` for main-RAM capture offsets. Data is little endian; u8 has no byte-order distinction. Code locations contain 32-bit LE MIPS instructions. PC and A0/A1/A2/V0/V1/RA below are 32-bit CPU registers, not RAM offsets or host-process addresses.

| Field | PS1 virtual address | Width and mask |
| --- | --- | --- |
| Actor base | `0x800CCBC4` | Object address, not a stored scalar |
| Current value, actor `+0xCC` | `0x800CCC90` | u16 storage, full `0xFFFF`; outcome code sign-extends to signed16 |
| Separate ceiling, actor `+0xCE` | `0x800CCC92` | u16 storage, full `0xFFFF`; cap code consumes signed16 |
| Lifecycle | `0x800CC858` | u32, full `0xFFFFFFFF`; world publish `0x08000000`, exit request `0x00020000`, consumer adds `0x00000040` |
| Native input control | `0x800CCBA0` | u32, full `0xFFFFFFFF`; movement filter `0x01000000` |
| Script task cursor | `0x800DEFEC` | u32 pointer, full `0xFFFFFFFF` |
| Primary/secondary routine | `0x800CCBC8` / `0x800CCBC9` | u8 each, full `0xFF` |
| Consumer task/interface guards | `0x800DCC14` / `0x800D442E` | u16 / u8, full `0xFFFF` / `0xFF` |
| Consumer camera equality | `0x800D1F7A` / `0x800CCBBE` | i16 / u8, full `0xFFFF` / `0xFF` |
| Task-selector entry 3 | `0x8009C968` | Three u32 words, full `0xFFFFFFFF` each: file index, code entry, load-base pointer |

The frozen runtime report's `health_u16` label at `0x800CCC92` refers to the ceiling. It must not be read as the changing current value. Original code reads/subtracts/stores actor `+0xCC` at `0x8003DD98..0x8003DDAC`; the add/cap path at `0x8003DE64..0x8003DE98` uses `+0xCE` separately.

| Epoch | Original stopped execution and observed result |
| --- | --- |
| 8 / 9 | Before world publication at `0x80024884`, lifecycle is `0x20001000` and V0 is `0x28001000`. The next source-bound normal-handler capture at `0x80039020` has R10D and the filter set. |
| 11 | The control-word write watchpoint stops at return PC `0x80052C70` with control zero. Original SET store `0x800547BC` consumed `4D 02 07 00` at RDT offset 14334, virtual `0x8011DF06`; task cursor is `0x8011DF0A`. The reader reports Display. |
| 12 / 13 | Before `sh A0,0xCC(A2)` at `0x8003DDAC`, current/ceiling is 200/200, A0 is 170, A1 zero, A2 `0x800CCBC4`, RA `0x80104DC4`. The callback return at that RA has 170/200 and V0 zero. This brackets the actual 200 to 170 subtraction/store. |
| 14 | Bounded read only: current/ceiling 20/200, primary/secondary 1/13 and reader Display. There is no full-RAM capture or full offline audit for this epoch. |
| 15 | Before exit-request store `0x8003DE4C`, current storage is `0xFFE2`, signed16 -30, and ceiling remains 200. A0 `0x800CA738`, A1 `0x00020000` and V1 `0x2C021000` identify the original store changing lifecycle `0x2C001000` to `0x2C021000`. Reader Retry. |
| 16 / 17 / 18 | Consumer `0x80024028` observes lifecycle `0x28021000`, task guard zero, interface guard zero and equal cameras. Selector `0x80031F50` receives A0 1/A1 3, RA `0x80024030`. Entry 3 identifies file 0, code `0x80194010`, load-base pointer `0x8001031C`. The next source-verified stop executes owned DIEDEMO at `0x80194010`, with request clear and lifecycle `0x28001040`. Reader Retry. |
| 19 / 20 / 21 | Selector A0 0/A1 0 chooses TITLE. The full epoch-20 capture and bounded epoch-21 read have the owned TITLE prefix, inactive world and zero actor fields while stale R10D bytes remain. Reader NonGameplay. No route or confirmation input caused this return. |

Lifecycle changed another bit between epochs 15 and 16; only the request mask is followed across that interval. Epoch 19's raw-input word `0xFFFFFFFF` is retained as observed. Its reset writer was not traced, and it is not evidence of delivered input. The earlier frozen epoch-43 request writer remains unclassified. This new episode does not retroactively identify it.

Owned-source binding compares the complete 51757-byte R10D.BIN object 3 at `0x80100000`, SHA256 `d8d1eba90103848621db9d62812eb03be6fbcd24c4a802fe88d51f684dcc7e7e`, at the subtraction and exit-writer captures. The callback return lies within that exact image. Source inspection is pinned to the owned executable identity above and the frozen `2026-11-12-re3-controller-mux-static/verified-final/` disassemblies `current-value-and-ceiling.asm`, `exit-request-consumer.asm`, `task-select.asm` and `DIEDEMO-entry.asm`. The replay also compares live code spans `[0x8003DD7C,0x8003DEA4)`, `[0x80023FA0,0x80024048)`, `[0x80031F50,0x80031FC0)` and `[0x8005472C,0x800547C0)` against that executable, plus the four revision windows. DIEDEMO SHA256 is `8d7c655d51fcc6c8f35024a7b0192215d897e4b3ab23f20b237cd1cdf7eb62d1`; TITLE SHA256 remains the value in RE3-NATIVE-002. Overlay identity is checked before interpreting reused virtual addresses.

### Offline reproduction, cleanup and limits

Frozen evidence root is `/Users/adamekka/.cache/re-map/evidence/2026-11-12-re3-seed-world-followup/`. Its `handoff.md`, `controller.jsonl`, checkpoint receipts, source/model records and manifest retain the exact inputs and observations. On 2026-11-13, offline verification rehashed all 334 entries and all 516 earlier entries across `2026-11-12-re3-fresh-admission-runtime`, `2026-11-12-re3-controller-mux-static` and `2026-11-12-re3-native-exit-attract`, before and after verification. Ten original application/settings/BIOS/media resources also remained unchanged. No emulator operation was performed for this documentation audit.

The unchanged 169-source binder, reader and native audit reproduce all nine coherent full captures exactly: one Display, four Retry, four NonGameplay. Dependency hashes agree with the frozen runtime. `campaign_admission` and `hard_identity` stay unresolved. Bounded epoch 14 adds no tenth full capture. The recorded-input producer did not hit within the bound, so this is no fresh recorded-negative matrix. No production predicate/profile, ownership, physical-floor, item, door or clearance contract follows. Generic SET1:63/0:23 aliases remain synthetic writer-closure obligations, not observed original-script counterexamples.

Run only the offline follow-up verifier into a new private output directory, with `PYTHONDONTWRITEBYTECODE=1`. Supply explicit `--evidence` as the follow-up root, `--frozen` as the fresh-admission root, `--static` as the controller-mux root, `--checkout` as this checkout, `--image` as the owned RE3 BIN, and `--output` as a nonexistent path. Never replay the retained launch/controller/preparation scripts to reproduce this offline check. The November 13 output is `/Users/adamekka/.cache/re-map/evidence/2026-11-13-re3-native-doc-integration/audit/followup/verification.json`, byte-identical to the frozen report.

Cleanup records wrapper exit 0 after 1165.1356 seconds, below the 1200-second watchdog, debugger-client exit 0, removed callbacks/watchpoints, PID 4556 absent and port 2401 bindable. The first cleanup attempt had already terminated the owned process and freed the port when it failed on missing optional preparation metadata. Preserve `cleanup-initial-failure.json`: `preflight.json`, `original-resources-before.json` and `binary-version.txt` were absent in the new episode folder. They were not later created to repair the record. Retained prelaunch settings, the actual pre-load PID receipt, live version log and previously verified frozen baselines provide the available configuration/resource evidence.

Despite its docstring, frozen `verify_cleanup.py` rewrites `prepare-used.py` and `cleanup-final.json` in its evidence directory. It requires an adapted copy with explicit fresh outputs, not direct rerunning. The November 13 copy adds required `--output` and redirects only those two writes; `cleanup-adaptation.diff` records the change. Its output reproduces the frozen cleanup report exactly and all four manifests still rehash unchanged. The new audit also preserves two corrected local verifier assumptions in `audit-attempts.json`: ARD and BIN require their own container offsets, and private settings acquired UI geometry. Neither changed the captured episode. Guest observations end at epoch 21, `2026-11-12T19:26:28.508362Z`; no guest read covers debugger disconnect through SIGTERM.

| Evidence | SHA256 |
| --- | --- |
| Frozen `handoff.md` | `e230e2a18bcbbedc0a32222d949fbf26afa48063b6b1fbadb0ecc40e492dd518` |
| Frozen `artifact-manifest.json` | `7714d52dadf15ee751fedbbc6474417f48fc1e6356e4802128e3d01fc9aad730` |
| Frozen `verify_followup.py` | `37521e3ebeb3144a69b0eb18890301ada6041f549f9bfec8f6b2c852823ac6e2` |
| Frozen and reproduced `verification.json` | `0d4c6290f7117b7c6eb5bc4ba06886fb964149763d3d7f643ee8455d408199ce` |
| Frozen and reproduced `cleanup-final.json` | `cfdf08dc3a2b02a56705e594e8110daf5433629ab484e2e813a761e0eedb2e37` |
| Audit `audit-before.json`, including exact runtime/audit model metadata | `707d3c72f3a7a8f35e34628d8b75d73a92b1c693d8cc389743192f957cef85e8` |
| Audit `independent-verification.json` | `a24242fc6c3e369935b80f9819bad1e068cc2268df833cc792d97c6f9ae58a13` |
| Audit `verify_independently.py` | `bdb60c64559667b0d445eafb58c6158ff0f7c308901c9b59d5540b33dddf684b` |
| Audit `verify_cleanup_fresh_outputs.py` | `3aaaf39ca08e4adb18b7ea880720ba46f1358be48efa4cb2947fafbc7a1bc167` |
| Audit `cleanup-adaptation.diff` | `ee644a106c9a951c7719449ac9229c5aedc6245142e92ec30d94f218ab5f7eaf` |

Audit paths are under `/Users/adamekka/.cache/re-map/evidence/2026-11-13-re3-native-doc-integration/audit/`. Raw RAM, native saves, screenshots, BIOS and disc bytes remain private outside Git. The original temporary audit was archived byte-for-byte at this durable path. Run relative-output audit helpers only from a fresh copied directory; hashes do not replace retained inputs. This is same-provider evidence verification, with no external endorsement or new runtime validation on November 13.

## Reproduction and verification

The [audit tool](../../../tools/re3_native_contracts.py) requires an owned BIN, an extracted executable and one or more explicit 2 MiB capture paths. It verifies the complete executable fingerprint and the four baseline runtime code windows, catalogs the supplied disc with the same required fingerprint, rereads and hashes each ARD, checks all native source-table rows, then audits the captures. It outputs numeric metadata and hashes only. An input failure returns 1 with a diagnostic and no partial JSON. Rejection evidence is a successful audit result, not a supported gameplay state.

Example using retained private evidence:

```sh
python3 tools/re3_native_contracts.py \
  '/Users/adamekka/Games/DuckStation/Resident Evil 3 - Nemesis.bin' \
  /tmp/re-map-re3-20261105-xqa_w0rf/SLUS_009.23 \
  /tmp/re-map-re3-runtime-20261105/no-input-later.ram \
  /tmp/re-map-re3-runtime-20261105/current-phase.ram \
  > /tmp/re3-native-audit.json
```

Private discovery is retained under `/tmp/re-map-re3-contracts-20261105/`, including `source_probe.py`, `source-probe.json`, `witnesses.py`, `witnesses.json`, owned executable/overlay disassemblies and initialization data. The parent's complete six-capture report is `parent-audit-final.json`, SHA256 `65b7af0c432e1734e68a45a274661cc20501e7b3f5d3e8374739b094d7bb2f10`. Its capture order is the six rows above. Rerunning after shared-bound extraction produced the same report bytes. Original capture hashes, settings, exact emulator version and failed-menu provenance remain in RE3-RUNTIME-001/002/003. Temporary evidence may expire; hashes are not replacements for retained inputs.

Run synthetic checks with the [test environment](../../testing.md#python-test-environment):

```sh
python3 -m pytest -q tests/test_re3_native_contracts.py tests/test_re3_map_data.py tests/test_re3_room_data.py tests/test_re3_room_catalog.py tests/test_re3_disc_identity.py
```

All 224 focused tests pass, including 50 native-audit cases. They check exact executable/capture identity, every code window, signed selectors, allocation disagreement, pointer/source bounds, camera bounds, opaque slot-2 relocation, independent geometry witnesses, native table disagreement, source ambiguity, mutable scripts and exact rewind, recorded-input rejection, and no admission even with all witnesses matching. Four additional menu/pause cases retain matching sources, check independent rejection reasons and exact earlier-state reversal, and allow a stale nonzero view after dismissal. CLI tests exercise real source-sector reads and hashes while isolating the separately tested catalog boundary; missing/changed/unsupported input and a later bad capture emit no partial JSON. No owned executable, RAM or artwork enters fixtures.

The later [Hard control experiment](hard-start.md#re3-input-002-native-hard-selection-and-control-in-two-rooms) establishes natural selection, deliberate control, sampled room-source binding and earlier/later restoration. Ordinary room departure/reentry, lifecycle states across title/demo/cutscene/UI/gameplay, fresh read ordering and allocation extent still need contracts. Source witnesses alone cannot substitute for those observations. Acquisition, door and story banks still require separate native before/after and restore evidence. No runtime profile, tracker history, map UI or game files changed.

## Contributions and review

- 2026-11-05; human user; supplied owned media, requested parallel work and selected Hard.
- 2026-11-05; implementation delegate, `gpt-6.1-sol` verified by returned run metadata; traced native tables/loader/recorded-input leads, probed the six retained captures and authored the initial audit draft. Workspace credits exhausted before tests, documentation, review or commit.
- 2026-11-05; Codex root, exact runtime model `gpt-6.1-sol`; recovered the draft, checked native instructions and all 169 table/source pairs, shared the revision fingerprint and section-bound formula, added synthetic/CLI regressions, reproduced the six-capture audit, wrote this topic record and performed final integration review. Review covered address/width/mask labels, bounds, input preservation, ambiguity, mutable-byte limits, modeled failures and refusal to claim gameplay admission. Configured external review providers remained unavailable; no external endorsement or new gameplay validation is claimed.
- 2026-11-05; Codex root, `gpt-6.1-sol`; corrected the overlay base against the retained disassembly and two independent prefix locations before using menu code addresses. The audit implementation and capture results are unchanged.
- 2026-11-05; Codex root, `gpt-6.1-sol`; linked later native Hard/control and difficulty-bit observations while preserving the offline audit's unresolved admission outputs. New runtime evidence and its limits belong to RE3-INPUT-002/003.
- 2026-11-05; Codex root, exact runtime model `gpt-6.1-sol`; authored RE3-NATIVE-004 after native Circle/L2/Start experiments, controlled blocked/resumed turning, source checks and verified private cleanup. Added raw interface/pause diagnostics and rejection reasons, four synthetic regressions and the eight-capture verifier. Local review checked native byte ownership and branch semantics, stale views, independent causes, field widths, capture timing, source preservation and refusal of positive admission. Configured external reviewers remained unavailable; no external endorsement is claimed.
- 2026-11-05 UTC; independent native investigator, `gpt-6.1-sol` verified from its matching session metadata and latest turn context; performed the bounded normal-handler/startup and settled input comparisons for RE3-NATIVE-005, authored the private report/verifier/manifest, preserved failed attempts and verified private cleanup. The experiment supplies a Candidate rejection, not sufficient positive admission.
- 2026-11-06 UTC; Codex root, exact runtime model `gpt-6.1-sol`; authored the additional offline rejection, three diagnostics, nine synthetic cases and RE3-NATIVE-005. Reproduced the missing reason before the fix, checked filter/dispatcher source, verified all manifest files and eleven revised audits against all owned sources, decoded both key native checkpoints and rechecked process/port cleanup. This integration performed no new emulator operation or user-history change.
- 2026-11-06 UTC; independent internal reviewer, `gpt-6.1-sol` verified from its matching session metadata and latest turn context; audited the native evidence and reviewed the new code, nine tests and RE3-NATIVE-005. Independently checked nine native states, eleven captures' critical code, both full-RAM restores, all 67 manifest files, private settings, cleanup and unchanged earlier audit fields. All 59 native-contract tests passed. Review corrected an overstated live-register attribution: A0/RA come from native payloads, while live PC and full RAM agree. Field masks, independent reasons, surviving inputs, failure provenance and unresolved positive admission were checked; no edits or emulator operation occurred.
- 2026-11-06 UTC; external snapshot reviewer, `gemini-3.8-flash` at high reasoning through Antigravity; returned no findings on the new diagnostics/rejection, synthetic fixtures, inherited capture/source checks and RE3-NATIVE-005. Review covered masks/widths, gated reads, independent causes, errors, rewind, input preservation, test risks, scope/reuse and evidence/admission limits. It ran no tests, native execution or gameplay experiments. Claude Opus 5.5 remained disabled in the provider inventory and supplied no review.
- 2026-11-12 UTC; native investigator, exact executing model `gpt-6.1-sol`, effort `xhigh`, verified from session `01a1d067-4a20-7472-8442-415e931be0e5` and its final turn context; performed the single seed restore, original no-input world/exit episode, checkpoint creation, offline replay and private cleanup recorded in RE3-NATIVE-006. Authored the frozen handoff, not this later project-document section. Earlier research authorship and human Hard selection remain unchanged.
- 2026-11-13 UTC; same-provider documentation auditor, exact executing model `gpt-6.1-sol`, effort `xhigh`, verified from session `01a1d417-fd61-7350-90e2-a577efd1b262` and its turn context; authored RE3-NATIVE-006 and qualified the header's emulator scope. Reproduced the nine-capture/169-source report byte-for-byte, independently decoded the seed and two new checkpoints, checked exact RAM and source-packet/code identity, rehashed 334 new plus 516 prior manifest entries before/after, and verified ten original resources and process/port cleanup through an output-redirected verifier. Review covered field signs/widths/masks, bounded/full-capture distinctions, prior-writer uncertainty, missing preparation metadata, mutating-verifier behavior and admission/restoration limits. Model-source paths and selected metadata are retained in `audit-before.json`; no emulator operation, external review or production-code change occurred.

- 2026-11-13 UTC; Codex root, verified `gpt-6.1-sol`, effort `xhigh`; checked the final record against the frozen native handoff and independent audit outputs, preserved the native-versus-offline limits, and archived every independent audit file byte-identically outside the temporary directory. Added the research index entry. This contribution performs no new emulator operation or native-state validation.
