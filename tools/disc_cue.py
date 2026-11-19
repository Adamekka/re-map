"""Read the file paths named by a disc CUE before opening any outputs."""

import re
from pathlib import Path


def read_cue_tracks(cue: Path) -> tuple[Path, ...]:
    # Match directives only. Comments can contain example FILE records.
    records = re.findall(
        r"^[ \t]*FILE(.*)$",
        cue.read_text(encoding="utf-8-sig"),
        re.IGNORECASE | re.MULTILINE,
    )
    if not records:
        raise ValueError("the CUE names no data track")
    tracks = []
    for record in records:
        match = re.fullmatch(r'[ \t]+(?:"([^"]+)"|([^" \t]+))[ \t]+\w+[ \t]*', record)
        if match is None:
            raise ValueError("invalid CUE FILE directive")
        name = match[1] if match[1] is not None else match[2]
        if "\0" in name:
            raise ValueError("embedded null byte in the CUE track name")
        tracks.append(cue.parent / name)
    return tuple(tracks)
