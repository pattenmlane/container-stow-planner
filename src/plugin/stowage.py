"""Builds a case around a planted plan, throws it out if a greedy first-fit can load the ship, and
damages the plan into the broken draft the agent repairs: planning from nothing doesn't fit one reply."""

from __future__ import annotations

from pathlib import Path

from contract import Container, Kind, PinnedStowageOutput, Placement, Slot, StowageOutput, StowInput
from plugin.rng import Rng
from verifier.rules import MAX_SEED, STACKS, TIERS, broken_lines, broken_rules

SHAPES = ((2, 2, 1, 1), (3, 1, 1, 1), (2, 2, 2, 0), (3, 2, 1, 0))
SLOTS_BY_STACK = [(stack, tier) for stack in STACKS for tier in TIERS]
SLOTS_BY_TIER = [(stack, tier) for tier in TIERS for stack in STACKS]
ATTEMPTS = 2000


def _attempt(seed: int, attempt: int) -> PinnedStowageOutput | None:
    rng = Rng(f"stowage:{seed}:{attempt}")
    ids = rng.shuffled([f"C{number}" for number in range(1, 7)])
    kinds = [Kind.REEFER, Kind.HAZMAT]
    kinds = rng.shuffled(kinds + [Kind.DRY] * (6 - len(kinds)))

    containers, plan = [], []
    for stack, height in zip(STACKS, rng.shuffled(rng.pick(SHAPES))):
        weight, port = rng.between(18, 30), rng.between(2, 4)
        for tier in range(1, height + 1):
            box = Container(ids[len(plan)], weight, kinds[len(plan)], port)
            containers.append(box)
            plan.append(Placement(box.id, stack, tier))
            weight -= rng.pick((0, 2, 3, 5))  # going up: never heavier, never later
            port = max(1, port - rng.below(2))

    boxes = {box.id: box for box in containers}
    plugs = {(spot.stack, spot.tier) for spot in plan if boxes[spot.container].kind is Kind.REEFER}
    plugs |= set(rng.shuffled(SLOTS_BY_STACK)[:2])
    case = PinnedStowageOutput(
        seed,
        sorted(containers, key=lambda box: int(box.id[1:])),
        [Slot(*slot) for slot in sorted(plugs)],
        0,
        0,
        sorted(plan, key=lambda spot: (spot.stack, spot.tier)),
        [],
        [],
    )
    totals = [sum(boxes[spot.container].weight for spot in plan if spot.stack == stack) for stack in STACKS]
    case.stack_limit = max(totals) + rng.between(0, 6)
    case.balance_limit = abs(totals[0] + totals[1] - totals[2] - totals[3]) + rng.between(0, 4)
    if broken_rules(case, plan) or first_fit(case, SLOTS_BY_STACK) or first_fit(case, SLOTS_BY_TIER):
        return None
    case.draft = _damaged(rng, case.plan)
    case.draft_broken = broken_lines(case, case.draft)
    return case if case.draft_broken else None


def _damaged(rng: Rng, plan: list[Placement]) -> list[Placement]:
    """``plan`` with one pair of containers swapped: still complete, usually broken."""
    one, other = rng.shuffled(range(len(plan)))[:2]
    names = [spot.container for spot in plan]
    names[one], names[other] = names[other], names[one]
    return [Placement(name, spot.stack, spot.tier) for name, spot in zip(names, plan)]


def first_fit(case: StowageOutput, slots: list[tuple[int, int]]) -> list[Placement] | None:
    """Heaviest first (ties by id) into the first legal slot, no going back. None if that doesn't load
    the ship. Balance needs the whole ship, so it's only judged at the end."""
    plan: list[Placement] = []
    for box in sorted(case.containers, key=lambda item: (-item.weight, int(item.id[1:]))):
        taken = {(spot.stack, spot.tier) for spot in plan}
        for stack, tier in slots:
            trial = [*plan, Placement(box.id, stack, tier)]
            if (stack, tier) not in taken and set(broken_rules(case, trial)) <= {"balance"}:
                plan = trial
                break
        else:
            return None
    return None if broken_rules(case, plan) else plan


def build_case(seed: int) -> PinnedStowageOutput:
    if not 1 <= seed <= MAX_SEED:
        raise ValueError(f"seed must be 1 to {MAX_SEED}, got {seed}")
    for attempt in range(ATTEMPTS):
        case = _attempt(seed, attempt)
        if case is not None:
            return case
    raise RuntimeError(f"no usable case for seed {seed} in {ATTEMPTS} attempts")


def pin_stowage(given: StowInput, workspace: Path) -> PinnedStowageOutput:
    return build_case(given.seed)


def read_stowage(given: StowInput, workspace: Path) -> StowageOutput:
    case = build_case(given.seed)
    return StowageOutput(
        case.seed, case.containers, case.plugs, case.stack_limit, case.balance_limit, case.draft, case.draft_broken
    )
