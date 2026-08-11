---
title: "Tool Definitions (tool.yml)"
description: "Every key of an eda tool definition — commands per job type, flows, resumable steps, log formatting and metrics files."
weight: 7
---

# `tools/<tool>/tool.yml`

A `tool.yml` tells Odatix **how to invoke an eda tool**: which command runs an
fmax search, which one runs a custom-frequency synthesis, an analysis or a place
& route, and how to check the tool is installed.

Odatix ships definitions for Vivado, Design Compiler, Genus, OpenLane,
Verilator, Innovus and IC Compiler II. Your own go in `tools_path` (default
`odatix_userconfig/tools/<tool>/`).

This page is the schema. For the walkthrough, see
[Add non supported tools](/docs/tools/add_tools/) and its
[tutorial](/tutorials/own_flows/add_tools/).

{{< toc >}}

## Top-level keys

| Key | Type | Description |
|-----|------|-------------|
| `label` | string | Human-readable name, shown in the GUI. |
| `description` | string | One-line description, shown in the GUI. |
| `icon` | path | Image replacing the default pictogram in the GUI. |
| `default_flow` | string | Name of the flow the `unix` / `windows` commands belong to. Default `default`. |
| `default_metrics_file` | path | [Metrics definitions](/docs/reference/metrics/) for this tool. |
| `process_group` | bool | Run each job in its own process group, so stopping a job kills the whole tool tree. |
| `unix` / `windows` | mapping | The commands, per platform. See below. |
| `flows` | mapping | Additional [flows](#flows), keyed by name. |
| `format` | mapping | [Log formatting](#log-formatting) rules for the monitor. |

## Commands per job type

Inside `unix` (or `windows`), one key per job type. A tool can run a job type
**only if** it declares the corresponding key — which is how Verilator is
offered for analysis but never for synthesis, and Innovus for place & route
only.

| Key | Job type |
|-----|----------|
| `tool_test_command` | Installation check, run before a campaign (skipped with `-T/--trust`). |
| `fmax_synthesis_command` | `odatix fmax` |
| `custom_freq_synthesis_command` | `odatix synth` |
| `analysis_command` | `odatix analyze` |
| `pnr_command` | `odatix pnr` |
| `<job_type>_steps` | The stepped form of any of the above. See [Steps](#steps). |
| `<job_type>_session` | How the tool is opened for a job type, once for all the steps of a run. See [Sessions](#sessions). |
| `constants` | YAML anchors reused by the commands above. Not read by Odatix itself. |

A command is a string, or a list of fragments joined with spaces.

{{< code lang=yaml filename="tools/mytool/tool.yml" >}}
label: "My Tool"
default_metrics_file: "$eda_tools_path/mytool/metrics.yml"

unix:
  tool_test_command: mytool -version
  custom_freq_synthesis_command: mytool -script $script_path/synth.tcl -log $log_path/synth.log
{{< /code >}}

Every `$token` of the [target file variable list](/docs/reference/targets/#variables-usable-in-paths)
is substituted before the command runs.

## Flows

A **flow** is a way of running the same tool: a different script, different
options, sometimes a different binary — Vivado timing-oriented versus
power-oriented with clock gating, Design Compiler with `dc_shell` versus
`dcnxt_shell`. Pick one with `-f/--flow`, or from the tool's card in the GUI.

The commands declared directly under `unix` / `windows` belong to the tool's
**default flow**, named by `default_flow`. Additional flows go under `flows`.

| Key | Type | Description |
|-----|------|-------------|
| `flows.<name>.label` | string | Human-readable name, shown in the GUI. |
| `flows.<name>.description` | string | One-line description, shown in the GUI. |
| `flows.<name>.icon` | path | Optional image replacing the default pictogram. |
| `flows.<name>.metrics_file` | path | Metrics file specific to this flow (defaults to `default_metrics_file`). |
| `flows.<name>.unix` / `.windows` | mapping | The flow's own job-type commands or steps. |

{{< code lang=yaml filename="tool.yml" >}}
default_flow: standard

unix:
  tool_test_command: [...]
  fmax_synthesis_command: [...]          # commands of the "standard" flow
  custom_freq_synthesis_command: [...]

flows:
  standard:                              # metadata for the default flow
    label: "Standard"
    description: "Timing oriented synthesis and implementation"

  power_opt:                             # an additional flow
    label: "Power optimized"
    description: "Automatic clock gating and power optimization pass"
    unix:
      custom_freq_synthesis_command: [...]
{{< /code >}}

Flows of the same tool are alternatives meant to be compared, so each one runs in
its own work directory, named `<tool>@<flow>`
(`work/custom_freq_synthesis/vivado@power_opt/…`). The default flow keeps the
bare tool name, so work directories produced before flows existed keep
resolving. All flows of a tool export into that tool's single results file, told
apart by the `flow` meta key — which is what lets Odatix Explorer compare them.

A flow never falls back to another flow's commands: asking for a flow that
cannot run a job type is an error rather than a silent run of the wrong thing.

> [!NOTE]
> A flow name becomes part of a directory name, so it cannot contain `@`, `/` or
> `\`. A flow declared with such a name is ignored.

### Merging with a built-in tool

A tool can be defined in the workspace **and** in the built-in directory at the
same time: the two `tool.yml` files are merged key by key, the workspace one
winning. A `tool.yml` in `odatix_userconfig/tools/vivado/` holding only a
`flows` section therefore *adds* flows to the built-in Vivado, without copying
the rest of its definition. Tcl scripts of both directories are copied to the
work directory, the workspace ones last.

## Steps

A job type can be declared as an ordered list of **steps** instead of a single
command, with `<job_type>_steps` in place of `<job_type>_command`, so a run can
stop partway and a later one picks up where it left off.

| Key | Type | Description |
|-----|------|-------------|
| `<job_type>_steps[].name` | string | Step identifier, used by `--until` and `--rerun-from`. |
| `<job_type>_steps[].command` | string or list | What the step runs, as a whole. The step is then a process of its own. |
| `<job_type>_steps[].args` | string or list | What the step adds to the job type's [session](#sessions) instead. |
| `<job_type>_steps[].default` | bool | Marks where a run stops when `--until` is not given. The **last** step so marked wins; if none is, the whole list runs. |

A step declares either `command` or `args`, never both.

{{< code lang=yaml filename="tool.yml" >}}
unix:
  custom_freq_synthesis_steps:
    - name: synthesis
      command: ...
    - name: pnr
      default: true          # a plain run stops here
      command: ...
    - name: bitstream        # only runs when asked for
      command: ...
{{< /code >}}

Being split into steps is a property of what the tool runs, not of one flow: it
is declared in the tool's platform section, and every flow inherits it.

**Steps are merged by name.** A flow redefining a step replaces it where it
already was, keeps the inherited order, and appends steps the default flow does
not have:

{{< code lang=yaml filename="tool.yml" >}}
flows:
  power_opt:
    label: "Power optimized"
    unix:
      custom_freq_synthesis_steps:
        - name: synthesis            # "pnr" and "bitstream" are inherited
          command: ...
{{< /code >}}

Declaring `<job_type>_command` in a flow does the opposite: it replaces the
inherited steps with a single command, so a flow can run in one go where the
default flow is stepped.

### Running steps

| Option | Effect |
|--------|--------|
| `-u`, `--until <step>` | Run up to this step, inclusive. |
| `--rerun-from <step>` | Re-run this step and the following ones, even if already recorded. |
| `-o`, `--overwrite` | Redo everything from the first step. |

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix synth -t vivado --until synthesis    # post-synthesis estimates only
$ odatix synth -t vivado                      # continues to the flow's default step
$ odatix synth -t vivado --until bitstream    # goes all the way
$ odatix synth -t vivado --rerun-from pnr     # redo implementation onwards
{{< /code >}}

A job whose requested steps are all done is skipped like any cached result; a
partially done one is listed as **Partially done** in the run checklist. Steps
completed are recorded in `log/steps.yml`, and the last one reached is exported
as the `step` meta key.

> [!NOTE]
> A recorded step that no longer matches the flow stops the resume count, so
> changing a `tool.yml` re-runs from the first difference instead of trusting
> stale files.

Each step hands its state to the next through a file the tool writes —
`write_checkpoint` / `open_checkpoint` for Vivado, `write -format ddc` for Design
Compiler, `write_db` for Genus. That part lives in the tool's own scripts;
Odatix only decides which steps to run.

## Sessions

Steps declaring a whole `command` each open and close the tool once per step,
which for a licensed tool is minutes of startup thrown away at every step
boundary. A job type can instead declare **how the tool is opened**, once per
run, and let its steps declare only what they add to it:

| Key | Type | Description |
|-----|------|-------------|
| `<job_type>_session.command` | string or list | How the tool is launched. Required for the session to be used. |
| `<job_type>_session.begin` | string or list | Added right after the tool opens, before any step. Optional. |
| `<job_type>_session.end` | string or list | Added after the last step of the run, before the tool exits. Optional. |

{{< code lang=yaml filename="tool.yml" >}}
unix:
  custom_freq_synthesis_session:
    command: [vivado, -mode tcl -notrace, -log $log_path/$first_step.log]
    end:     [-source $script_path/exit.tcl]

  custom_freq_synthesis_steps:
    - name: synthesis
      args: [-source $script_path/step_synthesis.tcl]
    - name: pnr
      default: true
      args: [-source $script_path/step_pnr.tcl]
    - name: bitstream
      args: [-source $script_path/step_bitstream.tcl]
{{< /code >}}

The steps of a run that share a session are run by a **single process**: the
command above becomes

```
vivado -mode tcl -notrace -log log/synthesis.log \
  -source scripts/step_synthesis.tcl \
  -source scripts/step_pnr.tcl \
  -source scripts/step_bitstream.tcl \
  -source scripts/exit.tcl
```

Nothing else changes: `--until` and `--rerun-from` work the same, and the session
covers exactly the steps the run has left to do — a run resuming at `pnr` opens
one session on `pnr` and `bitstream` alone. Steps declaring their own `command`
keep a process each, and may be mixed with session steps in the same list.

Two variables name the steps of the process about to run, on top of the usual
ones:

| Variable | Value |
|----------|-------|
| `$first_step` | The first step the process runs. |
| `$last_step` | The last step it runs. |
| `$steps` | All of them, joined with `-`. |

Logging to `$log_path/$first_step.log` rather than a fixed name is what keeps a
resuming run from overwriting the log of the run before it.

> [!IMPORTANT]
> Odatix records the steps of a process once that process exits, so a session
> dying halfway would lose the steps it had already finished. A tool running
> steps in a session should record each one as it completes, by calling
> `odatix_step_done <name>` (defined in `_common/settings.tcl`) at the end of each
> step script. Recording a step twice is harmless.

In-memory continuation is the tool's business: within one session the design is
already loaded, so a step should skip reading back the checkpoint the previous
one wrote. The built-in Vivado steps track what the process holds and
`odatix_open_checkpoint` returns immediately when it is already the right design
— while still writing the checkpoints a *later* run would resume from.

### Steps of an fmax search

An fmax search reruns the flow at every frequency it probes, so its steps are not
a design carried forward but **searches of increasing depth**. Vivado declares
`synthesis` (converge on post-synthesis timing: fast and optimistic), `pnr`
(converge on post-route timing: what the design really reaches) and `bitstream`.
Each search starts again from the RTL — a binary search has no partial result to
continue from — so what a later step reuses is the decision you made from the
previous one's results, not its files.

### Metrics of a partial run

Metrics are exported when the run ends, whichever step it ended on, so every step
producing meaningful numbers must write the reports they are read from. The
built-in Vivado flows report after `synthesis` and after `pnr`, keeping a copy of
each under `report/<step>/`.

`step` is **not** a dimension: a job carried further replaces its own record, its
post-synthesis estimates giving way to the implemented numbers. `flow` *is* a
dimension — two flows run in separate directories and are meant to be compared.

## Log formatting

`format` maps tokens a tool's scripts print to colours and replacements in the
[Job Monitor](/docs/gui/monitor/).

{{< code lang=yaml filename="tool.yml" >}}
format:
  tags:
    bold:  ['<bold>']
    end:   ['<end>']
    red:   ['<red>']
    green: ['<green>']
  replace:
    ...
{{< /code >}}

## In the GUI

**EDA Tools** (`/tools`) lists the tools of the workspace and, separately, the
built-in ones — create, duplicate, edit flows and steps, and edit the metrics
file, all writing this YAML. See [The Odatix GUI](/docs/gui/app/).

## See also

- Guide: [Add non supported tools](/docs/tools/add_tools/) · [Add your own flows](/docs/tools/add_flows/)
- Tutorials: [Add unsupported tools](/tutorials/own_flows/add_tools/) · [Add your own flows](/tutorials/own_flows/add_flows/)
- [Target files](/docs/reference/targets/) — the devices a tool implements for.
- [Metrics files](/docs/reference/metrics/) — what a tool extracts from its reports.
