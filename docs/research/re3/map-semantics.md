# RE3 native map metadata, projection and source contours

[RE3 scope](../../re3.md) · [Room and MAP directories](room-format.md)

Target: Resident Evil 3: Nemesis, PlayStation, USA, SLUS-00923, executable `SLUS_009.23`, SHA256 `2e143418e358b2c99995cdc1a88c387163fb751912c723b755614f38e236bd29`. Hard is the user-selected target, verified separately in [RE3-INPUT-002](hard-start.md#re3-input-002-native-hard-selection-and-control-in-two-rooms). Claims 001/002 are the original Candidate source/copy-execution findings. Claims 003/004 add bounded metadata and two observed native map positions using DuckStation `0.1-12083-g00e299795`. Claims 005/006/007 add source contours, selection counterexamples and heading interpretation without new gameplay observations.

The tracking blocker is spatial interpretation. RE3-ROOM-004 establishes resource directories but cannot supply actual room outlines. Later increments resolve Candidate native rows, layers, position projection and per-quad source-texel contours. Room ownership, tracker floor identity, visibility and completion still need separate contracts.

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

## RE3-MAP-005: packed texture planes supply separate source contours

Status: Candidate for the pinned executable and MAP fingerprint. Source inspection, owned-data comparisons and copied renderer execution only. This increment starts no emulator and adds no gameplay validation.

The atlas packs two independent two-bit planes into four-bit palette indices. Treating every nonzero nibble as occupied includes texels belonging to the other plane. The native renderer at `0x80071354..0x800713A8` computes:

```text
effective_variant = 0 if style[0] == 7 else requested_variant
relative_clut_row = 8 * (style[1] & 1) + style[0] + effective_variant
texture_page_x_words = (((style[1] >> 1) + 7) & 15) * 64
texture_page_y_rows = 256
CLUT word position = [304, 490 + relative_clut_row]
```

Group 0 requests variants `{0, 2, 5}` through `0x8007275C..0x80072AC4`. Group 1 requests `{0, 2}` through the Boolean conversion and shift at `0x80070530..0x8007053C`. Style kind 7 forces effective variant zero at `0x800711A4..0x800711B4`; requested variants remain separately identified in the export. All 14 actual group/style combinations stay within main CLUT rows `0..15` for their requested variants.

These are little-endian file fields and VRAM word coordinates, not live PS1 RAM addresses:

| TIM field | Width and mask | Supported source contract |
| --- | --- | --- |
| Magic and flags | Two u32 LE, full width | `16`, `8`, a four-bit indexed TIM with CLUT |
| Block size | u32 LE, full width | Exactly `12 + 2 * word_width * height` |
| Block rectangle | Four u16 LE, each `0xFFFF` | X/Y, word width and row height |
| Main CLUT | Sixteen rows of sixteen u16 LE entries | File X 304; upload Y 490 |
| Overlay CLUT | One row of sixteen u16 LE entries | File X 304; upload Y 506 |
| Main image | 64 or 128 words by 256 rows | Upload X/Y replaced with `[448, 256]` |
| Overlay image | 64 words by 40 rows, file Y 216 | Upload X replaced with 512; Y becomes `256 + 216` |

The loader resets page/CLUT slots at `0x800714CC..0x800714F8`. Main upload `0x800784E0..0x800785E4` precedes overlay upload `0x8006EBEC..0x8006ECB0`; TIM block interpretation is at `0x8008DF40..0x8008E058`. Palette X is preserved. Both palette Ys, both image Xs and main image Y are overwritten. Original rectangles remain in numeric provenance. The overlay replaces overlapping words in the main image's second page. Record 2's narrower main image leaves part of that page unloaded; absent words are an explicit failure, never transparent padding.

Within each VRAM u16, the nibble is `(word >> (4 * (u & 3))) & 15`. Main CLUT rows `0..7` repeat by the lower two bits; rows `8..15` repeat by the upper two bits. The decoder checks full-word repetition before sampling. Only CLUT word zero is transparent; `0x8000` still contributes coverage. These addressing and transparency rules agree with the pinned DuckStation [GPU register definitions](https://raw.githubusercontent.com/stenzek/duckstation/00e299795/src/core/gpu_types.h), `GPUDrawModeReg` and `GPUTexturePaletteReg`, and [software rasterizer](https://raw.githubusercontent.com/stenzek/duckstation/00e299795/src/core/gpu_sw_rasterizer.inl), `ShadePixel` lines 90–96 and 116–117.

`extract_map_contours(data, executable)` in [the offline exporter](../../../tools/re3_map_geometry.py) first uses the mandatory full executable gate and bounded layout decoder. It checks exact TIM section consumption, supported dimensions and palettes before returning numeric coverage. Each quad keeps its own requested/effective palette variants, CLUT row, plane shift, nontransparent-class membership, coverage rings and separate shade-class rings. Class zero membership is computed from the supplied palette too. The shared [contour tracer](../../../tools/map_geometry.py) preserves components, holes and exact cell area. No colors or image payloads are exported.

The effective CLUT row selects the plane after variant addition. Record 0/7, row 0, group 0, primitive 1 has style `[4, 0, 0, 0]`: requested variants 0/2 use the lower plane, but variant 5 addresses row 9 and uses the upper plane. Its area changes from 440 to 23 cells. Style parity alone is insufficient. For actual kind-0 draws, variant 5 hides class 2 and retains classes 1/3; other supported combinations retain classes 1/2/3. These memberships come from the actual CLUT, not hardcoded role or clearance rules.

The renderer stores upper UV endpoints plus one into byte fields at `0x80071300..0x80071350`. Reversed endpoints and upper endpoints of 255 therefore remain `unresolved-directed-or-wrapping-uv`; the exporter does not normalize them or invent GPU interpolation. The owned resource has one reversed quad and no upper endpoints of 255. Coverage describes nontransparent source texels before clipping, modulation and blending, not final framebuffer visibility or room ownership.

### Source and copied-code verification

The owned export contains 792 decoded quads and one explicitly unresolved quad, retaining all 427 group-0 and 366 group-1 records. Its 2,010 supported palette variants matched an independent, earlier sampler in occupied cells, exact directed unit boundary edges and signed area. Another 5,729 shade contours matched their sampled class cells. Of 426 forward group-0 quads, 269 variant-zero masks are smaller than their rectangles.

Unicorn 2.1.4 executed the exact renderer for all 2,013 quad/requested-variant combinations, including the reversed quad. GPU CLUT/page registers and all four UV pairs matched the formulas and byte storage above. The shared code-hook store auditor predicted every write; complete 2 MiB before/after comparisons matched. No memory-write hook, substituted renderer or guest-game patch was used. Copied execution does not confirm gameplay admission or geometry ownership.

Private evidence is under `/var/folders/9d/q5n746z953bcs654g_1sqcy80000gn/T/re-map-re3-contours-integration-20261105-_f9fzukh/`. `verify.py` repeats the numeric sampler and copied-code comparisons. Discovery and selection evidence remain under `/tmp/re-map-re3-contours-20261105-Xb0Fz0/` and `/tmp/re-map-re3-contour-contract-20261105-NyxDb3/`; original files were not overwritten.

| Integration evidence | Bytes | SHA256 |
| --- | ---: | --- |
| `contours.json` | 33439459 | `db2dda034593c17f809245e829e184cf7551d4b96d4f36c3895a7344311039cd` |
| `source-audit.py` | 8248 | `a90e11047865e31af72b050af6c50f638af05dd8ad185dc023b3f44ce91c02b8` |
| `mask-report.json` | 425592 | `d4c1b28234ed3e19d2ade8c6608937de697e6718c5775b9b9f8399c861f0c099` |
| `verify.py` | 6877 | `1e52b66b8ccd1937c39d6ce3b58c4a3292e7396deb225a657729f7e321b55b8a` |
| `verification.json` | 1126 | `072346992155ec65a2828a9f143f33c8f4e7fd77008a90cdfec71ef4bf5e97c0` |

## RE3-MAP-006: static quad unions do not establish room ownership

Status: Candidate source interpretation and retained-capture comparisons. The new exporter preserves alternatives; it does not implement conditional draw admission or tracker visibility.

At `0x80071ACC..0x80071B40`, current native map key `0x0001` and signed i8 at PS1 virtual `0x800CCBCD` below 3 exclude row-1 primitives 1/2. Values at least 3 exclude primitive 0 instead, subject to earlier filters. The source masks differ: primitive 0 covers 2,961 cells, while the later pair covers 2,416. At `0x80071B44..0x80071B68`, current key `0x000D` excludes row-13 primitive 1. Primitive 0 covers 2,144 cells with 12 corners; including the connector yields 2,444 cells with 16 corners. An unconditional union changes the room's extent.

Row 27 also contains a 323-cell outline with a 1,848-cell hole, a separate fill matching that hole exactly, and fragmented detail. Source selection at `0x80071C58..0x80071CB4` distinguishes alternatives. Neither all of group 0 nor one palette class automatically defines a floor or door.

The two retained map captures in RE3-MAP-004 have signed byte values 1 and 0 respectively. Their projected points lie inside the source-selected 2,961-cell and 2,144-cell masks. Both native visit bits are set and map-acquisition bit zero is clear. These observations do not establish tracker visit admission, physical floor identity, general shape ownership or new gameplay coverage. The private `retained-point-checks.json` has SHA256 `ac6b676429cb71711dce535b67f954db7c14faa2f1240c19010fa15477fc131c`; `contract-report.json` has SHA256 `71821f93e0c9fc2f37533d60cf74093ffa6fdc28f848089dc21dedddde070c05`.

## RE3-MAP-007: yaw phase determines heading and native marker sector

Status: Candidate general conversion for the named revision. Source/copy execution and the retained controlled observations corroborate the rule. Further cardinal, reverse-wrap and other-group gameplay observations remain untested. This increment starts no emulator.

Raw player facing is a u16 LE at PS1 virtual `0x800CCC32`, capture offset `0xCCC32`, full mask `0xFFFF`. Its orientation phase uses mask `0x0FFF`; higher stored bits are preserved diagnostically. Raw values above 4095 are valid, not a reason to reject a capture.

The actor forward step reads yaw at actor byte `+0x6E`, rotates the local movement vector at `+0xC0`, then adds the result to world X/Z at `+0x34`/`+0x3C`. The pure-MIPS yaw-only matrix has first column `[cos(theta), 0, -sin(theta)]` with `theta = phase * 2*pi/4096`. The existing map projection has differential `[world X, -world Z]`, so yaw zero points right and increasing yaw rotates clockwise on the map:

```text
phase = raw_facing_u16 & 0x0FFF
heading_degrees = (90 + phase * 360 / 4096) % 360
native_arrow_sector = ((raw_facing_u16 + 0x100) >> 9) & 7
```

Heading zero points up. Raw phases `0`, `1024`, `2048`, `3072` point right, down, left, up respectively. Native map initialization rounds to eight sectors and writes texture U `sector * 8` into both marker buffers at PS1 virtual `0x801AFE80` and `0x801AFEA8`. Their edge V coordinates are 240/248. No stage, row or camera rotation appears in the traced initialization/placement path. All nine owned MAP records have matching numeric marker coverage signatures; this is not gameplay confirmation of other map contexts.

| Owned source | PS1 virtual interval, end exclusive | SHA256 |
| --- | --- | --- |
| Actor forward step | `0x80017DF0..0x80017EAC` | `54c9a1b05bd5d60c955e3a1ea21b1dfa69115549e4fef5ee93ed08a0aaccc108` |
| Marker initialization | `0x8006F0F4..0x8006F174` | `76aba3c0a430c6d9aab7f2237f693c31607bdcffbbcdc10d107dd72d8cd0f483` |
| Marker placement | `0x80070608..0x8007085C` | `aea441385ccd7d13e272d50a121883d4692b2fe23cb7957b178475be6787ca6b` |
| Pure-MIPS matrix | `0x800894E4..0x80089770` | `b2ceb5cbcb3d21497ca1bce6abbaeb2841463522aebcc0711487c836f1e2e3ac` |
| Optimized movement matrix | `0x8008A0E4..0x8008A2F4` | `acb0b00cb3dbae11866b320bd8978d6c644d6391e3c0812fba535a1e657bba5c` |
| Trig table | `0x800A41B0..0x800A81B0` | `b40c47b014ca8650c539760fd4c519cabce6f091628566ca0dd22318bb2c5b7a` |

The [snapshot decoder](../../../src/games/re3/map_data.py) now returns `raw_facing_u16`, `player_heading_degrees` and the computed `native_arrow_sector` after its existing executable, capture and map-context checks. The sector predicts fresh native marker initialization; cached marker packets can retain an earlier facing until the map reopens. These numeric fields do not admit gameplay or establish a loaded-room witness. The [shared heading formula](../../../src/games/player_heading.py) also serves RE1 and RE2, with explicit offset/direction parameters. RE1 retains its complete-halfword input check; RE2 retains its existing profile orientation and coherent-pose read. RE2 profile loading rejects missing or malformed direction and nonfinite/nonnumeric offsets before polling; required settings receive no fallback.

### Retained and copied-code comparisons

The retained first-room forward observation at raw facing 2048 moved `[-1184, 0]` in world X/Z, exactly map-left at 270 degrees. The independent second-room pair moved `[535, 1306]`, net heading 22.276 degrees, while final facing 3328 predicts 22.5 degrees. That pair includes an earlier turn, and collision can change net displacement; it is corroboration rather than an exact facing measurement. Stationary Right turning from raw 3888 to 4448 preserves position and crosses the phase boundary clockwise by 49.21875 degrees. Earlier/later restores retain their corresponding raw yaw and heading. Both retained native maps agree with the predicted marker U at their sampled facing.

The parent compared the production decoder with all eleven retained heading captures and independently checked the six source hashes. Copied execution covered all 4,096 orientation phases plus seven high-bit cases through the pure-MIPS matrix, and 38 marker initialization cases around rounding/wrap boundaries. Every call passed the code-hook store audit and complete 2 MiB before/after comparison. Maximum direction discrepancy from the fixed-point matrix was 0.009569 degrees. All 65,536 unsigned yaw values also agree with the nearest-sector interval `[-22.5, 22.5)` degrees. The optimized GTE movement routine was inspected, not executed. No memory-write hook, substituted matrix, guest patch or new gameplay observation was used.

Private discovery evidence is under `/tmp/re-map-re3-heading-20261105-415748fee063/`. Parent integration evidence is under `/var/folders/9d/q5n746z953bcs654g_1sqcy80000gn/T/re-map-re3-heading-integration-20261105-z3z70zzm/`; copy its `verify.py` into a fresh private directory before rerunning, with the supplied test interpreter and retained owned inputs. Original reports were not overwritten.

| Heading evidence | Bytes | SHA256 |
| --- | ---: | --- |
| Discovery `audit.py` | 9942 | `fe856d4c29c7f4ae6f1ef7e1f16fdc3de11733d9a62edcbae51bc9bff68caa2f` |
| Discovery `report.json` | 11864 | `752d029b9f462008bb402bf457613914912ea7511f5bdf5a3304aa397043c771` |
| Parent `verify.py` | 5650 | `e6152719cca17825d6924ef75fc289f3f429cda862248876c37d69281e9ae4e8` |
| Parent `verification.json` | 3426 | `83b5045b51d17182150a5cabbeadd72a35ed0fd264affc14568d6f4d534e040d` |

## RE3-MAP-008: section 1 supplies ordered group-0 quad requirements

Status: Candidate source contract for the named revision. This adds bounded static metadata, not runtime selection or tracker visibility.

The group-0 caller at PS1 virtual `0x800703F8` invokes `0x80071878` with a map group, row index and primitive index. Its metadata prefix uses the loaded section-1 pointer at `0x800E0274` (u32 LE), adds header word 3 at section byte `+12`, and scans four-byte entries. Each entry is `(row:u8, primitive:u8, flag_index:u8, bank_selector:u8)`. A first row byte `0xFF` terminates the table; the remaining sentinel bytes are ignored. Header word 4 bounds the static decoder's table. A non-sentinel entry crossing that bound or a missing sentinel produces an explicit `map-conditions` failure without partial output.

Every nonzero selector uses PS1 virtual flag-bank base `0x800D1FA0`; zero uses `0x800D20CC`. [Shared MSB-first addressing](../../../src/games/bit_flags.py) returns `base + 4*(index//32)` and mask `0x80000000 >> (index%32)`. The native helper reads that u32 word little-endian. Duplicate targets remain ordered and separate: all matching requirements must be set. Table entries need not identify a called row/quad; the export retains their unsigned indices without inferring ownership.

The native map-acquisition bank at `0x800D2124` uses the same indexing with the invocation's unsigned stage byte. A set acquisition bit bypasses only this metadata prefix. Later shape conditions and the caller's row visibility still apply. Acquisition, native visibility and tracker visits remain separate. The static export does not evaluate those bits or read `0x800E0274` from a capture.

The displayed group is a caller argument from map-work byte `0x800E026B`; it can differ from current-location group byte `0x800E026A`. Current-location row is byte `0x800E026C`. These are u8 values with full mask `0xFF`. A future loaded-map selector needs an explicit source witness; predicting the current room's record does not bind a browsed map's metadata.

The [condition decoder](../../../src/games/re3/map_conditions.py) requires the actual pinned executable, then reuses the bounded layout decoder. It exports nine ordered tables with absolute MAP byte offsets, raw selectors, unsigned indices and resolved flag word/mask pairs. The owned input has nine requirements: three in record 0, five in record 1 and one in record 4, all with selector 1. Empty tables remain empty, including alternate records 7/8. No native predicate families, selected contours, room union, floor identity, gameplay admission, visit or clearance state is added.

| Owned source | PS1 virtual interval, end exclusive | SHA256 |
| --- | --- | --- |
| Metadata prefix | `0x80071878..0x80071994` | `4ebd9432e152a3ee9ee346c4c7a2e18b58336ac87e334e4fb0c6cce05f8e8057` |
| Complete group-0 admission routine | `0x80071878..0x8007275C` | `4ea7fcf3da59365e4b26ad4ea7eba605b4eb30217676193b9df46f0ddb37deb2` |
| MSB-first bit helper | `0x80078930..0x80078954` | `fe32913d8f052205d92af65e011e16c0a1e58bfbfda89f9807ad09c0f5f17d8a` |

Parent integration evidence is under `/tmp/re-map-re3-conditions-integration-20261106-nzKSJM/`. Its verifier checked the owned input hashes, compared every table extent, terminator and requirement with the independent source catalog, and repeated the new decoder byte-identically. Existing primitive and layout exports retain their published hashes. Copy `verify.py` into a fresh private directory before rerunning; pass executable, MAP, independent catalog and output paths explicitly. No emulator, raw-RAM export, source texture or user history was used by this increment.

| Integration evidence | Bytes | SHA256 |
| --- | ---: | --- |
| `conditions.json` | 4367 | `ba8a2b83420a6d8bc6be241e7ebf9a2e6de9a38a088b3a0fb3c8734325db0aa0` |
| `verify.py` | 3289 | `a1732a11ea83838ad544e0281142777e63a978006ff4f59bc54ce837d7b9169b` |
| `verification.json` | 759 | `2a50b72e23914b9bdad13e38e41018281db77b8e4cd7610328436e058296d4df` |

## RE3-MAP-009: bind the loaded source before evaluating group-0 shapes

Status: Candidate source contract and retained-snapshot comparison for the named revision. This evaluates the native group-0 predicate, not actual row visibility, room ownership or tracker visits. No new emulator observation was made by this implementation increment.

The [snapshot selector](../../../src/games/re3/map_selection.py) requires explicit MAP bytes, the actual pinned executable, exactly 2 MiB of captured RAM with the existing four code witnesses, and a selected record index 0–8. It never chooses a record from the current room or a matching fallback. Records 7/8 use native group arguments 0/1. The selected group must equal map-work AB, while current-location AA/AC can describe another group/row when browsing.

| Snapshot field, PS1 virtual address | Width, byte order and mask | Interpretation in this contract |
| --- | --- | --- |
| `0x800E026A`, `0x800E026B`, `0x800E026C` | Each u8, `0xFF` | Current group, displayed group, current row |
| `0x800E028C` | u32 LE, `0xFFFFFFFF` | Loaded record pointer CC |
| `0x800E0274` | u32 LE, `0xFFFFFFFF` | Loaded section-1 pointer B4 |
| `0x800CCBCD` | i8, raw mask `0xFF` | Opaque signed phase; thresholds 3/4/9/10 |
| `0x800E0278` | u16 LE, `0xFFFF` | Native overlay/subview selector |
| `0x800D2124` | u32 LE, stage mask `0x80000000 >> native_group` | Acquisition bypass of metadata only for supported groups 0–6 |

CC and B4 must be aligned cached PS1 RAM pointers; unsupported address aliases are rejected without masking. B4 must equal CC plus the validated source section-1 offset. The complete contiguous source prefix from the record header through the bounded requirement table's end, given by section-1 header word 4, must match captured bytes. This checks the section-0 directory and quad bytes used by the caller as well as the requirement table. Separate header and section-1 comparisons would leave geometry unchecked. Mutable image sections are outside the witness. Unsupported pointers, mismatched source bytes, mixed/pending browse state or counts exceeding 256 rows or group-0 quads produce explicit failures without partial results. Binding failure is not evidence of invalid gameplay or an unvisited room; map buffers can be absent or retained outside the map menu.

The source loader predicts `AB + 7` when `0x800CC858 & 0x80`, otherwise AB. That prediction describes a fresh load, not a stored loaded-record identity. The selector instead checks the explicitly requested source bytes. It can therefore evaluate an intact retained record even if the current variant flag would select another record on reload. No raw-stage 5/6 folding occurs here: AB is already the native selected group.

All nine owned headers and bounded prefixes are distinct. Their prefix lengths, in record order, are `2432, 3272, 880, 1304, 1268, 688, 724, 2180, 2648` bytes. Both retained map snapshots from RE3-MAP-004 match record 0 at CC `0x801B1500`, B4 `0x801B1CAC`. This corroborates that source witness in those two situations, not other records, browsing transitions or general runtime admission.

The [immutable predicate families](../../../src/games/re3/map_shape_predicates.py) retain 31 source conditions with their native instruction ranges. One evaluator handles equality, signed comparison, MSB-first flag tests, conjunction, disjunction and negation. Matching metadata requirements from RE3-MAP-008 are conjunctive unless the selected group's acquisition bit is set. Overlay and early shape families then apply. System mask `0x80` bypasses only the late families for groups 0/1, never metadata, overlay or early exclusions. Groups 5/6 have no extra shape families; their metadata still applies. The signed phase's purpose and physical floor meaning remain unresolved.

The following masks combine the fixed predicate dependencies per u32 LE word. Individual indices, bank bases and source ranges remain in the immutable families; [RE3-MAP-008](#re3-map-008-section-1-supplies-ordered-group-0-quad-requirements) defines metadata addressing. These are opaque source conditions, not named acquisition or puzzle claims.

| PS1 virtual word | Used mask |
| --- | --- |
| `0x800CC858` | `0x00000080` |
| `0x800D1FA0` | `0x20040000` |
| `0x800D1FA4` | `0x00000100` |
| `0x800D1FB0` | `0x00040004` |
| `0x800D1FB4` | `0x00000010` |
| `0x800D1FB8` | `0x08800200` |
| `0x800D1FC0` | `0x00000004` |
| `0x800D2008` | `0x00080000` |
| `0x800D200C` | `0x78010010` |
| `0x800D2010` | `0x80000001` |
| `0x800D202C` | `0x01000200` |
| `0x800D20CC` | `0x00400000` |
| `0x800D2594` | `0x04000000` |

Source inspection of `0x80070290..0x80070348` establishes CC/header-based directory reads, and `0x800703BC..0x8007042C` establishes byte-valued group/row/quad arguments. The loader intervals `0x8006EE04..0x8006EE88` and `0x800713DC..0x800714CC` establish record prediction and CC/B4 ownership. The independent interface report under `/tmp/re-map-re3-selector-binding-20261106-Z0ebzx/` records all ten source-window hashes; its SHA256 is `ac89f16e29ccd1edd790d3924d67088ea555350d2bb8a13db2c8d4c843c4bf35`. The complete native predicate and bit-helper hashes are in RE3-MAP-008.

The earlier independent copied-native proof under `/tmp/re-map-re3-selection-copy-proof-20261105-3IZjwh/` compared the unchanged analysis model in 30,419 distinct contexts, including all 427 corpus group-0 quads, both metadata banks, duplicate requirements, acquisition boundaries, overlay modes, all phase-byte encodings at the threshold families and late-bypass ordering. Original function and helper bytes executed without substitutions or memory-write hooks; each call reached a bounded return and passed a full 2 MiB store audit. All 31 families received true/false target queries. Two of 264 conditional branch taken edges are source-unreachable; their dominance arguments remain in `proof-summary.json`. These checks establish copied-source agreement, not gameplay coverage.

Parent integration compared the production families structurally and their evaluator against that unchanged model in the same 30,419 saved contexts, with zero mismatches. This increment did not repeat native execution. Both retained map snapshots also produce complete per-quad predicate results matching the model. Flags and signed phase are read afresh on each call, so earlier snapshots reverse the results. The output explicitly leaves native row visibility unchecked and group-1 selection, room ownership, campaign admission and tracker visibility unresolved. Predicate-allowed indices must not become explored rooms or unconditional room unions.

Private parent evidence is under `/tmp/re-map-re3-binding-integration-20261106-BzXMBW/` and `/tmp/re-map-re3-selection-integration-20261106-pR6Det/`. Copy each verifier to a fresh private directory before rerunning; their command-line inputs are explicit owned executable/MAP paths, the corresponding independent report/proof root, output path and retained capture paths. Original evidence is preserved.

To evaluate another explicit capture, supply the expected source record; record 0 below is an example that must match the captured loaded bytes:

```sh
python3 - /path/to/SLUS_009.23 /path/to/MAP_U.MAP /path/to/capture.ram 0 /tmp/re3-map-selection.json <<'PY'
import json, sys
from pathlib import Path
sys.path.insert(0, 'src')
from games.re3.map_selection import decode_native_map_selection
from games.re3.room_data import RoomFormatFailure
executable, data, ram = [Path(p).read_bytes() for p in sys.argv[1:4]]
result = decode_native_map_selection(data, executable, ram, int(sys.argv[4]))
if isinstance(result, RoomFormatFailure):
    raise SystemExit(f'{result.kind} at {result.offset:#x}: {result.detail}')
Path(sys.argv[5]).write_text(json.dumps(result, indent=2) + '\n')
PY
```

| Evidence | Bytes | SHA256 |
| --- | ---: | --- |
| Copied-native `proof-summary.json` | — | `820f8451068a8027ccdab90c7afa448b475ac89f451b17284f922b988fd4a173` |
| Copied-native `comparison-expanded.json` | 20332 | `6c95bfafca451ed59c0301854d58056834f4a95072f8bab9401b61b9072c3eb5` |
| Binding `verify.py` | 3569 | `6c98a391a5b5e292716f2f590a98df857ae5d4964c723b60fbddd8f621fa0c6e` |
| Binding `verification.json` | 1416 | `e1a788909c0c2fc67aa7951df63cec9ff91b0062c19f2c3fdca46a40148bf1bf` |
| Selection `verify.py` | 7064 | `57dc5c17e8af229fe926c03105b185c17b69a84425419c55f777c8d29c1a4b56` |
| Selection `verification.json` | 1316 | `1764f56cd3a55dc8d5bbfa65712dbb404359d97443976d3c4c3dc8e91e8c5637` |

## RE3-MAP-010: group-1 admission and style use different condition tables

Status: Candidate source contract and bounded static export for the named revision. This increment does not evaluate group-1 shapes, style or runtime visibility. Reusing group-0 metadata rules would select the wrong banks and flag polarity.

The [detail-condition decoder](../../../src/games/re3/map_conditions.py) requires the actual pinned executable and existing bounded layout. It exports two ordered four-byte tables per record. Offsets are MAP-file bytes; section-1 header words are u32 LE offsets relative to that section. Header word 5 is zero in all nine owned records and is not a table bound.

| Table | Start | Static bound | Native entry fields |
| --- | --- | --- | --- |
| Group-1 admission | Header word 4, section byte `+16` | Section-1 end | `row:u8, quad:u8, flag_index:u8, control:u8` |
| Group-1 style | Header word 2, section byte `+8` | Header word 3 | `row:u8, quad:u8, flag_index:u8, bank_selector:u8` |

Both scans terminate on the first row byte `0xFF`, ignoring the remaining sentinel bytes. The shared bounded scanner preserves duplicates, order and exact offsets; a partial non-sentinel entry or missing terminator returns `RoomFormatFailure` without partial output. Its extraction leaves the complete owned group-0 export byte-identical to RE3-MAP-008.

When the native admission scan is reached, control bit `0x01` selects PS1 virtual bank `0x800D1FA0`; a clear bit selects `0x800D20CC`, even when other control bits are nonzero. Matching selected flags must be clear, unlike group 0. Control bit `0x10` rejects when the cached acquisition byte is zero. The export retains the full control byte and its `reject_if_acquisition_byte_clear` condition. Other control bits are ignored by the traced branch. Every matching entry must pass; no room ownership or unconditional visibility follows from these raw requirements.

The cached byte must not be replaced with Boolean map acquisition. The original helper returns a raw MSB-first mask, and admission stores its low byte with `sb` at `0x80072DAC`. For supported native groups 0–6, acquisition masks `0x80000000` through `0x02000000` truncate to zero, even when set. Records 7/8 still use native groups 0/1. Thus `0x10` rejects for supported records whenever the scan is reached. The byte is a transient stack local, not tracker history. Generated high-group checks establish truncation behavior without establishing additional valid map groups.

System word `0x800CC858`, u32 LE mask `0x80`, can return early in native map groups 0/1 after their initial shape exclusions. Such returns bypass this scan. If a matching metadata entry is reached instead, that mask rejects the entry. The static export does not implement this ordering or the remaining shape families; it leaves `shape_selection` unresolved.

Style selectors `0/1/2/3` choose PS1 virtual banks `0x800D20CC`, `0x800D1FA0`, `0x800D1FC8`, `0x800D1FE8`. Each selected word is u32 LE with [MSB-first indexing](#re3-map-008-section-1-supplies-ordered-group-0-quad-requirements). Any matching recognized-bank entry whose flag is clear returns style 1; duplicates therefore act as alternatives. Unknown selector values are skipped natively and exported with explicit kind `ignored-bank-selector`, without a fallback bank. Recognized entries have kind `flag-test` and their exact word/mask. The caller supplies palette variant 0/2; the renderer's existing kind-7 forced-zero rule still applies. System-mask style exceptions remain outside this static export. Style does not establish item or door state.

The owned source has sixteen admission entries with controls `0x01/0x11`, and 89 style entries with selectors 0/1. All nine records retain separate tables, including empty alternate-record tables. Exported full-section-1 prefix sizes are `2444, 3320, 884, 1308, 1284, 692, 728, 2184, 2652` bytes. A future group-1 snapshot witness must include its last table; the existing group-0 selector still checks its narrower, unchanged prefix and reports group 1 unresolved.

| Owned source | PS1 virtual interval, end exclusive | SHA256 |
| --- | --- | --- |
| Group-1 admission | `0x80072D38..0x800738CC` | `673124ffa53b080a0fecd48981dc0f63403da2ad9ec47428ef4174c57e2e5f96` |
| Group-1 style | `0x800738CC..0x80073BC8` | `785b40dcfc7d195294cefa0d294f2cca34fc79bf0ed4268bbc2fade29b5ff2e9` |
| Original bit helper | `0x80078930..0x80078954` | `fe32913d8f052205d92af65e011e16c0a1e58bfbfda89f9807ad09c0f5f17d8a` |

Independent source/copy evidence is under `/tmp/re-map-re3-group1-source-20261106-ellib54l/`. It preserves the rejected normalization assumption, failing context and original-code trace, followed by a 40-call raw-mask/byte witness and 203,602 passing original admission/style calls with full 2 MiB store audits. These checks used the unchanged helper and code hooks, without substituted helpers or memory-write hooks. They establish copied-source agreement, not gameplay selection or admission. The numeric contract has SHA256 `852321d4f2232fc3f4cb7b96fccdfab4a420c8403ea9f535b11db29d550e5bab`; its independent catalog has SHA256 `935745dd5c907c3a16b13cb78b6abf9cc02092c24e3d56a6c5e37cc9c4ee6aff`.

Parent metadata integration is under `/tmp/re-map-re3-detail-conditions-integration-20261106-yW4kxv/`. It verified the owned input hashes and every table extent, terminator, ordered raw entry, bank, word/mask and prefix size against that catalog. Two exports were byte-identical. The previous group-0 JSON retains SHA256 `ba8a2b83420a6d8bc6be241e7ebf9a2e6de9a38a088b3a0fb3c8734325db0aa0`. Copy the verifier into a fresh private directory before rerunning, passing executable, MAP, catalog and new output paths explicitly. No new native execution or emulator operation occurred in this implementation increment.

| Parent evidence | Bytes | SHA256 |
| --- | ---: | --- |
| `conditions.json` | 40462 | `fd285aa0ee4227de304699ef915ff58176c233bcf5741e29ced8d578495b1348` |
| `verify.py` | 3612 | `77a8d252872265a469ee84a5cd804fd33bd17ccdec348947c91e43b2429f7f14` |
| `verification.json` | 697 | `5c819a7ca549b48b25215317c7ee49b7c75a864b47fe3e39aafaa50b0a41e3aa` |

## RE3-MAP-011: bind group-1 shape admission and palette selection

Status: Candidate source interpretation for the same pinned SLUS-00923 executable and MAP resource. The [snapshot selector](../../../src/games/re3/map_selection.py) now evaluates group-1 admission and style. It does not establish native row visibility, physical room ownership, campaign admission, visits or completion. No runtime game profile or UI uses this result yet.

`decode_native_map_detail_selection(data, executable, ram, selected_record_index)` requires the explicit record index `0..8`, full executable identity, exact 2 MiB capture and four code witnesses. It shares the mandatory source-binding path with group 0. Records 7/8 use native groups 0/1; browsed group AB must match that native group. Current-location AA/AC and the current variant flag do not silently choose a different source. The CC/B4 pointer relationship, cached aligned RAM ranges and native byte argument bounds are unchanged from [RE3-MAP-009](#re3-map-009-bind-the-loaded-source-before-evaluating-group-0-shapes).

Group 1 requires a longer contiguous witness through the complete section-1 end, including its admission table. It checks all nine full prefix lengths recorded in [RE3-MAP-010](#re3-map-010-group-1-admission-and-style-use-different-condition-tables). Header, section-0 directory/quads and section-1 bytes must match the supplied source together. Mutable image sections remain outside the witness. Group 0 retains its narrower prefix and byte-identical output. A binding failure is a modeled source-context failure, not evidence that gameplay is invalid.

| Snapshot input | PS1 virtual address | Width, byte order and meaning |
| --- | --- | --- |
| Current group and row | `0x800E026A`, `0x800E026C` | Each u8, mask `0xFF`; current key is `AA << 8 \| AC` |
| Browsed group | `0x800E026B` | u8, mask `0xFF`; independent of current key |
| Phase | `0x800CCBCD` | Signed i8, full byte; comparisons preserve `-128..127` |
| Raw stage | `0x800D1F76` | u16 LE, mask `0xFFFF`; compared directly with 2/3/4, without native-group folding |
| System override | `0x800CC858` | u32 LE, mask `0x80`, MSB-first flag index 24 |
| Acquisition source | `0x800D2124` | u32 LE, mask `0x80000000 >> native_group`; cache keeps only the result's low byte |

The [33 immutable shape families](../../../src/games/re3/map_detail_predicates.py) preserve the native intervals in RE3-MAP-010's source contract. Group-0 and group-1 rules share one trusted Boolean-expression evaluator and exclusion test. Group 1 reads no overlay word. It produces an explicit decision before scanning metadata:

1. Initial group-0/1 exclusions can reject before the system return.
2. When the system mask is set, group 0 allows without metadata. Group 1 allows without metadata except row 16 quads 1/2, which reject. Neither return bypasses initial exclusions.
3. Remaining families run for other paths. Native groups 2–4 have no system early return, so their ordinary families still run with that mask set.
4. If metadata is reached, every matching admission entry must pass the clear-flag and acquisition-byte rules in RE3-MAP-010. A matching entry also rejects with the system mask set. No matching entry imposes no metadata test.

The raw acquisition mask must survive the shared flag reader. Boolean conversion before the native `sb` would invent an acquired byte for every supported group. The selector explicitly applies `& 0xFF`; all supported groups 0–6 still produce zero even with their acquisition flag set. This is freshly computed snapshot state, not retained exploration.

For an admitted quad, ordinary style is the OR of matching recognized clear-flag entries. Unknown selectors remain ignored. The system path bypasses style metadata and uses only the exact group-0/1 membership sets in the immutable source rules; other groups return style zero. The caller requests palette variant `2 * bool(style)`. Each allowed entry reports both `requested_palette_variant` and `effective_palette_variant`, preserving the renderer's kind-7 forced zero. All 366 owned group-1 quads currently have kind 4; variants 0/2 have the same occupied cells but use different CLUT rows. This does not identify those cells as a room or infer item state.

The result uses schema `re3-native-map-detail-selection-v1`. Each numeric row includes its source count and allowed quad indices with the two palette variants. `native_row_visibility` remains `unchecked`; `room_ownership`, `campaign_admission` and `tracker_visibility` remain `unresolved`. These are per-quad predicate results before the native row gate. A retained or absent map buffer cannot establish campaign control. Inputs are reread for every call, including earlier-snapshot reversals.

### Integration and reproduction

The unchanged corrected source model and original copied-native evidence are indexed in RE3-MAP-010. Parent integration under `/tmp/re-map-re3-detail-selection-integration-20261106-ySzPsT/` compares the new shape helper in all 187,398 saved admission contexts. It also compares complete production outputs in all 11,502 distinct supported owned-source contexts from that saved plan. All rows, admission decisions and palette variants agree. Native-only synthetic tables and high caller groups are outside this public binding interface; their copied-native checks are not counted as new production coverage.

The two retained source-bound captures produce 45 and 42 allowed group-1 quads respectively, with complete per-row agreement against the unchanged model. These counts are not rendered or gameplay-visible room counts. The shared extraction also matches all 30,419 prior group-0 source-model contexts, retaining their result digest and both serialized captured outputs. A separate child comparison preserves group-0 output across 1,753 synthetic contexts. No new native execution, emulator observation, savestate load or user-history access occurs in this increment.

| Parent evidence | Bytes | SHA256 |
| --- | ---: | --- |
| `verify.py` | 7844 | `6811cdd2fae8b782c28fcdc98b765271362f1e023808126e8cf545de1a58f41f` |
| `verification.json` | 1516 | `d66c5d6ef8b947310ae0cc175a730bef6a9954559bd809999556ea349fdae85e` |
| `retained-0.json` | 11878 | `211b5977c6832d78772020e4ff1827537d0dcdf5053fe28753819a50a04475d3` |
| `retained-1.json` | 11487 | `f0f4f59e1f60a5bd83a2942e7035a68289c46b7e9e1dd9dc4db24b334baa9703` |
| `group0/verification.json` | 1316 | `1764f56cd3a55dc8d5bbfa65712dbb404359d97443976d3c4c3dc8e91e8c5637` |

Copy `verify.py` into a fresh private directory before rerunning it. From the repository root, pass explicit executable, MAP, saved source-evidence directory, fresh output directory and the two retained RAM paths in that order. The verifier checks pinned input/model/report hashes, compares only Python interpretation and writes numeric reports outside Git. The saved plan has SHA256 `0e6040e2b892d6f16a980e0a5492655950737bbd1ce538e0d34799ab7e24b7ad`. It does not operate an emulator or substitute native execution. The separate `verify-g0.py` takes the same arguments with the group-0 proof directory and an output JSON path; use a separate output directory so its retained files do not replace group-1 evidence.

The new 193 shape and 63 binding/integration cases cover all families, signed phase boundaries, raw-stage width, bypass order, acquisition truncation, duplicate admission/style behavior, exact banks, ignored selectors, forced palette zero, source bounds and fresh reversal. All 976 RE3 tests pass. Synthetic tests contain no owned executable, RAM or image bytes.

## RE3-MAP-012: native row reveal precedes both quad groups

Status: Candidate source interpretation for the pinned revision. The per-quad selectors deliberately leave row visibility unchecked. Applying only their predicates to the two retained map captures produces many candidates that the native outer row gate rejects. This increment supplies that separate gate, without identifying physical rooms or importing native reveal bits into tracker exploration.

The native outer slice `0x80070348..0x800703BC` runs before either quad loop. It tests the full raw acquisition mask from `0x800D2124`, unlike group 1's truncated byte. With acquisition clear it rejects row indices at least 48 before consulting native visits. Acquisition set bypasses visits except native group 4 rows 11–15, which still require their native visit bit. Structural and selected-layer checks follow in every surviving case.

Native visits use u32 LE words at `0x800D20DC + 4 * (2 * native_group + (row >> 5))`, mask `0x80000000 >> (row & 31)`. This is one physical RAM array, not a separate Boolean store for each semantic bank label. The implementation reuses shared MSB-first addressing with full index `64 * native_group + row`. Isolated helper tests for higher rows do not prove additional reachable visit bits, since the outer cutoff comes first.

The [row predicate](../../../src/games/re3/map_row_predicates.py) preserves the structural helper's numeric group/key/raw-stage rules, then compares the selected layer when layer mode is nonzero. Story tests use PS1 virtual u32 LE word `0x800D1FA4`, mask `0x20`, bank index 58, and word `0x800D1FB8`, mask `0x08000000`, bank index 196. Current key and raw-stage widths remain as specified in RE3-MAP-011. Phase, overlay, system mask `0x80` and current-layer AF are not inputs to this gate.

| Cached layer field | PS1 virtual address | Width and source |
| --- | --- | --- |
| AD, layer mode | `0x800E026D` | Raw u8, mask `0xFF`; source layer-header byte 4; any nonzero value enables comparison |
| AE, browsed layer | `0x800E026E` | Signed i8, full byte; independent of AF/current location |
| B0, layer count | `0x800E0270` | u8, mask `0xFF`; source layer-header byte 5; not read by the native row predicate |

The native layer helper at `0x80073BC8` now has [one shared implementation](../../../src/games/re3/map_layer.py). Position initialization retains its separate story/previous-room override and metadata checks. Row gating calls the base helper directly; it does not inherit that position-only override or force AE to equal AF.

`decode_native_map_row_visibility(data, executable, ram, selected_record_index)` in [map_selection.py](../../../src/games/re3/map_selection.py) uses the same mandatory identity, capture, explicit-record, browsed-group, CC/B4 and contiguous source binding as the quad selectors. Its source-row count must fit the native byte argument. The existing group-0 prefix already contains the whole directory and source layer header, so no image bytes or quad predicate evaluation are needed. The new API also checks cached AD/B0 against those raw source bytes. When AD is nonzero, signed AE must satisfy `0 <= AE < B0`; otherwise it returns `map-selection-binding` at the offending RAM offset. These are explicit wrapper coherence checks, not branches invented inside the native predicate. Unlayered native behavior ignores AE and the wrapper preserves that behavior.

In addition to the existing four sampled capture witnesses, this API compares all five complete gate/helper windows below against the supplied verified executable. The shared capture checker accepts explicit additional address/width spans; these cannot replace its four mandatory sampled witnesses. Extra-window mismatches return `capture` with RAM offsets. All addresses in this table are PS1 virtual; interval ends are exclusive.

| Native code | Interval | SHA256 |
| --- | --- | --- |
| Outer row gate | `0x80070348..0x800703BC` | `4b6e743201d6ccde7e2be01383a660cb75f7956e30a5c3659cecc5e59972af85` |
| Visit helper | `0x80071668..0x800716A4` | `e603c122474c57b35236294428ecbd2d640d1fb19ffd24daf078b45b6fffb049` |
| Structural helper | `0x800716A4..0x80071878` | `dad683c50e54920cac52a7e39f0345462f316d6f1ac89b069ca7dc508822c3fc` |
| Layer helper | `0x80073BC8..0x80073CCC` | `b4cdd194b38765ce700309db1957aa49b1fea90878eca9388abf636bb3864ccb` |
| Original bit helper | `0x80078930..0x80078954` | `fe32913d8f052205d92af65e011e16c0a1e58bfbfda89f9807ad09c0f5f17d8a` |

The result uses schema `re3-native-map-row-visibility-v1` and reports `native_visible` for each numeric source row. Room ownership, campaign admission and tracker visibility remain unresolved. The two earlier quad APIs retain their output and unchecked-row contract. A caller combining these source results must use the same capture and explicit record. Native acquisition can reveal rows that the tracker has never observed; it must never replace the separately persisted tracker visit history.

### Evidence and limits

Private source evidence is `/tmp/re-map-re3-row-visibility-20261106-3hkx8ozv/`. The contract has SHA256 `215e6310dd094231c8c7d756d85be805b221bec8bf2f8bb170304314f1f684f5`; copied proof SHA256 is `65713da3ef7983b0428b9d6f4c2253314e501d5a1833c6298ca1441c8f350f16`. It records 17,896 original copied executions, including 7,298 bounded outer slices and all 130 retained source rows, with full 2 MiB decoded-store audits and no substitutions or memory-write hooks. The outer slice stops before quad rendering and is not a complete renderer call. The report explains three one-sided branch edges and preserves rejected harness assumptions and their corrections.

Parent integration under `/tmp/re-map-re3-row-integration-20261106-v71P7s/` checks 11 source-window hashes and compares the 17,766 generated-plan contexts against production Python. Outer and layer cases use the production helpers directly; visit cases compare shared physical addressing; structural cases enable acquisition/visits to isolate the production structural path without changing its inputs. A further 221 coherent-source controls check 14,161 complete row results across all nine records. These generated controls are separate from the original native plan and do not add runtime observations.

| Retained capture | Candidate visible rows | Group-0 candidates before/after gate | Group-1 candidates before/after gate |
| --- | --- | --- | --- |
| `l2-menu-settled` | 1, 13 | 54 / 3 | 42 / 1 |
| `room-0d-map` | 13 | 55 / 1 | 45 / 1 |

These reductions match the unchanged source model. They are neither new rendering observations nor tracker room counts. Both earlier selectors' retained JSON hashes remain unchanged. Source binding and full gate-code comparisons pass for both retained inputs. This integration operates no emulator and changes no captured bytes, history, UI or runtime profile.

| Parent artifact | Bytes | SHA256 |
| --- | ---: | --- |
| `verify.py` | 8347 | `619c71046b92db0744d49e6aea38d85d6025eb2c87fe3f474896ad57aaca2579` |
| `verification.json` | 2138 | `e0004dbcae188c5fe43a23def05d05b15aae26631a8b23f4b0b014a04636ef66` |
| `retained-0.json` | 4667 | `2e830c6c3f9c90ab5a064dd9e4ae3bd3436add7188bdd822886eda4c26f39fa2` |
| `retained-1.json` | 4669 | `6f6a73c483f7ad0b4232e78b68b559089109cba5b838a851cffa0124c517e6a4` |

To reproduce Python integration, copy `verify.py` into a fresh private directory and run it from the repository root with explicit executable, MAP, saved row-proof directory, fresh output directory, settled RAM and room-0d RAM paths in that order. It validates the model/plan/contract/proof hashes and writes only numeric reports outside Git. The tests include 891 new pure-predicate/layer cases and 39 new wrapper/capture cases, including enforcement of the four general witnesses when extra spans are requested. Run the selected tests with `PYTHONPATH=src python3 -m pytest -q tests/test_re3_map_row_predicates.py tests/test_re3_map_row_visibility.py tests/test_re3_map_binding.py`. Synthetic fixtures contain no owned code, RAM or artwork bytes.

## RE3-MAP-013: native current-row draws distinguish two R101 features

Status: Confirmed for the original draw calls and exact restores in the two listed checkpoint states. Generalization to other states remains Candidate. Target is Resident Evil 3: Nemesis, USA PS1, SLUS-00923, Hard, executable SHA256 `2e143418e358b2c99995cdc1a88c387163fb751912c723b755614f38e236bd29`, with the MAP_U fingerprint below. One isolated session used DuckStation `0.1-12083-g00e299795`, binary SHA256 `5c879677051cfb173002df22baee741c96fa8071c6fe1dd7e5454092bf128173`, native-state version 87.

This comparison addresses the geometry-selection gap left by RE3-MAP-006/009 and [RE3-LIVE-002](live-reader.md#re3-live-002-fresh-native-map-position-under-current-room-guards). One RDT can select different current-row quads while retaining the same native numeric layer. The result does not establish physical floor names, navigable area, room-owned contours or tracker reveal policy.

### Exact states and original calls

The lower and upper original checkpoints were restored with native F1 under an acknowledged debugger pause. Before input, each restored full 2 MiB RAM, GPR0..31, HI/LO, PC and all 1024 scratchpad bytes matched its native payload. Native Pad pressed masks were zero. The upper checkpoint previously had creation/payload agreement only; this session supplies its first exact restore observation. No memory-card persistence is inferred.

| State | Original checkpoint SHA256 | Exact restored RAM SHA256 |
| --- | --- | --- |
| Lower, raw actor floor 1 | `3e3d067475daab53a7589fff3649521e6f9331746331998de09407dcb2c38290` | `41d7dbb07cd026b8cb0427e197dc9a48f6aed6299077b0c44c4078544f7a0c63` |
| Upper, raw actor floor 4 | `4fd26335f93945de165d55a4577c0e32ec1e285af5a4c4ac466924ea5b03f8cc` | `8c9d9bb4aacc8a684f3cb660bde1a74189373f886bad531ba15ae9f4368acf34` |

CUA sent only native F1/F2 and the previously validated F15-to-L2 map toggle. No movement, action, item input, forced pose, flag write or guest-code patch was used. Original execute callbacks observed admission return `0x80070400`, renderer entry `0x8007116C` and group-0 row completion `0x800704DC`. The pinned caller establishes S6 as row and S0 as quad index. At the renderer, RA is `0x8007042C`, A0 is map work `0x800E01C0`, A2 is the source quad pointer and A3 is the palette argument. Register values are unsigned 32-bit native observations; instruction addresses are PS1 virtual addresses.

| State | Admission V0 for quads 0 / 1 / 2 | Original renderer calls and A2 | A3 palette | Native layer AF |
| --- | --- | --- | ---: | ---: |
| Lower | 1 / 0 / 0 | Quad 0 at `0x801B176C`, MAP offset 620 | 2 | 0 |
| Upper | 0 / 1 / 1 | Quad 1 at `0x801B1778`, offset 632; quad 2 at `0x801B1784`, offset 644 | 2 for both | 0 |

Both sequences reached row-one group-0 completion with S4 equal to three. Thus all three current-row admission results, the accepted calls and completion were observed. Nine noncurrent upper stops, all row zero, were retained separately. These observations corroborate the signed raw actor-floor comparison at `0x800CCBCD` in the original group-0 rule for current key `0x0001`. This field is distinct from lifecycle byte `0x800C7960`. The observations do not runtime-confirm every input to the shared predicate tables.

### Source, projection and interface binding

Seven full captures uniquely match `CD_DATA/STAGE1/R101.ARD` among all 169 owned sources using the established relocated header/camera/zone witnesses. Source and allocation pointers remain `0x8011A708`. Mutable initializer differences remain explicit; this is not whole-RDT byte identity.

At map stops, MAP base `0x801B1500` and section-1 pointer `0x801B1CAC` match record zero. Its complete header and drawing/projection sections match owned MAP_U bytes. Image-section differences are retained and do not become a whole-record identity claim. Native code windows for caller, admission, renderer, row gate, palette, layer and remapping also match the pinned executable in every full capture.

Before opening the menu, `read_current_map_position` returns the admitted R101 source and native group/row `0/1`, layer zero. Lower world XYZ is `[-6363,-1800,-11415]`, facing 1952, projected point `[512,332]`; upper XYZ is `[-18808,-7200,-11475]`, facing zero, projected `[484,332]`. Position/facing widths and guards remain those of RE3-LIVE-001/002. Cached AA/AB/AC are zero before opening and are not live-reader inputs. In the menu they become `0/0/1`, pan equals the negative projected point, scale is 100 and the reader returns `NonGameplay`.

The existing source selector and row gate agree with the native calls. Requested-palette-2 coverage has 2961 source cells for lower quad zero and 2416 for upper quads one/two; each projected point lies inside its selected coverage. This is interpretation of previously exported source texels, not newly observed GPU pixels, walkable floor or room ownership. Native visit/acquisition bits do not seed tracker exploration.

### Stop, save and isolation limits

Lower quad zero and upper quad one have new native F2 saves matching the same acknowledged stop's full RAM, GPR/HI/LO/PC and scratchpad. GDB PC is renderer entry `0x8007116C`, while native `current_instruction_pc` is caller delay slot `0x80070428`, instruction `0x304700FF`; the buffered next instruction is renderer prologue `0x27BDFFC0`. This is renderer entry, not evidence that the prologue already executed. Upper quad two has GDB registers/code and full RAM without a separate native CPU-current-instruction save. Later row completion confirms continued original execution.

Three new checkpoints, `lower-renderer-native`, `upper-renderer-native` and `upper-map-final-native`, were created and payload-compared, not restored. Their hashes and raw branch-state bytes are in the verification report. Critical draw captures retain a raw map-opening input word after host release, with native Pad zero. Settled captures and the final native save verify all five RAM input words zero and native Pad zero.

Both RetroAchievements namespaces and integration were disabled before all loads, with cards None, no cheats/patches, private paths and hidden/muted gameplay. The first controller attempt stopped on a missing layout argument before test input; possible bootstrap disconnect execution is unqualified. The exact lower F1 restore precedes all accepted experimental claims. No emulator restart was inferred from that failed attempt.

Callbacks and the sole client were closed, owned PID 5856 exited with wrapper status zero, and port 2394 was absent and bindable. Private settings remain byte-identical, SHA256 `dfd2a30a65daa90142864f51c397dbe90b159d69ab6a217eb6ffc14522b3143b`; two user settings/history file-stat records are unchanged. No user history content, tracker state, application profile or UI was modified. CUA completion was recorded once. Final guest claims end at acknowledged stop 23. Execution between client closure at `12:22:00.899150 UTC` and SIGTERM at `12:22:35.483262 UTC` was not observed.

### Reproduction and review

The portable replay amendment is `/tmp/re-map-re3-map013-amended-20261107/`. Run its top-level `verify.py` with the existing Python environment, one mandatory nonexistent output directory and the owned BIN explicitly:

```sh
python /tmp/re-map-re3-map013-amended-20261107/verify.py /absolute/new/output --disc-image /absolute/owned/RE3.bin
```

It checks frozen source/media, both restores, original calls, loaded MAP, seven captures, three new save payloads and cleanup without starting an emulator or CPU model. Executable, source contours and all 184 original manifest-bound evidence files are included with relative paths. The owned BIN and development dependencies remain required external inputs. Replay creates no new bytecode and preserves the original bound caches. All original files remain unchanged under `native/`, including the original report, verifier and manifest below. Their original directory is `/var/folders/9d/q5n746z953bcs654g_1sqcy80000gn/T/re-map-re3-map-draw-native-20261107-u1t2k4p0/`.

| Original native artifact | SHA256 |
| --- | --- |
| `native/report.md` | `2f7e48670c516685818f09dd5ae6d9c705dfa15eaeba8a00a608f73ee82a2c2a` |
| `native/verify.py` | `a5587a0f0a41b858128ac6c2c911c777deb1854761718b24c6c6d18c442a4425` |
| `native/verified-3/verification.json` | `add1ed516acd31173610f61628711d60ac24c5fc6a92e075dc6fdcc421da72f5` |
| `native/artifact-manifest.json`, 184 files | `adf769601be0bb0cbb44e767dbac28a8a5068384fff741daa9f18d31b5e6f1e4` |

| Replay amendment artifact | SHA256 |
| --- | --- |
| `verify.py` | `b226b7d277d435532c8b3a67ea78bea7ed1e40f5b425d5ca17d37026f0e88537` |
| `verified-final/verification.json` | `64e91e503367f2c2824ae60ab3c952b683d18cb47a7711d8e5e9fd9dfe9e54e6` |
| `artifact-manifest.json`, 198 files | `6a40cbf599485eaa61146834891aba92edd73f827cd815e01471cf472a8c6341` |
| `amendment-checks.json` | `244e67871821ff93fcf3f41cbcb7cc668d2148c5d688128ba6dee0dcc3a20483` |

The amended report differs only in verifier hash and actor-floor wording; all native observation fields remain identical. A separate relocated bundle reproduced the amended report byte-for-byte with the owned BIN supplied explicitly. The included contour file retains SHA256 `db2dda034593c17f809245e829e184cf7551d4b96d4f36c3895a7344311039cd`. This closes the original verifier's dependency on an older transient contour-export directory without changing the experiment.

Root reproduced the original verification report byte-for-byte in `/tmp/re-map-re3-map-draw-root-verify-20261107/`. A separate audit checked all 184 artifact entries and all 104 frozen Python files against preparation commit `e4f9b32`. Independent zstd CLI decompression found each complete captured 2 MiB RAM image exactly once in all five relevant native payloads, without relying on the verifier's fixed extraction offset. That audit also rechecked prior PID/port cleanup without connecting to the separate later acquisition experiment. `/tmp/re-map-re3-map-draw-root-audit-20261107/audit.json` has SHA256 `99151ce1adeeb67a7aeb3a36bb7db0680d6c85a5f34812fc9ff9a0736ebc5975`. This audit adds no new gameplay.

- 2026-11-07; native experiment, source/capture interpretation, frozen verifier and private report by exact verified model `gpt-6.1-sol`, effort `xhigh`. Root, the same verified model/effort, independently audited the files, decompression, source equality and bounded conclusions, and authored this claim. Earlier source and human contributions remain unchanged.
- 2026-11-07; independent reviewer, exact verified model `gpt-6.1-sol`, effort `xhigh`, reproduced the original report byte-for-byte and checked all 184 hashes and 104 frozen source files against preparation commit `e4f9b32`. It checked native register roles, delay slots, admission/completion, source-prefix limits, restores versus creation-only saves, input release, bootstrap/disconnect gaps, changed links and preserved earlier documentation. It returned no findings. This was source/file review, not a new runtime observation.
- 2026-11-07; external snapshot reviewer `gemini-3.8-flash`, high reasoning through Antigravity, reviewed the documentation diff, native report/verifier/controller, unchanged debugger interface, numeric results and root audit. It identified the unbundled contour dependency, ambiguous actor-floor wording and a redundant loop. Root fixed these in the portable replay amendment while preserving original evidence, then verified unchanged native results and relocated reproduction. The returned review is bound in that amendment as `external-review.json`, SHA256 `402d2cfad8169979b098d5b7aa8934025e523410857309e8717599b67c2de8ac`. No further external endorsement is inferred. Claude Opus 5.5 remained disabled and supplied no review.

## RE3-MAP-014: an ordinary R100 map opening selects a separate current feature

Status: Candidate for general room/floor binding. One retained R100 state supplies an additional original-engine current-feature observation, independent of RE3-MAP-013's two R101 states. Target is Resident Evil 3: Nemesis, PlayStation, USA, SLUS-00923, Hard, executable `SLUS_009.23`, SHA256 `2e143418e358b2c99995cdc1a88c387163fb751912c723b755614f38e236bd29`. One isolated session used DuckStation `0.1-12083-g00e299795`, binary SHA256 `5c879677051cfb173002df22baee741c96fa8071c6fe1dd7e5454092bf128173`, native-state version 87.

The experiment restored `r100-earlier-native.sav`, SHA256 `5a6784037097f1f1d4397fb03355bc8f51a43f1c4dadc9e151de75b458830668`, with native F1. Before input, an acknowledged pause established exact agreement of all 2 MiB RAM, GPR0..31, HI/LO, PC and 1024 scratchpad bytes with the native payload. Native Pad pressed mask was zero. This is a tested restore; the two new F2 saves below were only created and payload-compared, not restored.

### Original calls and source binding

Before the single ordinary L2 opening, `read_current_map_position` returned R100, selectors `0/0/0`, XYZ `[-20400,0,-20790]`, facing 2048, raw actor floor 0, native group/row `0/0`, numeric layer 0 and projected point `[480,330]`. The menu returned `NonGameplay`. These are raw/native numbers, not a physical floor label. RE3-MAP-013's lower/upper states are R101 at raw actor floors 1/4, both native layer 0.

Original callbacks stopped at admission return `0x80070400`, renderer entry `0x8007116C` and group-0 completion `0x800704DC`. Exact caller instructions establish S6 as row, S0 as quad index, A2 as source quad pointer and A3 as palette. GPR observations are full unsigned 32-bit values; code addresses below are PS1 virtual addresses.

| Native row and role | Admission V0 by quad | Group-0 renderer calls, RA `0x8007042C` | A3 | Completion S4 |
| --- | --- | --- | ---: | ---: |
| Current row 0 | Quads 0/1/2/3: `1/0/1/1` | Quads 0/2/3, A2 `0x801B1730/0x801B1748/0x801B1754`, MAP offsets 560/584/596 | 2 | 4 |
| Noncurrent row 1 | Quads 0/1/2: `0/1/1` | Quads 1/2, A2 `0x801B1778/0x801B1784`, offsets 632/644 | 0 | 3 |

A separate renderer stop had RA `0x80070540`, A2 `0x801B1760`, palette 0 and source group-1 row-zero quad zero at offset 608. The original second-count loop calls `0x80072D38/0x800738CC` then the renderer at `0x80070538`; this receipt is kept separate from the group-0 calls. At the saved current renderer stop, GDB PC was `0x8007116C` but native `current_instruction_pc` was caller delay slot `0x80070428`, instruction `0x304700FF`, with renderer prologue `0x27BDFFC0` queued next. The prologue had not yet executed.

Four full captures match the established partial relocated header/camera/zone witnesses uniquely among all 169 owned sources. R100 RDT SHA256 is `e47f25b5a6e82d73f79bf356c111a8add6a7e24555a4deb83ed8725e3979ed50`, size 109208, native file index 376; source and allocation stay `0x8011A708`. Mutable initializer differences remain explicit. At menu captures, record-zero header and complete drawing/projection sections match MAP_U SHA256 `7182beb90347fe4ea0c2a4db30dff93aaee88b8ef1b633398ffcef6f3d3d1268`, and nine complete selected native code windows match the executable.

The actual loaded MAP pointer field is PS1 virtual `0x800E028C`, u32 LE/mask `0xFFFFFFFF`, value `0x801B1500`; section-one field `0x800E0274`, u32 LE/mask `0xFFFFFFFF`, is `0x801B1CAC`. Overlay `0x800E0278`, u16 LE/mask `0xFFFF`, is zero at these observations. The frozen preliminary plan incorrectly named map-work field `0x800E01C8` as the loaded pointer. Its original bytes remain preserved; `plan-erratum.md` records the correction made before launch. The controller and shared binder use `0x800E028C`.

Native visit word `0x800D20DC`, u32 LE, remains `0xC0040000`; row-zero/one masks are `0x80000000/0x40000000`. Acquisition word `0x800D2124`, u32 LE, remains zero. Both rows reach their original per-quad loops, agreeing with the bound row gate. The earlier lower-R101 seed instead has visit word `0x40040000` and acquisition zero, so its absent row zero is rejected before the group-0 predicate. That absence cannot validate early per-quad suppression. Native visits/acquisition remain separate from tracker exploration.

### Coverage meaning, reproduction and limits

Reinterpreting the retained contour export gives R100 quads `[0,2,3]` 527 palette-2 nontransparent source cells, of which 403 are absent from palette 5. Upper R101's quads `[1,2]` have 2416/1932 cells respectively; their class-2 contribution has zero overlap with R100's 403 cells. Lower R101 quad zero has 2961/2514 cells and still overlaps both alternatives. These are source texel-class masks, not observed GPU pixels, navigable area or complete room-owned floor. This closes one independent current-feature selection gap; physical-floor identity, room ownership, tracker reveal and a runnable Hard profile remain unresolved.

Private evidence is `/tmp/re-map-re3-r100-map-native-20261107-nUiK0jpY/`. Its verifier reads copied support and frozen runtime/helper modules through relative paths, rebuilding/binding the complete corpus and MAP from the mandatory explicit owned BIN. The full prior contour export, eight retained captures and prior R101 native receipts are included. Historical absolute paths are provenance only. A new relocated child-process replay reproduced the final report byte-for-byte; this was retained-file reproduction by the experiment author, not independent review or another native observation.

```sh
python /tmp/re-map-re3-r100-map-native-20261107-nUiK0jpY/verify.py /absolute/new/output --disc-image /absolute/owned/RE3.bin
```

| Private artifact | SHA256 |
| --- | --- |
| `r100-exact-restored.ram` | `49f23b281794036fcb027c2966ac0138748d7eef500499900e57aac3bcf13f2a` |
| `r100-current-renderer-quad0.ram` | `4267a36f9fae231efddbec487e545553cd57d25538a8f30f3fa2b24ea0fc9dac` |
| `r100-noncurrent-row1-quad1.ram` | `9e8bd72c955e233662b5671da45ceff75b0059120302fb55b9dfe58c3dbdbec9` |
| `r100-final-released-menu.ram` | `d46afdeaf477cd82df7fdcb907d40dcc16a6fb86d033dad875008be6f476e867` |
| `r100-current-renderer-native.sav`, creation only | `155679f7838eca5f44873e6ce222cf07161d64b98abbbb616512fa1df8ef4a0c` |
| `r100-final-released-native.sav`, creation only | `e8a2b7b854a3a5b551bb4aede60ea8e46690166ac483a49f349f189aa85070f8` |
| `verify.py` | `5739397c352b9e8bcae84411e6ce39aa329a6780805c7208e96d75ab2d504f8b` |
| `verified-final/verification.json` | `210cd47a506e6fa3ce4ca6d855c1ce7230af04233d590d5f531ea1533a137011` |
| `artifact-manifest.json`, 190 files | `dfaf1ab56caf1cc6610f0f7046ddf31ea0c046c3f2a54ad36481c10dd0ba9b27` |
| `support-manifest.json`, 23 copied files | `4e9379aa8ec9657e495da8b4bd361ed1355a08b40d3ca84edd7db18e666c5aa7` |

Before game/seed loading and native F1, both RetroAchievements namespaces and integration were disabled, ApplyGameSettings was false, accounts/overrides/cheats/patches absent, cards None and private gameplay black/muted. CUA used only F1, F15-to-L2 on/off and two F2 saves. No movement, action or pickup input, agent-issued guest-memory/PC/pose/flag edits or game-file modification occurred. Host release preceded native input mapping, so intermediate raw L2 remained set despite native Pad zero. After removing all three callbacks, a bounded no-input run reached acknowledged epoch 17 with all five RAM input words zero; the final save also has native Pad zero.

The sole client closed; verified owned PID 99922 received SIGTERM and its wrapper exited zero. Port 2396 was absent/bindable. Private settings remain byte-identical, SHA256 `fae67cde21842dabfb818c2df25cc4c542705636aa3f4ef801d3f9037e335160`; two prior user settings/history file-stat records are unchanged, without reading their contents. CUA completion was recorded once. Claims end at acknowledged epoch 17; last-client disconnect to SIGTERM may resume execution and is unobserved. No native probe failed. Three verifier-development errors and the first portability copy's missing error-record dependency are preserved; their corrections changed no native input/evidence. Only the 26 relevant RE3/runtime/helper hashes were compared with preparation/frozen files; concurrent RE2/docs changes are outside that comparison. No tracker state, user exploration, application profile or UI was modified, and raw assets/RAM/states remain private.

- 2026-11-07; native experiment, source/capture interpretation, retained-file verifier, private report and this claim by exact verified model `gpt-6.1-sol`, effort `xhigh`, session metadata id `01a1b0bc-6b73-7101-ab2f-8aa8669a7247`. Earlier claims and authorship remain unchanged. Independent verification/review is recorded separately when completed; none is inferred here.

- 2026-11-07; independent reviewer `investigate_gdb_recovery`, verified `gpt-6.1-sol`, effort `xhigh`, checks all 190 artifact entries, performs a relocated byte-identical offline replay, independently reproduces selected TIM/CLUT cell sets and checks caller/row completion, source/MAP binding, restore versus creation-only saves, inputs and cleanup. It finds no supported issues within that scope. `/tmp/re-map-re3-r100-independent-review-20261107-65dmh_15/review.json` has SHA256 `344b492b488b58bb8c4a4734509b942631f7d4708f9ab105f2012333970f343a`. This is independent evidence review, not another native session.
- 2026-11-07; Codex root, the same exact verified model/effort, separately checks all 190 entries, 108 frozen Python hashes and 26 current critical source files. Independent zstd CLI decompression finds each complete 2 MiB captured RAM image exactly once in the seed and both new payloads. Root also observes PID 99922 absent and port 2396 bindable without connecting to an emulator. `/tmp/re-map-re3-r100-root-audit-20261107/audit.json` has SHA256 `47b3f8437ab8b54d3d350f4f2b99980a080500949ffeebd72fc552e040c56e30`. Its separate offline verifier run reproduces report SHA256 `210cd47a506e6fa3ce4ca6d855c1ce7230af04233d590d5f531ea1533a137011`. The payload/manifest audit adds no independent CPU-state or gameplay claim beyond the retained comparisons.

- 2026-11-07; a fresh `gemini-3.8-flash` high-reasoning snapshot review of this record, native report/controller/verifier, command-result fields and root audit fails to open an Antigravity session. Claude Opus 5.5 remains disabled. No external review completes or supplies an endorsement. Local final review checks original caller/register roles, source bounds, projection/palette numbers, restore and input chronology, portability, cleanup and claim limits. Scoped documentation links and whitespace checks pass; this evidence-only change adds no production code or full-suite run.

### Retained projected-point follow-up, 2026-11-07

Status: Candidate offline geometry check, with no additional native observation. The fresh source selections in RE3-MAP-015 below supply the three pre-opening projected points. The frozen contour export supplies closed unit-cell polygons for requested palette variant 2. None of these seven quads exercises native kind 7 or its effective-variant-zero override. Exact polygon area agrees with each exported cell count. These polygons describe source coverage before pan, scaling, clipping and GPU rasterization.

| Retained state | Projected point | Selected source area | Strictly inside | On boundary |
| --- | --- | ---: | --- | --- |
| R100 | `480,330` | 527 cells | yes | no |
| Lower R101 | `512,332` | 2,961 cells | yes | no |
| Upper R101 | `484,332` | 2,416 cells | no | yes |

All three points belong to their selected closed polygons. This does not establish a universal containment requirement for future admitted states. Boundary membership is a geometric result, not a claim that a GPU pixel is drawn there. A strict interior-containment gate would reject the retained upper-R101 point. All three numeric native layers are zero; raw actor floors remain 0/1/4 and are not physical floor IDs.

The complete R100 mask is contained in lower R101's mask. The lower-R101 point also belongs to the upper-R101 mask. R100's unselected quad 1 covers its current projected point, while the selected and unconditional row unions both cover 527 cells. Lower R101's selected and unconditional row unions likewise both cover 2,961 cells. Thus point membership or equal union area cannot validate the actual admitted quad set, assign physical room ownership or distinguish floors. Source record/row and selected quad identities must remain explicit.

Private reproduction is `/tmp/re-map-re3-selected-point-root-20261107/check.py`, SHA256 `ea98ba658e2e4dab33de0b29fc0a25985e80a2f545d905285e68106db5b492c8`. It hash-checks the frozen contour export and final RE3-MAP-015 retained report before comparing the three states. `report.json`, SHA256 `ef21f74bf382c2455676eca37173e323b49ae39ff811f88fcffb2e9024753c1e`, records each selected/unselected quad's point membership, boundary distance, area and cross-state overlap. This check adds no ownership algorithm, tracker visit, floor label, production profile, emulator input or gameplay coverage. Contribution: Codex root, exact model `gpt-6.1-sol`, effort `xhigh`, authors the comparison and this dated note.

Independent verification, 2026-11-07: `review_re3_rows`, exact model `gpt-6.1-sol`, effort `xhigh`, reconstructs integer-cell sets without Shapely and matches every area, point/boundary distance and overlap result. Its report SHA256 is `0fe4589f3dbdd4ea1d3574aa97d8cfed2c718d4ee39c85ac24f67c0b98ee9bed`, under `/private/var/folders/9d/q5n746z953bcs654g_1sqcy80000gn/T/re-map-re3-selected-point-review-20261107-kk_g6nob/`. It finds no numerical defect and preserves the ownership, GPU and universal-admission limits. Root verifies hashes, coordinate spaces and claim wording, including the unexercised kind-7 limit. A Gemini 3.8 Flash high-reasoning request fails to open its provider session; Claude Opus 5.5 is disabled. No external endorsement follows. The private comparison, local documentation links and whitespace checks pass; this documentation-only increment does not rerun the Python suite.

Root's `review-erratum.json` preserves one correction to that review's prose: its second recommendation incorrectly calls the cell with origin `484,332` absent. The independent numeric report and root's separate check both find it occupied. The closed-polygon point is still on a boundary because its two left-adjacent cells are absent and two right-adjacent cells are present. The review's numerical results and the comparison above remain unchanged.

## RE3-MAP-015: fresh ordinary-view current-row group-0 source observation

Status: Candidate. This is a prospective ordinary overlay-zero source observation under the [existing Hard current-room admission](live-reader.md#re3-live-001-bounded-hard-current-room-and-pose-observations), not actual hardware L2 admission or a guarantee the map menu would open. Target is Resident Evil 3: Nemesis, PlayStation, USA, SLUS-00923, supplied disc/revision, Hard; executable `SLUS_009.23` SHA256 `2e143418e358b2c99995cdc1a88c387163fb751912c723b755614f38e236bd29`, MAP_U.MAP SHA256 `7182beb90347fe4ea0c2a4db30dff93aaee88b8ef1b633398ffcef6f3d3d1268`. Retained runtime inputs come from RE3-MAP-013/014's DuckStation `0.1-12083-g00e299795`, native-state version 87. This increment starts no emulator and adds no native execution, gameplay observation or restore.

### Source contract and API

`compile_map_feature_layout` takes explicit immutable owned MAP/executable bytes, checks both exact hashes and compiles a typed, deeply immutable layout once before polling. It reuses `compile_map_position_layout`, bounded metadata decoding and shared record/group mapping. The authority retains compiler-created tuple identities and permits no public construction or `dataclasses.replace`, including simultaneous substitution of a derived value and a matching receipt. No decoded list/dictionary or mutable source buffer survives inside it. Row/quad byte-argument counts, metadata targets and aligned physical flag-word extents fail with modeled source errors.

`read_current_map_features(catalog, layout, read_memory)` adds an explicit alternative to the shared live transaction. It reads fresh remapping/world state and resolves the current native group, source record, row, projected pose and numeric layer through `resolve_native_map_position` and the shared layer code. It then uses the existing group-0 shape predicates, shared conjunctive metadata requirements and `native_row_visible`. Acquisition bypasses metadata only. The separate `native_row_visible` boolean can be false while `group_zero_allowed_indices` remains nonempty. Native visit/acquisition words are game facts and grant no tracker exploration. Only the current row's group-0 quad indices are returned; group-1 detail calls and palette semantics remain separate.

The loaded MAP cache can be absent or stale in ordinary gameplay. This API predicts from pinned owned sources and fresh world state; it neither reads nor claims a current loaded-source pointer. The older capture selection API still requires its explicit loaded-MAP prefix binding. Cached AA/AB/AC and AE/AF are not inputs to this prospective API. No room whitelist, room/floor label, room ownership, complete item list, clearance, exploration persistence or registered RE3 production profile is added.

### Pending context and overlay are fresh inputs

The supplied source-only followup at `/tmp/re-map-re3-l2-overlay-source-20261107-39mh2sl7/` checks fourteen pinned original windows across eleven retained captures. All eleven observed overlays are zero. This does not establish zero as an ordinary L2 invariant. Original `0x80023CB4..0x80023CD8` sets work mode 4 and request bit `0x0200` without clearing overlay. The common request tail sets pending byte `0x800C7961` and request bit `0x0100`. Entry `0x8006D948` invokes fresh selectors at `0x8006ED28`; `0x8006DB8C` reads overlay and nonzero cases can override browsed group. Bootstrap `0x8006D928` and completed-menu cleanup `0x8006E1A8`, before task-zero resume `0x8006E248`, contain explicit zero stores. Closed-menu state alone precedes that completed cleanup and cannot prove zero overlay.

The source-map handler `0x80058C70/0x80058CB4` sets pending state and stores a zero-extended source-u8 operand into the overlay u16 before menu-active becomes true. This is inspected source control flow, not an observed execution of that source opcode. Ordinary L2's `0x80023C24` reads the full u16 at `0x800C7960`, including its pending high byte. The earlier `0x80031F50` selector-4 call is OPTION.BIN, not the L2 map route; that rejected interpretation is not used here.

The new request therefore requires the following fresh PS1 virtual fields, in addition to the existing room/position gates. No address below is a host-process address.

| Field | Width / byte order | Mask / accepted value |
| --- | --- | --- |
| `0x800E0278`, actual overlay | u16 LE | `0xFFFF`, zero only; nonzero gives `UnsupportedSettings` |
| `0x800C7961`, pending map/UI byte | u8 | `0xFF`, zero; pending gives `NonGameplay` |
| `0x800D1F2C`, request word | u32 LE | `0x0300`, both bits clear; pending gives `NonGameplay` |
| `0x800CCBCD`, raw signed actor floor | i8 | all eight bits, used as the shared shape predicate's signed argument |
| `0x800CCBF8`, XYZ, and `0x800CCC32`, facing | 3 × i32 LE and u16 LE | full widths, one contiguous actor/pose sample |

Active menu/pause stays `NonGameplay`, including a nonzero overlay. Existing position-only and collectible observations keep their previously accepted behavior; their `Display` is not a prospective menu-entry receipt.

### Complete dependencies and coherence

The compiler enumerates shared predicate trees, source metadata and native row dependencies across the nine records. Its exact supplied-source plan has 26 u32 LE flag words. These union masks name predicate dependencies; the live transaction explicitly reads and compares each complete `0xFFFFFFFF` word. Existing remapping masks remain additional requirements, including `0x00800000` at `0x800D1FB8`, `0x4000` at `0x800D1FBC` and `1` at `0x800D1FC0`, as recorded in [RE3-LIVE-002](live-reader.md#re3-live-002-fresh-native-map-position-under-current-room-guards). Visit indices retain the native two-word-per-group stride and physical aliasing. The dependency plan is source-derived, including branches skipped this poll, rather than an estimated contiguous flag region.

| PS1 virtual word address, u32 LE | Dependency mask |
| --- | --- |
| `0x800CC858` | `0x00000080` |
| `0x800D1FA0` | `0x20040010` |
| `0x800D1FA4` | `0x00000120` |
| `0x800D1FA8` | `0x80000003` |
| `0x800D1FAC` | `0x80000000` |
| `0x800D1FB0` | `0x00040005` |
| `0x800D1FB4` | `0x00000010` |
| `0x800D1FB8` | `0x08800200` |
| `0x800D1FBC` | `0x00200000` |
| `0x800D1FC0` | `0x00000004` |
| `0x800D2008` | `0x00080000` |
| `0x800D200C` | `0x78010010` |
| `0x800D2010` | `0x80000001` |
| `0x800D202C` | `0x01000200` |
| `0x800D20CC` | `0x00400000` |
| `0x800D20DC` | `0xFFFFFFFF` |
| `0x800D20E0` | `0xFFFFFFFF` |
| `0x800D20E4` | `0xFFFFFFFF` |
| `0x800D20E8` | `0xFFFFFFFF` |
| `0x800D20EC` | `0xFFFC0000` |
| `0x800D20F4` | `0xFFFFFE00` |
| `0x800D20FC` | `0xFFFFC000` |
| `0x800D2104` | `0xFFE00000` |
| `0x800D210C` | `0xFFF00000` |
| `0x800D2124` | `0xFE000000` |
| `0x800D2594` | `0x04000000` |

The transaction brackets one 103-byte actor/pose sample at `0x800CCBCD` with these explicit words, repeated in reverse. XYZ/facing come only from this sample, not the earlier/later broad core blocks. Overlay, pending flags, raw actor floor, selectors, source identity and remapping guards also agree before/after. A same-room savestate replacement changing flags or floor cannot combine old XYZ with a detected new selection context. Changed words/guards and failed or short reads return atomic `Retry` with no partial observation. Wrong revision and unsupported source/context retain explicit modeled failures. Repeated reads detect the covered changes; they are not a stopped-world snapshot or a theorem about arbitrary changes that revert between samples.

For the pinned 169-source catalog, successful reads have at most 79 requests, 8,485 requested bytes and a largest request of 1,384 bytes, including runtime signature and repeated source witnesses. R100 uses 4,221 bytes; R101 uses 8,485. The new flags contribute 52 four-byte requests, or 208 bytes, plus one actor/pose read and two overlay reads. There is no full-RAM polling or source recompilation during a poll.

### Retained-file comparison and reproduction

Offline replay rebuilds and binds all 169 RDT sources and MAP from the explicit owned BIN, then runs the new current API on unchanged full retained RAM images. The observations below reproduce RE3-MAP-013/014's current-row native admission/renderer indices and the capture API's separate loaded-source results. Each pre-opening observation also reproduces after layout reconstruction. The three associated menu captures return `NonGameplay`.

| Retained pre-opening observation | Raw actor floor | Native group/row | Numeric layer | Group-0 indices | Native row visible |
| --- | ---: | --- | ---: | --- | --- |
| R100 exact restore | 0 | `0/0` | 0 | `[0,2,3]` | true |
| R101 lower exact restore | 1 | `0/1` | 0 | `[0]` | true |
| R101 upper exact restore | 4 | `0/1` | 0 | `[1,2]` | true |

Eight additional retained ordinary snapshots reproduce the same R100/floor-zero and R101/floor-one/two/four alternatives. Signed floor 3 selects `[1,2]` in the shared source/synthetic checks; it is not claimed as another retained pre-opening runtime observation here. R101 raw actor floors 1/2 select one feature and 3/4 another. These are signed actor floors, not lifecycle phases or physical floor IDs. The separate R100 noncurrent row-one `[1,2]` loop and group-1 callback remain evidence of different calls; the new API returns neither of them as current group-0 ownership.

Private implementation evidence is `/tmp/re-map-re3-map015-implementation-20261107-zR9itYfK/`. Run its `verify.py` with `--repo`, `--disc-image`, `--exe`, `--map`, `--native-evidence`, `--map013`, `--overlay-evidence` and a mandatory nonexistent `--output` directory. The native evidence root is `/tmp/re-map-re3-r100-map-native-20261107-nUiK0jpY/`; MAP-013 is `/tmp/re-map-re3-map013-amended-20261107/`. Inputs remain private. The verifier checks the frozen prior hashes below, records each retained RAM/menu hash and checks request counts/bytes against the exact source catalog. It does not rerun the prior native/save/cleanup experiments.

| Private artifact | SHA256 |
| --- | --- |
| MAP-014 `verify.py` | `5739397c352b9e8bcae84411e6ce39aa329a6780805c7208e96d75ab2d504f8b` |
| MAP-014 `verified-final/verification.json` | `210cd47a506e6fa3ce4ca6d855c1ce7230af04233d590d5f531ea1533a137011` |
| Overlay followup `verify.py` | `f92f2f3a12c5ee23a468cc8e44672526341cab9c0b1e0db715faafb967c02ee4` |
| Overlay followup `verified/verification.json` | `80c1aa78ba53eaf915dded9b8d891f9d5f2e33a6003c77ca282c6cf6ff42fa02` |
| Overlay followup `artifact-manifest.json` | `8d8374d8022a3d7bc5a3d1b8956c8f6d5a94c659eb9363d6933d1482e38805c7` |
| Implementation `verify.py` | `6b303757fe39606718187a3d3cfd73bb98e2ad7bc9488da245bee2ef468d864d` |
| Implementation `verified-final-reviewed/verification.json` | `6e864feaa32c0b2c20b53f7ed3b42758d27956dc13dcf6f9178af94ed90992f0` |

Twenty-nine added regression cases cover immutable nested authority, matching receipt substitution, wrong/changed inputs, required fields and spans, metadata duplicates, predicate/metadata/acquisition changes, separate row visibility, fresh reconstruction and restores, all dependency/guard changes around pose, every failed/short transaction read, pending bits, full-width overlay rejection and active menu rejection. All 2,277 RE3 checks and the full Python suite pass, with 7,139 passed and 50 skipped. Scoped Ruff, formatting, documentation links and whitespace checks pass. These are software/source checks, not runtime campaign coverage.

- 2026-11-07; implementation sub-agent, verified exact model `gpt-6.1-sol`, effort `xhigh`, session `01a1b76e-f538-79e3-95b5-e0e92ab493a3`; authored the source compiler, shared metadata/dependency changes, fresh request, tests, private offline replay and this claim. Local review checked source identity/derivation authority, physical bounds, complete dependency reads, source/pose coherence, original API preservation and the separation of row, quad, native evidence and tracker rights. No subagent or external review was started; parent and independent review remain pending.
- The supplied source-only overlay followup is authored by its recorded `gpt-6.1-sol` investigator and retained with its own date/model fields. RE3-MAP-013/014's original runtime authorship, independent reviews, save creation/restore distinctions and limits are unchanged. This implementation adds no new native evidence or parent/external endorsement.

Physical room ownership, physical-floor identity, tracker reveal rules, full-campaign admission and playthrough readiness remain unresolved. This API alone supplies no complete item/door/story model, clearance, user exploration update or runnable RE3 profile. Group-1 selection, palette interpretation and nonzero prospective overlays are outside this increment.

Integration review, 2026-11-07: Codex root and two independent agents, exact model `gpt-6.1-sol`, effort `xhigh`, review the actual implementation. Review A checks immutable authority, exact dependencies and shared capture semantics. It independently enumerates 245 logical flag dependencies across the 26 physical words, checks 39,572 row/shape flag reads against those masks and reproduces byte-identical condition/group-0/group-1/row exports across eleven retained captures. Its 1,426 focused tests pass. Review B checks shared live reads, admission, failure statuses, contiguous pose and source coherence, including 22 additional bounded probes and the complete owned-catalog retained replay. Neither review adds native observations or hardware-admission evidence.

Root identifies and corrects one coherence defect before integration. The broad initial/final guard blocks could agree while the two intervening feature-word samples agreed with each other at a different value. The returned mode/remapping context could then disagree with a physical word that had actually been read. Before sampling pose, the reader now checks the feature blocks against the original guards through the existing guard decoder. This adds no memory requests. Five regressions covering mode and remapping overlaps fail with the exact original transaction and pass with the corrected reader. Review B independently reproduces both results and rechecks the fix. The live-focused suite passes 335 tests, and the combined full suite passes 7,194 with explicit owned RE2 inputs, including the 50 cases skipped in the child run above.

The final main-checkout retained verifier reproduces all three named pre-opening selections, eight additional observations, active-menu rejection, request bounds and reconstruction. Its report matches the implementation report in every field except the changed reader's source hash. Private evidence is `/tmp/re-map-re3-map015-root-integration-20261107/`, including the original-transaction regression plugin, `retained-run/verification.json`, full/focused checks and integration manifest. The retained report SHA256 is `9b7f66abbbb1dc62b114a6d552a8756e0d5dbfb2ef672bb7fe718ad87a1a2c82`. Prior frozen evidence remains unchanged. A new Gemini 3.8 Flash high-reasoning request fails to open its Antigravity session; Claude Opus 5.5 is disabled. Neither supplies an external endorsement. Scoped Ruff, formatting, documentation links and whitespace checks pass. No renderer or UI changes require a README image update.

## RE3-MAP-016: fresh current-row group-1 detail admission and style

Status: Candidate. This extends [RE3-MAP-015](#re3-map-015-fresh-ordinary-view-current-row-group-0-source-observation) with source-bound current-row group-1 selection. Target remains Resident Evil 3: Nemesis, PlayStation, USA, SLUS-00923, supplied revision, Hard. Executable `SLUS_009.23` SHA256 `2e143418e358b2c99995cdc1a88c387163fb751912c723b755614f38e236bd29`; MAP_U.MAP SHA256 `7182beb90347fe4ea0c2a4db30dff93aaee88b8ef1b633398ffcef6f3d3d1268`. Retained runtime evidence uses DuckStation `0.1-12083-g00e299795`, native-state version 87. This increment performs only offline source/file comparisons and software tests. It starts no emulator, executes no native game code and adds no gameplay or save-restore observation.

### Explicit scope and shared source interpretation

The existing three-argument `read_current_map_features(catalog, layout, read_memory)` retains its `NativeCurrentRowFeatures` result and 26-word group-0 read plan. Passing the explicit keyword `scope=CurrentMapFeatureScope.GroupZeroAndOne` returns `NativeCurrentRowDetails` instead. Its `group_zero` member carries the existing group-0 facts, fresh projection, numeric layer and separate `native_row_visible`; `group_zero.flag_words` contains the combined transaction's complete observed word values. Separate fields contain `native_map_acquisition_byte`, the source `group_one_count`, and `group_one_allowed`. Each allowed detail names its current-row index, source `native_kind`, requested palette variant and effective palette variant. There is no optional field whose absence selects behavior.

The same `compile_map_feature_layout` pins both owned inputs and compiles both plans once. Group-1 kinds and ordered admission/style metadata become compiler-owned nested tuples under the existing nonreplaceable authority. It retains ignored selectors, duplicates and unmatched metadata. In the owned record-zero style table, row 13 / detail 1 has no corresponding source quad. The native matching scan ignores that target; the compiler preserves it and its dependency. It does not invent geometry or silently repair the source.

`select_group_one_detail` shares the complete shape/admission/style formula with `decode_native_map_detail_selection`. It calls the existing `group_one_shape_decision` and `GROUP_ONE_SYSTEM_STYLE`, with the same native current key, raw signed actor floor and raw unsigned stage. The source helper's parameter named `phase_i8` receives actor floor at this call site; it is not a lifecycle phase. Earlier allow branches bypass metadata. When metadata is reached, each matching entry rejects in system / acquisition-byte / flag order and duplicates remain conjunctive. Style entries are alternatives, selectors above 3 are ignored, and the system-style branch bypasses the style table. The shared bank tuple preserves selectors 0–3 as PS1 virtual banks `0x800D20CC`, `0x800D1FA0`, `0x800D1FC8`, `0x800D1FE8`.

The acquisition byte is `raw_flag_helper_mask & 0xFF`, matching the native byte store at `0x80072DAC`. Supported groups 0–6 have masks whose low byte is zero, even when the separate full-mask acquisition test is true. It is computed from each read, never replaced with a hardcoded zero or `bool(acquired)`. Requested variants are 0 or 2; the original renderer's kind-7 rule forces effective variant 0 while retaining the requested variant. These are source/native palette arguments, not observed GPU pixels.

Only the freshly remapped current source row is returned. Per-detail admission/style, native row visibility, physical room/floor ownership and tracker rights remain separate. A hidden row can still have admitted detail indices. Cached AA/AB/AC, loaded MAP pointers and prior polls supply no authority here. The older capture API still requires its explicit selected-record loaded-source binding and preserves its schema, values and failures. Position-only and collectible calls keep their prior accepted behavior.

### Physical dependencies and coherent reads

Both plans derive every dependency from the shared predicate trees, bounded metadata and row predicates, including branches skipped in a poll and unmatched recognized metadata. The combined plan has 28 aligned physical words, listed below as PS1 virtual addresses, not RAM offsets or host-process addresses. Every value is u32 little-endian. The masks identify source dependencies; the transaction reads and repeats each full `0xFFFFFFFF` word.

| PS1 virtual word address, u32 LE | Combined dependency mask |
| --- | --- |
| `0x800CC858` | `0x00000080` |
| `0x800D1F2C` | `0x04000000` |
| `0x800D1FA0` | `0x20040010` |
| `0x800D1FA4` | `0x00004120` |
| `0x800D1FA8` | `0x80019203` |
| `0x800D1FAC` | `0x80100000` |
| `0x800D1FB0` | `0x00040005` |
| `0x800D1FB4` | `0x00000010` |
| `0x800D1FB8` | `0x08800202` |
| `0x800D1FBC` | `0x80200000` |
| `0x800D1FC0` | `0x08000024` |
| `0x800D2008` | `0x00080000` |
| `0x800D200C` | `0x78010010` |
| `0x800D2010` | `0x80000001` |
| `0x800D202C` | `0x01000200` |
| `0x800D20CC` | `0x33E36CFF` |
| `0x800D20D0` | `0xDA000000` |
| `0x800D20DC` | `0xFFFFFFFF` |
| `0x800D20E0` | `0xFFFFFFFF` |
| `0x800D20E4` | `0xFFFFFFFF` |
| `0x800D20E8` | `0xFFFFFFFF` |
| `0x800D20EC` | `0xFFFC0000` |
| `0x800D20F4` | `0xFFFFFE00` |
| `0x800D20FC` | `0xFFFFC000` |
| `0x800D2104` | `0xFFE00000` |
| `0x800D210C` | `0xFFF00000` |
| `0x800D2124` | `0xFE000000` |
| `0x800D2594` | `0x04000000` |

The extra physical addresses relative to group 0 are `0x800D1F2C` and `0x800D20D0`; several existing-word masks also grow. Group-1 MSB-indexed flag 5 at `0x800D1F2C` has mask `0x04000000`. The same word's independent pending-UI guard still requires mask `0x00000300` clear. The mode/remapping guard masks, raw actor-floor i8 at `0x800CCBCD`, XYZ i32 LE at `0x800CCBF8` and facing u16 LE at `0x800CCC32` retain MAP-015's full-width/context rules. Actual overlay u16 LE at `0x800E0278`, mask `0xFFFF`, is freshly read and must be zero. Pending byte `0x800C7961`, mask `0xFF`, must also be zero. Active/pending UI is `NonGameplay`; nonzero ordinary overlay is `UnsupportedSettings`.

The shared transaction compares all explicit copies of overlapping mode/remapping/request guards with the initial broad reads before pose. Explicit guard copies are decoded independently because the new `0x800D1F2C` word has exactly the broad span's base address; a dictionary union would hide one sample. MAP-015's original overlap checks and regression cases remain enforced. One contiguous 103-byte actor/floor/pose sample is bracketed by the complete explicit word plan, repeated in reverse, followed by reverse source witnesses and final broad guards. Failed/short reads, detected flag/floor changes, source mismatches and every observed guard conflict reject atomically without partial publication. Repeated reads are not a stopped-world snapshot and cannot detect an arbitrary change that reverts between samples.

Rebuilding the exact catalog from the explicit owned BIN binds all 169 sources. Every source has four required witness ranges, totaling 147–2,371 bytes. The successful combined request bound is exactly 83 requests, 8,501 requested bytes and a largest read of 1,384 bytes. R100 requests 4,237 bytes; R101 requests 8,501. The combined scope adds four four-byte requests to the group-0 plan. The old group-0 maximum remains 79 requests / 8,485 bytes. No full-RAM polling or source recompilation occurs during a poll.

### Retained comparisons and limits

Eleven retained ordinary RAM paths reproduce after reconstruction. The three exact pre-opening captures give the following group-1 results. Tuples are `(detail index, native kind, requested variant, effective variant)`.

| Retained ordinary observation | Raw actor floor | Current native group/row | Group-1 allowed |
| --- | ---: | --- | --- |
| R100 exact restored | 0 | `0/0` | `[(0,4,0,0)]` |
| R101 lower exact restored | 1 | `0/1` | `[(1,4,2,2)]` |
| R101 upper exact restored | 4 | `0/1` | `[(0,4,0,0),(1,4,2,2)]` |

Eight additional retained ordinary snapshots agree with these source alternatives. All numeric layers remain 0. Full pre-change versus post-change group-0, group-1 and row capture API results agree across fourteen retained paths with twelve distinct RAM hashes: three actual source-bound menu captures succeed and eleven ordinary captures retain their explicit binding failure. The new API's current row agrees with the old group-1 capture API in eight matching retained-context pairs, comparing only relevant dependency masks, actor floor, raw stage and current key. The three menu captures reject the prospective API as `NonGameplay`. No loaded-source bytes, pointers or cached selectors are substituted to manufacture capture binding.

The separate RE3-MAP-014 callback at stop epoch 10 is tied to its actual group-1 source before comparison. Original GPRs give PC `0x8007116C`, RA `0x80070540`, S6 row 0, S4 detail counter 0, S0 style byte 0, A2 `0x801B1760`, A3 palette 0, and source base `0x801B1500`. The caller copies the S4 counter into S0 at `0x80070504`, then overwrites S0 with the style result at `0x80070530` before deriving A3. S0 therefore no longer identifies the detail at renderer entry. S4 and the unique A2 match within the current row both identify detail zero. The owned record-zero directory locates it at MAP offset 608. The retained A2 bounded read's first twelve bytes equal that owned quad, including native kind 4. Current raw selectors and cached current group/row are zero, so this call is current row zero. The pre-opening R100 prediction admits that detail with requested/effective palette 0. This is one retained callback plus bounded source bytes, not a new native run or a full RAM capture at that callback. Original callback code bytes also match the pinned executable. RA `0x8007042C` group-0 calls and the noncurrent row-one loop are excluded from this group-1 comparison. Original native/save/cleanup evidence and limits in MAP-013/014 remain unchanged.

### Reproduction, checks and authorship

Original implementation evidence is `/tmp/re-map-re3-map016-implementation-20261107-D4m5dF`. Its frozen verifier used S0 as the callback index; the integration correction below replaces that interpretation. For reproduction, copy the corrected `verify.py` and unchanged `baseline_map_selection.py` from `/tmp/re-map-re3-map016-root-integration-20261107/` together to a fresh private directory. The baseline module is the exact `082c3c9` capture selector. Run with mandatory `--repo`, `--disc-image`, `--exe`, `--map`, `--native-evidence`, `--map013`, `--overlay-evidence` and a nonexistent `--output` directory. The explicit source/evidence paths are those recorded in MAP-015. The script checks pinned inputs and frozen MAP-014/overlay/root-integration hashes, rebuilds the complete catalog, records retained input hashes, compares APIs, checks the separate callback and writes numeric reports outside Git. Frozen directories are read only. The following hashes identify the original implementation evidence.

| Private artifact | SHA256 |
| --- | --- |
| `verify.py` | `272e086092fb1f8667a1c7f57660d9b2b27075ed878d4a01b177e50c52bb770d` |
| `baseline_map_selection.py` | `eb208e21fc065c18bd56afdff663bbfef934a32c9053ef80cfd8f878fa4dd9be` |
| `verified-reviewed/verification.json` | `fb59067a6b38eecc552e677cfb710d03097be04a4beb47011fb5666b04093d4b` |
| `union_overlap_plugin.py` | `bae9842a18162cf15cea4313d24b7182cf874192df3aa7e236913cabb7240899` |
| `prior-overlap-regression.txt` | `ab059e9e57454982464fc8b8d4f30c23a82cc53c17187102bc3861011cbf56a9` |

Tests cover the original capture/group-0 contracts, exact style banks/kind-7 rule, ignored and duplicate entries, acquisition truncation, early/late/system branches, immutable nested authority, explicit current-row scope, reconstruction and clear/set/clear reversals, every compiled physical dependency around pose, overlapping broad guards including the shared-base request word, pending/active UI and full-width overlay rejection, and every failed/short transaction read. All 2,332 RE3 tests and 385 live-reader tests pass. The full Python suite passes all 7,244 tests with `RE_MAP_RE2_OWNED_CUE` explicitly set to the owned Leon disc, including the owned-binding cases. Scoped Ruff E4/E7/E9/F/I with the established E402 exclusion, formatting, local documentation links and whitespace checks pass. A private plugin restores the earlier dictionary-union overlap check: the two new request-word conflict cases fail as expected while the five inherited overlap cases pass. The production transaction passes all seven. No UI changes require a README screenshot update.

- 2026-11-07; implementation sub-agent, exact model `gpt-6.1-sol`, effort `xhigh`, verified from matching session `01a1b78d-bf8c-7753-85df-b62a257f3341` and latest turn context; authored the implementation, tests, private offline comparisons and this claim. Local final review checks source authority and bounds, native arithmetic/order/palette semantics, complete dependency plans, coherent overlap/pose/source reads, retained callback identity, API preservation and claim limits. No subagent or external review was requested or performed; root's independent/external review and integration remain pending. No parent or external endorsement is claimed.
- Human instructions set Hard as the target and supplied the owned inputs and bounded task. Existing source/runtime authorship, reviews and rejected/superseded interpretations remain in their original claims.

Integration review, 2026-11-07: Codex root and an independent agent, both exact model `gpt-6.1-sol`, effort `xhigh`, inspect the implementation and evidence. The independent review checks all 105 metadata entries, the exact 28-word union, immutable substitutions, shared capture behavior and preservation of the group-0 plan. Its 31 focused tests pass, and its retained replay reproduces the original report byte-for-byte. The frozen review report is `/private/var/folders/9d/q5n746z953bcs654g_1sqcy80000gn/T/re-map-re3-map016-review-20261107-s7j_gam5/review.json`, SHA256 `a1357fd9f2651f4d3c915747a995011173eceeddaff85edecbd097a46afe1060`.

The review identifies the callback register-attribution error described above. Root checks the original caller instructions, corrects the claim and copies the private verifier before changing it. The corrected verifier binds the index through S4 and independently requires a unique A2 match within the row. A synthetic register control changes S0 to 1 and A3 to 2 while leaving S4 and A2 unchanged; it still binds detail zero. That control checks register roles and is not another native observation. The original child evidence remains unchanged. The corrected `verify.py` SHA256 is `4f0691c47a76eaeff9eb105068063b646188194b80185716644e1e737f70140b`; its `retained-final/verification.json` SHA256 is `165a8d980d3454e6e3a7cd5ea7fcc8576c0a6c6ab00c07bcd5b4c73788fae978`. Root reproduces all 169 sources, retained selections, old capture outputs/failures and request bounds. All 7,244 full-suite tests pass with explicit owned RE2 inputs. This adds no native execution or gameplay coverage.

The root live-reader checks pass all 385 tests; scoped Ruff, formatting, 360 local documentation links and whitespace checks pass. A separate Gemini 3.8 Flash high-reasoning request fails to open its Antigravity provider session. Claude Opus 5.5 is disabled. Neither supplies an external endorsement. The failed request, exact changed-file hashes and check results are retained in the root integration evidence directory. No renderer or UI changes require a README image update.

Physical room/floor ownership, actual hardware L2 admission/menu opening, tracker reveal/history, complete items/doors/clearance, full-campaign coverage and a runnable RE3 profile remain unresolved. Source texels, quad metadata and palette arguments do not establish game GPU pixels.

## RE3-MAP-017: camera zones do not establish room or floor ownership

Status: Rejected as a camera-only association between selected contours and physical room/floor footprints. The native camera interpretation remains Candidate for the same pinned USA SLUS-00923 Hard revision and EXE/MAP identities as RE3-MAP-016. This tests one proposed spatial join against three retained observations from MAP-013/014/015. It adds zero physical room/floor bindings and no emulator, native execution, map-opening, save-restore or gameplay observation. The retained DuckStation version remains `0.1-12083-g00e299795`.

The original camera code at `[0x8002A84C,0x8002A9AC)` selects the first source-camera zone, then scans subsequent enabled records for transitions. Each 20-byte RDT record has enable byte 0, signed byte 1, camera key/target bytes 2/3 and four signed i16 LE X/Z pairs at +4..+19. Transition byte 1 must equal raw actor floor i8 at PS1 virtual `0x800CCBCD`, mask `0xFF`, or be wildcard -128. The first polygon also supplies a separate entity-culling point test. These roles do not declare architectural floors or MAP ownership. A separate native path at `[0x80051864,0x800518C4)` can modify first-zone coordinates; this comparison requires each retained source witness to match rather than assuming immutable camera polygons in every state.

The candidate compares requested-palette-2 source masks with the current first camera polygon, including the more permissive union with eligible transition polygons. Each occupied source-cell origin is inverse-projected at exact integer multiples of 450 using the existing source anchor. The original zone test at `[0x8001020C,0x800102E8)` uses signed low-32-bit products. Its classifications match unbounded products on all tested lattice points. Counts below are sampled cell origins, not intersection area, whole-cell containment, navigability or GPU pixels.

| Retained context | Camera | First zone RDT byte offset | Selected mask cells | Origins inside first zone |
| --- | ---: | ---: | ---: | ---: |
| R100 | 0 | 216 | 527 | 527 |
| Lower R101 | 10 | 1816 | 2961 | 625 |
| Upper R101 | 6 | 1576 | 2416 | 379 |

All three poses lie inside their first polygon, whose attributes are `0x8001`, including the wildcard high byte. Lower R101's camera-10 polygon accepts identical 625-origin sets from selected quad 0 and excluded quad 2. Adding its eligible transition at RDT offset 1856 produces identical 628-origin sets. Upper camera 6 accepts 427 origins from inactive quad 0, more than the 379-origin selected union. Camera overlap therefore neither recovers the complete selected masks nor distinguishes the lower/upper alternatives. Raw actor floors 1/4 and native numeric layer 0 retain their existing nonarchitectural meanings.

The complete 169-source binding contains 2105 camera records and 4585 zones, with 2091 contiguous first groups. Fourteen camera indices across eight sources lack a group despite being below camera count. A count check alone cannot authorize a generic zone lookup. This does not establish that those indices occur during gameplay. The census retains 76 target bytes at or above camera count as uninterpreted source values. It does not label them invalid-camera bugs. Of the first groups, 2082 have attributes `0x8001`; the other nine prevent a universal wildcard-first-polygon assumption.

Frozen private evidence is `/var/folders/9d/q5n746z953bcs654g_1sqcy80000gn/T/re-map-re3-camera-join-20261107-t_f4_eou/`. `reproduce.py` requires explicit `--repo`, owned `--disc` BIN and a nonexistent `--out`. All contour/report/RAM inputs it reads are relative copies under `inputs/`; it does not rely on a prior transient contour path. The report SHA256 is `acec71c4406a10121078f568d06c2e1546ead202d7a2a5d3c6e04ca13c5d3dad`, the corpus SHA256 is `1f4485bb03c0656bd5d3b26bf47b5d6a2a92c12fac3972e4e73023be5f739bf4`, and the 60-file manifest SHA256 is `6f2fb5f5927cdcc6052480fd0da0afbd5a1fd02af66aa0e9ca06714e1a8c4110`. Initial calculation and output-truncation failures remain recorded separately and supply no accepted result.

Contribution, 2026-11-07 UTC: the independent investigator, verified `gpt-6.1-sol`, effort `xhigh`, authors the source/camera investigation and private verifier. Root, the same exact model and effort, checks all 60 hashes and reproduces the report and census byte-for-byte from a separate copy. A separate root calculation reads the RDT coordinates directly and uses polygon symmetric difference and polygon coverage, independently of the investigator's ray counter and native point-test formula. It reproduces all per-quad counts and the equal 625/628-origin sets. Root writes this claim. No production reader, renderer, UI, exploration history or source data changes.

Integration review, 2026-11-07 UTC: a second independent agent, verified `gpt-6.1-sol`, effort `xhigh`, finds no issue in the numerical/source/provenance scope. It checks all 60 artifact hashes, freshly reruns both calculations, decodes all eleven native windows and verifies the claim's counts, widths, limits and authorship. Tested signed-subtraction intermediates stay within 28684, so an omitted signed-overflow trap does not affect these samples. Its frozen review is `/tmp/re-map-re3-map017-review-20261107-uXxuPGUH/review.json`, SHA256 `19adb6228385cd7432a2cd9f981b4624e6e1d5b42e1a3a99759e510aed110eee`. Root evidence is `/tmp/re-map-re3-map017-root-integration-20261107/`; the independent geometry report SHA256 is `327ed29a94ffd1c4bbed8d3bcdd122a81dce97e2e119334d56df8882ff3b8e5a`. Local documentation links and whitespace checks pass. A Gemini 3.8 Flash high-reasoning request fails to open its Antigravity session; Claude Opus 5.5 is disabled. Neither supplies an external endorsement. No UI change requires a README image update.

This rejects camera-clipped exploration as an ownership rule. The next bounded source check is height producer `0x8004D720`, reached by the original caller at `0x80033C64` before passing its result to the raw-floor publisher. It must establish a bounded support-region role before another ordinary native observation can address that association. Existing ramp-record/height observations alone do not supply it. Physical floors, room-owned contours and tracker reveal remain unresolved.

## RE3-MAP-018: the support index is bounded, but height also consumes runtime work

Status: Candidate source and copied-component contracts for the supplied USA
SLUS-00923 revision, targeting Hard. This follows MAP-017's height-producer lead.
It adds no physical floor/room association, campaign admission, live reader,
exploration or gameplay observation. The executable remains `SLUS_009.23`,
SHA256 `2e143418e358b2c99995cdc1a88c387163fb751912c723b755614f38e236bd29`.
No DuckStation instance or save is loaded. Historical DuckStation version and
confirmation limits remain unchanged.

### Original inputs and the source index

All addresses below are PS1 cached virtual addresses; multibyte fields are
little endian. The original caller at `0x80033C64` passes a prepared XYZ vector,
u16 work field `+0x1A`, one of three query masks selected by work-category u8
`+2`, and mode `9`. The mask table at `0x8009CBC8` contains u32 values
`0x8000`, `0x0800`, `0x0200`. Before this call, the caller can subtract the
actor's signed i16 `+0x1B8` adjustment from the prepared Y. These are inspected
caller roles, not a new general player/lifecycle admission rule.

Height producer `[0x8004D720,0x8004DB10)` reads the loaded RDT pointer at
`0x800CC86C`, then its relocated collision pointer at RDT `+0x20`. Its candidate
leaf `[0x8004DDC4,0x8004DE40)` uses a 16 by 16 grid after the 16-byte collision
header and records. The header count includes the header. A 512-byte table of
u16 offsets follows `16 * count` bytes; nonempty offsets are relative to the
byte list after that table. `0xFFFF` means no bucket. Each nonempty bucket is
a nonempty list of u8 record indices terminated by `0xFF`; index zero names
the first record after the header. Empty non-`0xFFFF` buckets are not admitted
by this source contract, because the native copy reads the first byte before
testing the following byte for termination.

The producer first bounds X and Z to the signed 16-bit coordinate domain. For
those inputs, the leaf selects
`((Z + 32768) >> 12) * 16 + ((X + 32768) >> 12)`. The coordinates remain i32
vector members; this domain comes from the producer's explicit guard. A
coordinate outside that domain can return the collision header's signed i16
height at `+0x0E` without proving support or room membership. A returned height
alone therefore does not establish a source footprint.

Fresh owned-disc inspection reconstructs all 169 sources and every bucket:

| Source property | Count or bound |
| --- | ---: |
| Collision records, excluding headers | 5,289 |
| Grid cells | 43,264 |
| Nonempty cells | 15,593 |
| Maximum records in one source | 75 |
| Maximum candidate indices in one bucket | 24 |
| Buckets with duplicate indices | 0 |

The existing complete native source binder independently accepts these exact
sources and their native file indices. Its corpus digest remains
`2e044734044d39327bdfabcb40c81a6f51e4f97f9859f0609e36217ce5fadaba`.
This is source compilation; no live code-signature read is performed here.

Every bucket offset and terminator fits its collision-section extent, and every
index names an actual record. R100 has 14 records and maximum bucket length 5;
R101 has 75 records and maximum length 18. These are source extents, not a
runtime guarantee that loaded collision flags or index storage are unchanged.

The original leaf matches the independent parser in 43,940 copied-code calls:
all 256 cell centers plus the four signed-domain corners for every source.
Each call checks the return value, every data-read/store range, exact output
bytes and complete two-MiB synthetic RAM against expected changes. The 66,963
byte stores stay in the declared result interval; empty cells leave it intact.
Original leaf SHA256 is
`e6cca3e1ed1a2ab7aa4679a2d7baf25624b70ec4a26eb8c1a8d24f21e339245a`.
This validates the bounded component and source parser, not runtime loading,
physical ownership or a native game observation.

### Selection and the separate runtime pass

The producer tests each selected record's u16 flags at `+8` against the caller's
mask, a signed floor-threshold byte at `+0x0C`, and geometric bounds. Attribute
u16 `+0x0A` mask `0x1000` selects its rotated-coordinate path. Low nibble
`flags & 0xF` chooses a handler from the two 13-entry tables at `0x8009E020`;
mode bit `8` chooses the second table. For caller mode `9`, its non-pass-through
entries are kinds `1`, `9`, `10`, `12`. This identifies query roles, without
equating every collision polygon with a walkable floor. Loaded flags require
their own fresh binding; the historical record mutation in
[RE3-INPUT-004](hard-start.md#re3-input-004-ordinary-reentry-attempt-reaches-a-disabled-collision-record)
remains separate runtime evidence.

Before returning, the producer calls `[0x8004DB10,0x8004DDC4)`, which also reads
runtime records beginning at `0x800DCED8`. Their stride is `0x18`, with sentinel
u32 `0xFFFFFFFF` at `+0x0C`. This pass uses additional masks and can consume an
owner pointer or construct temporary geometry. It is not supplied solely by
the owned RDT. Its writes to scratch fields at `0x800DEB58 +0x28/+0x2C` also
distinguish selected runtime owners.

Three direct copied-tail controls use the same owned R100 collision header,
synthetic XYZ `[0,-1900,0]`, radius argument `450`, category-zero mask, mode `9`
and incoming static height `0`. An empty runtime list returns `0`. One matching
synthetic kind-one rectangle with height `-1800` returns `-1800`. Clearing its
query-mask bit restores `0`. The source and input pose remain byte-identical,
the original stack is restored, and all stores fit declared scratch/stack
ranges, including the native argument homes. These are explicitly synthetic
component controls; they do not claim that this runtime object exists in R100
or establish a full-height gameplay result.

The attempted full-producer probe is not accepted. It escapes to PC zero after
the trace reports two entries to `0x8004DB10` with different stack pointers;
the original return frame is not preserved. Its CPU exception and bounded
early-stop diagnostics remain in the private evidence. No game instruction is
patched and no simulator-bug diagnosis is claimed. The accepted direct-tail
controls enter that component separately. Neither the failed probe nor the
direct-tail controls supplies a complete producer proof.

### Reproduction, limits and contribution

Private durable evidence is under
`/Users/adamekka/.cache/re-map/evidence/2026-11-12-re3-height-producer/`.
Run from the repository root with Python 3.12, the repository's
[development requirements](../../../requirements-dev.txt), and Capstone
`5.0.7`. The verification environment below has those dependencies and Unicorn
`2.1.4`; a new environment also needs `pip install capstone==5.0.7`.
Every output path must be new. The complete accepted reproduction is:

```sh
set -e
re3_python=/Users/adamekka/.cache/re-map/verification-venv/bin/python
re3_evidence=/Users/adamekka/.cache/re-map/evidence/2026-11-12-re3-height-producer
re3_cue='/Users/adamekka/Games/DuckStation/Resident Evil 3 - Nemesis.cue'
re3_image='/Users/adamekka/Games/DuckStation/Resident Evil 3 - Nemesis.bin'
re3_output=/absolute/path/to/new-evidence-directory
PYTHONPATH=src:tools "$re3_python" "$re3_evidence/inspect_height.py" --cue "$re3_cue" --out "$re3_output"
PYTHONPATH=src:tools "$re3_python" "$re3_evidence/census_support_index.py" --image "$re3_image" --out "$re3_output/index-census.json"
PYTHONPATH=src:tools "$re3_python" "$re3_evidence/bind_inputs.py" --image "$re3_image" --catalog "$re3_output/catalog.json" --census "$re3_output/index-census.json" --out "$re3_output/source-binding.json"
PYTHONPATH=src:tools "$re3_python" "$re3_evidence/verify_native_index.py" --image "$re3_image" --catalog "$re3_output/catalog.json" --census "$re3_output/index-census.json" --out "$re3_output/native-index.json"
PYTHONPATH=src:tools "$re3_python" "$re3_evidence/probe_height_dependency.py" --image "$re3_image" --catalog "$re3_output/catalog.json" --component dynamic-tail --incoming-height 0 --point 0 -1900 0 --radius 450 --category 0 --out "$re3_output/dynamic-tail.json"
```

`inspect_height.py` requires `--cue` and a nonexistent `--out`; it verifies the
disc/executable before rebuilding the complete catalog and decoding bounded
native windows. `census_support_index.py` requires the owned `--image` and a new
`--out`. `bind_inputs.py` requires `--image`, `--catalog`, `--census`, `--out`
and checks those sources through the existing complete native binder.
`verify_native_index.py` takes explicit `--image`, `--catalog`,
`--census`, `--out` and reproduces every source/cell comparison. The direct-tail
probe additionally requires explicit component, incoming height, XYZ, radius
and category arguments. No earlier transient evidence or RAM capture is needed
for these source/component results. The manifest binds scripts, outputs,
original native windows and failed diagnostics.

A future support observation needs fresh loaded collision/index binding,
mutable flags and runtime-work handling alongside the caller's mode and mask.
It must preserve the distinction between a default height, a source-selected
support and a runtime-selected support. None establishes architectural floor
labels, room-owned MAP masks or reveal rights by itself. MAP-017's rejected
camera-only association remains rejected. No production code, UI, persisted
history or README image changes in this increment.

Contribution, 2026-11-12: root, exact executing model `gpt-6.1-sol`, effort
`xhigh`, authors the fresh source census, copied-index comparison, direct-tail
controls, preserved failed probes and this record. Source inspection, copied
native execution and gameplay confirmation remain distinct.

Independent review, 2026-11-12: `review_trusted_door_core`, verified executing
model `gpt-6.1-sol`, effort `xhigh`, checks all 44 evidence hashes, the owned BIN,
fresh source reconstruction and binding, all 43,940 copied index calls, a
separate raw bucket parser and a separate direct-tail register-preservation
control. The review identifies missing import-path/dependency instructions.
Root adds the explicit recipe above; its independent fresh rerun matches all
seven semantic outputs, with only elapsed time differing. Review and recipe
evidence are retained in the private `2026-11-12-re3-height-producer-core-review/`
and `verification-existing-venv-core/` directories. Configured Claude Opus 5.5
is disabled; Gemini 3.8 Flash high fails to open its provider session. Neither
supplies an external review or gameplay endorsement.


### Follow-up: corrected full-function controls

A later bounded investigation on 2026-11-12 identifies the original probe's
`UC_HOOK_MEM_WRITE` instrumentation as the cause of its duplicated callee
prologue. The existing [MIPS-AUDIT-001](../native-mips-audits.md#mips-audit-001-observe-stores-without-a-memory-write-hook)
records the same delay-slot limitation. The eight-variant matrix uses identical
original instructions, synthetic RAM and o32 inputs. No hooks, code hooks, and
code plus read hooks return correctly. Adding the write hook to the same
code/register hook reproduces two `0x8004DB10` entries, a stack one `0x38`-byte
frame too low and PC zero. The matrix's read-hook control also has the code
hook; a standalone read-hook-only run is not claimed. This diagnoses the
instrumentation in the named Unicorn environment, not a game defect or a
universal simulator fault. The original failed probes remain frozen and
rejected.

The original native call setup needs no repair. The outer frame moves SP from
`0x801E0000` to `0x801DFF98`. JAL at `0x8004DAD8` returns to `0x8004DAE0`;
its delay-slot SW at `0x8004DADC` places the fifth argument at `0x801DFFA8`.
One tail prologue moves SP to `0x801DFF60`, whose `+0x48` reads that same
argument. Executing that prologue twice accounts for the rejected frame loss.

A new private probe enters the original complete function at `0x8004D720`,
with the unchanged real callees and no memory-write hook, instruction patch,
stub or PC repair. It reuses the existing shared store auditor. Three audited
runs return heights `0`, `-1800`, `0` for the empty, matching and masked runtime
lists, in 160, 224 and 178 instructions. Each reaches the tail once, returns to
`0x80008000`, restores SP, RA and seeded S0-S7/FP/GP, and predicts 30 stores
within the declared stack/scratch bounds. Predicted loads equal the safe
memory-read observations. Store predictions are accepted only after completed
return and exact two-MiB RAM comparison; each complete RAM image and all 32
GPRs also equal its unhooked counterpart. A pre-instruction callback alone is
not reported as an observed completed write.

All three calls select empty static grid cell 136 in the same owned R100 RDT.
They therefore cover the header's default static height plus the runtime
support pass. They do not exercise static shape handlers or prove every
producer branch. The earlier direct-tail controls remain independently bounded
evidence. Neither these full-function controls nor the earlier index census
grants live binding, Hard admission, physical floor ownership or reveal rights.

The new evidence is
`/Users/adamekka/.cache/re-map/evidence/2026-11-12-re3-full-height-harness-diagnosis/`.
Its original report, scripts and hashes remain unchanged. Root adds explicit
input/output wrappers that pin the catalog and shared auditor and require new
output directories. From the repository root, with the same verified Python
3.12 dependencies:

```sh
set -e
re3_python=/Users/adamekka/.cache/re-map/verification-venv/bin/python
re3_followup=/Users/adamekka/.cache/re-map/evidence/2026-11-12-re3-full-height-harness-diagnosis
re3_catalog=/Users/adamekka/.cache/re-map/evidence/2026-11-12-re3-height-producer/source-inspection-extended/catalog.json
re3_image='/Users/adamekka/Games/DuckStation/Resident Evil 3 - Nemesis.bin'
re3_full_output=/absolute/path/to/new-full-height-evidence
re3_matrix_output=/absolute/path/to/new-hook-matrix-evidence
"$re3_python" "$re3_followup/root_verify_full_height.py" --image "$re3_image" --catalog "$re3_catalog" --snapshot "$re3_followup/snapshot" --out "$re3_full_output"
"$re3_python" "$re3_followup/root_diagnose_matrix.py" --image "$re3_image" --catalog "$re3_catalog" --snapshot "$re3_followup/snapshot" --out "$re3_matrix_output"
```

Contribution, 2026-11-12: `review_trusted_door_core`, verified executing model
`gpt-6.1-sol`, effort `xhigh`, authors the isolated instrumentation matrix and
corrected private full-function controls on immutable `3af7197`. Root, the same
separately verified model and effort, inspects the native call and audit bounds,
adds explicit reproduction arguments, verifies all original artifact hashes,
and independently reproduces identical complete control JSON and all eight
matrix results after excluding elapsed time. Root records the matrix's exact
hook combination and writes this follow-up. No emulator, save, history, input,
production code or profile changes occur.


Independent follow-up review, 2026-11-12: `review_re3_full_height`, verified
`gpt-6.1-sol`, effort `xhigh`, checks eleven artifact hashes, seven preserved
source/rejection hashes, five native windows, frame arithmetic, empty cell136,
the unchanged shared auditor and reproduction instructions. Fresh wrapper runs
match the complete control output and all eight matrix results, with elapsed
time excluded, and all32 local document links pass. The report returns no
findings within that scope and is retained under
`2026-11-12-re3-full-height-independent-review/`. Configured Claude Opus 5.5
remains disabled; the fresh Gemini 3.8 Flash high review fails to open its
provider session. It supplies no external endorsement. Root retains those
results beside the new reproduction wrappers and their hashes.

### Follow-up: retained inputs do not establish an eligible recurring query

Status: Candidate source/input contract for the same pinned SLUS-00923 revision
and Hard target. No height call, support result, physical floor/room binding,
tracker admission or visit is added. The six retained inputs below were created
with DuckStation `0.1-12640-gbb4e9ac5e`; they are separate from the older MAP-013/014
captures made with `0.1-12083-g00e299795`.

The documented R100/lower-R101/upper-R101 evidence paths are absent on this
machine. A bounded inventory finds none of their three recorded RAM hashes
among 21 two-MiB files in four explicit retained November 12 research trees.
It examines neither archive payloads nor original user saves/history. This is
a current reproducibility gap, not a rejection of the original observations.
Their selected-mask comparison remains unclosed without the original inputs.

The changed scope binds six R10D captures to the complete 169-source corpus.
Their entire 1,636-byte loaded collision/index section, 39 records including
the header, equals owned source SHA256
`00f7421777e57655c426e675d8bad52bd8b2d544ff6c27b48101df45f183525c`.
The loaded RDT is `0x8011A708`, collision pointer `0x8011C78C`, source offset
8324. This exact sample match supplies no universal mutable-flag guarantee.
The ordered work list contains eight other actors before player work
`0x800CCC44`, bound to owner `0x800CCBC4`, then a zero terminator. The verifier's
list bound is diagnostic, not a newly established native allocation capacity.

All addresses here are cached PS1 virtual addresses, with little-endian
multibyte values. Category is u8 work `+2`, radius is u16 `+0x1A`, prepared XYZ
are i32 `+8/+0x0C/+0x10`, and owner Y adjustment is i16 `+0x1B8`. All six have
category zero, radius 450, adjustment zero and category-mask table value
`0x8000` at `0x8009CBC8`. The original caller supplies mode 9.

| Gate representation | Location | Width and mask |
| --- | --- | --- |
| Work flags | work `+0x2E`, `0x800CCC72` | u16, `0x0080` |
| Aligned overlapping word | work `+0x2C`, `0x800CCC70` | u32, `0x00800000` |
| Owner-relative alias | actor `+0xAE` | u16, `0x0080` |

The recurring caller reads the flags at `0x80033C4C`, masks `0x0080` at
`0x80033C54`, and branches over the height call when clear at `0x80033C58`.
Its delay slot always clears work-byte `+0x39` mask `0x08`. The call at
`0x80033C64` otherwise supplies mode 9, then passes the result to raw-floor
publisher `0x8004B7E8`. All six retained player flags are `0x4000`, `0xC000`
or zero, with `0x0080` clear. Entering this caller with those fields would skip
the height query. These captures do not observe that branch executing or prove
the fields' future values. One capture is paused and retains its existing
native-audit pause rejection.

The dispatcher prepares work and collision state before that caller. Its
`0x06C0` and `0x00C0` preparation masks preserve the gate. Static pass
`0x8004AF04` returns before recomputation when X/Z and radius equal their prior
values. All six retained inputs satisfy that condition, but earlier preparation
could change the inputs. Recalculation instead clears `0x00C0` at `0x8004AFF8`;
admitted shape paths can set `0x0080`. R10D's one direct setter candidate,
zero-based record 10, fails region and radius-expanded X filters in all six.
Those filters are hypothetical and dominated by the unchanged-input return.
The inspected halfword stores at work `+0x2C` preserve the gate; a word alias
would not. The candidate store scan includes data and unrelated structures and
does not establish global writer or actor/VM closure.

The gate is not universal. Registration `0x80033580` calls helper `0x80034124`,
which clears work flags and, for category below three, calls the same height
producer at `0x8003425C` without a `0x0080` test. It stores the returned u16 to
owner `+0x122`. This is an inspected source counterexample, not an observed
registration, an invented entry state or an executed height call.

The next recurring-query observation needs the original caller with its gate
set, owner/work identity, prepared XYZ/radius/category/mode, freshly bound
collision/index bytes and bounded runtime records/owners. No gate was forced
and no synthetic direct call substituted for that missing observation. Default,
static-selected and runtime-selected support, physical floors, contour ownership
and tracker reveal remain separate unresolved contracts.

Private evidence is under
`~/.cache/re-map/evidence/2026-11-13-re3-support-input-contract/` and
`~/.cache/re-map/evidence/2026-11-13-re3-support-gate-producer/`. Their
`reproduction-argv.json` files declare every required image/catalog/capture,
source-investigator metadata and provenance input. Run the explicit `inspection`,
`inventory` and `argv` vectors with each `--out` replaced by a fresh absolute
path. Original report SHA256 values are
`4a6fe31e80b9518441a64a948daad6e84ef0187131b8ffa65ac7495813c1dabb`
and `62dd56b0e618afc36e0a358b3c1096c56c44f35f05ba4d3d7059788bb23def8a`.
The original research manifests bind all 56 preserved artifacts.

Contribution, 2026-11-13: investigator `investigate_re3_support_join`, verified
`gpt-6.1-sol`, effort `xhigh`, authors the source/input verifiers, bounded
calculations and private handoffs. Root, separately verified as the same exact
model and effort, inspects the original branch/delay-slot and registration
instructions, reruns all three vectors in new private directories and writes
this follow-up. The gate report and availability inventory reproduce
byte-identically. The input report differs only in selected source-investigator
author metadata after its later turn; all numeric/source/input fields agree.
All 56 original artifact hashes remain unchanged. Root's comparisons are under
`~/.cache/re-map/evidence/2026-11-13-re3-support-integration/`.
No emulator, native restoration, GPU/UI,
history, production predicate or runtime profile changes occur.

Independent review, 2026-11-13: `review_re3_support_contract`, verified
`gpt-6.1-sol`, effort `xhigh`, reports no findings in the source/evidence and
documentation scope. It independently extracts all 169 owned sources, checks
eight native windows and 22 instruction-word/control-flow facts, reconstructs
the six work/input/alias contexts and all 256 R10D index cells, and checks
fresh-output refusal and explicit failure receipts. Its three fresh reruns
preserve all 56 original artifacts and 12 capture/receipt inputs. Exact review
and limits are in
`~/.cache/re-map/evidence/2026-11-13-re3-support-contract-independent-review-01a1d478/`.

The configured external snapshot review returns "No findings." T3 reports
`gemini-3.8-flash`, requested `thinking_level=high`, through Antigravity,
without a separate executed-model attestation. It inspects the supplied
verifiers, bounded native excerpts, numeric results and documentation, with no
tools or execution. Configured Claude Opus 5.5 remains disabled and supplies
no review. Candidate status and all missing runtime/ownership contracts remain
unchanged. Root's final manifest retains the reviewed source/artifact hashes,
review responses, reproduction commands, local link checks and limitations.

## RE3-MAP-019: an original constructor query reaches its height consumer

Status: Candidate for Resident Evil 3 Nemesis, PS1 USA NTSC-U, SLUS-00923,
targeting the previously human-selected Hard seed retained by
[NATIVE-006](native-contracts.md#re3-native-006-a-restored-seed-reaches-source-bound-world-and-native-exit).
This adds one original
constructor query to [MAP-018](#re3-map-018-the-support-index-is-bounded-but-height-also-consumes-runtime-work).
It does not establish a recurring query, positive campaign admission, selected
support, physical floor/room ownership or tracker visibility. The source
follow-up below attributes this exact sampled return to a header fallback.
The executable
SHA256 remains `2e143418e358b2c99995cdc1a88c387163fb751912c723b755614f38e236bd29`.
The private DuckStation is `0.1-12640-gbb4e9ac5e`, binary SHA256
`ddceaaa426e67e328430fcb916320803fddc014374ea45a00778e58081f36dcb`.

### A changed restore route, with the failed attempt preserved

The earlier file-dialog attempt never verified a restore. Its final coherent
RAM was BIOS-only, SHA256
`9c4fd8def18ba905b6be191d05824a2cd3115e6f8d5354a2da2a68a203b1e143`.
It observed zero constructor calls, height returns or consumers. UI binding
failures and the disabled Open action are retained; unknown actions were not
repeated. Its exact-owned PID 84278 exits zero and port 2427 is freed according
to the retained cleanup receipts. This failure is separate from the new run.

The changed route follows original DuckStation source at commit
`bb4e9ac5e6b3872126dc76f1fe4f46169c96b082`.
[QTHost](https://github.com/stenzek/duckstation/blob/bb4e9ac5e6b3872126dc76f1fe4f46169c96b082/src/duckstation-qt/qthost.cpp#L3425)
accepts `-statefile` without a boot filename. Its `-version` path prints the
version then returns false from argument parsing; main returns exit 1. The
new check accepts that status only alongside the exact expected version
banner and pinned binary, never an arbitrary nonzero exit or empty output.
[System](https://github.com/stenzek/duckstation/blob/bb4e9ac5e6b3872126dc76f1fe4f46169c96b082/src/core/system.cpp#L1744)
selects existing saved media from the state header. It loads the state before
GDB initialization and the final startup pause, using `Main/StartPaused`.
The source receipt pins QTHost SHA256
`6b966bbf9c11733cbb8f0db85772ae2d03be5b9bfc91fd90099109ec3dcaef2d`
and System SHA256
`b395cd59bda7d110a72b2ae6fb7458945cc0fc327d13141b1b36c4c6415c5a22`.

The new private invocation is
`DuckStation -nogui -nofullscreen -batch -statefile <private>/seed.sav`.
Before spawning automatic loading, both achievement namespaces have Enabled,
ChallengeMode and UseRAIntegration false; cards are None, overrides and BIOS
instruction patches are disabled, audio is muted and the private black shader
is configured. No accounts, cheats or controller input are supplied. The saved
media path at native v94 header byte 168, u32 LE length/offset, names the owned
CUE; its BIN SHA256 is
`d6c828dc92d50b28fd58329dbe607d4d22eeaeb1d9a46be54ac81b130fc2c7a6`.
There is no executable override. The actual boot log confirms that media.
The later PID/listener audit is explicitly post-automatic-load. It does not
replace the prelaunch configuration proof or claim to precede loading.

One early controller exits before connecting because the listener is not yet
ready. After actual listener ownership is checked, one client connects; the
restore is not repeated. The first live two MiB RAM equals the seed payload
exactly, SHA256
`9d880e76f431a6bd946785c602b65f2f0b17fd6760ac94de3a2196229289ca0a`.
PC is `0x800292F0`. GPR0..31, HI/LO and PC also match the prior exact stock
restore receipt. Seed SHA256 is
`9fd59cebaa32a0c007663d4437a481d067f83fac2863be760515d3366e93cc56`;
its prior Hard provenance remains separate from a fresh difficulty selection.
No complete-device or buffered/current-instruction equality is claimed.

### Original arguments, return and store

All addresses below are PS1 cached virtual addresses. Captured multibyte
fields are little endian. Seven bounded host-timed resumes traverse startup;
the eighth reaches the constructor. Host seconds are not guest frames. All 25
sampled input words are zero; no guest-memory, PC, pose or flag write is sent.

| Original stop | Observation |
| --- | --- |
| `0x8003425C`, before JAL | S1 work `0x800CCC44`, S3 owner `0x800CCBC4`, A0 vector pointer `0x801FF9F0`, A1 radius 450, SP `0x801FF9D8` |
| `0x8004D720`, function entry | XYZ i32 `[13262,0,-12537]`, A1 450, actual A2 mask `0x8000`, A3 mode 9, RA `0x80034264` and unchanged caller SP |
| `0x8004DAD8`, before runtime tail | S3 intermediate 0, six source-index candidates and an immediate runtime-list sentinel |
| `0x80034264`, return | V0 signed i32 zero; SP, RA, S0-S7, FP and GP equal their actual entry values |
| `0x80034268`, consumer stop | Width-two native write watch reports owner `+0x122`, address `0x800CCCE6`; original SH stores V0 low u16 zero |

Pre-JAL A2 is still `0x801FF9F0` and A3 is 1380. The preceding LW and JAL delay
slot prepare the final arguments, so the actual function-entry registers define
the query. They must not be replaced by the earlier pre-JAL values. Pinned
[CPU source](https://github.com/stenzek/duckstation/blob/bb4e9ac5e6b3872126dc76f1fe4f46169c96b082/src/core/cpu_core.cpp#L1604)
and [GDB source](https://github.com/stenzek/duckstation/blob/bb4e9ac5e6b3872126dc76f1fe4f46169c96b082/src/core/gdb_server.cpp#L1137)
also distinguish delayed loads and deferred memory-watch stops.

The consumer field already contains zero. Return and consumer RAM are
byte-identical, SHA256
`b333e43794e5c9783da30c53ce9adcef82934915859b21f52586e387b5866309`.
That equality alone proves no write. The separate native watch receipt and
the original SH decoded against actual return registers establish its target,
width and value. No copied execution substitutes for this native observation.
No new checkpoint was created; only the existing seed was restored.

### Fresh source and constructor-phase limits

All 169 owned sources are reconstructed and bound. Each of five stopped call
captures uniquely binds `CD_DATA/STAGE1/R10D.ARD`, native file index 413,
RDT SHA256 `b49017b7a7bd28d71f1129001d2acffb6ce549928f700e9a927a5f19ad4cddb2`.
RDT pointer and allocation are `0x8011A708`. Its relocated u32 collision
pointer at `+0x20` is `0x8011C78C`, source offset 8324. All 1636 bytes of
geometry, flags and index match the owned section in all five samples,
SHA256 `00f7421777e57655c426e675d8bad52bd8b2d544ff6c27b48101df45f183525c`.
The count is 39 records including the header. Full query/caller/handler code
windows also match. These sample bindings do not imply future immutability.

The actual grid cell 75 yields indices `[19,20,30,32,35,36]` and a `0xFF`
terminator, matching the original output buffer at `0x800DEB98`. Their kinds
are `[2,2,2,4,4,6]`; mode 9 entries name `0x8004DEA8`. This is a native
nonempty-bucket observation. It does not admit every listed record. Header
height i16, S3 at DAD8 and V0 are all zero. Scratch flags/attributes at
`0x800DEB7C/0x800DEB7E`, both u16, are `0x1000/0`. No DAA0 stop occurs while
DAA0 and DAD8 are both armed. These separate native observations alone do not
close candidate admission, winner selection or default/static attribution.

Work `+4` u32 names the owner, category u8 `+2` is 0 and radius u16 `+0x1A`
is 450. Linked head/tail at `0x800DCED0/0x800DCED4` both name `0x800CCC44`,
whose next pointer u32 `+0x34` is 0. Ordinary ordered array `0x800DCDD0`
still starts with zero; a later ordinary slot-eight association is not reused.
Runtime work at `0x800DCED8`, stride 24, has u32 sentinel `0xFFFFFFFF` at
`+0x0C` in all five samples. This sampled list is empty; no runtime owner
pointer or future list lifetime is inferred.

The constructor bypasses the recurring `0x0080` gate. Work `+0x2E` u16 and
its aligned `+0x2C` u32 alias are both zero; the recurring masks would be
`0x0080/0x00800000`. This is not the recurring caller `0x80033C64` or its raw
floor publisher. All five samples remain NonGameplay in the existing reader,
with Hard/campaign admission unresolved. One constructor context stays
Candidate, not Confirmed. Room/contour/floor associations, reveal, visits,
clearance, memory-card persistence and a production profile remain unresolved.

### Bounded source attribution of this sampled return

A subsequent source/data investigation traces every admission branch for
these exact captured inputs, without CPU or emulator execution. All five
samples bind the complete original code windows and collision data. The
verifier checks 45 instruction words and the actual short-circuit arithmetic.
Each indexed record is rejected before a shape handler or winner update:

| Record | First rejection | Native branch |
| --- | --- | --- |
| 19 | Z delta 6022 exceeds width 3390 | `0x8004D9A8` |
| 20 | Z delta 6254 exceeds width 3246 | `0x8004D9A8` |
| 30 | X delta 18097 exceeds width 17128 | `0x8004D984` |
| 32 | Wrapping u32 X delta `0xFFFFF9B5` exceeds width 6242 | `0x8004D984` |
| 35 | Wrapping u32 X delta `0xFFFFF839` exceeds width 5332 | `0x8004D984` |
| 36 | Flags `0x0226 & 0x8000 == 0` | `0x8004D838` |

The first five pass the prior signed floor/height checks. Their attribute
bit `0x1000` is clear, so no rotation changes the bounds. Mode 9 has bit
`0x20` clear, so radius 450 does not expand these static bounds. Radius is
not globally irrelevant. All failure branches advance at `0x8004DAB8`; none
reaches a shape handler or `0x8004DAA0`. The loaded header height 0 therefore
survives to the tail. The mode 9 pass-through handler addresses are checked
but are not invoked on this path.

The JAL delay-slot store at `0x8004DADC` passes that height at
`0x801FF980`. The runtime tail's `0x38`-byte frame loads the same fifth
argument through `SP+0x48`. Its region-mask leaf reads the bound header and
query X/Z before the first sentinel test. The sampled `0xFFFFFFFF` sentinel
skips every runtime record body and returns the incoming height unchanged
at `0x8004DD90`. The actual return capture agrees with that source-derived
header fallback. This establishes no selected static or runtime support.
It adds no observation of internal native branches or a live mutable-source
lifetime proof, and does not classify other inputs or future runtime lists.

`2026-11-13-re3-constructor-support-attribution/verify_attribution.py` accepts
the same explicit owned media/catalog/capture inputs and a fresh `--out`.
Its SHA256 is `b199d581975648b484020aecde980d14843933b056893812d4d9d6631a13bec8`.
Two author reruns and root's fresh rerun produce attribution report SHA256
`0402fb3ab0cbae2ed4d5db11dd806d026fca65d8067d7ca77f306bceac28ca6a`.
All 317 original CLI manifest entries remain unchanged. Investigator
`investigate_re3_constructor_support`, task-verified `gpt-6.1-sol` at `xhigh`,
session `01a1d4e2-5a9b-7720-9e14-4cae8f14aace`, authors this inference and
verifier. The earlier native observation retains its separate authorship.

### Reproduction, preservation and contribution

Private evidence is under
`~/.cache/re-map/evidence/2026-11-13-re3-height-native-cli/`; the failed attempt
remains under `2026-11-13-re3-height-native-registration/`. The explicit
read-only vector in `reproduction-argv.json` runs `verify_call.py` with required
`--evidence`, `--checkout`, owned `--image`, `--catalog`, `--source-contract`
and a nonexistent `--out`. It starts no emulator. `verify_attempt.py` retains
the failed attempt's zero observations. The successful verifier SHA256 is
`6b081cfdc7993fb00842dca4ff9beb42d4545acfd5ea25b27f173c6fc6f33c7f`.
Root's fresh reports reproduce SHA256
`9361876ecbe93a222d97d217f658405a1eef379b2d354a7bc048022ecdb4a679`
and `0de1397f0cd7a071dd4c30c1414b1b55fe5f840d457ff6f518701daf249be0f3`
for the successful and failed attempts respectively. All 317 new manifest
entries, 359 preserved prior entries and seven original resources rehash
unchanged. Counts are manifest entries, not necessarily distinct files.

Retained cleanup removes the connected client's own watch/breakpoints, closes
it and verifies exact-owned argv before SIGTERM. PID 5871 exits zero after
902.866949 seconds, below the 1200-second watchdog, without SIGKILL. Port 2431
is absent and bindable in that receipt. Private settings gain only four window
geometry keys. Guest claims end at the coherent consumer capture,
`2026-11-13T11:33:59.870162Z`; disconnect-to-SIGTERM execution is unobserved.
This integration reruns verifiers and hash checks, not cleanup or gameplay.
No production code, profile, UI, exploration history or README image changes.

Contribution, 2026-11-13: investigator `investigate_re3_support_join`, verified
`gpt-6.1-sol`, effort `xhigh`, session `01a1d45e-f6cc-7d23-a4f9-863afabedcf2`,
authors the native attempt, setup/controller adaptations, verifier and private
handoff. Root, separately verified as `gpt-6.1-sol` at `xhigh`, authors the
pinned CLI source contract, independently inspects caller/source/consumer
boundaries, reruns both verifiers, checks preservation and writes this record.
Earlier helper authorship and the human's Hard selection remain separate.
Root evidence is under
`~/.cache/re-map/evidence/2026-11-13-re3-constructor-integration/`.

Independent evidence review `review_re3_constructor_observation`, verified
`gpt-6.1-sol`, effort `xhigh`, reports no findings. It reproduces both reports,
checks all manifest/resource hashes, original ABI/source/index/consumer facts,
34 native commands, 25 zero-input observations, isolation and cleanup receipts,
and pinned CPU/GDB startup/load-delay/watch semantics. It adds no emulator run,
second native situation, rendered UI assessment or new gameplay confirmation.
Exact source URLs and limits are retained under
`~/.cache/re-map/evidence/2026-11-13-re3-independent-review-01a1d4c1/`.

Independent attribution review `review_re3_constructor_attribution`, separately
task-verified `gpt-6.1-sol` at `xhigh`, reports no findings. It reproduces the
attribution report, independently calculates signed intervals from the owned
source, disassembles the original branches/delay slots, checks fifth-argument
and sentinel control, and preserves all 317 original and 11 attribution
manifest entries. It reviews the actual documentation and its limits, without
CPU/emulator execution. Exact evidence is under
`~/.cache/re-map/evidence/2026-11-13-re3-attribution-review-01a1d4ea/`.

The configured external snapshot review returns "No findings." T3 reports
`gemini-3.8-flash`, requested `thinking_level=high`, through Antigravity,
without a separate executed-model attestation. The supplied snapshot includes
the claim, verifiers, numeric reports, bounded original disassembly and pinned
DuckStation source excerpts. The reviewer performs no tools or execution.
Configured Claude Opus 5.5 remains disabled and supplies no review. Root's
final manifest retains the reviewed hashes, responses and local link/whitespace
checks. These reviews add no native situation or gameplay confirmation.

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
from games.re3.map_conditions import decode_map_conditions, decode_map_detail_conditions
from games.re3.room_data import RoomFormatFailure
from re3_map_geometry import extract_map_contours
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
conditions = decode_map_conditions(data, executable)
assert not isinstance(conditions, RoomFormatFailure), conditions
Path('/tmp/re3-map-conditions.json').write_text(json.dumps(conditions, indent=2) + '\n')
details = decode_map_detail_conditions(data, executable)
assert not isinstance(details, RoomFormatFailure), details
Path('/tmp/re3-map-detail-conditions.json').write_text(json.dumps(details, indent=2) + '\n')
contours = extract_map_contours(data, executable)
assert not isinstance(contours, RoomFormatFailure), contours
Path('/tmp/re3-map-contours.json').write_text(json.dumps(contours, indent=2) + '\n')
PY
```

The parser independently checks the executable; these fixed extents are reproduction details for the pinned owned image, not production defaults. The primitive JSON has SHA256 `aeaae3c1cc938a413cda6c3e44138aa1f372b024a1c37c3c345d53bf7234776f`, matching the original draft run and parent rerun byte-for-byte. The added layout JSON matches `layout.json` in the RE3-MAP-004 evidence table.

Private discovery evidence is under `/var/folders/9d/q5n746z953bcs654g_1sqcy80000gn/T/re-map-re3-map-20261105-4hn9iq7k/`. Parent evidence is under `/tmp/re-map-re3-map-integration-20261105/`, containing the numeric export, `audit.py` and `audit.json`. The audit script SHA256 is `1ed1c7f8ef7a1cfc9a136742504e469295ce2b2a675a690303d7c49fbd4e2d2d`; report SHA256 is `b28f1a2c6b6477787560f1e125dcf2c03b1e04c78522a6a908abf77fd7083df4`. Temporary evidence may expire; hashes do not replace retained bytes.

The parent used Unicorn 2.1.4 to execute the exact renderer and its header helper once for each of the 793 owned primitives, with synthetic zero pan, 100% scale and viewport center `[160, 120]`. All four output vertices matched the decoded directed edges after that translation and native halfword storage. The shared code-hook store auditor predicted every write; complete 2 MiB before/after RAM comparisons matched all predicted stores. No memory-write hook or substituted renderer was used. These are copied-code checks, not gameplay observations, and do not validate conditional selection, native map acquisition or world projection.

## Tests and remaining limits

Run with the [test environment](../../testing.md#python-test-environment):

```sh
python3 -m pytest -q tests/test_re3_map_detail_selection.py tests/test_re3_map_detail_predicates.py tests/test_re3_map_detail_conditions.py tests/test_re3_map_selection.py tests/test_re3_map_conditions.py tests/test_re3_map_geometry.py tests/test_re3_map_binding.py tests/test_re3_map_data.py tests/test_re3_native_contracts.py tests/test_re3_room_data.py tests/test_re3_room_catalog.py tests/test_re3_disc_identity.py tests/test_floor_plan.py tests/test_re2_metadata.py tests/test_player_heading.py tests/test_re2_tracking.py
```

The 27 synthetic contour cases cover palette-plane crossing, full-word transparency, holes and components, shade detail, upload replacement, absent texture words, TIM bounds, unsupported UVs and no partial export on later failure. Binding checks cover executable/capture gating, independent table bounds, signed origins, native truncation, early returns, ordered/chained remaps, raw-stage folding, position/story thresholds, layer/previous-state overrides, alternate records and earlier-snapshot reversal. Thirteen additional RE3 heading cases cover cardinal phases, rounded-sector boundaries, unsigned high bits and reversal; RE1/RE2 heading checks retain native-displacement references and coherent publication. Synthetic RE3 fixtures contain no owned executable, RAM or artwork bytes.

A useful tracker map still needs physical floor identity/labels, runtime validation of both selection groups and room/door/stair ownership of the source contours. Candidate row/layer/projection contracts exist, with only two native positions observed. Per-quad coverage and shade detail now survive export; those masks are not automatically room outlines. General lifecycle admission, ordinary room reentry and item/door/story interpretation remain unresolved. No runtime profile, UI, persistence or user exploration changed. Visits and completion remain unresolved.

Thirty-two synthetic requirement cases cover all nine record offsets, mandatory identity, both flag banks, noncanonical nonzero selectors, indices 0/31/32/255, duplicate targets, first-byte-only sentinels, truncated entries, missing terminators and failure in the final record. Another 321 selector cases cover explicit records, captured-source witnesses, invalid pointers and byte-argument bounds, browsing context, native phase boundaries, bypass scope and earlier-snapshot reversal. These checks establish source interpretation only.

## Contributions and review

- 2026-11-05; human user; supplied the owned media, requested parallel research and selected Hard.
- 2026-11-05; implementation delegate, `gpt-6.1-sol` verified by returned run metadata; inspected the owned map/executable and authored the initial decoder and synthetic tests. Its run stopped for exhausted workspace credits before review, documentation or commit.
- 2026-11-05; Codex root, exact runtime model `gpt-6.1-sol`; recovered the draft, checked native count/stride and signed-edge instructions, shared the revision fingerprint, reran source/test checks, executed the copied renderer audit, wrote this record and completed integration review. Review covered bounds, aliases, identity gating, opaque fields, failure behavior and separation from runtime map claims. Configured external reviewers were unavailable; no independent external endorsement or gameplay validation is claimed.
- 2026-11-05; Codex root, exact runtime model `gpt-6.1-sol`; authored RE3-MAP-003/004, traced remapping/anchors/layers/projection, added bounded metadata and snapshot decoders, shared capture witnesses, checked 424 copied-code contexts and two native map positions, and verified private cleanup. Local review covered address spaces, masks, ordered control flow, signed arithmetic, independent bounds, raw layer limits, capture identity, input preservation and unresolved admission. No model agreement substitutes for gameplay observations.
- 2026-11-05; independent internal source checker, `gpt-6.1-sol` verified from its matching session metadata and latest turn context; found no actionable issues after checking remap order/early returns, raw-stage folding, flag masks, layer selection, signed projection, parser bounds and shared capture checks. Independently verified the executable fingerprint and 49-row remap table, and inspected the copied-code report and both retained projection pairs. It did not rerun tests or emulator experiments, change files or establish gameplay behavior.
- 2026-11-05; external review attempt, `gemini-3.8-flash` at high reasoning through Antigravity; the provider returned no content for 15 minutes and T3 stopped the run. Claude Opus 5.5 was disabled in the provider inventory. Neither supplied a completed review or an endorsement.
- 2026-11-05; independent source investigator and internal reviewer, `gpt-6.1-sol` verified from its matching session metadata and latest turn context; authored the private mask/selection evidence for RE3-MAP-005/006, checked native variant sets, upload relocation, packed-plane patterns and primary GPU references, and reread the two retained captures. Final source review of the new exporter and 27 tests found no actionable issues. It independently passed those tests, verified the owned fingerprints, exported 792 decoded quads plus one unresolved quad and compared 80 palette masks with its earlier numeric audit. No new emulator/UI operation or gameplay validation occurred.
- 2026-11-05; Codex root, exact runtime model `gpt-6.1-sol`; authored the bounded contour exporter, synthetic regressions and RE3-MAP-005/006 integration record. Verified source hashes, exact boundary/area agreement for 2,010 masks and 5,729 shades, 2,013 copied renderer calls and full RAM write effects. Local review covered identity and TIM bounds, upload order, absent data, full palette words, class-zero membership, plane crossing, directed/wrapping UVs, shared contour logic, source-only claims and conditional-ownership limits.
- 2026-11-05; external snapshot reviewer, `gemini-3.8-flash` at high reasoning through Antigravity; returned no findings on the contour exporter, synthetic fixtures, shared tracer and format/layout context, with bounds, native formulas, failures, test risks, maintainability and research-claim limits in scope. It ran no tests or gameplay experiments. Claude Opus 5.5 remained disabled in the provider inventory and supplied no review.
- 2026-11-05 UTC; independent heading investigator, `gpt-6.1-sol` verified from its matching session metadata and latest turn context; authored the private RE3-MAP-007 source and retained-capture evidence, traced marker selection and both matrix paths, checked nine numeric glyph signatures and repeated its report byte-identically. No repository edit, new emulator observation or gameplay admission was performed.
- 2026-11-05 UTC; Codex root, exact runtime model `gpt-6.1-sol`; integrated the shared yaw formula and Candidate RE3 fields, added thirteen heading/reversal cases and explicit orientation tests, checked eleven retained captures, repeated 4,141 copied native calls with full RAM store auditing and checked all unsigned yaw/sector intervals. Local review covered field widths, signed/high-bit behavior, axis convention, preserved RE1/RE2 semantics, native glyph rounding, stale packet limits and refusal of gameplay admission. All 4,940 tests passed after the configuration correction.
- 2026-11-05 UTC; independent internal reviewer, `gpt-6.1-sol` verified from its matching session metadata and latest turn context; checked the shared helper, three game callers, tests, source hashes, rounding, stale-packet limits and Candidate claims. It identified that malformed external RE2 orientation could reach a programmer assertion after room mutation. The root reproduced this and added mandatory profile-loading validation with fifteen configuration regressions. The reviewer independently passed 72 tests, excluding six fixture-dependent cases; it did not run the root's full suite, edit files or operate an emulator.
- 2026-11-05 UTC; external snapshot reviewer, `gemini-3.8-flash` at high reasoning through Antigravity; returned no findings on the final shared formula, three game callers, startup validation, synthetic tests and RE3-MAP-007 claims. Review covered native signs/phase/rounding, widths, identity checks, configuration failure before mutation, preserved supported-profile behavior and unresolved admission. It ran no tests or gameplay experiments. Claude Opus 5.5 remained disabled in the provider inventory and supplied no review.
- 2026-11-05 UTC; independent source investigator, `gpt-6.1-sol` verified from its matching session metadata and latest turn context; authored the private ordered requirement catalog used by RE3-MAP-008, traced the original predicate routine and its group-0 caller, and distinguished browsed-group selection from current-location context. Source/copy checks do not establish runtime selection, ownership or gameplay admission.
- 2026-11-05 UTC; Codex root, exact runtime model `gpt-6.1-sol`; authored the bounded requirement export, thirty-two original synthetic cases and RE3-MAP-008. Verified every owned table against the independent catalog, repeated output byte-identically and checked that earlier primitive/layout hashes remain unchanged. Local review covered identity gating, independent extents, sentinel reads, selector and index widths, duplicate preservation, source address/mask interpretation, explicit failures and separation from runtime visibility.
- 2026-11-05 UTC; independent internal reviewer, `gpt-6.1-sol` verified from its matching session metadata and latest turn context; found no actionable issues in the requirement decoder, synthetic tests or RE3-MAP-008. Checked the native scan/helper and group-0 caller, layout identity/extents, sentinel reads, nonzero selectors, duplicate conjunction, addresses/masks and unresolved runtime claims. Independently passed 113 focused checks and verified the owned input, three source and three integration artifact hashes. No edits, emulator operation or user-history access occurred.
- 2026-11-05 UTC; external snapshot reviewer, `gemini-3.8-flash` at high reasoning through Antigravity; returned no findings on the final requirement decoder, synthetic fixtures, inherited layout checks and RE3-MAP-008. Review covered source semantics, bounds, identity and failure behavior, test risks, reuse and source-only claims. The final snapshot labeled each file and excerpt explicitly after the initial concatenated snapshot caused boundary ambiguity. It ran no tests or gameplay experiments. Claude Opus 5.5 remained disabled in the provider inventory and supplied no review.
- 2026-11-05 UTC; independent source investigator, `gpt-6.1-sol` verified from its matching session metadata and latest turn context; authored the immutable families' numeric source model, the 30,419-context copied-native proof and RE3-MAP-009's independent selected-source interface report. It preserved original helper execution, full RAM store audits, missing-sentinel negatives and unreachable-edge arguments. No gameplay or repository edit was performed by that source investigation.
- 2026-11-05 UTC; Codex root, exact runtime model `gpt-6.1-sol`; implemented the explicit loaded-source selector and shared predicate evaluator, authored 321 original synthetic cases and RE3-MAP-009, checked all ten interface source hashes and both retained source-prefix witnesses, and matched the unchanged source model in all saved contexts. All 5,293 tests passed. This implementation did not rerun copied native execution, operate an emulator or alter user exploration.
- 2026-11-05 UTC; independent internal reviewer, `gpt-6.1-sol` verified from its matching session metadata and latest turn context; found no actionable issues in the source-bound selector, immutable predicates, captured-code check wording, tests or RE3-MAP-009. Verified exact equality of all 31 families, all thirteen documented word masks and seven referenced evidence hashes. Review covered pointer/byte-argument bounds, contiguous source binding, current/browsed/variant distinctions, fresh state, phase and bypass order, explicit failures and unresolved runtime claims. No edits, emulator operation, duplicated test suite or native-proof rerun occurred.
- 2026-11-05 UTC; external snapshot reviewer, `gemini-3.8-flash` at high reasoning through Antigravity; returned no actionable findings on the source-bound selector, immutable rules, inherited layout/capture/metadata contracts, synthetic tests and RE3-MAP-009. Review covered arithmetic/control flow, source/pointer bounds, explicit-record and current/browsed/variant distinctions, errors, invariants, rewind, reuse, test risks and unresolved gameplay/visibility claims. It inspected only the supplied snapshot and ran no tests, native execution or gameplay experiments. Claude Opus 5.5 remained disabled in the provider inventory and supplied no review.
- 2026-11-06 UTC; independent source investigator, `gpt-6.1-sol` verified from its matching session metadata and latest turn context; authored the group-1 source contract, catalog, model and copied-native evidence behind RE3-MAP-010. Original execution exposed the raw-mask-to-byte normalization error; the initial model/failure and correction witness remain preserved. No repository edit or emulator observation was performed.
- 2026-11-06 UTC; Codex root, exact runtime model `gpt-6.1-sol`; authored the shared bounded scan and group-1 table export, 51 original synthetic cases and RE3-MAP-010. Matched all owned entries and prefix sizes against the independent catalog, repeated export byte-identically and preserved the prior group-0 export. All 720 RE3 tests passed. This increment performs no predicate evaluation, native execution, gameplay admission or user-history change.
- 2026-11-06 UTC; independent static-export reviewer, `gpt-6.1-sol` verified from its matching session metadata and latest turn context; found no actionable issues in the shared scan, old/new decoders, 51 new cases and RE3-MAP-010. Independently passed 83 focused checks, matched all 105 owned entries/extents, checked the input/source-window/contract/catalog/parent hashes and verified both export payloads. Review covered exact selectors and control bits, bounds/sentinels, ordering, modeled failures, source-only limits and raw-mask truncation. No edits, emulator action, native-proof rerun or gameplay validation occurred.
- 2026-11-06 UTC; external snapshot reviewer, `gemini-3.8-flash` at high reasoning through Antigravity; returned no findings on the shared scanner, preserved group-0 API, new group-1 table export, fixtures, inherited layout and RE3-MAP-010. Review covered grammar, identity/bounds, exact selector/control semantics, explicit ignored entries, failures, ordering, reuse, tests and unresolved runtime/provenance limits. It ran no tests, native execution or gameplay experiments. Claude Opus 5.5 remained disabled in the provider inventory and supplied no review.
- 2026-11-06 UTC; implementation agent, `gpt-6.1-sol` verified from its matching session metadata and latest turn context; authored RE3-MAP-011's 33 immutable shape families, explicit decision enum, system-style sets, 193 synthetic cases and bound detail selector. It extracted shared mandatory binding, preserved raw flag masks and verified 1,753 before/after group-0 serialized contexts. No native execution, emulator action or gameplay validation occurred.
- 2026-11-06 UTC; Codex root, exact runtime model `gpt-6.1-sol`; authored the shared Boolean/exclusion evaluator, 63 source-binding/integration cases, RE3-MAP-011 and the private production/model comparison. All 976 RE3 tests pass. Shape, full-source and retained-capture comparisons retain the counts and limits above. The prior group-0 comparison reproduces its unchanged digest and outputs. This contribution adds no native execution, gameplay observation or user-history access.
- 2026-11-06 UTC; independent internal reviewer, `gpt-6.1-sol` verified from its matching session metadata and latest turn context; found no actionable issues in the shared evaluation/binding extraction, new group-1 rules, selector or synthetic tests. It matched all 33 families, ordering, exclusions and source intervals, checked raw-mask truncation, metadata and style semantics, kind-7 handling, invariant/error boundaries and group-0 preservation. It independently compared 108 old/new synthetic publications and failures. This source/evidence review did not rerun the native proof or operate an emulator.
- 2026-11-06 UTC; external snapshot reviewer, `gemini-3.8-flash` at high reasoning through Antigravity; returned no findings on the shared helpers, preserved group-0 families/API, new group-1 rules/selector, synthetic tests, inherited layout/capture/condition contracts, independent source model and RE3-MAP-011. Review covered native arithmetic/order, source identity and bounds, explicit record semantics, fresh state, failures, invariants, reuse, tests and unresolved gameplay/visibility claims. It inspected only the supplied snapshot and ran no tools, tests or gameplay experiments. Claude Opus 5.5 remained disabled in the provider inventory and supplied no review.
- 2026-11-06 UTC; source investigator and implementation agent, `gpt-6.1-sol` verified from its matching session metadata and latest turn context; authored RE3-MAP-012's numeric source contract, model, 17,896-call copied proof, retained-byte comparison, pure row/layer helpers and 891 synthetic cases. It preserved failed harness assumptions and corrections. No emulator, new runtime observation or tracker-history change occurred.
- 2026-11-06 UTC; Codex root, exact runtime model `gpt-6.1-sol`; authored the source-bound row API, explicit binding scopes, additional mandatory capture spans, 39 wrapper/capture cases, RE3-MAP-012 and private Python integration. Review tightened extra-span semantics so callers cannot replace the four general capture witnesses. All 1,906 RE3 tests pass. Native-row results retain unresolved ownership, campaign and tracker contracts; no new native execution or emulator action occurs in this integration.
- 2026-11-06 UTC; independent internal reviewer, `gpt-6.1-sol` verified from its matching session metadata and latest turn context; found no actionable issues in the row/layer helpers, binding/capture changes, tests, RE3-MAP-012 or Python integration. It checked all 20 source-manifest artifacts, eleven code/ownership windows, four parent artifact hashes/sizes, source formulas/order, physical aliasing, generated/saved/isolated coverage distinctions, retained outputs and unchanged group-0/1 hashes. It passed 1,452 focused checks before the final additional-span regression, then reviewed that enforcement change without repeating the suite. No edits, native-proof rerun or emulator operation occurred.
- 2026-11-06 UTC; external snapshot reviewer, `gemini-3.8-flash` at high reasoning through Antigravity; returned no findings on the new row/layer helpers, capture/binding changes, tests and fixtures, inherited layout/condition contracts, independent source model and RE3-MAP-012. Review covered native order and widths, source/coherence/code bounds, prior API preservation, fresh state, errors/invariants, reuse, tests and source/runtime distinctions. It used no tools and performed no tests, native execution or gameplay validation. Claude Opus 5.5 remained disabled in the provider inventory and supplied no review.
