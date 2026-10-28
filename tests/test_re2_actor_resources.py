"""RE2-DS-005: source bounds must match the native resource and model header."""

import copy
import hashlib
import struct
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from build_re2_metadata import verify_actor_part_resource


@pytest.fixture
def resource():
    model = bytearray(128)
    struct.pack_into("<II", model, 0, 96, 8)
    struct.pack_into("<8I", model, 96, *range(8, 65, 8))
    struct.pack_into("<I", model, 72, 46)
    archive = bytes(2048) + model
    executable = bytearray(4096)
    struct.pack_into("<I", executable, 0x18, 0x80010000)
    table = 0x80010040
    entry = 0x800 + 0x40 + 75 * 8
    struct.pack_into("<II", executable, entry, 1, len(model))
    proof = {
        "model_type": 34,
        "part_count": 23,
        "resource_sector": 1,
        "resource_width": len(model),
        "resource_sha256": hashlib.sha256(model).hexdigest(),
    }
    return executable, archive, proof, table


def test_actor_model_bounds_bind_native_lookup_and_resource_header(resource):
    verify_actor_part_resource(*resource)


@pytest.mark.parametrize(
    "case",
    [
        "short-executable",
        "table-outside",
        "table-in-header",
        "model-type",
        "sector",
        "width",
        "archive-truncated",
        "hash",
        "section-count",
        "directory-before-header",
        "directory-outside",
        "model-before-header",
        "model-outside",
        "zero-parts",
        "odd-object-count",
        "part-count",
    ],
)
def test_actor_resource_validation_rejects_incoherent_bounds(resource, case):
    executable, archive, proof, table = copy.deepcopy(resource)
    if case == "short-executable":
        executable = executable[:20]
    elif case == "table-outside":
        table = 0x80100000
    elif case == "table-in-header":
        table = 0x8000F000
    elif case == "model-type":
        proof["model_type"] = 35
    elif case in ("sector", "width"):
        proof["resource_" + case] += 1
    elif case == "archive-truncated":
        archive = archive[:-1]
    elif case == "hash":
        proof["resource_sha256"] = "0" * 64
    elif case == "part-count":
        proof["part_count"] -= 1
    else:
        model = bytearray(archive[2048:])
        if case == "section-count":
            struct.pack_into("<I", model, 4, 7)
        elif case.startswith("directory-"):
            struct.pack_into("<I", model, 0, 4 if case.endswith("header") else 100)
        elif case.startswith("model-"):
            struct.pack_into("<I", model, 124, 4 if case.endswith("header") else 96)
        else:
            struct.pack_into("<I", model, 72, 0 if case == "zero-parts" else 45)
        archive = bytes(2048) + model
        proof["resource_sha256"] = hashlib.sha256(model).hexdigest()
    with pytest.raises(ValueError, match="RE2 actor-part"):
        verify_actor_part_resource(executable, archive, proof, table)
