"""Compile RE3 room scripts into the shared evaluation model. RE3-EVAL-001.

Opcode widths come from each handler's script-pointer advance in the pinned
SLUS-00923 executable (handler table 0x8009E0F8), checked against every
owned room procedure.
"""

from __future__ import annotations

from games.scd_compile import OpcodeSet, compile_section

# fmt: off
WIDTHS = (
    1, 2, 1, 4, 4, 2, 4, 4, 2, 1, 3, 1, 1, 6, 6, 2, 4, 2, 4, 2, 4, 6, 2, 2,
    6, 2, 2, 2, 1, 4, 4, 3, 6, 4, 2, 1, 1, 4, 6, 1, 1, 8, 6, 2, 4, 4, 6, 1,
    6, 6, 6, 4, 10, 6, 3, 2, 2, 16, 16, 3, 1, 2, 2, 3, 4, 3, 3, 6, 6, 4, 11,
    3, 4, 1, 1, 1, 4, 4, 6, 1, 2, 1, 2, 3, 4, 8, 8, 6, 6, 8, 2, 6, 2, 1, 3,
    2, 22, 32, 40, 20, 28, 10, 2, 22, 30, 14, 16, 2, 4, 4, 4, 2, 16, 18, 22,
    24, 5, 2, 3, 12, 6, 4, 2, 6, 1, 24, 2, 40, 4, 8, 10, 1, 4, 2, 1, 1, 4, 2,
    1, 1, 1, 1, 4, 2,
)
# fmt: on

RE3_OPCODES = OpcodeSet(
    widths=WIDTHS,
    ends=frozenset({0x01, 0x1A}),
    if_=0x06,
    else_=0x07,
    goto=0x18,
    # For, While and Do. For2 (0x0E) never occurs in the owned scripts and is
    # left unmodeled, so its Next makes a procedure Unsupported.
    loops=frozenset({0x0D, 0x10, 0x12}),
    for_loop=0x0D,
    while_loop=0x10,
    do_loop=0x12,
    loop_ends=frozenset({0x0F, 0x11, 0x13}),
    switch=0x14,
    case=0x15,
    default=0x16,
    end_switch=0x17,
    break_=0x1B,
    ck=0x4C,
    # Cmp handler 0x800547F0 indexes signed variables at 0x800D1F46.
    cmp=0x4E,
    set_=0x4D,
    # Actor member comparison (0x80053C74) and the player-control check
    # (0x80058B84).
    approach_conditions=frozenset({0x27, 0x43}),
    # Inventory search 0x8006CC8C through the pointer at 0x800D23B4.
    has_item=0x6B,
    # An inventory quantity test (0x80055A18), a game-state table test
    # (0x800555BC) and a system-flag test (0x80055660).
    state_conditions=frozenset({0x35, 0x36, 0x6C}),
    # Save, Copy and Member_copy.
    variable_writes={
        0x1E: (0, 1, 2),
        0x1F: (1, 1, 2),
        0x42: (3, 1, 0),
    },
    fixed_variable_writes={},
    # Operator table 0x80010900 (handler 0x80053A54).
    calc=0x20,
    calc2=0x21,
    items={0x67: 14, 0x68: 22},
    # The RE3 room catalog binds no direct awards, so no award command is
    # modeled.
    awards=frozenset(),
    doors=frozenset({0x61, 0x62}),
    interactions=frozenset({0x63, 0x64}),
    reset=0x65,
    aot_on=0x66,
    gosub=0x19,
    exec_=0x04,
    # Handler 0x800538E0.
    work_copy=0x1D,
)


def compile_room_scripts(data: bytes) -> dict[str, list[list]]:
    # RE3 rooms have one procedure directory in RDT section 16.
    return compile_section(RE3_OPCODES, data, 16, "main")
