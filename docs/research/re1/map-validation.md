# RE1 map gameplay observations

[Documentation index](../../README.md) · [Claim index](../../research.md)

## RE1-MAP-007: first live adjacency check and incomplete floor-crossing experiment

Status: Candidate; one captured natural transition on Mansion 1F, no completed floor-crossing test
Scope: Resident Evil Director's Cut NTSC-U SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`, Training Jill
Environment: isolated official DuckStation `0.1-11894-gc66b2694d`, owned CUE loaded from the user's Games directory, native keyboard input, GDB localhost:2345, production tracker at `c90d60b`, private map preview on port 8766
Authored: 2026-10-07; Codex root; model: GPT-6.1 Sol
Basis: normal controller input, native screenshots, two coherent paused RAM captures and exact replay through the shared tracker
Claim: the observed Storeroom-to-East-Stairway transition preserves entry-only map reveal and supported remaining-item/door details. This experiment does not establish natural floor switching or increase whole-game item/door interpretation coverage.

Evidence and test log:

| Action | Expected | Observed |
| --- | --- | --- |
| Load the existing Chemical-before setup in Storeroom `00-18`; start a fresh tracker | Only Storeroom outlined, Chemical remaining | Region `mansion1f:18` only; Chemical available, complete item list, `INCOMPLETE`; exit to `00-0b` has no lock |
| Leave through the room's door using movement and confirm input | East Stairway `00-0b` added, Chemical untouched, remaining herb shown | Regions `18` and `0B` only; Green Herb available, complete item list, `INCOMPLETE`; return exit has no lock, exit to `00-0a` is unlocked, upstairs exit to `01-07` has no lock |
| Attempt the East Stairway ascent | Stable Mansion 2F view, followed by a captured return | Later native observation showed the title screen; no coherent upstairs capture or controlled round trip was obtained |
| Load the fresh opening Dining Room setup | Obtain a route to Main Hall stairs | The Main Hall door reports passage unavailable during this story phase; excluded from the floor-crossing result |
| Load the previously validated post-opening Art Room setup | Leave the statue platform and reach Main Hall stairs | Platform navigation did not complete; no additional adjacency or floor result |
| Load the existing Herb-before setup in Winding Passage `00-09` | Reach an adjacent stairway and resume the floor test | Fresh tracker showed only region `09`, Green Herb remaining and supported door access. Native control then repeatedly timed out, so no floor result |

The first two captures verify the runtime executable signatures before reading all 2 MiB of PS1 RAM while paused. No guest RAM writes, teleports, executable patches or injected event calls were used. Existing Main/Sub bytes at PS1 virtual `0x800C8660`/`0x800C8661` and camera at `0x800C8662` are u8 values. The Chemical byte `0x800C86DE`, u8 mask `0x04`, stayed `0xFF`. Source binding, item interpretation and door access use the existing profile rules. The live browser displayed the two outlined rooms and their supported details. During the door transition, polling briefly rejected disagreeing room/source identity and out-of-RAM script ranges before recovering.

Private evidence under `/tmp/tasks/re-map/multi-area-gameplay/`:

| Artifact | SHA256 | Purpose |
| --- | --- | --- |
| `storeroom-before.bin` | `f25890c65f29c2a9653dc8432077795828453ef2ed46117b9986173ade6d5845` | Coherent starting RAM |
| `east-stairs-before.bin` | `52ecade361ce3cfc9b2bbd9265eb9ce257b11d855914345227159ccb67a6be67` | Coherent RAM after the observed exit |
| `adjacency-audit.json` | `490d5ff25925c55d26934510e9e007ed22f2d8728cc66806536a2988ac162a44` | Exact snapshot publication equality, room/area/reveal/item checks |
| `live-floors-b.jsonl` | `d12b367ea0858e45cc8f8bf2576a0a50ba2b68a9047b9c7b8d5a279dfed34703` | Separate Art Room setup run |
| `live-floors-c.jsonl` | `b8ab08817105de08bddd8b1d5f1b065fb5cd99a58f05fa6b8634c4acb4795c0c` | Separate Winding Passage setup run |

The exact replay uses one fresh profile/cache and tracker for the two new captures, checks their hashes and byte lengths, and compares each complete published payload with its live capture metadata. It adds reproducibility for this transition, not another natural run. Earlier buffered poll output included `01-07` among room changes across setup loads, but no contemporaneous controlled screenshot/capture establishes its entry or return; it is excluded from validation.

Limits and failed setup: the title-screen outcome is unexplained. Native automation later reported repeated five-second timeouts and a macOS ScreenCaptureKit audio/video capture failure. DuckStation's own Screenshot menu still produced one view of the loaded Winding Passage setup. Disconnecting the owned GDB client and resetting the native-control session did not restore app access. This does not establish a GDB performance fault or a tracker floor-selection defect. All temporary GDB/HTTP sessions ended normally and the agent-created browser tab closed. The isolated emulator remained running because native control could no longer close it. No user save was overwritten; raw captures, screenshots, states, logs and the private polling script remain outside Git. Natural Mansion 1F/2F switching, return histories and later areas still require a completed controlled experiment.
History:

- 2026-10-07; Codex root, GPT-6.1 Sol; performed the first observed adjacency, captured and replayed its RAM, checked live browser publication, and recorded unsuccessful floor-test setups separately. Production code and profile data were unchanged.
- 2026-10-07; Codex root, GPT-6.1 Sol; subsequent RE1-MAP-008 completed a Main Hall floor round trip with a different starting setup after native control recovered. The earlier failed setups remain excluded from floor validation.

## RE1-MAP-008: natural Main Hall floor switching and return history

Status: Confirmed for this revision, limited to the observed Main Hall crossings and session history
Scope: Resident Evil Director's Cut NTSC-U SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`, Training Jill
Environment: isolated official DuckStation `0.1-11894-gc66b2694d`, owned `Resident Evil - Director's Cut.cue` from the user's Games directory, native keyboard input, GDB localhost:2345, production tracker at `e15e9be` with feature code from `c90d60b`, private map preview on port 8766
Authored: 2026-10-07; Codex root; model: GPT-6.1 Sol
Basis: natural controller input, native screenshots and browser DOM observations, nine coherent paused RAM captures, exact replay through the shared tracker
Claim: ordinary Main Hall stair use switches the tracker between Mansion 1F and 2F, reveals only entered regions, and restores each floor's observed visits and supported item/door details on return.

Evidence and test log:

| Action | Expected | Observed |
| --- | --- | --- |
| Load the existing private floor-level Art Room setup; start a fresh tracker | Only entered Art Room outlined | `00-07`, region `mansion1f:07`, Map and Ink Ribbon available; no other room revealed |
| Leave normally for Main Hall 1F | Main Hall added, items untouched | `00-06`, regions `06` and `07` only; Ink Ribbon available, quantity 3, `INCOMPLETE`; four exits detected, including Armor Key lock toward `00-11` |
| Walk to the central staircase and ascend | Switch to Mansion 2F, reveal only the entered Main Hall | `01-03`, region `mansion2f:03` only, `CLEARED` with complete zero-item coverage; four no-lock exits after animation, downstairs destination named and the three unvisited destinations unnamed |
| Descend through the same stairs without loading a state | Restore 1F history and remaining item | `00-06`, regions `06` and `07` only; Ink Ribbon still available, `INCOMPLETE`; same four supported exits, with upstairs now named Main Hall 2F |
| Ascend again without loading a state | Restore 2F history without revealing neighbors | `01-03`, region `03` only; same complete zero-item state and four no-lock exits |
| Replay starting-state RAM, followed by all nine new captures | Reproduce complete published payloads | Exact equality for each capture, including item quantities, directional doors and visit-dependent destination labels; final visit set exactly `mansion1f:07`, `mansion1f:06`, `mansion2f:03` |

Only the initial Art Room setup used a savestate. All four subsequent room changes used ordinary movement and confirm input; no guest RAM writes, teleports, executable patches or injected events were used. Each capture verifies the running executable signatures, pauses the CPU and reads all 2 MiB of RAM. Room Main/Sub at PS1 virtual `0x800C8660`/`0x800C8661` and camera at `0x800C8662` remain u8 values under the existing profile. Captured Main Hall cameras were 2 then 1 downstairs and 0 upstairs. These observations validate existing map selection, not a new address interpretation.

The live 2F DOM contained exactly one current, cleared room group with the Main Hall's multi-ring SVG outline and three open wall markers. Its sidebar contained four exits; the cross-floor stair exit has no same-floor neighbor marker. No unopened adjacent room outline appeared. On the downstairs return, the browser showed two explored rooms, the remaining Ink Ribbon, the Armor Key lock and the visited upstairs destination. All native views showed Jill under player control after each stair animation. Initial automatic pauses also captured the transition animation; the later `controlled`/`return` captures and browser observations establish the settled gameplay views separately. Polling briefly rejected room/source disagreement and out-of-RAM script ranges during each crossing, then recovered without reconnecting.

Private evidence under `/tmp/tasks/re-map/multi-area-gameplay/`:

| RAM capture | UTC time, 2026-10-07 | SHA256 |
| --- | --- | --- |
| `e-main-before.bin` | 19:12:36 | `8928a69b82aa64edb8a3cc9fd8daa7b1b26d0107031fb0da428163cadd839cc8` |
| `e-stair-approach.bin` | 19:14:03 | `16877eaa67a40ccc324cfadca61a4ba1519fa94811845d7342887f95d3863613` |
| `e-stair-blocked.bin` | 19:15:16 | `853027d8b9d408a57ed1a63c9fad2d0e6c8e6b285d86413087ab5ef10e6d7c2d` |
| `e-floor-1.bin` | 19:16:04 | `6a21d9663a1951d2c73c4f7d405f17d06c685296f5a4e8fe5544b5b89982e4ce` |
| `e-upstairs-controlled.bin` | 19:19:34 | `6132eb64b5f865e6088edd474ee505b9817273f2229f6a135efe040b49956ccc` |
| `e-floor-2.bin` | 19:20:51 | `39f4f08bf781a7b6ab1ec60e4beb744a5e025d0366f4a131696996c1a3513cc3` |
| `e-main-return.bin` | 19:21:27 | `fcca8b81a61123773727c400cf91ddf9fd9482f571ddbbd9cb328d926d84c976` |
| `e-floor-3.bin` | 19:21:55 | `a12d1cebe72caea6b3c96b8cd1386943a502878f95fd44d9b91c68659bf02980` |
| `e-upstairs-return.bin` | 19:22:33 | `c77ca5140180bd0b4d96b51f4e8f830f30bdf0c225e585c090af73a4f37b3e9d` |

Each adjacent `.json` records the full live payload, timestamp, region, camera and capture hash. `live-floors-e.jsonl` SHA256 `8771e2ff5253c65ca989808308ada5c4277393538647fb14920128b60f4e2eec` records the session. `floor-crossing-audit.json` SHA256 `5c668401fc3241a7f0338ac1e3434ec2f22ff41c4f3d3da1f9147c05050d4e40` records publication equality and final history. Reproduce with `python /tmp/tasks/re-map/multi-area-gameplay/audit_floors_e.py` using the recorded artifacts and source revision; script SHA256 `a6d637374d05c2f292b8eb4cf7a4125b0e669d72a025e26c7ba579d5c748b489`. The starting private `SLUS-00551_2.sav` has SHA256 `609184b9bef7eab045790b5a3873e1eb73957954be33a9303192945379465e76`; its extracted RAM SHA256 is `e19a99452d27e0e69fefbe9ba2d11c47218eb07912c63c2340ebe5b601b17f44`. That extraction primes the replay's initial Art Room visit and is not an additional live observation.

Failed setup and changed conditions: native control recovered after restarting the isolated emulator. A renewed Chemical-before route again reached East Stairway 1F, where a zombie visibly grabbed Jill; the starting health candidate was 54 and the run later reached the intro/title flow without an upstairs capture. This does not prove the cause of RE1-MAP-007's earlier title outcome. Its separate `live-floors-d.jsonl` SHA256 is `1bfaf2531086554e3f9ff17cb0e1acdf3466bd3fc8ea0d242ddeef2f99a7f1b1`. The successful run instead used the existing Art Room floor-level setup with health candidate 150 and an enemy-free Main Hall route. All nine successful captures retained that value and the untouched Chemical byte `0xFF`; health was a setup check, not a newly confirmed tracker address.

Limits: this is one Training Jill session with two ascent observations and one descent, not a whole-game playthrough. It does not validate the other nine floor plans, all Mansion rooms, native map-screen alignment, map acquisition in this run, pickup/save reversals, other scenarios, or changed story conditions. RE1-MAP-004/005/006 retain their broader source/synthetic validation limits. Whole-game item and door coverage is unchanged. Raw RAM, saves, game assets and private scripts remain outside Git. The owned GDB/HTTP session ended normally, its browser tab closed, and the isolated game closed without saving.
History:

- 2026-10-07; Codex root, GPT-6.1 Sol; performed the natural Art Room exit and Main Hall up/down/up run, checked rendered outlines and supported details, captured and replayed nine snapshots exactly, and documented the scoped result. Production code and profile data were unchanged.

## RE1-MAP-009: native Main Hall map views preserve tracker state

Status: Confirmed for this revision, limited to the two recorded Main Hall map-menu openings
Scope: Resident Evil Director's Cut NTSC-U SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`, Training Jill
Environment: isolated official DuckStation `0.1-11894-gc66b2694d`, owned CUE from the user's Games directory, native keyboard input, GDB localhost:2345, production tracker at `d0610fd`, private map preview on port 8766
Authored: 2026-10-07; Codex root; model: GPT-6.1 Sol
Basis: native map-menu observations and screenshots, seven coherent paused RAM captures, exact replay through the shared tracker
Claim: opening the game's map in Main Hall 1F and 2F selects the same floor and current region as the tracker and leaves its complete published state unchanged. The native current-room shapes were also compared visually with the catalog's Main Hall outlines; this is a qualitative comparison, not a measurement of every pixel or room.

Evidence and test log:

| Action | Expected | Observed |
| --- | --- | --- |
| Load the existing full-health floor-level Art Room setup and start a fresh tracker | Reveal Art Room only | Region `mansion1f:07`, Map and Ink Ribbon available |
| Leave normally for Main Hall 1F | Add Main Hall, preserve untouched items | Regions `06` and `07` only; Main Hall Ink Ribbon remains available; supported door access unchanged |
| Open status menu, select Map, confirm Mansion 1F | Native floor/current room agree; tracker reveals no extra room | Native context `[0,0,6]`, current Main Hall shown as the large central room; complete tracker payload exactly equal to the pre-menu capture |
| Return to gameplay and ascend normally | Switch to Mansion 2F | Current `01-03`, region `03` only, complete zero-item state and four supported exits |
| Open status menu, select Map, confirm Mansion 2F | Native floor/current room agree; tracker reveals no extra room | Native context `[1,1,3]`, Main Hall's separate balcony/stair regions shown; complete tracker payload exactly equal to the entry capture |
| Attempt the eastern balcony route to Terrace Entry | Capture a new adjoining room | No new room reached. Two navigation captures stayed in `01-03`; later computer control rejected actions because the emulator window changed, so input stopped |
| Replay all seven captures in order with one fresh profile/cache and tracker | Reproduce complete live publications | Exact equality for all seven payloads; final visit set only `mansion1f:07`, `mansion1f:06`, `mansion2f:03` |

RE1-MAP-004's temporary native map context at PS1 virtual `0x800B7F85`, `0x800B7F86`, `0x800B7F87` contains three unsigned bytes for normalized family, selected floor and region. The two menu captures observed `00 00 06` and `01 01 03`, respectively. These are experimental reads of the selected native view, not new production room addresses. The catalog selected `mansion1f:06` and `mansion2f:03` from the existing Main/Sub/camera reads. Both map views preserved the full item, quantity, completion and directional-door payload, not just room count. The native 1F image also showed previously visited rooms absent from this fresh tracker's history; those extra outlines did not appear in the tracker. No in-game map was collected during this run.

The native 1F screenshot shows the central Main Hall and adjoining Art Room to its right, consistent with their catalog outlines. The 2F screenshot shows the Main Hall's two side balconies, rear connection and separate central stair regions, consistent with its three catalog rings. The game uses red for its current room; the tracker uses its own item/completion colors. This comparison does not validate room-clear colors against the original game's map.

Private evidence under `/tmp/tasks/re-map/multi-area-gameplay/`:

| RAM capture | UTC time, 2026-10-07 | SHA256 |
| --- | --- | --- |
| `f-art-start.bin` | 19:29:15 | `9283fff86a0eb297a507528a1fbb754bb6472e23866e5e93fda86cda5f81a0f0` |
| `f-main1-before-map.bin` | 19:30:03 | `a67623d80c6cc6d4a3d82a886a3f946f487f33a7ca92d5ed656de1a1a9742e73` |
| `f-native-map1.bin` | 19:32:24 | `7f84f1753a82ec4fcb3f7bcc216112cdf044d29d8281f99404fedca529cdb601` |
| `f-floor-1.bin` | 19:34:57 | `6a8e26e57f06b12d60492670fc705c5d034c9f8a4ded2eb2563477931147f097` |
| `f-native-map2.bin` | 19:37:53 | `aecb76fad4a78dda866b9e9a4052b9a4799dc1ccf9cc4ede4f180dfb053c237e` |
| `f-balcony-position.bin` | 19:40:00 | `c23d39b36447d3dff19a01e916df371b4271bda74355f48b4d3a13221ada96a4` |
| `f-balcony-position2.bin` | 19:41:49 | `2cc9f76b7bef513e72728a9d48d414bc538ce1f3c3f7f3af49de5c7b33498a2a` |

Adjacent `.json` files contain the full live payloads. `live-floors-f.jsonl` SHA256 is `55ae13d971019ed5d449ca1c1a95e2505e356b54c7911180c7bd1f14e1a7ceb5`; `native-map-audit.json` SHA256 is `e101dfa48f51c78e763b64b5aec19fa65e8d1345154278b9a2dfe310ba5d6aa2`. Reproduce with `python /tmp/tasks/re-map/multi-area-gameplay/audit_native_maps_f.py` using these artifacts and source revision; script SHA256 is `1b7db49561b50a5d7eb5b4c7a8e1da8f045188607af96b57f343600add7a3659`. Each RAM capture verifies the executable signatures before reading 2 MiB while paused. All retained the setup's health candidate 150 and Chemical byte `0xFF`.

Native screenshots remain in the isolated emulator's private `Contents/MacOS/screenshots/` directory: `Resident Evil - Director's Cut 2026-10-07-21-32-51.png`, SHA256 `cf64c100a77ca157c9972131455762b2599cae2db1e28c3205cfa67655772107`, and `Resident Evil - Director's Cut 2026-10-07-21-38-11.png`, SHA256 `08ed30d7ef89647a978904b6273b0f09f793cc5e5865c80b9389a634aecee235`. Filenames use local time; capture metadata uses UTC. The emulator's Screenshot action saved these views without the desktop window or performance overlay. Screenshots and game bytes remain outside Git.

Limits: two Main Hall map views do not confirm the other nine floor plans, adjoining 2F rooms, all wall-marker positions, other cameras/scenarios, map acquisition, pickup/save reversal or whole-game reliability. No new item/door source coverage was gained. Navigation did not reach Terrace Entry and is excluded from successful validation. The experiment used only the initial existing savestate and ordinary controls thereafter, with no guest RAM writes or injected events. The owned GDB/HTTP session ended normally and the temporary browser tab closed. The emulator was not closed after the external window-change notices. Production code and profile data were unchanged.
History:

- 2026-10-07; Codex root, GPT-6.1 Sol; opened and captured both native map views, compared their context and visible geometry, replayed all seven publications exactly, and recorded the interrupted adjoining-room attempt separately.

## RE1-MAP-010: adjoining Mansion 2F rooms reveal on entry and retain history

Status: Confirmed for this revision, limited to the recorded Main Hall, Terrace Entry and Terrace route
Scope: Resident Evil Director's Cut NTSC-U SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`, Training Jill
Environment: isolated official DuckStation `0.1-11894-gc66b2694d`, owned CUE from the user's Games directory, ordinary keyboard controls through computer use, GDB localhost:2345, production tracker at `8c692b1`, private preview on port 8766
Authored: 2026-10-07; Codex root; model: GPT-6.1 Sol
Basis: natural room transitions, rendered map observations, ten coherent paused RAM captures and exact replay through the shared tracker
Claim: the existing map reveals Terrace Entry `01-11` and Terrace `01-12` only upon entering them. Leaving Terrace and returning preserves all three observed 2F outlines and the supported collected-item state. This extends RE1-MAP-008/009's live coverage by two adjoining rooms, without adding production rules or geometry.

Evidence and test log:

| Action | Expected | Observed |
| --- | --- | --- |
| Start a fresh tracker in the retained Main Hall 2F gameplay state | Reveal current room only | `mansion2f:03` only, complete zero-item state and four supported exits |
| Descend and ascend through the central stairs, then use the right side stairs | Preserve logical Main Hall identity on the side balcony | Main Hall 1F visit recorded; back upstairs, only region `03` outlined; side-stair movement kept `01-03` and its completion unchanged |
| Walk to and enter Terrace Entry | Reveal one adjoining corridor | `01-11`, regions `03` and `11` only; zero items, `CLEARED`; two no-lock exits, with unentered Terrace unnamed |
| Enter Terrace normally | Reveal its outline and supported item | `01-12`, regions `03`, `11`, `12` only; one item, quantity 6, `INCOMPLETE`; no-lock exit to Terrace Entry |
| Confirm Barry's scripted Bazooka grant | Reevaluate current room | One item collected, `CLEARED`; acquisition evidence is recorded separately in RE1-PICKUP-005 |
| Leave Terrace for Terrace Entry and re-enter | Keep entered-room history and collected state | Same three outlines; Terrace remains `CLEARED`, its item taken and exit supported; settled native gameplay observed after each return |
| Replay all ten new captures with one profile/cache and tracker | Match complete published state | Exact payload equality, including quantities, room colors, door access and visit-dependent destination labels |

Changed navigation conditions after RE1-MAP-009: inspected the owned `ROOM2030.RDT` collision section and active stair interactions, then used confirm at the right side stairs instead of walking through the railing. The [pinned reevengi collision reader](https://github.com/pmandin/reevengi/blob/8130d5fd029a7548135bdbbff19b0b8e338bd42d/src/g_re1/rdt_sca.c#L37-L71) supplied a format lead. The original file's five counts are `(11,3,4,2,0)`; its 20 collision records match the loaded room bytes exactly. Loaded header fields are relocated pointers, so reading them as file offsets or counts was rejected. This was private route preparation, not a new collision API or confirmation of universal floor/type semantics. Ordinary confirm input visibly started the side-stair animation and reached the balcony. Timed turn assumptions were also corrected using short paused position reads. One input was rejected after a GDB pause/resume changed the window state; refreshing the current view allowed input to proceed.

Each new capture verifies the running executable signatures and reads all 2 MiB while paused. Existing room Main/Sub/camera at PS1 virtual `0x800C8660`/`0x800C8661`/`0x800C8662` remain unsigned bytes. The four automatic entry captures caught door animation; `g-entry-controlled` and `g-terrace-return`, plus native and browser observations, distinguish settled gameplay. Polling briefly rejected inconsistent room/source or camera reads during transitions and the cutscene, then recovered on the same connection. No guest RAM writes, teleports, executable changes or injected events were used.

Private evidence under `/tmp/tasks/re-map/multi-area-gameplay/`:

| RAM capture | UTC time, 2026-10-07 | SHA256 |
| --- | --- | --- |
| `g-balcony-start.bin` | 20:08:46 | `716f0872e7d9cf018ac2d70525398a282fb68a75c523969728c4fb2c6e46a906` |
| `g-side-balcony.bin` | 20:13:12 | `1d47bb7c5ca86c2bb5a9ed40d508023408a040392db00b1474c7c3c8e49ae76a` |
| `g-floor-1.bin` | 20:15:20 | `4efb168a62bdf41c7609e7c65d235a06c7fc79c8ec81da0ba30777e1094c5548` |
| `g-entry-controlled.bin` | 20:17:04 | `64b6f4b2ea198aea1d5bf74031be94f1ce2c09feaaae5ede1297872ab045c494` |
| `g-floor-2.bin` | 20:18:21 | `681502ef3863419115058e16a40d6fc5fc0378802582ffb52e4d1e7d69283b3e` |
| `g-terrace-grant-prompt.bin` | 20:21:12 | `3063615c723aed864a55d307c2b2ae697b13fe4dcb42138622994bf2425641db` |
| `g-terrace-collected.bin` | 20:22:40 | `e1b3db62d6c52cba400228bc7a9af746c0802495730fd7767a2302d7eff3231b` |
| `g-floor-3.bin` | 20:24:38 | `789375145496bb47b58722bb992899aec7cc458e51c4140cac325184b952ade8` |
| `g-floor-4.bin` | 20:26:02 | `f4e14e9ace669932f248df34409d6609f15e0794dede290774afdeaf8612d6c4` |
| `g-terrace-return.bin` | 20:27:26 | `f45a2d7aa95fc51ef933fbd63f85689bc4b55dd118bda22796343f5a32e97e91` |

Adjacent `.json` files contain complete live publications. `live-floors-g2.jsonl` SHA256 is `4404f68ca108cdda62d2f4f32b0aa810c67d9473977a22afe754bc3baacd9384`. Reproduce with `python /tmp/tasks/re-map/multi-area-gameplay/audit_adjoining_g.py`; script SHA256 is `1801ede31602fe95cbcfb0f4ce900d458e6b33776474213ac760989ed6a1ae00`, output `adjoining-room-audit.json` SHA256 `7d37d8b1f76169be5658976cba0c2e8d9c4c616f2aa937ce1845c100bbfab20b`. The private watcher `floor_g.py` SHA256 is `338a395e569c2c4b6b0f6d9c9018bcf991289968f1bdc5395100b071f9223381`. An intervening Main Hall 1F visit was journaled without a new full RAM capture. Replay reuses RE1-MAP-009's `f-main1-before-map.bin` to prime that source and visit, and checks its resulting complete publication against the actual G-session journal. That prior capture is excluded from the ten new captures and from new gameplay coverage. Final observed visits are exactly `mansion1f:06`, `mansion2f:03`, `mansion2f:11`, `mansion2f:12`.

A new private checkpoint `g-terrace-collected.sav`, SHA256 `21d29e6a52c093f291e4b5760746de0f07eb53b780fb24275d0cc596dc699936`, preserves progress at the returned Terrace without overwriting any existing slot. Extracted checkpoint RAM SHA256 is `af08a2e37f070391a6f03c62222067c578ec5b15be987a091e3359aae6b0ce17`; the audit verifies room `01-12`, the cleared acquisition bit and inventory item/quantity. Extraction does not validate a savestate reload. The GDB/HTTP watcher ended normally, the temporary browser tab closed, and the isolated game closed without saving another state. RAM, game files, saves and private scripts remain outside Git.

Limits: this adds two rooms on an already tested floor, not live coverage of another area or the remaining nine floor plans. It does not confirm all Mansion door-wall positions, all cameras, other scenarios, map acquisition, pickup reversal, normal save/load of this item or a whole-game playthrough. Item/door source coverage is unchanged. Production code and profile data were unchanged.
History:

- 2026-10-07; Codex root, GPT-6.1 Sol; prepared the side-stair route, entered both adjoining rooms naturally, observed entry-only outlines and return history, replayed all ten captures exactly and preserved a separate checkpoint. No external implementation review was performed because this work changes research documentation only.
- 2026-10-07; Codex root, GPT-6.1 Sol; actually loaded that retained checkpoint in RE1-MAP-011 and observed the collected Terrace state. The original extraction-only experiment is preserved above; the later runtime evidence adds after-state restoration.

## RE1-MAP-011: three further Mansion 2F rooms reveal on natural entry

Status: Confirmed for this revision, limited to the recorded C-Passage, Small Library and East Stairway 2F entries and checkpoint restoration
Scope: Resident Evil Director's Cut NTSC-U SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`, Training Jill
Environment: isolated official DuckStation `0.1-11894-gc66b2694d`, owned disc, ordinary controls through computer use, GDB localhost:2345, production tracker at `c2dbf65`, private browser preview on port 8766
Authored: 2026-10-07; Codex root; model: GPT-6.1 Sol
Basis: native gameplay and messages, 17 coherent paused RAM captures, browser observations and 21 exact state replays with the shared profile/tracker
Claim: natural entries into C-Passage `01-04`, Small Library `01-06` and East Stairway 2F `01-07` add their outlines individually. Loading an earlier checkpoint reevaluates game-derived door and item state while retaining the session's observed-room history. This adds three rooms to RE1-MAP-010's live route without changing production geometry or rules.

Evidence and test log:

| Action | Expected | Observed |
| --- | --- | --- |
| Load RE1-MAP-010's retained Terrace checkpoint and start a fresh tracker | Reveal current room only; retain its collected item | Only region `12`; `CLEARED`, item taken, quantity 6; native character restored |
| Enter Terrace Entry, then Main Hall 2F | Reveal only entered rooms | Regions `11,12`, then `03,11,12` |
| Enter C-Passage naturally | Add its outline without revealing its locked destinations | `01-04`; regions `03,04,11,12`; five interpreted doors; complete zero-item list, `CLEARED` |
| Interact with two Armor Key doors and the door locked from inside | Native access agrees with the tracker | Native armor-carving messages for targets `01-0d` and `01-05`; inside-lock message for `01-07`; tracker remains locked/locked/blocked respectively |
| Enter Small Library through C-Passage | Add only the Library | `01-06`; regions `03,04,06,11,12`; two interpreted doors; complete zero-item list, `CLEARED` |
| Unlock its door and enter East Stairway 2F | Update access before revealing the next room | Native unlock message, then `01-07`; regions `03,04,06,07,11,12`; four interpreted current-room doors; complete zero-item list, `CLEARED` |
| Load the earlier Terrace checkpoint in the same tracker session | Reread game state and keep session visit history | Current room returns to `01-12`; all six outlines remain; Terrace item stays taken; cached Library door reevaluates from unlocked to unlockable, as detailed in RE1-DOORS-007 |
| Replay four recorded tracker histories | Match complete publications, including destination labels and quantities | All 17 unique captures match exactly; 21 replay steps include four reused history/initial-state captures, which are not counted as new observations |

Room Main/Sub/camera remain u8 at PS1 virtual `0x800C8660`/`0x800C8661`/`0x800C8662`. Each capture verifies the pinned runtime signatures before reading all 2 MiB while paused. Automatic entry captures can catch door animation; native views subsequently showed Jill in the C-Passage, Library and East Stairway. The interpreted zero-item states agree across the captures; this did not independently search every surface or exercise later story spawns. Enemies were present while the tracker reported cleared, consistent with the collectible-only completion definition.

Experiment changes and failures: the first private capture harness stopped after a GDB read timed out at `0x800C3002`; the existing production runner already has reconnection, so subsequent private harnesses copied that behavior. Transitions also temporarily rejected room-script ranges outside PS1 RAM and then recovered. Two initial C-Passage attempts ended in death. Computer use rejected the two-nonmodifier `E+K` aim/fire chord; the isolated copy's R1 binding was temporarily changed from E to Shift, permitting ordinary `Shift+K` combat. Native firing and use of the carried First Aid Spray allowed the later C-Passage route to reach both new rooms. A separate harness attempt incorrectly issued resume while already running and stopped at its assertion; it produced no room-entry evidence beyond Terrace. These are experiment failures, not evidence of a production reconnect or completion bug.

The East Stairway return attempt also ended in death after the entry capture. An attempted inventory hold did not open the status screen; the later diagnostic capture records that death rather than a healthy return. The earlier checkpoint was loaded instead to obtain the distinct state-restoration test. No successful Library return or checkpoint preserving the new unlock is claimed. No guest RAM writes, teleports or injected events were used. The private watcher and browser tab were closed, the isolated app exited without saving over existing states, and its R1 binding was restored to E.

Private evidence under `/tmp/tasks/re-map/multi-area-gameplay/`:

| RAM capture | UTC time, 2026-10-07 | SHA256 |
| --- | --- | --- |
| `h-terrace-restored.bin` | 20:39:30 | `60a1dbad615a2747f513c485ef47224ce4df3b80e5b872db6b6dfeb37fff1038` |
| `h-floor-1.bin` | 20:41:07 | `c3baa2a64b97af0e684519b48460e9ddbef74d8e1c583b66ad2f0c92905f1547` |
| `h-floor-2.bin` | 20:42:40 | `03cf307826ea538cdcb7f5aa0fb390669241f2feff5ef823347976163457ae0b` |
| `h2-floor-1.bin` | 20:47:36 | `c853d98e7519279db9996412d828ee04c57d0d972a0b57c42e6e121258602c6e` |
| `h-cpassage-controlled.bin` | 20:49:04 | `0841acabd5022ed499591a5a51b7377f7baea38ffcabdf44b8a0a2a33f2ae2c6` |
| `h3-terrace-equipped.bin` | 20:54:02 | `0228590ee8aceb0e621fce3481aabe639f8bd3be23ab43f67d0352cfdd66837c` |
| `h4-floor-1.bin` | 20:55:49 | `f9c26583d23643ce713ae7ea6f2dbb5e572053723dc0a6950e9c3c0e3844e82c` |
| `h4-floor-2.bin` | 20:56:31 | `d101a631f5be5cd1e3df4a52356c1f9bef9367c2bf92c8c8bb63dd91cf6ae5f9` |
| `h4-floor-3.bin` | 20:57:13 | `2e692e9e33316ca218f59f320eb21aad21d70efe139d84eb11da9175951cca01` |
| `h-armor-door-message.bin` | 21:00:29 | `bb4e022e5d607bf3313ca0847fd03a2ed071d034b63e89c7334f349e9170de34` |
| `h-armor-room-message.bin` | 21:02:57 | `2f831885182f173b6514e6573ab0a3e70d676674f641afb0c9736025d1228617` |
| `h-opposite-door-message.bin` | 21:06:39 | `ccb5637c16a1c810f67e04350f531f833979643647eb533ac0736ceb482d9aac` |
| `h4-floor-4.bin` | 21:07:45 | `1421edfa3231d3397b36cb53530a254126cdddee053f6383ec5f238d3d4dc19a` |
| `h-library-unlocked-message.bin` | 21:13:10 | `2d41a07ceeeeaa2c1f8ab78a6b6423171f1c2789bba399d144c458987d879537` |
| `h4-floor-5.bin` | 21:14:20 | `206584c3ceff133a5d731bd2d63b14c494a42e49fe2c3721e47890a1ecb8344e` |
| `h-eaststairs-controlled.bin` | 21:15:16 | `87c48a2d9058d75bd7ff4af1f01c6fbc93e10eb6788fd4bd9f979ad1864bd9bd` |
| `h4-floor-6.bin` | 21:17:07 | `f89f40a2a9852e03a0313879dbff9bd3157a9e7a0e90ed1213ca9678072110ee` |

Adjacent JSON files contain full published state and capture metadata. `audit_native_h.py`, SHA256 `1a8b8abb7450c0ff1324abed82908f1e83035140636edcd0b250e8ce738657b2`, verifies identity, hashes, full publication equality, exact visit sets and the unlock/reload assertions. Its `native-h-audit.json`, SHA256 `b2d35ab3757ca5d408eb97e0f3831b4ae2e28cf14d9edc6a7de463520a46feb5`, distinguishes unique captures from replay steps. The final live journal `live-floors-h4.jsonl` has SHA256 `13f01d9bbf86b4fd3653a0abf91da6f93b18f25bdaf5f09c1c3a58b4f29ee08a`; the earlier failure journal `live-floors-h.jsonl` has SHA256 `9bf60af0cfb0532da1968ea2cb5f9735fdf0c5b3d02d8121a24bd0bb3188cc07`. `h-restored-library-map.png`, SHA256 `e98c3cca9f4b02c5d506ba6e1ea482359a58deb47654d8f11286ceb435c39002`, shows the six outlines and restored Library door label. The loaded checkpoint is unchanged, SHA256 `21d29e6a52c093f291e4b5760746de0f07eb53b780fb24275d0cc596dc699936`.

Limits: this extends one Mansion 2F route, not additional floor plans. Nine other floor plans still lack gameplay validation. No return from East Stairway, normal save/load for the new door, later-area transition, alternate character/revision or whole-game playthrough was completed. The isolated control setup and diagnostic deaths are not player-facing tracker features. Research-only changes introduce no production rules or assets.
History:

- 2026-10-07; Codex root, GPT-6.1 Sol; loaded the checkpoint, used ordinary combat and native door interactions, observed three new room entries, loaded the earlier state in the same tracker session, checked rendered labels and replayed all captures exactly. Manually reviewed the documentation and passed `git diff --check`; no Markdown formatter/linter is configured.

## RE1-MAP-012: Laboratory B3 and Courtyard B1 reveal rooms on natural entry

Status: Confirmed for this revision for the named routes and publications; whole-floor and item-rule validation remain incomplete
Scope: SLUS-00551 executable identity in RE1-SAVE-005; Chris Laboratory route from `BASLUS-005511`, Jill Courtyard route from `BASLUS-005512`
Environment: RE1-SAVE-005's isolated DuckStation, production tracker at `055a94d`, native keyboard input, read-only GDB, private browser preview on port 8766; final captures replayed with RE1-SOURCE-003's correction
Authored: 2026-10-08; Codex root; model: GPT-6.1 Sol
Basis: normal checkpoint loads, natural room entries/return, browser floor-plan observation and exact replay of captured map publications
Claim: Laboratory B3 Save → Elevator Entry → O-Room and Courtyard B1 Save → Straight Passage → Black Tiger → Straight Passage select their proper plans and reveal only entered outlines. The Courtyard return retains all three entered outlines.

| Capture | Room | Visible regions | Published item/door result |
| --- | --- | --- | --- |
| `i-floor-1` | `04-0e` | `0E` | Incomplete; Green Herb taken, Blue Herb available, Magnum Rounds available ×6, Ink Ribbon available ×3; exit `04-0c` has no lock |
| `i-floor-2` | `04-0c` | `0C,0E` | Cleared, zero items; five doors have no lock |
| `i-floor-3`, `i-o-room-settled` | `04-05` | `05,0C,0E` | Cleared, zero items; after settling, five resolved doors, including unlocked exits `04-07` and `04-0c` |
| `j-floor-1`, `j-floor-2` | `02-0e` | `0E` | Cleared; Blue Herb, First Aid Spray and Ink Ribbon already taken |
| `j-floor-3`, `j-straight-settled` | `02-0d` | `0D,0E` | Cleared, zero items; after settling, three doors have no lock |
| `j-floor-4`, `j-black-status` | `02-0c` | `0C,0D,0E` | Incomplete; Combat Knife taken, Ink Ribbon available ×2; after settling, two doors have no lock |
| `j-floor-5` | `02-0d` | `0C,0D,0E` | Return retains the Black Tiger outline and remaining-item state |

Each private RAM capture is exactly 2097152 bytes. Times below are UTC on 2026-10-07; the local research date is 2026-10-08. The private audit checks pinned executable signatures, capture hashes and exact equality with the full live map JSON for all eleven captures, using a fresh tracker for each route.

| Capture | UTC time | RAM SHA256 |
| --- | --- | --- |
| `i-floor-1` | 21:53:34 | `c2ffb00bfc745154ddd62b254c1163c32c85a627db13bdee31eb90d2504a0a75` |
| `i-floor-2` | 21:56:31 | `d4624da29768d493b97484236d176e13e91e1cd8582ef85093f9569080b2667d` |
| `i-floor-3` | 21:58:16 | `19c8d059595afd5ffad4fa3e2c7bc2b5e1a2186d29c455cd88710a14e97331de` |
| `i-o-room-settled` | 21:59:02 | `e4c0e541ab798fde62ead595a28ef5fe989ba02bb886406f82b59304959c55d7` |
| `j-floor-1` | 22:06:44 | `ffa461f53b231db8b28686e63f2b80bf6d85bbcbeeadf8a4f1f5b9c86b675d54` |
| `j-floor-2` | 22:07:17 | `76c02b54b4ff6b1295e5c448f4b2fcd7012127adaed346d548afa391c5af07ee` |
| `j-floor-3` | 22:07:48 | `74f72111ccc48693ea48d1913d75895a579186bfd5cd463be221199dd51c0ff8` |
| `j-straight-settled` | 22:08:25 | `03690b828734ed765ab436e1d6e7005e7029f05aa39fde3dfa860e6fad64debf` |
| `j-floor-4` | 22:09:50 | `06795fc00e734b273f3a3bee4d44c8458fc30cc49a33cf73f0cfb461abd91c1f` |
| `j-black-status` | 22:10:31 | `a1b9e26f961f698d5fe3fd91b735cc2f1c0600aeb9d6216d2a189d1b3d25aa50` |
| `j-floor-5` | 22:11:31 | `608d592f0e815ed790ecb8496be33d82a9d818049eeb8a5657eb720b9a3a65f1` |

Original tracker screenshots are `i-lab-initial-map.jpg`, SHA256 `89b8805fc06f0a7781aaa43498aa1528299013555d0fe7350e950e7388faa07a`, and `j-courtyard-return-map.jpg`, SHA256 `5add4114071d2d65c99b5a7e86a4859d0aee97767cd05567d7b2a69df7f4a79b`. The latter shows the three retained outlines and Black Tiger's remaining-item color. Private journals `live-online-i.jsonl` and `live-online-j2.jsonl` have SHA256 `c362a01d981c2935561dbf4ce50a39189c76cfa400c5c54af7c06338f8b6fbb9` and `2ca54372976b92fc9a52b205f4dfcfbd4c4d216b958cfce29763fad5b78d5e21`.

Failure/limits: Chris died to Chimeras while attempting O-Room → Laboratory B2 stairs; no B2 entry was completed. Jill's checkpoint was already poisoned. The candidate little-endian u16 at PS1 virtual `0x800C51AC` fell from 96 through 90, 10, 8 to 2, and native status showed Poison. The return to Straight Passage succeeded, but a subsequent attempt to reach Save ended at the title sequence. No cure, pickup, unlock, normal-save write or successful Save-room return was observed. This value is a navigation/health lead, not a newly confirmed profile field. These routes establish map publication, not independent proof of every displayed item or door rule. Native map-screen comparisons outside the Mansion are still untested.

The alternate Chris Lab load `i-floor-5` at 22:04:22 UTC, SHA256 `5384e2593262d92ce067082c24425123e8d1050124009ae92ce90fba8f3fd643`, displays Green/Blue Herbs and Ink Ribbon available with Magnum Rounds taken. Only its current identity/detail replay is compared, because uncaptured demo rooms had already entered the same tracker history. It adds no new room coverage. RE1-LIFECYCLE-001 records that defect.
History:

- 2026-10-08; Codex root, GPT-6.1 Sol; loaded both checkpoints, observed six rooms with ordinary passage between them, observed the Courtyard return, captured exact publications and browser plans, replayed eleven full states, and recorded the deaths and uncompleted routes without counting them as coverage.

## RE1-MAP-013: Guardhouse and Courtyard switch areas on passage and return

Status: Confirmed for this revision for the named entries and crossing; unresolved Guardhouse coverage remains unfinished work
Scope: SLUS-00551 executable identity in RE1-SAVE-005; Chris from `BASLUS-005510`, rooms `03-03`, `03-00`, `02-04`
Environment: RE1-SAVE-005's isolated DuckStation, production tracker baseline `055a94d` and then RE1-SOURCE-003's one-line correction, native controls, read-only GDB and private browser preview on port 8766
Authored: 2026-10-08; Codex root; model: GPT-6.1 Sol
Basis: normal checkpoint load, reproduced source failure, successful natural area crossing/return, browser observation and exact captured-publication replay
Claim: the Guardhouse Save outline reveals alone after load. With RE1-SOURCE-003 corrected, a fresh tracker in Guardhouse Entry follows the player to Courtyard Gate and back, selects the correct floor plan and retains both observed visits without revealing other rooms.

| Capture | Room/area | Visible regions | Publication |
| --- | --- | --- | --- |
| `l-floor-1` | `03-03`, Guardhouse 1F | `03` | Cleared; Handgun ammo and First Aid Spray taken; exit `03-00` has no lock |
| `m-floor-1` | `03-00`, Guardhouse 1F | `00` | Incomplete; three Blue Herbs available; item conditions and door coverage unresolved |
| `m-floor-2`, `m-gate-settled` | `02-04`, Courtyard 1F | `04` | Cleared; two Green Herbs and two Blue Herbs taken; two exits have no lock |
| `m-floor-3`, `m-return-settled` | `03-00`, Guardhouse 1F | `00` | Return retains Entry and Gate visits; three herbs still available; coverage still unresolved |

| Capture | UTC time, 2026-10-07 | RAM SHA256 |
| --- | --- | --- |
| `l-floor-1` | 22:15:07 | `79af0b648805983cc10f20fdbc4ace5d8ee6359353ae806554ee28155cb5805d` |
| `m-floor-1` | 22:21:05 | `7d5bf038450a2944fb1416f36d7ab790ef41a4cabc067631d623ad21cda5dbb3` |
| `m-floor-2` | 22:22:30 | `90c5a0053f5a787cc292525fdb174ee0ef9373ba8d418bd0fee91519a4d396cd` |
| `m-gate-settled` | 22:23:16 | `5309e7b1301af55a14d060d50338a68417f38662ea2779596bd5610c5de10ae6` |
| `m-floor-3` | 22:23:53 | `17009d72084eb7a3ac9b7f0669745a733bee7c0a72d53c8f536b02ce678a7a38` |
| `m-return-settled` | 22:25:44 | `352aeb93f754fa0b44769765723b0f3a6643c160d4a3c03190a60766750121ed` |

The private audit exactly replays all six full publications, with a fresh tracker for the Save capture and another for the five corrected Entry/Gate captures. The latter final history is exactly `courtyard1f:04` and `guardhouse1f:00`; the current map contains only Entry, while its Gate exit retains `target_visited = true`. At Gate the reciprocal Entry exit already reports visited. Native Chris remained controllable on both sides and on return. The candidate health word in RE1-MAP-012 stayed 53 throughout this crossing.

Private tracker screenshot `m-courtyard-first-map.jpg`, SHA256 `57db5065bd8ff6a047c9dcd57f3bac96fc1c96584dcfcbdeb55f5a1fe7aa8335`, shows only the entered Gate outline on Courtyard 1F. Journals `live-online-l.jsonl` and `live-online-m.jsonl` have SHA256 `26016ca74a7e1a0fc72227affe39588450e236d950dea19d048cddf972833277` and `97edf3bc00bb0cafdfd1a5570307c363d404bb0d95eb34b2fbc0c3dd93c631b6`. The new return checkpoint is recorded in RE1-SAVE-005.

Shared audit evidence for RE1-MAP-012/013 and RE1-SOURCE-003 is private `audit_online.py`, SHA256 `c858eddbdf5ee21878584beef875c647f878de19095fd4b476bb57fc81bb38b9`, and `online-audit.json`, SHA256 `15b325c6cc384432dc9ac954dadb452cc8e6cc904857cc60de7172c4989c4ed0`. It checks seventeen exact full publications, two explicitly limited current-detail comparisons and baseline-versus-corrected source identity. The baseline comparison pins `055a94d` so a later commit cannot change its meaning.

Together, RE1-MAP-012/013 add nine rooms across four floor plans. Scoped live map checks now exist on six of eleven plans, including Mansion 1F/2F. Mansion B1, Guardhouse B1 and Laboratory B1/B2/B4 still lack completed live entry checks. Six of eleven is map-area coverage, not a whole-game readiness percentage. No new item pickup, key use, story condition or normal-save persistence was validated here. Guardhouse Entry's unresolved item conditions and door coverage remain concrete unfinished detection work.
History:

- 2026-10-08; Codex root, GPT-6.1 Sol; loaded Save, reproduced the Entry failure, resumed a fresh tracker after the shared correction, crossed to Gate and back, checked area titles and entry-only outlines, replayed all six full publications and preserved the return checkpoint. The source fix and external code reviews are recorded separately in RE1-SOURCE-003.

## RE1-MAP-014: Guardhouse basement ladder selects its plan and returns

Status: Confirmed for this revision for the named route and exact publications; whole-floor and independent item-rule validation remain incomplete
Scope: SLUS-00551 executable identity in RE1-SAVE-005; Chris from private `m-guardhouse-return.sav`, rooms `03-00`, `03-05`, `03-06`, `03-0d`
Environment: RE1-CHEAT-003's isolated emulator and health lock; production tracker at `dc7a360`, native keyboard input, read-only GDB and private browser preview on port 8766
Authored: 2026-10-08; Codex root; model: GPT-6.1 Sol
Basis: natural doors/ladder passage, native basement movement, browser floor-plan observation and exact replay of eight captured publications
Claim: Entry → Passage → Room 002 → Water Tank Entry → Room 002 automatically selects Guardhouse 1F/B1 on the ladder crossing and return. B1 initially reveals only the entered Water Tank Entry outline, and returning retains all four observed region visits.

Reproduction: restore the private Guardhouse return checkpoint before attaching a fresh tracker. Keep RetroAchievements disabled. Enable the scoped health lock in RE1-CHEAT-003. Walk from Entry through the unlocked Passage door into Room 002. Use its already exposed ladder through the normal interaction prompt, walk away from the ladder in B1, then return and climb back. Do not load a savestate between the entry and return or change position, inventory, story or acquisition flags directly.

| Capture | Room/area | Visible regions | Published result |
| --- | --- | --- | --- |
| `n2-floor-1`, `n2-health-lock-active` | `03-00`, Guardhouse 1F | `00` | Incomplete; three Blue Herbs available; coverage unresolved |
| `n2-floor-2` | `03-05`, Guardhouse 1F | `00,05` | Cleared; three Green Herbs taken; Room 002 exit unlocked |
| `n2-floor-3` | `03-06`, Guardhouse 1F | `00,05,06` | Incomplete; Shotgun shells available ×7 and Map available; three exits have no lock |
| `n2-floor-4`, `n2-basement-settled` | `03-0d`, Guardhouse B1 | `0D` | Cleared; two Green Herbs taken; Room 002 and Water Tank exits have no lock |
| `n2-floor-5`, `n2-return-settled` | `03-06`, Guardhouse 1F | `00,05,06` | Return retains items and visits; the B1 exit now reports its destination visited |

| Capture | UTC time, 2026-10-08 | RAM SHA256 |
| --- | --- | --- |
| `n2-floor-1` | 15:16:17 | `cb20c4175bcc0e45e832ef4d970278e67c44dfd80feb2c15a2c97c47b83d3b0d` |
| `n2-health-lock-active` | 15:20:46 | `9d4041e976f9178cebf471e99bc3018f44fa51031e258fdccbea826df1011260` |
| `n2-floor-2` | 15:22:52 | `207df0c02b66b0e16f18a1adaca979fc750573e7eac59db26e474eaae610b78b` |
| `n2-floor-3` | 15:30:02 | `e023f31b3f60bac001d6a902a3c0affa77d0e6541d3073b81d7bb4b6a319ff2b` |
| `n2-floor-4` | 15:36:10 | `7c1d1f29607cd01253a59ba18090a275265708ed42de0e73b8fa4b121f4d2a2a` |
| `n2-basement-settled` | 15:36:50 | `7616d4df30a799ea801aa8807cfc7448bbcade9813d1c5a6626d458048ae243c` |
| `n2-floor-5` | 15:38:00 | `f2fd960521301b0c5ada2c09ffc802fa2ec04d96800b7e433fdd17161e4d0b83` |
| `n2-return-settled` | 15:38:39 | `1528a3e71f7f3b32b7afd6b6a579b95fe82faac6883c48f46627bc2eaebae6a7` |

Every private RAM capture is 2097152 bytes. `audit_health_route.py`, SHA256 `03d3e5ddf11a03c5837f3187c68761295fbd551dcc05b6be7b9a1f742c865f02`, verifies their hashes, pinned executable signatures, exact live JSON, four region visits, reciprocal ladder visit state and unchanged acquisition bank. Its `health-route-audit.json` has SHA256 `5bf7861d27a86fd34d39254ced01ca5ade35d50e284d33082f1766953ef50e4f`. Journal `live-online-n2.jsonl` has SHA256 `8658cb7ce66293126edc5b4c427f43b5198ea0b3feb8fb760d0a7b3ab8637ad3`.

Private browser image `n2-guardhouse-b1-map.jpg`, SHA256 `256c08e4c5e40f572436067f17476e8073a02c3c6b6fbe2a3bf1fa02a8d20e89`, shows the spatial Water Tank Entry outline alone, its cleared color, two collected herbs and two exits. The native screenshot/movement check showed Chris controllable beside the basement ladder. Private return checkpoint `n2-guardhouse-b1-return.sav` is 1581315 bytes, SHA256 `e15b1c250cdec88bb1abcd417990e931ed9530912eb8a18d68703406772fa6fc`. It contains the health-patched test state and must not be described as an unmodified playthrough save.

This adds three rooms and one new floor plan to RE1-MAP-012/013. Scoped live entry checks now cover seven of eleven floor plans. Mansion B1 and Laboratory B1/B2/B4 remain unvalidated. Seven of eleven describes map-area coverage, not whole-game readiness. Guardhouse Entry's unresolved conditions remain unfinished work. The other Guardhouse B1 rooms, native in-game map comparison, new pickups, unlocks, story changes and normal-save persistence were not tested. A later Laboratory retry did not obtain a valid checkpoint load; no tracker was attached and it adds no coverage.
History:

- 2026-10-08; Codex root, GPT-6.1 Sol; entered three additional rooms through native controls, checked B1 movement and browser geometry, completed the ladder return, replayed eight exact publications and preserved the scoped checkpoint. This continuation changes no production tracking code.

## RE1-MAP-015: Laboratory B2 stairs and B1 ladder select their plans and return

Status: Confirmed for this revision for the named crossings, publications and B1 locked-door observation; whole-floor and independent item-rule validation remain incomplete
Scope: RE1 Director's Cut, NTSC-U, SLUS-00551 executable identity in RE1-SAVE-005; Chris from normal card entry `BASLUS-005513`, then its private B2 checkpoint
Environment: isolated DuckStation 0.1-11894-gc66b2694d, commit `c66b2694da65cece8886ed3d4a069098831f8358`; production tracker at `ab94cc8`, native controller input, RE1-CHEAT-003 health lock, read-only GDB and private browser preview on port 8766; RetroAchievements disabled
Authored: 2026-10-08; Codex root; model: GPT-6.1 Sol
Basis: normal checkpoint load, natural door/stair/ladder crossings, native movement/lock/map observations, browser floor plans and exact captured-publication replay
Claim: the O-Room → Stairway → O-Room crossing selects Laboratory B3/B2 correctly. A separate Stairway → Ladder Room → Laboratory Entry → Ladder Room route selects B2/B1 correctly. Each new floor initially reveals only its entered room, and both returns retain the observed visits. Laboratory Entry's exit `04-01` reports locked when the game refuses passage.

The first route loaded public card entry 4 through the game's Load Game menu before attaching a fresh tracker. Save `04-0e` → Elevator Entry `04-0c` → O-Room `04-05` used ordinary doors. Run along the O-Room's outer corridor to its stairs, enter Stairway `04-03`, move on the landing, then descend normally. The second route restored private `r-laboratory-b2.sav` before attaching another fresh tracker. Walk around the Stairway's enclosed landing and central corridor to Ladder Room `04-02`, climb its ladder to Laboratory Entry `04-00`, check the locked gate, and climb back. No savestate was loaded during either round trip. No position, inventory, acquisition or story flags were written directly.

| Capture | Room/area | Visible regions | Published result |
| --- | --- | --- | --- |
| `r-floor-1` | `04-0e`, Laboratory B3 | `0E` | Incomplete; Green/Blue Herbs and Ink Ribbon ×3 available, Magnum Rounds taken |
| `r-floor-2` | `04-0c`, Laboratory B3 | `0C,0E` | Cleared, zero items; five exits have no lock |
| `r-o-entry` | `04-05`, Laboratory B3 | `05,0C,0E` | Cleared, zero items; five resolved exits |
| `r-floor-3`, `r-b2-settled` | `04-03`, Laboratory B2 | `03` | Incomplete; MODisk and one Green Herb taken, another Green Herb available; three exits have no lock |
| `r-floor-4`, `r-return-settled` | `04-05`, Laboratory B3 | `05,0C,0E` | Return retains all four route visits; Stairway exit now reports destination visited |
| `s-floor-1` | `04-03`, Laboratory B2 | `03` | Fresh tracker after restore; same item/door results as the first route |
| `s-floor-2` | `04-02`, Laboratory B2 | `02,03` | Cleared, zero items; Stairway and Laboratory Entry exits have no lock |
| `s-floor-3`, `s-b1-locked` | `04-00`, Laboratory B1 | `00` | Cleared, zero items; exit `04-01` locked, other two exits have no lock |
| `s-floor-4`, `s-return-settled` | `04-02`, Laboratory B2 | `02,03` | Return retains three route visits; Laboratory Entry exit now reports destination visited |

Native movement changes captured positions from `(19100,16600)` to `(18638,16352)` on the first B2 visit, from `(3500,23100)` to `(3500,21735)` after the B3 return, and from `(5300,11200)` to `(5300,10125)` after the B2 ladder return. These are navigation observations using the existing candidate player-coordinate reads, not new production profile fields. The native B2 map shows the L-shaped Stairway and adjoining rectangular Ladder Room in the same arrangement as the two tracker outlines. This is a qualitative comparison of those entered rooms, not a whole-floor geometry audit.

At the B1 gate, the game displayed "The door is tightly locked." Capture `s-b1-locked` still publishes `04-00 → 04-01` as `LOCKED`, labeled Master Key. The refusal independently checks the locked state; the message does not independently establish the key name. No key use, unlock or post-unlock traversal was tested.

Every private RAM capture is 2097152 bytes. All times below are UTC on 2026-10-08.

| Capture | UTC time | RAM SHA256 |
| --- | --- | --- |
| `r-floor-1` | 16:39:57 | `bcbadaf76be700d1b16c4ece3f7fab0f9a542461cd3e8786d4e43d65476b3dbc` |
| `r-floor-2` | 16:40:34 | `36ce2b395efe333d0357f8f8513cd8b72fec6c2fb88ce84cd084a124dcc57323` |
| `r-o-entry` | 16:47:32 | `cfe69b6fcc435c3fdc53944d0ae36e85f05751c99d77691356368a7c9fd4247b` |
| `r-floor-3` | 16:50:27 | `f28898ad5f5c0cc723d22944034b7fc60fa49ebb69586736c6bbab29d89a5666` |
| `r-b2-settled` | 16:51:30 | `99d80d912482a17f0ff9b34e281f2501a867b6e46c338b42c510fbe814b2544a` |
| `r-floor-4` | 16:53:03 | `50618a4ee4b811ae1bdea62a52e4a16e59e52dbee82a83b5c8796a60625f78d3` |
| `r-return-settled` | 16:54:23 | `b46fc7eae96bba6e6dd5d606e49f4b8eb8dfd82592a12f1b04f0cdab563da508` |
| `s-floor-1` | 16:56:08 | `5df5eb5d485f1c65fe31ead01343e1b82a428a995ea8bd047e241e5a8e1d1ccb` |
| `s-floor-2` | 17:01:22 | `7061a2d2da318952fcacd36a4cbb3af6ca2dd06dff8774a9f51ed3b14fa71041` |
| `s-floor-3` | 17:02:23 | `e6db614ddafba300432ffc829e3e63c5d1667f627b9119a1404a75460a04ee84` |
| `s-b1-locked` | 17:04:09 | `c67409cba2cf5df08cfca840144409418a529ae132e6e97be5f515d097b8395a` |
| `s-floor-4` | 17:05:20 | `864004874a6bac17ef4686b03bc62609157aa376d2a4d7fb7e72cb464219f660` |
| `s-return-settled` | 17:06:21 | `49c5569416ad9a552358f4d34cbec99ff193e881592ed815ee438a0d8bfdaba0` |

The private audits verify capture hashes, pinned executable signatures, exact equality with all thirteen full live map publications, entry-only outlines, retained region visits and reciprocal destination visits. Each route preserves all 32 acquisition bytes at PS1 virtual `0x800C86DC`, RAM offset `0xC86DC`. Both routes read the patched u16 health value 140 throughout.

| Private evidence | SHA256 |
| --- | --- |
| `audit_laboratory_route.py` | `0f65393a4fd85ec093198803e5bb16e849cdb84ffb4a16a10581dd9610aa7380` |
| `laboratory-route-audit.json` | `25f613adb24735d2558015897fae35cdaed8f5617b1fa6224be8378ff87eb297` |
| `audit_laboratory_b1_route.py` | `c7801dd636e546f77181a443bb944ccbd63a18d44a449559a12ead24e07e548e` |
| `laboratory-b1-route-audit.json` | `8fcaff7bc5758c827f342a24db24c07dc5213561d69b4a54a17f8bf880679deb` |
| `live-online-r.jsonl` | `dc8ac15fa1f4f245f9a9086b39ff7eee3e2a18ab855cb52e87d248bb1beb94bc` |
| `live-online-s.jsonl` | `aca687bafe1b22063fa3d884b0b83b510f50eca9153e3f3d8a45a6b4a8cb1be0` |
| `r-lab-b2-map.jpg` | `755468760f6aa90d553b0efd6ea2256a492e29606ce10707e450f5066367d928` |
| `r-lab-b3-return-map.jpg` | `553a5c373f1c13c309ccc61d3272886fec40faf7fcc7d910dcef64b0931ad113` |
| `s-lab-b1-map.jpg` | `c787e1a7ba36b082bf14fafe709cde267d6a69009aa23df3298575218cfcc7de` |
| `s-lab-b2-return-map.jpg` | `44bcb54321d3764caa6afdc44398a4ed90354e9530257b5c0263b9c439825612` |
| `s-native-lab-b2.jpg` | `eb2a9c717f2df9b2de6120bc85c7a64dac9618c802aed61dda9ebd1aa06325f8` |
| `s-native-b1-locked.jpg` | `8843f68312f3b4064f245ffb2ed6bd9e5e343da24d2798ab66614f1ef3b74a7e` |

Private `r-laboratory-b2.sav` is 1473437 bytes, SHA256 `0a81a2ef6bd061621196426165cb847336fd9b48f86bc2c7e402871824058b8e`. Its successful restore and second route were observed. It contains the health-patched test state. Restoring this GDB-paused checkpoint required a read-only GDB resume before the native load completed; do not count this as normal in-game save persistence. The two tracker histories are deliberately separate.

Failed routes/limits: preceding sessions `o`, `p` and `q` from card entry `BASLUS-005511` reached only already checked B3 rooms. Repeated Chimera grabs prevented the stair crossing; holding health at 140 did not prevent stagger. Changing to card entry 4 and sustaining ordinary movement eventually reached B2. Both checkpoints still had Chimeras in O-Room. The B4 elevator attempt from entry 4 displayed "There's no reaction" and did not enter B4. Inactive power is an inference from that message; no power flag or simultaneous blocked-elevator RAM capture was established. None of these failed attempts adds floor coverage. Journals and combat captures remain private under the same evidence directory.

This adds three rooms and two floor plans to the scoped live checks, now nine of eleven plans. Mansion B1 and Laboratory B4 still need completed live entries. Nine of eleven describes map-area coverage, not whole-game readiness. New pickups, story changes, unlock reversals, normal-save persistence and other rooms on these floors remain untested. The isolated emulator was closed, original global settings restored byte-for-byte with SHA256 `c1669f45b60c9cdc8ccce4ec66bc616ddee5b8dff2b46e7d299d1fc148250ea3`, and temporary cheat/per-game settings archived so their originally absent files remain absent. The private preview was closed.
History:

- 2026-10-08; Codex root, GPT-6.1 Sol; completed both native round trips, observed the B1 lock refusal and B2 native map, replayed thirteen full publications, preserved the private checkpoint, recorded failed attempts and restored the temporary setup. This continuation changes no production tracking code.

## RE1-MAP-016: Laboratory power route enters B4 and returns with retained state

Status: Confirmed for this revision for the named route, entry-only outlines and return publications; whole-game readiness remains incomplete
Scope: RE1-PICKUP-006's Jill setup, rooms `04-0e`, `04-0c`, `04-0f`, `04-10`, `04-11`, `04-15`, `04-14`, `04-13`
Environment: isolated DuckStation 0.1-11894-gc66b2694d; production tracker at `631ea2f`, RE1-CHEAT-003 health lock, ordinary controls, read-only GDB and private browser preview on port 8766; RetroAchievements disabled
Authored: 2026-10-08; Codex root; model: GPT-6.1 Sol
Basis: normal card load, native room crossings, pickup/power interactions, native encounter and movement, browser map observations and captured-publication replay
Claim: the Laboratory route reveals Power Maze 1, Power Maze 2 and Power Room as they are entered, then switches to B4 for the elevator and returns to B3 with visits, collected Battery and open elevator retained. B4 reveals Main Lab Entry first and Main Lab only when the native sequence enters it.

Reproduction: load public card entry 5 (`BASLUS-005514`) through the game's Load Game menu with achievements disabled. Attach a fresh tracker after Jill is controllable. Walk Save → Elevator Entry → Power Maze 1 → Power Maze 2 → Power Room. Session `u` stops at a private checkpoint before the Battery. Restore that checkpoint before attaching a separate fresh tracker for session `v`. Take the Battery and use both power panels and the elevator call as recorded in RE1-PICKUP-006/RE1-DOORS-008. Let the native Barry/Wesker sequence enter Main Lab. Defeat the Tyrant through ordinary aim/fire controls, interact with Barry, walk the opened exit corridor, and let the native return sequence use the elevator. No savestate was restored during session `v`'s pickup, power changes or B4 round trip. No position, inventory, acquisition, story or enemy flags were written directly.

| Capture | Room/floor | Visible regions | Observed publication |
| --- | --- | --- | --- |
| `u-floor-1` | `04-0e`, B3 | `0E` | Incomplete; Green/Blue Herbs taken, Flame Rounds ×6 and Ink Ribbon ×3 available |
| `u-floor-2` | `04-0c`, B3 | `0C,0E` | Cleared, zero items; elevator blocked, four other exits open |
| `u-floor-3` | `04-0f`, B3 | `0C,0E,0F` | Power Maze 1 cleared, zero items; both exits open |
| `u-floor-4` | `04-10`, B3 | `0C,0E,0F,10` | Power Maze 2 cleared, zero items; transient incomplete door coverage during entry |
| `u-floor-5` | `04-11`, B3 | `0C,0E,0F,10,11` | Power Room incomplete; Battery available; maze exit open |
| `v-floor-1` | `04-11`, B3 | `11` | Fresh tracker after checkpoint restore; Battery still available |
| `v-floor-6` | `04-15`, B4 | none | Declared unoutlined elevator; B4 selected without revealing its rooms |
| `v-floor-7` | `04-14`, B4 | `14` | Main Lab Entry cleared, zero items; both exits open; Main Lab still hidden |
| `v-mainlab-arrival`, `v-mainlab-settled` | `04-13`, B4 | `13,14` | Main Lab cleared, zero items; exit unavailable, including after the encounter |
| `v-mainlab-after-barry` | `04-13`, B4 | `13,14` | Exit now open, complete door coverage; no active event or registered interaction |
| `v-floor-8` | `04-14`, B4 | `13,14` | Native exit return retains both B4 outlines |
| `v-floor-9`, `v-b3-return-settled` | `04-0c`, B3 | `0C,0F,10,11` | Retained four B3 outlines and taken Battery; elevator open with destination visited |

Main Lab's blocked-to-open exit is an observed consequence of the native encounter and Barry interaction, not a new inferred flag address. The native corpse and subsequent movement establish that the encounter was completed. An initial navigation attempt treated the Barry interaction as a terminal lead; the native conversation contradicted that interpretation. Barry's radio pose continued after player control returned, so its appearance alone did not establish an ongoing cutscene. The final B3 capture has no active event or registered interaction and complete door coverage.

The browser observations show original spatial outlines and wall door markers: B4 initially displays the L-shaped Entry alone, adds the adjoining Main Lab on entry, and B3 restores the four explored outlines on return. Private images and their hashes are listed below. No whole-floor native-map geometry comparison was performed. The elevator has no polygon in the supported map metadata; its room ID and floor selection remain available.

The shared private audit replays all 31 RAM captures across separate `u` and `v` trackers, verifies each 2097152-byte capture's SHA256 and pinned executable signatures, and checks every full live map payload. Fifteen payloads match exactly. All 31 match after sorting only the door array by source/target: continuous live polling populated cached doors in a different order from the sparse replay, with otherwise identical content. The audit preserves both counts; it does not claim byte-for-byte equality for all payloads. It also asserts pickup/power byte changes, blocked refusal, B4 entry-only reveal, main-lab exit change, six retained outlined-region visits in session `v`, and the open/visited B3 elevator. The final capture's complete 32-byte acquisition bank matches `v-battery-after`.

Selected route captures below complement the pickup/power tables above. All times are UTC on 2026-10-08. The private audit lists every capture, hash, room, visible region set and replay result.

| Capture | UTC time | RAM SHA256 |
| --- | --- | --- |
| `u-floor-3` | 17:26:13 | `9cf7884a86705827e119a53e481906b7c7d9b0958e4dea0bfdcb3689d2990281` |
| `u-floor-4` | 17:32:47 | `dcef367365274efd40f47197c9312fc66f6d5ff4afae31ea570cbcada28587d3` |
| `u-floor-5` | 17:34:41 | `c2f9839eb27584897d8b6deabbc8ee5c57ba13871386628cfdfdc35c5a9fcb92` |
| `v-floor-6` | 18:33:33 | `b438db5044b56f0081e5a903a7ad44b450067591e77145942c7c2ae5ab435341` |
| `v-floor-7` | 18:35:14 | `5c4b3211d044e0d14c891aae506d4ae47c819ae633a12bd3d56e11d08abd5636` |
| `v-mainlab-arrival` | 18:48:05 | `3d109ee938564e45115926ab39227575c76dd586f65bd4aa29d91336425bb6b4` |
| `v-mainlab-settled` | 18:51:05 | `55405f5dfa9a43554084565060897a9667899286ce86d78669c03b11ecee4cb3` |
| `v-mainlab-after-barry` | 18:58:26 | `81f47872b7e25ba87f3af2dba1678efe04e323790e430463386726a243018532` |
| `v-floor-8` | 19:02:10 | `35bed9da36b271c6d584ce224fccfa04dd45691c8dec31c2e54937c9f1fe68fe` |
| `v-floor-9` | 19:03:37 | `b835af73ac5ca806a9c785bdf125cb482958405860ef7f4bee9c82a710f37b3b` |
| `v-b3-return-settled` | 19:06:26 | `f61a347bf9b30f99a2567cff4f8153f3fe9fa2ba0e6a938339aae219ad0a9460` |

| Private evidence under `/tmp/tasks/re-map/online-saves` | SHA256 |
| --- | --- |
| `audit_laboratory_power_route.py` | `a5bfda67726296a594fe8f644c5d52c6f489f9fc61c7b6022ccc10c114ff0fd3` |
| `laboratory-power-route-audit.json` | `bcb865e4d3f89c3bffe40d832955736d6cc8cb9ba1af12bad20f8aaa1a844615` |
| `live-online-u.jsonl` | `87d3b9867f47cab3daad6dfe52317a37f12c7265e5947e2c6a2f1e4308e2015f` |
| `live-online-v.jsonl` | `b7819db5d81e9e776febd31ee7f092adcb4c7f27b1f04bde9f1cb6d6c7127820` |
| `v-b4-entry-map.png` | `d6c4f4499969859283b1026065ab5c29255bf7711deaa257c13adc31d4044414` |
| `v-b4-mainlab-map.png` | `dea96b5f47686086e84b458877d80808728a7d13806f65ca47c6f21445d5eb1e` |
| `v-b3-return-map.png` | `52ded19cd46dc307b1fcfc96685eb99189af02872486e161f0a58587377ec9ac` |
| `v-validation-settings.ini` | `eb76d4dbc937d9009c6a63a2e1473a7c464b1c668bb172110135cd4e22b0ab2d` |
| `v-validation-cheats.cht` | `23a323e04c53d54f1880a986afb2430fc96b381a331dea678894dc31730b3bf9` |
| `v-validation-gamesettings.ini` | `f8d225066726e91ba5f11a04970ea5c3034c694b69aa969a350f0447ac16835b` |

Private return checkpoint `v-laboratory-b4-return.sav` is 1661208 bytes, SHA256 `47613e244a80d3886c974bdaa5ff21194534b8bc63f6c8f28e4059805ee639e9`. It was saved through DuckStation's Save To File action, contains the health-patched test state, and has not been restored. It is not evidence of normal in-game save persistence.

Limits and failed setup observations: uppercase `U` sent an added Shift modifier, which was also bound to aim, and did not provide the intended run input. Lowercase controller macro keys resolved that navigation issue. Chimera grabs still interrupted movement with health held at 140; ordinary sustained aim/fire cleared the visible blockers. Entry transitions sometimes produced retry/read-failure publications before recovering to the correct room; `u-floor-4`'s incomplete door coverage also resolved later. These temporary observations were preserved, not counted as independently established parser defects. All captured health words read 140.

This adds Laboratory B4 to completed live entry/return checks: ten of eleven floor plans have scoped live entry coverage. Mansion B1 remains unvalidated. This count measures map-area coverage only. Other room outcomes, unresolved conditions, additional scenarios, normal-save persistence and pickup/power reversals still require gameplay validation before claiming whole-game readiness. The emulator and private preview were closed; global settings were restored byte-for-byte with SHA256 `c1669f45b60c9cdc8ccce4ec66bc616ddee5b8dff2b46e7d299d1fc148250ea3`. Temporary cheat/per-game files were archived and removed, restoring their original absence. The user's normal emulator was untouched.
History:

- 2026-10-08; Codex root, GPT-6.1 Sol; completed the native route, checked entry-only B4 expansion and B3 return, recorded the Battery and power outcomes under separate claim IDs, replayed 31 full publications with the stated ordering normalization, preserved the private checkpoint and restored the isolated setup. No production tracking code changed.

## RE1-MAP-017: Mansion B1 entry, four outlined regions and stairway return

Status: Confirmed for this revision for the named floor transitions, entry-only outlines and retained completion publications; door destinations have the defect recorded in RE1-DOORS-009
Scope: RE1 Director's Cut NTSC-U SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`, Jill Original, public card entry 3 `BASLUS-005512`; Courtyard, returned Mansion and Mansion B1
Environment: isolated DuckStation 0.1-11894-gc66b2694d, production tracker at `fd0294a`, ordinary controls, read-only GDB and private browser preview on port 8766; RetroAchievements disabled; RE1-CHEAT-003 health lock
Authored: 2026-10-09; Codex root; model: GPT-6.1 Sol
Basis: normal card load, native rope/ladder/door/stair interactions, browser observations and captured-publication replay with journal-derived visit history
Claim: native entry reveals only Underground Passage 1 on Mansion B1. Entering Passage 2, Kitchen and the basement landing adds each outline separately. Ascending and descending the Elevator Stairway switches between Mansion 1F and B1 while retaining all four basement outlines and Passage 2's two remaining Green Herbs.

Reproduction: with achievements disabled, load RE1-SAVE-004's public card entry 3 through the game's Load Game menu. Attach a fresh tracker after Jill is controllable. Session `y` follows `02-0e → 02-0d → 02-0c → 02-0b → 02-07 → 02-02 → 02-00 → 05-1b → 05-1a → 05-0a → 05-0b → 06-07 → 06-0b → 06-0c`. Use the native rope prompt, walk the lower Lesson Room passage, then confirm its ladder prompt. The rope's destination remains room `06-0c` but camera 4 selects Mansion 1F region `1F`; it is not yet Mansion B1. The ladder enters `06-1a`. Walk through `06-1b` and `06-1c`, trigger the Kitchen exit's native zombie event, clear the blocker through ordinary shotgun controls and enter `05-10`. Ascend the stairs, descend again and cross back into the Kitchen. Keep the same tracker throughout this route. No save or savestate was loaded during session `y`; no position, inventory, acquisition, story or enemy flags were written directly. The saved setup already has the Lesson Room access and rope available.

| Capture | Room/floor | Visible regions | Observed publication |
| --- | --- | --- | --- |
| `y-floor-12` | `06-07`, Mansion 2F | `07` | Entered East Stairway only |
| `y-floor-13` | `06-0b`, Mansion 2F | `07,0B` | Entry cleared; Green Herb taken; Lesson Room door unlocked |
| `y-floor-14` | `06-0c`, Mansion 2F | `07,0B,0C` | Lesson Room cleared; Radio taken |
| `y-lesson-downstairs` | `06-0c`, Mansion 1F | `0A,0B,1A,1B,1F` | Native rope descent selects the lower passage without revealing B1 |
| `y-floor-15` | `06-1a`, Mansion B1 | `1A` | Passage 1 cleared; Shotgun shells taken; adjacent rooms hidden |
| `y-floor-16` | `06-1b`, Mansion B1 | `1A,1B` | Passage 2 incomplete; two Green Herbs available, quantity 1 each |
| `y-floor-17` | `06-1c`, Mansion B1 | `1A,1B,1C` | Kitchen cleared with zero registered collectibles; stairway exit unavailable |
| `y-kitchen-exit-event` | `06-1c`, Mansion B1 | `1A,1B,1C` | Kitchen exit now open after the native event; destination label is wrong |
| `y-floor-18` | `05-10`, Mansion B1 | `1A,1B,1C,1E` | Basement landing revealed; Tea Room shortcut can unlock from this side |
| `y-stairway-upper` | `05-10`, Mansion 1F | `0A,0B,10,1A,1B,1F` | Native ascent adds the upstairs outline and retains previous 1F exploration |
| `y-basement-return` | `05-10`, Mansion B1 | `1A,1B,1C,1E` | Native descent retains all four basement outlines and both available herbs |
| `y-floor-19`, `y-kitchen-return-settled` | `06-1c`, Mansion B1 | `1A,1B,1C,1E` | Reverse Kitchen crossing and settled control retain the four outlines and item states |

Browser observations show original spatial room outlines and wall door markers. The first B1 screenshot contains only Passage 1. Subsequent screenshots contain all four entered regions, with Passage 2 incomplete and the other three cleared. The entire floor was not revealed at startup or on an in-game map pickup. No whole-floor comparison against the game's native map geometry was performed.

The private audit checks 46 full RAM captures across separate `w`, `x` and `y` trackers. Each capture is 2097152 bytes, passes its SHA256 and pinned executable checks, and reproduces its complete recorded map payload exactly. This replay supplies region visits explicitly observed in each live journal before each capture, including camera-only visits omitted by the sparse RAM capture sequence. It is a replay of RAM plus observed journal history, not a claim that sparse RAM captures alone reconstruct every visit. The audit adds no fabricated RAM or cached item/door state. It checks B1 expansion, the upstairs/downstairs switch, two retained herbs, the unchanged 32-byte acquisition bank across session `y`, and both wrong door targets in RE1-DOORS-009.

The earlier `w` route reached Dining Room through the western Mansion rooms. Its capture process ended on an agent-issued `resume` command while already running; this private-tool assertion is not a production tracker failure. Fresh tracker `x` continued to Tea Room, where the native door refused passage and the tracker reported the basement shortcut locked from the other side. Repeated hunter stagger blocked that approach. Session `y` reloaded the same normal card entry and used the eastern stairs instead. These failed approaches are not additional B1 validation. The initially empty no-TTY `w` startup journal is excluded from the audit.

Selected RAM captures below use UTC on 2026-10-08; the authoring date above uses the user's Europe/Prague date. The private audit lists all 46 captures.

| Capture | UTC time | RAM SHA256 |
| --- | --- | --- |
| `y-floor-15` | 22:23:57 | `60628a9f2d0686d2f449d4c879d17cf7dd5cc42f897d82faf3084e3e5dd08c52` |
| `y-floor-16` | 22:25:44 | `12faee4c1265972e48bbbe715c133b211a27df5b9962c18e3e11eff282f1411a` |
| `y-floor-17` | 22:28:18 | `4f1d6befd0bbc5f79a1d299b09fdad1f092b42d7d7e22052da0ef1c9f893c1ee` |
| `y-kitchen-exit-event` | 22:30:44 | `43b9e8535bde95eb2bd18e1c05627a5a9e97ddd157c371106d127bd5caf9713e` |
| `y-floor-18` | 22:34:01 | `c7d5a94012917779ec3ff216724c82df09e6e6d70ae7ad8931a44b4e671e1366` |
| `y-stairway-upper` | 22:36:43 | `d3b4251ed76ce3e663f90d2fce012ffe2d656c7833f3e853491d6143b2cde0e6` |
| `y-basement-return` | 22:38:17 | `9733bbcd9df16a6fe7a82721a6e4bce5532a7d0c1e392741acd3eceb338c58b2` |
| `y-floor-19` | 22:39:22 | `41c7a2b7ef92696536de2b1bbd17cd94f38219edcb7966ffcfb7a4f9fe1a995b` |
| `y-kitchen-return-settled` | 22:40:39 | `b1e6b3665d29feaf412d85c78cdeb66d1fd1050ecc1c85a347d876c4ded15507` |

| Private evidence under `/tmp/tasks/re-map/online-saves` | SHA256 |
| --- | --- |
| `audit_mansion_basement.py` | `d8ef6e1396d79a7ab2be30d8e64df458685a2c3933b6498f577a67b54ed8e9f1` |
| `mansion-basement-audit.json` | `eee54302f0c6b0b568ea3f957fb7111d2a680d2d6799518363aab8219846ce82` |
| `live-online-w.jsonl` | `29ffc28ea39137e5274c6ffada953c7ea345a8467886e7f7305ce7cb6438d704` |
| `live-online-x.jsonl` | `80de587b094bbaee41c1495789594ac3986bbe047750f527938f20bbec768fff` |
| `live-online-y.jsonl` | `a98e42a622ee7ecd814142e972c6f86a4478fd23d5115aff2ad7949152a2bda5` |
| `y-basement-first.png` | `b9073a146c5414cb80421ec05cd477094c5b3e5029a215a6c57e5ab131f849c2` |
| `y-basement-four-rooms.png`, `y-basement-return-map.png` | `fb956f215dc1b5b69d48d178fa78881fb54678ddee8f48d140e2422d752cd553` |
| `y-stairway-upper-map.png` | `4b0beb1da22318ca084d780f8f6917164bd23916dfd260a5a7e23eae2e4d7b55` |
| `w-y-validation-settings.ini` | `695a30486f7067dec92c1f340162562f44189290f283264fbb41d161fb92a0f9` |
| `w-y-validation-cheats.cht` | `23a323e04c53d54f1880a986afb2430fc96b381a331dea678894dc31730b3bf9` |
| `w-y-validation-gamesettings.ini` | `f8d225066726e91ba5f11a04970ea5c3034c694b69aa969a350f0447ac16835b` |
| `w-y-cleanup-audit.json` | `72bb9cd42a5fded30cac8df7ea5dfd639285f02a637a3dc7db3b8227b1c9090c` |

Private checkpoints saved through DuckStation's Save To File action are `y-mansion-approach.sav`, 1575313 bytes, SHA256 `4e2a639362dcff7fff634f6c9251bd2c36c353a8d2660035159f99b4b9a0bab1`, and `y-basement-return.sav`, 1647218 bytes, SHA256 `0a2fbf70c5b8953fce6ae45bba12eab3ea65c2692e9be46b64da8d5e42a9bd8a`. Both contain the health-patched validation state and have not been restored. They are not evidence of normal-save persistence.

Mansion B1 completes scoped live entry checks for all eleven supported floor plans. This measures map-area entry coverage, not whole-game readiness. Wrong door destinations, other unresolved outcomes, normal-save persistence, earlier-load reversals and additional scenarios remain. The Kitchen's empty registered item list is an observed publication for this save, not a general proof of every Kitchen scenario. No new pickups or shortcut unlocks were tested. Transitions sometimes produced retry/read-failure publications before recovering. All captured health words read 140; the patch does not prevent poison poses, grabs or stagger.

The private emulator and browser preview were closed. Global settings were restored byte-for-byte to SHA256 `c1669f45b60c9cdc8ccce4ec66bc616ddee5b8dff2b46e7d299d1fc148250ea3`, and temporary cheat/per-game files were archived then removed. Original card `SCEVMC1.mcd` retains SHA256 `21bc80edfdcbdae68d2341256930413306997a3c46765ae9e20b8009b125db7a`. Working card `w-working-card.mcd` has SHA256 `478262def290e9c37bd6bcb7e6a2e75f94f394783e826715c36bee4bddac8a8e`; all fifteen save blocks at offsets `8192..131071` are byte-identical to the original. The user's normal emulator was untouched.
History:

- 2026-10-09; Codex root, GPT-6.1 Sol; ran the native B1 route and stairway return, recorded four entered outlines and retained herbs, audited 46 publications with actual journal history, preserved two private checkpoints and restored the isolated setup. No production tracking code changed.
