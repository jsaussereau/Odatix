---
title: "Custom flows and scripts"
description: "Declare flows in tool.yml, split them into resumable steps, and add flows of your own to the tools Odatix ships."
weight: 3
---

# Run your own flows and scripts

> [!IMPORTANT] Requires Odatix 4.0+

A **flow** is a way of running an eda tool: different options, different scripts,
sometimes a different binary. Vivado ships a timing oriented flow and a power
oriented one; Design Compiler ships a `dc_shell` flow and a `dcnxt_shell` one.
Flows of the same tool are **alternatives meant to be compared**, so each one
runs in its own work directory and tags the results it produces.

Adding a flow is the shortest path to running your own scripts under Odatix:
you keep the tool, its metrics and its targets, and change only what runs.

{{< toc >}}

## The default flow

The commands declared directly in the `unix` / `windows` section of a `tool.yml`
belong to the tool's **default flow** — the one used when `--flow` is not given.
Its name comes from the top-level `default_flow` key (`default` when absent);
declaring it under `flows:` only attaches metadata to it.

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
{{< /code >}}

## Declaring another flow

Every other flow is an entry of the `flows` section, with its own platform
sections:

{{< code lang=yaml filename="tool.yml" >}}
flows:
  power_opt:
    label: "Power optimized"
    description: "Automatic clock gating and power optimization pass"
    unix:
      custom_freq_synthesis_command:
        - vivado -mode tcl -notrace
        - -source $script_path/init_script.tcl
        - -source $script_path/flow_power_opt.tcl
        - -source $script_path/synth_script.tcl
        - -source $script_path/exit.tcl
{{< /code >}}

A command is either a string or a list of strings; a list is joined with spaces,
which is the readable way to write a long command line.

### Flow keys

| Key | Type | Description |
|-----|------|-------------|
| `label` | string | Human-readable name, shown in the GUI. Defaults to the flow name. |
| `description` | string | One line, shown on the tool's card in the GUI. |
| `icon` | string | Optional image replacing the default pictogram. |
| `metrics_file` | string | Metrics definition file specific to this flow. Defaults to the tool's `default_metrics_file`. |
| `unix` / `windows` | dict | What this flow runs on that platform (see below). |

### What a platform section of a flow may declare

| Key | Description |
|-----|-------------|
| `tool_test_command` | Installation check. Inherited from the tool; only a flow running a *different binary* needs its own. |
| `<job_type>_command` | The job type run in one shot. |
| `<job_type>_steps` | The job type run as an ordered list of resumable steps. |
| `<job_type>_session` | How the tool is opened for the job type, once for all the steps of a run. |
| `constants` | YAML anchors, for readability only (see [Anchors](#anchors)). |

with `<job_type>` one of:

| Job type key | Run by | Steps key | Session key |
|--------------|--------|-----------|-------------|
| `fmax_synthesis_command` | `odatix fmax` | `fmax_synthesis_steps` | `fmax_synthesis_session` |
| `custom_freq_synthesis_command` | `odatix synth` | `custom_freq_synthesis_steps` | `custom_freq_synthesis_session` |
| `pnr_command` | `odatix pnr` | `pnr_steps` | `pnr_session` |
| `analysis_command` | `odatix analyze` | `analysis_steps` | `analysis_session` |

## Inheritance: a flow changes only what it says

A flow starts from the **default flow's declaration** for each job type and
overrides only what it declares. For a given job type:

- it declares **nothing** → it runs what the default flow runs;
- it declares a **`<job_type>_command`** → it runs that, in one shot, even if the
  default flow is split into steps;
- it declares **`<job_type>_steps`** → its steps are merged into the inherited
  ones **by name**;
- it declares **`<job_type>_session`** → it is merged into the inherited session
  **key by key**, so a flow changing where the log goes, or adding a script every
  session must source, says that much and keeps the steps as they are.

This is why the Vivado `power_opt` flow above is four lines and not a copy of the
whole tool: everything it does not mention still comes from `standard`.

A flow therefore supports every job type the tool supports, unless it explicitly
replaces one. Asking for a flow that cannot run a job type is an error naming the
flows that can — never a silent run of something else.

## Splitting a flow into steps

Instead of one command, a job type can declare an ordered list of **steps**, so a
run can stop at any of them and a later run picks up where it left off instead of
starting over.

{{< code lang=yaml filename="tool.yml" >}}
unix:
  custom_freq_synthesis_steps:
    - name: synthesis
      command: tclsh $script_path/step_synthesis.tcl $work_path
    - name: pnr
      default: true
      command: tclsh $script_path/step_pnr.tcl $work_path
    - name: bitstream
      command: tclsh $script_path/step_bitstream.tcl $work_path
{{< /code >}}

| Step key | Description |
|----------|-------------|
| `name` | Identifier used by `--until` and `--rerun-from`, and recorded as the `step` meta key. Required. |
| `command` | String or list, like any command. The step is then a process of its own. |
| `args` | What the step adds to the job type's [session](#running-every-step-in-one-session) instead of running a command of its own. |
| `default` | Optional. Marks the step a run stops at when it is not told where to. The **last** marked step wins; no marked step means the whole flow runs. |

Being stepped is a property of what the tool runs, not a flow of its own: every
flow of the tool inherits the split, and `--until` works the same whichever flow
is picked.

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix synth -t vivado --until pnr        # implement, no bitstream yet
$ odatix synth -t vivado                    # only runs the bitstream step
$ odatix synth -t vivado --rerun-from pnr   # redo place & route onwards
{{< /code >}}

### Merging steps by name

A flow redefining `<job_type>_steps` does **not** replace the list: steps are
merged by name, the inherited order is kept, a step of the same name is replaced
where it already was, and steps the default flow does not have are appended.

{{< code lang=yaml filename="tool.yml" >}}
flows:
  power_opt:
    unix:
      custom_freq_synthesis_steps:
        - name: synthesis            # "pnr" and "bitstream" are inherited
          command: ...
{{< /code >}}

That is the honest model of what actually differs: a power optimization pass
changes how the design is synthesized, and a checkpoint carries the result into a
place & route that has no reason to change.

> [!NOTE]
> An **fmax search** is a special case: it reruns the whole flow at every
> frequency it probes, so its steps are not a design carried forward but
> *searches of increasing depth* — converge on post-synthesis timing (fast,
> optimistic), then on post-route timing (what the design really reaches), then
> implement. A flow overriding one of them usually has to override all of them,
> since nothing is handed over between them. See
> [Steps of an fmax search](/docs/reference/tools/#steps-of-an-fmax-search).

### Running every step in one session

Steps declaring a whole `command` each open and close the tool once per step.
For Vivado that is a minute of startup thrown away at every step boundary, and
a design written to disk and read back for nothing.

Declare instead **how the tool is opened** — once per run — and let the steps
declare only what they add to it:

{{< code lang=yaml filename="tool.yml" >}}
unix:
  custom_freq_synthesis_session:
    command:
      - export LC_ALL=C; unset LANGUAGE;
      - vivado -mode tcl -notrace
      - -log $log_path/$first_step.log
    end:
      - -source $script_path/exit.tcl

  custom_freq_synthesis_steps:
    - name: synthesis
      args: [-source $script_path/step_synthesis.tcl]
    - name: pnr
      default: true
      args: [-source $script_path/step_pnr.tcl]
    - name: bitstream
      args: [-source $script_path/step_bitstream.tcl]
{{< /code >}}

The steps of a run that share a session are run by a **single process**: Vivado
opens, sources what each step adds, and exits. `--until` and `--rerun-from` are
unaffected — the session covers exactly the steps the run has left to do, so
resuming at `pnr` opens one session on `pnr` and `bitstream` alone.

Two details make this work in practice:

- **Name the log after the run, not the step.** `$first_step` and `$last_step`
  expand to the steps the process covers, so `-log $log_path/$first_step.log`
  gives one log per run instead of a shared file a resuming run overwrites.
- **Record each step as it completes.** Odatix records the steps of a process
  once it exits, so a session dying halfway would lose what it had already
  finished. Call `odatix_step_done <name>` (from `_common/settings.tcl`) at the
  end of each step script.

Steps declaring their own `command` keep a process each, and can be mixed with
session steps in the same list — which is what the built-in Vivado fmax steps do,
each being a whole search of its own.

### Handing state over between steps

Odatix decides *which* steps to run; carrying the design from one to the next is
the scripts' job. Tools do it with their own checkpoint mechanism —
`write_checkpoint` / `open_checkpoint` for Vivado, `write -format ddc` for Design
Compiler, `write_db` for Genus.

Inside one session the design is still in memory, so a step should skip reading
back what the previous one wrote. Odatix's Vivado steps track what the process
holds: `odatix_open_checkpoint` returns immediately when it is already the right
design, and the checkpoints are written anyway, since a *later* run resuming in a
fresh process has nothing else to start from.

The steps a job directory has completed are recorded in `log/steps.yml`, and the
last one reached is exported as the `step` meta key. Metrics are exported
whichever step a run ended on, so **every step producing meaningful numbers must
write the reports they are read from**.

## Variables available in commands

Commands are expanded before being run:

| Variable | Value |
|----------|-------|
| `$work_path` | The job's work directory (absolute). |
| `$script_path` | `<work_path>/scripts`, where the tool's scripts have been copied. |
| `$log_path` | `<work_path>/log`. |
| `$tool_path` | The tool's own directory (the workspace one when it exists). |
| `$eda_tools_path` | The built-in tools directory. |
| `$odatix_path` | The Odatix installation directory. |
| `$tool_install_path` | The `tool_install_path` of the target file. |
| `$clock_signal`, `$top_level_module`, `$lib_name` | Of the design being run. |
| `$source_work_path`, `$source_tool` | Place & route jobs only: the synthesis job this one continues. |
| `$first_step`, `$last_step`, `$steps` | Stepped job types only: the steps the process about to run covers. |

## Adding a flow to a built-in tool

Create a `tool.yml` under `odatix_userconfig/tools/<builtin name>/` holding
nothing but your flow. It is merged over the built-in definition, so the tool
keeps its commands, its metrics and its log formatting:

{{< code lang=yaml filename="odatix_userconfig/tools/vivado/tool.yml" >}}
flows:
  retiming:
    label: "Retiming"
    description: "Timing oriented synthesis with global retiming enabled"
    unix:
      custom_freq_synthesis_steps:
        - name: synthesis
          command:
            - export LC_ALL=C; unset LANGUAGE;
            - vivado -mode tcl -notrace
            - -log $log_path/synthesis.log
            - -source $script_path/init_script.tcl
            - -source $script_path/flow_retiming.tcl
            - -source $script_path/analyze_script.tcl
            - -source $script_path/step_synthesis.tcl
            - -source $script_path/exit.tcl
{{< /code >}}

Scripts of your own go in `odatix_userconfig/tools/vivado/tcl/`: both directories
are copied into every job directory, yours last, so `flow_retiming.tcl` sits next
to Odatix's own scripts and can `source` them.

> [!WARNING]
> Redefining a **built-in** flow, the `unix` / `windows` section of a built-in
> tool, or its `default_flow` has no effect: those keys are dropped with a
> warning. Give your flow a new name, or duplicate the tool to own all of it.

## Work directories and results

Each flow runs in `work/<job type>/<tool>@<flow>/…`; the tool's default flow
keeps the bare `<tool>` directory, so work directories produced before flows
existed keep resolving.

All the flows of a tool export into that tool's single results file, told apart
by the `flow` meta key — which is what lets Odatix Explorer plot them against
each other. The flow is also written into the job directory (`flow.txt`), so a
full re-export (`odatix res_synth`) keeps the flow of results produced earlier.

`flow` is a dimension; `step` is not. A result record is identified by the run it
comes from — its architecture, its configuration, its target, its tool and its
flow — so running the same configuration under two flows leaves **two records**,
side by side, which is exactly what makes them comparable.

`step` is recorded on the result, but it is not part of that identity. Running a
job `--until synthesis` and later resuming it to `pnr` therefore **replaces the
first record** instead of adding a second one. That is the intended behaviour:
the two runs do not describe two designs, they describe the same one measured
twice, the second time more accurately — post-synthesis estimates give way to
post-route numbers. Keeping both would mean two points where there is one, one of
them known to be obsolete, so the latest wins.

In short: to compare, use flows; going further into the steps of a flow refines a
result, it does not add one.

### Comparing the steps of a run

That leaves one question open: what if you *do* want to see what place & route
did to the post-synthesis estimate? Since both numbers belong to the same run,
they belong to the same record — as two metrics, not two records.

A metric can name the step it is extracted from. `$step` in its file then
resolves to the report directory that step wrote, and the metric is simply left
out when the job never reached that step: a run stopped at synthesis is not
missing its post-route numbers, it has not produced them.

{{< code lang=yaml filename="tools/vivado/metrics.yml" >}}
metrics:
  LUT_count_synth:
    type: regex
    step: synthesis
    settings:
      file: report/$step/utilization.rep
      pattern: "\\| (Slice|CLB) LUTs \\s*\\|\\s*([0-9]+).*"
      group_id: 2
    format: "%.0f"

  LUT_count_pnr:
    type: regex
    step: pnr
    settings:
      file: report/$step/utilization.rep
      pattern: "\\| (Slice|CLB) LUTs \\s*\\|\\s*([0-9]+).*"
      group_id: 2
    format: "%.0f"

  # Only defined on a job that ran both steps, hence error_if_missing
  LUT_pnr_delta:
    type: operation
    step: pnr
    error_if_missing: false
    settings:
      op: LUT_count_pnr - LUT_count_synth
    format: "%.0f"
{{< /code >}}

For this to work the tool's scripts have to keep a copy of the reports per step,
since each step overwrites the report files of the one before. Vivado's steps do
it through `odatix_write_reports <step>` (`step_common.tcl`), which writes the
usual `report/utilization.rep` *and* a snapshot under `report/<step>/`. The
built-in Vivado metrics use this to expose `LUT_count_synth` / `LUT_count_pnr`
and `Reg_count_synth` / `Reg_count_pnr` out of the box.

Both values end up on the same record, so Odatix Explorer plots one against the
other directly. A job resumed from synthesis to place & route keeps its
post-synthesis columns — they live in `report/synthesis/`, which place & route
does not touch — and gains the post-route ones.

> [!NOTE]
> A flow name becomes part of a directory name, so it cannot contain `@` (the
> separator), `/`, `\`, or be `.` / `..`. A flow declared with such a name is
> ignored.

## Anchors

The built-in `tool.yml` files use a `constants:` list of YAML anchors to avoid
repeating options across flows and steps:

{{< code lang=yaml filename="tool.yml" >}}
unix:
  constants:
    - &vivado_unix vivado
    - &vivado_opt_unix -mode tcl -notrace

  fmax_synthesis_command:
    - *vivado_unix
    - *vivado_opt_unix
{{< /code >}}

`constants` is not read by Odatix — it exists only so the anchors have somewhere
to be defined. Anchors are resolved when the file is loaded; the graphical editor
re-emits a flat, anchor-free `tool.yml` on save.

## From the GUI

**EDA Tools → Settings** opens the Tool Editor, whose **Flows** section mirrors
everything above: one card per flow, foldable, with its label, description, and,
per platform and per job type, a three-way choice:

| Choice | `tool.yml` equivalent |
|--------|----------------------|
| **Inherited** (on the default flow: *Not supported*) | declares nothing |
| **Command** | `<job_type>_command` |
| **Steps** | `<job_type>_session` (how the tool is opened, plus what runs on opening and on closing) followed by `<job_type>_steps`, each with its name, what it runs and a **Default** chip |

A step's text field holds its `command` when the job type opens no session, and
what it adds to the session (`args`) when it does — steps added to a job type
that declares a session join it.

One flow is marked as the default. Built-in flows appear locked; **Add a flow**
creates yours, and the duplicate button on a flow is the fastest way to start
from one that already works.

## See also

- Tutorial: [Add a flow of your own](/tutorials/own_flows/add_flows/)
- [Add non supported tools](/docs/tools/add_tools/) — when there is no tool to add a flow to
- [Configuration reference](/docs/reference/tools/#steps) — condensed schema, `--until` / `--rerun-from` semantics
- [Commands reference](/docs/commands/#selecting-a-flow)
