"""Pinned SLUS-00551 command returns audited in RE1-SCD-007.

These handlers return one after their visual, audio, enemy or event work.
They do not directly write the modeled item/door descriptors or persistent flags.
Event activation remains covered by the possible-event effects in room rules.
Commands that write tracked variables or flags have separate semantic rules.
"""

# This allowlist describes native return paths, not guessed no-ops. Unlisted
# commands require an explicit condition/effect rule before reconstruction.
CONTINUING_OPCODES = frozenset(
    {
        0x0B,
        0x0E,
        0x14,
        0x15,
        0x16,
        0x17,
        0x19,
        0x1B,
        0x1F,
        0x20,
        0x21,
        0x25,
        0x27,
        0x28,
        0x2A,
        0x2B,
        0x2F,
        0x30,
        0x32,
        0x33,
        0x34,
        0x35,
        0x37,
        0x39,
        0x3A,
        0x3B,
        0x3D,
        0x3E,
        0x41,
        0x42,
        0x43,
        0x44,
        0x45,
        0x47,
        0x49,
        0x4A,
        0x4B,
    }
)

# Each predicate only reads its condition and advances the script pointer.
# Inventory, buttons, geometry and enemy state have no supported past-room
# snapshot; retain both outcomes rather than read another room's temporary state.
UNRESOLVED_PREDICATE_OPCODES = frozenset(
    {0x10, 0x11, 0x1A, 0x1D, 0x22, 0x36, 0x38, 0x3C, 0x3F}
)

# Indirect/native writes can overlap local flag banks. Forget those physical
# bits even though the command's return is one. Current RAM cannot supply the
# corresponding local state of an earlier room. Tuples are bank, first bit, count.
LOCAL_FLAG_WRITES = {
    0x0B: ((6, 16, 16),),  # Message helper masks the CAB00 halfword conditionally.
    0x1B: ((6, 160, 32), (4, 200, 8)),  # Enemy pointer CAB14 and spawn counter C3022.
    0x2A: ((4, 224, 32),),  # Particle creation can replace the C3024 record header.
    0x3D: ((4, 224, 32),),
    0x3E: ((4, 224, 32),),
    0x42: ((4, 224, 32),),
}
