---
title: "Add non supported tools"
description: "The full anatomy of a tool directory: tool.yml, the job directory contract, variables, metrics and targets."
weight: 4
---

# Add non supported tools

> [!IMPORTANT] Requires Odatix 4.0+

There is no list of supported tools in Odatix's code. A tool is a **directory
containing a `tool.yml`**, discovered by scanning the workspace tools directory
and the built-in one. Adding one is therefore adding a directory — no plugin to
register, no source file to patch, no reinstall.

This page is the reference for what that directory contains. For a walkthrough,
see the tutorial [Add an unsupported tool](/tutorials/own_flows/add_tools/).

{{< toc >}}

## When to add a tool

Add a tool when you want Odatix's synthesis machinery — the parallel fmax binary
search, the frequency sweep, the targets, the per-tool metrics — to drive
something it does not ship. If what you want to run has no clock and no target,
what you want is a [workflow](/docs/features/workflows/), not a tool.

## Anatomy of a tool directory

{{< code lang=text filename="odatix_userconfig/tools/myTool/" >}}
myTool/
├── tool.yml       # required — what to run
├── metrics.yml    # what to measure (any path, see default_metrics_file)
├── analysis.yml   # how to read what its analysis reports (odatix analyze)
└── tcl/           # optional — copied into the scripts/ directory of every job
    ├── synth_script.tcl
    └── ...
{{< /code >}}

Only `tool.yml` is required. The `tcl/` directory is copied into each job's
`scripts/` directory whatever the language of what it holds — the name is
historical; shell scripts, Python and Makefiles are copied just the same.

Nothing else is registered anywhere: dropping this directory in
`odatix_userconfig/tools/` is what makes `odatix fmax -t myTool` work.

> [!NOTE]
> The tools directory is `odatix_userconfig/tools/` by default and can be moved
> with the `tools_path` key of `odatix.yml`. Directory names starting with `_` or
> `.` are never treated as tools.

## `tool.yml`

### Top-level keys

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `label` | string | the directory name | Display name in the GUI. |
| `description` | string | — | One line, shown on the tool's card. |
| `icon` | string | — | Image shown on the tool's card, relative to the GUI assets. |
| `icon_filter` | bool | `false` | Recolor the icon to follow the theme, for a monochrome logo. |
| `extends` | string | — | A tool this one is a variant of: it runs that tool's flows and scripts, and only says what differs. See [Extending a tool](/docs/reference/tools/#extending-a-tool). |
| `process_group` | bool | `true` | Run each job in its own process group, so that pausing, resuming or killing it reaches the tool and everything it started. Set to `false` for tools that manage their own process group (containers, `make` wrappers): only the job's own process -- the shell running the command -- is then signaled, and whatever the tool started on its own is left running on purpose, for the tool to stop. See [Stopping a job](#stopping-a-job). |
| `default_metrics_file` | string | `$tool_path/metrics.yml` when that file exists | Metrics definition file used at export time; use `$tool_path/metrics.yml` to point inside your own tool directory. Needed to export results: only a tool that measures nothing (an RTL linter) goes without. |
| `target_file` | string | `target_<tool>.yml` | Name of the [target definition file](#target-definition-file). |
| `default_flow` | string | `default` | Name the commands of the platform sections are known under. |
| `parameters` | dict | — | Parameters of the default flow, used in commands as `$<name>` and inherited by every flow. See [Parameters](/docs/tools/add_flows/#parameters-a-strategy-in-a-few-lines). |
| `unix` / `windows` | dict | — | What the tool runs on that platform — the commands of the default flow. |
| `flows` | dict | — | Additional flows. See [Run your own flows and scripts](/docs/tools/add_flows/). |
| `format` | dict | — | [Log formatting](#log-formatting) rules for the Job Monitor. |

### Platform sections

`unix` and `windows` hold what the tool actually runs. A tool declaring only
`unix` simply is not available on Windows, and says so with a clear error.

| Key | Description |
|-----|-------------|
| `tool_test_command` | Command run to check the tool is installed and reachable. **Required** — a missing one means the tool is not supported on that platform. It must exit non-zero when the tool is missing. |
| `fmax_synthesis_command` | Run by `odatix fmax`: search the maximum frequency of a design. |
| `custom_freq_synthesis_command` | Run by `odatix synth`: synthesize at a given frequency. |
| `pnr_command` | Run by `odatix pnr`: place & route a netlist another job synthesized. |
| `analysis_command` | Run by `odatix analyze`: lint / elaborate a design. |
| `<job_type>_steps` | The same job type as an ordered list of resumable steps, instead of a single command. |
| `constants` | YAML anchors, ignored by Odatix, for readability. |

A tool declares only the job types it can run: a linter declares
`analysis_command` alone, and is simply not offered for a synthesis.

What an analysis reports is read by the `analysis.yml` next to `tool.yml`: which
log lines are errors and warnings, and what each one is about. A tool without
one still gets the messages of the Odatix scripts; see
[Analysis definitions](/docs/reference/analysis/) to write it.

{{< code lang=yaml filename="tool.yml — a minimal, complete tool" >}}
label: "My Tool"
description: "In-house synthesis script"
process_group: True
default_metrics_file: "$tool_path/metrics.yml"
default_flow: standard

unix:
  tool_test_command: my_tool --version

  custom_freq_synthesis_command:
    - cd $work_path;
    - my_tool
    - --rtl rtl
    - --top $top_level_module
    - --clock $clock_signal
    - --script $script_path/synth.py
    - --log $log_path/synthesis.log

flows:
  standard:
    label: "Standard"
    description: "Default synthesis script"
{{< /code >}}

### Variables

Commands are expanded before being run:

| Variable | Value |
|----------|-------|
| `$work_path` | The job's work directory (absolute). |
| `$script_path` | `<work_path>/scripts` — where the tool's scripts have been copied. |
| `$log_path` | `<work_path>/log`. |
| `$tool_path` | The tool's own directory. |
| `$eda_tools_path` | The built-in tools directory. |
| `$odatix_path` | The Odatix installation directory. |
| `$rtl_path` | `<work_path>/rtl`, the design sources of the job. |
| `$report_path`, `$result_path` | `<work_path>/report`, `<work_path>/result`. |
| `$tool_install_path` | The `tool_install_path` of the target file; empty when the tool is on your `PATH`. |
| `$clock_signal` | Clock signal name of the design. |
| `$top_level_module` | Top level module name. |
| `$lib_name` | Library name of the job. |
| `$architecture` | The design and its configuration, `Counter/08bits`. |
| `$target` | The target the job runs on. |
| `$tool` | The name of the tool. |
| `$<parameter>` | A [parameter](/docs/tools/add_flows/#parameters-a-strategy-in-a-few-lines) of the flow; a list is joined with spaces. This is how a script that is not tcl gets the options of a flow. |
| `$source_work_path`, `$source_tool` | Place & route jobs only: the synthesis job this one continues. |

Commands run from the job directory (`$work_path`), so a script can read
`rtl/`, `settings.yml` or `frequency.txt` relative to it. Starting a command with
`cd $work_path;` costs nothing and keeps it right wherever it is run from, by
hand for instance.

## The job directory

Before running anything, Odatix builds one directory per job and fills it. This
is the contract between Odatix and your tool.

{{< code lang=text filename="work/custom_freq_synthesis/myTool/<target>/<architecture>/<config>/100MHz/" >}}
├── rtl/                  # the design sources, parameters already substituted
├── scripts/              # _common/ scripts, then your tool's, then the target's
│   ├── settings.tcl      # job settings, as tcl "set" statements
│   └── ...
├── log/                  # your logs, and the status files Odatix reads
├── report/               # your reports — where metrics are extracted from
├── result/               # netlists and other deliverables
├── settings.yml          # job settings, as YAML — for non-tcl tools
├── architecture.txt      # configuration name
├── target.txt            # target name
├── flow.txt              # flow the job ran with
├── frequency.txt         # "100 MHz": the target frequency
└── <constraint file>     # the constraint file named by the target file
{{< /code >}}

`frequency.txt` and the constraint file are written by Odatix before the job
runs, for a fixed-frequency synthesis. The constraint file holds a clock
constraint in SDC (`create_clock -period 10 [get_ports clock]` at 100 MHz), the
format most timing tools read; a tool sourcing `_common/init_script.tcl` (all
the built-in ones) rewrites it in its own format. An fmax search gets neither:
its frequency changes at each iteration, so your script writes them.

### Knowing what to run

Two files describe the job, in two languages. Read whichever suits your scripts:

{{< tabs >}}
{{% tab name="Tcl" %}}
`scripts/settings.tcl` starts as the shared `_common/settings.tcl` and has its
`set` statements rewritten for this job. Source it and everything is a variable:

{{< code lang=tcl filename="scripts/synth_script.tcl" >}}
source scripts/settings.tcl

# top_level_module, top_level_file, clock_signal, reset_signal
# rtl_path, script_path, report_path, log_path, result_path
# target_frequency, fmax_lower_bound, fmax_upper_bound
# constraints_file, lib_name, continue_on_error, single_thread
{{< /code >}}

`source scripts/<file>.tcl` lines are rewritten into absolute paths when the job
is prepared, so a script keeps sourcing its siblings whatever directory the tool
runs from.
{{% /tab %}}
{{% tab name="Anything else" %}}
`settings.yml`, at the root of the job directory, describes the design as
plain YAML — for tools driven by Python, shell or a Makefile:

{{< code lang=yaml filename="settings.yml" >}}
arch_name: ALU/64bits
target: xc7a100t-csg324-1
top_level_module: alu_top
top_level_file: alu_top.sv
clock_signal: i_clk
reset_signal: i_rst
rtl_path: rtl
script_path: .../scripts
report_path: .../report
log_path: .../log
target_frequency: 100
fmax_lower_bound: 50
fmax_upper_bound: 1000
constraint_filename: constraints.xdc
lib_name: WORK
param_domains: [...]
tool_install_path: ""   # also written as install_path, its former name
workspace_path: /home/me/my_workspace
job_path: /home/me/my_workspace/work/custom_freq_synthesis/my_tool/.../100MHz
{{< /code >}}

Its paths are not where your command runs: `rtl_path` is relative to the job
directory, `script_path`, `report_path` and `log_path` to the workspace;
`job_path` and `workspace_path` are absolute. Join them, or take the paths from the variables of the
command instead (`$work_path`, `$script_path`, `$log_path`, `$report_path`),
start the command with `cd $work_path;` and read `rtl/`, `report/`… relative to
it. A value left unset is `null`, or an empty string. The parameters of the flow are not in
this file: pass them to your script in the command, as `$<name>`.
{{% /tab %}}
{{< /tabs >}}

### Reporting progress

The Job Monitor reads two files under `log/`:

| File | Written by | Format |
|------|-----------|--------|
| `log/synth_status.log` | any synthesis job | `In progress: <n>%`, then `Done: 100%` when finished |
| `log/status.log` | fmax searches | `<label>: <n>% (<current>/<total>)`, then `Done: 100%` |

A run that never writes them still works; it just shows no progress bar. In tcl,
`_common/settings.tcl` provides `report_progress <percent> <file>` for exactly
this.

A job is considered successful when its command exits `0`. Odatix does not parse
your log to decide. `Done: 100%` is what tells a finished job from a stopped
one: when your command exits `0` without writing it, Odatix appends it to the
status file itself (`log/synth_status.log`, or `log/status.log` for an fmax
search), so that `odatix results` exports the job later too. A job whose status
file lacks it is skipped by `odatix results`, with a warning naming the file.

### Producing results

Metrics are extracted from the files your scripts leave behind, from paths
relative to the job directory — typically `report/…`. Whatever a step produces
must be on disk when it exits: a run's metrics are exported when it ends,
whichever step that was.

### Handing a netlist to `odatix pnr`

`odatix pnr` places & routes a design **another** job synthesized, possibly with
another tool. The handoff is three files, under these exact names, in the job's
`result/` directory:

| File | Content |
|------|---------|
| `result/netlist.v` | The synthesized netlist. |
| `result/design.sdc` | The constraints it was synthesized under. |
| `result/design.sdf` | The delays. |

Tools name their outputs as they please, so publish yours under these names at
the end of a synthesis. In tcl, `_common/settings.tcl` provides
`odatix_publish_handoff <netlist> <sdc> <sdf>` (and `odatix_require_source` for
the other end, which also exposes `$source_work_path`, `$source_netlist`,
`$source_sdc`, `$source_sdf`, `$source_tool` and `$source_flow`).

A tool that declares `pnr_command` / `pnr_steps` but is never used as a synthesis
source needs to *read* the handoff only; one that is only ever a source needs to
*write* it only.

### Stopping a job

A job runs its command through the shell. When it is killed from the Job
Monitor, or when its session ends, it receives `SIGTERM` (a break event under
Windows) and has five seconds to exit before it is killed outright. Use them to
write what is worth keeping; a tool that needs longer should not rely on them.

What the signal reaches depends on `process_group`:

- `true` (the default): the job runs in a process group of its own, and the
  whole group is signaled -- the shell, the tool, and every process the tool
  started. Pausing and resuming a job work the same way.
- `false`: the job shares the process group of the Job Monitor, so only its own
  process is signaled, never the group. With a single command the shell usually
  hands its place over to the tool, which is then what gets the signal; with
  several, the shell stops and **what the tool started keeps running**. This is
  intended: it is what `false` is for, tools that manage their own processes
  (containers, `make` wrappers), and the job log says so when it happens. Such
  a tool has to stop its processes itself.

## Metrics

`default_metrics_file` names the file describing what to extract, and from where.
Sections are per job type, plus a common one:

{{< code lang=yaml filename="metrics.yml" >}}
fmax_synthesis_metrics:
  Fmax:
    type: regex
    settings:
      file: log/frequency_search.log
      pattern: ".*Highest frequency with timing constraints being met: ([0-9_]+) MHz"
      group_id: 1
    format: "%.0f"
    unit: MHz

custom_freq_synthesis_metrics:
  Frequency:
    type: regex
    settings:
      file: frequency.txt
      pattern: "([0-9_]+) MHz"
      group_id: 1
    format: "%.0f"
    unit: MHz

pnr_metrics: {}

metrics:          # extracted whatever the job type
  Cell_count:
    type: regex
    error_if_missing: No
    settings:
      file: report/utilization.rep
      pattern: "Cell count: ([0-9_]+)"
      group_id: 1
    format: "%.0f"
{{< /code >}}

`regex`, `csv`, `yaml`, `json`, `xml` and computed `operation` extractors are all
available — see [Metrics](/docs/results/metrics/) for the full reference, and the
**Metrics** button of the GUI for a graphical editor of this file.

A flow can override the file with its own `metrics_file` — useful when one flow
reports numbers the others do not have.

## Target definition file

Targets — devices, technology nodes, PDKs — are not declared in `tool.yml` but in
`odatix_userconfig/targets/target_<tool>.yml` (or the name given by `target_file`).

{{< code lang=yaml filename="odatix_userconfig/targets/target_myTool.yml" >}}
constraint_file: "constraints.sdc"   # optional, constraints.sdc by default
tool_install_path: "~/tools/myTool"  # optional, empty: the tool is on your PATH

targets:
  - xc7a100t-csg324-1
  - xc7s25-csga225-1

# optional: copy a script into every job directory
script_copy_enable: false
script_copy_source: ""

# optional: per-target overrides
target_settings:
  xc7s25-csga225-1:
    script_copy_enable: true
    script_copy_source: "$tool_path/tcl/spartan7.tcl"
{{< /code >}}

The target name is written into `target.txt` and set in `settings.tcl` /
`settings.yml`; mapping it to a device, a library or a PDK is your scripts' job.
See [Target tool files](/docs/reference/targets/).

## Log formatting

The `format` section colorizes the tool's output in the Job Monitor:

{{< code lang=yaml filename="tool.yml" >}}
format:
  logs:                      # whole line, matched by a marker
    error:         ['ERROR:']
    crit_warning:  ['CRITICAL WARNING:']
    warning:       ['WARNING:']
    info:          ['INFO:']
    trace:         ['Command:']

  tags:                      # inline markers replaced by escape codes
    bold:  ['<bold>']
    end:   ['<end>']
    red:   ['<red>']
    green: ['<green>']

  replace:                   # regular expressions
    - "(Slack \\(VIOLATED\\))": "<red>$1<end>"
    - "(.* completed successfully)": "<green>$1<end>"
{{< /code >}}

`logs` levels are `error`, `crit_warning`, `warning`, `info` and `trace`. The
`tags` names are a fixed set of styles and colors (`bold`, `end`, `black`, `red`,
`green`, `yellow`, `blue`, `magenta`, `cyan`, `grey`, `white`, and their `light_`
variants): a tool only chooses which marker string maps to each of them.

## The Tool Editor

`odatix-gui` → **Configure** → **Tools** → **Add new tool** opens the editor on a
new tool; **Save all** creates its directory and its `tool.yml`, which names
`$tool_path/metrics.yml` as its metrics file. On an existing tool, **Settings**
opens the same editor:

| Section | Keys |
|---------|------|
| **Tool Metadata** | `label`, `description`, `icon` |
| **Behaviour** | `extends` (**Base Tool**), `process_group`, `target_file`, `default_metrics_file` |
| **Flows** | `default_flow`, `flows`, the platform sections, commands, steps and `parameters` |
| **Log Formatting** / **Log Replacements** | `format.logs`, `format.tags`, `format.replace` |

The **Metrics** button opens the metrics editor for the same tool. Scripts are
not edited in the GUI: the folder button opens the tool directory.

On a **built-in** tool the editor works as an overlay — its own flows are shown
read-only, everything else can be overridden, only what actually differs is
written, and each section has a button putting it back to the built-in state.

Picking a **Base Tool** makes the tool a variant of another one (`extends`, see
[Extending a tool](/docs/reference/tools/#extending-a-tool)): the flows of the
base tool appear, locked and marked *from &lt;tool&gt;*, and the tool only says
what differs. That is usually a parameter of its default flow — another
executable, say: **Override** `shell` there and the change applies to every flow.
Flows of its own can be added next to the inherited ones. Unsetting the base
tool keeps the tool's own flows and the parameters its default flow changed.

## Checklist

1. `odatix_userconfig/tools/<name>/tool.yml`, with `tool_test_command` and at
   least one job type command.
2. Scripts in `<name>/tcl/`, reading `scripts/settings.tcl` or `settings.yml`.
3. A `metrics.yml`, pointed at by `default_metrics_file`.
4. A `target_<name>.yml` with at least one target (`constraint_file` and
   `tool_install_path` are optional).
5. Optionally, write `log/synth_status.log` for progress, and the
   `result/netlist.v` + `design.sdc` + `design.sdf` handoff for `odatix pnr`.
6. Run it: `odatix synth -t <name>` — the tool appears in `-t`, in `odatix-gui`
   and in the results, with nothing else to declare.

## See also

- Tutorial: [Add an unsupported tool](/tutorials/own_flows/add_tools/)
- [Run your own flows and scripts](/docs/tools/add_flows/) — flows, steps and inheritance
- [Metrics](/docs/results/metrics/) · [Configuration reference](/docs/reference/) · [Commands reference](/docs/commands/)
