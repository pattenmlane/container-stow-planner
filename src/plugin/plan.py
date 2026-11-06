from __future__ import annotations

import json
from pathlib import Path

from slimconfig import plain_output

from contract import CheckOutput, Placement, PlanInput, PlanOutput, TrySwapInput, TrySwapOutput
from plugin.stowage import build_case
from verifier.rules import broken_lines, coverage_problem, side_weights, stack_weights


def check_plan(given: PlanInput, workspace: Path) -> CheckOutput:
    case = build_case(given.seed)
    problem = coverage_problem(case, given.plan)
    if problem:
        raise ValueError(problem)
    return CheckOutput(
        given.seed, broken_lines(case, given.plan), stack_weights(case, given.plan), *side_weights(case, given.plan)
    )


def try_swap(given: TrySwapInput, workspace: Path) -> TrySwapOutput:
    """The draft with two containers trading places, and what it breaks. The agent picks the swaps."""
    case = build_case(given.seed)
    names = {spot.container for spot in case.draft}
    if given.first == given.second or not {given.first, given.second} <= names:
        raise ValueError(f"swap two different containers of the draft, not {given.first} and {given.second}")
    trade = {given.first: given.second, given.second: given.first}
    plan = [Placement(trade.get(spot.container, spot.container), spot.stack, spot.tier) for spot in case.draft]
    return TrySwapOutput(given.seed, given.first, given.second, broken_lines(case, plan), plan)


def save_plan(given: PlanInput, workspace: Path) -> PlanOutput:
    relative = f"plans/{given.seed}.json"
    path = workspace / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plain_output(given), indent=2), encoding="utf-8")
    return PlanOutput(given.seed, relative, given.plan)
