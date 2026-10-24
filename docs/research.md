# Research

Findings are grouped by game and topic. Each entry retains its own status, revision, evidence and attribution. Earlier source-only notes do not override later runtime observations.

## Original emulator source investigation

| Claim | Finding |
| --- | --- |
| <a id="research-external-ps1-ram-access-from-duckstation-on-macos"></a>[Original investigation](research/emulator-source.md#research-external-ps1-ram-access-from-duckstation-on-macos) | Original emulator source investigation |
| <a id="ranked-options-for-10-30-hz-external-polling"></a><a id="1-built-in-gdb-remote-server-over-tcp-loopback-most-maintainable"></a><a id="2-savestate-files-plus-a-small-diff-tool-best-for-reverse-engineering"></a><a id="3-host-process-memory-reading-emuhook-style-fast-but-brittle"></a><a id="explicitly-not-recommended-yet"></a>[Ranked options for 10-30 Hz external polling](research/emulator-source.md#ranked-options-for-10-30-hz-external-polling) | Original emulator source investigation |
| <a id="re1-emu-001-gdb-server-exposes-ram-reads-and-writes-over-tcp"></a>[RE1-EMU-001](research/emulator-source.md#re1-emu-001-gdb-server-exposes-ram-reads-and-writes-over-tcp) | GDB server exposes RAM reads and writes over TCP |
| <a id="re1-emu-002-shared-memory-export-and-exported-ram-symbols"></a>[RE1-EMU-002](research/emulator-source.md#re1-emu-002-shared-memory-export-and-exported-ram-symbols) | shared memory export and exported RAM symbols |
| <a id="re1-emu-003-direct-process-memory-reading-and-emuhook-precedent"></a>[RE1-EMU-003](research/emulator-source.md#re1-emu-003-direct-process-memory-reading-and-emuhook-precedent) | direct process memory reading and EmuHook precedent |
| <a id="re1-emu-004-savestate-format-wraps-ram-in-a-compressed-framed-file"></a>[RE1-EMU-004](research/emulator-source.md#re1-emu-004-savestate-format-wraps-ram-in-a-compressed-framed-file) | savestate format wraps RAM in a compressed framed file |
| <a id="re1-emu-005-integrated-debugger-and-memory-views-are-in-process-only"></a>[RE1-EMU-005](research/emulator-source.md#re1-emu-005-integrated-debugger-and-memory-views-are-in-process-only) | integrated debugger and memory views are in-process only |
| <a id="re1-emu-006-no-http-pipe-or-scripting-api-found"></a>[RE1-EMU-006](research/emulator-source.md#re1-emu-006-no-http-pipe-or-scripting-api-found) | no HTTP, pipe, or scripting API found |
| <a id="what-was-not-verified"></a>[What was not verified](research/emulator-source.md#what-was-not-verified) | Original emulator source investigation |
| <a id="suggested-next-experiments"></a>[Suggested next experiments](research/emulator-source.md#suggested-next-experiments) | Original emulator source investigation |

## Emulator access and agent test setup

| Claim | Finding |
| --- | --- |
| <a id="local-baseline-2026-09-22"></a>[Local baseline 2026-09-22](research/emulator-runtime.md#local-baseline-2026-09-22) | Emulator access and agent test setup |
| <a id="re1-cheat-001-third-party-anchors-no-room-or-pickup-flag"></a>[RE1-CHEAT-001](research/emulator-runtime.md#re1-cheat-001-third-party-anchors-no-room-or-pickup-flag) | third-party anchors, no room or pickup flag |
| <a id="re1-auto-001-automated-boot-and-gdb-without-manual-play-is-feasible"></a>[RE1-AUTO-001](research/emulator-runtime.md#re1-auto-001-automated-boot-and-gdb-without-manual-play-is-feasible) | automated boot and GDB without manual play is feasible |
| <a id="re1-cheat-002-gamehacking-directors-cut-set-has-no-room-codes"></a>[RE1-CHEAT-002](research/emulator-runtime.md#re1-cheat-002-gamehacking-directors-cut-set-has-no-room-codes) | GameHacking Director's Cut set has no room codes |
| <a id="re1-emu-007-asynchronous-gdb-stops-must-not-complete-memory-reads"></a>[RE1-EMU-007](research/emulator-runtime.md#re1-emu-007-asynchronous-gdb-stops-must-not-complete-memory-reads) | asynchronous GDB stops must not complete memory reads |
| <a id="re1-emu-008-native-write-watch-stops-and-single-step-framing"></a>[RE1-EMU-008](research/emulator-runtime.md#re1-emu-008-native-write-watch-stops-and-single-step-framing) | native write-watch stops and single-step framing |
| <a id="re1-cheat-003-temporary-health-lock-for-isolated-map-validation"></a>[RE1-CHEAT-003](research/emulator-runtime.md#re1-cheat-003-temporary-health-lock-for-isolated-map-validation) | temporary health lock for isolated map validation |
| <a id="re1-cheat-004-bundled-invincibility-patch-does-not-match-the-pinned-executable"></a>[RE1-CHEAT-004](research/emulator-runtime.md#re1-cheat-004-bundled-invincibility-patch-does-not-match-the-pinned-executable) | bundled Invincibility patch does not match the pinned executable |
| <a id="re1-emu-009-gameplay-endurance-and-reconnect-recovery"></a>[RE1-EMU-009](research/emulator-runtime.md#re1-emu-009-gameplay-endurance-and-reconnect-recovery) | gameplay endurance and reconnect recovery |

## RE1 room sources research

| Claim | Finding |
| --- | --- |
| <a id="re1-rdt-001-static-room-and-item-data-is-parseable-pickup-flag-mapping-is-not"></a>[RE1-RDT-001](research/re1/room-sources.md#re1-rdt-001-static-room-and-item-data-is-parseable-pickup-flag-mapping-is-not) | static room and item data is parseable, pickup flag mapping is not |
| <a id="re1-disc-001-local-directors-cut-disc-identity"></a>[RE1-DISC-001](research/re1/room-sources.md#re1-disc-001-local-directors-cut-disc-identity) | local Director's Cut disc identity |
| <a id="re1-static-001-rdt-enumeration-without-booting-is-feasible"></a>[RE1-STATIC-001](research/re1/room-sources.md#re1-static-001-rdt-enumeration-without-booting-is-feasible) | RDT enumeration without booting is feasible |
| <a id="re1-usermap-001-retroachievements-code-notes-as-the-candidate-feed"></a>[RE1-USERMAP-001](research/re1/room-sources.md#re1-usermap-001-retroachievements-code-notes-as-the-candidate-feed) | RetroAchievements code notes as the candidate feed |
| <a id="re1-static-002-335-rdt-files-listed-from-slus-00551-without-extraction"></a>[RE1-STATIC-002](research/re1/room-sources.md#re1-static-002-335-rdt-files-listed-from-slus-00551-without-extraction) | 335 RDT files listed from SLUS-00551 without extraction |
| <a id="re1-row-001-first-room-to-item-row-for-art-room-with-offline-end-to-end-run"></a>[RE1-ROW-001](research/re1/room-sources.md#re1-row-001-first-room-to-item-row-for-art-room-with-offline-end-to-end-run) | first room to item row for Art Room with offline end to end run |
| <a id="re1-table-001-partial-initmain-item-scan-across-335-rdts"></a>[RE1-TABLE-001](research/re1/room-sources.md#re1-table-001-partial-initmain-item-scan-across-335-rdts) | partial init/main item scan across 335 RDTs |
| <a id="re1-link-001-filename-rule-holds-for-87-of-90-stage-0-doors"></a>[RE1-LINK-001](research/re1/room-sources.md#re1-link-001-filename-rule-holds-for-87-of-90-stage-0-doors) | filename rule holds for 87 of 90 stage 0 doors |
| <a id="re1-room-001-room-change-art-room-to-main-hall-observed-live"></a>[RE1-ROOM-001](research/re1/room-sources.md#re1-room-001-room-change-art-room-to-main-hall-observed-live) | room change Art Room to Main Hall observed live |
| <a id="re1-milestone-001-first-milestone-complete-on-slus-00551-art-room"></a>[RE1-MILESTONE-001](research/re1/room-sources.md#re1-milestone-001-first-milestone-complete-on-slus-00551-art-room) | first milestone complete on SLUS-00551 Art Room |
| <a id="re1-rdt-002-re1-item-opcode-stores-globalid-at-byte-22"></a>[RE1-RDT-002](research/re1/room-sources.md#re1-rdt-002-re1-item-opcode-stores-globalid-at-byte-22) | RE1 item opcode stores GlobalId at byte 22 |

## RE1 runtime state research

| Claim | Finding |
| --- | --- |
| <a id="re1-runtime-001-room-bytes-live-on-slus-00551-cli-extraction-works"></a>[RE1-RUNTIME-001](research/re1/runtime-state.md#re1-runtime-001-room-bytes-live-on-slus-00551-cli-extraction-works) | room bytes live on SLUS-00551, CLI extraction works |
| <a id="re1-stage-001-room-file-folder-selector-for-base-and-alternate-areas"></a>[RE1-STAGE-001](research/re1/runtime-state.md#re1-stage-001-room-file-folder-selector-for-base-and-alternate-areas) | room-file folder selector for base and alternate areas |
| <a id="re1-variant-001-two-runtime-rooms-load-suffix-1-rdt-files"></a>[RE1-VARIANT-001](research/re1/runtime-state.md#re1-variant-001-two-runtime-rooms-load-suffix-1-rdt-files) | two runtime rooms load suffix-1 RDT files |
| <a id="re1-variant-002-stage-0-rdt-loader-uses-a-per-room-selector-and-flag-bit"></a>[RE1-VARIANT-002](research/re1/runtime-state.md#re1-variant-002-stage-0-rdt-loader-uses-a-per-room-selector-and-flag-bit) | Stage 0 RDT loader uses a per-room selector and flag bit |
| <a id="re1-cache-001-source-dependencies-bound-prior-room-manifest-reuse"></a>[RE1-CACHE-001](research/re1/runtime-state.md#re1-cache-001-source-dependencies-bound-prior-room-manifest-reuse) | source dependencies bound prior-room manifest reuse |
| <a id="re1-source-001-room-initialization-and-quantity-transfer-mutate-source-bytes"></a>[RE1-SOURCE-001](research/re1/runtime-state.md#re1-source-001-room-initialization-and-quantity-transfer-mutate-source-bytes) | room initialization and quantity transfer mutate source bytes |
| <a id="re1-cache-002-indexed-event-analysis-permits-guarded-mansion-item-cache-reuse"></a>[RE1-CACHE-002](research/re1/runtime-state.md#re1-cache-002-indexed-event-analysis-permits-guarded-mansion-item-cache-reuse) | indexed event analysis permits guarded Mansion item-cache reuse |
| <a id="re1-cache-003-nested-predicate-lifetimes-and-transitive-source-guards"></a>[RE1-CACHE-003](research/re1/runtime-state.md#re1-cache-003-nested-predicate-lifetimes-and-transitive-source-guards) | nested predicate lifetimes and transitive source guards |
| <a id="re1-load-001-room-loader-executes-init-synchronously-before-returning"></a>[RE1-LOAD-001](research/re1/runtime-state.md#re1-load-001-room-loader-executes-init-synchronously-before-returning) | room loader executes init synchronously before returning |
| <a id="re1-source-002-indexed-event-relocation-belongs-in-loaded-source-identity"></a>[RE1-SOURCE-002](research/re1/runtime-state.md#re1-source-002-indexed-event-relocation-belongs-in-loaded-source-identity) | indexed-event relocation belongs in loaded source identity |
| <a id="re1-select-001-complete-source-choices-for-supported-logical-rooms"></a>[RE1-SELECT-001](research/re1/runtime-state.md#re1-select-001-complete-source-choices-for-supported-logical-rooms) | complete source choices for supported logical rooms |
| <a id="re1-source-003-native-event-relocation-wraps-at-32-bits"></a>[RE1-SOURCE-003](research/re1/runtime-state.md#re1-source-003-native-event-relocation-wraps-at-32-bits) | native event relocation wraps at 32 bits |
| <a id="re1-lifecycle-001-attract-mode-playback-records-false-playthrough-visits"></a>[RE1-LIFECYCLE-001](research/re1/runtime-state.md#re1-lifecycle-001-attract-mode-playback-records-false-playthrough-visits) | attract-mode playback records false playthrough visits |
| <a id="re1-lifecycle-002-lifecycle-byte-gates-visit-recording"></a>[RE1-LIFECYCLE-002](research/re1/runtime-state.md#re1-lifecycle-002-lifecycle-byte-gates-visit-recording) | lifecycle byte gates visit recording |
| <a id="re1-lifecycle-003-gate-holds-through-continuous-attract-playback"></a>[RE1-LIFECYCLE-003](research/re1/runtime-state.md#re1-lifecycle-003-gate-holds-through-continuous-attract-playback) | gate holds through continuous attract playback |

## RE1 collectibles research

| Claim | Finding |
| --- | --- |
| <a id="re1-pickup-001-art-room-map-bit-differs-between-backup-and-slot-saves"></a>[RE1-PICKUP-001](research/re1/collectibles.md#re1-pickup-001-art-room-map-bit-differs-between-backup-and-slot-saves) | Art Room map bit differs between backup and slot saves |
| <a id="re1-pickup-002-controlled-green-herb-take-confirms-polarity-and-flag"></a>[RE1-PICKUP-002](research/re1/collectibles.md#re1-pickup-002-controlled-green-herb-take-confirms-polarity-and-flag) | controlled green herb take confirms polarity and flag |
| <a id="re1-pickup-003-controlled-chemical-take-confirms-second-flag"></a>[RE1-PICKUP-003](research/re1/collectibles.md#re1-pickup-003-controlled-chemical-take-confirms-second-flag) | controlled chemical take confirms second flag |
| <a id="re1-flag-001-opcode-0x18-globalid-selects-an-item-flag-bit"></a>[RE1-FLAG-001](research/re1/collectibles.md#re1-flag-001-opcode-0x18-globalid-selects-an-item-flag-bit) | opcode 0x18 GlobalId selects an item flag bit |
| <a id="re1-aot-001-item-object-state-is-a-handler-index-not-an-availability-bit"></a>[RE1-AOT-001](research/re1/collectibles.md#re1-aot-001-item-object-state-is-a-handler-index-not-an-availability-bit) | item object state is a handler index, not an availability bit |
| <a id="re1-aot-002-interaction-scans-use-a-dynamic-item-object-bound"></a>[RE1-AOT-002](research/re1/collectibles.md#re1-aot-002-interaction-scans-use-a-dynamic-item-object-bound) | interaction scans use a dynamic item-object bound |
| <a id="re1-collect-001-confirmation-can-delegate-a-collectible-award-to-a-child-event"></a>[RE1-COLLECT-001](research/re1/collectibles.md#re1-collect-001-confirmation-can-delegate-a-collectible-award-to-a-child-event) | confirmation can delegate a collectible award to a child event |
| <a id="re1-flag-002-alternate-pickup-acquisition-needs-an-explicit-flag-rule"></a>[RE1-FLAG-002](research/re1/collectibles.md#re1-flag-002-alternate-pickup-acquisition-needs-an-explicit-flag-rule) | alternate pickup acquisition needs an explicit flag rule |
| <a id="re1-flag-003-shared-acquisition-rules-preserve-separate-activation-and-fresh-ownership"></a>[RE1-FLAG-003](research/re1/collectibles.md#re1-flag-003-shared-acquisition-rules-preserve-separate-activation-and-fresh-ownership) | shared acquisition rules preserve separate activation and fresh ownership |
| [RE1-CLEAR-006](research/re1/collectibles.md#re1-clear-006-player-placed-replacements-are-not-room-rewards) | placed emblems, Broken Shotgun and Room 003 Red Book do not add room rewards; original pickups remain required |
| [RE1-CLEAR-007](research/re1/collectibles.md#re1-clear-007-permanently-disabled-initializer-items-are-not-puzzle-rewards) | permanently disabled initializer items are not puzzle rewards; Jill Meeting Room Small Key |
| <a id="re1-pickup-004-controlled-art-room-map-acquisition-and-reversal"></a>[RE1-PICKUP-004](research/re1/collectibles.md#re1-pickup-004-controlled-art-room-map-acquisition-and-reversal) | controlled Art Room map acquisition and reversal |
| <a id="re1-quantity-001-shared-quantity-uncertainty-no-longer-invalidates-a-known-pickup"></a>[RE1-QUANTITY-001](research/re1/collectibles.md#re1-quantity-001-shared-quantity-uncertainty-no-longer-invalidates-a-known-pickup) | shared quantity uncertainty no longer invalidates a known pickup |
| <a id="re1-aot-003-disabling-a-registry-handler-does-not-dereference-its-retained-source"></a>[RE1-AOT-003](research/re1/collectibles.md#re1-aot-003-disabling-a-registry-handler-does-not-dereference-its-retained-source) | disabling a registry handler does not dereference its retained source |
| <a id="re1-aot-004-shared-disabling-preserves-stale-source-rejection-and-fresh-load-results"></a>[RE1-AOT-004](research/re1/collectibles.md#re1-aot-004-shared-disabling-preserves-stale-source-rejection-and-fresh-load-results) | shared disabling preserves stale-source rejection and fresh load results |
| <a id="re1-quantity-002-transfer-writes-preserve-item-identity-and-collection-is-independent-of-amount"></a>[RE1-QUANTITY-002](research/re1/collectibles.md#re1-quantity-002-transfer-writes-preserve-item-identity-and-collection-is-independent-of-amount) | transfer writes preserve item identity and collection is independent of amount |
| <a id="re1-collect-002-shared-proofs-recognize-bounded-scripted-collectible-access"></a>[RE1-COLLECT-002](research/re1/collectibles.md#re1-collect-002-shared-proofs-recognize-bounded-scripted-collectible-access) | shared proofs recognize bounded scripted collectible access |
| <a id="re1-collect-003-acquired-scripted-items-need-no-new-access-proof"></a>[RE1-COLLECT-003](research/re1/collectibles.md#re1-collect-003-acquired-scripted-items-need-no-new-access-proof) | acquired scripted items need no new access proof |
| <a id="re1-collect-004-live-and-cached-scripted-items-recognize-fresh-acquisition-first"></a>[RE1-COLLECT-004](research/re1/collectibles.md#re1-collect-004-live-and-cached-scripted-items-recognize-fresh-acquisition-first) | live and cached scripted items recognize fresh acquisition first |
| <a id="re1-pickup-005-terrace-scripted-bazooka-grant-clears-its-acquisition-bit"></a>[RE1-PICKUP-005](research/re1/collectibles.md#re1-pickup-005-terrace-scripted-bazooka-grant-clears-its-acquisition-bit) | Terrace scripted Bazooka grant clears its acquisition bit |
| <a id="re1-pickup-006-power-room-battery-clears-its-calculated-acquisition-bit"></a>[RE1-PICKUP-006](research/re1/collectibles.md#re1-pickup-006-power-room-battery-clears-its-calculated-acquisition-bit) | Power Room Battery clears its calculated acquisition bit |

## RE1 doors research

| Claim | Finding |
| --- | --- |
| <a id="re1-doors-001-782-door-edges-plus-filename-rule-for-runtime-linkage"></a>[RE1-DOORS-001](research/re1/doors.md#re1-doors-001-782-door-edges-plus-filename-rule-for-runtime-linkage) | 782 door edges plus filename rule for runtime linkage |
| <a id="re1-doors-002-active-door_set-records-expose-directional-lock-state"></a>[RE1-DOORS-002](research/re1/doors.md#re1-doors-002-active-door_set-records-expose-directional-lock-state) | active Door_set records expose directional lock state |
| <a id="re1-doors-003-message-handlers-retain-door-identity-without-requesting-passage"></a>[RE1-DOORS-003](research/re1/doors.md#re1-doors-003-message-handlers-retain-door-identity-without-requesting-passage) | message handlers retain door identity without requesting passage |
| <a id="re1-doors-004-validated-message-doors-publish-blocked-access-in-both-tracking-paths"></a>[RE1-DOORS-004](research/re1/doors.md#re1-doors-004-validated-message-doors-publish-blocked-access-in-both-tracking-paths) | validated message doors publish blocked access in both tracking paths |
| <a id="re1-doors-005-scripted-door-interactions-need-a-delegated-access-rule"></a>[RE1-DOORS-005](research/re1/doors.md#re1-doors-005-scripted-door-interactions-need-a-delegated-access-rule) | scripted door interactions need a delegated access rule |
| <a id="re1-doors-006-bounded-scripted-door-rules-share-ordinary-lock-interpretation"></a>[RE1-DOORS-006](research/re1/doors.md#re1-doors-006-bounded-scripted-door-rules-share-ordinary-lock-interpretation) | bounded scripted-door rules share ordinary lock interpretation |
| <a id="re1-doors-007-native-unlock-and-earlier-savestate-restore-reevaluate-a-library-door"></a>[RE1-DOORS-007](research/re1/doors.md#re1-doors-007-native-unlock-and-earlier-savestate-restore-reevaluate-a-library-door) | native unlock and earlier savestate restore reevaluate a Library door |
| <a id="re1-doors-008-laboratory-elevator-refusal-and-two-native-power-switches"></a>[RE1-DOORS-008](research/re1/doors.md#re1-doors-008-laboratory-elevator-refusal-and-two-native-power-switches) | Laboratory elevator refusal and two native power switches |
| <a id="re1-doors-009-returned-mansion-kitchen-exits-publish-wrong-stage-ids"></a>[RE1-DOORS-009](research/re1/doors.md#re1-doors-009-returned-mansion-kitchen-exits-publish-wrong-stage-ids) | returned-Mansion Kitchen exits publish wrong stage IDs |
| <a id="re1-doors-010-shared-door-target-rule-remaps-stage-01-to-56-when-the-story-flag-is-set"></a>[RE1-DOORS-010](research/re1/doors.md#re1-doors-010-shared-door-target-rule-remaps-stage-01-to-56-when-the-story-flag-is-set) | shared door target rule remaps stage 0/1 to 5/6 when the story flag is set |
| <a id="re1-doors-011-courtyard-store-room-door-resolves-under-the-remap-rule-with-no-variant-regressions"></a>[RE1-DOORS-011](research/re1/doors.md#re1-doors-011-courtyard-store-room-door-resolves-under-the-remap-rule-with-no-variant-regressions) | Courtyard store-room door resolves under the remap rule with no variant regressions |
| <a id="re1-doors-012-all-recorded-capture-door-sweep-shows-no-unknown-targets-under-the-remap-rule"></a>[RE1-DOORS-012](research/re1/doors.md#re1-doors-012-all-recorded-capture-door-sweep-shows-no-unknown-targets-under-the-remap-rule) | all-recorded-capture door sweep shows no unknown targets under the remap rule |
| <a id="re1-doors-013-committed-offline-door-projection-guards-the-remap-rule"></a>[RE1-DOORS-013](research/re1/doors.md#re1-doors-013-committed-offline-door-projection-guards-the-remap-rule) | committed offline door projection guards the remap rule |

## RE1 reconstruction research

| Claim | Finding |
| --- | --- |
| <a id="re1-join-001-ra-flags-joined-to-rdt-rooms-15-of-24-placed"></a>[RE1-JOIN-001](research/re1/reconstruction.md#re1-join-001-ra-flags-joined-to-rdt-rooms-15-of-24-placed) | RA flags joined to RDT rooms, 15 of 24 placed |
| <a id="re1-spawn-001-room-scripts-conditionally-create-item-objects"></a>[RE1-SPAWN-001](research/re1/reconstruction.md#re1-spawn-001-room-scripts-conditionally-create-item-objects) | room scripts conditionally create item objects |
| <a id="re1-reentry-001-the-taken-herb-flag-remains-cleared-after-a-reported-room-return"></a>[RE1-REENTRY-001](research/re1/reconstruction.md#re1-reentry-001-the-taken-herb-flag-remains-cleared-after-a-reported-room-return) | the taken Herb flag remains cleared after a reported room return |
| <a id="re1-avail-001-three-main-hall-item-rows-are-skipped-in-the-captured-state"></a>[RE1-AVAIL-001](research/re1/reconstruction.md#re1-avail-001-three-main-hall-item-rows-are-skipped-in-the-captured-state) | three Main Hall item rows are skipped in the captured state |
| <a id="re1-cover-001-tested-chemical-branch-reaches-one-normal-item-row"></a>[RE1-COVER-001](research/re1/reconstruction.md#re1-cover-001-tested-chemical-branch-reaches-one-normal-item-row) | tested Chemical branch reaches one normal item row |
| <a id="re1-branch-001-normal-load-can-set-the-storeroom-item-branch-bit"></a>[RE1-BRANCH-001](research/re1/reconstruction.md#re1-branch-001-normal-load-can-set-the-storeroom-item-branch-bit) | normal load can set the Storeroom item branch bit |
| <a id="re1-reentry-005-failed-scripts-block-reconstruction-only-when-reachable"></a>[RE1-REENTRY-005](research/re1/reconstruction.md#re1-reentry-005-failed-scripts-block-reconstruction-only-when-reachable) | failed scripts block reconstruction only when reachable |
| <a id="re1-cover-002-bounded-registered-room-pickups-and-deferred-awards"></a>[RE1-COVER-002](research/re1/reconstruction.md#re1-cover-002-bounded-registered-room-pickups-and-deferred-awards) | bounded registered room pickups and deferred awards |
| <a id="re1-cover-003-bounded-native-overlay-inventory-audit"></a>[RE1-COVER-003](research/re1/reconstruction.md#re1-cover-003-bounded-native-overlay-inventory-audit) | bounded native overlay inventory audit |
| <a id="re1-live-002-floor-plan-item-and-door-integration-checks"></a>[RE1-LIVE-002](research/re1/reconstruction.md#re1-live-002-floor-plan-item-and-door-integration-checks) | floor-plan, item and door integration checks |
| <a id="re1-engine-001-shared-reconstruction-of-entered-rooms-from-scripts-and-fresh-flags"></a>[RE1-ENGINE-001](research/re1/reconstruction.md#re1-engine-001-shared-reconstruction-of-entered-rooms-from-scripts-and-fresh-flags) | shared reconstruction of entered rooms from scripts and fresh flags |
| <a id="re1-engine-002-recurring-scripts-and-possible-event-histories-share-itemdoor-rules"></a>[RE1-ENGINE-002](research/re1/reconstruction.md#re1-engine-002-recurring-scripts-and-possible-event-histories-share-itemdoor-rules) | recurring scripts and possible event histories share item/door rules |
| <a id="re1-vars-001-byte-and-word-commands-share-physical-shadow-bits"></a>[RE1-VARS-001](research/re1/reconstruction.md#re1-vars-001-byte-and-word-commands-share-physical-shadow-bits) | byte and word commands share physical shadow bits |
| <a id="re1-clear-001-main-halls-typewriter-slot-blocks-completion-after-ribbon-acquisition"></a>[RE1-CLEAR-001](research/re1/reconstruction.md#re1-clear-001-main-halls-typewriter-slot-blocks-completion-after-ribbon-acquisition) | Main Hall's typewriter slot blocks completion after ribbon acquisition |
| <a id="re1-clear-002-explicit-live-noncollectible-evidence-resolves-current-room-slot-uncertainty"></a>[RE1-CLEAR-002](research/re1/reconstruction.md#re1-clear-002-explicit-live-noncollectible-evidence-resolves-current-room-slot-uncertainty) | explicit live noncollectible evidence resolves current-room slot uncertainty |
| <a id="re1-clear-003-normal-main-hall-departure-loses-coverage-with-acquisition-unchanged"></a>[RE1-CLEAR-003](research/re1/reconstruction.md#re1-clear-003-normal-main-hall-departure-loses-coverage-with-acquisition-unchanged) | normal Main Hall departure loses coverage with acquisition unchanged |
| <a id="re1-clear-004-source-proofs-recognize-overwritten-dormant-item-records"></a>[RE1-CLEAR-004](research/re1/dormant-items.md#re1-clear-004-source-proofs-recognize-overwritten-dormant-item-records) | superseded registry-proof prototype; replaced by RE1-CLEAR-005 collection policy |
| <a id="re1-clear-005-known-puzzle-rewards-remain-until-collected"></a>[RE1-CLEAR-005](research/re1/dormant-items.md#re1-clear-005-known-puzzle-rewards-remain-until-collected) | known puzzle rewards keep current and departed rooms incomplete until acquired; controlled flag reversal |
| <a id="re1-reentry-004-shared-fresh-entry-reconstruction-preserves-tested-departed-room-clearance"></a>[RE1-REENTRY-004](research/re1/reconstruction.md#re1-reentry-004-shared-fresh-entry-reconstruction-preserves-tested-departed-room-clearance) | shared fresh-entry reconstruction preserves tested departed-room clearance |
| <a id="re1-reentry-002-display-request-has-a-transient-control-and-scalar-alias-footprint"></a>[RE1-REENTRY-002](research/re1/reconstruction.md#re1-reentry-002-display-request-has-a-transient-control-and-scalar-alias-footprint) | display request has a transient control and scalar-alias footprint |
| <a id="re1-reentry-003-registry-setup-retains-source-pointers-behind-cleared-handlers"></a>[RE1-REENTRY-003](research/re1/reconstruction.md#re1-reentry-003-registry-setup-retains-source-pointers-behind-cleared-handlers) | registry setup retains source pointers behind cleared handlers |

## RE1 native map geometry

| Claim | Finding |
| --- | --- |
| <a id="re1-visit-001-game-visited-bits-decode-into-room-lists"></a>[RE1-VISIT-001](research/re1/map-geometry.md#re1-visit-001-game-visited-bits-decode-into-room-lists) | game visited bits decode into room lists |
| <a id="re1-map-001-mansion-1f-topology-from-doors-mutually-consistent"></a>[RE1-MAP-001](research/re1/map-geometry.md#re1-map-001-mansion-1f-topology-from-doors-mutually-consistent) | Mansion 1F topology from doors, mutually consistent |
| <a id="re1-map-002-numeric-mansion-1f-floor-plan-from-indexed-room-regions"></a>[RE1-MAP-002](research/re1/map-geometry.md#re1-map-002-numeric-mansion-1f-floor-plan-from-indexed-room-regions) | numeric Mansion 1F floor plan from indexed room regions |
| <a id="re1-map-003-other-disc-map-files-expose-limits-of-the-mansion-only-extractor"></a>[RE1-MAP-003](research/re1/map-geometry.md#re1-map-003-other-disc-map-files-expose-limits-of-the-mansion-only-extractor) | other disc map files expose limits of the Mansion-only extractor |
| <a id="re1-map-004-native-floor-selection-depends-on-main-sub-and-camera"></a>[RE1-MAP-004](research/re1/map-geometry.md#re1-map-004-native-floor-selection-depends-on-main-sub-and-camera) | native floor selection depends on Main, Sub and camera |
| <a id="re1-map-005-eleven-numeric-floor-plans-contain-paired-full-and-boundary-door-markers"></a>[RE1-MAP-005](research/re1/map-geometry.md#re1-map-005-eleven-numeric-floor-plans-contain-paired-full-and-boundary-door-markers) | eleven numeric floor plans contain paired, full and boundary door markers |
| <a id="re1-map-006-shared-map-publication-switches-floors-and-reveals-only-entered-regions"></a>[RE1-MAP-006](research/re1/map-geometry.md#re1-map-006-shared-map-publication-switches-floors-and-reveals-only-entered-regions) | shared map publication switches floors and reveals only entered regions |

## RE1 map controls, facing and door symbols

| Claim | Finding |
| --- | --- |
| <a id="re1-player-001-player-position-and-facing-next-to-health"></a>[RE1-PLAYER-001](research/re1/map-ui.md#re1-player-001-player-position-and-facing-next-to-health) | player position and facing next to health |
| <a id="re1-map-018-door-markers-share-the-floor-layouts-stage-identity"></a>[RE1-MAP-018](research/re1/map-ui.md#re1-map-018-door-markers-share-the-floor-layouts-stage-identity) | door markers share the floor layout's stage identity |
| <a id="re1-map-019-retain-native-interior-map-geometry"></a>[RE1-MAP-019](research/re1/map-ui.md#re1-map-019-retain-native-interior-map-geometry) | retain native interior map geometry |
| <a id="re1-player-002-live-yaw-and-a-directional-room-marker"></a>[RE1-PLAYER-002](research/re1/map-ui.md#re1-player-002-live-yaw-and-a-directional-room-marker) | live yaw and a directional room marker |
| <a id="re1-map-020-name-the-unresolved-room-color-in-the-map-legend"></a>[RE1-MAP-020](research/re1/map-ui.md#re1-map-020-name-the-unresolved-room-color-in-the-map-legend) | name the unresolved room color in the map legend |
| [RE1-MAP-021](research/re1/map-ui.md#re1-map-021-matching-access-survives-different-descriptions-on-opposite-sides) | matching access survives different descriptions on opposite sides |
| [RE1-MAP-022](research/re1/map-ui.md#re1-map-022-remove-a-key-symbol-after-fresh-unlock-proof) | remove a key symbol after fresh unlock proof |
| [RE1-MAP-023](research/re1/map-ui.md#re1-map-023-follow-player-explicitly-resumes-room-selection) | follow player explicitly resumes room selection |
| [RE1-MAP-024](research/re1/map-ui.md#re1-map-024-retain-the-native-ladder-shade) | retain the native ladder shade, including Room 002 |

## RE1 approximate player position

| Claim | Finding |
| --- | --- |
| [RE1-PLAYER-003](research/re1/player-position.md#re1-player-003-room-local-coordinates-drive-an-explicitly-approximate-marker) | room-local coordinates drive an explicitly approximate marker |

## RE1 script opcodes research

| Claim | Finding |
| --- | --- |
| <a id="re1-scd-001-two-scanner-opcode-widths-disagree-with-the-executable"></a>[RE1-SCD-001](research/re1/script-opcodes.md#re1-scd-001-two-scanner-opcode-widths-disagree-with-the-executable) | two scanner opcode widths disagree with the executable |
| <a id="re1-scd-002-an-apparent-winding-passage-item-follows-script-termination"></a>[RE1-SCD-002](research/re1/script-opcodes.md#re1-scd-002-an-apparent-winding-passage-item-follows-script-termination) | an apparent Winding Passage item follows script termination |
| <a id="re1-scd-003-branch-aware-scan-of-ordinary-room-procedures"></a>[RE1-SCD-003](research/re1/script-opcodes.md#re1-scd-003-branch-aware-scan-of-ordinary-room-procedures) | branch-aware scan of ordinary room procedures |
| <a id="re1-scd-004-object-initializer-is-28-bytes-in-slus-00551"></a>[RE1-SCD-004](research/re1/script-opcodes.md#re1-scd-004-object-initializer-is-28-bytes-in-slus-00551) | object initializer is 28 bytes in SLUS-00551 |
| <a id="re1-scd-005-pinned-variable-command-widths-and-operand-free-block-end"></a>[RE1-SCD-005](research/re1/script-opcodes.md#re1-scd-005-pinned-variable-command-widths-and-operand-free-block-end) | pinned variable command widths and operand-free block end |
| <a id="re1-scd-006-operand-free-script-ends-allow-adjacent-dining-room-branch-targets"></a>[RE1-SCD-006](research/re1/script-opcodes.md#re1-scd-006-operand-free-script-ends-allow-adjacent-dining-room-branch-targets) | operand-free script ends allow adjacent Dining Room branch targets |
| <a id="re1-scd-007-native-command-results-and-effects-govern-shared-reconstruction"></a>[RE1-SCD-007](research/re1/script-opcodes.md#re1-scd-007-native-command-results-and-effects-govern-shared-reconstruction) | native command results and effects govern shared reconstruction |
| <a id="re1-scd-008-complete-native-dispatch-audit-separates-pc-advance-and-read-bounds"></a>[RE1-SCD-008](research/re1/script-opcodes.md#re1-scd-008-complete-native-dispatch-audit-separates-pc-advance-and-read-bounds) | complete native dispatch audit separates PC advance and read bounds |
| <a id="shared-command-effect-audit-re1-scd-009-through-re1-scd-014"></a><a id="shared-command-effect-generation-and-regression-audit"></a>[Shared command-effect audit, RE1-SCD-009 through RE1-SCD-014](research/re1/script-opcodes.md#shared-command-effect-audit-re1-scd-009-through-re1-scd-014) | RE1 script opcodes research |
| <a id="re1-scd-009-light-setup-continues-without-changing-tracked-state"></a>[RE1-SCD-009](research/re1/script-opcodes.md#re1-scd-009-light-setup-continues-without-changing-tracked-state) | light setup continues without changing tracked state |
| <a id="re1-scd-010-particle-clear-zeros-only-the-overlapping-header-halfword"></a>[RE1-SCD-010](research/re1/script-opcodes.md#re1-scd-010-particle-clear-zeros-only-the-overlapping-header-halfword) | particle clear zeros only the overlapping header halfword |
| <a id="re1-scd-011-movie-setup-establishes-control-word-bit-17"></a>[RE1-SCD-011](research/re1/script-opcodes.md#re1-scd-011-movie-setup-establishes-control-word-bit-17) | movie setup establishes control-word bit 17 |
| <a id="re1-scd-012-inventory-removal-has-two-outcomes-and-can-invalidate-scalar-aliases"></a>[RE1-SCD-012](research/re1/script-opcodes.md#re1-scd-012-inventory-removal-has-two-outcomes-and-can-invalidate-scalar-aliases) | inventory removal has two outcomes and can invalidate scalar aliases |
| <a id="re1-scd-013-forced-document-callbacks-conditionally-set-pending-bit-8"></a>[RE1-SCD-013](research/re1/script-opcodes.md#re1-scd-013-forced-document-callbacks-conditionally-set-pending-bit-8) | forced document callbacks conditionally set pending bit 8 |
| <a id="re1-scd-014-forced-callback-command-returns-and-pending-flags-are-independent"></a>[RE1-SCD-014](research/re1/script-opcodes.md#re1-scd-014-forced-callback-command-returns-and-pending-flags-are-independent) | forced callback command returns and pending flags are independent |
| <a id="re1-scd-015-forced-door-callbacks-preserve-descriptors-and-use-fresh-unlock-state"></a>[RE1-SCD-015](research/re1/script-opcodes.md#re1-scd-015-forced-door-callbacks-preserve-descriptors-and-use-fresh-unlock-state) | forced door callbacks preserve descriptors and use fresh unlock state |
| <a id="re1-scd-016-movement-callbacks-preserve-descriptors-but-their-request-is-consumed"></a>[RE1-SCD-016](research/re1/script-opcodes.md#re1-scd-016-movement-callbacks-preserve-descriptors-but-their-request-is-consumed) | movement callbacks preserve descriptors but their request is consumed |
| <a id="re1-scd-017-flag-callback-consumes-three-registry-words"></a>[RE1-SCD-017](research/re1/script-opcodes.md#re1-scd-017-flag-callback-consumes-three-registry-words) | flag callback consumes three registry words |
| <a id="re1-native-001-shared-forced-callback-support-and-source-projection"></a>[RE1-NATIVE-001](research/re1/script-opcodes.md#re1-native-001-shared-forced-callback-support-and-source-projection) | shared forced callback support and source projection |
| <a id="re1-scd-018-lighting-writes-require-a-bounded-room-file-destination"></a>[RE1-SCD-018](research/re1/script-opcodes.md#re1-scd-018-lighting-writes-require-a-bounded-room-file-destination) | lighting writes require a bounded room-file destination |
| <a id="re1-scd-019-model-recoloring-preserves-tracked-descriptor-and-flag-state"></a>[RE1-SCD-019](research/re1/script-opcodes.md#re1-scd-019-model-recoloring-preserves-tracked-descriptor-and-flag-state) | model recoloring preserves tracked descriptor and flag state |
| <a id="re1-scd-020-effect-record-flag-writes-do-not-change-the-aliased-pool-header"></a>[RE1-SCD-020](research/re1/script-opcodes.md#re1-scd-020-effect-record-flag-writes-do-not-change-the-aliased-pool-header) | effect-record flag writes do not change the aliased pool header |
| <a id="re1-native-002-shared-rendering-command-support-and-unchanged-projection-limits"></a>[RE1-NATIVE-002](research/re1/script-opcodes.md#re1-native-002-shared-rendering-command-support-and-unchanged-projection-limits) | shared rendering command support and unchanged projection limits |
| <a id="re1-scd-021-item-interaction-predicates-compare-transient-byte-variables"></a>[RE1-SCD-021](research/re1/script-opcodes.md#re1-scd-021-item-interaction-predicates-compare-transient-byte-variables) | item-interaction predicates compare transient byte variables |
| <a id="re1-scd-022-shared-item-interaction-comparisons-retain-bounded-value-lifetimes"></a>[RE1-SCD-022](research/re1/script-opcodes.md#re1-scd-022-shared-item-interaction-comparisons-retain-bounded-value-lifetimes) | shared item-interaction comparisons retain bounded value lifetimes |

## RE1 events research

| Claim | Finding |
| --- | --- |
| <a id="re1-event-001-event-scripts-remain-outside-the-committed-item-scan"></a>[RE1-EVENT-001](research/re1/events.md#re1-event-001-event-scripts-remain-outside-the-committed-item-scan) | event scripts remain outside the committed item scan |
| <a id="re1-event-002-winding-passage-indexed-events-show-no-second-item-command"></a>[RE1-EVENT-002](research/re1/events.md#re1-event-002-winding-passage-indexed-events-show-no-second-item-command) | Winding Passage indexed events show no second item command |
| <a id="re1-dialog-001-dialog-busy-and-choice-values-explain-the-scripted-door-guard"></a>[RE1-DIALOG-001](research/re1/events.md#re1-dialog-001-dialog-busy-and-choice-values-explain-the-scripted-door-guard) | dialog busy and choice values explain the scripted-door guard |
| <a id="re1-event-003-indexed-event-reads-returns-and-shared-depth-follow-the-native-vm"></a>[RE1-EVENT-003](research/re1/events.md#re1-event-003-indexed-event-reads-returns-and-shared-depth-follow-the-native-vm) | indexed-event reads, returns and shared depth follow the native VM |
| <a id="re1-event-004-ordered-event-blocks-retain-their-internal-progress-conditions"></a>[RE1-EVENT-004](research/re1/events.md#re1-event-004-ordered-event-blocks-retain-their-internal-progress-conditions) | ordered event blocks retain their internal progress conditions |
| <a id="re1-event-005-native-event-activity-is-separate-from-retained-script-pointers"></a>[RE1-EVENT-005](research/re1/events.md#re1-event-005-native-event-activity-is-separate-from-retained-script-pointers) | native event activity is separate from retained script pointers |
| <a id="re1-event-006-script-and-interaction-commands-share-the-native-event-initializer"></a>[RE1-EVENT-006](research/re1/events.md#re1-event-006-script-and-interaction-commands-share-the-native-event-initializer) | script and interaction commands share the native event initializer |
| <a id="re1-event-007-shared-source-metadata-binds-transient-event-activity"></a>[RE1-EVENT-007](research/re1/events.md#re1-event-007-shared-source-metadata-binds-transient-event-activity) | shared source metadata binds transient event activity |
| <a id="re1-event-008-live-demo-registry-entries-bind-to-source-event-targets"></a>[RE1-EVENT-008](research/re1/events.md#re1-event-008-live-demo-registry-entries-bind-to-source-event-targets) | live demo registry entries bind to source event targets |
| <a id="re1-event-009-reusable-coherent-event-observation-log"></a>[RE1-EVENT-009](research/re1/events.md#re1-event-009-reusable-coherent-event-observation-log) | reusable coherent event observation log |
| <a id="re1-event-010-live-capture-records-item-state-savestate-reversal"></a>[RE1-EVENT-010](research/re1/events.md#re1-event-010-live-capture-records-item-state-savestate-reversal) | live capture records item-state savestate reversal |
| <a id="re1-event-011-activity-write-capture-completes-the-pinned-initializer"></a>[RE1-EVENT-011](research/re1/events.md#re1-event-011-activity-write-capture-completes-the-pinned-initializer) | activity-write capture completes the pinned initializer |
| <a id="re1-event-012-native-transition-clears-hit-every-activity-watch"></a>[RE1-EVENT-012](research/re1/events.md#re1-event-012-native-transition-clears-hit-every-activity-watch) | native transition clears hit every activity watch |
| <a id="re1-event-013-natural-opening-events-validate-initializer-stepping-and-stops"></a>[RE1-EVENT-013](research/re1/events.md#re1-event-013-natural-opening-events-validate-initializer-stepping-and-stops) | natural opening events validate initializer stepping and stops |
| <a id="re1-event-014-vm05-exposes-parent-pc1-during-child-initialization"></a>[RE1-EVENT-014](research/re1/events.md#re1-event-014-vm05-exposes-parent-pc1-during-child-initialization) | VM05 exposes parent PC+1 during child initialization |
| <a id="re1-event-015-art-room-map-interaction-binds-its-natural-event-starts"></a>[RE1-EVENT-015](research/re1/events.md#re1-event-015-art-room-map-interaction-binds-its-natural-event-starts) | Art Room map interaction binds its natural event starts |
| <a id="re1-event-016-room-setup-clears-only-a-bounded-portion-of-local-flag-storage"></a>[RE1-EVENT-016](research/re1/events.md#re1-event-016-room-setup-clears-only-a-bounded-portion-of-local-flag-storage) | room setup clears only a bounded portion of local flag storage |
| <a id="re1-event-017-main-hall-pickup-handler-activation-depends-on-room-local-progress"></a>[RE1-EVENT-017](research/re1/events.md#re1-event-017-main-hall-pickup-handler-activation-depends-on-room-local-progress) | Main Hall pickup-handler activation depends on room-local progress |
| <a id="re1-event-018-out-of-section-event-tails-reach-the-native-state-0-disable"></a>[RE1-EVENT-018](research/re1/events.md#re1-event-018-out-of-section-event-tails-reach-the-native-state-0-disable) | out-of-section event tails reach the native state-0 disable |

## RE1 saves research

| Claim | Finding |
| --- | --- |
| <a id="re1-save-001-chemical-acquisition-survives-a-normal-in-game-save-and-load"></a>[RE1-SAVE-001](research/re1/saves.md#re1-save-001-chemical-acquisition-survives-a-normal-in-game-save-and-load) | Chemical acquisition survives a normal in-game save and load |
| <a id="re1-save-002-the-normal-save-payload-includes-the-herb-acquisition-byte"></a>[RE1-SAVE-002](research/re1/saves.md#re1-save-002-the-normal-save-payload-includes-the-herb-acquisition-byte) | the normal-save payload includes the Herb acquisition byte |
| <a id="re1-save-003-art-room-map-acquisition-survives-normal-saves-and-reverses-with-an-earlier-save"></a>[RE1-SAVE-003](research/re1/saves.md#re1-save-003-art-room-map-acquisition-survives-normal-saves-and-reverses-with-an-earlier-save) | Art Room map acquisition survives normal saves and reverses with an earlier save |
| <a id="re1-save-004-public-memory-card-provides-candidate-later-area-checkpoints"></a>[RE1-SAVE-004](research/re1/saves.md#re1-save-004-public-memory-card-provides-candidate-later-area-checkpoints) | public memory card provides candidate later-area checkpoints |
| <a id="re1-save-005-four-public-card-entries-load-through-the-native-game-menu"></a>[RE1-SAVE-005](research/re1/saves.md#re1-save-005-four-public-card-entries-load-through-the-native-game-menu) | four public card entries load through the native game menu |

## RE1 analysis research

| Claim | Finding |
| --- | --- |
| <a id="re1-pilot-001-live-debug-view-tracks-the-winding-passage-herb"></a>[RE1-PILOT-001](research/re1/analysis.md#re1-pilot-001-live-debug-view-tracks-the-winding-passage-herb) | live debug view tracks the Winding Passage Herb |
| <a id="re1-pilot-002-live-debug-view-names-the-conditional-chemical"></a>[RE1-PILOT-002](research/re1/analysis.md#re1-pilot-002-live-debug-view-names-the-conditional-chemical) | live debug view names the conditional Chemical |
| <a id="re1-analysis-005-remaining-gaps-after-shared-message-door-support"></a>[RE1-ANALYSIS-005](research/re1/analysis.md#re1-analysis-005-remaining-gaps-after-shared-message-door-support) | remaining gaps after shared message-door support |
| <a id="re1-analysis-006-remaining-reconstruction-gaps-after-reachable-script-coverage"></a>[RE1-ANALYSIS-006](research/re1/analysis.md#re1-analysis-006-remaining-reconstruction-gaps-after-reachable-script-coverage) | remaining reconstruction gaps after reachable script coverage |
| <a id="re1-analysis-007-remaining-gaps-after-bounded-scripted-door-tracking"></a>[RE1-ANALYSIS-007](research/re1/analysis.md#re1-analysis-007-remaining-gaps-after-bounded-scripted-door-tracking) | remaining gaps after bounded scripted-door tracking |
| <a id="re1-analysis-001-whole-room-shadow-dependencies-preserve-published-results-and-reduce-branching"></a>[RE1-ANALYSIS-001](research/re1/analysis.md#re1-analysis-001-whole-room-shadow-dependencies-preserve-published-results-and-reduce-branching) | whole-room shadow dependencies preserve published results and reduce branching |
| <a id="re1-analysis-002-extending-unknown-flag-assumptions-to-current-execution-exceeded-existing-budgets"></a>[RE1-ANALYSIS-002](research/re1/analysis.md#re1-analysis-002-extending-unknown-flag-assumptions-to-current-execution-exceeded-existing-budgets) | extending unknown-flag assumptions to current execution exceeded existing budgets |
| <a id="re1-analysis-003-merging-interaction-alternatives-at-matching-branch-states-avoids-two-procedure-limits"></a>[RE1-ANALYSIS-003](research/re1/analysis.md#re1-analysis-003-merging-interaction-alternatives-at-matching-branch-states-avoids-two-procedure-limits) | merging interaction alternatives at matching branch states avoids two procedure limits |
| <a id="re1-analysis-004-bounded-branch-merging-preserves-source-and-guard-uncertainty"></a>[RE1-ANALYSIS-004](research/re1/analysis.md#re1-analysis-004-bounded-branch-merging-preserves-source-and-guard-uncertainty) | bounded branch merging preserves source and guard uncertainty |
| <a id="re1-analysis-008-remaining-gaps-after-bounded-scripted-collectible-tracking"></a>[RE1-ANALYSIS-008](research/re1/analysis.md#re1-analysis-008-remaining-gaps-after-bounded-scripted-collectible-tracking) | remaining gaps after bounded scripted-collectible tracking |
| <a id="re1-analysis-009-item-interaction-predicate-probe-preserves-coverage-without-gains"></a>[RE1-ANALYSIS-009](research/re1/analysis.md#re1-analysis-009-item-interaction-predicate-probe-preserves-coverage-without-gains) | item-interaction predicate probe preserves coverage without gains |
| <a id="re1-analysis-010-playthrough-progress-audit-after-interaction-predicates"></a>[RE1-ANALYSIS-010](research/re1/analysis.md#re1-analysis-010-playthrough-progress-audit-after-interaction-predicates) | playthrough progress audit after interaction predicates |

## RE1 map gameplay observations

| Claim | Finding |
| --- | --- |
| <a id="re1-map-007-first-live-adjacency-check-and-incomplete-floor-crossing-experiment"></a>[RE1-MAP-007](research/re1/map-validation.md#re1-map-007-first-live-adjacency-check-and-incomplete-floor-crossing-experiment) | first live adjacency check and incomplete floor-crossing experiment |
| <a id="re1-map-008-natural-main-hall-floor-switching-and-return-history"></a>[RE1-MAP-008](research/re1/map-validation.md#re1-map-008-natural-main-hall-floor-switching-and-return-history) | natural Main Hall floor switching and return history |
| <a id="re1-map-009-native-main-hall-map-views-preserve-tracker-state"></a>[RE1-MAP-009](research/re1/map-validation.md#re1-map-009-native-main-hall-map-views-preserve-tracker-state) | native Main Hall map views preserve tracker state |
| <a id="re1-map-010-adjoining-mansion-2f-rooms-reveal-on-entry-and-retain-history"></a>[RE1-MAP-010](research/re1/map-validation.md#re1-map-010-adjoining-mansion-2f-rooms-reveal-on-entry-and-retain-history) | adjoining Mansion 2F rooms reveal on entry and retain history |
| <a id="re1-map-011-three-further-mansion-2f-rooms-reveal-on-natural-entry"></a>[RE1-MAP-011](research/re1/map-validation.md#re1-map-011-three-further-mansion-2f-rooms-reveal-on-natural-entry) | three further Mansion 2F rooms reveal on natural entry |
| <a id="re1-map-012-laboratory-b3-and-courtyard-b1-reveal-rooms-on-natural-entry"></a>[RE1-MAP-012](research/re1/map-validation.md#re1-map-012-laboratory-b3-and-courtyard-b1-reveal-rooms-on-natural-entry) | Laboratory B3 and Courtyard B1 reveal rooms on natural entry |
| <a id="re1-map-013-guardhouse-and-courtyard-switch-areas-on-passage-and-return"></a>[RE1-MAP-013](research/re1/map-validation.md#re1-map-013-guardhouse-and-courtyard-switch-areas-on-passage-and-return) | Guardhouse and Courtyard switch areas on passage and return |
| <a id="re1-map-014-guardhouse-basement-ladder-selects-its-plan-and-returns"></a>[RE1-MAP-014](research/re1/map-validation.md#re1-map-014-guardhouse-basement-ladder-selects-its-plan-and-returns) | Guardhouse basement ladder selects its plan and returns |
| <a id="re1-map-015-laboratory-b2-stairs-and-b1-ladder-select-their-plans-and-return"></a>[RE1-MAP-015](research/re1/map-validation.md#re1-map-015-laboratory-b2-stairs-and-b1-ladder-select-their-plans-and-return) | Laboratory B2 stairs and B1 ladder select their plans and return |
| <a id="re1-map-016-laboratory-power-route-enters-b4-and-returns-with-retained-state"></a>[RE1-MAP-016](research/re1/map-validation.md#re1-map-016-laboratory-power-route-enters-b4-and-returns-with-retained-state) | Laboratory power route enters B4 and returns with retained state |
| <a id="re1-map-017-mansion-b1-entry-four-outlined-regions-and-stairway-return"></a>[RE1-MAP-017](research/re1/map-validation.md#re1-map-017-mansion-b1-entry-four-outlined-regions-and-stairway-return) | Mansion B1 entry, four outlined regions and stairway return |

## RE2 Leon A research

| Claim | Finding |
| --- | --- |
| <a id="re2-identity-001-leon-a-disc-identity-and-candidate-room-layout"></a>[RE2-IDENTITY-001](research/re2.md#re2-identity-001-leon-a-disc-identity-and-candidate-room-layout) | Leon A disc identity and candidate room layout |
| <a id="re2-scd-001-bounded-leon-room-metadata-and-acquisition-contracts"></a>[RE2-SCD-001](research/re2.md#re2-scd-001-bounded-leon-room-metadata-and-acquisition-contracts) | bounded Leon room metadata and acquisition contracts |
| <a id="re2-map-001-native-leon-floor-selectors-and-numeric-contours"></a>[RE2-MAP-001](research/re2.md#re2-map-001-native-leon-floor-selectors-and-numeric-contours) | native Leon floor selectors and numeric contours |
| <a id="re2-player-001-native-movement-confirms-continuous-heading"></a>[RE2-PLAYER-001](research/re2.md#re2-player-001-native-movement-confirms-continuous-heading) | native movement, rendered arrow direction and fresh heading after restores |
| <a id="re2-player-002-approximate-position-follows-native-pose-and-restores"></a>[RE2-PLAYER-002](research/re2.md#re2-player-002-approximate-position-follows-native-pose-and-restores) | guarded approximate placement, live movement and fresh position after restores |
| <a id="re2-floor-001-native-same-room-floor-changes-and-restores"></a>[RE2-FLOOR-001](research/re2.md#re2-floor-001-native-same-room-floor-changes-and-restores) | native floor changes within one source, separate region visits, browsing and restores |
| <a id="re2-map-002-door-markers-follow-native-trigger-floors"></a>[RE2-MAP-002](research/re2.md#re2-map-002-door-markers-follow-native-trigger-floors) | paired native crossings, trigger-floor marker filtering and unresolved absolute wall alignment |
| <a id="re2-session-001-live-tracker-restarts-and-restores"></a>[RE2-SESSION-001](research/re2.md#re2-session-001-live-tracker-restarts-and-restores) | actual CLI restarts, persistent exploration and fresh item/door/floor state after native loads |
| <a id="re2-live-001-coherent-opening-room-reads-and-explicit-runtime-limits"></a>[RE2-LIVE-001](research/re2.md#re2-live-001-coherent-opening-room-reads-and-explicit-runtime-limits) | coherent opening-room reads and explicit runtime limits |
| <a id="re2-live-002-gun-shop-ammunition-and-savestate-reversal"></a>[RE2-LIVE-002](research/re2.md#re2-live-002-gun-shop-ammunition-and-savestate-reversal) | gun-shop ammunition and savestate reversal |
| <a id="re2-live-003-controlled-route-pickups-and-reentry"></a>[RE2-LIVE-003](research/re2.md#re2-live-003-controlled-route-pickups-and-reentry) | controlled route, pickups, reentry and restored exploration |
| <a id="re2-collect-001-source-established-items-remain-until-collected"></a>[RE2-COLLECT-001](research/re2.md#re2-collect-001-source-established-items-remain-until-collected) | source-established items remain until collected |
| <a id="re2-collect-002-conflicting-slots-preserve-unrelated-item-proofs"></a>[RE2-COLLECT-002](research/re2.md#re2-collect-002-conflicting-slots-preserve-unrelated-item-proofs) | conflicting slots preserve unrelated item proofs |
| <a id="re2-collect-003-scripted-activation-preserves-collection-identity"></a>[RE2-COLLECT-003](research/re2.md#re2-collect-003-scripted-activation-preserves-collection-identity) | scripted activation preserves collection identity and quantity uncertainty |
| <a id="re2-collect-004-exclusive-event-delivery-collection-flags"></a>[RE2-COLLECT-004](research/re2.md#re2-collect-004-exclusive-event-delivery-collection-flags) | native event delivery, exclusive acquisition binding, inventory-independent collection and restore reversal |
| <a id="re2-collect-005-source-proven-pre-delivery-event-presence"></a>[RE2-COLLECT-005](research/re2.md#re2-collect-005-source-proven-pre-delivery-event-presence) | required pre-delivery items, inactive-event restores and fresh presence gates |
| <a id="re2-collect-006-stable-conditions-preserve-departed-pickups"></a>[RE2-COLLECT-006](research/re2.md#re2-collect-006-stable-conditions-preserve-departed-pickups) | stable startup conditions, remaining ordinary pickups after departure and native restore checks |
| <a id="re2-collect-007-fixed-scenario-proof-excludes-impossible-pickups"></a>[RE2-COLLECT-007](research/re2.md#re2-collect-007-fixed-scenario-proof-excludes-impossible-pickups) | separate fixed-scenario exclusion, real-item clearance, departure/reentry and restores |
| <a id="re2-collect-008-scenario-exclusions-through-audited-script-effects"></a>[RE2-COLLECT-008](research/re2.md#re2-collect-008-scenario-exclusions-through-audited-script-effects) | ordinary pickups, reentry and restores in three native contexts; one full-clearance case; two remaining item/condition limits |
| <a id="re2-collect-009-native-pickup-and-use-keep-acquisition-identities-separate"></a>[RE2-COLLECT-009](research/re2.md#re2-collect-009-native-pickup-and-use-keep-acquisition-identities-separate) | native pickup and repeated use, independent acquisition IDs, reentry and byte-identical restores; remaining activation unresolved |
| <a id="re2-collect-010-system-mode-predicate-gates-alternate-pickup-identities"></a>[RE2-COLLECT-010](research/re2.md#re2-collect-010-system-mode-predicate-gates-alternate-pickup-identities) | Candidate system-mode gate for alternate pickup IDs; hypothetical proof only, flag lifecycle and opposite-mode gameplay unverified |
| <a id="re2-collect-011-pinned-native-mode-excludes-an-alternate-pickup"></a>[RE2-COLLECT-011](research/re2.md#re2-collect-011-pinned-native-mode-excludes-an-alternate-pickup) | enforced native mode excludes one alternate pickup; full clearance, native reentry and earlier/later restores |
| <a id="re2-collect-012-counter-initialization-blocks-departed-item-presence"></a>[RE2-COLLECT-012](research/re2.md#re2-collect-012-counter-initialization-blocks-departed-item-presence) | native pickups, departure/reentry and six exact restores validate two retained item checks; broader counter coverage remains Candidate |
| <a id="re2-collect-013-unrelated-startup-flag-writes-block-conditional-presence"></a>[RE2-COLLECT-013](research/re2.md#re2-collect-013-unrelated-startup-flag-writes-block-conditional-presence) | shared flag-write guard retains conditional pickups; one native pickup/reentry case and six exact restores; broader lifecycle coverage Candidate |
| <a id="re2-collect-014-fixed-scenario-selects-conflicting-pickup-identities"></a>[RE2-COLLECT-014](research/re2.md#re2-collect-014-fixed-scenario-selects-conflicting-pickup-identities) | three native selected-pickup lifecycles, reentry and exact restores; two clearance cases |
| <a id="re2-collect-015-counter-independent-pickup-presence"></a>[RE2-COLLECT-015](research/re2.md#re2-collect-015-counter-independent-pickup-presence) | read-only startup comparisons require both outcomes; all six scenario-compatible pickup IDs have native lifecycle observations, including reverse collection order and exact restores |
| <a id="re2-collect-016-bounded-script-writes-preserve-scenario-proofs"></a>[RE2-COLLECT-016](research/re2.md#re2-collect-016-bounded-script-writes-preserve-scenario-proofs) | bounded self-modifying operands, collision flags and FOR procedures; selected native pickup clearance, reentry and six exact restores |
| <a id="re2-collect-017-fixed-context-gates-fresh-pickup-presence"></a>[RE2-COLLECT-017](research/re2.md#re2-collect-017-fixed-context-gates-fresh-pickup-presence) | all four compatible new presence rules have native pickup, departure/reentry and exact restore observations; two clearance cases, one retained Unknown check and one required remaining item |
| <a id="re2-source-001-bounded-sound-relocation-preserves-room-identity"></a>[RE2-SOURCE-001](research/re2.md#re2-source-001-bounded-sound-relocation-preserves-room-identity) | source hashes accept paired sound relocation in four prior native captures; 21 section pointers and camera proofs retain strict identity |
| <a id="re2-quantity-001-native-pickup-award-amount-differs-from-catalog"></a>[RE2-QUANTITY-001](research/re2.md#re2-quantity-001-native-pickup-award-amount-differs-from-catalog) | native pickup amount override reconstructed from fresh mode flags; flag-clear gameplay unverified |
| <a id="re2-door-001-event-driven-unlock-and-savestate-reversal"></a>[RE2-DOOR-001](research/re2.md#re2-door-001-event-driven-unlock-and-savestate-reversal) | event-driven unlock, paired passage and fresh access after restores |
| <a id="re2-door-002-named-key-use-and-savestate-reversal"></a>[RE2-DOOR-002](research/re2.md#re2-door-002-named-key-use-and-savestate-reversal) | native key pickup/use, carrying versus unlocking and fresh state after restores |
| <a id="re2-door-003-one-sided-unlock-and-savestate-reversal"></a>[RE2-DOOR-003](research/re2.md#re2-door-003-one-sided-unlock-and-savestate-reversal) | native one-sided unlock, paired passage and fresh access after restores |

2026-10-17 contribution: Codex root, `gpt-6.1-sol`, reorganized the existing entries by topic, retained their original evidence and attribution, and preserved legacy claim anchors in this index.
