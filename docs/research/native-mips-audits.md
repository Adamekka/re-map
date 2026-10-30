# Copied native MIPS audits

[Documentation index](../README.md) · [Claim index](../research.md)

## MIPS-AUDIT-001: observe stores without a memory-write hook

Status: Candidate backend finding reproduced with synthetic instructions and owned RE2 native code on macOS 27.2 arm64, Python 3.14.10 and Unicorn 2.1.4. This is copied execution, not DuckStation gameplay confirmation. No DuckStation instance is started or accessed by these experiments.

### Failure and reproduction

A `UC_HOOK_MEM_WRITE` callback on a store in a JAL delay slot changes execution in this environment. The first instruction at the call target executes twice. A stack prologue therefore subtracts its frame size twice, while the epilogue restores it once. The error occurs even when the write callback reads no registers.

The synthetic program in [the regression test](../../tests/test_mips_store_audit.py) calls `0x1010` from `0x1000`, with `SW zero, 0x4000(zero)` in the delay slot. The callee subtracts and restores `0x40` from SP, then returns. These are MIPS virtual instruction/data addresses; instruction words and the stored word are four-byte little endian, mask `0xFFFFFFFF`. Expected final SP is its initial `0x3000`.

With a code hook alone, the program returns to `0x2000` with SP `0x3000`. Adding a memory-write hook that only appends address/size/value duplicates PC `0x1010` and leaves SP `0x2FC0`. Private `/tmp/re-map-mips-audit-20261030/backend-regression.json` records both traces. The earlier agent reproduction and its source remain in `/tmp/re-map-sound002-abi-20261030/backend-delay-write.py/json` and `backend-delay-no-write-hook.py/json`.

The same instrumentation fault shortened a native sound-bank initialization loop to 65 of 128 index stores. Its later driver execution appeared to enter BIOS/thread-return paths after stack corruption. Those runs are rejected evidence about the game's sound ABI. Changing CPU variants, repairing PC, or modeling RFE did not establish a faithful replacement. The corrected bank initialization completes all 128 index stores without those repairs.

### Shared audit method

[mips_store_audit.py](../../tools/mips_store_audit.py) decodes unchanged instructions from a pre-instruction code hook. It predicts the effective address, width and low stored bits of `SB`, `SH` and `SW`, including signed displacement and 32-bit address wrap. It rejects unsupported store families and unaligned halfword/word stores explicitly. It returns MIPS virtual addresses, leaving address-space conversion to the caller.

A predicted store is not proof that an instruction completed. Accept a run only after its expected return or bounded stop, check its store destinations against the claimed ownership domain, and compare the complete RAM image with the expected writes. Check same-value stores too, since a final-byte comparison alone cannot reveal them. Faulting or interrupted runs do not establish the write bound. The decoder does not implement PS1 CPU timing, devices or arbitrary memory effects.

The regression checks the completed branch-delay program's SP, return PC, exact predicted store and complete mapped-memory result. It asserts correct execution, rather than requiring a future Unicorn version to retain the bug. Other tests cover integer store widths, displacement, address wrap, zero-register semantics and explicit unsupported-store failures. Unicorn is optional for the pure decoder tests; the integration test requires it and ran in the environment above.

### Corrected RE2 replays

The revision, source identity, packet offsets and native ownership bounds live in [RE2-PUZZLE-002](re2/known-puzzle-items.md#re2-puzzle-002-source-00-12-needs-incoming-resource-and-opposite-mode-bounds). Corrected private probes use the shared decoder and no memory-write hooks:

- `/tmp/re-map-mips-audit-20261030/motion/native-object-motion.py/json` and `native-motion31.json` reproduce 560 complete native handler executions with exact two-MiB comparisons.
- `/tmp/re-map-mips-audit-20261030/bit-copy/native-bit-copy.py/json` completes 4608 synthetic Copy/flag pairs, 9216 native calls. All byte-sized bit indices, two counter high-byte settings, three flag operations and three initial words match exact full-RAM expectations.
- `/tmp/re-map-member-bounds-20261030/native-members.py/json` completes 252 scalar/predicate calls with exact full-RAM and store-list expectations. It supersedes the earlier scalar-handler exception as instrumentation evidence.
- `/tmp/re-map-mips-audit-20261030/sound-waiting/native-bank-driver-code-store.py/json` and `sound-second/native-bank-driver-code-store-second-ram.py/json` independently replay the complete source sound setup/calls/drivers over two retained initialized game RAM captures. Header relocation logs 36 stores, bank binding 216 stores, and each source sound packet 36 stores. Complete drivers log 412 stores per packet in the first capture and 356 in the second. All phases return with the original SP, complete RAM-difference coverage, no store to either mode word and no store to an executed instruction byte.

The sound probes preserve the captures' real 22-voice library state. They model only the reached GTE LZCS/LZCR transfers using the pinned official DuckStation [leading-bit calculation](https://github.com/stenzek/duckstation/blob/00e2997958d62de79d352cd680ec0c1ad95d491c/src/core/gte.cpp#L84) and [register write](https://github.com/stenzek/duckstation/blob/00e2997958d62de79d352cd680ec0c1ad95d491c/src/core/gte.cpp#L381). The privately mapped BIOS is never executed in accepted runs. SPU MMIO inputs are zero initialized; asynchronous DMA, interrupts and gameplay are outside the experiment. These samples do not establish a universal resource or room-entry contract.

### Review and attribution

On 2026-10-30, the human user requested continued RE2 improvements. The `startup_experience` agent, exact model `gpt-6.1-sol` verified through inherited authoritative runtime metadata, diagnosed the delay-slot hook fault, ran the original corrected sound probes and inspected the pinned DuckStation instruction semantics. Root, exact model `gpt-6.1-sol` from authoritative runtime metadata, reproduced the no-register-read failure, authored the shared decoder/tests, reran motion, Copy and both sound captures with that decoder, and wrote this record. The `member_bounds` agent, the same verified model, authored the corrected scalar/predicate experiments.

Direct review checked decoder arithmetic, unsupported-store failure behavior, virtual-address handling, full-RAM comparison limits, duplicated audit logic, replay completion and the distinction between copied execution and gameplay. The 25 decoder tests and 163 existing puzzle/entry/declaration tests pass. Ruff formatting/lint and whitespace checks pass. Claude Opus and Gemini Flash review providers remain disabled and returned no review. No UI or accessibility behavior changes in this increment.
