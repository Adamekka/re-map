# RE3 room containers and static metadata

## Scope and identity

Target: Resident Evil 3: Nemesis, PlayStation, USA, SLUS-00923, user-selected Hard mode. No runtime difficulty observation was made in this workstream. The exact tested disc identity is the executable fingerprint below; no retail revision label beyond that fingerprint has been established.

Independent reads from the owned MODE2/2352 image on 2026-11-05 reproduced the initial file listing and boot identity:

- 1,354 ISO9660 files, including 169 `.ARD` and zero `.RDT` entries.
- `SYSTEM.CNF` selects `SLUS_009.23`, 868,352 bytes, ISO LBA 288380.
- Executable SHA256 `2e143418e358b2c99995cdc1a88c387163fb751912c723b755614f38e236bd29`.
- PS-X entry `0x80011B80`, load `0x80010000`, declared text size 866,304 bytes. These are executable header observations, not live process addresses.
- No emulator was booted. Tested DuckStation version: none in this workstream. No RAM, savestates, patches, settings or playthrough histories were used.

Private evidence is under `/tmp/re-map-re3-room-20261105/`. It includes independently regenerated `files.json`, `initial-scan.json`, `structure-scan.json`, `table-scan.json` and `room-catalog-initial.json`. Extracted executable, ARD and RDT bytes remain private. The repository contains original parser code, synthetic tests and numeric findings only.

## Primary source leads

Sources describe candidate layouts. They do not establish behavior on this revision.

1. Patrice Mandin's reevengi, commit `8130d5fd029a7548135bdbbff19b0b8e338bd42d`: [`src/g_re3/ard.h`](https://github.com/pmandin/reevengi/blob/8130d5fd029a7548135bdbbff19b0b8e338bd42d/src/g_re3/ard.h), `RE3_ARD_RDT` and the header/object structs; [`ard.c`](https://github.com/pmandin/reevengi/blob/8130d5fd029a7548135bdbbff19b0b8e338bd42d/src/g_re3/ard.c), `ard_loadFile`; [`rdt.h`](https://github.com/pmandin/reevengi/blob/8130d5fd029a7548135bdbbff19b0b8e338bd42d/src/g_re3/rdt.h), section indices; [`rdt_scd.c`](https://github.com/pmandin/reevengi/blob/8130d5fd029a7548135bdbbff19b0b8e338bd42d/src/g_re3/rdt_scd.c), `rdt3_scd_scriptInit`.
2. BioRand biohazard-utils, commit `6095aee3a9dd40576dece9c7598e37a003b5ab45`: [`Room/Rdt2.cs`](https://github.com/biorand/biohazard-utils/blob/6095aee3a9dd40576dece9c7598e37a003b5ab45/src/IntelOrca.Biohazard/Room/Rdt2.cs), `_offsetTableKinds3`, slot-2 exclusion, `SCDMAIN`; [`ScdProcedureList.cs`](https://github.com/biorand/biohazard-utils/blob/6095aee3a9dd40576dece9c7598e37a003b5ab45/src/IntelOrca.Biohazard/Room/ScdProcedureList.cs), `Count`, `GetOffset` and the indexer.
3. Reevengi at the same pinned commit: [`g_re2/rdt_rid.h`](https://github.com/pmandin/reevengi/blob/8130d5fd029a7548135bdbbff19b0b8e338bd42d/src/g_re2/rdt_rid.h), 32-byte camera struct; [`g_re3/rdt.c`](https://github.com/pmandin/reevengi/blob/8130d5fd029a7548135bdbbff19b0b8e338bd42d/src/g_re3/rdt.c), RE3 wiring to that reader; [`g_re2/rdt_rvd.h`](https://github.com/pmandin/reevengi/blob/8130d5fd029a7548135bdbbff19b0b8e338bd42d/src/g_re2/rdt_rvd.h), 20-byte zone struct; [`g_re3/rdt_sca.c`](https://github.com/pmandin/reevengi/blob/8130d5fd029a7548135bdbbff19b0b8e338bd42d/src/g_re3/rdt_sca.c), count and 16-byte collision records.
4. Mortician's lib_bio, commit `ee30311756f213f60e0d885d9c2eef668ccb53e9`: [`lib_bio/lib_sca.py`](https://github.com/mortician/lib_bio/blob/ee30311756f213f60e0d885d9c2eef668ccb53e9/lib_bio/lib_sca.py), version-3 branches of `sca_object.read` and `sca_file.read_from_stream`. Its trailing collision field labels differ from reevengi's. Neither interpretation is adopted as a runtime fact.

## RE3-ROOM-001: ARD object 8 contains bounded room data

Status: Candidate for the fingerprint above. Offline corpus agreement only.

The ISO paths are `CD_DATA/STAGE{S}/R{S}{RR}.ARD`, with stage digits 1 through 7 and a two-digit hexadecimal source number. Counts by directory are 38, 28, 24, 23, 17, 15 and 24. Filename numbers are source identifiers; a live room/stage mapping has not been established.

| Field | Address space / offset | Width, endian, mask | Observed contract |
| --- | --- | --- | --- |
| ISO extent | ISO9660 logical block number | 32-bit LE extent field, all bits | 2048-byte logical blocks within 2352-byte raw sectors; user data begins at raw-sector byte 24 |
| ARD size | ARD file byte `0` | u32 LE, `0xFFFFFFFF` | Equals ISO file length for all 169 sources |
| Object count | ARD file byte `4` | u32 LE, `0xFFFFFFFF` | Ten for all 169 sources |
| Object length | ARD file byte `8 + 8*i` | u32 LE, `0xFFFFFFFF` | Payload size excluding alignment padding |
| Object tag | ARD file byte `12 + 8*i` | u32 LE, `0xFFFFFFFF` | Preserved numerically, meaning unresolved |
| Payload position | ARD-relative byte offset | Derived integer, no stored field/mask | Object 0 starts at `0x800`; next is `(offset + length + 0x7FF) & ~0x7FF` |
| Room payload | ARD object index 8 | Index, no endian/mask | Embedded RDT, read without decompression |

For `CD_DATA/STAGE1/R100.ARD`, container size is 387,072 and SHA256 is `488ca7da73b5d99760100fcb5c088006ea90a2978c905ab16aa2ea065eb02f38`. Object 8 begins at `0x39800`, has length 109,208 and SHA256 `e47f25b5a6e82d73f79bf356c111a8add6a7e24555a4deb83ed8725e3979ed50`.

Rejected hypothesis: use reevengi's strict-next alignment `(offset + length | 0x7FF) + 1`. It adds a sector when a payload ends on a boundary. Five owned containers then disagree with their final extent; three put object 8 at the wrong position. The ordinary ceil formula gives the exact final extent for all 169. Synthetic tests retain exact-boundary and zero-length counterexamples. The corpus itself contains no zero-length objects.

## RE3-ROOM-002: room header and geometry boundaries

Status: Candidate for the fingerprint above. No player position, facing or floor projection has been validated.

The bounded parser reads an eight-byte prefix followed by 22 u32 words, ending at `0x60`. Reevengi's 21-word struct omits the final word described by biohazard-utils. Slot 21 is zero on all 169 owned sources; it must not become the first camera word by a mistaken RE2 23-word read.

Slot 2 is preserved as an opaque word and excluded from boundary calculations. In 165 sources it equals slot 1 minus one. Four sources contain out-of-file values instead: `R201`, `R214`, `R215` and `R50A`. This agrees with biohazard-utils' exclusion, but conflicts with its comment describing the common value as slot 1 plus one. Neither a pointer nor that plus-one formula is accepted.

| Field | Address space / offset | Width, endian, mask | Candidate contract |
| --- | --- | --- | --- |
| Camera count | RDT byte `1` | u8, `0xFF`, endian n/a | Count of 32-byte camera records |
| Section words | RDT bytes `8 + 4*i`, `i=0..21` | u32 LE, `0xFFFFFFFF` | RDT-relative offsets except opaque slot 2; zero means no referenced section |
| Camera table | Slot 7 | 32-byte records | Two u16 attribute words, six signed i32 XYZ coordinates, one u32 mask offset; LE, full-width fields |
| Camera-zone table | Slot 8 | 20-byte records | u16 attributes, two u8 camera fields, eight signed i16 X/Z coordinates; LE except u8, full-width fields |
| Zone terminator | End of slot-8 section | Four bytes, `0xFFFFFFFF` | Exact terminator follows complete records |
| Collision header | Slot 6 | Four u32 LE words, all bits | First word counts header plus 16-byte records; remaining words stay opaque |
| Collision record | Slot 6 plus `16 + 16*i` | Four signed i16 then four u16, LE, full-width | Coordinate and opaque attribute values only |

For each required section, the parser bounds it by the next greater in-file section offset, excluding slot 2. It rejects missing sections, short records and inconsistent extents. All 169 camera sections end exactly after their declared records. All 169 zone sections end with the four-byte terminator. Totals are 2,105 cameras, 4,585 camera-zone records and 5,289 candidate collision records.

The collision section has additional bytes after those records in every source. The parser reports that unresolved tail size. It does not call collision rectangles walkable space, assign floor/shape masks, or turn a union of camera zones into a floor plan. Reevengi and lib_bio disagree about the four trailing record words, so their semantics remain unresolved.

## RE3-ROOM-003: initializer procedure directory, without opcode semantics

Status: Candidate for the fingerprint above. No execution, pickup or door outcome is established.

Slot 16 contains a u16 LE relative-offset table. Its first entry is the table's byte size, so the procedure count is `first / 2`. Entries must be strictly increasing, begin after the table and lie inside the bounded section. Each envelope ends at the next entry or section end. All fields use their full 16 bits, mask `0xFFFF`; table entries are relative to the slot-16 section, while exported procedure offsets are RDT-relative.

All 169 sources satisfy these bounds, giving 4,238 procedure envelopes. The parser emits offsets, sizes and SHA256 hashes. It does not walk opcodes or infer reachability, conditions, rewards, acquisition flags, Hard-mode alternatives or complete item lists.

Rejected hypothesis: decode slot 17 as RE2's second SCD directory. It is nonzero on 167 sources and none of those 167 satisfy the same bounded directory contract. Biohazard-utils labels it ESP IDs for RE3 and provides no RE3 `SCDMAIN`; reevengi's header retains the old script label but its initializer reader explicitly returns no run script. Slot 17 remains opaque in this implementation. A zero value is not evidence that a room has no future events.

Reuse decision: existing RE2 procedure-boundary checks informed the bounds, but its decoder also couples RE2 opcodes to presence and completion rules. It is not called or generalized here. Existing ISO traversal/sector helpers can be reused by a catalog tool without changing RE1/RE2 behavior. Shared map tracing should be considered only after this disc's spatial representation and floor/source binding are established.

## Verification and limits

`tests/test_re3_room_data.py` uses synthetic data only. It covers exact-sector alignment, zero-sized objects, malformed sizes, opaque slot 2, the 22-word header, signed geometry, unknown collision fields, nested-table truncation, missing required sections, invalid procedure offsets and slot 17 remaining undecoded. Successful parsing always retains `script_semantics = unresolved` and `completion = unknown`.

The initial increment passed 76 RE3 cases and 570 checks including `tests/test_re2_metadata.py` and `tests/test_rdt_global_id.py`, using the supplied clean test interpreter. No formatter or linter is configured in this checkout.

Runtime integration still needs fresh room identity and loaded-RDT base/extent observations, immutable source witnesses, section relocation rules and difficulty/scenario state. Item and door support then needs RE3 command widths and native constructor layouts, control-flow and condition semantics, acquisition/unlock banks with masks, and earlier/later restoration checks. A first spatial map needs floor/source associations, coordinate projection, true room outlines, stair geometry and door-wall anchors. Source counts do not satisfy these contracts.

## Dated contributions

- 2026-11-05, `gpt-6.1-sol`: authored parser, synthetic tests and this note; independently read the owned disc and compared pinned primary source leads. Executing model verified from the matching local Codex session's latest `turn_context.payload.model`, with `session_meta.payload.id` matching `CODEX_THREAD_ID`. No model identifier was inferred from a catalog or review model.
- Human contribution: supplied owned media, selected Hard mode and set the research/privacy constraints. Parent agent supplied the initial static executable fingerprint and file listing, independently reproduced here.
- No external model review or gameplay endorsement is claimed. The parent owns cross-stream integration and final review.
