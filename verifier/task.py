"""The verdict on a saved plan: integrity first, then every rule at once."""

from .checks import result, saved_json
from .rules import RULES, broken_lines, broken_rules, coverage_problem


def key_problem(seed, pinned):
    """Why the answer key can't be trusted, or None. The witness has to pass our own checker."""
    if pinned is None:
        return "no answer key was pinned"
    if pinned.seed != seed:
        return f"the answer key is for seed {pinned.seed}, not {seed}"
    if not pinned.containers:
        return "the answer key has no containers"
    problem = coverage_problem(pinned, pinned.plan)
    if problem:
        return f"the witness is not a full plan: {problem}"
    broken = broken_rules(pinned, pinned.plan)
    if broken:
        return f"the witness breaks {', '.join(broken)}"
    problem = coverage_problem(pinned, pinned.draft)
    if problem:
        return f"the draft is not a full plan: {problem}"
    lines = broken_lines(pinned, pinned.draft)
    if not lines or lines != pinned.draft_broken:
        return "the draft must break a rule, and show exactly what it breaks"
    return None


def spots(plan):
    return sorted((spot.container, spot.stack, spot.tier) for spot in plan)


def saved_problem(output, workspace):
    expected = f"plans/{output.seed}.json"
    if output.path != expected:
        return f"the submission names {output.path!r}, not {expected!r}"
    saved = saved_json(workspace, expected)
    if saved is None:
        return f"no plan is saved at {expected}: call save_plan before submitting"
    try:
        entries = sorted((entry["container"], entry["stack"], entry["tier"]) for entry in saved["plan"])
        same = saved["seed"] == output.seed and entries == spots(output.plan)
    except (KeyError, TypeError):
        return f"the file at {expected} is not a plan"
    return None if same else f"the submission differs from the plan saved at {expected}"


def plan_verdict(arguments, output, reference, workspace):
    problem = key_problem(arguments.seed, reference)
    if problem:
        return result(False, f"answer-key: {problem}", score=0.0, failed=["answer-key"])
    if output.seed != arguments.seed:
        return result(False, f"seed: the submission is for seed {output.seed}", score=0.0, failed=["seed"])
    problem = saved_problem(output, workspace)
    if problem:
        return result(False, f"saved: {problem}", score=0.0, failed=["saved"])
    problem = coverage_problem(reference, output.plan)
    if problem:
        return result(False, f"coverage: {problem}", score=0.0, failed=["coverage"])

    broken = broken_rules(reference, output.plan)
    if not broken:
        return result(True, f"All {len(RULES)} rules hold")
    first = next(iter(broken))
    message = f"{first}: {broken[first][0]} ({len(broken)} of {len(RULES)} rules broken: {', '.join(broken)})"
    score = min(1 - len(broken) / len(RULES), 0.99)
    return result(False, message, score=score, failed=list(broken), problems=broken)
