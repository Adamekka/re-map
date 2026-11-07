# RE3 collectible acquisition

## RE3-COLLECT-001: one native pickup survives reentry and reverses with saves

Status: Candidate reusable acquisition contract for Resident Evil 3: Nemesis, PS1, NTSC-U, SLUS-00923, Hard. One ordinary inventory pickup, source recreation after reentry and exact earlier/later native restores were observed. This does not establish a complete room item list, clearance, a production collectible reader or a registered tracking profile.

The owned executable SHA256 is `2e143418e358b2c99995cdc1a88c387163fb751912c723b755614f38e236bd29`. The isolated session used DuckStation `0.1-12083-g00e299795`, binary SHA256 `5c879677051cfb173002df22baee741c96fa8071c6fe1dd7e5454092bf128173`, native save version 87. All native addresses below are cached PS1 virtual addresses. Multibyte values are little endian; a RAM offset is the virtual address minus `0x80000000`.

### Source and native write

The selected source is `CD_DATA/STAGE1/R100.ARD`, embedded RDT SHA256 `e47f25b5a6e82d73f79bf356c111a8add6a7e24555a4deb83ed8725e3979ed50`, 109208 bytes. Its canonical initializer procedure 6 begins with opcode `67` at RDT byte offset 3238. Root procedure 0 calls procedure 6 unconditionally at offset 3084. The 22-byte owned packet is:

```text
670d0231000080a9a5b48403a4067300010002000280
```

The packet names registry slot 13, raw type `0x73`, quantity 1 and acquisition index 2. Its native category record is `05010500`, category 5. This specimen underwent no type remap. The live registry at `0x800CC890 + 4 * 13` pointed to `0x8011B3B0`, loaded base `0x8011A708` plus descriptor offset 3240. All packet bytes initially matched the owned source.

Original kind-2 entry `0x8005111C` observed descriptor S0=`0x8011B3B0` and payload A0=`0x8011B3BC`. At original callsite `0x8006A144`, inventory slot 4 had gained bytes `73010000`, while the acquisition word was still zero and the descriptor kind was already zero. This intermediate UI state must not be published as a settled acquisition result.

The original setter entry `0x800788DC` observed A0=`0x800D2008`, A1=2 and caller `0x8006A14C`. A native write watch then stopped at that caller with acquisition word `0x20000000`. The actual helper store is in the return delay slot at `0x80078900`.

For this index, the observed flag location is PS1 virtual `0x800D2008`, RAM offset `0x000D2008`, width u32 and mask `0x20000000`. The source helper computes word address `bank + 4 * (index >> 5)` and mask `0x80000000 >> (index & 31)`. One observed bank/index does not establish every stage's bank selection or every item form.

### Reentry and native restore checks

Ordinary source-bound doors took R100 to R101 and back. Both the acquisition word and inventory entry remained present. On reentry, original creator callsite `0x80057600` observed S0=`base + 3238`, S4=13, S6=2 and A0=`0x800D2008`. A1 was still 1 at the stopped `jal`; the original delay slot assigns S6 to A1. The stopped register value is not relabeled as an observed getter-entry argument.

After reentry settled, slot 13 again pointed to `base + 3240`. Every packet byte matched the owned source except its native kind byte changing from 2 to 0. This is an observed ordinary recreation using the acquired state, distinct from savestate restoration.

| Native checkpoint | Save SHA256 | Acquisition / kind / inventory slot 4 |
| --- | --- | --- |
| Earlier | `5a6784037097f1f1d4397fb03355bc8f51a43f1c4dadc9e151de75b458830668` | clear / 2 / `00000000` |
| Later | `192c3d7451234a6317906bbe98d521014881b8ebffb9ade71520296a7f6e7ac0` | set / 0 / `73010000` |

Native F1 restored each checkpoint after the round trip. Before experimental resume, each restored state matched its complete 2 MiB RAM, GPR 0 through 31, HI/LO, PC and 1024-byte scratchpad. Earlier reversed the acquisition, descriptor and inventory; later restored them. These checks do not compare every serialized device field or establish memory-card persistence. A separate final F2 creation matched its captured RAM/CPU/scratch and released native Pad state.

### Read boundary and limits

The existing [current-room source binding](live-reader.md#re3-live-001-bounded-hard-current-room-and-pose-observations) checks immutable header/camera witnesses. It deliberately excludes mutable SCD bytes and grants no collectible-source right. A production item reader needs its own canonical packet and registry binding, checked index/bank semantics and coherent lifecycle/UI exclusion. It must reread after restore and distinguish the observed native kind mutation from arbitrary source changes. A missing live object alone establishes neither collection nor absence.

This experiment covers one category-5 ordinary item. Cancellation, inventory-full behavior, consumption, another specimen, four-point item forms, later stages and other revisions remain untested. No item name, complete room list, room-clear authority, door knowledge or tracker exploration is inferred.

### Evidence, isolation and attribution

The original private bundle is `/tmp/re-map-re3-acquisition-native-20261107-7kP8Df/`. `handoff.md` has SHA256 `bba59f51e9665a0a5b91774efe7eecfcdbde0648d45a54279cfb98c241bfb1ee`; `verification.json` has SHA256 `44e843782dd26b3eca650601ecbb61551c6ef3c3b5b4c4b9848f6e24788f7324`; `artifact-manifest.json` has SHA256 `da7fe123d884e0417afd1bea63592234651b69c4bd2b96cbdfaae8f5f9392ff8`. The report checks seven retained captures, 130 controller commands, 92 native run stops, four native payloads and three exact restores. Static precursor evidence remains `/tmp/re-map-re3-acquisition-20261107-EPqnqc/`; its handoff SHA256 is `90e3191e2108216a46cce13c48444d0f3d1474da38cc7e11041534baabd36a1e`.

Achievements and RA integration were disabled in both namespaces before boot and every load. Cards were unmounted, accounts blank, game overrides absent, audio muted and gameplay output suppressed. No guest memory/code patch, tracker history or production profile was written. Failed input/heading probes, the diagnostic-address correction and the CUA capture timeout remain recorded rather than treated as successful input delivery.

Cleanup observed native Pad mask zero and all five input words zero, removed every owned callback, stopped only verified PID 13660 with wrapper exit zero and checked port 2395 free. Private settings remained byte-identical. Previously enumerated user-file size/mtime remained unchanged without reading their contents. Claims end at the final acknowledged capture before last-client disconnect; the disconnect-to-termination guest interval is unobserved. Raw media, BIOS, RAM, saves and the private app remain outside Git.

Contribution, 2026-11-07 UTC: the human supplied the owned disc and Hard target. `investigate_gdb_recovery`, exact verified model `gpt-6.1-sol`, effort `xhigh`, performed the isolated source/controller/native experiment and authored its private evidence. Codex root, exact runtime model `gpt-6.1-sol`, effort `xhigh`, authored this bounded research record. Prior static and human provenance remains unchanged. This writing step adds no broader gameplay confirmation.

Parent verification, 2026-11-07 UTC: Codex root independently checks all 51 root artifact hashes and all 104 frozen Python hashes. Independent zstd CLI decompression finds each complete captured 2 MiB RAM image exactly once in all four relevant native payloads. The parent also observes PID 13660 absent and port 2395 bindable without connecting to an emulator. `/tmp/re-map-re3-acquisition-root-audit-20261107/audit.json` has SHA256 `e09cd09bd3416e4db9634134d950cc3dd8a3c262182696df875c4d84eb3a5961`. This audit adds no native gameplay or CPU/device-state claim beyond the separately retained checks.

The original verifier depends on absolute temporary EXE/binary paths and live author-session metadata, rewrites its input report, and does not itself require root-manifest validation. A separate portable amendment fixes those evidence-tool defects while preserving every original file. The original experiment author performed the portability audit in a later turn; that audit is not an independent review of the experiment.

Use CPython 3.14 or later with assertions enabled, the explicit exact owned CUE/BIN and a fresh output directory. The capsule can be relocated:

```sh
re3_bundle=/path/to/re-map-re3-acquisition-portable-capsule
python3.14 "$re3_bundle/verify_portable.py" \
  --bundle "$re3_bundle" \
  --cue '/path/to/owned/Resident Evil 3 - Nemesis.cue' \
  --output /path/to/fresh-output
```

The retained capsule is `/tmp/re-map-re3-acquisition-portable-20261107-LUpM3N/`. Its `portable-manifest.json` SHA256 is `420465a7e2948f386f95f6081be96ae456984a716f9eb4320c8b4e2dbbfc1b2d`, and `verify_portable.py` SHA256 is `69352adf5bd85a2f32995f483b9ccb06c6e8adab3b1c161115bf28ffe9ee02db`. Mandatory checks bind all 165 capsule files, the pinned original artifact manifest, all 51 original root artifacts and 104 frozen Python files. The exact owned disc remains a required external input. The copied native executable is hashed only; BIOS and the full emulator app are unnecessary for offline verification.

Two fresh audit runs, including a relocated read-only capsule with `CODEX_THREAD_ID` unset, regenerate the native report byte-for-byte. Tampering and Python `-O` reject. All 422 files in the original session tree remain unchanged. The audit output `/tmp/re-map-re3-acquisition-audit-output-20261107-DzheQp/` contains `audit-result.json`, SHA256 `022d78b05bb052165e29afbdf6a206d51ead068ed0490fc01b9d005abf2b5fb3`, and handoff SHA256 `7c4ef6c76e0cb5352d344ea38021a6dd8b6a1bc475e25e5c243f2eebe71937f8`. Root separately reruns the portable verifier from `/tmp` with `CODEX_THREAD_ID` unset and reproduces original report SHA256 `44e843782dd26b3eca650601ecbb61551c6ef3c3b5b4c4b9848f6e24788f7324` in `/tmp/re-map-re3-acquisition-root-portable-verify-20261107/`. These offline checks add no gameplay; artifact hashes are integrity references, not signed execution attestation.

External review, 2026-11-07 UTC: `gemini-3.8-flash`, high reasoning through Antigravity, returns No findings on the complete proposed claim, native/portable handoffs and verifier, original native report, selected exact instruction windows and command-result fields, load/cleanup receipts, independent parent audit and integration summary. The completed response has no pending child work or tool attempts. The review checks correctness, provenance, integrity, portability, bounded scope, diagnostics and evidence limits. Claude Opus 5.5 remains disabled and supplies no review. This prose review adds no native observation or item-tracking authority.

## RE3-COLLECT-002: one fresh registered collectible condition

Status: Candidate Python API for the same exact SLUS-00923 Hard revision. It reports one currently registered canonical packet's raw acquisition condition. This is separate from a proof that the player collected it, that a departed room contains it, or that the relevant item list is complete. Script flag/reset aliases still need their own proof before those stronger uses.

### Required compilation

Call `games.re3.collectibles.bind_collectible_source(executable, catalog, stage, room, procedure_index)` with the pinned complete executable and an existing complete 169-source `SourceCatalog`. Every argument is explicit. Unsupported inputs return `RoomFormatFailure`; there is no fixture, partial-catalog or offset-scanning fallback.

The binder recognizes opcode `67` only at a native procedure-directory entry, with its complete 22 bytes inside that procedure's existing parsed envelope. This avoids interpreting a matching byte in an operand as a creator. It qualifies the first ordinary schema: stage zero, slot below 32, kind 2, rectangular SAT `31`, flag byte 21 bit 0 clear, raw type below 256, native category 5 and acquisition index below `F8`. Category 6, flag1 animation, four-point `68`, other constructors and later-stage banks remain outside this contract.

Native type categories come from the pinned table at PS1 virtual `0x800A0514`, four bytes per raw type, category byte at offset zero. The stage-zero bank pointer is read from pinned `0x8009E414` and must equal `0x800D2008`. Shared `games.bit_flags.msb_flag_location` supplies the word/mask formula. Category/source-table parsing uses executable file offsets; the returned live flag address is PS1 virtual.

`CollectibleBinding` retains the exact source, packet, procedure, raw fields, source hash and flag address/mask under its immutable derivation. Mandatory constructors require immutable bytes and exact native integer fields before comparing the derivation. This rejects value-equal `bytearray`, `memoryview`, boolean and floating aliases rather than allowing changed backing storage after validation. Correct unbound source parsing failures remain modeled separately from these programmer invariant violations.

### One guarded read

Call `games.re3.live_reader.read_current_collectible(binding, read_memory)`. It extends the existing current-room transaction; it does not call the room reader and then read items after that transaction returns.

The selected current source must be the binding's catalog member. Its registry word at `0x800CC890 + 4 * slot`, u32 little endian, must equal `loaded_base + packet_offset + 2`. Only that exact pointer is accepted; a missing or foreign registration is a modeled failure. The code never follows an arbitrary registry pointer.

The complete loaded packet must match the owned bytes except for the specific native kind mutation. Kind 2 qualifies only with its acquisition bit clear; kind 0 qualifies only with that bit set. Other pairs or changed bytes return `Retry`. A contiguous 60-byte pose read at `0x800CCBF8` supplies signed i32 little-endian XYZ at offsets 0, 4 and 8 and unsigned u16 facing at offset `0x3A`. The selected flag mask and complete observed packet bracket that pose read in forward/reverse order before the existing source/lifecycle sweep ends. This prevents a same-room restore from pairing an earlier pose with the restored acquisition condition. Unrelated bits in the same flag word may change without invalidating the selected condition.

The same transaction adds interface-request phase `0x800C7961`, u8/full mask, expected zero, and pending status `0x800D1F2C`, u32/mask `0x200`, expected zero. Both fields and the selected registry pointer already lie inside the existing initial/repeated spans. Pending/active interface states return `NonGameplay`; changing guards return `Retry`. Existing revision, Hard, loading, source, pause, control and pose rules remain mandatory. Read errors or short replies return `ReadFailure` without a partial observation. An admitted different source returns `UnsupportedRoom`.

The output contains the same-read `CurrentRoomObservation`, executable/RDT hashes and packet offset, registry slot, raw type, raw source amount, index and `acquisition_set` boolean. Source amount is not a display-unit or accepted inventory-quantity promise. No inventory slot is a runtime requirement. Immutable compilation can persist, but registration, guards and flag state are freshly read after every poll, reconnect and restore.

### Verification and limits

The actual complete owned corpus binds through the production factory. R100 procedure 6 qualifies packet offset 3238, slot 13, type `73`, amount 1, index 2, word `0x800D2008` and mask `0x20000000`. Six retained R100 captures return the expected clear/set/reentry/earlier/later condition; the R101 capture rejects this different-source binding. These are replays of RE3-COLLECT-001, not a new native experiment or a live cadence measurement.

Each accepted R100 replay uses 27 bounded memory requests and 3874 payload bytes, including revision and repeated source witnesses; the packet, flag and intervening pose add five requests. No full-RAM polling, corpus scan or source hashing occurs during a poll. The existing coherent-read and original-engine domain remains unchanged; arbitrary ABA or patched/corrupted states are not newly proved safe.

The 144 new regressions cover native slot/flag boundaries, every packet byte, all 27 transport failures/short replies, mutable/equivalent constructor fields, source/registry mismatch, pending/active UI, both kind/bit mismatches, changing packet/bit/pointer/guards, unrelated bit changes, moving pose, same-room restores at five points around the packet/flag/pose reads in both acquisition directions, and fresh Hard/Easy/earlier/later reversal. Combined focused checks pass 342 tests, and the working-tree full suite passes 7028 in 132.03 seconds. Scoped Ruff lint/formatting and whitespace checks pass. No renderer, profile, exploration history or completion state is changed.

Fresh final replay is `/tmp/re-map-re3-current-collectible-20261107/restore-coherence/replay.py`. Its `verification.json`, SHA256 `c00bb698d595fbcbf30b74bf00c31c7b616556307bf90a7c9cc9719e2419352e`, binds both implementation files, the shared source-witness dependency and both current test files. The original report remains separate. Reproduce with the supplied Python environment, exact owned CUE/BIN and retained native bundle; copy the verifier to a fresh output directory first. Raw assets and RAM remain private.

Contribution, 2026-11-07 UTC: Codex root, exact runtime model `gpt-6.1-sol`, effort `xhigh`, authors the singular binder/read transaction, regressions, real-source replay and this claim. Independent reviewer `review_re3_rows`, the same exact verified model/effort, checks the code against the original creator/UI/setter/helper windows and retained evidence. It identifies and rechecks the mutable-packet constructor defect plus the separate camera/zone witness defect in RE3-LIVE-001. Both are corrected; eight direct equivalent-type probes reject and no further code finding remains. Its frozen `review.json` SHA256 is `5796b7bcd05f9f4d24589116057786bae13a055f39846581d80e230ae08beec8`, with five-file snapshot digest `9187126e36072caae4ba2a58c275dabd0960e0672d4a418a1e1b12a4a957f52e`. This code/source review adds no native gameplay or stronger item rights. External review of this API is separate from the completed RE3-COLLECT-001 evidence review.

Parent correction, 2026-11-07 UTC: Codex root reproduces a same-room restore between the initial pose and first packet read pairing the old XYZ/facing with the restored acquisition condition. Both acquisition directions fail the new regression before the fix. Reading pose inside the packet/flag interval corrects the mismatch without requiring stationary coordinates or changing the existing room/map observations. The private baseline failure and current replay remain under the `restore-coherence` evidence directory above. This is synthetic restore-timing validation against the production reader; it adds no native gameplay observation.

Independent restore recheck, 2026-11-07 UTC: `review_re3_rows`, verified `gpt-6.1-sol`, effort `xhigh`, separately loads the exact prior reader from the preserved review packet and reproduces both mismatches. All ten fixed restore boundaries and 54 transport failure/short-reply cases pass. Its frozen `/tmp/re-map-re3-collectible-restore-review-20261107-COINX9Vd/review.json`, SHA256 `d76961d35c9668dd33b7869a21e479c3d8dfb591ddf627edd9d519daac3c4e81`, binds the final implementation and test hashes and reports no findings within that scope.

External review attempts, 2026-11-07 UTC: the original combined API request to `gemini-3.8-flash`, high reasoning through Antigravity, ends without a response after 15 minutes. Fresh separate binder and runtime requests both fail to open provider sessions. Both are terminal with no pending child work and provide no review or endorsement. Claude Opus 5.5 remains disabled. The reviewed local code, independent constructor/native audit and narrow restore recheck above are the completed perspectives. The completed RE3-COLLECT-001 evidence review does not cover this API.
