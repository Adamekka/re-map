# RE3 native map drawing primitives

[RE3 scope](../../re3.md) · [Room and MAP directories](room-format.md)

Target: Resident Evil 3: Nemesis, PlayStation, USA, SLUS-00923, executable `SLUS_009.23`, SHA256 `2e143418e358b2c99995cdc1a88c387163fb751912c723b755614f38e236bd29`. Hard is the user-selected target; this work does not establish runtime difficulty. All findings remain Candidate. No DuckStation version was tested in this workstream.

The tracking blocker is spatial interpretation. RE3-ROOM-004 establishes resource directories but cannot supply actual room outlines. This increment identifies the records consumed by the native map renderer. It does not bind them to rooms or floors or authorize their visibility.

## RE3-MAP-001: directory words count two groups of textured quads

Status: Candidate for the exact executable and `CD_DATA/ETC/MAP_U.MAP` fingerprint documented in RE3-ROOM-004. Source inspection, owned-data agreement and copied execution only.

The two previously opaque u16 directory words count successive groups of 12-byte drawing records. The native row loop at PS1 virtual `0x800703BC..0x800705D0` reads both counts, advances the drawing pointer by 12 and calls `0x8007116C` for each admitted primitive. It applies separate conditional checks before each draw. Those checks are not interpreted by this decoder.

| Field | Address space and offset | Width, byte order and mask | Meaning used here |
| --- | --- | --- | --- |
| Group counts | Section 0 plus `8 + 8*row`, then `10 + 8*row` | Two u16 LE, each `0xFFFF` | Successive drawing-record counts |
| Texture endpoints | Drawing record bytes `0..3` | Four u8, endian n/a, each `0xFF` | `u0, v0, u1, v1`, inclusive endpoints |
| Destination origin | Drawing record bytes `4..7` | Two signed i16 LE, each full `0xFFFF` | Native map X/Y before pan and zoom |
| Style | Drawing record bytes `8..11` | Four u8, endian n/a, each `0xFF` | Preserved without assigning visibility or completion semantics |

`decode_map_primitives(data, executable)` verifies the actual executable SHA256 before calling the shared bounded directory decoder. It preserves row order, aliases and both groups. Counts must fit the next distinct payload offset or section end. Unconsumed payload bytes remain explicit; a zero-count alias is not evidence of an empty room. The numeric export contains no texture pixels, image payloads, room ownership or visit facts.

The owned resource yields 427 group-0 and 366 group-1 primitives across nine records and 363 directory rows. These are drawing counts, not room/floor coverage. The original directory-only export and its rejection evidence remain valid; the new interpretation supplies additional evidence for the two count words.

## RE3-MAP-002: native edges retain inclusive and reversed endpoints

Status: Candidate. Native map coordinates have X increasing right and Y increasing down in the drawing routine; their relation to room-world coordinates remains unresolved.

The renderer at PS1 virtual `0x8007116C..0x800713DB` loads the texture endpoints as unsigned bytes and the destination origin as signed halfwords. At `0x800711BC..0x80071204` it computes:

```text
width  = u1 - u0 + 1
height = v1 - v0 + 1
native edges = [x, y, x + width, y + height]
```

The differences remain signed integer arithmetic. The routine later applies pan, percentage scaling and viewport centering before writing GPU vertex halfwords. The exported edges precede those transformations; they are directed edges rather than normalized rectangles.

Rejected hypothesis: wrap a reversed endpoint difference into an unsigned 8-bit width or sort the edges into an ordinary rectangle. Record 3, row 0 has a real primitive at MAP file byte 190784 with native edges `[392, 220, 364, 227]`, width -28. Either transformation changes its geometry. RE2 rectangle assumptions cannot be imported here.

The renderer's 624 bytes, executable virtual interval `[0x8007116C, 0x800713DC)`, have SHA256 `66310d722fe83b92bd46ab9941c1a109120b2317c8d300396d41c87f6b6fb280`. These addresses identify owned executable code, not live state fields or host-process pointers. The helper at virtual `0x8008F654` initializes the GPU primitive header and is included in the copied execution.

## Reproduction and evidence

The existing [disc inspector](identity.md) and [room catalog](room-format.md#reproduction-and-interface) establish the owned input identity. The exact MAP resource is 634880 bytes at ISO LBA 6807, SHA256 `7182beb90347fe4ea0c2a4db30dff93aaee88b8ef1b633398ffcef6f3d3d1268`. LBA uses the zero-offset single MODE2/2352 track contract of RE3-ID-001.

From the repository root, provide the owned BIN explicitly and write numeric metadata outside Git:

```sh
python3 - '/Users/adamekka/Games/DuckStation/Resident Evil 3 - Nemesis.bin' <<'PY'
import hashlib, json, sys
from pathlib import Path
sys.path[:0] = ['src', 'tools']
from build_item_table import _read_file
from games.re3.map_data import decode_map_primitives
from games.re3.room_data import RoomFormatFailure
with Path(sys.argv[1]).open('rb') as image:
    executable = _read_file(image, 288380, 868352)
    data = _read_file(image, 6807, 634880)
assert hashlib.sha256(data).hexdigest() == '7182beb90347fe4ea0c2a4db30dff93aaee88b8ef1b633398ffcef6f3d3d1268'
result = decode_map_primitives(data, executable)
assert not isinstance(result, RoomFormatFailure), result
Path('/tmp/re3-map-primitives.json').write_text(json.dumps(result, indent=2) + '\n')
PY
```

The parser independently checks the executable; these fixed extents are reproduction details for the pinned owned image, not production defaults. The resulting JSON has SHA256 `aeaae3c1cc938a413cda6c3e44138aa1f372b024a1c37c3c345d53bf7234776f`, matching the original draft run and parent rerun byte-for-byte.

Private discovery evidence is under `/var/folders/9d/q5n746z953bcs654g_1sqcy80000gn/T/re-map-re3-map-20261105-4hn9iq7k/`. Parent evidence is under `/tmp/re-map-re3-map-integration-20261105/`, containing the numeric export, `audit.py` and `audit.json`. The audit script SHA256 is `1ed1c7f8ef7a1cfc9a136742504e469295ce2b2a675a690303d7c49fbd4e2d2d`; report SHA256 is `b28f1a2c6b6477787560f1e125dcf2c03b1e04c78522a6a908abf77fd7083df4`. Temporary evidence may expire; hashes do not replace retained bytes.

The parent used Unicorn 2.1.4 to execute the exact renderer and its header helper once for each of the 793 owned primitives, with synthetic zero pan, 100% scale and viewport center `[160, 120]`. All four output vertices matched the decoded directed edges after that translation and native halfword storage. The shared code-hook store auditor predicted every write; complete 2 MiB before/after RAM comparisons matched all predicted stores. No memory-write hook or substituted renderer was used. These are copied-code checks, not gameplay observations, and do not validate conditional selection, native map acquisition or world projection.

## Tests and remaining limits

Run with the [test environment](../../testing.md#python-test-environment):

```sh
python3 -m pytest -q tests/test_re3_map_data.py tests/test_re3_room_data.py tests/test_re3_room_catalog.py tests/test_re3_disc_identity.py
```

All 174 focused tests pass, including 25 new primitive cases. Synthetic tests cover exact executable gating, signed origins, inclusive/reversed endpoints, opaque style bytes, group selection, zero-count aliases, unsorted rows, unconsumed tails, count overflow, truncation and failure in a later record without partial export. They contain no owned executable or artwork bytes.

A useful tracker map still needs room/floor associations, the native selection conditions for both groups, world-to-map projection and true outline/door/stair geometry. Textured quads may include artwork or overlays; their rectangles are not automatically room contours. No runtime profile, UI, persistence or user exploration changed. Visits and completion remain unresolved.

## Contributions and review

- 2026-11-05; human user; supplied the owned media, requested parallel research and selected Hard.
- 2026-11-05; implementation delegate, `gpt-6.1-sol` verified by returned run metadata; inspected the owned map/executable and authored the initial decoder and synthetic tests. Its run stopped for exhausted workspace credits before review, documentation or commit.
- 2026-11-05; Codex root, exact runtime model `gpt-6.1-sol`; recovered the draft, checked native count/stride and signed-edge instructions, shared the revision fingerprint, reran source/test checks, executed the copied renderer audit, wrote this record and completed integration review. Review covered bounds, aliases, identity gating, opaque fields, failure behavior and separation from runtime map claims. Configured external reviewers were unavailable; no independent external endorsement or gameplay validation is claimed.
