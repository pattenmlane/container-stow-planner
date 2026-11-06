"""The ship and its rules: the one checker every plan, the witness included, has to pass."""

from itertools import permutations

from contract import Kind

from .checks import repeated

MAX_SEED = 100_000
STACKS = (1, 2, 3, 4)  # a row across the ship: 1 and 2 port side, 3 and 4 starboard
PORT_SIDE = (1, 2)
TIERS = (1, 2, 3)
RULES = ("no-floating", "no-restow", "no-crush", "reefer-plug", "hazmat-separation", "stack-weight", "balance")


def stack_weights(case, plan):
    weight = {box.id: box.weight for box in case.containers}
    return [sum(weight[spot.container] for spot in plan if spot.stack == stack) for stack in STACKS]


def side_weights(case, plan):
    weights = dict(zip(STACKS, stack_weights(case, plan)))
    port = sum(weights[stack] for stack in PORT_SIDE)
    return port, sum(weights.values()) - port


def coverage_problem(case, plan):
    """Why ``plan`` isn't one real slot per container, or None."""
    named = [spot.container for spot in plan]
    known = {box.id for box in case.containers}
    if repeated(named):
        return f"placed more than once: {', '.join(repeated(named))}"
    if set(named) - known:
        return f"no such container: {', '.join(sorted(set(named) - known))}"
    if known - set(named):
        return f"never placed: {', '.join(sorted(known - set(named)))}"
    bad = [f"{spot.container} at stack {spot.stack} tier {spot.tier}" for spot in plan if not on_ship(spot)]
    if bad:
        return f"no such slot: {', '.join(bad)}"
    twice = repeated([(spot.stack, spot.tier) for spot in plan])
    return f"slot given twice: {', '.join(f'stack {s} tier {t}' for s, t in twice)}" if twice else None


def on_ship(spot):
    return spot.stack in STACKS and spot.tier in TIERS


def broken_rules(case, plan):
    """{rule id: what's wrong} for every broken rule. Works on a part-built plan too."""
    box = {item.id: item for item in case.containers}
    plugs = {(slot.stack, slot.tier) for slot in case.plugs}
    filled = {(spot.stack, spot.tier) for spot in plan}
    broken = {rule: [] for rule in RULES}

    for spot in plan:
        if spot.tier > 1 and (spot.stack, spot.tier - 1) not in filled:
            broken["no-floating"].append(f"{spot.container} has nothing under it")
        if box[spot.container].kind is Kind.REEFER and (spot.stack, spot.tier) not in plugs:
            broken["reefer-plug"].append(f"{spot.container} has no plug at stack {spot.stack} tier {spot.tier}")

    for one, other in permutations(plan, 2):
        a, b = box[one.container], box[other.container]
        if one.stack == other.stack and one.tier > other.tier:  # anywhere above, so a gap hides nothing
            if a.discharge_port > b.discharge_port:
                broken["no-restow"].append(f"{a.id} sits on {b.id}, which discharges earlier")
            if a.weight > b.weight:
                broken["no-crush"].append(f"{a.id} sits on the lighter {b.id}")
        if a.kind is Kind.HAZMAT and b.kind is Kind.REEFER:
            if one.stack == other.stack:
                broken["hazmat-separation"].append(f"{a.id} shares a stack with {b.id}")
            elif abs(one.stack - other.stack) == 1 and one.tier == other.tier:
                broken["hazmat-separation"].append(f"{a.id} is beside {b.id} at tier {one.tier}")

    for stack, weight in zip(STACKS, stack_weights(case, plan)):
        if weight > case.stack_limit:
            broken["stack-weight"].append(f"stack {stack} weighs {weight}, over {case.stack_limit}")
    port, starboard = side_weights(case, plan)
    if abs(port - starboard) > case.balance_limit:
        broken["balance"].append(f"port {port} and starboard {starboard} differ by over {case.balance_limit}")
    return {rule: found for rule, found in broken.items() if found}


def broken_lines(case, plan):
    """Every broken rule as one line of text, the way the tools show them."""
    return [f"{rule}: {text}" for rule, texts in broken_rules(case, plan).items() for text in texts]
