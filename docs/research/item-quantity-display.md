# Item quantity display

[Claim index](../research.md) · [Room completion rules](../room-completion.md)

The shared renderer restricts `×N` to revision-bound item types whose pickup amount counts ordinary units. Raw quantities remain intact, including explicit unreconstructed values. Weapon resources and key-use counters do not become object multipliers. A source amount retained after collection or departure describes the pickup award or initial contents, not the player's current inventory resources or remaining key uses.

These findings are Candidate source contracts and finite copied-code experiments. They add no gameplay confirmation or natural key-use sequence. Production formatting and its regression checks are separate from confirmation of gameplay semantics.

## RE1-QUANTITY-003: pickup amounts need explicit multiplier eligibility

Scope: Resident Evil Director's Cut, USA, SLUS-00551, supported Jill profile. Owned executable `SLUS_005.51` is 651264 bytes, SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`. Status: Candidate, exact native source inspection without emulator access or new gameplay.

The positive count set is `[11,12,13,14,16,17,18,47]`, hexadecimal `0x0B,0x0C,0x0D,0x0E,0x10,0x11,0x12,0x2F`. These are ammunition stacks and Ink Ribbon. Other types have no multiplier eligibility. This is a display policy, not an item-presence, acquisition or room-clearance rule.

The ordinary award routine `0x8002CD30..0x8002D00C` reads type at source+8 and quantity at source+9. Its stack admission at `0x8002CE70..0x8002CE90` accepts `0x0B..0x12` and `0x2F`; `0x8002CED0..0x8002CF08` adds matching amounts with a 250-unit stack limit. The source quantity remains separate from acquisition, as recorded in [RE1-QUANTITY-002](re1/collectibles.md#re1-quantity-002-transfer-writes-preserve-item-identity-and-collection-is-independent-of-amount).

Fuel type `0x0F` is excluded despite entering that stack branch. The native property table gives both Fuel and Flame Thrower `0x06` capacity 240. Their combination records select reload callbacks `0x80057594..0x80057620` and `0x80057624..0x800576B0`, which transfer resource amounts into the weapon and retain excess in the refill slot. That amount does not count separate fuel objects. This inspection does not establish a percentage unit.

Weapon types `0x02..0x0A` likewise hold weapon resources. The amount renderer `0x8005436C..0x80054628` uses the same numeric format for weapons, ammunition and Ribbon, so numeric presentation alone cannot establish object counts. Its weapon path masks the amount with `0x7F`, except type `0x06`; this rendering mask must not alter the recorded raw quantity. The use path `0x80034450..0x800344C4` decrements a slot's amount while retaining its type, with explicit last-use handling for keys `0x33..0x3C`. Small Key `0x3D` has capacity one and no combination records; it is outside the native stack and number-display classes audited here.

Native instruction and data addresses here are PS1 virtual addresses, not host-process addresses. Source/file offsets are labeled separately. Source quantities and types are unsigned one-byte fields, mask `0xFF`. The inventory pointer at `0x800BA008` is unsigned four-byte little-endian, mask `0xFFFFFFFF`; each two-byte inventory slot has type at +0 and amount at +1. The property table at `0x8008E18C` uses four-byte records indexed by type minus one, with unsigned byte capacity at +0 and combination index at +2. Pointer tables `0x8008E0CC` and `0x80091DA8` use unsigned four-byte little-endian entries, mask `0xFFFFFFFF`.

The offline room metadata contains multi-use key operands and loaded weapon operands greater than one, alongside ordinary ammunition and Ribbon stacks. It does not prove scenario availability, natural collection or inventory consumption. No conclusion here extends to another RE1 executable or to every item obtainable by Jill.

## RE2-QUANTITY-002: resource and key-use amounts are not object counts

Scope: independently inspected USA Dual Shock Leon A and Claire B executables. Status: Candidate source inspection and copied native execution, without emulator access or new gameplay confirmation. The original USA release profiles remain unverified for this policy.

| Profile | Executable SHA256 | Count types |
| --- | --- | --- |
| Dual Shock Leon A, SLUS-00748 | `e576348f64d015ecff6e1ce875a8924ee252ba7f3f9478b0917cbbdeb97db441` | `[20,21,22,24,25,26,29,30,31]` |
| Dual Shock Claire B, SLUS-00756 | `1664e7c634f8cfd03e421f10a6d7e8e8e9fa9bc7982f7c649cc86d28a983fbee` | `[20,21,22,24,25,26,29,30,31]` |
| Original Leon A, SLUS-00421 | Expected only: `1cd618bc4390db4bd60735b0db1e91534f6134ede56fae454eb580be2aa686ef` | Explicit `[]`, native bytes unavailable |
| Original Claire B, SLUS-00592 | Expected only: `2800c21f6a468cf030af75703b952062d8dc98c20753c8f8735558764f2f6814` | Explicit `[]`, native bytes unavailable |

Both inspected Dual Shock executables are 987136 bytes. Each independently supplies the native stack test `unsigned(type - 20) < 12`, its ItemInfo table and its amount renderer. The classification admits only that stack range with ItemInfo byte-two bit `0x80` clear and low seven bits unequal to four. It yields ammunition types 20, 21, 22, 24, 25, 26 and 29, Ink Ribbon 30 and Small Key 31. Fuel 23 and special ammunition 27/28 carry the extra-glyph flag and remain excluded. The meaning of that extra glyph is not established here; no percentage or universal rounds unit is assigned.

| Exact-revision native reference | SLUS-00748 | SLUS-00756 |
| --- | --- | --- |
| Stack admission test | `0x80071F34` | `0x80071EEC` |
| ItemInfo table, eight-byte records indexed by type | `0x800A9E1C` | `0x800A9DD8` |
| Native table setup before renderer call | `0x80072CB4` | `0x80072C6C` |
| Amount renderer | `0x8007300C` | `0x80072FC4` |

The quantity at ordinary creator+16 or four-point creator+24 is an unsigned two-byte little-endian field, mask `0xFFFF`. Event-award packet+2 is an unsigned byte, mask `0xFF`. These creator/packet offsets are byte offsets within source instructions. ItemInfo capacity at +0 and display flags at +2 are unsigned bytes, mask `0xFF`; the renderer tests `(flags & 0x7F) == 4` to suppress the numeric overlay and separately uses mask `0x80` for its extra-glyph format.

Copied execution for exact SLUS-00748 runs the complete inventory writer `0x8006947C`, keyed-door callback `0x80051718` and equipped-weapon resource consumer `0x8006A0CC`. Inventory entries start at `0x800D4A3C`, stride four; type is an unsigned byte at +0 and amount an unsigned byte at +1, both mask `0xFF`.

The writer retains the passed Shotgun amount five and Spade Key amount two in one slot each. The key callback reduces types 89/90 from two to one and type 92 from three to two while retaining the same key type. These are remaining-use counters in one key, not multiple keys. ItemInfo suppresses amounts for all suit-key types 89 through 92; the copied callback cases do not include type 91. Small Key 31 belongs to the stack class and must not inherit a rule based on its name containing "Key".

The complete weapon consumer reduces Handgun 18 to 17, Magnum eight to seven and Shotgun five to four without replacing the weapon. Special-resource cases have different rates. A rejected harness expectation assumed one unit per eighth continuous-resource invocation; the complete handler actually reduces 100 to 98 for the tested types 15/16/18, including its shared tail. The corrected experiment retains that rejected expectation in its evidence. No current inventory counter should be inferred from a tracker record's retained pickup amount.

Each Dual Shock renderer's hidden-amount path was also executed with flags four. Its output region stays unchanged. These finite copied executions validate the inspected paths, not natural pickup, inventory UI or save/load behavior.

For the original releases, the bounded owned-file search found no corresponding executable/disc and the fixture check found only RE2 observation JSON with historical hashes, not native RAM/code/table bytes. Their configured hashes are expected identities and were not recomputed. An explicit empty set with preserved raw amounts records the missing unit evidence. It does not assert that those games lack countable pickups, and no Dual Shock set is copied into either original profile.

## Reproduction and evidence

The private environment uses Python 3.14.10, Capstone 5.0.9 and Unicorn 2.1.4. No DuckStation version or patch configuration applies to these offline experiments. Extract owned executables to a private directory with `tools/extract_psx_file.py CUE IMAGE_PATH OUTPUT`, verify the exact hashes above, then use PS-X EXE header load address and file offset `0x800 + virtual_address - load_address` for each inspected window. Extracted executables, native excerpts and raw captures stay outside Git.

RE1 evidence is under `/tmp/re-map-re1-quantity-units-20261029.ovcjooxf/`. Run `investigate.py` with the private Python environment to recheck the executable identity, native properties/combination records, excerpts and offline source metadata. Its `report.json` SHA256 is `c166ee2d40c1eae8ed74e66bc40a46e881f21dc3b1009d0dbb9518fca8ce79fc`; the script SHA256 is `d53bf4ce5c9b86cc80347500dad9446da13cf376878f2dbacba063b7db16adaf`.

RE2 evidence is under `/tmp/re-map-item-amount-20261029.flm67tx_/`. Run `investigate.py` for the finite SLUS-00748 consumers, `count_policy.py` for each available owned revision's stack/table/renderer audit, and `original_availability.py` for the bounded original-release fixture check. The scripts record their local owned-file inputs; restore those inputs or adjust their private paths before rerunning. Original-release verification needs actual native bytes with independently established revision identity and patch provenance.

| RE2 evidence report | SHA256 |
| --- | --- |
| `report.json` | `1f526499617750e76d6c7466d11934dec3dd6c7b55125c3d431b0c88487b06c9` |
| `count-policy.json` | `c318bb3c47938ee7a449b5e4aaa24c65bdb099922051a450b7cb1e543cf6395f` |
| `original-availability.json` | `85ba57e288a6249e61685f456c17fe320eb0e174d913a5d5a821210669f21019` |

## Contributions

- 2026-10-29, Codex `re1_quantity_units`, exact model `gpt-6.1-sol`: read-only RE1 executable inspection, private reproduction script/report, and this combined documentation increment. This writing independently rechecked both owned Dual Shock executable hashes and their count-table slices against the RE2 reports. It performed no RE2 copied execution or gameplay.
- 2026-10-29, Codex `mode_provenance`, exact model `gpt-6.1-sol` recorded in the evidence reports: authored the separate RE2 native-consumer investigation, both Dual Shock count-policy audits and original-release availability check. These are source/copied-code experiments, not gameplay or a review endorsement.
- 2026-10-29, Root, exact model `gpt-6.1-sol` verified by T3 runtime metadata: reruns the RE1 audit and both Dual Shock policy audits, integrates mandatory profile/model units through all three production item constructors and the shared JSON/renderer, and verifies formatting separately from item outcomes. The original-release sets stay explicitly empty. Integration checks and review limits are recorded in [RE2 testing](../testing/re2.md#item-quantities-and-named-unresolved-checks).

Earlier quantity-transfer and gameplay findings retain their original authorship and limits in the linked game research. This documentation increment includes no external review and does not promote either claim to Confirmed.
