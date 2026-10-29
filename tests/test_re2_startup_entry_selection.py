"""Entry routing requires pinned native resources and the full source corpus."""

import copy
import hashlib
import json
from dataclasses import replace

import pytest
from test_re2_metadata import ROOT

from games.re2.startup_entry_selection import (
    EXECUTABLE_SHA256,
    EntrySelectionConfig,
    EntrySelectionFailure,
    EntrySelectionResource,
    EntrySelectionSource,
    VerifiedEntrySelection,
    bind_entry_selection,
    entry_selection_config,
)


@pytest.fixture
def manifest():
    return json.loads((ROOT / "profiles/re2_leon_a_slus00748.json").read_text())[
        "startup_declaration_audit"
    ]


@pytest.fixture
def config(manifest):
    return entry_selection_config(
        manifest["selection"],
        tuple(EntrySelectionResource(**row) for row in manifest["resources"]),
        manifest["executable_sha256"],
    )


def test_pinned_entry_manifest_binds_all_sources_and_native_resources(config):
    assert isinstance(config, EntrySelectionConfig)
    assert len(config.resources) == 69
    assert len(config.sources) == 125
    assert len(config.resource_lookup) == len(config.resources)
    assert len(config.source_lookup) == len(config.sources)
    assert next(row for row in config.sources if row.room_id == "00-02").path == (
        "PL0/RDT/ROOM1020.RDT"
    )


@pytest.mark.parametrize(
    "fault",
    [
        "scope",
        "source-hash",
        "source-index",
        "source-lba",
        "resource-index",
        "extra",
        "revision",
        "resource-hash",
        "resource-order",
    ],
)
def test_manifest_drift_fails_startup_instead_of_inventing_an_entry(manifest, fault):
    raw = copy.deepcopy(manifest["selection"])
    resources = tuple(EntrySelectionResource(**row) for row in manifest["resources"])
    revision = manifest["executable_sha256"]
    if fault == "scope":
        raw["scope"] = "memory-card-startup"
    elif fault == "source-hash":
        raw["sources"][0]["sha256"] = "0" * 64
    elif fault == "source-index":
        raw["sources"][0]["file_index"] += 1
    elif fault == "source-lba":
        raw["sources"][0]["lba"] += 1
    elif fault == "resource-index":
        raw["resource_lookup"][0]["file_index"] += 1
    elif fault == "extra":
        raw["allow_unverified"] = True
    elif fault == "revision":
        revision = "0" * 64
    elif fault == "resource-hash":
        resources = (replace(resources[0], sha256="0" * 64), *resources[1:])
    else:
        resources = tuple(reversed(resources))
    with pytest.raises(ValueError, match="entry selection"):
        entry_selection_config(raw, resources, revision)


def test_native_revision_failure_precedes_resource_or_source_access(config):
    assert (
        bind_entry_selection(config, b"another executable", {}, {})
        is EntrySelectionFailure.Revision
    )


@pytest.mark.parametrize("domain", ["source", "resource", "lookup"])
def test_typed_config_construction_cannot_bypass_the_manifest(config, domain):
    with pytest.raises(AssertionError):
        if domain == "source":
            replace(
                config,
                sources=(
                    replace(config.sources[0], sha256="0" * 64),
                    *config.sources[1:],
                ),
            )
        elif domain == "resource":
            replace(
                config,
                resources=(
                    replace(config.resources[0], sha256="0" * 64),
                    *config.resources[1:],
                ),
            )
        else:
            replace(config, resource_lookup=config.resource_lookup[:-1])


def test_verified_receipt_requires_the_fresh_source_and_qualified_stage():
    data = b"explicit synthetic source"
    sha = hashlib.sha256(data).hexdigest()
    source = EntrySelectionSource("00-02", "PL0/RDT/ROOM1020.RDT", len(data), sha)
    # This explicit test receipt does not stand in for the production binder.
    # It isolates the source gate without copyrighted fixture resources.
    receipt = VerifiedEntrySelection(
        EXECUTABLE_SHA256, (), (source,), frozenset({0}), (("00-02", (2, 10)),)
    )
    room = {
        "stage": 0,
        "room": 2,
        "id": source.room_id,
        "source": source.path,
        "size": len(data),
        "sha256": sha,
    }
    assert receipt.covers_source(data, room)
    assert receipt.models_for("00-02") == (2, 10)
    assert receipt.models_for("01-01") == ()
    assert not receipt.covers_source(data + b"\0", room)
    for key, value in (
        ("stage", 1),
        ("stage", False),
        ("room", 3),
        ("id", "00-03"),
        ("source", "PL0/RDT/ROOM1030.RDT"),
        ("size", len(data) + 1),
        ("sha256", "0" * 64),
    ):
        assert not receipt.covers_source(data, {**room, key: value})


@pytest.mark.parametrize("models", [(10, 2), (2, 2), (True,), (-1,), (256,)])
def test_receipt_cannot_hide_conflicting_or_invalid_model_bindings(models):
    with pytest.raises(AssertionError):
        VerifiedEntrySelection(
            EXECUTABLE_SHA256, (), (), frozenset({0}), (("00-02", models),)
        )
