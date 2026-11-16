"""Shared room-script evaluation. RE2-EVAL-001."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from games.scd_state import (  # noqa: E402
    EngineTasks,
    GameState,
    ScriptStateCache,
    Support,
    room_script_state,
)

TASKS = EngineTasks(("init:0", "main:0", "main:1"), frozenset({1}))
BANK = 8


def rows(*body: list) -> list[list]:
    # Offsets advance by ten; tests address jump targets by these offsets.
    return [[index * 10, index * 10 + 10, *row] for index, row in enumerate(body)]


def evaluate(
    program, flags=None, variables=None, approach=frozenset(), gids=(), carried=()
):
    flags = flags or {}
    variables = variables or {}
    state = GameState(
        lambda bank, bit: flags.get((bank, bit), False),
        lambda index: variables.get(index, 0),
        approach,
        frozenset({11}),
        lambda item: item in carried,
    )
    program = {"main:0": rows(["end"]), "main:1": rows(["end"]), **program}
    return room_script_state(program, state, TASKS, {gid: (BANK, gid) for gid in gids})


def test_flag_condition_selects_the_created_item():
    program = {
        "init:0": rows(
            ["if", 40],
            ["ck", 4, 7, 1],
            ["item", 3, 0x31, 20, 15, 77],
            ["end"],
            ["end"],
        )
    }
    assert evaluate(program, gids=[77]).item_presence == {77: False}
    present = evaluate(program, flags={(4, 7): True}, gids=[77])
    assert present.item_presence == {77: True}
    assert present.item_identity == {77: (20, 15)}


def test_else_branch_and_variable_comparison():
    program = {
        "init:0": rows(
            ["if", 40],
            ["cmp", 32, 0, 14],
            ["item", 3, 0x31, 20, 15, 1],
            ["else", 60],
            ["item", 3, 0x31, 21, 7, 2],
            ["end"],
            ["end"],
        )
    }
    assert evaluate(program, variables={32: 14}, gids=[1, 2]).item_presence == {
        1: True,
        2: False,
    }
    assert evaluate(program, variables={32: 2}, gids=[1, 2]).item_presence == {
        1: False,
        2: True,
    }


def test_unreadable_state_keeps_divergent_items_unresolved():
    program = {
        "init:0": rows(
            ["if", 30],
            ["cond", 0],
            ["item", 3, 0x31, 20, 15, 1],
            ["end"],
        )
    }
    result = evaluate(program, gids=[1])
    assert result.support is Support.Supported
    assert result.item_presence == {1: None}


def test_arrival_alternatives_each_keep_their_items():
    # The entered floor selects which items load; both exist in the room.
    program = {
        "init:0": rows(
            ["if", 40],
            ["cond", 1],
            ["item", 3, 0x31, 20, 15, 1],
            ["else", 60],
            ["item", 4, 0x31, 21, 7, 2],
            ["end"],
            ["end"],
        )
    }
    assert evaluate(program, gids=[1, 2]).item_presence == {1: True, 2: True}


def test_tainted_flag_write_propagates_to_later_conditions():
    program = {
        "init:0": rows(
            ["if", 30],
            ["cond", 0],
            ["set", 4, 1, 1],
            ["if", 60],
            ["ck", 4, 1, 1],
            ["item", 3, 0x31, 20, 15, 1],
            ["end"],
        )
    }
    assert evaluate(program, gids=[1]).item_presence == {1: None}


def test_switch_takes_the_first_match_or_default():
    program = {
        "init:0": rows(
            ["switch", 70, 5, [[10, 1], [40, None]]],
            ["case"],
            ["item", 3, 0x31, 20, 15, 1],
            ["break"],
            ["case"],
            ["item", 3, 0x31, 21, 7, 2],
            ["break"],
            ["end"],
        )
    }
    assert evaluate(program, variables={5: 1}, gids=[1, 2]).item_presence == {
        1: True,
        2: False,
    }
    assert evaluate(program, variables={5: 9}, gids=[1, 2]).item_presence == {
        1: False,
        2: True,
    }


def test_trigger_reward_is_obtainable_before_the_puzzle_is_solved():
    program = {
        "init:0": rows(["aot", 6, 5, 0x31, 2], ["aot", 7, 5, 0x31, 3], ["end"]),
        # Solving the puzzle sets a room flag that a second trigger checks.
        "main:2": rows(["set", 4, 9, 1], ["end"]),
        "main:3": rows(
            ["if", 40],
            ["ck", 4, 9, 1],
            ["reset", 6, 2, 0x31, -1, 70, 1, 5],
            ["end"],
            ["end"],
        ),
    }
    result = evaluate(program, gids=[5])
    assert result.item_presence == {5: True}
    assert result.later_items == frozenset({5})
    assert result.item_identity == {5: (70, 1)}


def test_parked_item_handed_over_by_aot_on_is_obtainable():
    program = {
        "init:0": rows(
            ["item", 3, 0, 20, 15, 13],
            ["aot", 8, 5, 0x31, 2],
            ["end"],
        ),
        "main:2": rows(["aot_on", 3], ["end"]),
    }
    assert evaluate(program, gids=[13]).item_presence == {13: True}


def test_collected_item_identity_survives_its_own_acquisition_flag():
    # The Reset only runs while the pickup is uncollected; once collected its
    # identity still names the Reset's item rather than the parked creator.
    program = {
        "init:0": rows(["item", 2, 0, 57, 1, 55], ["aot", 4, 5, 0x31, 2], ["end"]),
        "main:2": rows(
            ["if", 40],
            ["ck", BANK, 55, 0],
            ["reset", 2, 2, 0x31, -1, 61, 1, 55],
            ["end"],
            ["end"],
        ),
    }
    result = evaluate(program, flags={(BANK, 55): True}, gids=[55])
    assert result.item_identity == {55: (61, 1)}


def test_per_frame_procedure_runs_on_entry():
    program = {
        "init:0": rows(["end"]),
        "main:1": rows(["item", 3, 0x31, 20, 15, 1], ["end"]),
    }
    assert evaluate(program, gids=[1]).item_presence == {1: True}


def test_door_replaced_by_event_and_alternative_creators():
    program = {
        "init:0": rows(
            ["door", 0, 0x31],
            ["door", 1, 0x31],
            ["if", 50],
            ["ck", 4, 70, 0],
            ["reset", 1, 5, 0x31, 9, -1, -1, -1],
            ["if", 90],
            ["ck", 1, 6, 1],
            ["door", 0, 0x31],
            ["end"],
            ["end"],
        ),
        "main:9": rows(["end"]),
    }
    doors = evaluate(program).doors
    assert doors[0].sat == 0x31 and not doors[0].replaced
    assert doors[10].replaced
    # The special-mode alternative for slot 0 does not run.
    assert 70 not in doors
    swapped = evaluate(program, flags={(4, 70): True, (1, 6): True}).doors
    assert 0 not in swapped and swapped[70].sat == 0x31
    assert not swapped[10].replaced


def test_unresolved_door_creator_choice():
    program = {
        "init:0": rows(
            ["if", 40],
            ["cond", 0],
            ["door", 0, 0x31],
            ["else", 60],
            ["door", 0, 0],
            ["end"],
            ["end"],
        )
    }
    doors = evaluate(program).doors
    assert doors[20].sat is None and doors[40].sat is None


def test_jump_outside_the_model_is_unsupported():
    program = {"init:0": rows(["gosub", 9], ["end"])}
    assert evaluate(program).support is Support.Unsupported


def test_cache_revalidates_every_value_it_read():
    flags = {(4, 7): False}
    state = GameState(
        lambda bank, bit: flags.get((bank, bit), False),
        lambda index: 0,
        frozenset(),
        frozenset(),
        lambda item: False,
    )
    program = {
        "init:0": rows(
            ["if", 40], ["ck", 4, 7, 1], ["item", 3, 0x31, 20, 15, 77], ["end"], ["end"]
        ),
        "main:0": rows(["end"]),
        "main:1": rows(["end"]),
    }
    cache = ScriptStateCache()
    acquisition = {77: (BANK, 77)}
    assert cache.get("r", program, state, TASKS, acquisition).item_presence == {
        77: False
    }
    flags[4, 7] = True
    assert cache.get("r", program, state, TASKS, acquisition).item_presence == {
        77: True
    }


def test_work_copy_patch_selects_the_checked_flag():
    # Work_copy stores variable 7 into the Ck's bit operand at offset 20 + 2.
    program = {
        "init:0": rows(
            ["patch", 22, 7, 1],
            ["if", 50],
            ["ck", 4, 0, 1],
            ["item", 3, 0x31, 20, 15, 1],
            ["end"],
            ["end"],
        )
    }
    assert evaluate(
        program, flags={(4, 9): True}, variables={7: 9}, gids=[1]
    ).item_presence == {1: True}
    assert evaluate(
        program, flags={(4, 0): True}, variables={7: 9}, gids=[1]
    ).item_presence == {1: False}


def test_task_started_under_unreadable_state_keeps_its_taint():
    program = {
        "init:0": rows(["if", 30], ["cond", 0], ["exec", 2], ["end"]),
        "main:2": rows(["item", 3, 0x31, 20, 15, 7], ["end"]),
    }
    assert evaluate(program, gids=[7]).item_presence == {7: None}


def test_early_exit_under_unreadable_state_taints_later_creators():
    program = {
        "init:0": rows(
            ["if", 30],
            ["cond", 0],
            ["end"],
            ["item", 3, 0x31, 20, 15, 7],
            ["door", 0, 0x31],
            ["end"],
        )
    }
    result = evaluate(program, gids=[7])
    assert result.item_presence == {7: None}
    assert result.doors[40].sat is None


def test_item_replaced_under_unreadable_state_is_unresolved():
    program = {
        "init:0": rows(
            ["item", 3, 0x31, 20, 15, 7],
            ["if", 40],
            ["cond", 0],
            ["item", 3, 0x31, 21, 7, 8],
            ["end"],
        )
    }
    assert evaluate(program, gids=[7, 8]).item_presence == {7: None, 8: None}


def test_later_pass_keeps_paths_that_start_different_tasks():
    program = {
        "init:0": rows(["aot", 4, 5, 0x31, 2], ["end"]),
        "main:2": rows(
            ["if", 40],
            ["cond", 1],
            ["case"],
            ["else", 50],
            ["exec", 6],
            ["end"],
        ),
        "main:6": rows(["item", 3, 0x31, 20, 15, 7], ["end"]),
    }
    assert evaluate(program, gids=[7]).item_presence == {7: True}


def test_zero_count_for_loop_skips_its_body():
    program = {
        "init:0": rows(
            ["loop", 30, 0],
            ["item", 3, 0x31, 20, 15, 7],
            ["loop_end"],
            ["end"],
        )
    }
    assert evaluate(program, gids=[7]).item_presence == {7: False}


def test_byte_patch_keeps_a_negative_operands_high_byte():
    # Work_copy replaces the low byte of Cmp's value -1 (0xFFFF) with 5.
    program = {
        "init:0": rows(
            ["patch", 24, 7, 1],
            ["if", 50],
            ["cmp", 3, 0, -1],
            ["item", 3, 0x31, 20, 15, 1],
            ["end"],
            ["end"],
        )
    }
    assert evaluate(program, variables={7: 5, 3: -251}, gids=[1]).item_presence == {
        1: True
    }


def test_calc_follows_native_operators():
    program = {
        "init:0": rows(
            ["var", 4, 0, 6],
            ["calc", 4, 0, 1],
            ["calc2", 4, 2, 5],
            ["switch", 70, 4, [[40, 21], [60, None]]],
            ["case"],
            ["item", 3, 0x31, 20, 15, 1],
            ["break"],
            ["case"],
            ["end"],
        )
    }
    # (6 + 1) * var5 = 21 selects the first case.
    assert evaluate(program, variables={5: 3}, gids=[1]).item_presence == {1: True}
    assert evaluate(program, variables={5: 2}, gids=[1]).item_presence == {1: False}


def test_carried_item_check_reads_the_inventory():
    program = {
        "init:0": rows(
            ["if", 40], ["has", 54], ["item", 3, 0x31, 20, 15, 77], ["end"], ["end"]
        )
    }
    assert evaluate(program, gids=[77]).item_presence == {77: False}
    assert evaluate(program, gids=[77], carried={54}).item_presence == {77: True}


def test_cache_revalidates_the_inventory():
    carried = set()
    state = GameState(
        lambda bank, bit: False,
        lambda index: 0,
        frozenset(),
        frozenset(),
        lambda item: item in carried,
    )
    program = {
        "init:0": rows(
            ["if", 40], ["has", 54], ["item", 3, 0x31, 20, 15, 77], ["end"], ["end"]
        ),
        "main:0": rows(["end"]),
        "main:1": rows(["end"]),
    }
    cache = ScriptStateCache()
    acquisition = {77: (BANK, 77)}
    assert cache.get("r", program, state, TASKS, acquisition).item_presence == {
        77: False
    }
    carried.add(54)
    assert cache.get("r", program, state, TASKS, acquisition).item_presence == {
        77: True
    }


def test_wait_inside_a_switch_case_ends_the_task():
    program = {
        "main:0": rows(
            ["switch", 60, 4, [[10, 0], [50, None]]],
            ["case"],
            ["item", 3, 0x31, 20, 15, 1],
            ["goto", 20],
            ["break"],
            ["case"],
            ["item", 3, 0x31, 20, 15, 2],
            ["end"],
        )
    }
    # Case 0 waits at its backward jump and never reaches the later item.
    assert evaluate(program, variables={4: 0}, gids=[1, 2]).item_presence == {
        1: True,
        2: False,
    }
    assert evaluate(program, variables={4: 1}, gids=[1, 2]).item_presence == {
        1: False,
        2: True,
    }


def test_copied_actor_member_selects_alternative_arrivals():
    program = {
        "init:0": rows(
            ["var", 16, 3, -1],
            ["calc", 16, 6, 2048],
            ["var", 4, 1, 16],
            ["if", 70],
            ["cmp", 4, 5, 0],
            ["item", 3, 0x31, 20, 15, 1],
            ["end"],
            ["end"],
        )
    }
    # Each actor state is one way the visit can go, so the item exists.
    assert evaluate(program, gids=[1]).item_presence == {1: True}
    # An unread game-state result stays unresolved.
    program["init:0"][0] = [0, 10, "var", 16, 2, -1]
    assert evaluate(program, gids=[1]).item_presence == {1: None}
    # An arrival variable overwritten with game state no longer forks into
    # alternatives.
    overwritten = {
        "init:0": rows(
            ["var", 26, 2, -1],
            ["if", 50],
            ["cmp", 26, 5, 0],
            ["item", 3, 0x31, 20, 15, 1],
            ["end"],
            ["end"],
        )
    }
    assert evaluate(overwritten, approach=frozenset({26}), gids=[1]).item_presence == {
        1: None
    }


def test_each_call_runs_its_loops_afresh():
    program = {
        "init:0": rows(
            ["gosub", 7],
            ["gosub", 7],
            ["if", 60],
            ["cmp", 4, 0, 4],
            ["item", 3, 0x31, 20, 15, 1],
            ["end"],
            ["end"],
        ),
        # Each call counts two iterations in variable 6 and adds them to 4.
        "main:7": rows(
            ["var", 6, 0, 0],
            ["calc", 6, 0, 1],
            ["calc", 4, 0, 1],
            ["if", 70],
            ["cmp", 6, 3, 2],
            ["goto", 10],
            ["end"],
            ["end"],
        ),
    }
    assert evaluate(program, gids=[1]).item_presence == {1: True}


def independent_writes(count: int, body, first: int = 0) -> list[list]:
    """``count`` blocks, each writing under its own unreadable condition.

    ``first`` is the row index of the first block within the procedure.
    """
    flat = []
    for index in range(count):
        block = [["cond", 0], *body(index)]
        end = (first + len(flat) + len(block) + 1) * 10
        flat += [["if", end], *block]
    return flat


def test_independent_writes_merge_at_crowded_joins():
    program = {
        "init:0": rows(
            *independent_writes(24, lambda index: [["set", 5, index, 1]]),
            ["item", 3, 0x31, 20, 15, 1],
            ["end"],
        )
    }
    result = evaluate(program, gids=[1])
    assert result.support is Support.Supported
    assert result.item_presence == {1: True}


def test_waiting_callee_ends_its_whole_task():
    program = {
        "init:0": rows(["end"]),
        "main:0": rows(["gosub", 7], ["door", 6, 0x31], ["end"]),
        "main:7": rows(["goto", 0], ["end"]),
    }
    assert evaluate(program).doors == {}


def test_waiting_task_resumes_in_later_analysis():
    program = {
        "init:0": rows(["aot", 4, 5, 0x31, 2], ["end"]),
        # Case 0 waits until another task changes variable 5.
        "main:0": rows(
            ["switch", 60, 5, [[10, 0], [40, None]]],
            ["case"],
            ["goto", 0],
            ["break"],
            ["case"],
            ["item", 3, 0x31, 20, 15, 1],
            ["end"],
        ),
        "main:2": rows(["var", 5, 0, 1], ["end"]),
    }
    result = evaluate(program, gids=[1])
    assert result.item_presence == {1: True}
    assert result.later_items == frozenset({1})


def test_crowded_join_keeps_values_every_path_agrees_on():
    def guarded(created: list) -> list[list]:
        # Variable 4 stays 0 through 256 combinations of independent writes,
        # so the creator after them never runs.
        flat = [
            ["var", 4, 0, 0],
            *independent_writes(8, lambda index: [["set", 5, index, 1]], 1),
        ]
        last = (len(flat) + 4) * 10
        return rows(*flat, ["if", last], ["cmp", 4, 0, 1], created, ["end"], ["end"])

    entry = {"init:0": guarded(["item", 3, 0x31, 20, 15, 1])}
    assert evaluate(entry, gids=[1]).item_presence == {1: False}
    later = {
        "init:0": rows(["aot", 4, 5, 0x31, 2], ["end"]),
        "main:2": guarded(["reset", 4, 2, 0x31, -1, 70, 1, 5]),
    }
    result = evaluate(later, gids=[5])
    assert result.later_items == frozenset()
    assert result.item_presence == {5: False}


def test_activating_an_interaction_written_under_game_state_taints_its_callback():
    program = {
        "init:0": rows(
            ["if", 30], ["cond", 0], ["aot", 4, 5, 0x31, 2], ["aot_on", 4], ["end"]
        ),
        "main:2": rows(["door", 6, 0x31], ["end"]),
    }
    assert evaluate(program).doors[0].sat is None


def test_handing_over_a_parked_item_under_game_state_is_unresolved():
    program = {
        "init:0": rows(
            ["item", 3, 0, 20, 15, 13],
            ["if", 40],
            ["cond", 0],
            ["aot_on", 3],
            ["end"],
            ["end"],
        )
    }
    assert evaluate(program, gids=[13]).item_presence == {13: None}


def test_resumed_wait_does_not_repeat_what_ran_before_it():
    program = {
        "init:0": rows(["end"]),
        # The pickup is replaced at once, then the task waits for good.
        "main:0": rows(
            ["item", 3, 0x31, 20, 15, 1],
            ["aot", 3, 4, 0x31, -1],
            ["goto", 20],
            ["end"],
        ),
    }
    result = evaluate(program, gids=[1])
    assert result.item_presence == {1: False}
    assert result.later_items == frozenset()


def test_resumed_wait_keeps_state_set_before_it_unread():
    program = {
        "init:0": rows(["aot", 4, 5, 0x31, 2], ["end"]),
        # Variable 5 is set once, then case 0 waits until another task
        # changes it.
        "main:0": rows(
            ["var", 5, 0, 0],
            ["switch", 70, 5, [[20, 0], [50, None]]],
            ["case"],
            ["goto", 10],
            ["break"],
            ["case"],
            ["item", 3, 0x31, 20, 15, 1],
            ["end"],
        ),
        "main:2": rows(["var", 5, 0, 1], ["end"]),
    }
    assert evaluate(program, gids=[1]).item_presence == {1: True}


def test_crowded_join_keeps_an_agreed_actor_member():
    flat = [
        ["var", 4, 3, -1],
        *independent_writes(8, lambda index: [["set", 5, index, 1]], 1),
    ]
    last = (len(flat) + 4) * 10
    program = {
        "init:0": rows(
            *flat,
            ["if", last],
            ["cmp", 4, 5, 0],
            ["item", 3, 0x31, 20, 15, 1],
            ["end"],
            ["end"],
        )
    }
    # Every arrival holds the same actor member, so its value still gives
    # alternatives rather than unresolved game state.
    assert evaluate(program, gids=[1]).item_presence == {1: True}


def test_jumping_back_before_a_block_reenters_it_once():
    from games.scd_state import evaluate_entry

    program = {
        "main:0": rows(
            ["switch", 80, 5, [[10, 0], [50, 1]]],
            ["case"],
            ["var", 5, 0, 1],
            # Back to the Switch, which opens its block again.
            ["goto", 0],
            ["break"],
            ["case"],
            # Wait inside case 1.
            ["goto", 60],
            ["break"],
            ["end"],
        )
    }
    state = GameState(
        lambda bank, bit: False,
        lambda index: 0,
        frozenset(),
        frozenset(),
        lambda item: False,
    )
    entry = evaluate_entry(program, state, ("main:0",))
    assert [[frame[2] for frame in task] for task in entry.suspended] == [
        [(("switch", 80, 0, False),)]
    ]


def test_wait_on_state_only_native_code_changes_resumes():
    program = {
        "init:0": rows(["end"]),
        # No room script writes variable 7; native code eventually does.
        "main:0": rows(
            ["switch", 60, 7, [[10, 0], [40, None]]],
            ["case"],
            ["goto", 0],
            ["break"],
            ["case"],
            ["item", 3, 0x31, 20, 15, 1],
            ["end"],
        ),
    }
    result = evaluate(program, gids=[1])
    assert result.item_presence == {1: True}
    assert result.later_items == frozenset({1})
