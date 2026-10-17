# RE1 analysis research

[Documentation index](../../README.md) · [Claim index](../../research.md)

## RE1-PILOT-001: live debug view tracks the Winding Passage Herb

Status: Confirmed for the tested SLUS-00551 Jill states
Scope: Resident Evil Director's Cut USA SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`; Winding Passage Main/Sub 00-09, loaded `ROOM1091.RDT`, Green Herb gid 111
Environment: isolated portable DuckStation 0.1-11894-gc66b2694d on macOS arm64, GDB port 2345, 2026-09-26; donated before and after Herb savestates copied outside Git
Authored: 2026-09-26; Codex with model GPT-6 Sol; subagents `/root/live_profile` and `/root/herb_availability` with model GPT-6 Sol independently checked profile and item evidence
Basis: controlled savestate fixtures, pinned executable and RDT research in RE1-FLAG-001/RE1-VARIANT-002/RE1-AOT-001/RE1-SCD-003, and live GDB reads from both isolated emulator boots
Claim: the live tracker can identify the tested Winding Passage variant and display the Herb as currently available and room state `INCOMPLETE` when its acquisition flag at PS1 VA `0x800C86EA` has mask `0x01` set and AOT id 5 at `0x800B819C` has handler `0x04` plus pointer `0x8013E65E`. The before-pickup boot reported room `00-09`, Items 1, Collected 0, `INCOMPLETE`. The after-pickup boot reported the same room, Items 1, Collected 1, Herb taken, and `UNKNOWN`. The list stays incomplete in both states. A flag set with an inactive or mismatched object, a different character/variant, a changed room during polling, or a failed memory read cannot produce `INCOMPLETE` under this pilot rule. The tracker rereads game-derived state each poll; external visit history is labeled as this tracker session only.
Evidence: `python3 tools/track.py --once` returned the stated outputs after launching the isolated DuckStation with `-nogui -statefile` on the before and after files. Those copies match committed fixtures `tests/fixtures/slus00551_green_herb_before.sav` SHA256 `837ee1d0a752538a4cf7e74b20d3991f0d403015ba19407b2e6f7972e9b67112` and `tests/fixtures/slus00551_green_herb_after.sav` SHA256 `f7fda842f192b453b89c3282abfda72609bd65bbf86df48fd10b3a6f5c7403c9`. A separate GDB experiment confirmed reads still work after issuing `c` to resume emulation, and continuous polling returned the before-state view while running. Five 32-byte runtime windows at PS1 VAs `0x8004484C`, `0x80045F28`, `0x8004897C`, `0x800489A8`, and `0x80091168` match the pinned executable in seven saved RAM captures; their concatenated SHA256 is `23311956abca97ba2522be37f6d45457f4ebbda529ede887a9d0a6d6a2a56958`. The live tracker checks those windows before interpreting room or item bytes. Fixture-backed tests cover both states, reloading the earlier state, a mismatched runtime window, inactive or mismatched item object, character and variant mismatches, read failure, a room transition during one poll, and simulated leave/return to an unmapped room.
Limits: the runtime-window hash identifies the tested executable code regions, not the entire running executable. Availability classification is deliberately limited to this one controlled Herb object; it is not a general AOT rule. The after-pickup state remains `UNKNOWN` because separate entry paths, later story behavior, and full room item coverage are unresolved; RE1-EVENT-002 narrows the indexed event-script concern for this room without closing it. RE1-REENTRY-001 records one later user-operated leave/return check; a normal in-game save/load of this Herb flag remains untested. Chemical-after normal save/load is separately confirmed in RE1-SAVE-001. The two-read room guard cannot detect a room changing away and back between reads. No save-linked visit-history persistence or map UI is implemented.
History:
- 2026-09-25; human user; produced the controlled before/after Herb savestates.
- 2026-09-26; Codex subagent `/root/live_profile` with model GPT-6 Sol; checked confirmed room addresses, Stage 0 variant selection, runtime signature options, and live-loop limits without repository edits.
- 2026-09-26; Codex subagent `/root/herb_availability` with model GPT-6 Sol; checked the exact Herb RDT row, flag, AOT record, and fixture transitions without repository edits.
- 2026-09-26; Codex with model GPT-6 Sol; implemented the limited live profile and debug rule, verified both isolated emulator boots over GDB plus a final before-state live read after review fixes, and recorded the scope and unknowns.
- 2026-09-26; Claude Opus 4.6 (Thinking); reviewed the supplied diff for profile parsing, polling, resource cleanup, and tests without reproducing gameplay. The numeric parsing, configuration diagnostics, reset handling, and test gaps were checked and addressed; its socket-leak finding was based on an older diff and was already fixed.
- 2026-09-26; Gemini 3.1 Pro (High); reviewed the supplied diff for live polling, object matching, and cleanup without reproducing gameplay. Reset handling and pointer-mismatch coverage were addressed; socket cleanup was already present in the final code.
- 2026-09-26; Gemini 3.8 Flash (High); reviewed the supplied diff for CLI execution, profile parsing, transition display, and tests without reproducing gameplay. Transition retry and test gaps were addressed; its missing-entrypoint and socket-leak findings did not apply to the final code.

## RE1-PILOT-002: live debug view names the conditional Chemical

Status: Confirmed for the tested SLUS-00551 Jill Chemical states
Scope: Resident Evil Director's Cut USA SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`; Mansion Storeroom Main/Sub 00-18, `ROOM1180.RDT`, Chemical gid 13
Environment: isolated portable DuckStation 0.1-11894-gc66b2694d on macOS arm64, GDB port 2345, 2026-09-27; controlled before and after Chemical savestates
Authored: 2026-09-27; Codex with model GPT-6 Sol
Basis: controlled savestate pair, prior script/flag/object findings RE1-SPAWN-001, RE1-FLAG-001 and RE1-AOT-001, fixture-backed polling tests, and live GDB reads from both isolated emulator boots
Claim: for the tested Jill room variant, the live tracker names the Chemical only when group-5 branch byte at PS1 VA `0x800C3006` has mask `0x02` clear. With the acquisition bit at `0x800C86DE` mask `0x04` set and AOT id 1 at `0x800B816C` holding handler `0x04` and opcode-plus-two pointer `0x80121E94`, the before-pickup boot displayed Chemical available, Items 1, Collected 0, and `INCOMPLETE`. The after-pickup boot displayed Chemical taken, Items 1, Collected 1, and `UNKNOWN`. The item list is explicitly incomplete in both states. When the branch bit is set, the tracker leaves item identity and completion unknown because the same room script can select Broken Shotgun instead.
Evidence: isolated `./DuckStation -nogui -statefile /private/tmp/re-map-duckstation-eyr2yxx9/chemical_before.sav` followed by `python3 tools/track.py --once` returned the before view above. Repeating with `chemical_after.sav` returned the after view. The copied savestates correspond to committed `tests/fixtures/slus00551_chemical_before.sav` SHA256 `5eeef607419e49ab3b36be49363c601d63523410a68755dabef0a15dcf178f2b` and `tests/fixtures/slus00551_chemical_after.sav` SHA256 `b5de7d17f76a6f2812c3761008f118d0d35e165d655dd24d737fb104e344085b`. Fixture tests additionally flip the branch bit in both states, suppressing the Chemical name and counts; test an inactive object, a failed branch read, and confirm the existing Herb pilot and room-transition behavior. The full Python suite passed, 36 tests, with one pre-existing fake-GDB-server thread warning. RE1-SAVE-001 separately records Chemical-after normal save/load persistence.
Limits: only the Chemical branch has a controlled pickup pair and live boot check; the Broken Shotgun branch was not played or classified. Flipping a bit in a fixture tests the tracker's conservative response, not the game's alternate spawn. The active object check is specific to this row and does not prove general availability. Full relevant item coverage and future story changes remain unresolved, so the room cannot be marked cleared. The runtime signature checks five code windows rather than the whole executable. No map UI or save-linked visit persistence is implemented.
History:
- 2026-09-26; human user; played and supplied the controlled before and after Chemical savestates and performed the normal Chemical-after save/load described in RE1-SAVE-001.
- 2026-09-27; Codex with model GPT-6 Sol; added the profile branch predicate and named live pilot, ran fixture-backed tests and both isolated live boots, and recorded the boundaries of the result.
- 2026-09-27; Claude Opus 4.6 (Thinking); reviewed the supplied code diff for branch checks and test isolation without running gameplay. Its confounded read-failure test finding was addressed.
- 2026-09-27; Gemini 3.1 Pro (High); reviewed the supplied code diff for profile parsing and debug wording without running gameplay. Its silent legacy-key and misleading branch-message findings were addressed.
- 2026-09-27; Gemini 3.8 Flash (High); reviewed the supplied code diff for profile parsing, scenario selection, and tests without running gameplay. Its decimal-versus-hex room ID and confounded test findings were addressed.

## RE1-ANALYSIS-005: remaining gaps after shared message-door support

Status: Candidate; source diagnostics under one unchanged captured flag state
Scope: RE1 Director's Cut NTSC-U SLUS-00551, pinned executable identity in RE1-DOORS-004; all 334 generated source variants at `860e905`
Environment: Python 3.14.8 and Capstone 5.0.9; donated Herb-before RAM SHA256 `d819fbd41abea6537bf9ce9f4967b479ea1f6278024b9f4e018290343c0bc8d4`; no emulator interaction or RAM writes
Authored: 2026-10-06; Codex root; model: GPT-6.1 Sol
Basis: unchanged diagnostic scripts, semantic source inspection and reinspection of existing native contracts
Claim: 88 source variants still have unresolved items or doors under this capture. The diagnostics distinguish 60 condition/descriptor ambiguities, 22 incomplete source programs and six source/context failures. No procedure budget is reached in this run. These are source-variant counts, not gameplay coverage.

Evidence:

- Reused the RE1-DOORS-003 private gap and descriptor diagnostics in a new directory, preserving their earlier artifacts. The prior 92 combined failures fall to 88; two newly resolved door variants still have unresolved items. RE1-DOORS-004 separately records the complete item/door projection counts.
- Four source/context failures occur at handler-9 updates to slot 3 in `ROOM10E0/10E1` and `ROOM60E0/60E1`; two occur at handler-2 updates to slot 1 in `ROOM5130/5131`. Each failing path lacks a modeled current-entry creator. RE1-REENTRY-003/004's retained-pointer constraint still applies. Removing that check cannot establish a new source or event target.
- The 22 incomplete programs include 13 indexed-event decoding failures, seven invalid event-creation targets and two forced awards without an item initializer. These categories use the first source-coverage failure; some rows have additional diagnostics. Init/main decoding is clean in all 22.
- Investigated whether an index at the zero marker could be treated as an event starting at section offset zero. Rejected that interpretation. Rechecked RE1-EVENT-002's loader at PS1 VA `0x80044B74..0x80044BDC`: it relocates only nonzero entries and stops before changing the zero marker. RE1-EVENT-005's complete initializer at `0x80025C1C..0x80025C58` copies the selected table word directly into the record's script pointer, with no base addition. Hash-bound `ROOM5070` and `ROOMC070` both declare index 7 after seven entries, selecting that unchanged zero. Their table's first byte `0x20` cannot establish a harmless state-0 stop for a null script pointer. Source coverage remains unresolved; no decoder bounds were relaxed.

Private artifacts under `/tmp/tasks/re-map/post-message-inspection/` are `gaps.json`, SHA256 `ccb63e43c0ea0569dec7f61aa5b1064aed8f43ca578eda447f61fcc56c1367a2`; `ambiguity.json`, SHA256 `6b8c1d09b259fad08dbd36d9fa28c8a0532e3a145c8a01152810a706304443be`; and `start-native.txt`, SHA256 `6bb7ed3a82bf7686f82b9993ea0143fbbeeaf78031d9ff418a8641717a291466`. Scratch scripts and game-derived artifacts remain outside Git.
Limits: no new gameplay, normal save/load, source-generation or implementation test was performed. An invalid start present in source need not execute in normal play; resolving its reachability requires supported conditions rather than declaring it harmless. Other captured flag configurations were not reclassified for this diagnostic.
History:

- 2026-10-06; Codex root, GPT-6.1 Sol; recomputed the gap categories, inspected missing-creator paths and incomplete-source diagnostics, and rejected the zero-marker event-root hypothesis against the hash-verified loader and initializer. Production code and generated metadata remain unchanged.

## RE1-ANALYSIS-006: remaining reconstruction gaps after reachable script coverage

Status: Candidate; private source diagnostics under one unchanged captured state
Scope: RE1 Director's Cut NTSC-U SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`; all 334 source variants at `2caa0c4`
Environment: Python 3.14.8 on macOS; the unchanged Herb-before RAM from RE1-ANALYSIS-001, SHA256 `d819fbd41abea6537bf9ce9f4967b479ea1f6278024b9f4e018290343c0bc8d4`; no new emulator actions
Authored: 2026-10-07; Codex root; model: GPT-6.1 Sol
Basis: mandatory profile loading, reentry evaluation, procedure/coverage traces and private interpreter substitutions
Claim: 72 source variants have unresolved items or doors in this configuration after RE1-REENTRY-005. This is an offline diagnostic count, not gameplay coverage.

Evidence:

- Reentry has 287 complete item lists and 301 complete door results. Their combined unresolved set has 47 item-list failures and 33 door failures, with eight variants in both sets. The 72 variants comprise 58 condition/descriptor ambiguities without a traced runner failure, eight ambiguities with a failed per-slot event closure, four reached invalid event starts and two structurally invalid event tables. The outer coverage result can remain complete while a per-slot closure leaves its own interaction unresolved; it does not authorize publishing that slot.
- Invalid starts remain in `ROOM5070/5071` and `ROOMC070/C071`. `ROOMB000/B001` retain structural coverage failures. The eight failed-closure variants are `ROOM10E0/10E1`, `ROOM10F0`, `ROOM5130/5131`, `ROOM60E0/60E1` and `ROOM60F0`. Their traced failure is a nonzero handler setter without a creator in that closure's source context. No traced procedure state or stack budget is exceeded.
- Repeated RE1-ANALYSIS-002's unknown-flag assumption experiment against the current interpreter, separately in current/reentry epochs. It produces no complete-result gains. Current complete item lists fall 263 -> 259; reentry item lists fall 287 -> 280 and door results 301 -> 291. It also loses previously published payloads. The earlier rejected approach remains rejected; no production predicate behavior changed.
- Repeated RE1-ANALYSIS-003's full-registry-context experiment after the reachability change. Current/reentry complete item counts remain 263/287 and door counts 256/301, with no previously published payload changes. Supplying that context alone does not resolve the observed gaps. Neither experiment changes source bounds or treats a missing creator as known.

Private reproducible scripts and reports are under `/tmp/tasks/re-map/post-reachability-inspection/`. `gaps.json` has SHA256 `5eb8410b9e7f544512e869dfe246e62fea739b25ed203a0a290c7659063d27c1`; `experiments.json` has SHA256 `f9ffa16a8bc035eab8403969ef141c25eda78b9ea958ab2bf3e1bbc05c036bd0`. The gap report initially groups all 66 bounded unresolved variants together; the eight failed-closure rows distinguish the two subcategories above. Run `gaps.py` and `experiments.py` against the named commit and fixture to reproduce the counts.
Limits: one captured flag configuration, no natural traversal, story progression, pickup, load or alternate character was newly tested. Absence of a traced procedure budget does not prove that every other analysis limit is impossible. The private substitutions are diagnostics, not implementation or additional runtime validation. Original earlier audit results and attribution remain unchanged.
History:

- 2026-10-07; Codex root, GPT-6.1 Sol; adapted the prior diagnostics to explicit reentry and final coverage, reran both rejected/ungained hypotheses, and separated reached invalid roots from interaction ambiguity. Production code, profile, generated manifest and runtime state remain unchanged.

## RE1-ANALYSIS-007: remaining gaps after bounded scripted-door tracking

Status: Candidate; source-derived diagnostic under one unchanged RAM snapshot
Scope: RE1 Director's Cut NTSC-U, SLUS-00551, pinned executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`; tracker commit `0b60d9e`, all 334 source variants
Environment: Python 3.14.8, committed semantic metadata and donated Herb-before RAM; no new emulator session or gameplay
Authored: 2026-10-07; Codex root; model: GPT-6.1 Sol
Basis: traced fresh-entry interpretation and source-bound event/descriptor inspection
Claim: after RE1-DOORS-006, the unchanged offline projection still has 47 incomplete item variants and 22 incomplete door variants. Sixty-one variants have either gap. These are source-analysis counts, not rooms validated during a playthrough.

Evidence:

- Repeated RE1-ANALYSIS-006's diagnostic against `0b60d9e`. Complete reentry items remain 287/334 and complete doors are 312/334. Eight variants have both kinds of gap, giving a union of 61. The earlier union was 72; the eleven previously recorded door gains account for the difference.
- Fifty-five variants have bounded final room coverage with condition/descriptor ambiguity. Within those, eight encounter a failed per-slot event procedure and conservatively retain independent writer alternatives. Four other variants reach the invalid event start to index 7 already recorded in RE1-ANALYSIS-006: `ROOM5070/5071` and `ROOMC070/C071`. Two `ROOMB000/B001` variants still lack structural source coverage. No failure was newly treated as harmless.
- The ambiguity groups include active/dormant pickup handlers, map/item script handlers, open/message doors and differing door definitions. No per-slot closure exceeds its 256-alternative bound in this snapshot. A single source can have more than one unresolved slot, so slot-category totals do not count distinct rooms.
- Inspection of registered item scripts identifies the bounded confirmation/child-event route in RE1-COLLECT-001. Other inspected item routes enter actor VM state or depend on room-local progress. They do not inherit that confirmation route's proposed availability interpretation.

Private reports are under `/tmp/tasks/re-map/post-scripted-door-inspection/`: `gaps.json`, SHA256 `a11f175d5ec75cec08a5a682db2f4955ba88e34ce4e8c01eb8e7cb6bcc3b958e`; and `interactions.json`, SHA256 `8315cac25c4781d56d145688e1244cd64c2e578038b404d421adab777654c1c6`. Run `gaps.py` against the named commit and donated Herb-before fixture to reproduce the projection; `interactions.py` records the inspected registry writers and owned event commands. No RAM or game bytes are committed.
Limits: no new availability verdict, save/load replay, native event execution, other snapshot or natural later-area gameplay was tested. This inspection changes no production behavior or map geometry.
History:

- 2026-10-07; Codex root, GPT-6.1 Sol; traced all 334 source variants, counted remaining gaps, inspected registered item event targets and retained structural/invalid-start failures. The user requested continuation; implementation of a new feature remains subject to separate approval.

## RE1-ANALYSIS-001: whole-room shadow dependencies preserve published results and reduce branching

Status: Candidate; interpreter inspection, synthetic regressions and captured-RAM replay
Scope: Resident Evil: Director's Cut, NTSC-U, SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`; all 334 generated source variants
Environment: Python 3.14.8, pytest 9.1.1; prior RAM captures retain their original DuckStation environment and provenance
Authored: 2026-10-06; Codex root; model: GPT-6.1 Sol
Basis: interpreter dependency inspection, synthetic tests, comparison against commit `86c42fa`, and replay of previously captured game states
Claim: before deduplicating procedure states, simulated writes can discard physical bits that no command in the whole room program reads. Keeping every flag/scalar predicate dependency and mode-1 quantity input preserves later procedure, event and tick decisions while preventing irrelevant shadow writes from multiplying paths. Acquisition and door access still use fresh game state.

Evidence:

- The mandatory evaluator collects physical byte-address/bit-mask dependencies across initialization, recurring main, ordered event blocks and standalone/deferred event commands. Flag predicates retain their addressed bit, byte/word predicates retain all 8/16 bits, and quantity mode 1 retains its eight scalar input bits even without a predicate. Flag toggles and native conditional writes read their own destination only; any destination observable by a later decision is already retained. Slot descriptors, registry parameters, quantities, event starts, unsupported effects and snapshot reads are not filtered. The existing 4,096-state, 16-stack and 256-descriptor limits remain unchanged.
- `tests/test_script_dependencies.py` adds 34 synthetic cases across current/reentry epochs: thirteen independent unread flag/byte/word branches, flag/scalar aliases, dependencies in later procedures, optional ordered/single events enabling a later main tick, registry callback alternatives retaining scalar quantities, event-only quantity inputs and unsupported effects. The two earlier path-budget tests now read the branched bits so they continue to exercise genuinely retained state. Existing callback, alias, quantity, story/acquisition and load tests also pass.
- All **1,039 tests pass in 43.59 seconds**. The four changed Python files pass manually scoped Ruff lint/format checks; no repository formatter/linter is configured. `git diff --check` passes.
- A differential audit runs both the unmodified evaluator from `86c42fa` and the new evaluator on all 334 programs, both epochs, and three captured RAM states: Herb-before SHA256 `d819fbd41abea6537bf9ce9f4967b479ea1f6278024b9f4e018290343c0bc8d4`, Herb-after `0130861a3a27d2810ccbd0d1e2e7bbc42c64abdac130e1d43dd71ed646784704`, and Chemical-before `bb9110536a02122d7c6a14d489b2e94e7d8224d8ccf297d617694c4eb6e804f2`. All 2,004 old/new evaluations preserve every previously published item descriptor, amount, acquisition state, door and disabled door. Every previously complete item/door result remains complete with the same payload.
- In each reentry snapshot, complete item results increase **258 -> 262** and complete door results **268 -> 272**. Gains are `PSX/STAGE3/ROOM30F0.RDT`, `ROOM30F1.RDT`, `PSX/STAGEA/ROOMA0F0.RDT` and `ROOMA0F1.RDT`. In each current snapshot, items remain **255**, while doors increase **250 -> 252** through `ROOM30B0/ROOM30B1`. These are source variants analyzed against existing flags, not six newly played rooms.
- Reentry analysis of all 334 variants takes 5.07-5.15 seconds with the baseline and 1.09-1.13 seconds with filtering in the paired audit. Current analysis takes 0.25-0.27 seconds before and 0.26-0.28 seconds after. These offline totals do not measure live polling latency or guarantee a speedup for current-room analysis.
- The unchanged RE1-REENTRY-004 twelve-step, eleven-distinct-capture replay passes through one tracker/profile. Main Hall clearance survives departure, normal-load captures and the ordinary round trip; an earlier Ribbon state becomes incomplete again; Art Room remains incomplete with its Ribbon and correct Map reversal. The map reveals only entered rooms 06/07. No RAM values were substituted and no new gameplay was performed.
- Private artifacts are under `/tmp/tasks/re-map/dependency-filtering/`: `audit.py`, `audit.json`, `projection.json`, `differential.py`, `differential.json` and pytest logs. Differential script SHA256 `3bb902d9987b00990b92e024a727a0b34651cf3fc0652312c8203f99fbda18a8`; differential report `8d407e27c2e92d336ee535c72230225f4652a36b33a245e968af7b5c967de549`; replay report `f2d96bd2405b0493bfcea757f6db560f07c30a06035d388f7ae943a777987662`. The committed manifest and profile are unchanged; raw game data and captures remain outside Git.

Limits: this does not establish natural gameplay coverage in the newly resolved variants. ROOM3030 remains unresolved because of descriptor/condition ambiguity; the dependency-filtered run no longer reports incomplete script coverage there. Other conditional spawns, cross-slot event reconstruction, scenario differences and whole-game save/load remain unfinished. Dependencies are conservative for the current command set; future commands that read shadow state must add their physical read dependencies. RE1-ANALYSIS-002 records the rejected broader predicate experiment.
History:

- 2026-10-06; Codex root, GPT-6.1 Sol; inspected all shadow read sites, implemented shared dependency filtering, added synthetic regressions, compared all published old/new payloads across six projections and replayed the existing save/load sequence.
- 2026-10-06; Codex root, GPT-6.1 Sol; corrected the stale ROOM3030 budget limitation after tracing the committed evaluator. Its item slot 1 and door slot 0 remain unresolved, with no failed procedure execution in the donated Herb-before projection. RE1-NATIVE-002's earlier budget observation remains valid for its earlier interpreter.
- 2026-10-06; Gemini 3.1 Pro High via agy, conversation `511d3146-3c2b-422e-8995-b0f1ba519d93`; reviewed the complete supplied diff, full interpreter/schema/event contracts/compiler, new tests and existing callback/quantity/reentry/event regressions. Returned "No findings." Process exit 0, final agent response DONE, result SUCCESS and empty stderr; no tools, tests or gameplay. Review packet 188,352 bytes, SHA256 `d4c682cfb56968c191c3a797b17c8c7a5f345e2237712f7f8aaa21be8311ce7d`. Root independently inspected every shadow consumer and verified the paired payload/replay results.
- 2026-10-06; Gemini 3.8 Flash High via agy, conversation `c3842318-5abe-4bbe-8d00-a54ad05c6812`; completed the same supplied-snapshot review and returned "No findings." Process exit 0, final agent response DONE, result SUCCESS and empty stderr; no tools, tests or gameplay. Neither review reproduced the runtime experiments or promoted their validation state.
- 2026-10-06; Claude Opus 5.5 High via agy; remained unavailable under the RE1-EVENT-011 quota exhaustion, reported on 2026-10-05 with a reset in 110 hours, 53 minutes, 55 seconds. No retry before reset, review, substitution or endorsement.

## RE1-ANALYSIS-002: extending unknown-flag assumptions to current execution exceeded existing budgets

Status: Rejected; private offline experiment, not implemented
Scope: same pinned SLUS-00551 executable and generated source set as RE1-ANALYSIS-001; one donated Herb-before flag configuration
Environment: Python 3.14.8; no emulator interaction
Authored: 2026-10-06; Codex root; model: GPT-6.1 Sol
Basis: private interpreter substitution and source-variant comparison against `86c42fa`
Claim investigated: applying historical repeated-flag assumptions to current execution might resolve the remaining branching limits.
Evidence: removing the historical-only guard for unknown flag assumptions resolved no additional variant and lost eight complete item results and thirteen complete door results under the existing budgets. Items changed 258 -> 250, doors 268 -> 255. Combining that experiment with dependency filtering still lost four item and nine door results despite four gains each. The accepted change only filters dependencies; it preserves the original predicate semantics. Private `/tmp/tasks/re-map/branch-consistency-inspection/comparison.json`, SHA256 `f5dedc5946a78ea5fad2943dd085115c2b4372c2cf341848c44a1e3cce0871dd`, lists the standalone experiment's losses; `dependencies-and-consistency-projection.json` records the combined experiment's source results.
Limits: rejection concerns this bounded interpreter and snapshot, not the native consistency of repeated reads or all possible future analyses.
History:

- 2026-10-06; Codex root, GPT-6.1 Sol; performed private substitutions, observed coverage losses, rejected the extension and left production predicate behavior unchanged.

## RE1-ANALYSIS-003: merging interaction alternatives at matching branch states avoids two procedure limits

Status: Candidate; private offline experiment, not implemented
Scope: Resident Evil Director's Cut NTSC-U SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`; all 334 generated source variants at `d3c36b3`, reentry analysis only
Environment: Python 3.14.8; donated Herb-before RAM SHA256 `d819fbd41abea6537bf9ce9f4967b479ea1f6278024b9f4e018290343c0bc8d4`; no emulator interaction or RAM writes
Authored: 2026-10-06; Codex root; model: GPT-6.1 Sol
Basis: interpreter tracing and three private in-memory substitutions, without production edits
Claim investigated: forward control flow permits joining possible interaction descriptors when paths reach the same script PC, IF stack and physical shadow values. This can reduce duplicate execution while preserving distinct flag states and all descriptor alternatives.

Evidence:

- The updated gap audit finds 92 variants with unresolved item or door coverage. Its mutually exclusive diagnostic categories are 62 with condition/descriptor ambiguity and no failed procedure, 22 with incomplete source coverage, six with other source/context failures, and two exceeding the procedure budget. These counts describe one offline snapshot, not naturally validated rooms.
- Repeating RE1-AOT-003's full-registry-context experiment after shared disabling produces no complete item/door gains, losses or changes to previously published payloads. A separate partial registry experiment retains known handler/mode/extended parameters without claiming a source identity and still rejects source-dependent reads. It also produces no complete coverage gains or losses in this snapshot. These observations do not reject the native contracts or establish that such models are unnecessary in other states.
- The branch experiment processes pending states by ascending PC. At a matching PC, IF stack and exact physical shadow tuple, it unions descriptor alternatives separately for each slot, including a missing descriptor when a path lacks that slot. It leaves paths with different flag shadows separate. `RuleProcedure` already enforces forward branch targets. The existing 4,096-state, stack, descriptor and fixed-point limits are unchanged.
- Complete item projections increase **269 -> 271**. The gains are `ROOM3050.RDT` and `ROOM3051.RDT`; each exposes item slots 15..18 with GlobalIds 203..206 under this captured configuration. Peak states per procedure fall **4,097 -> 524**, and each variant's failed-procedure count falls one -> zero. Door slots 1/2 become interpretable, but slot 0 still has a message-handler ambiguity, so complete door coverage remains **281/334**.
- Across all 334 paired evaluations, every previously published item descriptor, quantity, acquisition state, door and disabled-door payload remains present and equal. No previously complete item or door result becomes incomplete. The report compares published results, not equality of every unresolved alternative or internal execution path.

Private artifacts remain under `/tmp/tasks/re-map/post-disable-inspection/`:

| Artifact | SHA256 | Purpose |
| --- | --- | --- |
| `gaps.json` | `7bd0db110768c74d00ee37ec5fc6554b1ccb8db354c1e13c46f04b6a7a74a18b` | Updated failure categories and traced commands |
| `context-comparison.json` | `f94a1fa759853e928b5e117dbae14f7690f06c80ff9b505f8b4d015bfd8141da` | Repeated full-context experiment |
| `registry-comparison.json` | `d41c99949dcd9738c480cb8148e0ddd69cddbc0fc25a102a242bcf15548830db` | Partial registry experiment |
| `merge_experiment.py` | `bdde18612aac971016ab01b0cf673f051a307b728b4e7515e1f20d3f4a7877f9` | Reproducible in-memory branch substitution and comparison |
| `merge-comparison.json` | `29f6e0d57529fca44e359e53a33e01dcb5b3ae90e4787405508ba5a1d6020c98` | Paired coverage and published-payload results |
| `merge-budget.json` | `88f6927bfed7e37432a98c11c166b05e52e26bb49d898ffc25214fa091c90b73` | Traced procedure counts and the two gained item lists |

Limits: no production implementation, regression suite, current-room experiment, other captured flag state, save/load replay or natural gameplay validation was performed for merging. Joining slots can discard correlations between them; implementation must verify that all consumers remain conservative and that distinct guard states remain separate. The private list-based scheduling is an experiment, not a polling-performance design. Remaining item/door ambiguity and incomplete source coverage are unchanged.
History:

- 2026-10-06; Codex root, GPT-6.1 Sol; reran the gap audit and full-context hypothesis, inspected unresolved descriptor meanings, compared a partial registry hypothesis, then measured the branch-state candidate across 334 variants and traced both prior budget failures. Recorded evidence before requesting implementation approval. Manually reviewed the documentation diff and passed `git diff --check`; no Markdown formatter/linter is configured.
- 2026-10-06; Codex root, GPT-6.1 Sol; implemented the approved shared runner change and recorded RE1-ANALYSIS-004's synthetic, paired-projection and captured-load checks. The initial experiment remains separate from implementation evidence; no natural gameplay validation is added.
- 2026-10-06; Codex root, GPT-6.1 Sol; found that merging distinct descriptor inputs before quantity/registry reads can discard a guard proof, despite matching earlier flag shadows. RE1-ANALYSIS-004 retains those inputs separately and adds the counterexample regressions. The original experiment's narrower measured results remain recorded.

## RE1-ANALYSIS-004: bounded branch merging preserves source and guard uncertainty

Status: Candidate; synthetic regressions, paired offline projections and previously captured RAM replay
Scope: RE1 Director's Cut NTSC-U SLUS-00551 identity from RE1-ANALYSIS-003; shared initialization/main/event runner in current and reentry analysis
Environment: Python 3.14.8 and pytest 9.1.1; capture environments/provenance remain RE1-REENTRY-004's, without a new DuckStation session
Authored: 2026-10-06; Codex root; model: GPT-6.1 Sol
Basis: approved interpreter change, direct invariant/consumer inspection, synthetic boundary tests and comparison against `620f44c`
Claim: pending states can join possible interaction descriptors at matching script PCs, IF stacks, demanded physical shadow tuples and source descriptor inputs to quantity/flag callbacks. The runner retains missing creators and conflicting identity, parameter, quantity and availability alternatives; differing guard inputs remain separate. This avoids some procedure-budget failures without inventing a source or granting acquisition/unlock.

Evidence:

- A heap processes validated forward PCs and uses a unique sequence number to avoid ordering unknown shadow values. Keyed pending buckets union descriptors separately per slot and include `None` when a predecessor lacks that slot. Inputs to quantity reads and door/flag/map callbacks stay in the join key, because those consumers can affect later scalar/flag guards. Enqueueing filters only RE1-ANALYSIS-001's already-unread shadow bits. A union exceeding the existing 256-descriptor limit fails reconstruction; the 4,096-state, 16-stack and 64-iteration limits remain unchanged. The common runner handles both epochs and every existing procedure entry point. No room-specific exceptions, profile/manifest changes or new memory addresses were added.
- `tests/test_branch_merging.py` adds 46 synthetic cases for independent registry branches in init/main/ordered events, distinct physical flag/scalar shadows, missing creators, source-dependent callbacks and quantity writes, alternative flag/event callback parameters, conflicting item/door identities, fresh acquisition reversal, unknown quantities, the descriptor boundary and malformed IF stacks. Four cases preserve a `>= 1` guard after reading either quantity 1/2 or registry flag parameters producing scalar 1/2. An unrestricted descriptor union loses that proof by turning the read into unknown. Separate relevant flag histories still reach the original procedure budget and remain unresolved. All tests use synthetic packets and explicitly supplied test RAM.
- The final full suite passes **1,181 tests in 44.37 seconds**; the final focused file passes **46 in 0.25 seconds**. Ruff formatting and lint checks pass on the modified Python files, and `git diff --check` passes. The repository has no configured formatter/linter; documentation is reviewed manually.
- The unchanged paired audit from RE1-AOT-004 compares both evaluators across all 334 sources, both epochs and Herb-before, Herb-after and Chemical-before captures, using their recorded hashes from RE1-ANALYSIS-001. All **2,004 comparisons** preserve previously published item descriptors, quantities, acquisition states, doors and disabled doors. Previously complete results remain complete and equal. In each snapshot, current item coverage increases **255 -> 259**, reentry item coverage **269 -> 271**. Complete current/reentry door coverage stays **252/281**.
- Current item gains are `ROOM3050/3051` and `ROOM5130/5131`; reentry gains are `ROOM3050/3051`. Under Herb-before, traced `ROOM3050/3051` peak states fall **4,097 -> 273** for current analysis and **4,097 -> 524** for reentry. Current `ROOM5130/5131` peaks fall **4,097 -> 2,932/2,942**. Each prior budget failure disappears. Their unresolved door slot 0 remains unresolved; item gains do not establish complete door access.
- RE1-REENTRY-004's unchanged twelve-step replay of eleven distinct coherent 2 MiB RAM captures passes through one profile/tracker. It covers the recorded Art Map pickup, Main Hall Ribbon states, three normal-load captures, ordinary departure/return and earlier-state reversal. Main Hall remains cleared after departure when its Ribbon is taken and becomes incomplete in the recorded uncollected state. Art Room keeps its remaining Ink Ribbon and Map acquisition reversal. Only entered rooms 06/07 are revealed. No bytes are substituted and no new gameplay occurs.

Private artifacts stay under `/tmp/tasks/re-map/branch-merging/`:

| Artifact | SHA256 | Purpose |
| --- | --- | --- |
| `differential.py` | `3bb902d9987b00990b92e024a727a0b34651cf3fc0652312c8203f99fbda18a8` | Unchanged paired-evaluator audit |
| `differential.json` | `9cb2a5f5a8c52fe55ac9e163762657755f841e39205faddefb48bb3f9dec0f14` | Six projections and preserved published results |
| `audit.json` | `b0fa14d6acb242cad3d1ed50094425d0c9e430f6cd8f550120276f3155698235` | Captured save/load/room replay and source projection |
| `budget.json` | `0e89c1129a35c8361f3b92f442d9a0c4feb967ee86803661d0514eed1ed07bc4` | Old/new procedure traces for the four gained variants |
| `pytest-final.log` | `5889e1e98f970fc9a65f1545ba8011202559633567fe623da7620c7eb24de7e3` | Final full-suite result |

Limits: merged slots can lose correlations between descriptors in different slots, so consumers must remain conservative. No claim of equivalence for every unresolved execution path is made. The source counts are disc variants under three captured flag configurations, not validated rooms or playthrough coverage. Newly resolved variants, broader story progression, alternate character/revision and whole-game behavior still need natural gameplay validation. Existing source/condition and door-handler gaps remain.
History:

- 2026-10-06; Codex root, GPT-6.1 Sol; implemented the approved shared join, inspected its forward-control-flow invariant and source/quantity/parameter consumers, ran the synthetic boundaries and full suite, compared all source projections and replayed the existing recorded load/room sequence. Raw game/capture data remains outside Git.
- 2026-10-06; Gemini 3.1 Pro (High), conversation `4716d2da-566d-48df-b85c-4ef211d5d30d`, and Gemini 3.8 Flash (High), conversation `be3054be-7e47-4048-88a4-d0b2a1757aab`; reviewed the initial 184,572-byte implementation/test snapshot and returned no findings. Both processes exited zero with completed responses, successful terminal results and empty stderr; neither used tools or ran tests/gameplay. These draft reviews were superseded after Codex root found the descriptor-input guard regression and corrected it.
- 2026-10-06; Gemini 3.1 Pro (High), conversation `cd770447-e720-4173-8d26-db30f9affe13`; reviewed the corrected implementation, 46 regression cases, caller/contracts and documentation in a 188,911-byte snapshot (SHA256 `f6e2e3f2144b506d0d6a30350d5cd036f3e0745459423c874f23383c2d38b122`) and returned no findings. Process exit zero, response DONE, terminal SUCCESS and empty stderr were checked; no tools, tests or gameplay were performed by the reviewer. Codex root verified the final diff and test/report evidence independently.
- 2026-10-06; Gemini 3.8 Flash (High), conversation `6110b773-1cd2-43a4-a1a3-fe265816388b`; the corrected snapshot's review encountered an unexpected stream EOF. The CLI retried internally and returned text, but its terminal result remained ERROR despite process exit zero and empty stderr. This failed call is diagnostic output, not a completed review; one fresh retry was dispatched with the identical snapshot.
- 2026-10-06; Gemini 3.8 Flash (High), fresh conversation `01c23e49-5d12-4fed-9c82-785e2c3a7180`; the retry encountered the same unexpected stream EOF and emitted an error step without a completed terminal result. Codex root stopped that failed process (exit one) rather than accepting diagnostic output or making another retry. The final Flash review remains unavailable; no endorsement is claimed.
- 2026-10-06; Claude Opus 5.5 (High); unavailable because of the quota exhaustion recorded on 2026-10-05, with a reported reset in 110 hours 53 minutes 55 seconds from that check. The model was not retried before its reset; no Claude review or endorsement is claimed.

## RE1-ANALYSIS-008: remaining gaps after bounded scripted-collectible tracking

Status: Candidate; source-derived diagnostic under one unchanged RAM snapshot
Scope: RE1 Director's Cut NTSC-U SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`; tracker commit `1d79e8a`, all 334 source variants
Environment: Python 3.14.8, committed semantic metadata and donated Herb-before RAM; no emulator interaction
Authored: 2026-10-07; Codex root; model: GPT-6.1 Sol
Basis: traced reentry interpretation, registry alternatives and owned event-command inspection
Claim: after RE1-COLLECT-002, the unchanged offline projection has 43 incomplete item variants and 22 incomplete door variants. Fifty-seven variants have either gap. These counts describe source analysis under this snapshot, not gameplay coverage.

Evidence:

- Repeated RE1-ANALYSIS-007's diagnostic against `1d79e8a`. Complete reentry item lists are 291/334 and complete doors are 312/334. Eight variants have both gaps. The four item gains from RE1-COLLECT-002 reduce the previous union from 61 to 57.
- Fifty-one variants have bounded final coverage with condition or descriptor ambiguity. Eight of those retain failed per-slot AOT-handler contexts: `ROOM10E0/10E1`, `ROOM10F0`, `ROOM5130/5131`, `ROOM60E0/60E1` and `ROOM60F0`. Four other variants still reach an invalid event start to index 7, `ROOM5070/5071` and `ROOMC070/C071`. `ROOMB000/B001` still lack structural source coverage.
- No traced unresolved slot exceeds the 256-alternative closure bound. The report records no procedure-budget or stack-depth failure under this snapshot. This does not prove that other game states fit those bounds.
- Four remaining variants contain item descriptors with handler-9 alternatives. Slot 6 in `ROOM1060/6060` has type `0x02`, GlobalId 26 and ordinary/scripted handlers 4/9. Slot 2 in `ROOM9120/ROOME120` has type `0x34`, GlobalId 27 and handlers 4/9. Their registered targets enter actor VM state. RE1-COLLECT-003 examines acquisition independently of those unsupported access routes.

Private evidence directory `/tmp/tasks/re-map/post-scripted-collectible-inspection/`: `gaps.json`, SHA256 `a60babc96b761f6d7632dcad501f990ac79e54c1f637aa6fc51d1a7dc532f8d3`; `interactions.json`, SHA256 `10035d9059b231d764f79854e76c9b200bf5980cdcd4e79db1c7ca17cbe4d03a`. Run `gaps.py` with the named commit, pinned profile and donated Herb-before capture, then `interactions.py` to record registry writers and owned event commands. Extracted base RAM SHA256 is `d819fbd41abea6537bf9ce9f4967b479ea1f6278024b9f4e018290343c0bc8d4`. No game bytes or RAM are committed.
Limits: this inspection adds no availability rule, live room observation, save/load experiment or spatial map. Source metadata retains its existing provenance; no new raw-disc extraction or native actor execution was performed.
History:

- 2026-10-07; Codex root, GPT-6.1 Sol; traced all 334 sources, checked the remaining category counts and inspected the four registered-item alternatives. Production rules remain unchanged.

## RE1-ANALYSIS-009: item-interaction predicate probe preserves coverage without gains

Status: Candidate; source-derived diagnostic and private interpreter comparison under one unchanged RAM snapshot
Scope: pinned SLUS-00551 identity from RE1-SCD-021; tracker commit `d1a8cf4`, all 334 generated source variants, both current and reentry epochs
Environment: Python 3.14.8, owned disc and donated Herb-before RAM; no gameplay, emulator writes or production edits
Authored: 2026-10-07; Codex root; model: GPT-6.1 Sol
Basis: RE1-SCD-021 native contracts, full-source hash verification, traced reentry interpretation and private semantic substitution
Claim: the remaining unchanged-snapshot gaps are still 43 item variants and 22 door variants. Mapping `10/11` to supported physical byte comparisons preserves all tested results but produces no whole-source coverage gain. This is a shared interpretation candidate, not evidence that these changes alone resolve the remaining unknown rooms.

Evidence:

- Repeated RE1-ANALYSIS-008's diagnostic against `d1a8cf4`. Reentry complete items remain 291/334 and complete doors remain 312/334. Fifty-seven variants have either gap and eight have both. Fifty-one variants retain bounded condition/descriptor ambiguity, four reach an invalid event start to index 7, and two lack structural source coverage. The same eight variants retain failed per-slot AOT-handler contexts. No traced unresolved slot exceeds the 256-alternative closure bound; no procedure-budget or stack-depth failure appears under this snapshot.
- Extracted each of the 334 source RDTs from the owned disc and verified its full SHA256 against the committed manifest before reading operands. Found 132 distinct `10/11` commands across 72 source variants, 102 opcode `10` and 30 opcode `11`. Every retained command has the audited two-byte extent.
- Private copies of the semantic programs replace only these `uncertain-test` commands with `byte-test`, index 18 or 19, comparison equality, and the source operand. The existing evaluator resolves only supported physical shadows; it reads no new transient RAM or inventory and introduces no initial value. Source identities, proof metadata and all other commands remain unchanged.
- A second private evaluator additionally assigns a known byte-19 shadow after the immediate map callback when its descriptor alternatives agree on item type. This is a precision experiment, not a complete native scheduling model or an approved production effect rule. Both modes, both epochs and 334 sources give 1,336 paired projections against the unchanged evaluator.
- Complete item counts remain 267 current and 291 reentry; complete door counts remain 263 current and 312 reentry in every mode. There are no gained/lost complete results or changed previously published items, quantities, acquisition states, doors or disabled doors. Every previously complete item result remains identical. The test uses one donated flag configuration and cannot establish full-playthrough coverage.

Private evidence directory `/tmp/tasks/re-map/post-acquisition-inspection/`: `gaps.json`, SHA256 `b6fcc1f6a67461f1d36729c860f9537568523665d4ddaabd1976351899515e8f`; `item-predicates.json`, SHA256 `73c710840ae5e7116aa5e56a823770997a5bd6f5ad6f0dbac63c1099e1e2fee8`; `predicate-probe.json`, SHA256 `2deeaf226237e6a1b95ae9ceff87c0b9a7fb98587ae558ace582b555915d2432`. Run `gaps.py` and then `item_predicates.py` against the named commit, pinned profile and owned disc. Extracted base RAM SHA256 is `d819fbd41abea6537bf9ce9f4967b479ea1f6278024b9f4e018290343c0bc8d4`. Game bytes, RAM and experimental evaluators remain outside Git.
Limits: no new natural puzzle, item interaction, character/scenario, normal-save/load or savestate reversal was tested. No room-entry zero seed, current inventory inference, production parser change or completion override was applied. Production implementation and broader effect/lifetime validation remain separate work.
History:

- 2026-10-07; Codex root, GPT-6.1 Sol; traced remaining gaps, verified all owned source hashes and predicate operands, ran both private comparison modes, checked result preservation and recorded the absence of coverage gains.

## RE1-ANALYSIS-010: playthrough progress audit after interaction predicates

Status: Candidate for playthrough readiness; recorded offline comparisons and a fresh diagnostic, no new gameplay
Scope: RE1 Director's Cut NTSC-U SLUS-00551, executable SHA256 `0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6`; commits `860e905` through `f0f4102`, all 334 source variants
Environment: Python 3.14.8; existing DuckStation captures only, no emulator actions or RAM writes
Authored: 2026-10-07; Codex root; model: GPT-6.1 Sol
Basis: recorded paired comparisons, repeated gap classification, and direct inspection of the current map UI
Claim: recent shared rules have improved offline item and door coverage, but the latest interaction-predicate change has no demonstrated whole-source gain. Map coverage and natural runtime validation have not advanced with those changes. Selecting more unsupported commands without a reproduced tracking outcome risks repeating work that does not improve a playthrough.

Comparable reentry results under the unchanged Herb-before capture are below. Each denominator is 334 room-file variants, including alternate source files, not 334 independently validated playable rooms. Current-room projection counts are separate and are not used in this comparison.

| Commit | Evidence | Complete item lists | Complete door results |
| --- | --- | ---: | ---: |
| `860e905` | RE1-DOORS-004 | 271 | 287 |
| `3c7ae4b` | RE1-FLAG-003 | 275 | 287 |
| `2caa0c4` | RE1-ANALYSIS-006 | 287 | 301 |
| `0b60d9e` | RE1-DOORS-006 | 287 | 312 |
| `1d79e8a` | RE1-COLLECT-002 | 291 | 312 |
| `d1a8cf4` | RE1-COLLECT-004 | 291 | 312 |
| `f0f4102` | RE1-SCD-022 | 291 | 312 |

Evidence and interpretation:

- The comparable baseline improves by 20 complete item variants and 25 complete door variants. Current reentry figures are 87.1% and 93.4% respectively. These are source interpretation measurements under a captured flag configuration. They do not establish the percentage of the game that works during normal play.
- RE1-COLLECT-004 resolves two additional source variants under a synthetic acquired-GlobalId-27 state even though the unchanged capture has no gain. It fixes a specific acquisition-dependent result. RE1-SCD-022 preserves all tested results across seven configurations but gains no complete item or door result in any of them. Its 132 newly interpreted commands and 52 new tests therefore do not increase demonstrated playthrough coverage.
- Reran RE1-ANALYSIS-009's gap diagnostic against `f0f4102` using Herb-before RAM SHA256 `d819fbd41abea6537bf9ce9f4967b479ea1f6278024b9f4e018290343c0bc8d4`. The same 43 item gaps and 22 door gaps remain, with eight overlaps and 57 unresolved variants in total. Categories remain 51 condition/descriptor ambiguities, four reached invalid event starts and two structural source failures. No new rejected hypothesis was tested and no analysis bound was relaxed.
- `src/ui/map_view.py` still loads only the Mansion 1F floor plan, selects only `mansion1f:` visits and same-stage-0 doors, and displays an unmapped-room message elsewhere. The seven commits in the table add no mapped area. RE1-MAP-003 separately inspects whether the owned disc can supply other floor plans.
- RE1-REENTRY-004's normal-save, walked-return and reversal captures remain useful evidence. Replaying that same twelve-step sequence tests regressions; it does not add new gameplay coverage. Later-area progression and natural execution of the recently interpreted interactions remain unvalidated.
- The next candidate is a shared multi-area floor-plan system for this revision, with automatic area selection, room-entry-only reveal and the existing item/door interpretation. It addresses an observable missing part of a playthrough. Native area/region bindings and map-specific marker encodings must be checked before publication. Implementation approval has not been granted for this candidate.

Private diagnostic artifacts under `/tmp/tasks/re-map/post-interaction-inspection/`: `gaps.py`, SHA256 `5d65f3888e95586b8f36c2cdc0aaebd1afc89623d9df994d333796742cd8a0f3`; `gaps.json`, SHA256 `d591cff5c5fea5b2725d0df1de1c53258e2679fd6acb2edfc62af3755bc47a13`; `coverage-summary.json`, SHA256 `ebdf617d03f2eecf63b02198148c99542adcbdab1b91156b88df63c00f8f713f`. Run the private diagnostic with the named Python environment to reproduce classification. The historical rows retain their original attribution and artifacts in the linked finding IDs.
Limits: no end-to-end playthrough or new runtime experiment establishes overall readiness. A rough readiness estimate is a planning judgment, not a calculation from source percentages, test counts or commit counts. Production behavior and generated metadata are unchanged by this audit.
History:

- 2026-10-07; human user; requested a readiness estimate and an audit for repeated work without progress.
- 2026-10-07; Codex root, GPT-6.1 Sol; compared the same reentry epoch and unchanged capture across recorded milestones, recomputed remaining gaps, inspected the map limitation and recorded concrete work-selection criteria in project instructions. Corrected an interim user-facing comparison that mixed current and reentry counts. No earlier finding's authorship or validation state was changed.
