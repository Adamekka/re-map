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
from games.re1.tracking_rules import RuleSnapshot, evaluate_room_program

if TYPE_CHECKING:
    from games.re1.re1_profile import Re1Profile


@dataclass(frozen=True)
class TrackedRoom:
    items: RuntimeRoomItems
    doors: tuple[tuple[int, bytes], ...]
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
            False,
            "Door access needs another visit.",
        )
    represented = {item.aot_id for item in observation.items}
    active_doors = {slot for slot, _ in observation.active_doors}
    doors_complete = True
    for source in sources:
        expected = evaluate_room_program(
            profile.room_programs[source.source_rdt],
            source.room,
            layout,
            snapshot,
            flags,
            room_layout.item_labels,
        )
        if (
            set(expected.unresolved_door_slots) - active_doors
            or {slot for slot, _ in expected.doors} - active_doors
            or not profile.room_programs[source.source_rdt].coverage_complete
        ):
            doors_complete = False
        if (
            expected.unresolved_item_slots
            and set(expected.unresolved_item_slots) - represented
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
            False,
            "Door access needs another visit.",
        )
    same_source = selection == cached.source_selection and any(
        source.source_rdt == selected_name for source in cached.sources
    )
    observed = refresh_cached_items(cached, context, flags)
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
        return TrackedRoom(observed, cached.observation.active_doors, True, "")
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
    evaluations = [
        evaluate_room_program(
            profile.room_programs[source.source_rdt],
            source.room,
            layout,
            snapshot,
            flags,
            room_layout.item_labels,
        )
        for source in rule_sources
    ]
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
    else:
        common_doors = set(evaluations[0].doors)
        for evaluation in evaluations[1:]:
            common_doors.intersection_update(evaluation.doors)
        doors = tuple(sorted(common_doors))
    doors_complete = reuse_doors or (
        all(
            not evaluation.unresolved_door_slots
            and profile.room_programs[source.source_rdt].coverage_complete
            for source, evaluation in zip(rule_sources, evaluations, strict=True)
        )
        and all(evaluation.doors == evaluations[0].doors for evaluation in evaluations)
    )
    return TrackedRoom(
        items,
        doors,
        doors_complete,
        "" if doors_complete else "Door access needs another visit.",
    )
