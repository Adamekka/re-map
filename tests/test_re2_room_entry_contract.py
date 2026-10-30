"""Native entry capabilities require an exact audit and every owned resource."""

import copy
import hashlib
import json
import struct
import sys
from dataclasses import asdict, replace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from games.re2 import room_entry_contract as entry


def _seal_test_manifest(raw, monkeypatch):
    # Only tests may select synthetic byte identities. Production accepts the
    # single digest for the recipe recorded in the revision profile.
    monkeypatch.setattr(
        entry, "AUDITED_ROOM_ENTRY_MANIFEST_SHA256", entry._manifest_digest(raw)
    )
    config = entry.room_entry_contract({"room_entry_contract": raw})
    assert isinstance(config, entry.RoomEntryContractConfig)
    return config


@pytest.fixture
def resources(monkeypatch):
    profile_path = (
        Path(__file__).resolve().parents[1] / "profiles/re2_leon_a_slus00748.json"
    )
    config = entry.room_entry_contract(json.loads(profile_path.read_text()))
    assert isinstance(config, entry.RoomEntryContractConfig)
    executable = bytearray(0xF1000)
    executable[:8] = b"PS-X EXE"
    struct.pack_into("<4I", executable, 0x10, 0x80078408, 0, 0x80010000, 0xF0800)

    def offset(address):
        return 0x800 + address - 0x80010000

    for address, value in (
        (0x800A74C8 + 3 * 4, 0x80053878),
        (0x800A74C8 + 4 * 4, 0x800538A4),
        (0x800A74C8 + 0x18 * 4, 0x800541A8),
        (0x800A73C4 + 5 * 4, 0x80051980),
    ):
        struct.pack_into("<I", executable, offset(address), value)
    for stage in config.stage_entries:
        stage_load = stage.load
        struct.pack_into(
            "<3I",
            executable,
            offset(
                int(stage_load.recipe_table_address_ps1, 0)
                + stage_load.recipe_index * 12
            ),
            stage_load.file_index,
            int(stage_load.entry_address_ps1, 0),
            int(stage_load.destination_pointer_address_ps1, 0),
        )
        struct.pack_into(
            "<I",
            executable,
            offset(int(stage_load.destination_pointer_address_ps1, 0)),
            int(stage_load.destination_address_ps1, 0),
        )
        struct.pack_into(
            "<II",
            executable,
            offset(0x800988A4 + stage_load.file_index * 8),
            stage.resource.width,
            stage_load.file_lba | stage_load.file_flags << 24,
        )
    archive = bytearray(
        max(row.sector * 2048 + row.width for row in config.actor_codes)
    )
    codes = []
    for row in config.actor_codes:
        code = bytes([row.resource_index]) * row.width
        archive[row.sector * 2048 : row.sector * 2048 + row.width] = code
        struct.pack_into(
            "<II",
            executable,
            offset(0x8009ADF4 + row.resource_index * 8),
            row.sector,
            row.width,
        )
        codes.append(replace(row, sha256=hashlib.sha256(code).hexdigest()))
    doors, bound_doors = {}, []
    for row in config.doors:
        data = bytearray([row.model]) * row.width
        start = row.payload_sector * 2048
        struct.pack_into("<II", data, start, 8 + row.script_width, 2048)
        struct.pack_into(
            "<H", executable, offset(0x8009A4B0 + row.model * 2), row.file_index
        )
        record = offset(0x800988A4 + row.file_index * 8)
        struct.pack_into("<I", executable, record, row.width)
        executable[record + 4 : record + 7] = row.lba.to_bytes(3, "little")
        struct.pack_into(
            "<HHII",
            executable,
            offset(0x8009A520 + row.model * 12),
            0,
            row.payload_width,
            row.payload_sector,
            0,
        )
        doors[row.model] = bytes(data)
        bound_doors.append(
            replace(
                row,
                sha256=hashlib.sha256(data).hexdigest(),
                script_sha256=hashlib.sha256(
                    data[start + 8 : start + 8 + row.script_width]
                ).hexdigest(),
            )
        )
    stages = {
        row.stage: bytes([0x5A + row.stage]) * row.resource.width
        for row in config.stage_entries
    }
    # Tests replace only the expected content hashes so no native code or
    # copyrighted resource is stored as a fixture. This tests binding, not the
    # semantic audit attached to the real production hashes.
    raw = asdict(config)
    raw["executable_sha256"] = hashlib.sha256(executable).hexdigest()
    for row in raw["stage_entries"]:
        row["resource"]["sha256"] = hashlib.sha256(stages[row["stage"]]).hexdigest()
    raw["actor_codes"] = [asdict(row) for row in codes]
    raw["doors"] = [asdict(row) for row in bound_doors]
    config = _seal_test_manifest(raw, monkeypatch)
    return config, bytes(executable), stages, bytes(archive), doors


def test_missing_contract_is_explicitly_unaudited():
    assert entry.room_entry_contract({}) is entry.RoomEntryContractSupport.Unaudited


def test_profile_owns_the_exact_audited_recipe():
    path = Path(__file__).resolve().parents[1] / "profiles/re2_leon_a_slus00748.json"
    profile = json.loads(path.read_text())
    assert isinstance(entry.room_entry_contract(profile), entry.RoomEntryContractConfig)
    assert (
        entry._manifest_digest(profile["room_entry_contract"])
        == entry.AUDITED_ROOM_ENTRY_MANIFEST_SHA256
    )


def test_manifest_binds_every_audited_variant_and_preset(resources):
    config, *_ = resources
    profile = {"room_entry_contract": json.loads(json.dumps(asdict(config)))}
    assert entry.room_entry_contract(profile) == config


@pytest.mark.parametrize(
    "case",
    (
        "null",
        "unknown-audit",
        "missing-stage",
        "boolean-stage",
        "floating-stage",
        "wrong-executable",
        "stage-path",
        "stage-load",
        "missing-actor-pool",
        "actor-sector",
        "actor-load-address",
        "constructor-preset",
        "floating-model",
        "missing-door",
        "door-payload",
        "native-layout",
        "write-layout",
        "extra-field",
    ),
)
def test_manifest_drift_is_a_modeled_failure(resources, case):
    config, *_ = resources
    raw = json.loads(json.dumps(asdict(config)))
    if case == "null":
        raw = None
    elif case == "unknown-audit":
        raw["audit"] = "another-native-contract"
    elif case == "missing-stage":
        del raw["stage_entries"]
    elif case == "boolean-stage":
        raw["stage_entries"][0]["stage"] = True
    elif case == "floating-stage":
        raw["stage_entries"][0]["stage"] = 1.0
    elif case == "wrong-executable":
        raw["executable_sha256"] = "0" * 64
    elif case == "stage-path":
        raw["stage_entries"][0]["resource"]["path"] = "COMMON/BIN/STAGE3.BIN"
    elif case == "stage-load":
        raw["stage_entries"][0]["load"]["recipe_index"] -= 1
    elif case == "missing-actor-pool":
        raw["actor_codes"].pop()
    elif case == "actor-sector":
        raw["actor_codes"][0]["sector"] += 1
    elif case == "actor-load-address":
        raw["actor_codes"][0]["load_address_ps1"] = "0x80100000"
    elif case == "constructor-preset":
        raw["constructor_presets"][0][1] = 0
    elif case == "floating-model":
        raw["constructor_presets"][0][0] = 34.0
    elif case == "missing-door":
        raw["doors"].pop()
    elif case == "door-payload":
        raw["doors"][0]["script_width"] -= 1
    elif case == "native-layout":
        raw["native_layout"]["actor_code_pool_stride"] += 4
    elif case == "write-layout":
        raw["write_partitions"]["object_capacity"] -= 1
    elif case == "extra-field":
        raw["allow_unknown"] = True
    else:
        raise AssertionError(case)
    assert (
        entry.room_entry_contract({"room_entry_contract": raw})
        is entry.RoomEntryContractFailure.Manifest
    )


def test_verified_contract_has_only_the_audited_capabilities(resources):
    result = entry.bind_room_entry_contract(*resources)
    assert isinstance(result, entry.VerifiedRoomEntryContract)
    assert result.minimum_source_address == 0x8011A000
    assert result.source_addresses == ((0, 0x8011A6A8), (1, 0x8011A65C))
    assert result.stages == frozenset({0, 1})
    assert result.roots == ("16:0", "17:0", "17:1")
    assert result.door_models == frozenset({0x01, 0x09, 0x0D})
    assert result.non_scheduling_interaction_kinds == frozenset({4, 10, 13})
    assert result.covers_constructor(0x22, 0x4402)
    assert not result.covers_constructor(0x22, 0)
    assert not result.covers_constructor(0x22, 0x4403)
    assert not result.covers_constructor(0x26, 0x4402)
    assert {row.resource_index for row in result.actor_code_images} == {72, 73}
    assert result.config == resources[0]
    assert result.executable_sha256 == resources[0].executable_sha256
    assert result.write_partitions.aot_address == 0x800CE558
    assert result.write_partitions.object_address == 0x800D0324
    assert result.write_partitions.aot_capacity == 32
    assert result.write_partitions.object_capacity == 32
    assert result.write_partitions.item_flag_count == 256
    assert result.write_partitions.interaction_flag_count == 64


@pytest.mark.parametrize(
    "source_addresses",
    (
        ((0, 0x8011A65C), (1, 0x8011A65C)),
        ((0, 0x8011A6A8), (1, 0x8011A6A8)),
        ((1, 0x8011A65C),),
    ),
)
def test_receipt_cannot_mix_stage_bases_or_omit_a_required_stage(
    resources, source_addresses
):
    receipt = entry.bind_room_entry_contract(*resources)
    assert isinstance(receipt, entry.VerifiedRoomEntryContract)
    with pytest.raises(AssertionError):
        replace(receipt, source_addresses=source_addresses)


@pytest.mark.parametrize(
    "case,expected",
    (
        ("executable-byte", entry.RoomEntryContractFailure.Executable),
        ("stage-byte", entry.RoomEntryContractFailure.StageResource),
        ("short-stage", entry.RoomEntryContractFailure.StageResource),
        ("actor-byte", entry.RoomEntryContractFailure.ActorResource),
        ("short-archive", entry.RoomEntryContractFailure.ActorResource),
        ("missing-door", entry.RoomEntryContractFailure.DoorResource),
        ("extra-door", entry.RoomEntryContractFailure.DoorResource),
        ("door-byte", entry.RoomEntryContractFailure.DoorResource),
        ("short-door", entry.RoomEntryContractFailure.DoorResource),
    ),
)
def test_resource_failures_never_produce_a_receipt(resources, case, expected):
    config, executable, stage, archive, doors = copy.deepcopy(resources)
    if case == "executable-byte":
        executable = executable[:-1] + bytes([executable[-1] ^ 1])
    elif case == "stage-byte":
        stage[0] = bytes([stage[0][0] ^ 1]) + stage[0][1:]
    elif case == "short-stage":
        stage[0] = stage[0][:-1]
    elif case == "actor-byte":
        archive = bytearray(archive)
        archive[config.actor_codes[0].sector * 2048] ^= 1
        archive = bytes(archive)
    elif case == "short-archive":
        archive = archive[:-1]
    elif case == "missing-door":
        del doors[9]
    elif case == "extra-door":
        doors[2] = bytes(32)
    elif case == "door-byte":
        doors[9] = bytes([doors[9][0] ^ 1]) + doors[9][1:]
    elif case == "short-door":
        doors[9] = doors[9][:-1]
    else:
        raise AssertionError(case)
    assert (
        entry.bind_room_entry_contract(config, executable, stage, archive, doors)
        is expected
    )


@pytest.mark.parametrize("stage", (0, 1))
@pytest.mark.parametrize("case", ("missing", "changed", "short", "swapped"))
def test_each_stage_requires_its_own_exact_resource(resources, stage, case):
    config, executable, stages, archive, doors = copy.deepcopy(resources)
    if case == "missing":
        del stages[stage]
    elif case == "changed":
        stages[stage] = bytes([stages[stage][0] ^ 1]) + stages[stage][1:]
    elif case == "short":
        stages[stage] = stages[stage][:-1]
    else:
        stages[stage] = stages[1 - stage]
    assert (
        entry.bind_room_entry_contract(config, executable, stages, archive, doors)
        is entry.RoomEntryContractFailure.StageResource
    )


def test_extra_stage_cannot_acquire_a_source_address(resources):
    config, executable, stages, archive, doors = resources
    assert (
        entry.bind_room_entry_contract(
            config, executable, stages | {2: b""}, archive, doors
        )
        is entry.RoomEntryContractFailure.StageResource
    )


@pytest.mark.parametrize("stage_entries", ((), "duplicate"))
def test_stage_entry_keys_are_unique_and_nonempty(
    resources, monkeypatch, stage_entries
):
    config, *_ = resources
    raw = asdict(config)
    raw["stage_entries"] = (
        (raw["stage_entries"][0],) * 2
        if stage_entries == "duplicate"
        else stage_entries
    )
    monkeypatch.setattr(
        entry, "AUDITED_ROOM_ENTRY_MANIFEST_SHA256", entry._manifest_digest(raw)
    )
    assert (
        entry.room_entry_contract({"room_entry_contract": raw})
        is entry.RoomEntryContractFailure.Manifest
    )


@pytest.mark.parametrize(
    "case,expected",
    (
        ("header", entry.RoomEntryContractFailure.NativeLayout),
        ("gosub-dispatch", entry.RoomEntryContractFailure.NativeLayout),
        ("event-dispatch", entry.RoomEntryContractFailure.NativeLayout),
        ("stage-recipe-file", entry.RoomEntryContractFailure.StageResource),
        ("stage-recipe-entry", entry.RoomEntryContractFailure.StageResource),
        ("stage-recipe-pointer", entry.RoomEntryContractFailure.StageResource),
        ("stage-destination", entry.RoomEntryContractFailure.StageResource),
        ("stage-file-width", entry.RoomEntryContractFailure.StageResource),
        ("stage-file-lba", entry.RoomEntryContractFailure.StageResource),
        ("stage-file-flags", entry.RoomEntryContractFailure.StageResource),
        ("stage-zero-recipe-file", entry.RoomEntryContractFailure.StageResource),
        ("stage-zero-recipe-entry", entry.RoomEntryContractFailure.StageResource),
        ("stage-zero-recipe-pointer", entry.RoomEntryContractFailure.StageResource),
        ("stage-zero-file-width", entry.RoomEntryContractFailure.StageResource),
        ("stage-zero-file-lba", entry.RoomEntryContractFailure.StageResource),
        ("stage-zero-file-flags", entry.RoomEntryContractFailure.StageResource),
        ("actor-sector", entry.RoomEntryContractFailure.ActorResource),
        ("actor-width", entry.RoomEntryContractFailure.ActorResource),
        ("door-file-index", entry.RoomEntryContractFailure.DoorResource),
        ("door-file-size", entry.RoomEntryContractFailure.DoorResource),
        ("door-lba", entry.RoomEntryContractFailure.DoorResource),
        ("door-payload-sector", entry.RoomEntryContractFailure.DoorResource),
        ("door-payload-width", entry.RoomEntryContractFailure.DoorResource),
    ),
)
def test_native_tables_bind_the_selected_resources(
    resources, monkeypatch, case, expected
):
    config, executable, stage, archive, doors = resources
    data = bytearray(executable)
    address, width = {
        "header": (0x8000F818, 4),
        "gosub-dispatch": (0x800A74C8 + 0x18 * 4, 4),
        "event-dispatch": (0x800A73C4 + 5 * 4, 4),
        "stage-recipe-file": (0x800A20B8 + 9 * 12, 4),
        "stage-recipe-entry": (0x800A20B8 + 9 * 12 + 4, 4),
        "stage-recipe-pointer": (0x800A20B8 + 9 * 12 + 8, 4),
        "stage-destination": (0x80010810, 4),
        "stage-file-width": (0x800988A4 + 8 * 8, 4),
        "stage-file-lba": (0x800988A4 + 8 * 8 + 4, 3),
        "stage-file-flags": (0x800988A4 + 8 * 8 + 7, 1),
        "stage-zero-recipe-file": (0x800A20B8 + 8 * 12, 4),
        "stage-zero-recipe-entry": (0x800A20B8 + 8 * 12 + 4, 4),
        "stage-zero-recipe-pointer": (0x800A20B8 + 8 * 12 + 8, 4),
        "stage-zero-file-width": (0x800988A4 + 7 * 8, 4),
        "stage-zero-file-lba": (0x800988A4 + 7 * 8 + 4, 3),
        "stage-zero-file-flags": (0x800988A4 + 7 * 8 + 7, 1),
        "actor-sector": (0x8009ADF4 + 72 * 8, 4),
        "actor-width": (0x8009ADF4 + 72 * 8 + 4, 4),
        "door-file-index": (0x8009A4B0 + 9 * 2, 2),
        "door-file-size": (0x800988A4 + 243 * 8, 4),
        "door-lba": (0x800988A4 + 243 * 8 + 4, 3),
        "door-payload-sector": (0x8009A520 + 9 * 12 + 4, 4),
        "door-payload-width": (0x8009A520 + 9 * 12 + 2, 2),
    }[case]
    offset = 0x800 + address - 0x80010000
    value = int.from_bytes(data[offset : offset + width], "little") + 1
    data[offset : offset + width] = value.to_bytes(width, "little")
    # Bypass only the synthetic fixture's outer hash to exercise each native
    # binding independently. Production manifests cannot change that hash.
    raw = asdict(config)
    raw["executable_sha256"] = hashlib.sha256(data).hexdigest()
    config = _seal_test_manifest(raw, monkeypatch)
    assert (
        entry.bind_room_entry_contract(config, bytes(data), stage, archive, doors)
        is expected
    )


@pytest.mark.parametrize("case", ["script-byte", "script-boundary"])
def test_door_code_hash_and_header_are_bound(resources, monkeypatch, case):
    config, executable, stage, archive, doors = resources
    row = config.doors[0]
    data = bytearray(doors[row.model])
    start = row.payload_sector * 2048
    data[start + (8 if case == "script-byte" else 0)] ^= 1
    doors = doors | {row.model: bytes(data)}
    raw = asdict(config)
    raw["doors"][0]["sha256"] = hashlib.sha256(data).hexdigest()
    config = _seal_test_manifest(raw, monkeypatch)
    assert (
        entry.bind_room_entry_contract(config, executable, stage, archive, doors)
        is entry.RoomEntryContractFailure.DoorResource
    )
