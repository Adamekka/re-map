# RE2 shared item slots

[Claim index](../../research.md) · [RE2 testing](../../testing/re2.md) · [Room completion](../../room-completion.md)

## RE2-COLLECT-023: impossible item alternatives no longer block required pickups

2026-10-29. Status: Candidate shared source contract for Resident Evil 2 Dual Shock Ver. USA Disc 1, SLUS-00748, Leon A, and USA Disc 2, SLUS-00756, Claire B, Original/Normal. Native Leon ID 34 observations below verify its selected pickup, current/departed results, controlled reentry and four exact restores. A second native pass verifies Leon ID 69 collection and two exact current-state restores, with departure/reentry still unverified. The three Claire outcomes retain source-only validation. Source proofs and replay admission do not establish campaign readiness.

### Failure and bounded correction

At baseline `d53f04c`, the explored Leon source `01-03` has a complete item list and a successful whole-source fixed-context proof. Its ammunition remains Unknown after departure even though the same proof excludes the alternate acquisition ID 36. The raw catalog correctly retains both identities because the reader must detect a live descriptor that contradicts the scenario proof. Collection presence nevertheless uses that complete raw item set to decide whether a registry slot has conflicting identities. The impossible alternate therefore blocks the real pickup before the existing startup-presence walker runs.

The correction omits proven-unreachable item creator offsets only from that initial slot-identity conflict comparison. It reuses the existing source/context result introduced for generic interactions in [RE2-LIFETIME-001](creator-lifetime.md#re2-lifetime-001-unreachable-generic-creators-preserve-pickup-presence). It does not delete raw item declarations, change `scenario_item_candidates`, filter reset or door definitions, or grant presence by itself. The existing startup walker must still establish sufficient presence for each eligible acquisition identity.

`collection_presence` requires an explicit `frozenset` of unreachable offsets, asserts that nonempty exclusions accompany fixed flags, requires the whole-source context result before accepting those flags, and asserts that every excluded offset belongs to a decoded item, interaction, door or reset creator. A failed context proof supplies no exclusions. Reachable alternatives, mutable predicates, direct or aliased fixed-bit writers, and existing door/reset conflicts still withhold the item proof. No opcode, native write domain, polling address or historical-mode assumption is added.

The existing reader continues to reread acquisition and context flags. A clear collection bit can now leave a source-established item Uncollected after departure; a fresh set bit still produces Taken. A live forbidden creator still produces Retry rather than being hidden. Earlier game states must reverse acquisition without discarding exploration. These remain the shared [collection rules](../../room-completion.md).

### Pinned revisions and source evidence

The owned executables are `SLUS_007.48`, SHA256 `e576348f64d015ecff6e1ce875a8924ee252ba7f3f9478b0917cbbdeb97db441`, and `SLUS_007.56`, SHA256 `1664e7c634f8cfd03e421f10a6d7e8e8e9fa9bc7982f7c649cc86d28a983fbee`. Their independent runtime layouts and earlier emulator observations remain in [RE2-DS-001/002](dualshock.md). Retained images keep their original version and assistance provenance; this source/replay pass starts no emulator and establishes no newly tested DuckStation version.

The following are RDT file identities. Offsets in this record are zero-based source-file bytes, not PS1 or host-process addresses.

| Revision | Owned source | Bytes | SHA256 |
| --- | --- | ---: | --- |
| SLUS-00748 | `PL0/RDT/ROOM2030.RDT` | 121804 | `4a6311f34cb1288ddf25b46123bbc2cbf938e746e358dbeb6d29da6385b189bc` |
| SLUS-00748 | `PL0/RDT/ROOM2090.RDT` | 78944 | `852fcf2c2f26551d5903f2e74190190b9a91a6d3b2793a1cd5aa1d7f376cb982` |
| SLUS-00756 | `PL1/RDT/ROOM10F1.RDT` | 197496 | `e77c70eb661cb0b348b4a9ac631cac48293f5d3426019f13c575f34313f1a001` |
| SLUS-00756 | `PL1/RDT/ROOM2031.RDT` | 156632 | `becaf2894b449917b8f96eb9b9fed57bff11a3fc356d256a6f0472e18fa3e301` |
| SLUS-00756 | `PL1/RDT/ROOM2091.RDT` | 89708 | `de60ed8f31005a4ccaf3a4357b430f28163f2d89689d31ca2ea504db4d105055` |

| Revision / source | Required item | Creator offsets / slot | Conflicting acquisition already excluded |
| --- | --- | --- | --- |
| Leon `01-03` | ID 34, type 20, Handgun ammo, amount 15 | `2000/2064`, slot 1 | ID 36 at `2152` |
| Leon `01-09` | ID 69, type 68, Film A, amount 1 | `3330/3824`, slot 2 | ID 70 at `3356/3850` |
| Claire `00-0f` | ID 157, type 20, Handgun ammo, amount 30 | `1848`, slot 5 | ID 39 at `1784` |
| Claire `01-03` | ID 39, type 47, Lighter, amount 1 | `2064`, slot 5 | ID 188 at `2000` |
| Claire `01-09` | ID 70, type 69, Film B, amount 1 | `3364/3834`, slot 2 | ID 69 at `3338/3808` |

In Leon `01-03`, the fixed check at 1988 requires bank 1 bit 1 clear. The nested mode check at 1996 selects creator 2064 in the supported context; offsets 2000 and 2152 are already in the proof's unreachable set. A direct call to the existing `source_presence` walker for the two ammunition creators returns Required before this fix. The defect is the earlier identity-conflict rejection. Source `01-09` has the same conflict with the other character's film. Its slot-5 callback invokes procedure 3, which dispatches item slot 2 at 4174. This correction establishes required collection presence, not current interaction availability or completion of that callback.

All acquisition fields below are existing PS1 virtual addresses, unsigned four-byte little-endian words. The mask selects the collection bit; set means collected. They are not RAM-file offsets or host-process pointers.

| Revision / acquisition | Word address | Mask |
| --- | --- | --- |
| Leon ID 34 | `0x800D48C0` | `0x20000000` |
| Leon ID 69 | `0x800D48C4` | `0x04000000` |
| Claire ID 157 | `0x800D4884` | `0x00000004` |
| Claire ID 39 | `0x800D4878` | `0x01000000` |
| Claire ID 70 | `0x800D487C` | `0x02000000` |

### Exact compilation differences and rejected wider change

The private Leon comparison decodes all 125 owned sources and reproduces baseline scenario and presence metadata exactly before applying the prototype. Twenty-nine sources pass the existing fixed-context proof. The narrow correction adds only `conditional_item_presence` records with `presence.kind = required` for `01-03` ID 34 and `01-09` ID 69. Full owned-CUE regeneration confirms those two changes, plus the claim reference. Existing declarations, quantities, unconditional collection IDs, exclusions, other presence rules and floor-plan bytes remain unchanged. These are offline compilation results, not newly observed room coverage.

For Claire, root runs the current full owned-CUE generator twice, changing only `collection_presence` to the function from `d53f04c` for the baseline run. The isolated difference is exactly three required conditional-presence records: `00-0f` ID 157, `01-03` ID 39 and `01-09` ID 70. Only those records and this claim reference are applied to the tracked Claire catalog. Both generated floor artifacts remain byte-identical to the tracked floor data.

The complete current Claire regeneration also exposes older catalog drift. It adds per-room `scenario_context_conditions`, actor-proof header data and older RE2-LIFETIME-001 / RE2-DS-005 references, and changes presence records for `01-02` ID 115, `00-15` ID 101 and `04-02` ID 21. Those differences also occur with the baseline collection function. They are therefore separate from this fix and are not shipped here. Original-release media are unavailable for regeneration; their tracked catalogs remain untouched, and native behavior is not generalized to those revisions.

A private wider prototype removes unreachable creators from the entire presence-eligible item map. It yields the same two Leon reader outcomes but also moves `00-15` ID 101 from `collection_item_ids` to an equivalent required conditional record. That reclassification adds no resolved item outcome. The narrower ambiguity-only correction is selected to retain the existing unconditional and reset-identity policies.

### Reproduction, replay and regressions

Private evidence is under `/tmp/re-map-source0103-20261029._9_igou4/`. `prototype.py` pins the baseline function, profile and catalog to `d53f04c` through `git show`; `all-source-comparison.json` records both prototype differences. `replay.py` creates private baseline/modified profiles from that same pinned catalog. `reader-replay.json` records file checksums and complete-map comparisons. `baseline-control.py/json/log` records the expected pre-fix regression failures. Owned RDTs, executable bytes, raw RAM and game saves remain outside Git.

The replay uses copied visits from the user's existing 31-region publication, without opening or writing the user's history. Fifty unique retained RAM images yield 35 Display and 15 Retry results. Both prototypes produce identical complete map publications. Every Display changes departed `01-03` ammunition from Unknown to Uncollected, quantity 15, and removes its now-unneeded unresolved-condition reason. Root's strict complete-map comparison permits exactly those changes in every published room copy. Independently required Ink Ribbon and Crank states, the Incomplete room verdict, all quantities, other rooms, doors, geometry and visits agree. The 35 results share one target-room outcome; they are not 35 independent target situations. The set includes earlier controlled and excluded preparations, so reader Display admission is not new native acceptance evidence. No retained current-room image for either Leon target exists in the two inspected evidence directories.

Owned-CUE output and the baseline Claire harness are under `/tmp/re-map-presence023-metadata-20261029.Zxk6Ps/`. `baseline-claire.py` substitutes only the pinned old collection function in the current generator. Compare its `baseline_rooms_slus00756.json` with `rooms_slus00756.json` to isolate the three fix-related fields, then compare against the tracked baseline separately to expose the older drift.

Run `python3 -m pytest -q tests/test_re2_metadata.py`. At the source-regression stage, all 492 metadata tests pass. Ten new RE2-COLLECT-023 cases cover impossible alternatives with different IDs/types, a reachable conflicting creator, mutable conditions, direct and aliased fixed-bit writers, and both reachable and proven-unreachable door/reset conflicts. Raw item declarations remain intact. The pinned pre-fix control fails exactly the two positive cases while all eight negative controls pass. Scoped Ruff formatting, lint with the established E402 exclusion, and whitespace checks pass for that test contribution. Aggregate checks and new native validation are not claimed by these results.

### Native Leon ID 34 lifecycle

Root uses isolated official DuckStation `0.1-12083-g00e299795`, full commit `00e2997958d62de79d352cd680ec0c1ad95d491c`, executable SHA256 `5c879677051cfb173002df22baee741c96fa8071c6fe1dd7e5454092bf128173`. Both achievement integrations are verified disabled before every boot. Cards are None/None, audio is muted, the black shader stays enabled and test history is private. The seed reports cheat taint and retains equipped type-two amount 99. No new health, ammunition, story, key or acquisition patch is added. CPU mode is not established by this run.

The first controlled entry copies the twelve authentic destination bytes from owned `ROOM2040.RDT` creator 6430 into an open source `01-0c` door. Its incoming model remains unchanged. Subsequent reentries copy that same authentic destination into the open source `01-04` slot-zero door, keeping incoming model nine. The actual named-key return door remains locked, with bit five clear and no matching key in the seed inventory. These are controlled equivalent reentries, not ordinary passage through that lock. Both departures use the unmodified source `01-03` slot-zero door. `preparation-writes.jsonl` records three twelve-byte destination copies and seven preparations of the nine established X/Z/yaw fields, with Y retained at zero. No ordinary walking route or named-key unlock is claimed.

The loaded-source pointer word at PS1 virtual `0x800CE324` contains `0x8011A65C`. Slot one's registry pointer word at `0x800CE55C` contains `0x8011AE6E`, binding creator 2064. Both fields are unsigned four-byte little-endian values, mask `0xFFFFFFFF`. The item is Available, amount 15, with ID 34's acquisition clear. Ordinary uncollected departure publishes Uncollected, amount 15. Controlled reentry recovers Available.

An initial preparation at X/Z `-18963/-26090`, yaw zero, clamps Z to `-25417` and awards nothing. Facing yaw 1024 from `-18963/-25417` opens the ordinary pickup prompt. Separate native Cross presses confirm and acknowledge it. The prompt's incoherent section layout returns Retry; after acknowledgement the item becomes Taken. The acquisition word changes from `0x40000040` to `0x60000040`, differing only by ID 34's `0x20000000` mask. In little-endian RAM the changed byte is word base plus three. Inventory slot three at PS1 virtual `0x800D4A48` changes from `14 1E 00 00` to `14 2D 00 00`: type 20 remains, and its unsigned byte amount at +1 increases from 30 to 45. The type/amount masks are `0xFF`. Other checked inventory cells and acquisition-bank bits stay unchanged. `audit-award.py` verifies the complete word, bank and inventory ranges; it retains an initial rejected byte-position expectation separately.

Taken survives ordinary departure and controlled reentry. Ink Ribbon and Crank remain independently uncollected, so the room stays Incomplete throughout; no full-room clearance is claimed. Four actual native F2 checkpoints match their preceding complete two-MiB captures. Their native payloads are restored with `StartPaused=true` and `-statefile`, and all RAM bytes and complete maps match independently extracted references under retained history. Earlier current/departed states recover Available/Uncollected and inventory amount 30; later states recover Taken and amount 45. This is paused-startup savestate restoration, not F1 or normal memory-card persistence.

| Checkpoint | Current source | Target | Complete RAM SHA256 |
| --- | --- | --- | --- |
| Before current | `01-03` | Available | `11894283eaf30a7dcf1c4988e6fabc0f4a5639f6bc733aead174867a1f2beb52` |
| Before departed | `01-04` | Uncollected | `5cb7e0a2c428936c64cc9822a8e2e1fc5b80fa53977c46eb75fb9117c42006e1` |
| After current | `01-03` | Taken | `a0acf9f132558843de4f3df96bd548b2e893e5f12fc1e54780c15299d5a1d5e7` |
| After departed | `01-04` | Taken | `a53926e72e3db19f28f776b8780d1ddbe2bbab7ce68b6898231d49e3e17aba09` |

Private evidence and reproducible scripts are under `/tmp/re-map-presence023-20261029.RqztaS/`. `native-award.json`, `cold-restore-validation.json`, `history-validation.json` and `cleanup.json` separate the award, four restores, fifteen file replays representing seven distinct RAM images, and cleanup. `audit-history.py` closes/reopens production visits-only history for every accepted file and reconstructs equal complete publications with exactly three sources and three regions. Its first comparator omitted the expected unresolved-reason removal and rejected that difference; the final comparator permits it only when the complete target list has no Unknown item. The owned process and port close, and all six original settings/actual global and per-game slot files restore byte for byte. The user's game, application settings and history are untouched.

### Native Leon ID 69 follow-up, 2026-10-29

This evidence-only follow-up uses production commit `aa8f05a`, the same pinned DuckStation executable, owned seed, black shader and isolation checks as the ID 34 pass. Both achievement integrations are disabled before every boot. Cards remain None/None and the private visits-only history contains two sources and two regions. The seed retains its inherited health assistance and equipped type-two amount 99 cheat taint. No new health, ammunition, item, enemy, story, key or acquisition patch is added.

Initial entry copies twelve authentic destination bytes from owned `ROOM2020.RDT` creator 7098 into the seed's open `01-0c` slot-zero door. Its SHA256 is `31a5b1206bfa71d28ae92a15bebb86f90d046e62474a5c7be1cc64d74cadc323`. The destination bytes are `68a70000b898000c01090000`. The original incoming model remains unchanged, so this is controlled equivalent entry rather than ordinary source `01-02` ingress. Two early transition polls return Retry and are excluded before the complete accepted capture.

In the accepted source `01-09`, the loaded-source pointer word at PS1 virtual `0x800CE324` is `0x8011A65C`. Slot two's pointer word at `0x800CE560` is `0x8011B54E`, binding creator 3824. Both are unsigned four-byte little-endian values with mask `0xFFFFFFFF`. ID 69 is Available, amount one. Its zero-area descriptor is separate from the slot-five interaction and procedure-three callback described above. This observation does not add a general zero-area interaction rule or change the catalog's empty dispatch-relation list.

Native interaction from X/Z `-23517/-22500`, yaw 3072, opens the pickup prompt. Separate Cross presses confirm and acknowledge it. During the prompt the source-section coherence check returns Retry; after acknowledgement it returns Display with ID 69 Taken. The acquisition word changes from `0x00000800` to `0x04000800`, exactly mask `0x04000000`. The complete bank-eight range at PS1 virtual `0x800D48BC`, 32 unsigned bytes, differs only at the target bit. Excluded ID 70 and independent ID 71 remain clear. Other banks can change through native preparation and combat, so a target-only change across all game flags is not claimed.

Inventory slot six at PS1 virtual `0x800D4A54` changes from `00 00 00 00` to `44 01 00 00`. Its unsigned byte type is 68 and its unsigned byte amount at +1 is one, each with mask `0xFF`. Other cells in the checked 64-byte inventory window at `0x800D4A3C` stay unchanged. The independent seven-round pickup remains Available, so the room stays Incomplete. No full-room clearance is observed.

The two actual native F2 saves exactly match their preceding complete two-MiB captures. Each retained compressed native payload is then booted with a black one-pixel thumbnail and `StartPaused=true`. Every RAM byte and the complete map publication agree with its extracted reference under retained private history. The earlier restore recovers Available and an empty slot six; the later restore recovers Taken and `44 01 00 00`. This verifies paused-startup current-state reversal, not F1 or memory-card persistence.

| Checkpoint | Current source | Target | Complete RAM SHA256 |
| --- | --- | --- | --- |
| Before current | `01-09` | Available | `72a192cff67376ae4b95b6e9801448e64ec3933e9e3a2d231661f82d4ce4d192` |
| After current | `01-09` | Taken | `5220caf3983321d6ca7b245b647abdb5df5fc796e79afd83fb4f3519cc09763d` |

#### Unsuccessful navigation and bounded replay

Enemy contact interrupts the attempted departures. Temporary native input macros hold R1 and repeat Cross, using [DuckStation's pinned binding implementation](https://github.com/stenzek/duckstation/blob/00e2997958d62de79d352cd680ec0c1ad95d491c/src/util/input_manager.cpp#L1908-L2042). Root sends both toggles again before pickup checks and removes the macros before later boots; this pass does not establish a held-pad-word contract. The complete native pickup is independently established by its acquisition bit and inventory award; the combat attempt does not establish that all actors were defeated. Source `01-09`'s one-sided slot-seven interaction sets the observed unlock boolean for ID 131 at PS1 virtual `0x800D4A34`, unsigned four-byte little-endian, mask `0x10000000`. Subsequent passage still fails. One intended departure capture rejects its wrong source with an assertion before writing a RAM file. Synchronous delayed resume attempts also fail to establish passage. Two later polls reach Non-gameplay and record no visits. These attempts supply no departure, reentry, ordinary route or general control-state contract. The planned four checkpoints are explicitly reduced to the two successful current checkpoints.

`preparation-writes.jsonl` contains one twelve-byte authentic destination copy and eleven preparations of the same nine X/Z/yaw fields used by the preceding pass, 99 pose writes in total. No Y, floor, control word, actor, inventory or game flag is directly changed. All raw captures, owned bytes and saves remain private under `/tmp/re-map-presence069-20261029.6DYmpL/`.

`audit.py/json` checks the whole collection bank, inventory window, native creator binding, write whitelist, two restores and cleanup. Nine capture/checkpoint file replays represent five distinct RAM images. Each reconstructs the same complete publication after private visits-only history close/reopen. `baseline-replay.py/json` pins the pre-fix catalog from `d53f04c`: the four distinct current-room publications agree exactly, while replaying the earlier seed with retained test exploration changes only off-screen ID 69 from Unknown to Uncollected and removes its derived unresolved reason. That seed replay is offline earlier-state reconstruction, not a successful native departure or an additional cold restore.

The owned process and port close, and all six original settings and actual global/per-game slot files restore byte for byte. The user's history is untouched. This follow-up changes no production code, catalog, renderer or README image. All 836 focused metadata, tracking and visit-history tests pass, as do 446 local documentation links/anchors and whitespace checks. Direct review checks source binding, award isolation, exact restore equality, visits-only reconstruction and failed-attempt limits. External review providers remain disabled; no additional independent review is claimed.

### Final integration checks

All 3816 Python tests pass. The 45 added cases comprise the ten source regressions, current/missing/departed bindings and fresh acquisition/reversal for all five new DualShock records, live forbidden-creator contradictions, and the existing exclusion matrix extended to ID 36. Complete lists may clear only after all relevant flags are set in these synthetic contracts; this does not establish native clearance for the unobserved items.

The standard RE2 browser suite passes, and desktop `1280x1060`/mobile `390x844` rendering from existing user exploration verifies the corrected Remaining row, removal of that room's incomplete-check entry, independent items, unchanged Incomplete verdict and reveal, and no overflow/page errors. The README screenshot is refreshed from that existing publication. Scoped Ruff checks, formatting and whitespace checks pass. Root directly reviews source/context gating, raw-catalog retention, unchanged reset/door conservatism, reader contradictions, acquisition freshness, scoped regeneration, native evidence and UI results. Configured external Claude/Antigravity review providers remain disabled; no external review or endorsement is claimed.

### Contributions

- 2026-10-29; human user; requested continued RE2 experience improvements and delegated routine feature selection.
- 2026-10-29; `startup_experience` agent, exact executing model `gpt-6.1-sol` from the inherited authoritative T3 runtime; diagnosed the shared-slot rejection, compared the two bounded prototypes across all Leon sources, replayed retained images against copied exploration, added the ten source regressions and their pinned baseline control, and authored this record. This contribution includes source experiments and writing, not emulator gameplay or an independent code review.
- 2026-10-29; root, exact executing model `gpt-6.1-sol` from the authoritative T3 runtime; selected and integrated the narrow ambiguity filter, added the generator claim reference, regenerated the two Leon records, isolated the three Claire records from pre-existing regeneration drift, and preserved the floor artifacts and original-release catalogs. Repeated the pinned source/replay recipes, strengthened full-publication comparisons, implemented the reader regressions, performed the hidden native lifecycle and four exact restores, audited history/cleanup, checked rendering and completed direct review and this record. Earlier research authorship and confirmation limits remain unchanged.
- 2026-10-29; `corridor_replay` agent, exact executing model `gpt-6.1-sol` from the inherited authoritative T3 runtime; prepared the private setup/session/checkpoint/restore/cleanup harness and source geometry, verified preflight backups and compiled scripts, and identified the locked ordinary return path. The agent performed no emulator boot, input or gameplay for this increment.

- 2026-10-29; root, exact executing model `gpt-6.1-sol` from authoritative T3 runtime metadata; performed the hidden ID 69 collection, two exact current-state restores, failed navigation attempts, pinned baseline replay, history/write/cleanup audits and direct evidence review. Authored the bounded follow-up without changing production behavior. The `corridor_replay` agent, exact inherited model `gpt-6.1-sol`, prepared this second private harness and source/door analysis without booting the emulator or supplying native input.
