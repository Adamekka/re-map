"""Combine live observations and source rules for every visited RE1 room."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from games.re1.room_cache import (
    CachedRoomObservation,
    RoomScriptSource,
    refresh_cached_items,
)
from games.re1.room_items import RuntimeItemState, RuntimeRoomItems
from games.re1.scripted_collectibles import scripted_collectible_access
from games.re1.scripted_doors import ScriptedDoorAccess, scripted_door_access
from games.re1.tracking_rules import (
    CachedReentryEvaluation,
    RoomRuleEpoch,
    RuleSnapshot,
    evaluate_room_program,
)

if TYPE_CHECKING:
    from games.re1.re1_profile import Re1Profile


@dataclass(frozen=True)
class TrackedRoom:
    items: RuntimeRoomItems
    doors: tuple[tuple[int, bytes], ...]
    disabled_doors: tuple[tuple[int, bytes], ...]
    doors_complete: bool
    door_reason: str


def validate_current_room(
    profile: Re1Profile,
    observation: RuntimeRoomItems,
    sources: tuple[RoomScriptSource, ...],
    snapshot: RuleSnapshot,
    flags: bytes,
) -> TrackedRoom:
    layout, room_layout = profile.tracking_rule_layout, profile.runtime_room_layout
    assert layout is not None and room_layout is not None
    if not sources:
        return TrackedRoom(
            replace(
                observation,
                list_complete=False,
                coverage_reason="Room script coverage is unavailable.",
            ),
            observation.active_doors,
            observation.disabled_doors,
            False,
            "Door access needs another visit.",
        )
    active, disabled = list(observation.active_doors), list(observation.disabled_doors)
    items = list(observation.items)
    unresolved_scripted_collectible = False
    for item, record, entry in observation.scripted_collectibles:
        # The coherent observer already read this source's acquisition flag.
        # A taken item needs no access proof; an uncollected alias still does.
        if item.state is RuntimeItemState.Taken or all(
            scripted_collectible_access(
                profile.room_programs[source.source_rdt].event_program,
                item.aot_id,
                item.item_type,
                record,
                entry,
            )
            for source in sources
        ):
            items.append(
                replace(
                    item,
                    state=RuntimeItemState.Taken
                    if item.state is RuntimeItemState.Taken
                    else RuntimeItemState.Available,
                )
            )
        else:
            unresolved_scripted_collectible = True
    unresolved_scripted_door = False
    for slot, opcode, entry in observation.scripted_doors:
        accesses = {
            scripted_door_access(
                profile.room_programs[source.source_rdt].event_program,
                slot,
                entry,
                opcode,
            )
            for source in sources
        }
        if accesses == {ScriptedDoorAccess.Delegated}:
            active.append((slot, opcode))
        elif accesses == {ScriptedDoorAccess.Blocked}:
            disabled.append((slot, opcode))
        else:
            unresolved_scripted_door = True
    observation = replace(
        observation,
        active_doors=tuple(active),
        disabled_doors=tuple(disabled),
        items=tuple(items),
        scripted_collectibles=(),
        # Consume candidates once, but retain unresolved access in coverage
        # even when current static conditions reconstruct no door at that slot.
        scripted_doors=(),
        list_complete=observation.list_complete and not unresolved_scripted_collectible,
        coverage_reason="Room item conditions are unresolved."
        if unresolved_scripted_collectible
        else observation.coverage_reason,
    )
    represented = {item.aot_id for item in observation.items}
    active_doors = {slot for slot, _ in observation.active_doors}
    disabled_doors = {slot for slot, _ in observation.disabled_doors}
    # An enabled message handler with a validated current source proves blocked
    # passage even when reconstruction retains an earlier active door. Handler
    # zero can survive reset with a stale pointer, so it grants no such override.
    message_doors = set(observation.message_door_slots)
    represented_doors = {
        slot for slot, _ in observation.active_doors + observation.disabled_doors
    }
    doors_complete = not unresolved_scripted_door
    for source in sources:
        program = profile.room_programs[source.source_rdt]
        # Forced awards ignore the current handler. Noncollectible evidence
        # resolves only current slots without that dormant-award possibility.
        resolved_slots = represented | (
            set(observation.non_collectible_slots) - set(program.award_slots)
        )
        expected = evaluate_room_program(
            program,
            source.room,
            layout,
            snapshot,
            flags,
            room_layout.item_labels,
        )
        if (
            set(expected.unresolved_door_slots) - represented_doors
            or {slot for slot, _ in expected.doors} - active_doors - message_doors
            or {slot for slot, _ in expected.disabled_doors} - disabled_doors
            or not profile.room_programs[source.source_rdt].coverage_complete
        ):
            doors_complete = False
        if (
            expected.unresolved_item_slots
            and set(expected.unresolved_item_slots) - resolved_slots
            or not profile.room_programs[source.source_rdt].coverage_complete
        ):
            observation = replace(
                observation,
                list_complete=False,
                coverage_reason="Room item conditions are unresolved.",
            )
        if any(
            item.state == RuntimeItemState.Available
            and not any(
                live.aot_id == item.aot_id
                and live.global_id == item.global_id
                and live.item_type == item.item_type
                and live.state == RuntimeItemState.Available
                for live in observation.items
            )
            for item in expected.items.items
        ):
            # Relocated scripts can be visible before their registry is fully initialized.
            # Missing required pickups must not make that partial room look cleared.
            observation = replace(
                observation,
                list_complete=False,
                coverage_reason="Room items are still updating.",
            )
    return TrackedRoom(
        observation,
        observation.active_doors,
        observation.disabled_doors,
        doors_complete,
        "" if doors_complete else "Door access needs another visit.",
    )


def refresh_visited_room(
    profile: Re1Profile,
    cached: CachedRoomObservation,
    context: tuple[int, ...],
    snapshot: RuleSnapshot,
    flags: bytes,
) -> TrackedRoom:
    layout = profile.tracking_rule_layout
    room_layout = profile.runtime_room_layout
    assert layout is not None and room_layout is not None
    values = dict(snapshot.values)
    selection = tuple(
        values[address] & mask for address, mask in layout.source_selection_masks
    )
    if not cached.sources:
        return TrackedRoom(
            RuntimeRoomItems(
                ok=True, coverage_reason="Re-enter this room to refresh its items."
            ),
            (),
            (),
            False,
            "Door access needs another visit.",
        )
    room = cached.sources[0].room
    selected_name = profile.room_source_choices.get(
        (
            room,
            int(bool(values[layout.variant_address] & layout.variant_mask)),
            int(bool(values[layout.alternate_address] & layout.alternate_mask)),
        )
    )
    if selected_name is None:
        return TrackedRoom(
            RuntimeRoomItems(
                ok=True, coverage_reason="Room source selection is unsupported."
            ),
            (),
            (),
            False,
            "Door access needs another visit.",
        )
    same_source = selection == cached.source_selection and any(
        source.source_rdt == selected_name for source in cached.sources
    )
    observed = refresh_cached_items(cached, context, flags, layout.acquisition, values)
    global_masks = {layout.character_address: 255}
    for group in layout.persistent_flag_groups:
        for offset in range(32):
            global_masks[layout.flag_bases[group] + offset] = 255
    for group, index in layout.persistent_flag_bits:
        address, mask = layout.flag(group, index)
        global_masks[address] = global_masks.get(address, 0) | mask
    for address, mask in layout.source_selection_masks:
        global_masks[address] = global_masks.get(address, 0) | mask
    global_context = all(
        dependency.width == 1
        and dependency.mask & ~global_masks.get(dependency.address, 0) == 0
        for source in cached.sources
        for dependency in source.dependencies
    )
    if not global_context or not same_source:
        # Equal bytes in another room do not establish this room's local state.
        # Use source reconstruction instead of treating transient banks as persistent.
        observed = replace(observed, list_complete=False)
    reuse_doors = (
        all(source.door_cache_complete for source in cached.sources)
        and context == cached.context
        and global_context
        and same_source
        and cached.doors_complete
    )
    if observed.list_complete and reuse_doors:
        return TrackedRoom(
            observed,
            cached.observation.active_doors,
            cached.observation.disabled_doors,
            True,
            "",
        )
    rule_sources = (
        cached.sources
        if same_source
        else tuple(
            source
            for source in profile.room_sources
            if source.source_rdt == selected_name
        )
    )
    assert rule_sources, "validated source choices must reference a source"
    evaluations = []
    for source in rule_sources:
        program = profile.room_programs[source.source_rdt]
        previous = profile.room_reentry_evaluations.get(source.source_rdt)
        if (
            previous is not None
            and previous.program is program
            and previous.room == source.room
            and previous.layout == layout
            and previous.snapshot == snapshot
            and previous.flags == flags
            and previous.item_labels == room_layout.item_labels
        ):
            evaluations.append(previous.result)
            continue
        result = evaluate_room_program(
            program,
            source.room,
            layout,
            snapshot,
            flags,
            room_layout.item_labels,
            RoomRuleEpoch.Reentry,
        )
        profile.room_reentry_evaluations[source.source_rdt] = CachedReentryEvaluation(
            program,
            source.room,
            layout,
            snapshot,
            flags,
            room_layout.item_labels,
            result,
        )
        evaluations.append(result)
    if observed.list_complete:
        items = observed
    else:
        common = set(evaluations[0].items.items)
        for evaluation in evaluations[1:]:
            common.intersection_update(evaluation.items.items)
        complete = all(
            evaluation.items.list_complete for evaluation in evaluations
        ) and all(
            evaluation.items.items == evaluations[0].items.items
            for evaluation in evaluations
        )
        reasons = sorted(
            {
                evaluation.items.coverage_reason
                for evaluation in evaluations
                if evaluation.items.coverage_reason
            }
        )
        if not complete and not reasons:
            reasons.append("Matching room variants disagree about items.")
        items = RuntimeRoomItems(
            ok=True,
            items=tuple(sorted(common, key=lambda item: item.aot_id)),
            list_complete=complete,
            coverage_reason=" ".join(reasons),
        )
    if reuse_doors:
        doors = cached.observation.active_doors
        disabled_doors = cached.observation.disabled_doors
    else:
        common_doors = set(evaluations[0].doors)
        common_disabled = set(evaluations[0].disabled_doors)
        for evaluation in evaluations[1:]:
            common_doors.intersection_update(evaluation.doors)
            common_disabled.intersection_update(evaluation.disabled_doors)
        doors = tuple(sorted(common_doors))
        disabled_doors = tuple(sorted(common_disabled))
    doors_complete = reuse_doors or (
        all(
            not evaluation.unresolved_door_slots and evaluation.coverage_complete
            for evaluation in evaluations
        )
        and all(
            (evaluation.doors, evaluation.disabled_doors)
            == (evaluations[0].doors, evaluations[0].disabled_doors)
            for evaluation in evaluations
        )
    )
    return TrackedRoom(
        items,
        doors,
        disabled_doors,
        doors_complete,
        "" if doors_complete else "Door access needs another visit.",
    )
