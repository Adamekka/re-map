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
            ["loop", 30, 0, "for"],
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
    entry = evaluate_entry(program, state, EngineTasks(("main:0",), frozenset()))
    suspended = {task for outcome in entry.terminals for task in outcome.suspended}
    assert [[frame[2] for frame in task] for task, _ in suspended] == [
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


def test_resumed_wait_reads_through_a_copied_selector():
    program = {
        "init:0": rows(["end"]),
        # The selector is copied from variable 7, which native code changes.
        "main:0": rows(
            ["var", 6, 1, 7],
            ["switch", 70, 6, [[20, 0], [50, None]]],
            ["case"],
            ["goto", 0],
            ["break"],
            ["case"],
            ["item", 3, 0x31, 20, 15, 1],
            ["end"],
        ),
    }
    assert evaluate(program, gids=[1]).item_presence == {1: True}


def test_resumed_wait_covers_the_goto_that_repeated():
    program = {
        "init:0": rows(["end"]),
        # An earlier conditional jump returns to the same head; the wait is
        # the later one inside the Switch on variable 7.
        "main:0": rows(
            ["if", 30],
            ["ck", 4, 1, 1],
            ["goto", 0],
            ["switch", 90, 7, [[40, 0], [70, None]]],
            ["case"],
            ["goto", 0],
            ["break"],
            ["case"],
            ["item", 3, 0x31, 20, 15, 1],
            ["end"],
        ),
    }
    assert evaluate(program, gids=[1]).item_presence == {1: True}


def test_wait_calling_a_missing_procedure_is_unsupported():
    program = {
        "init:0": rows(["end"]),
        "main:0": rows(
            ["switch", 80, 7, [[10, 0], [70, None]]],
            ["case"],
            # A call that never runs, to a procedure the room lacks.
            ["if", 50],
            ["ck", 4, 1, 1],
            ["gosub", 9],
            ["goto", 0],
            ["break"],
            ["case"],
            ["end"],
        ),
    }
    assert evaluate(program).support is Support.Unsupported


def test_resumed_wait_keeps_its_own_outcomes_interactions():
    program = {
        "init:0": rows(["end"]),
        # One arrival parks an inactive pickup; the other waits, then
        # activates slot 3, which it never filled.
        "main:0": rows(
            ["switch", 100, 26, [[10, 0], [80, None]]],
            ["case"],
            ["switch", 60, 7, [[30, 0]]],
            ["case"],
            ["goto", 20],
            ["break"],
            ["aot_on", 3],
            ["break"],
            ["case"],
            ["item", 3, 0, 20, 15, 1],
            ["end"],
        ),
    }
    result = evaluate(program, variables={26: None}, approach=frozenset({26}), gids=[1])
    assert result.item_presence == {1: False}


def test_suspended_task_keeps_its_callers_loop_count():
    from games.scd_state import evaluate_entry

    program = {
        # The caller's loop is in its second pass when the callee waits.
        "main:0": rows(
            ["loop", 40, -1, "while"],
            ["calc", 4, 0, 1],
            ["gosub", 7],
            ["loop_end"],
            ["end"],
        ),
        "main:7": rows(
            ["switch", 40, 4, [[10, 2]]],
            ["case"],
            ["goto", 0],
            ["break"],
            ["end"],
        ),
    }
    state = GameState(
        lambda bank, bit: False,
        lambda index: 0,
        frozenset(),
        frozenset(),
        lambda item: False,
    )
    entry = evaluate_entry(program, state, EngineTasks(("main:0",), frozenset()))
    ((frames, _),) = {task for outcome in entry.terminals for task in outcome.suspended}
    assert frames[0][4] == ((0, (1, 0, 39)),)


def test_resumes_differing_only_in_taint_run_once(monkeypatch):
    import games.scd_state as scd_state

    # Each unreadable condition's early jump taints the same pickup write on
    # one side only, so entry outcomes differ in taint alone.
    body = []
    for index in range(3):
        base = len(body) * 10
        body += [
            ["if", base + 30],
            ["ck", 4, index, 1],
            ["goto", base + 40],
            ["case"],
            ["item", index, 0x31, 20, 15, 100 + index],
        ]
    base = len(body) * 10
    body += [
        ["switch", base + 40, 7, [[base + 10, 0]]],
        ["case"],
        ["goto", base],
        ["break"],
        ["end"],
    ]
    program = {"main:0": rows(*body)}
    state = GameState(
        lambda bank, bit: None if bank == 4 else False,
        lambda index: 0,
        frozenset(),
        frozenset(),
        lambda item: False,
    )
    entry = scd_state.evaluate_entry(
        program, state, EngineTasks(("main:0",), frozenset())
    )
    assert len(entry.terminals) > 1
    runs = []
    original = scd_state._Interpreter.run

    def counted(self, start):
        runs.append(len(start))
        return original(self, start)

    monkeypatch.setattr(scd_state._Interpreter, "run", counted)
    later = scd_state.evaluate_later(program, state, entry, frozenset())
    assert later.support is Support.Supported
    assert len(runs) == 1


def test_later_analysis_bounds_its_total_work(monkeypatch):
    import games.scd_state as scd_state

    # Each choice parks a pickup in another slot before the same wait, so
    # resumed tasks multiply with their interactions.
    labels = [[10 + 30 * index, index] for index in range(10)]
    body = [["switch", 10 + 30 * len(labels), 5, labels]]
    for index in range(len(labels)):
        body += [["case"], ["item", index, 0, 20, 15, 100 + index], ["break"]]
    wait = len(body) * 10
    body += [
        ["switch", wait + 40, 7, [[wait + 10, 0]]],
        ["case"],
        ["goto", wait],
        ["break"],
        ["end"],
    ]
    program = {
        "init:0": rows(["end"]),
        "main:0": rows(*body),
        "main:1": rows(["end"]),
    }
    monkeypatch.setattr(scd_state, "MAX_LATER_STEPS", 50)
    result = evaluate(program, variables={5: None}, approach=frozenset({5}))
    assert result.support is Support.Unsupported
    assert result.reason == "later script evaluation step limit"


def test_resumes_differing_only_in_task_taint_run_once(monkeypatch):
    import games.scd_state as scd_state

    program = {
        # The waiting task starts once under an unreadable condition and once
        # outside it.
        "init:0": rows(["if", 30], ["ck", 4, 1, 1], ["exec", 2], ["exec", 2], ["end"]),
        "main:2": rows(
            ["switch", 40, 7, [[10, 0]]],
            ["case"],
            ["goto", 0],
            ["break"],
            ["end"],
        ),
    }
    state = GameState(
        lambda bank, bit: None if bank == 4 else False,
        lambda index: 0,
        frozenset(),
        frozenset(),
        lambda item: False,
    )
    entry = scd_state.evaluate_entry(
        program, state, EngineTasks(("init:0",), frozenset())
    )
    runs = []
    original = scd_state._Interpreter.run

    def counted(self, start):
        runs.append(start[0].frames[0].tainted)
        return original(self, start)

    monkeypatch.setattr(scd_state._Interpreter, "run", counted)
    later = scd_state.evaluate_later(program, state, entry, frozenset())
    assert later.support is Support.Supported
    assert runs == [False]


def test_while_waiting_on_native_state_keeps_its_effects_pending():
    def program(read: list) -> dict:
        # The door is replaced in place, then a While loop waits before
        # restoring it, as room 00-1b does with key flag 9:27.
        return {
            "init:0": rows(["end"]),
            "main:0": rows(
                ["var", 4, 0, 0],
                ["door", 6, 0x31],
                ["reset", 6, 0, 0, -1, -1, -1, -1],
                ["loop", 60, -1, "while"],
                read,
                ["loop_end"],
                ["reset", 6, 1, 0x31, -1, -1, -1, -1],
                ["end"],
            ),
        }

    # A key flag no room script writes: the door stays replaced until it is set.
    waiting = evaluate(program(["ck", 9, 27, 0])).doors[10]
    assert (waiting.sat, waiting.replaced) == (0, True)
    opened = evaluate(program(["ck", 9, 27, 0]), flags={(9, 27): True}).doors[10]
    assert (opened.sat, opened.replaced) == (0x31, False)
    # Another running task writes variable 4, so the wait ends by itself.
    counted = evaluate(
        {**program(["cmp", 4, 0, 0]), "main:1": rows(["var", 4, 0, 1], ["end"])}
    ).doors[10]
    assert (counted.sat, counted.replaced) == (0x31, False)
    # Only the waiting task's own earlier write sets it: nothing can end it.
    stuck = evaluate(program(["cmp", 4, 0, 0])).doors[10]
    assert (stuck.sat, stuck.replaced) == (0, True)


def door_after_wait(wait: list[list], extra: dict | None = None) -> dict:
    """Slot 6's door is replaced, then restored after ``wait``'s rows."""
    return {
        "init:0": rows(["end"]),
        "main:0": rows(
            ["door", 6, 0x31],
            ["reset", 6, 0, 0, -1, -1, -1, -1],
            *wait,
            ["reset", 6, 1, 0x31, -1, -1, -1, -1],
            ["end"],
        ),
        **(extra or {}),
    }


def door_state(program: dict, **state) -> tuple:
    door = evaluate(program, **state).doors[0]
    return door.sat, door.replaced


def test_do_waiting_on_native_state_keeps_its_effects_pending():
    # The predicate follows the closing command.
    wait = [["loop", 50, -1, "do"], ["loop_end"], ["ck", 9, 27, 0]]
    assert door_state(door_after_wait(wait)) == (0, True)
    assert door_state(door_after_wait(wait), flags={(9, 27): True}) == (0x31, False)


def test_do_whose_predicate_fails_exits_after_one_pass():
    wait = [
        ["loop", 60, -1, "do"],
        ["set", 9, 3, 1],
        ["loop_end"],
        ["ck", 9, 3, 0],
    ]
    assert door_state(door_after_wait(wait)) == (0x31, False)


def test_incidental_native_read_does_not_make_a_counter_loop_wait():
    wait = [
        ["var", 4, 0, 0],
        ["loop", 80, -1, "while"],
        ["cmp", 4, 3, 3],
        ["calc", 4, 0, 1],
        # A native variable copied into a temporary the loop never tests.
        ["var", 5, 1, 7],
        ["loop_end"],
    ]
    assert door_state(door_after_wait(wait)) == (0x31, False)


def test_only_a_runnable_releasing_write_ends_a_wait():
    wait = [["loop", 50, -1, "while"], ["ck", 9, 27, 0], ["loop_end"]]
    # Procedure 8 would set the flag, but nothing runs it.
    unrunnable = {"main:8": rows(["set", 9, 27, 1], ["end"])}
    assert door_state(door_after_wait(wait, unrunnable)) == (0, True)
    # A script that only clears the flag cannot release the wait either.
    clearing = {"main:1": rows(["set", 9, 27, 0], ["end"])}
    assert door_state(door_after_wait(wait, clearing)) == (0, True)
    # A trigger the room creates can set it, so the wait ends by itself.
    trigger = {
        "init:0": rows(["aot", 2, 5, 0x31, 8], ["end"]),
        "main:8": rows(["set", 9, 27, 1], ["end"]),
    }
    assert door_state(door_after_wait(wait, trigger)) == (0x31, False)


def test_patched_flag_writer_can_release_a_wait_in_its_bank():
    wait = [["loop", 50, -1, "while"], ["ck", 9, 27, 0], ["loop_end"]]
    patched = {
        "main:1": rows(["patch", 32, 4, 1], ["end"], ["end"], ["set", 9, 0, 1]),
    }
    assert door_state(door_after_wait(wait, patched)) == (0x31, False)


def test_conditional_goto_waits_only_on_native_state():
    def program(flag: tuple[int, int]) -> dict:
        return door_after_wait(
            [["if", 60], ["ck", *flag, 0], ["goto", 20], ["end"]],
            {"main:1": rows(["set", 4, 1, 1], ["end"])},
        )

    assert door_state(program((9, 27))) == (0, True)
    # Flag 4:1 is set by a running script, so the jump ends by itself.
    assert door_state(program((4, 1))) == (0x31, False)


def test_do_with_an_unread_predicate_forks_exit_and_repeat():
    # Leaving after one pass restores the door; repeating waits on native
    # flag 4:5, so which happens depends on unread game state.
    program = door_after_wait(
        [["loop", 60, -1, "do"], ["set", 9, 3, 7], ["loop_end"], ["ck", 4, 5, 1]]
    )
    assert evaluate(program, flags={(4, 5): None}).doors[0].sat is None


def test_do_on_an_arrival_variable_gives_alternatives():
    program = {
        "init:0": rows(["end"]),
        "main:0": rows(
            ["item", 3, 0x31, 20, 15, 77],
            ["loop", 40, -1, "do"],
            ["loop_end"],
            ["cmp", 26, 5, 1],
            ["reset", 3, 0, 0, -1, -1, -1, -1],
            ["end"],
        ),
    }
    result = evaluate(
        program, variables={26: None}, approach=frozenset({26}), gids=[77]
    )
    assert result.item_presence == {77: True}


def test_else_wait_needs_a_write_that_ends_it():
    # if flag 9:27 is set: leave; else: jump back. Only a clear is written.
    wait = [["if", 50], ["ck", 9, 27, 1], ["else", 60], ["goto", 20]]
    clearing = {"main:1": rows(["set", 9, 27, 0], ["end"])}
    assert door_state(door_after_wait(wait, clearing)) == (0, True)
    setting = {"main:1": rows(["set", 9, 27, 1], ["end"])}
    assert door_state(door_after_wait(wait, setting)) == (0x31, False)


def test_value_copied_from_native_state_in_a_called_procedure_waits():
    wait = [
        ["loop", 60, -1, "while"],
        ["gosub", 8],
        ["cmp", 4, 0, 0],
        ["loop_end"],
    ]
    copied = {"main:8": rows(["var", 4, 1, 7], ["end"])}
    assert door_state(door_after_wait(wait, copied)) == (0, True)


def test_only_a_predicate_inside_the_wait_decides_it():
    # The outer If on flag 4:1, which a running script sets, opens before the
    # wait's head; the jump really waits on native flag 9:27.
    program = door_after_wait(
        [
            ["if", 80],
            ["ck", 4, 1, 0],
            # Loop head: leave once 9:27 is set, otherwise jump back.
            ["if", 70],
            ["ck", 9, 27, 1],
            ["goto", 80],
            ["goto", 40],
        ],
        {"main:1": rows(["set", 4, 1, 1], ["end"])},
    )
    assert door_state(program) == (0, True)


def test_wait_inside_a_for_reads_the_whole_loop():
    program = door_after_wait(
        [
            ["loop", 80, 3, "for"],
            ["if", 60],
            ["ck", 9, 27, 1],
            ["break"],
            ["goto", 20],
            ["loop_end"],
        ]
    )
    assert door_state(program) == (0, True)


def test_patched_predicate_bit_needs_a_releasing_write_in_its_bank():
    wait = [["if", 60], ["patch", 42, 4, 1], ["ck", 9, 0, 0], ["goto", 20]]
    # Any bit of bank 9 may be the one tested; only a set can release it.
    clearing = {"main:1": rows(["set", 9, 5, 0], ["end"])}
    assert door_state(door_after_wait(wait, clearing)) == (0, True)
    setting = {"main:1": rows(["set", 9, 5, 1], ["end"])}
    assert door_state(door_after_wait(wait, setting)) == (0x31, False)


def test_else_wait_needs_every_predicate_of_its_if():
    # Leaving needs both 9:27 and 9:28; the room can only set 9:27.
    wait = [
        ["if", 70],
        ["ck", 9, 27, 1],
        ["set", 3, 3, 1],
        ["ck", 9, 28, 1],
        ["else", 80],
        ["goto", 20],
    ]
    setting = {"main:1": rows(["set", 9, 27, 1], ["end"])}
    assert door_state(door_after_wait(wait, setting)) == (0, True)


def test_one_releasable_predicate_ends_a_compound_while():
    # The loop repeats while the counter is below 3 and native flag 9:27 is
    # clear, so the counter alone ends it.
    wait = [
        ["var", 4, 0, 0],
        ["loop", 80, -1, "while"],
        ["cmp", 4, 3, 3],
        ["ck", 9, 27, 0],
        ["calc", 4, 0, 1],
        ["loop_end"],
    ]
    assert door_state(door_after_wait(wait)) == (0x31, False)


def test_patched_comparison_value_follows_its_native_source():
    wait = [
        ["var", 4, 0, 0],
        ["loop", 80, -1, "while"],
        ["cmp", 4, 0, 0],
        # Work_copy writes native variable 7's copy into the compared value
        # for the next pass.
        ["var", 5, 1, 7],
        ["patch", 44, 5, 2],
        ["loop_end"],
    ]
    assert door_state(door_after_wait(wait)) == (0, True)


def test_patched_predicate_bit_chosen_by_a_room_variable_can_end_a_wait():
    wait = [["if", 60], ["patch", 42, 4, 1], ["ck", 9, 0, 0], ["goto", 20]]
    choosing = {"main:1": rows(["var", 4, 0, 1], ["end"])}
    assert door_state(door_after_wait(wait, choosing)) == (0x31, False)


def test_do_on_unread_game_state_waits_natively():
    wait = [["loop", 50, -1, "do"], ["loop_end"], ["cond", 0]]
    assert evaluate(door_after_wait(wait)).doors[0].sat is None


def test_tainted_do_predicate_that_leaves_taints_what_follows():
    # Flag 9:1 is set only under unread game state. With it set the Do leaves
    # after one pass and the door is restored; otherwise it runs twice.
    program = {
        "init:0": rows(["end"]),
        "main:0": rows(
            ["door", 6, 0x31],
            ["reset", 6, 0, 0, -1, -1, -1, -1],
            ["if", 50],
            ["cond", 0],
            ["set", 9, 1, 1],
            ["var", 6, 0, 0],
            ["loop", 100, -1, "do"],
            ["calc", 6, 0, 1],
            ["loop_end"],
            ["ck", 9, 1, 0],
            ["if", 130],
            ["cmp", 6, 0, 1],
            ["reset", 6, 1, 0x31, -1, -1, -1, -1],
            ["end"],
        ),
    }
    assert evaluate(program).doors[0].sat is None


def test_tainted_if_that_skips_writes_taints_what_follows():
    # Flag 9:1 is set only under unread game state; when set, the If skips
    # the counter, and the door is restored only if the counter stayed 0.
    program = {
        "init:0": rows(["end"]),
        "main:0": rows(
            ["door", 6, 0x31],
            ["reset", 6, 0, 0, -1, -1, -1, -1],
            ["if", 50],
            ["cond", 0],
            ["set", 9, 1, 1],
            ["if", 80],
            ["ck", 9, 1, 0],
            ["calc", 6, 0, 1],
            ["if", 110],
            ["cmp", 6, 0, 0],
            ["reset", 6, 1, 0x31, -1, -1, -1, -1],
            ["end"],
        ),
    }
    assert evaluate(program).doors[0].sat is None


def test_else_wait_ends_when_a_predicate_in_the_else_fails():
    # if 9:27: leave; else: while 9:28 holds, jump back. A running task
    # clears 9:28.
    wait = [["if", 50], ["ck", 9, 27, 1], ["else", 70], ["ck", 9, 28, 1], ["goto", 20]]
    clearing = {"main:1": rows(["set", 9, 28, 0], ["end"])}
    assert door_state(door_after_wait(wait, clearing), flags={(9, 28): True}) == (
        0x31,
        False,
    )


def test_else_wait_needs_only_the_if_predicates_that_do_not_hold_yet():
    # Leaving needs 9:27 and 9:28; 9:27 already holds and the room sets 9:28.
    wait = [
        ["if", 60],
        ["ck", 9, 27, 1],
        ["ck", 9, 28, 1],
        ["else", 70],
        ["goto", 20],
    ]
    setting = {"main:1": rows(["set", 9, 28, 1], ["end"])}
    assert door_state(door_after_wait(wait, setting), flags={(9, 27): True}) == (
        0x31,
        False,
    )


def test_branch_inside_a_wait_reads_the_whole_loop():
    # A forward jump can skip the counter test, so the wait is classified by
    # every read: native flag 9:27 keeps it waiting.
    wait = [
        ["loop", 100, -1, "while"],
        ["ck", 9, 27, 0],
        ["if", 70],
        ["ck", 4, 9, 0],
        ["goto", 90],
        ["cmp", 5, 3, 3],
        ["calc", 5, 0, 1],
        ["loop_end"],
    ]
    assert door_state(door_after_wait(wait)) == (0, True)


def test_counter_ends_a_wait_with_a_native_bound():
    wait = [
        ["var", 4, 0, 0],
        ["loop", 90, -1, "while"],
        ["cmp", 4, 3, 3],
        # The bound comes from native variable 7 through Work_copy.
        ["var", 5, 1, 7],
        ["patch", 44, 5, 2],
        ["calc", 4, 0, 1],
        ["loop_end"],
    ]
    assert door_state(door_after_wait(wait), variables={7: 3}) == (0x31, False)


def test_outer_counter_guard_ends_an_inner_native_wait():
    wait = [
        ["var", 4, 0, 0],
        ["loop", 100, -1, "while"],
        ["cmp", 4, 3, 3],
        ["calc", 4, 0, 1],
        ["if", 90],
        ["ck", 9, 27, 0],
        ["goto", 30],
        ["loop_end"],
    ]
    assert door_state(door_after_wait(wait)) == (0x31, False)
