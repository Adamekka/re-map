"""Bound both owned language texts used by the audited nonchoice UI path."""

from __future__ import annotations

import hashlib
import itertools
import struct
from enum import Enum


class NonchoiceMessageFailure(Enum):
    SourceBinding = "message source layout mismatch"
    Directory = "unsupported message directory"
    Text = "unsupported nonchoice text"


def nonchoice_message_proofs(
    data: bytes, section_offsets: tuple[int, ...], message_id: int
) -> tuple[dict, ...] | NonchoiceMessageFailure:
    assert type(data) is bytes
    assert type(section_offsets) is tuple and len(section_offsets) == 23
    assert all(type(value) is int and value >= 0 for value in section_offsets)
    assert type(message_id) is int and 0 <= message_id <= 255
    if len(data) < 100 or struct.unpack_from("<23I", data, 8) != section_offsets:
        return NonchoiceMessageFailure.SourceBinding
    result = []
    for section in (13, 14):
        table = section_offsets[section]
        boundary = min(
            (offset for offset in section_offsets if offset > table), default=len(data)
        )
        if not 0 < table <= boundary - 2 or boundary > len(data):
            return NonchoiceMessageFailure.Directory
        table_width = int.from_bytes(data[table : table + 2], "little")
        if (
            table_width % 2
            or not 2 <= table_width <= 512
            or table + table_width > boundary
            or message_id >= table_width // 2
        ):
            return NonchoiceMessageFailure.Directory
        entries = [
            int.from_bytes(data[position : position + 2], "little")
            for position in range(table, table + table_width, 2)
        ]
        if any(
            not table_width <= entry <= boundary - table for entry in entries
        ) or any(first > second for first, second in itertools.pairwise(entries)):
            return NonchoiceMessageFailure.Directory
        start = table + entries[message_id]
        final = message_id + 1 == len(entries)
        end = boundary if final else table + entries[message_id + 1]
        if not final and not 2 <= end - start <= 4096:
            return NonchoiceMessageFailure.Text
        # A final entry has no next offset. Bound every read by its enclosing
        # section and stop at native FE, before unrelated mutable model data.
        limit = min(end, start + 4096)
        position, terminated = start, False
        while position < limit:
            command = data[position]
            position += 1
            if command <= 0xED or command == 0xFC:
                continue
            if (
                command not in (0xEE, 0xEF, 0xF0, 0xF9, 0xFA, 0xFD, 0xFE)
                or position == limit
                or command == 0xFA
                and data[position] == 0
            ):
                break
            position += 1
            if command == 0xFE:
                terminated = final or not any(data[position:end])
                break
        if not terminated:
            return NonchoiceMessageFailure.Text
        for offset, width in (
            (table + message_id * 2, 2 if final else 4),
            (start, position - start if final else end - start),
        ):
            result.append(
                {
                    "offset": offset,
                    "width": width,
                    "sha256": hashlib.sha256(data[offset : offset + width]).hexdigest(),
                }
            )
    return tuple(result)
