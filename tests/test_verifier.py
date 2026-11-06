from __future__ import annotations

import json
from pathlib import Path

import pytest
from slimconfig import build_output, plain_output

import verifier
from contract import (
    CheckOutput,
    Container,
    Kind,
    PinnedStowageOutput,
    Placement,
    PlanInput,
    PlanOutput,
    Slot,
    StowInput,
)
from plugin import check_plan, pin_stowage, save_plan
from tests.test_stowage import legal_plans
from verifier.checks import repeated
from verifier.rules import RULES, broken_lines, broken_rules, coverage_problem
from verifier.task import spots

SEED = 7
TASK = "plan-stowage"


# The verifier gets contract instances, as NanoAgent's sandbox builds them from JSON.
def key(tmp_path: Path) -> PinnedStowageOutput:
    return build_output(plain_output(pin_stowage(StowInput(SEED), tmp_path)), PinnedStowageOutput)


def judge(plan: list[Placement], tmp_path: Path, reference=None) -> dict:
    output = build_output(plain_output(save_plan(PlanInput(SEED, plan), tmp_path)), PlanOutput)
    return verifier.verify_task(TASK, StowInput(SEED), output, reference or key(tmp_path), str(tmp_path))


def ship(*boxes: tuple, plugs=(), stack_limit=100, balance_limit=100) -> PinnedStowageOutput:
    """A hand-made case from (id, weight, kind, discharge port)."""
    return PinnedStowageOutput(
        SEED, [Container(*box) for box in boxes], [Slot(*p) for p in plugs], stack_limit, balance_limit, [], [], []
    )


def at(*spots: tuple) -> list[Placement]:
    return [Placement(*spot) for spot in spots]


def moved(plan: list[Placement], index: int, stack: int, tier: int) -> list[Placement]:
    return [Placement(plan[index].container, stack, tier) if n == index else s for n, s in enumerate(plan)]


def top_index(plan: list[Placement]) -> int:
    """A stack top that has room above it."""
    tops = {spot.stack: n for n, spot in sorted(enumerate(plan), key=lambda item: item[1].tier)}
    return next(n for n in tops.values() if plan[n].tier < 3)


DRY, REEFER, HAZMAT = Kind.DRY, Kind.REEFER, Kind.HAZMAT


def test_accepts_the_witness_in_any_order(tmp_path: Path) -> None:
    pinned = key(tmp_path)
    assert judge(pinned.plan, tmp_path)["score"] == 1.0
    assert judge(list(reversed(pinned.plan)), tmp_path)["valid"] is True


def test_accepts_a_legal_plan_that_is_not_the_witness(tmp_path: Path) -> None:
    pinned = key(tmp_path)
    other = next(plan for plan in legal_plans(pinned, 2) if spots(plan) != spots(pinned.plan))
    verdict = judge(other, tmp_path)
    assert verdict["valid"] is True and verdict["score"] == 1.0


def test_a_tier_gap_is_a_broken_rule_with_partial_score(tmp_path: Path) -> None:
    plan = key(tmp_path).plan
    n = top_index(plan)
    verdict = judge(moved(plan, n, plan[n].stack, plan[n].tier + 1), tmp_path)
    assert verdict["valid"] is False and "no-floating" in verdict["details"]["failed"]
    assert verdict["message"].startswith("no-floating: ")
    assert verdict["score"] == pytest.approx(1 - len(verdict["details"]["failed"]) / len(RULES))


def test_reports_every_broken_rule_and_scores_the_share_that_hold(tmp_path: Path) -> None:
    pinned = key(tmp_path)
    flipped = []  # every stack upside down
    for spot in pinned.plan:
        height = max(other.tier for other in pinned.plan if other.stack == spot.stack)
        flipped.append(Placement(spot.container, spot.stack, height + 1 - spot.tier))
    verdict = judge(flipped, tmp_path)
    assert verdict["valid"] is False and len(verdict["details"]["failed"]) >= 2
    assert list(broken_rules(pinned, flipped)) == verdict["details"]["failed"]
    assert verdict["score"] == pytest.approx(1 - len(verdict["details"]["failed"]) / len(RULES))


def test_one_broken_rule_scores_six_sevenths_and_the_limit_itself_passes(tmp_path: Path) -> None:
    case = ship(("A", 20, DRY, 1), ("B", 15, DRY, 1), balance_limit=5)
    case.plan = at(("A", 2, 1), ("B", 3, 1))
    case.draft = at(("A", 1, 1), ("B", 1, 2))
    case.draft_broken = broken_lines(case, case.draft)
    assert judge(case.plan, tmp_path, case)["score"] == 1.0  # the difference is exactly 5
    verdict = judge(at(("A", 1, 1), ("B", 1, 2)), tmp_path, case)
    assert verdict["details"]["failed"] == ["balance"] and verdict["score"] == pytest.approx(6 / 7)


def test_integrity_failures_score_zero(tmp_path: Path) -> None:
    plan = key(tmp_path).plan
    twice = moved(plan, 1, plan[0].stack, plan[0].tier)
    cases = [
        plan[1:],  # missing
        [],
        [plan[0], *plan],  # repeated container
        twice,  # a slot given twice
        [Placement("C99", 1, 1), *plan[1:]],  # unknown container
        moved(plan, 0, 5, 1),  # no such stack
        moved(plan, 0, 1, 4),  # no such tier
        moved(plan, 0, 1, 0),
    ]
    for wrong in cases:
        verdict = judge(wrong, tmp_path)
        assert verdict["valid"] is False and verdict["score"] == 0.0
        assert verdict["details"]["failed"] == ["coverage"]
    assert "slot given twice" in judge(twice, tmp_path)["message"]


def test_repeated_copes_with_enums_and_slots() -> None:
    assert repeated([DRY, HAZMAT, DRY, HAZMAT, REEFER]) == [DRY, HAZMAT]
    assert repeated([(1, 1), (1, 1), (2, 1)]) == [(1, 1)]


@pytest.mark.parametrize(
    "nonsense",
    [
        [("C1", 99, 1)],
        [("C1", -1, -1), ("C2", 0, 0)],
        [("C1", 1, 10**12)],
        [("", 1, 1)],
        [("C99", 99, 99), ("C99", 99, 99)],
        [("C1", 1, 1), ("C1", 1, 1), ("C2", 1, 1), ("C2", 1, 1)],
        [(f"C{n}", 1, 1) for n in range(1, 9)],
        [(f"C{n}", 7, n) for n in range(1, 9)],
    ],
)
def test_well_typed_nonsense_gets_a_clean_refusal(tmp_path: Path, nonsense: list) -> None:
    plan = at(*nonsense)
    assert verifier.verify_input("save_plan", PlanInput(SEED, plan))["message"]
    verdict = judge(plan, tmp_path)
    assert verdict["valid"] is False and verdict["score"] == 0.0 and verdict["details"]["failed"] == ["coverage"]


def test_refuses_a_file_that_is_not_text(tmp_path: Path) -> None:
    pinned = key(tmp_path)
    (tmp_path / "plans").mkdir()
    (tmp_path / "plans" / f"{SEED}.json").write_bytes(b"\xff\xfe")
    output = PlanOutput(SEED, f"plans/{SEED}.json", pinned.plan)
    assert verifier.verify_task(TASK, StowInput(SEED), output, pinned, str(tmp_path))["details"]["failed"] == ["saved"]


def test_refuses_a_submission_with_nothing_saved(tmp_path: Path) -> None:
    pinned = key(tmp_path)
    output = PlanOutput(SEED, f"plans/{SEED}.json", pinned.plan)
    verdict = verifier.verify_task(TASK, StowInput(SEED), output, pinned, str(tmp_path))
    assert verdict["score"] == 0.0 and verdict["details"]["failed"] == ["saved"]


def test_refuses_a_submission_that_differs_from_the_file(tmp_path: Path) -> None:
    pinned = key(tmp_path)
    save_plan(PlanInput(SEED, pinned.plan[:-1]), tmp_path)
    output = PlanOutput(SEED, f"plans/{SEED}.json", pinned.plan)
    verdict = verifier.verify_task(TASK, StowInput(SEED), output, pinned, str(tmp_path))
    assert verdict["valid"] is False and "differs" in verdict["message"]


@pytest.mark.parametrize(
    "text",
    ["not json", "[]", '{"seed": 7}', '{"seed": 7, "plan": [1]}', '{"seed": 7, "plan": 3}', '{"plan": [{"stack": 1}]}'],
)
def test_refuses_a_malformed_file(tmp_path: Path, text: str) -> None:
    pinned = key(tmp_path)
    (tmp_path / "plans").mkdir()
    (tmp_path / "plans" / f"{SEED}.json").write_text(text)
    output = PlanOutput(SEED, f"plans/{SEED}.json", pinned.plan)
    verdict = verifier.verify_task(TASK, StowInput(SEED), output, pinned, str(tmp_path))
    assert verdict["valid"] is False and verdict["details"]["failed"] == ["saved"]


def test_refuses_another_path_or_seed(tmp_path: Path) -> None:
    pinned = key(tmp_path)
    save_plan(PlanInput(SEED, pinned.plan), tmp_path)
    output = PlanOutput(SEED, "../elsewhere.json", pinned.plan)
    assert verifier.verify_task(TASK, StowInput(SEED), output, pinned, str(tmp_path))["details"]["failed"] == ["saved"]
    save_plan(PlanInput(8, pinned.plan), tmp_path)
    output = PlanOutput(8, "plans/8.json", pinned.plan)
    assert verifier.verify_task(TASK, StowInput(SEED), output, pinned, str(tmp_path))["details"]["failed"] == ["seed"]


def test_refuses_a_missing_or_altered_answer_key(tmp_path: Path) -> None:
    pinned = key(tmp_path)
    save_plan(PlanInput(SEED, pinned.plan), tmp_path)
    output = PlanOutput(SEED, f"plans/{SEED}.json", pinned.plan)
    assert verifier.verify_task(TASK, StowInput(SEED), output, None, str(tmp_path))["score"] == 0.0
    for change in (
        lambda bad: setattr(bad, "stack_limit", 1),
        lambda bad: setattr(bad, "plan", bad.plan[1:]),
        lambda bad: setattr(bad, "containers", []),
        lambda bad: setattr(bad, "seed", 8),
    ):
        bad = build_output(plain_output(pinned), PinnedStowageOutput)
        change(bad)
        verdict = verifier.verify_task(TASK, StowInput(SEED), output, bad, str(tmp_path))
        assert verdict["score"] == 0.0 and verdict["details"]["failed"] == ["answer-key"]


@pytest.mark.parametrize(("limit", "broken"), [(30, {}), (29, {"stack-weight"})])
def test_stack_weight_exactly_at_the_limit(limit: int, broken: set) -> None:
    case = ship(("A", 20, DRY, 1), ("B", 10, DRY, 1), stack_limit=limit)
    assert set(broken_rules(case, at(("A", 1, 1), ("B", 1, 2)))) == set(broken)


@pytest.mark.parametrize(("limit", "broken"), [(5, {}), (4, {"balance"})])
def test_balance_exactly_at_the_limit_and_one_over(limit: int, broken: set) -> None:
    case = ship(("A", 20, DRY, 1), ("B", 15, DRY, 1), balance_limit=limit)
    assert set(broken_rules(case, at(("A", 2, 1), ("B", 3, 1)))) == set(broken)
    assert set(broken_rules(case, at(("B", 2, 1), ("A", 3, 1)))) == set(broken)  # absolute, either way


def test_equal_weights_and_equal_ports_may_stack() -> None:
    case = ship(("A", 20, DRY, 2), ("B", 20, DRY, 1), ("C", 15, DRY, 1))
    assert not broken_rules(case, at(("A", 1, 1), ("B", 1, 2), ("C", 1, 3)))


def test_restow_and_crush_go_the_right_way_round() -> None:
    late_on_early = ship(("A", 20, DRY, 1), ("B", 10, DRY, 2))
    assert set(broken_rules(late_on_early, at(("A", 1, 1), ("B", 1, 2)))) == {"no-restow"}
    assert not broken_rules(late_on_early, at(("A", 1, 1), ("B", 2, 1)))
    heavy_on_light = ship(("A", 10, DRY, 2), ("B", 20, DRY, 1))
    assert set(broken_rules(heavy_on_light, at(("A", 1, 1), ("B", 1, 2)))) == {"no-crush"}


def test_a_gap_hides_neither_restow_nor_crush() -> None:
    case = ship(("A", 10, DRY, 1), ("B", 20, DRY, 2))
    assert set(broken_rules(case, at(("A", 1, 1), ("B", 1, 3)))) == {"no-floating", "no-restow", "no-crush"}


def test_no_floating_at_tier_two_on_an_empty_stack() -> None:
    assert set(broken_rules(ship(("A", 10, DRY, 1)), at(("A", 1, 2)))) == {"no-floating"}


def test_reefer_needs_a_plug_in_that_exact_slot() -> None:
    case = ship(("A", 10, REEFER, 1), plugs=[(2, 1)])
    assert not broken_rules(case, at(("A", 2, 1)))
    assert set(broken_rules(case, at(("A", 1, 1)))) == {"reefer-plug"}


@pytest.mark.parametrize(
    ("hazmat", "reefer", "allowed"),
    [
        ((1, 1), (2, 1), False),  # neighbours, same tier
        ((2, 1), (3, 1), False),  # neighbours across the centreline
        ((4, 1), (3, 1), False),
        ((1, 1), (3, 1), True),  # two apart
        ((1, 1), (4, 1), True),  # the far sides
        ((2, 1), (4, 1), True),
        ((1, 1), (2, 2), True),  # neighbours, other tier
        ((1, 1), (1, 2), False),  # same stack
        ((1, 1), (1, 3), False),  # same stack, not touching
    ],
)
def test_hazmat_separation(hazmat: tuple, reefer: tuple, allowed: bool) -> None:
    case = ship(("H", 20, HAZMAT, 1), ("R", 10, REEFER, 1), plugs=[reefer])
    assert ("hazmat-separation" not in broken_rules(case, at(("H", *hazmat), ("R", *reefer)))) is allowed


def test_coverage_names_a_slot_given_twice() -> None:
    case = ship(("A", 10, DRY, 1), ("B", 10, DRY, 1))
    assert "slot given twice" in coverage_problem(case, at(("A", 1, 1), ("B", 1, 1)))


def test_refuses_bad_tool_input() -> None:
    assert verifier.verify_input("read_stowage", StowInput(0))["valid"] is False
    assert verifier.verify_input("read_stowage", StowInput(100_001))["valid"] is False
    assert verifier.verify_input("read_stowage", StowInput(100_000))["valid"] is True
    twice = PlanInput(1, at(("C1", 1, 1), ("C1", 2, 1)))
    assert verifier.verify_input("save_plan", twice)["valid"] is False
    assert verifier.verify_input("check_plan", twice)["valid"] is False


def test_tool_outputs_are_checked(tmp_path: Path) -> None:
    pinned = key(tmp_path)
    given = PlanInput(SEED, pinned.plan)
    made = save_plan(given, tmp_path)
    assert json.loads((tmp_path / made.path).read_text())["plan"] == plain_output(given)["plan"]
    assert verifier.verify_output("save_plan", given, made, str(tmp_path))["valid"] is True
    assert verifier.verify_output("pin_stowage", StowInput(SEED), pinned, str(tmp_path))["valid"] is True
    checked = build_output(plain_output(check_plan(given, tmp_path)), CheckOutput)
    assert verifier.verify_output("check_plan", given, checked, str(tmp_path))["valid"] is True
    assert verifier.verify_output("pin_stowage", StowInput(8), pinned, str(tmp_path))["valid"] is False


def test_refuses_the_draft_unchanged(tmp_path: Path) -> None:
    pinned = key(tmp_path)
    made = save_plan(PlanInput(SEED, pinned.draft), tmp_path)
    output = build_output(plain_output(made), PlanOutput)
    verdict = verifier.verify_task("plan-stowage", StowInput(SEED), output, pinned, str(tmp_path))
    assert verdict["valid"] is False and verdict["details"]["failed"]


def test_refuses_an_answer_key_whose_draft_is_not_broken(tmp_path: Path) -> None:
    pinned = key(tmp_path)
    pinned.draft, pinned.draft_broken = pinned.plan, []
    made = save_plan(PlanInput(SEED, pinned.plan), tmp_path)
    output = build_output(plain_output(made), PlanOutput)
    verdict = verifier.verify_task("plan-stowage", StowInput(SEED), output, pinned, str(tmp_path))
    assert verdict["details"]["failed"] == ["answer-key"]
