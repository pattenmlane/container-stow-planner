"""Each tool's and task's typed input and output (see nanoagent.plugin.v0001.contract): declarations only."""

from dataclasses import dataclass
from enum import Enum
from typing import Annotated

from slimconfig import Output


class Tool(Enum):
    PIN_STOWAGE = "pin_stowage"
    READ_STOWAGE = "read_stowage"
    CHECK_PLAN = "check_plan"
    TRY_SWAP = "try_swap"
    SAVE_PLAN = "save_plan"


class Task(Enum):
    PLAN_STOWAGE = "plan-stowage"


class Kind(Enum):
    DRY = "dry"
    REEFER = "reefer"
    HAZMAT = "hazmat"


SEED = "The case number, 1 to 100000: the same number always gives the same containers"
PLAN = "One placement per container"
CONTAINERS = "Every container to load"
PLUGS = "The slots with a power plug"
STACK_LIMIT = "The most a stack may weigh, in tonnes"
BALANCE_LIMIT = "The largest allowed difference between port and starboard weight, in tonnes"


@dataclass
class Container(Output):
    id: Annotated[str, "The container's id"]
    weight: Annotated[int, "Its weight in tonnes"]
    kind: Annotated[Kind, "What it carries: dry, reefer or hazmat"]
    discharge_port: Annotated[int, "Where it comes off the ship: 1 is the first port"]


@dataclass
class Slot(Output):
    stack: Annotated[int, "The stack, 1 to 4"]
    tier: Annotated[int, "The tier, 1 (bottom) to 3"]


@dataclass
class Placement(Output):
    container: Annotated[str, "The container's id"]
    stack: Annotated[int, "The stack, 1 to 4"]
    tier: Annotated[int, "The tier, 1 (bottom) to 3"]


@dataclass
class StowInput(Output):
    seed: Annotated[int, SEED]


@dataclass
class StowageOutput(Output):
    seed: Annotated[int, SEED]
    containers: Annotated[list[Container], CONTAINERS]
    plugs: Annotated[list[Slot], PLUGS]
    stack_limit: Annotated[int, STACK_LIMIT]
    balance_limit: Annotated[int, BALANCE_LIMIT]
    draft: Annotated[list[Placement], "A complete plan someone drew up, which breaks at least one rule"]
    draft_broken: Annotated[list[str], "Every rule the draft breaks, as rule id: what is wrong"]


@dataclass
class PinnedStowageOutput(Output):
    # The answer key: the case and the plan it was planted around, out of the agent's sight.
    seed: Annotated[int, SEED]
    containers: Annotated[list[Container], CONTAINERS]
    plugs: Annotated[list[Slot], PLUGS]
    stack_limit: Annotated[int, STACK_LIMIT]
    balance_limit: Annotated[int, BALANCE_LIMIT]
    plan: Annotated[list[Placement], PLAN]
    draft: Annotated[list[Placement], "A complete plan someone drew up, which breaks at least one rule"]
    draft_broken: Annotated[list[str], "Every rule the draft breaks, as rule id: what is wrong"]


@dataclass
class PlanInput(Output):
    seed: Annotated[int, SEED]
    plan: Annotated[list[Placement], PLAN]


@dataclass
class CheckOutput(Output):
    seed: Annotated[int, SEED]
    broken: Annotated[list[str], "Every broken rule, as rule id: what is wrong. Empty when the plan is legal"]
    stack_weights: Annotated[list[int], "The weight of stacks 1, 2, 3 and 4 in tonnes"]
    port_weight: Annotated[int, "The weight of stacks 1 and 2 in tonnes"]
    starboard_weight: Annotated[int, "The weight of stacks 3 and 4 in tonnes"]


@dataclass
class PlanOutput(Output):
    seed: Annotated[int, SEED]
    path: Annotated[str, "The saved plan, relative to the plugin workspace"]
    plan: Annotated[list[Placement], PLAN]


@dataclass
class TrySwapInput(Output):
    seed: Annotated[int, SEED]
    first: Annotated[str, "One container of the draft"]
    second: Annotated[str, "The container it trades places with"]


@dataclass
class TrySwapOutput(Output):
    seed: Annotated[int, SEED]
    first: Annotated[str, "One container of the draft"]
    second: Annotated[str, "The container it traded places with"]
    broken: Annotated[list[str], "Every rule the swapped plan breaks; empty when it keeps them all"]
    plan: Annotated[list[Placement], PLAN]


TOOLS = {
    Tool.PIN_STOWAGE: (StowInput, PinnedStowageOutput),
    Tool.READ_STOWAGE: (StowInput, StowageOutput),
    Tool.CHECK_PLAN: (PlanInput, CheckOutput),
    Tool.TRY_SWAP: (TrySwapInput, TrySwapOutput),
    Tool.SAVE_PLAN: (PlanInput, PlanOutput),
}
TASKS = {Task.PLAN_STOWAGE: (StowInput, PlanOutput)}
