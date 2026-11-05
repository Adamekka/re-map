# RE3 native room and lifecycle candidates

[RE3 scope](../../re3.md) · [Disc identity](identity.md) · [Room sources](room-format.md) · [Runtime baseline](runtime.md)

Target: Resident Evil 3: Nemesis, PlayStation, USA, SLUS-00923, executable `SLUS_009.23`, SHA256 `2e143418e358b2c99995cdc1a88c387163fb751912c723b755614f38e236bd29`. Hard remains the human-selected target. Claims 001 through 003 are Candidate offline contracts. Claim 004 adds confirmed observations of specific menu/pause boundaries. The audit reads the owned executable/disc and retained RAM; it does not operate an emulator. The retained captures came from DuckStation `0.1-12083-g00e299795`, as recorded in RE3-RUNTIME-001.

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
