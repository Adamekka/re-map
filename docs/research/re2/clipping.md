# RE2 clipping effects

[Documentation index](../../README.md) · [Claim index](../../research.md) · [RE2 testing](../../testing/re2.md)

## RE2-CLIP-001: startup clipping preserves the fixed item context

Status: Candidate for Resident Evil 2 Dual Shock Ver. USA Disc 1, SLUS-00748, Leon A, Original/Normal. Owned-source inspection, complete copied native consumers, a controlled native entry and an exact native savestate restore support this bounded rule. They do not establish other revisions, ordinary access through the locked entrance, pickup lifecycles or campaign readiness.

The human reported unresolved explored rooms. The preceding baseline, `4bfbced`, leaves source `01-0e` without a fixed-context proof because opcode `0x73` at source offset 6012 is unsupported. As a result, two opposite-context pickup declarations remain unresolved and a conflicting item identity stays generic after departure. This entry supersedes that particular clipping limit in the earlier [unresolved-room investigation](dualshock.md#re2-door-006-alternate-door-creators-share-one-detail-row). Its other rejected approaches and room limits remain unchanged.

### Identity and resulting item outcomes

The owned executable is `SLUS_007.48`, 987136 bytes, SHA256 `e576348f64d015ecff6e1ce875a8924ee252ba7f3f9478b0917cbbdeb97db441`. The target source is `PL0/RDT/ROOM20E0.RDT`, SHA256 `94f38aa44a170d207c7625a41e24c595da82af57ad46f9fad7383600a0e92a0e`. Native inspection below refers to that executable's PS1 virtual instruction addresses. Source offsets are file-byte offsets, not virtual addresses.

The private emulator is official DuckStation `0.1-12083-g00e299795`, full commit `00e2997958d62de79d352cd680ec0c1ad95d491c`, executable SHA256 `5c879677051cfb173002df22baee741c96fa8071c6fe1dd7e5454092bf128173`. Its console log independently reports this version. Older research retains its own version claims and limits; a profile field does not establish which emulator originally produced a user savestate.

Owned-CUE generation with the new opt-in changes only three source fields, all in `01-0e`:

| Field | Before | After |
| --- | --- | --- |
| Fixed context | unresolved | preserved |
| Opposite-context acquisition IDs | unresolved | 61 and 171 excluded |
| Conflicting ID 56 identity | generic after departure | type 60, creators 6534 and 6560, quantity one |

No additional item-presence proof is generated. The two excluded handgun-ammunition rows disappear. The four real items remain available in the accepted current-room captures. Departed unresolved items remain Unknown, even though their full identity list is now established. The room stays Incomplete when a real item is known to remain, and Unknown where independent presence is unresolved. No collection or full-room clearance is inferred.

Eight accepted capture replays compare the same private visits before and after the change. Every other explored source, door, pose, map selection, visit and polling status stays identical. The opted-in and baseline floor documents are byte-identical, SHA256 `ed0d180d7cec62245194b35d43e4c61aae3cd621031935d9b469b137de5369ec`. Baseline regeneration without the opt-in reproduces the preceding production room catalog exactly. These are source and interpretation outcomes, not new pickups or source-coverage counts.

### Native inputs and write contract

All addresses in this table are PS1 virtual, little endian. Full-width masks apply unless a narrower mask is listed. Private copied execution converts virtual addresses to RAM offsets with `address & 0x1FFFFF`.

| Field | Address | Width, mask and observed value |
| --- | --- | --- |
| System flags | `0x800CFB74` | unsigned four bytes; required mode mask/value `0x40` |
| Status flags | `0x800CFBD8` | unsigned four bytes; opcode OR mask `0x00010000`, separate from enforced scenario mask `0xC2000000` |
| Clipping selector | `0x800CFB7D` | unsigned byte, `0xFF`; zero |
| Plane coordinate | `0x800CFB7E` | signed two bytes, `0xFFFF`; -19800 |
| First range operand | `0x800CFB82` | signed two bytes, `0xFFFF`; -25000 |
| Second range operand | `0x800CFB80` | signed two bytes, `0xFFFF`; -19000 |
| Loaded-source pointer | `0x800CE324` | unsigned four bytes, `0xFFFFFFFF`; `0x8011A65C` |
| Camera and counter 26 | `0x800D4820` | unsigned two bytes, `0xFFFF`; three for the active entry |
| Native counter base | `0x800D47EC` | two-byte indexed values; counter 26 aliases the camera field |
| Story flag bank 4, bit 69 | word `0x800D485C` | unsigned four bytes; mask `0x04000000`; clear in the accepted setup |
| Player actor | `0x800CFBF8` | unsigned four-byte flags; active mask one |
| Player X / Z | `0x800CFC30` / `0x800CFC38` | signed four bytes, `0xFFFFFFFF`; -17300 / -13000 |
| Player heading | `0x800CFC6E` | signed two bytes, `0xFFFF`; -2048 in the accepted entry |
| Part count | actor plus `0x107`, `0x800CFCFF` | unsigned byte, `0xFF`; sixteen after weapon attachment |
| Source parts pointer | actor plus `0x198`, `0x800CFD90` | unsigned four bytes, `0xFFFFFFFF`; `0x801D857C` |
| Scratch parts pointer | actor plus `0x1A4`, `0x800CFD9C` | unsigned four bytes, `0xFFFFFFFF`; `0x8016C130` |
| Extra player-part workspace | `0x800D8CE8` | unsigned four-byte pointer; `0x8016CB44` |
| Free-work pointer | `0x800CE32C` | unsigned four-byte pointer; `0x80180464` |

The source packet is `73 00 A8 B2 58 9E C8 B5`. The complete handler, `0x80058EF8..0x80058F78`, sets the status bit, writes the selector and three halfwords in the order above, advances task PC by eight and returns. The contiguous parameter bytes in active RAM are `00 A8 B2 C8 B5 58 9E`, reflecting the two halfwords' destination order. Thirty copied synchronous cases cover status-word seeds and selector operands, including unsupported selectors as diagnostic inputs. They check every store and the PC advance. Production admits only selectors zero, one and two.

The flag proof compares actual little-endian byte lanes. Status-mask and parameter aliases cannot silently change a fixed predicate through a different bank number. The deferred geometry contract is limited to the revision's system/status context words; a new fixed predicate in actor, matrix or heap state does not inherit this proof.

### Startup and allocation lifetime

The complete 125-source owned Leon corpus contains one decoded `0x73`, in synchronous procedure `17:0` at offset 6012. The preceding `16:0` contains two door declarations and termination. The relevant `17:0` prefix contains a camera comparison, flag writes and another flag predicate. It has no prior model creation, scheduled task, call or yield. Its branch requires camera three and story flag 4/69 clear.

Native room initialization at `0x80053528` schedules procedures `16:0` and `17:0`, executes them through `0x800536C4`, runs `0x80053244`, and calls the clipping construction phase at `0x80053620`. The latter enters `0x800532D8`, tests status mask `0x10000`, detaches the weapon count through `0x80041060`, and calls `0x8002E2D8` at `0x80053348`. That allocator's store at `0x8002E318` records its workspace argument in actor plus `0x1A4`.

The shared guard enforces this startup placement. It rejects event/frame procedures, potential model creation, scheduling, calls and yields before the clipping command, unsupported startup loop/backjump forms, and script references that could reenter `17:0` later. Reverse control-flow analysis keeps branches that cannot reach the clipping command separate from its possible predecessors. Callback geometry must agree with the declared payload shape. These restrictions apply generically, without room or item names.

The owned resources supply concrete constructor bounds:

- Native `0x80028324` derives part count from the model header's unsigned four-byte object count divided by two, stores the unsigned byte and reserves `count * 0xAC` part-record bytes.
- The six embedded TMD models in the target source have object count two, one part each. Their native source offsets are `0x1F38`, `0x242C`, `0x2A98`, `0x2B84`, `0x2D68` and `0x33C4`.
- The complete owned `PL0/PLD` census contains 111 player/weapon resources. Body counts are 15, 16, 19 or 20; weapon counts are 1, 2, 3 or 13. Every count is positive. The allocator reserves twenty additional player-part records before its copied model data. The active Leon body has fifteen parts and its attached weapon adds one.
- The separate 55-header `CDEMD0.EMS` scan is retained as a resource lead. Its resource-ID mapping is not established by that scan and is unnecessary to the accepted player allocation observation.

The accepted native image has these exact intervals:

| Allocation | PS1 interval, end exclusive |
| --- | --- |
| Fifteen body records | `0x8016C130..0x8016CB44` |
| Twenty reserved weapon records | `0x8016CB44..0x8016D8B4` |
| Sixteen live body/weapon records | `0x8016C130..0x8016CBF0` |
| Copied body TMD data begins | `0x8016D8B4` |
| Observed weapon TMD data begins | `0x80179C58` |
| Final free-work pointer | `0x80180464` |

The copy at `0x8002E788` and part filter at `0x8002EC70` consume the same unsigned count and `0xAC` stride. The code assumes legitimate initialized game models. It does not validate arbitrary actor pointers/counts or claim exhaustive engine memory safety. Static object structures can have zero actor-part counts while not belonging to this initialized part-copy path; their active flag alone is not an eligibility proof.

### Controlled native observations and restore

The root agent prepares an isolated portable emulator on GDB port 2347, verifies both achievement integrations disabled before loading, uses None/None memory cards, mutes audio and verifies a black display at BIOS before RE2 loading. Per-game overrides are absent. Test histories are separate; the user's released history lock is not reacquired. No health or ammunition aid is enabled. Assisted player placement is recorded in `pose-writes.jsonl`: the final source `01-0c` preparation sets X/Z to -27200/-18700 and heading 2048, then uses the real door interaction. It also updates the engine's signed two-byte position mirrors at `0x800CFC3C`, `0x800CFC40`, `0x800CFC42`, `0x800CFC46`, `0x800CFD10` and `0x800CFD12`, all mask `0xFFFF`.

1. Restore the private source `01-0c` checkpoint and enter `01-0e` through its open slot-three door. The native destination camera is zero. Capture `clip-entry.ram`, SHA256 `c7b71242a77d7a4635a5227e04c4c6ab7a7c2d712c7b16ceb6d5c3ac955c1f14`. Status mask `0x10000` and the parameters remain clear. This is the inactive baseline.
2. An initial camera-only preparation yields `clip-active-entry.ram`, SHA256 `319c7c76896759c9038f790c3b1da71046acbaf48f7ec942d89672b33f26490a`. The status bit and parameters are set, but Z remains -25600 and the scratch pointer is zero. Copied execution of the actual eligibility helper, `0x8002EA40`, returns zero. This incomplete entry geometry is excluded as active scratch-lifetime validation.
3. Prepare the complete equivalent destination using the other owned door in the same source. Copy its destination Z, packet offset 18, and camera, packet offset 24, into the open door's loaded descriptor. The two descriptor writes are two bytes at `0x8011C278`, `00 9C` to `38 CD`, and one byte at `0x8011C27E`, zero to three. They do not unlock the other door or change acquisition, key or story flags. This is controlled entry preparation, not ordinary locked-door passage.
4. Perform native passage. The corrected image, `clip-full-corrected-entry.ram`, SHA256 `1fafe8cd8fc474e59610652bed3647277e3f5bf791ca6c5f77e963a9fb34f8da`, has camera three, X/Z -17300/-13000, status mask `0x10000` set, the parameter bytes above, sixteen live parts and the bounded nonzero scratch allocation. The actual eligibility helper now returns one in copied execution. The accepted evidence is the settled image's allocation, not a claim that every constructor instruction was traced live.
5. Save a native F2 checkpoint, `clip-full-checkpoint.sav`. Its independently extracted complete 2 MiB RAM and the actual F1-restored capture both have SHA256 `49910c524bf563d0d7e4b2c6ba9c8f8506fb7bb05d44e3e9018ff76991efcbcf`. Allocation and corrected item publications survive restoration. This is DuckStation savestate validation, not normal memory-card persistence.

The primary copied tests execute all 255 positive unsigned-byte part counts through `0x8002E788`. Every store and changed RAM byte stays inside `count * 0xAC` destination bytes. Thirty-six filter cases cover selectors zero/one/two, representative actual counts and enabled/disabled part masks, with stores confined to scratch and stack. Finally, copied consumers run over the actual corrected native image. Eligibility returns one with no writes; the copy makes 1472 bounded stores and changes zero bytes because those copied fields already match; the filter makes six stack stores and changes eight stack bytes. Source records and fixed system/status words remain unchanged.

An earlier attempt to reconstruct startup from a settled, weapon-attached RAM image does not return cleanly. It remains explicitly excluded in `native-73-owned-scratch.json`; it establishes neither a successful constructor run nor an engine defect. The accepted allocation observation comes from the controlled native entry above.

### Reproduction artifacts, checks and review

Private owned bytes and experiments stay under `/tmp/re-map-unresolved-20261028/`. Relevant files are `native-73-immediate.py/json`, `native-73-owned-models.json`, `native-73-all-owned-models.json`, `native-73-command-locations.json`, `native-73-part-copy.py/json`, `native-73-part-filter.py/json`, `native-73-full-entry-allocation.json` and `native-73-real-allocation-consumers.py/json`. No raw RAM, model, disc or BIOS file is added to Git.

Native preparation and captures are under `/tmp/re-map-loop-20261028/`; `clip-full-entry-setup.json` records both exact descriptor writes. `clipping-comparison/metadata-comparison.json`, `runtime-comparison.json` and `replay.py` preserve the before/after catalog and equal-history publication checks. Regenerate the opted-in catalog with the owned CUE using `tools/build_re2_metadata.py`; the profile's `scenario_clipping` contract is mandatory when declared and must match the generated catalog exactly. Absent declarations produce the explicit Unaudited state. Malformed declarations fail startup.

The dedicated clipping suite passes 133 cases. The selected RE2 metadata/profile/tracking/reachability/lifetime/resource suite passes 1252 tests. Root's final complete Python suite passes 3020 tests. Scoped Ruff formatting, E4/E7/E9/F checks with the established E402 exclusion, and whitespace checks pass. These checks cover strict configuration/catalog binding, unsupported revisions/defaults, selector and fixed-word aliases, source placement, late callbacks, model-before-effect paths and source exclusion/identity outcomes. A headless render from the exact restored native checkpoint verifies four remaining item rows, no spurious ammo or unresolved item rows, no overflow or browser errors, and refreshes the README screenshot.

Primary review checks the full bounded contract, affected generator/profile/reader callers, constructor order, resource counts, source/heap separation, callback reentry, partial native stores, equal-history replay and honest completion limits. The configured Claude and Antigravity providers are disabled, so the requested Claude Opus and Gemini Flash perspectives are unavailable. No substitute provider or CLI fallback is used. Their absence is not an endorsement. The clipping increment changes interpretation and item rows; it introduces no layout or control changes.

Remaining limits include native acquisition and reversal of these real pickups, departed presence, ordinary locked-door access, other clipping selectors at runtime, other revisions and memory-card persistence. The proof does not clear other reported gray rooms or replace their independent uncertainty.

Contributions, 2026-10-28:

- Human user: supplied the unresolved-map screenshots and requested continued fix, verification and commit work; subsequently requested release of the production history.
- Codex root, exact executing model `gpt-6.1-sol`, verified by the current T3 runtime metadata: prepared emulator isolation, performed native passages and the two-field destination preparation, captured allocation, created/restored the native checkpoint and verified complete RAM equality. Root independently reviewed the final contract and affected callers, checked native event-entry operand selection, ran the complete suite and rendered the native publication for the README screenshot.
- Codex `door_diagnosis`, exact executing model `gpt-6.1-sol`, inherited from that verified runtime without a model override: inspected owned native code/resources, executed copied consumers, implemented the shared guard and profile/catalog wiring, generated and compared metadata, replayed captures, added regressions, performed primary review and authored this record. Earlier research authorship and conclusions retain their original scope.
