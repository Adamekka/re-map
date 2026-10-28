"""Native storage partitions, without command entry or AOT activation claims."""

import copy
import hashlib
import struct
from dataclasses import replace

import pytest
from test_re2_metadata import (
    PRESENCE_COUNTERS,
    PRESENCE_FLAGS,
    PRESENCE_WRITES,
    item_command,
    synthetic_room,
)

from games.re2.room_data import decode_room
from games.re2.room_write_partitions import (
    EmbeddedModelResource,
    ModelResourceState,
    RoomWritePartitionConfig,
    RoomWritePartitionFailure,
    RoomWritePartitions,
    ScaWritePartition,
    SourceRange,
    room_write_partitions,
    sca_write_partition,
)


CONFIG = RoomWritePartitionConfig(0x800CE558, 32, 0x800D0324, 32, 256, 64)
END = b"\x01\0"


def test_pickup_operands_cannot_also_be_decoded_control_instructions():
    # This IF targets the quantity halfword, initially decoded as END. Native
    # Original-mode pickup changes 1 to 2, which would expose a SLEEP instead.
    item = bytearray(item_command(30, 1, 24))
    item[20] = 255
    body = bytes([4, 255, 24, 0, 6, 0, 20, 0, 0x21, 4, 7, 1]) + item + b"\x08\0" + END
    data, room, _ = source(END, (body, END), [], [0])
    rows = room["programs"]["17:0"]["commands"]
    pickup = next(row for row in rows if row["kind"] == "item")
    assert any(row["offset"] == pickup["offset"] + 16 for row in rows)
    assert (
        room_write_partitions(data, room, CONFIG)
        is RoomWritePartitionFailure.ScriptLayout
    )


def md1(triangles, quads):
    body = 84 + triangles * 12 + quads * 16
    data = bytearray(body + triangles * 12 + quads * 16)
    struct.pack_into("<3I", data, 0, body, 0, 2)
    struct.pack_into("<7I", data, 12, 56, 1, 64, 1, 72, triangles, body - 12)
    struct.pack_into(
        "<7I",
        data,
        40,
        56,
        1,
        64,
        1,
        72 + triangles * 12,
        quads,
        body - 12 + triangles * 12,
    )
    return data


def source(init, main, models, cameras):
    data = bytearray(synthetic_room(init, main))
    # Reserve all seven camera records before SCD, keeping the usual helper's
    # relative script branches unchanged when its two tables move together.
    data[132:132] = bytes(6 * 32)
    data[1] = 7
    for section in (16, 17):
        at = 8 + section * 4
        struct.pack_into("<I", data, at, struct.unpack_from("<I", data, at)[0] + 192)
    data.extend(bytes((-len(data)) % 4))
    directory = len(data)
    data[2] = len(models)
    struct.pack_into("<I", data, 8 + 10 * 4, directory)
    data.extend(bytes(len(models) * 8))
    model_offsets = []
    for slot, model in enumerate(models):
        offset = 0 if model is ModelResourceState.Absent else len(data)
        model_offsets.append(offset)
        struct.pack_into("<II", data, directory + slot * 8, 0, offset)
        if model is not ModelResourceState.Absent:
            data.extend(model)
    collision = len(data)
    struct.pack_into("<I", data, 8 + 6 * 4, collision)
    data.extend(bytes(4 * 16))
    struct.pack_into("<I", data, collision + 4, 4)
    rvd = len(data)
    struct.pack_into("<I", data, 8 + 8 * 4, rvd)
    for camera in cameras:
        data.extend(bytes([1, 255, camera, 0]) + bytes(16))
    data.extend(b"\xff" * 4)
    floor = len(data)
    struct.pack_into("<I", data, 8 + 2 * 4, floor)
    data.extend(bytes(32))
    raw = bytes(data)
    room = decode_room(
        raw, "synthetic", PRESENCE_FLAGS, PRESENCE_COUNTERS, PRESENCE_WRITES
    )
    return (
        raw,
        room,
        {
            "directory": directory,
            "models": model_offsets,
            "collision": collision,
            "rvd": rvd,
            "floor": floor,
        },
    )


def rebound(data, room):
    room = copy.deepcopy(room)
    room.update(
        size=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        section_offsets=list(struct.unpack_from("<23I", data, 8)),
    )
    return bytes(data), room


def object_command(slot):
    return bytes([0x2D, slot]) + bytes(36)


def camera_trigger(flag, target, camera, four_point=False):
    return (
        bytes([0x67 if four_point else 0x2C, 8, 13, 0xB1 if four_point else 0x31])
        + bytes(18 if four_point else 10)
        + struct.pack("<3H", flag, target, camera)
    )


@pytest.mark.parametrize("triangles,quads", [(0, 0), (1, 0), (0, 1), (2, 3), (48, 0)])
def test_model_partition_includes_uv_tail_and_native_record_pointer_stores(
    triangles, quads
):
    data, room, layout = source(
        object_command(0) + END,
        (END,),
        (md1(triangles, quads),),
        (0,),
    )
    result = room_write_partitions(data, room, CONFIG)
    assert isinstance(result, RoomWritePartitions)
    model = result.objects[0].model
    assert isinstance(model, EmbeddedModelResource)
    assert model.asset == SourceRange(
        layout["models"][0], 84 + 2 * (triangles * 12 + quads * 16)
    )
    assert model.render_objects == 2
    assert len(model.writes) == 8 + 2 * (triangles + quads)
    assert model.writes[:4] == tuple(
        SourceRange(model.asset.offset + 12 + field, 4) for field in (0, 8, 16, 24)
    )
    assert result.objects[0].record.address == CONFIG.object_address
    assert result.objects[0].record.width == 0x1F8
    assert all(
        row.offset + row.width <= model.asset.offset + model.asset.width
        for row in model.writes
    )
    assert result.source_writes[0].writes == model.writes


def test_null_model_is_explicit_and_still_has_a_fixed_object_record():
    data, room, _ = source(
        object_command(1) + END, (END,), (md1(1, 0), ModelResourceState.Absent), (0,)
    )
    result = room_write_partitions(data, room, CONFIG)
    assert isinstance(result, RoomWritePartitions)
    assert result.objects[0].model is ModelResourceState.Absent
    assert result.objects[0].record.address == CONFIG.object_address + 0x1F8
    assert not result.source_writes


def test_repeated_model_storage_does_not_claim_relocation_freshness_or_entry_closure():
    data, room, _ = source(object_command(0) * 2 + END, (END,), (md1(1, 1),), (0,))
    result = room_write_partitions(data, room, CONFIG)
    assert isinstance(result, RoomWritePartitions)
    assert len(result.objects) == 2
    assert result.objects[0].model == result.objects[1].model
    assert not hasattr(result, "entry_closed") and not hasattr(result, "active_doors")


def test_distinct_object_slots_can_share_one_asset_without_implying_freshness():
    data, room, layout = source(
        object_command(0) + object_command(1) + END,
        (END,),
        (md1(1, 1), ModelResourceState.Absent),
        (0,),
    )
    data = bytearray(data)
    struct.pack_into("<I", data, layout["directory"] + 12, layout["models"][0])
    data, room = rebound(data, room)
    result = room_write_partitions(data, room, CONFIG)
    assert isinstance(result, RoomWritePartitions)
    assert result.objects[0].record != result.objects[1].record
    assert result.objects[0].model.asset == result.objects[1].model.asset


def test_mutable_collision_records_cannot_alias_embedded_model_data():
    data, room, layout = source(
        object_command(0) + bytes([0x37, 0, 0x80, 0]) + END,
        (END,),
        (md1(8, 0),),
        (0,),
    )
    data = bytearray(data)
    collision = layout["models"][0] + 68
    struct.pack_into("<I", data, 32, collision)
    struct.pack_into("<I", data, collision + 4, 4)
    data, room = rebound(data, room)
    assert (
        room_write_partitions(data, room, CONFIG)
        is RoomWritePartitionFailure.SourceOverlap
    )


@pytest.mark.parametrize("fault", ["kind", "interaction"])
def test_native_opcode_classification_cannot_be_hidden_by_decoded_labels(fault):
    target = bytearray(item_command(20, 15, 92, slot=9))
    target[20] = 1
    data, room, _ = source(
        camera_trigger(1, 9, 6) + END,
        (bytes(target) + END,),
        (ModelResourceState.Absent,) * 2,
        (6,),
    )
    row = room["programs"]["16:0"]["commands"][0]
    row["kind"] = "other" if fault == "kind" else row["kind"]
    row["interaction"] = 4
    assert (
        room_write_partitions(data, room, CONFIG)
        is RoomWritePartitionFailure.ScriptLayout
    )


@pytest.mark.parametrize(
    "fault",
    [
        "null-floor",
        "unaligned-floor",
        "past-source",
        "script-after-floor",
        "changed-source",
        "changed-sections",
        "changed-program",
        "missing-entry",
    ],
)
def test_partition_requires_bound_source_and_complete_procedure_tables(fault):
    data, room, layout = source(END, (END,), (ModelResourceState.Absent,), (0,))
    data = bytearray(data)
    if fault in ("null-floor", "unaligned-floor", "past-source", "script-after-floor"):
        value = {
            "null-floor": 0,
            "unaligned-floor": layout["floor"] + 1,
            "past-source": len(data) + 4,
            "script-after-floor": 100,
        }[fault]
        struct.pack_into("<I", data, 16, value)
        data, room = rebound(data, room)
    elif fault == "changed-source":
        data[-1] = 1
    elif fault == "changed-sections":
        room["section_offsets"][2] += 4
    elif fault == "changed-program":
        room["programs"]["17:0"]["limit"] -= 1
    else:
        room["programs"]["17:0"]["commands"] = []
    result = room_write_partitions(bytes(data), room, CONFIG)
    assert isinstance(result, RoomWritePartitionFailure)


@pytest.mark.parametrize(
    "fault",
    [
        "slot",
        "unaligned-directory",
        "directory-over-script",
        "model-unaligned",
        "model-over-script",
        "model-after-floor",
        "flags",
        "zero-objects",
        "odd-objects",
        "short-body",
        "body-after-floor",
        "vertex",
        "normal",
        "primitive",
        "uv-offset",
        "uv-tail-after-floor",
        "texture",
    ],
)
def test_embedded_model_bounds_reject_bad_offsets_and_source_aliases(fault):
    data, room, layout = source(object_command(0) + END, (END,), (md1(1, 1),), (0,))
    data = bytearray(data)
    model, directory = layout["models"][0], layout["directory"]
    if fault == "slot":
        data[room["programs"]["16:0"]["entry"] + 1] = 1
    elif fault == "unaligned-directory":
        struct.pack_into("<I", data, 48, directory + 1)
    elif fault == "directory-over-script":
        struct.pack_into("<I", data, 48, room["programs"]["16:0"]["entry"] - 2)
    elif fault.startswith("model-"):
        value = {
            "model-unaligned": model + 1,
            "model-over-script": room["programs"]["16:0"]["entry"],
            "model-after-floor": layout["floor"],
        }[fault]
        struct.pack_into("<I", data, directory + 4, value)
    elif fault in (
        "flags",
        "zero-objects",
        "odd-objects",
        "short-body",
        "body-after-floor",
    ):
        at, value = {
            "flags": (4, 1),
            "zero-objects": (8, 0),
            "odd-objects": (8, 3),
            "short-body": (0, 12),
            "body-after-floor": (0, layout["floor"]),
        }[fault]
        struct.pack_into("<I", data, model + at, value)
    elif fault in ("vertex", "normal", "primitive", "uv-offset"):
        at = {"vertex": 0, "normal": 8, "primitive": 16, "uv-offset": 24}[fault]
        struct.pack_into("<I", data, model + 12 + at, 0)
    elif fault == "uv-tail-after-floor":
        struct.pack_into("<I", data, model + 12 + 20, 65535)
    else:
        struct.pack_into("<I", data, directory, len(data))
    data, room = rebound(data, room)
    assert isinstance(
        room_write_partitions(data, room, CONFIG), RoomWritePartitionFailure
    )


@pytest.mark.parametrize(
    "index,accepted", [(0, True), (2, True), (3, False), (255, False)]
)
def test_collision_index_skips_the_header_and_stays_in_declared_records(
    index, accepted
):
    data, room, layout = source(
        bytes([0x37, index, 0x80, 0]) + END, (END,), (ModelResourceState.Absent,), (0,)
    )
    result = room_write_partitions(data, room, CONFIG)
    assert isinstance(result, RoomWritePartitions) is accepted
    if accepted:
        assert result.source_writes[0].writes == (
            SourceRange(layout["collision"] + (index + 1) * 16 + 8, 2),
        )
    else:
        assert result is RoomWritePartitionFailure.Collision


@pytest.mark.parametrize(
    "fault", ["missing", "unaligned", "over-script", "oversized-count"]
)
def test_collision_headers_and_full_regions_are_bounded(fault):
    data, room, layout = source(
        bytes([0x37, 0, 0x80, 0]) + END, (END,), (ModelResourceState.Absent,), (0,)
    )
    data = bytearray(data)
    if fault == "oversized-count":
        struct.pack_into("<I", data, layout["collision"] + 4, 0x10000000)
    else:
        value = {
            "missing": 0,
            "unaligned": layout["collision"] + 1,
            "over-script": room["programs"]["16:0"]["entry"],
        }[fault]
        struct.pack_into("<I", data, 32, value)
    data, room = rebound(data, room)
    assert isinstance(
        room_write_partitions(data, room, CONFIG), RoomWritePartitionFailure
    )


def test_shared_sca_bounds_do_not_implicitly_require_a_heap_floor():
    data, room, layout = source(
        bytes([0x37, 2, 0x80, 0]) + END,
        (END,),
        (ModelResourceState.Absent,),
        (0,),
    )
    data = bytearray(data)
    struct.pack_into("<I", data, 16, layout["collision"])
    data, room = rebound(data, room)
    result = sca_write_partition(
        data, tuple(room["section_offsets"]), room["programs"]["16:0"]["entry"]
    )
    assert result == ScaWritePartition(
        SourceRange(layout["collision"], 64),
        SourceRange(layout["collision"] + 56, 2),
    )
    assert (
        room_write_partitions(data, room, CONFIG)
        is RoomWritePartitionFailure.SourceOverlap
    )


@pytest.mark.parametrize(
    "fault", ["stale-directory", "truncated-section", "wrong-command", "outside-source"]
)
def test_shared_sca_bounds_reject_corrupt_source_and_packet_bindings(fault):
    data, room, layout = source(
        bytes([0x37, 0, 0x80, 0]) + END,
        (END,),
        (ModelResourceState.Absent,),
        (0,),
    )
    data = bytearray(data)
    position = room["programs"]["16:0"]["entry"]
    if fault == "stale-directory":
        struct.pack_into("<I", data, 32, layout["collision"] + 4)
    elif fault == "truncated-section":
        struct.pack_into("<I", data, 8 + 9 * 4, layout["collision"] + 60)
        room["section_offsets"][9] = layout["collision"] + 60
    elif fault == "wrong-command":
        data[position] = 0
    else:
        position = len(data)
    result = sca_write_partition(bytes(data), tuple(room["section_offsets"]), position)
    assert isinstance(result, RoomWritePartitionFailure)


@pytest.mark.parametrize("four_point", [False, True])
def test_kind13_camera_volume_uses_first_native_byte_search_not_camera_index(
    four_point,
):
    target = bytearray(item_command(20, 15, 92, slot=9))
    target[20] = 1
    trigger = camera_trigger(1, 9, 6, four_point)
    data, room, layout = source(
        trigger + END,
        (bytes(target) + END,),
        (ModelResourceState.Absent,) * 2,
        (1, 6, 0, 6),
    )
    result = room_write_partitions(data, room, CONFIG)
    assert isinstance(result, RoomWritePartitions)
    write = result.source_writes[0]
    assert write.writes == tuple(
        SourceRange(layout["rvd"] + 20 + field, 2) for field in range(4, 20, 2)
    )
    assert result.objects[0].slot == 1
    assert result.objects[0].model is ModelResourceState.NotAccessed


@pytest.mark.parametrize(
    "fault",
    [
        "flag",
        "target",
        "camera",
        "missing-target",
        "wrong-kind",
        "four-point-target",
        "model",
        "acquisition",
        "missing-camera",
        "missing-sentinel",
        "short-record",
        "rvd-over-script",
        "reset-kind",
        "reset-geometry",
    ],
)
def test_kind13_requires_payload_target_model_and_bounded_camera_resource(fault):
    target = bytearray(item_command(20, 15, 92, slot=9))
    target[20] = 1
    trigger = camera_trigger(
        64 if fault == "flag" else 1,
        32 if fault == "target" else 9,
        7 if fault == "camera" else 6,
    )
    if fault == "wrong-kind":
        target = bytearray(bytes([0x2C, 9, 4, 0x31]) + bytes(16))
    elif fault == "four-point-target":
        target[3] |= 0x80
    elif fault == "model":
        target[20] = 32
    elif fault == "acquisition":
        struct.pack_into("<H", target, 18, 256)
    main = bytes(target) + END if fault != "missing-target" else END
    if fault in ("reset-kind", "reset-geometry"):
        main = (
            bytes(target)
            + bytes(
                [
                    0x46,
                    9,
                    4 if fault == "reset-kind" else 2,
                    0xB1 if fault == "reset-geometry" else 0x31,
                ]
            )
            + bytes(6)
            + END
        )
    data, room, layout = source(
        trigger + END,
        (main,),
        (ModelResourceState.Absent,) * 2,
        (1, 0) if fault == "missing-camera" else (1, 6),
    )
    data = bytearray(data)
    if fault == "missing-sentinel":
        data[layout["floor"] - 4 : layout["floor"]] = bytes(4)
    elif fault == "short-record":
        struct.pack_into("<I", data, 16, layout["rvd"] + 4)
    elif fault == "rvd-over-script":
        struct.pack_into("<I", data, 40, room["programs"]["16:0"]["entry"] - 2)
    data, room = rebound(data, room)
    assert isinstance(
        room_write_partitions(data, room, CONFIG), RoomWritePartitionFailure
    )


@pytest.mark.parametrize("opcode,sat,width", [(0x3B, 0x31, 32), (0x68, 0xB1, 40)])
def test_door_creator_packets_are_protected_with_their_native_width(opcode, sat, width):
    door = bytes([opcode, 0, 1, sat]) + bytes(width - 4)
    data, room, _ = source(door + END, (END,), (ModelResourceState.Absent,), (0,))
    result = room_write_partitions(data, room, CONFIG)
    assert isinstance(result, RoomWritePartitions)
    expected = SourceRange(room["programs"]["16:0"]["entry"], width)
    assert result.door_creators == (expected,)
    assert expected in result.protected_source


def test_bounded_alternate_item_models_and_reset_keep_all_possible_record_domains():
    first = bytearray(item_command(20, 15, 92, slot=9))
    second = bytearray(item_command(21, 7, 92, slot=9))
    first[20], second[20] = 0, 1
    reset = bytes([0x46, 9, 2, 0x31]) + struct.pack("<3H", 20, 15, 255)
    data, room, _ = source(
        camera_trigger(1, 9, 6) + END,
        (bytes(first) + bytes(second) + reset + END,),
        (ModelResourceState.Absent,) * 2,
        (6,),
    )
    result = room_write_partitions(data, room, CONFIG)
    assert isinstance(result, RoomWritePartitions)
    assert [row.slot for row in result.objects] == [0, 1]
    assert all(row.model is ModelResourceState.NotAccessed for row in result.objects)


@pytest.mark.parametrize("programs", [None, [], "invalid"])
def test_malformed_external_program_container_has_a_modeled_failure(programs):
    data, room, _ = source(END, (END,), (ModelResourceState.Absent,), (0,))
    room["programs"] = programs
    assert (
        room_write_partitions(data, room, CONFIG)
        is RoomWritePartitionFailure.SourceBinding
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("aot_address", True),
        ("aot_address", 0x800CE559),
        ("aot_capacity", 0),
        ("object_capacity", True),
        ("object_address", 0x8011A000),
        ("object_address", 0x800CE558),
        ("item_flag_count", 0),
        ("interaction_flag_count", 33),
    ],
)
def test_revision_configuration_asserts_programmer_invariants(field, value):
    with pytest.raises(AssertionError):
        replace(CONFIG, **{field: value})


def test_configuration_is_required_and_none_never_selects_a_fallback():
    data, room, _ = source(END, (END,), (ModelResourceState.Absent,), (0,))
    with pytest.raises(TypeError):
        room_write_partitions(data, room)
    with pytest.raises(AssertionError):
        room_write_partitions(data, room, None)
