"""Exact owned native/resource corpus identity shared by separate authorities."""

from __future__ import annotations

import hashlib
import json
from dataclasses import fields, is_dataclass

# This derived audit identity comes from the complete owned 69-resource,
# 125-source binder, not from a caller-supplied selection or receipt mirror.
NORMAL_ENGINE_BINDING_SHA256 = (
    "727c49593f3d756594049140e357d8c4c6f47aefdb215d7fd6d0a0a79ed670a8"
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
