"""Shared source identity/bounds, without a campaign-admission capability."""

import hashlib
import json
import struct
from dataclasses import FrozenInstanceError, replace
from types import SimpleNamespace

import pytest
from test_re3_native_contracts import coherent as coherent  # noqa: PLC0414
from test_re3_room_data import synthetic_room

from games.re3 import source_witnesses as shared
from games.re3.room_data import RoomFormatFailure
from games.runtime_identity import RuntimeSignature


def synthetic_manifest_hash(sources):
    records = sorted(
        [
            s.path,
            s.stage_digit,
            s.room_number,
            s.ard_lba,
            s.ard_size,
            len(s.rdt),
            hashlib.sha256(s.rdt).hexdigest(),
        ]
        for s in sources
    )
    return hashlib.sha256(
        json.dumps(records, separators=(",", ":")).encode()
    ).hexdigest()


@pytest.fixture
def catalog(coherent, monkeypatch):
    # Bind one wholly synthetic corpus through the real mandatory hash gates;
    # production has no fixture or caller-supplied expected-hash alternative.
    monkeypatch.setattr(
        shared, "_SOURCE_CATALOG_SHA256", synthetic_manifest_hash((coherent.source,))
    )
    result = shared.bind_source_catalog(coherent.executable, (coherent.source,))
    assert isinstance(result, shared.SourceCatalog)
    return result


def test_unbound_compiler_and_partial_native_binding_do_not_construct_live_catalog(
    coherent,
):
    compiled = shared.compile_source_witness(coherent.source)
    partial = shared.bind_diagnostic_sources(coherent.executable, (coherent.source,))
    assert isinstance(compiled, shared.SourceWitness)
    assert not isinstance(compiled, shared.BoundSource)
    assert isinstance(partial, tuple) and isinstance(partial[0], shared.BoundSource)
    result = shared.bind_source_catalog(coherent.executable, (coherent.source,))
    assert isinstance(result, RoomFormatFailure)
    assert "complete revision corpus" in result.detail


def test_catalog_lookup_uses_zero_based_signed_native_selectors(catalog, coherent):
    source = catalog.lookup(0, 0)
    assert isinstance(source, shared.BoundSource)
    assert source.source == coherent.source
    assert (source.rdt_size, source.camera_count, source.native_file_index) == (
        200,
        1,
        0x100,
    )
    for stage, room in ((-1, 0), (0, -1), (1, 0), (7, 0), (0, 32767)):
        assert isinstance(catalog.lookup(stage, room), RoomFormatFailure)


def test_catalog_and_source_payloads_are_immutable(catalog):
    with pytest.raises(FrozenInstanceError):
        catalog.sources = ()
    with pytest.raises(FrozenInstanceError):
        catalog.sources[0].cameras = b"x"
    assert type(catalog.sources) is tuple
    assert type(catalog.sources[0].source.rdt) is bytes
    with pytest.raises(AssertionError):
        shared.SourceCatalog((), catalog.runtime_signature, object())


@pytest.mark.parametrize("field", ["cameras", "zones"])
@pytest.mark.parametrize("buffer", [bytearray, memoryview])
def test_equal_mutable_witness_buffers_cannot_reuse_a_catalog_receipt(
    catalog, field, buffer
):
    witness = catalog.sources[0]
    changed = buffer(bytearray(getattr(witness, field)))
    assert changed == getattr(witness, field)
    # Reject before an equal buffer reaches the catalog. Otherwise changing
    # its backing bytes later could rewrite the supposedly owned witness.
    with pytest.raises(AssertionError):
        replace(catalog, sources=(replace(witness, **{field: changed}),))


@pytest.mark.parametrize("field", ["cameras", "zones"])
def test_unbound_source_compilation_also_requires_immutable_buffers(coherent, field):
    witness = shared.compile_source_witness(coherent.source)
    assert isinstance(witness, shared.SourceWitness)
    with pytest.raises(AssertionError):
        replace(witness, **{field: bytearray(getattr(witness, field))})


@pytest.mark.parametrize(
    "field",
    [
        "rdt_size",
        "camera_count",
        "cameras_offset",
        "zones_offset",
        "initializer_offset",
        "initializer_end",
        "native_file_index",
    ],
)
def test_numeric_aliases_cannot_change_compiled_witness_field_types(catalog, field):
    witness = catalog.sources[0]
    with pytest.raises(AssertionError):
        replace(witness, **{field: float(getattr(witness, field))})


def test_section_words_are_an_immutable_tuple_of_native_integers(catalog):
    witness = catalog.sources[0]
    with pytest.raises(AssertionError):
        replace(witness, section_words=list(witness.section_words))
    words = tuple(float(word) for word in witness.section_words)
    assert words == witness.section_words
    with pytest.raises(AssertionError):
        replace(witness, section_words=words)
    with pytest.raises(AssertionError):
        replace(witness, camera_count=True)


@pytest.mark.parametrize("change", ["sources", "signature"])
def test_replacing_a_catalog_cannot_remove_source_or_revision_binding(catalog, change):
    changed = (
        {"sources": ()}
        if change == "sources"
        else {
            "runtime_signature": RuntimeSignature(
                (), 32, hashlib.sha256(b"").hexdigest()
            )
        }
    )
    with pytest.raises(AssertionError):
        replace(catalog, **changed)


@pytest.mark.parametrize("change", ["cameras", "section_words", "camera_count"])
def test_replacing_compiled_witness_fields_cannot_reuse_catalog_binding(
    catalog, change
):
    witness = catalog.sources[0]
    altered = replace(
        witness,
        **{
            "cameras": {"cameras": b""},
            "section_words": {"section_words": (0,) * 21},
            "camera_count": {"camera_count": 0},
        }[change],
    )
    assert altered.source == witness.source
    with pytest.raises(AssertionError):
        replace(catalog, sources=(altered,))


def test_runtime_signature_retains_all_four_general_code_witnesses(catalog, coherent):
    signature = catalog.runtime_signature
    assert signature.window_addresses == shared.CODE_WINDOWS
    assert signature.window_width == 32

    def read(address, width):
        offset = address - 0x80000000
        return SimpleNamespace(
            ok=True, data=coherent.ram[offset : offset + width], error=""
        )

    result = signature.verify(read)
    assert result.ok and result.value
    coherent.ram[shared.CODE_WINDOWS[-1] - 0x80000000] ^= 1
    result = signature.verify(read)
    assert result.ok and not result.value


@pytest.mark.parametrize("change", ["executable", "rdt", "lba", "size", "missing"])
def test_catalog_binding_fails_explicitly_on_external_identity_change(
    catalog, coherent, change
):
    executable, sources = coherent.executable, (coherent.source,)
    if change == "executable":
        executable += b"x"
    elif change == "rdt":
        data = bytearray(coherent.source.rdt)
        data[188] ^= 1
        sources = (replace(coherent.source, rdt=bytes(data)),)
    elif change == "lba":
        sources = (replace(coherent.source, ard_lba=25),)
    elif change == "size":
        sources = (replace(coherent.source, ard_size=coherent.source.ard_size + 1),)
    else:
        sources = ()
    result = shared.bind_source_catalog(executable, sources)
    assert isinstance(result, RoomFormatFailure)


def test_full_executable_gate_precedes_source_interpretation(coherent):
    invalid = replace(coherent.source, rdt=b"invalid")
    result = shared.bind_source_catalog(coherent.executable + b"x", (invalid,))
    assert isinstance(result, RoomFormatFailure) and result.kind == "executable"
    result = shared.compile_source_witness(invalid)
    assert (
        isinstance(result, RoomFormatFailure) and "Invalid room source" in result.detail
    )


def test_native_metadata_masks_tag_bytes_and_rejects_duplicate_identifiers(coherent):
    result = shared.bind_diagnostic_sources(coherent.executable, (coherent.source,))
    assert isinstance(result, tuple) and result[0].native_file_index == 0x100
    duplicate = shared.bind_diagnostic_sources(
        coherent.executable, (coherent.source, coherent.source)
    )
    assert isinstance(duplicate, RoomFormatFailure)
    assert "Duplicate source stage/room" in duplicate.detail


@pytest.mark.parametrize("change", ["same-witness", "same-path"])
def test_catalog_binding_rejects_ambiguity_and_duplicate_paths(
    coherent, monkeypatch, change
):
    other = replace(
        coherent.source, path="CD_DATA/STAGE2/R200.ARD", stage_digit=2, ard_lba=25
    )
    if change == "same-path":
        data = bytearray(other.rdt)
        data[104] ^= 1
        other = replace(other, path=coherent.source.path, rdt=bytes(data))
    sources = (coherent.source, other)
    monkeypatch.setattr(
        shared, "_SOURCE_CATALOG_SHA256", synthetic_manifest_hash(sources)
    )
    result = shared.bind_source_catalog(coherent.executable, sources)
    assert isinstance(result, RoomFormatFailure)
    assert "duplicate paths or ambiguous witnesses" in result.detail


def test_ranges_match_original_relocation_with_zero_masks_and_opaque_word(coherent):
    data = bytearray(coherent.source.rdt)
    struct.pack_into("<I", data, 16, 0xDEADBEEF)
    source = shared.compile_source_witness(replace(coherent.source, rdt=bytes(data)))
    assert isinstance(source, shared.SourceWitness)
    ranges = source.ranges(0x80100000)
    assert isinstance(ranges, tuple)
    assert [offset for offset, _ in ranges] == [1, 8, 96, 128]
    header = struct.unpack("<21I", ranges[1][1])
    assert header[0] == 0
    assert header[2] == (0xDEADBEEF + 0x80100000) & 0xFFFFFFFF
    assert struct.unpack_from("<I", ranges[2][1], 28)[0] == 0x80100000
    assert ranges[3][1] == data[128:152]
    assert ranges[3][1][-4:] == b"\xff" * 4


@pytest.mark.parametrize("base", [0, 0xA0100000, 0x80100001, 0x80200000 - 196])
def test_ranges_require_the_whole_aligned_cached_ram_extent(coherent, base):
    source = shared.compile_source_witness(coherent.source)
    assert isinstance(source.ranges(base), RoomFormatFailure)


def test_ranges_accept_the_exact_last_fitting_aligned_extent(coherent):
    source = shared.compile_source_witness(coherent.source)
    assert isinstance(source.ranges(0x80200000 - 200), tuple)


def test_large_camera_ranges_are_split_without_omitting_bytes(coherent):
    original = synthetic_room()
    count = 140
    extra = (count - 1) * 32
    data = original[:96] + original[96:128] * count + original[128:]
    data[1] = count
    for index in range(22):
        value = struct.unpack_from("<I", data, 8 + index * 4)[0]
        if value >= 128:
            struct.pack_into("<I", data, 8 + index * 4, value + extra)
    source = shared.compile_source_witness(replace(coherent.source, rdt=bytes(data)))
    assert isinstance(source, shared.SourceWitness)
    ranges = source.ranges(0x80100000)
    assert isinstance(ranges, tuple)
    assert all(0 < len(expected) <= 4096 for _, expected in ranges)
    cameras = [
        (offset, expected)
        for offset, expected in ranges
        if 96 <= offset < 96 + count * 32
    ]
    assert [offset for offset, _ in cameras] == [96, 96 + 4096]
    expected = bytearray(original[96:128])
    struct.pack_into("<I", expected, 28, 0x80100000)
    assert b"".join(packet for _, packet in cameras) == expected * count


def test_normalized_fingerprint_is_base_independent_and_conservative(coherent):
    source = shared.compile_source_witness(coherent.source)
    data = bytearray(coherent.source.rdt)
    data[0] = 100
    struct.pack_into("<I", data, 8 + 21 * 4, 200)
    data[188] ^= 1
    data[132] ^= 1
    changed = shared.compile_source_witness(replace(coherent.source, rdt=bytes(data)))
    assert isinstance(changed, shared.SourceWitness)
    assert changed.normalized_fingerprint == source.normalized_fingerprint
    assert changed.ranges(0x80100000) != source.ranges(0x80100000)
    assert source.ranges(0x80100000) != source.ranges(0x80110000)


def test_ambiguity_key_cannot_use_an_opaque_word_that_relocates_to_zero(coherent):
    ordinary = shared.compile_source_witness(coherent.source)
    data = bytearray(coherent.source.rdt)
    struct.pack_into("<I", data, 16, 0x7FF00000)
    wrapped = shared.compile_source_witness(replace(coherent.source, rdt=bytes(data)))
    assert wrapped.normalized_fingerprint == ordinary.normalized_fingerprint
    assert wrapped.ranges(0x80100000) == ordinary.ranges(0x80100000)
