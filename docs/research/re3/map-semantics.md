# RE3 native map metadata and projection

[RE3 scope](../../re3.md) · [Room and MAP directories](room-format.md)

Target: Resident Evil 3: Nemesis, PlayStation, USA, SLUS-00923, executable `SLUS_009.23`, SHA256 `2e143418e358b2c99995cdc1a88c387163fb751912c723b755614f38e236bd29`. Hard is the user-selected target, verified separately in [RE3-INPUT-002](hard-start.md#re3-input-002-native-hard-selection-and-control-in-two-rooms). Claims 001/002 are the original Candidate source/copy-execution findings. Claims 003/004 add bounded metadata and two observed native map positions using DuckStation `0.1-12083-g00e299795`.

The tracking blocker is spatial interpretation. RE3-ROOM-004 establishes resource directories but cannot supply actual room outlines. The original increment identifies drawing records; the later increment resolves Candidate native rows, layers and position projection. Room contours, tracker floor identity, visibility and completion still need separate contracts.

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

## RE3-MAP-003: section 1 contains bounded projection anchors

Status: Candidate for the named executable and MAP resource. Static decoding and copied-code checks cover the source corpus; runtime metadata agreement is limited to the two observations in RE3-MAP-004.

Each native MAP record's section 1 begins with eight u32 LE words. The first five are increasing section-relative starts; the remaining three stay opaque. The first start is 32. The interval from the first start to the second contains eight-byte projection anchors, each four signed i16 LE values: map X, map Y, world X origin and world Z origin. The second interval supplies an eight-byte prefix whose bytes 4/5 are the native layered-map indicator and layer count. A zero layer count on an unlayered map remains zero; the decoder does not invent a floor.

`decode_map_layout(data, executable)` extends the numeric primitive export with anchors, raw header words, layer metadata and the ordered native room-remap table. It requires the full executable identity and nine MAP records, checks every record before returning, and bounds anchors independently from drawing rows. Anchor counts are `[42, 29, 14, 24, 19, 12, 13, 42, 29]`. These counts differ from drawing-row counts. A row must exist in both source tables before it can supply a projected position.

The loader at PS1 virtual `0x800713DC..0x8007150C` reads nine record lengths from `[0x800A03AC, 0x800A03D0)`, SHA256 `2e5772821d97f000e3077506f4be340dae23e59ec51d61152bec80d53d5e0a98`. It selects section 1 through the record header. Native projection indexes its anchor array by the remapped room row. These are owned executable locations, not live host addresses.

## RE3-MAP-004: native room remapping and position projection

Status: Candidate general binding contract, with projection/source agreement Confirmed for the two named runtime observations below. Position/story branches, alternate records and layered maps have copied-code validation only.

The original identity between source room ID and drawing-row ID is insufficient. Native code at `[0x80073CCC, 0x80073E7C)`, SHA256 `70eb97ef72547dd4fb3e1cbd989d44c60f803ef5b10fc9dc0060f0dde00fdde1`, handles position/story cases before applying a table. The 49 ordered four-byte rows and sentinel at `[0x800A0430, 0x800A04F8)` have SHA256 `d3026b4e6288a298e0ba5a2bde3758abdfec7af732e9140806ae3f83e010b19b`. Each row contains four u8 values: source stage/room and destination native group/row. Matching mutates the current pair and continues through later rows once. Three early-return cases bypass that table. Raw stages 5/6 fold to 0/1 before table processing; table destinations 5/6 remain native map groups.

`decode_native_map_position(data, executable, ram)` requires explicit MAP/executable bytes and an exact 2 MiB snapshot. The complete executable fingerprint is mandatory before the shared four-window capture check. The [source audit](native-contracts.md) uses that same capture-check implementation, preserving its existing output. The position decoder returns `loaded_room_binding: unchecked` and `campaign_admission: unresolved`; it does not substitute map arithmetic for a loaded-RDT witness or a lifecycle gate.

| Required snapshot field | PS1 virtual address | Width, byte order and mask | Source use |
| --- | --- | --- | --- |
| Stage / room | `0x800D1F76` / `0x800D1F78` | Signed i16 LE each, full `0xFFFF` | Source pair, validated as stage 0..6 and room 0..255 |
| Player X / Z | `0x800CCBF8` / `0x800CCC00` | Signed i32 LE each, full `0xFFFFFFFF` | Position-dependent remaps and projection |
| Lifecycle word | `0x800CC858` | u32 LE, mask `0x00000080` | Select native group plus 7 for the alternate record set; this is separate from difficulty bit `0x100` |
| Remap flag word | `0x800D1FC0` | u32 LE, mask `0x00000001` | Raw stage 4 / room 2 can select row 17 |
| Position-remap flag word | `0x800D1FB8` | u32 LE, mask `0x00800000` | Raw stage 2 / room 23 position split |
| Layer-override flag word | `0x800D1FBC` | u32 LE, mask `0x00004000` | Raw stage 4 / canonical row 3 layer override |
| Previous identifier | `0x800D1F7C` | u16 LE, full `0xFFFF` | Layer override compares raw value `0x0503`; its broader encoding is not established here |

All addresses above are main-RAM virtual addresses. Subtract `0x80000000` for capture offsets. The native flag helper at `0x80078930..0x80078950` reads little-endian words with MSB-first indexed bits; the concrete masks above preserve that convention.

The native position cases use X thresholds -8822 and 800 for source pairs `1/15` and `3/21`. Their right-hand branches select rows 16 and 17 and adjust projection X by +9501 and -9000. Source pair `2/23` uses Z >= -11300 plus the clear position-remap flag to select row 2 before table processing. The layer helper at `[0x80073BC8, 0x80073CCC)`, SHA256 `b4cdd194b38765ce700309db1957aa49b1fea90878eca9388abf636bb3864ccb`, supplies numeric layer categories by native group/row. The story/previous-identifier override is retained separately. These are revision-specific native cases, with no inferred item or puzzle semantics.

The projection interval `[0x80070644, 0x8007074C)` has SHA256 `005ce4d36712bc5f67213422017affaa07532d3ea3a3f7aacd0c23a912ed5db0`. Before native pan, percentage scaling and viewport placement, it computes:

```text
dx = signed32(adjusted world X - anchor world X)
dz = signed32(world Z - anchor world Z)
map X = anchor map X + truncate_toward_zero(dx / 450)
map Y = anchor map Y - truncate_toward_zero(dz / 450)
```

Signed 32-bit subtraction wraps as native `SUBU`; negative division truncates toward zero. Python floor division alone would move negative fractional deltas one map unit. The decoder shares the divisor and position predicates, preserves early returns and ordered aliases, bounds the final record/row/layer, and returns modeled failures without partial positions for unsupported inputs. A native layer is a map-selection category; it has not been established as the tracker's physical-floor identity or floor label.

### Native map witnesses in two rooms

The first observation reuses the verified private `l2-menu-settled` capture from RE3-NATIVE-004. The second used a new private portable instance under `/var/folders/9d/q5n746z953bcs654g_1sqcy80000gn/T/re-map-re3-map-live-20261105-zgl73r0i/`, port 2357, loading the checksum-verified `hard-control-baseline` from RE3-INPUT-002. Before boot and every load, both achievements sections were disabled, accounts/overrides were absent, `ApplyGameSettings=false`, cards were `None`, audio was muted and the black shader was enabled. Preboot/final settings are byte-identical. No user history, game-file changes, guest-memory writes or testing patches were used.

The requested pause-on-start setting did not establish a frozen restored checkpoint: the first debugger observation had already advanced and was excluded from the map comparison. With its persistent GDB connection holding the guest, the test rechecked isolation, invoked native Load Selected State, verified the restored baseline fields and opened the map with native L2 input. Fresh native state completion, decompression and four-window identity were checked before accepting the sample. No game screenshot is published.

| Native sample | Fresh RDT source | World X / Z | Native group / row | Anchor map X / Y | Anchor world X / Z | Projected map X / Y | Observed native pan X / Y |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `l2-menu-settled` | `STAGE1/R101.ARD` | -4842 / -11028 | 0 / 1 | 462 / 370 | -29075 / -28683 | 515 / 331 | -515 / -331 |
| `room-0d-map` | `STAGE1/R10D.ARD` | 13209 / -14515 | 0 / 13 | 572 / 245 | -4994 / -13753 | 612 / 246 | -612 / -246 |

Both samples have one independent RDT header/camera/zone witness and matching selectors. Both load native MAP record 0 at virtual `0x801B1500`. The 36-byte record header and complete drawing/projection sections match the owned source: section 0 is 1928 bytes, SHA256 `9c37062d74cf90962fb7e496aa63df0a3f52910237a5ba4369d1729b5b6b9562`; section 1 is 480 bytes, SHA256 `d8442b7ade9cbd8ace36677ec85b170b4d3227db18cbce54fdd97186e2dc23e2`.

Rejected: require whole-record byte identity. Nine bytes differ in image sections 2/3 in each capture; those differences are retained in the report. They are not silently masked inside the numeric witness. Images are not decoded or exported by this increment.

| Native map diagnostic | PS1 virtual address | Width, byte order and mask | Observed value/use |
| --- | --- | --- | --- |
| Current canonical group / selected map group / room row | `0x800E026A` / `0x800E026B` / `0x800E026C` | u8 each, endian n/a, full `0xFF` | 0 / 0 / 1 and 0 / 0 / 13 |
| Loaded MAP base | `0x800E028C` | u32 LE, full `0xFFFFFFFF` | Cached virtual pointer `0x801B1500` |
| Native pan X / Y | `0x800E023C` / `0x800E0240` | Signed i32 LE each, full `0xFFFFFFFF` | Exact negatives of the projected coordinates in these centered views |
| Native percentage scale | `0x800E0264` | Signed i32 LE, full `0xFFFFFFFF` | 100 in both samples |

The decoder reports pre-pan coordinates. User-selected views, zoom and browsing another native layer can change pan or visibility; the two observed centered views do not establish a universal pan-equality rule. Map-menu captures correctly retain `native-menu-loop-active` rejection evidence and do not become tracker visits.

### Reproduction and additional validation

From the owned MAP and executable established below, call `decode_map_layout(data, executable)` for numeric metadata or `decode_native_map_position(data, executable, explicit_ram)` for a Candidate position. Pair each runtime comparison with the independent RDT/source audit; the map decoder intentionally does not interpret RDT allocation, lifecycle admission, ownership or completion. The original `decode_map_primitives` export remains available.

Private integration evidence is under `/var/folders/9d/q5n746z953bcs654g_1sqcy80000gn/T/re-map-re3-map-binding-20261105-f2ixzm8u/`. `audit.py` runs the owned remapper, layer-selection path and projection instructions through Unicorn 2.1.4. It covers 424 contexts, including all 169 cataloged source IDs with flag alternatives, position thresholds, signed extremes, previous-identifier overrides and alternate map records. All 1,024 copied native calls agree with the decoder; code-hook store predictions and complete before/after 2 MiB RAM comparisons agree for every call. These are copied-code checks, not runtime coverage of those rooms, flags or layers.

`verify.py` independently checks the two native captures, map metadata bytes, projected positions, pan/scale and unique RDT sources. Its two source-audit executions are byte-identical. The earlier eight-capture menu/pause audit also retains its exact SHA256 `53c889e32c375530be44176c439017e7da09dbebc61f0a223f6d85f95abed0cb` after sharing capture validation.

| Binding evidence under the integration directory | Bytes | SHA256 |
| --- | ---: | --- |
| `layout.json` | 560405 | `e9975233c3ec7e865bbb1db24dbe4262e5f4c3bf661f4d7aafbd1725014817b5` |
| `copied-native-audit.json` | 518 | `bb1fbd45eba39c5fc98d332d1eaea442860ed25046838a1033fd3bae7a0d73a5` |
| `runtime-source-audit.json` | 3325 | `65b228405ef33ba673f245cd286b83ad36f9b86b43058d12a929bf37d81cd44e` |
| `verification.json` | 8293 | `521c3232efb527a95aa177bd2ed5a07e510d456a5782d14fa6f5163d778ca755` |

| Evidence under the new private live directory | Bytes | SHA256 |
| --- | ---: | --- |
| `room-0d-map.sav` | 1697287 | `a45eef4bd159748d004e67acdaf13203df4803988e6643aaf74e7d2a1e266db8` |
| `controller.jsonl` | 3757 | `a516712713591610a03af024e05727b17235a8a3e263988368d9d1988277c1e1` |
| `settings-preboot.ini` | 2129 | `4e0f2cc363bfb7dc2707e8db2f0e9e6614b7782fc8d5fc00048470a9cdc5d944` |
| `load-audit.jsonl` | 420 | `a0ccf70932d1feea25a0019832f4db3b003de540a10a3a3eebb4e26e7348fa99` |
| `cleanup.json` | 342 | `c57d4cae72f71621900bb3d36733db3e25ed94bd790958832fdc7ff29bdfa036` |

Retained preparation, launch, controller and load scripts refer to those exact private paths. Reproduction needs fresh process/port checks and explicit path updates. Cleanup matched PID 39024's complete command and listener ownership, closed the debugger client, stopped that process only, verified the launch wrapper exited successfully and confirmed port 2357 free. No native state, RAM, owned executable/disc/BIOS bytes or image enters Git. Checkpoint reversal here does not establish memory-card persistence.

## Reproduction and evidence

The existing [disc inspector](identity.md) and [room catalog](room-format.md#reproduction-and-interface) establish the owned input identity. The exact MAP resource is 634880 bytes at ISO LBA 6807, SHA256 `7182beb90347fe4ea0c2a4db30dff93aaee88b8ef1b633398ffcef6f3d3d1268`. LBA uses the zero-offset single MODE2/2352 track contract of RE3-ID-001.

From the repository root, provide the owned BIN explicitly and write numeric metadata outside Git:

```sh
python3 - '/Users/adamekka/Games/DuckStation/Resident Evil 3 - Nemesis.bin' <<'PY'
import hashlib, json, sys
from pathlib import Path
sys.path[:0] = ['src', 'tools']
from build_item_table import _read_file
from games.re3.map_data import decode_map_layout, decode_map_primitives
from games.re3.room_data import RoomFormatFailure
with Path(sys.argv[1]).open('rb') as image:
    executable = _read_file(image, 288380, 868352)
    data = _read_file(image, 6807, 634880)
assert hashlib.sha256(data).hexdigest() == '7182beb90347fe4ea0c2a4db30dff93aaee88b8ef1b633398ffcef6f3d3d1268'
result = decode_map_primitives(data, executable)
assert not isinstance(result, RoomFormatFailure), result
Path('/tmp/re3-map-primitives.json').write_text(json.dumps(result, indent=2) + '\n')
layout = decode_map_layout(data, executable)
assert not isinstance(layout, RoomFormatFailure), layout
Path('/tmp/re3-map-layout.json').write_text(json.dumps(layout, indent=2) + '\n')
PY
```

The parser independently checks the executable; these fixed extents are reproduction details for the pinned owned image, not production defaults. The primitive JSON has SHA256 `aeaae3c1cc938a413cda6c3e44138aa1f372b024a1c37c3c345d53bf7234776f`, matching the original draft run and parent rerun byte-for-byte. The added layout JSON matches `layout.json` in the RE3-MAP-004 evidence table.

Private discovery evidence is under `/var/folders/9d/q5n746z953bcs654g_1sqcy80000gn/T/re-map-re3-map-20261105-4hn9iq7k/`. Parent evidence is under `/tmp/re-map-re3-map-integration-20261105/`, containing the numeric export, `audit.py` and `audit.json`. The audit script SHA256 is `1ed1c7f8ef7a1cfc9a136742504e469295ce2b2a675a690303d7c49fbd4e2d2d`; report SHA256 is `b28f1a2c6b6477787560f1e125dcf2c03b1e04c78522a6a908abf77fd7083df4`. Temporary evidence may expire; hashes do not replace retained bytes.

The parent used Unicorn 2.1.4 to execute the exact renderer and its header helper once for each of the 793 owned primitives, with synthetic zero pan, 100% scale and viewport center `[160, 120]`. All four output vertices matched the decoded directed edges after that translation and native halfword storage. The shared code-hook store auditor predicted every write; complete 2 MiB before/after RAM comparisons matched all predicted stores. No memory-write hook or substituted renderer was used. These are copied-code checks, not gameplay observations, and do not validate conditional selection, native map acquisition or world projection.

## Tests and remaining limits

Run with the [test environment](../../testing.md#python-test-environment):

```sh
python3 -m pytest -q tests/test_re3_map_binding.py tests/test_re3_map_data.py tests/test_re3_native_contracts.py tests/test_re3_room_data.py tests/test_re3_room_catalog.py tests/test_re3_disc_identity.py
```

All 267 focused tests pass, including the original 25 primitive cases and 43 binding cases. They cover exact executable/capture gating, independent table bounds, signed origins, native truncation, early returns, ordered/chained remaps, raw-stage folding, position/story thresholds, layer/previous-state overrides, alternate records and earlier-snapshot reversal. The original primitive tests retain inclusive/reversed endpoints, opaque styles, aliases, group selection, unconsumed tails and no partial export on later failure. They contain no owned executable, RAM or artwork bytes.

A useful tracker map still needs physical floor identity/labels, the native selection conditions for both drawing groups and true outline/door/stair geometry. Candidate row/layer/projection contracts now exist, with only two native positions observed. Textured quads may include artwork or overlays; their rectangles are not automatically room contours. General lifecycle admission, ordinary room reentry and item/door/story interpretation remain unresolved. No runtime profile, UI, persistence or user exploration changed. Visits and completion remain unresolved.

## Contributions and review

- 2026-11-05; human user; supplied the owned media, requested parallel research and selected Hard.
- 2026-11-05; implementation delegate, `gpt-6.1-sol` verified by returned run metadata; inspected the owned map/executable and authored the initial decoder and synthetic tests. Its run stopped for exhausted workspace credits before review, documentation or commit.
- 2026-11-05; Codex root, exact runtime model `gpt-6.1-sol`; recovered the draft, checked native count/stride and signed-edge instructions, shared the revision fingerprint, reran source/test checks, executed the copied renderer audit, wrote this record and completed integration review. Review covered bounds, aliases, identity gating, opaque fields, failure behavior and separation from runtime map claims. Configured external reviewers were unavailable; no independent external endorsement or gameplay validation is claimed.
- 2026-11-05; Codex root, exact runtime model `gpt-6.1-sol`; authored RE3-MAP-003/004, traced remapping/anchors/layers/projection, added bounded metadata and snapshot decoders, shared capture witnesses, checked 424 copied-code contexts and two native map positions, and verified private cleanup. Local review covered address spaces, masks, ordered control flow, signed arithmetic, independent bounds, raw layer limits, capture identity, input preservation and unresolved admission. No model agreement substitutes for gameplay observations.
- 2026-11-05; independent internal source checker, `gpt-6.1-sol` verified from its matching session metadata and latest turn context; found no actionable issues after checking remap order/early returns, raw-stage folding, flag masks, layer selection, signed projection, parser bounds and shared capture checks. Independently verified the executable fingerprint and 49-row remap table, and inspected the copied-code report and both retained projection pairs. It did not rerun tests or emulator experiments, change files or establish gameplay behavior.
- 2026-11-05; external review attempt, `gemini-3.8-flash` at high reasoning through Antigravity; the provider returned no content for 15 minutes and T3 stopped the run. Claude Opus 5.5 was disabled in the provider inventory. Neither supplied a completed review or an endorsement.
