# RE2 interior geometry

[Documentation index](../../README.md) · [Claim index](../../research.md)

## RE2-MAP-006: collision footprints supplement two empty native room sprites

Status: Candidate for Resident Evil 2 Dual Shock Ver. USA, Leon A Disc 1 SLUS-00748 and Claire B Disc 2 SLUS-00756, Original Game on Normal. Owned-source inspection, numeric geometry inspection and synthetic regressions only. These contours establish static collision footprints, not proven visible walls, exact furniture outlines or live alignment.

### Report and identities

On 2026-10-27 the human reported missing interiors in 1F RPD Main Hall and 1F RPD East Office. Both native map sprites have empty `detail_segments` under the existing tile extractor. Empty sprite detail does not establish an empty physical room. The authorized investigation is limited to owned source geometry, without emulator interaction, game/save loads, guest-memory writes, settings/history changes or native-game screenshots.

[RE2-DS-001](dualshock.md#re2-ds-001-leon-a-dualshock-revision-port) and [RE2-DS-002](dualshock.md#re2-ds-002-claire-b-dualshock-revision-port) pin the two profiles. Executables independently extracted for this pass match those profiles:

| Executable | SHA256 |
| --- | --- |
| `SLUS_007.48` | `e576348f64d015ecff6e1ce875a8924ee252ba7f3f9478b0917cbbdeb97db441` |
| `SLUS_007.56` | `1664e7c634f8cfd03e421f10a6d7e8e8e9fa9bc7982f7c649cc86d28a983fbee` |

The current owned CUEs are `Resident Evil 2 - Dual Shock Ver. (Disc 1) (Leon).cue` and `Resident Evil 2 - Dual Shock Ver. (Disc 2) (Claire).cue`. Each source below was independently read from its CUE's data track. The Leon bytes also match the parent investigation's private `hall.rdt` and `office.rdt` extracts.

| Source | Bytes | SHA256 |
| --- | ---: | --- |
| `PL0/RDT/ROOM2000.RDT` | 448820 | `7586728196fd83ec3992964746efd8d7f793fee383963e11c70951ff307fe000` |
| `PL1/RDT/ROOM2001.RDT` | 447196 | `d2211f9c8db60617eae3a84b20745e9ac190c621968f6c2c246a4065ea8aebe3` |
| `PL0/RDT/ROOM20B0.RDT` | 191432 | `c6b1fe6135f346ffb71500328ffef35a62c6f3d755138ce2a8513411274fc7f6` |
| `PL1/RDT/ROOM20B1.RDT` | 188084 | `ac4cdfce6a857cd776f55e33c59de04f197c95dcdb6e88cc2bfd7e976c78bb24` |

No DuckStation version is newly tested. The private RDTs, executables and native disassemblies remain outside Git.

### Format and native interpretation

The external format lead is Megan Grass's [Starter Kit `source/bio2/data.h`](https://github.com/MeganGrass/Resident-Evil-2-Starter-Kit/blob/447bc6cc5388bf943616f54d50e5c20781003b71/source/bio2/data.h), declarations `tagSCA_DATA`, `tagSCA_HEAD` and `tagROOM_HEAD`. The parent investigation identified the matching local declarations as leads. Function/table names come from the same commit's [`source/assembly/directive.s`](https://github.com/MeganGrass/Resident-Evil-2-Starter-Kit/blob/447bc6cc5388bf943616f54d50e5c20781003b71/source/assembly/directive.s), `Sca_*` symbols. Owned executable inspection supplies the actual behavior below; the header alone does not prove a shape is a visible wall.

Every RDT offset here is a file byte offset, not a RAM or host-process address. All multibyte fields are little-endian. Section pointer six is an unsigned 32-bit file offset at RDT byte `0x20`, full mask `0xFFFFFFFF`. Its 16-byte header contains signed 16-bit center X/Z, unsigned 32-bit Num at `+4`, signed 32-bit Ceiling and an opaque trailing word. Num includes the header. The last record ends at `section_start + Num * 16`, exactly the next source section in all four files. Native `Sca_search` skips the header before visiting records and uses that same endpoint.

| Room | Section start | Section bytes | Num | Shape records | SHA256 of complete section |
| --- | --- | ---: | ---: | ---: | --- |
| Main Hall, both discs | `0x212C` | 832 | 52 | 51 | `f47e4f6e32511becd4f815d49d15477c63431a352a670017d82e81eef5fafb19` |
| East Office, both discs | `0x2C1C` | 544 | 34 | 33 | `c88f56746e72a753a814362f92c0e0b9603f96951142b1ea6aa2a39ffc416d9e` |

Each subsequent 16-byte record has signed 16-bit X/Z at `+0/+2`, unsigned 16-bit W/D at `+4/+6`, unsigned 16-bit Id/Type at `+8/+10`, and unsigned 32-bit Floor at `+12`. Full field masks are `0xFFFF` and `0xFFFFFFFF`; Id's low mask `0x000F` selects the shape. Floor mask `0x00000001` selects records whose lowest native collision level is Y=0. `Sca_get_low` finds the first set Floor bit and subtracts 1800 per preceding bit. This mask is not the native player trigger-floor byte used to select a map region.

The following addresses are PS1 virtual executable addresses, with file offset `0x800 + address - 0x80010000`, not RDT offsets:

| Inspected source | Leon | Claire | Observation |
| --- | --- | --- | --- |
| Shape dispatch table | `0x800A737C` | `0x800A7338` | Fourteen little-endian 32-bit function pointers, indexed by Id's low nibble |
| `Sca_search` | `0x80050FF4` | `0x80050FCC` | Header-inclusive Num and 16-byte iteration |
| `Sca_get_low` | `0x80050FC8` | `0x80050FA0` | Floor mask interpretation |
| `Sca_ck_circle` | `0x8004ED84` | `0x8004ED5C` | Radius `W >> 1`; center X/Z each add that radius |
| `Sca_ck_koban_x` | `0x8004EF0C` | `0x8004EEE4` | Horizontal capsule with circular ends of diameter D |
| `Sca_ck_koban_z` | `0x8004F17C` | `0x8004F154` | Vertical capsule with circular ends of diameter W |
| `Sca_get_stairs_high` | `0x8004FA28` | `0x8004FA00` | Direction/height quantization for shape 12, not a visual tread mesh |
| Ground shape switch | `0x8004FE2C..0x8004FFAC` | `0x8004FE04..0x8004FF84` | Separate shape 11 slope and shape 12 step-height paths |

Id 0 is a box, 6 a circle, 7/8 horizontal/vertical capsules, 11 a slope footprint and 12 a step footprint. All selected circles have equal W/D, and each capsule's long axis agrees with its type. The generator rejects malformed supported shapes. Diagonals, diamonds and curved slopes are omitted rather than replaced with their bounding boxes. Most complete Leon function byte strings do not match Claire verbatim because calls and data references differ. That failed byte search is not equivalence evidence; the listed Claire locations were inspected directly for the field, shape and mask behavior.

### Conservative generation and alignment limits

`tools/re2_map_interiors.py` reads the owned SCA section, requires the pinned section hash for each room and enables this addition only for the two DualShock profiles. It shares the existing `Re2MapProjection` implementation. The projection contract, bias 28000 and scale 450, remains in [RE2-MAP-001](../re2.md#re2-map-001-native-leon-floor-selectors-and-numeric-contours). Main Hall uses native origin `118/169`; East Office uses `184/169`.

The numeric diagnostic overlay shows substantial distortion between collision extents and the native room sprite. For example, Main Hall SCA record 3 projects its left X to about 126.658, outside the sprite's inset wall. Perimeter blockers also span outside the room and can leave a misleading straight line across otherwise filled sprite space. Their intersection with the map is not proof of an interior wall.

The retained solid footprints must fit completely inside the native mapped floor inset by 0.75 map units. This accommodates the existing 1.4-unit detail stroke and rounding. Oversized or partially outside solid blockers are omitted, preserving uncertainty about visible partitions. Overlapping retained solids are united before drawing their perimeter so shared collider seams do not invent partitions through an obstacle. Circles and capsule ends use 32-segment circular approximations, rounded to three decimal map units. At the largest retained circle radius, chord error is below 0.06 map units.

Slope and step footprints remain separate because they describe traversable geometry. Only their original source perimeter is intersected with the inset floor. This adds neither a closing line along the clipping boundary nor guessed stair treads. Main Hall records 3 and 43 preserve the two side-ramp envelopes; record 5 preserves the short step envelope. East Office gains the contained box/circular/capsule obstacles around its central desk-sized collision cluster and other contained objects. These are useful navigation footprints, not identification of every depicted object.

The result adds 285 segments in Main Hall and 241 in East Office to each DualShock catalog. Segment count is an output audit, not gameplay coverage. Only these four `detail_segments` arrays change. Outer contours, origins, labels, selectors, door arrays and room/item catalogs remain byte-equivalent after parsing; the two original-release catalogs are unchanged. No doorway position, door state, completion rule or UI implementation changes.

Still missing: independent observations establishing which collision edges match visible partitions, corrected alignment of the excluded perimeter geometry, actual visible stair treads, upper-level geometry, and any runtime collision changes. No assertion of exact visible floor-plan completeness follows from this work. The combined parent integration should refresh the tracker README image after integrating its separate doorway/presentation work; this isolated interior task changes no screenshot or UI file.

### Reproduction and checks

The generation environment was `/tmp/re-map-dualshock/venv/bin/python`, with Shapely `2.1.2` installed for offline polygon union and clipping. Generation now requires Shapely 2.1 in addition to the existing Unicorn dependency. Neither library is imported by the running tracker for this geometry.

Reproduce by extracting the four named RDTs and two executables with `tools/extract_psx_file.py`, checking the hashes above, then running `tools/build_re2_metadata.py` for each owned CUE and profile with both outputs under `/tmp`. Compare the generated floor-plan catalog against the checked-in document. Full regeneration matches both current floor-plan and room catalogs. For integration with other pending generator work, replace only `detail_segments` in the two named 1F regions; do not replace the parent's door arrays or room metadata.

Run:

```sh
/tmp/re-map-dualshock/venv/bin/python -m pytest -q tests/test_re2_map_interiors.py tests/test_re2_metadata.py tests/test_re2_profile.py tests/test_re2_position.py tests/test_re2_tracking.py tests/test_re2_door_layout.py tests/test_floor_plan.py
ruff check --select F tools/re2_map_interiors.py tools/build_re2_metadata.py tests/test_re2_map_interiors.py
ruff format --check tools/re2_map_interiors.py tools/build_re2_metadata.py tests/test_re2_map_interiors.py
```

The focused suite passes 987 tests, including 30 new cases for shape semantics, source bounds/counts, signed coordinates, unsigned extents, shared projection, overlapping obstacles, floor masks, unknown shape rejection, perimeter exclusion, holes, disconnected islands and source-only clipping. Catalog regressions pin source-derived ramp and office edges, enforce the stroke inset and retain original-release empty interiors. Reapplying the addition is idempotent. Ruff checks and whitespace checks pass.

Private evidence is under `/tmp/re-map-re2-interiors-20261027/`: extracted sources, native disassemblies, `native-source-audit.json`, `catalog-audit.json`, `regenerate.py`, full generation outputs, `plot.py` and numeric `*-diagnostic.png` overlays. The catalog audit structurally removes only the four new arrays before comparing complete documents, thereby checking all door arrays and unrelated metadata. Numeric overlays are source diagnostics, not native-game screenshots or a rendered tracker validation. Browser/UI behavior, runtime observations and campaign coverage are unchanged.

Contributions:

- 2026-10-27; human user; reported both missing interiors and supplied tracker screenshots.
- 2026-10-27; parent coordination, verified model `gpt-6.1-sol`; supplied owned-source paths and format leads, scoped the isolated offline geometry task, reported disabled external providers and reserved RE2-MAP-006 after assigning RE2-MAP-005 to doorway placement.
- 2026-10-27; authoring, experiments, direct review and writing: exact model `gpt-6.1-sol`, verified from this session's matching `session_meta` identifier and latest `turn_context`. Independently extracted both discs, inspected the native shape/mask code, implemented the scoped interior pass, compared numeric diagnostics, regenerated only the requested arrays, ran focused checks and authored this entry. Direct review checked correctness, source fidelity, dependencies, revision isolation, clipping, conservative omissions, deterministic output, test coverage, DX, integration scope and unchanged runtime contracts. UI/UX/AX assessment is limited to geometry and existing renderer source, without a rendered tracker or native view. Claude/Gemini providers were disabled in T3, as reported by the parent; no external review was attempted or endorsed. This review is not runtime validation.

### Parent integration and tracker rendering, 2026-10-27

The combined generator retains the separate native-doorway and vibration-proof changes. A structural comparison against the parent catalogs changes exactly the two requested interior arrays per DualShock disc; all door arrays and other floor-plan metadata remain identical. Full regeneration matches both combined floor-plan catalogs and Leon's room catalog. Claire's room proofs are unchanged; its regenerated catalog additionally serializes the integrated generator's empty vibration capability and research header, without enabling that capability.

Headless tracker renders use one retained read-only publication containing only the user's already explored rooms. Before/after renders preserve that publication. They show both obstacle sets, keep labels clear of their strokes and pass desktop/narrow-screen overflow and page-error checks. Inspecting a selected room exposed an existing CSS selector that recolored interior cores along with the outer outline. The parent restricts that highlight to the outer outline and adds a regression for inspecting each of the two rooms. The README screenshot now shows the combined geometry and item symbols.

The combined focused suite passes 1043 tests. The RE2 browser checks all 132 DualShock room labels as current with story-item colors, original-release outlines and controls, the two selected interiors, native doorway positions and key-symbol reversal. These remain tracker rendering and offline interpretation checks. No native game, savestate, guest memory or user exploration history is changed by this integration, and visible-wall alignment remains Candidate.

- 2026-10-27; parent integration, direct review, rendered checks and writing: verified executing model `gpt-6.1-sol`; preserved independently verified changes during cherry-pick, corrected contributor attribution, checked complete catalog deltas and combined regeneration, inspected tracker renders, fixed selected-room stroke scope, ran the combined focused/browser checks and refreshed the README image. External reviews remain unavailable as recorded above.
