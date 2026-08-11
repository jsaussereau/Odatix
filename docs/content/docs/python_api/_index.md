---
title: "Python API"
description: "odatix.workspace, odatix.run and odatix config — reading and writing the configuration of a workspace, and running what it describes, from Python instead of by hand."
weight: 20
---

# Python API

> [!IMPORTANT] Requires Odatix 4.0+

Every file documented in this section can be written by hand, and that is often
the shortest path. When it is not — a workspace generated from a spreadsheet, a
CI job that adds a target, a script that sweeps a design over several
technologies — the same files are read and written by the **`odatix.workspace`**
API, and by the **`odatix config`** command built on it. What they describe is
then run through **`odatix.run`**.

These are the very APIs Odatix itself uses: what a page of the graphical
interface does to a workspace, and what a command runs, is exactly what a script
does through them.

{{< toc >}}

## Opening a workspace

Everything hangs off a `Workspace`. Paths are resolved once, from `odatix.yml`,
so nothing else takes a path.

{{< code lang=python filename="open.py" >}}
from odatix.workspace import Workspace

ws = Workspace.open()              # the workspace of the current directory
ws = Workspace.open("~/designs")   # or another one
ws = Workspace.init("new_dir")     # create the configuration files, then open it

print(ws.paths.arch_path)          # where its architectures are
print(ws.architectures.names())    # what it holds
{{< /code >}}

`Workspace.open()` never fails on a directory that holds no `odatix.yml`: the
Odatix defaults apply, which is what a workspace about to be initialized looks
like. Pass `required=True` to refuse it instead.

## What a workspace holds

| Attribute | What it gives |
|-----------|---------------|
| `ws.architectures` | the [architectures](/docs/reference/architecture/) |
| `ws.simulations` | the [simulations](/docs/reference/simulation/) |
| `ws.workflows` | the [workflows](/docs/reference/workflow/) |
| `ws.tools` | the [eda tools](/docs/reference/tools/), built-in ones included |
| `ws.targets` | the [target files](/docs/reference/targets/), one per tool |
| `ws.jobs` | the [run settings files](/docs/reference/run_settings/), one per command |
| `ws.derived_metrics` | the [derived metrics](/docs/reference/metrics/) of the workspace |
| `ws.paths` | where each of them is |

Collections behave like the mappings they are, and iterate over objects:

{{< code lang=python filename="browse.py" >}}
"MyCPU" in ws.architectures        # True / False
ws.architectures["MyCPU"]          # raises NotFoundError if there is none
ws.architectures.get("MyCPU")      # None instead
ws.architectures.entry("MyCPU")    # whether or not it exists yet

for architecture in ws.architectures:
    print(f"{architecture.name} => {architecture.settings.top_level_module}")
{{< /code >}}

## Settings objects

Settings are typed: they know their keys, their defaults and how each one is
written. They are also mappings, so code that would rather use them as such can.

{{< code lang=python filename="settings.py" >}}
architecture = ws.architectures.create("MyCPU")

architecture.settings.rtl_path = "rtl/cpu"
architecture.settings.top_level_file = "cpu.sv"
architecture.settings.top_level_module = "cpu"
architecture.settings.clock_signal = "clk"
architecture.settings.use_parameters = True
architecture.settings.fmax_synthesis.lower_bound = 50
architecture.save()

architecture.update(top_level_module="cpu_top")   # change and save, in one call

architecture.settings["clock_signal"]             # same thing, as a mapping
architecture.settings.to_dict()                   # plain values
{{< /code >}}

Values are read as their type whatever they come as, so `"Yes"`, `true` and
`True` all mean the same thing, and `"50"` is stored as `50`.

> [!NOTE]
> Saving keeps what you put in the file: its comments, its key order, its
> quoting and every key Odatix does not know about. 
> Only what actually changed is rewritten, and unknown
> keys stay reachable through `settings.extra`. A file that does not exist yet
> is generated with the section comments that make it readable.

## Parameter domains and configurations

An architecture (or a workflow) carries a main [parameter
domain](/docs/configurations/param_domains/) and any number of named ones. Both
behave the same here.

{{< code lang=python filename="domains.py" >}}
architecture.configs.write("08bits", "\n  parameter WIDTH = 8;\n")
architecture.configs.names()                 # ["08bits"], no ".txt"
architecture.configs["08bits"].read()

width = architecture.domains.create("width", param_target_file="rtl/cpu.sv")
width.settings.start_delimiter = "#("
width.settings.stop_delimiter = ")"
width.save()

architecture.combinations()                  # what a run would sweep
architecture.count_combinations()
{{< /code >}}

Configurations can be generated instead of written, from the same settings
[`odatix generate`](/docs/configurations/config_generation/) reads:

{{< code lang=python filename="generate.py" >}}
generation = width.settings.generate_configurations_settings
generation.name = "${width}bits"
generation.template = "WIDTH = ${width}"
width.settings.set_variable("width", "range", {"from": 8, "to": 64, "step": 8})
width.settings.generate_configurations = True
width.save()

width.preview_configurations()               # {name: content}, writes nothing
width.generate_configurations(overwrite=True)
{{< /code >}}

## Tools and targets

{{< code lang=python filename="tools.py" >}}
tool = ws.tools["vivado"]
tool.is_builtin                              # shipped with Odatix
tool.settings.flow_names()                   # ["standard", "power_opt"]
tool.settings.default_flow.command("fmax_synthesis")

tool.settings.label = "Vivado 2024.1"
tool.save()          # writes only what differs from the built-in definition

targets = ws.targets["vivado"]
targets.enabled_names()                      # what runs
targets.add("xc7a100t-csg324-1")
targets.disable("xc7s25-csga225-1")          # kept in the file, commented out
{{< /code >}}

A tool of your own is created the same way, and is written whole:

{{< code lang=python filename="own_tool.py" >}}
tool = ws.tools.create("my_tool", label="My Tool")
tool.settings.default_flow.set_command("fmax_synthesis", ["make fmax"])
tool.save()
{{< /code >}}

## What each command runs

`ws.jobs` holds one entry per run command, each with the settings of its file.

{{< code lang=python filename="jobs.py" >}}
run = ws.jobs.fmax_synthesis
run.settings.architectures = ["MyCPU/08bits", "MyCPU/16bits"]
run.settings.nb_jobs = "auto"
run.settings.fmax_synthesis.lower_bound = 50
run.save()

ws.jobs.simulation.settings.simulations = {"TB_Counter": ["MyCPU/08bits"]}
ws.jobs.simulation.save()

ws.jobs["analysis"].settings.tools = ["vivado", "verilator"]
{{< /code >}}

Reading one the way a run needs it — every required key spelled out, values of
the right kind — is `load()`, which raises `InvalidSettingsError` on a file a
run could not start from:

{{< code lang=python filename="load.py" >}}
settings = ws.jobs.fmax_synthesis.load()
print(settings.nb_jobs, settings.architectures)
{{< /code >}}

## Running

`odatix.run` starts what those files describe. A run goes through three steps,
and stopping after any of them is a normal thing to do.

{{< code lang=python filename="run.py" >}}
from odatix.workspace import Workspace
from odatix.run import Run

run = Run(Workspace.open(), "fmax_synthesis", tool="vivado", overwrite=True)

plan = run.check()      # what would be run, having touched nothing
print(plan.counts())    # {'new': 12, 'cached': 3, 'error': 0, ...}

run.prepare()           # every work directory written, nothing started
run.start()             # handed over to the daemon
{{< /code >}}

Each step does the ones before it when they have not been done, so
`run.start()` alone runs everything, and `run_job("fmax_synthesis",
tool="vivado")` is the whole thing in one call.

Every path comes from the workspace. What a run does differently from what its
settings file says is passed as keyword arguments — the command line flags, by
name: `overwrite`, `nb_jobs`, `flow`, `until`, `keep`, `lower_bound` /
`upper_bound`, `frequencies`, `detach`, `session`…

| Mode | What it runs |
|------|--------------|
| `"fmax_synthesis"` | the fmax binary search of `odatix fmax` |
| `"custom_freq_synthesis"` | the synthesis at given frequencies of `odatix synth` |
| `"pnr"` | the place & route of `odatix pnr` |
| `"analysis"` | the RTL analysis of `odatix analyze` |
| `"simulation"` | the simulations of `odatix sim` |
| `"workflow"` | the workflows of `odatix workflow` |

A run never stops the interpreter and never asks a question: what it cannot do
raises `RunError`, carrying what it reported, and everything it said along the
way is on `run.reporter`.

{{< code lang=python filename="errors.py" >}}
from odatix.run import RunError

try:
    run.check()
except RunError as error:
    print(error)              # what went wrong
    print(error.errors())     # everything reported as an error
{{< /code >}}

## Errors

| Exception | Raised when |
|-----------|-------------|
| `NotFoundError` | there is no such architecture, domain, tool, target… (also a `KeyError`) |
| `AlreadyExistsError` | the name asked for is taken (also a `ValueError`) |
| `InvalidNameError` | the name cannot be a directory name (empty, contains `/`…) |
| `NotAWorkspaceError` | the directory holds no settings file, and one was required |
| `InvalidSettingsError` | a settings file cannot be run from (missing, unreadable, incomplete) |

All of them derive from `WorkspaceError`. A run raises `RunError` (it could not
go on) and `RunCancelled` (it was asked to stop).

## See also

- [Configuration file reference](/docs/reference/) — every file, every key.
- [Commands reference](/docs/commands/) — every command and its options.
