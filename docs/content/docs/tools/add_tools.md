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
| `process_group` | bool | `true` | Group the tool's child processes so they can be terminated together. Set to `false` for tools that manage their own process group (containers, `make` wrappers). |
| `report_path` | string | `report` | Where, relative to the job directory, the tool writes its reports. |
| `default_metrics_file` | string | — | Metrics definition file used at export time. Required in practice; use `$tool_path/metrics.yml` to point inside your own tool directory. |
| `target_file` | string | `target_<tool>.yml` | Name of the [target definition file](#target-definition-file). |
| `default_flow` | string | `default` | Name the commands of the platform sections are known under. |
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
| `$tool_install_path` | The `tool_install_path` of the target file. |
| `$clock_signal` | Clock signal name of the design. |
| `$top_level_module` | Top level module name. |
| `$lib_name` | Library name of the job. |
| `$source_work_path`, `$source_tool` | Place & route jobs only: the synthesis job this one continues. |

Commands do not run from a guaranteed working directory: start them with
`cd $work_path;`, or pass absolute paths built from the variables above.

## The job directory

Before running anything, Odatix builds one directory per job and fills it. This
is the contract between Odatix and your tool.

{{< code lang=text filename="work/custom_freq_synthesis/myTool/<target>/<config>/100MHz/" >}}
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
└── <constraint file>     # the constraint file named by the target file
{{< /code >}}

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
`settings.yml`, at the root of the job directory, holds the same information as
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
{{< /code >}}
{{% /tab %}}
{{< /tabs >}}

### Reporting progress

The Job Monitor reads two files under `log/`:

| File | Written by | Format |
|------|-----------|--------|
| `log/synth_status.log` | any synthesis job | `In progress: <n>%` — and `Done: 100%` when finished |
| `log/status.log` | fmax searches | `<label>: <n>% (<current>/<total>)` |

A run that never writes them still works; it just shows no progress bar. In tcl,
`_common/settings.tcl` provides `report_progress <percent> <file>` for exactly
this.

A job is considered successful when its command exits `0`. Odatix does not parse
your log to decide.

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
constraint_file: "constraints.xdc"
tool_install_path: "~/tools/myTool"

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

`odatix-gui` → **EDA Tools** → **Create New Tool** creates the directory and a
minimal `tool.yml`; **Settings** opens the editor:

| Section | Keys |
|---------|------|
| **Tool Metadata** | `label`, `description`, `icon` |
| **Behaviour** | `process_group`, `report_path`, `target_file`, `default_metrics_file` |
| **Flows** | `default_flow`, `flows`, the platform sections, commands and steps |
| **Log Formatting** / **Log Replacements** | `format.logs`, `format.tags`, `format.replace` |

The **Metrics** button opens the metrics editor for the same tool. Scripts are
not edited in the GUI: the folder button opens the tool directory.

On a **built-in** tool the editor works as an overlay — its own flows are shown
read-only, everything else can be overridden, only what actually differs is
written, and each section has a button putting it back to the built-in state.

## Checklist

1. `odatix_userconfig/tools/<name>/tool.yml`, with `tool_test_command` and at
   least one job type command.
2. Scripts in `<name>/tcl/`, reading `scripts/settings.tcl` or `settings.yml`.
3. A `metrics.yml`, pointed at by `default_metrics_file`.
4. A `target_<name>.yml` with a `constraint_file` and at least one target.
5. Optionally, write `log/synth_status.log` for progress, and the
   `result/netlist.v` + `design.sdc` + `design.sdf` handoff for `odatix pnr`.
6. Run it: `odatix synth -t <name>` — the tool appears in `-t`, in `odatix-gui`
   and in the results, with nothing else to declare.

## See also

- Tutorial: [Add an unsupported tool](/tutorials/own_flows/add_tools/)
- [Run your own flows and scripts](/docs/tools/add_flows/) — flows, steps and inheritance
- [Metrics](/docs/results/metrics/) · [Configuration reference](/docs/reference/) · [Commands reference](/docs/commands/)
