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
