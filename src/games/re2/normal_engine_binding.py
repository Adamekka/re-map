"""Exact owned native/resource corpus identity shared by separate authorities."""

from __future__ import annotations

import hashlib
import json
from dataclasses import fields, is_dataclass
from enum import Enum

# This derived audit identity comes from the complete owned 69-resource,
# 125-source binder, not from a caller-supplied selection or receipt mirror.
NORMAL_ENGINE_BINDING_SHA256 = (
    "727c49593f3d756594049140e357d8c4c6f47aefdb215d7fd6d0a0a79ed670a8"
)

# These are the raw decoded inputs to source-effect ownership. Later compilers
# replace derived presence/quantity fields; those are not decoder witnesses.
OWNED_SOURCE_FIELDS = (
    "sha256",
    "size",
    "cameras",
    "section_offsets",
    "items",
    "doors",
    "reset_item_variants",
    "candidate_list_complete",
    "programs",
)


def typed_binding_digest(value: object) -> str:
    def encode(value):
        # Preserve exact types: JSON alone equates tuple/list, and ordinary
        # Python equality equates bool/int in consistently replaced receipts.
        kind = type(value)
        if kind in (str, int, bool):
            return [kind.__name__, value]
        if kind is bytes:
            return ["bytes", len(value), hashlib.sha256(value).hexdigest()]
        if kind is tuple:
            return ["tuple", [encode(part) for part in value]]
        if kind is frozenset:
            return ["frozenset", sorted(encode(part) for part in value)]
        if isinstance(value, Enum):
            # Source partitions use enums for deliberately unaccessed resources.
            # Preserve the class and typed value rather than equating its label
            # with a caller-supplied string or integer.
            return [
                "enum",
                f"{kind.__module__}.{kind.__qualname__}",
                value.name,
                encode(value.value),
            ]
        if is_dataclass(value) and not isinstance(value, type):
            return [
                f"{kind.__module__}.{kind.__qualname__}",
                [
                    [field.name, encode(getattr(value, field.name))]
                    for field in fields(value)
                ],
            ]
        raise ValueError("unsupported normal-engine binding field")

    return hashlib.sha256(
        json.dumps(encode(value), separators=(",", ":")).encode()
    ).hexdigest()


def semantic_profile_digest(profile: dict) -> str:
    # File locations may change during packaging; they grant no native rights.
    return hashlib.sha256(
        json.dumps(
            {
                k: v
                for k, v in profile.items()
                if k not in ("room_metadata_path", "floor_plans_path", "names_path")
            },
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()
