---
title: "Tools and flows"
description: "Tools and flows in Odatix, and how to add your own."
weight: 11
---

# Tools and flows

Odatix ships with ready-to-use definitions for the most common EDA tools, and
has **no hard-coded list of supported tools**: a tool is simply a directory
containing a `tool.yml`, discovered at run time. That is what makes it possible
to run Odatix on an in-house script, on a tool Odatix has never heard of, or on
the tools it ships with — but run your way.

{{< toc >}}

## Tool, flow, job type, step

Four notions are easy to confuse, and telling them apart makes the rest of this
section obvious:

| Notion | What it is | Chosen by |
|--------|-----------|-----------|
| **Tool** | A directory with a `tool.yml`: Vivado, Genus, your own script. | `-t/--tool` |
| **Job type** | What Odatix runs: an fmax search, a synthesis at given frequencies, a place & route, an RTL analysis. | the command (`odatix fmax`, `synth`, `pnr`, `analyze`) |
| **Flow** | A way of running a tool: other options, other scripts, another binary. Flows of one tool are alternatives meant to be **compared**, so each gets its own work directory and tags its results. | `-f/--flow` |
| **Step** | One stage of a flow — synthesis, place & route, bitstream — run as its own process, stoppable and resumable. | `-u/--until` |

## Tools shipped with Odatix

Each built-in tool declares the **job types** it can run. A job type is what a
command asks for; a tool that does not declare one simply cannot be selected for
that command.

{{< data-table filters="Target,Job types,Maturity" badgeRules="Job types::Fmax search=data-badge-violet|Synthesis=data-badge-blue|Place & route=data-badge-teal|RTL analysis=data-badge-amber;;Target::FPGA=data-badge-sky|ASIC=data-badge-fuchsia;;Maturity::Validated=data-badge-green|Legacy=data-badge-orange|WIP=data-badge-yellow;;License::Commercial=data-badge-orange|Open source=data-badge-lime" >}}
| Tool | Vendor | Target | Job types | Flows | Maturity | License |
|------|--------|--------|-----------|-------|----------|---------|
| **Vivado** | AMD/Xilinx | FPGA | Fmax search, Synthesis, RTL analysis | `standard`, `power_opt` | Validated | Commercial |
| **Design Compiler** | Synopsys | ASIC | Fmax search, Synthesis, RTL analysis | `dc_shell`, `dcnxt_shell` | Validated | Commercial |
| **Genus** | Cadence | ASIC | Fmax search, Synthesis, RTL analysis | `synthesis` | Validated | Commercial |
| **IC Compiler II** | Synopsys | ASIC | Place & route | `implementation` | WIP | Commercial |
| **Innovus** | Cadence | ASIC | Place & route | `implementation` | WIP | Commercial |
| **OpenLane** | OpenROAD | ASIC | Fmax search | `synthesis` | Legacy | Open source |
| **Verilator** | Veripool | Any | RTL analysis | `lint` | Validated | Open source |
{{< /data-table >}}

### Which command runs what

| Job type | Command | What it does | Tools |
|----------|---------|--------------|-------|
| **Fmax search** | `odatix fmax` | Binary search of the highest frequency the design closes timing at | Vivado, Design Compiler, Genus, OpenLane |
| **Synthesis** | `odatix synth` | Synthesis (and, on FPGA, place & route and bitstream) at the frequencies you give | Vivado, Design Compiler, Genus |
| **Place & route** | `odatix pnr` | Places & routes a netlist a *previous* synthesis job produced, possibly with another tool (`--from-tool`) | IC Compiler II, Innovus |
| **RTL analysis** | `odatix analyze` | Elaborates the RTL without synthesizing it: lint, elaboration errors, early estimates | Vivado, Design Compiler, Genus, Verilator |

Because place & route is a job type of its own, an ASIC chain is two commands
rather than one monolithic flow — and the two halves need not come from the same
vendor:

{{< code lang=bash filename="Synthesis with one tool, place & route with another" >}}
odatix synth -t design_compiler
odatix pnr   -t innovus --from-tool design_compiler
{{< /code >}}

Simulation is not in this table: it is not driven by the synthesis machinery but
by [workflows](/docs/features/workflows/), which run the commands of *any*
simulator — Verilator, GHDL, ModelSim, cocotb or a Makefile of your own.

> [!NOTE]
> Odatix never installs or bundles these tools. It runs the ones already
> installed on your machine, and each `tool.yml` declares a test command so
> `odatix` can tell you up front whether a tool is reachable.

## Three things you can add

Your tool is not in the table above, or it is but you want it run differently?
That is the normal case, not the exception:

| You want to | Add a | Read |
|-------------|-------|------|
| Run an existing tool differently — other options, other scripts, another binary, a resumable pipeline | **flow** | [Run your own flows and scripts](/docs/tools/add_flows/) |
| Run a synthesis / place & route / analysis tool Odatix does not ship | **tool** | [Add non supported tools](/docs/tools/add_tools/) |
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

## Doing it from the GUI

Everything on this page can be done without opening a text editor. `odatix-gui` →
**EDA Tools** lists the tools of your workspace and, apart, the built-in ones:

- **Create New Tool** — a new workspace tool with a minimal `tool.yml`;
- **Settings** — the [Tool Editor](/docs/tools/add_tools/#the-tool-editor):
  metadata, behaviour, flows, steps and log formatting;
- **Metrics** — the metrics editor for the tool's `metrics.yml`;
- **Duplicate** — on a built-in tool, copies it into your workspace to be edited
  as a whole; on a workspace tool, clones it;
- on a workspace tool, the folder button opens the tool directory, for the
  scripts the GUI does not edit, and the bin button deletes the tool.

Cards of tools declaring several flows list them under the name. Built-in tools
say **built-in** under theirs, which becomes **built-in + your changes** once the
workspace overrides or extends something — and in the Tool Editor, the flows
Odatix itself declares carry a **read-only** badge.

## In this section

{{< doc-cards cols="2" >}}
{{< doc-card title="Run your own flows and scripts" link="/docs/tools/add_flows/" icon="workflow" accent="#7c3aed" >}}
Declare flows, split them into resumable steps, and add flows of your own to the tools Odatix ships — without touching their built-in ones.
{{< /doc-card >}}

{{< doc-card title="Add non supported tools" link="/docs/tools/add_tools/" icon="wrench" accent="#7c3aed" >}}
The anatomy of a tool directory: `tool.yml`, variables, the job directory contract, metrics and targets — plus the Tool Editor.
{{< /doc-card >}}
{{< /doc-cards >}}
