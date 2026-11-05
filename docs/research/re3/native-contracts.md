# RE3 native room and lifecycle candidates

[RE3 scope](../../re3.md) · [Disc identity](identity.md) · [Room sources](room-format.md) · [Runtime baseline](runtime.md)

Target: Resident Evil 3: Nemesis, PlayStation, USA, SLUS-00923, executable `SLUS_009.23`, SHA256 `2e143418e358b2c99995cdc1a88c387163fb751912c723b755614f38e236bd29`. Hard remains the human-selected target. All findings below are Candidate. This work reads the owned executable/disc and retained RAM; it does not run an emulator. The retained captures came from DuckStation `0.1-12083-g00e299795`, as recorded in RE3-RUNTIME-001.

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

Status: Candidate field leads. Hard selection and scenario identity remain unresolved.

| Candidate field label | PS1 virtual address | Width, byte order and mask | Limit |
| --- | --- | --- | --- |
| Saved status word | `0x800D1F2C` | u32 LE, `0xFFFFFFFF` | Raw diagnostics; no campaign/difficulty interpretation |
| New-game option word | `0x800D1F30` | u32 LE, full `0xFFFFFFFF`; exported low-bit view uses `0x00000001` | Raw option lead; neither bit value is mapped to Hard |

The owned `INIT_TBL.DAT` and `INIT_SUB.DAT` are each 2312 bytes. Their SHA256 hashes are `821da14c1716e00256d2556f43942f19c6e9176d43d5fba74a8aa1e24745996f` and `e8817cdcfb34436a6c822de406a82d28bd9b774efe6a7abe44f70a63d862bcbe`. They give initialization leads, not a verified runtime selector. All six retained captures have zero at the proposed option word. The saved status word is zero except `post-menu-attempt`, which has `0x140`. Treating these values as proof of Hard would repeat the original no-input admission error.

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

All 220 focused tests pass, including 46 native-audit cases. They check exact executable/capture identity, every code window, signed selectors, allocation disagreement, pointer/source bounds, camera bounds, opaque slot-2 relocation, independent geometry witnesses, native table disagreement, source ambiguity, mutable scripts and exact rewind, recorded-input rejection, and no admission even with all witnesses matching. CLI tests exercise real source-sector reads and hashes while isolating the separately tested catalog boundary; missing/changed/unsupported input and a later bad capture emit no partial JSON. No owned executable, RAM or artwork enters fixtures.

Next, establish natural Hard selection and player control, observe ordinary room departure/reentry, bind lifecycle states across title/demo/cutscene/UI/gameplay, and validate fresh read ordering and allocation extent. Source witnesses alone cannot substitute for those observations. Acquisition, door and story banks still require separate native before/after and restore evidence. No runtime profile, tracker history, map UI or game files changed.

## Contributions and review

- 2026-11-05; human user; supplied owned media, requested parallel work and selected Hard.
- 2026-11-05; implementation delegate, `gpt-6.1-sol` verified by returned run metadata; traced native tables/loader/recorded-input leads, probed the six retained captures and authored the initial audit draft. Workspace credits exhausted before tests, documentation, review or commit.
- 2026-11-05; Codex root, exact runtime model `gpt-6.1-sol`; recovered the draft, checked native instructions and all 169 table/source pairs, shared the revision fingerprint and section-bound formula, added synthetic/CLI regressions, reproduced the six-capture audit, wrote this topic record and performed final integration review. Review covered address/width/mask labels, bounds, input preservation, ambiguity, mutable-byte limits, modeled failures and refusal to claim gameplay admission. Configured external review providers remained unavailable; no external endorsement or new gameplay validation is claimed.
- 2026-11-05; Codex root, `gpt-6.1-sol`; corrected the overlay base against the retained disassembly and two independent prefix locations before using menu code addresses. The audit implementation and capture results are unchanged.
