# RE2 item presence through startup setup

[Claim index](../../research.md) · [RE2 testing](../../testing/re2.md)

## RE2-STARTUP-001: setup effects and equivalent creators preserve known items

Status: Confirmed current item bindings in the existing native clipping-entry captures for Resident Evil 2 Dual Shock Ver. USA Disc 1, SLUS-00748, Leon A, Original/Normal. The shared source-based presence inference remains Candidate outside those observations. The new source walker adds no native pickup observation or memory-card persistence claim.

Executable `SLUS_007.48` SHA256 is `e576348f64d015ecff6e1ce875a8924ee252ba7f3f9478b0917cbbdeb97db441`. Source `PL0/RDT/ROOM20E0.RDT` SHA256 is `94f38aa44a170d207c7625a41e24c595da82af57ad46f9fad7383600a0e92a0e`. Native evidence uses isolated DuckStation `0.1-12083-g00e299795`, full commit `00e2997958d62de79d352cd680ec0c1ad95d491c`, with emulator identity, setup writes and exact restore recorded in [RE2-CLIP-001](clipping.md#re2-clip-001-startup-clipping-preserves-the-fixed-item-context).

### Reported failure and two causes

The visited examination/interrogation source stayed gray after departure. Its full relevant item identities were resolved, but three unacquired items still had Unknown presence. Current native entry captures already showed the four relevant pickups Available or Collected. The departed item-presence lists were empty.

The first cause was inconsistent interpretation of setup. The fixed-context proof already validated native opcode 73 at offset 6012 and bounded SCA opcode 37 at 6096, 6188 and 6266. Both item-presence walkers nevertheless treated those setup commands as unsupported. Their startup-completion checks therefore withheld every item guarantee.

The second cause affected acquisition ID 56 independently. Its equivalent creators at 6534 and 6560 occupy opposite outcomes of an opaque comparison. Proving each creator separately and then ORing the results loses the guarantee that one of them executes. The walker now groups identical acquisition ID/type goals before intersecting branch outcomes. Different IDs, item types and awards keep separate goals. It does not select a camera outcome or assume a current counter value.

### Bounded shared correction

A revision opt-in selects the exact audited setup recipe. `ScenarioItemProof` exports a source-hash-bound continuation receipt only after the existing whole-source context proof succeeds. The receipt records validated instruction locations and the physical predicate bits they preserve. A broader query cannot inherit that receipt's guarantees.

SCA validation reuses the existing shared native record/write bounds. The complete declared collision asset must be disjoint from both complete script sections, including procedure directories. Clipping reuses its existing selector, startup placement, initializer-entry, allocation and write-mask guards. Decoded instruction spans must not overlap. Unproved commands retain the existing unsupported outcome.

This recipe protects only the explicit native system/status words already covered by the clipping audit. All addresses here are PS1 virtual and little endian: system flags `0x800CFB74` and status flags `0x800CFBD8`, each unsigned four bytes. Flag bank masks use `0x80000000 >> bit`. Source offsets above are RDT byte offsets, never host addresses. A predicate alias into task, source, model or heap work requires a separate proof and receives no continuation permission here. See RE2-CLIP-001 for the exact parameter stores and deferred model-copy limits.

The two startup walkers consume the same receipt. It grants continuation through its validated setup locations, not blanket permission for an opcode, source or revision. No new runtime cache, exploration field, guessed state value or clearance exception is introduced.

### Outcomes and reproduction

Owned-CUE generation changes only source `01-0e`'s conditional presence records, adding unconditional required presence for IDs 56, 60, 110 and 199. The two ID 56 creators remain in the catalog. Earlier fixed-scenario exclusions 61/171 and all selected identities remain unchanged. Every other room field and the floor artifact are identical, apart from the top-level audit/claim declaration.

In the retained user state, the three Unknown rows become Uncollected and the room changes from Unknown to Incomplete. The already collected Small Key remains Collected. Fresh acquisition flags continue to win, and synthetic earlier/later acquisition reversals rebuild all four rows without retaining a previous completion result.

Reproduce with the pinned owned CUE and `tools/build_re2_metadata.py`, using the profile's explicit `startup_effect_audit`. Compare the generated `01-0e` records before and after opt-in. Private `clip-presence-joint-diagnosis.py/json` records the two isolated causes; `startup-item-replay.py/json` compares 23 distinct native RAM captures against commit `fcf0c03`. Nineteen Display results preserve every other room, door, position and visit. Fourteen departed publications gain the three item-presence outcomes; four accepted current source captures keep their live item results. The remaining Display image is the previously excluded camera-only geometry preparation, `clip-active-entry.ram`; it changes four Unknown rows to Uncollected in the comparison, but is explicitly labeled an excluded control rather than native acceptance evidence. Four UI-transition Retry results remain unchanged. Each Display result also matches after a separate private history close/reopen and fresh poll.

The native evidence is reused rather than relabeled as a new gameplay experiment. The full equivalent entry and exact earlier/later savestate restoration remain those documented by RE2-CLIP-001. BIOS, RDT files, raw RAM and RE2 saves remain outside Git. The agent emulator is stopped, both achievement integrations are disabled in its private configuration, and the user's released history remains untouched.

### Validation and review

The applicable full Python suite passes 3471 tests. The parallel puzzle/compiler work is excluded from this increment's test run and commit. Thirty-three dedicated startup cases cover revision opt-in, missing capability, native bounds/placement, yield and entry rejection, complete script/table exclusions, instruction overlap, physical predicate aliases, source/query binding, collective startup/scheduled goals, nonmerging different identities and the actual generated artifact. Reader regressions cover fresh acquisition reversal and history-independent reconstruction. Scoped Ruff formatting/lint and whitespace checks pass.

Desktop/mobile rendering of the retained state verifies three Remaining rows, Collected Small Key, the Incomplete room color and no overflow or browser errors. The README screenshot is refreshed. No claim is made that unrelated door conditions or the other gray rooms are resolved.

Contributions, 2026-10-28: the human user supplied the unresolved map report and requested the fix loop. Codex `metadata_diagnosis`, exact model `gpt-6.1-sol`, diagnosed both walkers, authored the shared receipts/collective goal correction and adversarial regressions. Root, the same exact model verified by authoritative T3 runtime metadata, reviewed the receipt and branch semantics, authored generator/profile integration and acquisition regressions, compared all native captures and private history round trips, checked rendering and wrote this record. Prior native clipping experiments retain their original attribution in RE2-CLIP-001. Configured external review providers remain disabled; no external endorsement is claimed.
