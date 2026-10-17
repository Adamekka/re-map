# Puzzle item collection evidence

[Documentation index](../../README.md) · [Claim index](../../research.md)

## RE1-CLEAR-004: source proofs recognize overwritten dormant item records

Status: Superseded by [RE1-CLEAR-005](#re1-clear-005-known-puzzle-rewards-remain-until-collected) for implementation and completion policy. The native registry observation remains Candidate for the pinned revision.

This section preserves the 2026-10-17 uncommitted registry-proof prototype, its experiments and reviews before the user clarified collection behavior. That prototype was removed; its implementation descriptions, test counts and availability-based verdicts below are historical, not the current tracker behavior. No new natural gameplay validation was performed.

Scope: Resident Evil Director's Cut, NTSC-U, SLUS-00551, Jill. Disc revision is pinned by `SLUS_005.51` SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`. Initial Mansion 2F Pillar Passage is runtime `01-0d`; Armor Room is `01-05`. The installed DuckStation application's metadata reads `0.1-12083-g00e299795`. This contribution did not launch or control an emulator and does not establish new runtime compatibility beyond successful offline extraction and profile identity checks.

Authored: 2026-10-17; Codex root, exact model `gpt-6.1-sol`. The user supplied the screenshots and played the reported room visits. Agent work was diagnosis, source inspection, synthetic implementation checks and documentation. No agent gameplay visits, live emulator memory writes, patches or user-history changes were made.

### Report and cause

The user's Pillar Passage publications showed two Green Herbs, then one taken, then both taken. Item coverage remained unresolved. Armor Room was cleared while current in the recorded publication, then unknown after departure. Frozen publications remain privately under `/tmp/re-map-pillar-passage/`. These are different failures; a gray outline alone does not establish an available collectible.

The owned `PSX/STAGE2/ROOM20D1.RDT`, SHA256 `30f065b94cbc524936456976d2d460932ad479f18cf672e521acc2b91620505f`, creates slot 2 at file offset 167812 with item type 11, amount 15, GlobalId 40, mode 129 and parameter 1. The immediately following extended setter at 167838 sets its handler, mode and three registry words to zero. Its source pointer survives. RE1-SCD-017 records the pinned extended-setter contract at PS1 virtual `0x80045BC4..0x80045C38`.

The former observer required dormant records' copied fields to equal the original initializer. It therefore discarded this legitimate dormant descriptor. A preliminary mode-only correction was rejected after checking the actual packet: parameter and registry ID also change. The final correction retains such records as candidates until the shared source evaluator proves their full registry state. It does not remove the stale-pointer checks.

### Shared proof

The existing source interpreter retains possible descriptor histories. A binding is emitted only for a bounded, covered current-room evaluation where every possible history retains the same item creator operands. A possible absent creator, generic interaction, different item identity, unsupported history, unresolved item meaning or unresolved mutable identity prevents proof. In particular, an uncollected dormant forced award still needs its event progress resolved. Known extended-setter parameters supply the three u16 registry words; the source command supplies the current handler and mode. Quantity-only uncertainty retains its separate existing treatment.

The observer still checks the loaded script span, initializer opcode, slot, source item identity, acquisition state and snapshot coherence. A changed dormant record becomes an explicit candidate carrying its creator offset, item type, source GlobalId, handler, mode and all three registry words. Every matching verified source must contain that exact binding before current-room validation can use it. Unaccepted candidates cannot resolve uncertain item slots. Selected pending awards retain their existing descriptor path, and candidate acquisition state is checked against the fresh poll flags before publication.

Addresses remain those of the pinned profile. The AOT table is PS1 virtual `0x800B8160`, RAM offset `0xB8160`, with 12-byte records encoded little-endian as `<BBHHHI>`. The handler and mode are u8 at offsets 0/1, followed by three u16 words at 2/4/6 and a u32 source pointer at 8. All bits participate in registry matching. The word at 6 is copied from the item GlobalId by an initializer but can be overwritten by an extended setter; it is not always the acquisition identity. Acquisition continues to use the validated source descriptor.

### Reproduction and results

1. Copy the user's save and backup to private scratch storage and extract each with `tools/extract_sav_ram.py`. Do not load them into the running emulator. Both copies passed the pinned runtime identity checks offline. The copied save SHA256 values were `4c403c35398fbd0899768900828fa0e7848814dd4ee63310cd7b2f5606180464` and `3f8a34f4736997c84baf7780be9375603dd13f150793841dedca6333fb3c137c`.
2. Read the fresh flags and reconstruct visited `01-05` and `01-0d`. Both remained unknown before and after this change. Pillar Passage's unresolved slot is 2; Armor Room's is 9. This is unchanged departed-room behavior, not a clearance fix.
3. Extract and verify the owned Pillar Passage RDT. In a private RAM copy, install it at PS1 virtual `0x80100000`, relocate the script header and indexed pointers according to the manifest, register its two doors, and register slot 2 with the actual extended setter's all-zero registry fields and retained item pointer. Use the copied save's flags, where both Herb bits are clear. This is a synthetic initialized room, not a captured gameplay state.
4. The real source matcher accepts the installed bytes. The observer retains one dormant ammo candidate. The source evaluator still reports slot 2's availability alternatives, but supplies the exact dormant registry binding. Current-room validation resolves that slot and the full poll reports `CLEARED`, complete item coverage and complete doors. Discarding the candidate reproduces the former unresolved result.
5. `tests/test_dormant_items.py` compiles fully synthetic sources and binds their actual bytes through the real poll. It checks dormant/available/taken reversal, different registry fields, a possibly skipped creator, conflicting item identities, pending and forced awards, and a load between candidate and flag reads. Existing inactive-pointer and source-coherence regressions remain applicable.

The private source probe is `/tmp/re-map-pillar-passage/source_probe.py`; its synthetic publication SHA256 is `e9402f41cc0768afa0edc71c453048d9ffde89e14fa63bdebef9eada395016de`. Extracted disc bytes, copied saves and raw RAM remain outside Git. The frozen initial Pillar publication SHA256 is `b751dcd7a4193ed2128a82f57ae22bb1e4f271c8f9bac81447489593ec010519`; the current Armor publication is `7da6f7d26a312a494ba587a723b4265a029dcc8ddeb4b8c1c1482170b0c01aac`; the later departed-room publication is `0c6853a62c04ab696524087877d248dfa77ce4d927eff774dc66839bd7bde45d`.

### Remaining limits

Armor Room's departed source evaluation retains the Sun Crest with both dormant and available handlers. In the copied save its source GlobalId 36 is still set and bank 0/index 58 is false. Pillar Passage's departed evaluation likewise retains dormant and available ammo alternatives. These alternatives are not resolved by the new current-room registry proof. Retaining an old cleared color across changed story state or earlier loads would hide uncertainty, so no cached-clear shortcut was added.

The relevant saved flags are u8 reads in PS1 virtual address space, with the profile's MSB-first index selection. Byte order does not alter a one-byte read.

| Flag | PS1 virtual address | RAM offset | Mask | Copied value under mask |
| --- | --- | --- | --- | --- |
| Armor puzzle, bank 0/index 58 | `0x800C8704` | `0xC8704` | `0x20` | clear |
| Sun Crest, ordinary GlobalId 36 | `0x800C86E3` | `0xC86E3` | `0x08` | set |
| Pillar ammo, ordinary GlobalId 40 | `0x800C86E2` | `0xC86E2` | `0x80` | set |
| Pillar Herb, ordinary GlobalId 197 | `0x800C86F7` | `0xC86F7` | `0x04` | clear |
| Pillar Herb, ordinary GlobalId 198 | `0x800C86F7` | `0xC86F7` | `0x02` | clear |

Suppressing camera-change local-state forgetting in a private comparison did not resolve either departed room. That experiment was rejected and no such interpreter change was retained. No natural Pillar reentry, puzzle activation, Sun Crest pickup, returned-Mansion variant, earlier/later user savestate load or normal card save/load was performed by this contribution. The fix must remain Candidate until independent natural observations validate it.

### Review and validation ledger

The preliminary mode-only review was abandoned with that implementation. Its Gemini call was stopped before a response and is not a review of the final correction. Claude Opus 4.6 Thinking returned quota exhaustion, reset reported as `1h24m29s`, conversation `7afe6dec-508c-48e4-b691-6669396d2a7c`. It supplied no review and was not retried or counted as an endorsement. The final change remains uncommitted because the required Opus perspective was unavailable.

Gemini 3.8 Flash High reviewed the full observer/candidate types, shared binding proof, current-room validation, poll acquisition checks, source matching and nine synthetic regressions. Conversation `dee56a17-aefe-4317-9b80-14d284bc7074` completed successfully in 340.14 seconds with an `agent_response` reaching `DONE`, terminal `SUCCESS`, nonblank `No findings.` response and empty stderr. No tool attempts occurred. The supplied prompt SHA256 is `96049e0a3760cb0ca6a8f13d3cc5c067285876f08acbc1b01aa60656f58c1ca0`; its private streams are under `/tmp/re-map-pillar-passage/review-v2/`.

During root's final inspection, the proof was additionally restricted to exclude unresolved item meanings, including dormant uncollected forced awards. A tenth regression checks that case through acquisition and reversal. This last guard was checked by root and tests, after the Gemini snapshot was supplied; it was not part of that external review. The actual Pillar source probe still resolves current-room coverage with the guard present.

Final checks: all 1,660 pytest tests passed in 124.90 seconds, including ten new dormant-item cases. Ruff lint and formatting, documentation file links and `git diff --check` passed. These checks establish implementation regressions, not new playthrough or runtime coverage. The missing Opus review remains a required-check blocker, so no commit was made for this correction. Earlier UI changes retain their separate completed commits and reviews.

## RE1-CLEAR-005: known puzzle rewards remain until collected

Status: Candidate for the pinned RE1 revision. This is a user-approved collection policy implemented and checked with synthetic scripts, the pinned Armor Room program and a private copied-save replay. It has no new natural puzzle/pickup gameplay validation.

Scope: Resident Evil Director's Cut, NTSC-U, SLUS-00551, Jill; executable SHA256 and installed DuckStation metadata are recorded under RE1-CLEAR-004 above. No emulator was launched, attached, paused or modified for this contribution. No health/ammunition patches were enabled, and no user exploration history was written.

Authored: 2026-10-17; Codex root, exact model `gpt-6.1-sol`, implementation, experiments and writing. Human contribution: the user reported gray Pillar Passage and Armor Room, clarified that Sun Crest collection should decide the latter's completion, and explicitly answered “Yes, for all puzzle items” when asked whether established rewards should block clearance before puzzle solution. The durable rule is in [Room completion](../../room-completion.md).

### Interpretation

The source evaluator now returns native availability and item collection separately from one shared script interpretation. Both results retain the existing source coverage, bounded-history, identity, acquisition and unsupported-mutation checks. The native result still reports uncertainty about dormant/active alternatives or unsupported physical access. The collection result can join those alternatives when every history establishes the same item and fresh acquisition flag. It reports `uncollected` without asserting that a pickup interaction is active. Optional creators, conflicting identities and unsupported effects are not converted to known rewards.

Current rooms supplement live observations only with source-established uncollected items shared by all matching sources. Conflicting source aliases cannot silently remove a required reward and permit clearance. The live observer's source-pointer and registry checks remain intact; overwritten inactive records do not authorize identity. Departed rooms use the same collection result with fresh flags. Existing actual available/taken observations retain their states, and cache refresh preserves the distinction between collection knowledge and active access. The UI includes both available and uncollected items in Remaining items. This applies to established ordinary collectibles and event rewards through shared rules, without a Sun Crest or Armor Room production exception.

The registry-proof prototype under RE1-CLEAR-004 is superseded: no dormant binding-candidate types, full-record proof or special acceptance path were retained. Its earlier result that Pillar Passage could clear with ammo still dormant is incompatible with the clarified policy. That ammo must now keep the room incomplete while its acquisition bit remains uncollected, even after both Herbs are taken. Unresolved identity or presence can still leave a room unknown.

### Reproduction and evidence

`tests/test_puzzle_items.py` uses fully synthetic source scripts bound through actual metadata hashes and `poll_once`, plus the pinned Armor Room program. It covers overwritten inactive registry words, activation, forced and pending awards, collection, earlier-state reversal, current/departed consistency after cache loss, optional/conflicting creators, source disagreement, fresh flags after an inactive-registry read, and native availability uncertainty remaining separate from collection. The tests reveal only explicitly entered rooms.

For the reported Armor case, replay the pinned profile using the existing controlled Winding Passage RAM fixture, explicitly mark Armor Room `01-05` / `mansion2f:05` visited, and vary only the puzzle and acquisition bits listed in RE1-CLEAR-004's address table. The source variants are owned `PSX/STAGE2/ROOM2050.RDT`, SHA256 `ff5079ce029afdd65af8c5d223104dec0d90f720a15710d27e21877c572be530`, and `ROOM2051.RDT`, SHA256 `a78ca9c140b0a6d9fb332d8dc78c2a27062e19c01d8553318fd384a47623576b`. The selected source establishes slot 9, Sun Crest type `0x2E`, ordinary GlobalId 36. These source bytes are not added to Git.

| Controlled state | Expected and observed completion | Item output |
| --- | --- | --- |
| Puzzle unsolved, pickup bit uncollected | Incomplete | Sun Crest uncollected |
| Puzzle solved, pickup bit uncollected | Incomplete | Sun Crest available or uncollected, depending on available-history proof |
| Puzzle solved, pickup bit collected | Cleared | Sun Crest taken |
| Rewind to unsolved and uncollected | Incomplete | Sun Crest uncollected |

The two flags are u8 values: puzzle bank 0/index 58 uses PS1 virtual `0x800C8704`, RAM offset `0xC8704`, mask `0x20` (set means solved); ordinary GlobalId 36 uses PS1 virtual `0x800C86E3`, RAM offset `0xC86E3`, mask `0x08` (clear means collected). Byte order has no effect on a one-byte read. These are pinned-profile interpretations, not new address confirmations.

A separate private replay used the user's copied end-of-session Main Hall RAM, SHA256 `bdb42992e325a7ed6d5d0b6aa88cef5d4ea3d51f4123ea869ffaf5689c73e516`, with already observed exploration from the frozen publication. One profile and tracker processed all four controlled states. Armor Room was incomplete/uncollected, incomplete/available, cleared/taken, then incomplete/uncollected, with complete item coverage throughout. After reversal the RAM bytearray equaled the original copied bytes exactly. Private script and JSON publications are under `/tmp/re-map-puzzle-completion/`; they are local evidence, not committed fixtures or a replacement for natural gameplay.

The README screenshot uses the final reversed publication while browsing the already explored Mansion 2F and selecting Armor Room. The player remains in Main Hall 1F in that snapshot; the screenshot does not invent an Armor Room visit or player position. The browser check changes the private publication from uncollected to collected and back, verifying the selected room's color and Remaining items without a reload.

### Validation limits

The user's initial reports and old publications are natural play observations, but the revised verdicts above use offline metadata and controlled flag changes. No native Armor puzzle interaction, Sun Crest pickup, Pillar Passage ammo pickup, returned-Mansion puzzle variant, new savestate load or normal card save/load was performed by the agent. All rooms with established rewards use the shared rule; this is not a claim that every campaign reward has resolved metadata. RE2 retains its separate candidate implementation and was checked only for shared-browser regression in this contribution.

### Review and validation ledger

Root's final inspection checked the two projections, current-room supplementation, source disagreement, cache/acquisition reversal, shared completion counts, remaining-item rendering and unchanged door interpretation. All 1,665 pytest tests passed in the final run in 161.60 seconds, including fifteen new puzzle-item cases. The earlier fourteen-case full run also passed (1,664 tests in 97.37 seconds). Ruff lint and formatting passed for all twelve changed Python files. Both browser suites passed: RE1's 118 outlines and shared controls, and RE2's 133 outlines and source-bound doors. The private Armor browser replay passed incomplete → cleared → incomplete while retaining manual selection, and the README screenshot was visually inspected. All 285 local documentation file links, the new claim anchors and `git diff --check` passed.

Claude Opus 4.6 (Thinking), the user-authorized installed alternative, could not review this implementation because the earlier call exhausted its individual quota. That call's exact error and conversation are preserved under RE1-CLEAR-004; its reported reset corresponds to approximately 23:19 Europe/Prague on 2026-10-17. No quota retry or silent model substitution was made. This unavailable required perspective is not an endorsement and initially blocked automatic commit under the repository's commit rule.

External review: `Gemini 3.8 Flash (High)`, conversation `5bdc85b5-47c7-4ff8-a1d3-b880ac514971`, completed in 342.20 seconds. The agent response reached `DONE`, the terminal result was `SUCCESS` with a nonblank response, stderr was empty, and no tool attempts occurred. Prompt SHA256: `960e7a260116caae2699339e5100d2a4e4e65862d4b4be238b34fd5c7f70c5a5`; private prompt, stream, response and CLI logs are under `/tmp/re-map-puzzle-completion/review/`. The snapshot included the full production/test diff, new puzzle regressions, source evaluator, live observer, source matching, current/departed validation, acquisition contracts, coherent poll, completion counts and UI rendering. It did not review this final research text.

Root checked the returned validator/cache concern directly. The validator replaces `observation.items` with the reconciled tuple before checking missing items, and incomplete cached coverage invokes source reconstruction rather than passing straight through to completion. The proposed failure was not reproduced. Additional current-room list-completeness assertions and a retained-cache variant of departure/collection/rewind all passed (fifteen puzzle cases total); no production change followed that suggestion. After the review snapshot, the shared cleared-state text was shortened to “Cleared” to remain accurate for both game profiles; both browser suites and the private Armor reversal were checked with that text. This is root verification of advisory output, not model agreement or new gameplay evidence.

2026-10-17; Codex root, exact model `gpt-6.1-sol`, recorded the user's explicit instruction to "continue without checks" after explaining the missing Opus review. This authorizes committing this completed change without that review or further checks. The unavailable review remains recorded above; this is a waiver for this change, not a change to the standing review policy.
