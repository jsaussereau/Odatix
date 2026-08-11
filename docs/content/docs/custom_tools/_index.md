---
title: "Custom tools and flows"
description: "Add your own EDA tools to Odatix, and your own ways of running the ones it already ships."
weight: 11
---

# Custom tools and flows

Odatix has **no hard-coded list of supported tools**. A tool is simply a
directory containing a `tool.yml`, discovered at run time. That is what makes it
possible to run Odatix on an in-house script, on a tool Odatix has never heard
of, or on the tools it ships with — but run your way.

{{< toc >}}

## Three things you can add

| You want to | Add a | Read |
|-------------|-------|------|
| Run an existing tool differently — other options, other scripts, another binary, a resumable pipeline | **flow** | [Run your own flows and scripts](/docs/custom_tools/add_flows/) |
| Run a synthesis / place & route / analysis tool Odatix does not ship | **tool** | [Add non supported tools](/docs/custom_tools/add_tools/) |
| Run something that is not a synthesis at all — a script, a training, a benchmark, an arbitrary pipeline | **workflow** | [Workflows](/docs/features/workflows/) |

The line between a *tool* and a *workflow* is what the job looks like. A tool is
driven by Odatix's synthesis machinery: it gets a design, a target, a clock, a
frequency (or a frequency search), and produces the metrics Odatix compares
across all of them. A workflow runs a task graph you describe yourself, with no
clock, no target and no frequency search, and produces whatever metrics you
define.

## Where tools live

Tools are looked up in two directories, **highest precedence first**:

1. the workspace tools directory — `odatix_userconfig/tools/` by default,
   configurable with the `tools_path` key of `odatix.yml`;
2. the built-in directory shipped with Odatix.

Any directory holding a `tool.yml` in either location is a tool. Directories
whose name starts with `_` or `.` are skipped — that is how `_common/` stays a
shared script directory instead of becoming a tool.

{{< code lang=text filename="Workspace layout" >}}
odatix_userconfig/
├── odatix.yml                  # tools_path: "odatix_userconfig/tools"
├── target_myTool.yml           # targets of your tool
└── tools/
    └── myTool/
        ├── tool.yml            # what to run — the only required file
        ├── metrics.yml         # what to measure
        └── tcl/                # scripts copied into every job directory
            └── synth_script.tcl
{{< /code >}}

### A tool defined in both places

A tool can exist in the workspace **and** in the built-in directory at the same
time. The two `tool.yml` files are then merged key by key, the workspace one
taking precedence, and the scripts of both directories are copied into the job
directory (the workspace ones last, so they win).

This is what lets a `odatix_userconfig/tools/vivado/tool.yml` holding nothing but
a `flows:` section *add* a flow to the built-in Vivado, without copying its whole
definition.

> [!IMPORTANT]
> The **built-in flows are read-only**. What a workspace `tool.yml` says about
> them — the `unix` / `windows` command sections of a built-in tool, its
> `default_flow`, and any flow name Odatix already declares — is dropped, with a
> warning naming what was ignored. A built-in tool always runs what Odatix says
> it runs, so a result tagged `vivado / standard` means the same thing in every
> workspace.
>
> Everything else goes through untouched: flows of your own, the metadata,
> `report_path`, `default_metrics_file`, the `format` section… And to start from
> what a built-in tool does and own all of it, **duplicate** it into your
> workspace: the copy is a tool of its own, with nothing read-only left.

## Tool, flow, job type, step

Four notions are easy to confuse, and telling them apart makes the rest of this
section obvious:

| Notion | What it is | Chosen by |
|--------|-----------|-----------|
| **Tool** | A directory with a `tool.yml`: Vivado, Genus, your own script. | `-t/--tool` |
| **Job type** | What Odatix runs: an fmax search, a synthesis at given frequencies, a place & route, an RTL analysis. | the command (`odatix fmax`, `synth`, `pnr`, `analyze`) |
| **Flow** | A way of running a tool: other options, other scripts, another binary. Flows of one tool are alternatives meant to be **compared**, so each gets its own work directory and tags its results. | `-f/--flow` |
| **Step** | One stage of a flow — synthesis, place & route, bitstream — run as its own process, stoppable and resumable. | `-u/--until` |

## Doing it from the GUI

Everything below can be done without opening a text editor. `odatix-gui` →
**EDA Tools** lists the tools of your workspace and, apart, the built-in ones:

- **Create New Tool** — a new workspace tool with a minimal `tool.yml`;
- **Settings** — the [Tool Editor](/docs/custom_tools/add_tools/#the-tool-editor):
  metadata, behaviour, flows, steps and log formatting;
- **Metrics** — the metrics editor for the tool's `metrics.yml`;
- **Duplicate** — on a built-in tool, copies it into your workspace to be edited
  as a whole; on a workspace tool, clones it;
- the folder button opens the tool directory, for the scripts the GUI does not
  edit.

Built-in tools show a **built-in** badge, which becomes **built-in + your
changes** once the workspace overrides something. Their own flows are displayed
read-only.

## Next

{{< section-container >}}
<div class="grid grid-cols-1 md:grid-cols-2 gap-6 my-8">

{{< card title="Run your own flows and scripts" link="/docs/custom_tools/add_flows/" >}}
Declare flows, split them into resumable steps, and add flows of your own to the tools Odatix ships.
{{< /card >}}

{{< card title="Add non supported tools" link="/docs/custom_tools/add_tools/" >}}
The full anatomy of a tool directory: `tool.yml`, variables, the job directory contract, metrics and targets.
{{< /card >}}

</div>
{{< /section-container >}}

## See also

- Tutorials: [Add a flow of your own](/tutorials/own_flows/add_flows/) ·
  [Add an unsupported tool](/tutorials/own_flows/add_tools/)
- [Configuration reference](/docs/reference/tools/) — the condensed `tool.yml` schema
- [Metrics](/docs/results/) — what a tool measures
- [Simulations](/docs/features/simulation/) · [RTL analysis](/docs/features/analysis/) · [Place & route](/docs/features/pnr/)
- [Commands reference](/docs/commands/#selecting-a-flow) — `--flow`, `--until`, `--rerun-from`
