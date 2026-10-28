"""Both language resources, including the final entry's native FE bound."""

import hashlib
import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from games.re2.nonchoice_messages import (
    NonchoiceMessageFailure,
    nonchoice_message_proofs,
)


def messages(text=b"\xfa\x02\x01\xfc\xfd\0\xfe\0", tail=b"\xf8\xff\xfb\xff"):
    data = bytearray(104)
    offsets = [0] * 23
    for section in (13, 14):
        offsets[section] = len(data)
        data.extend(struct.pack("<3H", 6, 8, 12) + b"\xfe\0\xfe\0\0\0" + text + tail)
    struct.pack_into("<23I", data, 8, *offsets)
    return bytes(data), tuple(offsets)


def test_final_message_hashes_only_its_real_entry_and_consumed_text():
    data, offsets = messages()
    proofs = nonchoice_message_proofs(data, offsets, 2)
    assert isinstance(proofs, tuple) and len(proofs) == 4
    for section, directory, text in zip(
        (13, 14), proofs[::2], proofs[1::2], strict=True
    ):
        assert (directory["offset"], directory["width"]) == (offsets[section] + 4, 2)
        assert (text["offset"], text["width"]) == (offsets[section] + 12, 8)
        assert (
            text["sha256"]
            == hashlib.sha256(b"\xfa\x02\x01\xfc\xfd\0\xfe\0").hexdigest()
        )


def test_nonfinal_message_keeps_directory_pair_and_padded_span_bytes():
    data, offsets = messages()
    proofs = nonchoice_message_proofs(data, offsets, 1)
    assert isinstance(proofs, tuple)
    for section, directory, text in zip(
        (13, 14), proofs[::2], proofs[1::2], strict=True
    ):
        assert (directory["offset"], directory["width"]) == (offsets[section] + 2, 4)
        assert (text["offset"], text["width"]) == (offsets[section] + 8, 4)
        assert text["sha256"] == hashlib.sha256(b"\xfe\0\0\0").hexdigest()


@pytest.mark.parametrize(
    "text",
    [
        b"",
        b"\xfe",
        b"\xee",
        b"\xfa\0\xfe\0",
        b"\xfb\0\xfe\0",
        b"\xf8\0\xfe\0",
        b"\xf7\xfe\0",
        bytes(4096) + b"\xfe\0",
    ],
)
def test_final_message_rejects_unterminated_unsafe_or_unbounded_text(text):
    data, offsets = messages(text, tail=b"")
    assert isinstance(
        nonchoice_message_proofs(data, offsets, 2), NonchoiceMessageFailure
    )


@pytest.mark.parametrize("section", [13, 14])
def test_each_language_requires_its_own_terminal_before_the_section_boundary(section):
    data, offsets = messages(tail=b"")
    mutated = bytearray(data)
    mutated[offsets[section] + 18 : offsets[section] + 20] = b"\0\0"
    assert (
        nonchoice_message_proofs(bytes(mutated), offsets, 2)
        is NonchoiceMessageFailure.Text
    )


def test_source_header_and_selected_entry_are_mandatory():
    data, offsets = messages()
    bad = list(offsets)
    bad[13] += 2
    assert (
        nonchoice_message_proofs(data, tuple(bad), 2)
        is NonchoiceMessageFailure.SourceBinding
    )
    assert (
        nonchoice_message_proofs(data, offsets, 3) is NonchoiceMessageFailure.Directory
    )
