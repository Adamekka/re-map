"""Read the pinned RE1 loader's file tables and validate their disc targets."""

from __future__ import annotations

import struct
from pathlib import Path


def build_source_choices(
    executable: bytes, catalog: list[str], rooms: list[dict], profile: dict
) -> list[dict]:
    config = profile["room_source_selector"]
    base = struct.unpack_from("<I", executable, 0x18)[0]

    def offset(key: str) -> int:
        address = int(config[key], 0)
        result = address - base + 0x800
        if not 0x800 <= result < len(executable):
            raise ValueError("room selector table is outside the pinned executable")
        return result

    file_ids = offset("file_id_table_address_ps1")
    variants = offset("variant_table_address_ps1")
    whitelists = offset("alternate_whitelist_address_ps1")
    sources = {row["source_rdt"] for row in rooms}
    choices = []
    for main, sub in sorted({(row["room_main"], row["room_sub"]) for row in rooms}):
        if not 0 <= main < 7 or not 0 <= sub < 32:
            raise ValueError("room selector needs Main 0..6 and Sub 0..31")
        for alternate in (0, 1):
            stage = (
                main + 7
                if alternate
                and sub
                in executable[whitelists + 9 * main : whitelists + 9 * (main + 1)]
                else main
            )
            first = struct.unpack_from(
                "<H", executable, file_ids + 64 * stage + 2 * sub
            )[0]
            selector = executable[variants + 32 * stage + sub]
            for variant in (0, 1):
                file_id = (
                    first
                    + (0 if stage in config["direct_base_file_stages"] else 1)
                    + (variant if selector == 0 else 0)
                )
                # RE1-VARIANT-002: the ISO listing has three files before file ID zero.
                index = file_id + 3
                if not 0 <= index < len(catalog):
                    raise ValueError("room file ID is outside the owned disc catalog")
                name = catalog[index]
                if not Path(name).name.startswith(f"ROOM{stage + 1:X}{sub:02X}"):
                    raise ValueError("room file ID does not match its logical room")
                if name not in sources:
                    raise ValueError(
                        "room selector targets an unsupported script source"
                    )
                choices.append(
                    {
                        "room_main": main,
                        "room_sub": sub,
                        "variant": variant,
                        "alternate": alternate,
                        "source_rdt": name,
                    }
                )
    return choices
