# Container Stow Planner

A `nanoagent.plugin/v0001` plugin. Its task gives an agent six containers,
a small ship, four stacks of up to three tiers, and a broken draft plan, and asks for a repaired plan
that keeps every rule. Many plans can be right, so the verifier is a constraint
checker, not an exact match. Everything runs offline: a case is built from its
seed alone.

## Tools

| Tool | Does | Code |
|---|---|---|
| `pin_stowage` | The answer key: the case and its planted witness plan, hidden from the agent | `src/plugin/stowage.py` |
| `read_stowage` | The containers, plug slots and limits, without the plan | `src/plugin/stowage.py` |
| `check_plan` | Lists every rule a draft breaks, with stack and side weights; saves nothing | `src/plugin/plan.py` |
| `try_swap` | Swaps two containers of the draft and lists what the result breaks | `src/plugin/plan.py` |
| `save_plan` | Saves the plan to `plans/<seed>.json` | `src/plugin/plan.py` |

### Tasks

| Task | Does | Runner |
|---|---|---|
| `plan-stowage` | Finds and saves a legal stowage plan | `agent`, with `read_stowage`, `try_swap` and `save_plan`; reference `pin_stowage` |

## Verification

Each case is built around a planted witness plan, and a case is thrown out if a
greedy first-fit (heaviest first, ties by id, into the first legal slot, no going
back; tried stack by stack and tier by tier) loads the ship. The verifier stores
no answer to compare with: it runs its own checker on the witness and refuses a
key that fails (`answer-key`). It then reads the saved file, not just the
submission, and judges in order: `answer-key`, `seed`, `saved`, `coverage`, then
all seven rules at once: `no-floating`, `no-restow`, `no-crush`, `reefer-plug`,
`hazmat-separation`, `stack-weight`, `balance`.

Integrity failures score 0. That includes `coverage`: a container missing,
repeated or unknown, a slot that does not exist, or a slot given twice. Otherwise
`details.failed` lists every broken rule and the score is the share of the seven
that hold, capped at 0.99.

## Limitations

- A plan saved by an earlier run with the same seed still counts if the agent
  submits it without saving again. The plan is judged the same either way.
- `try_swap` tells the agent what is broken, and one swap always repairs the draft, so
  the task measures choosing and reading repairs, not planning a ship blind. Planning
  from nothing took DeepSeek up to 16,000 reasoning tokens, past the hosted 2,048 cap.
- `check_plan` stays for direct use, and the task does not offer it.
- The verifier cannot rebuild a case from its seed, because the generator is
  outside its sandbox. It trusts the pinned containers and limits, and only proves
  the witness is legal for them.
- Cases are small, to fit the hosted agent's step and token limits.

## Layout

```text
.
├── nanoagent.yaml   # manifest (a slimconfig ManifestConfig): id, runtime, permissions, tools, tasks
├── contract.py      # each tool's and task's typed input and output: slimconfig Output classes
├── README.md
├── LICENSE
├── pyproject.toml
├── uv.lock
├── .gitignore
├── .env             # environment variable NAMEs this plugin needs, never values
├── src/plugin/      # the MCP server, the seeded case generator, and the plan checker and writer
├── tests/
├── ui/              # how the page draws the outputs: renderers.js and renderers.css
├── product/         # the product page a catalog shows: product.yaml and icon.svg
└── verifier/        # deterministic verifier package
```

`contract.py` is the one place a value's shape is declared. Its `Output`
classes are the JSON Schemas the server offers and the agent sees, and every
input and output is built into its class on the way in and out: the server,
NanoAgent and the verifier all get typed values, never loose dicts. A tool
that fails raises; NanoAgent sees an MCP error.

To add a tool: add a `Tool` member, its input and output classes and its
`TOOLS` entry to `contract.py` (a snake_case name, classes named `...Input`
and `...Output`); write its implementation in `src/plugin/`, taking its input
and the workspace and returning its output; write its `verify_input` /
`verify_output` in `verifier/`, and tests for both. Then register it in
`src/plugin/__main__.py` (`IMPLEMENTATIONS`), `verifier/__init__.py` (`TOOLS`),
`nanoagent.yaml` (`tools`) and this README's Tools table; a task goes in its
Tasks table.

`LICENSE` stays the template's MIT license under your name, `.gitignore`
keeps its entries, and this README keeps its title and sections: NanoAgent refuses a plugin
that changes them (rule 10 of `nanoagent.plugin.manifest`). Renaming the
plugin means renaming it in `nanoagent.yaml` and this title together.

To add a task, add a `Task` member (a kebab-case id) and its `TASKS` input and
output classes to `contract.py`, and declare it in `nanoagent.yaml` with its `runner` (`tool`,
`agent` or `decide`) and a `reference` tool, or `null` if it has none. A `tool`
task's classes are its tool's; an `agent` task's agent ends by calling `submit`
with the task's output; a `decide` task's model only chooses, and every tool
argument and output field is an Enum or bool, or copied from a value of exactly
its type in the task's input or an earlier tool output. Then add the check of
its output, `verify_task(arguments, output, reference, workspace)`, to `TASKS`
in `verifier/__init__.py`. People use the plugin by chatting with its agent,
which runs its tasks and shows each output on the page (see `ui/`).

## Develop and run

```bash
uv sync --extra dev
uv run pytest
```

Publishing checks every plugin rule: push the plugin to a public GitHub
repository and run `rush publish <server> <github-url>`.
