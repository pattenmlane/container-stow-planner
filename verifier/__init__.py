"""The deterministic verifier: a constraint checker on contract instances, so any legal plan passes. No model."""

from contract import Task, Tool

from .checks import repeated, result, saved_json
from .rules import MAX_SEED
from .task import key_problem, plan_verdict

TASKS = {Task.PLAN_STOWAGE: plan_verdict}


def verify_input(tool, value):
    if not 1 <= value.seed <= MAX_SEED:
        return result(False, f"seed must be 1 to {MAX_SEED}")
    if Tool(tool) in (Tool.CHECK_PLAN, Tool.SAVE_PLAN):
        twice = repeated([spot.container for spot in value.plan])
        if twice:
            return result(False, f"placed more than once: {', '.join(twice)}")
    return result(True, "input is valid")


def verify_output(tool, input_value, output_value, workspace):
    if output_value.seed != input_value.seed:
        return result(False, "the output is for another seed")
    match Tool(tool):
        case Tool.PIN_STOWAGE:
            problem = key_problem(input_value.seed, output_value)
            return result(not problem, problem or "the answer key holds")
        case Tool.READ_STOWAGE:
            return result(bool(output_value.containers), "the case has containers")
        case Tool.CHECK_PLAN:
            return result(len(output_value.stack_weights) == 4, "one weight per stack")
        case Tool.TRY_SWAP:
            return result(bool(output_value.plan), "the swap gave a plan")
        case Tool.SAVE_PLAN:
            saved = saved_json(workspace, output_value.path)
            return result(saved is not None, "saved" if saved is not None else "nothing was saved")


def verify_task(task, arguments, output, reference, workspace):
    return TASKS[Task(task)](arguments, output, reference, workspace)
