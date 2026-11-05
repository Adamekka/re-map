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
from games.re3.map_conditions import decode_map_conditions
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
python3 -m pytest -q tests/test_re3_map_selection.py tests/test_re3_map_conditions.py tests/test_re3_map_geometry.py tests/test_re3_map_binding.py tests/test_re3_map_data.py tests/test_re3_native_contracts.py tests/test_re3_room_data.py tests/test_re3_room_catalog.py tests/test_re3_disc_identity.py tests/test_floor_plan.py tests/test_re2_metadata.py tests/test_player_heading.py tests/test_re2_tracking.py
```

The 27 synthetic contour cases cover palette-plane crossing, full-word transparency, holes and components, shade detail, upload replacement, absent texture words, TIM bounds, unsupported UVs and no partial export on later failure. Binding checks cover executable/capture gating, independent table bounds, signed origins, native truncation, early returns, ordered/chained remaps, raw-stage folding, position/story thresholds, layer/previous-state overrides, alternate records and earlier-snapshot reversal. Thirteen additional RE3 heading cases cover cardinal phases, rounded-sector boundaries, unsigned high bits and reversal; RE1/RE2 heading checks retain native-displacement references and coherent publication. Synthetic RE3 fixtures contain no owned executable, RAM or artwork bytes.

A useful tracker map still needs physical floor identity/labels, group-1 selection, runtime validation of group-0 selection and room/door/stair ownership of the source contours. Candidate row/layer/projection contracts exist, with only two native positions observed. Per-quad coverage and shade detail now survive export; those masks are not automatically room outlines. General lifecycle admission, ordinary room reentry and item/door/story interpretation remain unresolved. No runtime profile, UI, persistence or user exploration changed. Visits and completion remain unresolved.

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
