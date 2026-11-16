# RE3 floor plans, door markers and names

[RE3 scope](../../re3.md) · [Native map semantics](map-semantics.md) · [Room and MAP directories](room-format.md)

Target: Resident Evil 3: Nemesis, PlayStation, USA, SLUS-00923, owned single-track disc, executable `SLUS_009.23` SHA256 `2e143418e358b2c99995cdc1a88c387163fb751912c723b755614f38e236bd29`, `CD_DATA/ETC/MAP_U.MAP` SHA256 `7182beb90347fe4ea0c2a4db30dff93aaee88b8ef1b633398ffcef6f3d3d1268`. All claims here are offline source and file inspection. No emulator was started and no gameplay observation was made for them.

The generator is [`tools/build_re3_floor_plans.py`](../../../tools/build_re3_floor_plans.py). It writes [`data/floor_plans_slus00923.json`](../../../data/floor_plans_slus00923.json) in the RE2 floor-plan schema, with numeric polygons, labels and door segments only. Room and area names are in [`data/re3_names.json`](../../../data/re3_names.json).

## RE3-PLAN-001: native map quads selected by projected camera zones form room outlines

Status: Candidate for the named revision. The outlines are a practical reconstruction of the native map, not a proof of physical room ownership. RE3-MAP-006 and RE3-MAP-017 remain valid: quad unions and camera zones alone do not establish ownership in general.

### Method

1. Every one of the 169 room sources is bound to native map records, rows and layers by calling the shared resolver `resolve_native_map_position` from [`map_data.py`](../../../src/games/re3/map_data.py) (RE3-MAP-004). The builder scans world X/Z over the signed 16-bit range and every combination of the resolver's flag and previous-room inputs, then keeps only the inputs that change a room's outcome. This yields explicit location rows: conditions in the RE2 `[address, mask, expected, negate]` form and inclusive `position_bounds` for world X or Z. The resolver now reports its split-room X adjustment (`projection_x_adjust`); the builder folds it into each location's anchor.
2. Ordinary records 0 to 6 supply the geometry. Lifecycle bit `0x80` at `0x800CC858` selects alternate records 7 and 8 instead. Their meaning is unresolved, and the builder does not use them.
3. For each native row, each group-0 quad is kept only if the immutable native shape predicates (RE3-MAP-009, `group_zero_shape_allowed`) admit it as if the player stood in that row. Phase values 0, 3, 4, 9 and 10 cover every interval the predicates distinguish, so a room with lower and upper levels keeps both. Story flags are clear except two documented choices: park flag `0x800D20CC` index 9 (while clear, a placeholder block replaces every park room) and factory flag `0x800D258C` index 69 (while clear, a walkway shared by two rooms is hidden). Metadata requirements (RE3-MAP-008) are not applied.
4. A quad whose largest hole exceeds its own drawn area is dropped. Those frames outline whole buildings shared by several rows.
5. Each remaining quad's variant-0 coverage (RE3-MAP-005) is compared with the camera zones of the rooms placed on that row, projected through each location's anchor. Zones of a split room count only on the row whose position bounds contain the zone centre. A quad is kept when at least half of its cells lie inside those projected zones. On this disc, context drawings such as the hospital footprint and park perimeter on the hospital-street row stay at or below 0.43; room quads are almost all fully covered.
6. Rows on one area page whose outlines overlap by at least 90% of the larger are merged into one region (for example R411 and R415). Two regions overlapping by at least 25% of the smaller are kept as stacked levels, as the native map draws them on one page. Other shared cells are wall strips. They go to the region whose quad has the higher zone coverage, then the region whose zones reach the cell, then the smaller region.
7. Cells become rings through the shared contour tracer [`map_geometry.py`](../../../tools/map_geometry.py). Class-1 detail strokes of at least four cells become `detail_segments`; shorter strokes are mostly native map lettering. Areas are `(record, native layer)` pairs.

Each location row carries `world_origin` (nearest integer, for `origin + world / 450` consumers) and `native_anchor` (exact map and adjusted world anchor). The rounding moves a projected point by less than half a map unit. The native integer truncation moves the game's own marker by less than one. Region `world_origin` is the row's unadjusted anchor, kept for RE2-schema compatibility. A split room needs its location's origin.

### Results

The output covers all 169 sources in 178 location rows, 13 area pages and 106 regions. Every source has an outline; `unoutlined_rooms` is empty. Fourteen location rows carry conditions or position bounds: R20F's X split, R415's X split, R317's Z/flag split, R502's flag row and R503's layer override. Four region pairs remain stacked: warehouse office R100 within warehouse R101; R211/R212; R20F-west with the R210 row; and R410 with the merged R411/R415 region.

### Validation

- Visual: each area was rendered from the JSON to private PNG files and compared with renders of the raw native quads. The Uptown, Downtown, clock tower, park, factory, police station and hospital pages show connected room layouts without building-context fills. No image is committed.
- Door destinations: each of the 441 non-self door transfers into a known room supplies a world position where the game places the player. Projected through the target's location rows with the exact anchor, 424 land inside the outline, 5 lie within 1.5 map units of it and 12 lie farther out. Two of those 12 are scripted placements at world `(0, 0)`. Others land in a neighbouring outline after a wall strip went to that neighbour (R204 from R203, R20B from R20A, R10F from R10A), in R302's outline for the unsplit R30F, or in R40D's outline for R410. With the rounded integer origin the counts are 423/6/12.
- Camera-zone centres: 4,224 of 4,714 lie inside, 122 within 1.5 units. Zone centres can lie outside walls, so this is a weak check.
- Retained runtime positions: all nine distinct player positions in the retained RE3 RAM captures under `~/.cache/re-map/evidence/*re3*/captures/` project inside their room's outline, with both anchors. They cover only R103 (one position) and R10D (eight). Other rooms have no runtime position check.

### Limits

Outlines follow the native map's distorted 450-unit grid, not collision geometry. Stacked regions overlap on one page. Player positions in a carved-out wall strip project outside the current room's outline, and the RE2 consumer then reports a room-only position. `position_bounds` is an RE3 addition to the location rows. The RE2 `select()` ignores it, so it finds R20F, R415 and R317 ambiguous. A consumer must test the player's world X/Z against the bounds. The alternate records, metadata requirements and the native current-room colours are not modelled. Story-dependent outline changes are reduced to one state per row.

## RE3-PLAN-002: door creators and wall markers

Status: Candidate. Trigger rectangles are script source data. A creator does not prove that its branch runs, that the door is unlocked or that the player used it.

[`script_doors.py`](../../../src/games/re3/script_doors.py) walks each initializer procedure from its start to its first `evt_end` (opcode 0x01), using the 144 command widths of the native handler table at PS1 virtual `0x8009E0F8`. With these widths all procedures of the 169 sources decode up to their first `evt_end`, and 118 have non-command bytes after it. No door creator follows the first `evt_end`. The two creator commands give 453 doors, 429 of which lead to another room:

| Command | Width | Fields used (byte offsets, little-endian) |
| --- | ---: | --- |
| `0x61` door, rectangle | 32 | floor `+4` (u8); X, Z `+6/+8` (i16); width, depth `+10/+12` (u16); destination X/Y/Z `+14/+16/+18` (i16); target stage, room, camera, floor `+22..+25` (u8); key `+29` (u8) |
| `0x62` door, four points | 40 | floor `+4`; four X/Z pairs `+6..+21` (i16); destination X/Y/Z `+22/+24/+26`; target stage, room, camera, floor `+30..+33`; key `+37` |

A marker's `observation_id` is `SS-RR:<creator byte offset in the RDT>`. The builder projects the trigger centre through the owning location and snaps it to the nearest outline edge of at least two map units within six units. It places a two-unit segment on that edge, and markers carry the target room. 350 of the 429 non-self creators receive at least one marker, 354 markers in all. The rest project more than six units from any wall. A room with several location rows on one region gets one marker per creator. Markers are not paired across rooms and carry no lock state.

## RE3-PLAN-003: item names from the executable

Status: Candidate. Item names are source data; room names come from external sources, and area names are editorial.

The executable stores 194 item names as single-byte game text, each ended by `0xF7`, starting after the terminator at PS1 virtual `0x8009BEE4`. A table of 194 u16 LE offsets at `0x8009C7C0` indexes them by item type. The character codes are: space `0x00`, `.` `0x01`, digits `0x0C..0x15`, `A..Z` `0x1D..0x36`, `a..z` `0x3D..0x56`, `'` `0x3A`, `-` `0x3B`. The two-byte glyph sequence `EA 24 EA 25 EA 26 EA 27 EA 24` draws the S.T.A.R.S. logo. `item_names()` in the builder decodes the table. `data/re3_names.json` keeps every name except item 0 and the `BOTU` placeholders for unreleased slots. Names keep the game's abbreviations, such as `F. Aid Spray`. Room messages use the same encoding.

Room names follow the Resident Evil Fandom wiki's RE3 location pages, read 2026-11-16. Those pages use names from the Japanese *Biohazard 3 Last Escape* official guidebook and match room files through background image names such as `R11904` (room R119, camera 04). Names are shortened to plain English. Files the wiki does not name take the name of the region they share: R30F, R317 and R316 get Dance Hall or Hall, and R219 gets Newspaper Building. [BioRand Classic `data/re3/rdt.json`](https://github.com/biorand/classic/blob/ee58344b8ac98979e599857fd9edf316ed2e1fdb/IntelOrca.Biohazard.BioRand/data/re3/rdt.json) at commit `ee58344b8ac98979e599857fd9edf316ed2e1fdb` supports those pairings with its linked-room data. Stage 6/7 files (R6NN, R7NN) take the names of R1NN and R2NN. [RE3_Descomp_and_port notes](https://github.com/jhonatasortega/RE3_Descomp_and_port/blob/1fe9e7b6c3995eaaaac7d3b40082e95333ef0719/docs/decomp/notes/door_handler.md) at commit `1fe9e7b6c3995eaaaac7d3b40082e95333ef0719` describe those files as Mercenaries copies, not story revisits. That is unverified here. If true, the plans' stage 6/7 locations and native records 7/8 may serve only Mercenaries. Area names are editorial: floor labels come from the room names on each native layer, not from a native floor field. No name is taken from any remake.

## Reproduction

```sh
python3 tools/build_re3_floor_plans.py "/path/to/Resident Evil 3 - Nemesis.cue" data/floor_plans_slus00923.json
RE_MAP_RE3_OWNED_CUE="/path/to/Resident Evil 3 - Nemesis.cue" python3 -m pytest -q tests/test_re3_floor_plans.py
```

Generation takes about 20 seconds. The owned-disc tests regenerate the plans and compare them with the committed file, and compare the item names with the executable table. Without the disc, the tests check the committed geometry: closed axis-aligned rings with roles that match orientation, labels inside outlines, every located room outlined or listed as unoutlined, door segments on their owning outline. They also cover synthetic door scripts, contour round trips and text decoding.

## Contributions and review

- 2026-11-16; human user; requested runnable RE3 spatial floor plans in the RE2 schema, names and tests, and supplied the owned disc.
- 2026-11-16; Claude, exact model `claude-opus-5-5`, at the human's request; wrote the door walker, the resolver's `projection_x_adjust` field, the builder, generated data, names, tests and this record. It found the external name sources through a delegated web search and did the offline validation above. No emulator was run and no independent review has been made.
