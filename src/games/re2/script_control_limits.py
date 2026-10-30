"""Native SCD control storage shared by the bounded source interpreters."""

import hashlib
import json

# Depth-indexed IF/loop fields have four frames including the root. A fifth
# frame aliases other task fields even though native Gosub has no bounds check.
NATIVE_CALL_FRAME_COUNT = 4

# Each call frame has four loop start/end pointers, counters and saved IF
# levels. A fifth loop aliases the next frame even without a native guard.
NATIVE_LOOP_FRAME_COUNT = 4

# Keep the established scalar work cap so summaries cannot certify a leaf
# that the write interpreter would stop before completion.
SCALAR_PROGRAM_STEP_LIMIT = 8192


def programs_digest(programs: dict) -> str:
    return hashlib.sha256(
        json.dumps(programs, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def calls_fit_native_frames(edges: dict[str, set[str]]) -> bool:
    """Bound every possible procedure entry, including independently run tasks."""
    assert type(edges) is dict and all(
        type(key) is str and type(targets) is set and targets <= edges.keys()
        for key, targets in edges.items()
    )
    heights, active = {}, set()

    def height(key: str) -> int:
        if key in active or len(active) >= NATIVE_CALL_FRAME_COUNT:
            # A cycle or fifth active procedure already exceeds the contract.
            # Stop here so malformed graphs cannot exhaust Python recursion.
            return NATIVE_CALL_FRAME_COUNT + 1
        if key in heights:
            return heights[key]
        active.add(key)
        result = 1
        for target in edges[key]:
            result = max(result, 1 + height(target))
            if result > NATIVE_CALL_FRAME_COUNT:
                break
        active.remove(key)
        heights[key] = result
        return result

    return all(height(key) <= NATIVE_CALL_FRAME_COUNT for key in edges)
