from __future__ import annotations

import hashlib
import json
from itertools import combinations
from pathlib import Path

import pytest
from slimconfig import build_output, plain_output

import verifier
from contract import Container, Kind, PinnedStowageOutput, Placement, PlanInput, PlanOutput, StowInput, TrySwapInput
from plugin import check_plan, read_stowage, save_plan, try_swap
from plugin.stowage import SLOTS_BY_STACK, SLOTS_BY_TIER, build_case, first_fit
from verifier.rules import broken_lines, broken_rules, coverage_problem
from verifier.task import key_problem, spots


def legal_plans(case: PinnedStowageOutput, enough: int) -> list[list[Placement]]:
    """Plain search up each stack, stopping once ``enough`` legal plans turn up."""
    found: list[list[Placement]] = []

    def walk(stack: int, tier: int, plan: list[Placement], left: frozenset[str]) -> None:
        if len(found) >= enough or stack > 4:
            return
        walk(stack + 1, 1, plan, left)
        for name in sorted(left) if tier <= 3 else ():
            trial = [*plan, Placement(name, stack, tier)]
            if set(broken_rules(case, trial)) <= {"balance"}:
                if len(left) > 1:
                    walk(stack, tier + 1, trial, left - {name})
                elif not broken_rules(case, trial) and spots(trial) not in map(spots, found):
                    found.append(trial)

    walk(1, 1, [], frozenset(box.id for box in case.containers))
    return found


@pytest.mark.parametrize("seed", range(1, 301))
def test_every_case_has_a_confirmed_witness_that_greedy_first_fit_misses(seed: int) -> None:
    case = build_case(seed)
    assert key_problem(seed, case) is None
    assert first_fit(case, SLOTS_BY_STACK) is None and first_fit(case, SLOTS_BY_TIER) is None


@pytest.mark.parametrize("seed", range(1, 301))
def test_every_draft_is_complete_and_really_broken(seed: int) -> None:
    case = build_case(seed)
    assert coverage_problem(case, case.draft) is None
    assert broken_rules(case, case.draft) and case.draft_broken == broken_lines(case, case.draft)


def test_most_cases_have_more_than_one_legal_plan_and_any_of_them_passes(tmp_path: Path) -> None:
    several = 0
    for seed in range(1, 61):
        case = build_case(seed)
        plans = legal_plans(case, 2)
        if len(plans) == 2:
            several += 1
            other = next(plan for plan in plans if spots(plan) != spots(case.plan))
            made = save_plan(PlanInput(seed, other), tmp_path)
            pinned = build_output(plain_output(case), PinnedStowageOutput)
            output = build_output(plain_output(made), PlanOutput)
            verdict = verifier.verify_task("plan-stowage", StowInput(seed), output, pinned, str(tmp_path))
            assert verdict["valid"] is True, verdict["message"]
    assert several >= 50


@pytest.mark.parametrize("seed", range(1, 301))
def test_one_swap_always_repairs_the_draft(seed: int, tmp_path: Path) -> None:
    case = build_case(seed)
    names = [box.id for box in case.containers]
    tried = [try_swap(TrySwapInput(seed, *pair), tmp_path) for pair in combinations(names, 2)]
    assert any(not attempt.broken for attempt in tried)


def test_try_swap_refuses_nonsense(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="swap"):
        try_swap(TrySwapInput(7, "C1", "C1"), tmp_path)
    with pytest.raises(ValueError, match="swap"):
        try_swap(TrySwapInput(7, "C1", "C99"), tmp_path)


def test_first_fit_really_can_load_an_easy_ship() -> None:
    boxes = [Container(f"C{n}", 10, Kind.DRY, 1) for n in range(1, 5)]
    easy = PinnedStowageOutput(1, boxes, [], 100, 100, [], [], [])
    assert not broken_rules(easy, first_fit(easy, SLOTS_BY_TIER))


def test_cases_are_reproducible_to_the_byte() -> None:
    digest = hashlib.sha256(json.dumps(plain_output(build_case(1)), sort_keys=True).encode()).hexdigest()
    assert digest == "a83f3cf42b64edfb78a4452ed3f7eba4ce70de2a9963d9bfe5c965b14e7e4d89"


def test_the_agent_never_sees_the_answer(tmp_path: Path) -> None:
    shown = plain_output(read_stowage(StowInput(3), tmp_path))
    assert "plan" not in shown and shown["containers"] == plain_output(build_case(3))["containers"]
    assert len(json.dumps(shown)) < 6000


def test_check_plan_adds_up_and_names_what_is_broken(tmp_path: Path) -> None:
    case = build_case(7)
    made = check_plan(PlanInput(7, case.plan), tmp_path)
    assert made.broken == []
    assert sum(made.stack_weights) == made.port_weight + made.starboard_weight == sum(b.weight for b in case.containers)
    top = next(
        s for s in case.plan if s.tier < 3 and (s.stack, s.tier + 1) not in {(o.stack, o.tier) for o in case.plan}
    )
    gap = [spot for spot in case.plan if spot is not top] + [Placement(top.container, top.stack, top.tier + 1)]
    assert any(line.startswith("no-floating: ") for line in check_plan(PlanInput(7, gap), tmp_path).broken)


def test_check_plan_refuses_an_incomplete_plan(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="never placed"):
        check_plan(PlanInput(7, build_case(7).plan[1:]), tmp_path)


@pytest.mark.parametrize("seed", [0, -1, 100_001])
def test_refuses_a_seed_out_of_range(seed: int) -> None:
    with pytest.raises(ValueError, match="seed"):
        build_case(seed)
