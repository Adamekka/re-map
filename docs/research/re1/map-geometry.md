# RE1 native map geometry

[Documentation index](../../README.md) · [Claim index](../../research.md)

## RE1-VISIT-001: game visited bits decode into room lists

Status: Candidate
Scope: SLUS-00551 Map Visited bytes 0xC8710 through 0xC8717 per RA notes
Environment: offline decode 2026-09-25 with tools/map_visited.py, no gameplay
Authored: 2026-09-25; agent/tool: opencode; model: opencode/muse-spark-1.3-contributor-free
Basis: runtime observation of save files against RA labels
Claim: each visited byte decodes one room per bit. The slot save reads 6 visited rooms: Art Room Secret Room, Bar, Art Room, Main Hall, Dining Room, Tea Room. That matches real progress including Main Hall before the live walk, so set means visited. The tracker will read these as game-derived visited state, reread on every load, kept separate from its own observation history per the persistence rules. A line-join bug that bled Files rows into the 0x8717 group is fixed by stopping continuation at any new dash entry.
Evidence: tools/map_visited.py output on /tmp/ram_slot.bin, 6 VISITED lines.
Limits: set means visited is inferred from consistency, not from watching a bit flip on entry. Unvisited rooms in this save are untested.
History:
- 2026-09-25; opencode with model opencode/muse-spark-1.3-contributor-free; authored; save decode only, still Candidate.

## RE1-MAP-001: Mansion 1F topology from doors, mutually consistent

Status: Candidate
Scope: SLUS-00551 STAGE1 files with stage 0 door targets
Environment: static build 2026-09-25 with tools/door_map.py, no gameplay
Authored: 2026-09-25; agent/tool: opencode; model: opencode/muse-spark-1.3-contributor-free
Basis: source inspection of disc bytes against RA labels
Claim: 27 nodes and 54 edges form the Mansion 1F graph, committed as ASCII through tools/door_map.py and as data/mansion1f.dot. Edges run both directions everywhere checked, for example save room to stairway to vacant room and back, dining room to main hall to art room to L-passage to winding passage. Three independent sources agree: door bytes give the edges, filenames give the numbers, RA notes give the names. Room 0x10 Elevator Stairway is a target with no file, matching the earlier join misses, so it stays numeric rather than guessed.
Evidence: tools/door_map.py output, data/mansion1f.dot, bidirectional spot checks above.
Limits: topology only, no geometry or draw order. Camera variant files fold into base rooms by number. Other stages were unmapped in this finding; RE1-STAGE-001 later adds a source-derived candidate folder link without gameplay validation.
History:
- 2026-09-25; opencode with model opencode/muse-spark-1.3-contributor-free; authored; static build only, still Candidate.
- 2026-09-27; Codex with model GPT-6 Sol; linked the later candidate folder-selection finding RE1-STAGE-001 without changing this Mansion 1F topology claim.

## RE1-MAP-002: numeric Mansion 1F floor plan from indexed room regions

Status: Candidate for live map behavior; pinned disc encoding and executable calculations checked statically
Scope: Resident Evil Director's Cut USA SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`; `PSX/ITEM_M2/MAP01.TIM`, runtime Main 0
Environment: owned MODE2/2352 disc, pinned PS-X executable and generated RDT metadata, 2026-09-29; no emulator connection or gameplay in this experiment
Authored: 2026-09-29; Codex subagent `/root/remake_geometry`; model GPT-6.1 Sol
Basis: direct disc-byte decoding, pinned executable disassembly, exact contour area checks, and comparison with all Mansion same-floor RDT door targets
Claim: the classic game's Mansion 1F map encodes 32 independently indexed architectural regions and 56 region-owned half-door markers. Palette floor index is `16 + 6*region`, with the neighboring group entries carrying floor detail and door marks. Tracing room-mask cell edges yields 32 connected outer polygons and no holes for this particular map. Pairing each half marker with its unique different-room counterpart exactly 1.5 pixels away yields 28 physical doors. All 54 directed same-floor Mansion RDT links in the committed table correspond to those physical pairs. Two additional reverse directions, `10→04` and `19→0A`, have no source RDT file in STAGE1. The generated artifact stores only numeric outlines, labels, door segments, IDs and evidence metadata, with no texture pixels, palette colors or original image.

Evidence:

- `PSX/ITEM_M2/MAP01.TIM` is at LBA 11780, 29216 bytes, SHA256 `0385b147fe2a698e7ece61e82a8cfa704bfc4903b1afc884afed5955602da20f`. Its little-endian TIM header has magic 16, flags 9, one 256-color CLUT of 524 bytes, then a 28684-byte image block. Image dimensions are 128 16-bit words by 112 rows, so 256 indexed pixels by 112 rows. The extracted floor bounds are X `[1,158)`, Y `[1,93)`.
- The pinned executable's map file-ID table at PS1 VA `0x8008EB80` begins `0x00DC`. Internal file record 220 at `0x80091F68 + 12*220` contains `(LBA=11780, size=29216, 4096)`, identifying MAP01. Routine `0x80032B2C..0x80032CA0` loads the map and advances its CLUT cursor by `0xC` bytes per region, or six 16-bit entries, while evaluating the region's visit flag. At `0x80032E84..0x80032E98`, it multiplies the selected region by six, adds `0x10`, and uses that as the palette entry for the flashing current-region color.
- Numeric regions give a coherent architectural layout: Main Hall `06` spans X60..100, Y58..93; Art Room `07` is east of it; Winding Passage `09` is north of L Passage `08`; the Mansion Storeroom `18` is east of East Stairway `0B`. Every region is one connected floor component. Collinear edge collapse preserves the exact encoded area. The tool rejects ambiguous contours and unpaired half markers instead of inventing geometry.
- `data/mansion1f_floor_plan.json` contains the numeric result. `python3 tools/build_floor_plan.py <owned CUE> <output JSON>` verifies both map and executable identities, then reproduces the committed JSON byte for byte. `tests/test_floor_plan.py` covers a hole, floor-area preservation, labels on real floor cells, owned door pairs and wall orientation, malformed files, unpaired markers, marker-without-floor failure, and the 54-link RDT comparison. Eight tests passed, plus Ruff lint and format checks.
- [Mortician's TIM parser](https://github.com/mortician/lib_bio/blob/ee30311756f213f60e0d885d9c2eef668ccb53e9/lib_bio/lib_tim.py#L113-L123), commit `ee30311756f213f60e0d885d9c2eef668ccb53e9`, provided an independent format lead for indexed TIM widths; the dimensions and blocks above were checked against the owned file.

Region selection limits:

- The map region normally retains runtime Sub, but the pinned selector first copies Sub into map-state byte `0x800B7F87` at `0x80033730..0x8003374C` and applies exceptions afterward. At `0x80033798..0x800337F8`, Sub07 with camera3..6 selects region1D, while Sub0F with camera3..4 selects region1E. These are embedded secret spaces in the Art Room and Bar. Revealing them merely because the parent logical room was visited would violate entry-only disclosure.
- Sub10 with camera0 selects map selector2, region1E at `0x800337FC..0x80033838`, rather than this Mansion 1F plan. Region1F's runtime identity has not been traced. The 32 drawn regions therefore are not 32 independent RDT room files.
- No map-screen gameplay was performed. Current-region flashing, the camera exceptions, visit-bit interpretation, door-lock states, door availability, transitions and earlier-save reversal were not newly validated. No game-world-to-map coordinate transform was established, so player or item coordinates cannot be plotted by simply scaling RDT positions into these polygons. This finding does not establish item coverage or room completion.

Rejected geometry shortcut: RDT camera records with `to=9` are per-camera boundary quadrilaterals, not a global architectural plan. Their large overlapping room-local regions and collision rectangles do not establish a coherent Mansion floor plan. [Reevengi's boundary layout](https://github.com/pmandin/reevengi/blob/8130d5fd029a7548135bdbbff19b0b8e338bd42d/src/g_re1/rdt_rvd.h#L26-L43) and [collision implementation](https://github.com/pmandin/reevengi/blob/8130d5fd029a7548135bdbbff19b0b8e338bd42d/src/g_re1/rdt_sca.c#L36-L51), commit `8130d5fd029a7548135bdbbff19b0b8e338bd42d`, were inspected as leads; obstacle-box union was not used as a room outline.

History:
- 2026-09-29; Codex subagent `/root/remake_geometry`, model GPT-6.1 Sol; extracted local map metadata, traced the executable palette and selector routines, implemented the extraction tool, and ran eight focused tests without connecting to the emulator.

## RE1-MAP-003: other disc map files expose limits of the Mansion-only extractor

Status: Candidate; numeric extraction experiment only, no live area or region validation
Scope: pinned SLUS-00551 executable from RE1-ANALYSIS-010; `PSX/ITEM_M2/MAP00.TIM` through `MAP0E.TIM`
Environment: owned MODE2/2352 disc, Python 3.14.8; existing extractor at `f0f4102`
Authored: 2026-10-07; Codex root; model: GPT-6.1 Sol
Basis: disc-directory inventory, hash-verified executable identity and calls to RE1-MAP-002's existing numeric extractor
Claim: fifteen files with map names exist on this disc. The unmodified Mansion extractor accepts five, including Mansion 1F, and rejects ten. Four additional accepted files establish a practical starting point for broader geometry support. Filename count does not establish fifteen playable floors, and extraction success does not establish a live room mapping.

Evidence:

- `python tools/list_psx_files.py <owned CUE> --filter MAP` lists fifteen map files. MAP00 is at LBA 11759 with 41504 bytes; MAP01 through MAP0B are eleven 29216-byte files at LBAs 11780 through 11930; MAP0C through MAP0E are three 41504-byte files at LBAs 11945, 11966 and 11987. The private report records each full SHA256.
- Reproduced MAP01's 32 regions and 28 door pairs. Additional accepted files are MAP02 with 26 regions and 24 pairs, MAP05 with 12 and 10, MAP07 with three and two, and MAP0B with five and four. These are numeric contours and marker pairs under the existing encoding rules, with no new mapping assumptions.
- MAP03, MAP04, MAP06, MAP08, MAP09 and MAP0A fail the existing reciprocal-half-door requirement. MAP00, MAP0C, MAP0D and MAP0E fail contour ambiguity checks. Those failures show that the current extractor cannot simply be applied to every file. No check was disabled, marker dropped or floor outline guessed to obtain success.
- Private script `map_inventory.py` verifies the disc executable SHA256, reads all fifteen files, calls the committed extractor and writes only metadata, counts and explicit failures. A second execution produces an identical `map-extraction-audit.json`, SHA256 `2978f58f8609f2328092deef93e23d329d391e4d94bc834db30c66b64fbc9a31`, under `/tmp/tasks/re-map/post-interaction-inspection/`.

Limits: native file-selector tables, runtime stage/room/camera bindings, map names, cross-floor doors and alternative marker encodings have not been newly traced. The four larger files may contain other map UI content; they must not be treated as playable floor plans on filename alone. No additional plan is shipped, and the existing entry-only reveal behavior is unchanged. Disc bytes and private extraction artifacts remain outside Git.
History:

- 2026-10-07; Codex root, GPT-6.1 Sol; inventoried map files, pinned the executable identity, tested the existing extractor without modification and reran the metadata report. Original extraction-method authorship remains in RE1-MAP-002.

## RE1-MAP-004: native floor selection depends on Main, Sub and camera

Status: Candidate; pinned executable inspection and bounded native execution, no new gameplay
Scope: RE1 Director's Cut NTSC-U SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`
Environment: Python 3.14.8, Capstone 5.0.9, owned disc; no emulator memory writes or new DuckStation session
Authored: 2026-10-07; Codex root; model: GPT-6.1 Sol
Basis: disassembly of the pinned executable, native file registry and an independent bounded MIPS instruction executor
Claim: the native map selects eleven floor files. Main modulo five selects the area family; Sub and, in several spaces, camera select the floor and highlighted region. Later Mansion phases use the same native geometry while retaining their actual logical room identities.

Evidence:

- Traced PS1 virtual addresses `0x800336EC..0x80033A00`, stopping before the first helper call. Main/Sub/camera are unsigned bytes at `0x800C8660/61/62`. The native temporary map context receives normalized family, floor selector and region at `0x800B7F85/86/87`, also unsigned bytes. These context fields are source evidence, not new production reads.
- The five little-endian u32 jump-table entries at `0x80010344` are `0x80033798`, `0x80033844`, `0x800338E8`, `0x80033978`, `0x80033998`. Ordinary region equals Sub. Family zero selects Mansion 1F; family one selects Mansion 2F below Sub `1A`, otherwise B1; family two selects Courtyard 1F below Sub six, otherwise B1; family three selects Guardhouse 1F below Sub `0D`, otherwise B1; family four selects Laboratory B1 below Sub two, B2 below five, B3 below `13`, otherwise B4.
- Camera overrides are: family zero/Sub `07`, cameras 3..6, Mansion 1F region `1D`; zero/`0F`, cameras 3/4, Mansion 1F `1E`; zero/`10`, camera zero, Mansion B1 `1E`; one/`0F`, cameras 2/5, Mansion 2F `1D`; one/`0C`, cameras 4..7, Mansion 1F `1F`; two/`0B`, cameras 5/6, Courtyard B1 `11`; two/`0F`, camera six, Courtyard B1 `12`; four/`07`, cameras 0..3, Laboratory B3 `16`.
- The eleven little-endian u16 file IDs at `0x8008EB80` are `220,221,222,223,224,229,230,225,226,227,228`. Registry entries at `0x80091F68 + 12*file_id` contain three little-endian u32 values: LBA, size and type. All selected files have size 29,216 and type 4,096; their LBA/size match the owned ISO directory. This establishes MAP01/02/03/04/05/0A/0B/06/07/08/09 in selector order. The four larger map-named files from RE1-MAP-003 are outside this selector table.
- Inspected helper `0x80033AA0..0x80033CEC`: it tests visited/map-availability state but does not replace the selected floor or region. External reveal deliberately follows observed entry, not those native map-ownership bits.
- A separate private executor runs the disassembled selector with branch delays, unsigned 32-bit multiplication/HI, shifts and sparse memory. Every one of the 159 supported logical source rooms at all 256 byte camera values agrees with both the generator transcription and loaded catalog: 40,704 comparisons, zero mismatches. This executes bounded native instructions outside DuckStation; it does not reproduce natural camera transitions.

Private evidence under `/tmp/tasks/re-map/multi-area-maps/`: `native-map.txt`, SHA256 `c68352bbcfeb9372cbd572b78e04494fd35a03fdd822ff7991385e7966b0ae73`; `native-map-helper.txt`, SHA256 `b70c378139f9e5aaa9245957977b9e0964d698891db18a89d3bb0a228722baa1`; `native-selector-check.json`, SHA256 `c60b38609fdb727c1fea4874948ee78c798199813e4203b311b058c418de78a9`. Run `native_selector_check.py` with the named environment and pinned private executable to repeat the comparisons. Disassembly and game bytes remain outside Git.
Limits: later-area room entry, natural camera changes, native map-screen comparison, character/story progression and normal-save/savestate reversal of these floor transitions remain untested. Source agreement does not promote these bindings to runtime-confirmed status or other revisions.
History:

- 2026-10-07; human user; approved multi-area floor plans with automatic switching, entry-only reveal and existing item/door states.
- 2026-10-07; Codex root, GPT-6.1 Sol; traced the native selector, file table and subsequent helper, transcribed numeric bindings, independently compared all supported room/camera inputs and retained actual phase-specific logical IDs.

## RE1-MAP-005: eleven numeric floor plans contain paired, full and boundary door markers

Status: Candidate; source extraction and geometry checks, no new live door-wall identification
Scope: pinned SLUS-00551 executable and eleven selected files from RE1-MAP-004
Environment: Python 3.14.8, owned disc; existing RE1-MAP-002 extractor extended with an explicit marker policy
Authored: 2026-10-07; Codex root; model: GPT-6.1 Sol
Basis: indexed map-region ownership, contour extraction, marker adjacency and verified native file records
Claim: the eleven native plans yield 118 outlined regions and 108 door markers. The new marker policy recognizes two full doorways and seven boundary markers in addition to 99 reciprocal pairs. Boundary geometry supplies an owned wall but no destination identity.

| Floor | File | Outlined regions | Door markers |
| --- | --- | ---: | ---: |
| Mansion 1F | MAP01 | 32 | 28 |
| Mansion 2F | MAP02 | 26 | 24 |
| Mansion B1 | MAP03 | 4 | 3 |
| Courtyard 1F | MAP04 | 5 | 4 |
| Courtyard B1 | MAP05 | 12 | 10 |
| Guardhouse 1F | MAP0A | 13 | 14 |
| Guardhouse B1 | MAP0B | 5 | 4 |
| Laboratory B1 | MAP06 | 2 | 3 |
| Laboratory B2 | MAP07 | 3 | 2 |
| Laboratory B3 | MAP08 | 14 | 14 |
| Laboratory B4 | MAP09 | 2 | 2 |

Evidence:

- Region shade groups and existing contour ownership remain unchanged. A previously unpaired marker is accepted only when rectangular, adjacent to exactly one complete owned floor edge and without non-opposing additional floor ownership. A complete opposite edge identifies the second region; otherwise the result records only the owned boundary wall. Malformed or ambiguous markers still fail extraction.
- The two full markers join MAP03 region `1C` with `1E`, and MAP0A region `0C` with `0A`. The seven boundary owners are Courtyard 1F `00/04`, Guardhouse 1F `00`, Laboratory B1 `00/01`, Laboratory B3 `0C` and Laboratory B4 `14`. Each owner has one boundary marker in this catalog. No boundary destination is inferred from exit count or floor membership.
- Five supported source rooms select a native region with no colored polygon: `06-00` Mansion elevator on 2F; `02-03` heliport on Courtyard 1F; `02-10` laboratory elevator on Courtyard B1; `04-0d` elevator on Laboratory B3; `04-15` elevator on Laboratory B4. The catalog declares these omissions and retains room metadata. It does not fabricate shapes.
- All 118 outlines have logical source aliases. The 159 actual Main/Sub identities normalize to 115 selector rows, with explicit camera overrides. Reference names come from the user-provided labels and are not evidence for identity. Native camera regions can share a logical room's item list.
- Two complete generations are byte-identical. The old reciprocal-only Mansion generator still produces its committed artifact byte-for-byte. Synthetic marker tests cover a full doorway, an owned boundary without a neighbor and rejected ambiguous ownership.

Numeric catalog SHA256 is `a91720c8a0f4070658712ba9941eacf58265c7b58ac7235672fe1cb625bda4b5`. Private `marker-audit.json` under `/tmp/tasks/re-map/multi-area-maps/` has SHA256 `d9aa4e3eaa71ee67a018c1c1f54901568c9818b30404dcbf8b20a753247eff46`. Reproduce with `tools/build_floor_plans.py <owned CUE> <output JSON>` and the pinned manifest, then compare output hashes. The catalog contains numeric contours, coordinates, labels, source hashes and bindings; no source image, texture or palette colors are exported.
Limits: geometric adjacency does not validate live directionality, door access or actual traversal. Seven boundary wall identities remain unfinished detection work even when their logical exits have known access. The larger map-named files remain excluded by the native table, rather than accepted by relaxed contour checks. Original contour-method authorship remains in RE1-MAP-002.
History:

- 2026-10-07; Codex root, GPT-6.1 Sol; extended the explicit extraction policy, audited marker ownership, generated and regenerated all eleven plans and checked unchanged Mansion output. Kept unoutlined rooms and boundary identities explicit.

## RE1-MAP-006: shared map publication switches floors and reveals only entered regions

Status: Candidate; implementation, synthetic browser checks and unchanged recorded-RAM replay
Scope: pinned SLUS-00551 profile and RE1-MAP-004/005 catalog; existing item/door tracking rules unchanged
Environment: Python 3.14.8, pytest 9.1.1, local browser preview on port 8766; no new emulator gameplay
Authored: 2026-10-07; Codex root; model: GPT-6.1 Sol
Basis: direct implementation inspection, regression tests, browser execution and existing captured-state replay
Claim: production map publication now selects the native area/floor from a coherent source-bound room/camera observation. It preserves entered geometry per floor, uses actual logical room IDs for item/door details and keeps completion separate from visits. Demonstrated map coverage increases from one floor to eleven; item/door interpretation coverage is unchanged.

Implementation and evidence:

- Runtime profiles require revision-matching floor-plan configuration. Mandatory loading validates schema, executable identity, area/region references, finite geometry, camera rules and corresponding logical source aliases. Every supported source room must have a binding. Unsupported external room data yields an explicit unavailable-map result, not a guessed area.
- Polling rereads camera before the final room check. A failed, short or changed camera read cannot publish a new region visit. Camera-dependent spaces enter history separately. In-game map-ownership changes do not reveal outlines. Unoutlined current rooms retain their details and selected floor without adding visits to nonexistent shapes.
- The browser automatically changes floor title, geometry and selection. It renders only the selected floor's entered regions. Full logical IDs preserve door links across later Mansion phases and area boundaries. Destination names are withheld until that logical room has been observed. Paired/full door markers use supported endpoint identities; boundary markers remain unassigned while known exit states stay in the list.
- The full suite passes 1,526 tests in 65.38 seconds. After the final boundary-rendering correction, all 60 focused map/extraction/HTTP tests pass in 3.65 seconds. The new tests cover selector/camera boundaries, all 159 source identities at all byte cameras, entry-only floor histories, map acquisition, undrawn rooms, camera coherence and malformed configuration including disagreeing aliases. Scoped Ruff lint/format and `git diff --check` pass; the repository has no configured project formatter, linter or Markdown check. Existing test import bootstraps retain their scoped lint exception.
- A private, explicitly synthetic browser preview exercised one room on each of all eleven floors: `00-09`, `01-03`, `06-1a`, `02-00`, `02-06`, `03-00`, `03-0d`, `04-00`, `04-02`, `04-05`, `04-13`. Every selected title and logical room ID matched, with exactly one entered/current outline and no cross-floor reveal. Returning to Mansion 1F retained its original outline, item and door details. A waiting snapshot retained geometry while removing current/completion colors, door markers and item/door details. Browser error/warning logs were empty.
- After review, a second browser case used Courtyard `02-00` with synthetic access on actual source endpoints `00-1b`, `02-01` and `02-02`. The paired marker showed Open/Unlocked, the boundary stayed Unchecked, and all three access labels remained in the list; only region `00` was revealed. This verifies renderer behavior, not those endpoints' natural access states. Temporary servers/tabs were closed; the user's tracker and emulator were untouched.
- The unchanged twelve-step, eleven-capture replay preserves Main Hall clearance, normal-load/return results, Art Room Ribbon and Map acquisition reversals and entry-only reveal of logical rooms `00-06/00-07`. Offline projection still reports 291/334 complete reentry item variants and 312/334 complete door variants under the unchanged Herb-before configuration. This feature adds map coverage, not new whole-source item or door completeness, natural progression tests or a whole-game reliability claim.

Private replay evidence under `/tmp/tasks/re-map/multi-area-maps/`: `audit.json`, SHA256 `ee748bb741a2d2c9f6c10e969548fd73373d24ee8956c9aa6575e72326995ebf`; `projection.json`, SHA256 `617bc89afaaede17874dcb5633c8a59588c4459f05972551a466d95c00e5ded5`. Run `audit.py` with the named environment and existing RE1-REENTRY-004 captures. Raw RAM, game files, saves and browser test fixtures remain outside Git. Replaying old captures adds regression evidence, not new gameplay coverage.
Limits: later-area natural entry, actual boundary-door wall identification, whole-game item/story behavior, character differences and broader normal-save/savestate validation remain open. Visit history still belongs to the tracker session and resets on restart. Five native unoutlined spaces retain details rather than invented geometry. The original 43 item and 22 door source gaps from RE1-ANALYSIS-010 are not resolved by this map feature.
History:

- 2026-10-07; Codex root, GPT-6.1 Sol; implemented required catalog loading, coherent selection, per-floor reveal and full-ID door publication; ran static/native comparisons, regressions, unchanged capture replay and browser checks. Independent direct review checked source aliases, camera publication, unoutlined details, stale-state removal and directional endpoint handling.
- 2026-10-07; human user; specifically authorized sending this feature's 306,066-byte redacted snapshot to Gemini Pro and Gemini Flash through agy. Snapshot SHA256 `374d927e8fdbd7a670035143155941d2427758c0f3eee2f86551102ae5fc6164`; code, tests, configuration and numeric map metadata only, with no game files, RAM, saves, credentials or personal paths.
- 2026-10-07; Gemini 3.1 Pro High via agy, conversation `f452a5d6-430d-4802-a997-47c1404142b0`; reviewed the supplied complete feature diff, core interfaces, catalog, regressions and pinned native contracts. Raised boundary-matching concerns. Root checked actual marker counts and source endpoints, then removed unsupported boundary-to-exit assignment and verified the corrected browser behavior. Advisory review did not reproduce native execution or gameplay.
- 2026-10-07; Gemini 3.8 Flash High via agy, conversation `049477ae-b97d-4ca4-bf24-39c9cf3853f8`; reviewed the same snapshot and returned no findings. Both completed calls have exit zero, final agent response DONE, terminal result SUCCESS, empty stderr and no tool use. Their snapshot predates the final boundary correction and small lint adjustments; those final changes were inspected and verified by root.
- 2026-10-07; Claude Opus 5.5 High via agy; unavailable under RE1-EVENT-011's quota exhaustion reported on 2026-10-05 with reset in 110 hours, 53 minutes, 55 seconds. No retry before reset, substitution, review or endorsement.
